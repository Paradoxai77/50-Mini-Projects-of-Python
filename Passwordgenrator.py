#!/usr/bin/env python3
"""Cryptographically Secure Password & Passphrase Generator CLI Application.

This module provides an enterprise-grade, cryptographically secure password and
passphrase generator adhering to PEP 8 standards. It includes strict set
compliance, ambiguous character filtering, Diceware passphrase generation,
a theoretical entropy calculation engine, system clipboard integration, and an
embedded unit test suite.
"""

from dataclasses import dataclass
import math
import os
import platform
import secrets
import string
import subprocess
import sys
import unittest
from typing import Dict, List, Optional, Set, Tuple


# =============================================================================
# CONSTANTS & CHARACTER SET POOLS
# =============================================================================

DEFAULT_LOWERCASE: str = string.ascii_lowercase
DEFAULT_UPPERCASE: str = string.ascii_uppercase
DEFAULT_DIGITS: str = string.digits
DEFAULT_SYMBOLS: str = "!@#$%^&*()_+-=[]{}|;:,.<>?"

# Commonly confused / ambiguous characters across fonts & terminals
AMBIGUOUS_CHARACTERS: Set[str] = {
    "l", "1", "I", "O", "0", "o", "i", "!", "|", "B", "8", "S", "5", "Z", "2"
}

# Wordlist for Diceware Passphrase Generation (~250 distinct, memorable words)
DICEWARE_WORDLIST: Tuple[str, ...] = (
    "ability", "account", "actor", "adapter", "address", "advance", "airport",
    "algebra", "anchor", "angel", "animal", "antenna", "apron", "arch",
    "arena", "arrow", "artist", "aspect", "atom", "autumn", "badge",
    "baker", "bamboo", "banner", "barrel", "beacon", "beetle", "bison",
    "blanket", "blazer", "blossom", "boulder", "breeze", "bridge", "bronze",
    "cactus", "canvas", "canyon", "captain", "castle", "cedar", "celestial",
    "center", "chance", "chapel", "charm", "cheetah", "cherry", "cipher",
    "circle", "citrus", "clover", "cobalt", "comet", "compass", "copper",
    "coral", "cosmos", "crater", "crystal", "cypress", "dancer", "dawning",
    "dolphin", "dragon", "echo", "eclipse", "effort", "elastic", "element",
    "emerald", "engine", "enigma", "falcon", "feather", "fiddler", "finch",
    "flame", "forest", "fountain", "fox", "galaxy", "garden", "garland",
    "glacier", "glider", "glimmer", "granite", "gravity", "harbor", "haven",
    "hawthorn", "hazel", "helmet", "hero", "horizon", "humming", "hunter",
    "iceberg", "igloo", "illusion", "impulse", "island", "ivory", "jasper",
    "javelin", "journal", "jungle", "jupiter", "kestrel", "keynote", "kingdom",
    "lagoon", "lantern", "laurel", "legend", "leopard", "liberty", "lightning",
    "lunar", "magnet", "magnolia", "mantis", "marble", "matrix", "meadow",
    "melody", "mercury", "meteor", "minnow", "mirage", "monarch", "monument",
    "moonlight", "mosaic", "mountain", "nebula", "nectar", "neptune", "nest",
    "neutron", "nimble", "nomad", "oasis", "obsidian", "ocean", "octave",
    "odyssey", "olive", "onyx", "opal", "orbit", "orchard", "orchid",
    "orient", "osprey", "owl", "palace", "panther", "paradise", "parchment",
    "parrot", "passcode", "pathway", "pebble", "pelican", "penguin", "phoenix",
    "planet", "plateau", "plaza", "polar", "prism", "pyramid", "quantum",
    "quartz", "quest", "quiver", "radar", "rainbow", "ravine", "redwood",
    "reflect", "rhythm", "river", "rocket", "ruby", "saffron", "sahara",
    "salmon", "sapphire", "saturn", "scholar", "sculptor", "sequoia", "shadow",
    "shield", "signal", "silver", "solstice", "sparrow", "spectrum", "sphere",
    "sphinx", "spindle", "spiral", "spring", "spruce", "square", "squirrel",
    "starlight", "status", "stellar", "summit", "sunflower", "sunrise", "sunset",
    "survival", "swallow", "symbol", "symmetry", "talent", "tapestry", "temple",
    "thor", "thunder", "tiger", "timber", "titan", "topaz", "tornado",
    "tower", "traveler", "trident", "trophy", "tundra", "twilight", "typhoon",
    "umbrella", "universe", "valley", "velvet", "vessel", "vibrant", "victory",
    "vintage", "violet", "viper", "virtue", "visage", "vision", "volcano",
    "voyage", "walnut", "warrior", "waterfall", "wayfarer", "whisper", "wildcat",
    "willow", "windward", "wisdom", "wizard", "wolverine", "woodland", "zephyr"
)


