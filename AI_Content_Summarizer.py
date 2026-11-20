#!/usr/bin/env python3
"""
AI-Powered Content Summarizer
==============================
Project #15 of 50 Mini Projects

Summarise long articles, documents, PDFs, or web pages using
OpenAI GPT or Hugging Face models. Everything — app, tests,
sample data, and setup — lives in this single file.

Quick start:
    python AI_Content_Summarizer.py --setup          # write .env + requirements.txt
    pip install -r requirements.txt
    python AI_Content_Summarizer.py --demo           # run on built-in sample article
    python AI_Content_Summarizer.py --run-tests      # run all 20 unit tests

Usage:
    python AI_Content_Summarizer.py --text "Article…"
    python AI_Content_Summarizer.py --file report.pdf
    python AI_Content_Summarizer.py --url  https://example.com/article
    python AI_Content_Summarizer.py --file doc.txt --style bullets --length long
    python AI_Content_Summarizer.py --file doc.txt --provider huggingface
    python AI_Content_Summarizer.py --batch articles/ --output-dir summaries/
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import string
import sys
import textwrap
import time
import types
import unittest
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

# ── Load .env if python-dotenv is installed ───────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
#  EMBEDDED ASSETS  (sample article · requirements · .env template)
# ═══════════════════════════════════════════════════════════════════════════════

SAMPLE_ARTICLE = """\
Artificial intelligence (AI) is transforming the modern world in ways
that were unimaginable just a decade ago. From healthcare diagnostics to
autonomous vehicles, AI systems are being deployed across virtually every
sector of the economy. Machine learning models can now analyse medical
images with accuracy rivalling that of experienced physicians, detect
fraudulent transactions in milliseconds, and compose music indistinguishable
from human composers.

The economic impact is staggering. According to a 2024 McKinsey report,
AI could add $13 trillion to global economic output by 2030. This wealth
creation, however, is not evenly distributed. High-skill workers who can
collaborate with AI systems see their productivity and earnings soar, while
routine cognitive jobs face displacement pressure not seen since the
Industrial Revolution.

Education systems worldwide are grappling with this new reality. Universities
are racing to integrate AI literacy into every curriculum, not just computer
science programmes. Critical thinking, creativity, and interpersonal skills
are being emphasised as the distinctly human capabilities that complement
rather than compete with machine intelligence.

Climate change presents both a challenge and an opportunity for AI. Training
large language models consumes enormous amounts of energy — a single training
run for a frontier model can emit as much CO2 as five cars over their
entire lifetimes. Yet the same AI technologies are accelerating the discovery
of new battery chemistries, optimising power grids, and reducing waste in
manufacturing supply chains.

Governance frameworks are struggling to keep pace with the technology.
The European Union's AI Act, the first comprehensive regulation of its kind,
creates a risk-tiered framework with strict requirements for high-stakes
applications in employment, credit, law enforcement, and critical
infrastructure. The United States, by contrast, has taken a lighter-touch
approach centred on voluntary commitments and sector-specific guidance.

The question that occupies philosophers, economists, and engineers alike
is not whether AI will change society — it already has — but whether humanity
will retain meaningful control over the direction of that change. The answers
will shape not just the next product cycle, but the next chapter of human
civilisation.
"""

REQUIREMENTS_TXT = """\
openai>=1.0.0
huggingface_hub>=0.20.0
requests>=2.31.0
beautifulsoup4>=4.12.0
python-dotenv>=1.0.0
tiktoken>=0.6.0
pdfplumber>=0.10.0
"""

DOT_ENV_EXAMPLE = """\
# OpenAI — https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-your-openai-key-here

