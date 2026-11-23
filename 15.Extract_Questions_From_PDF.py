#!/usr/bin/env python3
"""
Extract_Questions_From_PDF.py - Intelligent PDF Question Extractor & Quiz Engine
================================================================================
Extracts academic, technical, interview, and exam questions from single or batch
PDF documents.

Features:
  - Multi-engine extraction: supports pypdf, PyPDF2, and pure-standard-library fallback
  - NLP-driven question classifier:
      * 5W1H interrogatives (Who, What, Where, When, Why, How)
      * Inverted auxiliary/modal verbs (Is, Are, Can, Do, Does, Would, etc.)
      * Academic imperative prompts (Explain, Calculate, Describe, Prove, Solve)
      * Enumerated exam numbers (Q1:, Question 1., 1.), Part A, Roman numerals
      * Multiple Choice Questions (MCQ) with bundled options (A, B, C, D)
  - PDF layout normalization (de-hyphenation, cross-line merging, header/footer filter)
  - Multi-factor question confidence scoring (0.0 to 1.0)
  - Multi-format export: Rich Terminal, JSON, JSONL, Markdown, CSV
  - Interactive Terminal Quizzer Mode (--quiz)
  - Built-in exam PDF sample generator (--create-sample)
  - Embedded 20+ unit test suite (--run-tests)

License: MIT
Python: 3.10+
Dependencies: pypdf (preferred, optional fallback included), standard library
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import glob
import io
import json
import os
import re
import sys
import time
import unittest
from typing import Any, Dict, Generator, List, Optional, Set, Tuple

# Try importing pypdf / PyPDF2
try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    try:
        import PyPDF2 as pypdf  # type: ignore
        HAS_PYPDF = True
    except ImportError:
        HAS_PYPDF = False


# ==============================================================================
# LINGUISTIC PATTERNS & REGEX DEFINITIONS
# ==============================================================================

WH_WORDS: Set[str] = {
    "what", "why", "when", "where", "who", "whom", "whose", "which", "how"
}

AUX_VERBS: Set[str] = {
    "is", "are", "am", "was", "were", "do", "does", "did",
    "can", "could", "should", "would", "may", "might", "must",
    "have", "has", "had", "shall", "will"
}

NEGATIVE_CONTRACTIONS: Set[str] = {
    "isn't", "aren't", "wasn't", "weren't", "don't", "doesn't", "didn't",
    "can't", "couldn't", "shouldn't", "wouldn't", "haven't", "hasn't", "won't"
}

IMPERATIVE_VERBS: Set[str] = {
    "explain", "describe", "discuss", "calculate", "compute", "determine",
    "find", "derive", "solve", "estimate", "compare", "differentiate",
    "distinguish", "identify", "list", "state", "define", "illustrate",
    "outline", "summarize", "summarise", "prove", "show", "verify",
    "demonstrate", "implement", "write", "design", "evaluate", "analyze",
    "analyse", "classify", "trace", "contrast", "justify"
}

# Regex to match question numbering prefixes:
# e.g., "Q1.", "Q 1:", "Q.4:", "Question 2:", "Problem 4.", "1.", "1)", "(1)", "[1]", "IV."
RE_QUESTION_PREFIX = re.compile(
    r"^(?:"
    r"(?:question|problem|exercise|task|item|q)\.?\s*#?\s*\d+[\.\:\)\-]*"
    r"|\d+[\.\:\)\-]"
    r"|\([0-9ivxIVX]+\)"
    r"|\[[0-9ivxIVX]+\]"
    r"|(?:[ivxIVX]+)[\.\:\)\-]"
    r")\s*",
    re.IGNORECASE
)

# Regex to match MCQ option lines: e.g., "(A) Option", "A. Option", "a) Option", "(1) Option"
RE_MCQ_OPTION = re.compile(
    r"^\s*(?:\(([A-Da-d])\)|\[([A-Da-d])\]|\(([1-4])\)|\[([1-4])\]|([A-Da-d])[\.\:\)\-])\s+(.+)$"
)

# Headers, Footers, and Section dividers to strip
RE_HEADER_FOOTER = re.compile(
    r"^(?:"
    r"page\s+\d+(\s+of\s+\d+)?"
    r"|\d+\s+of\s+\d+"
    r"|---\s*page\s*\d+\s*---"
    r"|all\s+rights\s+reserved"
    r"|confidential"
    r"|section\s+[a-z0-9]+[\:\.\s\-].*"
    r"|part\s+[a-z0-9]+[\:\.\s\-].*"
    r"|end\s+of\s+.*"
    r")$",
    re.IGNORECASE
)


# ==============================================================================
# DATA MODELS
# ==============================================================================

@dataclasses.dataclass
class ExtractedQuestion:
    """Represents a question extracted from a PDF document."""
    question_id: str
    source_file: str
    page_number: int
    raw_number: Optional[str]
    question_text: str
    question_type: str        # 'INTERROGATIVE' | 'INQUIRY' | 'IMPERATIVE_TASK' | 'MULTIPLE_CHOICE' | 'EXAM_PROMPT'
    confidence: float          # 0.0 to 1.0
    options: List[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.question_id,
            "source_file": self.source_file,
            "page": self.page_number,
            "number": self.raw_number,
            "type": self.question_type,
            "confidence": round(self.confidence, 2),
            "text": self.question_text,
            "options": self.options,
        }


# ==============================================================================
# PDF TEXT EXTRACTOR ENGINE
# ==============================================================================

class PdfTextExtractor:
    """Extracts text pages from PDF documents with multi-engine fallback."""

    @staticmethod
    def extract_pages(pdf_path: str) -> List[Tuple[int, str]]:
        """
        Extracts (page_number, page_text) tuples from a PDF file.
        1-indexed page numbers.
        """
        if not os.path.isfile(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        results: List[Tuple[int, str]] = []

        if HAS_PYPDF:
            try:
                reader = pypdf.PdfReader(pdf_path)
                for idx, page in enumerate(reader.pages, start=1):
                    txt = page.extract_text() or ""
                    results.append((idx, txt))
                return results
            except Exception as e:
                # If pypdf fails, fallback to stream search
                pass

        # Fallback pure-python basic stream text reader (for uncompressed/standard text streams)
        results = PdfTextExtractor._fallback_extract(pdf_path)
        return results

    @staticmethod
    def _fallback_extract(pdf_path: str) -> List[Tuple[int, str]]:
        """A simple stream scanner fallback for basic uncompressed text PDFs."""
        pages: List[Tuple[int, str]] = []
        try:
            with open(pdf_path, "rb") as f:
                content = f.read().decode("latin1", errors="ignore")

            # Find all BT ... ET text blocks
            bt_blocks = re.findall(r"BT(.*?)ET", content, re.DOTALL)
            all_lines: List[str] = []
            for block in bt_blocks:
                # Extract strings inside parentheses: (Text) Tj or (Text) '
                strings = re.findall(r"\((.*?)\)\s*(?:Tj|'|\")", block)
                for s in strings:
                    # Unescape parens and backslashes
                    s = s.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
                    all_lines.append(s)

            full_text = "\n".join(all_lines)
            pages.append((1, full_text if full_text else "[Binary or compressed PDF requires 'pypdf' package]"))
        except Exception as ex:
            pages.append((1, f"[Error reading PDF: {ex}]"))
        return pages


# ==============================================================================
# QUESTION CLASSIFIER & NORMALIZATION ENGINE
# ==============================================================================

class QuestionClassifier:
    """
    Normalizes PDF layout quirks and classifies text spans into questions
    using lexical, structural, and grammatical heuristics.
    """

    @classmethod
    def normalize_text(cls, raw_text: str) -> List[str]:
        """
        Cleans headers/footers, repairs hyphenated words across lines,
        and produces clean logical lines.
        """
        # De-hyphenate line breaks: e.g. "connec-\ntion" -> "connection"
        text = re.sub(r"(\w+)-\n\s*(\w+)", r"\1\2", raw_text)
        
        lines = [line.strip() for line in text.split("\n")]
        clean_lines: List[str] = []

        for line in lines:
            if not line:
                clean_lines.append("")
                continue
            # Strip pure header/footer lines
            if RE_HEADER_FOOTER.match(line):
                continue
            clean_lines.append(line)

        return clean_lines

    @classmethod
    def extract_questions_from_page(
        cls,
        page_num: int,
        raw_text: str,
        source_file: str,
        min_confidence: float = 0.5
    ) -> List[ExtractedQuestion]:
        """
        Scans a page of text, detects question boundaries, attaches MCQ options,
        calculates confidence scores, and returns ExtractedQuestion instances.
        """
        lines = cls.normalize_text(raw_text)
        questions: List[ExtractedQuestion] = []

        current_prompt_lines: List[str] = []
        current_options: List[str] = []
        current_raw_num: Optional[str] = None
        global_q_counter = 1

        def flush_current():
            nonlocal current_prompt_lines, current_options, current_raw_num, global_q_counter
            if not current_prompt_lines:
                return

            full_text = " ".join(current_prompt_lines).strip()
            # Clean duplicate internal whitespace
            full_text = re.sub(r"\s+", " ", full_text)

            q_type, conf = cls.evaluate_candidate(full_text, bool(current_options), bool(current_raw_num))

            if conf >= min_confidence and len(full_text) > 8:
                qid = f"Q-{page_num:02d}-{len(questions)+1:02d}"
                q = ExtractedQuestion(
                    question_id=qid,
                    source_file=os.path.basename(source_file),
                    page_number=page_num,
                    raw_number=current_raw_num,
                    question_text=full_text,
                    question_type=q_type,
                    confidence=conf,
                    options=list(current_options)
                )
                questions.append(q)

            current_prompt_lines = []
            current_options = []
            current_raw_num = None

        for line in lines:
            if not line:
                continue

            if RE_HEADER_FOOTER.match(line):
                flush_current()
                continue

            # 1. Check if line starts a new question via numbered prefix
            prefix_match = RE_QUESTION_PREFIX.match(line)
            if prefix_match:
                # Flush previous question
                flush_current()
                prefix = prefix_match.group(0).strip()
                # Clean prefix from text
                body = line[len(prefix_match.group(0)):].strip()
                current_raw_num = prefix.rstrip(".:)-# ")
                current_prompt_lines.append(body)
                continue

            # 2. Check if line is an MCQ Option: (A), B., etc.
            mcq_match = RE_MCQ_OPTION.match(line)
            if mcq_match and current_prompt_lines:
                opt_letter = (
                    mcq_match.group(1) or mcq_match.group(2) or
                    mcq_match.group(3) or mcq_match.group(4) or mcq_match.group(5)
                )
                opt_text = mcq_match.group(6).strip()
                current_options.append(f"({opt_letter.upper()}) {opt_text}")
                continue

            # 3. Check if line starts a new standalone question (5W1H or Aux or Imperative)
            first_word = line.split()[0].lower().rstrip("?:,.")
            is_new_direct = (
                first_word in WH_WORDS or
                first_word in AUX_VERBS or
                first_word in NEGATIVE_CONTRACTIONS or
                (first_word in IMPERATIVE_VERBS and line.endswith("?"))
            )

            # If current question ends with ?, or has options, this new line is a new question
            prev_ended = False
            if current_prompt_lines:
                last_line = current_prompt_lines[-1].strip()
                if last_line.endswith("?") or current_options:
                    prev_ended = True

            if is_new_direct and prev_ended:
                flush_current()
                current_prompt_lines.append(line)
                continue

            # Otherwise, line continues previous prompt or begins one
            if current_prompt_lines:
                current_prompt_lines.append(line)
            else:
                # Potential unnumbered question candidate
                if is_new_direct or line.endswith("?") or first_word in IMPERATIVE_VERBS:
                    current_prompt_lines.append(line)

        flush_current()
        return questions

    @classmethod
    def evaluate_candidate(
        cls,
        text: str,
        has_options: bool = False,
        has_number: bool = False
    ) -> Tuple[str, float]:
        """
        Determines the question type and computes a confidence score [0.0, 1.0].
        """
        score = 0.0
        words = text.split()
        if not words:
            return "UNKNOWN", 0.0

        first_word = words[0].lower().rstrip("?:,.")
        ends_with_qmark = text.rstrip().endswith("?")

        # 1. Punctuation factor
        if ends_with_qmark:
            score += 0.40

        # 2. Interrogative starter factor (5W1H)
        is_5w1h = first_word in WH_WORDS
        is_aux = first_word in AUX_VERBS or first_word in NEGATIVE_CONTRACTIONS
        is_imperative = first_word in IMPERATIVE_VERBS

        if is_5w1h:
            score += 0.35
        elif is_aux:
            score += 0.25
        elif is_imperative:
            score += 0.30

        # 3. Enumeration prefix factor
        if has_number:
            score += 0.25

        # 4. MCQ options factor
        if has_options:
            score += 0.25

        # Cap score at 1.0
        confidence = min(round(score, 2), 1.0)

        # Determine Question Type
        if has_options:
            q_type = "MULTIPLE_CHOICE"
        elif is_5w1h:
            q_type = "INTERROGATIVE"
        elif is_aux or (ends_with_qmark and not is_imperative):
            q_type = "INQUIRY"
        elif is_imperative:
            q_type = "IMPERATIVE_TASK"
        elif has_number:
            q_type = "EXAM_PROMPT"
        else:
            q_type = "GENERAL_QUESTION"

        return q_type, confidence


# ==============================================================================
# SAMPLE PDF GENERATOR (BUILT-IN DEMO GENERATOR)
# ==============================================================================

class SamplePdfGenerator:
    """
    Creates a valid, multi-page academic examination PDF with mixed question
    types using pure standard library byte streaming (zero external dependencies).
    """

    @staticmethod
    def generate_exam_pdf(output_path: str) -> str:
        """Writes a realistic 2-page examination paper."""
        page1_lines = [
            "DEPARTMENT OF COMPUTER SCIENCE & SOFTWARE ENGINEERING",
            "CS-401: Advanced Systems & Distributed Architecture (Midterm Exam)",
            "Time Allowed: 120 Minutes | Total Marks: 50 | Page 1 of 2",
            "--------------------------------------------------------------------------------",
            "SECTION A: MULTIPLE CHOICE QUESTIONS",
            "",
            "1. What is the primary advantage of user-level threads over kernel threads?",
            "   (A) Faster context switching without kernel trap",
            "   (B) True multi-core hardware parallel execution",
            "   (C) Direct access to privileged instructions",
            "   (D) Immunity from page faults",
            "",
            "2. Which protocol ensures reliable, in-order byte stream delivery over IP?",
            "   (A) UDP",
            "   (B) ICMP",
            "   (C) TCP",
            "   (D) IGMP",
            "",
            "3. Why does Python utilize a Global Interpreter Lock (GIL)?",
            "   (A) To facilitate non-blocking multi-threading",
            "   (B) To simplify memory management and reference counting safety",
            "   (C) To accelerate Just-In-Time compilation",
            "   (D) To interface with GPU shaders",
            "",
            "SECTION B: INTERROGATIVE & ANALYTICAL INQUIRIES",
            "",
            "4. How does the Raft consensus algorithm guarantee leader completeness?",
            "5. Can a deadlock occur if all processes request resources in ascending order?",
        ]

        page2_lines = [
            "DEPARTMENT OF COMPUTER SCIENCE (Page 2 of 2)",
            "SECTION C: IMPERATIVE & ALGORITHMIC TASKS",
            "",
            "6. Explain the difference between optimistic and pessimistic concurrency control.",
            "7. Calculate the maximum theoretical throughput of a 10Gbps Ethernet link with 1500-byte MTU.",
            "8. Describe how consistent hashing minimizes key remapping in distributed caches.",
            "9. Derive the time complexity of QuickSelect in the average and worst cases.",
            "10. Is an ACID database strictly required for write-heavy append-only telemetry?",
            "",
            "END OF EXAMINATION PAPER",
        ]

        pdf_bytes = SamplePdfGenerator._build_two_page_pdf(page1_lines, page2_lines)
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        return output_path

    @staticmethod
    def _build_two_page_pdf(lines_p1: List[str], lines_p2: List[str]) -> bytes:
        """Constructs a standard 2-page PDF byte buffer."""
        def make_stream(lines: List[str]) -> bytes:
            content = "BT\n/F1 11 Tf\n14 TL\n54 730 Td\n"
            for line in lines:
                clean = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                content += f"({clean}) ' \n"
            content += "ET\n"
            return content.encode("latin1")

        s1 = make_stream(lines_p1)
        s2 = make_stream(lines_p2)

        obj_cat = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        obj_pages = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>\nendobj\n"
        obj_p1 = b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>\nendobj\n"
        obj_p2 = b"4 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 7 0 R >>\nendobj\n"
        obj_font = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        obj_s1 = f"6 0 obj\n<< /Length {len(s1)} >>\nstream\n".encode("latin1") + s1 + b"\nendstream\nendobj\n"
        obj_s2 = f"7 0 obj\n<< /Length {len(s2)} >>\nstream\n".encode("latin1") + s2 + b"\nendstream\nendobj\n"

        header = b"%PDF-1.4\n"
        body = header
        offsets = [0]
        objects = [obj_cat, obj_pages, obj_p1, obj_p2, obj_font, obj_s1, obj_s2]

        for obj in objects:
            offsets.append(len(body))
            body += obj

        xref_pos = len(body)
        xref = f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("latin1")
        for off in offsets[1:]:
            xref += f"{off:010d} 00000 n \n".encode("latin1")

        trailer = f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin1")
        return body + xref + trailer


# ==============================================================================
# EXPORT MANAGERS (TERMINAL, JSON, CSV, MARKDOWN)
# ==============================================================================

class QuestionExporter:
    """Exports structured question data into various target formats."""

    @staticmethod
    def to_terminal(questions: List[ExtractedQuestion]) -> None:
        """Pretty-prints colorized question cards to stdout."""
        type_colors = {
            "INTERROGATIVE": "\033[96m",   # Cyan
            "INQUIRY": "\033[94m",         # Blue
            "IMPERATIVE_TASK": "\033[93m", # Yellow
            "MULTIPLE_CHOICE": "\033[92m", # Green
            "EXAM_PROMPT": "\033[95m",     # Magenta
            "GENERAL_QUESTION": "\033[97m" # White
        }
        reset = "\033[0m"
        bold = "\033[1m"
        dim = "\033[2m"

        for q in questions:
            color = type_colors.get(q.question_type, reset)
            num_label = f"[{q.raw_number}] " if q.raw_number else ""
            print(f"{bold}{color}┌── {q.question_id} {dim}(Page {q.page_number} | {q.source_file}){reset}")
            print(f"{color}│ {bold}{q.question_type}{reset} {dim}• Conf: {int(q.confidence * 100)}%{reset}")
            print(f"│ {bold}{num_label}{q.question_text}{reset}")

            if q.options:
                for opt in q.options:
                    print(f"│   {dim}↳{reset} {opt}")
            print(f"└─────────────────────────────────────────────────────────────\n")

    @staticmethod
    def to_json(questions: List[ExtractedQuestion], output_path: str, indent: int = 2) -> None:
        """Saves questions list as JSON."""
        data = [q.to_dict() for q in questions]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)

    @staticmethod
    def to_jsonl(questions: List[ExtractedQuestion], output_path: str) -> None:
        """Saves questions as newline-delimited JSON (JSONL)."""
        with open(output_path, "w", encoding="utf-8") as f:
            for q in questions:
                f.write(json.dumps(q.to_dict(), ensure_ascii=False) + "\n")

    @staticmethod
    def to_csv(questions: List[ExtractedQuestion], output_path: str) -> None:
        """Saves questions as CSV spreadsheet."""
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Source File", "Page", "Number", "Type", "Confidence", "Question Text", "Options"])
            for q in questions:
                writer.writerow([
                    q.question_id,
                    q.source_file,
                    q.page_number,
                    q.raw_number or "",
                    q.question_type,
                    f"{q.confidence:.2f}",
                    q.question_text,
                    " | ".join(q.options)
                ])

    @staticmethod
    def to_markdown(questions: List[ExtractedQuestion], output_path: str) -> None:
        """Exports questions organized as a structured Markdown study checklist."""
        lines = [
            "# 📚 Extracted PDF Questions Repository",
            f"*Generated on {time.strftime('%Y-%m-%d %H:%M:%S')} | Total Questions: {len(questions)}*\n",
            "---",
        ]

        # Group by source file and page
        by_file: Dict[str, Dict[int, List[ExtractedQuestion]]] = {}
        for q in questions:
            by_file.setdefault(q.source_file, {}).setdefault(q.page_number, []).append(q)

        for src, pages in by_file.items():
            lines.append(f"\n## 📄 Source: `{src}`\n")
            for page_num, q_list in pages.items():
                lines.append(f"### Page {page_num}\n")
                for q in q_list:
                    prefix = f"**{q.raw_number}.** " if q.raw_number else ""
                    conf_pct = int(q.confidence * 100)
                    lines.append(f"- [ ] {prefix}{q.question_text} `[{q.question_type} | {conf_pct}%]`")
                    if q.options:
                        for opt in q.options:
                            lines.append(f"  - {opt}")
                lines.append("")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


# ==============================================================================
# INTERACTIVE TERMINAL QUIZZER MODE
# ==============================================================================

def run_interactive_quiz(questions: List[ExtractedQuestion]) -> None:
    """Launches an interactive flashcard quiz session in the terminal."""
    if not questions:
        print("No questions available for quiz mode.")
        return

    print("════════════════════════════════════════════════════════════════")
    print("  🧠   PDF QUESTION EXTRACTOR — INTERACTIVE QUIZ MODE")
    print(f"  Loaded {len(questions)} question(s) from document(s).")
    print("  Type your response or press [ENTER] to reveal / proceed.")
    print("  Type 'q' or 'exit' at any time to return.")
    print("════════════════════════════════════════════════════════════════\n")

    for idx, q in enumerate(questions, start=1):
        num_str = f"#{q.raw_number} " if q.raw_number else ""
        print(f"────────────────────────────────────────────────────────────────")
        print(f"  Question {idx}/{len(questions)}  [Page {q.page_number} | {q.question_type}]")
        print(f"  {num_str}{q.question_text}\n")

        if q.options:
            for opt in q.options:
                print(f"    {opt}")
            print()

        try:
            ans = input("  Your Answer / Notes > ").strip()
            if ans.lower() in ("q", "exit"):
                print("\nQuiz session ended by user.")
                break
        except (KeyboardInterrupt, EOFError):
            print("\nQuiz aborted.")
            break

        print(f"  ✅ Saved! Moving to next question...\n")

    print("\n════════════════════════════════════════════════════════════════")
    print(f"  🎉 Quiz session complete! Practiced {idx} question(s).")
    print("════════════════════════════════════════════════════════════════\n")


# ==============================================================================
# PIPELINE ORCHESTRATOR
# ==============================================================================

class QuestionExtractionPipeline:
    """Coordinates multi-file extraction, classification, filtering, and export."""

    def __init__(self, min_confidence: float = 0.5):
        self.min_confidence = min_confidence

    def process_file(self, file_path: str) -> List[ExtractedQuestion]:
        """Extracts questions from a single PDF file."""
        pages = PdfTextExtractor.extract_pages(file_path)
        all_questions: List[ExtractedQuestion] = []
        for page_num, raw_text in pages:
            qs = QuestionClassifier.extract_questions_from_page(
                page_num=page_num,
                raw_text=raw_text,
                source_file=file_path,
                min_confidence=self.min_confidence
            )
            all_questions.extend(qs)
        return all_questions

    def process_directory(
        self,
        dir_path: str,
        pattern: str = "*.pdf",
        recursive: bool = False
    ) -> List[ExtractedQuestion]:
        """Scans a directory of PDFs and aggregates extracted questions."""
        if not os.path.isdir(dir_path):
            raise NotADirectoryError(f"Directory not found: {dir_path}")

        search_path = os.path.join(dir_path, "**" if recursive else "", pattern)
        pdf_files = glob.glob(search_path, recursive=recursive)

        all_questions: List[ExtractedQuestion] = []
        for pdf in sorted(pdf_files):
            try:
                qs = self.process_file(pdf)
                all_questions.extend(qs)
            except Exception as e:
                print(f"⚠️  Warning: Failed to process '{pdf}': {e}", file=sys.stderr)

        return all_questions


# ==============================================================================
# EMBEDDED UNIT TEST SUITE (20+ TESTS)
# ==============================================================================

class _TestLinguisticHeuristics(unittest.TestCase):
    def test_5w1h_interrogatives(self):
        text = "What is the computational complexity of Dijkstra's algorithm?"
        q_type, conf = QuestionClassifier.evaluate_candidate(text)
        self.assertEqual(q_type, "INTERROGATIVE")
        self.assertGreaterEqual(conf, 0.70)

    def test_why_interrogative(self):
        text = "Why do neural networks experience vanishing gradients?"
        q_type, conf = QuestionClassifier.evaluate_candidate(text)
        self.assertEqual(q_type, "INTERROGATIVE")
        self.assertGreaterEqual(conf, 0.70)

    def test_auxiliary_inquiry(self):
        text = "Is Python an interpreted language?"
        q_type, conf = QuestionClassifier.evaluate_candidate(text)
        self.assertEqual(q_type, "INQUIRY")
        self.assertGreaterEqual(conf, 0.60)

    def test_negative_contraction_inquiry(self):
        text = "Isn't HTTP a stateless application layer protocol?"
        q_type, conf = QuestionClassifier.evaluate_candidate(text)
        self.assertEqual(q_type, "INQUIRY")
        self.assertGreaterEqual(conf, 0.60)

    def test_imperative_prompt(self):
        text = "Explain the difference between TCP and UDP sockets."
        q_type, conf = QuestionClassifier.evaluate_candidate(text)
        self.assertEqual(q_type, "IMPERATIVE_TASK")
        self.assertGreaterEqual(conf, 0.20)

    def test_imperative_with_question_mark(self):
        text = "Can you calculate the standard deviation of the sample?"
        q_type, conf = QuestionClassifier.evaluate_candidate(text)
        self.assertEqual(q_type, "INQUIRY")
        self.assertGreaterEqual(conf, 0.65)

    def test_non_question_statement(self):
        text = "The quick brown fox jumps over the lazy dog."
        q_type, conf = QuestionClassifier.evaluate_candidate(text)
        self.assertLess(conf, 0.30)


class _TestLayoutNormalization(unittest.TestCase):
    def test_dehyphenation(self):
        raw = "This is an inves-\ntigation into system design."
        cleaned = QuestionClassifier.normalize_text(raw)
        self.assertIn("This is an investigation into system design.", cleaned)

    def test_header_footer_stripping(self):
        raw = "Page 1 of 5\nQuestion 1: What is RAM?\nConfidential"
        cleaned = QuestionClassifier.normalize_text(raw)
        self.assertNotIn("Page 1 of 5", cleaned)
        self.assertNotIn("Confidential", cleaned)
        self.assertIn("Question 1: What is RAM?", cleaned)


class _TestExtractionParser(unittest.TestCase):
    def test_mcq_option_extraction(self):
        raw = (
            "1. Which sorting algorithm has O(n log n) worst-case?\n"
            "   (A) QuickSort\n"
            "   (B) MergeSort\n"
            "   (C) BubbleSort\n"
            "   (D) InsertionSort\n"
        )
        qs = QuestionClassifier.extract_questions_from_page(1, raw, "exam.pdf")
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0].question_type, "MULTIPLE_CHOICE")
        self.assertEqual(len(qs[0].options), 4)
        self.assertIn("(A) QuickSort", qs[0].options[0])

    def test_numbered_prefix_parsed(self):
        raw = "Q.4: How does a B-Tree balance itself?"
        qs = QuestionClassifier.extract_questions_from_page(1, raw, "exam.pdf")
        self.assertEqual(len(qs), 1)
        self.assertIn("B-Tree", qs[0].question_text)
        self.assertIn("4", qs[0].raw_number)

    def test_multi_question_page(self):
        raw = (
            "1. What is virtual memory?\n"
            "2. How does paging prevent external fragmentation?\n"
            "3. Define thrashing in operating systems.\n"
        )
        qs = QuestionClassifier.extract_questions_from_page(1, raw, "exam.pdf")
        self.assertEqual(len(qs), 3)

    def test_roman_numeral_prefix(self):
        raw = "IV. Calculate the determinant of matrix A."
        qs = QuestionClassifier.extract_questions_from_page(1, raw, "exam.pdf")
        self.assertEqual(len(qs), 1)
        self.assertIn("Calculate", qs[0].question_text)

    def test_confidence_filtering(self):
        raw = (
            "1. What is the fundamental difference between processes and threads in Linux?\n"
            "2. Note that this is just a general informational note.\n"
        )
        qs_strict = QuestionClassifier.extract_questions_from_page(1, raw, "exam.pdf", min_confidence=0.8)
        self.assertEqual(len(qs_strict), 1)
        self.assertIn("processes and threads", qs_strict[0].question_text)



class _TestSamplePdfGeneration(unittest.TestCase):
    def setUp(self):
        self.test_pdf = "temp_test_exam.pdf"

    def tearDown(self):
        if os.path.exists(self.test_pdf):
            os.remove(self.test_pdf)

    def test_generate_and_extract(self):
        SamplePdfGenerator.generate_exam_pdf(self.test_pdf)
        self.assertTrue(os.path.exists(self.test_pdf))
        self.assertGreater(os.path.getsize(self.test_pdf), 500)

        pipeline = QuestionExtractionPipeline(min_confidence=0.4)
        questions = pipeline.process_file(self.test_pdf)
        self.assertGreaterEqual(len(questions), 5)
        # Verify MCQ presence
        mcqs = [q for q in questions if q.question_type == "MULTIPLE_CHOICE"]
        self.assertGreaterEqual(len(mcqs), 1)


class _TestExporters(unittest.TestCase):
    def setUp(self):
        self.sample_q = ExtractedQuestion(
            question_id="Q-01-01",
            source_file="test.pdf",
            page_number=1,
            raw_number="1",
            question_text="What is concurrency?",
            question_type="INTERROGATIVE",
            confidence=0.95,
            options=["(A) Parallel", "(B) Interleaved"]
        )
        self.tmp_files: List[str] = []

    def tearDown(self):
        for f in self.tmp_files:
            if os.path.exists(f):
                os.remove(f)

    def test_json_export(self):
        path = "temp_test.json"
        self.tmp_files.append(path)
        QuestionExporter.to_json([self.sample_q], path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "Q-01-01")

    def test_csv_export(self):
        path = "temp_test.csv"
        self.tmp_files.append(path)
        QuestionExporter.to_csv([self.sample_q], path)
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertGreaterEqual(len(lines), 2)
        self.assertIn("What is concurrency?", lines[1])

    def test_markdown_export(self):
        path = "temp_test.md"
        self.tmp_files.append(path)
        QuestionExporter.to_markdown([self.sample_q], path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Extracted PDF Questions", content)
        self.assertIn("What is concurrency?", content)

    def test_jsonl_export(self):
        path = "temp_test.jsonl"
        self.tmp_files.append(path)
        QuestionExporter.to_jsonl([self.sample_q], path)
        with open(path, "r", encoding="utf-8") as f:
            line = f.readline()
        data = json.loads(line)
        self.assertEqual(data["id"], "Q-01-01")
        self.assertEqual(data["type"], "INTERROGATIVE")

    def test_dataclass_dict_serialization(self):
        d = self.sample_q.to_dict()
        self.assertEqual(d["page"], 1)
        self.assertEqual(d["confidence"], 0.95)
        self.assertEqual(len(d["options"]), 2)



def _run_embedded_tests() -> int:
    """Runs all embedded unit tests and returns exit code."""
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTests(loader.loadTestsFromTestCase(_TestLinguisticHeuristics))
    suite.addTests(loader.loadTestsFromTestCase(_TestLayoutNormalization))
    suite.addTests(loader.loadTestsFromTestCase(_TestExtractionParser))
    suite.addTests(loader.loadTestsFromTestCase(_TestSamplePdfGeneration))
    suite.addTests(loader.loadTestsFromTestCase(_TestExporters))

    print("\n════════════════════════════════════════════════════════════════")
    print("  📚  Running PDF Question Extractor Embedded Unit Tests")
    print("════════════════════════════════════════════════════════════════\n")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


# ==============================================================================
# CLI ARGUMENT PARSER & ENTRYPOINT
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract_Questions_From_PDF.py - Intelligent PDF Question Extractor & Quiz Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python Extract_Questions_From_PDF.py --create-sample                     # Generate sample_exam.pdf
  python Extract_Questions_From_PDF.py -f sample_exam.pdf                  # Extract & print questions
  python Extract_Questions_From_PDF.py -f exam.pdf --export json -o out.json  # Export structured JSON
  python Extract_Questions_From_PDF.py -d ./papers --export md -o study.md # Batch scan folder to Markdown
  python Extract_Questions_From_PDF.py -f exam.pdf --quiz                  # Interactive terminal quizzer
  python Extract_Questions_From_PDF.py -f exam.pdf --stats                 # Document question metrics
  python Extract_Questions_From_PDF.py --run-tests                         # Run 20+ unit tests
        """
    )

    parser.add_argument("-f", "--file", type=str,
                        help="Path to a single PDF document to extract questions from")
    parser.add_argument("-d", "--dir", type=str,
                        help="Directory containing PDF files for batch extraction")
    parser.add_argument("--pattern", type=str, default="*.pdf",
                        help="Glob pattern for batch directory scan (default: '*.pdf')")
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="Recursively scan subdirectories for PDFs")
    parser.add_argument("-c", "--min-confidence", type=float, default=0.50,
                        help="Minimum question confidence threshold (0.0 to 1.0; default: 0.50)")
    parser.add_argument("--export", choices=["terminal", "json", "jsonl", "csv", "md"], default="terminal",
                        help="Output format (terminal, json, jsonl, csv, md; default: terminal)")
    parser.add_argument("-o", "--output", type=str,
                        help="Output file destination for export (required for json, csv, md)")
    parser.add_argument("--quiz", action="store_true",
                        help="Launch interactive flashcard quiz session from extracted questions")
    parser.add_argument("--stats", action="store_true",
                        help="Display question distribution and linguistic statistics")
    parser.add_argument("--create-sample", nargs="?", const="sample_exam.pdf", metavar="FILE",
                        help="Generate a realistic sample academic exam PDF (default: sample_exam.pdf)")
    parser.add_argument("--run-tests", action="store_true",
                        help="Run the embedded 20-test unit test suite")

    args = parser.parse_args()

    # 1. Run Unit Tests
    if args.run_tests:
        sys.exit(_run_embedded_tests())

    # 2. Sample PDF Generation
    if args.create_sample:
        out_pdf = args.create_sample
        print(f"Generating realistic sample examination PDF: '{out_pdf}'...")
        SamplePdfGenerator.generate_exam_pdf(out_pdf)
        print(f"✅ Created sample PDF successfully ({os.path.getsize(out_pdf)} bytes).")
        print(f"👉 You can now run: python Extract_Questions_From_PDF.py -f {out_pdf}")
        sys.exit(0)

    # Validate target source
    if not args.file and not args.dir:
        parser.print_help()
        print("\n❌ Error: Please specify a PDF file (-f FILE), a directory (-d DIR), or --create-sample")
        sys.exit(1)

    pipeline = QuestionExtractionPipeline(min_confidence=args.min_confidence)
    start_time = time.perf_counter()

    questions: List[ExtractedQuestion] = []
    if args.file:
        questions = pipeline.process_file(args.file)
    elif args.dir:
        questions = pipeline.process_directory(args.dir, pattern=args.pattern, recursive=args.recursive)

    elapsed = time.perf_counter() - start_time

    # 3. Interactive Quiz Mode
    if args.quiz:
        run_interactive_quiz(questions)
        sys.exit(0)

    # 4. Display Statistics
    if args.stats or args.export == "terminal":
        print("════════════════════════════════════════════════════════════════")
        print("  📚   PDF QUESTION EXTRACTOR RESULTS")
        print("════════════════════════════════════════════════════════════════")
        print(f"  Target Source      : {args.file or args.dir}")
        print(f"  Extraction Time    : {elapsed:.3f} seconds")
        print(f"  Confidence Cutoff  : {args.min_confidence * 100:.0f}%")
        print(f"  Total Extracted    : {len(questions)} question(s)")

        # Breakdown by category
        breakdown: Dict[str, int] = {}
        for q in questions:
            breakdown[q.question_type] = breakdown.get(q.question_type, 0) + 1

        print("\n  [Distribution by Question Type]:")
        for q_type, count in sorted(breakdown.items(), key=lambda x: -x[1]):
            pct = (count / len(questions) * 100) if questions else 0
            print(f"    - {q_type:<18} : {count:>3} ({pct:>5.1f}%)")
        print("════════════════════════════════════════════════════════════════\n")

    # 5. Export Output
    if args.export == "terminal":
        QuestionExporter.to_terminal(questions)
    elif args.export == "json":
        out_dest = args.output or "extracted_questions.json"
        QuestionExporter.to_json(questions, out_dest)
        print(f"💾 JSON exported to '{out_dest}'")
    elif args.export == "jsonl":
        out_dest = args.output or "extracted_questions.jsonl"
        QuestionExporter.to_jsonl(questions, out_dest)
        print(f"💾 JSONL exported to '{out_dest}'")
    elif args.export == "csv":
        out_dest = args.output or "extracted_questions.csv"
        QuestionExporter.to_csv(questions, out_dest)
        print(f"💾 CSV exported to '{out_dest}'")
    elif args.export == "md":
        out_dest = args.output or "extracted_questions.md"
        QuestionExporter.to_markdown(questions, out_dest)
        print(f"💾 Markdown study checklist exported to '{out_dest}'")


if __name__ == "__main__":
    main()
