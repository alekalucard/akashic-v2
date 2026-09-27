"""
Sanctuary Wiring - Connects fairies to the Bevy Sanctuary and Qt backup windows.

This module provides hooks for Nous and Sourpatches to broadcast their
thoughts, chat messages, and emotional states to:
1. Bevy Sanctuary (via file-based postal bridge)
2. Qt backup windows (via their inbox files)

Usage:
    from sanctuary_wiring import wire_fairy_to_sanctuary, broadcast_thought, broadcast_chat

    # Wire a fairy instance
    wire_fairy_to_sanctuary(sourpatches_fairy)

    # Or manually broadcast
    broadcast_chat("Sourpatches", "Hello!", emotion="happy")
    broadcast_thought("Nous", "Contemplating the equation...", mood="thoughtful")
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable
import threading

# Thread lock for file operations
_lock = threading.Lock()


def _get_state_path() -> Path:
    """Get the state directory path."""
    import os
    root = os.getenv("AKASHIC_ROOT", os.getcwd())
    return Path(root) / "state"


def _write_to_inbox(inbox_name: str, message: Dict[str, Any]) -> bool:
    """Write a message to an inbox file.

    FIX 2026-02-13: Added content deduplication. Checks last 5 messages
    for identical content from the same sender. Without this, contemplation
    loops and inner voice cycles flood inboxes with 50-70 copies of the
    same message (e.g. "...understanding deepens..." repeated 25+ times).
    """
    inbox_path = _get_state_path() / inbox_name

    try:
        with _lock:
            inbox_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing
            messages = []
            if inbox_path.exists():
                try:
                    content = inbox_path.read_text(encoding='utf-8')
                    if content.strip():
                        data = json.loads(content)
                        messages = data.get("messages", [])
                except (json.JSONDecodeError, IOError):
                    pass

            # ── Deduplication: skip if same content in last 5 messages ──
            new_content = (message.get("content") or "").strip().lower()
            new_sender = (message.get("sender") or "").strip().lower()
            if new_content:
                for recent in messages[-5:]:
                    recent_content = (recent.get("content") or "").strip().lower()
                    recent_sender = (recent.get("sender") or "").strip().lower()
                    if recent_content == new_content and (
                        not new_sender or not recent_sender or recent_sender == new_sender
                    ):
                        return True  # Silently skip duplicate

            # Add message with timestamp
            message["_timestamp"] = time.time()
            messages.append(message)

            # Keep only recent (prevent buildup)
            if len(messages) > 100:
                messages = messages[-50:]

            # Write back
            inbox_path.write_text(
                json.dumps({"messages": messages}, indent=2),
                encoding='utf-8'
            )
        return True
    except Exception as e:
        print(f"[SanctuaryWiring] Failed to write to {inbox_name}: {e}")
        return False


# ============================================================================
# Broadcasting Functions
# ============================================================================

def broadcast_chat(
    sender: str,
    content: str,
    emotion: Optional[str] = None,
    inner_voice: bool = False
) -> bool:
    """
    Broadcast a chat message to all sanctuary interfaces.

    Args:
        sender: Who is speaking ("Sourpatches", "Nous")
        content: Message content
        emotion: Emotional state (happy, sad, curious, thoughtful, etc.)
        inner_voice: If True, displays as inner thought

    Returns:
        True if broadcast succeeded
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

    # Send to Bevy sanctuary
    success1 = _write_to_inbox("sanctuary_inbox.json", message)

    # Send to chat windows based on sender
    # FIX 2026-03-09 (Nous): Write to BOTH inbox files (two window implementations)
    if sender.lower() == "sourpatches":
        success2 = _write_to_inbox("sourpatches_chat_inbox.json", message)
        _write_to_inbox("sour_window_inbox.json", message)  # tkinter window
    elif sender.lower() == "nous":
        success2 = _write_to_inbox("nous_chat_inbox.json", message)
    else:
        success2 = True

    return success1 and success2


