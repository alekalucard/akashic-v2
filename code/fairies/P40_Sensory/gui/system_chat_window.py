"""
system_chat_window.py - HEADLESS MODE STUB
===========================================
System chat has been replaced by web dashboard Inbox/Messages.

To use system chat:
1. Start web dashboard: start_dashboard.bat
2. Go to localhost:8080/inbox for messages
3. Use Broadcast button to send to all fairies
"""

from . import send_to_inbox, route_to_dashboard, _deprecated_warning


def open_system_chat():
    """Stub - directs to web dashboard."""
    _deprecated_warning("open_system_chat")
    print("[system_chat_window] Use web dashboard at localhost:8080/inbox")


def send_message(sender: str, content: str):
    """Send message via postal to web dashboard."""
    route_to_dashboard("system.chat.message", {
        "sender": sender,
        "content": content,
        "source": "system_chat_stub"
    })


class SystemChatWindow:
    """Stub class to prevent import errors."""

    def __init__(self, *args, **kwargs):
        _deprecated_warning("SystemChatWindow")

    def show(self):
        print("[SystemChatWindow] Use web dashboard at localhost:8080")

    def isVisible(self):
        return False

    def add_message(self, sender: str, content: str):
        send_message(sender, content)
