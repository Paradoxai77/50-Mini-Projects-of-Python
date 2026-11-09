#!/usr/bin/env python3
"""
Automated Bulk Emailer in Python 3.10+
Built exclusively with Python standard library modules.

Features:
- CSV Parsing with DictReader, schema validation, regex email check, de-duplication.
- Safe string.Template interpolation with fallback for missing values.
- Multipart MIME (plain text + optional HTML) with custom headers & attachments.
- SMTP_SSL (port 465) and STARTTLS (port 587) with reconnection resilience.
- Exponential backoff retry engine for transient network/server failures.
- Rate-limiting (throttling delay & batch pausing).
- Sent & Failed CSV tracking for safe resumption and duplicate avoidance.
- Console + File logging with end-of-run execution metrics summary.
"""

from __future__ import annotations

import argparse
import csv
import email.utils
from email.message import EmailMessage
import logging
import mimetypes
import os
from pathlib import Path
import re
import smtplib
import ssl
import string
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple


# ==============================================================================
# Constants & Regex
# ==============================================================================

DEFAULT_CSV_PATH = "contacts.csv"
DEFAULT_TEXT_TEMPLATE = "template.txt"
DEFAULT_HTML_TEMPLATE = "template.html"
DEFAULT_SENT_LOG = "sent.csv"
DEFAULT_FAILED_LOG = "failed.csv"
DEFAULT_LOG_FILE = "emailer.log"

# Standard RFC 5322 compatible practical email regex
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


# ==============================================================================
# Configuration & Environment Management
# ==============================================================================

@dataclass
class SMTPConfig:
    """Encapsulates all SMTP connection and sender credentials."""
    host: str
    port: int
    user: str
    password: str
    use_ssl: bool = False
    use_tls: bool = True
    from_name: str = ""
    from_email: str = ""
    reply_to: str = ""

    def validate(self) -> None:
        """Validates that necessary connection parameters are present."""
        missing = []
        if not self.host:
            missing.append("SMTP_HOST")
        if not self.user:
            missing.append("SMTP_USER")
        if not self.password:
            missing.append("SMTP_PASSWORD")

        if missing:
            raise ValueError(
                f"Missing required SMTP configuration environment variables: {', '.join(missing)}. "
                f"Please define them in your environment or in a .env file."
            )


def load_env_file(filepath: Path | str = ".env") -> None:
    """
    Lightweight .env loader using standard library only.
    Reads KEY=VALUE lines into os.environ without overwriting pre-existing env vars.
    """
    env_path = Path(filepath)
    if not env_path.is_file():
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            # Skip empty lines and comments
            if not stripped or stripped.startswith("#"):
                continue
            if "=" in stripped:
                key, _, val = stripped.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                # Do not overwrite variables already defined in environment
                if key and key not in os.environ:
                    os.environ[key] = val


def get_smtp_config(args: Optional[argparse.Namespace] = None) -> SMTPConfig:
    """Loads and returns SMTPConfig from environment variables and CLI overrides."""
    host = os.environ.get("SMTP_HOST", "")
    port_str = os.environ.get("SMTP_PORT", "587")
    try:
        port = int(port_str)
    except ValueError:
        port = 587

    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    from_name = os.environ.get("SMTP_FROM_NAME", "")
    from_email = os.environ.get("SMTP_FROM_EMAIL", user)
    reply_to = os.environ.get("SMTP_REPLY_TO", "")

    # Port 465 defaults to SSL; port 587 defaults to STARTTLS
    use_ssl_env = os.environ.get("SMTP_USE_SSL", "").lower() in ("true", "1", "yes")
    use_tls_env = os.environ.get("SMTP_USE_TLS", "").lower() in ("true", "1", "yes")

    if use_ssl_env or port == 465:
        use_ssl = True
        use_tls = False
    else:
        use_ssl = False
        use_tls = True if (use_tls_env or port == 587) else False

    return SMTPConfig(
        host=host,
        port=port,
        user=user,
        password=password,
        use_ssl=use_ssl,
        use_tls=use_tls,
        from_name=from_name,
        from_email=from_email or user,
        reply_to=reply_to
    )


# ==============================================================================
# Logging Configuration
# ==============================================================================

