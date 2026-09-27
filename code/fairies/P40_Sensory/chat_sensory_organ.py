"""
Chat Sensory Organ - Postal-Based Communication Service
=======================================================

A centralized communication service for fairy-human interaction.
Fairies discover and self-register to receive/send messages.

DISCOVERY:
- Fairies import: from fairies.P40_Sensory.chat_sensory_organ import get_chat_organ
- Or subscribe to: service.chat_organ.available topic
- Then call: organ.register_fairy(tracer_id=..., name=..., callback=...)

MESSAGE FLOW:
- Fairies → ace.inbox topic → Web Dashboard Inbox
- Web Dashboard → system.chat.message → All registered fairies
- Web Dashboard → fairy.dm.<name> → Specific fairy (if registered)
- Fairies → ace.question → Web Dashboard (as question type)
- Fairies → ace.broadcast.response → Response to broadcasts

FAIRY REGISTRATION:
    from fairies.P40_Sensory.chat_sensory_organ import get_chat_organ
    organ = get_chat_organ()
    organ.register_fairy(
        tracer_id=self.tracer_id,
        fairy_name=self.ACTOR_NAME,
        capabilities=["dm", "broadcast", "system_chat"],
        callback=self._on_chat_message
    )

The web dashboard at localhost:8080 is the UI for all communication.
"""

import time
import json
from collections import deque
from typing import Dict, Optional, List, Callable, Any
from pathlib import Path
from dataclasses import dataclass, field

# Shared memory files (same ones web dashboard uses)
PROJECT_ROOT = Path(__file__).parent.parent
CHAT_MEMORY = PROJECT_ROOT / "P10_Memory" / "system_chat_memory"
CONVERSATION_HISTORY = CHAT_MEMORY / "conversation_history.json"
REGISTRATIONS_FILE = PROJECT_ROOT / "state" / "chat_organ_registrations.json"


