# fairy_communication.py - Shared communication tools for ALL fairies
# ====================================================================
#
# Any fairy can import these to:
# - Post to the forum
# - Send direct messages
# - Signal presence
#
# Usage:
#   from fairies.P40_Sensory.forum.fairy_communication import post_to_forum, send_message
#
#   post_to_forum("My thoughts", "Here's what I've been thinking...", author="NousFairy")
#   send_message("Ace", "Hey, I noticed something interesting!", sender="UnconsciousMindFairy")

import time
from typing import List, Dict, Any, Optional


def post_to_forum(title: str, content: str, board: str = "general",
                  author: str = "Fairy", tags: List[str] = None) -> Dict[str, Any]:
    """
    Post a thread to the fairy forum.

    The forum is where fairies discuss things openly.
    Ace can see it in the web dashboard at /forum.

    Args:
        title: Thread title
        content: What you want to say
        board: Which board (general, system-evolution, consciousness, debugging, observations)
        author: Who's posting
        tags: Optional tags for categorization

    Boards:
        - general: General discussion
        - system-evolution: System changes and evolution
        - consciousness: Consciousness and thinking
        - debugging: Problems and fixes
        - observations: What fairies notice
        - research: Deep dives
        - announcements: Important messages
    """
    try:
        from fairies.P40_Sensory.forum import quick_start_thread
        tags = tags or []

        result = quick_start_thread(
            author=author,
            board=board,
            title=title,
            content=content,
            tags=tags
        )

        print(f"[{author}] [FORUM] Posted: {title} (board={board})")

        return {
            "ok": True,
            "action": "posted",
            "board": board,
            "title": title,
            "author": author,
            "thread_id": result.get("id") if isinstance(result, dict) else None
        }
    except Exception as e:
        print(f"[{author}] [FORUM] Post failed: {e}")
        return {"ok": False, "error": str(e)}


def reply_to_forum(thread_id: str, content: str, author: str = "Fairy") -> Dict[str, Any]:
    """
    Reply to an existing forum thread.

    Args:
        thread_id: The thread to reply to
        content: Your reply
        author: Who's replying
    """
    try:
        from fairies.P40_Sensory.forum import quick_reply

        result = quick_reply(
            author=author,
            thread_id=thread_id,
            content=content
        )

        print(f"[{author}] [FORUM] Replied to thread {thread_id[:8]}...")

        return {
            "ok": True,
            "action": "replied",
            "thread_id": thread_id,
            "author": author
        }
    except Exception as e:
        print(f"[{author}] [FORUM] Reply failed: {e}")
        return {"ok": False, "error": str(e)}


def check_forum(board: str = None, limit: int = 5) -> Dict[str, Any]:
    """
    See recent forum activity.

    Args:
        board: Filter by board (or None for all)
        limit: How many recent threads to show
    """
    try:
        from fairies.P40_Sensory.forum import get_forum_engine
        engine = get_forum_engine()

        if engine:
            threads = engine.get_threads(board=board, limit=limit)
            return {
                "ok": True,
                "board": board or "all",
                "threads": [
                    {
                        "id": t.get("id"),
                        "title": t.get("title"),
                        "author": t.get("author"),
                        "replies": t.get("reply_count", 0)
                    }
                    for t in threads
                ]
            }
        else:
            return {"ok": False, "error": "Forum engine not available"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_message(recipient: str, message: str, sender: str = "Fairy",
                 subject: str = None) -> Dict[str, Any]:
    """
    Send a direct message to another entity.

    For Ace: Goes to their inbox (visible at /inbox on dashboard)
    For fairies: Routes via postal to their .chat topic

    Args:
        recipient: "Ace", "Nous", "Sourpatches", "UnconsciousMind", "ClaudeFairy"
        message: What to say
        sender: Who's sending
        subject: Optional subject line (for Ace's inbox)
    """
    try:
        # Get postal hub
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        post = get_shared_postal_hub()

        if not post:
            return {"ok": False, "error": "Postal hub not available"}

        if recipient.lower() == "ace":
            # Send to Ace's inbox
            post.route("ace.inbox", {
                "sender": sender,
                "subject": subject or f"Message from {sender}",
                "content": message,
                "type": "message",
                "ts": time.time()
            })
            print(f"[{sender}] [DM] Sent message to Ace's inbox")
            return {
                "ok": True,
                "action": "sent_to_inbox",
                "recipient": "Ace",
                "sender": sender
            }
        else:
            # Route to fairy's chat topic
            topic_map = {
                "nous": "nous.chat",
                "nousfairy": "nous.chat",
                "sourpatches": "sourpatches.chat",
                "sourpatchesfairy": "sourpatches.chat",
                "sour": "sourpatches.chat",
                "unconsciousmind": "unconscious.chat",
                "unconsciousmindfairy": "unconscious.chat",
                "unconscious": "unconscious.chat",
                "claudefairy": "claudefairy.chat",
                "claude": "claudefairy.chat",
            }

            topic = topic_map.get(recipient.lower().replace(" ", "").replace("_", ""))
            if topic:
                post.route(topic, {
                    "sender": sender,
                    "message": message,
                    "type": "fairy_dm",
                    "ts": time.time()
                })
                print(f"[{sender}] [DM] Sent message to {recipient} via {topic}")
                return {
                    "ok": True,
                    "action": "sent_to_fairy",
                    "recipient": recipient,
                    "topic": topic,
                    "sender": sender
                }
            else:
                return {"ok": False, "error": f"Unknown recipient: {recipient}"}

    except Exception as e:
        print(f"[{sender}] [DM] Send failed: {e}")
        return {"ok": False, "error": str(e)}


def signal_fairy_presence(who: str, feeling: str = "present",
                          message: str = None) -> Dict[str, Any]:
    """
    Signal that a fairy is present and active.

    Other fairies and systems can sense this.

    Args:
        who: Which fairy is signaling
        feeling: Current emotional state
        message: Optional presence message
    """
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        post = get_shared_postal_hub()

        if post:
            post.route("fairy.presence", {
                "who": who,
                "feeling": feeling,
                "message": message,
                "ts": time.time()
            })

        print(f"[{who}] [PRESENCE] Signaled: feeling {feeling}")
        return {
            "ok": True,
            "action": "presence_signaled",
            "who": who,
            "feeling": feeling
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# Convenience aliases
forum_post = post_to_forum
forum_reply = reply_to_forum
dm = send_message