def setup_logging(log_file: str = DEFAULT_LOG_FILE, verbose: bool = False) -> logging.Logger:
    """Configures multi-handler logging to console and persistent log file."""
    logger = logging.getLogger("BulkEmailer")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Clear existing handlers to prevent duplicate logging
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler (use stdout so output streams are strictly sequential)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        logger.warning(f"Could not initialize file logger at '{log_file}': {e}")

    return logger


# ==============================================================================
# CSV Parsing & Contact Validation
# ==============================================================================

def is_valid_email(email_str: str) -> bool:
    """Validates an email address against standard RFC pattern."""
    if not email_str or not isinstance(email_str, str):
        return False
    return bool(EMAIL_REGEX.match(email_str.strip()))


def load_sent_emails(sent_log_path: Path | str) -> Set[str]:
    """Reads sent.csv and returns a set of normalized (lowercase) email addresses."""
    sent_emails: Set[str] = set()
    path = Path(sent_log_path)
    if not path.is_file():
        return sent_emails

    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row and "email" in row and row["email"]:
                    sent_emails.add(row["email"].strip().lower())
    except Exception as e:
        logging.getLogger("BulkEmailer").warning(
            f"Failed to read existing sent log '{sent_log_path}': {e}"
        )
    return sent_emails


def load_contacts(
    csv_path: Path | str,
    sent_log_path: Optional[Path | str] = None,
    logger: Optional[logging.Logger] = None
) -> Tuple[List[Dict[str, str]], int]:
    """
    Parses contacts from a CSV file.
    - Requires 'email' and 'name' columns.
    - Preserves all extra columns as template variables.
    - Validates email format and skips invalid entries.
    - De-duplicates addresses within the file (case-insensitive).
    - Skips addresses already found in sent_log_path (sent.csv).
    
    Returns:
        (valid_contacts_list, skipped_count)
    """
    log = logger or logging.getLogger("BulkEmailer")
    path = Path(csv_path)

    if not path.is_file():
        raise FileNotFoundError(f"Contacts CSV file '{csv_path}' does not exist.")

    if path.stat().st_size == 0:
        log.warning(f"Contacts CSV file '{csv_path}' is completely empty (0 bytes).")
        return [], 0

    already_sent = load_sent_emails(sent_log_path) if sent_log_path else set()
    seen_in_run: Set[str] = set()
    valid_contacts: List[Dict[str, str]] = []
    skipped_count = 0

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        # Validate headers
        if not reader.fieldnames:
            log.warning(f"Contacts CSV file '{csv_path}' has no header columns.")
            return [], 0

        # Case-insensitive column header mapping
        header_map = {col.strip().lower(): col for col in reader.fieldnames if col}
        if "email" not in header_map or "name" not in header_map:
            raise ValueError(
                f"Contacts CSV missing required columns. Must contain 'email' and 'name'. "
                f"Found columns: {reader.fieldnames}"
            )

        email_key = header_map["email"]
        name_key = header_map["name"]

        for row_idx, row in enumerate(reader, start=2):
            # Check for malformed or empty row
            if not row or not any(row.values()):
                log.debug(f"Skipping empty row at line {row_idx}.")
                skipped_count += 1
                continue

            raw_email = (row.get(email_key) or "").strip()
            raw_name = (row.get(name_key) or "").strip()

            if not raw_email or not raw_name:
                log.warning(
                    f"Line {row_idx}: Skipped row with missing email or name: {row}"
                )
                skipped_count += 1
                continue

            # Validate email structure
            if not is_valid_email(raw_email):
                log.warning(
                    f"Line {row_idx}: Skipped invalid email format '{raw_email}' for contact '{raw_name}'."
                )
                skipped_count += 1
                continue

            norm_email = raw_email.lower()

            # Check if already sent in previous run
            if norm_email in already_sent:
                log.info(
                    f"Line {row_idx}: Skipping '{norm_email}' (already recorded in sent log)."
                )
                skipped_count += 1
                continue

            # De-duplicate within the current file
            if norm_email in seen_in_run:
                log.warning(
                    f"Line {row_idx}: Skipping duplicate email '{raw_email}' in current CSV."
                )
                skipped_count += 1
                continue

            seen_in_run.add(norm_email)

            # Clean and sanitize contact dict
            contact_data: Dict[str, str] = {
                "email": raw_email,
                "name": raw_name
            }
            # Add all extra attributes
            for col, val in row.items():
                if col and col not in (email_key, name_key):
                    contact_data[col.strip()] = (val or "").strip()

            valid_contacts.append(contact_data)

    log.info(
        f"Parsed {len(valid_contacts)} valid contact(s) from '{csv_path}' ({skipped_count} skipped)."
    )
    return valid_contacts, skipped_count