# =============================================================================
# CONFIGURATION DATA CLASSES
# =============================================================================

@dataclass
class PasswordConfig:
    """Configuration container for Standard Password Generation."""

    length: int = 16
    use_uppercase: bool = True
    use_lowercase: bool = True
    use_digits: bool = True
    use_symbols: bool = True
    exclude_ambiguous: bool = False

    def validate(self) -> None:
        """Validate password configuration boundaries."""
        if not (8 <= self.length <= 128):
            raise ValueError(
                f"Password length must be between 8 and 128. Got {self.length}."
            )
        if not any(
            [self.use_uppercase, self.use_lowercase, self.use_digits, self.use_symbols]
        ):
            raise ValueError(
                "At least one character set (uppercase, lowercase, digits, symbols) must be enabled."
            )


@dataclass
class PassphraseConfig:
    """Configuration container for Diceware Passphrase Generation."""

    word_count: int = 4
    delimiter: str = "-"
    capitalize: bool = True
    add_number: bool = True

    def validate(self) -> None:
        """Validate passphrase configuration boundaries."""
        if not (3 <= self.word_count <= 20):
            raise ValueError(
                f"Word count must be between 3 and 20. Got {self.word_count}."
            )


# =============================================================================
# SECURITY ASSESSMENT ENGINE
# =============================================================================

class SecurityAssessmentEngine:
    """Engine to calculate entropy in bits and evaluate password strength."""

    @staticmethod
    def calculate_entropy(length: int, pool_size: int) -> float:
        """Calculate theoretical entropy in bits using E = L * log2(R).

        Args:
            length: The length of the password or number of words in passphrase.
            pool_size: Total number of possible choices per slot.

        Returns:
            Calculated entropy in bits rounded to 2 decimal places.
        """
        if pool_size <= 0 or length <= 0:
            return 0.0
        return round(length * math.log2(pool_size), 2)

    @staticmethod
    def classify_strength(entropy_bits: float) -> Tuple[str, str]:
        """Classify password strength based on theoretical entropy bits.

        Returns:
            Tuple of (RatingLabel, ColorIndicator/Description)
        """
        if entropy_bits < 40.0:
            return "Weak", "[!] Vulnerable to automated brute-force attacks."
        elif entropy_bits < 60.0:
            return "Moderate", "[*] Acceptable for low-risk online accounts."
        elif entropy_bits < 80.0:
            return "Strong", "[+] Suitable for primary accounts & email logins."
        else:
            return "Very Strong", "[#] Enterprise security standard (Cryptographically Resilient)."


# =============================================================================
# CRYPTOGRAPHIC SHUFFLE & RANDOMNESS UTILITIES
# =============================================================================