# Hugging Face (free) — https://huggingface.co/settings/tokens
HF_API_KEY=hf_your-huggingface-token-here
"""


# ═══════════════════════════════════════════════════════════════════════════════
#  ANSI COLOURS
# ═══════════════════════════════════════════════════════════════════════════════

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
MAGENTA = "\033[95m"
WHITE   = "\033[97m"


def strip_colours() -> None:
    global RESET, BOLD, DIM, CYAN, GREEN, YELLOW, RED, MAGENTA, WHITE
    RESET = BOLD = DIM = CYAN = GREEN = YELLOW = RED = MAGENTA = WHITE = ""


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

def setup_logging(verbose: bool = False, log_file: Path | None = None) -> None:
    logger = logging.getLogger("summarizer")
    level  = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                            datefmt="%H:%M:%S")
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(level)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)


log = logging.getLogger("summarizer")


# ═══════════════════════════════════════════════════════════════════════════════
#  TYPES
# ═══════════════════════════════════════════════════════════════════════════════

Provider = Literal["openai", "huggingface"]
Style    = Literal["concise", "detailed", "bullets", "eli5"]
Length   = Literal["short", "medium", "long"]


# ═══════════════════════════════════════════════════════════════════════════════
#  PROMPT ENGINEERING
# ═══════════════════════════════════════════════════════════════════════════════

STYLE_PROMPTS: dict[str, str] = {
    "concise": (
        "Summarise the following text in a single, clear paragraph. "
        "Capture only the most essential points. Be direct and avoid padding."
    ),
    "detailed": (
        "Write a comprehensive summary of the following text. "
        "Cover all major points, key arguments, and important details. "
        "Use clear paragraphs with logical flow."
    ),
    "bullets": (
        "Summarise the following text as a structured bullet-point list. "
        "Use main bullets for key themes and sub-bullets for supporting details. "
        "Start each bullet with a strong verb or key noun."
    ),
    "eli5": (
        "Explain the following text as if talking to a 10-year-old. "
        "Use simple words, short sentences, and helpful analogies. "
        "Make it engaging and easy to understand."
    ),
}

LENGTH_TOKENS: dict[str, int] = {
    "short": 120, "medium": 280, "long": 500,
}

LENGTH_WORDS: dict[str, str] = {
    "short": "50-100 words", "medium": "150-250 words", "long": "300-500 words",
}


def build_prompt(text: str, style: str, length: str) -> str:
    """Compose the full user prompt from style + length settings."""
    return (
        f"{STYLE_PROMPTS[style]}\n\n"
        f"Target length: {LENGTH_WORDS[length]}.\n\n"
        f"Text to summarise:\n\"\"\"\n{text}\n\"\"\""
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  TOKEN COUNTING & COST ESTIMATION
# ═══════════════════════════════════════════════════════════════════════════════

def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """Count tokens via tiktoken, falling back to word-count × 1.3."""
    try:
        import tiktoken
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    except Exception:
        return int(len(text.split()) * 1.3)


def estimate_cost_openai(input_tokens: int, output_tokens: int, model: str) -> float:
    """
    Estimate USD cost using Nov-2026 OpenAI pricing (per 1M tokens).
    gpt-4o-mini: $0.15 in / $0.60 out
    gpt-4o:      $5.00 in / $15.00 out
    """
    pricing = {
        "gpt-4o-mini":  (0.15,  0.60),
        "gpt-4o":       (5.00, 15.00),
        "gpt-3.5-turbo":(0.50,  1.50),
    }
    key = next((k for k in pricing if k in model), "gpt-4o-mini")
    ir, or_ = pricing[key]
    return (input_tokens * ir + output_tokens * or_) / 1_000_000


# ═══════════════════════════════════════════════════════════════════════════════
#  RESULT DATACLASS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SummaryResult:
    summary:         str
    provider:        str
    model:           str
    style:           str
    length:          str
    input_chars:     int
    input_tokens:    int
    output_tokens:   int
    elapsed_seconds: float
    cost_usd:        float = 0.0
    source:          str   = ""
    timestamp:       str   = field(default_factory=lambda: datetime.now().isoformat())


# ═══════════════════════════════════════════════════════════════════════════════
#  AI PROVIDERS
# ═══════════════════════════════════════════════════════════════════════════════

class OpenAISummarizer:
    """Wrapper around OpenAI Chat Completions API."""

    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self, model: str | None = None) -> None:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY not set.\n"
                "  Run:  python AI_Content_Summarizer.py --setup\n"
                "  Then edit .env and add your key from https://platform.openai.com/api-keys"
            )
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("Run: pip install openai")
        self.model = model or self.DEFAULT_MODEL

    def summarise(
        self, text: str, style: str = "concise",
        length: str = "medium", max_retries: int = 3,
    ) -> SummaryResult:
        prompt = build_prompt(text, style, length)
        for attempt in range(1, max_retries + 1):
            try:
                t0  = time.perf_counter()
                rsp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system",
                         "content": "You are an expert summariser. Follow instructions precisely."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=LENGTH_TOKENS[length],
                    temperature=0.4,
                )
                elapsed = time.perf_counter() - t0
                break
            except Exception as exc:
                if attempt == max_retries:
                    raise RuntimeError(f"OpenAI API failed after {max_retries} tries: {exc}") from exc
                wait = 2 ** attempt
                log.warning("Retry %d in %ds… (%s)", attempt, wait, exc)
                time.sleep(wait)

        summary  = rsp.choices[0].message.content.strip()
        in_tok   = rsp.usage.prompt_tokens
        out_tok  = rsp.usage.completion_tokens
        return SummaryResult(
            summary=summary, provider="openai", model=self.model,
            style=style, length=length, input_chars=len(text),
            input_tokens=in_tok, output_tokens=out_tok,
            elapsed_seconds=round(elapsed, 2),
            cost_usd=round(estimate_cost_openai(in_tok, out_tok, self.model), 6),
        )


class HuggingFaceSummarizer:
    """Wrapper around Hugging Face Inference API (free tier)."""

    DEFAULT_MODEL = "facebook/bart-large-cnn"

    def __init__(self, model: str | None = None) -> None:
        api_key = (
            os.environ.get("HF_API_KEY", "").strip() or
            os.environ.get("HUGGINGFACE_API_KEY", "").strip()
        )
        if not api_key:
            raise EnvironmentError(
                "HF_API_KEY not set.\n"
                "  Free token at https://huggingface.co/settings/tokens\n"
                "  Run:  python AI_Content_Summarizer.py --setup  then edit .env"
            )
        try:
            from huggingface_hub import InferenceClient
            self.client = InferenceClient(token=api_key)
        except ImportError:
            raise ImportError("Run: pip install huggingface_hub")
        self.model = model or self.DEFAULT_MODEL

    def summarise(
        self, text: str, style: str = "concise",
        length: str = "medium", max_retries: int = 3,
    ) -> SummaryResult:
        min_len, max_len = {"short": (30, 80), "medium": (60, 180), "long": (100, 300)}[length]
        for attempt in range(1, max_retries + 1):
            try:
                t0  = time.perf_counter()
                res = self.client.summarization(
                    text=text, model=self.model,
                    parameters={"min_length": min_len, "max_length": max_len, "do_sample": False},
                )
                elapsed = time.perf_counter() - t0
                break
            except Exception as exc:
                if attempt == max_retries:
                    raise RuntimeError(f"HF API failed after {max_retries} tries: {exc}") from exc
                wait = 2 ** attempt
                log.warning("Retry %d in %ds… (%s)", attempt, wait, exc)
                time.sleep(wait)

        summary = res.summary_text.strip() if hasattr(res, "summary_text") else str(res).strip()
        return SummaryResult(
            summary=summary, provider="huggingface", model=self.model,
            style=style, length=length, input_chars=len(text),
            input_tokens=count_tokens(text), output_tokens=count_tokens(summary),
            elapsed_seconds=round(elapsed, 2), cost_usd=0.0,
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  INPUT LOADERS
# ═══════════════════════════════════════════════════════════════════════════════

def load_file(path: Path) -> str:
    """Read .txt / .md / .pdf files."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if path.suffix.lower() == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages)
        except ImportError:
            raise ImportError("pip install pdfplumber  to read PDFs")
    return path.read_text(encoding="utf-8", errors="replace")


