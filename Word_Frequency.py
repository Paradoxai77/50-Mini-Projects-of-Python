#!/usr/bin/env python3
"""
Word Frequency Counter
======================
Project #14 of 50 Mini Projects

Compute the frequency of words from input text and display them
sorted alphanumerically. Supports single-line, multi-line, file,
and pipe input modes.

Usage:
    python Word_Frequency.py                        # interactive single-line
    python Word_Frequency.py --multi                # multi-line (Ctrl+Z/D to end)
    python Word_Frequency.py --file input.txt       # read from file
    python Word_Frequency.py --text "some words"    # inline text
    python Word_Frequency.py --top 5                # show top N most frequent
    python Word_Frequency.py --case-sensitive       # treat upper/lower as distinct
    python Word_Frequency.py --strip-punct          # remove punctuation from words
    echo "hello world" | python Word_Frequency.py   # pipe mode
"""

import argparse
import string
import sys
import textwrap
from collections import Counter
from pathlib import Path


# ─── ANSI ─────────────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
MAGENTA= "\033[95m"
WHITE  = "\033[97m"


# ─── Core Logic ───────────────────────────────────────────────────────────────

def tokenise(
    text: str,
    case_sensitive: bool = False,
    strip_punct: bool = False,
    min_length: int = 1,
) -> list[str]:
    """
    Split text into words, applying optional normalisation.

    Args:
        text:           raw input string
        case_sensitive: if False, fold to lowercase before counting
        strip_punct:    if True, strip leading/trailing punctuation from each token
        min_length:     skip tokens shorter than this (after stripping)

    Returns:
        list of processed word tokens
    """
    tokens = text.split()

    if strip_punct:
        tokens = [t.strip(string.punctuation) for t in tokens]

    if not case_sensitive:
        tokens = [t.lower() for t in tokens]

    # Drop empty strings produced by stripping
    tokens = [t for t in tokens if len(t) >= min_length]
    return tokens


def count_words(
    text: str,
    case_sensitive: bool = False,
    strip_punct: bool = False,
    min_length: int = 1,
) -> Counter:
    """Return a Counter of word frequencies from raw text."""
    tokens = tokenise(text, case_sensitive, strip_punct, min_length)
    return Counter(tokens)


def sorted_freq(freq: Counter, reverse: bool = False) -> list[tuple[str, int]]:
    """Return (word, count) pairs sorted alphanumerically by word."""
    return sorted(freq.items(), key=lambda x: x[0].lower(), reverse=reverse)


def top_n(freq: Counter, n: int) -> list[tuple[str, int]]:
    """Return the N most common (word, count) pairs, ties broken alphabetically."""
    return freq.most_common(n)


# ─── Input Readers ────────────────────────────────────────────────────────────

def read_single_line() -> str:
    """Read one line from stdin."""
    try:
        return input(f"  {CYAN}Enter text:{RESET} ")
    except EOFError:
        return ""


def read_multi_line() -> str:
    """Read multiple lines until EOF (Ctrl+D on Unix, Ctrl+Z on Windows)."""
    print(f"  {DIM}Enter text (press Ctrl+Z then Enter on Windows, Ctrl+D on Unix to finish):{RESET}")
    lines = []
    try:
        while True:
            lines.append(input())
    except EOFError:
        pass
    return " ".join(lines)