class CryptographicRNG:
    """Cryptographically secure random utilities wrapper around secrets module."""

    @staticmethod
    def choice(sequence: List[str] | str | Tuple[str, ...]) -> str:
        """Select a random element from a non-empty sequence using secrets."""
        return secrets.choice(sequence)

    @staticmethod
    def secure_shuffle(items: List[str]) -> List[str]:
        """In-place Fisher-Yates shuffle using secrets.randbelow for non-deterministic ordering."""
        shuffled = list(items)
        n = len(shuffled)
        for i in range(n - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
        return shuffled


# =============================================================================
# STANDARD PASSWORD GENERATOR
# =============================================================================

class PasswordGenerator:
    """Core generator for cryptographically secure standard passwords."""

    def __init__(self, config: PasswordConfig) -> None:
        self.config = config
        self.config.validate()

    def _build_character_pools(self) -> Tuple[Dict[str, str], str]:
        """Construct available character set pools based on active options."""
        pools: Dict[str, str] = {}

        def filter_pool(chars: str) -> str:
            if self.config.exclude_ambiguous:
                return "".join(c for c in chars if c not in AMBIGUOUS_CHARACTERS)
            return chars

        if self.config.use_uppercase:
            pools["uppercase"] = filter_pool(DEFAULT_UPPERCASE)
        if self.config.use_lowercase:
            pools["lowercase"] = filter_pool(DEFAULT_LOWERCASE)
        if self.config.use_digits:
            pools["digits"] = filter_pool(DEFAULT_DIGITS)
        if self.config.use_symbols:
            pools["symbols"] = filter_pool(DEFAULT_SYMBOLS)

        # Ensure no pool became empty after excluding ambiguous characters
        for name, pool_str in list(pools.items()):
            if not pool_str:
                raise ValueError(
                    f"Character set '{name}' became empty after excluding ambiguous characters."
                )

        combined_pool = "".join(pools.values())
        return pools, combined_pool

    def generate(self) -> Tuple[str, float, int]:
        """Generate a cryptographically secure password with strict set compliance.

        Returns:
            Tuple of (generated_password, entropy_in_bits, pool_size)
        """
        pools, combined_pool = self._build_character_pools()
        password_chars: List[str] = []

        # 1. Strict Set Compliance: Pick at least ONE char from each enabled pool
        for pool_str in pools.values():
            password_chars.append(CryptographicRNG.choice(pool_str))

        # 2. Fill the remaining length from the combined character pool
        remaining_length = self.config.length - len(password_chars)
        for _ in range(remaining_length):
            password_chars.append(CryptographicRNG.choice(combined_pool))

        # 3. Cryptographically shuffle to prevent deterministic position artifacts
        final_chars = CryptographicRNG.secure_shuffle(password_chars)
        password = "".join(final_chars)

        # 4. Calculate Entropy
        pool_size = len(combined_pool)
        entropy = SecurityAssessmentEngine.calculate_entropy(self.config.length, pool_size)

        return password, entropy, pool_size


# =============================================================================
# DICEWARE PASSPHRASE GENERATOR
# =============================================================================

class DicewareGenerator:
    """Generator for human-rememberable Diceware passphrases."""

    def __init__(self, config: PassphraseConfig) -> None:
        self.config = config
        self.config.validate()
        self.wordlist = DICEWARE_WORDLIST

    def generate(self) -> Tuple[str, float, int]:
        """Generate a Diceware passphrase using cryptographically selected words.

        Returns:
            Tuple of (generated_passphrase, entropy_in_bits, dictionary_size)
        """
        selected_words: List[str] = [
            CryptographicRNG.choice(self.wordlist)
            for _ in range(self.config.word_count)
        ]

        if self.config.capitalize:
            selected_words = [w.capitalize() for w in selected_words]

        passphrase = self.config.delimiter.join(selected_words)

        # Add optional random number suffix
        digit_entropy_boost = 0.0
        if self.config.add_number:
            random_num = secrets.randbelow(100)  # 0 to 99 (100 choices -> log2(100) = 6.64 bits)
            passphrase += f"{self.config.delimiter}{random_num:02d}"
            digit_entropy_boost = math.log2(100)

        # Entropy calculation for passphrases
        dict_size = len(self.wordlist)
        base_entropy = SecurityAssessmentEngine.calculate_entropy(self.config.word_count, dict_size)
        total_entropy = round(base_entropy + digit_entropy_boost, 2)

        return passphrase, total_entropy, dict_size


# =============================================================================
# CLIPBOARD INTEGRATION UTILITY
# =============================================================================

class ClipboardManager:
    """Helper to handle cross-platform clipboard copy operations securely."""

    @staticmethod
    def copy_to_clipboard(text: str) -> bool:
        """Copy text to system clipboard. Returns True on success, False otherwise."""
        # 1. Try pyperclip if installed
        try:
            import pyperclip  # type: ignore
            pyperclip.copy(text)
            return True
        except ImportError:
            pass

        # 2. Native OS Fallback commands
        system_os = platform.system().lower()
        try:
            if "windows" in system_os:
                proc = subprocess.Popen(
                    ["clip"], stdin=subprocess.PIPE, close_fds=True
                )
                proc.communicate(text.encode("utf-16le"))
                return True
            elif "darwin" in system_os:
                proc = subprocess.Popen(
                    ["pbcopy"], stdin=subprocess.PIPE, close_fds=True
                )
                proc.communicate(text.encode("utf-8"))
                return True
            elif "linux" in system_os:
                proc = subprocess.Popen(
                    ["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, close_fds=True
                )
                proc.communicate(text.encode("utf-8"))
                return True
        except Exception:
            return False

        return False


# =============================================================================
# EMBEDDED UNIT TEST SUITE
# =============================================================================

class TestPasswordGenerator(unittest.TestCase):
    """Comprehensive unit test suite for Password Generator components."""

    def test_standard_password_length_and_range(self) -> None:
        """Test default and valid custom lengths, plus range validation."""
        cfg = PasswordConfig(length=16)
        gen = PasswordGenerator(cfg)
        pwd, entropy, pool_sz = gen.generate()
        self.assertEqual(len(pwd), 16)
        self.assertGreater(entropy, 0)

        # Invalid lengths
        with self.assertRaises(ValueError):
            PasswordConfig(length=5).validate()
        with self.assertRaises(ValueError):
            PasswordConfig(length=200).validate()

    def test_strict_set_compliance(self) -> None:
        """Ensure password contains at least 1 character from each enabled class."""
        cfg = PasswordConfig(
            length=12,
            use_uppercase=True,
            use_lowercase=True,
            use_digits=True,
            use_symbols=True,
        )
        gen = PasswordGenerator(cfg)
        for _ in range(20):  # Run multiple times to verify consistency
            pwd, _, _ = gen.generate()
            self.assertTrue(any(c in DEFAULT_UPPERCASE for c in pwd))
            self.assertTrue(any(c in DEFAULT_LOWERCASE for c in pwd))
            self.assertTrue(any(c in DEFAULT_DIGITS for c in pwd))
            self.assertTrue(any(c in DEFAULT_SYMBOLS for c in pwd))

    def test_exclude_ambiguous_characters(self) -> None:
        """Verify ambiguous characters are excluded when flag is True."""
        cfg = PasswordConfig(length=32, exclude_ambiguous=True)
        gen = PasswordGenerator(cfg)
        for _ in range(10):
            pwd, _, _ = gen.generate()
            for amb in AMBIGUOUS_CHARACTERS:
                self.assertNotIn(amb, pwd)

    def test_no_character_set_enabled(self) -> None:
        """Validation fails if no character set is enabled."""
        cfg = PasswordConfig(
            use_uppercase=False,
            use_lowercase=False,
            use_digits=False,
            use_symbols=False,
        )
        with self.assertRaises(ValueError):
            cfg.validate()

    def test_diceware_passphrase_generation(self) -> None:
        """Test Diceware passphrase generation options."""
        cfg = PassphraseConfig(
            word_count=5, delimiter="-", capitalize=True, add_number=True
        )
        gen = DicewareGenerator(cfg)
        passphrase, entropy, dict_sz = gen.generate()
        parts = passphrase.split("-")
        # 5 words + 1 random number = 6 parts
        self.assertEqual(len(parts), 6)
        self.assertTrue(parts[0][0].isupper())  # Check capitalization
        self.assertTrue(parts[-1].isdigit())     # Check number appended
        self.assertGreater(entropy, 40.0)

    def test_entropy_calculation(self) -> None:
        """Verify mathematical entropy calculation formula."""
        # 16 length from pool of 94 -> 16 * log2(94) = 16 * 6.5545888 = ~104.87 bits
        calc_entropy = SecurityAssessmentEngine.calculate_entropy(16, 94)
        self.assertAlmostEqual(calc_entropy, 104.87, delta=0.1)

        rating, desc = SecurityAssessmentEngine.classify_strength(calc_entropy)
        self.assertEqual(rating, "Very Strong")

    def test_cryptographic_randomness_usage(self) -> None:
        """Verify that 'random' module is NOT imported in this module's scope."""
        self.assertNotIn("random", globals())


# =============================================================================
# CLI PARSER & ENTRYPOINT
# =============================================================================

def build_cli_parser():
    """Build command-line interface argument parser."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Cryptographically Secure Password & Passphrase Generator CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python Passwordgenrator.py -l 20 --exclude-ambiguous -n 3
  python Passwordgenrator.py --mode diceware --words 5 --delimiter "." --capitalize --add-number
  python Passwordgenrator.py --copy
  python Passwordgenrator.py --test
""",
    )

    # Generation Mode
    parser.add_argument(
        "--mode",
        choices=["standard", "diceware"],
        default="standard",
        help="Generation mode: 'standard' (character-based) or 'diceware' (word-based passphrase).",
    )

    # Standard Password Options
    parser.add_argument(
        "-l",
        "--length",
        type=int,
        default=16,
        help="Password length for standard mode (default: 16, range: 8-128).",
    )
    parser.add_argument(
        "--no-upper", action="store_true", help="Exclude uppercase letters (A-Z)."
    )
    parser.add_argument(
        "--no-lower", action="store_true", help="Exclude lowercase letters (a-z)."
    )
    parser.add_argument(
        "--no-digits", action="store_true", help="Exclude numbers (0-9)."
    )
    parser.add_argument(
        "--no-symbols", action="store_true", help="Exclude special symbols (!@#%%...)."
    )
    parser.add_argument(
        "--exclude-ambiguous",
        action="store_true",
        help="Exclude ambiguous characters (e.g., l, 1, I, O, 0, B, 8, S, 5, Z, 2).",
    )

    # Diceware Passphrase Options
    parser.add_argument(
        "--words",
        type=int,
        default=4,
        help="Number of words for Diceware passphrase (default: 4, range: 3-20).",
    )
    parser.add_argument(
        "--delimiter",
        type=str,
        default="-",
        help="Separator character for Diceware passphrase words (default: '-').",
    )
    parser.add_argument(
        "--capitalize",
        action="store_true",
        help="Capitalize the first letter of each Diceware word.",
    )
    parser.add_argument(
        "--add-number",
        action="store_true",
        help="Append a random 2-digit number to the passphrase.",
    )

    # Output & Utility Flags
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=1,
        help="Number of passwords to generate (default: 1).",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy generated password to system clipboard automatically.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run embedded unit test suite and exit.",
    )

    return parser


