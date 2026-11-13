#!/usr/bin/env python3
"""
Random Quote Generator
======================
Project #11 of 50 Mini Projects

Prints a random quote — motivational, funny, or programming-flavoured —
every time you run it. Supports optional flags for category filtering,
multiple quotes, and listing all categories.

Usage:
    python Random_Quoter.py
    python Random_Quoter.py --category programming
    python Random_Quoter.py --count 3
    python Random_Quoter.py --all
    python Random_Quoter.py --categories
"""

import random
import argparse
import textwrap
from dataclasses import dataclass


# ─── Data ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Quote:
    text: str
    author: str
    category: str


QUOTES: list[Quote] = [
    # ── Motivational ──────────────────────────────────────────────────────────
    Quote("The only way to do great work is to love what you do.",
          "Steve Jobs", "motivational"),
    Quote("It does not matter how slowly you go as long as you do not stop.",
          "Confucius", "motivational"),
    Quote("Success is not final, failure is not fatal: it is the courage to "
          "continue that counts.",
          "Winston Churchill", "motivational"),
    Quote("Believe you can and you're halfway there.",
          "Theodore Roosevelt", "motivational"),
    Quote("The future belongs to those who believe in the beauty of their dreams.",
          "Eleanor Roosevelt", "motivational"),
    Quote("Don't watch the clock; do what it does. Keep going.",
          "Sam Levenson", "motivational"),
    Quote("Act as if what you do makes a difference. It does.",
          "William James", "motivational"),
    Quote("Start where you are. Use what you have. Do what you can.",
          "Arthur Ashe", "motivational"),
    Quote("You are never too old to set another goal or to dream a new dream.",
          "C.S. Lewis", "motivational"),
    Quote("What you get by achieving your goals is not as important as what you "
          "become by achieving your goals.",
          "Zig Ziglar", "motivational"),

    # ── Programming ───────────────────────────────────────────────────────────
    Quote("Any fool can write code that a computer can understand. Good "
          "programmers write code that humans can understand.",
          "Martin Fowler", "programming"),
    Quote("First, solve the problem. Then, write the code.",
          "John Johnson", "programming"),
    Quote("Experience is the name everyone gives to their mistakes.",
          "Oscar Wilde", "programming"),
    Quote("In order to be irreplaceable, one must always be different.",
          "Coco Chanel", "programming"),
    Quote("Java is to JavaScript what car is to carpet.",
          "Chris Heilmann", "programming"),
    Quote("The best method for accelerating a computer is the one that "
          "boosts it by 9.8 m/s².",
          "Anonymous", "programming"),
    Quote("There are only two kinds of languages: the ones people complain "
          "about and the ones nobody uses.",
          "Bjarne Stroustrup", "programming"),
    Quote("Code is like humor. When you have to explain it, it's bad.",
          "Cory House", "programming"),
    Quote("Programming isn't about what you know; it's about what you can "
          "figure out.",
          "Chris Pine", "programming"),
    Quote("Deleted code is debugged code.",
          "Jeff Sickel", "programming"),
    Quote("The most disastrous thing that you can ever learn is your first "
          "programming language.",
          "Alan Kay", "programming"),
    Quote("A programmer's best tool is a good night's sleep.",
          "Anonymous", "programming"),
    Quote("There are two hard problems in computer science: cache invalidation, "
          "naming things, and off-by-one errors.",
          "Leon Bambrick", "programming"),
    Quote("Talk is cheap. Show me the code.",
          "Linus Torvalds", "programming"),
    Quote("Python is an experiment in how much freedom programmers need. "
          "Too little and they become restricted. Too much and they become lost.",
          "Guido van Rossum", "programming"),

    # ── Funny ─────────────────────────────────────────────────────────────────
    Quote("I told my wife she was drawing her eyebrows too high. She looked surprised.",
          "Anonymous", "funny"),
    Quote("Why do programmers prefer dark mode? Because light attracts bugs.",
          "Anonymous", "funny"),
    Quote("I asked the librarian if the library had books about paranoia. "
          "She whispered, 'They're right behind you!'",
          "Anonymous", "funny"),
    Quote("I'm reading a book about anti-gravity. It's impossible to put down.",
          "Anonymous", "funny"),
    Quote("I used to think I was indecisive, but now I'm not sure.",
          "Anonymous", "funny"),
    Quote("There are 10 types of people in the world: those who understand "
          "binary, and those who don't.",
          "Anonymous", "funny"),
    Quote("A SQL query walks into a bar, walks up to two tables and asks: "
          "'Can I join you?'",
          "Anonymous", "funny"),
    Quote("Why do Java developers wear glasses? Because they don't C#.",
          "Anonymous", "funny"),
    Quote("I have a joke about UDP but you might not get it.",
          "Anonymous", "funny"),
    Quote("My software never has bugs. It just develops random features.",
          "Anonymous", "funny"),
    Quote("Debugging: Removing the needles from the haystack. Programming: "
          "Putting them back in.",
          "Anonymous", "funny"),
    Quote("I would love to change the world, but they won't give me the source code.",
          "Anonymous", "funny"),

    # ── Philosophy ────────────────────────────────────────────────────────────
    Quote("The unexamined life is not worth living.",
          "Socrates", "philosophy"),
    Quote("We are what we repeatedly do. Excellence, then, is not an act, "
          "but a habit.",
          "Aristotle", "philosophy"),
    Quote("Two things are infinite: the universe and human stupidity; "
          "and I'm not sure about the universe.",
          "Albert Einstein", "philosophy"),
    Quote("Be yourself; everyone else is already taken.",
          "Oscar Wilde", "philosophy"),
    Quote("You only live once, but if you do it right, once is enough.",
          "Mae West", "philosophy"),
    Quote("In the middle of every difficulty lies opportunity.",
          "Albert Einstein", "philosophy"),
    Quote("It is not the strongest of the species that survive, nor the most "
          "intelligent, but the one most responsive to change.",
          "Charles Darwin", "philosophy"),
    Quote("Life is what happens when you're busy making other plans.",
          "John Lennon", "philosophy"),
]