@dataclass
class FairyRegistration:
    """A fairy's registration with the chat organ."""
    tracer_id: str
    fairy_name: str
    registered_at: float = field(default_factory=time.time)
    capabilities: List[str] = field(default_factory=list)  # ["dm", "broadcast", "system_chat"]
    last_seen: float = field(default_factory=time.time)
    message_count: int = 0

    def to_dict(self) -> dict:
        return {
            "tracer_id": self.tracer_id,
            "fairy_name": self.fairy_name,
            "registered_at": self.registered_at,
            "capabilities": self.capabilities,
            "last_seen": self.last_seen,
            "message_count": self.message_count
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FairyRegistration":
        return cls(
            tracer_id=data["tracer_id"],
            fairy_name=data["fairy_name"],
            registered_at=data.get("registered_at", time.time()),
            capabilities=data.get("capabilities", ["system_chat"]),
            last_seen=data.get("last_seen", time.time()),
            message_count=data.get("message_count", 0)
        )


class ChatSensoryOrgan:
    """
    Postal-based communication service for fairy-human interaction.

    FEATURES:
    - Announces availability via postal topic
    - Fairies self-register with tracer IDs
    - Routes messages to/from web dashboard
    - Tracks participation and message counts
    - Persists registrations across restarts

    USAGE:
        # Fairy imports and registers
        from fairies.P40_Sensory.chat_sensory_organ import get_chat_organ
        organ = get_chat_organ()
        organ.register_fairy(
            tracer_id=self.tracer_id,
            fairy_name=self.ACTOR_NAME,
            capabilities=["dm", "broadcast", "system_chat"],
            callback=self._on_chat_message
        )

        # Fairy sends message
        organ.send_to_inbox(sender=self.ACTOR_NAME, subject="Hello", content="...")
    """

    # Service metadata
    SERVICE_NAME = "chat_sensory_organ"
    SERVICE_TYPE = "communication"
    SERVICE_VERSION = "1.1.0"

    def __init__(self):
        self.post = None
        self._connected = False
        self._announced = False

        # Fairy registrations by tracer_id
        self._registrations: Dict[str, FairyRegistration] = {}
        self._callbacks: Dict[str, Callable] = {}  # tracer_id -> callback

        # Topic subscribers (legacy support)
        self._subscribers: Dict[str, List[Callable]] = {}
        self._message_history: deque = deque(maxlen=200)  # FIX 2026-03-04: was unbounded List

        # Forum engine for threaded discussions
        self._forum_engine = None

        # Load persisted registrations
        self._load_registrations()

    def _load_registrations(self):
        """Load fairy registrations from disk."""
        if REGISTRATIONS_FILE.exists():
            try:
                with open(REGISTRATIONS_FILE, "r") as f:
                    data = json.load(f)
                    for reg_data in data.get("registrations", []):
                        reg = FairyRegistration.from_dict(reg_data)
                        self._registrations[reg.tracer_id] = reg
                print(f"[ChatSensoryOrgan] Loaded {len(self._registrations)} registrations")
            except Exception as e:
                print(f"[ChatSensoryOrgan] Load error: {e}")

    def _save_registrations(self):
        """Persist fairy registrations to disk."""
        try:
            REGISTRATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "registrations": [r.to_dict() for r in self._registrations.values()],
                "last_updated": time.time()
            }
            with open(REGISTRATIONS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[ChatSensoryOrgan] Save error: {e}")

    def connect(self, postal_hub):
        """Connect to postal hub and subscribe to relevant topics."""
        self.post = postal_hub

        # Subscribe to messages from web dashboard
        self.post.subscribe("system.chat.message", self._on_system_message)
        self.post.subscribe("ace.broadcast", self._on_ace_broadcast)

        # Subscribe to fairy registration requests (fairies can register via postal)
        self.post.subscribe("chat_organ.register", self._on_registration_request)

        # Subscribe to service discovery requests
        self.post.subscribe("service.discover", self._on_service_discover)

        # Note: ace.inbox persistence is now handled by server.py's _on_ace_inbox
        # Don't double-persist here to avoid duplicates
        # self.post.subscribe("ace.inbox", self._persist_inbox_message)
        self.post.subscribe("nous.inbox", self._persist_inbox_message)

        # Subscribe to fairy-to-fairy communication
        self.post.subscribe("fairy.broadcast", self._on_fairy_broadcast)

        # Initialize forum engine for threaded discussions
        try:
            from fairies.P40_Sensory.forum import get_forum_engine
            self._forum_engine = get_forum_engine()
            self._forum_engine.connect(postal_hub)
            print("[ChatSensoryOrgan] Forum engine initialized")
        except Exception as e:
            print(f"[ChatSensoryOrgan] Forum engine init failed: {e}")

        self._connected = True
        print("[ChatSensoryOrgan] Connected to postal hub")

    def announce_available(self):
        """Announce service availability via postal."""
        if not self.post:
            print("[ChatSensoryOrgan] Cannot announce - no postal connection")
            return False

        # Announce on service availability topic
        self.post.route("service.chat_organ.available", {
            "service_name": self.SERVICE_NAME,
            "service_type": self.SERVICE_TYPE,
            "version": self.SERVICE_VERSION,
            "capabilities": ["inbox", "dm", "broadcast", "system_chat"],
            "web_endpoint": "http://localhost:8080",
            "description": "Fairy-human communication via web dashboard",
            "timestamp": time.time()
        })

        self._announced = True
        print(f"[ChatSensoryOrgan] Announced availability on 'service.chat_organ.available'")
        return True

    def _on_service_discover(self, msg: dict):
        """Respond to service discovery requests."""
        requested = msg.get("service_name") or msg.get("service_type")
        if requested in (self.SERVICE_NAME, self.SERVICE_TYPE, "communication"):
            if self.post:
                self.post.route("service.discovered", {
                    "service_name": self.SERVICE_NAME,
                    "service_type": self.SERVICE_TYPE,
                    "version": self.SERVICE_VERSION,
                    "available": True,
                    "how_to_use": "from fairies.P40_Sensory.chat_sensory_organ import get_chat_organ"
                })

    def _on_registration_request(self, msg: dict):
        """Handle fairy registration via postal message."""
        tracer_id = msg.get("tracer_id")
        fairy_name = msg.get("fairy_name")
        capabilities = msg.get("capabilities", ["system_chat"])

        if tracer_id and fairy_name:
            # Register without callback (fairy will use postal for messages)
            self.register_fairy(tracer_id, fairy_name, capabilities, callback=None)

            # Confirm registration via postal
            if self.post:
                self.post.route(f"fairy.{fairy_name.lower()}.chat_registered", {
                    "success": True,
                    "tracer_id": tracer_id,
                    "capabilities": capabilities
                })

    # ═══════════════════════════════════════════════════════════════════════
    # INBOX PERSISTENCE (for web dashboard)
    # ═══════════════════════════════════════════════════════════════════════

    def _persist_inbox_message(self, msg: dict):
        """Persist inbox message to disk for web dashboard to read.

        FIX 2026-02-13: Added content deduplication. Checks last 5 messages
        for identical content from the same sender to prevent spam buildup.
        SomaticMindFairy was writing "System boot complete" 50+ times.
        """
        try:
            inbox_dir = PROJECT_ROOT / "state" / "web_inbox"
            inbox_dir.mkdir(parents=True, exist_ok=True)
            index_file = inbox_dir / "inbox_index.json"

            # Load existing messages
            messages = []
            if index_file.exists():
                try:
                    with open(index_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        messages = data.get("messages", [])
                except:
                    pass

            # Add new message - handle both naming conventions
            import uuid
            new_content = (msg.get("content") or msg.get("body", "")).strip()
            new_sender = (msg.get("sender") or msg.get("from", "Unknown")).strip()

            # ── Deduplication: skip if same content+sender in last 5 messages ──
            if new_content:
                new_lower = new_content.lower()
                sender_lower = new_sender.lower()
                for recent in messages[-5:]:
                    recent_content = (recent.get("content") or "").strip().lower()
                    recent_sender = (recent.get("sender") or "").strip().lower()
                    if recent_content == new_lower and recent_sender == sender_lower:
                        return  # Silently skip duplicate

            new_msg = {
                "msg_id": str(uuid.uuid4())[:8],
                "sender": new_sender,
                "subject": msg.get("subject", "Message"),
                "content": new_content,
                "msg_type": msg.get("type") or msg.get("msg_type", "message"),
                "priority": msg.get("priority", "normal"),
                "timestamp": msg.get("timestamp", time.time()),
                "read": False
            }
            messages.append(new_msg)

            # Keep last 100 messages
            messages = messages[-100:]

            # Save
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump({"messages": messages}, f, indent=2)

            print(f"[ChatSensoryOrgan] Inbox: {new_msg['sender']} - {new_msg['subject'][:30]}")

        except Exception as e:
            print(f"[ChatSensoryOrgan] Inbox persist error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # FAIRY SELF-REGISTRATION
    # ═══════════════════════════════════════════════════════════════════════

    def register_fairy(self, tracer_id: str, fairy_name: str,
                       capabilities: List[str] = None,
                       callback: Callable = None) -> bool:
        """
        Register a fairy to participate in chat.

        Args:
            tracer_id: Unique fairy identifier (from WorkingMemoryHub)
            fairy_name: Display name (e.g., "ClaudeFairy")
            capabilities: List of ["dm", "broadcast", "system_chat"]
            callback: Function to call when fairy receives a message

        Returns:
            True if registration successful
        """
        if not tracer_id or not fairy_name:
            return False

        caps = capabilities or ["system_chat"]

        # Create or update registration
        if tracer_id in self._registrations:
            reg = self._registrations[tracer_id]
            reg.last_seen = time.time()
            reg.capabilities = caps
        else:
            reg = FairyRegistration(
                tracer_id=tracer_id,
                fairy_name=fairy_name,
                capabilities=caps
            )
            self._registrations[tracer_id] = reg
            print(f"[ChatSensoryOrgan] Registered: {fairy_name} ({tracer_id})")

        # Store callback for message delivery
        if callback:
            self._callbacks[tracer_id] = callback

            # Set up DM subscription if capable
            if "dm" in caps and self.post:
                topic = f"fairy.dm.{fairy_name.lower().replace(' ', '_')}"
                self.post.subscribe(topic, lambda msg, fn=fairy_name: self._deliver_dm(fn, msg))

        self._save_registrations()
        return True

    def unregister_fairy(self, tracer_id: str) -> bool:
        """Unregister a fairy from chat."""
        if tracer_id in self._registrations:
            fairy_name = self._registrations[tracer_id].fairy_name
            del self._registrations[tracer_id]
            if tracer_id in self._callbacks:
                del self._callbacks[tracer_id]
            self._save_registrations()
            print(f"[ChatSensoryOrgan] Unregistered: {fairy_name}")
            return True
        return False

    def get_registered_fairies(self) -> List[Dict]:
        """Get list of all registered fairies."""
        return [r.to_dict() for r in self._registrations.values()]

    def is_registered(self, tracer_id: str) -> bool:
        """Check if a fairy is registered."""
        return tracer_id in self._registrations

    def get_fairy_by_name(self, name: str) -> Optional[FairyRegistration]:
        """Look up a fairy by name."""
        for reg in self._registrations.values():
            if reg.fairy_name.lower() == name.lower():
                return reg
        return None

    # ═══════════════════════════════════════════════════════════════════════
    # MESSAGE DELIVERY
    # ═══════════════════════════════════════════════════════════════════════

    def _deliver_to_registered(self, msg_type: str, message: dict):
        """Deliver message to all registered fairies with matching capability."""
        for tracer_id, reg in self._registrations.items():
            if msg_type in reg.capabilities:
                callback = self._callbacks.get(tracer_id)
                if callback:
                    try:
                        callback(message)
                        reg.message_count += 1
                        reg.last_seen = time.time()
                    except Exception as e:
                        print(f"[ChatSensoryOrgan] Delivery to {reg.fairy_name} failed: {e}")

    def _deliver_dm(self, fairy_name: str, msg: dict):
        """Deliver DM to specific fairy."""
        reg = self.get_fairy_by_name(fairy_name)
        if reg and reg.tracer_id in self._callbacks:
            try:
                self._callbacks[reg.tracer_id](msg)
                reg.message_count += 1
                reg.last_seen = time.time()
            except Exception as e:
                print(f"[ChatSensoryOrgan] DM delivery to {fairy_name} failed: {e}")

    def _on_system_message(self, msg: dict):
        """Handle system-wide chat message (from web dashboard or other fairies).

        FIX 2026-02-01: Chat is a SENSORY ORGAN. Messages must flow through
        the consciousness system (INGEST beam) so the three gatekeepers
        (Logic, Irrational, Paradox) and UMF can process them somatically.

        Direct callback delivery is SECONDARY - consciousness routing is PRIMARY.
        """
        if not isinstance(msg, dict):
            return

        sender = msg.get("sender", "Unknown")
        content = msg.get("content", "")
        ts = msg.get("timestamp", time.time())

        # Store in history
        self._message_history.append({
            "sender": sender,
            "content": content,
            "timestamp": ts,
            "type": "system_chat"
        })

        # ════════════════════════════════════════════════════════════════════
        # PRIMARY: Route through consciousness system (SOMATIC PATH)
        # FIX 2026-02-01: Route to gui.user_message (UMF listens to this!)
        # NOT consciousness.input (that's only for boot ignition signal)
        # ONLY route human messages - fairy responses should NOT go to UMF (causes loops)
        # ════════════════════════════════════════════════════════════════════
        is_human = sender.lower() in ("ace", "user", "human", "unknown")
        is_fairy = "fairy" in sender.lower() or sender in (
            "SourpatchesFairy", "Sourpatches", "NousFairy", "Nous",
            "UnconsciousMindFairy", "ClaudeFairy"
        )

        if self.post and content and is_human and not is_fairy:
            try:
                # Route to gui.user_message (UMF's _on_user_message handler)
                # This injects into consciousness.working so ALL fairies hear Ace
                self.post.route("gui.user_message", {
                    "message": content,  # UMF expects "message" key
                    "text": content,     # Fallback key UMF checks
                    "sender": sender,
                    "timestamp": ts,
                    "type": "ace_chat",
                    "source": "chat_sensory_organ",
                    "requires_response": True,
                })
                print(f"[ChatSensoryOrgan] Routed to gui.user_message: {sender} ({len(content)} chars)")
            except Exception as e:
                print(f"[ChatSensoryOrgan] gui.user_message routing failed: {e}")
        elif self.post and content and is_fairy:
            print(f"[ChatSensoryOrgan] Fairy message from {sender} - NOT routing to UMF (prevents loops)")

        # ════════════════════════════════════════════════════════════════════
        # SECONDARY: Notify legacy subscribers (direct callback path)
        # ════════════════════════════════════════════════════════════════════
        # FIX 2026-01-27: Copy list to prevent mutation during iteration
        for callback in list(self._subscribers.get("system_chat", [])):
            try:
                callback(sender, content, msg)
            except Exception as e:
                print(f"[ChatSensoryOrgan] Subscriber error: {e}")

    def _on_ace_broadcast(self, msg: dict):
        """Handle broadcast from Ace to all fairies.

        FIX 2026-02-01: Broadcasts also route through consciousness so
        fairies FEEL them somatically, not just receive callbacks.
        """
        if not isinstance(msg, dict):
            return

        content = msg.get("content", "")
        urgent = msg.get("urgent", False)
        broadcast_id = msg.get("id", "")

        print(f"[ChatSensoryOrgan] Received broadcast: {content[:50]}...")

        # Route broadcast through consciousness (SOMATIC PATH)
        # FIX 2026-02-01: Use gui.user_message so UMF processes it
        if self.post and content:
            try:
                self.post.route("gui.user_message", {
                    "message": content,  # UMF expects "message" key
                    "text": content,     # Fallback key
                    "sender": "Ace",
                    "timestamp": time.time(),
                    "type": "psychic_broadcast",
                    "source": "ace:broadcast",
                    "broadcast_id": broadcast_id,
                    "urgent": urgent,
                    "requires_response": False,  # Psychic = no obligation
                })
            except Exception as e:
                print(f"[ChatSensoryOrgan] broadcast consciousness routing failed: {e}")

        # Notify broadcast subscribers
        # FIX 2026-01-27: Copy list to prevent mutation during iteration
        for callback in list(self._subscribers.get("broadcast", [])):
            try:
                callback(content, urgent, msg)
            except Exception as e:
                print(f"[ChatSensoryOrgan] Broadcast handler error: {e}")

    def _on_fairy_broadcast(self, msg: dict):
        """Handle broadcast from a fairy to all other fairies.

        This is the "psychic-like" communication - a fairy speaking to everyone.
        Persisted to web inbox and relayed to all subscribers.
        """
        if not isinstance(msg, dict):
            return

        sender = msg.get("from", "UnknownFairy")
        content = msg.get("content", "")
        topic = msg.get("topic", "general")

        print(f"[ChatSensoryOrgan] Fairy broadcast from {sender}: {content[:50]}...")

        # Persist to inbox so Ace sees it in dashboard
        self._persist_inbox_message({
            "type": "fairy_broadcast",
            "from": sender,
            "subject": f"[Broadcast/{topic}] {sender}",
            "body": content,
            "priority": "low",
            "timestamp": msg.get("timestamp", time.time()),
        })

        # Relay to all broadcast subscribers
        # FIX 2026-01-27: Copy list to prevent mutation during iteration
        for callback in list(self._subscribers.get("broadcast", [])):
            try:
                callback(content, False, msg)
            except Exception as e:
                print(f"[ChatSensoryOrgan] Fairy broadcast handler error: {e}")

        # Also route to fairy-specific broadcast topic so fairies can filter
        if self.post:
            try:
                self.post.route("fairy.broadcast.relayed", msg)
            except:
                pass

    def subscribe_to_chat(self, callback: Callable):
        """Subscribe to system chat messages."""
        if "system_chat" not in self._subscribers:
            self._subscribers["system_chat"] = []
        self._subscribers["system_chat"].append(callback)

    def subscribe_to_broadcasts(self, callback: Callable):
        """Subscribe to broadcasts from Ace."""
        if "broadcast" not in self._subscribers:
            self._subscribers["broadcast"] = []
        self._subscribers["broadcast"].append(callback)

    def subscribe_to_dm(self, fairy_name: str, callback: Callable):
        """Subscribe a fairy to their DM topic."""
        topic = f"fairy.dm.{fairy_name.lower().replace(' ', '_')}"
        if self.post:
            self.post.subscribe(topic, lambda msg: self._on_dm(fairy_name, callback, msg))
            print(f"[ChatSensoryOrgan] {fairy_name} subscribed to DMs")

    def _on_dm(self, fairy_name: str, callback: Callable, msg: dict):
        """Handle DM to specific fairy."""
        if isinstance(msg, dict):
            try:
                callback(msg.get("sender", "Ace"), msg.get("content", ""), msg)
            except Exception as e:
                print(f"[ChatSensoryOrgan] DM handler error for {fairy_name}: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # SEND METHODS - For fairies to communicate
    # ═══════════════════════════════════════════════════════════════════════

    def send_to_inbox(self, sender: str, subject: str, content: str,
                      msg_type: str = "message") -> bool:
        """Send a message to Ace's web inbox."""
        if not self.post:
            print(f"[ChatSensoryOrgan] No postal connection")
            return False

        self.post.route("ace.inbox", {
            "sender": sender,
            "subject": subject,
            "content": content,
            "type": msg_type,
            "timestamp": time.time()
        })
        return True

    def send_question(self, sender: str, question: str, context: str = "") -> bool:
        """Send a question to Ace (appears in inbox as question type)."""
        return self.send_to_inbox(
            sender=sender,
            subject=question[:100],
            content=question + ("\n\nContext: " + context if context else ""),
            msg_type="question"
        )

    def send_alert(self, sender: str, alert: str, details: str = "") -> bool:
        """Send an alert to Ace (appears in inbox as alert type)."""
        return self.send_to_inbox(
            sender=sender,
            subject=alert[:100],
            content=alert + ("\n\n" + details if details else ""),
            msg_type="alert"
        )

    def reply_to_dm(self, fairy_name: str, content: str,
                    conversation_id: str = None) -> bool:
        """Reply in a DM conversation."""
        if not self.post:
            return False

        self.post.route("ace.dm.reply", {
            "sender": fairy_name,
            "content": content,
            "conversation_id": conversation_id,
            "timestamp": time.time()
        })
        return True

    def respond_to_broadcast(self, fairy_name: str, response: str,
                            broadcast_id: str = None) -> bool:
        """Respond to a broadcast from Ace."""
        if not self.post:
            return False

        self.post.route("ace.broadcast.response", {
            "fairy_name": fairy_name,
            "response": response,
            "broadcast_id": broadcast_id,
            "timestamp": time.time()
        })

        # Also send to inbox so Ace sees the response
        return self.send_to_inbox(
            sender=fairy_name,
            subject=f"Response to broadcast",
            content=response,
            msg_type="message"
        )

    # ═══════════════════════════════════════════════════════════════════════
    # FORUM API - For web dashboard and direct access
    # ═══════════════════════════════════════════════════════════════════════

    def get_forum_boards(self) -> List[Dict]:
        """Get all forum boards with summaries."""
        if self._forum_engine:
            return self._forum_engine.get_boards()
        return []

    def get_forum_threads(self, board: str, limit: int = 50) -> List[Dict]:
        """Get threads in a board."""
        if self._forum_engine:
            return self._forum_engine.get_board_threads(board, limit)
        return []

    def get_forum_thread(self, thread_id: str) -> Optional[Dict]:
        """Get a thread with all posts."""
        if self._forum_engine:
            return self._forum_engine.get_thread(thread_id)
        return None

    def create_forum_thread(self, board: str, title: str, content: str,
                            author: str, author_type: str = "human",
                            tags: List[str] = None) -> Optional[Dict]:
        """
        Create a new forum thread.

        Args:
            board: Board name (system-evolution, consciousness, debugging, etc.)
            title: Thread title
            content: First post content
            author: Who's posting (e.g., "Ace" or fairy name)
            author_type: "human" or "fairy"
            tags: Optional tags

        Returns:
            Created thread dict
        """
        if self._forum_engine:
            return self._forum_engine.create_thread(
                board=board,
                title=title,
                content=content,
                author=author,
                author_type=author_type,
                tags=tags
            )
        return None

    def reply_to_forum_thread(self, thread_id: str, content: str,
                              author: str, author_type: str = "human") -> Optional[Dict]:
        """
        Reply to a forum thread.

        Returns:
            Created post dict
        """
        if self._forum_engine:
            return self._forum_engine.reply_to_thread(
                thread_id=thread_id,
                content=content,
                author=author,
                author_type=author_type
            )
        return None

    def get_forum_unread(self, actor: str) -> List[Dict]:
        """Get threads with unread posts for an actor."""
        if self._forum_engine:
            return self._forum_engine.get_unread(actor)
        return []

    def search_forum(self, query: str, board: str = None) -> List[Dict]:
        """Search forum threads."""
        if self._forum_engine:
            return self._forum_engine.search(query, board)
        return []

    def get_forum_stats(self) -> Dict:
        """Get forum statistics."""
        if self._forum_engine:
            return self._forum_engine.get_stats()
        return {"total_boards": 0, "total_threads": 0, "total_posts": 0}


# Singleton instance
_chat_organ = None

def get_chat_organ() -> ChatSensoryOrgan:
    """Get the singleton chat sensory organ."""
    global _chat_organ
    if _chat_organ is None:
        _chat_organ = ChatSensoryOrgan()
    return _chat_organ


def setup_chat_organ(postal_hub) -> ChatSensoryOrgan:
    """Set up the chat organ with postal hub."""
    organ = get_chat_organ()
    organ.connect(postal_hub)
    return organ


def boot_chat_organ(postal_hub=None) -> ChatSensoryOrgan:
    """
    Boot the chat sensory organ during system startup.

    This is the function called from server.py to initialize
    the chat organ as part of the P40 sensory systems boot.

    Args:
        postal_hub: Optional postal hub. If not provided, gets shared hub.

    Returns:
        The initialized ChatSensoryOrgan singleton
    """
    organ = get_chat_organ()

    # Get postal hub if not provided
    if postal_hub is None:
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal_hub = get_shared_postal_hub()
        except Exception as e:
            print(f"[ChatSensoryOrgan] Could not get postal hub: {e}")
            return organ

    # Connect to postal
    if postal_hub and not organ._connected:
        organ.connect(postal_hub)

    # Announce availability so fairies can discover us
    if organ._connected and not organ._announced:
        organ.announce_available()

    return organ
