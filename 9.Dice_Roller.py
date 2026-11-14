#!/usr/bin/env python3
"""
Dice Roller
===========
Project #12 of 50 Mini Projects

Roll any number of any-sided dice from the command line.
Supports standard RPG dice notation (e.g. 2d6, 1d20, 4d8),
individual die ASCII art, roll history, and advantage/disadvantage mode.

Usage:
    python Dice_Roller.py                   # roll 1d6
    python Dice_Roller.py 2d6               # roll two 6-sided dice
    python Dice_Roller.py 1d20              # roll a 20-sided die
    python Dice_Roller.py 3d8 2d4           # roll multiple groups
    python Dice_Roller.py --advantage 1d20  # roll twice, take highest
    python Dice_Roller.py --disadvantage 1d20
    python Dice_Roller.py --history         # show last 10 rolls
    python Dice_Roller.py --clear-history   # wipe history
"""

import random
import argparse
import json
import re
import textwrap
from datetime import datetime
from pathlib import Path


# ─── Constants ────────────────────────────────────────────────────────────────

HISTORY_FILE = Path(__file__).parent / ".dice_history.json"
MAX_HISTORY  = 50
MAX_DICE     = 100       # guard against absurd inputs
MAX_SIDES    = 10_000

STANDARD_DICE = [2, 4, 6, 8, 10, 12, 20, 100]

# ANSI
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
MAGENTA= "\033[95m"
WHITE  = "\033[97m"


# ─── ASCII Die Faces (d6 only) ─────────────────────────────────────────────────

D6_FACES = {
    1: ["┌───────┐",
        "│       │",
        "│   ●   │",
        "│       │",
        "└───────┘"],
    2: ["┌───────┐",
        "│ ●     │",
        "│       │",
        "│     ● │",
        "└───────┘"],
    3: ["┌───────┐",
        "│ ●     │",
        "│   ●   │",
        "│     ● │",
        "└───────┘"],
    4: ["┌───────┐",
        "│ ●   ● │",
        "│       │",
        "│ ●   ● │",
        "└───────┘"],
    5: ["┌───────┐",
        "│ ●   ● │",
        "│   ●   │",
        "│ ●   ● │",
        "└───────┘"],
    6: ["┌───────┐",
        "│ ●   ● │",
        "│ ●   ● │",
        "│ ●   ● │",
        "└───────┘"],
}


def render_d6_row(values: list[int]) -> str:
    """Render up to 6 d6 dice side-by-side as ASCII art."""
    faces = [D6_FACES[v] for v in values[:6]]
    rows  = ["  ".join(face[row] for face in faces) for row in range(5)]
    return "\n".join(rows)


# ─── Dice Notation Parser ──────────────────────────────────────────────────────

DICE_PATTERN = re.compile(r"^(\d+)[dD](\d+)([+-]\d+)?$")


def parse_notation(notation: str) -> tuple[int, int, int]:
    """
    Parse dice notation like '2d6', '1d20', '3d8+2'.
    Returns (count, sides, modifier).
    Raises ValueError on invalid format.
    """
    m = DICE_PATTERN.match(notation.strip())
    if not m:
        raise ValueError(
            f"Invalid dice notation '{notation}'. "
            "Expected format: NdS or NdS+M (e.g. 2d6, 1d20, 3d8+2)"
        )
    count    = int(m.group(1))
    sides    = int(m.group(2))
    modifier = int(m.group(3)) if m.group(3) else 0

    if count < 1:
        raise ValueError("Number of dice must be at least 1.")
    if count > MAX_DICE:
        raise ValueError(f"Maximum {MAX_DICE} dice per group.")
    if sides < 2:
        raise ValueError("A die must have at least 2 sides.")
    if sides > MAX_SIDES:
        raise ValueError(f"Maximum {MAX_SIDES} sides per die.")

    return count, sides, modifier


# ─── Roll Engine ───────────────────────────────────────────────────────────────

def roll_die(sides: int) -> int:
    """Roll a single die with the given number of sides."""
    return random.randint(1, sides)


def roll_group(count: int, sides: int, modifier: int = 0) -> dict:
    """
    Roll `count` dice of `sides` sides.
    Returns a result dict with individual rolls, total, and metadata.
    """
    rolls   = [roll_die(sides) for _ in range(count)]
    subtotal = sum(rolls)
    total    = subtotal + modifier
    return {
        "notation": f"{count}d{sides}" + (f"{modifier:+d}" if modifier else ""),
        "sides":    sides,
        "count":    count,
        "modifier": modifier,
        "rolls":    rolls,
        "subtotal": subtotal,
        "total":    total,
        "min_possible": count + modifier,
        "max_possible": count * sides + modifier,
    }


