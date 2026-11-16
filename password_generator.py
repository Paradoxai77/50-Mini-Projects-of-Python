#!/usr/bin/env python3
"""
Password Generator
==================
Project #6 of 50 Mini Projects

Generate cryptographically secure random passwords of any length
using any combination of character sets: uppercase, lowercase,
digits, and symbols.

Supports bulk generation, strength analysis, clipboard copy,
exclusion of ambiguous characters, and custom symbol sets.

Usage:
    python password_generator.py                     # 16-char default
    python password_generator.py -n 24              # 24 characters
    python password_generator.py -n 32 --count 5   # 5 passwords of 32 chars
    python password_generator.py --no-symbols       # letters + digits only
    python password_generator.py --only-digits -n 6 # 6-digit PIN
    python password_generator.py --no-ambiguous     # skip 0/O/l/1/I
    python password_generator.py --analyse "Tr0ub4dor&3"
"""

import secrets
import string
import argparse
import textwrap
import sys
import math
from dataclasses import dataclass, field


# ─── Character Sets ───────────────────────────────────────────────────────────

UPPERCASE  = string.ascii_uppercase          # A-Z
LOWERCASE  = string.ascii_lowercase          # a-z
DIGITS     = string.digits                   # 0-9
SYMBOLS    = "!@#$%^&*()-_=+[]{}|;:,.<>?"   # curated safe set
AMBIGUOUS  = set("0O1lI")                    # visually confusable chars