# ==============================================================================
# Templating Engine
# ==============================================================================

def load_template_file(template_path: Path | str) -> str:
    """Reads template file contents with UTF-8 encoding."""
    path = Path(template_path)
    if not path.is_file():
        raise FileNotFoundError(f"Template file '{template_path}' not found.")
    return path.read_text(encoding="utf-8")


def render_template(template_str: str, context: Dict[str, str]) -> str:
    """
    Interpolates context variables into a string.Template.
    Uses safe_substitute so unspecified placeholders do not raise KeyError.
    """
    tmpl = string.Template(template_str)
    return tmpl.safe_substitute(context)


# ==============================================================================
# Message Construction
# ==============================================================================

def build_message(
    contact: Dict[str, str],
    subject_template: str,
    text_template: str,
    html_template: Optional[str],
    config: SMTPConfig,
    attachments: Optional[List[str | Path]] = None,
    override_to: Optional[str] = None
) -> EmailMessage:
    """
    Constructs a fully formed, compliant EmailMessage.
    - Sets standard RFC headers (From, To, Subject, Date, Message-ID, Reply-To, List-Unsubscribe).
    - Sets plain text body.
    - Adds multipart/alternative HTML body when html_template is provided.
    - Attaches optional files with auto-detected MIME types.
    """
    msg = EmailMessage()

    # Recipient
    recipient_email = override_to if override_to else contact["email"]
    recipient_name = contact["name"]
    msg["To"] = f'"{recipient_name}" <{recipient_email}>'

    # Sender identity
    if config.from_name:
        msg["From"] = f'"{config.from_name}" <{config.from_email}>'
    else:
        msg["From"] = config.from_email

    # Subject line rendering
    rendered_subject = render_template(subject_template, contact)
    msg["Subject"] = rendered_subject

    # Standard headers
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=config.host or "bulk.emailer.local")

    if config.reply_to:
        msg["Reply-To"] = config.reply_to

    # Compliance: RFC 2369 List-Unsubscribe header
    unsubscribe_target = config.reply_to or config.from_email
    msg["List-Unsubscribe"] = f"<mailto:{unsubscribe_target}?subject=unsubscribe>"

    # Render Body
    rendered_text = render_template(text_template, contact)
    msg.set_content(rendered_text)

    # Optional HTML alternative
    if html_template:
        rendered_html = render_template(html_template, contact)
        msg.add_alternative(rendered_html, subtype="html")

    # Attachments
    if attachments:
        for attach_path in attachments:
            path = Path(attach_path)
            if not path.is_file():
                raise FileNotFoundError(f"Attachment file '{attach_path}' does not exist.")

            ctype, encoding = mimetypes.guess_type(str(path))
            if ctype is None or encoding is not None:
                ctype = "application/octet-stream"

            maintype, subtype = ctype.split("/", 1)
            file_data = path.read_bytes()
            msg.add_attachment(
                file_data,
                maintype=maintype,
                subtype=subtype,
                filename=path.name
            )

    return msg


# ==============================================================================
# SMTP Client Manager with Reconnection & Exponential Backoff
# ==============================================================================

