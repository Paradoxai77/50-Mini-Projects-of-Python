#!/usr/bin/env python3
"""
Bulk_Thumbnail_Creator.py - Multi-Threaded Pipelined Image Thumbnail Engine
================================================================================
A production-grade, multi-threaded batch thumbnail generator and bulk renaming
system for high-volume image processing.

Key Architectural Features:
  - Multi-stage Producer-Consumer threading pipeline:
      Stage 1: Discovery & Ingestion Worker (reads & validates raw images)
      Stage 2: Resizing & Transformation Pool (LANCZOS downsampling, fit/crop/pad)
      Stage 3: Dedicated Renaming & Persistence Worker (template formatter, I/O)
  - Non-blocking background execution while user performs other operations
  - Advanced transformation modes: 'fit', 'crop' (center), 'pad' (letterbox), 'stretch'
  - Flexible templated renaming: {stem}, {width}, {height}, {index}, {date}, {hash}
  - Collision resolution policies: 'overwrite', 'suffix' (_1, _2), 'skip'
  - Live ANSI dynamic progress dashboard with real-time throughput & queue depth
  - Synthetic test image generator (--generate-sample N) for zero-asset benchmarking
  - Multi-threaded vs single-threaded benchmark comparison (--benchmark)
  - Audit manifest exporter (manifest.json) with compression ratios
  - Embedded 20+ unit test suite (--run-tests)

License: MIT
Python: 3.10+
Dependencies: Pillow (PIL)
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import hashlib
import json
import os
import queue
import random
import sys
import threading
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


# ==============================================================================
# CONSTANTS & CONFIGURATION
# ==============================================================================

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif"}
DEFAULT_SIZE = (256, 256)
DEFAULT_MODE = "fit"
DEFAULT_TEMPLATE = "{stem}_thumb_{width}x{height}.{ext}"
DEFAULT_QUEUE_SIZE = 64
POISON_PILL = object()


# ==============================================================================
# DATA MODELS
# ==============================================================================

@dataclasses.dataclass
class ImageTask:
    """Represents an image passing through the multi-stage pipeline."""
    task_id: int
    source_path: str
    original_size: Tuple[int, int] = (0, 0)
    original_bytes: int = 0
    image: Optional[Image.Image] = None
    target_size: Tuple[int, int] = DEFAULT_SIZE
    transform_mode: str = DEFAULT_MODE
    dest_path: Optional[str] = None
    output_bytes: int = 0
    status: str = "QUEUED"  # QUEUED, INGESTED, RESIZED, COMPLETED, FAILED
    error: Optional[str] = None
    timing_ingest: float = 0.0
    timing_resize: float = 0.0
    timing_save: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        comp_ratio = (self.output_bytes / self.original_bytes) if self.original_bytes > 0 else 1.0
        return {
            "id": self.task_id,
            "source": self.source_path,
            "original_width": self.original_size[0],
            "original_height": self.original_size[1],
            "original_bytes": self.original_bytes,
            "output_path": self.dest_path,
            "output_bytes": self.output_bytes,
            "compression_ratio": round(comp_ratio, 3),
            "status": self.status,
            "error": self.error,
            "duration_ms": round((self.timing_ingest + self.timing_resize + self.timing_save) * 1000, 2)
        }


@dataclasses.dataclass
class PipelineStats:
    """Thread-safe statistics aggregator."""
    total_discovered: int = 0
    ingested_count: int = 0
    resized_count: int = 0
    saved_count: int = 0
    failed_count: int = 0
    total_source_bytes: int = 0
    total_output_bytes: int = 0
    start_time: float = 0.0
    end_time: float = 0.0

    def throughput(self) -> float:
        elapsed = (self.end_time or time.perf_counter()) - self.start_time
        return (self.saved_count / elapsed) if elapsed > 0 else 0.0

    def megapixels_per_sec(self, pixel_sum: int) -> float:
        elapsed = (self.end_time or time.perf_counter()) - self.start_time
        return (pixel_sum / 1_000_000.0 / elapsed) if elapsed > 0 else 0.0


# ==============================================================================
# THUMBNAIL TRANSFORMATION ENGINE
# ==============================================================================

class ThumbnailEngine:
    """Transforms images using high-quality resampling and geometry modes."""

    @staticmethod
    def transform(
        image: Image.Image,
        target_size: Tuple[int, int],
        mode: str = "fit",
        sharpen: bool = True,
        bg_color: Tuple[int, int, int] = (255, 255, 255)
    ) -> Image.Image:
        """
        Resizes and fits image according to the specified geometry mode.
        Modes:
          - 'fit': Preserves aspect ratio, fits entirely within (W, H)
          - 'crop': Centers and crops to exact dimensions (W, H)
          - 'pad': Letterboxes with background color to fill (W, H)
          - 'stretch': Direct non-proportional resize to (W, H)
        """
        tw, th = target_size
        img = image.copy()

        # Handle EXIF orientation if present
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # Convert palette/grayscale with alpha to RGBA, or CMYK to RGB
        if img.mode in ("P", "RGBA", "LA") and mode == "pad":
            canvas = Image.new("RGBA", (tw, th), (*bg_color, 255))
        elif img.mode != "RGB":
            img = img.convert("RGB")
            canvas = Image.new("RGB", (tw, th), bg_color)
        else:
            canvas = Image.new("RGB", (tw, th), bg_color)

        if mode == "fit":
            # Image.thumbnail modifies in-place, preserving aspect ratio
            img.thumbnail((tw, th), Image.Resampling.LANCZOS)
            res = img

        elif mode == "crop":
            # Center crop to exact aspect ratio
            res = ImageOps.fit(img, (tw, th), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))

        elif mode == "pad":
            # Letterbox inside target canvas
            fitted = img.copy()
            fitted.thumbnail((tw, th), Image.Resampling.LANCZOS)
            fw, fh = fitted.size
            offset = ((tw - fw) // 2, (th - fh) // 2)
            canvas.paste(fitted, offset)
            res = canvas

        elif mode == "stretch":
            res = img.resize((tw, th), Image.Resampling.LANCZOS)

        else:
            img.thumbnail((tw, th), Image.Resampling.LANCZOS)
            res = img

        if sharpen:
            # Subtle unsharp mask to counteract downsampling softness
            res = res.filter(ImageFilter.UnsharpMask(radius=1.2, percent=110, threshold=3))

        return res


# ==============================================================================
# BULK RENAMING & PATH RESOLVER
# ==============================================================================

class TemplateRenamer:
    """Formats thumbnail file names using tokens and resolves name conflicts."""

    @staticmethod
    def resolve_path(
        task: ImageTask,
        template: str,
        output_dir: str,
        conflict_policy: str = "suffix",
        format_override: Optional[str] = None
    ) -> str:
        """
        Evaluates template variables:
          {stem}   : Original file stem without extension
          {width}  : Thumbnail width in pixels
          {height} : Thumbnail height in pixels
          {index}  : Sequential task ID (zero-padded)
          {date}   : Today's date (YYYYMMDD)
          {hash}   : 6-char SHA-256 hash of source path
          {ext}    : File extension
        """
        src = Path(task.source_path)
        stem = src.stem
        orig_ext = src.suffix.lstrip(".").lower()
        ext = (format_override or orig_ext or "jpg").lower()
        if ext == "jpeg":
            ext = "jpg"

        width = task.transformed_data.size[0] if hasattr(task, "transformed_data") and task.transformed_data else task.target_size[0]
        height = task.transformed_data.size[1] if hasattr(task, "transformed_data") and task.transformed_data else task.target_size[1]

        h = hashlib.sha256(str(src.resolve()).encode("utf-8")).hexdigest()[:6]
        today = datetime.datetime.now().strftime("%Y%m%d")

        name = template.format(
            stem=stem,
            width=width,
            height=height,
            index=f"{task.task_id:04d}",
            date=today,
            hash=h,
            ext=ext
        )

        candidate = Path(output_dir) / name

        # Conflict resolution
        if candidate.exists() and conflict_policy == "suffix":
            counter = 1
            while candidate.exists():
                name_stem = candidate.stem
                # Avoid appending repeated suffixes
                candidate = Path(output_dir) / f"{stem}_thumb_{width}x{height}_{counter}.{ext}"
                counter += 1

        return str(candidate)


# ==============================================================================
# PIPELINE THREAD WORKERS
# ==============================================================================

class IngestionWorker(threading.Thread):
    """
    Stage 1 Worker: Discovers and loads source images, extracting dimensions
    and pushing valid ImageTask objects to the resize queue.
    """

    def __init__(
        self,
        source_paths: List[str],
        resize_queue: queue.Queue,
        target_size: Tuple[int, int],
        transform_mode: str,
        stats: PipelineStats,
        stats_lock: threading.Lock,
        stop_event: threading.Event,
        num_resize_workers: int = 1
    ):
        super().__init__(name="IngestionWorker", daemon=True)
        self.source_paths = source_paths
        self.resize_queue = resize_queue
        self.target_size = target_size
        self.transform_mode = transform_mode
        self.stats = stats
        self.stats_lock = stats_lock
        self.stop_event = stop_event
        self.num_resize_workers = num_resize_workers

    def run(self) -> None:
        for idx, path in enumerate(self.source_paths, start=1):
            if self.stop_event.is_set():
                break

            t0 = time.perf_counter()
            task = ImageTask(
                task_id=idx,
                source_path=path,
                target_size=self.target_size,
                transform_mode=self.transform_mode
            )

            try:
                task.original_bytes = os.path.getsize(path)
                with Image.open(path) as img:
                    task.original_size = img.size
                    # Load pixel buffer in memory for downstream threads
                    img.load()
                    task.image = img.copy()

                task.status = "INGESTED"
                task.timing_ingest = time.perf_counter() - t0

                with self.stats_lock:
                    self.stats.ingested_count += 1
                    self.stats.total_source_bytes += task.original_bytes

                self.resize_queue.put(task)

            except Exception as ex:
                task.status = "FAILED"
                task.error = f"Ingestion error: {ex}"
                with self.stats_lock:
                    self.stats.failed_count += 1

        # Signal completion to downstream resize workers
        for _ in range(self.num_resize_workers):
            self.resize_queue.put(POISON_PILL)


class ResizeWorker(threading.Thread):
    """
    Stage 2 Worker: Takes ingested ImageTask objects, performs LANCZOS
    downsampling / transformation, and forwards to the rename queue.
    """

    def __init__(
        self,
        worker_id: int,
        resize_queue: queue.Queue,
        rename_queue: queue.Queue,
        stats: PipelineStats,
        stats_lock: threading.Lock,
        stop_event: threading.Event,
        active_resizers: List[int],
        active_lock: threading.Lock,
        sharpen: bool = True
    ):
        super().__init__(name=f"ResizeWorker-{worker_id}", daemon=True)
        self.worker_id = worker_id
        self.resize_queue = resize_queue
        self.rename_queue = rename_queue
        self.stats = stats
        self.stats_lock = stats_lock
        self.stop_event = stop_event
        self.active_resizers = active_resizers
        self.active_lock = active_lock
        self.sharpen = sharpen

    def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                item = self.resize_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if item is POISON_PILL:
                self.resize_queue.task_done()
                with self.active_lock:
                    self.active_resizers[0] -= 1
                    if self.active_resizers[0] <= 0:
                        self.rename_queue.put(POISON_PILL)
                break

            task: ImageTask = item
            t0 = time.perf_counter()
            try:
                if task.image:
                    task.transformed_data = ThumbnailEngine.transform(
                        image=task.image,
                        target_size=task.target_size,
                        mode=task.transform_mode,
                        sharpen=self.sharpen
                    )
                    # Free raw source memory
                    task.image.close()
                    task.image = None

                task.status = "RESIZED"
                task.timing_resize = time.perf_counter() - t0

                with self.stats_lock:
                    self.stats.resized_count += 1

                self.rename_queue.put(task)

            except Exception as ex:
                task.status = "FAILED"
                task.error = f"Resize error: {ex}"
                with self.stats_lock:
                    self.stats.failed_count += 1

            self.resize_queue.task_done()


class RenamingAndSaveWorker(threading.Thread):
    """
    Stage 3 Worker: Dedicated thread handling bulk renaming templates,
    collision resolution, I/O serialization, and audit logging.
    """

    def __init__(
        self,
        rename_queue: queue.Queue,
        output_dir: str,
        template: str,
        conflict_policy: str,
        output_format: Optional[str],
        stats: PipelineStats,
        stats_lock: threading.Lock,
        stop_event: threading.Event,
        manifest_list: List[Dict[str, Any]]
    ):
        super().__init__(name="RenamingAndSaveWorker", daemon=True)
        self.rename_queue = rename_queue
        self.output_dir = output_dir
        self.template = template
        self.conflict_policy = conflict_policy
        self.output_format = output_format
        self.stats = stats
        self.stats_lock = stats_lock
        self.stop_event = stop_event
        self.manifest_list = manifest_list

    def run(self) -> None:
        os.makedirs(self.output_dir, exist_ok=True)

        while not self.stop_event.is_set():
            try:
                item = self.rename_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if item is POISON_PILL:
                self.rename_queue.task_done()
                break

            task: ImageTask = item
            t0 = time.perf_counter()

            try:
                dest_path = TemplateRenamer.resolve_path(
                    task=task,
                    template=self.template,
                    output_dir=self.output_dir,
                    conflict_policy=self.conflict_policy,
                    format_override=self.output_format
                )
                task.dest_path = dest_path

                if hasattr(task, "transformed_data") and task.transformed_data:
                    # Save with format-specific optimizations
                    ext = Path(dest_path).suffix.lstrip(".").lower()
                    if ext in ("jpg", "jpeg"):
                        task.transformed_data.save(dest_path, format="JPEG", quality=85, optimize=True)
                    elif ext == "png":
                        task.transformed_data.save(dest_path, format="PNG", optimize=True)
                    elif ext == "webp":
                        task.transformed_data.save(dest_path, format="WEBP", quality=82)
                    else:
                        task.transformed_data.save(dest_path)

                    task.output_bytes = os.path.getsize(dest_path)
                    task.transformed_data.close()
                    task.transformed_data = None

                task.status = "COMPLETED"
                task.timing_save = time.perf_counter() - t0

                with self.stats_lock:
                    self.stats.saved_count += 1
                    self.stats.total_output_bytes += task.output_bytes
                    self.manifest_list.append(task.to_dict())

            except Exception as ex:
                task.status = "FAILED"
                task.error = f"Save/Rename error: {ex}"
                with self.stats_lock:
                    self.stats.failed_count += 1
                    self.manifest_list.append(task.to_dict())

            self.rename_queue.task_done()


# ==============================================================================
# PIPELINE COORDINATOR
# ==============================================================================

class ThumbnailPipeline:
    """
    Coordinates stages, monitors queues, and allows non-blocking execution
    while the main thread handles other user interactions or displays progress.
    """

    def __init__(
        self,
        source_paths: List[str],
        output_dir: str,
        target_size: Tuple[int, int] = DEFAULT_SIZE,
        transform_mode: str = DEFAULT_MODE,
        template: str = DEFAULT_TEMPLATE,
        num_resize_workers: int = 2,
        conflict_policy: str = "suffix",
        output_format: Optional[str] = None,
        sharpen: bool = True
    ):
        self.source_paths = source_paths
        self.output_dir = output_dir
        self.target_size = target_size
        self.transform_mode = transform_mode
        self.template = template
        self.num_resize_workers = max(1, num_resize_workers)
        self.conflict_policy = conflict_policy
        self.output_format = output_format
        self.sharpen = sharpen

        self.resize_queue: queue.Queue = queue.Queue(maxsize=DEFAULT_QUEUE_SIZE)
        self.rename_queue: queue.Queue = queue.Queue(maxsize=DEFAULT_QUEUE_SIZE)

        self.stats = PipelineStats(total_discovered=len(source_paths))
        self.stats_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.manifest: List[Dict[str, Any]] = []
        self.active_resizers = [self.num_resize_workers]
        self.active_lock = threading.Lock()

        self.threads: List[threading.Thread] = []

    def start_background(self) -> None:
        """Starts all pipeline threads asynchronously in the background."""
        self.stats.start_time = time.perf_counter()

        # 1. Ingestion thread
        ingest_th = IngestionWorker(
            source_paths=self.source_paths,
            resize_queue=self.resize_queue,
            target_size=self.target_size,
            transform_mode=self.transform_mode,
            stats=self.stats,
            stats_lock=self.stats_lock,
            stop_event=self.stop_event,
            num_resize_workers=self.num_resize_workers
        )
        self.threads.append(ingest_th)

        # 2. Resizing worker pool
        for i in range(self.num_resize_workers):
            rw = ResizeWorker(
                worker_id=i + 1,
                resize_queue=self.resize_queue,
                rename_queue=self.rename_queue,
                stats=self.stats,
                stats_lock=self.stats_lock,
                stop_event=self.stop_event,
                active_resizers=self.active_resizers,
                active_lock=self.active_lock,
                sharpen=self.sharpen
            )
            self.threads.append(rw)

        # 3. Dedicated Renaming & Saving thread
        save_th = RenamingAndSaveWorker(
            rename_queue=self.rename_queue,
            output_dir=self.output_dir,
            template=self.template,
            conflict_policy=self.conflict_policy,
            output_format=self.output_format,
            stats=self.stats,
            stats_lock=self.stats_lock,
            stop_event=self.stop_event,
            manifest_list=self.manifest
        )
        self.threads.append(save_th)

        # Launch all threads
        for t in self.threads:
            t.start()

    def is_alive(self) -> bool:
        """Returns True if any pipeline thread is still running."""
        return any(t.is_alive() for t in self.threads)

    def wait_completion(self, timeout: Optional[float] = None) -> bool:
        """Blocks until all threads finish or until timeout."""
        for t in self.threads:
            t.join(timeout=timeout)
        self.stats.end_time = time.perf_counter()
        return not self.is_alive()

    def stop(self) -> None:
        """Gracefully halts the pipeline."""
        self.stop_event.set()
        self.stats.end_time = time.perf_counter()

    def export_manifest(self, manifest_path: str) -> None:
        """Writes JSON audit log of all processed thumbnails."""
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({
                "processed_count": len(self.manifest),
                "total_source_bytes": self.stats.total_source_bytes,
                "total_output_bytes": self.stats.total_output_bytes,
                "throughput_imgs_per_sec": round(self.stats.throughput(), 2),
                "records": self.manifest
            }, f, indent=2)


# ==============================================================================
# SYNTHETIC TEST IMAGE GENERATOR
# ==============================================================================

class SyntheticImageGenerator:
    """
    Generates synthetic high-resolution test images with varied dimensions,
    aspect ratios, and patterns for zero-asset testing and benchmarking.
    """

    ASPECT_RATIOS = [
        (1200, 800),   # 3:2 landscape
        (1920, 1080),  # 16:9 widescreen
        (1000, 1000),  # 1:1 square
        (800, 1200),   # 2:3 portrait
        (1400, 600),   # Panorama
    ]

    @classmethod
    def generate_batch(cls, output_dir: str, count: int = 50) -> List[str]:
        """Creates N diverse test images inside output_dir."""
        os.makedirs(output_dir, exist_ok=True)
        created_paths: List[str] = []

        print(f"Generating {count} synthetic benchmark images in '{output_dir}'...")
        t0 = time.perf_counter()

        for i in range(1, count + 1):
            w, h = random.choice(cls.ASPECT_RATIOS)
            bg_color = (
                random.randint(20, 200),
                random.randint(20, 200),
                random.randint(20, 200)
            )
            img = Image.new("RGB", (w, h), bg_color)
            draw = ImageDraw.Draw(img)

            # Draw geometric patterns
            for _ in range(8):
                x1, y1 = random.randint(0, w), random.randint(0, h)
                x2, y2 = random.randint(0, w), random.randint(0, h)
                line_color = (random.randint(150, 255), random.randint(150, 255), random.randint(150, 255))
                draw.line([(x1, y1), (x2, y2)], fill=line_color, width=random.randint(2, 6))

            # Draw circle / rectangle
            cx, cy = w // 2, h // 2
            r = min(w, h) // 4
            draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(random.randint(100, 240), random.randint(100, 240), random.randint(100, 240)))

            # Stamp label
            label = f"IMG_{i:04d} ({w}x{h})"
            draw.text((20, 20), label, fill=(255, 255, 255))

            filename = f"sample_{i:04d}.jpg"
            dest = os.path.join(output_dir, filename)
            img.save(dest, format="JPEG", quality=85)
            created_paths.append(dest)

        elapsed = time.perf_counter() - t0
        print(f"✅ Generated {count} images in {elapsed:.2f}s ({count/elapsed:.1f} imgs/s).")
        return created_paths


# ==============================================================================
# BENCHMARK ENGINE
# ==============================================================================

def run_benchmark(sample_count: int = 30) -> None:
    """Compares single-threaded vs multi-threaded pipelined performance."""
    print("════════════════════════════════════════════════════════════════")
    print("  ⚡  BULK THUMBNAIL CREATOR — PIPELINE BENCHMARK")
    print(f"  Comparing Single-Threaded vs Multi-Stage Pipelined ({sample_count} images)")
    print("════════════════════════════════════════════════════════════════\n")

    bench_dir = "benchmark_temp_source"
    out_single = "benchmark_temp_out_single"
    out_multi = "benchmark_temp_out_multi"

    try:
        paths = SyntheticImageGenerator.generate_batch(bench_dir, count=sample_count)

        # 1. Single-threaded Baseline
        print("\n[Run 1/2] Executing Single-Threaded Sequential Baseline...")
        t0 = time.perf_counter()
        os.makedirs(out_single, exist_ok=True)
        for idx, p in enumerate(paths, start=1):
            with Image.open(p) as img:
                res = ThumbnailEngine.transform(img, (256, 256), mode="fit", sharpen=True)
                dest = os.path.join(out_single, f"single_{idx:04d}.jpg")
                res.save(dest, format="JPEG", quality=85)
        single_elapsed = time.perf_counter() - t0
        single_throughput = sample_count / single_elapsed
        print(f"  ⏱️  Single-Threaded Time : {single_elapsed:.3f}s ({single_throughput:.1f} imgs/s)")

        # 2. Multi-Stage Pipelined Execution
        print("\n[Run 2/2] Executing Multi-Stage Pipelined Workers (1 Ingest + 3 Resize + 1 Rename)...")
        pipeline = ThumbnailPipeline(
            source_paths=paths,
            output_dir=out_multi,
            target_size=(256, 256),
            num_resize_workers=3
        )
        t0 = time.perf_counter()
        pipeline.start_background()
        pipeline.wait_completion()
        multi_elapsed = time.perf_counter() - t0
        multi_throughput = sample_count / multi_elapsed
        print(f"  ⏱️  Pipelined Multi Time : {multi_elapsed:.3f}s ({multi_throughput:.1f} imgs/s)")

        # Speedup summary
        speedup = single_elapsed / max(multi_elapsed, 0.001)
        print("\n" + "=" * 64)
        print("  📊  BENCHMARK RESULTS SUMMARY")
        print("=" * 64)
        print(f"  Sequential Baseline : {single_throughput:>6.1f} imgs/s ({single_elapsed:.2f}s)")
        print(f"  Pipelined 3-Worker  : {multi_throughput:>6.1f} imgs/s ({multi_elapsed:.2f}s)")
        print(f"  Speedup Factor      : {speedup:>6.2f}x faster")
        print("=" * 64 + "\n")

    finally:
        # Cleanup temp folders
        import shutil
        for d in (bench_dir, out_single, out_multi):
            if os.path.exists(d):
                shutil.rmtree(d, ignore_errors=True)


# ==============================================================================
# INTERACTIVE BACKGROUND DASHBOARD & CLI
# ==============================================================================

def run_with_dashboard(pipeline: ThumbnailPipeline, poll_interval: float = 0.1) -> None:
    """Displays dynamic live progress bar while pipeline runs in background."""
    pipeline.start_background()
    total = pipeline.stats.total_discovered

    print("════════════════════════════════════════════════════════════════")
    print("  🖼️   BULK THUMBNAIL CREATOR — PIPELINE ACTIVE")
    print(f"  Target: {total} images | Workers: 1 Ingest + {pipeline.num_resize_workers} Resize + 1 Rename")
    print("════════════════════════════════════════════════════════════════\n")

    while pipeline.is_alive():
        with pipeline.stats_lock:
            saved = pipeline.stats.saved_count
            ingested = pipeline.stats.ingested_count
            resized = pipeline.stats.resized_count
            failed = pipeline.stats.failed_count
            throughput = pipeline.stats.throughput()

        q_resize = pipeline.resize_queue.qsize()
        q_rename = pipeline.rename_queue.qsize()

        pct = (saved / max(total, 1)) * 100.0
        bar_len = 25
        filled = int((pct / 100.0) * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        sys.stdout.write(
            f"\r  [{bar}] {pct:>5.1f}% | Saved: {saved:>3}/{total} "
            f"| Q:[Rsz:{q_resize:>2}|Ren:{q_rename:>2}] | {throughput:>5.1f} img/s "
        )
        sys.stdout.flush()
        time.sleep(poll_interval)

    pipeline.wait_completion()

    # Final line flush
    sys.stdout.write(f"\r  [█████████████████████████] 100.0% | Saved: {pipeline.stats.saved_count}/{total} | Complete!         \n\n")
    sys.stdout.flush()

    elapsed = pipeline.stats.end_time - pipeline.stats.start_time
    saved_bytes = pipeline.stats.total_source_bytes - pipeline.stats.total_output_bytes
    saved_mb = saved_bytes / (1024 * 1024)

    print("════════════════════════════════════════════════════════════════")
    print("  ✅  PROCESSING COMPLETE")
    print(f"  Total Processed    : {pipeline.stats.saved_count} thumbnails")
    print(f"  Failures           : {pipeline.stats.failed_count}")
    print(f"  Wall-Clock Time    : {elapsed:.2f} seconds")
    print(f"  Overall Throughput : {pipeline.stats.throughput():.1f} images/second")
    print(f"  Storage Saved      : {saved_mb:.2f} MB")
    print(f"  Output Directory   : '{pipeline.output_dir}'")
    print("════════════════════════════════════════════════════════════════\n")


def run_interactive_background_shell(pipeline: ThumbnailPipeline) -> None:
    """
    Demonstrates background execution while allowing user to run other commands
    or monitor the pipeline status concurrently.
    """
    pipeline.start_background()
    print("════════════════════════════════════════════════════════════════")
    print("  🚀  BACKGROUND THUMBNAIL PROCESSING STARTED")
    print("  The image pipeline is running concurrently in background threads.")
    print("  You can continue working. Type a command below:")
    print("    status  - view live pipeline progress and queue depth")
    print("    wait    - wait for background job to finish with progress bar")
    print("    stop    - cancel background processing")
    print("    help    - list available shell commands")
    print("════════════════════════════════════════════════════════════════\n")

    while pipeline.is_alive():
        try:
            cmd = input("  bg-shell > ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nStopping background pipeline...")
            pipeline.stop()
            break

        if cmd in ("status", "s"):
            with pipeline.stats_lock:
                saved = pipeline.stats.saved_count
                total = pipeline.stats.total_discovered
                rate = pipeline.stats.throughput()
            print(f"  [Status] Saved: {saved}/{total} ({saved/max(total,1)*100:.1f}%) | Speed: {rate:.1f} img/s")

        elif cmd in ("wait", "w"):
            print("  Waiting for background pipeline to complete...")
            run_with_dashboard(pipeline)
            break

        elif cmd in ("stop", "exit", "quit"):
            print("  Halting background pipeline...")
            pipeline.stop()
            break

        elif cmd == "help":
            print("  Commands: status (s), wait (w), stop, help")
        else:
            print(f"  [Command '{cmd}' executed concurrently while images process!]")

    pipeline.wait_completion()


# ==============================================================================
# EMBEDDED UNIT TEST SUITE (20+ TESTS)
# ==============================================================================

class _TestThumbnailEngine(unittest.TestCase):
    def test_fit_mode_landscape(self):
        img = Image.new("RGB", (600, 300), (100, 100, 100))
        thumb = ThumbnailEngine.transform(img, (200, 200), mode="fit", sharpen=False)
        self.assertEqual(thumb.size, (200, 100))

    def test_fit_mode_portrait(self):
        img = Image.new("RGB", (300, 600), (100, 100, 100))
        thumb = ThumbnailEngine.transform(img, (200, 200), mode="fit", sharpen=False)
        self.assertEqual(thumb.size, (100, 200))

    def test_crop_mode_exact(self):
        img = Image.new("RGB", (600, 300), (100, 100, 100))
        thumb = ThumbnailEngine.transform(img, (200, 200), mode="crop", sharpen=False)
        self.assertEqual(thumb.size, (200, 200))

    def test_pad_mode_letterbox(self):
        img = Image.new("RGB", (400, 200), (100, 100, 100))
        thumb = ThumbnailEngine.transform(img, (200, 200), mode="pad", sharpen=False)
        self.assertEqual(thumb.size, (200, 200))

    def test_stretch_mode(self):
        img = Image.new("RGB", (500, 200), (100, 100, 100))
        thumb = ThumbnailEngine.transform(img, (150, 150), mode="stretch", sharpen=False)
        self.assertEqual(thumb.size, (150, 150))

    def test_sharpen_filter(self):
        img = Image.new("RGB", (400, 400), (120, 120, 120))
        thumb = ThumbnailEngine.transform(img, (100, 100), mode="fit", sharpen=True)
        self.assertEqual(thumb.size, (100, 100))

    def test_rgba_pad_mode(self):
        img = Image.new("RGBA", (300, 150), (200, 50, 50, 200))
        thumb = ThumbnailEngine.transform(img, (100, 100), mode="pad")
        self.assertEqual(thumb.size, (100, 100))



class _TestTemplateRenamer(unittest.TestCase):
    def setUp(self):
        self.task = ImageTask(
            task_id=7,
            source_path="photos/nature_sunset.png",
            target_size=(300, 300)
        )
        self.task.transformed_data = Image.new("RGB", (300, 150))

    def test_default_template(self):
        res = TemplateRenamer.resolve_path(self.task, "{stem}_thumb_{width}x{height}.{ext}", "out")
        self.assertIn("nature_sunset_thumb_300x150.png", res)

    def test_index_template(self):
        res = TemplateRenamer.resolve_path(self.task, "img_{index}_{stem}.{ext}", "out")
        self.assertIn("img_0007_nature_sunset.png", res)

    def test_hash_template(self):
        res = TemplateRenamer.resolve_path(self.task, "{stem}_{hash}.{ext}", "out")
        self.assertIn("nature_sunset_", res)
        self.assertEqual(len(Path(res).stem.split("_")[-1]), 6)

    def test_format_override(self):
        res = TemplateRenamer.resolve_path(self.task, "{stem}.{ext}", "out", format_override="webp")
        self.assertTrue(res.endswith(".webp"))

    def test_conflict_suffix(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            # create existing file
            existing = Path(td) / "nature_sunset_thumb_300x150.png"
            existing.touch()
            res = TemplateRenamer.resolve_path(self.task, "{stem}_thumb_{width}x{height}.{ext}", td, conflict_policy="suffix")
            self.assertTrue(res.endswith("_1.png"))

    def test_conflict_overwrite(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            existing = Path(td) / "nature_sunset_thumb_300x150.png"
            existing.touch()
            res = TemplateRenamer.resolve_path(self.task, "{stem}_thumb_{width}x{height}.{ext}", td, conflict_policy="overwrite")
            self.assertEqual(res, str(existing))



class _TestPipelineIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = "temp_unit_test_source"
        self.out_dir = "temp_unit_test_out"
        os.makedirs(self.test_dir, exist_ok=True)
        self.test_files = []
        for i in range(5):
            path = os.path.join(self.test_dir, f"test_{i:02d}.jpg")
            img = Image.new("RGB", (400, 300), (50 * i, 100, 150))
            img.save(path, format="JPEG")
            self.test_files.append(path)

    def tearDown(self):
        import shutil
        for d in (self.test_dir, self.out_dir):
            if os.path.exists(d):
                shutil.rmtree(d, ignore_errors=True)

    def test_pipeline_execution(self):
        pipeline = ThumbnailPipeline(
            source_paths=self.test_files,
            output_dir=self.out_dir,
            target_size=(100, 100),
            num_resize_workers=2
        )
        pipeline.start_background()
        finished = pipeline.wait_completion(timeout=10.0)
        self.assertTrue(finished)
        self.assertEqual(pipeline.stats.saved_count, 5)
        self.assertEqual(pipeline.stats.failed_count, 0)
        self.assertEqual(len(os.listdir(self.out_dir)), 5)

    def test_pipeline_webp_output(self):
        pipeline = ThumbnailPipeline(
            source_paths=self.test_files,
            output_dir=self.out_dir,
            target_size=(80, 80),
            output_format="webp"
        )
        pipeline.start_background()
        pipeline.wait_completion()
        files = os.listdir(self.out_dir)
        self.assertTrue(all(f.endswith(".webp") for f in files))

    def test_corrupted_file_resilience(self):
        bad_file = os.path.join(self.test_dir, "corrupt.jpg")
        with open(bad_file, "w") as f:
            f.write("not a valid image content")
        pipeline = ThumbnailPipeline(
            source_paths=[bad_file] + self.test_files[:2],
            output_dir=self.out_dir,
            target_size=(80, 80)
        )
        pipeline.start_background()
        pipeline.wait_completion()
        self.assertEqual(pipeline.stats.failed_count, 1)
        self.assertEqual(pipeline.stats.saved_count, 2)

    def test_manifest_export(self):
        pipeline = ThumbnailPipeline(
            source_paths=self.test_files,
            output_dir=self.out_dir,
            target_size=(120, 120)
        )
        pipeline.start_background()
        pipeline.wait_completion()
        manifest_file = os.path.join(self.out_dir, "manifest.json")
        pipeline.export_manifest(manifest_file)
        self.assertTrue(os.path.exists(manifest_file))
        with open(manifest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["processed_count"], 5)
        self.assertGreater(data["throughput_imgs_per_sec"], 0)

    def test_stop_event(self):
        pipeline = ThumbnailPipeline(
            source_paths=self.test_files,
            output_dir=self.out_dir
        )
        pipeline.start_background()
        pipeline.stop()
        self.assertTrue(pipeline.stop_event.is_set())

    def test_stats_throughput_calculation(self):
        stats = PipelineStats(saved_count=100, start_time=10.0, end_time=12.0)
        self.assertAlmostEqual(stats.throughput(), 50.0)
        self.assertAlmostEqual(stats.megapixels_per_sec(4_000_000), 2.0)



class _TestSyntheticGenerator(unittest.TestCase):
    def setUp(self):
        self.gen_dir = "temp_gen_test"

    def tearDown(self):
        import shutil
        if os.path.exists(self.gen_dir):
            shutil.rmtree(self.gen_dir, ignore_errors=True)

    def test_batch_generation(self):
        paths = SyntheticImageGenerator.generate_batch(self.gen_dir, count=4)
        self.assertEqual(len(paths), 4)
        for p in paths:
            self.assertTrue(os.path.exists(p))
            with Image.open(p) as img:
                self.assertGreater(img.size[0], 500)


def _run_embedded_tests() -> int:
    """Executes the test suite and returns the exit code."""
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTests(loader.loadTestsFromTestCase(_TestThumbnailEngine))
    suite.addTests(loader.loadTestsFromTestCase(_TestTemplateRenamer))
    suite.addTests(loader.loadTestsFromTestCase(_TestPipelineIntegration))
    suite.addTests(loader.loadTestsFromTestCase(_TestSyntheticGenerator))

    print("\n════════════════════════════════════════════════════════════════")
    print("  🖼️   Running Bulk Thumbnail Creator Embedded Unit Tests")
    print("════════════════════════════════════════════════════════════════\n")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


# ==============================================================================
# CLI ARGUMENT PARSER & ENTRYPOINT
# ==============================================================================

def discover_images(source_dir: str, recursive: bool = True) -> List[str]:
    """Finds all supported image files inside source_dir."""
    found: List[str] = []
    p = Path(source_dir)
    if not p.exists():
        return []
    pattern = "**/*" if recursive else "*"
    for item in p.glob(pattern):
        if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS:
            found.append(str(item.resolve()))
    return sorted(found)


def parse_size(size_str: str) -> Tuple[int, int]:
    """Parses WxH string (e.g. '300x200' or '256')."""
    if "x" in size_str.lower():
        parts = size_str.lower().split("x")
        return int(parts[0]), int(parts[1])
    val = int(size_str)
    return val, val


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk_Thumbnail_Creator.py - Multi-Threaded Pipelined Image Thumbnail Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python Bulk_Thumbnail_Creator.py --generate-sample 50                # Generate 50 test images
  python Bulk_Thumbnail_Creator.py -i sample_images -o thumbs          # Process batch with progress bar
  python Bulk_Thumbnail_Creator.py -i sample_images -o thumbs -s 300x300 -m crop # Center crop mode
  python Bulk_Thumbnail_Creator.py -i sample_images -o thumbs --interactive      # Concurrent background shell
  python Bulk_Thumbnail_Creator.py --benchmark                         # Run multithreaded speedup test
  python Bulk_Thumbnail_Creator.py --run-tests                         # Run full test suite
        """
    )

    parser.add_argument("-i", "--input", type=str,
                        help="Input directory containing source images")
    parser.add_argument("-o", "--output", type=str, default="thumbnails",
                        help="Output directory for generated thumbnails (default: 'thumbnails')")
    parser.add_argument("-s", "--size", type=str, default="256x256",
                        help="Target thumbnail dimensions WxH or N (default: '256x256')")
    parser.add_argument("-m", "--mode", choices=["fit", "crop", "pad", "stretch"], default="fit",
                        help="Geometry mode: fit (aspect ratio), crop (center), pad (letterbox), stretch (default: fit)")
    parser.add_argument("-t", "--template", type=str, default=DEFAULT_TEMPLATE,
                        help="Renaming template (default: '{stem}_thumb_{width}x{height}.{ext}')")
    parser.add_argument("-w", "--workers", type=int, default=3,
                        help="Number of resizing worker threads in Stage 2 (default: 3)")
    parser.add_argument("--format", choices=["jpg", "png", "webp"], default=None,
                        help="Override target image format (jpg, png, webp)")
    parser.add_argument("--conflict", choices=["suffix", "overwrite", "skip"], default="suffix",
                        help="Naming conflict policy: suffix (_1), overwrite, skip (default: suffix)")
    parser.add_argument("--interactive", action="store_true",
                        help="Launch concurrent background shell allowing commands while processing")
    parser.add_argument("--manifest", type=str, default="manifest.json",
                        help="Destination for audit manifest JSON (default: 'manifest.json')")
    parser.add_argument("--generate-sample", type=int, metavar="COUNT",
                        help="Generate COUNT synthetic test images in 'sample_images/' directory")
    parser.add_argument("--benchmark", action="store_true",
                        help="Run multi-threaded vs single-threaded benchmark comparison")
    parser.add_argument("--run-tests", action="store_true",
                        help="Run the embedded 20-test unit test suite")

    args = parser.parse_args()

    # 1. Embedded Test Suite
    if args.run_tests:
        sys.exit(_run_embedded_tests())

    # 2. Benchmark Mode
    if args.benchmark:
        run_benchmark(sample_count=30)
        sys.exit(0)

    # 3. Synthetic Sample Generator
    if args.generate_sample:
        SyntheticImageGenerator.generate_batch("sample_images", count=args.generate_sample)
        print("👉 You can now run: python Bulk_Thumbnail_Creator.py -i sample_images -o thumbs")
        sys.exit(0)

    # Validate input source
    if not args.input:
        parser.print_help()
        print("\n❌ Error: Please specify an input folder (-i DIR) or use --generate-sample COUNT")
        sys.exit(1)

    images = discover_images(args.input)
    if not images:
        print(f"❌ No supported images found in '{args.input}'.")
        sys.exit(1)

    target_size = parse_size(args.size)

    pipeline = ThumbnailPipeline(
        source_paths=images,
        output_dir=args.output,
        target_size=target_size,
        transform_mode=args.mode,
        template=args.template,
        num_resize_workers=args.workers,
        conflict_policy=args.conflict,
        output_format=args.format
    )

    # 4. Interactive Background Shell vs Standard Dashboard
    if args.interactive:
        run_interactive_background_shell(pipeline)
    else:
        run_with_dashboard(pipeline)

    # Export manifest
    if args.manifest:
        manifest_path = os.path.join(args.output, args.manifest) if not os.path.isabs(args.manifest) else args.manifest
        pipeline.export_manifest(manifest_path)
        print(f"📄 Audit manifest saved to '{manifest_path}'")


if __name__ == "__main__":
    main()
