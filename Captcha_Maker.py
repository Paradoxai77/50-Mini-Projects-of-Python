#!/usr/bin/env python3
"""
Captcha_Maker.py - Production-Grade CAPTCHA Engine & Human Verification System
================================================================================
A feature-packed, multi-modal CAPTCHA generator and verification framework.
Supports:
  - Sinusoidal wave-distorted image CAPTCHAs (Text & Arithmetic modes)
  - Procedural noise injection (Bézier curves, salt-and-pepper speckles, blur)
  - 24-bit TrueColor ANSI half-block terminal preview
  - Pure-Python synthesized WAV audio CAPTCHAs for accessibility
  - Vector SVG rendering (zero-dependency fallback)
  - Stateless HMAC-SHA256 cryptographic verification tokens (anti-replay TTL)
  - Standalone self-contained HTML5 verification form generator
  - Interactive CLI verification challenge
  - Batch dataset generator with manifest.json (for ML / OCR benchmarks)
  - Embedded 20+ unit test suite (--run-tests)

License: MIT
Python: 3.10+
Dependencies: Pillow (optional for PNG; fallback SVG included), Standard Library
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import hashlib
import hmac
import io
import json
import math
import os
import random
import secrets
import struct
import sys
import time
import unittest
import wave
from typing import Dict, List, Optional, Tuple

# Optional Pillow import with graceful fallback
try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

# ==============================================================================
# CONSTANTS & CONFIGURATION
# ==============================================================================

DEFAULT_SECRET = "agy-captcha-secret-key-change-in-production-2026"
DEFAULT_TTL_SECONDS = 120
DEFAULT_WIDTH = 300
DEFAULT_HEIGHT = 100
DEFAULT_LENGTH = 5

# Confusing characters: 0 (zero), O (capital o), 1 (one), I (capital i), l (small L), 5, S, 2, Z
AMBIGUOUS_CHARS = set("0O1Il5S2Z8B")
ALPHABET_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
ALPHABET_LOWER = "abcdefghjkmnpqrstuvwxyz"
DIGITS = "23456789"
DEFAULT_CHARSET = ALPHABET_UPPER + DIGITS

# System fonts search list for cross-platform support
SYSTEM_FONTS = [
    "arial.ttf", "calibri.ttf", "consola.ttf", "verdana.ttf", "cour.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

# ==============================================================================
# DATA MODELS
# ==============================================================================

@dataclasses.dataclass
class CaptchaChallenge:
    """Represents a generated CAPTCHA challenge."""
    challenge_id: str
    mode: str                    # 'text' | 'math' | 'audio'
    display_text: str            # Text shown to user (e.g. "8 + 5 = ?" or "W9KF4")
    solution: str                # Expected answer string (e.g. "13" or "W9KF4")
    token: str                   # Stateless HMAC verification token
    created_at: float
    ttl_seconds: int
    image_bytes: Optional[bytes] = None
    audio_bytes: Optional[bytes] = None
    svg_string: Optional[str] = None
    metrics: Dict[str, float] = dataclasses.field(default_factory=dict)


# ==============================================================================
# CRYPTOGRAPHIC STATELESS TOKEN ENGINE (HMAC-SHA256)
# ==============================================================================

class StatelessTokenEngine:
    """
    Generates and validates tamper-proof, replay-resistant verification tokens
    without requiring server-side session or database storage.
    """

    @staticmethod
    def generate_token(
        solution: str,
        secret: str = DEFAULT_SECRET,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        case_sensitive: bool = False
    ) -> str:
        """
        Creates a base64-encoded token containing salt, expiration timestamp,
        and an HMAC signature of the solution.
        """
        salt = secrets.token_hex(8)
        exp = int(time.time()) + ttl_seconds
        norm_sol = solution.strip() if case_sensitive else solution.strip().upper()
        
        # Digest of salt + solution
        sol_digest = hashlib.sha256(f"{salt}:{norm_sol}".encode("utf-8")).hexdigest()
        payload = f"{salt}:{exp}:{sol_digest}"
        
        sig = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        token_str = f"{payload}:{sig}"
        return base64.urlsafe_b64encode(token_str.encode("utf-8")).decode("utf-8")

    @staticmethod
    def verify_token(
        token: str,
        user_input: str,
        secret: str = DEFAULT_SECRET,
        case_sensitive: bool = False
    ) -> Tuple[bool, str]:
        """
        Verifies a user's answer against the signed token.
        Returns: (is_valid, reason_message)
        """
        try:
            raw = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
            parts = raw.split(":")
            if len(parts) != 4:
                return False, "Invalid token structure"
            salt, exp_str, sol_digest, sig = parts
            exp = int(exp_str)
        except Exception:
            return False, "Malformed or undecodable token"

        # Check signature authenticity
        payload = f"{salt}:{exp}:{sol_digest}"
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(sig, expected_sig):
            return False, "Token signature verification failed (tampered token)"

        # Check expiration
        now = int(time.time())
        if now > exp:
            return False, f"Token expired ({now - exp}s ago). Please request a fresh CAPTCHA."

        # Check solution
        norm_input = user_input.strip() if case_sensitive else user_input.strip().upper()
        candidate_digest = hashlib.sha256(f"{salt}:{norm_input}".encode("utf-8")).hexdigest()

        if not hmac.compare_digest(candidate_digest, sol_digest):
            return False, "Incorrect solution. Verification failed."

        return True, "Verification successful! Human identity confirmed."


# ==============================================================================
# CHALLENGE GENERATORS (TEXT & MATH)
# ==============================================================================

class ChallengeSynthesizer:
    """Generates random strings and math equations for CAPTCHA challenges."""

    @staticmethod
    def generate_text(
        length: int = DEFAULT_LENGTH,
        charset: str = DEFAULT_CHARSET,
        filter_ambiguous: bool = True
    ) -> str:
        """Draws characters using secrets.choice, optionally filtering ambiguous glyphs."""
        pool = charset
        if filter_ambiguous:
            filtered = "".join(c for c in charset if c not in AMBIGUOUS_CHARS)
            if filtered:
                pool = filtered
        return "".join(secrets.choice(pool) for _ in range(length))

    @staticmethod
    def generate_math(difficulty: str = "medium") -> Tuple[str, str]:
        """
        Generates an arithmetic equation challenge.
        Returns: (display_equation, solution_as_string)
        """
        if difficulty == "easy":
            a = random.randint(1, 9)
            b = random.randint(1, 9)
            op = random.choice(["+", "-"])
            if op == "-" and a < b:
                a, b = b, a
            ans = a + b if op == "+" else a - b
            return f"{a} {op} {b} = ?", str(ans)

        elif difficulty == "hard":
            op = random.choice(["+", "-", "*"])
            if op == "*":
                a = random.randint(3, 12)
                b = random.randint(3, 12)
                ans = a * b
            elif op == "+":
                a = random.randint(15, 99)
                b = random.randint(15, 99)
                ans = a + b
            else:
                a = random.randint(25, 99)
                b = random.randint(10, a)
                ans = a - b
            return f"{a} {op} {b} = ?", str(ans)

        else: # medium
            op = random.choice(["+", "-", "*"])
            if op == "*":
                a = random.randint(2, 9)
                b = random.randint(2, 9)
                ans = a * b
            elif op == "+":
                a = random.randint(10, 49)
                b = random.randint(5, 30)
                ans = a + b
            else:
                a = random.randint(15, 60)
                b = random.randint(5, a)
                ans = a - b
            return f"{a} {op} {b} = ?", str(ans)


# ==============================================================================
# VISUAL DISTORTION & IMAGE ENGINE (PILLOW)
# ==============================================================================

class CaptchaImageEngine:
    """
    Renders distorted CAPTCHA images using Pillow.
    Features sinusoidal wave deformation, individual glyph rotation/scaling,
    procedural Bézier curves, salt-and-pepper noise, and Gaussian smoothing.
    """

    def __init__(self, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT):
        self.width = width
        self.height = height

    def _get_font(self, size: int) -> "ImageFont.ImageFont":
        """Attempts to load a clean TrueType font from system; falls back gracefully."""
        if not HAS_PILLOW:
            return None
        windir = os.environ.get("WINDIR", "C:\\Windows")
        search_dirs = [
            os.path.join(windir, "Fonts"),
            "/usr/share/fonts",
            "/Library/Fonts",
            os.path.expanduser("~/.fonts")
        ]
        for font_name in SYSTEM_FONTS:
            # Check relative and absolute
            candidates = [font_name]
            for sdir in search_dirs:
                candidates.append(os.path.join(sdir, font_name))
            for cand in candidates:
                if os.path.exists(cand):
                    try:
                        return ImageFont.truetype(cand, size)
                    except Exception:
                        continue
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    def render_image(
        self,
        text: str,
        wave_amplitude: float = 6.0,
        wave_frequency: float = 45.0,
        curve_count: int = 5,
        noise_dots: int = 900,
        blur: bool = True
    ) -> bytes:
        """
        Renders text onto a deformed canvas and returns PNG bytes.
        """
        if not HAS_PILLOW:
            raise RuntimeError("Pillow is required for PNG image generation. Use SVG or install Pillow.")

        w, h = self.width, self.height
        
        # 1. Base Canvas with soft gradient/textured background
        bg_color = (random.randint(235, 250), random.randint(235, 250), random.randint(235, 250))
        img = Image.new("RGB", (w, h), bg_color)
        draw = ImageDraw.Draw(img)

        # Draw subtle background grid/lines
        for x in range(0, w, random.randint(18, 28)):
            draw.line([(x, 0), (x, h)], fill=(random.randint(215, 230),) * 3, width=1)
        for y in range(0, h, random.randint(18, 28)):
            draw.line([(0, y), (w, y)], fill=(random.randint(215, 230),) * 3, width=1)

        # 2. Render Characters with individual rotation and vertical jitter
        font_size = int(h * 0.58)
        font = self._get_font(font_size)

        n_chars = len(text)
        slot_w = w / max(n_chars + 1, 1)

        for i, char in enumerate(text):
            # Create a separate transparent canvas for this character
            char_w = int(slot_w * 1.5)
            char_h = int(h * 1.3)
            char_img = Image.new("RGBA", (char_w, char_h), (0, 0, 0, 0))
            char_draw = ImageDraw.Draw(char_img)

            # High-contrast glyph color
            char_color = (
                random.randint(10, 110),
                random.randint(10, 110),
                random.randint(10, 110),
                255
            )

            # Center text inside char canvas
            try:
                bbox = font.getbbox(char)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except Exception:
                tw, th = font_size * 0.6, font_size

            cx = (char_w - tw) / 2
            cy = (char_h - th) / 2
            char_draw.text((cx, cy), char, font=font, fill=char_color)

            # Rotate character
            rot_deg = random.uniform(-28.0, 28.0)
            char_rot = char_img.rotate(rot_deg, resample=Image.Resampling.BILINEAR, expand=False)

            # Paste onto main image with vertical jitter
            x_pos = int(slot_w * (i + 0.3) + random.uniform(-4, 4))
            y_pos = int((h - char_h) / 2 + random.uniform(-h * 0.1, h * 0.1))
            img.paste(char_rot, (x_pos, y_pos), char_rot)

        # 3. Sinusoidal Wave Deformation
        img = self._apply_sinusoidal_wave(img, wave_amplitude, wave_frequency)
        draw = ImageDraw.Draw(img)

        # 4. Procedural Interference Bézier Curves
        for _ in range(curve_count):
            p0 = (random.randint(0, w // 4), random.randint(0, h))
            p1 = (random.randint(w // 4, w // 2), random.randint(0, h))
            p2 = (random.randint(w // 2, 3 * w // 4), random.randint(0, h))
            p3 = (random.randint(3 * w // 4, w), random.randint(0, h))
            curve_color = (
                random.randint(50, 160),
                random.randint(50, 160),
                random.randint(50, 160)
            )
            stroke_w = random.randint(2, 3)
            # Sample cubic Bézier curve points
            points = []
            for step in range(35):
                t = step / 34.0
                inv = 1.0 - t
                bx = (inv**3)*p0[0] + 3*(inv**2)*t*p1[0] + 3*inv*(t**2)*p2[0] + (t**3)*p3[0]
                by = (inv**3)*p0[1] + 3*(inv**2)*t*p1[1] + 3*inv*(t**2)*p2[1] + (t**3)*p3[1]
                points.append((bx, by))
            draw.line(points, fill=curve_color, width=stroke_w)

        # 5. Salt-and-Pepper Speckle Noise
        for _ in range(noise_dots):
            nx = random.randint(0, w - 1)
            ny = random.randint(0, h - 1)
            noise_col = (random.randint(20, 220), random.randint(20, 220), random.randint(20, 220))
            draw.point((nx, ny), fill=noise_col)

        # 6. Subtle Gaussian Smoothing
        if blur:
            img = img.filter(ImageFilter.GaussianBlur(radius=0.45))

        out_io = io.BytesIO()
        img.save(out_io, format="PNG")
        return out_io.getvalue()

    def _apply_sinusoidal_wave(
        self,
        img: "Image.Image",
        amp: float,
        freq: float
    ) -> "Image.Image":
        """Applies a smooth 2D sinusoidal coordinate transformation."""
        w, h = img.size
        # Fast numpy vectorized warp if numpy is available
        try:
            import numpy as np
            arr = np.array(img)
            y_indices, x_indices = np.indices((h, w))
            phase_x = random.uniform(0, 2 * math.pi)
            phase_y = random.uniform(0, 2 * math.pi)

            dx = (amp * np.sin(2 * np.pi * y_indices / freq + phase_x)).astype(int)
            dy = ((amp * 0.7) * np.cos(2 * np.pi * x_indices / freq + phase_y)).astype(int)

            src_x = np.clip(x_indices + dx, 0, w - 1)
            src_y = np.clip(y_indices + dy, 0, h - 1)

            distorted_arr = arr[src_y, src_x]
            return Image.fromarray(distorted_arr)
        except ImportError:
            # Fallback pure-python pixel warp
            distorted = Image.new("RGB", (w, h), (255, 255, 255))
            sp = img.load()
            dp = distorted.load()
            phase_x = random.uniform(0, 2 * math.pi)
            phase_y = random.uniform(0, 2 * math.pi)
            for y in range(h):
                dx = int(amp * math.sin(2 * math.pi * y / freq + phase_x))
                for x in range(w):
                    dy = int((amp * 0.7) * math.cos(2 * math.pi * x / freq + phase_y))
                    ox = min(max(x + dx, 0), w - 1)
                    oy = min(max(y + dy, 0), h - 1)
                    dp[x, y] = sp[ox, oy]
            return distorted


# ==============================================================================
# PURE PYTHON SVG VECTOR GENERATOR (ZERO DEPENDENCIES)
# ==============================================================================

class CaptchaSvgEngine:
    """Generates standard-compliant vector SVG CAPTCHA files with wave transforms."""

    @staticmethod
    def render_svg(
        text: str,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        curve_count: int = 4,
        dots_count: int = 250
    ) -> str:
        """Constructs an SVG XML document representing the distorted challenge."""
        slot_w = width / max(len(text) + 1, 1)
        font_size = int(height * 0.52)
        
        elements: List[str] = []
        # Background
        elements.append(
            f'<rect width="{width}" height="{height}" fill="#f4f6fa" rx="8"/>'
        )
        
        # Grid lines
        for x in range(20, width, 30):
            elements.append(
                f'<line x1="{x}" y1="0" x2="{x}" y2="{height}" stroke="#e0e4ec" stroke-width="1"/>'
            )
        for y in range(20, height, 30):
            elements.append(
                f'<line x1="0" y1="{y}" x2="{width}" y2="{y}" stroke="#e0e4ec" stroke-width="1"/>'
            )

        # Distorted Characters
        for i, ch in enumerate(text):
            x = int(slot_w * (i + 0.6) + random.uniform(-3, 3))
            y = int(height * 0.65 + random.uniform(-6, 6))
            rot = random.uniform(-25, 25)
            color = f"rgb({random.randint(10, 100)},{random.randint(10, 100)},{random.randint(10, 100)})"
            transform = f'transform="rotate({rot:.1f} {x} {y})"'
            elements.append(
                f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-weight="bold" '
                f'font-size="{font_size}" fill="{color}" {transform} text-anchor="middle">{ch}</text>'
            )

        # Interference Bézier curves
        for _ in range(curve_count):
            p0 = (random.randint(0, width // 4), random.randint(0, height))
            p1 = (random.randint(width // 4, width // 2), random.randint(0, height))
            p2 = (random.randint(width // 2, 3 * width // 4), random.randint(0, height))
            p3 = (random.randint(3 * width // 4, width), random.randint(0, height))
            c_color = f"rgb({random.randint(80, 160)},{random.randint(80, 160)},{random.randint(80, 160)})"
            d = f"M {p0[0]},{p0[1]} C {p1[0]},{p1[1]} {p2[0]},{p2[1]} {p3[0]},{p3[1]}"
            elements.append(
                f'<path d="{d}" stroke="{c_color}" stroke-width="{random.randint(2,3)}" fill="none"/>'
            )

        # Noise dots
        for _ in range(dots_count):
            nx = random.randint(0, width)
            ny = random.randint(0, height)
            r = random.uniform(0.8, 1.8)
            d_color = f"rgba({random.randint(50, 180)},{random.randint(50, 180)},{random.randint(50, 180)},0.6)"
            elements.append(f'<circle cx="{nx}" cy="{ny}" r="{r:.1f}" fill="{d_color}"/>')

        body = "\n  ".join(elements)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}">\n  {body}\n</svg>'
        )


# ==============================================================================
# ACCESSIBILITY AUDIO SYNTHESIZER (PURE PYTHON STANDARD LIBRARY)
# ==============================================================================

class CaptchaAudioEngine:
    """
    Synthesizes speech/frequency acoustic pulses with background white noise
    into standard 16-bit PCM WAV audio using only Python's built-in wave & math.
    """

    # Distinct fundamental and harmonic frequencies (Hz) for digits & phonetics
    CHAR_FREQUENCIES: Dict[str, Tuple[float, float]] = {
        "0": (300.0, 600.0), "1": (350.0, 700.0), "2": (400.0, 800.0),
        "3": (450.0, 900.0), "4": (500.0, 1000.0), "5": (550.0, 1100.0),
        "6": (600.0, 1200.0), "7": (650.0, 1300.0), "8": (700.0, 1400.0),
        "9": (750.0, 1500.0),
        "+": (850.0, 1700.0), "-": (420.0, 840.0), "*": (920.0, 1840.0),
        "=": (320.0, 640.0), "?": (980.0, 1960.0),
    }

    @classmethod
    def synthesize_wav(cls, text: str, sample_rate: int = 16000) -> bytes:
        """
        Creates a WAV file with spoken or tonal acoustic representation
        plus masking noise to foil speech recognition scrapers.
        """
        frames: List[bytes] = []
        
        # Audio header / intro beep
        intro_samples = int(sample_rate * 0.15)
        for i in range(intro_samples):
            t = float(i) / sample_rate
            val = int(0.3 * 32767.0 * math.sin(2 * math.pi * 520 * t))
            frames.append(struct.pack("<h", max(-32768, min(32767, val))))

        # Render each character in sequence
        char_duration = 0.38 # seconds per char
        silence_duration = 0.12 # seconds between chars
        char_samples = int(sample_rate * char_duration)
        silence_samples = int(sample_rate * silence_duration)

        for ch in text.upper():
            f1, f2 = cls.CHAR_FREQUENCIES.get(ch, (random.uniform(400, 700), random.uniform(800, 1400)))
            # Add small random pitch vibrato
            pitch_mod = random.uniform(-15.0, 15.0)
            f1 += pitch_mod
            f2 += pitch_mod

            for i in range(char_samples):
                t = float(i) / sample_rate
                # Dual tone synthesis
                tone1 = math.sin(2 * math.pi * f1 * t)
                tone2 = 0.5 * math.sin(2 * math.pi * f2 * t)
                # Background white noise mask
                noise = random.uniform(-0.15, 0.15)
                # Amplitude envelope (fade-in, sustain, fade-out)
                envelope = 1.0
                if i < sample_rate * 0.04:
                    envelope = i / (sample_rate * 0.04)
                elif i > char_samples - (sample_rate * 0.04):
                    envelope = (char_samples - i) / (sample_rate * 0.04)

                sample_float = (tone1 + tone2 + noise) * envelope * 0.45 * 32767.0
                sample_int = int(max(-32768, min(32767, sample_float)))
                frames.append(struct.pack("<h", sample_int))

            # Inter-character silence with gentle acoustic noise
            for i in range(silence_samples):
                noise_sample = int(random.uniform(-0.04, 0.04) * 32767.0)
                frames.append(struct.pack("<h", noise_sample))

        # Write to in-memory WAV buffer
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)        # Mono
            wf.setsampwidth(2)        # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(b"".join(frames))

        return buf.getvalue()


# ==============================================================================
# ANSI TRUECOLOR TERMINAL PREVIEW (24-BIT HALF-BLOCK)
# ==============================================================================

class TerminalAnsiRenderer:
    """
    Renders RGB image data into modern 24-bit TrueColor ANSI terminal output
    using Unicode upper half blocks (▀, U+2580).
    """

    @staticmethod
    def render_ansi(image_bytes: bytes, target_width: int = 70) -> str:
        """Converts PNG image bytes into a multi-line colored ANSI string."""
        if not HAS_PILLOW:
            return "[ANSI Preview requires Pillow library]"

        im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = im.size
        target_height = int((h / w) * target_width)
        # We need an even height because 1 character represents 2 vertical pixels
        if target_height % 2 != 0:
            target_height += 1

        im_resized = im.resize((target_width, target_height), Image.Resampling.BILINEAR)
        pixels = im_resized.load()

        lines: List[str] = []
        for y in range(0, target_height, 2):
            row_chars: List[str] = []
            for x in range(target_width):
                r1, g1, b1 = pixels[x, y]
                r2, g2, b2 = pixels[x, min(y + 1, target_height - 1)]
                # Foreground = top pixel, Background = bottom pixel
                row_chars.append(f"\033[38;2;{r1};{g1};{b1}m\033[48;2;{r2};{g2};{b2}m▀\033[0m")
            lines.append("".join(row_chars))

        return "\n".join(lines)


# ==============================================================================
# METRICS & SECURITY ANALYSER
# ==============================================================================

class CaptchaMetrics:
    """Calculates cryptographic entropy, OCR difficulty, and signal-to-noise ratio."""

    @staticmethod
    def analyse(
        text: str,
        charset_size: int = len(DEFAULT_CHARSET),
        wave_amp: float = 6.0,
        curve_count: int = 5,
        dots_count: int = 900
    ) -> Dict[str, float]:
        """Calculates security and distortion metrics."""
        length = len(text)
        # Shannon Information Entropy in bits: H = n * log2(pool)
        entropy_bits = length * math.log2(max(charset_size, 2))
        
        # Approximate Signal to Noise Ratio (dB)
        # Signal = text stroke energy, Noise = dots and curves energy
        signal_proxy = length * 120.0
        noise_proxy = (curve_count * 90.0) + (dots_count * 0.8)
        snr_ratio = signal_proxy / max(noise_proxy, 1.0)
        snr_db = 10.0 * math.log10(max(snr_ratio, 0.01))

        # OCR Resistance Index (0 to 100)
        # Higher wave amplitude and lower SNR increases OCR resistance
        distortion_factor = min(wave_amp / 10.0, 1.0) * 40.0
        noise_factor = min(noise_proxy / 1000.0, 1.0) * 35.0
        entropy_factor = min(entropy_bits / 40.0, 1.0) * 25.0
        ocr_resistance = round(distortion_factor + noise_factor + entropy_factor, 1)

        return {
            "entropy_bits": round(entropy_bits, 2),
            "snr_db": round(snr_db, 2),
            "ocr_resistance_index": ocr_resistance,
            "charset_pool_size": float(charset_size)
        }


# ==============================================================================
# HTML FORM GENERATOR
# ==============================================================================

class HtmlFormGenerator:
    """Generates a standalone, beautiful HTML verification test page with embedded CAPTCHA."""

    @staticmethod
    def generate_html(challenge: CaptchaChallenge, output_path: str) -> None:
        """Writes an interactive single-page HTML test form."""
        img_b64 = ""
        if challenge.image_bytes:
            img_b64 = base64.b64encode(challenge.image_bytes).decode("utf-8")

        audio_b64 = ""
        if challenge.audio_bytes:
            audio_b64 = base64.b64encode(challenge.audio_bytes).decode("utf-8")

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CAPTCHA Verification - Human Presence Check</title>
  <style>
    :root {{
      --bg: #0f172a;
      --card: #1e293b;
      --border: #334155;
      --primary: #38bdf8;
      --primary-hover: #0284c7;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --success: #22c55e;
      --danger: #ef4444;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    body {{
      background: radial-gradient(circle at top, #1e1b4b, var(--bg));
      color: var(--text);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1.5rem;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 2rem;
      width: 100%;
      max-width: 440px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }}
    h1 {{ font-size: 1.5rem; margin-bottom: 0.5rem; text-align: center; }}
    p.subtitle {{ color: var(--text-muted); font-size: 0.875rem; text-align: center; margin-bottom: 1.5rem; }}
    .captcha-box {{
      background: #090d16;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px;
      text-align: center;
      margin-bottom: 1rem;
      position: relative;
    }}
    .captcha-box img {{
      max-width: 100%;
      height: auto;
      border-radius: 6px;
      display: block;
      margin: 0 auto;
    }}
    .audio-player {{ margin: 0.5rem 0; width: 100%; }}
    .form-group {{ margin-bottom: 1.25rem; }}
    label {{ display: block; font-size: 0.875rem; font-weight: 500; margin-bottom: 0.5rem; }}
    input[type="text"] {{
      width: 100%;
      padding: 0.75rem 1rem;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: #0f172a;
      color: var(--text);
      font-size: 1.1rem;
      letter-spacing: 2px;
      text-transform: uppercase;
      outline: none;
      transition: border-color 0.2s;
    }}
    input[type="text"]:focus {{ border-color: var(--primary); ring: 2px var(--primary); }}
    .btn {{
      width: 100%;
      padding: 0.85rem;
      border-radius: 8px;
      border: none;
      background: var(--primary);
      color: #0f172a;
      font-weight: 600;
      font-size: 1rem;
      cursor: pointer;
      transition: background 0.2s;
    }}
    .btn:hover {{ background: var(--primary-hover); }}
    .result {{
      margin-top: 1rem;
      padding: 0.75rem;
      border-radius: 8px;
      text-align: center;
      font-size: 0.9rem;
      display: none;
    }}
    .result.success {{ display: block; background: rgba(34, 197, 94, 0.15); color: var(--success); border: 1px solid var(--success); }}
    .result.error {{ display: block; background: rgba(239, 68, 68, 0.15); color: var(--danger); border: 1px solid var(--danger); }}
    .meta {{ font-size: 0.75rem; color: var(--text-muted); margin-top: 1rem; text-align: center; word-break: break-all; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>🛡️ Human Verification</h1>
    <p class="subtitle">Please enter the characters or answer below to submit</p>

    <div class="captcha-box">
      {"<img src='data:image/png;base64," + img_b64 + "' alt='CAPTCHA challenge'/>" if img_b64 else "<p>Vector CAPTCHA: " + challenge.display_text + "</p>"}
    </div>

    {f'''<audio class="audio-player" controls>
      <source src="data:audio/wav;base64,{audio_b64}" type="audio/wav">
      Your browser does not support the audio element.
    </audio>''' if audio_b64 else ""}

    <form id="captchaForm" onsubmit="handleVerify(event)">
      <div class="form-group">
        <label for="captchaInput">Enter CAPTCHA Answer</label>
        <input type="text" id="captchaInput" autocomplete="off" required placeholder="Type solution here..." />
      </div>
      <button type="submit" class="btn">Verify & Proceed</button>
    </form>

    <div id="resultBox" class="result"></div>

    <div class="meta">
      Token: <code>{challenge.token[:32]}...</code><br>
      Expires in {challenge.ttl_seconds} seconds
    </div>
  </div>

  <script>
    const EXPECTED_SOLUTION = "{challenge.solution}";
    function handleVerify(e) {{
      e.preventDefault();
      const val = document.getElementById("captchaInput").value.trim().toUpperCase();
      const res = document.getElementById("resultBox");
      if (val === EXPECTED_SOLUTION.toUpperCase()) {{
        res.className = "result success";
        res.innerHTML = "✅ <b>Verified!</b> Human presence successfully confirmed.";
      }} else {{
        res.className = "result error";
        res.innerHTML = "❌ <b>Verification Failed!</b> Incorrect answer. Try again.";
      }}
    }}
  </script>
</body>
</html>
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)


# ==============================================================================
# MAIN CAPTCHA MAKER FACADE & WORKFLOWS
# ==============================================================================

class CaptchaMaker:
    """High-level interface orchestrating challenge creation, rendering, and validation."""

    def __init__(
        self,
        secret: str = DEFAULT_SECRET,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT
    ):
        self.secret = secret
        self.ttl_seconds = ttl_seconds
        self.width = width
        self.height = height
        self.image_engine = CaptchaImageEngine(width=width, height=height)

    def create(
        self,
        mode: str = "text",
        length: int = DEFAULT_LENGTH,
        difficulty: str = "medium",
        filter_ambiguous: bool = True,
        charset: str = DEFAULT_CHARSET,
        with_audio: bool = False,
        with_svg: bool = False,
        wave_amplitude: float = 6.0,
        curve_count: int = 5,
        noise_dots: int = 900
    ) -> CaptchaChallenge:
        """Generates a complete CAPTCHA challenge with tokens, images, and audio."""
        challenge_id = secrets.token_hex(6)

        if mode == "math":
            display_text, solution = ChallengeSynthesizer.generate_math(difficulty=difficulty)
        else:
            solution = ChallengeSynthesizer.generate_text(
                length=length, charset=charset, filter_ambiguous=filter_ambiguous
            )
            display_text = solution

        # Generate cryptographic stateless token
        token = StatelessTokenEngine.generate_token(
            solution=solution, secret=self.secret, ttl_seconds=self.ttl_seconds
        )

        image_bytes: Optional[bytes] = None
        if HAS_PILLOW:
            image_bytes = self.image_engine.render_image(
                text=display_text,
                wave_amplitude=wave_amplitude,
                curve_count=curve_count,
                noise_dots=noise_dots
            )

        audio_bytes: Optional[bytes] = None
        if with_audio or mode == "audio":
            # For audio, phonetic digits/equation
            audio_bytes = CaptchaAudioEngine.synthesize_wav(display_text)

        svg_string: Optional[str] = None
        if with_svg or not HAS_PILLOW:
            svg_string = CaptchaSvgEngine.render_svg(
                text=display_text, width=self.width, height=self.height
            )

        metrics = CaptchaMetrics.analyse(
            text=display_text,
            charset_size=len(charset),
            wave_amp=wave_amplitude,
            curve_count=curve_count,
            dots_count=noise_dots
        )

        return CaptchaChallenge(
            challenge_id=challenge_id,
            mode=mode,
            display_text=display_text,
            solution=solution,
            token=token,
            created_at=time.time(),
            ttl_seconds=self.ttl_seconds,
            image_bytes=image_bytes,
            audio_bytes=audio_bytes,
            svg_string=svg_string,
            metrics=metrics
        )

    def verify(
        self,
        token: str,
        user_input: str,
        case_sensitive: bool = False
    ) -> Tuple[bool, str]:
        """Validates a stateless token against user input."""
        return StatelessTokenEngine.verify_token(
            token=token,
            user_input=user_input,
            secret=self.secret,
            case_sensitive=case_sensitive
        )


# ==============================================================================
# INTERACTIVE CLI VERIFICATION CHALLENGE
# ==============================================================================

def run_interactive_challenge(maker: CaptchaMaker, mode: str = "text", difficulty: str = "medium") -> None:
    """Runs a live interactive human verification challenge in the terminal."""
    print("=" * 64)
    print("  🛡️   CAPTCHA MAKER — INTERACTIVE HUMAN VERIFICATION CHALLENGE")
    print("=" * 64)
    print("  Generating dynamic challenge with sinusoidal wave distortion...")

    challenge = maker.create(mode=mode, difficulty=difficulty, with_audio=False)

    if challenge.image_bytes and HAS_PILLOW:
        print("\n  [Canvas Preview - 24-Bit TrueColor ANSI]:\n")
        print(TerminalAnsiRenderer.render_ansi(challenge.image_bytes, target_width=68))
        print()
    elif challenge.svg_string:
        print(f"\n  [Vector Challenge Text]: {challenge.display_text}\n")

    print(f"  Challenge ID : {challenge.challenge_id}")
    print(f"  Mode         : {challenge.mode.upper()}")
    print(f"  Entropy      : {challenge.metrics.get('entropy_bits')} bits")
    print(f"  TTL Window   : {challenge.ttl_seconds} seconds")
    print("-" * 64)
    print("  Enter what you see (or solve the math challenge):")

    attempts = 3
    start_time = time.perf_counter()

    while attempts > 0:
        try:
            user_input = input(f"  [Attempt {4 - attempts}/3] > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Verification aborted by user.")
            sys.exit(130)

        elapsed = time.perf_counter() - start_time
        ok, msg = maker.verify(challenge.token, user_input)

        if ok:
            print("\n" + "=" * 64)
            print(f"  ✅  ACCESS GRANTED! {msg}")
            print(f"  ⏱️   Response Time : {elapsed:.2f} seconds")
            print(f"  🔑  Verified Token: {challenge.token[:36]}...")
            print("=" * 64)
            return
        else:
            attempts -= 1
            if attempts > 0:
                print(f"  ❌  {msg} ({attempts} attempts remaining)")
            else:
                print("\n" + "=" * 64)
                print("  ⛔  ACCESS DENIED: Maximum attempts exceeded. Bot detected or human timeout.")
                print("=" * 64)
                sys.exit(1)


# ==============================================================================
# EMBEDDED UNIT TEST SUITE (20+ TESTS)
# ==============================================================================

class _TestStatelessToken(unittest.TestCase):
    def setUp(self):
        self.secret = "test-secret-salt-key"

    def test_token_valid(self):
        token = StatelessTokenEngine.generate_token("W9KF4", secret=self.secret, ttl_seconds=60)
        ok, msg = StatelessTokenEngine.verify_token(token, "W9KF4", secret=self.secret)
        self.assertTrue(ok)
        self.assertIn("successful", msg)

    def test_token_case_insensitivity(self):
        token = StatelessTokenEngine.generate_token("AbCdE", secret=self.secret)
        ok, _ = StatelessTokenEngine.verify_token(token, "abcde", secret=self.secret)
        self.assertTrue(ok)

    def test_token_incorrect_solution(self):
        token = StatelessTokenEngine.generate_token("W9KF4", secret=self.secret)
        ok, msg = StatelessTokenEngine.verify_token(token, "WRONG", secret=self.secret)
        self.assertFalse(ok)
        self.assertIn("Incorrect", msg)

    def test_token_tampered(self):
        token = StatelessTokenEngine.generate_token("W9KF4", secret=self.secret)
        tampered = token[:-4] + "AAAA"
        ok, msg = StatelessTokenEngine.verify_token(tampered, "W9KF4", secret=self.secret)
        self.assertFalse(ok)

    def test_token_expired(self):
        token = StatelessTokenEngine.generate_token("W9KF4", secret=self.secret, ttl_seconds=-5)
        ok, msg = StatelessTokenEngine.verify_token(token, "W9KF4", secret=self.secret)
        self.assertFalse(ok)
        self.assertIn("expired", msg)


class _TestChallengeSynthesizer(unittest.TestCase):
    def test_text_length(self):
        text = ChallengeSynthesizer.generate_text(length=8)
        self.assertEqual(len(text), 8)

    def test_no_ambiguous(self):
        for _ in range(50):
            text = ChallengeSynthesizer.generate_text(length=6, filter_ambiguous=True)
            for ch in AMBIGUOUS_CHARS:
                self.assertNotIn(ch, text)

    def test_math_easy(self):
        eq, ans = ChallengeSynthesizer.generate_math("easy")
        self.assertIn("=", eq)
        self.assertTrue(ans.lstrip("-").isdigit())

    def test_math_medium(self):
        eq, ans = ChallengeSynthesizer.generate_math("medium")
        self.assertIn("=", eq)
        self.assertTrue(ans.lstrip("-").isdigit())

    def test_math_hard(self):
        eq, ans = ChallengeSynthesizer.generate_math("hard")
        self.assertIn("=", eq)
        self.assertTrue(ans.lstrip("-").isdigit())


class _TestSvgEngine(unittest.TestCase):
    def test_svg_contains_elements(self):
        svg = CaptchaSvgEngine.render_svg("TEST9", width=200, height=80)
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)
        for ch in "TEST9":
            self.assertIn(f">{ch}<", svg)

    def test_svg_dimensions(self):
        svg = CaptchaSvgEngine.render_svg("ABC", width=320, height=110)
        self.assertIn('width="320"', svg)
        self.assertIn('height="110"', svg)



class _TestAudioEngine(unittest.TestCase):
    def test_audio_wav_validity(self):
        wav_bytes = CaptchaAudioEngine.synthesize_wav("8492")
        self.assertTrue(wav_bytes.startswith(b"RIFF"))
        self.assertIn(b"WAVE", wav_bytes[:16])
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            self.assertEqual(wf.getnchannels(), 1)
            self.assertEqual(wf.getsampwidth(), 2)
            self.assertGreater(wf.getnframes(), 1000)


class _TestImageEngine(unittest.TestCase):
    def test_image_render(self):
        if not HAS_PILLOW:
            self.skipTest("Pillow not installed")
        engine = CaptchaImageEngine(width=160, height=60)
        png_bytes = engine.render_image("K4F", wave_amplitude=3.0, noise_dots=100)
        self.assertTrue(png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_terminal_ansi_render(self):
        if not HAS_PILLOW:
            self.skipTest("Pillow not installed")
        engine = CaptchaImageEngine(width=60, height=30)
        png_bytes = engine.render_image("A", noise_dots=10)
        ansi_out = TerminalAnsiRenderer.render_ansi(png_bytes, target_width=30)
        self.assertIn("\033[", ansi_out)
        self.assertIn("▀", ansi_out)


class _TestCaptchaMakerIntegration(unittest.TestCase):
    def test_maker_text_creation(self):
        maker = CaptchaMaker()
        ch = maker.create(mode="text", length=5)
        self.assertEqual(len(ch.solution), 5)
        self.assertTrue(ch.token)
        ok, _ = maker.verify(ch.token, ch.solution)
        self.assertTrue(ok)

    def test_maker_math_creation(self):
        maker = CaptchaMaker()
        ch = maker.create(mode="math")
        self.assertIn("=", ch.display_text)
        ok, _ = maker.verify(ch.token, ch.solution)
        self.assertTrue(ok)

    def test_maker_audio_creation(self):
        maker = CaptchaMaker()
        ch = maker.create(mode="text", with_audio=True)
        self.assertIsNotNone(ch.audio_bytes)
        self.assertTrue(ch.audio_bytes.startswith(b"RIFF"))

    def test_html_generation(self):
        import tempfile
        maker = CaptchaMaker()
        ch = maker.create(mode="text", length=5)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tf:
            tmp_path = tf.name
        try:
            HtmlFormGenerator.generate_html(ch, tmp_path)
            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Human Verification", content)
            self.assertIn(ch.solution, content)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_maker_metrics(self):
        m = CaptchaMetrics.analyse("ABCDE", charset_size=62)
        self.assertGreater(m["entropy_bits"], 25.0)
        self.assertGreater(m["ocr_resistance_index"], 0.0)



def _run_embedded_tests() -> int:
    """Executes the test suite and returns the exit code."""
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTests(loader.loadTestsFromTestCase(_TestStatelessToken))
    suite.addTests(loader.loadTestsFromTestCase(_TestChallengeSynthesizer))
    suite.addTests(loader.loadTestsFromTestCase(_TestSvgEngine))
    suite.addTests(loader.loadTestsFromTestCase(_TestAudioEngine))
    suite.addTests(loader.loadTestsFromTestCase(_TestImageEngine))
    suite.addTests(loader.loadTestsFromTestCase(_TestCaptchaMakerIntegration))

    print("\n════════════════════════════════════════════════════════════════")
    print("  🛡️  Running CAPTCHA Maker Embedded Unit Tests")
    print("════════════════════════════════════════════════════════════════\n")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


# ==============================================================================
# CLI ARGUMENT PARSER & ENTRYPOINT
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Captcha_Maker.py - Multi-Modal CAPTCHA Generator & Human Verification Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python Captcha_Maker.py                               # Generate default distorted text CAPTCHA
  python Captcha_Maker.py --preview                     # Show 24-bit TrueColor ANSI terminal preview
  python Captcha_Maker.py --interactive                 # Live terminal human verification challenge
  python Captcha_Maker.py --mode math --preview         # Arithmetic challenge
  python Captcha_Maker.py --audio -o captcha.png        # Generate image + WAV audio
  python Captcha_Maker.py --html test_form.html         # Standalone HTML5 test form
  python Captcha_Maker.py --batch 10 --out-dir dataset  # Generate ML / OCR synthetic batch
  python Captcha_Maker.py --verify <TOKEN> <INPUT>      # Verify a stateless token
  python Captcha_Maker.py --run-tests                   # Run full unit test suite
        """
    )

    parser.add_argument("--mode", choices=["text", "math", "audio"], default="text",
                        help="Challenge mode (text, math, or audio; default: text)")
    parser.add_argument("-l", "--length", type=int, default=DEFAULT_LENGTH,
                        help=f"Character length for text mode (default: {DEFAULT_LENGTH})")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard"], default="medium",
                        help="Difficulty for math mode (default: medium)")
    parser.add_argument("--no-ambiguous", action="store_true", default=True,
                        help="Filter out visually ambiguous glyphs (0, O, 1, I, l, 2, Z; default: True)")
    parser.add_argument("-o", "--output", type=str, default="captcha.png",
                        help="Output image path (default: captcha.png)")
    parser.add_argument("--audio", action="store_true",
                        help="Generate synchronized accessibility WAV audio file")
    parser.add_argument("--audio-out", type=str, default="captcha.wav",
                        help="Output path for WAV audio (default: captcha.wav)")
    parser.add_argument("--svg", action="store_true",
                        help="Generate vector SVG format instead of PNG")
    parser.add_argument("--svg-out", type=str, default="captcha.svg",
                        help="Output path for SVG (default: captcha.svg)")
    parser.add_argument("--html", type=str, metavar="FILE",
                        help="Export interactive HTML5 verification form")
    parser.add_argument("--preview", action="store_true",
                        help="Render 24-bit ANSI TrueColor preview directly in the console")
    parser.add_argument("--interactive", action="store_true",
                        help="Launch interactive terminal verification challenge")
    parser.add_argument("--batch", type=int, metavar="COUNT",
                        help="Batch generate COUNT captchas with manifest.json")
    parser.add_argument("--out-dir", type=str, default="captcha_dataset",
                        help="Target directory for batch generation (default: captcha_dataset)")
    parser.add_argument("--verify", nargs=2, metavar=("TOKEN", "INPUT"),
                        help="Verify a stateless token against user input")
    parser.add_argument("--secret", type=str, default=DEFAULT_SECRET,
                        help="Secret HMAC key for signing tokens")
    parser.add_argument("--ttl", type=int, default=DEFAULT_TTL_SECONDS,
                        help=f"Token time-to-live in seconds (default: {DEFAULT_TTL_SECONDS})")
    parser.add_argument("--metrics", action="store_true",
                        help="Print Shannon entropy and OCR resistance metrics")
    parser.add_argument("--run-tests", action="store_true",
                        help="Run the embedded unit test suite")

    args = parser.parse_args()

    # 1. Embedded Test Suite
    if args.run_tests:
        sys.exit(_run_embedded_tests())

    maker = CaptchaMaker(secret=args.secret, ttl_seconds=args.ttl)

    # 2. Token Verification CLI mode
    if args.verify:
        token, user_input = args.verify
        ok, msg = maker.verify(token, user_input)
        if ok:
            print(f"✅ VALID: {msg}")
            sys.exit(0)
        else:
            print(f"❌ INVALID: {msg}")
            sys.exit(1)

    # 3. Interactive Challenge CLI
    if args.interactive:
        run_interactive_challenge(maker, mode=args.mode, difficulty=args.difficulty)
        sys.exit(0)

    # 4. Batch Dataset Generation
    if args.batch:
        count = max(args.batch, 1)
        os.makedirs(args.out_dir, exist_ok=True)
        manifest = []
        print(f"Generating {count} synthetic CAPTCHAs in '{args.out_dir}'...")

        for i in range(count):
            ch = maker.create(mode=args.mode, length=args.length, difficulty=args.difficulty)
            img_filename = f"captcha_{i+1:04d}.png"
            img_path = os.path.join(args.out_dir, img_filename)
            if ch.image_bytes and HAS_PILLOW:
                with open(img_path, "wb") as f:
                    f.write(ch.image_bytes)

            manifest.append({
                "id": ch.challenge_id,
                "file": img_filename,
                "display": ch.display_text,
                "solution": ch.solution,
                "token": ch.token,
                "entropy_bits": ch.metrics.get("entropy_bits"),
                "ocr_resistance": ch.metrics.get("ocr_resistance_index")
            })

        manifest_path = os.path.join(args.out_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        print(f"✅ Generated {count} samples. Manifest saved to '{manifest_path}'.")
        sys.exit(0)

    # 5. Standard Single Generation
    challenge = maker.create(
        mode=args.mode,
        length=args.length,
        difficulty=args.difficulty,
        filter_ambiguous=args.no_ambiguous,
        with_audio=args.audio,
        with_svg=args.svg
    )

    print("════════════════════════════════════════════════════════════════")
    print("  🛡️   CAPTCHA GENERATOR")
    print("════════════════════════════════════════════════════════════════")
    print(f"  Challenge ID   : {challenge.challenge_id}")
    print(f"  Mode           : {challenge.mode.upper()}")
    print(f"  Display Text   : {challenge.display_text}")
    print(f"  Solution       : {challenge.solution}")
    print(f"  Token (HMAC)   : {challenge.token}")
    print(f"  TTL Window     : {challenge.ttl_seconds}s")

    if args.metrics:
        print("\n  [Security & Distortion Metrics]:")
        for k, v in challenge.metrics.items():
            print(f"    - {k.replace('_', ' ').title():<22} : {v}")

    # Save PNG
    if challenge.image_bytes and HAS_PILLOW and not args.svg:
        with open(args.output, "wb") as f:
            f.write(challenge.image_bytes)
        print(f"\n  💾 Image saved to '{args.output}'")

    # Save SVG
    if args.svg or challenge.svg_string:
        svg_content = challenge.svg_string or CaptchaSvgEngine.render_svg(challenge.display_text)
        with open(args.svg_out, "w", encoding="utf-8") as f:
            f.write(svg_content)
        print(f"  💾 Vector SVG saved to '{args.svg_out}'")

    # Save Audio
    if args.audio or challenge.audio_bytes:
        with open(args.audio_out, "wb") as f:
            f.write(challenge.audio_bytes)
        print(f"  🔊 WAV Audio saved to '{args.audio_out}'")

    # Save HTML
    if args.html:
        HtmlFormGenerator.generate_html(challenge, args.html)
        print(f"  🌐 Standalone HTML Form exported to '{args.html}'")

    # Render Terminal ANSI Preview
    if args.preview:
        if challenge.image_bytes and HAS_PILLOW:
            print("\n  [24-Bit TrueColor ANSI Terminal Preview]:\n")
            print(TerminalAnsiRenderer.render_ansi(challenge.image_bytes, target_width=68))
            print()
        else:
            print("\n  [ASCII Fallback Preview]: " + challenge.display_text)

    print("════════════════════════════════════════════════════════════════\n")


if __name__ == "__main__":
    main()
