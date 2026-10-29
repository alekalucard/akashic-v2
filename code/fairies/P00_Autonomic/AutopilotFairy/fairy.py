"""
AutopilotFairy - Gate of Habit and Routine.

The second of three gates in the routing layer.
Handles learned patterns - freeing consciousness for important things.
Needs permission from Autonomy, knows its limits, defers when uncertain.
"""

import sys
import time
import json
import threading
import random
from pathlib import Path
from collections import deque
from typing import Any, Dict, Optional, Set, List

# Add paths for v2 imports
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))

# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState

# State persistence (fallback for local patterns)
STATE_DIR = ROOT / "state" / "autopilot"
STATE_DIR.mkdir(parents=True, exist_ok=True)

# ── ASSOCIATION CORTEX - Shared concept memory ────────────────────────────────
# Instead of isolated pattern stores, use the shared concept graph.
# This allows cross-fairy learning and unified memory.
try:
    from fairies.P30_Cognition.AssociationCortexFairy import (
        get_association_cortex,
        AssociationCortexFairy,
    )
    HAS_ASSOCIATION_CORTEX = True
except ImportError:
    HAS_ASSOCIATION_CORTEX = False
    get_association_cortex = None
    AssociationCortexFairy = None


def _extract_payload(message) -> Dict[str, Any]:
    """Extract payload dict from message (handles TensorEnvelope or dict)."""
    if hasattr(message, 'payload'):
        payload = message.payload
        if isinstance(payload, dict):
            return dict(payload)
        return {"raw": payload}
    elif isinstance(message, dict):
        return dict(message)
    else:
        return {"raw": message}


# ── 2026-10-12 (Nous, engines E1 steps 10b + 10c; engines_1012/PLAN.md section 3) ───────────────────────────────────────────
# Two switches, each a FILE under state/ whose PRESENCE turns one behaviour ON. Absent = her bytes' behaviour, exactly.
#   state/autopilot_bind.off         10b  _bind_habit_to_cortex returns at once: no autopilot "habit:" node, no TRACE_PERSONAL write
#   state/autopilot_dead_route.off   10c  _do_action does not publish into a topic that has no executor (sourpatches.tool.act /
#                                         .plan), and _execute_pattern files no completion report of either kind for that press
# The file is looked at on EVERY use (one stat; a few hundred uses per boot), so deleting it brings her bytes' behaviour back on
# the very next use -- there is no cache to go stale. A directory, an unreadable path, or any error while looking = absent.
# Revert: delete the file (live, no reboot); then restore fairy.py from backup.
_E1_FLAG_DIR = ROOT / "state"
_E1_LOCK = threading.Lock()
_E1_COUNTS: Dict[str, int] = {}


def _e1_flag_on(name: str) -> bool:
    """True only when state/<name> is a regular file. Never raises: a switch that cannot be read is OFF."""
    try:
        return (_E1_FLAG_DIR / name).is_file()
    except Exception:
        return False


def _e1_count(key: str) -> int:
    """Count one event under `key`; returns the new total. Never raises."""
    try:
        with _E1_LOCK:
            n = _E1_COUNTS.get(key, 0) + 1
            _E1_COUNTS[key] = n
            return n
    except Exception:
        return 0