# ─── Helpers ─────────────────────────────────────────────────────────────────

CATEGORIES: list[str] = sorted({q.category for q in QUOTES})

CATEGORY_COLORS: dict[str, str] = {
    "motivational": "\033[93m",   # yellow
    "programming":  "\033[96m",   # cyan
    "funny":        "\033[92m",   # green
    "philosophy":   "\033[95m",   # magenta
}
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
ITALIC = "\033[3m"


def category_color(category: str) -> str:
    return CATEGORY_COLORS.get(category, "\033[97m")


def format_quote(quote: Quote, width: int = 72) -> str:
    """Return a pretty-formatted, word-wrapped quote block."""
    color  = category_color(quote.category)
    tag    = f"[{quote.category.upper()}]"
    border = "─" * width

    wrapped = textwrap.fill(f'"{quote.text}"', width=width - 4,
                            initial_indent="  ", subsequent_indent="  ")

    lines = [
        f"{color}{border}{RESET}",
        f"{color}{BOLD}  {tag}{RESET}",
        "",
        f"{ITALIC}{wrapped}{RESET}",
        "",
        f"{DIM}      — {quote.author}{RESET}",
        f"{color}{border}{RESET}",
    ]
    return "\n".join(lines)


def get_quotes(category: str | None = None) -> list[Quote]:
    """Return quotes filtered by category, or all quotes."""
    if category is None:
        return QUOTES
    return [q for q in QUOTES if q.category == category.lower()]


# ─── Command handlers ─────────────────────────────────────────────────────────

def cmd_random(category: str | None, count: int) -> int:
    pool = get_quotes(category)
    if not pool:
        print(f"❌  No quotes found for category '{category}'.")
        print(f"    Available: {', '.join(CATEGORIES)}")
        return 1

    # Sample without replacement when possible, otherwise allow repeats.
    sample = random.sample(pool, min(count, len(pool)))
    if count > len(pool):
        sample += random.choices(pool, k=count - len(pool))

    for quote in sample:
        print()
        print(format_quote(quote))

    return 0


def cmd_all() -> int:
    """Print every quote grouped by category."""
    for cat in CATEGORIES:
        pool = get_quotes(cat)
        color = category_color(cat)
        header = f"\n{color}{BOLD}{'━' * 72}\n  ✦  {cat.upper()}  ({len(pool)} quotes)\n{'━' * 72}{RESET}"
        print(header)
        for q in pool:
            print(format_quote(q))
            print()
    return 0


def cmd_categories() -> int:
    """List available categories and their quote counts."""
    print(f"\n{BOLD}Available categories:{RESET}\n")
    for cat in CATEGORIES:
        color  = category_color(cat)
        count  = len(get_quotes(cat))
        print(f"  {color}●{RESET}  {BOLD}{cat:<14}{RESET}  {DIM}{count} quotes{RESET}")
    print()
    return 0


# ─── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Random_Quoter",
        description="🎲  Random Quote Generator — motivational · funny · programming · philosophy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              python Random_Quoter.py                        # one random quote
              python Random_Quoter.py --count 3             # three random quotes
              python Random_Quoter.py --category funny      # from the funny pool
              python Random_Quoter.py --category programming --count 2
              python Random_Quoter.py --all                 # every quote
              python Random_Quoter.py --categories          # list categories
        """),
    )
    parser.add_argument(
        "--category", "-c",
        metavar="CAT",
        help=f"filter by category: {{{', '.join(CATEGORIES)}}}",
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=1,
        metavar="N",
        help="number of quotes to print (default: 1)",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="print every quote, grouped by category",
    )
    parser.add_argument(
        "--categories",
        action="store_true",
        help="list available categories and quote counts",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args   = parser.parse_args()

    # Validate --count
    if args.count < 1:
        parser.error("--count must be at least 1")

    # Validate --category
    if args.category and args.category.lower() not in CATEGORIES:
        parser.error(
            f"unknown category '{args.category}'. "
            f"Choose from: {', '.join(CATEGORIES)}"
        )

    if args.categories:
        return cmd_categories()

    if args.all:
        return cmd_all()

    return cmd_random(args.category, args.count)


if __name__ == "__main__":
    raise SystemExit(main())