def roll_with_advantage(sides: int) -> dict:
    """Roll 1dN twice, keep the higher result."""
    r1, r2 = roll_die(sides), roll_die(sides)
    kept   = max(r1, r2)
    return {"sides": sides, "roll1": r1, "roll2": r2, "kept": kept, "mode": "advantage"}


def roll_with_disadvantage(sides: int) -> dict:
    """Roll 1dN twice, keep the lower result."""
    r1, r2 = roll_die(sides), roll_die(sides)
    kept   = min(r1, r2)
    return {"sides": sides, "roll1": r1, "roll2": r2, "kept": kept, "mode": "disadvantage"}


# ─── History ───────────────────────────────────────────────────────────────────

def load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_history(entry: dict) -> None:
    history = load_history()
    history.append(entry)
    history = history[-MAX_HISTORY:]          # keep last N entries
    try:
        HISTORY_FILE.write_text(
            json.dumps(history, indent=2), encoding="utf-8"
        )
    except OSError:
        pass   # history is optional — never crash on it


def clear_history() -> None:
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()


# ─── Colour helpers ────────────────────────────────────────────────────────────

def colour_roll(value: int, sides: int) -> str:
    """Colour-code a single roll: red=min, green=max, yellow=mid."""
    if value == 1:
        return f"{RED}{BOLD}{value}{RESET}"
    if value == sides:
        return f"{GREEN}{BOLD}{value}{RESET}"
    return f"{YELLOW}{value}{RESET}"


def colour_total(total: int, min_v: int, max_v: int) -> str:
    pct = (total - min_v) / max((max_v - min_v), 1)
    if pct <= 0.25:
        return f"{RED}{BOLD}{total}{RESET}"
    if pct >= 0.85:
        return f"{GREEN}{BOLD}{total}{RESET}"
    return f"{CYAN}{BOLD}{total}{RESET}"


# ─── Output Formatters ─────────────────────────────────────────────────────────

def print_header(label: str) -> None:
    border = "═" * 60
    print(f"\n{CYAN}{border}{RESET}")
    print(f"{CYAN}  🎲  {BOLD}{label}{RESET}")
    print(f"{CYAN}{border}{RESET}")


def print_group_result(result: dict) -> None:
    notation  = result["notation"]
    rolls     = result["rolls"]
    sides     = result["sides"]
    modifier  = result["modifier"]
    subtotal  = result["subtotal"]
    total     = result["total"]
    min_v     = result["min_possible"]
    max_v     = result["max_possible"]

    coloured  = " + ".join(colour_roll(r, sides) for r in rolls)
    total_str = colour_total(total, min_v, max_v)

    print(f"\n  {BOLD}{notation}{RESET}")
    print(f"  Rolls    : [{coloured}{RESET}]")
    if len(rolls) > 1 or modifier:
        print(f"  Subtotal : {subtotal}")
    if modifier:
        print(f"  Modifier : {modifier:+d}")
    print(f"  {BOLD}Total    : {total_str}")
    print(f"  {DIM}Range    : {min_v} – {max_v}{RESET}")

    # ASCII art for d6 rolls (up to 6 dice)
    if sides == 6 and len(rolls) <= 6:
        print()
        print(render_d6_row(rolls))


def print_advantage_result(result: dict) -> None:
    mode  = result["mode"].title()
    sides = result["sides"]
    r1    = colour_roll(result["roll1"], sides)
    r2    = colour_roll(result["roll2"], sides)
    kept  = result["kept"]
    icon  = "⬆️ " if result["mode"] == "advantage" else "⬇️ "
    kept_str = colour_total(kept, 1, sides)

    discarded = result["roll1"] if result["mode"] == "advantage" and result["roll1"] < result["roll2"] \
                else result["roll2"]

    print(f"\n  {BOLD}1d{sides} with {mode}{RESET}")
    print(f"  Rolled   : [{r1}{RESET}]  [{r2}{RESET}]")
    print(f"  {icon} Kept   : {kept_str}   {DIM}(discarded: {discarded}){RESET}")


def print_summary(groups: list[dict]) -> None:
    if len(groups) <= 1:
        return
    grand = sum(g["total"] for g in groups)
    grand_min = sum(g["min_possible"] for g in groups)
    grand_max = sum(g["max_possible"] for g in groups)
    print(f"\n  {'─'*40}")
    print(f"  {BOLD}Grand Total : {colour_total(grand, grand_min, grand_max)}")
    print(f"  {DIM}Range       : {grand_min} – {grand_max}{RESET}")