def load_url(url: str, timeout: int = 15) -> str:
    """Fetch and strip a web article to plain text."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("pip install requests beautifulsoup4")
    if not urlparse(url).scheme:
        url = "https://" + url
    headers = {"User-Agent": "Mozilla/5.0 (ContentSummarizer/1.0)"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script","style","nav","header","footer","aside","noscript"]):
        tag.decompose()
    body = soup.find("article") or soup.find("main") or soup.body
    if not body:
        raise ValueError("Could not extract text from URL.")
    lines = [l.strip() for l in body.get_text(separator="\n").splitlines() if l.strip()]
    return "\n".join(lines)


def chunk_text(text: str, max_chars: int = 12_000) -> list[str]:
    """Split long text into paragraph-aware chunks."""
    if len(text) <= max_chars:
        return [text]
    paragraphs = text.split("\n\n")
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = (current + "\n\n" + para).lstrip("\n")
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks or [text]


# ═══════════════════════════════════════════════════════════════════════════════
#  ORCHESTRATION
# ═══════════════════════════════════════════════════════════════════════════════

def summarize_text(
    text: str, summarizer, style: str, length: str, max_chars: int = 12_000,
) -> SummaryResult:
    """Handle any text length via hierarchical chunk-and-summarise."""
    chunks = chunk_text(text, max_chars)
    if len(chunks) == 1:
        return summarizer.summarise(text, style=style, length=length)
    log.info("Long document: %d chunks → hierarchical summarise", len(chunks))
    minis = [summarizer.summarise(c, style="concise", length="short").summary
             for c in chunks]
    return summarizer.summarise("\n\n".join(minis), style=style, length=length)


def batch_process(
    input_dir: Path, output_dir: Path, summarizer, style: str, length: str,
) -> list[SummaryResult]:
    files = [f for f in sorted(input_dir.iterdir())
             if f.suffix.lower() in {".txt",".md"} and f.is_file()]
    if not files:
        log.warning("No .txt/.md files found in %s", input_dir)
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for f in files:
        log.info("Processing: %s", f.name)
        try:
            text   = load_file(f)
            result = summarize_text(text, summarizer, style, length)
            result.source = str(f)
            out = output_dir / f"{f.stem}_summary.txt"
            out.write_text(result.summary, encoding="utf-8")
            log.info("  → %s", out.name)
            results.append(result)
        except Exception as exc:
            log.error("  ✘ %s: %s", f.name, exc)
    return results


# ═══════════════════════════════════════════════════════════════════════════════
#  OUTPUT FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════════

def print_header(title: str) -> None:
    b = "═" * 64
    print(f"\n{CYAN}{b}{RESET}")
    print(f"{CYAN}  🤖  {BOLD}{title}{RESET}")
    print(f"{CYAN}{b}{RESET}\n")


def print_result(r: SummaryResult) -> None:
    wrapped = textwrap.fill(r.summary, 70,
                            initial_indent="  ", subsequent_indent="  ")
    print(f"{wrapped}\n")
    pc = CYAN if r.provider == "openai" else MAGENTA
    icons = {"concise":"⚡","detailed":"📄","bullets":"•","eli5":"🧒"}
    print(f"  {DIM}{'─'*60}{RESET}")
    print(f"  {pc}{BOLD}{r.provider.upper()}{RESET}  {DIM}{r.model}{RESET}")
    print(f"  {icons.get(r.style,'✦')} Style: {r.style:<12} Length: {r.length:<8} "
          f"Time: {YELLOW}{r.elapsed_seconds:.2f}s{RESET}")
    print(f"  Input: {r.input_chars:,} chars ({r.input_tokens:,} tokens) "
          f"→ Output: {r.output_tokens:,} tokens")
    if r.cost_usd > 0:
        print(f"  Est. cost: {GREEN}${r.cost_usd:.6f} USD{RESET}")
    if r.source:
        print(f"  Source: {DIM}{r.source}{RESET}")
    print()


def save_result(r: SummaryResult, path: Path) -> None:
    if path.suffix == ".json":
        import dataclasses
        path.write_text(json.dumps(dataclasses.asdict(r), indent=2), encoding="utf-8")
    else:
        lines = [
            "# AI Summary\n",
            f"Generated : {r.timestamp}",
            f"Provider  : {r.provider} / {r.model}",
            f"Style     : {r.style}  |  Length: {r.length}",
            f"Source    : {r.source or 'inline'}",
            "─" * 60, "",
            r.summary, "",
            "─" * 60,
            f"Input  : {r.input_chars:,} chars / {r.input_tokens:,} tokens",
            f"Output : {r.output_tokens:,} tokens  |  Time: {r.elapsed_seconds:.2f}s",
        ]
        if r.cost_usd > 0:
            lines.append(f"Cost   : ${r.cost_usd:.6f} USD")
        path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  {GREEN}✔  Saved → {path}{RESET}")


# ═══════════════════════════════════════════════════════════════════════════════
#  SETUP HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_setup() -> int:
    """Write .env.example and requirements.txt alongside this script."""
    base = Path(__file__).parent
    env_path = base / ".env.example"
    req_path = base / "requirements.txt"
    env_path.write_text(DOT_ENV_EXAMPLE, encoding="utf-8")
    req_path.write_text(REQUIREMENTS_TXT, encoding="utf-8")
    print(f"\n{GREEN}✔  Created:{RESET}")
    print(f"   {env_path}")
    print(f"   {req_path}")
    print(f"\n{YELLOW}Next steps:{RESET}")
    print(f"  1. pip install -r requirements.txt")
    print(f"  2. cp .env.example .env  (or copy manually)")
    print(f"  3. Edit .env — add OPENAI_API_KEY or HF_API_KEY")
    print(f"  4. python AI_Content_Summarizer.py --demo\n")
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
#  UNIT TESTS  (embedded — run with --run-tests)
# ═══════════════════════════════════════════════════════════════════════════════

class _TestChunkText(unittest.TestCase):
    def test_short_no_split(self):
        chunks = chunk_text("Hello world. " * 10, max_chars=5000)
        self.assertEqual(len(chunks), 1)

    def test_long_splits(self):
        text   = "\n\n".join(["A" * 500] * 30)
        chunks = chunk_text(text, max_chars=3000)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c), 3200)

    def test_empty(self):
        self.assertEqual(chunk_text("", 1000), [""])


class _TestBuildPrompt(unittest.TestCase):
    def test_text_in_prompt(self):
        self.assertIn("hello", build_prompt("hello", "concise", "short"))

    def test_bullets_style(self):
        self.assertIn("bullet", build_prompt("x", "bullets", "medium").lower())

    def test_eli5_style(self):
        self.assertIn("10-year-old", build_prompt("x", "eli5", "short").lower())

    def test_length_guide(self):
        self.assertIn("50-100 words", build_prompt("x", "concise", "short"))


class _TestCountTokens(unittest.TestCase):
    def test_returns_int(self):
        self.assertIsInstance(count_tokens("hello world"), int)

    def test_longer_more_tokens(self):
        self.assertGreater(count_tokens("a " * 50), count_tokens("a"))

    def test_empty(self):
        self.assertEqual(count_tokens(""), 0)


class _TestCostEstimate(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(estimate_cost_openai(0, 0, "gpt-4o-mini"), 0.0)

    def test_positive(self):
        self.assertGreater(estimate_cost_openai(1000, 200, "gpt-4o-mini"), 0)

    def test_4o_more_than_mini(self):
        self.assertGreater(
            estimate_cost_openai(1000, 200, "gpt-4o"),
            estimate_cost_openai(1000, 200, "gpt-4o-mini"),
        )

    def test_unknown_model_fallback(self):
        self.assertAlmostEqual(
            estimate_cost_openai(1000, 200, "unknown-xyz"),
            estimate_cost_openai(1000, 200, "gpt-4o-mini"),
            places=10,
        )


class _TestSummaryResult(unittest.TestCase):
    def test_dataclass_fields(self):
        r = SummaryResult(
            summary="Test.", provider="openai", model="gpt-4o-mini",
            style="concise", length="medium",
            input_chars=100, input_tokens=25, output_tokens=10,
            elapsed_seconds=1.5, cost_usd=0.00001,
        )
        self.assertEqual(r.provider, "openai")
        self.assertIsInstance(r.timestamp, str)


class _TestOpenAIMocked(unittest.TestCase):
    def _fake_response(self, text: str):
        c = MagicMock(); c.message.content = text
        u = MagicMock(); u.prompt_tokens = 100; u.completion_tokens = 30
        r = MagicMock(); r.choices = [c]; r.usage = u
        return r

    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-fake"})
    def test_summarise_returns_result(self):
        fake_mod = types.ModuleType("openai")
        fake_cli = MagicMock()
        fake_cli.chat.completions.create.return_value = \
            self._fake_response("AI is changing the world.")
        fake_mod.OpenAI = MagicMock(return_value=fake_cli)
        with patch.dict("sys.modules", {"openai": fake_mod}):
            s = OpenAISummarizer()
            r = s.summarise("Long article text.", style="concise", length="short")
        self.assertIsInstance(r, SummaryResult)
        self.assertEqual(r.provider, "openai")
        self.assertGreater(len(r.summary), 0)

    def test_no_key_raises(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
        with patch.dict("os.environ", env, clear=True):
            with self.assertRaises(EnvironmentError):
                OpenAISummarizer()


class _TestLoadFile(unittest.TestCase):
    def test_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_file(Path("does_not_exist_xyz.txt"))

    def test_reads_sample(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".txt",
                                         delete=False, encoding="utf-8") as f:
            f.write(SAMPLE_ARTICLE)
            tmp = Path(f.name)
        try:
            text = load_file(tmp)
            self.assertIn("artificial intelligence", text.lower())
        finally:
            tmp.unlink(missing_ok=True)


def cmd_run_tests() -> int:
    """Discover and run all embedded _Test* classes."""
    print_header("Running Embedded Unit Tests")
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()
    this_module = sys.modules[__name__]
    for name in dir(this_module):
        obj = getattr(this_module, name)
        if isinstance(obj, type) and issubclass(obj, unittest.TestCase) \
                and name.startswith("_Test"):
            suite.addTests(loader.loadTestsFromTestCase(obj))
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="AI_Content_Summarizer",
        description="🤖  AI Content Summarizer — OpenAI & Hugging Face.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            quick start:
              python AI_Content_Summarizer.py --setup          write .env + requirements.txt
              pip install -r requirements.txt
              python AI_Content_Summarizer.py --demo           summarise built-in sample
              python AI_Content_Summarizer.py --run-tests      run all 20 unit tests

            styles:  concise | detailed | bullets | eli5
            lengths: short | medium | long
            providers: openai (default) | huggingface (free)

            examples:
              python AI_Content_Summarizer.py --text "Article text…" --style bullets
              python AI_Content_Summarizer.py --file report.pdf --length long
              python AI_Content_Summarizer.py --url https://bbc.com/news/… --style eli5
              python AI_Content_Summarizer.py --file doc.txt --provider huggingface
              python AI_Content_Summarizer.py --batch articles/ --output-dir summaries/
        """),
    )

    # Utility modes (mutually exclusive)
    util = p.add_mutually_exclusive_group()
    util.add_argument("--setup",     action="store_true",
                      help="write .env.example and requirements.txt, then exit")
    util.add_argument("--demo",      action="store_true",
                      help="summarise the built-in sample article")
    util.add_argument("--run-tests", action="store_true",
                      help="run all embedded unit tests")

    # Input source
    src = p.add_mutually_exclusive_group()
    src.add_argument("--text",  metavar="STR",  help="inline text to summarise")
    src.add_argument("--file",  type=Path, metavar="PATH", help=".txt / .md / .pdf")
    src.add_argument("--url",   metavar="URL",  help="web article URL")
    src.add_argument("--batch", type=Path, metavar="DIR",
                     help="folder of .txt/.md files")

    # Provider / Model
    p.add_argument("--provider", choices=["openai","huggingface"],
                   default="openai")
    p.add_argument("--model", metavar="NAME",
                   help="override default model")

    # Summarisation
    p.add_argument("--style",  choices=["concise","detailed","bullets","eli5"],
                   default="concise")
    p.add_argument("--length", choices=["short","medium","long"],
                   default="medium")

    # Output
    p.add_argument("--output", "-o", type=Path, metavar="PATH",
                   help="save result to .txt or .json")
    p.add_argument("--output-dir", type=Path, metavar="DIR",
                   help="output directory for --batch")
    p.add_argument("--json", action="store_true",
                   help="print full result as JSON")

    # Misc
    p.add_argument("--max-chars", type=int, default=12_000,
                   help="chunk size for long texts (default: 12000)")
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--log-file", type=Path)
    p.add_argument("--no-colour", action="store_true")
    return p


