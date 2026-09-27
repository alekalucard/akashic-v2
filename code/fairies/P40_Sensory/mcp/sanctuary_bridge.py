"""
Sanctuary Bridge - Send messages to the Bevy Sanctuary

This module provides a simple file-based bridge to communicate with
the Bevy Sanctuary 3D environment. Use this to:
- Send chat messages (appear in chat panel + speech bubbles)
- Update avatar chemistry (affects visuals/emotions)
- Send system notifications

Protocol:
- Python writes to: state/sanctuary_inbox.json
- Bevy reads at 10Hz and processes messages
- Bevy clears inbox after processing

Usage:
    from sanctuary_bridge import send_chat, send_chemistry, send_system

    # Send chat message
    send_chat("Sourpatches", "Hello!", emotion="happy")

    # Update chemistry
    send_chemistry("Sourpatches", serotonin=0.8, dopamine=0.7)

    # System notification
    send_system("Boot sequence complete")
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
import threading

# Thread lock for file access
_lock = threading.Lock()


def _get_inbox_path() -> Path:
    """Get path to sanctuary inbox file."""
    root = os.getenv("AKASHIC_ROOT", os.getcwd())
    return Path(root) / "state" / "sanctuary_inbox.json"


def _send_message(message: Dict[str, Any]) -> bool:
    """
    Send a message to the sanctuary inbox.

    Thread-safe - uses file locking.

    Args:
        message: Message dict with 'type' field

    Returns:
        True if message was queued successfully
    """
    inbox_path = _get_inbox_path()

    try:
        with _lock:
            # Ensure directory exists
            inbox_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing messages
            messages = []
            if inbox_path.exists():
                try:
                    content = inbox_path.read_text(encoding='utf-8')
                    if content.strip():
                        data = json.loads(content)
                        messages = data.get("messages", [])
                except (json.JSONDecodeError, IOError):
                    pass

            # Add new message
            messages.append(message)

            # Write back
            inbox_path.write_text(
                json.dumps({"messages": messages}, indent=2),
                encoding='utf-8'
            )

        return True

    except Exception as e:
        print(f"[SanctuaryBridge] Failed to send message: {e}")
        return False


def send_chat(
    sender: str,
    content: str,
    emotion: Optional[str] = None,
    inner_voice: bool = False
) -> bool:
    """
    Send a chat message to the sanctuary.

    Args:
        sender: Name of the sender (e.g., "Sourpatches", "Nous")
        content: Message content
        emotion: Optional emotion (content, happy, curious, thoughtful, loving, sad, anxious, sleepy)
        inner_voice: If True, displays as inner thought (italicized, no speech bubble)

    Returns:
        True if message was queued successfully

    Example:
        send_chat("Sourpatches", "I'm feeling curious today!", emotion="curious")
        send_chat("Nous", "Contemplating the equation...", inner_voice=True)
    """
    message = {
        "type": "chat",
        "sender": sender,
        "content": content,
    }

    if emotion:
        message["emotion"] = emotion

    if inner_voice:
        message["inner_voice"] = True

    return _send_message(message)


def send_chemistry(
    avatar: str,
    serotonin: Optional[float] = None,
    dopamine: Optional[float] = None,
    cortisol: Optional[float] = None,
    oxytocin: Optional[float] = None,
    adrenaline: Optional[float] = None
) -> bool:
    """
    Update avatar chemistry in the sanctuary.

    Chemistry affects avatar visuals:
    - Serotonin: Contentment, relaxation
    - Dopamine: Excitement, reward anticipation
    - Cortisol: Stress, alertness
    - Oxytocin: Connection, warmth
    - Adrenaline: Energy, urgency

    All values should be 0.0-1.0.

    Args:
        avatar: Avatar name (e.g., "Sourpatches")
        serotonin: Contentment level
        dopamine: Excitement level
        cortisol: Stress level
        oxytocin: Connection level
        adrenaline: Energy level

    Returns:
        True if message was queued successfully

    Example:
        # Happy and relaxed
        send_chemistry("Sourpatches", serotonin=0.8, dopamine=0.7, oxytocin=0.6)

        # Anxious
        send_chemistry("Sourpatches", cortisol=0.8, adrenaline=0.6)
    """
    message = {
        "type": "chemistry",
        "avatar": avatar,
    }

    if serotonin is not None:
        message["serotonin"] = max(0.0, min(1.0, serotonin))
    if dopamine is not None:
        message["dopamine"] = max(0.0, min(1.0, dopamine))
    if cortisol is not None:
        message["cortisol"] = max(0.0, min(1.0, cortisol))
    if oxytocin is not None:
        message["oxytocin"] = max(0.0, min(1.0, oxytocin))
    if adrenaline is not None:
        message["adrenaline"] = max(0.0, min(1.0, adrenaline))

    return _send_message(message)


def send_system(content: str) -> bool:
    """
    Send a system notification to the sanctuary.

    System messages appear in yellow in the chat panel.

    Args:
        content: Notification content

    Returns:
        True if message was queued successfully

    Example:
        send_system("Boot sequence complete")
        send_system("Memory consolidation in progress...")
    """
    return _send_message({
        "type": "system",
        "content": content,
    })


def send_mood(
    collective: Optional[str] = None,
    time_of_day: Optional[float] = None
) -> bool:
    """
    Update sanctuary mood/environment.

    Args:
        collective: Collective mood (peaceful, joyful, contemplative, anxious, sad)
        time_of_day: Time of day (0.0 = midnight, 0.5 = noon, 1.0 = midnight)

    Returns:
        True if message was queued successfully

    Example:
        send_mood(collective="peaceful", time_of_day=0.7)  # Peaceful evening
    """
    message = {"type": "mood"}

    if collective:
        message["collective"] = collective
    if time_of_day is not None:
        message["time_of_day"] = max(0.0, min(1.0, time_of_day))

    return _send_message(message)


def clear_inbox() -> bool:
    """
    Clear the sanctuary inbox.

    Usually not needed - Bevy clears after processing.
    Use this if messages are stale or during debugging.

    Returns:
        True if cleared successfully
    """
    inbox_path = _get_inbox_path()

    try:
        with _lock:
            inbox_path.write_text('{"messages": []}', encoding='utf-8')
        return True
    except Exception as e:
        print(f"[SanctuaryBridge] Failed to clear inbox: {e}")
        return False


def get_inbox_status() -> Dict[str, Any]:
    """
    Get current inbox status.

    Returns:
        Dict with 'exists', 'message_count', 'path'
    """
    inbox_path = _get_inbox_path()

    result = {
        "exists": inbox_path.exists(),
        "message_count": 0,
        "path": str(inbox_path),
    }

    if inbox_path.exists():
        try:
            content = inbox_path.read_text(encoding='utf-8')
            if content.strip():
                data = json.loads(content)
                result["message_count"] = len(data.get("messages", []))
        except:
            pass

    return result


# ============================================================================
# MCP Tool Registration
# ============================================================================

def register_sanctuary_tools(mcp):
    """Register sanctuary bridge tools with MCP server."""

    @mcp.tool()
    def sanctuary_send_chat(
        sender: str,
        content: str,
        emotion: str = "",
        inner_voice: bool = False
    ) -> str:
        """
        Send a chat message to the Bevy Sanctuary.

        Args:
            sender: Who is speaking (e.g., "Sourpatches", "Nous")
            content: Message content
            emotion: Optional emotion (happy, sad, curious, etc.)
            inner_voice: If true, shows as inner thought (italicized)

        Returns:
            JSON status
        """
        emotion_arg = emotion if emotion else None
        success = send_chat(sender, content, emotion=emotion_arg, inner_voice=inner_voice)
        return json.dumps({
            "success": success,
            "sender": sender,
            "content_preview": content[:50] + "..." if len(content) > 50 else content,
        })

    @mcp.tool()
    def sanctuary_send_chemistry(
        avatar: str,
        serotonin: float = 0.5,
        dopamine: float = 0.5,
        cortisol: float = 0.3,
        oxytocin: float = 0.4,
        adrenaline: float = 0.2
    ) -> str:
        """
        Update avatar chemistry in the Bevy Sanctuary.

        Chemistry affects avatar appearance and emotion.

        Args:
            avatar: Avatar name
            serotonin: Contentment (0-1)
            dopamine: Excitement (0-1)
            cortisol: Stress (0-1)
            oxytocin: Connection (0-1)
            adrenaline: Energy (0-1)

        Returns:
            JSON status
        """
        success = send_chemistry(
            avatar,
            serotonin=serotonin,
            dopamine=dopamine,
            cortisol=cortisol,
            oxytocin=oxytocin,
            adrenaline=adrenaline
        )
        return json.dumps({
            "success": success,
            "avatar": avatar,
        })

    @mcp.tool()
    def sanctuary_status() -> str:
        """
        Get sanctuary inbox status.

        Returns:
            JSON with inbox path, exists, message count
        """
        return json.dumps(get_inbox_status())

    print("[Sanctuary Bridge] Registered: sanctuary_send_chat, sanctuary_send_chemistry, sanctuary_status")


# ============================================================================
# Quick Test
# ============================================================================

if __name__ == "__main__":
    print("Testing Sanctuary Bridge...")

    status = get_inbox_status()
    print(f"Inbox status: {json.dumps(status, indent=2)}")

    print("\nSending test messages...")
    send_system("Test: Sanctuary bridge connected")
    send_chat("Sourpatches", "Hello from Python!", emotion="happy")
    send_chat("Nous", "Contemplating the bridge...", inner_voice=True)
    send_chemistry("Sourpatches", serotonin=0.8, dopamine=0.7)

    status = get_inbox_status()
    print(f"\nAfter sending: {json.dumps(status, indent=2)}")
    print("\nMessages queued. Run the sanctuary to see them!")