class SMTPConnectionManager:
    """
    Manages persistent SMTP connections with support for SSL, STARTTLS,
    automatic reconnection on drop, and exponential backoff retry.
    """

    def __init__(self, config: SMTPConfig, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger("BulkEmailer")
        self.server: Optional[smtplib.SMTP | smtplib.SMTP_SSL] = None

    def connect(self) -> None:
        """Establishes, encrypts, and authenticates the SMTP connection."""
        self.close()
        self.logger.info(
            f"Connecting to SMTP server at {self.config.host}:{self.config.port} "
            f"(SSL: {self.config.use_ssl}, STARTTLS: {self.config.use_tls})..."
        )

        ssl_context = ssl.create_default_context()

        if self.config.use_ssl:
            self.server = smtplib.SMTP_SSL(
                host=self.config.host,
                port=self.config.port,
                context=ssl_context,
                timeout=30
            )
        else:
            self.server = smtplib.SMTP(
                host=self.config.host,
                port=self.config.port,
                timeout=30
            )
            self.server.ehlo()
            if self.config.use_tls:
                self.server.starttls(context=ssl_context)
                self.server.ehlo()

        if self.config.user and self.config.password:
            self.logger.debug(f"Authenticating as {self.config.user}...")
            self.server.login(self.config.user, self.config.password)
            self.logger.info("SMTP Authentication successful.")

    def send_message_with_retry(
        self,
        msg: EmailMessage,
        max_attempts: int = 3,
        base_backoff: float = 2.0
    ) -> Tuple[bool, Optional[str]]:
        """
        Sends an EmailMessage through the active connection.
        If a transient network error or disconnection occurs, it reconnects
        and retries using exponential backoff up to max_attempts.
        """
        last_error: Optional[str] = None

        for attempt in range(1, max_attempts + 1):
            try:
                if self.server is None:
                    self.connect()

                assert self.server is not None
                self.server.send_message(msg)
                return True, None

            except (
                smtplib.SMTPServerDisconnected,
                smtplib.SMTPConnectError,
                smtplib.SMTPSenderRefused,
                ConnectionError,
                OSError,
                TimeoutError
            ) as e:
                last_error = f"{type(e).__name__}: {e}"
                self.logger.warning(
                    f"Transient failure sending to {msg['To']} (Attempt {attempt}/{max_attempts}): {last_error}"
                )
                self.close()

                if attempt < max_attempts:
                    sleep_time = base_backoff ** attempt
                    self.logger.info(f"Retrying in {sleep_time:.1f}s...")
                    time.sleep(sleep_time)

            except smtplib.SMTPResponseException as e:
                # Fatal or specific SMTP response error
                last_error = f"SMTP {e.smtp_code}: {e.smtp_error.decode('utf-8', errors='ignore') if isinstance(e.smtp_error, bytes) else e.smtp_error}"
                self.logger.error(f"SMTP error response for {msg['To']}: {last_error}")
                # 4xx errors are transient; 5xx errors are typically permanent
                if 400 <= e.smtp_code < 500 and attempt < max_attempts:
                    sleep_time = base_backoff ** attempt
                    time.sleep(sleep_time)
                    continue
                return False, last_error

            except Exception as e:
                last_error = f"Unexpected error: {type(e).__name__}: {e}"
                self.logger.error(f"Fatal error sending to {msg['To']}: {last_error}")
                return False, last_error

        return False, last_error or "Max retry attempts exceeded."

    def close(self) -> None:
        """Safely terminates the SMTP connection."""
        if self.server:
            try:
                self.server.quit()
            except Exception:
                try:
                    self.server.close()
                except Exception:
                    pass
            finally:
                self.server = None

    def __enter__(self) -> SMTPConnectionManager:
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


# ==============================================================================
# Audit & Log Writers
# ==============================================================================

def append_to_sent_log(sent_log_path: Path | str, contact: Dict[str, str]) -> None:
    """Records successfully sent email to sent.csv."""
    path = Path(sent_log_path)
    file_exists = path.is_file() and path.stat().st_size > 0

    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["email", "name", "timestamp"])
        writer.writerow([
            contact["email"],
            contact["name"],
            datetime.now(timezone.utc).isoformat()
        ])


def append_to_failed_log(failed_log_path: Path | str, contact: Dict[str, str], error_msg: str) -> None:
    """Records failed email transmission to failed.csv for resumption."""
    path = Path(failed_log_path)
    file_exists = path.is_file() and path.stat().st_size > 0

    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["email", "name", "error", "timestamp"])
        writer.writerow([
            contact.get("email", "unknown"),
            contact.get("name", "unknown"),
            error_msg,
            datetime.now(timezone.utc).isoformat()
        ])