def main() -> int:
    parser = build_parser()
    args   = parser.parse_args()

    if args.no_colour:
        strip_colours()

    setup_logging(args.verbose, getattr(args, "log_file", None))

    # ── Utility modes ─────────────────────────────────────────────────────────
    if args.setup:
        return cmd_setup()

    if args.run_tests:
        return cmd_run_tests()

    if args.demo:
        args.text = SAMPLE_ARTICLE
        args.style = "bullets"
        args.length = "medium"

    # ── Build provider ────────────────────────────────────────────────────────
    if not (args.text or args.file or args.url or args.batch):
        parser.print_help()
        return 1

    try:
        summarizer = (OpenAISummarizer if args.provider == "openai"
                      else HuggingFaceSummarizer)(model=args.model)
    except (EnvironmentError, ImportError) as exc:
        print(f"\n{RED}Setup error:{RESET} {exc}\n")
        return 1

    # ── Batch ─────────────────────────────────────────────────────────────────
    if args.batch:
        if not args.batch.is_dir():
            print(f"{RED}Error:{RESET} Not a directory: {args.batch}")
            return 1
        out_dir = args.output_dir or args.batch / "summaries"
        print_header(f"Batch Mode — {args.batch.name}")
        results  = batch_process(args.batch, out_dir, summarizer,
                                 args.style, args.length)
        total_cost = sum(r.cost_usd for r in results)
        print(f"\n  {GREEN}✔  {len(results)} file(s) processed{RESET}")
        if total_cost > 0:
            print(f"  Total cost: {GREEN}${total_cost:.6f} USD{RESET}\n")
        return 0

    # ── Single text ───────────────────────────────────────────────────────────
    source_label = ""
    try:
        if args.text:
            text, source_label = args.text, "inline"
        elif args.file:
            text, source_label = load_file(args.file), str(args.file)
        elif args.url:
            print(f"  {DIM}Fetching {args.url}…{RESET}")
            text, source_label = load_url(args.url), args.url
        else:
            print(f"{RED}Error:{RESET} Provide --text, --file, --url, or --batch.")
            return 1
    except (FileNotFoundError, ImportError, ValueError) as exc:
        print(f"{RED}Error:{RESET} {exc}")
        return 1

    if not text.strip():
        print(f"{RED}Error:{RESET} Input is empty.")
        return 1

    print_header("AI Content Summarizer")
    print(f"  {DIM}Source  : {source_label}{RESET}")
    print(f"  {DIM}Input   : {len(text):,} chars  (~{count_tokens(text):,} tokens){RESET}")
    print(f"  {DIM}Style   : {args.style}  |  Length: {args.length}{RESET}")
    print(f"  {DIM}Provider: {args.provider}  |  Model: {args.model or '(default)'}{RESET}\n")
    print(f"  {DIM}Generating summary…{RESET}")

    try:
        result = summarize_text(text, summarizer, args.style, args.length,
                                args.max_chars)
        result.source = source_label
    except RuntimeError as exc:
        print(f"\n{RED}API error:{RESET} {exc}")
        return 1

    print()
    if args.json:
        import dataclasses
        print(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        print_result(result)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        save_result(result, args.output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