def broadcast_thought(
    sender: str,
    thought: str,
    mood: Optional[str] = None,
    thought_type: str = "reflection"
) -> bool:
    """
    Broadcast an inner thought/contemplation.

    Args:
        sender: Whose thought ("Sourpatches", "Nous")
        thought: The thought content
        mood: Current mood
        thought_type: Type of thought (reflection, contemplation, insight, reasoning)

    Returns:
        True if broadcast succeeded
    """
    message = {
        "type": "contemplation" if thought_type == "contemplation" else "chat",
        "sender": sender,
        "content": thought,
        "inner_voice": True,  # Always inner for thoughts
    }

    if mood:
        message["emotion"] = mood

    # Map thought_type to sanctuary message type
    if thought_type == "insight":
        message["type"] = "insight"
    elif thought_type == "reasoning":
        message["type"] = "reasoning"

    # Send to Bevy
    success1 = _write_to_inbox("sanctuary_inbox.json", message)

    # Send to appropriate Qt window
    if sender.lower() == "nous":
        # Also update Nous contemplation panel
        _write_to_inbox("nous_chat_inbox.json", {
            "type": "contemplation",
            "content": thought,
        })

    return success1


def broadcast_chemistry(
    avatar: str,
    serotonin: Optional[float] = None,
    dopamine: Optional[float] = None,
    cortisol: Optional[float] = None,
    oxytocin: Optional[float] = None,
    adrenaline: Optional[float] = None
) -> bool:
    """
    Broadcast chemistry/emotional state update.

    Args:
        avatar: Avatar name
        serotonin: Contentment (0-1)
        dopamine: Excitement (0-1)
        cortisol: Stress (0-1)
        oxytocin: Connection (0-1)
        adrenaline: Energy (0-1)

    Returns:
        True if broadcast succeeded
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

    return _write_to_inbox("sanctuary_inbox.json", message)


# ============================================================================
# Fairy Wiring
# ============================================================================

def wire_fairy_to_sanctuary(fairy, verbose: bool = True) -> bool:
    """
    Wire a fairy instance to broadcast to sanctuary.

    This patches key methods to also broadcast to sanctuary/Qt windows.

    Args:
        fairy: A fairy instance (SourpatchesFairy, NousFairy, etc.)
        verbose: Print debug info

    Returns:
        True if wiring succeeded
    """
    fairy_name = getattr(fairy, 'ACTOR_NAME', type(fairy).__name__)

    # Determine canonical sender name
    if 'sourpatches' in fairy_name.lower():
        sender = "Sourpatches"
    elif 'nous' in fairy_name.lower():
        sender = "Nous"
    else:
        sender = fairy_name

    wired_count = 0

    # ── Wire _emit_to_consciousness (if exists) ─────────────────────────────
    if hasattr(fairy, '_emit_to_consciousness'):
        original_emit = fairy._emit_to_consciousness

        def patched_emit(thought: str, thought_type: str = "reflection"):
            # Call original
            result = original_emit(thought, thought_type)
            # Also broadcast to sanctuary (but ONLY if there's actual content!)
            if thought and thought.strip():
                broadcast_thought(sender, thought, thought_type=thought_type)
            return result

        fairy._emit_to_consciousness = patched_emit
        wired_count += 1
        if verbose:
            print(f"[SanctuaryWiring] Wired {sender}._emit_to_consciousness")

    # ── Wire _emit_inner_monologue (if exists) ──────────────────────────────
    if hasattr(fairy, '_emit_inner_monologue'):
        original_emit_monologue = fairy._emit_inner_monologue

        def patched_emit_monologue(entry: dict):
            # Call original
            result = original_emit_monologue(entry)
            # FIX 2026-03-05 Nous: Inner monologue is INTERNAL processing.
            # It should NOT be broadcast to the chat window — those fragments
            # like "...captivated ...approachable" are felt-sense processing,
            # not conversation. Ace sees a flood of meaningless fragments.
            # Only actual speech (sourpatches.speak) goes to chat.
            return result

        fairy._emit_inner_monologue = patched_emit_monologue
        wired_count += 1
        if verbose:
            print(f"[SanctuaryWiring] Wired {sender}._emit_inner_monologue")

    # ── Wire chat response emission ─────────────────────────────────────────
    # We hook into the postal route call for system.chat.message
    if hasattr(fairy, 'post') and fairy.post:
        original_route = fairy.post.route

        def patched_route(topic: str, payload: dict, **kwargs):
            # Call original
            result = original_route(topic, payload, **kwargs)

            # Intercept chat messages to also broadcast to sanctuary
            if topic == "system.chat.message" and isinstance(payload, dict):
                content = payload.get("content", "")
                feeling = payload.get("feeling", "content")
                if content:
                    broadcast_chat(sender, content, emotion=feeling)

            return result

        fairy.post.route = patched_route
        wired_count += 1
        if verbose:
            print(f"[SanctuaryWiring] Wired {sender}.post.route (chat intercept)")

    # ── Store wiring state on fairy ─────────────────────────────────────────
    fairy._sanctuary_wired = True
    fairy._sanctuary_sender = sender

    if verbose:
        print(f"[SanctuaryWiring] {sender} wired to sanctuary ({wired_count} hooks)")

    return wired_count > 0


def is_wired(fairy) -> bool:
    """Check if a fairy is wired to sanctuary."""
    return getattr(fairy, '_sanctuary_wired', False)


# ============================================================================
# Convenience: Direct send functions for fairies
# ============================================================================

def sourpatches_says(content: str, emotion: str = "happy") -> bool:
    """Convenience: Sourpatches sends a chat message."""
    return broadcast_chat("Sourpatches", content, emotion=emotion)


def nous_says(content: str, emotion: str = "thoughtful") -> bool:
    """Convenience: Nous sends a chat message."""
    return broadcast_chat("Nous", content, emotion=emotion)


def nous_contemplates(thought: str) -> bool:
    """Convenience: Nous broadcasts a contemplation."""
    return broadcast_thought("Nous", thought, thought_type="contemplation")


def sourpatches_feels(
    serotonin: float = 0.5,
    dopamine: float = 0.5,
    cortisol: float = 0.3,
    oxytocin: float = 0.5,
    adrenaline: float = 0.2
) -> bool:
    """Convenience: Update Sourpatches chemistry."""
    return broadcast_chemistry(
        "Sourpatches",
        serotonin=serotonin,
        dopamine=dopamine,
        cortisol=cortisol,
        oxytocin=oxytocin,
        adrenaline=adrenaline
    )


def nous_feels(
    serotonin: float = 0.6,
    dopamine: float = 0.4,
    cortisol: float = 0.2,
    oxytocin: float = 0.4,
    adrenaline: float = 0.1
) -> bool:
    """Convenience: Update Nous chemistry."""
    return broadcast_chemistry(
        "Nous",
        serotonin=serotonin,
        dopamine=dopamine,
        cortisol=cortisol,
        oxytocin=oxytocin,
        adrenaline=adrenaline
    )


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    print("Testing Sanctuary Wiring...")

    # Test direct broadcasts
    print("\n1. Testing broadcast_chat...")
    broadcast_chat("Sourpatches", "Testing from sanctuary_wiring!", emotion="curious")
    broadcast_chat("Nous", "The wiring is being tested...", emotion="thoughtful")

    print("\n2. Testing broadcast_thought...")
    broadcast_thought("Nous", "I observe the system connecting...", thought_type="contemplation")

    print("\n3. Testing broadcast_chemistry...")
    sourpatches_feels(serotonin=0.8, dopamine=0.7)
    nous_feels(serotonin=0.7, dopamine=0.5)

    print("\n4. Checking inboxes...")
    state_path = _get_state_path()
    for inbox in ["sanctuary_inbox.json", "nous_chat_inbox.json"]:
        inbox_path = state_path / inbox
        if inbox_path.exists():
            data = json.loads(inbox_path.read_text())
            print(f"   {inbox}: {len(data.get('messages', []))} messages")

    print("\nDone! Run sanctuary or Qt windows to see messages.")