def print_history(entries: list[dict]) -> None:
    if not entries:
        print(f"\n  {DIM}No roll history yet.{RESET}\n")
        return
    print(f"\n  {BOLD}{'Timestamp':<22}  {'Notation':<12}  {'Result':>8}{RESET}")
    print(f"  {'─'*50}")
    for e in reversed(entries[-10:]):
        ts     = e.get("timestamp", "?")[:19].replace("T", " ")
        label  = e.get("notation",  "?")
        total  = e.get("total",     "?")
        print(f"  {DIM}{ts}{RESET}  {CYAN}{label:<12}{RESET}  {YELLOW}{total:>8}{RESET}")
    print()


# ─── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Dice_Roller",
        description="🎲  Dice Roller — roll any dice, any time, with style.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            dice notation:
              NdS       — roll N dice with S sides  (e.g. 2d6, 1d20)
              NdS+M     — add modifier M to the total  (e.g. 3d8+2)
              NdS-M     — subtract modifier  (e.g. 2d6-1)

            examples:
              python Dice_Roller.py                      # 1d6
              python Dice_Roller.py 2d6                  # two 6-sided dice
              python Dice_Roller.py 1d20                 # 20-sided die
              python Dice_Roller.py 3d8+2 2d4            # multiple groups
              python Dice_Roller.py --advantage 1d20     # roll twice, keep highest
              python Dice_Roller.py --disadvantage 1d20  # roll twice, keep lowest
              python Dice_Roller.py --history            # last 10 rolls
              python Dice_Roller.py --clear-history      # wipe history
        """),
    )
    parser.add_argument(
        "dice",
        nargs="*",
        default=["1d6"],
        metavar="NdS",
        help="dice notation(s) to roll (default: 1d6)",
    )
    parser.add_argument(
        "--advantage", "-adv",
        action="store_true",
        help="roll the first die twice and keep the higher result",
    )
    parser.add_argument(
        "--disadvantage", "-dis",
        action="store_true",
        help="roll the first die twice and keep the lower result",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="show the last 10 rolls from history",
    )
    parser.add_argument(
        "--clear-history",
        action="store_true",
        help="clear all stored roll history",
    )
    parser.add_argument(
        "--no-colour",
        action="store_true",
        help="disable ANSI colour output",
    )
    return parser


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = build_parser()
    args   = parser.parse_args()

    # Strip colours globally if requested
    if args.no_colour:
        global RESET, BOLD, DIM, RED, GREEN, YELLOW, CYAN, MAGENTA, WHITE
        RESET = BOLD = DIM = RED = GREEN = YELLOW = CYAN = MAGENTA = WHITE = ""

    # ── History commands ──────────────────────────────────────────────────────
    if args.clear_history:
        clear_history()
        print("🗑️  Dice roll history cleared.")
        return 0

    if args.history:
        print_header("Roll History")
        print_history(load_history())
        return 0

    # ── Advantage / Disadvantage ──────────────────────────────────────────────
    if args.advantage or args.disadvantage:
        notation = args.dice[0] if args.dice else "1d20"
        try:
            count, sides, _ = parse_notation(notation)
        except ValueError as exc:
            print(f"{RED}Error:{RESET} {exc}")
            return 1

        mode   = "advantage" if args.advantage else "disadvantage"
        result = (roll_with_advantage if args.advantage else roll_with_disadvantage)(sides)

        print_header(f"1d{sides} — {mode.title()}")
        print_advantage_result(result)
        print()

        save_history({
            "timestamp": datetime.now().isoformat(),
            "notation":  f"1d{sides}({mode[:3]})",
            "total":     result["kept"],
        })
        return 0

    # ── Normal Roll ───────────────────────────────────────────────────────────
    groups: list[dict] = []
    errors: list[str]  = []

    for notation in args.dice:
        try:
            count, sides, modifier = parse_notation(notation)
            groups.append(roll_group(count, sides, modifier))
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        for err in errors:
            print(f"{RED}Error:{RESET} {err}")
        return 1

    label = "  ·  ".join(g["notation"] for g in groups)
    print_header(label)

    for g in groups:
        print_group_result(g)

    print_summary(groups)
    print()

    # Save each group to history
    for g in groups:
        save_history({
            "timestamp": datetime.now().isoformat(),
            "notation":  g["notation"],
            "total":     g["total"],
        })

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