def read_file(path: Path) -> str:
    """Read text from a file."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"{RED}Error:{RESET} File not found: {path}")
        sys.exit(1)
    except OSError as exc:
        print(f"{RED}Error:{RESET} Could not read file: {exc}")
        sys.exit(1)


def read_pipe() -> str:
    """Read from stdin pipe (non-interactive)."""
    return sys.stdin.read()


# ─── Output Formatters ────────────────────────────────────────────────────────

def print_header(title: str) -> None:
    border = "═" * 60
    print(f"\n{CYAN}{border}{RESET}")
    print(f"{CYAN}  📝  {BOLD}{title}{RESET}")
    print(f"{CYAN}{border}{RESET}\n")


def _bar(count: int, max_count: int, width: int = 24) -> str:
    filled = round((count / max_count) * width) if max_count else 0
    bar    = "█" * filled + "░" * (width - filled)
    if count == max_count:
        return f"{GREEN}{bar}{RESET}"
    elif filled >= width * 0.6:
        return f"{CYAN}{bar}{RESET}"
    return f"{DIM}{bar}{RESET}"


def print_table(pairs: list[tuple[str, int]], show_bar: bool = True) -> None:
    """Print a nicely aligned frequency table with optional bar chart."""
    if not pairs:
        print(f"  {DIM}(no words found){RESET}\n")
        return

    max_word  = max(len(w) for w, _ in pairs)
    max_count = max(c for _, c in pairs)
    col_w     = max(max_word, 8)

    # Header
    print(f"  {BOLD}{DIM}{'Word':<{col_w}}  {'Count':>6}  {'Bar' if show_bar else ''}{RESET}")
    print(f"  {'─' * col_w}  {'─' * 6}  {'─' * 24 if show_bar else ''}")

    for word, count in pairs:
        bar = _bar(count, max_count) if show_bar else ""
        pct = count / sum(c for _, c in pairs) * 100
        print(
            f"  {YELLOW}{word:<{col_w}}{RESET}  "
            f"{GREEN}{BOLD}{count:>6}{RESET}  "
            f"{bar}  {DIM}{pct:4.1f}%{RESET}"
        )

    total = sum(c for _, c in pairs)
    unique = len(pairs)
    print(f"\n  {DIM}Total words: {total}  |  Unique words: {unique}{RESET}\n")


def print_simple(pairs: list[tuple[str, int]]) -> None:
    """Original exercise output format: word:count per line."""
    for word, count in pairs:
        print(f"{word}:{count}")


def print_stats(freq: Counter) -> None:
    """Print summary statistics about the frequency distribution."""
    if not freq:
        return
    total  = sum(freq.values())
    unique = len(freq)
    top3   = freq.most_common(3)
    least3 = freq.most_common()[-3:]

    print(f"  {BOLD}Statistics{RESET}")
    print(f"  {'─' * 40}")
    print(f"  {'Total words':<22} {YELLOW}{total}{RESET}")
    print(f"  {'Unique words':<22} {YELLOW}{unique}{RESET}")
    print(f"  {'Vocabulary richness':<22} {YELLOW}{unique/total*100:.1f}%{RESET}  "
          f"{DIM}(unique/total){RESET}")
    print(f"\n  {BOLD}Most common:{RESET}")
    for w, c in top3:
        print(f"    {GREEN}{w}{RESET} → {c}×")
    print(f"\n  {BOLD}Least common:{RESET}")
    for w, c in reversed(least3):
        print(f"    {DIM}{w}{RESET} → {c}×")
    print()


# ─── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Word_Frequency",
        description="📝  Word Frequency Counter — alphanumeric sort, bar chart, stats.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            input modes (mutually exclusive):
              default      single line from stdin
              --multi      multi-line from stdin until EOF
              --file PATH  read from a text file
              --text STR   inline string argument
              pipe         echo "text" | python Word_Frequency.py

            examples:
              python Word_Frequency.py
              python Word_Frequency.py --multi
              python Word_Frequency.py --file story.txt --strip-punct --top 10
              python Word_Frequency.py --text "to be or not to be" --simple
              python Word_Frequency.py --text "Hello hello HELLO" --case-sensitive
              echo "one fish two fish" | python Word_Frequency.py --simple
        """),
    )

    # Input source
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--multi", action="store_true",
                     help="read multiple lines until EOF")
    src.add_argument("--file", type=Path, metavar="PATH",
                     help="read input from a text file")
    src.add_argument("--text", metavar="STRING",
                     help="use an inline string as input")

    # Processing
    parser.add_argument("--case-sensitive", action="store_true",
                        help="treat upper and lowercase as different words")
    parser.add_argument("--strip-punct", action="store_true",
                        help="strip leading/trailing punctuation from each word")
    parser.add_argument("--min-length", type=int, default=1, metavar="N",
                        help="skip words shorter than N chars (default: 1)")

    # Output
    parser.add_argument("--top", type=int, metavar="N",
                        help="show only the top N most frequent words")
    parser.add_argument("--simple", action="store_true",
                        help="plain word:count output (original exercise format)")
    parser.add_argument("--no-bar", action="store_true",
                        help="hide the bar chart column")
    parser.add_argument("--stats", action="store_true",
                        help="show summary statistics")
    parser.add_argument("--no-colour", action="store_true",
                        help="disable ANSI colour output")

    return parser


def strip_colours() -> None:
    global RESET, BOLD, DIM, CYAN, GREEN, YELLOW, RED, MAGENTA, WHITE
    RESET = BOLD = DIM = CYAN = GREEN = YELLOW = RED = MAGENTA = WHITE = ""


def main() -> int:
    parser = build_parser()
    args   = parser.parse_args()

    if args.no_colour:
        strip_colours()

    # ── Read input ────────────────────────────────────────────────────────────
    if args.text:
        text = args.text
    elif args.file:
        text = read_file(args.file)
    elif not sys.stdin.isatty():
        text = read_pipe()          # piped input
    elif args.multi:
        print_header("Word Frequency Counter — Multi-line Mode")
        text = read_multi_line()
    else:
        print_header("Word Frequency Counter")
        text = read_single_line()

    if not text.strip():
        print(f"{RED}Error:{RESET} No input text provided.")
        return 1

    # ── Count ─────────────────────────────────────────────────────────────────
    freq = count_words(
        text,
        case_sensitive=args.case_sensitive,
        strip_punct=args.strip_punct,
        min_length=args.min_length,
    )

    if not freq:
        print(f"{RED}Error:{RESET} No words found after processing.")
        return 1

    # ── Output ────────────────────────────────────────────────────────────────
    if args.simple:
        # Original exercise format: sorted alphanumerically, word:count
        for word, count in sorted_freq(freq):
            print(f"{word}:{count}")
        return 0

    if args.top:
        pairs = top_n(freq, args.top)
        title = f"Top {args.top} Most Frequent Words"
    else:
        pairs = sorted_freq(freq)
        title = "Word Frequency — Alphanumeric Order"

    if not args.text and sys.stdin.isatty():
        pass   # header already printed
    else:
        print_header(title)

    print_table(pairs, show_bar=not args.no_bar)

    if args.stats:
        print_stats(freq)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
