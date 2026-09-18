
from dataclasses import dataclass
import os
import platform
import subprocess
import sys
import unittest
from typing import Optional, Tuple

try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q
    from PIL import Image, ImageColor
except ImportError as err:  # pragma: no cover
    print(
        f"[CRITICAL ERROR] Missing required dependencies: {err}\n"
        "Please install them using: pip install qrcode pillow",
        file=sys.stderr,
    )
    sys.exit(1)


# =============================================================================
# DATA STRUCTURES & CONFIGURATION
# =============================================================================

@dataclass
class QRCodeConfig:
    """Configuration options for QR code generation."""

    data: str
    fill_color: str = "black"
    back_color: str = "white"
    output_filename: str = "qrcode.png"
    box_size: int = 10
    border: int = 4
    error_correction: int = ERROR_CORRECT_M

    def validate(self) -> None:
        """Validate configuration settings.

        Raises:
            ValueError: If data is empty or colors/dimensions are invalid.
        """
        if not self.data or not self.data.strip():
            raise ValueError("QR code data payload cannot be empty.")

        if self.box_size <= 0:
            raise ValueError("Box size must be a positive integer.")

        if self.border < 0:
            raise ValueError("Border size must be a non-negative integer.")

        validate_color(self.fill_color, "Fill color")
        validate_color(self.back_color, "Background color")

        # Ensure fill and back colors are visually distinct
        fill_rgb = ImageColor.getrgb(self.fill_color)
        back_rgb = ImageColor.getrgb(self.back_color)
        if fill_rgb == back_rgb:
            raise ValueError("Fill color and background color cannot be identical.")


# =============================================================================
# HELPER & CORE FUNCTIONS
# =============================================================================

def validate_color(color_name: str, field_label: str = "Color") -> Tuple[int, int, int]:
    """Validate if a color string is recognized by Pillow ImageColor.

    Args:
        color_name: Name or hex string of the color (e.g., 'black', '#FF0000', 'rgb(0,0,0)').
        field_label: Context descriptive label for error reporting.

    Returns:
        Tuple[int, int, int]: RGB tuple representation of the valid color.

    Raises:
        ValueError: If the color representation is invalid or unparseable.
    """
    if not color_name or not color_name.strip():
        raise ValueError(f"{field_label} cannot be empty.")

    try:
        return ImageColor.getrgb(color_name.strip())
    except ValueError as exc:
        raise ValueError(
            f"Invalid {field_label.lower()} '{color_name}'. "
            "Please use valid color names (e.g. 'black', 'white', 'red', 'navy') "
            "or hex codes (e.g. '#000000', '#FFFFFF')."
        ) from exc


def normalize_filename(filename: str, default_filename: str = "qrcode.png") -> str:
    """Normalize file name ensuring proper image extension (.png, .jpg, .jpeg).

    Args:
        filename: Proposed output filename or path.
        default_filename: Fallback filename if empty input provided.

    Returns:
        str: Cleaned absolute or relative path with standard extension.
    """
    cleaned = filename.strip() if filename else ""
    if not cleaned:
        cleaned = default_filename

    # Default to .png if no standard image extension is present
    valid_extensions = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")
    if not any(cleaned.lower().endswith(ext) for ext in valid_extensions):
        cleaned += ".png"

    return cleaned


def generate_qr_code(config: QRCodeConfig) -> str:
    """Generate and save QR code image based on configuration.

    Args:
        config: QRCodeConfig instance detailing data payload and styling.

    Returns:
        str: Absolute filepath of the created QR code image file.

    Raises:
        ValueError: If config parameters are invalid.
        OSError: If output image file could not be saved.
    """
    config.validate()

    qr = qrcode.QRCode(
        version=None,  # Automatically determine version based on data complexity
        error_correction=config.error_correction,
        box_size=config.box_size,
        border=config.border,
    )

    qr.add_data(config.data.strip())
    qr.make(fit=True)

    img = qr.make_image(
        fill_color=config.fill_color.strip(),
        back_color=config.back_color.strip(),
    )

    output_path = normalize_filename(config.output_filename)
    
    # Ensure directory path exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    img.save(output_path)
    return os.path.abspath(output_path)


def open_image(filepath: str) -> bool:
    """Open an image file automatically in the system's default viewer.

    Args:
        filepath: Path to the image file to open.

    Returns:
        bool: True if launched successfully, False otherwise.
    """
    if not os.path.exists(filepath):
        print(f"[ERROR] Cannot open file. Path does not exist: {filepath}", file=sys.stderr)
        return False

    system_name = platform.system().lower()
    try:
        if system_name == "windows":
            os.startfile(filepath)
        elif system_name == "darwin":  # macOS
            subprocess.run(["open", filepath], check=True)
        else:  # Linux and Unix-like OS
            subprocess.run(["xdg-open", filepath], check=True)
        return True
    except Exception as err:
        # Fallback to PIL Image display if OS launcher fails
        try:
            with Image.open(filepath) as img:
                img.show()
            return True
        except Exception as pil_err:
            print(f"[WARNING] Could not launch automatic viewer: {err} | PIL fallback: {pil_err}", file=sys.stderr)
            return False


# =============================================================================
# INTERACTIVE CLI INTERFACE
# =============================================================================

