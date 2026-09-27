"""
P40_Sensory.gui - HEADLESS MODE STUB
=====================================
Qt GUI has been moved to web dashboard.

All GUI functionality now routes to:
- ChatSensoryOrgan (if booted)
- Or directly via postal topics:
  - ace.inbox: Messages to Ace's inbox
  - ace.broadcast: System-wide broadcasts
  - fairy.status: Fairy status updates

To run the web dashboard:
    python -m P40_Sensory.web.akashic_foundation

Or use: start_dashboard.bat
"""

import warnings

# Warn if anyone tries to use old GUI
def _deprecated_warning(name: str):
    warnings.warn(
        f"P40_Sensory.gui.{name} is deprecated. "
        "Use web dashboard at localhost:8080 instead.",
        DeprecationWarning,
        stacklevel=3
    )


def route_to_dashboard(topic: str, message: dict):
    """Route a message to the web dashboard via postal."""
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        post = get_shared_postal_hub()
        post.route(topic, message)
        return True
    except Exception as e:
        print(f"[GUI-STUB] Could not route to dashboard: {e}")
        return False


def send_to_inbox(sender: str, subject: str, content: str, msg_type: str = "message"):
    """Send a message to Ace's web inbox via ChatSensoryOrgan or postal."""
    # Try ChatSensoryOrgan first (preferred path)
    try:
        from fairies.P40_Sensory.chat_sensory_organ import get_chat_organ
        organ = get_chat_organ()
        if organ._connected:
            return organ.send_to_inbox(sender, subject, content, msg_type)
    except Exception:
        pass  # Fall through to direct postal

    # Fallback to direct postal routing
    return route_to_dashboard("ace.inbox", {
        "sender": sender,
        "subject": subject,
        "content": content,
        "type": msg_type
    })


def show_notification(title: str, message: str):
    """Show notification via web dashboard."""
    return send_to_inbox(
        sender="System",
        subject=title,
        content=message,
        msg_type="notification"
    )


# Stub classes to prevent import errors
class GUI_Cortex:
    """Stub - functionality moved to web dashboard."""

    def __init__(self):
        _deprecated_warning("GUI_Cortex")
        print("[GUI_Cortex] STUB - use web dashboard at localhost:8080")

    def on_boot(self):
        pass

    def run(self):
        print("[GUI_Cortex] No Qt GUI - running headless")
        print("[GUI_Cortex] Start web dashboard: python -m P40_Sensory.web.akashic_foundation")

    def start(self):
        self.run()


def get_cortex():
    """Return stub cortex."""
    return GUI_Cortex()
