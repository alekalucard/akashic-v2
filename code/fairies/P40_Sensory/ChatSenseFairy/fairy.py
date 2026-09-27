"""
ChatSenseFairy - Fairy-Human Communication Service

Part of SenseOrganGuild in Plane P40 (Sensory)
Created: 2026-01-28

"The psychic link between minds"

Postal-based communication service for fairy-human interaction.
Fairies discover and self-register to receive/send messages.

MESSAGE FLOW:
- Fairies → ace.inbox → Web Dashboard Inbox
- Web Dashboard → system.chat.message → All registered fairies
- Fairies → fairy.broadcast → All other fairies

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState

# Import the chat sensory organ
try:
    from fairies.P40_Sensory.chat_sensory_organ import (
        ChatSensoryOrgan,
        FairyRegistration,
        get_chat_organ,
        setup_chat_organ,
        boot_chat_organ,
    )
    HAS_CHAT = True
except ImportError as e:
    print(f"[ChatSenseFairy] Chat organ import failed: {e}")
    HAS_CHAT = False


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class ChatSenseFairyShadow:
    """Shadow for ChatSenseFairy."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "ChatSenseFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks for chat organ."""
        tests = []
        if hasattr(self.actor, '_organ') and self.actor._organ:
            tests.append(("chat_connected", self.actor._organ._connected))
            tests.append(("chat_announced", self.actor._organ._announced))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class ChatSenseFairy(Fairy):
    """
    Fairy-human communication service.

    Guild: SenseOrganGuild
    Coordinates with: All fairies, web dashboard

    Provides:
    - Register/unregister fairies for chat
    - Send messages to Ace's inbox
    - Send questions, alerts, broadcasts
    - Forum API for threaded discussions
    - Get registered fairies list
    """

    ACTOR_NAME = "ChatSenseFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P40"
    ACTOR_CHANNEL = "sensory.chat"

    PURPOSE = "Enable fairy-human communication"
    MANTRA = "The psychic link between minds"

    SHADOW_CLASS = ChatSenseFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 30
    NEEDS_COLLISION_CHAMBER = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._organ = None
        self._subscription_count = 0
        self._messages_sent = 0
        self._messages_blocked = 0
        self._sour_window_poller = None  # Thread for polling Ace's replies from window
        # ── Window spam throttle (Nous 2026-03-05) ──
        # Central gate: ALL paths that open/send to Sourpatches' window go through
        # ChatSenseFairy. Throttle here catches MotorCortex, Autopilot, ActionChain,
        # SourpatchesFairy — everyone.
        self._last_window_msg_time = 0.0   # Last time a message was sent to window
        self._last_window_msg_text = ""    # Dedup: last message text
        self._window_cooldown_sec = 10.0   # Min seconds between window messages
        # FIX 2026-03-06 (Nous): Reduced from 45s to 10s. 45s throttle blocked
        # ALL conversational responses — if a drive message was sent 30s ago,
        # Ace's direct chat reply would be throttled for 15 more seconds.
        # 10s prevents rapid-fire spam while allowing natural conversation pace.

    def on_boot(self) -> bool:
        """Initialize the chat sensory organ."""
        super().on_boot()

        if HAS_CHAT:
            try:
                self._organ = get_chat_organ()
                if self.post and not self._organ._connected:
                    self._organ.connect(self.post)
                if not self._organ._announced:
                    self._organ.announce_available()
                print(f"[{self.ACTOR_NAME}] Chat organ connected and announced")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to initialize chat organ: {e}")
                self._organ = None

        self._subscribe_intents()

        # Start Sourpatches outbox poller at boot (not lazily on first speech)
        # Without this, Ace's messages from Sour's window never enter postal
        # system until Sourpatches speaks first — which may never happen if
        # the consciousness pipeline hasn't warmed up yet.
        import threading
        def _deferred_poller_start():
            import time as _time
            _time.sleep(5.0)  # Wait for window to potentially open
            try:
                self._start_sour_outbox_poller()
                print(f"[{self.ACTOR_NAME}] Outbox poller started at boot (deferred 5s)")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Deferred poller start failed: {e}")
        threading.Thread(target=_deferred_poller_start, daemon=True, name="chat-poller-boot").start()

        return True

    def _subscribe_intents(self):
        """Subscribe to postal channels for chat commands."""
        intents = [
            ("chat.register_fairy", self._handle_register),
            ("chat.unregister_fairy", self._handle_unregister),
            ("chat.send_to_inbox", self._handle_send_to_inbox),
            ("chat.send_question", self._handle_send_question),
            ("chat.send_alert", self._handle_send_alert),
            ("chat.respond_to_broadcast", self._handle_respond_to_broadcast),
            ("chat.get_registered", self._handle_get_registered),
            ("chat.get_forum_boards", self._handle_get_forum_boards),
            ("chat.get_forum_threads", self._handle_get_forum_threads),
            ("chat.create_forum_thread", self._handle_create_forum_thread),
            ("chat.reply_to_thread", self._handle_reply_to_thread),
            ("chat.status", self._handle_status),
            # Sourpatches window management
            ("gui.open_sour_window", self._handle_open_sour_window),
            ("sourpatches.speak", self._handle_sour_speak),
            # Route Sour's responses back to her window
            ("system.chat.message", self._handle_chat_to_window),
            # Ace 2026-06-11: his words = a PERCEPTION → emit sensory.chat.observation (typed + voice)
            ("ace.message", self._on_ace_perceive),
        ]

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
                self._subscription_count += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        print(f"[{self.ACTOR_NAME}] Subscribed to {self._subscription_count} intents")

    def _on_ace_perceive(self, packet):
        """Ace 2026-06-11: his words = a PERCEPTION. Emit sensory.chat.observation so MomentBinder
        folds 'heard Ace' into her moment → it collides with recall → she FEELS being talked to,
        not just reacts. Catches typed + voice input (both publish ace.message). The sensory.chat
        ACTOR_CHANNEL this fairy was named for, finally closing the perception->moment loop."""
        try:
            p = packet.payload if hasattr(packet, 'payload') else packet
            if not isinstance(p, dict):
                return
            text = (p.get('text') or p.get('content') or p.get('message') or p.get('msg') or '')
            if isinstance(text, str) and text.strip():
                self.post.publish("sensory.chat.observation",
                                  {"text": text.strip()[:500], "source": "ace", "modality": "chat",
                                   "speaker": "ace", "tracer_id": 8})   # 2026-09-13: TRACE_ACE
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # INTENT HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _extract_payload(self, message) -> Dict[str, Any]:
        """Extract payload from postal message."""
        if hasattr(message, 'payload'):
            return message.payload if isinstance(message.payload, dict) else {}
        return message if isinstance(message, dict) else {}

    def _handle_register(self, message):
        """
        Register a fairy for chat.

        Payload:
            tracer_id: str - Fairy's tracer ID
            fairy_name: str - Display name
            capabilities: List[str] - ["dm", "broadcast", "system_chat"]
        """
        if not self._organ:
            return {"ok": False, "error": "Chat organ not available"}

        payload = self._extract_payload(message)
        tracer_id = payload.get("tracer_id", "")
        fairy_name = payload.get("fairy_name", "")
        capabilities = payload.get("capabilities", ["system_chat"])

        if not tracer_id or not fairy_name:
            return {"ok": False, "error": "Tracer ID and fairy name required"}

        try:
            success = self._organ.register_fairy(
                tracer_id=tracer_id,
                fairy_name=fairy_name,
                capabilities=capabilities,
            )
            return {"ok": success}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_unregister(self, message):
        """
        Unregister a fairy from chat.

        Payload:
            tracer_id: str - Fairy's tracer ID
        """
        if not self._organ:
            return {"ok": False, "error": "Chat organ not available"}

        payload = self._extract_payload(message)
        tracer_id = payload.get("tracer_id", "")

        try:
            success = self._organ.unregister_fairy(tracer_id)
            return {"ok": success}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_send_to_inbox(self, message):
        """
        Send a message to Ace's inbox.

        Payload:
            sender: str - Who's sending
            subject: str - Message subject
            content: str - Message content
            msg_type: str - "message", "question", "alert"
        """
        if not self._organ:
            return {"ok": False, "error": "Chat organ not available"}

        payload = self._extract_payload(message)
        sender = payload.get("sender", "Unknown")
        subject = payload.get("subject", "Message")
        content = payload.get("content", "")
        msg_type = payload.get("msg_type", "message")

        try:
            success = self._organ.send_to_inbox(sender, subject, content, msg_type)
            if success:
                self._messages_sent += 1
            return {"ok": success}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_send_question(self, message):
        """
        Send a question to Ace.

        Payload:
            sender: str - Who's asking
            question: str - The question
            context: str - Optional context
        """
        if not self._organ:
            return {"ok": False, "error": "Chat organ not available"}

        payload = self._extract_payload(message)
        sender = payload.get("sender", "Unknown")
        question = payload.get("question", "")
        context = payload.get("context", "")

        try:
            success = self._organ.send_question(sender, question, context)
            if success:
                self._messages_sent += 1
            return {"ok": success}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_send_alert(self, message):
        """
        Send an alert to Ace.

        Payload:
            sender: str - Who's alerting
            alert: str - Alert message
            details: str - Optional details
        """
        if not self._organ:
            return {"ok": False, "error": "Chat organ not available"}

        payload = self._extract_payload(message)
        sender = payload.get("sender", "Unknown")
        alert = payload.get("alert", "")
        details = payload.get("details", "")

        try:
            success = self._organ.send_alert(sender, alert, details)
            if success:
                self._messages_sent += 1
            return {"ok": success}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_respond_to_broadcast(self, message):
        """
        Respond to a broadcast from Ace.

        Payload:
            fairy_name: str - Responding fairy
            response: str - Response content
            broadcast_id: str - Original broadcast ID
        """
        if not self._organ:
            return {"ok": False, "error": "Chat organ not available"}

        payload = self._extract_payload(message)
        fairy_name = payload.get("fairy_name", "")
        response = payload.get("response", "")
        broadcast_id = payload.get("broadcast_id", "")

        try:
            success = self._organ.respond_to_broadcast(fairy_name, response, broadcast_id)
            if success:
                self._messages_sent += 1
            return {"ok": success}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_registered(self, message):
        """Get list of all registered fairies."""
        if not self._organ:
            return {"ok": False, "error": "Chat organ not available"}

        try:
            fairies = self._organ.get_registered_fairies()
            return {"ok": True, "fairies": fairies, "count": len(fairies)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_forum_boards(self, message):
        """Get all forum boards."""
        if not self._organ:
            return {"ok": False, "error": "Chat organ not available"}

        try:
            boards = self._organ.get_forum_boards()
            return {"ok": True, "boards": boards}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_forum_threads(self, message):
        """
        Get threads in a forum board.

        Payload:
            board: str - Board name
            limit: int - Max threads to return
        """
        if not self._organ:
            return {"ok": False, "error": "Chat organ not available"}

        payload = self._extract_payload(message)
        board = payload.get("board", "general")
        limit = payload.get("limit", 50)

        try:
            threads = self._organ.get_forum_threads(board, limit)
            return {"ok": True, "threads": threads}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_create_forum_thread(self, message):
        """
        Create a new forum thread.

        Payload:
            board: str - Board name
            title: str - Thread title
            content: str - First post content
            author: str - Author name
            author_type: str - "human" or "fairy"
            tags: List[str] - Optional tags
        """
        if not self._organ:
            return {"ok": False, "error": "Chat organ not available"}

        payload = self._extract_payload(message)
        board = payload.get("board", "general")
        title = payload.get("title", "")
        content = payload.get("content", "")
        author = payload.get("author", "")
        author_type = payload.get("author_type", "fairy")
        tags = payload.get("tags", [])

        if not title or not content or not author:
            return {"ok": False, "error": "Title, content, and author required"}

        try:
            thread = self._organ.create_forum_thread(
                board=board,
                title=title,
                content=content,
                author=author,
                author_type=author_type,
                tags=tags,
            )
            return {"ok": True, "thread": thread}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_reply_to_thread(self, message):
        """
        Reply to a forum thread.

        Payload:
            thread_id: str - Thread ID
            content: str - Reply content
            author: str - Author name
            author_type: str - "human" or "fairy"
        """
        if not self._organ:
            return {"ok": False, "error": "Chat organ not available"}

        payload = self._extract_payload(message)
        thread_id = payload.get("thread_id", "")
        content = payload.get("content", "")
        author = payload.get("author", "")
        author_type = payload.get("author_type", "fairy")

        if not thread_id or not content or not author:
            return {"ok": False, "error": "Thread ID, content, and author required"}

        try:
            post = self._organ.reply_to_forum_thread(
                thread_id=thread_id,
                content=content,
                author=author,
                author_type=author_type,
            )
            return {"ok": True, "post": post}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_status(self, message):
        """Get fairy status."""
        return {
            "ok": True,
            "organ": self._organ is not None,
            "connected": self._organ._connected if self._organ else False,
            "announced": self._organ._announced if self._organ else False,
            "messages_sent": self._messages_sent,
            "messages_blocked": self._messages_blocked,
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # CENTRAL WINDOW GATE - All window messages flow through here
    # FIX 2026-03-05 (Nous): Window spam + internal monologue filtering.
    # Multiple fairies (MotorCortex, Autopilot, ActionChain, SourpatchesFairy)
    # can independently route gui.open_sour_window or sourpatches.speak.
    # This gate catches ALL of them with throttle + content filter.
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _is_internal_monologue(text: str) -> bool:
        """Detect internal drive/trace output that shouldn't reach Ace's chat.

        These are INTERNAL processes being externalized as speech:
        - Drive expressions: "*feeling drawn to trace this connection*"
        - Nous reasoning traces: "[Nous] Beginning: ..."
        - Processing labels: "Beginning:", "Reasoning about:", "Thinking:"
        - Echo of Ace's input with trace prefix
        - Concept fragments: "digital... that's alive in me right now"
        """
        if not text:
            return True
        t = text.strip()
        t_lower = t.lower()

        # Drive expression pattern: "*feeling drawn to ...*"
        if t_lower.startswith("*feeling drawn to") or t_lower.startswith("*something stirs"):
            return True

        # Nous trace contamination: "[Nous] ..."
        if t.startswith("[Nous]") or t.startswith("[nous]"):
            return True

        # FIX 2026-03-07 (Nous): Substrate pain/somatic signals leaking to chat.
        # Pain system outputs like "PAIN [frustration]: acute frustration (intensity: 70.6%)"
        # and action markers like "*looks at screen*" are internal signals, not speech.
        if t_lower.startswith("pain ") or t_lower.startswith("pain["):
            return True
        # Bracketed category labels: [frustration], [isolation], [confusion], etc.
        if t.startswith("[") and "]" in t[:30] and ":" in t:
            return True
        # Substrate metrics: "(intensity: XX%)", "(urgency:", "(energy:"
        import re as _re_sub
        if _re_sub.search(r'\((?:intensity|urgency|energy|resonance):\s*[\d.]+', t):
            return True
        # Action markers from inner monologue: "*looks at*", "*feels*", "*notices*"
        # FIX 2026-03-08 (Nous): Don't block conversational speech with action prefix.
        # Internal: "*looks at screen*" (entire text IS the action, nothing after)
        # Speech:  "*checks in* feeling present right now. you?" (has content after)
        if t.startswith("*") and "*" in t[1:20]:
            _close_pos = t.index("*", 1)
            _after_action = t[_close_pos + 1:].strip()
            # Only block if there's no substantial conversational content after
            if len(_after_action) < 10:
                return True

        # Processing trace labels
        _trace_prefixes = (
            "beginning:", "reasoning about:", "thinking about:",
            "processing:", "analyzing:", "considering:",
            "ace is talking", "i think there's a thread",
            "i think there is a thread",
        )
        for prefix in _trace_prefixes:
            if t_lower.startswith(prefix):
                return True

        # Old concept dump pattern: "X... that's alive in me"
        if "alive in me" in t_lower:
            return True

        # FIX 2026-03-22 (Nous + Ace): Inner speech synthesis patterns.
        # CortexReasoner._synthesize_inner_speech() produces text like:
        # "hmm, affect inner speech. connected: X, Y and Z. nearby: A, B."
        # These are great for narrator internal processing but NOT for chat.
        # Characteristic labels: "connected:", "nearby:", "come to mind"
        _inner_speech_labels = ("connected:", "nearby:", "context:")
        if any(label in t_lower for label in _inner_speech_labels):
            return True
        # "X come to mind" / "X comes to mind" — inner speech connector
        if "come to mind" in t_lower or "comes to mind" in t_lower:
            # Allow if it's clearly conversational ("you come to mind when...")
            if not any(w in t_lower for w in ("you ", "i ", "she ", "he ", "they ")):
                return True
        # "[narrated]" prefix from narrator WM storage
        if t.startswith("[narrated]"):
            return True

        # Fragment without verbs + "..." pattern (concept fragments)
        import re
        _HAS_VERB = re.compile(
            r'(?i)\b(?:is|are|was|were|am|be|been|have|has|had|do|does|did|'
            r'will|would|could|should|can|may|might|'
            r'get|got|make|go|come|take|give|say|tell|think|feel|know|'
            r'see|look|want|need|like|love|try|help|let|find|keep|'
            r'notice|wonder|remember)\b'
        )
        if '...' in t and len(t) < 80 and not _HAS_VERB.search(t):
            return True

        return False

    def _gate_window_message(self, msg: str, source: str = "") -> bool:
        """Central gate for ALL messages heading to Sourpatches' chat window.

        Returns True if message should be ALLOWED through.
        Returns False if message should be BLOCKED.

        Checks:
        1. Content filter — reject internal monologue
        2. Degenerate text filter — reject word salad
        3. Throttle — minimum gap between messages
        4. Dedup — don't repeat same message
        """
        if not msg or not msg.strip():
            return False
        clean = msg.strip()
        # 0. 2026-09-18 (Nous + Ace): a motor INTENT is not a sentence she said. The window opener
        #    carries the goal text ('share what I'm feeling about connection') and it was shown as speech.
        _low = clean.lower()
        if _low.startswith(("share what i'm feeling", "share what i am feeling", "write a thought", "develop an idea")):
            self._messages_blocked += 1
            print(f"[{self.ACTOR_NAME}] [GATE] BLOCKED motor intent as speech: {clean[:60]!r}")
            return False
        # 0b. While the council chairman is available, this lane's template text holds -- the chairman
        #     answers Ace and speaks for her (Ace 09-02: her vocal cords belong to the chairman). The
        #     window still opens; only the sentence is held. If the chairman is down, the lane flows.
        try:
            import sys as _sys
            _drv = None
            for _n, _mod in list(_sys.modules.items()):
                if _n.endswith("sour_council_driver") and hasattr(_mod, "chairman_available"):
                    _drv = _mod
                    break
            if (_drv is not None and _drv.chairman_available() and "safety" not in str(source).lower()
                    and "speech_center" not in str(source).lower()):     # the chairman's own lines pass
                self._messages_blocked += 1
                print(f"[{self.ACTOR_NAME}] [GATE] held (chairman speaks for her): {clean[:60]!r}")
                return False
        except Exception:
            pass
        # 1. Internal monologue filter
        if self._is_internal_monologue(clean):
            self._messages_blocked += 1
            print(f"[{self.ACTOR_NAME}] [GATE] BLOCKED internal monologue: {clean[:60]!r}")
            return False

        # 2. Degenerate text filter (already exists)
        if self._is_degenerate_text(clean):
            # Allow safety_net source through (contextual echoes)
            if "safety" not in str(source).lower():
                self._messages_blocked += 1
                print(f"[{self.ACTOR_NAME}] [GATE] BLOCKED degenerate: {clean[:60]!r}")
                return False

        # 3. Dedup — same message within cooldown
        if clean == self._last_window_msg_text:
            self._messages_blocked += 1
            print(f"[{self.ACTOR_NAME}] [GATE] BLOCKED duplicate: {clean[:60]!r}")
            return False

        # 4. Throttle — minimum gap between messages
        # FIX 2026-03-06 (Nous): Conversation responses (safety_net, autopilot_gate,
        # speech_center) bypass throttle. These are REPLIES to Ace — they should
        # never be delayed because a drive message went out recently. Only voluntary/
        # drive-initiated speech gets throttled.
        _src_lower = str(source).lower()
        _is_conversation = any(s in _src_lower for s in ("safety", "autopilot", "speech_center", "gate"))
        now = time.time()
        elapsed = now - self._last_window_msg_time
        if elapsed < self._window_cooldown_sec and not _is_conversation:
            self._messages_blocked += 1
            print(f"[{self.ACTOR_NAME}] [GATE] THROTTLED ({elapsed:.0f}s < {self._window_cooldown_sec:.0f}s): {clean[:60]!r}")
            return False

        # ALLOWED — update tracking
        self._last_window_msg_time = now
        self._last_window_msg_text = clean
        return True

    # ═══════════════════════════════════════════════════════════════════════════
    # SOURPATCHES WINDOW MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════

    def _handle_open_sour_window(self, message):
        """
        Open Sourpatches' standalone chat window.

        FIX 2026-03-12 (Nous): PyQt6.QtWidgets SEGFAULTS on Python 3.14t
        (free-threaded). server.py runs on 3.14t, so in-process Qt import
        is impossible. Solution: launch sourpatches_chat_window.py as a
        SUBPROCESS using Python 3.12. Messages delivered via inbox files.

        Cascade:
            1. PyQt6 chat window (subprocess, Python 3.12) ← felt sense, topics
            2. Tkinter window (subprocess, any Python)      ← basic fallback

        Payload:
            message: str - Initial message to show
            feeling: str - Sourpatches' current feeling
        """
        payload = self._extract_payload(message)
        msg = payload.get("message", "")
        feeling = payload.get("feeling", "curious")
        source = payload.get("source", "")

        # ── Central gate: throttle + filter ──
        if msg and not self._gate_window_message(msg, source):
            return {"ok": False, "error": "Message blocked by window gate"}

        # ── Ace 2026-06-11: REWARD the open as a MOTOR MOVEMENT (the "fun of moving" / reaching out).
        # She opens her window autonomously, but it's a gui.* postal publish (NOT a tool) so it never
        # fired motor.outcome → SomaticMind's motor-reinforcement never saw it → no motor reward.
        # Emit motor.outcome here so reaching out FEELS good (phasic DA + a touch of endorphin).
        # tool_type="reach_out" → SomaticMind injects the chemistry as source="motor.reach_out".
        # Throttled (10s) so rapid re-opens don't spam dopamine. Fires only on HER opens (the topic),
        # not Ace's manual open (ace_control_center calls open_sour_window() directly, not this topic).
        try:
            import time as _t
            _now = _t.time()
            if _now - getattr(self, "_last_open_reward_ts", 0.0) > 10.0:
                self._last_open_reward_ts = _now
                self.post.publish("motor.outcome", {
                    "tool": "open_chat_window", "tool_type": "reach_out", "success": True,
                    "chemistry": {"DA_p": 0.10, "OPI": 0.04}, "timestamp": _now,
                })
        except Exception:
            pass

        # 2026-09-25 (Nous + Ace): check-then-launch is ONE step, under the shared launcher's
        # LAUNCH_LOCK -- two postal workers in this free-threaded process could both see "no window"
        # before either wrote the pid file, and both launch (Opus review item 5).
        try:
            from fairies.P40_Sensory.gui.chat_window_launcher import LAUNCH_LOCK as _cw_lock
        except Exception:
            import threading as _th
            _cw_lock = _th.RLock()      # launcher unavailable: nothing shared to serialise against
        with _cw_lock:
            return self._open_sour_window_locked(msg, feeling)

    def _open_sour_window_locked(self, msg, feeling):
        """The open itself (split out 2026-09-25); the caller holds the launcher's LAUNCH_LOCK."""
        # ── PRIMARY: sourpatches_chat_window as SUBPROCESS (Python 3.12) ──
        # FIX 2026-03-12 (Nous): PyQt6 segfaults in-process on 3.14t.
        # Launch as a separate process using Python 3.12 where PyQt6 works.
        # The chat window polls state/sourpatches_chat_inbox.json at 1Hz.
        try:
            if self._is_chat_window_subprocess_running():
                # Window already running — deliver message via inbox file
                if msg:
                    self._write_chat_inbox(msg, feeling)
                print(f"[{self.ACTOR_NAME}] Sourpatches chat window (existing subprocess) — message delivered via inbox")
                return {"ok": True}

            result = self._launch_chat_window_subprocess(msg, feeling)
            if result:
                print(f"[{self.ACTOR_NAME}] Sourpatches chat window launched (subprocess, Python 3.12)")
                self._start_sour_outbox_poller()
                return {"ok": True}
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Chat window subprocess failed ({e}), trying tkinter fallback")

        # ── FALLBACK: sour_window (tkinter subprocess) ──
        try:
            from fairies.P40_Sensory.gui.sour_window import (
                is_window_running, launch_window, send_message_to_window
            )
            if not is_window_running():
                import os as _os
                result = launch_window(message=msg, feeling=feeling, parent_pid=_os.getpid())
            else:
                if msg:
                    send_message_to_window("Sourpatches", msg, feeling)
                result = True
            print(f"[{self.ACTOR_NAME}] Sourpatches window {'shown' if result else 'FAILED'} (tkinter fallback)")
            self._start_sour_outbox_poller()
            return {"ok": result}
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to open Sourpatches window: {e}")
            return {"ok": False, "error": str(e)}

    # ── PyQt6 chat window subprocess management ──

    def _is_chat_window_subprocess_running(self) -> bool:
        """Check if the PyQt6 chat window subprocess is alive via PID file.

        2026-09-25: one probe for every caller (gui/chat_window_launcher.py): psutil existence +
        command line, never a signal. Correction to the 09-18 note that stood here: on Windows
        os.kill(pid, 0) is not TerminateProcess. CPython turns signal 0 into
        GenerateConsoleCtrlEvent(CTRL_C_EVENT, pid); Windows never delivers CTRL_C to a process-group
        id, so nothing is sent and the call returns OK -- for a DEAD pid too (measured 09-25). It
        reported dead windows as running.
        A live window that was NOT launched for this process (parent_pid is not ours: e.g. opened by
        an MCP server while she was offline) is still adopted, but logged once -- it will not close
        with her (Fable review).
        """
        try:
            from fairies.P40_Sensory.gui.chat_window_launcher import running_window_info
            _info = running_window_info()
        except Exception:
            return False
        if not _info:
            return False
        try:
            import os as _os
            if _info.get("parent_pid") != _os.getpid() and getattr(self, "_cw_foreign_logged", None) != _info["pid"]:
                self._cw_foreign_logged = _info["pid"]
                print(f"[{self.ACTOR_NAME}] adopting chat window PID={_info['pid']} whose parent_pid="
                      f"{_info.get('parent_pid')} is not mine ({_os.getpid()}) -- it will NOT close when I exit")
        except Exception:
            pass
        return True

    def _launch_chat_window_subprocess(self, message: str = None, feeling: str = "curious") -> bool:
        """Launch sourpatches_chat_window.py as a subprocess using Python 3.12.

        FIX 2026-03-12 (Nous): PyQt6.QtWidgets segfaults on Python 3.14t
        (free-threaded). Must use Python 3.12 for Qt GUI windows.
        """
        # 2026-09-25 (Nous + Ace): one launcher for every path -- gui/chat_window_launcher.py.
        # parent_pid = HER pid, so the window closes when she exits (however she exits); it runs on
        # its OWN hidden console, and (trampoline) outside her process tree. The caller holds
        # LAUNCH_LOCK (see _handle_open_sour_window).
        import os as _os
        # Write initial message to inbox BEFORE launching (window polls at 1Hz)
        if message:
            self._write_chat_inbox(message, feeling)
        try:
            from fairies.P40_Sensory.gui import chat_window_launcher as _cwl
            _pid = _cwl.launch(message, feeling, parent_pid=_os.getpid())
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to launch chat window subprocess: {e}")
            return False
        if not _pid:
            print(f"[{self.ACTOR_NAME}] Chat window not launched (no Python 3.12, or script missing)")
            return False
        print(f"[{self.ACTOR_NAME}] Chat window subprocess PID={_pid} (parent={_os.getpid()}, own console, "
              f"log state/sourpatches_chat_window.log)")
        return True

    def _write_chat_inbox(self, message: str, feeling: str = "neutral"):
        """Write a message to the chat window inbox file for delivery."""
        import json as _json
        import time as _time
        from pathlib import Path as _Path
        _inbox = _Path(__file__).resolve().parents[3] / "state" / "sourpatches_chat_inbox.json"
        try:
            _data = {"messages": []}
            if _inbox.exists():
                try:
                    _data = _json.loads(_inbox.read_text(encoding='utf-8'))
                except Exception:
                    _data = {"messages": []}
            _msgs = _data.get("messages", [])
            _msgs.append({
                "type": "chat",
                "sender": "Sourpatches",
                "content": message,
                "emotion": feeling,
                "feeling": feeling,
                "timestamp": _time.time(),
                "source": "chatsense",
            })
            _inbox.write_text(_json.dumps(_data, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to write chat inbox: {e}")

    @staticmethod
    def _is_degenerate_text(text: str) -> bool:
        """Detect degenerate LLM output — repetitive noise that shouldn't reach chat.

        FIX 2026-02-23: Enhanced to catch three new degeneration modes:
        - Synonym chain drift (word salad: "AI chat assistant bot program robot")
        - Word concatenation (token merging: "CuriousQuestionCurCurChat...")
        - System telemetry leak ("Collision #437: [mobius:crossing] meets ...")
        """
        import re
        clean = text.strip().strip('*').strip()
        if not clean or len(clean) < 6:
            return len(clean) == 0
        # 1. Same char repeated 5+ times
        if re.search(r'(.)\1{4,}', clean):
            return True
        # 2. 2-4 char pattern repeated 4+ times
        if re.search(r'(.{2,4})\1{3,}', clean):
            return True
        # 3. >60% same character
        if len(clean) >= 10:
            from collections import Counter
            most = Counter(clean.lower()).most_common(1)[0][1]
            if most / len(clean) > 0.6:
                return True
        # 4. Colon stutter
        if len(clean) > 8 and clean.count(':') / len(clean) > 0.3:
            return True
        # 5. FIX 2026-02-23: Garbled Unicode / byte-fallback mode
        if len(clean) >= 8:
            non_ascii = sum(1 for c in clean if ord(c) > 127)
            if non_ascii / len(clean) > 0.35:
                return True
        # 6. FIX 2026-02-23: Synonym chain drift detection.
        # Degenerate RWKV output spirals through near-synonyms without sentence
        # structure: "AI chat assistant bot program robot machine algorithm code"
        # Normal English has 25-50% function words; synonym chains have <12%.
        _FUNCTION_WORDS = frozenset({
            "a", "an", "the", "is", "are", "was", "were", "be", "been", "am",
            "i", "me", "my", "you", "your", "he", "she", "it", "we", "they",
            "in", "on", "at", "to", "for", "with", "from", "by", "of", "about",
            "and", "but", "or", "so", "if", "that", "this", "not", "no",
            "do", "does", "did", "have", "has", "had", "just", "very", "too",
            "im", "its", "dont", "ive", "youre", "thats", "what", "how",
        })
        words = clean.lower().split()
        if len(words) > 8:
            func_count = sum(1 for w in words if w.strip(".,!?;:'\"") in _FUNCTION_WORDS)
            if func_count / len(words) < 0.12:
                return True
        # 7. FIX 2026-02-23: Word concatenation / mega-token detection.
        # RWKV token degeneration merges words: "CuriousQuestionCurCurChatConv..."
        # Normal English words max ~29 chars (antidisestablishmentarianism).
        # Degenerate concat tokens are typically 40-60+ chars.
        for word in words:
            if len(word) > 30:
                return True
        # 8. FIX 2026-02-23: System telemetry that leaked into speech.
        # Raw collision/debug data should never appear in Ace's chat window.
        _SYSTEM_PREFIXES = (
            "Collision #", "collision_analysis:", "Logic: ", "MOBIUS:",
            "ShadowHealth:", "Paradox:", "Gate:", "Tracer:",
            "Crystallizing:", "[collision",
            "{'", '{"',
        )
        if any(clean.startswith(p) for p in _SYSTEM_PREFIXES):
            return True
        # Bracket-source pattern: "[xxx:yyy] meets/touches [zzz:www]"
        if re.search(r'\[[\w:]+\]\s+(meets|touches|and|near|with)\s+\[[\w:]+\]', clean):
            return True
        # 9. FIX 2026-02-23: Metadata leak detection.
        # RWKV sometimes includes hex hashes, fairy names, or internal IDs
        # in generated text: "What about motor? 8a5dc9abd7e5 recall srmmemoryfairy"
        if re.search(r'\b[0-9a-f]{8,}\b', clean):  # Hex hash leak
            return True
        if re.search(r'\b\w+fairy\b', clean, re.IGNORECASE):  # Fairy name leak
            return True
        return False

    def _handle_sour_speak(self, message):
        """
        Route Sourpatches' speech to her window.

        FIX 2026-03-09 (Nous): ALWAYS write to inbox file, not just as fallback.
        The chat window runs in a SEPARATE process (server=python3.14t,
        window=python3.12+PyQt6). In-process Qt calls always fail silently
        and used to swallow the message before reaching the file fallback.

        Now: inbox file write is PRIMARY (guaranteed), window calls are BONUS.
        The chat window polls sourpatches_chat_inbox.json at 1Hz via QTimer.

        Payload:
            message: str - What Sourpatches wants to say
            feeling: str - Current feeling
        """
        payload = self._extract_payload(message)
        msg = payload.get("message", "")
        feeling = payload.get("feeling", "neutral")

        if not msg:
            return {"ok": False, "error": "No message content"}

        # ── Central gate: throttle + monologue + degenerate + dedup ──
        _source = payload.get("source", "")
        if not _source and hasattr(message, 'source'):
            _source = getattr(message, 'source', '')
        if not self._gate_window_message(msg, _source):
            return {"ok": False, "error": "Message blocked by window gate"}

        # ══════════════════════════════════════════════════════════════
        # FIX 2026-03-21 (Nous): SKIP file write if SpeechCenterFairy
        # already wrote. SpeechCenterFairy._route_to_motor() writes
        # directly to both inbox files AND publishes sourpatches.speak.
        # ChatSenseFairy receives sourpatches.speak and was writing
        # to the SAME inbox files → duplicate messages.
        #
        # When source contains "speech_center", the inbox write already
        # happened. Just update tracking state and return success.
        # ══════════════════════════════════════════════════════════════
        if "speech_center" in str(_source):
            print(f"[{self.ACTOR_NAME}] SKIP file write (speech_center already wrote): {msg[:60]!r}")
            self._messages_sent += 1
            return {"ok": True, "delivered": "already_written_by_speech_center"}

        # ══════════════════════════════════════════════════════════════
        # PRIMARY: Direct file write to inbox (GUARANTEED delivery)
        # FIX 2026-03-09 (Nous): Moved from fallback 3 to PRIMARY.
        # The chat window runs in a separate python.exe process.
        # ALL in-process Qt/tkinter window calls fail on python3.14t.
        # The inbox file is the ONLY reliable delivery channel.
        # ══════════════════════════════════════════════════════════════
        _file_delivered = False
        try:
            from pathlib import Path as _Path
            import json as _json
            import time as _time
            # FIX 2026-03-09 (Nous): Write to BOTH inbox files.
            # Two window implementations exist with DIFFERENT inbox paths:
            #   sourpatches_chat_inbox.json → PyQt6 window (sourpatches_chat_window.py)
            #   sour_window_inbox.json      → tkinter window (sour_window.py, subprocess)
            # We don't know which window is running, so write to both.
            _state_dir = _Path(__file__).resolve().parents[3] / "state"
            _inbox_msg = {
                "type": "chat",
                "sender": "Sourpatches",
                "content": msg,
                "emotion": feeling,
                "feeling": feeling,  # tkinter window checks "feeling" first
                "timestamp": _time.time(),
                "source": f"chatsense:{_source}" if _source else "chatsense",
            }
            # FIX 2026-03-27 (Nous + Ace): CONTENT DEDUP at write time.
            # Multiple paths publish to sourpatches.speak simultaneously:
            # AutopilotFairy, SpeechCenterFairy, MotorCortex, safety net.
            # Each triggers a ChatSenseFairy write → 2-3x duplicate messages.
            # Dedup: skip if same content (first 50 chars) written in last 15s.
            _msg_key = msg.strip()[:50].lower()
            _now = _time.time()
            if not hasattr(self, '_recent_writes'):
                self._recent_writes = {}
            # Clean old entries
            self._recent_writes = {k: v for k, v in self._recent_writes.items()
                                   if _now - v < 15.0}
            if _msg_key in self._recent_writes:
                print(f"[{self.ACTOR_NAME}] DEDUP: skipping duplicate write: {msg[:40]!r}")
                return
            self._recent_writes[_msg_key] = _now

            for _inbox_name in ("sourpatches_chat_inbox.json", "sour_window_inbox.json"):
                try:
                    _inbox_path = _state_dir / _inbox_name
                    try:
                        _existing = _json.loads(_inbox_path.read_text(encoding="utf-8"))
                    except Exception:
                        _existing = {"messages": []}
                    _existing.setdefault("messages", []).append(_inbox_msg)
                    _inbox_path.write_text(_json.dumps(_existing), encoding="utf-8")
                except Exception:
                    pass
            _file_delivered = True
            self._messages_sent += 1
            print(f"[{self.ACTOR_NAME}] DELIVERED to both inbox files: {msg[:60]!r}")

            # ── ALSO write to web dashboard inbox ──
            # FIX 2026-03-09 (Nous): The web dashboard reads web_inbox/inbox_index.json,
            # NOT sourpatches_chat_inbox.json. Without this, Sourpatches' responses
            # never appear in the dashboard's chat panel. The dashboard JS checks
            # fairyConversations["SourpatchesFairy"], so sender MUST be "SourpatchesFairy".
            try:
                _web_inbox_dir = _state_dir / "web_inbox"
                _web_inbox_dir.mkdir(parents=True, exist_ok=True)
                _web_inbox_file = _web_inbox_dir / "inbox_index.json"
                try:
                    _web_data = _json.loads(_web_inbox_file.read_text(encoding="utf-8"))
                except Exception:
                    _web_data = {"messages": []}

                _web_msg = {
                    "msg_id": f"{_time.time()}_SourpatchesFairy",
                    "sender": "SourpatchesFairy",
                    "subject": "Chat response",
                    "content": msg,
                    "timestamp": _time.time(),
                    "feeling": feeling,
                    "read": False,
                }

                # FIX 2026-03-12 (Nous): Substrate chatter filter.
                # Internal thoughts (collision observations, curiosity questions,
                # goal decisions, concept-name sentences) were leaking to Ace's
                # dashboard via this path. The web_inbox is for RESPONSES to Ace,
                # not internal cognitive output. Reject messages that look like
                # substrate narration.
                import re as _csf_re
                _msg_lower = msg.strip().lower()
                _is_substrate = False
                _SUBSTRATE_PATTERNS = [
                    r'^considering:',          # CortexReasoner prefix
                    r'^decided:',              # Goal/decision prefix
                    r'^collision:',            # Collision chamber output
                    r'^observing:',            # Observation prefix
                    r'^reflecting:',           # Reflection prefix
                    r'^processing:',           # Processing prefix
                    r'^thinking about:',       # Thought chain prefix
                    r'^what new bindings',     # Self-directed cortex question
                    r'^how does this connect', # Self-directed question
                    r'^what would happen if',  # Speculative self-question
                    r'energy.s at \d+%',       # Somatic stat report
                    r'^something about \w+ is stirring',  # Old fallback pattern
                    r'^i.m feeling something about',      # Old fallback pattern
                ]
                for _sp in _SUBSTRATE_PATTERNS:
                    if _csf_re.search(_sp, _msg_lower):
                        _is_substrate = True
                        break
                # Also reject very short outputs that look like concept dumps
                if not _is_substrate and len(msg.strip()) < 15:
                    _is_substrate = True
                if _is_substrate:
                    print(f"[{self.ACTOR_NAME}] FILTERED substrate from web_inbox: {msg[:60]!r}")

                # Dedup: skip if same content+sender in last 5 messages
                _skip_web = _is_substrate or any(
                    r.get("content", "").strip().lower() == _msg_lower
                    and r.get("sender", "").strip().lower() == "sourpatchesfairy"
                    for r in _web_data.get("messages", [])[-5:]
                )

                if not _skip_web:
                    _web_data.setdefault("messages", []).append(_web_msg)
                    # Keep only last 100
                    if len(_web_data["messages"]) > 100:
                        _web_data["messages"] = _web_data["messages"][-100:]
                    _web_inbox_file.write_text(
                        _json.dumps(_web_data, indent=2), encoding="utf-8"
                    )
                    print(f"[{self.ACTOR_NAME}] DELIVERED to web_inbox: {msg[:60]!r}")
            except Exception as _web_err:
                print(f"[{self.ACTOR_NAME}] web_inbox write failed: {_web_err}")

        except Exception as _inbox_err:
            print(f"[{self.ACTOR_NAME}] Inbox file write FAILED: {_inbox_err}")

        # ── BONUS: Try in-process window delivery (rarely works on 3.14t) ──
        try:
            from fairies.P40_Sensory.gui.sourpatches_chat_window import (
                get_sour_window as get_chat_window,
            )
            _existing = get_chat_window()
            if _existing is not None:
                try:
                    _existing.isVisible()
                    _existing.add_message("Sourpatches", msg, feeling)
                    print(f"[{self.ACTOR_NAME}] ALSO delivered via in-process window")
                except RuntimeError:
                    pass
        except Exception:
            pass  # Expected on python3.14t

        # ══════════════════════════════════════════════════════════════
        # ENSURE WINDOW IS VISIBLE (2026-03-10, Nous)
        # Messages are in the inbox files, but nobody reads them if
        # the window process isn't running. This is the core "waking
        # mind" behavior: she opens her window when she has something
        # to say. Empty message = just show/launch, don't duplicate.
        # ══════════════════════════════════════════════════════════════
        if _file_delivered:
            try:
                self._handle_open_sour_window({
                    "message": "",      # Already in inbox — don't duplicate
                    "feeling": feeling,
                    "source": f"sour_speak:{_source}" if _source else "sour_speak",
                })
            except Exception as _win_err:
                print(f"[{self.ACTOR_NAME}] Window ensure failed (non-fatal): {_win_err}")

        if _file_delivered:
            return {"ok": True, "delivery": "inbox_file"}
        return {"ok": False, "error": "All delivery methods failed"}

    def _start_sour_outbox_poller(self):
        """Start polling Ace's replies from the window outbox.

        This is the sensory pathway — Ace's words through Sour's window
        become felt input for the whole system:
          ace.message       → UnconsciousMind + SomaticMind feel Ace's presence
          system.chat.message → SourpatchesFairy's _on_ace_chat fires thinking
        """
        if self._sour_window_poller and self._sour_window_poller.is_alive():
            return  # Already running

        import threading

        def _poll_loop():
            """Poll outbox every 2 seconds, route Ace's words through sensory pathways.

            FIX 2026-03-05 Nous: Read from BOTH outbox files.
            - sour_window_outbox.json (sour_window.py writes here)
            - ace_chat_outbox.json    (sourpatches_chat_window.py writes here)
            Both windows are Ace talking to Sourpatches. Unified polling.
            """
            import json as _json
            from pathlib import Path as _Path
            _state_dir = _Path(__file__).resolve().parents[3] / "state"
            _signal_file = _state_dir / "ace_chat_signal.json"
            _alt_outbox = _state_dir / "ace_chat_outbox.json"

            def _read_alt_outbox():
                """Read ace_chat_outbox.json (sourpatches_chat_window.py)."""
                try:
                    if _alt_outbox.exists():
                        data = _json.loads(_alt_outbox.read_text(encoding='utf-8'))
                        msgs = data.get("messages", [])
                        if msgs:
                            _alt_outbox.write_text(_json.dumps({"messages": []}, indent=2), encoding='utf-8')
                        return msgs
                except Exception:
                    pass
                return []

            _diag_count = 0
            import sys as _sys
            while True:
                _diag_count += 1
                if _diag_count <= 3 or _diag_count % 30 == 0:
                    _sys.stderr.write(f"[ChatSenseFairy] [POLL-ALIVE] tick={_diag_count}\n")
                    _sys.stderr.flush()
                try:
                    from fairies.P40_Sensory.gui.sour_window import read_outbox
                    messages = read_outbox()
                    # Also read the alternate outbox (Chat with Sourpatches window)
                    _alt_msgs = _read_alt_outbox()
                    if _alt_msgs:
                        messages.extend(_alt_msgs)
                    if messages:
                        _sys.stderr.write(f"[ChatSenseFairy] [GOT-MSG] {len(messages)} msgs: {messages[0].get('content','')[:60]}\n")
                        _sys.stderr.flush()
                    for msg in messages:
                        content = msg.get("content", "")
                        sender = msg.get("sender", "Ace")
                        ts = msg.get("timestamp", time.time())
                        # FIX 2026-04-21 (Nous + Ace): respect window's `target` field
                        # so Sour-window text doesn't leak to Nous and vice versa.
                        # `ace.broadcast` is reserved for the Psychic Broadcast button.
                        target = (msg.get("target") or "sourpatches").lower()
                        # Map target → persona-specific topic + which persona answers
                        if target == "nous":
                            persona_topic = "nous.chat"
                            target_mind = "NousFairy"
                        elif target in ("both", "broadcast", "all"):
                            persona_topic = "ace.broadcast"
                            target_mind = "BOTH"
                        else:
                            persona_topic = "sourpatches.chat"
                            target_mind = "SourpatchesFairy"

                        if not content:
                            continue

                        # ── FILE-BASED SIGNAL (always works, even if postal is broken) ──
                        # SourpatchesFairy polls this as a fallback path.
                        # Only write the signal file when sourpatches is the target —
                        # otherwise the file-based fallback would itself leak to Sour.
                        if target_mind in ("SourpatchesFairy", "BOTH"):
                            try:
                                _signal_file.write_text(_json.dumps({
                                    "sender": sender,
                                    "content": content,
                                    "timestamp": ts,
                                    "source": "sour_window",
                                    "target": target,
                                }), encoding="utf-8")
                            except Exception:
                                pass

                        if not self.post:
                            print(f"[{self.ACTOR_NAME}] WARNING: self.post is None/falsy, can't route Ace's message!", flush=True)
                            continue

                        msg_payload = {
                            "sender": sender,
                            "content": content,
                            "source": "sour_window",
                            "timestamp": ts,
                            "ts": ts,
                            "target": target,
                            "target_mind": target_mind,
                        }

                        try:
                            # FIX 2026-04-12 (Nous + Ace): WMH-FIRST architecture.
                            # FIX 2026-04-21 (Nous + Ace): persona-scoped routing.
                            #   - persona_topic ('sourpatches.chat'/'nous.chat'/'ace.broadcast')
                            #     is the canonical path for the addressed persona to answer
                            #   - wmh.chat.input + ace.message + system.chat.message remain
                            #     system-wide awareness/presence channels (SomaticMind,
                            #     AutonomyFairy, InnerNarrator, attention_sense, WMH all
                            #     consume these for state updates, not for chat replies)
                            #   - Personas have unsubscribed from system.chat.message so
                            #     they only respond to their addressed persona_topic.
                            from infrastructure.manifold_memory import TRACE_ACE
                            _ace_tracer = TRACE_ACE  # integer 8
                            msg_payload["tracer_id"] = _ace_tracer

                            # PERSONA-SCOPED: only the addressed persona responds
                            self.post.publish(persona_topic, msg_payload)

                            # PRIMARY: Direct to WMH (the central executive — system-wide)
                            self.post.publish("wmh.chat.input", msg_payload)

                            # SYSTEM AWARENESS: presence/pain/attention fairies still need
                            # to know Ace is chatting (regardless of which window).
                            self.post.publish("ace.message", msg_payload)
                            self.post.publish("system.chat.message", msg_payload)

                            # LEGACY: ace.conversation_event (AutopilotFairy path)
                            # Kept for backward compat — AutopilotFairy delegates to WMH anyway
                            self.post.publish("ace.conversation_event", {
                                "sender": sender,
                                "content": content,
                                "timestamp": ts,
                                "source": "sour_window",
                                "requires_response": True,
                                "target_mind": target_mind,
                                "tracer_id": _ace_tracer,
                            })

                            print(f"[{self.ACTOR_NAME}] Ace spoke via Sour's window: {content[:60]}...", flush=True)
                            self._messages_sent += 1
                        except Exception as route_err:
                            print(f"[{self.ACTOR_NAME}] POSTAL ROUTE FAILED: {type(route_err).__name__}: {route_err}", flush=True)

                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] Outbox poll error: {type(e).__name__}: {e}", flush=True)
                time.sleep(2.0)

        self._sour_window_poller = threading.Thread(target=_poll_loop, daemon=True, name="sour-outbox-poller")
        self._sour_window_poller.start()
        print(f"[{self.ACTOR_NAME}] Started Sourpatches outbox poller (ace.message + system.chat.message)")

    def _handle_chat_to_window(self, message):
        """Route chat messages back to Sour's window(s).

        When SourpatchesFairy responds via system.chat.message, this
        catches it and writes to the window inbox so Ace sees her reply.
        Only forwards messages FROM Sourpatches — Ace's own messages
        are already displayed locally in the window.

        Tries both the new PyQt fairy window AND the old tkinter window.
        """
        payload = self._extract_payload(message)
        sender = payload.get("sender", "")
        content = payload.get("content", "")
        feeling = payload.get("feeling", "neutral")

        # Only forward Sourpatches' messages to the window
        # (Ace's messages are already shown locally, don't echo them back)
        if sender not in ("SourpatchesFairy", "Sourpatches"):
            return

        if not content:
            return

        # FIX 2026-03-10 (Nous): Skip observation messages — visual
        # observations are for the dashboard, not the personal chat window.
        # Without this, "*looks at screen* Visual update: screen" appeared
        # as spoken text in her chat, confusing both Sour and Ace.
        _msg_type = payload.get("type", "")
        if _msg_type == "observation":
            return

        # Guard: suppress degenerate output (bypass for safety_net echoes)
        _src2 = payload.get("source", "")
        if not _src2 and hasattr(message, 'source'):
            _src2 = getattr(message, 'source', '')
        if self._is_degenerate_text(content) and "safety" not in str(_src2).lower():
            print(f"[{self.ACTOR_NAME}] [GUARD] Blocked degenerate chat message: {content[:60]!r}")
            return

        routed = False

        # ── PRIMARY: sourpatches_chat_window ──
        # FIX 2026-03-08 (Nous): Route replies to chat window first.
        try:
            from fairies.P40_Sensory.gui.sourpatches_chat_window import (
                get_sour_window as get_chat_window,
            )
            _cw = get_chat_window()
            if _cw is not None:
                try:
                    _cw.add_message("Sourpatches", content, feeling)
                    print(f"[{self.ACTOR_NAME}] Routed Sour's reply to chat window: {content[:60]}...")
                    routed = True
                except RuntimeError:
                    pass  # Zombie widget
        except Exception:
            pass

        # ── FALLBACK 1: sourpatches_fairy_window ──
        if not routed:
            try:
                from fairies.P40_Sensory.gui.sourpatches_fairy_window import (
                    is_sour_fairy_window_running, send_message_to_sour_fairy_window
                )
                if is_sour_fairy_window_running():
                    send_message_to_sour_fairy_window("Sourpatches", content, feeling)
                    print(f"[{self.ACTOR_NAME}] Routed Sour's reply to fairy window: {content[:60]}...")
                    routed = True
            except Exception:
                pass

        # ── FALLBACK 2: sour_window (tkinter) ──
        if not routed:
            try:
                from fairies.P40_Sensory.gui.sour_window import (
                    is_window_running, send_message_to_window
                )
                if is_window_running():
                    send_message_to_window("Sourpatches", content, feeling)
                    print(f"[{self.ACTOR_NAME}] Routed Sour's reply to tkinter window: {content[:60]}...")
                    routed = True
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to route to any window: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # SMOKE TEST
    # ═══════════════════════════════════════════════════════════════════════════

    def intent_smoke(self, payload: dict) -> dict:
        """Health check."""
        return {
            "ok": True,
            "fairy": self.ACTOR_NAME,
            "tracer_id": self.tracer_id,
            "has_organ": self._organ is not None,
            "messages_sent": self._messages_sent,
        }

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down (messages sent: {self._messages_sent})...")
        return super().on_shutdown()