def prompt_non_empty(prompt_text: str, error_msg: str = "Input cannot be empty. Please try again.") -> str:
    """Prompt user repeatedly until a non-empty string is entered.

    Args:
        prompt_text: Message presented to the user.
        error_msg: Error message displayed on empty input.

    Returns:
        str: Validated non-empty user string.
    """
    while True:
        value = input(prompt_text).strip()
        if value:
            return value
        print(f"❌ [Error] {error_msg}")


def prompt_color(prompt_text: str, default_color: str, field_label: str) -> str:
    """Prompt user for a valid color string with default fallback.

    Args:
        prompt_text: User prompt description.
        default_color: Fallback color if input left empty.
        field_label: Description for error feedback.

    Returns:
        str: Validated color string.
    """
    while True:
        user_input = input(f"{prompt_text} [Default: '{default_color}']: ").strip()
        if not user_input:
            return default_color
        try:
            validate_color(user_input, field_label)
            return user_input
        except ValueError as err:
            print(f"❌ {err}")


def interactive_cli() -> None:
    """Run interactive CLI for user input collection, QR generation, and display."""
    print("=" * 65)
    print("           📱 MODULAR PYTHON QR CODE GENERATOR 📱          ")
    print("=" * 65)
    print("Generate high-quality custom QR codes effortlessly!\n")

    # Prompt 1: Text or URL (Mandatory, non-empty)
    data = prompt_non_empty(
        "Enter text or URL to encode into QR code: ",
        error_msg="Text/URL payload cannot be empty!"
    )

    # Prompt 2: Fill / Foreground Color
    fill_color = prompt_color(
        "Enter fill color (e.g., 'black', 'blue', '#003366')",
        default_color="black",
        field_label="Fill color"
    )

    # Prompt 3: Background Color (Ensure it differs from fill color)
    while True:
        back_color = prompt_color(
            "Enter background color (e.g., 'white', 'yellow', '#FFFFFF')",
            default_color="white",
            field_label="Background color"
        )
        try:
            if ImageColor.getrgb(fill_color) == ImageColor.getrgb(back_color):
                print("❌ [Error] Foreground fill color and background color cannot be identical!")
                continue
            break
        except ValueError as err:
            print(f"❌ {err}")

    # Prompt 4: Output Filename
    filename_input = input("Enter output file name [Default: 'qrcode.png']: ").strip()
    output_filename = normalize_filename(filename_input, default_filename="qrcode.png")

    print("\n⏳ Generating QR code with parameters:")
    print(f"   • Content Payload: {data}")
    print(f"   • Fill Color:     {fill_color}")
    print(f"   • Background:     {back_color}")
    print(f"   • Output Target:  {output_filename}")

    try:
        config = QRCodeConfig(
            data=data,
            fill_color=fill_color,
            back_color=back_color,
            output_filename=output_filename,
        )
        saved_path = generate_qr_code(config)
        print(f"\n✅ QR code successfully generated and saved to:\n   {saved_path}")

        print("\n🖼️ Opening generated image...")
        if open_image(saved_path):
            print("✨ Image opened in system default viewer.")
        else:
            print("⚠️ Automatic image viewing was not supported or failed.")

    except Exception as err:
        print(f"\n❌ [CRITICAL ERROR] Failed to generate QR code: {err}", file=sys.stderr)


# =============================================================================
# UNIT TESTS
# =============================================================================

class TestQRCodeGenerator(unittest.TestCase):
    """Automated unit test suite for QR Code Generator functions."""

    def test_normalize_filename(self) -> None:
        """Test filename normalization and extension handling."""
        self.assertEqual(normalize_filename(""), "qrcode.png")
        self.assertEqual(normalize_filename("   "), "qrcode.png")
        self.assertEqual(normalize_filename("myqr"), "myqr.png")
        self.assertEqual(normalize_filename("test.jpg"), "test.jpg")
        self.assertEqual(normalize_filename("test.PNG"), "test.PNG")
        self.assertEqual(normalize_filename("custom.webp"), "custom.webp")

    def test_validate_color(self) -> None:
        """Test color string validation."""
        self.assertEqual(validate_color("black"), (0, 0, 0))
        self.assertEqual(validate_color("white"), (255, 255, 255))
        self.assertEqual(validate_color("#FF0000"), (255, 0, 0))

        with self.assertRaises(ValueError):
            validate_color("")

        with self.assertRaises(ValueError):
            validate_color("not_a_real_color_xyz")

    def test_qr_config_validation(self) -> None:
        """Test config validation rules."""
        # Empty data validation
        config_empty = QRCodeConfig(data="")
        with self.assertRaises(ValueError):
            config_empty.validate()

        # Identical colors validation
        config_same_color = QRCodeConfig(data="https://example.com", fill_color="black", back_color="black")
        with self.assertRaises(ValueError):
            config_same_color.validate()

        # Valid config
        config_valid = QRCodeConfig(data="Hello World", fill_color="blue", back_color="yellow")
        config_valid.validate()  # Should not raise

    def test_generate_qr_code_file_creation(self) -> None:
        """Test generating and saving a QR code file."""
        test_filename = "test_output_qr.png"
        if os.path.exists(test_filename):
            os.remove(test_filename)

        config = QRCodeConfig(
            data="https://github.com",
            fill_color="black",
            back_color="white",
            output_filename=test_filename,
        )
        path = generate_qr_code(config)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.path.getsize(path) > 0)

        # Cleanup test file
        if os.path.exists(path):
            os.remove(path)


# =============================================================================
# SCRIPT ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    # If called with --test argument, execute unit tests
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        sys.argv.pop(1)
        unittest.main()
    else:
        interactive_cli()
