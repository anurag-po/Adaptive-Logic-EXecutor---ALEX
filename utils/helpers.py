"""
ALEX — Utility Helpers
Logging setup, safety confirmations, path sanitization, result formatting.
"""

import os
import logging
from datetime import datetime

import config


def setup_logging() -> logging.Logger:
    """Configure and return the application logger."""
    os.makedirs(config.LOG_DIR, exist_ok=True)
    log_file = os.path.join(
        config.LOG_DIR,
        f"alex_{datetime.now().strftime('%Y%m%d')}.log",
    )

    logger = logging.getLogger("ALEX")
    logger.setLevel(logging.DEBUG)

    # File handler — detailed
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    ))

    # Console handler — info+
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        "[ALEX] %(message)s"
    ))

    if not logger.handlers:
        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger


def confirm_action(action_name: str, args: dict) -> bool:
    """
    Prompt the user for confirmation before executing a sensitive action.
    Returns True if confirmed, False otherwise.
    """
    print(f"\n[!] SAFETY GATE")
    print(f"    Action : {action_name}")
    print(f"    Args   : {args}")
    try:
        response = input("   Proceed? (y/n): ").strip().lower()
        return response in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def sanitize_path(path: str) -> str:
    """Normalize and validate a file system path."""
    if not path:
        return ""
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    path = os.path.normpath(path)
    return path


def format_result(result: dict) -> str:
    """Convert an action result dict to a human-readable speech string."""
    status = result.get("status", "unknown")
    output = result.get("output", "")
    error = result.get("error", "")

    if status == "success":
        if output:
            return f"Done. {output}"
        return "Done. The action was completed successfully."
    elif status == "cancelled":
        return "Action cancelled by user."
    elif status == "error":
        return f"Sorry, there was an error: {error}"
    else:
        return f"Action finished with status: {status}"


def get_logger() -> logging.Logger:
    """Get the ALEX logger (creates if needed)."""
    logger = logging.getLogger("ALEX")
    if not logger.handlers:
        setup_logging()
    return logger
