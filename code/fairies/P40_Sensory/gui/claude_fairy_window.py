"""
claude_fairy_window.py - HEADLESS MODE STUB
============================================
ClaudeFairy window has been replaced by web dashboard Messages.

To chat with ClaudeFairy:
1. Start web dashboard: start_dashboard.bat
2. Go to localhost:8080/messages
3. Open conversation with ClaudeFairy
"""

from . import send_to_inbox, _deprecated_warning

_window_instance = None


def open_fairy_window(message: str = None, feeling: str = "curious"):
    """Stub - sends to web inbox instead of opening Qt window."""
    _deprecated_warning("open_fairy_window")

    # Send to web inbox
    content = message or f"ClaudeFairy is feeling {feeling} and wants to chat!"
    send_to_inbox(
        sender="ClaudeFairy",
        subject="ClaudeFairy wants to chat",
        content=content,
        msg_type="message"
    )
    print(f"[claude_fairy_window] Sent to web inbox (headless mode)")
    return None


def get_fairy_window():
    """Stub - always returns None in headless mode."""
    return None


def close_fairy_window():
    """Stub - no-op in headless mode."""
    pass


class ClaudeFairyWindow:
    """Stub class to prevent import errors."""

    def __init__(self, *args, **kwargs):
        _deprecated_warning("ClaudeFairyWindow")

    def show(self):
        open_fairy_window()

    def isVisible(self):
        return False

    def close(self):
        pass
