"""
Thought Stream Log — Rolling log of Sourpatches' thinking pipeline.

Captures the full journey: input → cortex activation → synthesis → quality gate → output.
Auto-clears when it hits MAX_LINES so it stays a comfortable review size.

Usage from any fairy:
    from infrastructure.thought_stream_log import thought_log
    thought_log("STAGE", "message", extra={"key": "value"})

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import time
import threading
from pathlib import Path

# ── Config ──
LOG_PATH = Path(__file__).parent.parent / "state" / "thought_stream.log"
MAX_LINES = 500      # ~500 lines ≈ easy to review in one read
_lock = threading.Lock()
_line_count = 0


def _count_lines():
    """Count existing lines on first use."""
    global _line_count
    try:
        if LOG_PATH.exists():
            _line_count = sum(1 for _ in LOG_PATH.open("r", encoding="utf-8"))
        else:
            _line_count = 0
    except Exception:
        _line_count = 0


def thought_log(stage: str, message: str, extra: dict = None):
    """Log a thought pipeline event.

    Args:
        stage: Pipeline stage tag (e.g., "INPUT", "CORTEX", "WM", "LANG-GATE",
               "SYNTHESIS", "OUTPUT", "HABIT", "NUDGE", "DECAY")
        message: Human-readable description of what happened
        extra: Optional dict of diagnostic data (concepts, scores, etc.)
    """
    global _line_count

    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] [{stage}] {message}"
    if extra:
        # Compact single-line extras
        extras = " | ".join(f"{k}={v}" for k, v in extra.items()
                            if v is not None and v != "" and v != [])
        if extras:
            line += f"  ({extras})"
    line += "\n"

    with _lock:
        try:
            # Lazy init line count
            if _line_count == 0 and LOG_PATH.exists():
                _count_lines()

            # Auto-clear when hitting limit
            if _line_count >= MAX_LINES:
                # Write a separator showing the clear happened
                LOG_PATH.write_text(
                    f"[{ts}] [CLEAR] Log cleared at {MAX_LINES} lines — "
                    f"previous stream ended\n"
                    f"{'=' * 70}\n",
                    encoding="utf-8",
                )
                _line_count = 2

            # Append
            with LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(line)
            _line_count += 1

        except Exception:
            pass  # Never crash a fairy for logging


def thought_divider(label: str = ""):
    """Write a visual divider (e.g., between conversations)."""
    global _line_count
    ts = time.strftime("%H:%M:%S")
    line = f"\n[{ts}] {'─' * 50} {label}\n"
    with _lock:
        try:
            with LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(line)
            _line_count += 2
        except Exception:
            pass