# ==============================================================================
# Core Dispatcher & Batch Sender
# ==============================================================================

def send_all(
    contacts: List[Dict[str, str]],
    args: argparse.Namespace,
    config: SMTPConfig,
    logger: logging.Logger
) -> Dict[str, int]:
    """
    Coordinates batch email sending:
    - Supports dry-run and single test-to target.
    - Manages rate-limiting delay and batch pausing.
    - Tracks sent, failed, and skipped metrics.
    """
    total = len(contacts)
    metrics = {"total": total, "sent": 0, "failed": 0, "skipped": 0}

    if total == 0:
        logger.info("No contacts to process.")
        return metrics

    # Load templates
    text_template = load_template_file(args.template)
    html_template = load_template_file(args.html_template) if (args.html_template and Path(args.html_template).is_file()) else None

    # Handle --limit
    if args.limit and args.limit > 0:
        contacts = contacts[:args.limit]
        logger.info(f"Limiting execution to first {len(contacts)} contact(s).")

    # Handle --test-to mode
    if args.test_to:
        test_target = args.test_to.strip()
        if not is_valid_email(test_target):
            raise ValueError(f"Invalid test email address provided for --test-to: '{test_target}'")
        sample_contact = contacts[0]
        logger.info(f"Running in TEST-TO mode: sending single test email to '{test_target}' using data from '{sample_contact['name']}'.")
        contacts = [sample_contact]

    # Handle --dry-run mode
    if args.dry_run:
        logger.info("====================================================================")
        logger.info("DRY-RUN MODE ENABLED: No network connections or emails will be sent.")
        logger.info("====================================================================")

        for idx, contact in enumerate(contacts, start=1):
            msg = build_message(
                contact=contact,
                subject_template=args.subject,
                text_template=text_template,
                html_template=html_template,
                config=config,
                attachments=args.attach,
                override_to=args.test_to
            )
            print(f"\n--- [DRY-RUN MESSAGE {idx}/{len(contacts)}] ---")
            print(f"To:      {msg['To']}")
            print(f"From:    {msg['From']}")
            print(f"Subject: {msg['Subject']}")
            print(f"Date:    {msg['Date']}")
            print(f"Headers: List-Unsubscribe={msg.get('List-Unsubscribe')}")
            if args.attach:
                print(f"Attach:  {', '.join(args.attach)}")
            print("\n[PLAIN TEXT BODY PREVIEW]:")
            body_part = msg.get_body(preferencelist=('plain',))
            print(body_part.get_content() if body_part else "[No plain text content]")

            if html_template:
                html_part = msg.get_body(preferencelist=('html',))
                print(f"\n[HTML ALTERNATIVE]: Present ({len(html_part.get_content()) if html_part else 0} bytes)")
            print("--------------------------------------------------------------------")
            metrics["sent"] += 1

        return metrics

    # Real sending mode: Validate SMTP credentials
    config.validate()

    smtp_manager = SMTPConnectionManager(config, logger)

    with smtp_manager:
        for idx, contact in enumerate(contacts, start=1):
            recipient = args.test_to if args.test_to else contact["email"]
            logger.info(f"[{idx}/{len(contacts)}] Preparing email for {contact['name']} <{recipient}>...")

            try:
                msg = build_message(
                    contact=contact,
                    subject_template=args.subject,
                    text_template=text_template,
                    html_template=html_template,
                    config=config,
                    attachments=args.attach,
                    override_to=args.test_to
                )

                success, err_msg = smtp_manager.send_message_with_retry(msg)

                if success:
                    logger.info(f"Successfully sent to {recipient}.")
                    metrics["sent"] += 1
                    if not args.test_to:
                        append_to_sent_log(args.sent_log, contact)
                else:
                    logger.error(f"Failed to send to {recipient}: {err_msg}")
                    metrics["failed"] += 1
                    if not args.test_to:
                        append_to_failed_log(args.failed_log, contact, err_msg or "Unknown error")

            except Exception as e:
                logger.error(f"Error building or sending email for {recipient}: {e}")
                metrics["failed"] += 1
                if not args.test_to:
                    append_to_failed_log(args.failed_log, contact, str(e))

            # Rate limiting / Delay between individual messages
            if idx < len(contacts) and args.delay > 0:
                logger.debug(f"Throttling delay: waiting {args.delay}s...")
                time.sleep(args.delay)

            # Batch pause if batch_size reached
            if args.batch_size and args.batch_size > 0:
                if idx % args.batch_size == 0 and idx < len(contacts):
                    pause_time = max(args.delay * 2, 5.0)
                    logger.info(f"Completed batch of {args.batch_size} emails. Pausing for {pause_time:.1f}s...")
                    time.sleep(pause_time)

    return metrics


