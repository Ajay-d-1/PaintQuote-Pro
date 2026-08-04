"""
config.py
─────────
Load and validate all environment variables from .env.
Import this module in app.py to ensure config is ready before startup.
"""

import os
import sys
import logging
from pathlib import Path

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv not installed — rely on shell env

logger = logging.getLogger(__name__)

# ── AI ────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
HAS_GROQ: bool = (
    bool(GROQ_API_KEY)
    and "your" not in GROQ_API_KEY.lower()
    and len(GROQ_API_KEY) > 20
)

# ── Email ─────────────────────────────────────────────────────
SMTP_SERVER: str   = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT: int     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "").strip()
DAD_EMAIL: str     = os.getenv("DAD_EMAIL", "").strip()

HAS_EMAIL: bool = bool(SMTP_USERNAME and SMTP_PASSWORD and DAD_EMAIL)

# ── App ───────────────────────────────────────────────────────
SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-insecure-key-please-change")
APP_URL: str    = os.getenv("APP_URL", "http://localhost:5000").rstrip("/")
FLASK_ENV: str  = os.getenv("FLASK_ENV", "development")
DEBUG: bool     = FLASK_ENV == "development"


def print_startup_banner() -> None:
    """Log a clear startup summary so the user knows what's configured."""
    lines = [
        "",
        "=" * 58,
        "  🎨  PaintQuote Pro — Starting Up",
        "=" * 58,
        f"  AI (Groq):    {'✅ Enabled (' + GROQ_API_KEY[:8] + '…)' if HAS_GROQ else '⚠️  Disabled — using rule-based fallback'}",
        f"  Email:        {'✅ Enabled → ' + DAD_EMAIL if HAS_EMAIL else '⚠️  Disabled — approvals shown in-app only'}",
        f"  App URL:      {APP_URL}",
        f"  Debug mode:   {DEBUG}",
        "=" * 58,
        "",
    ]
    for line in lines:
        logger.info(line) if line.strip() else print()
    # Always print to console regardless of log level
    print("\n".join(lines))