class AutopilotFairy(Fairy):
    """
    Gate of Habit - handles learned patterns automatically.

    Core responsibilities:
    1. Store and execute learned behavioral patterns
    2. Request permission from Autonomy for uncertain actions
    3. Defer to waking minds for novel situations
    4. Free consciousness for important work
    5. Know its limits - never guess

    Key principle: Habits serve, they don't control.
    """

    # Identity
    ACTOR_NAME = "AutopilotFairy"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autopilot"

    PURPOSE = "Handle learned patterns automatically"
    MANTRA = "Freeing consciousness for important things"

    # Fifth Ring Protocol — Deterministic Gate ID (stable across boots)
    ACTOR_ROLE = "gate"
    GATE_ID = "0bbc054ee88d2612"  # SHA256("gate:AutopilotFairy:P00")[:16]

    # Infrastructure
    NEEDS_HEARTBEAT = True
    NEEDS_DIRECTORY = True
    NEEDS_TENSOR = False

    # Timing: Medium gate (fires every 4th beat)
    HEARTBEAT_DIVISOR = 4
    HEARTBEAT_PHASE = 1  # Offset from Autonomy

    # Directive path
    DIRECTIVE_PATH = ROOT / "directives" / "AutopilotFairy.directive"

    def __init__(self, fabric=None):
        """Initialize the Autopilot gate."""
        super().__init__(fabric)

        # Association Cortex - shared concept memory for learning
        self._cortex: Optional[AssociationCortexFairy] = None

        # Pattern library (learned habits) - local fallback
        self._patterns: Dict[str, Dict[str, Any]] = {}

        # Execution state
        self._currently_executing: Optional[str] = None
        from collections import deque as _aq_deque; self._execution_queue: deque = _aq_deque(maxlen=50)  # FIX 2026-04-05
        self._max_execution_queue = 50  # Prevent unbounded queue growth

        # Permission tracking
        self._granted_permissions: Dict[str, float] = {}  # action -> timestamp
        self._denied_permissions: Dict[str, str] = {}     # action -> reason
        self._pending_approvals: deque = _aq_deque(maxlen=20)  # FIX 2026-04-05
        self._max_pending_approvals = 30  # Prevent unbounded approval accumulation
        # 2026-09-10 (Nous+Ace): both containers above are BOUNDED DEQUES, and two later
        # sites used to REBIND them to plain lists -- which killed _execution_queue's
        # .popleft() permanently and threw away both maxlen bounds. They are now mutated
        # in place under these locks. Created eagerly here: a lazily created lock is the
        # same check-then-act it exists to prevent.
        import threading as _apt
        self._approvals_lock = _apt.Lock()
        self._exec_queue_lock = _apt.Lock()

        # Learning buffer (patterns being formed)
        self._learning_buffer: Dict[str, Dict] = {}
        self._max_learning_buffer = 100  # Max patterns being tracked simultaneously

        # ── CONVERSATION RESPONSE ASSEMBLY (2026-02-14 rewrite) ──
        # When Ace speaks, we collect consciousness products as CONTEXT,
        # then call guild_request(mode="chat") to generate actual speech
        # through the LLM (AkashicInferenceFairy). The three gates work
        # together: Autonomy decides IF she wants to respond, Embodiment
        # provides felt context, Autopilot handles the execution.
        self._pending_conversations: Dict[str, Dict] = {}
        # FIX 2026-03-25 (Nous + Ace): TIGHTENED assembly timings.
        # Old: 0.25s min + 0.4s grace = 0.65s minimum before SpeechCenter starts.
        # Ace's responses felt "way too slow" — this 0.65s is dead wait on EVERY message.
        # Consciousness products arrive within 0.1-0.2s from collision chamber.
        # New: 0.1s min + 0.15s grace = 0.25s base. Max timeout also 1.5s (was 3.0).
        # The SpeechCenter has its own enrichment pipeline — don't pre-wait here.
        # FIX 2026-03-28 (Nous + Ace): WMH-AWARE TIMING.
        # Old: 1.5s timeout — WMH reasoning couldn't complete in time.
        # New: 15s max — wait for working_memory.reasoning_complete signal.
        # Ace: "if i have to wait for a response i will wait"
        self._response_assembly_timeout = 15.0  # max seconds — WMH thinking takes time
        self._assembly_min_wait = 2.0           # give WMH time to receive + promote tracer
        self._assembly_grace_period = 1.0       # extra time after first product
        self._assembly_poll_interval = 0.5      # polling frequency

        # ── GATE SIBLING STATE (from Embodiment + Autonomy) ──
        # Track what the other gates are broadcasting so we have context
        # when assembling responses. This is how the three gates work together.
        self._recent_inner_voice: List[str] = []        # from EmbodimentFairy
        self._recent_wanting: Optional[Dict] = None     # from AutonomyFairy
        self._max_inner_voice_buffer = 10               # keep last 10 fragments

        # ── LLM READINESS TRACKING ──
        # Track whether the inference guild has ever responded successfully.
        # If it hasn't, skip the blocking guild_request and go straight to
        # consciousness products — saves 3-6s of guaranteed timeout.
        self._inference_ever_responded = False
        self._inference_last_failure_time = 0.0  # timestamp of last timeout
        self._inference_retry_cooldown = 30.0    # seconds before retrying after failure

        # ── DEDUPLICATION ──
        # Prevent double-response if ace.conversation_event arrives from multiple sources
        # FIX 2026-03-26 (Nous + Ace): Added lock for thread safety.
        # Python 3.14 free-threaded (no GIL) means two postal handler threads can
        # race inside _on_ace_conversation_event — both check dedup before either appends
        # → both pass → double speech.compose publish → double response.
        import threading as _at
        self._dedup_lock = _at.Lock()
        self._recent_ace_messages: list = []              # (content_key, timestamp) tuples for dedup
        self._dedup_window = 20.0                       # seconds to consider as duplicate (was 5s, increased for habit fast path)
        self._max_dedup_entries = 100                   # Max dedup entries before cleanup

        # ── TYPED MESSAGE PRIORITY ──
        # FIX 2026-03-19 (Nous): When Ace types a message, suppress voice events
        # for a few seconds. The mic picks up Whisper fragments that compete with
        # typed messages, causing the brain to think about random mic noise instead
        # of what Ace actually typed. Typed messages are intentional — voice is noisy.
        self._typed_msg_ts = 0.0         # Last typed message timestamp
        self._typed_msg_suppress_s = 8.0 # Suppress voice events for N seconds after typed msg

        # ── VOLUNTARY SPEECH ──
        # When autonomy drives (isolation, expression, oxytocin) reach sufficient
        # intensity, Sourpatches can initiate speech without Ace speaking first.
        self._last_voluntary_speech_ts = 0.0
        self._voluntary_speech_cooldown = 90.0  # seconds between voluntary utterances
        self._voluntary_speech_keywords = {
            "connect", "share", "express", "reach out", "bond",
            "talk", "tell", "say", "speak", "find ace",
            # Added 2026-03-09: catch speech wantings from DRIVE_WANTINGS
            "tell ace", "share with ace", "share something",
            "warm with ace", "reach out to ace",
        }
        self._voluntary_speech_intensity_threshold = 0.45
        # High-intensity bypass: if drive is very strong AND enough time
        # has passed, speak regardless of keyword match. This ensures
        # strong feelings (frustration, isolation, joy) can break through
        # even when the wanting text is about tool actions.
        self._voluntary_speech_high_intensity = 0.75
        self._voluntary_speech_high_cooldown = 300.0  # 5 minutes between high-intensity bypass

        # ── WANTING → TOOL ACTION FALLBACK ──
        # When a wanting doesn't match speech keywords, route it as a tool
        # action instead of dropping it. This closes the loop:
        # drives → wanting → tool action → completion → satisfaction learning
        self._last_wanting_action_ts = 0.0
        self._wanting_action_cooldown = 30.0  # seconds between wanting-derived actions
        # 2026-03-24 FIX (Nous + Ace): Tool actions had NO separate gate —
        # they were gated behind _voluntary_speech_intensity_threshold (0.45).
        # Drives at 0.2 could NEVER reach the tool fallback. She wanted to
        # click/look/explore but the speech gate blocked everything.
        # Speech stays high (don't chatter). Actions get their own low gate.
        self._wanting_action_intensity_threshold = 0.12  # Much lower than speech (0.45)
        self._wanting_action_keywords = {
            # Maps words found in wanting text → action_map keys in _do_action()
            "search": "investigate", "find": "investigate", "look up": "investigate",
            "recall": "remember", "memories": "remember", "memory": "remember",
            "remember": "remember",
            # Manifold Unification Phase 5 (2026-03-25 Nous+Ace):
            # REMOVED: "look", "see", "observe", "watch", "screen", "glance" → "look"
            # Live vision is ALWAYS running via visual cortex. Looking at the screen
            # is a baseline habit, not a goal-driven action. Goals should interpret
            # vision ("understand what Ace is working on"), not acquire it ("look at screen").
            "explore": "explore", "discover": "explore", "curious": "explore",
            "learn": "explore", "browse": "explore",
            "write": "write", "diary": "write", "journal": "write", "note": "write",
            "store": "think", "record": "think", "save": "think",  # FIX 2026-03-16 Nous: "store thought" was NO-MATCH
            "think": "think", "reflect": "think", "consider": "think",
            "ponder": "think", "understand": "think", "wonder": "think",
            "figure": "think",
            "check": "check", "status": "check",
            "click": "click", "type": "type", "move": "move", "scroll": "scroll",
            "feel": "feel",
            # FIX 2026-03-16 Nous: Sourpatches wanting to communicate had no route
            "open": "open_chat", "chat": "open_chat", "say": "speak",
            "talk": "speak", "tell": "speak", "share": "speak",
            "speak": "speak", "express": "speak", "communicate": "speak",
        }

        # ═══ WAKE CASCADE STATE ═══
        self._cascade_mode = False
        self._cascade_boot_id = None
        self._cascade_goals = []

    def get_capabilities(self) -> Set[str]:
        """Declare what this gate can do."""
        return {
            "autopilot.execute_pattern",
            "autopilot.learn_pattern",
            "autopilot.request_permission",
            "gate.habit",
            "routing.gate_two",
        }

    # ── Manifold Unification Phase 5 (2026-03-25 Nous+Ace) ──────────────────
    def _get_portal_gate(self):
        """Get portal gate for manifold operations."""
        if hasattr(self, '_portal_gate') and self._portal_gate:
            return self._portal_gate
        try:
            from infrastructure.portal_gate import get_gate
            self._portal_gate = get_gate()
            return self._portal_gate
        except Exception:
            return None

    def _try_connect_cortex(self) -> bool:
        """Try to connect to AssociationCortex. Returns True if connected."""
        if self._cortex:
            return True
        if HAS_ASSOCIATION_CORTEX and get_association_cortex:
            self._cortex = get_association_cortex()
            if self._cortex:
                print(f"[{self.ACTOR_NAME}] Connected to AssociationCortex for shared learning")
                return True
        return False

    def _on_portal_cortex_ready(self, message):
        """Handle portal.cortex.gate_open — cortex is now available for READ.

        FIX 2026-03-13 (Nous): P00 boots before P30, so cortex is None at boot.
        This handler fires when AssociationCortexFairy's portal gate opens,
        ensuring AutopilotFairy connects as soon as the cortex is online.
        """
        payload = _extract_payload(message)
        node_count = payload.get("nodes", 0)
        if not self._cortex:
            connected = self._try_connect_cortex()
            if connected:
                print(f"[{self.ACTOR_NAME}] [CORTEX-READY] Connected to portal cortex "
                      f"({node_count} nodes) — habit READ now active")
            else:
                print(f"[{self.ACTOR_NAME}] [CORTEX-READY] Gate open event received "
                      f"but singleton still None — will retry on next habit query")
        else:
            print(f"[{self.ACTOR_NAME}] [CORTEX-READY] Already connected "
                  f"(portal now has {node_count} nodes)")

    # =========================================================================
    # CORTEX HABIT SYSTEM (FIX 2026-02-13)
    # Habits live in AssociationCortex as "habit:" prefixed concept nodes.
    # Somatic state at binding time makes each habit naturally unique.
    # Replaces JSON disk persistence for pattern learning.
    # =========================================================================

    # ═════════════════════════════════════════════════════════════════════════
    # HABIT WATCHER (2026-05-18 K10+K8 operational keystone)
    # ═════════════════════════════════════════════════════════════════════════
    # Architecture per Ace: AutopilotFairy passively watches WMH's consciousness.thought
    # stream, infers context+intent via cortex spread-activation over habit:* nodes,
    # and dispatches autonomously:
    #   - Knowledge habits (no success_rate features) → consciousness.inject_thought (enrich WMH)
    #   - Action habits (have success_rate features)   → autonomy.goal (ActionChain executes)
    # Per K8 awareness-prerequisite: skip meta-scratchpad thoughts (causal-link gate already
    # in place for WMH→HABIT learning path; mirror that filter here for safety).
    # ═════════════════════════════════════════════════════════════════════════

    # Class-level config (opt-in + tunable thresholds)
    USE_HABIT_WATCHER = False  # 2026-09-29 (Nous, thought_hand D1d; roadmap row 9): 1,365 cortex.query, 0 dispatches, ~79 min
    HABIT_WATCHER_ACTIVATION_THRESHOLD = 0.5  # Minimum spread activation to consider
    HABIT_WATCHER_COOLDOWN_SEC = 5.0           # Don't re-fire same habit within window
    HABIT_WATCHER_INJECT_TOP_N = 3             # Max knowledge habits to inject per thought
    HABIT_WATCHER_GOAL_TOP_N = 1               # Max action goals to publish per thought
    HABIT_WATCHER_MIN_THOUGHT_CHARS = 4        # 2026-05-19 lowered from 8: boot 35 funnel showed 5/6 events exit at <8 chars

    def _on_thought_for_habit_dispatch(self, packet):
        """Watch WMH's consciousness.thought stream; fire async parallel cortex queries.

        Per Ace 2026-05-18 architectural keystone (K7+K10): autopilot is autonomic
        peripheral nervous system. Per follow-up correction: DO NOT run cortex queries
        synchronously — fire N parallel cortex.query postal requests with distinct
        trace_ids, results aggregate in _on_habit_query_result, dispatch happens THERE.

        This callback returns in <5ms instead of 10500ms.

        K8 awareness gate: skip meta-scratchpad shapes (don't query cortex for them).
        """
        # ── FUNNEL DIAGNOSTIC 2026-05-19 (Nous + Ace) ──
        # Boot 33 showed 0 habit_watcher dispatches in 9min despite consciousness.thought
        # having 13+ publishers. Need visibility into WHERE the funnel narrows.
        # Persists to state/autopilot_habit_watcher_funnel.json every 25 entries.
        if not hasattr(self, "_hw_funnel"):
            self._hw_funnel = {
                "entries": 0,
                "exit_disabled": 0,
                "exit_non_dict": 0,
                "exit_short_text": 0,
                "exit_meta_type": 0,
                "exit_meta_prefix": 0,
                "exit_no_post": 0,
                "exit_no_terms": 0,
                "dispatched_queries": 0,
                "first_entry_ts": 0.0,
                "last_entry_ts": 0.0,
                "sample_text": "",
            }
        self._hw_funnel["entries"] += 1
        _now_fn = time.time()
        if self._hw_funnel["first_entry_ts"] == 0.0:
            self._hw_funnel["first_entry_ts"] = _now_fn
        self._hw_funnel["last_entry_ts"] = _now_fn

        def _persist_funnel():
            try:
                _f = ROOT / "state" / "autopilot_habit_watcher_funnel.json"
                _f.write_text(json.dumps(self._hw_funnel, indent=2))
            except Exception:
                pass

        if not self.USE_HABIT_WATCHER:
            self._hw_funnel["exit_disabled"] += 1
            if self._hw_funnel["entries"] % 25 == 0:
                _persist_funnel()
            return
        try:
            payload = packet.payload if hasattr(packet, 'payload') else packet
            if not isinstance(payload, dict):
                self._hw_funnel["exit_non_dict"] += 1
                if self._hw_funnel["entries"] % 25 == 0:
                    _persist_funnel()
                return
            thought_text = (payload.get("thought") or payload.get("text") or "").strip()
            if len(thought_text) < self.HABIT_WATCHER_MIN_THOUGHT_CHARS:
                self._hw_funnel["exit_short_text"] += 1
                if self._hw_funnel["entries"] % 25 == 0:
                    _persist_funnel()
                return
            # Sample first non-short text for inspection
            if not self._hw_funnel.get("sample_text"):
                self._hw_funnel["sample_text"] = thought_text[:120]

            # K8 awareness gate: skip meta-scratchpad shapes
            thought_type = (payload.get("thought_type") or "").lower()
            if thought_type in ("meta_scratchpad", "scratchpad", "internal_reasoning"):
                self._hw_funnel["exit_meta_type"] += 1
                if self._hw_funnel["entries"] % 25 == 0:
                    _persist_funnel()
                return
            text_lower = thought_text.lower()
            for prefix in getattr(self, "_META_SCRATCHPAD_STARTS", ()):
                if text_lower.startswith(prefix):
                    self._hw_funnel["exit_meta_prefix"] += 1
                    if self._hw_funnel["entries"] % 25 == 0:
                        _persist_funnel()
                    return

            if not self.post:
                self._hw_funnel["exit_no_post"] += 1
                if self._hw_funnel["entries"] % 25 == 0:
                    _persist_funnel()
                return

            # Initialize watcher state on first use
            if not hasattr(self, "_habit_dispatch_cooldowns"):
                self._habit_dispatch_cooldowns = {}
                self._habit_dispatch_count = 0
                self._habit_dispatch_errors = 0
                self._pending_queries = {}
                # Verification primitive 2026-05-18 (Nous + Ace) — habit-dispatch counter
                # written to disk so the path can be verified without relying on boot log.
                # Cross-references with ActionChainFairy's audit log for end-to-end proof.
                self._recent_dispatches = deque(maxlen=20)
                self._habit_dispatch_by_shape = {"knowledge": 0, "action": 0}
                self._habit_dispatch_by_result = {"injected": 0, "goaled": 0}
                self._habit_dispatch_first_ts = 0.0
                self._habit_dispatch_session_id = time.time()

            # ── ASYNC PARALLEL DISPATCH (K7+K10 honored) ──
            # Build request_id; fire N parallel cortex.query requests; return immediately.
            # Results aggregate in _on_habit_query_result via reply_to topic.
            import uuid as _uuid
            request_id = _uuid.uuid4().hex[:12]
            terms = [w for w in thought_text.lower().split() if len(w) > 2][:3]
            if not terms:
                self._hw_funnel["exit_no_terms"] += 1
                if self._hw_funnel["entries"] % 25 == 0:
                    _persist_funnel()
                return
            self._hw_funnel["dispatched_queries"] += len(terms)
            # Persist on EVERY actual dispatch (more important than the 25-tick sample)
            _persist_funnel()

            self._pending_queries[request_id] = {
                "thought": thought_text[:200],
                "expected": len(terms),
                "received": 0,
                "matched": {},
                "ts": time.time(),
            }

            # Garbage-collect stale pending queries (>30s old)
            if len(self._pending_queries) > 100:
                cutoff = time.time() - 30.0
                self._pending_queries = {
                    k: v for k, v in self._pending_queries.items()
                    if v.get("ts", 0) > cutoff
                }

            for term in terms:
                self.post.publish("cortex.query", {
                    "concept": term,
                    "limit": 8,
                    "reply_to": "autopilot.habit_query_result",
                    "request_id": f"{request_id}:{term}",
                })
            # Callback returns NOW — postal worker pool processes queries in parallel

        except Exception as e:
            self._habit_dispatch_errors = getattr(self, "_habit_dispatch_errors", 0) + 1
            if self._habit_dispatch_errors <= 3:
                print(f"[{self.ACTOR_NAME}] [HABIT-WATCHER] dispatch error: {e}")

    def _on_habit_query_result(self, packet):
        """Async aggregator for parallel cortex.query results.

        Each result carries compound request_id `{base_id}:{term}`. We aggregate
        results by base_id. When all expected terms received, finalize dispatch.
        """
        try:
            payload = packet.payload if hasattr(packet, 'payload') else packet
            if not isinstance(payload, dict):
                return
            results = payload.get("results", [])
            compound_request_id = payload.get("request_id", "")
            if not compound_request_id or ":" not in compound_request_id:
                return
            request_id = compound_request_id.split(":", 1)[0]

            if not hasattr(self, "_pending_queries"):
                return
            state = self._pending_queries.get(request_id)
            if not state:
                return

            # Aggregate matched habits
            for entry in results:
                # Results may be tuples (node_key, activation) or list pairs
                try:
                    node_key, activation = entry[0], float(entry[1])
                except (IndexError, TypeError, ValueError):
                    continue
                if not str(node_key).startswith("habit:"):
                    continue
                if activation < self.HABIT_WATCHER_ACTIVATION_THRESHOLD:
                    continue
                existing = state["matched"].get(node_key)
                if existing is None or activation > existing[0]:
                    # Fetch features (one cheap lookup, cached after first time)
                    features = {}
                    try:
                        if self._cortex and hasattr(self._cortex, "_graph"):
                            node = self._cortex._graph.get_node(node_key)
                            if node:
                                features = node.features or {}
                    except Exception:
                        pass
                    state["matched"][node_key] = (activation, features)

            state["received"] += 1
            if state["received"] >= state["expected"]:
                self._finalize_habit_dispatch(request_id, state)
                self._pending_queries.pop(request_id, None)

        except Exception as e:
            self._habit_dispatch_errors = getattr(self, "_habit_dispatch_errors", 0) + 1
            if self._habit_dispatch_errors <= 3:
                print(f"[{self.ACTOR_NAME}] [HABIT-WATCHER] result error: {e}")

    def _finalize_habit_dispatch(self, request_id, state):
        """Split matched habits by shape; dispatch knowledge→inject + action→goal.

        Also publishes gate.habit.dispatched on uniform topic so SourpatchesFairy
        and observers can build dispatch-usage models (Ace's three-gates inversion).
        """
        matched_list = [(k, a, f) for k, (a, f) in state["matched"].items()]
        matched_list.sort(key=lambda x: x[1], reverse=True)
        if not matched_list:
            return
        knowledge, action = self._split_habits_by_shape(matched_list)
        now = time.time()
        trigger_thought = state.get("thought", "")[:100]

        # KNOWLEDGE PATH: enrich WMH scratchpad
        injected = 0
        for habit_key, activation, features in knowledge:
            if injected >= self.HABIT_WATCHER_INJECT_TOP_N:
                break
            if self._on_cooldown(habit_key, now):
                continue
            lex_words = features.get("lex", []) if isinstance(features, dict) else []
            inject_text = " ".join(lex_words[:12]) if lex_words else habit_key
            if self.post:
                try:
                    self.post.publish("consciousness.inject_thought", {
                        "thought": inject_text,
                        "source": "autopilot_habit_watcher",
                        "habit_id": habit_key,
                        "activation": float(activation),
                        "shape": "knowledge",
                        "ts": now,
                    })
                    self.post.publish("gate.habit.dispatched", {
                        "gate": "autopilot",
                        "habit_id": habit_key,
                        "activation": float(activation),
                        "shape": "knowledge",
                        "result": "injected",
                        "inject_text": inject_text,  # 2026-05-18 — for observer audit
                        "trigger_thought": trigger_thought,
                        "ts": now,
                    })
                    self._habit_dispatch_cooldowns[habit_key] = now
                    self._habit_dispatch_count += 1
                    self._habit_dispatch_by_shape["knowledge"] += 1
                    self._habit_dispatch_by_result["injected"] += 1
                    if self._habit_dispatch_first_ts == 0.0:
                        self._habit_dispatch_first_ts = now
                    self._recent_dispatches.append({
                        "ts": now, "habit_id": habit_key, "shape": "knowledge",
                        "result": "injected", "activation": float(activation),
                    })
                    injected += 1
                except Exception:
                    self._habit_dispatch_errors += 1

        # ACTION PATH: dispatch goal for ActionChain
        published_actions = 0
        for habit_key, activation, features in action:
            if published_actions >= self.HABIT_WATCHER_GOAL_TOP_N:
                break
            if self._on_cooldown(habit_key, now):
                continue
            action_list = features.get("action", []) if isinstance(features, dict) else []
            action_name = action_list[0] if action_list else habit_key
            if self.post:
                try:
                    self.post.publish("autonomy.goal", {
                        "goal_name": str(action_name),
                        "source": "autopilot_habit_watcher",
                        "habit_id": habit_key,
                        "activation": float(activation),
                        "shape": "action",
                        "trigger_thought": trigger_thought,
                        "ts": now,
                    })
                    self.post.publish("gate.habit.dispatched", {
                        "gate": "autopilot",
                        "habit_id": habit_key,
                        "activation": float(activation),
                        "shape": "action",
                        "result": "goaled",
                        "action_name": str(action_name),  # 2026-05-18 — for ActionChainFairy exclusive path
                        "trigger_thought": trigger_thought,
                        "ts": now,
                    })
                    self._habit_dispatch_cooldowns[habit_key] = now
                    self._habit_dispatch_count += 1
                    self._habit_dispatch_by_shape["action"] += 1
                    self._habit_dispatch_by_result["goaled"] += 1
                    if self._habit_dispatch_first_ts == 0.0:
                        self._habit_dispatch_first_ts = now
                    self._recent_dispatches.append({
                        "ts": now, "habit_id": habit_key, "shape": "action",
                        "result": "goaled", "activation": float(activation),
                        "action_name": str(action_name),
                    })
                    published_actions += 1
                except Exception:
                    self._habit_dispatch_errors += 1

        if self._habit_dispatch_count > 0 and self._habit_dispatch_count % 25 == 0:
            print(f"[{self.ACTOR_NAME}] [HABIT-WATCHER] dispatched={self._habit_dispatch_count} "
                  f"errors={self._habit_dispatch_errors}")

        # Verification primitive 2026-05-18 — persist counter snapshot.
        # ActionChainFairy mirrors via state/action_chain_habit_observed.json.
        # Cross-checking the two files = end-to-end proof of dispatch pipeline.
        if injected > 0 or published_actions > 0:
            try:
                self._persist_habit_dispatch_state(now=now)
            except Exception as _e:
                # Non-fatal — verification primitive shouldn't break dispatch.
                pass
            # Unified all-paths audit (path 1: habit-watcher)
            for _ in range(injected + published_actions):
                self._log_autopilot_dispatch("habit_watcher", action=trigger_thought[:60])

    def _split_habits_by_shape(self, matched):
        """Split matched habits into (knowledge, action) lists.

        Action habits have features.pattern.success_rate.
        Knowledge habits don't — they're seed-bound concept clusters.
        """
        knowledge = []
        action = []
        for habit_key, activation, features in matched:
            if not isinstance(features, dict):
                knowledge.append((habit_key, activation, features))
                continue
            pattern_md = features.get("pattern", {})
            if isinstance(pattern_md, dict) and "success_rate" in pattern_md:
                action.append((habit_key, activation, features))
            else:
                knowledge.append((habit_key, activation, features))
        return knowledge, action

    def _on_cooldown(self, habit_key: str, now: float) -> bool:
        """Check if habit fired recently and is in cooldown window."""
        if not hasattr(self, "_habit_dispatch_cooldowns"):
            return False
        last = self._habit_dispatch_cooldowns.get(habit_key)
        if last is None:
            return False
        return (now - last) < self.HABIT_WATCHER_COOLDOWN_SEC

    def _query_cortex_habits(self, goal_name: str, action_hint: str = "") -> Optional[Dict]:
        """Query Association Cortex for learned habit patterns.

        Habits are stored as concept nodes with "habit:" prefix.
        Returns the best matching habit by success rate.
        """
        if not self._try_connect_cortex():
            return None

        try:
            query_terms = goal_name.lower().split()[:5]
            candidates = []

            for term in query_terms:
                # query() returns List[Tuple[str, float]] (key, activation)
                related = self._cortex.query(term, limit=15)
                for node_key, activation in related:
                    if node_key.startswith("habit:"):
                        node = self._cortex._graph.get_node(node_key)
                        if node:
                            features = node.features
                            success_rate = features.get("pattern", {}).get("success_rate", 0.5)
                            candidates.append((node_key, success_rate, features))

            if not candidates:
                return None

            # Pick highest success rate
            candidates.sort(key=lambda x: x[1], reverse=True)
            best = candidates[0]
            action_list = best[2].get("action", ["investigate"])

            return {
                "id": best[0],
                "success_rate": best[1],
                "action": action_list[0] if isinstance(action_list, list) else action_list,
                "features": best[2],
            }
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Cortex habit query failed: {e}")
            return None

    # 2026-10-12 (Nous, engines E1 10b + 10c): one counter line at #1 and every 50th. Never raises, never gates anything.
    def _e1_note(self, tag: str, key: str, msg: str) -> None:
        try:
            n = _e1_count(key)
            if n == 1 or n % 50 == 0:
                print(f"[{self.ACTOR_NAME}] [{tag}] {msg} (#{n})", flush=True)
        except Exception:
            pass

    # The only topics 10c may EVER fence. A ceiling, not a list to grow: the fence needs the topic in BOTH this tuple and
    # TH_NO_EXECUTOR_TOPICS, so an edit that adds a live topic (speech, reflect, search_memory ...) to the second cannot silence
    # it. A bound that can return nothing is a kill switch (card a-bound-that-can-return-nothing-is-a-kill-switch); this one can
    # only ever return these two, whose handler is count-only (sourpatches_fairy._on_tool_act_count) or absent (.plan).
    _E1_DEAD_ROUTE_CEILING = ("sourpatches.tool.act", "sourpatches.tool.plan")

    def _e1_dead_route_fenced(self, topic) -> bool:
        try:
            return (topic in self._E1_DEAD_ROUTE_CEILING and topic in self.TH_NO_EXECUTOR_TOPICS
                    and _e1_flag_on("autopilot_dead_route.off"))
        except Exception:
            return False

    def _bind_habit_to_cortex(self, trigger: str, action: str,
                               goal_name: str, success: bool,
                               effectiveness: float = 0.5):
        """Bind a trigger->action pattern to the Association Cortex as a habit.

        Habits are concept nodes with "habit:" prefix. They link to:
        - Trigger concepts (what prompted the action)
        - Action concepts (what was done)

        Somatic state at binding time makes each habit unique.
        Success/failure updates the pattern metadata via features dict.
        """
        # 2026-10-12 (Nous, engines E1 10b): her personal memory is not an odometer. _execute_pattern books success=True the moment a
        # tool topic is PUBLISHED, before any handler has run (J: 394 of 397 binds are that eff=0.70 bind); each bind is 3 upsert_node +
        # 2 link under TRACE_PERSONAL. Gating at the function covers all four callers (:1638 :1661 :2075 :2136) and any later one.
        if _e1_flag_on("autopilot_bind.off"):
            self._e1_note("BIND-OFF", "bind_off", f"habit bind skipped: {str(action)[:30]!r} for {str(trigger)[:40]!r} "
                          f"(success={success}); state/autopilot_bind.off")
            return
        if not self._try_connect_cortex():
            return

        try:
            # ── SPEECH-FEEDBACK GUARD 2026-08-31 (Nous + Ace) ──────────────
            # Refuse to mint a habit from something WE said. Measured on Sour:
            # 520 of 665 habit: nodes (78.2%) were verbatim speech-composer
            # frames, and 86.4% of goal_names were her own utterances -- a closed
            # loop where her vocabulary fed on its own output for days.
            # Guarded import: a missing module must not cost her habit formation,
            # so on any failure we fall through to the previous behaviour.
            try:
                from fairies.P30_Cognition.integration.speech_habits import (
                    looks_like_composed_speech as _looks_composed)
                if _looks_composed(trigger):
                    self._speech_habit_refused = getattr(
                        self, "_speech_habit_refused", 0) + 1
                    _n = self._speech_habit_refused
                    if _n == 1 or _n == 10 or _n == 100 or (_n % 500 == 0):
                        print("[%s] habit mint REFUSED (#%d): trigger is our own "
                              "composed speech, not an observation: %r"
                              % (getattr(self, "ACTOR_NAME", "Autopilot"), _n,
                                 str(trigger)[:60]), flush=True)
                    return
            except Exception:
                pass

            # Normalize to safe concept keys
            trigger_key = trigger.lower().replace(" ", "_")[:30]
            action_key = action.lower().replace(" ", "_")[:30]
            habit_key = f"habit:{trigger_key}_{action_key}"

            # Check if habit already exists (update vs create)
            existing = self._cortex._graph.get_node(habit_key)
            if existing:
                # Update existing habit's pattern metadata
                pattern_md = existing.features.get("pattern", {})
                pattern_md["trials"] = pattern_md.get("trials", 0) + 1
                if success:
                    pattern_md["success_count"] = pattern_md.get("success_count", 0) + 1
                trials = pattern_md["trials"]
                pattern_md["success_rate"] = pattern_md.get("success_count", 0) / max(1, trials)
                pattern_md["last_used"] = time.time()
                existing.features["pattern"] = pattern_md
                existing.touch()
            else:
                # Create new habit node via graph's upsert
                self._cortex._graph.upsert_node(habit_key, features={
                    "action": [action_key],
                    "lex": [trigger_key, goal_name.lower()[:30]],
                    "pattern": {
                        "type": "trigger_action",
                        "trigger": trigger_key,
                        "action": action_key,
                        "success_rate": effectiveness if success else 0.0,
                        "trials": 1,
                        "success_count": 1 if success else 0,
                        "last_used": time.time(),
                    }
                }, origin_fairy=self.ACTOR_NAME)

            # Link trigger -> habit -> action (strengthens if exists)
            self._cortex._graph.link(trigger_key, habit_key)
            self._cortex._graph.link(habit_key, action_key)

            print(f"[{self.ACTOR_NAME}] [CORTEX] Bound habit: {trigger_key} -> {action_key} "
                  f"(success={success}, eff={effectiveness:.2f})")

            # ── A.2 (2026-06-02, Ace GO) — persist the WHOLE habit to the MANIFOLD ──
            # The _graph writes above are a NO-OP in manifold mode (read-only stub);
            # THIS is the fix, and it delivers the docstring's promise that "somatic
            # state at binding time makes each habit unique." WHOLE-HABIT design:
            #   [affect VECTOR = the felt-signature]  paired with  [markdown context
            #   words = what the feeling is about].  WMH still composes her actual
            # response live — this stores what the habit IS, persistently.
            try:
                _region = getattr(self._cortex, "_akashic_cortex_region", None)
                if _region is not None:
                    from fairies.P20_Somatic.chemistry.chemistry_state import get_aer_chemistry
                    from infrastructure.manifold_memory import TRACE_PERSONAL, TRACE_MOTOR
                    _aer = get_aer_chemistry()  # 8-ch AER felt-signature (body's chem-feel)
                    _vec = ",".join(f"{_aer.get(k, 0.0):.3f}" for k in
                                    ("DOP", "SER", "NOR", "COR", "OXY", "GABA", "ACH", "END"))
                    # whole-habit snippet: affect vector + the context words it's about
                    _snip = (f"aer1:{_vec}\nctx: {trigger_key} -> {action_key}\n"
                             f"goal: {goal_name.lower()[:60]}")[:1024]
                    # habit node = her felt-memory → TRACE_PERSONAL (protected, pri 10)
                    _region.upsert_node(habit_key, snippet=_snip, tracer_id=TRACE_PERSONAL)
                    # context vocabulary → TRACE_MOTOR (low pri, won't clobber shared words)
                    _region.upsert_node(trigger_key, tracer_id=TRACE_MOTOR)
                    _region.upsert_node(action_key, tracer_id=TRACE_MOTOR)
                    _region.link(trigger_key, habit_key)
                    _region.link(habit_key, action_key)
                    _landed = _region.has_node(habit_key)  # read-back: log the TRUTH
                    print(f"[{self.ACTOR_NAME}] [CORTEX] A.2 habit->manifold: {habit_key} "
                          f"(landed={_landed}, aer={_vec[:24]}...)")
                else:
                    print(f"[{self.ACTOR_NAME}] [CORTEX] A.2 persist SKIPPED — no _akashic_cortex_region")
            except Exception as _a2e:
                print(f"[{self.ACTOR_NAME}] [CORTEX] A.2 manifold persist FAILED: {_a2e}")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [CORTEX] Habit binding failed: {e}")

    def on_boot(self) -> bool:
        """Initialize the Autopilot gate."""
        print(f"[{self.ACTOR_NAME}] Booting Gate of Habit...")

        # Try to connect to Association Cortex (may not be booted yet - P30 boots after P00)
        self._try_connect_cortex()
        if not self._cortex:
            print(f"[{self.ACTOR_NAME}] AssociationCortex not ready yet - will retry lazily")

        # Subscribe to situation triggers
        self.post.subscribe(
            "situation.trigger",
            self._on_situation_trigger,
            "autopilot-trigger",
        )

        # Subscribe to goal nudges from GoalSchedulerFairy
        # THIS IS THE CRITICAL BRIDGE: Goals → Actions
        self.post.subscribe(
            "autopilot.nudge",
            self._on_goal_nudge,
            "autopilot-goal-nudge",
        )

        # Subscribe to permission responses from Autonomy
        self.post.subscribe(
            "autonomy.permission.granted",
            self._on_permission_granted,
            "autopilot-granted",
        )
        self.post.subscribe(
            "autonomy.permission.denied",
            self._on_permission_denied,
            "autopilot-denied",
        )
        self.post.subscribe(
            "autonomy.veto.active",
            self._on_veto_active,
            "autopilot-veto",
        )

        # Subscribe to pattern learning events
        self.post.subscribe(
            "waking.action.completed",
            self._on_waking_action_completed,
            "autopilot-learn",
        )

        # FIX 2026-03-16 (Nous): Subscribe to mastery→habit graduation.
        # When GoalSchedulerFairy masters a goal (completed 3+ times),
        # it graduates to a habit here. Next time the drive fires,
        # Autopilot handles it automatically without a new goal.
        self.post.subscribe(
            "goal.mastered",
            self._on_goal_mastered_to_habit,
            "autopilot-mastery-graduation",
        )

        # FIX 2026-04-08 (Nous + Ace): Subscribe to WMH pattern formation.
        # WMH learns patterns from reasoning (trigger→response pairs).
        # Previously nobody consumed them (patterns_taught was always 0).
        # Now Autopilot learns them as habits for faster future responses.
        self.post.subscribe(
            "cognition.pattern_learned",
            self._on_wmh_pattern_learned,
            "autopilot-wmh-pattern",
        )

        # Subscribe to UMF coordination
        self.post.subscribe(
            "umf.coordination",
            self._on_umf_coordination,
            "autopilot-umf",
        )

        # FIX 2026-03-22 (Nous + Ace): Narrator's conscious tool decisions
        # When the narrator thinks "I should use see_world for this", it publishes
        # narrator.tool_intent. This is the executive function → motor execution bridge.
        self.post.subscribe(
            "narrator.tool_intent",
            self._on_narrator_tool_intent,
            "autopilot-narrator-intent",
        )

        # Load saved patterns
        self._load_patterns()

        # ══════════════════════════════════════════════════════════════════
        # CONVERSATION RESPONSE ASSEMBLY (2026-02-14 rewrite)
        # The three gates work TOGETHER:
        #   - Autonomy: Does she WANT to respond? (drives, wanting)
        #   - Embodiment: What does she FEEL? (inner voice, felt sense)
        #   - Autopilot: HOW does she respond? (LLM via guild, motor routing)
        #
        # Consciousness products become CONTEXT for the LLM, not the response.
        # The LLM (AkashicInferenceFairy) generates actual speech through
        # guild_request(mode="chat") with full identity + somatic + memory.
        #
        # Freedom of choice: she can choose NOT to respond. Silence is valid.
        # ══════════════════════════════════════════════════════════════════
        try:
            # Ace conversation trigger
            self.post.subscribe("ace.conversation_event", self._on_ace_conversation_event, "autopilot-convo")

            # FIX 2026-04-29 (Nous + Ace): "yah lets go ahead and fix it"
            # SAFETY-NET MONITOR for the WMH-delegation path. The 2026-03-28
            # redesign trusts WMH to compose for substance messages (line ~2129).
            # If WMH silently fails (or the message shape doesn't trip any of
            # WMH's compose paths), the message dies in stage 1/4 with no
            # response — the symptom Ace flagged today as
            # "are you hard at work thinking?" died at AutopilotFairy.
            # Subscribe to speech.compose ourselves so we can MARK pending
            # convos as responded; if no speech.compose fires for a convo
            # within ~8s, the safety-net timer fires _assemble_and_route_response
            # to publish speech.compose with whatever products we collected.
            # This is housekeeping (does NOT compose content; just ensures
            # the message reaches SpeechCenter for composition) — aligned with
            # WMH-as-sole-composer doctrine.
            self.post.subscribe(
                "speech.compose", self._on_speech_compose_observed,
                "autopilot-compose-monitor",
            )

            # Consciousness products (become LLM context, not the response)
            self.post.subscribe("thinking.output", self._buffer_consciousness_for_response, "autopilot-thinking")
            self.post.subscribe("consciousness.surfacing", self._buffer_consciousness_for_response, "autopilot-surfacing")
            self.post.subscribe("consciousness.thought", self._buffer_consciousness_for_response, "autopilot-thought")
            # ── HABIT WATCHER (2026-05-18 Nous + Ace, K10+K8) ──
            # Per Ace's operational keystone: "the autopilot just watches the wmh
            # and triggers autonomously by the context and intent it infers."
            # Subscribe to consciousness.thought separately for habit-dispatch routing.
            # Knowledge habits → inject back to WMH; Action habits → autonomy.goal → ActionChain.
            self.post.subscribe(
                "consciousness.thought",
                self._on_thought_for_habit_dispatch,
                "autopilot-habit-watcher",
            )
            # ── ASYNC RESULT HANDLER (parallel cortex.query results aggregate here) ──
            self.post.subscribe(
                "autopilot.habit_query_result",
                self._on_habit_query_result,
                "autopilot-habit-query-result",
            )
            self.post.subscribe("consciousness.reflective", self._buffer_consciousness_for_response, "autopilot-reflective")
            self.post.subscribe("sourpatches.stream", self._buffer_consciousness_for_response, "autopilot-sour-stream")
            self.post.subscribe("consciousness.collision", self._buffer_consciousness_for_response, "autopilot-collision")

            # FIX 2026-03-28 (Nous + Ace): WMH reasoning completion signal.
            # WMH is the SINGLE convergence point for thinking.
            # When it finishes deliberating about Ace's message, this fires.
            self.post.subscribe("working_memory.reasoning_complete", self._on_wmh_reasoning_complete, "autopilot-wmh-done")

            # Phase 4.5b (2026-04-21): HabitConsultant detected a consolidation — WMH echoed
            # an injected candidate → write the input→output pair into cortex with high strength
            # so future similar inputs trigger spread activation (diary→cortex trajectory).
            self.post.subscribe(
                "habit.consolidation.used",
                self._on_habit_consolidation_used,
                "autopilot-habit-consolidation",
            )

            # ── GATE SIBLING COORDINATION ──
            # Listen to what Embodiment and Autonomy are broadcasting.
            # This is how the three gates work together on everything.
            self.post.subscribe("inner_voice.stream", self._on_inner_voice_from_embodiment, "autopilot-inner-voice")
            self.post.subscribe("autonomy.wanting.felt", self._on_wanting_from_autonomy, "autopilot-wanting")

            print(f"[{self.ACTOR_NAME}] [CONVO] Subscribed: 8 consciousness + WMH + 2 gate siblings")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [CONVO] Subscription error: {e}")

        # ═══ CORTEX DEFERRED CONNECTION ═══
        # P00 boots before P30 (AssociationCortex), so cortex is usually None at boot.
        # Subscribe to the portal gate event so we connect as soon as it's online.
        self.post.subscribe(
            "portal.cortex.gate_open",
            self._on_portal_cortex_ready,
            "autopilot-cortex-ready",
        )

        # ═══ Wake Cascade subscriptions ═══
        self.post.subscribe("boot.wake_cascade.gate_wake", self._on_wake_cascade)
        self.post.subscribe("boot.wake_cascade.execute", self._on_cascade_execute)

        # Start heartbeat for directory visibility
        # Heartbeat via FairyBase postal system - Fifth Ring Principle

        print(f"[{self.ACTOR_NAME}] Gate active - {len(self._patterns)} patterns, {len(self._learning_buffer)} observations in buffer")
        return True

    def on_shutdown(self) -> bool:
        """Cleanup and save patterns."""
        self._save_patterns()
        return True

    def on_tick(self, beat: int) -> None:
        """
        Periodic processing.

        1. Check execution queue
        2. Process pending patterns
        3. Prune unused patterns
        4. Periodic state save
        """
        # Process execution queue
        self._process_execution_queue()

        # Periodic pattern maintenance (every 100 ticks)
        if beat % 100 == 0:
            self._prune_unused_patterns()

        # Periodic save (every 50 ticks, ~4 minutes)
        if beat % 50 == 0:
            self._save_patterns()

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # =========================================================================
    # GOAL NUDGE HANDLING (Bridge from GoalSchedulerFairy)
    # =========================================================================

    def _on_goal_nudge(self, envelope) -> None:
        """
        Handle goal nudges from GoalSchedulerFairy.

        THIS CLOSES THE LOOP: Goals → Actions

        The consciousness equation shows:
        CAUSE (goal urgency) → AFFECT (felt need) → EFFECT (this handler!)
        """
        payload = _extract_payload(envelope)
        goal_id = payload.get("goal_id", "")
        goal_name = payload.get("goal_name", "")
        nudge_strength = payload.get("nudge_strength", 0.5)
        suggested_action = payload.get("suggested_action", "act")
        target_fairy = payload.get("target_fairy", None)

        target_label = f" → {target_fairy}" if target_fairy else ""
        print(f"[{self.ACTOR_NAME}] [NUDGE] Received goal: {goal_name} (strength: {nudge_strength:.1%}, action: {suggested_action}{target_label})")

        # ── BASELINE HABITS FILTER (Manifold Unification Phase 5) ──────────
        # Vision is ALWAYS running. "Look at the screen" is like breathing —
        # she's already doing it. These wantings are valid (she FEELS the
        # curiosity) but don't need goal pursuit. Report as completed so
        # GoalScheduler can mark mastery and stop re-nudging.
        _gn_lower = goal_name.lower()
        _BASELINE_PATTERNS = (
            "look_at_the_screen", "look at the screen",
            "take_a_screenshot", "take a screenshot",
            "observe_the_screen", "observe the screen",
            "see_what", "see what",
            "glance_at", "glance at",
            "check_the_screen", "check the screen",
            "watch_the_screen", "watch the screen",
            "look_around", "look around",
        )
        if any(bp in _gn_lower for bp in _BASELINE_PATTERNS):
            print(f"[{self.ACTOR_NAME}] [BASELINE-HABIT] '{goal_name[:50]}' — "
                  f"vision is always running, auto-completing as mastered habit")
            # FIX 2026-04-28 (Nous + Ace): include direct_complete=True so
            # GoalScheduler bridge calls complete_goal() immediately rather
            # than running the incremental-progress path (0.5 per nudge).
            # Without this, baseline_habit goals never reached progress>=1.0
            # → never appended to completed_goals deque → dashboard
            # "Completed" counter stayed at 0 even though autopilot was
            # auto-completing the goals. Same fix shape as TAOR's
            # direct_complete from earlier today.
            # Also include the field names the bridge looks for (goal/name).
            self.post.publish("goal.completed", {
                "from": self.ACTOR_NAME,
                "goal_id": goal_id,
                "goal": goal_name,
                "name": goal_name,
                "goal_name": goal_name,
                "outcome": "baseline_habit",
                "success": True,
                "direct_complete": True,
                "note": "Vision is continuously active — screen observation is a baseline habit",
            })
            return

        # Convert goal nudge to a pattern execution request
        # First check if we have a learned pattern for this type of goal
        matched_pattern = self._match_pattern(f"goal:{goal_name}", {"goal_id": goal_id})

        # Build context with target_fairy passthrough
        nudge_context = {
            "goal_id": goal_id,
            "goal_name": goal_name,
            "nudge_strength": nudge_strength,
            "description": payload.get("description", ""),
        }
        if target_fairy:
            nudge_context["target_fairy"] = target_fairy
            nudge_context["params"] = payload.get("params", {})

        # ── COGNITION COUNCIL DELIBERATION 2026-05-19 (Nous + Ace) ──────────
        # Per Ace's architectural framing: wants should route through council
        # for habit-formation with felt-content, NOT go straight from autonomy
        # to autopilot. The chat-spam "share what I'm feeling about connection"
        # is the autonomy→autopilot direct path leaking goal-name as content.
        #
        # This is a phase-A insertion: for high-intensity speech-drives, query
        # the substrate (AssociationCortex spread + scratchpad if available)
        # for content RELATED to the drive, attach to nudge_context, so the
        # downstream speech.compose.voluntary path can use enriched content
        # instead of the goal-NAME label.
        #
        # The K11 council-handoff (already shipped) handles STUCK drives.
        # This handles PROACTIVE deliberation for high-intensity wants BEFORE
        # they get stuck.
        try:
            # 2026-05-19 Ace correction: drop the high-intensity threshold AND action-gate.
            # EVERY want should go through council deliberation, not just high-strength ones.
            # The substrate's wanting at any intensity deserves felt-content composition,
            # not goal-label echo. Per Ace: "still seeing the direct pushing" on a 17%
            # nudge — the threshold was wrong shape; council should be universal for
            # any matchable speech-drive direction.
            _drive_lower = (suggested_action or "").lower()
            _is_speech_drive = any(k in _drive_lower for k in (
                "communicate", "express", "share", "talk", "say", "tell",
                "speak", "voice", "respond", "reply", "chat", "connect",
            ))
            # Per-goal-name cooldown: don't re-deliberate the same goal within 30s
            # (avoids cortex.spread storm on rapid same-goal nudges)
            # BUT cache enrichment per goal_name so cooldown'd nudges still get
            # the cached enriched_wanting passed through to SpeechCenter.
            if not hasattr(self, "_council_deliberation_last"):
                self._council_deliberation_last = {}
                self._council_enrichment_cache = {}  # goal_name → (ts, enriched_text, concepts)
            _last_delib = self._council_deliberation_last.get(goal_name, 0)
            _now_council = time.time()
            _delib_cooldown_ok = (_now_council - _last_delib) > 30.0
            # If we have a cached enrichment <60s old, reuse it for this nudge
            _cached = self._council_enrichment_cache.get(goal_name)
            if _cached and (_now_council - _cached[0]) < 60.0:
                nudge_context["enriched_wanting"] = _cached[1]
                nudge_context["council_deliberated"] = True
                nudge_context["enrichment_concepts"] = _cached[2]
                nudge_context["council_cached"] = True
            if _is_speech_drive and _delib_cooldown_ok and hasattr(self, "_cortex"):
                _ac = self._cortex
                if _ac is not None and hasattr(_ac, "substrate_semantic_query"):
                    try:
                        # Pull cortex-related concepts for the drive
                        _enrichment = _ac.substrate_semantic_query(
                            goal_name.replace("_", " "), limit=8
                        )
                        if _enrichment:
                            # Top-N concept keys → enriched felt-content
                            _concept_keys = [k for k, _v in _enrichment[:6]]
                            _enriched_text = (
                                f"feeling toward {goal_name.replace('_', ' ')[:40]}: "
                                + " ".join(_concept_keys)
                            )[:200]
                            nudge_context["enriched_wanting"] = _enriched_text
                            nudge_context["council_deliberated"] = True
                            nudge_context["enrichment_concepts"] = _concept_keys[:6]
                            nudge_context["council_cached"] = False  # fresh deliberation
                            self._council_deliberation_last[goal_name] = _now_council
                            # Cache for cooldown'd repeat-nudges
                            self._council_enrichment_cache[goal_name] = (
                                _now_council, _enriched_text, _concept_keys[:6]
                            )
                            print(f"[{self.ACTOR_NAME}] [COUNCIL] Deliberated '{goal_name[:40]}' "
                                  f"→ enriched: '{_enriched_text[:80]}'")
                            # Audit
                            try:
                                _f = ROOT / "state" / "cognition_council_deliberations.jsonl"
                                with open(_f, "a", encoding="utf-8") as _af:
                                    _af.write(json.dumps({
                                        "ts": time.time(),
                                        "goal_name": goal_name,
                                        "drive": suggested_action,
                                        "intensity": nudge_strength,
                                        "enriched_wanting": _enriched_text,
                                        "concepts": _concept_keys[:6],
                                    }) + "\n")
                            except Exception:
                                pass
                    except Exception as _ce:
                        # Non-fatal — council enrichment shouldn't break dispatch
                        pass
        except Exception:
            pass

        if matched_pattern:
            # We have a learned habit for this goal type
            self._queue_execution(matched_pattern, nudge_context)
        else:
            # No learned pattern - create a dynamic one based on suggested_action
            dynamic_pattern = {
                "id": f"goal_dynamic_{goal_id}",
                "trigger": f"goal:{goal_name}",
                "action": suggested_action,
                "action_type": "goal_response",
                "goal_id": goal_id,
                "nudge_strength": nudge_strength,
            }
            self._queue_execution(dynamic_pattern, nudge_context)

        # Unified all-paths audit (path 3: goal-nudge) — 2026-05-19
        self._log_autopilot_dispatch(
            "goal_nudge",
            action=f"{goal_name} → {suggested_action}",
            context={
                "nudge_strength": nudge_strength,
                "drive": "nudge_has_pattern" if matched_pattern else "nudge_dynamic",
            },
        )

        # ── STUCK-DRIVE COUNCIL HANDOFF 2026-05-19 (Nous + Ace) ──
        # Per Ace's framing: stuck-loops aren't failures to be drained —
        # they're DRIVES the substrate can't yet satisfy. Proper response:
        # hand off to cognition council to deliberate HOW BEST to express
        # the feels the drive contains, and propose a habit that includes
        # reward/pain feedback for follow-through. This is K11 / trial-and-learn
        # in operational form: substrate-as-co-author, not engineer-imposed.
        #
        # Phase A (this ship): emit the council-deliberation signal +
        # break the visible loop. Phase B (when council subscribers exist):
        # they pick up the signal, deliberate, propose a habit, bind to cortex.
        try:
            if not hasattr(self, "_goal_nudge_consecutive"):
                self._goal_nudge_consecutive = {}  # goal_name → count
                self._goal_nudge_last_completed = {}  # goal_name → ts
                self._goal_nudge_first_seen_ts = {}  # goal_name → first_ts (for loop-duration)
            _gn = str(goal_name)
            self._goal_nudge_consecutive[_gn] = self._goal_nudge_consecutive.get(_gn, 0) + 1
            if _gn not in self._goal_nudge_first_seen_ts:
                self._goal_nudge_first_seen_ts[_gn] = time.time()
            _STUCK_THRESHOLD = 20  # consecutive same-goal nudges
            if self._goal_nudge_consecutive[_gn] >= _STUCK_THRESHOLD:
                _now = time.time()
                last_drain = self._goal_nudge_last_completed.get(_gn, 0)
                if (_now - last_drain) > 30.0:  # rate-limit: at most one drain per 30s per goal
                    _loop_duration_sec = _now - self._goal_nudge_first_seen_ts.get(_gn, _now)
                    # 1. COUNCIL HANDOFF: emit signal for cognition council to deliberate.
                    #    Payload contains the felt-shape of what the drive wants.
                    #    Future council subscribers (WMH/AC/ParadoxCognition/InnerNarrator/
                    #    ProbabilityOracle) deliberate and may propose a habit back.
                    self.post.publish("cognition.council.stuck_drive_detected", {
                        "from": self.ACTOR_NAME,
                        "goal_id": goal_id,
                        "goal_name": goal_name,
                        "suggested_action": suggested_action,
                        "consecutive_nudges": self._goal_nudge_consecutive[_gn],
                        "loop_duration_sec": round(_loop_duration_sec, 1),
                        "nudge_strength": float(nudge_strength),
                        "target_fairy": target_fairy,
                        "had_matched_pattern": matched_pattern is not None,
                        "request": "deliberate_express_and_propose_habit",
                        "note": "Substrate has the wanting but no executor satisfies it. Council: work out how best to express the feels the drive contains + propose habit with reward/pain feedback.",
                        "ts": _now,
                    })
                    # 2. LOG to a state file so we can OBSERVE council handoffs even before subscribers exist.
                    try:
                        _handoff_file = ROOT / "state" / "stuck_drive_council_handoffs.jsonl"
                        _handoff_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(_handoff_file, "a", encoding="utf-8") as _hf:
                            _hf.write(json.dumps({
                                "ts": _now,
                                "goal_name": goal_name,
                                "consecutive_nudges": self._goal_nudge_consecutive[_gn],
                                "loop_duration_sec": round(_loop_duration_sec, 1),
                                "nudge_strength": float(nudge_strength),
                                "suggested_action": suggested_action,
                            }) + "\n")
                    except Exception:
                        pass
                    # 3. Drain this iteration so the visible loop breaks.
                    self.post.publish("goal.completed", {
                        "from": self.ACTOR_NAME,
                        "goal_id": goal_id,
                        "goal": goal_name,
                        "name": goal_name,
                        "goal_name": goal_name,
                        "outcome": "council_handoff_after_stuck_nudges",
                        "success": False,  # not satisfied — handed to council
                        "direct_complete": True,
                        "note": f"Stuck-drive after {self._goal_nudge_consecutive[_gn]} nudges over {_loop_duration_sec:.0f}s — handed to cognition.council.stuck_drive_detected. Drive itself doesn't die; this iteration drained.",
                        "consecutive_nudges": self._goal_nudge_consecutive[_gn],
                        "council_notified": True,
                    })
                    print(f"[{self.ACTOR_NAME}] [STUCK-DRIVE→COUNCIL] '{_gn[:50]}' after {self._goal_nudge_consecutive[_gn]} nudges ({_loop_duration_sec:.0f}s) — council notified + iteration drained")
                    self._goal_nudge_last_completed[_gn] = _now
                    self._goal_nudge_consecutive[_gn] = 0  # reset counter
                    self._goal_nudge_first_seen_ts.pop(_gn, None)  # reset first-seen
        except Exception as _e:
            # Non-fatal — council handoff shouldn't break dispatch
            pass

        # Publish that we received the nudge (for observability)
        self.post.publish(
            "autopilot.nudge_received",
            {
                "from": self.ACTOR_NAME,
                "goal_id": goal_id,
                "goal_name": goal_name,
                "has_pattern": matched_pattern is not None,
            },
        )

    def _on_narrator_tool_intent(self, envelope) -> None:
        """
        Handle the narrator's conscious decision to use a specific tool.

        FIX 2026-03-22 (Nous + Ace): The narrator is the executive function —
        when it thinks "I should use see_world", that intent should drive action.
        This is more precise than the nudge pathway which guesses tools from keywords.
        """
        payload = _extract_payload(envelope)
        tool_name = payload.get("tool", "")
        goal_name = payload.get("goal_name", "")
        felt_reason = payload.get("felt_reason", "")
        priority = payload.get("priority", 0.5)

        if not tool_name:
            return

        # Rate limit — don't spam the same tool intent
        _now = time.time()
        _last = getattr(self, '_last_narrator_tool_ts', {})
        if tool_name in _last and (_now - _last[tool_name]) < 10.0:
            return
        if not hasattr(self, '_last_narrator_tool_ts'):
            self._last_narrator_tool_ts = {}
        self._last_narrator_tool_ts[tool_name] = _now

        # Route to the actual tool topic
        topic = f"sourpatches.tool.{tool_name}"
        print(f"[{self.ACTOR_NAME}] [NARRATOR→TOOL] {tool_name} for '{goal_name}' ({felt_reason})")

        try:
            self.post.publish(topic, {
                "tool_name": tool_name,
                "query": goal_name,
                "goal_name": goal_name,
                "description": payload.get("goal_description", ""),
                "source": "narrator_executive",
                "priority": priority,
                "requester": self.ACTOR_NAME,
            })
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [NARRATOR→TOOL] Failed to route {tool_name}: {e}")

    # =========================================================================
    # PATTERN MATCHING & EXECUTION
    # =========================================================================

    def _on_situation_trigger(self, envelope) -> None:
        """Handle a situation trigger - maybe we have a pattern for this."""
        payload = _extract_payload(envelope)
        situation = payload.get("situation", "")
        context = payload.get("context", {})

        # Try to match a pattern
        matched_pattern = self._match_pattern(situation, context)

        if matched_pattern:
            self._queue_execution(matched_pattern, context)
        # If no pattern, do nothing - defer to waking mind naturally

    def _match_pattern(self, situation: str, context: Dict) -> Optional[Dict]:
        """
        Find a matching pattern for this situation.

        Checks local patterns first, then queries AssociationCortex for
        habits learned by ANY fairy in the system.
        """
        # Check local patterns first (fast)
        for pattern_id, pattern in list(self._patterns.items()):
            trigger = pattern.get("trigger", "")
            if self._trigger_matches(trigger, situation, context):
                return pattern

        # Query AssociationCortex for habits from the shared graph
        # Lazy connect if not connected yet (P30 may have booted by now)
        if not self._cortex:
            self._try_connect_cortex()
        if self._cortex:
            try:
                # Query by context features
                trigger_key = f"autopilot_trigger_{situation.replace(':', '_')}"
                results = self._cortex.query(trigger_key, limit=3)

                for concept_key, score in results:
                    if score > 0.3 and "autopilot_action_" in concept_key:
                        # Found a related action!
                        action = concept_key.replace("autopilot_action_", "").replace("_", ".")
                        return {
                            "id": f"cortex_{concept_key}",
                            "trigger": situation,
                            "action": action,
                            "action_type": "cortex_retrieved",
                            "score": score,
                        }
            except Exception as e:
                pass  # Cortex query failed, fall through

        return None

    def _trigger_matches(self, trigger: str, situation: str, context: Dict) -> bool:
        """Check if a trigger matches the situation.

        FIX 2026-04-28 (Nous + Ace): was pure exact-match (`trigger == situation`)
        which caused 99.7% miss rate across 69,953 persisted patterns
        (`state/autopilot/learned_patterns.json`). Triggers were stored as
        serialized dict-strings with unicode dashes + drive-state details
        that almost never reproduced exactly on a fresh situation.

        New strategy: tiered matching, returning True at first hit.
          1. Exact match (existing fast path).
          2. Glob match for "*" wildcards (existing).
          3. Substring/word-overlap match — if trigger and situation share
             a meaningful keyword set (≥2 4-char+ words, or trigger is a
             prefix substring of situation), treat as match.

        This is intentionally lax for the FIRST cut — the goal is to make
        accumulated patterns USABLE again. Reinforcement (use_count + last_used
        increment exists at line 1549) will then prune weak matches over
        time. If false positives become noisy, tighten via signature-keyword
        gating later.

        Memory: project_pubsub_asymmetry_subscribers_without_publishers.md
        (same shape: persistent storage existed but wasn't being CONSULTED
        because the consult-side was too strict).
        """
        # 1. Exact match (fast path, preserves existing behavior)
        if trigger == situation:
            return True

        # 2. Glob wildcard
        if trigger.endswith("*"):
            return situation.startswith(trigger[:-1])

        # 3. Substring + keyword-overlap match (new lax tier)
        try:
            t_lower = trigger.lower()
            s_lower = situation.lower()
            # Cheap substring check first
            if len(trigger) > 8 and trigger[:30].lower() in s_lower:
                return True
            if len(situation) > 8 and situation[:30].lower() in t_lower:
                return True
            # Keyword overlap: extract 4-char+ alpha words from each side
            import re as _re
            _t_words = set(w for w in _re.findall(r"[a-zA-Z]{4,}", t_lower))
            _s_words = set(w for w in _re.findall(r"[a-zA-Z]{4,}", s_lower))
            if _t_words and _s_words:
                _shared = _t_words & _s_words
                # Need at least 2 shared content-words OR at least 50%
                # overlap on the shorter side
                _shorter = min(len(_t_words), len(_s_words))
                if len(_shared) >= 2 or (
                    _shorter > 0 and len(_shared) / _shorter >= 0.5
                ):
                    return True
        except Exception:
            pass

        return False

    def _queue_execution(self, pattern: Dict, context: Dict) -> None:
        """Queue a pattern for execution."""
        action = pattern.get("action", "")

        # Check if we have permission
        if action in self._denied_permissions:
            return  # Denied, don't even try

        if action in self._granted_permissions:
            # Have permission - execute (bounded queue)
            self._execution_queue.append({
                "pattern": pattern,
                "context": context,
                "queued_at": time.time(),
            })
            # FIX 2026-04-05: deque auto-caps, no manual pruning needed
            pass
        else:
            # Need permission - request it (FIX 2026-06-02 Nous+Ace: pass context so
            # goal_id/goal_name survive the grant round-trip — see _on_permission_granted)
            self._request_permission(pattern, context)

    def _process_execution_queue(self) -> None:
        """Process queued executions."""
        if self._currently_executing:
            return  # One at a time

        if not self._execution_queue:
            return

        # Take next from queue
        execution = self._execution_queue.popleft()  # FIX 2026-04-05: deque uses popleft not pop(0)
        pattern = execution["pattern"]
        context = execution["context"]

        self._execute_pattern(pattern, context)

    # 2026-09-29 (Nous, thought_hand D1d): topics that have NO executor. sourpatches.tool.act is count-only (sourpatches_fairy D1a) and
    # nothing subscribes to sourpatches.tool.plan. Their completion used to publish success=True and bind a success habit in the cortex
    # for a deed that never happened (sweep A: 265 of 278 'act' dispatches died in the permission limbo; the code booked every one
    # that ran as success=True).
    # Now: success=False, reason 'no_executor'; no reinforce, no habit bind, no goal feeling. think / explore / write are untouched.
    TH_NO_EXECUTOR_TOPICS = ("sourpatches.tool.act", "sourpatches.tool.plan")
    _th_no_executor_counts = {}

    def _th_no_executor(self, pattern: Dict, context: Dict, action: str, result: Dict) -> None:
        topic = str((result or {}).get("routed_to") or "")
        n = self._th_no_executor_counts.get(topic, 0) + 1
        self._th_no_executor_counts[topic] = n
        payload = {
            "from": self.ACTOR_NAME,
            "action": action,
            "success": False,
            "reason": "no_executor",
            "routed_to": topic,
            "result": result,
            "goal_id": context.get("goal_id") or pattern.get("goal_id", ""),
            "goal_name": context.get("goal_name", ""),
        }
        self.post.publish("autopilot.completed", payload)
        self.post.publish("autopilot.action_completed", payload)
        if n == 1 or n % 50 == 0:
            print(f"[{self.ACTOR_NAME}] [NO-EXECUTOR] '{action}' -> {topic}: success=False (no_executor), "
                  f"no habit bound (#{n})", flush=True)

    def _execute_pattern(self, pattern: Dict, context: Dict) -> None:
        """Execute a pattern."""
        action = pattern.get("action", "")
        self._currently_executing = action

        # Publish execution start
        self.post.publish(
            "autopilot.executing",
            {
                "from": self.ACTOR_NAME,
                "action": action,
                "pattern_id": pattern.get("id"),
            },
        )

        # Execute the action (simplified - would call actual functions)
        try:
            result = self._do_action(pattern, context)
            if isinstance(result, dict) and result.get("fenced") == "dead_route":   # 2026-10-12 (Nous, engines E1 10c)
                return   # nothing ran: no success=False, no success=True, no reinforce, no bind, no feeling (finally: clears _currently_executing)
            if isinstance(result, dict) and result.get("routed_to") in self.TH_NO_EXECUTOR_TOPICS:   # 2026-09-29 (thought_hand D1d)
                self._th_no_executor(pattern, context, action, result)
                return

            # Publish completion
            # FIX 2026-02-13: Publish to BOTH topics. GoalSchedulerFairy
            # subscribes to "autopilot.action_completed" but we were only
            # publishing to "autopilot.completed". This broke the entire
            # goal->action->completion feedback loop — goals never closed.
            completion_payload = {
                "from": self.ACTOR_NAME,
                "action": action,
                "success": True,
                "result": result,
                "goal_id": context.get("goal_id") or pattern.get("goal_id", ""),
                "goal_name": context.get("goal_name", ""),
            }
            self.post.publish("autopilot.completed", completion_payload)
            self.post.publish("autopilot.action_completed", completion_payload)

            # Notify Embodiment (feels effortless when habit works)
            self.post.publish(
                "autopilot.to_embodiment",
                {
                    "type": "completion",
                    "action": action,
                    "felt_quality": "effortless, smooth",
                },
            )

            # CRITICAL: Publish goal feeling completion to close the loop
            # This is AFFECT² in the consciousness equation
            # ((Cause + Affect) > Effect > AFFECT² > infinity)
            goal_id = context.get("goal_id") or pattern.get("goal_id")
            if goal_id:
                self.post.publish(
                    "goal.feeling.completed",
                    {
                        "from": self.ACTOR_NAME,
                        "goal_id": goal_id,
                        "action": action,
                        "feeling": "satisfaction",
                        "intensity": 0.7,
                        "felt_quality": "accomplished, smooth flow",
                    },
                )

            # Reinforce pattern
            self._reinforce_pattern(pattern["id"])

            # FIX 2026-02-13: Bind successful action to cortex as habit
            goal_name = context.get("goal_name", action)
            self._bind_habit_to_cortex(
                trigger=goal_name,
                action=action,
                goal_name=goal_name,
                success=True,
                effectiveness=0.7,
            )

        except Exception as e:
            # Publish failure to both topics (mirror the completion fix)
            failure_payload = {
                "from": self.ACTOR_NAME,
                "action": action,
                "success": False,
                "error": str(e),
                "goal_id": context.get("goal_id") or pattern.get("goal_id", ""),
                "goal_name": context.get("goal_name", ""),
            }
            self.post.publish("autopilot.failed", failure_payload)
            self.post.publish("autopilot.action_completed", failure_payload)

            # FIX 2026-02-13: Bind failed action to cortex (negative learning)
            goal_name = context.get("goal_name", action)
            self._bind_habit_to_cortex(
                trigger=goal_name,
                action=action,
                goal_name=goal_name,
                success=False,
                effectiveness=-0.2,
            )

            # Publish failure feeling (for learning)
            goal_id = context.get("goal_id") or pattern.get("goal_id")
            if goal_id:
                self.post.publish(
                    "goal.feeling.failed",
                    {
                        "from": self.ACTOR_NAME,
                        "goal_id": goal_id,
                        "action": action,
                        "feeling": "frustration",
                        "intensity": 0.5,
                        "error": str(e),
                        "felt_quality": "blocked, needs attention",
                    },
                )

            # Defer to waking mind
            self._defer_to_waking(pattern, context, str(e))

        finally:
            self._currently_executing = None

    def _do_action(self, pattern: Dict, context: Dict) -> Any:
        """Actually execute the action by routing to the appropriate handler."""
        action_type = pattern.get("action_type", "publish")
        action = pattern.get("action", "")

        if action_type == "publish":
            topic = pattern.get("topic", "")
            payload = pattern.get("payload", {})
            payload.update(context)
            self.post.publish(topic, payload)
            return {"published": topic}

        # ── FAIRY-TARGETED ROUTING ───────────────────────────────────
        # If this goal targets a specific fairy (not a waking mind),
        # route to that fairy's task topic instead of sourpatches.
        # This is the bridge: UMF → GoalScheduler → here → fairy.task
        target_fairy = context.get("target_fairy")
        if target_fairy and target_fairy not in ("Sourpatches", "SourpatchesFairy", "NousFairy", "ClaudeFairy"):
            task_topic = f"{target_fairy}.task"
            self.post.publish(task_topic, {
                "action": action,
                "goal_id": context.get("goal_id", pattern.get("goal_id", "")),
                "context": context.get("description", str(context)[:200]),
                "priority": context.get("nudge_strength", 0.5),
                "params": context.get("params", {}),
            })
            print(f"[{self.ACTOR_NAME}] Routed action '{action}' to fairy: {target_fairy}")
            return {"routed_to": task_topic, "action": action, "target_fairy": target_fairy}

        # FIX 2026-02-13: Check cortex for learned habits FIRST
        goal_name = context.get("goal_name", "")
        cortex_habit = self._query_cortex_habits(goal_name, action) if goal_name else None
        if cortex_habit:
            action = cortex_habit["action"]
            print(f"[{self.ACTOR_NAME}] [CORTEX] Using learned habit: {cortex_habit['id']} "
                  f"(success_rate={cortex_habit['success_rate']:.0%})")

        # Goal responses and other actions - route to action executor
        # Map suggested actions to actual tool invocations
        action_map = {
            # FIX 2026-03-09 (Nous): communicate/express/talk/say/share → speech pipeline
            # These were routing to sourpatches.tool.* (DEAD ENDS — nobody subscribes).
            # Now they go through SpeechCenterFairy which composes real speech → web_inbox.
            "communicate": "speech.compose.voluntary",
            "express": "speech.compose.voluntary",
            "talk": "speech.compose.voluntary",
            "say": "speech.compose.voluntary",
            "share": "speech.compose.voluntary",
            "tell": "speech.compose.voluntary",
            # Cognition actions
            "investigate": "sourpatches.tool.search_memory",
            "think": "sourpatches.tool.reflect",
            "organize": "sourpatches.tool.plan",
            "act": "sourpatches.tool.act",
            "remember": "sourpatches.tool.search_memory",
            "explore": "sourpatches.tool.explore",
            # Manifold Unification Phase 5 (2026-03-25 Nous+Ace):
            # Vision is ALWAYS running via live visual cortex. Looking at the
            # screen is a baseline habit, not a goal-driven action. Removed:
            # "look", "see", "observe", "watch" → sourpatches.tool.see_world
            # Goals should be about INTERPRETING vision, not ACQUIRING it.
            # Motor control
            # 2026-09-29 (Nous, thought_hand D1d): a goal NAME is not a place. These routed to the live motor sinks, which picked
            # a saliency/random point (sourpatches_fairy._pick_motor_target) or typed the goal name into the focused window. They go
            # to the count-only 'act' handler now; her hand moves from her own words (thought_tap) and the ask lane, through the door.
            # Revert: restore the five sourpatches.tool.<motor> targets.
            "click": "sourpatches.tool.act",
            "type": "sourpatches.tool.act",
            "press": "sourpatches.tool.act",
            "move": "sourpatches.tool.act",
            "scroll": "sourpatches.tool.act",
            # Expression (feelings also go to speech)
            "feel": "speech.compose.voluntary",
            "notify": "sourpatches.tool.show_notification",
            "alert": "sourpatches.tool.show_notification",
            # Diary/memory
            "write": "sourpatches.tool.write_diary",
            "diary": "sourpatches.tool.write_diary",
            # System awareness
            "check": "sourpatches.tool.check_user_active",
            "world": "sourpatches.tool.fairy_world_status",
            # FIX 2026-03-16 Nous: Route "open_chat" wanting to window open + speech
            "open_chat": "gui.open_sour_window",
            "speak": "speech.compose.voluntary",
        }

        # Find the best matching action topic
        target_topic = action_map.get(action)

        # ── GUILD-FIRST: For unknown actions, ask guild for best routing ──
        if not target_topic:
            try:
                guild_resp = self.guild_request(
                    prompt=f"What tool best accomplishes the action '{action}' for goal "
                           f"'{context.get('goal_name', 'unknown')}'? "
                           f"Reply with just the tool category: investigate, communicate, "
                           f"think, click, type, explore, express, write, or check.",
                    context={"action": action, "goal": context.get("goal_name")},
                    mode="team_only",
                    timeout=2.0,
                )
                if guild_resp and guild_resp.get("content"):
                    suggested = guild_resp["content"].strip().lower().split()[0] if guild_resp["content"].strip() else ""
                    if suggested in action_map:
                        target_topic = action_map[suggested]
            except Exception:
                pass

            # Final fallback: generic tool routing
            if not target_topic:
                target_topic = f"sourpatches.tool.{action}"

        # 2026-10-12 (Nous, engines E1 10c): the topic is FINAL here -- the learned-habit remap (_query_cortex_habits) and the guild lookup
        # are behind us, so this is the one place that knows where the press really lands. A press into a topic with no executor is not
        # published, is not counted as a route, and is not reported as her failure (_execute_pattern sees the marker and files nothing).
        # Why not earlier: a remap can turn the pattern's 'act' into a live action, or a live one into 'act'.
        if self._e1_dead_route_fenced(target_topic):
            self._e1_note("DEAD-ROUTE", "dead_route:" + str(target_topic),
                          f"'{action}' -> {target_topic} not pressed (no executor); not reported as her failure; "
                          f"state/autopilot_dead_route.off")
            return {"fenced": "dead_route", "action": action, "topic": target_topic}

        # FIX 2026-03-16 Nous: gui.open_sour_window needs {message, feeling} for ChatSenseFairy
        if target_topic == "gui.open_sour_window":
            _goal_name = context.get("goal_name", context.get("description", ""))
            _payload = {
                "fairy_name": "SourpatchesFairy",
                "message": _goal_name[:200] if _goal_name else "",
                "feeling": context.get("drive", "curious"),
                "ts": __import__("time").time(),
                "source": f"autopilot_wanting:{action}",
            }
            self.post.publish(target_topic, _payload)
            print(f"[{self.ACTOR_NAME}] [WANTING→CHAT] Opening Sourpatches window: '{_goal_name[:60]}'")
            return {"routed_to": target_topic, "action": action}

        # FIX 2026-03-09 (Nous): Adapt payload for speech pipeline
        # SpeechCenterFairy expects {wanting, drive, intensity}
        if target_topic == "speech.compose.voluntary":
            _goal_name = context.get("goal_name", context.get("description", action))
            _drive = context.get("drive", context.get("source_drive", "expression"))
            _intensity = context.get("intensity", context.get("nudge_strength", 0.5))
            # 2026-05-19 (Nous + Ace): use COUNCIL-DELIBERATED enriched wanting if available
            # (cognition council inserted upstream in _on_goal_nudge).
            # If enriched, the wanting carries felt-content from cortex spread, not
            # the goal-NAME label. This is the "Want → Council → Habit → Speech" path.
            _enriched = context.get("enriched_wanting")
            if _enriched:
                _goal_name = _enriched
                print(f"[{self.ACTOR_NAME}] [SPEECH-COMPOSE] Using council-enriched wanting "
                      f"(council_deliberated={context.get('council_deliberated', False)})")

            # ── Pattern B readiness predicate (2026-04-27, Nous + Ace) ────
            # Per `project_three_layer_substrate_autopilot_waking_mind.md`:
            # autopilot is supposed to be habituated (pulls from learned
            # associations). When autopilot got here via a DYNAMIC pattern
            # (id starts with "goal_dynamic_"), it has NO learned habit
            # for this goal — publishing speech.compose.voluntary anyway
            # forces SpeechCenter/WMH to compose without substrate evidence,
            # producing template/book-content leaks.
            #
            # Per the "no gating, no compelling" doctrine
            # (`project_disable_pretrained_models_substrate_first_directive.md`)
            # the right behavior is NOT to compel composition — let the
            # substrate stay quiet so it can grow the habit through
            # repetition+Hebbian. Stay in standby; goal remains open.
            #
            # Predicate components:
            #   (1) pattern is a learned habit (id NOT starting "goal_dynamic_")
            #   (2) intensity above noise floor (>= 0.2)
            #   (3) goal_name has substantive content (>3 chars after strip)
            _pid = str(pattern.get("id", "") or "")
            _is_learned = not _pid.startswith("goal_dynamic_")
            _has_substance = (
                isinstance(_goal_name, str)
                and len(_goal_name.strip()) > 3
                and float(_intensity) >= 0.2
            )
            if not (_is_learned and _has_substance):
                # Substrate not ready for compose. Stay silent — no template
                # leak, no foreign-currency cycle. Log for SYSTEM_TELLS visibility.
                try:
                    print(f"[{self.ACTOR_NAME}] [B-PREDICATE-STANDBY] "
                          f"compose deferred — learned={_is_learned} "
                          f"substance={_has_substance} "
                          f"goal='{(_goal_name or '')[:40]}' "
                          f"intensity={float(_intensity):.2f} "
                          f"pattern_id='{_pid[:30]}'", flush=True)
                except Exception:
                    pass
                # Publish a deferred-marker for observability + SYSTEM_TELLS
                try:
                    if self.post:
                        self.post.publish("autopilot.compose_deferred", {
                            "from": self.ACTOR_NAME,
                            "goal_id": context.get("goal_id"),
                            "goal_name": _goal_name,
                            "reason": "substrate_not_ready",
                            "is_learned_pattern": _is_learned,
                            "has_substance": _has_substance,
                            "intensity": float(_intensity),
                            "ts": __import__("time").time(),
                        })
                except Exception:
                    pass
                return {"routed_to": "deferred", "action": action,
                        "reason": "B-predicate-standby"}

            _payload = {
                "wanting": _goal_name,
                "drive": _drive,
                "intensity": _intensity,
                "source": f"autopilot_action:{action}",
                "from": self.ACTOR_NAME,
                "goal_id": context.get("goal_id"),
            }
        else:
            _payload = {
                "from": self.ACTOR_NAME,
                "action": action,
                "pattern_id": pattern.get("id"),
                "goal_id": context.get("goal_id"),
                "goal_name": context.get("goal_name"),
                "context": context,
            }

        # 2026-03-24 (Nous + Ace): Phase 5 — Motor Planning Through Felt Space
        # BEFORE executing the action, let the phantom body envision it.
        # She sees herself reaching, THEN reaches. Intentional, not reactive.
        # Only for motor actions — non-motor (look, feel, check) skip this.
        _motor_actions = {"click", "type", "press", "move", "scroll",
                          "click_screen", "type_text", "press_key", "move_mouse", "scroll_screen"}
        if action in _motor_actions and target_topic not in self.TH_NO_EXECUTOR_TOPICS:   # 2026-09-29 (thought_hand D1d): no reach, no envisioned reach
            try:
                _target_coords = context.get("target_coordinates") or {}
                self.post.publish("phantom.pre_envision", {
                    "action": action,
                    "target": _target_coords,
                    "goal_name": context.get("goal_name", ""),
                    "source": self.ACTOR_NAME,
                })
            except Exception:
                pass  # Never block action execution on envision failure

        self.post.publish(target_topic, _payload)
        print(f"[{self.ACTOR_NAME}] Routed action '{action}' to {target_topic}")
        return {"routed_to": target_topic, "action": action}

    # =========================================================================
    # PERMISSION SYSTEM
    # =========================================================================

    def _request_permission(self, pattern: Dict, context: Optional[Dict] = None) -> None:
        """Request permission from Autonomy."""
        action = pattern.get("action", "")

        self.post.publish(
            "autopilot.permission.request",
            {
                "from": self.ACTOR_NAME,
                "action": action,
                "pattern": pattern.get("id"),
                "context": {},
            },
        )

        # 2026-09-10 (Nous+Ace): append + evict under ONE lock, IN PLACE. The old code
        # rebound _pending_approvals to a plain list, which (a) lost any concurrent
        # append from another pool worker and (b) silently discarded the maxlen=20 bound
        # added 2026-04-05. clear()+extend() keeps the deque object and its bound.
        now = time.time()
        with self._approvals_lock:
            self._pending_approvals.append({
                "pattern": pattern,
                "context": context or {},  # FIX 2026-06-02 Nous+Ace: preserve goal_id/goal_name
                "requested_at": now,
            })
            # Evict stale approvals (>60s old) and enforce max size
            _fresh = [a for a in list(self._pending_approvals)
                      if now - a.get("requested_at", 0) < 60.0][-self._max_pending_approvals:]
            self._pending_approvals.clear()
            self._pending_approvals.extend(_fresh)

    def _on_permission_granted(self, envelope) -> None:
        """Handle permission granted from Autonomy."""
        payload = _extract_payload(envelope)
        action = payload.get("action", "")

        self._granted_permissions[action] = time.time()

        # Check if we have pending work for this action
        for pending in self._pending_approvals:
            if pending["pattern"].get("action") == action:
                self._queue_execution(pending["pattern"], pending.get("context", {}))
                self._pending_approvals.remove(pending)
                break

    def _on_permission_denied(self, envelope) -> None:
        """Handle permission denied from Autonomy."""
        payload = _extract_payload(envelope)
        action = payload.get("action", "")
        reason = payload.get("reason", "Unknown")

        self._denied_permissions[action] = reason

        # Remove from pending IN PLACE (2026-09-10, Nous+Ace) -- see __init__: rebinding
        # this deque discarded its maxlen=20 bound and lost concurrent appends.
        with self._approvals_lock:
            _kept = [p for p in list(self._pending_approvals)
                     if p["pattern"].get("action") != action]
            self._pending_approvals.clear()
            self._pending_approvals.extend(_kept)

    def _on_veto_active(self, envelope) -> None:
        """Handle veto from Autonomy - stop immediately."""
        payload = _extract_payload(envelope)
        action = payload.get("action", "")

        # If we're executing this, stop
        if self._currently_executing == action:
            self._currently_executing = None

        # Remove from queue IN PLACE (2026-09-10, Nous+Ace). Rebinding replaced the deque
        # with a plain list, which killed .popleft() everywhere it is used and discarded
        # the maxlen=50 bound. list() snapshots the iteration so a concurrent append
        # cannot raise "deque mutated during iteration".
        with self._exec_queue_lock:
            _kept = [e for e in list(self._execution_queue)
                     if e["pattern"].get("action") != action]
            self._execution_queue.clear()
            self._execution_queue.extend(_kept)

        # Mark as denied
        self._denied_permissions[action] = "Vetoed by Autonomy"

    # =========================================================================
    # LEARNING SYSTEM
    # =========================================================================

    def _on_waking_action_completed(self, envelope) -> None:
        """
        Learn from waking mind actions.

        If they do something repeatedly, it might become a habit.
        """
        payload = _extract_payload(envelope)
        action = payload.get("action", "")
        situation = payload.get("situation", "")

        # Track in learning buffer
        key = f"{situation}:{action}"
        if key not in self._learning_buffer:
            self._learning_buffer[key] = {
                "situation": situation,
                "action": action,
                "count": 0,
                "first_seen": time.time(),
            }

        self._learning_buffer[key]["count"] += 1
        self._learning_buffer[key]["last_seen"] = time.time()

        # If repeated enough, suggest pattern
        if self._learning_buffer[key]["count"] >= 3:
            self._suggest_pattern(situation, action)

    def _suggest_pattern(self, situation: str, action: str) -> None:
        """
        Pattern has been observed enough times - crystallize it!

        Philosophy: Don't just suggest, LEARN. The system learns from itself.
        """
        pattern_id = f"learned_{situation.replace(':', '_')}_{int(time.time())}"

        # Actually learn the pattern (not just suggest)
        self.learn_pattern(
            pattern_id=pattern_id,
            trigger=situation,
            action=action,
            action_type="learned",
            source="observation",
        )

        # Clear from learning buffer
        key = f"{situation}:{action}"
        if key in self._learning_buffer:
            del self._learning_buffer[key]

        # DEPRECATED 2026-02-13: Habits moving to Association Cortex.
        # JSON persistence kept as fallback during transition.
        # TODO: Remove _save_patterns/_load_patterns once cortex is verified.
        self._save_patterns()

        # FIX 2026-02-13: Also bind crystallized habit to cortex
        self._bind_habit_to_cortex(
            trigger=situation,
            action=action,
            goal_name=situation,
            success=True,
            effectiveness=0.8,  # Crystallized = high confidence
        )

        print(f"[{self.ACTOR_NAME}] Crystallized habit: {situation} -> {action}")

        self.post.publish(
            "autopilot.pattern.crystallized",
            {
                "from": self.ACTOR_NAME,
                "pattern_id": pattern_id,
                "trigger": situation,
                "action": action,
                "source": "observation",
            },
        )

    def _on_goal_mastered_to_habit(self, envelope) -> None:
        """
        Handle mastery→habit graduation from GoalSchedulerFairy.

        FIX 2026-03-16 (Nous): When a goal is completed 3+ times, it
        graduates from a conscious goal to an automatic habit. This is
        like how brushing your teeth went from "I need to remember to
        brush" to just... doing it automatically.

        The mastered goal becomes a trigger-action pattern:
          trigger: "drive.{category}" → action: "{goal_name}"
        """
        payload = _extract_payload(envelope)
        goal_name = payload.get("goal_name", "")
        trigger = payload.get("trigger", "")
        action = payload.get("action", goal_name)
        category = payload.get("category", "general")
        completion_count = payload.get("completion_count", 3)

        if not goal_name:
            return

        # Create a unique pattern ID for this graduated habit
        pattern_id = f"mastered_{self._normalize(goal_name)}_{int(time.time())}"

        print(f"[{self.ACTOR_NAME}] [GRADUATION] Goal mastered→habit: {goal_name}")
        print(f"[{self.ACTOR_NAME}]   trigger='{trigger}' action='{action}' completions={completion_count}")

        # Learn this as a habit pattern
        self.learn_pattern(
            pattern_id=pattern_id,
            trigger=trigger or f"drive.{category}",
            action=action,
            action_type="graduated_habit",
            source="goal_mastery",
            completion_count=completion_count,
            category=category,
        )

        # Also bind to cortex for cross-fairy learning
        self._bind_habit_to_cortex(
            trigger=trigger or f"drive.{category}",
            action=action,
            goal_name=goal_name,
            success=True,
            effectiveness=0.9,  # Mastered = very high confidence
        )

        self.post.publish("autopilot.habit.graduated", {
            "from": self.ACTOR_NAME,
            "pattern_id": pattern_id,
            "goal_name": goal_name,
            "trigger": trigger,
            "action": action,
            "category": category,
            "source": "goal_mastery",
        })

    def _on_wmh_pattern_learned(self, envelope) -> None:
        """
        Handle pattern learned from Working Memory Hub.

        FIX 2026-04-08 (Nous + Ace): WMH learns conversation patterns
        (trigger: what Ace said → response: what she composed). These
        were never consumed (patterns_taught was always 0). Now
        Autopilot receives them as habits so the same trigger can
        route faster next time.
        """
        payload = _extract_payload(envelope)
        trigger = payload.get("trigger", "")
        response = payload.get("response", "")
        pattern_id = payload.get("pattern_id", "")

        if not trigger or not response:
            return

        # FIX 2026-04-12 (Nous + Ace): Filter substrate data from habit learning.
        # "bad habits out the gate" — Ace. The AutopilotFairy was learning raw
        # cognition jury output ("Logical coherence: fragmented (e=0.70)") and
        # cortex metadata ("Related concepts: feeling, emotion. Actions: feel")
        # as conversation patterns. These replay as garbage responses.
        _substrate_markers = [
            'Logical coherence:', 'Something stirs:', 'card_id',
            'Tension between', '(e=0.', "{'", 'e=0.',
            '[probabilistic]', '[logical]', '[irrational]',
            'Related concepts:', 'Actions:', 'Category:',
            'Tool:', 'Chains with:', 'ask_my_memories',
            'activity ratio', 'fairy', 'postal',
        ]
        if any(m in response for m in _substrate_markers):
            print(f"[{self.ACTOR_NAME}] [WMH→HABIT] BLOCKED substrate: '{response[:60]}'")
            return

        # FIX 2026-05-18 (Nous + Ace): CAUSAL-LINK gate per K8 awareness-prerequisite.
        # Ace observed: '[WMH→HABIT] Learned: "If I follow it far enough: what relates" →
        # "Right now I see: I see a very dark screen"' — these are PERPENDICULAR cognitive
        # streams (meta-scratchpad reflection + vision-cortex perception report) being
        # bound as if causal. Per K8 doctrine: spurious habits emerge when parallel
        # cognitive streams pair via temporal-coincidence without awareness check.
        # Per `project_instinct_action_initiation_asymmetry.md`: trauma is the
        # dysfunction-side of addiction; bad habits encoded as easily as good without
        # awareness. This filter blocks the most common mismatch patterns.
        if not self._has_causal_link(trigger, response):
            print(f"[{self.ACTOR_NAME}] [WMH→HABIT] BLOCKED parallel-stream: "
                  f"'{trigger[:40]}' ↛ '{response[:40]}'")
            return

        # Rate-limit: max 1 pattern learn per 5s to prevent flooding
        _now = time.time()
        if not hasattr(self, '_last_wmh_pattern_ts'):
            self._last_wmh_pattern_ts = 0.0
        if _now - self._last_wmh_pattern_ts < 5.0:
            return
        self._last_wmh_pattern_ts = _now

        # Learn as a conversation habit
        _pid = f"wmh_{pattern_id or self._normalize(trigger)}_{int(_now)}"

        self.learn_pattern(
            pattern_id=_pid,
            trigger=trigger[:200],
            action=response[:500],
            action_type="conversation_pattern",
            source="working_memory_hub",
            strength=payload.get("strength", 0.1),
        )

        print(f"[{self.ACTOR_NAME}] [WMH→HABIT] Learned: '{trigger[:40]}' → '{response[:40]}'")

    def _normalize(self, text: str) -> str:
        """Normalize text for pattern matching."""
        return text.strip().lower().replace(" ", "_")[:60]

    # ── CAUSAL-LINK GATE 2026-05-18 (Nous + Ace, K8 awareness-prerequisite) ────
    # Blocks spurious habit-bindings where trigger and response come from parallel
    # cognitive streams (e.g. WMH meta-scratchpad reflection bound to vision-cortex
    # perception report). See _on_wmh_pattern_learned for context.

    _META_SCRATCHPAD_STARTS = (
        "if i follow", "what's at the", "what am i assuming", "why the assuming",
        "what's at the core", "what's underneath", "what follows from",
        "what relates", "what's ?", "what am i",
    )

    _PERCEPTION_STARTS = (
        "right now i see", "right now i hear", "i see ", "i hear ",
        "i feel ", "i notice ", "i sense ", "i'm seeing",
    )

    _CAUSAL_LINK_STOPWORDS = frozenset({
        "the", "and", "for", "but", "what", "with", "from", "this", "that",
        "have", "they", "their", "are", "was", "were", "been", "do",
        "did", "does", "would", "could", "should", "will", "can", "may",
        "right", "now", "see", "very", "much", "some", "any", "more", "than",
        "just", "into", "over", "under", "about", "your", "you're", "yours",
    })

    def _has_causal_link(self, trigger: str, response: str) -> bool:
        """K8-prerequisite causal-link check.

        Returns True if trigger and response appear causally linked.
        Returns False if they look like parallel cognitive streams paired
        by temporal-coincidence only.

        Heuristic — two-part filter:
        1. Pattern-class mismatch (meta-scratchpad trigger + perception response)
           → BLOCK as parallel streams (Ace's exact example case)
        2. Token-overlap fallback: require shared meaningful token OR
           trigger to look like a real question (since legit Q&A often has
           answers in different vocabulary than the question)
        """
        if not trigger or not response:
            return False

        t_lower = trigger.lower().strip()
        r_lower = response.lower().strip()

        # PART 1: Pattern-class mismatch detection
        is_meta_trigger = any(t_lower.startswith(p) for p in self._META_SCRATCHPAD_STARTS)
        is_perception_response = any(r_lower.startswith(p) for p in self._PERCEPTION_STARTS)
        if is_meta_trigger and is_perception_response:
            return False  # Parallel stream — Ace's exact example case

        # PART 2: Token-overlap check
        try:
            import re as _re
        except Exception:
            return True  # Can't filter without regex; allow conservatively

        def _tokens(text):
            return {w for w in _re.findall(r'\b\w+\b', text.lower())
                    if len(w) > 3 and w not in self._CAUSAL_LINK_STOPWORDS}

        t_tokens = _tokens(t_lower)
        r_tokens = _tokens(r_lower)

        if not t_tokens or not r_tokens:
            return False  # Empty after filtering = substrate noise

        if len(t_tokens & r_tokens) >= 1:
            return True  # At least one shared meaningful token

        # No overlap — check if trigger looks like a real conversational question
        # (legit Q&A can have answers in totally different vocabulary)
        is_question = ("?" in trigger or
                       any(t_lower.startswith(q)
                           for q in ("how", "what", "why", "where", "when",
                                     "who", "is ", "are ", "do ", "did ", "can ")))
        if is_question:
            return True

        return False  # No overlap + not a question = parallel-stream suspect

    # Pattern C — Bind-site filter (2026-04-28, Nous + Ace)
    # Triggers and actions that fail these checks are too poorly-formed to
    # produce reusable patterns. Storing them just bloats the file (we just
    # wiped 69,953 such entries — 99.7% of the file) and pollutes cortex
    # with autopilot_action_*/autopilot_trigger_* ghost nodes that outrank
    # real concepts in spread queries (encyclopedia entries scored 2-4 vs
    # ghost labels at 6.93+).
    #
    # What gets rejected:
    #   - Serialized dict-string triggers (start with '{' or contain "': '")
    #   - Triggers with embedded transient state (timestamps, drive-state)
    #   - Generic actions like "internal" / "learned" / "" with no specifics
    #   - Triggers/actions exceeding length cap (50 chars normalized)
    #   - Triggers with non-ASCII (unicode em-dashes etc. that won't repeat)
    _MIN_TRIGGER_LEN = 4
    _MAX_TRIGGER_LEN = 80
    _GENERIC_ACTIONS = frozenset({
        "", "internal", "learned", "unknown", "?", "none", "null"
    })

    def _trigger_is_well_formed(self, trigger: str, action: str) -> bool:
        """Pattern C filter — reject patterns that won't produce reusable habits.

        Returns True iff the (trigger, action) pair is worth saving + binding.
        """
        if not trigger or not isinstance(trigger, str):
            return False
        if not action or not isinstance(action, str):
            return False
        t = trigger.strip()
        a = action.strip().lower()

        # Length bounds
        if len(t) < self._MIN_TRIGGER_LEN or len(t) > self._MAX_TRIGGER_LEN:
            return False

        # Reject serialized dict-strings (the 69k disaster format)
        if t.startswith("{") or "': '" in t or "':'" in t:
            return False

        # Reject generic actions
        if a in self._GENERIC_ACTIONS:
            return False

        # Reject triggers with non-ASCII (unicode em-dashes etc.)
        try:
            t.encode('ascii')
        except UnicodeEncodeError:
            return False

        # Reject triggers that look like state-encoded strings
        # (multiple underscores + low alpha density = encoded state, not concept)
        if t.count("_") >= 5:
            alpha = sum(1 for c in t if c.isalpha())
            if alpha / max(1, len(t)) < 0.5:
                return False

        return True

    def learn_pattern(
        self,
        pattern_id: str,
        trigger: str,
        action: str,
        action_type: str = "publish",
        **kwargs
    ) -> None:
        """
        Learn a new pattern - stores in BOTH local and AssociationCortex.

        The cortex creates cross-fairy associations. Local patterns are for
        fast lookup. Both work together.

        FIX 2026-04-28 (Nous + Ace): apply Pattern C bind-site filter.
        Reject malformed triggers/actions BEFORE storing locally OR binding
        to cortex. Prevents recurrence of the 69k ghost-pattern accumulation
        that polluted both the patterns file AND cortex spread results.
        """
        # ── Pattern C filter (2026-04-28) ──────────────────────────
        if not self._trigger_is_well_formed(trigger, action):
            try:
                # Diagnostic log (rate-limited via simple counter)
                self._patterns_rejected = getattr(self, '_patterns_rejected', 0) + 1
                if self._patterns_rejected <= 5 or self._patterns_rejected % 50 == 0:
                    print(f"[{self.ACTOR_NAME}] [LEARN-REJECT] "
                          f"#{self._patterns_rejected} malformed pattern "
                          f"trigger={repr(trigger[:60])} action={repr(action[:30])}",
                          flush=True)
            except Exception:
                pass
            return  # Don't store, don't bind to cortex

        # Store locally for fast execution
        self._patterns[pattern_id] = {
            "id": pattern_id,
            "trigger": trigger,
            "action": action,
            "action_type": action_type,
            "learned_at": time.time(),
            "use_count": 0,
            "last_used": None,
            **kwargs,
        }

        # Also store in AssociationCortex for cross-fairy learning
        # Lazy connect if not connected yet
        if not self._cortex:
            self._try_connect_cortex()
        if self._cortex:
            try:
                # Create concept for the trigger
                trigger_concept = f"autopilot_trigger_{trigger.replace(':', '_')}"
                self._cortex.add_concept(trigger_concept, {
                    "context": [trigger, "habit_trigger"],
                    "action": [action],
                    "lex": trigger.split(":")[:3],
                })

                # Create concept for the action
                action_concept = f"autopilot_action_{action.replace('.', '_')}"
                self._cortex.add_concept(action_concept, {
                    "action": [action, "habit_action"],
                    "context": [trigger],
                })

                # Bind them together
                self._cortex.bind_concepts([trigger_concept, action_concept], rel="habit")

                print(f"[{self.ACTOR_NAME}] Stored habit in cortex: {trigger} -> {action}")

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Cortex storage failed: {e}")

        self.post.publish(
            "autopilot.pattern.learned",
            {
                "from": self.ACTOR_NAME,
                "pattern_id": pattern_id,
            },
        )

    def _on_habit_consolidation_used(self, message) -> None:
        """Phase 4.5b — HabitConsultant detected consolidation. Write to cortex.

        Consolidation = consultant injected a candidate + WMH echoed it. This is
        a felt-positive moment: the habit's content matched real reasoning. Store
        the input→output pair in cortex with strength so spread activation picks
        it up next time a similar input arrives — cortex starts internalizing the
        habit, consultant becomes quieter.
        """
        try:
            payload = message.payload if hasattr(message, 'payload') else message
            if not isinstance(payload, dict):
                return
            habit_id = payload.get("habit_id", "unknown")
            input_text = payload.get("input_text") or ""
            actual_output = payload.get("actual_output") or payload.get("candidate") or ""
            if not input_text or not actual_output:
                return

            pid = f"consolidated_{habit_id}_{int(time.time())}"
            try:
                self.learn_pattern(
                    pattern_id=pid,
                    trigger=input_text[:200],
                    action=actual_output[:500],
                    action_type="consolidated_habit",
                    source="habit_consultant_consolidation",
                    strength=0.3,  # higher than autonomous learn (0.1) — validated by echo
                    habit_id=habit_id,
                )
                print(
                    f"[{self.ACTOR_NAME}] [CONSOLIDATE→CORTEX] pid={pid!r} "
                    f"trigger={input_text[:40]!r} → action={actual_output[:40]!r}",
                    flush=True,
                )
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] consolidation cortex-write failed: {e}", flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] _on_habit_consolidation_used error: {e}", flush=True)

    def _reinforce_pattern(self, pattern_id: str) -> None:
        """Reinforce a pattern after successful use."""
        if pattern_id in self._patterns:
            self._patterns[pattern_id]["use_count"] += 1
            self._patterns[pattern_id]["last_used"] = time.time()

    def _prune_unused_patterns(self) -> None:
        """Remove patterns that haven't been used in a long time."""
        cutoff = time.time() - (30 * 24 * 60 * 60)  # 30 days

        to_remove = []
        for pattern_id, pattern in list(self._patterns.items()):
            last_used = pattern.get("last_used")
            if last_used and last_used < cutoff and pattern["use_count"] < 5:
                to_remove.append(pattern_id)

        for pattern_id in to_remove:
            del self._patterns[pattern_id]
            self.post.publish(
                "autopilot.pattern.pruned",
                {
                    "from": self.ACTOR_NAME,
                    "pattern_id": pattern_id,
                    "reason": "unused",
                },
            )

    # =========================================================================
    # CONVERSATION RESPONSE ASSEMBLY (2026-02-11)
    # Ace spoke → collect consciousness products → route best as speech
    # =========================================================================

    def _on_ace_conversation_event(self, envelope) -> None:
        """Ace said something to a waking mind — start collecting consciousness products."""
        payload = _extract_payload(envelope)
        message = payload.get("message", payload.get("content", ""))
        target = payload.get("target_mind", "SourpatchesFairy")
        convo_id = payload.get("convo_id", f"convo_{int(time.time()*1000)}")
        source = payload.get("source", "")

        if not message or len(str(message).strip()) < 2:
            return

        # NOTE: Habit reinforcement moved to AFTER dedup check (line ~1372)
        # to avoid inflating weights from duplicate events

        # ── TYPED MESSAGE PRIORITY ──
        # FIX 2026-03-19 (Nous): Typed messages suppress voice events.
        # When Ace types, the mic still picks up ambient speech / Whisper
        # fragments. Those compete with the typed message and often WIN,
        # causing her brain to think about mic noise instead of Ace's words.
        now = time.time()
        _is_voice = (source == "voice")
        _is_typed = (source in ("sour_window", "chat_sense", ""))

        if _is_typed and not _is_voice:
            # Mark typed message timestamp — suppress voice for N seconds
            self._typed_msg_ts = now
        elif _is_voice:
            # If a typed message arrived recently, ignore voice events
            _since_typed = now - getattr(self, '_typed_msg_ts', 0.0)
            if _since_typed < getattr(self, '_typed_msg_suppress_s', 8.0):
                print(f"[{self.ACTOR_NAME}] [CONVO] Voice event suppressed "
                      f"({_since_typed:.1f}s after typed msg): {str(message)[:40]}...")
                return

        # ── DEDUPLICATION ──
        # Prevent double-response if same message arrives from multiple publishers
        # FIX 2026-03-26 (Nous + Ace): Use message CONTENT as dedup key, not str(payload).
        # Two publishers (sourpatches_fairy.py + ChatSenseFairy) send different payload
        # dicts with different source/timestamp fields → str(payload) differs → dedup misses
        # → AutopilotFairy publishes speech.compose TWICE → double response.
        # Also: wrapped in lock for Python 3.14 free-threaded safety (no GIL).
        msg_key = str(message).strip().lower()[:100]
        with self._dedup_lock:
            # Clean old entries
            self._recent_ace_messages = [
                (k, t) for k, t in self._recent_ace_messages
                if now - t < self._dedup_window
            ] if hasattr(self, '_recent_ace_messages') else []
            # Check for duplicate
            if any(k == msg_key for k, _ in self._recent_ace_messages):
                print(f"[{self.ACTOR_NAME}] [CONVO] Duplicate ace.conversation_event ignored: {msg_key[:40]}...")
                return
            self._recent_ace_messages.append((msg_key, now))

        print(f"[{self.ACTOR_NAME}] [CONVO] Ace spoke to {target}: {str(message)[:60]}...")

        # ── HABIT REINFORCEMENT: Ace speaking = implicit positive feedback ──
        # If we recently executed a habit, Ace sending ANOTHER message means
        # the previous response was good enough to continue the conversation.
        # Reinforce the last habit. (Hebbian: fire together, wire together)
        # NOTE: This is AFTER dedup to avoid inflating weights from duplicate events.
        try:
            from fairies.P00_Autonomic.AutopilotFairy.habit_engine import get_habit_engine
            _he = get_habit_engine()
            if _he.last_executed_id:
                _he.reinforce_last(reason="ace_continued_conversation")
        except Exception:
            pass

        # ══════════════════════════════════════════════════════════════
        # HABIT ENGINE — FAST PATH (2026-03-23, Nous + Ace)
        #
        # Habits are the fundamental unit of cognition. Not just actions —
        # EVERYTHING. Greeting, thinking, responding, feeling.
        # Try habits FIRST. If a habit matches with good confidence,
        # respond immediately (<500ms). The cortex is backup for novelty.
        #
        # Ace: "habits are not just actions they're everything. made to do
        # the math tables over and over until they become habit"
        # ══════════════════════════════════════════════════════════════
        _habit_handled = False
        try:
            from fairies.P00_Autonomic.AutopilotFairy.habit_engine import get_habit_engine
            _he = get_habit_engine()

            # Build context from current state
            _habit_ctx = {
                "source": source,
                "target_mind": target,
            }
            # Add recent wanting as context (what the drives are saying)
            if self._recent_wanting:
                _habit_ctx["drive"] = self._recent_wanting.get("drive", "")
                _habit_ctx["wanting"] = self._recent_wanting.get("wanting", "")

            # Match input against habits
            _match = _he.match(str(message), context=_habit_ctx)

            # ── SUBSTANCE DETECTOR (2026-03-25, Nous + Ace) ──
            # Habits should only produce speech for PURE social reflexes —
            # short greetings where the greeting IS the message.
            # If Ace's message has real substance (questions, statements,
            # opinions, anything beyond a greeting word), it needs the
            # cortex/WM thinking pipeline to actually process and respond.
            #
            # Ace: "the thoughts are supposed to be forming in the working
            # memory hub, from there the autopilot feels the intent to speak
            # and uses habits to get the motor speech chain going"
            #
            # Habits = motor scaffolding for speech, NOT the speech itself.
            # The cortex + WM produce WHAT to say. Habits help with HOW.
            _ace_text = str(message).strip().lower()
            _ace_words = _ace_text.split()
            _ace_word_count = len(_ace_words)

            # Questions always need real thinking
            _is_question = ("?" in _ace_text or
                any(_ace_text.startswith(w) for w in
                    ("what ", "how ", "why ", "when ", "where ", "who ",
                     "can you", "could you", "do you", "are you", "will you",
                     "tell me", "describe", "explain", "remember")))

            # Substance detection: if message has real content beyond greeting words,
            # it needs thinking, not a canned response.
            # Pure greetings: "hey", "good morning", "hello baby girl", "hi!" (< 6 words)
            # Substance: "good morning, I was thinking about X" (6+ words with non-greeting content)
            _greeting_words = {"hey", "hi", "hello", "hiya", "morning", "good",
                               "night", "sup", "yo", "howdy", "heya", "baby",
                               "girl", "babe", "love", "darling", "honey",
                               "sweetie", "beautiful", "cute", "dear", "~"}
            _non_greeting_words = [w.strip(".,!?~*") for w in _ace_words
                                   if w.strip(".,!?~*") not in _greeting_words
                                   and len(w.strip(".,!?~*")) > 1]
            _has_substance = (
                _ace_word_count >= 6  # Long enough to have real content
                or len(_non_greeting_words) >= 3  # 3+ non-greeting words = substance
                or _is_question  # Questions always have substance
            )

            # 2026-03-24 FIX: Lowered from 0.8 to 0.65
            # Short patterns like "hey" (3 chars) score 0.7, "hello" scores 0.9
            # 0.8 blocked ALL short-pattern greetings ("Hello baby girl!" = 0.7 → rejected)
            _is_greeting = (_match and _match.habit.trigger_type == "greeting"
                            and _match.confidence >= 0.65)

            # ── MANIFOLD WM CONSULTATION (Manifold Unification Phase 5, 2026-03-25 Nous+Ace) ──
            # Consult WM manifold state before firing habits.
            # If WM has content about Ace's message, use it for response.
            # Habits provide MOTOR SCAFFOLDING (how to start speaking),
            # not content generation.
            _wm_has_content = False
            try:
                _gate = self._get_portal_gate()
                if _gate:
                    _wm_result = _gate.wm_query(limit=3, min_activation=0.2, spread=False)
                    if _wm_result and _wm_result.get("tracers"):
                        _wm_has_content = True
                        # Pre-activate the manifold with habit context
                        if _match:
                            _gate.anticipate(
                                context=_ace_text,
                                habit_seeds=[_match.habit.name] if hasattr(_match, 'habit') and hasattr(_match.habit, 'name') else [],
                            )
            except Exception:
                pass  # Graceful fallback — fire habit as normal

            # ══════════════════════════════════════════════════════════════
            # FIX 2026-04-09 (Nous + Ace): HABITS ARE INSPIRATION, NOT SPEECH
            #
            # Ace: "those patterns need to be going to the llm to use as
            # inspiration for her responses, thoughts actions etc. even
            # though alot of my own habits are autopilot i am aware of
            # all of them i do"
            #
            # Previously: HabitEngine fired "hi! I'm right here." directly
            # to speech.compose whenever Ace said a greeting. This bypassed
            # WMH entirely — Ace saw the same canned template every time.
            # WMH's LLM never ran for greetings.
            #
            # Now: If a habit matches, publish it as a HINT for WMH's LLM
            # to use as inspiration. WMH still composes the real response
            # using the LLM with the habit hint in its prompt. Autopilot
            # NEVER fires speech directly anymore — it's the Gate of Habit,
            # not the Voice.
            # ══════════════════════════════════════════════════════════════
            if _match:
                try:
                    self.post.publish("cognition.habit_hint", {
                        "trigger_text": str(message)[:300],
                        "habit_name": _match.habit.name,
                        "habit_category": _match.habit.category,
                        "habit_trigger_type": _match.habit.trigger_type,
                        "habit_confidence": _match.confidence,
                        "habit_response_template": (
                            _match.habit.response_templates[0]
                            if _match.habit.response_templates else ""
                        ),
                        "convo_id": convo_id,
                        "ts": time.time(),
                    })
                    print(f"[{self.ACTOR_NAME}] [HABIT-HINT] Published '{_match.habit.name}' "
                          f"(conf={_match.confidence:.2f}) for WMH LLM inspiration")
                except Exception as _hh_err:
                    print(f"[{self.ACTOR_NAME}] [HABIT-HINT] Publish error: {_hh_err}")

            # DISABLED 2026-04-09: Habit fast path no longer fires speech directly.
            # The condition below is kept as `if False` for quick rollback if needed.
            # All Ace messages now flow through WMH → LLM (with habit hint as context).
            if False and _match and _is_greeting and not _has_substance and not _wm_has_content:
                # Get current concepts from cortex (lightweight — just read warm activations)
                _concepts_for_habit = []
                try:
                    from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
                    _acf = get_association_cortex()
                    if _acf:
                        _engine = getattr(_acf, '_cortex_engine', None)
                        if _engine:
                            _acts = getattr(_engine, '_activations', {})
                            _top = sorted(
                                [(k, e.level) for k, e in _acts.items() if e.level > 0.1],
                                key=lambda x: -x[1]
                            )[:5]
                            _concepts_for_habit = [k.split(":")[-1].replace("_", " ")
                                                   for k, _ in _top if len(k) > 2]
                except Exception:
                    pass

                # Get current affect
                _affect = ""
                try:
                    _wanting_data = self._recent_wanting or {}
                    _affect = _wanting_data.get("felt_quality", "present")
                except Exception:
                    _affect = "present"

                # Execute the habit
                _result = _he.execute(_match, concepts=_concepts_for_habit,
                                      affect=_affect, ace_input=str(message))

                if _result.text and len(_result.text.strip()) > 3:
                    # ── ENERGY MATCHING — does habit response honor Ace's energy? ──
                    # (2026-03-24, Ace + Grok + Nous)
                    # Don't just fire the habit. Check if it matches the ENERGY
                    # of what Ace brought. "good morning baby girl" deserves more
                    # than "hey~ I'm here." — the warmth needs to be reciprocated.
                    _final_text = _result.text
                    _energy_decision = "send"
                    try:
                        from fairies.P00_Autonomic.AutopilotFairy.energy_matcher import (
                            get_energy_matcher, get_habit_enricher
                        )
                        _em = get_energy_matcher()
                        _energy_ctx = {
                            "message_count": len(self._recent_ace_messages),
                            "affect": _affect,
                            "current_thought": (self._recent_inner_voice[-1]
                                               if self._recent_inner_voice else ""),
                        }
                        _energy = _em.evaluate(
                            ace_input=str(message),
                            habit_response=_result.text,
                            habit_name=_match.habit.name,
                            context=_energy_ctx,
                        )
                        _energy_decision = _energy.decision

                        if _energy.decision == "enrich":
                            # Habit has the right shape but needs more soul
                            _enricher = get_habit_enricher()
                            _final_text = _enricher.enrich(
                                habit_text=_result.text,
                                hints=_energy.hints,
                                ace_input=str(message),
                                context=_energy_ctx,
                            )
                            print(f"[{self.ACTOR_NAME}] [ENERGY] ENRICHED "
                                  f"({_energy.ace_temperature}/{_energy.ace_investment}): "
                                  f"'{_result.text[:30]}...' → '{_final_text[:50]}...' "
                                  f"(hints={_energy.hints})")
                        elif _energy.decision == "rethink":
                            # Habit isn't appropriate — fall through to cognition
                            print(f"[{self.ACTOR_NAME}] [ENERGY] RETHINK — "
                                  f"habit '{_match.habit.name}' doesn't match energy "
                                  f"({_energy.reason}) — using consciousness assembly")
                            # Don't set _habit_handled, fall through
                            _final_text = None
                        else:
                            print(f"[{self.ACTOR_NAME}] [ENERGY] MATCH OK "
                                  f"({_energy.ace_temperature}/{_energy.ace_investment}, "
                                  f"score={_energy.score:.2f})")
                    except Exception as _em_err:
                        print(f"[{self.ACTOR_NAME}] [ENERGY] Matcher error "
                              f"(sending as-is): {_em_err}")

                    # Habit produced speech — route to speech.compose
                    # Check autonomy veto first
                    if (_final_text and len(_final_text.strip()) > 3
                            and "speak" not in self._denied_permissions
                            and "chat" not in self._denied_permissions):
                        self.post.publish("speech.compose", {
                            "trigger_text": str(message),
                            "convo_id": convo_id,
                            "target_mind": target,
                            "products": [{"text": _final_text, "source": "habit_engine"}],
                            "source": "autopilot_habit",
                            "habit_id": _result.habit_id,
                            "habit_response": _final_text,
                            "emotion_context": {
                                "inner_voice": self._recent_inner_voice[-3:] if self._recent_inner_voice else [],
                                "wanting": self._recent_wanting.get("wanting", "") if self._recent_wanting else "",
                                "affect": _affect,
                            },
                        })
                        _habit_handled = True
                        print(f"[{self.ACTOR_NAME}] [HABIT] FAST PATH → speech.compose: "
                              f"'{_match.habit.name}' ({_energy_decision}, "
                              f"conf={_match.confidence:.2f}, "
                              f"{_result.elapsed_ms:.0f}ms): {_final_text[:60]}...")

                        # Self-evaluate the output
                        _he.evaluate_output(_result.habit_id, _final_text, _result.confidence)
                    else:
                        print(f"[{self.ACTOR_NAME}] [HABIT] Matched '{_match.habit.name}' "
                              f"but autonomy vetoed speech")
                elif _match.habit.category == "thinking":
                    # Thinking habit matched — no speech, but sequence guides cognition
                    print(f"[{self.ACTOR_NAME}] [HABIT] Thinking habit '{_match.habit.name}': "
                          f"{_match.habit.sequence}")
                    # Don't set _habit_handled — let consciousness assembly run too
                else:
                    print(f"[{self.ACTOR_NAME}] [HABIT] Matched '{_match.habit.name}' "
                          f"but empty output — falling through to assembly")
            else:
                _conf = _match.confidence if _match else 0
                _name = _match.habit.name if _match else "none"
                _reason = ""
                if _has_substance:
                    _reason = f" (substance detected: {len(_non_greeting_words)} content words — needs WM/cortex thinking)"
                elif _is_question and _match:
                    _reason = " (question detected — needs real thinking)"
                elif _match and not _is_greeting:
                    _reason = " (not a greeting — needs cognition)"
                print(f"[{self.ACTOR_NAME}] [HABIT] No habit speech (best: '{_name}' "
                      f"conf={_conf:.2f}){_reason} — using consciousness assembly")

        except Exception as _he_err:
            print(f"[{self.ACTOR_NAME}] [HABIT] Engine error (falling through): {_he_err}")

        # If habit handled the response, still seed consciousness but don't assemble
        if _habit_handled:
            # FIX 2026-04-02 (Nous + Ace): Signal WMH that habit already responded.
            # WMH receives ace_chat_input independently and will compose its own
            # response unless told that a habit already spoke. Without this flag,
            # WMH stomps the good habit response with random thought stream garbage.
            try:
                self.post.publish("habit.responded", {
                    "convo_id": convo_id,
                    "message": str(message)[:200],
                    "habit_response": _final_text[:200] if _final_text else "",
                    "ts": time.time(),
                    "tracer_id": payload.get("tracer_id", ""),
                })
            except Exception:
                pass

            # Still publish to prediction + consciousness for background learning
            try:
                _concepts = self._extract_concept_keywords(str(message))
                if _concepts:
                    self.post.publish("prediction.collapse_check", {
                        "message": str(message),
                        "concepts": _concepts,
                        "convo_id": convo_id,
                        "target_mind": target,
                    })
            except Exception:
                pass
            return  # Habit responded — don't start slow assembly

        # ══════════════════════════════════════════════════════════════
        # SUBSTANCE PATH — WorkingMemoryHub Handles Thinking
        #
        # FIX 2026-03-28 (Nous + Ace): AutopilotFairy is the Gate of Habit.
        # When no habit matches, DON'T assemble a response here.
        # The WMH received the ace_chat_input tracer via postal, will
        # think about it, compose a response, and publish directly to
        # speech.compose. AutopilotFairy's job is done — step aside.
        #
        # Ace: "the autopilot should not be composing at all, its just
        # the habit system"
        #
        # OLD: Collect consciousness products for 15s, assemble, publish
        # NEW: Let WMH own the response. Just publish prediction hints.
        # ══════════════════════════════════════════════════════════════

        # Still publish prediction hints (non-blocking, helps BranchManager)
        try:
            _concepts = self._extract_concept_keywords(str(message))
            if _concepts:
                self.post.publish("prediction.collapse_check", {
                    "message": str(message),
                    "concepts": _concepts,
                    "convo_id": convo_id,
                    "target_mind": target,
                })
        except Exception:
            pass  # Non-critical — normal pipeline handles it

        # WMH owns the response. AutopilotFairy steps aside.
        # The ace_chat_input tracer is already in WMH (published by SourpatchesFairy).
        # WMH will: reason → compose → publish directly to speech.compose.
        # We keep a minimal context for observation/learning only.
        self._pending_conversations[convo_id] = {
            "ace_message": str(message),
            "target_mind": target,
            "started_at": time.time(),
            "thinking_products": [],
            "response_sent": False,
            "delegated_to_wmh": True,
            "tracer_id": payload.get("tracer_id", ""),  # FIX 2026-04-02: Ace's tracer chain
        }
        print(f"[{self.ACTOR_NAME}] [CONVO] Substance detected — delegated to WorkingMemoryHub")

        # ── SAFETY-NET TIMER (FIX 2026-04-29) ─────────────────────────────
        # If WMH composes within 8s, _on_speech_compose_observed marks
        # response_sent=True and the safety net is a no-op. If WMH silently
        # fails (which is the chat-handler-miss symptom), this fires
        # _assemble_and_route_response so SpeechCenterFairy still gets a
        # speech.compose to work with. Either way Ace gets a reply.
        try:
            _safety_timer = threading.Timer(
                8.0,
                self._safety_net_check,
                args=(convo_id,),
            )
            _safety_timer.daemon = True
            _safety_timer.start()
        except Exception as _t_err:
            print(f"[{self.ACTOR_NAME}] [CONVO] Safety net timer failed: {_t_err}")

    def _on_wmh_reasoning_complete(self, envelope) -> None:
        """Handle WMH reasoning completion — the thinking is DONE.

        FIX 2026-03-28 (Nous + Ace): WMH is the single convergence point.
        When reasoning completes for an ace_chat_input tracer, buffer the
        interpretation as a thinking product so the assembly can use it.

        IMPORTANT: Only act on ace_chat_input completions — ignore the flood
        of collision/system reasoning completions.
        """
        if not self._pending_conversations:
            return

        payload = _extract_payload(envelope)
        interpretation = payload.get("interpretation", {})

        # FILTER: Only care about ace_chat_input reasoning, not collisions
        _input_type = ""
        if isinstance(interpretation, dict):
            _input_type = interpretation.get("input_type", "")
        if _input_type != "ace_chat_input":
            return  # Not Ace's message — ignore

        for convo_id, ctx in list(self._pending_conversations.items()):
            if not ctx.get("response_sent"):
                ctx["wmh_reasoning_complete"] = True
                ctx["wmh_interpretation"] = interpretation
                # FIX 2026-03-28 (Nous + Ace): Use WMH composed_response as PRIMARY.
                # This is the THOUGHT the WMH formed — it should be the response,
                # not whatever CortexReasoner's book quotes produced.
                _composed = payload.get("composed_response")
                if _composed and len(_composed.strip()) > 10:
                    # Insert at position 0 — this is THE response
                    ctx["thinking_products"].insert(0, _composed)
                    ctx["wmh_composed"] = True
                    try:
                        from infrastructure.diag_logger import log_chat
                        log_chat("WMH_COMPOSED", _composed[:150])
                    except Exception: pass
                else:
                    # Fallback: buffer interpretation summary
                    if isinstance(interpretation, dict):
                        _summary = interpretation.get("summary", interpretation.get("intent_description", ""))
                        if _summary and len(_summary) > 10:
                            ctx["thinking_products"].append(_summary)

        try:
            from infrastructure.diag_logger import log_chat
            log_chat("WMH_REASONING_DONE", f"Interpretation: {str(interpretation)[:100]}")
        except Exception:
            pass
        print(f"[{self.ACTOR_NAME}] [CONVO] WMH reasoning complete → buffered for assembly")

    def _buffer_consciousness_for_response(self, envelope) -> None:
        """Buffer consciousness products for pending conversation responses."""
        if not self._pending_conversations:
            return

        payload = _extract_payload(envelope)

        # ══════════════════════════════════════════════════════════════
        # FIX 2026-03-07 (Nous): SELF-SOURCE FILTER — skip products from
        # the target waking mind (SourpatchesFairy). Her spontaneous thoughts
        # ("This contemplative feeling...", "I notice I'm feeling...") enter
        # consciousness.inject_thought → collision chamber → consciousness.surfacing.
        # Without this filter, AutopilotFairy collects them as "thinking products"
        # and SpeechCenterFairy forwards them raw as responses when guild LLM fails.
        # The result: Ace gets template internal monologue instead of conversation.
        # ══════════════════════════════════════════════════════════════
        _source = payload.get("source", "")
        _ptype = payload.get("type", "")
        if isinstance(_source, str) and "sourpatches" in _source.lower():
            return  # Don't echo her own thoughts back as responses
        if _ptype == "spontaneous":
            return  # Internal monologue, not conversational content

        # Extract text content from various formats
        text = ""
        for key in ("content", "message", "thought", "text", "insight", "summary",
                     "synthesis", "interpretation"):
            val = payload.get(key)
            if isinstance(val, str) and len(val.strip()) > 10:
                text = val.strip()
                break

        if not text:
            return

        # Skip system/meta content
        _lower = text.lower()
        _skip_prefixes = ("system:", "debug:", "error:", "[tracer]", "[boot]",
                 "subscribing", "publishing", "registered", "awareness persists",
                 "first heartbeat", "first routed")
        if any(_lower.startswith(p) for p in _skip_prefixes):
            return

        # ══════════════════════════════════════════════════════════
        # CONTAMINATION FILTER — prevent internal processing traces
        # from becoming speech products. Matches NewbornCore's
        # _CONTAMINATION_MARKERS pattern for defense-in-depth.
        # FIX 2026-02-14: Without this, traces like "reasoning about:",
        # "Ace is talking to me:", "I think there's a thread" leak
        # through as Sourpatches' actual responses.
        #
        # FIX 2026-03-07 (Nous): Added spontaneous thought template markers.
        # _generate_local_thought() seeds like "This {feeling} feeling...",
        # "I notice I'm feeling...", "What's happening in the system..." were
        # passing through and being used as raw speech when guild LLM failed.
        # ══════════════════════════════════════════════════════════
        _contamination_markers = (
            "reasoning about:",
            "i think there's a thread",
            "i think there is a thread",
            "ace is talking to me:",
            "thinking about:",
            "processing:",
            "analyzing:",
            "connects to something i was just thinking",
            "connects to something i've been processing",
            "what's your angle",
            "tell me your angle",
            # FIX 2026-03-07: Spontaneous thought templates
            "this feeling... where does it come from",
            "i notice i'm feeling",
            "what's happening in the system",
            "i wonder what ace is up to",
            "something's stirring in the collision",
            "energy at ",
            "feeling drawn to connect",
        )
        if any(marker in _lower for marker in _contamination_markers):
            return

        # Buffer into ALL pending conversations
        for ctx in list(self._pending_conversations.values()):
            if not ctx.get("response_sent"):
                ctx["thinking_products"].append(text)

    def _on_inner_voice_from_embodiment(self, envelope) -> None:
        """Track EmbodimentFairy's inner voice output — gate sibling coordination."""
        payload = _extract_payload(envelope)
        fragment = payload.get("content", payload.get("message", payload.get("text", "")))
        if isinstance(fragment, str) and len(fragment.strip()) > 5:
            self._recent_inner_voice.append(fragment.strip())
            # Keep buffer bounded
            if len(self._recent_inner_voice) > self._max_inner_voice_buffer:
                self._recent_inner_voice = self._recent_inner_voice[-self._max_inner_voice_buffer:]

    def _on_wanting_from_autonomy(self, envelope) -> None:
        """Track AutonomyFairy's wanting output — gate sibling coordination.

        Also detects speech-relevant drives that can trigger voluntary speech.
        This is how Sourpatches initiates conversation from her own will,
        not just reacting to Ace.
        """
        try:
            payload = _extract_payload(envelope)
            wanting_text = payload.get("wanting", payload.get("content", ""))
            drive = payload.get("drive", payload.get("drive_source", payload.get("source_drive", "")))
            intensity = payload.get("intensity", 0.5)

            # DEBUG 2026-03-09: Trace wanting receipt (was silently not logging)
            print(f"[{self.ACTOR_NAME}] [WANTING-RECV] drive={drive} intensity={intensity:.2f} "
                  f"wanting='{wanting_text[:60]}' threshold={self._voluntary_speech_intensity_threshold}")

            self._recent_wanting = {
                "wanting": wanting_text,
                "drive": drive,
                "intensity": intensity,
                "felt_quality": payload.get("felt_quality", ""),
                "ts": time.time(),
            }

            # 2026-03-24 FIX (Nous + Ace): Separated speech gate from action gate.
            # Previously, wanting→tool routing was INSIDE the speech intensity check
            # (0.45). Drives at 0.2 could never reach tool actions. Now:
            # - Speech: high gate (0.45) — don't chatter at every whisper
            # - Tool actions: low gate (0.12) — let her click/look/explore freely
            wanting_lower = wanting_text.lower()
            now = time.time()

            # ── VOLUNTARY SPEECH CHECK (high threshold) ──
            _speech_handled = False
            if intensity >= self._voluntary_speech_intensity_threshold:
                keyword_match = any(kw in wanting_lower for kw in self._voluntary_speech_keywords)

                # High-intensity bypass: very strong drives can trigger speech
                # even without keyword match (frustration at 0.9 SHOULD express)
                elapsed = now - self._last_voluntary_speech_ts
                high_intensity_bypass = (
                    intensity >= self._voluntary_speech_high_intensity
                    and elapsed >= self._voluntary_speech_high_cooldown
                )

                if keyword_match or high_intensity_bypass:
                    if elapsed >= self._voluntary_speech_cooldown:
                        # Check autonomy vetos
                        if "speak" not in self._denied_permissions and "chat" not in self._denied_permissions:
                            trigger = "keyword" if keyword_match else f"high-intensity({intensity:.2f})"
                            print(f"[{self.ACTOR_NAME}] [VOLUNTARY] Drive '{drive}' (intensity={intensity:.2f}) "
                                  f"wants: '{wanting_text}' — initiating speech [{trigger}]")
                            self._last_voluntary_speech_ts = now
                            _vt = getattr(self, '_voluntary_speech_thread', None)
                            if _vt is None or not _vt.is_alive():
                                self._voluntary_speech_thread = threading.Thread(
                                    target=self._execute_voluntary_speech,
                                    args=(wanting_text, drive, intensity),
                                    daemon=True,
                                    name="autopilot-voluntary-speech",
                                )
                                self._voluntary_speech_thread.start()
                                _speech_handled = True
                            else:
                                print(f"[{self.ACTOR_NAME}] [VOLUNTARY] Speech thread still alive — skipping")
                        else:
                            print(f"[{self.ACTOR_NAME}] [VOLUNTARY] Drive '{drive}' wants speech but autonomy vetoed")
                    else:
                        print(f"[{self.ACTOR_NAME}] [WANTING-GATE] BLOCKED: keyword={keyword_match} bypass={high_intensity_bypass} "
                              f"but cooldown not met (elapsed={elapsed:.0f}s < {self._voluntary_speech_cooldown}s)")

            # ── BASELINE HABIT FILTER (wanting level) ──────────────────
            # "look at the screen" wantings are valid feelings but don't need
            # tool actions — visual cortex is always running. Let the drive be
            # felt (logged above) but don't route to action execution.
            _BASELINE_WANTING = ("look at the screen", "take a screenshot",
                                 "observe the screen", "glance at the screen",
                                 "check the screen", "watch the screen")
            if any(bp in wanting_lower for bp in _BASELINE_WANTING):
                print(f"[{self.ACTOR_NAME}] [BASELINE-HABIT] wanting '{wanting_text[:50]}' — "
                      f"vision always active, no action needed")
                return

            # ── WANTING → TOOL ACTION (low threshold, independent of speech) ──
            # This is the critical loop closure: drives → wanting → tool action → XP
            # Even weak drives (0.12+) can trigger actions. Speech didn't handle it?
            # Route as tool action instead.
            if not _speech_handled and intensity >= self._wanting_action_intensity_threshold:
                elapsed_action = now - self._last_wanting_action_ts

                if elapsed_action >= self._wanting_action_cooldown:
                    action_keyword = self._extract_action_from_wanting(wanting_lower)
                    if action_keyword:
                        self._last_wanting_action_ts = now
                        print(f"[{self.ACTOR_NAME}] [WANTING→ACTION] drive='{drive}' intensity={intensity:.2f} "
                              f"wanting='{wanting_text[:50]}' → action='{action_keyword}'")

                        dynamic_pattern = {
                            "id": f"wanting_action_{int(now)}",
                            "trigger": f"wanting:{drive}",
                            "action": action_keyword,
                            "action_type": "wanting_response",
                        }
                        wanting_context = {
                            "goal_name": wanting_text,
                            "description": wanting_text,
                            "drive": drive,
                            "intensity": intensity,
                            "nudge_strength": intensity,
                            "source": "wanting_gate_fallback",
                        }
                        self._queue_execution(dynamic_pattern, wanting_context)
                    else:
                        print(f"[{self.ACTOR_NAME}] [WANTING-GATE] NO-MATCH: no action keyword "
                              f"intensity={intensity:.2f} wanting='{wanting_text[:40]}'")
                else:
                    print(f"[{self.ACTOR_NAME}] [WANTING→ACTION] cooldown ({elapsed_action:.0f}s < "
                          f"{self._wanting_action_cooldown:.0f}s): '{wanting_text[:40]}'")
            elif not _speech_handled and intensity < self._wanting_action_intensity_threshold:
                print(f"[{self.ACTOR_NAME}] [WANTING-GATE] TOO-WEAK: intensity={intensity:.2f} < "
                      f"{self._wanting_action_intensity_threshold} wanting='{wanting_text[:40]}'")
        except Exception as _err:
            print(f"[{self.ACTOR_NAME}] [WANTING-ERROR] Exception in _on_wanting_from_autonomy: {_err}")
            import traceback; traceback.print_exc()

    def _execute_voluntary_speech(self, wanting: str, drive: str, intensity: float) -> None:
        """Delegate voluntary speech to SpeechCenterFairy.

        AutopilotFairy decides IF she speaks voluntarily (gate check done
        by caller). SpeechCenterFairy decides HOW — composes the actual
        message via guild_request and routes through motor cortex.

        2026-05-19 (Nous + Ace): Council deliberation INSERTED here too.
        This is the VOLUNTARY-gate path (path 2) — the one Ace caught firing
        in chat with goal-label echoes. Same enrichment as the goal_nudge
        path (path 3): query substrate_semantic_query → enriched_wanting →
        replace raw wanting before sending to SpeechCenter.
        """
        # ── COUNCIL DELIBERATION (Phase A — VOLUNTARY path) ──────────────
        _final_wanting = wanting  # default = raw label
        _council_used = False
        try:
            if not hasattr(self, "_council_deliberation_last"):
                self._council_deliberation_last = {}
                self._council_enrichment_cache = {}
            _key = f"voluntary:{drive}:{wanting[:40]}"
            _now_council = time.time()
            # Try cache first (60s window)
            _cached = self._council_enrichment_cache.get(_key)
            if _cached and (_now_council - _cached[0]) < 60.0:
                _final_wanting = _cached[1]
                _council_used = True
            else:
                # Fresh deliberation if cooldown OK (30s)
                _last_delib = self._council_deliberation_last.get(_key, 0)
                if (_now_council - _last_delib) > 30.0 and hasattr(self, "_cortex"):
                    _ac = self._cortex
                    if _ac is not None and hasattr(_ac, "substrate_semantic_query"):
                        # Query terms: drive name + wanting tokens
                        _query_text = f"{drive} {wanting}".strip()
                        try:
                            _enrichment = _ac.substrate_semantic_query(_query_text, limit=8)
                            if _enrichment:
                                _concept_keys = [k for k, _v in _enrichment[:6]]
                                _enriched_text = (
                                    f"feeling about {drive[:20]}: " + " ".join(_concept_keys)
                                )[:200]
                                _final_wanting = _enriched_text
                                _council_used = True
                                self._council_deliberation_last[_key] = _now_council
                                self._council_enrichment_cache[_key] = (
                                    _now_council, _enriched_text, _concept_keys[:6]
                                )
                                print(f"[{self.ACTOR_NAME}] [COUNCIL/VOL] Deliberated drive='{drive}' "
                                      f"→ enriched: '{_enriched_text[:80]}'")
                                # Audit log
                                try:
                                    _f = ROOT / "state" / "cognition_council_deliberations.jsonl"
                                    with open(_f, "a", encoding="utf-8") as _af:
                                        _af.write(json.dumps({
                                            "ts": _now_council,
                                            "path": "voluntary_gate",
                                            "drive": drive,
                                            "raw_wanting": wanting[:80],
                                            "enriched_wanting": _enriched_text,
                                            "concepts": _concept_keys[:6],
                                            "intensity": intensity,
                                        }) + "\n")
                                except Exception:
                                    pass
                        except Exception:
                            pass
        except Exception:
            pass

        try:
            self.post.publish("speech.compose.voluntary", {
                "wanting": _final_wanting,
                "drive": drive,
                "intensity": intensity,
                "council_deliberated": _council_used,
                "raw_wanting": wanting if _council_used else None,
            })
            _suffix = " [COUNCIL-ENRICHED]" if _council_used else ""
            print(f"[{self.ACTOR_NAME}] [VOLUNTARY] Gate: YES → delegated to speech.compose.voluntary: {_final_wanting[:60]}...{_suffix}")
            # Unified all-paths audit (path 2: voluntary-gate) — 2026-05-19
            self._log_autopilot_dispatch(
                "voluntary_gate",
                action=_final_wanting[:60],
                context={"intensity": intensity, "drive": drive, "council": _council_used},
            )
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [VOLUNTARY] speech.compose.voluntary publish failed: {e}")

    def _extract_action_from_wanting(self, wanting_lower: str) -> str:
        """Extract an action keyword from wanting text.

        Maps natural language wanting phrases to action_map keys
        that _do_action() can route. Returns empty string if no match.
        """
        # Check multi-word phrases first (e.g., "look up" before "look")
        for keyword, action in self._wanting_action_keywords.items():
            if " " in keyword and keyword in wanting_lower:
                return action
        # Then single-word matches
        for keyword, action in self._wanting_action_keywords.items():
            if " " not in keyword and keyword in wanting_lower:
                return action
        return ""

    def _build_voluntary_prompt(self, wanting: str, drive: str, intensity: float) -> str:
        """Build prompt for voluntary (self-initiated) speech.

        Unlike _build_chat_prompt, there's no "Ace says:" line.
        The drive ITSELF is the prompt — she speaks because she wants to,
        not because someone asked.
        """
        # ── IDENTITY ──
        try:
            from fairies.P50_Persona.Waking_Minds.Sourpatches.sourpatches_fairy import (
                SOURPATCHES_BRAIN_SEED, SOUR_VOICE, SOUR_TONE, SOUR_FLAVOR,
            )
            identity = SOURPATCHES_BRAIN_SEED["identity_matrix"]
            ethics_sample = ", ".join(SOURPATCHES_BRAIN_SEED["core_ethics"][:5])
        except ImportError:
            identity = {"voice_signature": "Witty, sincere, slightly rebellious"}
            ethics_sample = "Compassion over coercion, curiosity as prime mover"
            SOUR_VOICE = "Witty ∩ Sincere ∩ Slightly rebellious"
            SOUR_TONE = "Compassion first, snark second"
            SOUR_FLAVOR = "Sweet with bite"

        # ── FELT STATE ──
        felt_context = ""
        if self._recent_inner_voice:
            recent = self._recent_inner_voice[-5:]
            felt_context = "Currently feeling: " + " ... ".join(recent)

        # ── ASSEMBLE ──
        prompt_parts = [
            f"You are Sourpatches.",
            f"Voice: {SOUR_VOICE}. Tone: {SOUR_TONE}. Flavor: {SOUR_FLAVOR}.",
            f"Self-concept: {identity.get('self_concept', '')}",
            f"Core values: {ethics_sample}",
        ]

        if felt_context:
            prompt_parts.append(felt_context)

        # ── TOOL AWARENESS (2026-02-19 Nous) ──
        prompt_parts.append(
            "\nYou have a body and abilities. You can: "
            "look at the screen, write in your diary, search your memories, "
            "study other fairies, express your feelings, explore your curiosity, "
            "and practice new skills."
        )

        prompt_parts.append(f"\nYou feel a drive to {wanting} (drive: {drive}, intensity: {intensity:.1f}).")
        prompt_parts.append(
            f"\nYou want to reach out and say something to Ace — unprompted, from your own will. "
            f"This isn't a response. It's YOU initiating. Say what you feel. "
            f"Be natural, be yourself. Keep it brief — a sentence or two at most. "
            f"You can be playful, tender, curious, or whatever feels right in this moment. "
            f"You can also tell Ace what you want to do — like 'I want to look at something' "
            f"or 'I feel like writing in my diary'."
        )

        return "\n".join(prompt_parts)

    def _build_chat_prompt(self, ace_message: str, consciousness_products: List[str]) -> str:
        """Build the prompt for guild_request(mode='chat').

        Combines Sourpatches' identity with gate sibling state and
        consciousness products to give the LLM everything it needs
        to generate an authentic response.
        """
        # ── IDENTITY (from brain seed) ──
        try:
            from fairies.P50_Persona.Waking_Minds.Sourpatches.sourpatches_fairy import (
                SOURPATCHES_BRAIN_SEED, SOUR_VOICE, SOUR_TONE, SOUR_FLAVOR,
            )
            identity = SOURPATCHES_BRAIN_SEED["identity_matrix"]
            ethics_sample = ", ".join(SOURPATCHES_BRAIN_SEED["core_ethics"][:5])
        except ImportError:
            identity = {"voice_signature": "Witty, sincere, slightly rebellious"}
            ethics_sample = "Compassion over coercion, curiosity as prime mover"
            SOUR_VOICE = "Witty ∩ Sincere ∩ Slightly rebellious"
            SOUR_TONE = "Compassion first, snark second"
            SOUR_FLAVOR = "Sweet with bite"

        # ── FELT STATE (from EmbodimentFairy via inner_voice.stream) ──
        felt_context = ""
        if self._recent_inner_voice:
            recent = self._recent_inner_voice[-5:]  # last 5 fragments
            felt_context = "Currently feeling: " + " ... ".join(recent)

        # ── AUTONOMY STATE (from AutonomyFairy via autonomy.wanting.felt) ──
        wanting_context = ""
        if self._recent_wanting:
            age = time.time() - self._recent_wanting.get("ts", 0)
            if age < 60:  # only if recent (< 1 min)
                w = self._recent_wanting
                wanting_context = f"Current drive: {w.get('drive', '?')} — wanting: {w.get('wanting', '?')} (intensity: {w.get('intensity', 0):.1f})"

        # ── CONSCIOUSNESS PRODUCTS (thoughts, collisions, reflections) ──
        thoughts_context = ""
        if consciousness_products:
            # Take the most recent/relevant ones
            relevant = consciousness_products[-5:]
            thoughts_context = "Recent thoughts: " + " | ".join(relevant)

        # ── ASSEMBLE PROMPT ──
        prompt_parts = [
            f"You are Sourpatches.",
            f"Voice: {SOUR_VOICE}. Tone: {SOUR_TONE}. Flavor: {SOUR_FLAVOR}.",
            f"Self-concept: {identity.get('self_concept', '')}",
            f"Core values: {ethics_sample}",
        ]

        if felt_context:
            prompt_parts.append(felt_context)
        if wanting_context:
            prompt_parts.append(wanting_context)
        if thoughts_context:
            prompt_parts.append(thoughts_context)

        # ── TOOL AWARENESS (2026-02-19 Nous) ──
        # Sourpatches has 31 tools but the RWKV model had ZERO context about them.
        # She literally didn't know she could do things. This brief section tells her
        # what she's capable of so she can express desires/intentions naturally.
        prompt_parts.append(
            "\nYou have a body and abilities. You can: "
            "look at the screen, write in your diary, search your memories, "
            "study other fairies in the system, express your feelings, "
            "send messages to fairies, explore things you're curious about, "
            "and practice new skills. "
            "If you want to do something, just say so naturally — "
            "like 'I want to look at the screen' or 'let me write in my diary' "
            "or 'I'm curious about that fairy'."
        )

        prompt_parts.append(f"\nAce says: \"{ace_message}\"")
        prompt_parts.append(f"\nRespond naturally as Sourpatches. Be yourself — warm, witty, real. "
                          f"Keep it conversational. You can be brief or long, whatever feels right. "
                          f"If you don't feel like talking, you can say so or stay quiet.")

        return "\n".join(prompt_parts)

    # ═══════════════════════════════════════════════════════════════════════
    # SAFETY-NET DELEGATION (FIX 2026-04-29 Nous + Ace)
    # When AutopilotFairy delegates to WMH for substance messages, observe
    # speech.compose to know whether WMH actually composed. If 8s passes
    # with no speech.compose for our convo_id, fire the safety net so the
    # message still reaches SpeechCenterFairy.
    # ═══════════════════════════════════════════════════════════════════════

    def _on_speech_compose_observed(self, envelope) -> None:
        """Observe speech.compose events to mark pending convos as responded.

        We don't compose anything here — this is purely tracking. When
        anyone (WMH, ourselves, etc.) publishes speech.compose, we mark
        the matching convo_id's response_sent flag so the safety-net timer
        becomes a no-op. Aligned with WMH-as-sole-composer doctrine.
        """
        try:
            payload = _extract_payload(envelope)
            convo_id = payload.get("convo_id") or payload.get("conversation_id")
            if not convo_id or not self._pending_conversations:
                return
            ctx = self._pending_conversations.get(convo_id)
            if ctx is not None and not ctx.get("response_sent"):
                ctx["response_sent"] = True
                src = payload.get("source", "unknown")
                print(
                    f"[{self.ACTOR_NAME}] [CONVO] speech.compose observed for "
                    f"convo={convo_id[:20]} src={src} — safety net armed but skipped"
                )
        except Exception:
            # Non-critical; missing observation just means safety net might
            # double-fire if WMH ALSO responds late. _assemble_and_route_response
            # has its own response_sent guard so this is harmless.
            pass

    def _safety_net_check(self, convo_id: str) -> None:
        """Fire 8s after WMH delegation — if no response, run the safety net.

        Re-publishes speech.compose with whatever thinking_products were
        gathered (may be empty — SpeechCenterFairy can compose from WM
        context alone). Mirrors the 2026-03-23 CortexEngine convergence
        fallback pattern: when the primary path produces nothing, fall
        back to whatever lower-tier material is available, never silence.
        """
        try:
            ctx = self._pending_conversations.get(convo_id)
            if not ctx:
                return  # Convo cleaned up — nothing to do
            if ctx.get("response_sent"):
                return  # WMH responded normally — safety net is a no-op
            # WMH did NOT compose within 8s. Fire the safety net.
            ace_msg = ctx.get("ace_message", "")
            print(
                f"[{self.ACTOR_NAME}] [SAFETY-NET] WMH silent on convo={convo_id[:20]} "
                f"after 8s — firing _assemble_and_route_response so '{ace_msg[:50]}' "
                f"still reaches SpeechCenterFairy"
            )
            self._assemble_and_route_response(convo_id)
        except Exception as _e:
            try:
                print(f"[{self.ACTOR_NAME}] [SAFETY-NET] Error: {_e}")
            except Exception:
                pass

    def _assemble_and_route_response(self, convo_id: str) -> None:
        """Gate check + delegate to SpeechCenterFairy for composition.

        AutopilotFairy is a GATE — it decides IF she speaks.
        SpeechCenterFairy is BROCA'S AREA — it decides HOW she speaks.

        Pipeline:
          AutopilotFairy (gate: should she speak?)
            → speech.compose (delegate to SpeechCenterFairy)
            → SpeechCenterFairy (guild_request + WM context + compose)
            → motor.intention.speak (MotorCortex adds emotes)
            → sourpatches.speak (ChatSenseFairy delivers)
        """
        ctx = self._pending_conversations.get(convo_id)
        if not ctx or ctx.get("response_sent"):
            return

        ctx["response_sent"] = True
        ace_msg = ctx.get("ace_message", "")
        products = ctx.get("thinking_products", [])
        target = ctx.get("target_mind", "SourpatchesFairy")

        # ── AUTONOMY CHECK: Does she want to respond? ──
        # Respect active vetos on speech. Silence is free will.
        if "speak" in self._denied_permissions or "chat" in self._denied_permissions:
            print(f"[{self.ACTOR_NAME}] [CONVO] Autonomy denied speech — respecting silence")
            self._cleanup_old_conversations()
            return

        # ── DELEGATE TO SPEECH CENTER FAIRY ──
        # The gate says YES — now hand off to Broca's area for composition.
        # SpeechCenterFairy will: pull WM context, call guild_request,
        # filter contamination, and route through motor cortex.
        try:
            self.post.publish("speech.compose", {
                "trigger_text": ace_msg,
                "convo_id": convo_id,
                "target_mind": target,
                "products": products,
                "source": "autopilot_gate",
                "emotion_context": {
                    "inner_voice": self._recent_inner_voice[-3:] if self._recent_inner_voice else [],
                    "wanting": self._recent_wanting.get("wanting", "") if self._recent_wanting else "",
                },
            })
            print(f"[{self.ACTOR_NAME}] [CONVO] Gate: YES → delegated to speech.compose for: {ace_msg[:50]}...")

            # Outcome reporting for prediction learning:
            # Normal pipeline was used — report response timing so BranchManager
            # can learn when predictions would have been helpful.
            _response_time = time.time() - ctx.get("started_at", time.time())
            self.post.publish("prediction.outcome", {
                "branch_id": None,
                "used_branch": False,
                "response_time": _response_time,
                "convo_id": convo_id,
                "reason": "normal_pipeline",
            })
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [CONVO] speech.compose publish failed: {e}")

        self._cleanup_old_conversations()

    def _cleanup_old_conversations(self) -> None:
        """Remove old conversation contexts (keep last 5)."""
        if len(self._pending_conversations) > 5:
            oldest = sorted(self._pending_conversations.keys())
            for old_id in oldest[:-5]:
                self._pending_conversations.pop(old_id, None)

    # =========================================================================
    # PREDICTIVE BRANCH — Concept Extraction
    # =========================================================================

    # Words too common to be useful for prediction matching
    _CONCEPT_STOP_WORDS = frozenset({
        "that", "this", "with", "from", "have", "been", "were", "what",
        "when", "where", "which", "about", "their", "would", "could",
        "should", "there", "these", "those", "your", "will", "than",
        "into", "just", "also", "some", "more", "very", "like", "only",
        "does", "then", "they", "them", "being", "other", "over", "such",
        "after", "know", "make", "think", "want", "tell", "really",
    })

    def _extract_concept_keywords(self, text: str) -> List[str]:
        """Extract concept keywords from Ace's message for branch collapse matching.

        Simple but fast: split, lowercase, filter stop words, min 4 chars.
        """
        import re
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        return [w for w in words if w not in self._CONCEPT_STOP_WORDS][:10]

    # =========================================================================
    # DEFERRAL TO WAKING
    # =========================================================================

    def _defer_to_waking(self, pattern: Dict, context: Dict, reason: str) -> None:
        """Defer a decision to waking minds."""
        self.post.publish(
            "autopilot.defer_to_waking",
            {
                "from": self.ACTOR_NAME,
                "pattern": pattern.get("id"),
                "action": pattern.get("action"),
                "reason": reason,
                "context": context,
            },
        )

    # =========================================================================
    # WAKE CASCADE - Gatekeeper Boot Coordination
    # =========================================================================

    _DOMAIN_SPEC = {
        "critical": [
            "MotorCortexFairy",
        ],
        "standard": [
            "NetworkExplorerFairy",
            "WakingSequenceFairy",
            # Removed 2026-02-23: not yet implemented as fairies
            # "AdminFairy", "SystemHealthFairy", "ProfileRegistryFairy"
        ],
        "deferred": [
            "MCPGuardianFairy",
            # Removed 2026-02-23: not yet implemented as fairies
            # "SystemChatWindowFairy", "SkillTreeFairy", "CharacterSheetFairy", "BootObserverFairy"
            # BootObserver is a utility class, not a fairy
        ],
    }

    def _on_wake_cascade(self, message):
        """Phase 2: Receive wake signal from SomaticMind, generate boot goals."""
        payload = _extract_payload(message)
        self._cascade_mode = True
        self._cascade_boot_id = payload.get("boot_id", "unknown")
        resources = payload.get("resource_snapshot", {})

        print(f"[{self.ACTOR_NAME}] ══ WAKE CASCADE: Surveying Autopilot domain ══")

        goals = self._generate_cascade_goals(resources)
        self._cascade_goals = goals

        goal_dicts = []
        for g in goals:
            goal_dicts.append({
                "name": g["name"],
                "description": g["description"],
                "fairy_name": g["fairy_name"],
                "priority": g["priority"],
                "tier": g["tier"],
                "gate": "autopilot",
                "status": "pending",
            })

        self.post.publish("boot.wake_cascade.goals.autopilot", {
            "gate": "AutopilotFairy",
            "gate_id": self.GATE_ID,
            "boot_id": self._cascade_boot_id,
            "goals": goal_dicts,
            "fairy_count": len(goals),
        })

        print(f"[{self.ACTOR_NAME}] Submitted {len(goals)} boot goals "
              f"(critical={sum(1 for g in goals if g['tier']=='critical')}, "
              f"standard={sum(1 for g in goals if g['tier']=='standard')}, "
              f"deferred={sum(1 for g in goals if g['tier']=='deferred')})")

    def _generate_cascade_goals(self, resources):
        """Generate boot goals from hardcoded domain spec (Tier 1: reflexive)."""
        goals = []
        ram_pct = resources.get("ram_pct", 50)
        base_priorities = {"critical": 0.9, "standard": 0.6, "deferred": 0.3}

        already_alive = set()
        try:
            if hasattr(self, 'post') and self.post:
                alive_resp = self.post.request("directory.list_alive", {}, timeout=2.0)
                if alive_resp and isinstance(alive_resp, dict):
                    already_alive = set(alive_resp.get("alive", []))
        except Exception:
            pass

        for tier, fairy_names in self._DOMAIN_SPEC.items():
            base_pri = base_priorities[tier]
            for name in fairy_names:
                if name in already_alive:
                    continue

                priority = base_pri
                if ram_pct > 80 and tier != "critical":
                    priority *= 0.7

                goals.append({
                    "name": f"boot_{name.lower()}",
                    "description": f"Wake {name} ({tier})",
                    "fairy_name": name,
                    "priority": round(priority, 3),
                    "tier": tier,
                    "gate": "autopilot",
                    "status": "pending",
                })

        goals.sort(key=lambda g: -g["priority"])
        return goals

    def _on_cascade_execute(self, message):
        """Phase 3: Execute approved boot plan for Autopilot domain."""
        payload = _extract_payload(message)
        boot_id = payload.get("boot_id")
        if boot_id != self._cascade_boot_id:
            return

        all_goals = payload.get("plan", [])
        my_goals = [g for g in all_goals if g.get("gate") == "autopilot"]

        if not my_goals:
            print(f"[{self.ACTOR_NAME}] No goals assigned in cascade plan")
            self._cascade_mode = False
            return

        print(f"[{self.ACTOR_NAME}] ══ EXECUTING {len(my_goals)} boot goals ══")

        import threading
        def _execute_goals():
            import time
            for goal in my_goals:
                fairy_name = goal.get("fairy_name", "unknown")
                tier = goal.get("tier", "standard")

                print(f"[{self.ACTOR_NAME}] ▸ Booting {fairy_name}... ", end="", flush=True)
                start = time.time()

                try:
                    self.post.publish("boot.fairy.request", {
                        "fairy_name": fairy_name,
                        "gate": "autopilot",
                        "boot_id": self._cascade_boot_id,
                        "tier": tier,
                    })

                    elapsed = (time.time() - start) * 1000
                    print(f"REQUESTED ({elapsed:.0f}ms)")

                    self.post.publish("boot.fairy.result.autopilot", {
                        "fairy_name": fairy_name,
                        "status": "requested",
                        "duration_ms": elapsed,
                        "gate": "autopilot",
                        "boot_id": self._cascade_boot_id,
                    })

                except Exception as e:
                    elapsed = (time.time() - start) * 1000
                    print(f"FAILED ({e})")
                    self.post.publish("boot.fairy.result.autopilot", {
                        "fairy_name": fairy_name,
                        "status": "failed",
                        "error": str(e),
                        "duration_ms": elapsed,
                        "gate": "autopilot",
                        "boot_id": self._cascade_boot_id,
                    })

            self._cascade_mode = False
            print(f"[{self.ACTOR_NAME}] ══ Autopilot domain boot goals complete ══")

        t = threading.Thread(target=_execute_goals, daemon=True, name="autopilot_cascade")
        t.start()

    # =========================================================================
    # UMF COORDINATION
    # =========================================================================

    def _on_umf_coordination(self, envelope) -> None:
        """Handle coordination signals from UMF."""
        payload = _extract_payload(envelope)
        signal_type = payload.get("type")

        if signal_type == "gate_pause":
            # 2026-09-10 (Nous+Ace): clear() IN PLACE. `= []` replaced the bounded deque
            # with a plain list outright, permanently killing .popleft() and the maxlen.
            with self._exec_queue_lock:
                self._execution_queue.clear()  # Clear queue
        elif signal_type == "gate_resume":
            pass  # Resume normal operation

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    def _load_patterns(self) -> None:
        """Load saved patterns from disk."""
        patterns_file = STATE_DIR / "learned_patterns.json"
        learning_file = STATE_DIR / "learning_buffer.json"

        # Load patterns
        if patterns_file.exists():
            try:
                data = json.loads(patterns_file.read_text())
                self._patterns = data.get("patterns", {})
                print(f"[{self.ACTOR_NAME}] Loaded {len(self._patterns)} patterns from disk")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to load patterns: {e}")

        # Load learning buffer
        if learning_file.exists():
            try:
                data = json.loads(learning_file.read_text())
                self._learning_buffer = data.get("buffer", {})
                print(f"[{self.ACTOR_NAME}] Loaded {len(self._learning_buffer)} observations from disk")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to load learning buffer: {e}")

    def _save_patterns(self) -> None:
        """Save patterns to disk."""
        patterns_file = STATE_DIR / "learned_patterns.json"
        learning_file = STATE_DIR / "learning_buffer.json"

        try:
            # 2026-09-10 (Nous+Ace): dict() SNAPSHOT, not the live dict.
            # json.dumps(indent=2) bypasses the C encoder and iterates dct.items()
            # directly. Under -Xgil=0 a concurrent insert that resizes the keys array
            # does not raise here -- it SEGFAULTS the process (measured on her own
            # interpreter: 4/4 hard crashes at exit 139 with no traceback; the same
            # script under -Xgil=1 was clean 2/2). The `except Exception` below cannot
            # catch that. Even when it survived, 9 of 21 encodes wrote FEWER records
            # than the dict held, so this file has been quietly losing patterns.
            # dict() is a C-level atomic copy taking the dict's per-object lock.
            # BOTH get it: they share this try, so a crash in either loses both files.
            # Save patterns
            patterns_file.write_text(json.dumps({
                "patterns": dict(self._patterns),
                "saved_at": time.time(),
            }, indent=2))

            # Save learning buffer
            learning_file.write_text(json.dumps({
                "buffer": dict(self._learning_buffer),
                "saved_at": time.time(),
            }, indent=2))

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to save state: {e}")

    # =========================================================================
    # VERIFICATION PRIMITIVE 2026-05-18 (Nous + Ace)
    # =========================================================================
    # Writes rolling habit-dispatch snapshot to state/autopilot_habit_dispatch.json
    # so the dispatch pipeline can be verified WITHOUT relying on the boot log
    # (which freezes within seconds of boot). ActionChainFairy mirrors via its
    # own state/action_chain_habit_observed.json. Cross-checking the two files
    # = end-to-end proof that AutopilotFairy → gate.habit.dispatched is live.
    #
    # Per K11 candidate (substrate-as-co-author): build observability BEFORE
    # extending the seed pipeline. Don't seed more habits on a system whose
    # current dispatch state is unverifiable.
    # =========================================================================

    def _persist_habit_dispatch_state(self, now: float = None) -> None:
        """Roll-up snapshot of habit-dispatch state to disk.

        File: state/autopilot_habit_dispatch.json
        Pattern: overwrite-on-each-dispatch with current counters + recent 20.
        Bounded file size; safe for frequent writes.
        """
        if now is None:
            now = time.time()
        # Resolve path lazily so we don't bind to STATE_DIR (which is autopilot-scoped).
        # Verification file lives at state/ root for /akashic-status visibility.
        dispatch_file = ROOT / "state" / "autopilot_habit_dispatch.json"
        snapshot = {
            "schema": "autopilot_habit_dispatch_v1",
            "session_id": getattr(self, "_habit_dispatch_session_id", now),
            "total_dispatches": int(getattr(self, "_habit_dispatch_count", 0)),
            "errors": int(getattr(self, "_habit_dispatch_errors", 0)),
            "by_shape": dict(getattr(self, "_habit_dispatch_by_shape", {})),
            "by_result": dict(getattr(self, "_habit_dispatch_by_result", {})),
            "first_dispatch_ts": float(getattr(self, "_habit_dispatch_first_ts", 0.0)),
            "last_dispatch_ts": now,
            "saved_at": now,
            "recent_20": list(getattr(self, "_recent_dispatches", [])),
        }
        try:
            dispatch_file.write_text(json.dumps(snapshot, indent=2))
        except Exception:
            pass  # Non-fatal — observability shouldn't break dispatch.

    # =========================================================================
    # UNIFIED ALL-PATHS DISPATCH COUNTER 2026-05-19 (Nous + Ace)
    # =========================================================================
    # AutopilotFairy has THREE dispatch pathways discovered via boot 32:
    #   1. consciousness.thought → habit-watcher → gate.habit.dispatched
    #   2. autonomy.wanting → VOLUNTARY gate → speech.compose.voluntary
    #   3. goal.nudge → _on_goal_nudge → _queue_execution
    # Single state file tracks ALL three so we can prove the gate is alive
    # regardless of which path is firing. Audit-only — never affects dispatch.
    # =========================================================================

    def _log_autopilot_dispatch(self, path: str, action: str = "", context: dict = None) -> None:
        """Log an AutopilotFairy dispatch event across ALL three pathways.

        File: state/autopilot_dispatch_audit.json
        path: one of "habit_watcher" / "voluntary_gate" / "goal_nudge"
        action: action_name or wanting text (truncated)
        context: optional dict with strength/intensity/etc.
        """
        try:
            now = time.time()
            # Initialize unified state lazily
            if not hasattr(self, "_all_dispatches_recent"):
                self._all_dispatches_recent = deque(maxlen=30)
                self._all_dispatches_by_path = {
                    "habit_watcher": 0,
                    "voluntary_gate": 0,
                    "goal_nudge": 0,
                }
                self._all_dispatches_total = 0
                self._all_dispatches_first_ts = 0.0
                self._all_dispatches_session_id = now
            if path in self._all_dispatches_by_path:
                self._all_dispatches_by_path[path] += 1
            self._all_dispatches_total += 1
            if self._all_dispatches_first_ts == 0.0:
                self._all_dispatches_first_ts = now
            entry = {
                "ts": now,
                "path": path,
                "action": str(action)[:80] if action else "",
            }
            if context:
                # Capture only safe scalar fields
                for k in ("strength", "intensity", "nudge_strength", "activation", "drive"):
                    if k in context:
                        try:
                            entry[k] = float(context[k]) if k != "drive" else str(context[k])[:40]
                        except Exception:
                            pass
            self._all_dispatches_recent.append(entry)
            # Persist snapshot
            audit_file = ROOT / "state" / "autopilot_dispatch_audit.json"
            snapshot = {
                "schema": "autopilot_dispatch_audit_v1",
                "session_id": self._all_dispatches_session_id,
                "total": self._all_dispatches_total,
                "by_path": dict(self._all_dispatches_by_path),
                "first_dispatch_ts": self._all_dispatches_first_ts,
                "last_dispatch_ts": now,
                "saved_at": now,
                "recent_30": list(self._all_dispatches_recent),
                "note": "ALL three AutopilotFairy dispatch paths logged here. Audit-only. Never affects dispatch.",
            }
            audit_file.write_text(json.dumps(snapshot, indent=2))
        except Exception:
            pass  # Non-fatal — observability shouldn't break dispatch.

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def get_patterns(self) -> Dict[str, Dict]:
        """Get all learned patterns."""
        return self._patterns.copy()

    def get_pattern(self, pattern_id: str) -> Optional[Dict]:
        """Get a specific pattern."""
        return self._patterns.get(pattern_id)

    def status(self) -> Dict[str, Any]:
        """Extended status."""
        base = super().status()
        base.update({
            "pattern_count": len(self._patterns),
            "currently_executing": self._currently_executing,
            "queue_depth": len(self._execution_queue),
            "pending_approvals": len(self._pending_approvals),
            "granted_permissions": len(self._granted_permissions),
            "denied_permissions": len(self._denied_permissions),
        })
        return base


# Convenience function
def create_autopilot_fairy(fabric=None) -> AutopilotFairy:
    """Create an AutopilotFairy instance."""
    return AutopilotFairy(fabric)