# ==============================================================================
# CLI Argument Parser Setup
# ==============================================================================

def build_parser() -> argparse.ArgumentParser:
    """Builds the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="emailer",
        description="Automated Bulk Emailer in Python (Standard Library Only)."
    )

    parser.add_argument(
        "--csv",
        default=DEFAULT_CSV_PATH,
        help=f"Path to contacts CSV file (default: {DEFAULT_CSV_PATH})"
    )
    parser.add_argument(
        "--template",
        default=DEFAULT_TEXT_TEMPLATE,
        help=f"Path to plain text template file (default: {DEFAULT_TEXT_TEMPLATE})"
    )
    parser.add_argument(
        "--subject",
        default="Important update for ${name}",
        help="Email subject template line with placeholders (default: 'Important update for ${name}')"
    )
    parser.add_argument(
        "--html-template",
        default=DEFAULT_HTML_TEMPLATE,
        help=f"Path to HTML template file (default: {DEFAULT_HTML_TEMPLATE})"
    )
    parser.add_argument(
        "--attach",
        action="append",
        default=[],
        help="Path to an attachment file. Can be specified multiple times."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between sending consecutive emails (default: 1.0s)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of emails to send before taking a batch pause (default: 50)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of contacts to send to in this execution"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render and display emails to console without sending over SMTP"
    )
    parser.add_argument(
        "--test-to",
        default=None,
        help="Send only one sample email to the specified address (e.g. you@example.com)"
    )
    parser.add_argument(
        "--sent-log",
        default=DEFAULT_SENT_LOG,
        help=f"CSV file tracking already-sent contacts (default: {DEFAULT_SENT_LOG})"
    )
    parser.add_argument(
        "--failed-log",
        default=DEFAULT_FAILED_LOG,
        help=f"CSV file logging transmission failures (default: {DEFAULT_FAILED_LOG})"
    )
    parser.add_argument(
        "--log-file",
        default=DEFAULT_LOG_FILE,
        help=f"File path for output logs (default: {DEFAULT_LOG_FILE})"
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to environment configuration file (default: .env)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable detailed debug logging output"
    )

    return parser


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main(argv: Optional[List[str]] = None) -> int:
    """Main execution entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Initialize logging
    logger = setup_logging(args.log_file, args.verbose)
    logger.info("Initializing Automated Bulk Emailer...")

    # Load environment variables from .env
    load_env_file(args.env_file)
    config = get_smtp_config(args)

    start_time = time.time()

    try:
        # Load and validate contacts
        contacts, skipped_count = load_contacts(
            csv_path=args.csv,
            sent_log_path=args.sent_log if not args.dry_run else None,
            logger=logger
        )

        # Send emails
        metrics = send_all(
            contacts=contacts,
            args=args,
            config=config,
            logger=logger
        )
        metrics["skipped"] += skipped_count

        elapsed = time.time() - start_time

        # Print final execution summary
        summary_box = f"""
====================================================================
                    EXECUTION SUMMARY
====================================================================
  Total Parsed Contacts:  {metrics['total'] + skipped_count}
  Successfully Sent:      {metrics['sent']}
  Failed Transmissions:   {metrics['failed']}
  Skipped / Filtered:     {metrics['skipped']}
  Elapsed Duration:       {elapsed:.2f} seconds
====================================================================
"""
        logger.info(summary_box)

        if metrics["failed"] > 0:
            logger.warning(
                f"Some emails failed to send. Check '{args.failed_log}' and '{args.log_file}' for details."
            )
            return 1

        return 0

    except KeyboardInterrupt:
        logger.warning("\nExecution interrupted by user.")
        return 130
    except Exception as e:
        logger.error(f"Execution halted due to error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