def main() -> None:
    """CLI execution entrypoint."""
    parser = build_cli_parser()
    args = parser.parse_args()

    # Trigger Unit Tests if requested
    if args.test:
        print("[+] Running Cryptographic Password Generator Unit Test Suite...\n")
        # Strip --test arg before handing over to unittest.main
        sys.argv = [sys.argv[0]]
        unittest.main()
        return

    print("=================================================================")
    print("      SECURE CRYPTOGRAPHIC PASSWORD GENERATOR (PEP 8)")
    print("=================================================================\n")

    generated_results: List[str] = []

    try:
        if args.mode == "standard":
            config = PasswordConfig(
                length=args.length,
                use_uppercase=not args.no_upper,
                use_lowercase=not args.no_lower,
                use_digits=not args.no_digits,
                use_symbols=not args.no_symbols,
                exclude_ambiguous=args.exclude_ambiguous,
            )
            generator = PasswordGenerator(config)

            for i in range(1, args.count + 1):
                pwd, entropy, pool_sz = generator.generate()
                generated_results.append(pwd)
                rating, desc = SecurityAssessmentEngine.classify_strength(entropy)

                print(f"[{i:02d}] Generated Password : {pwd}")
                print(f"     Length             : {len(pwd)} characters")
                print(f"     Pool Size          : {pool_sz} distinct characters")
                print(f"     Theoretical Entropy: {entropy} bits")
                print(f"     Security Rating    : {rating} -> {desc}\n")

        elif args.mode == "diceware":
            config = PassphraseConfig(
                word_count=args.words,
                delimiter=args.delimiter,
                capitalize=args.capitalize,
                add_number=args.add_number,
            )
            generator = DicewareGenerator(config)

            for i in range(1, args.count + 1):
                passphrase, entropy, dict_sz = generator.generate()
                generated_results.append(passphrase)
                rating, desc = SecurityAssessmentEngine.classify_strength(entropy)

                print(f"[{i:02d}] Generated Passphrase: {passphrase}")
                print(f"     Word Count          : {args.words} words")
                print(f"     Wordlist Size       : {dict_sz} distinct words")
                print(f"     Theoretical Entropy : {entropy} bits")
                print(f"     Security Rating     : {rating} -> {desc}\n")

        # Clipboard handle
        if args.copy and generated_results:
            text_to_copy = generated_results[0]
            success = ClipboardManager.copy_to_clipboard(text_to_copy)
            if success:
                print(
                    f"[+] Successfully copied item [01] ({len(text_to_copy)} chars) to system clipboard!"
                )
            else:
                print(
                    "[!] Clipboard copy failed. Please install 'pyperclip' or check OS clipboard utility."
                )

    except ValueError as err:
        print(f"[!] Configuration Error: {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as ex:
        print(f"[!] Unexpected Error: {ex}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