# ANSI
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[91m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
MAGENTA= "\033[95m"
WHITE  = "\033[97m"


# ─── Strength Analyser ────────────────────────────────────────────────────────

@dataclass
class StrengthReport:
    password:    str
    length:      int
    entropy:     float          # bits
    pool_size:   int
    has_upper:   bool
    has_lower:   bool
    has_digit:   bool
    has_symbol:  bool
    score:       int            # 0-4
    label:       str
    suggestions: list[str] = field(default_factory=list)


def analyse_password(pwd: str) -> StrengthReport:
    """
    Compute Shannon entropy and a 0-4 strength score for `pwd`.
    Entropy = length × log₂(pool_size).
    """
    has_upper  = any(c in UPPERCASE for c in pwd)
    has_lower  = any(c in LOWERCASE for c in pwd)
    has_digit  = any(c in DIGITS    for c in pwd)
    has_symbol = any(c in SYMBOLS or c in string.punctuation for c in pwd)

    pool = 0
    if has_upper:  pool += 26
    if has_lower:  pool += 26
    if has_digit:  pool += 10
    if has_symbol: pool += len(SYMBOLS)

    pool = max(pool, 1)
    entropy = len(pwd) * math.log2(pool)

    # Score: 0=very weak … 4=very strong
    suggestions: list[str] = []
    score = 0

    if entropy >= 28:  score += 1
    if entropy >= 40:  score += 1
    if entropy >= 60:  score += 1
    if entropy >= 80:  score += 1

    if len(pwd) < 8:
        suggestions.append("Use at least 8 characters.")
    if not has_upper:
        suggestions.append("Add uppercase letters (A-Z).")
    if not has_lower:
        suggestions.append("Add lowercase letters (a-z).")
    if not has_digit:
        suggestions.append("Add digits (0-9).")
    if not has_symbol:
        suggestions.append("Add symbols (!@#$…).")
    if len(pwd) < 12 and score < 3:
        suggestions.append("Consider 12+ characters for stronger security.")

    labels = ["Very Weak", "Weak", "Fair", "Strong", "Very Strong"]
    return StrengthReport(
        password=pwd, length=len(pwd), entropy=round(entropy, 1),
        pool_size=pool, has_upper=has_upper, has_lower=has_lower,
        has_digit=has_digit, has_symbol=has_symbol,
        score=score, label=labels[score], suggestions=suggestions,
    )


# ─── Generator ────────────────────────────────────────────────────────────────

def build_alphabet(
    use_upper:    bool = True,
    use_lower:    bool = True,
    use_digits:   bool = True,
    use_symbols:  bool = True,
    no_ambiguous: bool = False,
    custom_symbols: str | None = None,
) -> str:
    """
    Assemble the character pool from the requested sets.
    Raises ValueError if the resulting alphabet is empty.
    """
    pool = ""
    if use_upper:   pool += UPPERCASE
    if use_lower:   pool += LOWERCASE
    if use_digits:  pool += DIGITS
    if use_symbols:
        pool += custom_symbols if custom_symbols is not None else SYMBOLS

    if no_ambiguous:
        pool = "".join(c for c in pool if c not in AMBIGUOUS)

    if not pool:
        raise ValueError(
            "Character pool is empty. Enable at least one character set."
        )
    return pool


def generate_password(
    length:    int,
    alphabet:  str,
    *,
    must_include: list[str] | None = None,
) -> str:
    """
    Generate a single cryptographically secure password.

    If `must_include` is a list of character-set strings, the password
    is guaranteed to contain at least one character from each set
    (rejection-sample approach — always terminates quickly).
    """
    if length < 1:
        raise ValueError("Password length must be at least 1.")

    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if must_include:
            if all(any(c in charset for c in pwd) for charset in must_include):
                return pwd
        else:
            return pwd


def generate_batch(
    count:        int,
    length:       int,
    alphabet:     str,
    must_include: list[str] | None = None,
) -> list[str]:
    return [generate_password(length, alphabet, must_include=must_include)
            for _ in range(count)]


# ─── Output Formatters ────────────────────────────────────────────────────────

def strength_bar(score: int, width: int = 20) -> str:
    colours = [RED, RED, YELLOW, GREEN, GREEN + BOLD]
    filled  = int((score / 4) * width)
    bar     = "█" * filled + "░" * (width - filled)
    return f"{colours[score]}{bar}{RESET}"


def print_header(title: str) -> None:
    border = "═" * 62
    print(f"\n{CYAN}{border}{RESET}")
    print(f"{CYAN}  🔐  {BOLD}{title}{RESET}")
    print(f"{CYAN}{border}{RESET}\n")


def print_password(pwd: str, index: int | None = None) -> None:
    prefix = f"  {DIM}#{index:<3}{RESET}" if index is not None else "  "
    # Colour-code character types inline
    coloured = ""
    for ch in pwd:
        if ch in UPPERCASE:
            coloured += f"{CYAN}{ch}{RESET}"
        elif ch in LOWERCASE:
            coloured += f"{WHITE}{ch}{RESET}"
        elif ch in DIGITS:
            coloured += f"{YELLOW}{ch}{RESET}"
        else:
            coloured += f"{MAGENTA}{ch}{RESET}"
    print(f"{prefix}{BOLD}{coloured}")


def print_strength(report: StrengthReport) -> None:
    score_colours = [RED, RED, YELLOW, GREEN, GREEN]
    sc = score_colours[report.score]
    bar = strength_bar(report.score)

    print(f"\n  {BOLD}Strength Analysis{RESET}")
    print(f"  {'─' * 40}")
    print(f"  Password  : {BOLD}{report.password}{RESET}")
    print(f"  Length    : {report.length} characters")
    print(f"  Pool Size : {report.pool_size} unique characters")
    print(f"  Entropy   : {CYAN}{report.entropy} bits{RESET}")
    print(f"  Strength  : {bar}  {sc}{BOLD}{report.label}{RESET}")
    print()

    checks = [
        ("Uppercase (A-Z)",  report.has_upper),
        ("Lowercase (a-z)",  report.has_lower),
        ("Digits (0-9)",     report.has_digit),
        ("Symbols (!@#…)",   report.has_symbol),
        ("Length ≥ 12",      report.length >= 12),
        ("Entropy ≥ 60 bits",report.entropy >= 60),
    ]
    for label, passed in checks:
        icon = f"{GREEN}✔{RESET}" if passed else f"{RED}✘{RESET}"
        print(f"  {icon}  {label}")

    if report.suggestions:
        print(f"\n  {YELLOW}{BOLD}Suggestions:{RESET}")
        for tip in report.suggestions:
            print(f"  {DIM}→{RESET}  {tip}")
    print()


def print_legend() -> None:
    print(f"  {DIM}Colour legend: "
          f"{CYAN}UPPERCASE{RESET}  "
          f"{WHITE}lowercase{RESET}  "
          f"{YELLOW}digits{RESET}  "
          f"{MAGENTA}symbols{RESET}{DIM}{RESET}")


# ─── Clipboard helper (optional, stdlib only) ─────────────────────────────────

def copy_to_clipboard(text: str) -> bool:
    """
    Attempt to copy text to the system clipboard via platform tools.
    Returns True on success, False if unavailable (never crashes).
    """
    import subprocess, platform
    try:
        os_name = platform.system()
        if os_name == "Windows":
            proc = subprocess.run(
                ["clip"], input=text.encode("utf-16"), check=True,
                capture_output=True,
            )
        elif os_name == "Darwin":
            proc = subprocess.run(
                ["pbcopy"], input=text.encode("utf-8"), check=True,
                capture_output=True,
            )
        else:  # Linux — try xclip then xsel
            for cmd in [["xclip", "-selection", "clipboard"],
                        ["xsel", "--clipboard", "--input"]]:
                try:
                    subprocess.run(cmd, input=text.encode("utf-8"),
                                   check=True, capture_output=True)
                    return True
                except FileNotFoundError:
                    continue
            return False
        return True
    except Exception:
        return False


# ─── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="password_generator",
        description="🔐  Password Generator — cryptographically secure, fully configurable.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            character sets:
              By default all four sets are active: UPPERCASE + lowercase + digits + symbols.
              Use --no-* flags to remove sets, or --only-* for exclusive modes.

            colour legend (output):
              CYAN   = uppercase  |  WHITE = lowercase
              YELLOW = digits     |  MAGENTA = symbols

            examples:
              python password_generator.py                     # 16-char default
              python password_generator.py -n 24              # 24 characters
              python password_generator.py -n 32 --count 5   # 5 × 32-char passwords
              python password_generator.py --no-symbols -n 20 # letters + digits
              python password_generator.py --only-digits -n 6 # 6-digit PIN
              python password_generator.py --no-ambiguous     # skip 0/O/1/l/I
              python password_generator.py --analyse "MyP@ss1"
              python password_generator.py --copy             # copy first to clipboard
        """),
    )

    # Length & count
    parser.add_argument("-n", "--length", type=int, default=16, metavar="N",
                        help="password length (default: 16)")
    parser.add_argument("--count", "-c", type=int, default=1, metavar="K",
                        help="number of passwords to generate (default: 1)")

    # Character-set flags
    cs = parser.add_argument_group("character sets")
    cs.add_argument("--no-upper",   action="store_true",
                    help="exclude uppercase letters (A-Z)")
    cs.add_argument("--no-lower",   action="store_true",
                    help="exclude lowercase letters (a-z)")
    cs.add_argument("--no-digits",  action="store_true",
                    help="exclude digits (0-9)")
    cs.add_argument("--no-symbols", action="store_true",
                    help="exclude symbols")
    cs.add_argument("--no-ambiguous", action="store_true",
                    help="exclude visually ambiguous characters: 0 O 1 l I")
    cs.add_argument("--only-digits", action="store_true",
                    help="generate a numeric-only PIN (overrides other flags)")
    cs.add_argument("--symbols", metavar="CHARS",
                    help='custom symbol set, e.g. --symbols "!@#"')

    # Utility
    ut = parser.add_argument_group("utilities")
    ut.add_argument("--analyse", metavar="PASSWORD",
                    help="analyse strength of an existing password")
    ut.add_argument("--copy", action="store_true",
                    help="copy the first generated password to the clipboard")
    ut.add_argument("--no-colour", action="store_true",
                    help="disable ANSI colour output")

    return parser


def strip_colours() -> None:
    global RESET, BOLD, DIM, RED, YELLOW, GREEN, CYAN, MAGENTA, WHITE
    RESET = BOLD = DIM = RED = YELLOW = GREEN = CYAN = MAGENTA = WHITE = ""


def main() -> int:
    parser = build_parser()
    args   = parser.parse_args()

    if args.no_colour:
        strip_colours()

    # ── Analyse mode ──────────────────────────────────────────────────────────
    if args.analyse:
        print_header("Password Strength Analyser")
        report = analyse_password(args.analyse)
        print_strength(report)
        return 0

    # ── Validate inputs ───────────────────────────────────────────────────────
    if args.length < 1:
        print(f"{RED}Error:{RESET} Password length must be at least 1.")
        return 1
    if args.length > 4096:
        print(f"{RED}Error:{RESET} Maximum password length is 4096.")
        return 1
    if args.count < 1:
        print(f"{RED}Error:{RESET} --count must be at least 1.")
        return 1
    if args.count > 1000:
        print(f"{RED}Error:{RESET} Maximum --count is 1000.")
        return 1

    # ── Build alphabet ────────────────────────────────────────────────────────
    try:
        if args.only_digits:
            alphabet = DIGITS
            if args.no_ambiguous:
                alphabet = "".join(c for c in alphabet if c not in AMBIGUOUS)
            must_include = None
        else:
            use_upper   = not args.no_upper
            use_lower   = not args.no_lower
            use_digits  = not args.no_digits
            use_symbols = not args.no_symbols

            alphabet = build_alphabet(
                use_upper=use_upper, use_lower=use_lower,
                use_digits=use_digits, use_symbols=use_symbols,
                no_ambiguous=args.no_ambiguous,
                custom_symbols=args.symbols,
            )

            # Guarantee at least one char from each active set
            must_include = []
            if use_upper:   must_include.append(UPPERCASE)
            if use_lower:   must_include.append(LOWERCASE)
            if use_digits:  must_include.append(DIGITS)
            if use_symbols: must_include.append(args.symbols or SYMBOLS)

            # Trim must_include sets against no_ambiguous
            if args.no_ambiguous:
                must_include = [
                    "".join(c for c in s if c not in AMBIGUOUS)
                    for s in must_include
                ]
                must_include = [s for s in must_include if s]

            # Can only guarantee inclusions if length >= active sets
            if args.length < len(must_include):
                must_include = None

    except ValueError as exc:
        print(f"{RED}Error:{RESET} {exc}")
        return 1

    # ── Generate ──────────────────────────────────────────────────────────────
    passwords = generate_batch(
        args.count, args.length, alphabet,
        must_include=must_include if not args.only_digits else None,
    )

    # ── Print ─────────────────────────────────────────────────────────────────
    title = f"Generated Password{'s' if args.count > 1 else ''}"
    print_header(title)

    if args.count == 1:
        print_password(passwords[0])
        print()
        print_legend()
        print()
        report = analyse_password(passwords[0])
        print_strength(report)
    else:
        for i, pwd in enumerate(passwords, 1):
            print_password(pwd, index=i)
        print()
        print_legend()
        print()

    # ── Clipboard ─────────────────────────────────────────────────────────────
    if args.copy:
        if copy_to_clipboard(passwords[0]):
            print(f"  {GREEN}✔  First password copied to clipboard.{RESET}\n")
        else:
            print(f"  {YELLOW}⚠  Clipboard unavailable on this platform.{RESET}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
