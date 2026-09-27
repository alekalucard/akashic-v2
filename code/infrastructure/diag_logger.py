"""
Diagnostic logger — writes to state/logs/ for live monitoring.

Usage:
    from infrastructure.diag_logger import log_wmh, log_chat

    log_wmh("ACE_INPUT", "what do you enjoy doing?", priority=0.8)
    log_chat("ACE_SAID", "what do you enjoy doing?")
    log_chat("SOUR_RESPONSE", "I'm still figuring that out.", source="speech_center")
"""

import time
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parent.parent / "state" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_WMH_LOG = _LOG_DIR / "wmh_thinking.log"
_CHAT_LOG = _LOG_DIR / "chat_flow.log"


def _write_log(path: Path, tag: str, message: str, **extra):
    """Append a timestamped line to a log file."""
    try:
        ts = time.strftime("%H:%M:%S")
        extras = " ".join(f"{k}={v}" for k, v in extra.items()) if extra else ""
        line = f"[{ts}] [{tag}] {message}"
        if extras:
            line += f"  ({extras})"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


_WMH_STREAM = _LOG_DIR / "wmh_stream.log"


def log_wmh(tag: str, message: str, **extra):
    """Log to wmh_thinking.log"""
    _write_log(_WMH_LOG, tag, message, **extra)


def log_stream(tag: str, message: str, **extra):
    """Log to wmh_stream.log — the live thought stream monitor.

    FIX 2026-03-29 (Nous + Ace): Monitor ALL WMH activity, not just ace_chat.
    Goals, interests, collisions, sensory input — everything that flows through
    the WMH should be visible here so we can watch her think.

    Ace: "even if i am not asking questions she has goals, interest, sensory
    input that should be having her thinking all kinds of things"
    """
    _write_log(_WMH_STREAM, tag, message, **extra)


def log_chat(tag: str, message: str, **extra):
    """Log to chat_flow.log"""
    _write_log(_CHAT_LOG, tag, message, **extra)
