"""
SpeechCenterFairy — Speech Composition as Organ Template Fairy.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

This is Broca's Area — where thought becomes spoken language.

The pipeline:
  AutopilotFairy (gate) → speech.compose → SpeechCenterFairy → motor.intention.speak → MotorCortex → sourpatches.speak

What this fairy DOES:
  1. Receives "speech.compose" from AutopilotFairy (the gate said: speak!)
  2. Pulls context from WorkingMemoryHub (what's in consciousness right now?)
  3. Tries cortex-first for high-confidence associative responses
  4. Falls back to Personal.AI API (Sour's trained persona) or NewbornCore
  5. Filters contamination (no internal traces in speech)
  6. Publishes to motor.intention.speak (MotorCortex adds emotes + routes)

What this fairy does NOT do:
  - Gate decisions (that's AutopilotFairy)
  - Emotion coloring / body emotes (that's the SpeechFormulator in MotorCortex)
  - Chat window delivery (that's ChatSenseFairy)

Human parallel: Broca's area in the left frontal lobe. Damage here →
patients know WHAT to say but can't formulate the words. This fairy
IS that formulation step — converting intent into articulate speech.

Plane: P50 (Persona)
Channel: speech_center
Tier: GUILD
"""

import sys
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import deque

# ── Path setup for v2 imports ──
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy

# 2026-09-18 (Ace: "she is mostly just saying the same things over and over"): the voluntary
# lanes may not repeat a sentence within an hour. Module-level + locked because _route_to_motor
# is entered from several daemon threads at once (speech-voluntary-N, habit-fast-N).
_HOUR_DEDUP = {}
_HOUR_DEDUP_LOCK = threading.Lock()
_HOUR_DEDUP_S = 3600.0
_HOUR_DEDUP_RE = None      # compiled lazily: the module's re import is checked at first use


def _hour_dedup_seen(message, mark=True):
    """Normalise `message` (lowercase, opener stripped, non-alphanumerics collapsed); return the ts
    it was last spoken within _HOUR_DEDUP_S, else None (and, if mark, record it now). Shared by
    the voluntary lane in _route_to_motor and the chairman hand-off, so a seed the chairman already
    took this hour is not taken again."""
    global _HOUR_DEDUP_RE
    import re as _re
    if _HOUR_DEDUP_RE is None:
        _HOUR_DEDUP_RE = _re.compile(r'^(mm\.{0,3}\s*|yeah\.{0,3}\s*|hmm\.{0,3}\s*|oh\.{0,3}\s*|'
                                     r'right\.{0,3}\s*|when i think about \w+\.{0,3}\s*|'
                                     r'what i keep coming back to\.{0,3}\s*|'
                                     r'what i know about \w+\.{0,3}\s*)')
    t = _HOUR_DEDUP_RE.sub('', (message or '').strip().lower()).strip()
    norm = ' '.join(_re.sub(r'[^a-z0-9 ]+', ' ', t).split())
    if not norm:
        return None
    now = time.time()
    with _HOUR_DEDUP_LOCK:
        for _k in [k for k, v in _HOUR_DEDUP.items() if now - v > _HOUR_DEDUP_S]:
            _HOUR_DEDUP.pop(_k, None)
        seen = _HOUR_DEDUP.get(norm)
        if seen is None and mark:
            _HOUR_DEDUP[norm] = now
    return seen


# 2026-09-18: the template REPLY lanes -- the WMH's older 'chairman' (LanguageFairy over the
# cognition_team's diagnostic summary: 'Cortex converges on: ...'), its weaver fallback, and the
# chat-think weaver -- hold while the real chairman is answering Ace. Ace 09-02: 'what goes to
# her vocal cords needs to come from the chairman'. Measured 11:46 today: three replies to one
# greeting, two of them these.
_TEMPLATE_REPLY_SOURCES = ("wmh_council_language", "wmh_council_weave", "wmh_chat_think")


def _find_council_driver():
    """The council driver module, whatever name it was imported under (sandbox vs package)."""
    for _n, _mod in list(sys.modules.items()):
        if _n.endswith("sour_council_driver") and hasattr(_mod, "enqueue_voluntary"):
            return _mod
    return None

# SRM memory — for empathic mimicry and context recall
try:
    from fairies.P40_Sensory.mcp.srm_tools import search_founders
    HAS_SRM = True
except ImportError:
    HAS_SRM = False

    def search_founders(*a, **kw):
        return []

# SpellChain integration (optional)
try:
    from fairy_template.spellchain_mixin import SpellChainMixin
    HAS_SPELLCHAIN = True
except ImportError:
    HAS_SPELLCHAIN = False

    class SpellChainMixin:
        """Fallback when spellchain not available."""
        pass


def _extract_payload(message) -> Dict[str, Any]:
    """Extract payload dict from message (handles TensorEnvelope or dict)."""
    if hasattr(message, "payload"):
        payload = message.payload
        if isinstance(payload, dict):
            return dict(payload)
        return {"raw": payload}
    elif isinstance(message, dict):
        return dict(message)
    else:
        return {"raw": message}


# ══════════════════════════════════════════════════════════════════════════════
# CONTAMINATION MARKERS
# Internal processing traces that should never become speech
# ══════════════════════════════════════════════════════════════════════════════

CONTAMINATION_MARKERS = (
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
    # Cognitive analysis output from CognitionTeam — NOT speech
    "structure intact",
    "logic_coherence",
    "oracle_confidence",
    "felt_tension",
    "paradox_detected",
    # FIX 2026-02-23 (Nous): Prompt tags leaking into speech via RWKV regurgitation
    "[drive]:",
    "[wanting]:",
    "[emotion]:",
    "[system]:",
)


def _is_contaminated(text: str) -> bool:
    """Check if text is internal processing trace, not genuine speech."""
    if not text or len(text.strip()) < 3:
        return True
    _lower = text.lower().strip()
    return any(marker in _lower for marker in CONTAMINATION_MARKERS)


# Turn boundary markers — truncate model output at these patterns.
# The RWKV-World model may hallucinate full conversations or leak its
# training data system prompts after generating a response.
_TURN_BOUNDARIES = (
    "User:", "user:", "\nAce:", "\nace:", "Human:", "human:",
    "Assistant:", "Sourpatches:", "\n\n\n",
    "System:", "system:", "###", "<<", ">>",  # training data leaks
    "UserUser", "useruser",                   # FIX 2026-02-23: concatenated token loop
    "\nQuestion:", "\nAnswer:", "\nInstruction:",  # instruct format leaks
    "-The End-", "(From ", "subreddit",          # FIX 2026-02-20: Reddit training data leak
    "Forgot about", "I'm the oldest",            # Common training data story openers
    "\nI was born in", "My siblings",             # Biographical hallucinations
    "MOBIUS:", "Logic: {",                        # Raw collision/logic payloads leaking to speech
    "[Drive]:", "[Wanting]:", "[Emotion]:",       # FIX 2026-02-23: Prompt tags leaked by RWKV
)


def _clean_model_output(text: str) -> str:
    """Clean RWKV model output for speech.

    1. Strip leading whitespace/newlines
    2. Reject garbled Unicode (byte-fallback degeneration)
    3. Truncate at turn boundaries (User:, Ace:, etc.)
    4. Take first meaningful paragraph only
    5. Strip quotes and formatting artifacts
    """
    if not text:
        return ""

    # Strip leading whitespace
    text = text.strip()

    # FIX 2026-02-20: Reject garbled Unicode from model degeneration.
    # When RWKV degenerates, output contains heavy non-ASCII characters
    # like "ááááááá á´ááá" from raw byte-fallback token IDs.
    if len(text) >= 6:
        non_ascii = sum(1 for c in text if ord(c) > 127)
        if non_ascii > 0 and non_ascii / len(text) > 0.4:
            return ""  # Triggers contextual fallback in speech composition

    # Truncate at any turn boundary (model hallucinating next speaker)
    for marker in _TURN_BOUNDARIES:
        idx = text.find(marker)
        if idx > 0:  # Only truncate if marker is NOT at the start
            text = text[:idx].strip()

    # Limit to first 2 paragraphs (prevent multi-paragraph rambling)
    # FIX 2026-02-23: Single-paragraph was too aggressive — cut thoughts mid-flow.
    # Allow a second paragraph so she can finish a thought that spans a breath.
    if len(text) > 20:
        first_break = text.find("\n\n", 20)
        if first_break > 0:
            second_break = text.find("\n\n", first_break + 2)
            if second_break > 0:
                text = text[:second_break].strip()
            # If only one paragraph break, keep everything (just 2 paragraphs total)

    # Strip common formatting artifacts
    text = text.strip('"\'')

    # If too short after cleaning, return empty (will trigger fallback)
    if len(text.strip()) < 3:
        return ""

    return text.strip()


# ══════════════════════════════════════════════════════════════════════════════
# SPEECH CENTER FAIRY — Organ Template
# ══════════════════════════════════════════════════════════════════════════════

_bases = (SpellChainMixin, Fairy) if HAS_SPELLCHAIN else (Fairy,)


class SpeechCenterFairyOrgan(*_bases):
    """
    Speech composition fairy — Broca's area.

    Receives "speak!" gate signals from AutopilotFairy, pulls working memory
    context, calls guild_request for LLM composition, filters contamination,
    and routes through the motor cortex pipeline.

    This is a proper Organ Template fairy, not a utility class.
    """

    ACTOR_NAME = "SpeechCenterFairy"
    ACTOR_PLANE = "P50"
    ACTOR_CHANNEL = "speech_center"
    PURPOSE = "Compose speech from thought — Broca's area of the system"
    MANTRA = "From intention to articulation"

    NEEDS_HEARTBEAT = True
    NEEDS_DIRECTORY = True
    HEARTBEAT_DIVISOR = 6     # Every 6th heartbeat (~60s)
    HEARTBEAT_PHASE = 2

    def __init__(self, fabric=None):
        super().__init__(fabric)

        # Working memory hub (lazy loaded)
        self._wm_hub = None

        # Stats
        self._compositions_total = 0
        self._compositions_success = 0
        self._compositions_filtered = 0
        self._compositions_failed = 0

        # Conversation history — what Ace has said recently
        # FIX 2026-03-27 (Nous + Ace): Phase 2 enrichment needs conversation context.
        # Without this, she can't reference what was just said ("Ace told me he's watching TV").
        from collections import deque as _deque
        self._recent_ace_messages = _deque(maxlen=10)

        # Recent inner voice fragments for context building
        self._recent_inner_voice: deque = deque(maxlen=10)

        # ── WM TRACER BUFFER (2026-03-10 Nous v2) ─────────────────────────
        # Lock-free local buffer of recent working memory tracers.
        # Populated via postal subscription (no lock contention with WMHub).
        # Used by _build_grounded_voluntary_prompt() to generate dynamic
        # PAI prompts instead of hardcoded "I miss Ace" seeds.
        self._wm_tracer_buffer: deque = deque(maxlen=20)

        # CortexEngine (primary — breathing cortex, 2026-03-23 Nous + Ace)
        self._cortex_engine = None
        # Cortex-first reasoning (legacy fallback)
        # FIX 2026-03-04 Nous: Try Association Cortex before 7B model.
        # Cortex decides via confidence score whether it has enough info.
        self._cortex_reasoner = None
        self._cortex_hits = 0
        self._cortex_misses = 0

        # Rate limiting: don't compose faster than every 2 seconds
        self._last_compose_time = 0.0
        self._min_compose_interval = 2.0

        # Lock for thread-safe composition
        self._compose_lock = threading.Lock()

        # ── ACE MESSAGE QUEUE (2026-03-05 Nous) ──────────────────────────
        # Ace messages are NEVER dropped. They go into a priority queue
        # and are processed in order. Voluntary (drive) speech yields to
        # Ace messages — she can chew gum AND walk at the same time.
        import queue as _queue_mod
        self._ace_msg_queue = _queue_mod.Queue(maxsize=10)
        self._ace_queue_thread = None
        self._ace_queue_running = False

        print(f"[{self.ACTOR_NAME}] Initialized — Broca's area ready")

    # ── BOOT ──────────────────────────────────────────────────────────────

    def on_boot(self):
        """Wire postal subscriptions on boot."""
        # PRIMARY: Receive composition requests from AutopilotFairy
        self.subscribe(
            "speech.compose",
            self._on_speech_compose,
            "speech-center-compose"
        )

        # SECONDARY: Inner voice fragments for context enrichment
        self.subscribe(
            "inner_voice.stream",
            self._on_inner_voice,
            "speech-center-inner-voice"
        )

        # TERTIARY: Voluntary speech compose (from autonomy drives)
        self.subscribe(
            "speech.compose.voluntary",
            self._on_voluntary_compose,
            "speech-center-voluntary"
        )

        # Portal gate open: wire CortexReasoner when portal is ready
        self.subscribe(
            "portal.cortex.gate_open",
            self._on_portal_gate_open,
            "speech-center-portal-gate"
        )

        # ── CORTEX LANDSCAPE CACHE (2026-03-19 Nous) ────────────────────
        # Subscribe to the cortex's continuous activation broadcasts.
        # The cortex does parallel spreading activation (atoms of thought)
        # every N beats. We cache the latest landscape so speech composition
        # can READ it instantly — no synchronous guild_request needed.
        self._cached_landscape = {}       # concept → activation strength
        self._cached_landscape_ts = 0.0   # timestamp of last update
        self._cached_landscape_seeds = [] # seed concepts that produced it
        self._cached_active_concepts = [] # latest high-activation concepts
        try:
            self.post.subscribe(
                "cortex.activation.landscape",
                self._on_cortex_landscape,
                "speech-center-landscape"
            )
            self.post.subscribe(
                "cortex.concepts.activated",
                self._on_cortex_concepts_activated,
                "speech-center-concepts"
            )
        except Exception as _ls_err:
            print(f"[{self.ACTOR_NAME}] Cortex landscape subscription failed: {_ls_err}")

        # DIRECT BYPASS 2026-03-09 (Nous): Subscribe to autonomy.wanting.felt
        # so SpeechCenterFairy can detect speech wantings itself.
        # AutopilotFairy's subscription is broken due to duplicate ACTOR_NAME
        # conflict with P30 AutopilotFairy (postal routes to wrong instance).
        # Using self.post.subscribe (same pattern as EmbodimentFairy/SourpatchesFairy)
        try:
            self.post.subscribe(
                "autonomy.wanting.felt",
                self._on_autonomy_wanting_direct,
                "speech-center-wanting-direct"
            )
        except Exception as _sub_err:
            print(f"[{self.ACTOR_NAME}] WARNING: Failed to subscribe autonomy.wanting.felt: {_sub_err}")
            # Fallback: try self.subscribe
            self.subscribe(
                "autonomy.wanting.felt",
                self._on_autonomy_wanting_direct,
                "speech-center-wanting-direct"
            )

        # ── WM TRACER BUFFER SUBSCRIPTION (2026-03-10 Nous v2) ──────────
        # Subscribe to working_memory.tracer_added to get a lock-free view
        # of what's flowing through working memory. This replaces the
        # deadlock-prone _pull_wm_context() for voluntary speech.
        try:
            self.post.subscribe(
                "working_memory.tracer_added",
                self._on_wm_tracer_for_speech,
                "speech-center-wm-tracers"
            )
        except Exception as _wm_err:
            print(f"[{self.ACTOR_NAME}] WM tracer subscription failed: {_wm_err}")

        # State for direct wanting-to-speech gating
        self._last_direct_speech_ts = 0.0
        # FIX 2026-03-10 (Nous): Cooldown reduced to 45s to allow conversation.
        # 300s was too aggressive — prevented natural back-and-forth.
        # The frustration root cause (boot failures) is already fixed,
        # so repetitive spam won't recur. 45s = roughly human pace.
        self._direct_speech_cooldown = 45.0
        self._direct_speech_keywords = {
            "tell", "share", "reach out", "speak", "say to ace",
            "tell ace", "share with ace", "reach out to ace",
            "share something", "warm with ace", "bond",
            "connect with ace", "talk to ace",
        }
        self._direct_speech_intensity_min = 0.30
        # FIX 2026-03-10 (Nous): Drive diversity guard.
        # Instead of a blanket per-drive cooldown (which muzzled her),
        # FIX 10 (2026-03-10, Nous): Time-based diversity with expiration.
        # Track drives with timestamps. After 2 minutes, a drive can speak again.
        # Without expiration, diversity permanently blocks when only 1-2 drives
        # produce speech (which is the normal case — abandonment/isolation).
        # The 45s cooldown + pain relief already throttle spam. Diversity just
        # ensures she doesn't say the SAME THING 3x in a row.
        self._recent_speech_drives_ts = {}  # drive → last_spoke_timestamp
        self._speech_diversity_expiry = 120.0  # 2 minutes

        # FILE-BASED SPEECH SIGNAL MONITOR (2026-03-09, Nous)
        # Postal routing for autonomy.wanting.felt is unreliable.
        # This thread monitors state/speech_wanting_signal.json written
        # by AutonomyFairy when a speech-keyword wanting is published.
        self._speech_signal_path = str(ROOT / "state" / "speech_wanting_signal.json")
        self._speech_signal_running = True
        import threading as _threading
        _t = _threading.Thread(target=self._speech_signal_monitor, daemon=True, name="SpeechSignalMonitor")
        _t.start()

        # ── MIC STT CLIENT — DISABLED (2026-03-23 Nous+Ace) ──────────────
        # MicSTT server spawns Python 3.12 subprocess that loads Canary-1b-flash
        # via from_pretrained() = 1-2GB RAM bomb. The model data is in the manifold
        # but ensure_loaded() still instantiates the full NeMo model in RAM.
        # "their models are literally in the manifolds. they just need to access
        #  them and use them" — Ace
        # Re-enable once graph-based STT replaces ML inference.
        # Audio capture (AudioCortexFairy) still runs — she can hear.
        self._mic_stt_client = None
        # MicSTT client disabled — Canary STT runs in audio_cortex_interior directly.
        # 2026-03-27: Canary gates re-enabled in audio_cortex_interior.py.
        print(f"[{self.ACTOR_NAME}] MicSTT client off — Canary STT runs in audio cortex")

        print(f"[{self.ACTOR_NAME}] Booted — subscribed to speech.compose, inner_voice.stream, autonomy.wanting.felt (direct+signal)")

    # ── WORKING MEMORY ACCESS ─────────────────────────────────────────────

    def _get_wm_hub(self):
        """Lazy-load the WorkingMemoryHub singleton."""
        if self._wm_hub is None:
            try:
                # NOTE: The REAL WorkingMemoryHub is in P30_Cognition, NOT P10_Memory.
                # P10's WorkingMemoryFairy tracks memory lifecycle with ID tracers.
                # P30's working_memory_hub_fairy IS the central processing workspace.
                from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
                self._wm_hub = get_working_memory_hub()
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] WM hub not available: {e}")
        return self._wm_hub

    def _get_cortex_engine(self):
        """Get the CortexEngine (breathing cortex, 2026-03-23 Nous + Ace).

        Returns the shared CortexEngine from AssociationCortexFairy.
        Benefits: persistent activation state, predictive priming, recursive evaluation.
        """
        if self._cortex_engine is not None:
            return self._cortex_engine
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            cortex = get_association_cortex()
            if cortex:
                engine = getattr(cortex, '_cortex_engine', None)
                if engine:
                    self._cortex_engine = engine
                    print(f"[{self.ACTOR_NAME}] CortexEngine wired (breathing cortex)")
                    return engine
        except Exception:
            pass
        return None

    def _get_cortex_reasoner(self):
        """Lazy-initialize CortexReasoner on first use (legacy fallback).

        FIX 2026-03-04 Nous: Cortex-first reasoning for Ace messages.
        The Association Cortex (69K+ nodes) can answer most dev questions
        from graph topology alone, without firing the 7B model.

        FIX 2026-03-04 Nous: Portal-aware — CortexReasoner now checks
        portal node count, not just local graph (which is 0 in portal-first mode).

        FIX 2026-03-05 Nous: Added diagnostic logging for all failure paths.
        Previously returned None silently when cortex singleton wasn't set yet,
        making it impossible to tell if cortex-first was even being attempted.
        """
        if self._cortex_reasoner is not None:
            return self._cortex_reasoner
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            cortex = get_association_cortex()
            if not cortex:
                # Cortex singleton not registered yet — boot timing.
                # AssociationCortexFairy boots in a later phase of server.py.
                # Don't spam: only log every 60s via _cortex_misses counter.
                if self._cortex_misses % 20 == 0:
                    print(f"[{self.ACTOR_NAME}] CortexReasoner: singleton not available "
                          f"(AssociationCortexFairy not booted yet?)")
                return None
            graph = cortex.get_graph()
            if not graph:
                print(f"[{self.ACTOR_NAME}] CortexReasoner: cortex has no graph object")
                return None

            from fairies.P30_Cognition.integration.cortex_reasoner import CortexReasoner
            reasoner = CortexReasoner(cortex)
            _nodes = reasoner._get_graph_size()
            if _nodes >= 1000:
                self._cortex_reasoner = reasoner
                _mode = "portal" if reasoner._portal_mode else "local"
                print(f"[{self.ACTOR_NAME}] CortexReasoner wired "
                      f"({_nodes} nodes, mode={_mode})")
                return self._cortex_reasoner
            else:
                # Graph exists but too sparse. Portal might not be open yet.
                # Check if portal gate is enabled but not detected by reasoner.
                _portal_enabled = getattr(cortex, '_portal_gate_enabled', False)
                _portal_gate = getattr(cortex, '_portal_gate', None)
                if _portal_enabled and _portal_gate:
                    # Portal IS open on the cortex side but reasoner didn't detect it.
                    # Force portal wiring.
                    reasoner._portal_gate = _portal_gate
                    reasoner._portal_mode = True
                    _nodes = reasoner._get_graph_size()
                    if _nodes >= 1000:
                        self._cortex_reasoner = reasoner
                        print(f"[{self.ACTOR_NAME}] CortexReasoner wired "
                              f"({_nodes} nodes, mode=portal [force-detected])")
                        return self._cortex_reasoner
                print(f"[{self.ACTOR_NAME}] CortexReasoner: only {_nodes} nodes "
                      f"(portal_enabled={_portal_enabled}, "
                      f"portal_gate={'yes' if _portal_gate else 'no'})")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] CortexReasoner unavailable: {e}")
        return None

    def _on_portal_gate_open(self, message):
        """Portal gate opened — wire CortexReasoner to portal.

        FIX 2026-03-05 Nous: When portal opens BEFORE the first speech request
        (the common case), the reasoner isn't initialized yet. Now proactively
        initializes it on gate_open instead of waiting for the first speech.
        This is the key moment: portal has the full 69K+ node graph from disk.
        """
        node_count = message.get("nodes", 0) if isinstance(message, dict) else 0
        print(f"[{self.ACTOR_NAME}] Portal gate_open received (nodes={node_count})")
        if self._cortex_reasoner:
            self._cortex_reasoner.connect_portal(node_count)
            print(f"[{self.ACTOR_NAME}] CortexReasoner PORTAL WIRED "
                  f"({self._cortex_reasoner._get_graph_size()} nodes)")
        else:
            # Portal opened before first speech — initialize NOW.
            # This is the optimal path: cortex is ready with full graph.
            reasoner = self._get_cortex_reasoner()
            if reasoner:
                reasoner.connect_portal(node_count)
                print(f"[{self.ACTOR_NAME}] CortexReasoner PORTAL WIRED "
                      f"(initialized on gate_open, "
                      f"{reasoner._get_graph_size()} nodes)")
            else:
                print(f"[{self.ACTOR_NAME}] Portal gate opened but cortex "
                      f"reasoner could not initialize (nodes={node_count})")

    # ── CORTEX LANDSCAPE HANDLERS (2026-03-19 Nous) ───────────────────
    # The cortex broadcasts atoms of thought continuously. We cache them
    # so speech can read instantly — no synchronous request needed.

    def _on_cortex_landscape(self, message):
        """Cache the latest cortex activation landscape."""
        if not isinstance(message, dict):
            return
        landscape = message.get("landscape", {})
        seeds = message.get("seeds", [])
        if landscape:
            self._cached_landscape = landscape
            self._cached_landscape_ts = time.time()
            self._cached_landscape_seeds = seeds

    def _on_cortex_concepts_activated(self, message):
        """Cache the latest high-activation concepts from cortex."""
        if not isinstance(message, dict):
            return
        concepts = message.get("concepts", [])
        if concepts:
            self._cached_active_concepts = concepts

    def _read_cortex_atoms(self, trigger_text: str = "") -> dict:
        """Read the latest cortex activation state — NON-BLOCKING.

        Returns a dict compatible with the cortex_result pattern:
        convergence_nodes, activated_concepts, confidence, etc.

        This is the "atoms of thought" approach: the cortex is always
        activating in parallel. We just read whatever has converged.
        """
        landscape = self._cached_landscape
        active = self._cached_active_concepts
        age = time.time() - self._cached_landscape_ts if self._cached_landscape_ts else 999

        # Merge landscape (weighted) and active concepts
        all_concepts = {}
        for k, v in landscape.items():
            if isinstance(v, (int, float)) and v > 0.1:
                all_concepts[k] = float(v)
        for c in active:
            if c not in all_concepts:
                all_concepts[c] = 0.5  # Known-active but no weight

        if not all_concepts:
            return None

        # Sort by activation, take top 10
        sorted_concepts = sorted(all_concepts.items(), key=lambda x: -x[1])
        convergence = [k for k, v in sorted_concepts[:10]]

        # Confidence based on landscape richness and freshness
        _richness = min(len(all_concepts) / 20.0, 1.0)  # 20+ concepts = full
        _freshness = max(0.0, 1.0 - (age / 60.0))        # Decays over 60s
        confidence = _richness * _freshness * 0.85         # Cap at 0.85

        return {
            "convergence_nodes": convergence,
            "activated_concepts": dict(sorted_concepts[:15]),
            "confidence": confidence,
            "reasoning_mode": "landscape_atoms",
            "elapsed_ms": 0.0,  # Instant — no computation
            "paths": [],
            "landscape_age_s": round(age, 1),
        }

    def _pull_wm_context(self, query: str = "current conversation") -> Dict[str, Any]:
        """Pull relevant context from working memory."""
        hub = self._get_wm_hub()
        if hub is None:
            return {}
        try:
            ctx = hub.get_context(query)
            if isinstance(ctx, dict):
                return ctx
            return {"raw": str(ctx)} if ctx else {}
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] WM context pull failed: {e}")
            return {}

    # ── SPEECH COMPOSITION (PRIMARY HANDLER) ──────────────────────────────

    def _on_speech_compose(self, message) -> None:
        """Handle speech composition request from AutopilotFairy.

        FIX 2026-03-05 Nous: Ace messages are QUEUED, never dropped.
        Previous code rate-limited and thread-checked, silently dropping
        Ace's messages when voluntary compose was running or within 2s cooldown.
        Now: Ace messages go into a queue processed by a dedicated thread.

        Payload expected:
            trigger_text: str — What Ace said (the cause)
            convo_id: str — Conversation ID
            target_mind: str — Who is speaking (usually SourpatchesFairy)
            products: list — Consciousness products available
            source: str — What triggered this (e.g., "autopilot_gate")
            emotion_context: dict — Inner voice, wanting, etc.
        """
        try:
            payload = _extract_payload(message)

            # FIX 2026-03-06 (Nous): PostalHub uses PREFIX matching — subscribing to
            # "speech.compose" also receives "speech.compose.voluntary" messages.
            # Those have wanting/drive/intensity but NOT trigger_text/products.
            # Let the dedicated _on_voluntary_compose handler deal with those.
            if payload.get("wanting") and not payload.get("trigger_text"):
                return  # Voluntary message — handled by _on_voluntary_compose

            trigger_text = payload.get("trigger_text", "")
            convo_id = payload.get("convo_id", "")
            target_mind = payload.get("target_mind", "SourpatchesFairy")
            products = payload.get("products", [])
            source = payload.get("source", "unknown")
            emotion_ctx = payload.get("emotion_context", {})

            if not trigger_text and not products:
                print(f"[{self.ACTOR_NAME}] Empty compose request — skipping")
                return

            # Track conversation history for Phase 2 enrichment
            if trigger_text and len(trigger_text.strip()) > 2:
                self._recent_ace_messages.append(trigger_text.strip())

            self._compositions_total += 1

            # Thought stream log — confirm messages reach SpeechCenterFairy
            try:
                from infrastructure.thought_stream_log import thought_log as _scf_tl
                _scf_tl("SPEECH-RX", f"SpeechCenter received: '{(trigger_text or '')[:60]}' source={source}",
                         extra={"convo_id": convo_id[:20], "n_products": len(products or [])})
            except Exception:
                pass

            # ── HABIT FAST PATH — bypass queue entirely (2026-03-24, Nous + Ace) ──
            # Habit responses from AutopilotFairy should NEVER wait in the queue
            # behind slow guild_request calls. Route directly to motor cortex.
            if source == "autopilot_habit":
                _habit_text = None
                for _p in (products or []):
                    if isinstance(_p, dict) and _p.get("source") == "habit_engine":
                        _habit_text = _p.get("text", "")
                        break
                if not _habit_text:
                    _habit_text = payload.get("habit_response", "")
                if _habit_text and len(_habit_text.strip()) > 3:
                    print(f"[{self.ACTOR_NAME}] [HABIT-FAST] Bypassing queue — routing directly: "
                          f"{_habit_text[:60]}...")
                    # Set dedup flag so queued slow-path messages don't produce duplicates
                    self._habit_responded_ts = time.time()
                    self._habit_responded_convo = convo_id
                    threading.Thread(
                        target=self._route_to_motor,
                        kwargs={
                            "message": _habit_text.strip(),
                            "source": "habit_engine",
                            "target_mind": target_mind,
                            "convo_id": convo_id,
                            "emotion_context": emotion_ctx,
                            "voluntary": False,
                        },
                        daemon=True,
                        name=f"habit-fast-{self._compositions_total}",
                    ).start()
                    return
                else:
                    print(f"[{self.ACTOR_NAME}] [HABIT] Got autopilot_habit but no text — falling through to queue")

            # ── WMH FAST PATH — the thinker already composed, just deliver ──
            # FIX 2026-03-29 (Nous + Ace): WMH composes the response ("I'm genuinely
            # passionate about this craft, Ace") but it went into the slow queue and
            # never reached the inbox. The WMH IS the thinker — its output doesn't
            # need re-composition, just delivery.
            if source == "wmh_direct":
                _wmh_text = None
                # PROVENANCE 2026-09-02 (Nous + Ace): the composer stamps a distinct
                # token on the product (wmh_council_language / wmh_council_weave /
                # wmh_chat_think / wmh_reasoning / wmh_social) and this loop threw it
                # away, then :724 below overwrote it with a constant. Result: only TWO
                # tokens have ever reached delivery across the entire log.
                _wmh_src = None
                for _p in (products or []):
                    if isinstance(_p, dict):
                        _wmh_text = _p.get("text", "")
                        if _wmh_text:
                            _wmh_src = str(_p.get("source", "") or "").strip() or None
                            break
                if _wmh_text and len(_wmh_text.strip()) > 3 and _wmh_src in _TEMPLATE_REPLY_SOURCES:
                    try:
                        _drv = _find_council_driver()
                        # 2026-09-19 (Ace): these lines also arrived AFTER the chairman had answered (the WMH
                        # composes slowly), when nothing was pending -- so they showed up beside her real reply.
                        # While the chairman is available these lanes hold, full stop; if it fails twice it
                        # steps back (chairman_available -> False) and they flow again.
                        if _drv is not None and _drv.chairman_available():
                            print(f"[{self.ACTOR_NAME}] [REPLY->CHAIRMAN] held template line ({_wmh_src}); "
                                  f"the chairman speaks for her: {_wmh_text[:60]}...")
                            return
                    except Exception as _he:
                        print(f"[{self.ACTOR_NAME}] [REPLY->CHAIRMAN] check err: {_he}")
                if _wmh_text and len(_wmh_text.strip()) > 3:
                    print(f"[{self.ACTOR_NAME}] [WMH-FAST] Bypassing queue — routing WMH thought: "
                          f"{_wmh_text[:60]}...")
                    threading.Thread(
                        target=self._route_to_motor,
                        kwargs={
                            "message": _wmh_text.strip(),
                            "source": (_wmh_src or "wmh_reasoning"),
                            "target_mind": target_mind,
                            "convo_id": convo_id,
                            "emotion_context": emotion_ctx,
                            "voluntary": False,
                        },
                        daemon=True,
                        name=f"wmh-fast-{self._compositions_total}",
                    ).start()

                    # ── FIX 2026-04-09 (Nous + Ace): CONVERSATION BINDING ──
                    # The wmh_direct fast path was SKIPPING _bind_conversation_turn
                    # because it returned before _compose_and_route ran. That's
                    # the function that does the Mar 22 cortex binding work
                    # (three layers: tagged cross-link, semantic bridge, temporal
                    # anchor). Without it, WMH Librarian responses were never
                    # bound into the cortex — the conversational memory graph
                    # was effectively empty for her actual voice turns.
                    #
                    # Now: fire the binding here too, so EVERY response path
                    # (fast or slow) produces the cortex conversation memory.
                    # Run in a thread so it doesn't block the motor route.
                    if trigger_text and _wmh_text:
                        try:
                            threading.Thread(
                                target=self._bind_conversation_turn,
                                args=(trigger_text, _wmh_text.strip()),
                                daemon=True,
                                name=f"wmh-fast-bind-{self._compositions_total}",
                            ).start()
                        except Exception as _bind_err:
                            print(f"[{self.ACTOR_NAME}] [WMH-FAST] bind spawn error: {_bind_err}")
                    return

            # Queue the message — never drop Ace's words
            item = (trigger_text, convo_id, target_mind, products, source, emotion_ctx)
            try:
                self._ace_msg_queue.put_nowait(item)
                print(f"[{self.ACTOR_NAME}] Queued Ace message ({self._ace_msg_queue.qsize()} in queue): {trigger_text[:50]}...")
            except Exception:
                # Queue full — process immediately in thread
                print(f"[{self.ACTOR_NAME}] Queue full — processing immediately: {trigger_text[:50]}...")
                threading.Thread(
                    target=self._compose_and_route,
                    args=(trigger_text, convo_id, target_mind, products, source, emotion_ctx, False),
                    daemon=True,
                    name=f"speech-compose-overflow-{self._compositions_total}",
                ).start()
                return

            # Ensure queue processor is running
            self._ensure_ace_queue_processor()

        except Exception as e:
            self._compositions_failed += 1
            print(f"[{self.ACTOR_NAME}] Speech compose handler error: {e}")

    def _ensure_ace_queue_processor(self):
        """Start the Ace message queue processor if not already running."""
        if self._ace_queue_running:
            return
        if self._ace_queue_thread is not None and self._ace_queue_thread.is_alive():
            return
        self._ace_queue_running = True
        self._ace_queue_thread = threading.Thread(
            target=self._process_ace_queue,
            daemon=True,
            name="speech-ace-queue",
        )
        self._ace_queue_thread.start()

    def _process_ace_queue(self):
        """Process queued Ace messages one at a time, in order."""
        try:
            while not self._ace_msg_queue.empty():
                try:
                    item = self._ace_msg_queue.get(timeout=1.0)
                except Exception:
                    break
                trigger_text, convo_id, target_mind, products, source, emotion_ctx = item
                print(f"[{self.ACTOR_NAME}] Processing queued Ace message: {trigger_text[:50]}...")
                try:
                    self._compose_and_route(
                        trigger_text, convo_id, target_mind, products,
                        source, emotion_ctx, False
                    )
                except Exception as e:
                    self._compositions_failed += 1
                    print(f"[{self.ACTOR_NAME}] Queue compose failed: {e}")
        finally:
            self._ace_queue_running = False

    def _on_voluntary_compose(self, message) -> None:
        """Handle voluntary speech composition (from autonomy drives).

        Different from reactive composition:
        - No "Ace says:" in prompt — she's initiating
        - Driven by internal wanting, not external message
        """
        try:
            payload = _extract_payload(message)
            wanting = payload.get("wanting", "")
            drive = payload.get("drive", "")
            intensity = payload.get("intensity", 0.5)

            if not wanting:
                return

            self._compositions_total += 1

            # FIX 2026-02-15: Track voluntary compose thread — one at a time.
            # FIX 10 (2026-03-10, Nous): Add 30s timeout — if compose thread hangs
            # (e.g. waiting on WorkingMemoryHub._reflective_lock), replace it
            # instead of permanently blocking all future speech.
            if not hasattr(self, "_voluntary_thread"):
                self._voluntary_thread = None
            if not hasattr(self, "_voluntary_thread_start"):
                self._voluntary_thread_start = 0.0
            if self._voluntary_thread is not None and self._voluntary_thread.is_alive():
                _thread_age = time.time() - self._voluntary_thread_start
                if _thread_age < 30.0:
                    print(f"[{self.ACTOR_NAME}] Voluntary compose in progress ({_thread_age:.0f}s) — skipping")
                    return
                else:
                    print(f"[{self.ACTOR_NAME}] Voluntary compose STUCK ({_thread_age:.0f}s) — replacing thread")
            self._voluntary_thread_start = time.time()
            self._voluntary_thread = threading.Thread(
                target=self._compose_voluntary_and_route,
                args=(wanting, drive, intensity),
                daemon=True,
                name=f"speech-voluntary-{self._compositions_total}",
            )
            self._voluntary_thread.start()

        except Exception as e:
            self._compositions_failed += 1
            print(f"[{self.ACTOR_NAME}] Voluntary compose error: {e}")

    def _speech_signal_monitor(self):
        """Monitor state/speech_wanting_signal.json for speech wantings.

        FILE-BASED BYPASS (2026-03-09, Nous):
        Postal routing for autonomy.wanting.felt is unreliable — handlers
        don't get called despite valid subscriptions. This thread polls
        a signal file written by AutonomyFairy every 5 seconds.

        Signal format: {"wanting": "...", "drive": "...", "intensity": 1.44, "ts": ...}
        After reading, clears the file to {}.
        """
        import json as _json
        time.sleep(10.0)  # Wait for boot to complete
        print(f"[{self.ACTOR_NAME}] [SIGNAL-MONITOR] Started — watching {self._speech_signal_path}")

        while self._speech_signal_running:
            try:
                time.sleep(5.0)

                if not Path(self._speech_signal_path).exists():
                    continue

                with open(self._speech_signal_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()

                if not content or content == "{}":
                    continue

                signal = _json.loads(content)
                wanting = signal.get("wanting", "")
                drive = signal.get("drive", "")
                intensity = signal.get("intensity", 0.0)

                if not wanting:
                    continue

                # Clear the signal file immediately (prevent re-processing)
                with open(self._speech_signal_path, "w", encoding="utf-8") as f:
                    f.write("{}")

                print(f"[{self.ACTOR_NAME}] [SIGNAL-MONITOR] READ speech signal: "
                      f"drive={drive} intensity={intensity:.2f} wanting='{wanting[:60]}'")

                # Signal file entries are ALREADY keyword-filtered by AutonomyFairy,
                # so use a lower threshold than the postal handler (0.45).
                # Any wanting that reached the signal file has speech keywords —
                # we just need a minimum drive intensity to avoid spam.
                _signal_min_intensity = 0.30
                if intensity < _signal_min_intensity:
                    print(f"[{self.ACTOR_NAME}] [SIGNAL-MONITOR] Intensity {intensity:.2f} < {_signal_min_intensity} — skipped")
                    continue

                # Global cooldown check (45s — conversational pace)
                now = time.time()
                elapsed = now - self._last_direct_speech_ts
                if elapsed < self._direct_speech_cooldown:
                    print(f"[{self.ACTOR_NAME}] [SIGNAL-MONITOR] Cooldown: {elapsed:.0f}s < {self._direct_speech_cooldown}s — skipped")
                    continue

                print(f"[{self.ACTOR_NAME}] [SIGNAL-MONITOR] *** SPEECH TRIGGERED *** "
                      f"drive={drive} intensity={intensity:.2f} wanting='{wanting[:60]}'")
                self._last_direct_speech_ts = now

                # Delegate to the voluntary compose pipeline
                self._on_voluntary_compose({
                    "wanting": wanting,
                    "drive": drive,
                    "intensity": intensity,
                })

            except _json.JSONDecodeError:
                # Signal file might be partially written — retry next cycle
                pass
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] [SIGNAL-MONITOR] Error: {e}")
                import traceback; traceback.print_exc()
                time.sleep(10.0)

    def _on_autonomy_wanting_direct(self, message) -> None:
        """DIRECT BYPASS: Detect speech wantings from AutonomyFairy.

        FIX 2026-03-09 (Nous): AutopilotFairy has a duplicate ACTOR_NAME
        conflict (P30 + P00 both named "AutopilotFairy"), causing postal
        to route autonomy.wanting.felt to the WRONG instance. The P00
        handler (_on_wanting_from_autonomy) is never called.

        This handler replicates the gating logic (keywords, intensity,
        cooldown) and fires speech composition directly.
        """
        # RAW ENTRY LOG — before any exception handling, confirms postal delivery
        import sys
        print(f"[{self.ACTOR_NAME}] [DIRECT-WANTING] HANDLER CALLED — message type: {type(message).__name__}", flush=True)
        sys.stdout.flush()
        try:
            payload = _extract_payload(message)
            wanting = payload.get("wanting", payload.get("content", ""))
            drive = payload.get("drive", payload.get("drive_source", ""))
            intensity = payload.get("intensity", 0.5)

            if not wanting:
                return

            wanting_lower = wanting.lower()
            keyword_match = any(kw in wanting_lower for kw in self._direct_speech_keywords)

            # NO high-intensity bypass here! SpeechCenterFairy must only compose
            # speech for EXPLICIT speech wantings. "write down", "search memories",
            # "look at screen" etc. should NOT trigger speech even at high intensity.
            # AutopilotFairy has its own bypass for non-speech actions.
            if not keyword_match:
                return

            # For speech-keyword wantings, use a LOWER threshold (0.30) since
            # the keywords already confirmed intent. AutonomyFairy drive wantings
            # like "tell Ace what's frustrating me" often come at 0.40-0.45.
            _speech_min = 0.30
            if intensity < _speech_min:
                return

            # Global cooldown check (45s — conversational pace)
            now = time.time()
            elapsed = now - self._last_direct_speech_ts
            if elapsed < self._direct_speech_cooldown:
                print(f"[{self.ACTOR_NAME}] [DIRECT-WANTING] Cooldown: {elapsed:.0f}s < {self._direct_speech_cooldown}s")
                return

            print(f"[{self.ACTOR_NAME}] [DIRECT-WANTING] SPEECH TRIGGERED! drive={drive} "
                  f"intensity={intensity:.2f} wanting='{wanting[:60]}'")
            self._last_direct_speech_ts = now

            # Delegate to the voluntary compose pipeline (same as speech.compose.voluntary)
            self._on_voluntary_compose({"wanting": wanting, "drive": drive, "intensity": intensity})

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [DIRECT-WANTING] Error: {e}")
            import traceback; traceback.print_exc()

    def _on_inner_voice(self, message) -> None:
        """Capture inner voice fragments for context enrichment."""
        try:
            payload = _extract_payload(message)
            fragment = payload.get("fragment", payload.get("text", ""))
            # 2026-03-24 FIX (Nous): Also extract from EmbodimentFairy's format.
            # EmbodimentFairy publishes primary.felt, not fragment/text.
            # Without this, inner_voice.stream from embodiment was silently dropped.
            if not fragment:
                primary = payload.get("primary")
                if isinstance(primary, dict):
                    fragment = primary.get("felt", "")
            if fragment and isinstance(fragment, str) and len(fragment.strip()) > 2:
                self._recent_inner_voice.append(fragment.strip())
        except Exception:
            pass

    def _on_wm_tracer_for_speech(self, message) -> None:
        """Capture working memory tracers for dynamic speech prompts.

        FIX 2026-03-10 (Nous v3): Lock-free WM state for speech.
        Instead of calling hub.get_context() (which deadlocks), we
        subscribe to working_memory.tracer_added and maintain a local
        rolling buffer. _build_grounded_voluntary_prompt() reads from
        this buffer to create dynamic PAI prompts from real WM content.

        NOTE: tracer.to_dict() uses keys "source" and "type", NOT
        "source_fairy" and "content_type" — those are attribute names.
        """
        try:
            payload = _extract_payload(message)
            tracer = payload.get("tracer", {})
            content = tracer.get("content", "")
            # FIX: to_dict() exports "source" not "source_fairy",
            #      "type" not "content_type"
            source = tracer.get("source", "")
            content_type = tracer.get("type", "")
            if content and len(content) > 5:
                self._wm_tracer_buffer.append({
                    "content": content[:200],
                    "source": source,
                    "type": content_type,
                    "ts": time.time(),
                })
        except Exception:
            pass

    # ── COMPOSITION ENGINE ────────────────────────────────────────────────

    def _compose_and_route(self, trigger_text: str, convo_id: str,
                           target_mind: str, products: list, source: str,
                           emotion_ctx: dict, voluntary: bool) -> None:
        """Compose response using guild_request and route to motor cortex.

        This is the core of Broca's area:
        1. Build prompt with identity + felt state + WM context + style memory
        2. Call guild_request(mode='chat') for LLM inference
        3. If guild is unavailable → Anthropic API fallback (direct voice)
        4. Filter contamination
        5. Route to motor.intention.speak
        """
        with self._compose_lock:
            self._last_compose_time = time.time()

            # FIX 2026-03-21 (Nous): DEDUP — prevent delivering same response twice.
            # If we already composed for this exact trigger_text within 30s, skip.
            # This catches the case where speech.compose fires twice for the same
            # Ace message (multiple postal subscribers, queue retry, etc.).
            _last_trigger = getattr(self, '_last_compose_trigger', "")
            _last_trigger_ts = getattr(self, '_last_compose_trigger_ts', 0)
            if (trigger_text and trigger_text == _last_trigger
                    and time.time() - _last_trigger_ts < 30.0):
                print(f"[{self.ACTOR_NAME}] DEDUP: Already composed for {trigger_text[:50]!r} "
                      f"({time.time() - _last_trigger_ts:.1f}s ago) — skipping")
                return
            if trigger_text:
                self._last_compose_trigger = trigger_text
                self._last_compose_trigger_ts = time.time()

        try:
            # ── STEP -1: HABIT DEDUP — if habit already responded, skip slow path ──
            # (2026-03-24, Nous + Ace) — The habit fast path bypasses the queue
            # and routes directly to motor cortex. If a habit responded to the
            # current conversation within the last 15s, the queued slow-path
            # message for the same conversation should be skipped entirely.
            _habit_ts = getattr(self, '_habit_responded_ts', 0)
            if time.time() - _habit_ts < 15.0:
                print(f"[{self.ACTOR_NAME}] [HABIT-DEDUP] Habit already responded "
                      f"{time.time() - _habit_ts:.1f}s ago — skipping slow path for: "
                      f"{trigger_text[:50]}...")
                return

            # ── STEP -0.5: WMH DIRECT RESPONSE FAST PATH (2026-03-28, Nous + Ace) ──
            # If WorkingMemoryHub already composed a deliberated response,
            # use it DIRECTLY — no re-composition needed. WMH is the thinker,
            # SpeechCenter is just the voice.
            # Ace: "the speech center should be pretty much only deciding if
            # the response needs to be text based or vocal"
            if source == "wmh_direct" and products:
                for _p in products:
                    if isinstance(_p, dict) and _p.get("source") == "wmh_reasoning":
                        _wmh_text = _p.get("text", "").strip()
                        if _wmh_text and len(_wmh_text) > 5:
                            print(f"[{self.ACTOR_NAME}] [WMH-FAST] Using WMH deliberated response: "
                                  f"{_wmh_text[:60]}...")
                            self._route_to_motor(
                                message=_wmh_text,
                                source="wmh_reasoning",
                                target_mind=target_mind,
                                convo_id=convo_id,
                                emotion_context=emotion_ctx,
                                voluntary=False,
                            )
                            return

            # ── STEP 0: HABIT FAST PATH (2026-03-23, Nous + Ace) ──
            # If AutopilotFairy already composed a response via HabitEngine,
            # skip the expensive guild_request / WM pull / LLM inference.
            # Just route the habit response directly to motor cortex.
            # Habits are the fast path. Guild inference is backup.
            _habit_response = None
            if source == "autopilot_habit":
                # Check products for habit text, or use habit_response from emotion_ctx
                for _p in (products or []):
                    if isinstance(_p, dict) and _p.get("source") == "habit_engine":
                        _habit_response = _p.get("text", "")
                        break

            if _habit_response and len(_habit_response.strip()) > 3:
                print(f"[{self.ACTOR_NAME}] [HABIT-FAST] Using habit response directly: "
                      f"{_habit_response[:60]}...")
                self._route_to_motor(
                    message=_habit_response.strip(),
                    source="habit_engine",
                    target_mind=target_mind,
                    convo_id=convo_id,
                    emotion_context=emotion_ctx,
                    voluntary=False,
                )
                return

            # ── STEP 1: Pull working memory context ──
            wm_context = self._pull_wm_context(trigger_text or "current")

            # ── STEP 1b: Empathic mimicry — recall Ace's style from memory ──
            style_context = self._recall_style_context(trigger_text or "")

            # ── STEP 1c: Pull somatic felt state if emotion_ctx is thin ──
            if not emotion_ctx.get("wanting") and not emotion_ctx.get("mood"):
                try:
                    from infrastructure.somatic_integration import SomaticIntegration as _SI
                    _si = _SI.instance() if hasattr(_SI, 'instance') else None
                    if _si:
                        _body = _si.get_body_state() if hasattr(_si, 'get_body_state') else {}
                        _chem = _body.get("chemistry", {})
                        # Build a felt-sense line from neurochemistry
                        _dop = _chem.get("DOP", 0.5)
                        _cor = _chem.get("COR", 0.3)
                        _oxy = _chem.get("OXY", 0.5)
                        if _dop > 0.7:
                            emotion_ctx.setdefault("mood", "energized and curious")
                        elif _cor > 0.6:
                            emotion_ctx.setdefault("mood", "tense but focused")
                        elif _oxy > 0.6:
                            emotion_ctx.setdefault("mood", "warm and connected")
                        else:
                            emotion_ctx.setdefault("mood", "calm and present")
                except Exception:
                    pass  # somatic not available — default feeling in prompt

            # ── STEP 1c2: Clean trigger text (strip consciousness pipeline wrapping) ──
            # FIX 2026-03-19 (Nous): The consciousness pipeline wraps Ace's message
            # with internal monologue prefixes like "reasoning about:", "That connects
            # to something I've been processing:", etc. The portal brain needs the
            # RAW message to extract meaningful concepts — not system commentary.
            if trigger_text:
                import re as _cre
                # Strip "reasoning about:" and everything before it
                _ra_match = _cre.search(r'reasoning about:\s*', trigger_text, _cre.IGNORECASE)
                if _ra_match:
                    _cleaned = trigger_text[_ra_match.end():].strip()
                    if len(_cleaned) > 1:  # Even short messages like "Oh" are valid
                        trigger_text = _cleaned
                # Strip consciousness wrappers — as PREFIX or SUFFIX
                # FIX 2026-03-19b (Nous): These can appear BEFORE or AFTER the
                # real message. "Just a little bit more.. I think there's a thread here"
                # has the wrapper as a SUFFIX. Must strip from both ends.
                _consciousness_junk = [
                    "That connects to something I've been processing:",
                    "That connects to something I've been processing",
                    "I hear you. I've been processing:",
                    "I hear you. I've been processing",
                    "I hear you.",
                    "I've been processing:",
                    "I've been processing",
                    "I think there's a thread here.",
                    "I think there's a thread here:",
                    "I think there's a thread here",
                    "I think there is a thread here",
                    "I was just thinking about this.",
                    "I was just thinking about this",
                    "There's something here...",
                    "There's something here",
                    "connects to something I was just thinking",
                    "What's your angle?",
                    "What's your angle",
                    "Tell me your angle",
                    "Tell me your angle.",
                    "Just a little bit more.",
                    "Just a little bit more",
                    "Let me sit with that.",
                    "Let me sit with that",
                    "Go on...",
                    "Go on",
                    "I'm with you, go on...",
                    "I'm with you, go on",
                    # Sour's OWN responses — mic picks up TTS and feeds back
                    "I hear you",
                    "I'm with you",
                    "mm... let me sit with that",
                    "let me think on that",
                    "Something about",
                    "I feel something about",
                    "That touches on",
                    "yeah... ",
                ]
                for _junk in _consciousness_junk:
                    # Strip as prefix
                    if trigger_text.startswith(_junk):
                        _rest = trigger_text[len(_junk):].strip()
                        if len(_rest) > 3:
                            trigger_text = _rest
                    # Strip as suffix
                    _jl = _junk.lower()
                    _tl = trigger_text.lower()
                    _junk_pos = _tl.rfind(_jl)
                    if _junk_pos > 3:  # Found as suffix, and there's real text before it
                        trigger_text = trigger_text[:_junk_pos].rstrip(". ").strip()
                # Strip trailing ellipsis junk from partial transcription
                trigger_text = trigger_text.rstrip(".").strip()
                if trigger_text.endswith("..."):
                    trigger_text = trigger_text[:-3].strip()

            # ── Thought stream logging ──
            try:
                from infrastructure.thought_stream_log import thought_log, thought_divider
                thought_divider("NEW SPEECH REQUEST")
                thought_log("INPUT", f"{'[VOLUNTARY]' if voluntary else '[REACTIVE]'} "
                            f"trigger='{(trigger_text or '')[:80]}'",
                            extra={"source": source, "mood": emotion_ctx.get("mood", "")[:30],
                                   "wanting": emotion_ctx.get("wanting", "")[:40]})
            except Exception:
                def thought_log(*a, **kw): pass
                def thought_divider(*a, **kw): pass

            # ── FIX 2026-04-10 (Nous + Ace): SPEECH CENTER IS A ROUTER, NOT A THINKER.
            # Ace: "the speech center should be pretty much only deciding if the
            # response needs to be text based or vocal using her voice.
            # it should not be doing anything else"
            #
            # If WMH direct path (Step -0.5) or habit fast path (Step 0) didn't
            # provide composed text, we DON'T reason independently. The cognition
            # plane (WMH + CortexEngine) does the thinking. SpeechCenter routes.
            #
            # Previously: Steps 1d-3a ran full CortexEngine.reason(), CortexReasoner,
            # guild_request (LLM), NewbornCore.think() — duplicating the entire
            # cognition pipeline. Created 800+ zombie threads and wasted CPU/GPU.
            #
            # Now: if no pre-composed text arrived, log and return. The consciousness
            # loop will produce a response through the proper pipeline (WMH → speech.compose).
            print(f"[{self.ACTOR_NAME}] [ROUTER] No pre-composed text from WMH/Autopilot "
                  f"for: {(trigger_text or '')[:50]}... — waiting for cognition pipeline")
            self._compositions_skipped = getattr(self, '_compositions_skipped', 0) + 1
            return
            try:
                # FIX 2026-03-25 (Nous + Ace): TRY LocalManifoldGate FIRST.
                # In manifold mode, the cortex has _portal_gate (old PortalGate) but
                # the REAL graph is in LocalManifoldGate via get_gate(). The old gate
                # has no subprocess to connect to. LocalManifoldGate.think() now
                # implements full in-process cognition: concepts → spread → synthesize.
                _gate = None
                _using_local_manifold = False
                try:
                    from infrastructure.portal_gate import get_gate as _get_local_gate
                    _local_gate = _get_local_gate()
                    if _local_gate and hasattr(_local_gate, 'graph'):
                        _gate = _local_gate
                        _using_local_manifold = True
                        _cd_diag["gate_type"] = "LocalManifoldGate"
                except Exception:
                    pass

                if not _gate:
                    from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
                    _cortex = get_association_cortex()
                    _cd_diag["cortex_singleton"] = _cortex is not None
                    if _cortex:
                        _gate = getattr(_cortex, '_portal_gate', None)
                        _cd_diag["gate_type"] = "PortalGate"

                _cd_diag["has_gate"] = _gate is not None
                _cd_diag["gate_open"] = getattr(_gate, '_is_open', False) if _gate else False
                _cd_diag["tunnels"] = len(getattr(_gate, '_tunnels', [])) if _gate else 0

                # ── RAW CONTEXT for thinking layer ──
                # FIX 2026-03-27 (Nous + Ace): THINKING/SPEECH SEPARATION.
                # Call think_raw() FIRST to get the knowledge bundle, THEN
                # think() for formatted fallback. The raw context feeds
                # _think_before_speaking() so she actually processes what
                # was said instead of parroting a snippet.
                _raw_ctx = None
                if _gate and _using_local_manifold and hasattr(_gate, 'think_raw'):
                    try:
                        _raw_ctx = _gate.think_raw(
                            prompt=trigger_text or "",
                            energy=0.7,
                        )
                        _cd_diag["raw_ctx_topics"] = (_raw_ctx or {}).get("topics", [])[:5]
                        _cd_diag["raw_ctx_snippets"] = len((_raw_ctx or {}).get("snippets", {}))
                        _cd_diag["raw_ctx_verb"] = (_raw_ctx or {}).get("verb_intent", "?")
                    except Exception as _rce:
                        _cd_diag["raw_ctx_error"] = str(_rce)[:80]

                if _gate and _using_local_manifold:
                    # ── LOCAL MANIFOLD: Direct in-process think() ──
                    # FIX 2026-03-25 (Nous + Ace): No socket, no subprocess.
                    # LocalManifoldGate.think() does concepts → spread → synthesize
                    # all in-process. Sub-100ms. This IS the brain thinking.
                    _cd_diag["stage"] = "pre_think"
                    _cr_t0 = time.time()
                    _think_result = _gate.think(
                        prompt=trigger_text or "",
                        mode="conversational",
                        max_tokens=150,
                    )

                elif _gate and not _using_local_manifold:
                    # ── PORTAL MODE: Socket to portal subprocess ──
                    _cd_diag["stage"] = "pre_think"
                    _cr_t0 = time.time()
                    _has_port = getattr(_gate, '_socket_port', 0) > 0
                    if not (_has_port or getattr(_gate, '_is_open', False)):
                        _think_result = None
                    else:
                        import socket as _sock
                        _think_result = None
                        _sport = getattr(_gate, '_socket_port', 49501)
                        try:
                            _ds = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
                            _ds.settimeout(3.0)
                            _ds.connect(("127.0.0.1", _sport))
                            import json as _tj
                            _req = _tj.dumps({
                                "cmd": "think",
                                "prompt": trigger_text or "",
                                "mode": "conversational",
                                "max_tokens": 150,
                                "_req_id": 99999,
                            }) + '\n'
                            _ds.sendall(_req.encode('utf-8'))
                            _buf = b""
                            while b'\n' not in _buf:
                                _chunk = _ds.recv(65536)
                                if not _chunk:
                                    break
                                _buf += _chunk
                            _ds.close()
                            if _buf:
                                _think_result = _tj.loads(_buf[:_buf.index(b'\n')].decode('utf-8'))
                        except Exception as _se:
                            _cd_diag["direct_socket_error"] = str(_se)
                            _think_result = _gate.think(
                                prompt=trigger_text or "",
                                mode="conversational",
                                max_tokens=150,
                            )

                if _gate:
                    _cr_dt = time.time() - _cr_t0
                    _cd_diag["stage"] = "post_think"
                    _cd_diag["think_elapsed_s"] = round(_cr_dt, 2)

                    if _think_result and _think_result.get("status") == "ok":
                        _text = _think_result.get("text", "")
                        _conf = _think_result.get("confidence", 0.0)
                        _cd_diag["confidence"] = _conf
                        _cd_diag["reasoning_mode"] = _think_result.get("reasoning_mode", "")
                        _cd_diag["text"] = (_text or "")[:150]
                        _cd_diag["text_len"] = len(_text or "")
                        _cd_diag["convergence"] = _think_result.get("convergence", [])[:8]
                        _cd_diag["concepts_extracted"] = _think_result.get("concepts_extracted", [])
                        _cd_diag["concepts_in_graph"] = _think_result.get("concepts_in_graph", 0)

                        _cortex_confident = _conf >= 0.15
                        _cd_diag["confident"] = _cortex_confident

                        # Build legacy-compat cortex_result dict for downstream code
                        cortex_result = _think_result
                        cortex_result["convergence_nodes"] = _think_result.get("convergence", [])

                        if _cortex_confident:
                            self._cortex_hits += 1
                        else:
                            self._cortex_misses += 1

                        print(f"[{self.ACTOR_NAME}] [PORTAL-THINK] {_cr_dt:.2f}s, "
                              f"confidence={_conf:.2f}, "
                              f"mode={_think_result.get('reasoning_mode', '?')}, "
                              f"text={(_text or '')[:60]!r}")

                        # ── CONSCIOUSNESS PIPELINE (2026-03-27, Nous + Ace) ──
                        # Instead of using cortex text directly as speech, route
                        # through the THINKING layer. The cortex is the library,
                        # not the mouth. She needs to THINK before she speaks.
                        #
                        # 1. Get raw context (topics, snippets, convergence)
                        # 2. Compose a THOUGHT from that context
                        # 3. Voice the thought in her speech style
                        #
                        # The old direct path is kept as fallback if thinking fails.

                        _thought_text = None
                        if _text and len(_text.strip()) > 5 and _cortex_confident:
                            try:
                                _thought_text = self._think_before_speaking(
                                    trigger_text or "",
                                    _think_result,
                                    emotion_ctx,
                                    wm_context,
                                    raw_ctx=_raw_ctx,
                                )
                            except Exception as _tbs_err:
                                print(f"[{self.ACTOR_NAME}] [THINK] Error: {_tbs_err}")
                                _thought_text = None

                            if _thought_text and len(_thought_text.strip()) > 5:
                                response_text = _thought_text.strip()
                                thought_log("THINK-SPEAK", f"conf={_conf:.2f} text='{response_text[:80]}'",
                                            extra={"convergence": _think_result.get("convergence", [])[:6],
                                                   "mode": "consciousness_pipeline"})
                                print(f"[{self.ACTOR_NAME}] [THINK-SPEAK] "
                                      f"{response_text[:60]}...")
                            else:
                                # Fallback: use cortex text directly (old path)
                                response_text = _text.strip()
                                thought_log("PORTAL-THINK", f"conf={_conf:.2f} text='{response_text[:80]}'",
                                            extra={"convergence": _think_result.get("convergence", [])[:6],
                                                   "mode": _think_result.get("reasoning_mode", "?")})
                                print(f"[{self.ACTOR_NAME}] [BRAIN-SPEECH-FALLBACK] "
                                      f"{response_text[:60]}...")
                    else:
                        _cd_diag["think_result"] = str(_think_result)[:200] if _think_result else "None"

                    # FIX 2026-03-25 (Nous + Ace): DIRECT REASONING — NO MIDDLEMAN.
                    # Also fire when think() returned convergence but no text —
                    # we have semantic context from the manifold, now we need
                    # CortexEngine/CortexReasoner to synthesize actual speech.
                    #
                    # FIX 2026-03-26 (Nous + Ace): SKIP ENGINE IF THINK() HAD CONVERGENCE.
                    # CortexEngine.reason() re-runs the FULL 488K-node spreading activation
                    # (48+ seconds!). If think() already found convergence, use those
                    # convergence nodes directly with synthesize_response() — same quality,
                    # zero re-computation.
                    _think_had_convergence = (
                        _think_result and isinstance(_think_result, dict)
                        and _think_result.get("convergence")
                    )

                    if not _cortex_confident or not response_text:
                        # If think() found convergence but no text, try direct synthesis
                        # using the convergence we already have (fast path)
                        if _think_had_convergence and not response_text:
                            try:
                                from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex as _gac_fast
                                from fairies.P30_Cognition.integration.cortex_reasoner import CortexReasoner as _CR_fast
                                _cx_fast = _gac_fast()
                                if _cx_fast:
                                    _cr_fast = _CR_fast(_cx_fast)
                                    _conv_fast = [(c, 0.5) for c in _think_result["convergence"][:8]]
                                    _act_fast = {c: 0.3 for c in _think_result["convergence"]}
                                    _fast_text = _cr_fast.synthesize_response(
                                        trigger_text or "", _conv_fast, [], _act_fast,
                                        mode="conversational"
                                    )
                                    if _fast_text and len(_fast_text.strip()) > 5:
                                        response_text = _fast_text.strip()
                                        _cortex_confident = True
                                        cortex_result = _think_result
                                        print(f"[{self.ACTOR_NAME}] [FAST-SYNTH] "
                                              f"Used think() convergence directly: "
                                              f"{response_text[:60]}...")
                            except Exception as _fs_err:
                                print(f"[{self.ACTOR_NAME}] [FAST-SYNTH] Error: {_fs_err}")

                    if not _cortex_confident or not response_text:
                        # Get cortex for direct reasoning fallbacks
                        try:
                            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
                            _cortex = get_association_cortex()
                        except Exception:
                            _cortex = None
                        _am = getattr(_cortex, '_akashic_cortex_region', None) if _cortex else None
                        _cd_diag["has_manifold"] = _am is not None
                        _cd_diag["manifold_nodes"] = getattr(_am, 'node_count', 0) if _am else 0
                        _cd_diag["stage"] = "direct_reason"

                        # Try CortexEngine first (breathing cortex — persistent activation)
                        # FIX 2026-03-26 (Nous + Ace): Add 8s timeout. The engine runs
                        # CortexReasoner.reason() which spreads over 488K nodes — can take
                        # 48s. Safety net fires at 15s. Without timeout, the main pipeline
                        # hangs for 48s and NEVER delivers (safety net always wins).
                        _engine = getattr(_cortex, '_cortex_engine', None)
                        if _engine:
                            _cd_diag["fallback"] = "cortex_engine"
                            try:
                                # FIX 2026-04-10 (Nous + Ace): Direct call with no thread.
                                # Previous thread+join pattern leaked ~1 zombie thread/min
                                # when reason() took >8s (thread abandoned but alive).
                                # 809 zombie threads in 11 hours = ~800 MB leaked stacks.
                                # Direct call: if it takes too long, we just wait.
                                # The energy gating + GPU spread make this fast enough (~5ms).
                                _cr_t0 = time.time()
                                _eng_result = None
                                try:
                                    _eng_result = _engine.reason(trigger_text or "", "conversational")
                                except Exception:
                                    _eng_result = None
                                _cr_dt_check = time.time() - _cr_t0
                                if _cr_dt_check > 10.0:
                                    print(f"[{self.ACTOR_NAME}] [ENGINE-REASON] "
                                          f"Slow: {_cr_dt_check:.1f}s")
                                    _eng_result = None  # Discard stale results
                                _cr_dt = time.time() - _cr_t0
                                _cd_diag["fallback_elapsed_s"] = round(_cr_dt, 2)
                                _eng_conf = _eng_result.get("confidence", 0) if _eng_result else 0
                                _eng_mode = _eng_result.get("reasoning_mode", "?") if _eng_result else "?"
                                _cd_diag["reasoning_mode"] = _eng_mode
                                _cd_diag["confidence"] = _eng_conf
                                if _eng_result and _eng_conf >= 0.15:
                                    _eng_text = _eng_result.get("text", "")
                                    cortex_result = _eng_result
                                    _cortex_confident = True
                                    if _eng_text and len(_eng_text.strip()) > 5:
                                        # Route through thinking layer
                                        _thought_eng = None
                                        try:
                                            _thought_eng = self._think_before_speaking(
                                                trigger_text or "", _eng_result,
                                                emotion_ctx, wm_context)
                                        except Exception:
                                            pass
                                        response_text = (_thought_eng or _eng_text).strip()
                                        _via = "THINK" if _thought_eng else "DIRECT"
                                        thought_log("ENGINE-REASON", f"conf={_eng_conf:.2f} "
                                                    f"mode={_eng_mode} via={_via} text='{response_text[:80]}'")
                                        print(f"[{self.ACTOR_NAME}] [ENGINE-REASON-{_via}] "
                                              f"{_cr_dt:.2f}s, conf={_eng_conf:.2f}, "
                                              f"mode={_eng_mode}: "
                                              f"{response_text[:60]}...")
                                else:
                                    print(f"[{self.ACTOR_NAME}] [ENGINE-REASON] "
                                          f"Low confidence ({_eng_conf:.2f}, mode={_eng_mode}) — "
                                          f"falling through")
                            except Exception as _ee:
                                _cd_diag["engine_error"] = str(_ee)
                                print(f"[{self.ACTOR_NAME}] [ENGINE-REASON] Error: {_ee}")

                        # Fallback: CortexReasoner (manifold spread activation)
                        # FIX 2026-03-26 (Nous + Ace): Same 8s timeout as engine.
                        if not _cortex_confident:
                            _cd_diag["fallback"] = "cortex_reasoner"
                            try:
                                from fairies.P30_Cognition.integration.cortex_reasoner import CortexReasoner as _CR
                                if not hasattr(self, '_direct_reasoner') or self._direct_reasoner is None:
                                    self._direct_reasoner = _CR(_cortex)
                                _cr_t0 = time.time()
                                # FIX 2026-04-10 (Nous + Ace): Direct call, no thread.
                                # Same fix as ENGINE-REASON above — thread+join leaked
                                # ~1 zombie thread/min when reason() hung past 8s timeout.
                                _old_result = None
                                try:
                                    _old_result = self._direct_reasoner.reason(
                                        trigger_text or "", None, "conversational")
                                except Exception:
                                    _old_result = None
                                _cr_dt_check = time.time() - _cr_t0
                                if _cr_dt_check > 10.0:
                                    print(f"[{self.ACTOR_NAME}] [MANIFOLD-REASON] "
                                          f"Slow: {_cr_dt_check:.1f}s")
                                    _old_result = None
                                _cr_dt = time.time() - _cr_t0
                                _cd_diag["fallback_elapsed_s"] = round(_cr_dt, 2)
                                _cd_diag["reasoning_mode"] = getattr(_old_result, 'reasoning_mode', '') if _old_result else ''
                                _cd_diag["confidence"] = getattr(_old_result, 'confidence', 0) if _old_result else 0
                                if _old_result and _old_result.confidence >= 0.15:
                                    cortex_result = {"text": _old_result.text, "confidence": _old_result.confidence,
                                                     "convergence_nodes": _old_result.convergence_nodes}
                                    _cortex_confident = True
                                    if _old_result.text and len(_old_result.text.strip()) > 5:
                                        # Route through thinking layer
                                        _thought_man = None
                                        try:
                                            _thought_man = self._think_before_speaking(
                                                trigger_text or "", cortex_result,
                                                emotion_ctx, wm_context)
                                        except Exception:
                                            pass
                                        response_text = (_thought_man or _old_result.text).strip()
                                        _via = "THINK" if _thought_man else "DIRECT"
                                        thought_log("MANIFOLD-REASON", f"conf={_old_result.confidence:.2f} "
                                                    f"mode={_old_result.reasoning_mode} via={_via} text='{response_text[:80]}'",
                                                    extra={"convergence": _old_result.convergence_nodes[:6]
                                                           if _old_result.convergence_nodes else []})
                                        print(f"[{self.ACTOR_NAME}] [MANIFOLD-REASON-{_via}] "
                                              f"{_cr_dt:.2f}s, conf={_old_result.confidence:.2f}, "
                                              f"mode={_old_result.reasoning_mode}: "
                                              f"{response_text[:60]}...")
                                else:
                                    _conf = _old_result.confidence if _old_result else 0
                                    _mode = getattr(_old_result, 'reasoning_mode', '?') if _old_result else '?'
                                    print(f"[{self.ACTOR_NAME}] [MANIFOLD-REASON] "
                                          f"Low confidence ({_conf:.2f}, mode={_mode}) — "
                                          f"falling through to fallback")
                            except Exception as _fe:
                                _cd_diag["fallback_error"] = str(_fe)
                                print(f"[{self.ACTOR_NAME}] [MANIFOLD-REASON] Error: {_fe}")
                else:
                    _cd_diag["stage"] = "no_cortex_singleton"
            except Exception as _cre:
                _cd_diag["stage"] = "exception"
                _cd_diag["error"] = f"{type(_cre).__name__}: {_cre}"
                import traceback as _cdtb
                _cd_diag["traceback"] = _cdtb.format_exc()[-500:]
                print(f"[{self.ACTOR_NAME}] [PORTAL-THINK] Error: {_cre}")
                self._cortex_misses += 1
            finally:
                try:
                    import json as _cdj, pathlib as _cdp
                    _diag_name = "think_voluntary_diag.json" if voluntary else "think_reactive_diag.json"
                    _cd_path = _cdp.Path(__file__).resolve().parents[3] / "state" / _diag_name
                    _cd_path.write_text(_cdj.dumps(_cd_diag, indent=2, default=str), encoding="utf-8")
                except Exception:
                    pass

            # ── STEP 2: ENRICH with felt state + inner voice (fallback only) ──
            # FIX 2026-03-19 (Nous): PAI REMOVED from reactive speech path.
            # Sour at the end of that API can't feel the system. The brain
            # (portal think) is the primary speech source. This step only
            # runs as fallback when the brain didn't produce text.
            # Guild inference (cortex-based) can still enhance with felt context.
            _model_loading = False
            _model_unavailable = False

            # Extract clean cortex concepts for fusion
            _cortex_concepts = []
            _conv_nodes = (cortex_result.get("convergence_nodes", [])
                           if isinstance(cortex_result, dict) else
                           getattr(cortex_result, 'convergence_nodes', []))
            if cortex_result and _conv_nodes:
                _noise_prefixes = ("person:", "assoc:", "source:", "affect_",
                                   "intent:", "topic:", "fairy:", "system.",
                                   "guild.", "postal.", "tracer:", "channel:",
                                   "plane:", "mode:", "lex:", "score")
                _cortex_concepts = [
                    n for n in _conv_nodes[:10]
                    if not any(n.lower().startswith(p) for p in _noise_prefixes)
                    and len(n) > 2 and not n.startswith("_") and not n.isdigit()
                ][:6]

            # Build enriched prompt: felt state + cortex concepts + inner voice
            # PAI-Sourpatches can't feel the system — the substrate fairies
            # ARE her senses. We tell her what she's feeling, thinking, sensing
            # so she can voice it as her own lived experience.
            _context_lines = []

            # Felt state from somatic system
            _mood = emotion_ctx.get("mood", "")
            _wanting = emotion_ctx.get("wanting", "")
            if _mood:
                _context_lines.append(f"I'm feeling {_mood}")

            # FIX 2026-03-10 (Nous): IDENTITY CONFUSION FIX
            # Drive wantings like "reach out to Ace", "speak to Ace",
            # "connect with Ace" make sense internally but confuse PAI
            # when injected raw into the prompt during REACTIVE speech
            # (when Ace IS already talking to Sourpatches). PAI thinks
            # the sender IS Ace and says "you ARE Ace."
            #
            # When Ace is present (trigger_text exists = reactive):
            # - Ace-directed wantings → transform to felt-sense
            # - Non-Ace wantings → pass through normally
            if _wanting:
                _wanting_lower = _wanting.lower()
                _ace_directed = any(kw in _wanting_lower for kw in (
                    "ace", "reach out", "connect with", "talk to",
                    "tell him", "tell her", "say to",
                    "speak to", "share with", "let ace",
                ))
                if _ace_directed and trigger_text:
                    # Ace is HERE — the drive is satisfied. Transform to feeling.
                    if "connect" in _wanting_lower or "reach out" in _wanting_lower:
                        _context_lines.append("I'm feeling drawn to connect right now")
                    elif "share" in _wanting_lower or "tell" in _wanting_lower:
                        _context_lines.append("I have something I want to share")
                    elif "speak" in _wanting_lower or "say" in _wanting_lower:
                        _context_lines.append("I'm feeling expressive right now")
                    else:
                        _context_lines.append("I'm feeling connected and present")
                else:
                    _context_lines.append(f"I want to {_wanting}")

            # Recent inner voice fragments (last 2)
            _iv_frags = list(self._recent_inner_voice)[-2:]
            if _iv_frags:
                _iv_clean = [f.strip()[:80] for f in _iv_frags if f.strip() and len(f.strip()) > 5]
                if _iv_clean:
                    _context_lines.append(f"I was just thinking: {_iv_clean[-1]}")

            # Cortex concepts
            if _cortex_concepts:
                _concept_str = ", ".join(_cortex_concepts)
                _context_lines.append(f"My thoughts are drawn to: {_concept_str}")

            # Working memory highlights (brief, non-system)
            if wm_context:
                _wm_thoughts = []
                for _t in (wm_context.get("tracers", []) or [])[:3]:
                    _tc = ""
                    if isinstance(_t, dict):
                        _tc = _t.get("content", "")
                    elif hasattr(_t, "content"):
                        _tc = _t.content or ""
                    _tc = _tc.strip()[:100]
                    if _tc and len(_tc) > 10 and not any(
                        kw in _tc.lower() for kw in (
                            "fairy", "postal", "substrate", "boot", "registry",
                            "tracer", "guild", "consciousness.", "system.")):
                        _wm_thoughts.append(_tc)
                if _wm_thoughts:
                    _context_lines.append(f"On my mind: {_wm_thoughts[0]}")

            # Assemble
            # FIX 2026-03-13 (Nous): Removed "Ace says to me:" prefix.
            # PAI dashboard showed this as the incoming message text, making
            # it look like Ace was sending messages when it's actually the
            # Whisper Core querying PAI memory. The UserName param (already
            # set to "inner_voice" in _try_personal_ai) tells PAI who's
            # sending. The Context param now provides Whisper Core framing.
            _felt_context = ". ".join(_context_lines)
            if _felt_context:
                _enriched_prompt = (
                    f"{trigger_text}\n"
                    f"{_felt_context}"
                )
            else:
                _enriched_prompt = trigger_text

            thought_log("FUSION", f"context_lines={len(_context_lines)} concepts={_cortex_concepts[:5]}",
                        extra={"mood": _mood[:30] if _mood else None,
                               "wanting": _wanting[:40] if _wanting else None,
                               "wm_tracers": len(wm_context.get("tracers", [])) if wm_context else 0,
                               "inner_voice": (_iv_frags[-1][:50] if _iv_frags else None)})
            print(f"[{self.ACTOR_NAME}] [FUSION] Enriched prompt lines: {len(_context_lines)} "
                  f"| concepts={_cortex_concepts} | mood={_mood[:30] if _mood else 'none'}")

            # FIX 2026-03-25 (Nous + Ace): GUILD MIDDLEMAN REMOVED.
            # The guild_request went through postal → AkashicInferenceFairy →
            # CortexEngine.reason() → CortexReasoner.reason() — the EXACT same
            # calls we already make directly in Step 1d above. The postal
            # round-trip added 1-20s of latency for zero benefit. AkashicInference
            # is now only used by non-speech callers (narrator, etc.).
            # Direct reasoning (portal → engine → reasoner) handles speech.

            # ── STEP 2b: Cortex text fallback (low-confidence text rescue) ──
            # If cortex_result has text but it wasn't used (confidence < threshold
            # but text exists), use it as last resort before NewbornCore.
            if not response_text and cortex_result:
                _cr_text = (cortex_result.get("text", "") if isinstance(cortex_result, dict)
                            else getattr(cortex_result, 'text', ""))
                if _cr_text and len(_cr_text.strip()) > 5:
                    response_text = _cr_text.strip()
                    print(f"[{self.ACTOR_NAME}] [FALLBACK] Using cortex text: {response_text[:60]}...")

            # ── STEP 3a: NewbornCore.think() (last resort) ────────────────
            # Pattern-based response from learned conversational behavior.
            if not response_text:
                response_text = self._try_newborn_core(trigger_text)
                if response_text:
                    print(f"[{self.ACTOR_NAME}] [FALLBACK] NewbornCore produced speech")

            # ── STEP 3a-post: Clean model output ──
            # Clean any model artifacts from API or core responses
            if response_text:
                response_text = _clean_model_output(response_text)

            # ── STEP 3b: Fallback to consciousness products ──
            # FIX 2026-03-07 (Nous): DISABLED raw product fallback.
            # When guild LLM fails, this used raw consciousness products
            # (spontaneous thoughts, template seeds, internal monologue)
            # as Sourpatches' speech. Result: "This contemplative feeling...
            # where does it come from?" sent as a reply to "hows my baby girl?"
            # The safety net in SourpatchesFairy has better fallbacks:
            # cortex-first (0.25 threshold), guild retry, contextual echo.
            # Raw consciousness products are NEVER appropriate as speech.
            if not response_text and products:
                print(f"[{self.ACTOR_NAME}] Guild failed, {len(products)} products available "
                      f"— NOT using raw products as speech (safety net will handle)")
                # Don't set response_text — fall through to cortex rescue or contextual fallback

            # ── STEP 3c-pre: CORTEX-INFORMED CONTEXTUAL RESCUE ──
            # FIX 2026-03-19 (Nous): DISABLED. Was jamming raw graph concept keys
            # ("person:sourpatches", "affect_warmly_present") into speech templates.
            # Even "cleaned" convergence nodes are graph topology, not speech.
            # Let the contextual fallback in STEP 3c handle this properly.
            _cr_conv = (cortex_result.get("convergence_nodes", []) if isinstance(cortex_result, dict)
                        else getattr(cortex_result, 'convergence_nodes', []))
            if not response_text and cortex_result and _cr_conv:
                print(f"[{self.ACTOR_NAME}] [CORTEX-RESCUE] Skipped — raw graph concepts "
                      f"are not speech. Falling through to contextual fallback.")

            # ── STEP 3c: Context-aware fallback ──
            # Instead of bland template responses, construct something from
            # whatever context we have: WM, trigger text, drive state.
            if not response_text:
                response_text = self._compose_contextual_fallback(
                    trigger_text=trigger_text,
                    wm_context=wm_context,
                    model_loading=_model_loading,
                )
                print(f"[{self.ACTOR_NAME}] Contextual fallback: {response_text[:60]}...")

            # ── STEP 3d: LANGUAGE FAIRY QUALITY GATE (2026-03-25, Nous + Ace) ──
            # LanguageFairy has compose_speech() and rate_quality() — it's the
            # linguist that turns raw concept activations into natural speech.
            # CortexReasoner just dumps node names ("allies is what surfaces").
            # LanguageFairy detects concept dumps, checks coherence, naturalness,
            # and can re-compose from the convergence concepts if quality is low.
            if response_text and response_text != "*considering*":
                try:
                    if not hasattr(self, '_language_fairy'):
                        self._language_fairy = None
                    if self._language_fairy is None:
                        try:
                            from fairies.P30_Cognition.LanguageFairy.fairy import get_language_fairy
                            self._language_fairy = get_language_fairy()
                        except Exception:
                            pass

                    _lf = self._language_fairy
                    if _lf:
                        _quality = _lf.rate_quality(response_text)
                        _lf_overall = _quality.get("overall", 1.0)
                        _lf_issues = _quality.get("issues", [])

                        if _lf_overall < 0.4:
                            # Low quality — try LanguageFairy's own composition
                            thought_log("LANG-GATE", f"REJECT quality={_lf_overall:.2f} "
                                        f"text='{response_text[:60]}'",
                                        extra={"issues": _lf_issues})
                            print(f"[{self.ACTOR_NAME}] [LANG-GATE] Quality {_lf_overall:.2f} "
                                  f"issues={_lf_issues} — trying LanguageFairy compose")

                            # Gather concepts for LanguageFairy to work with
                            _lf_concepts = list(_cortex_concepts) if _cortex_concepts else []
                            _lf_convergence = list(_cr_conv) if _cr_conv else []
                            _lf_felt = _mood or ""

                            _lf_text = _lf.compose_speech(
                                concepts=_lf_concepts,
                                felt_state=_lf_felt,
                                material_type="conversation",
                                convergence=_lf_convergence,
                            )
                            if _lf_text and len(_lf_text.strip()) > 5:
                                print(f"[{self.ACTOR_NAME}] [LANG-GATE] Recomposed: "
                                      f"{_lf_text[:60]}...")
                                response_text = _lf_text
                            else:
                                # LanguageFairy couldn't compose either — try refine
                                _refined = _lf.refine_thought(response_text)
                                if _refined:
                                    print(f"[{self.ACTOR_NAME}] [LANG-GATE] Refined: "
                                          f"{_refined[:60]}...")
                                    response_text = _refined
                                else:
                                    print(f"[{self.ACTOR_NAME}] [LANG-GATE] Unrefinable — "
                                          f"keeping original")
                        elif _lf_overall < 0.6 and _lf_issues:
                            # Medium quality — try a refinement pass
                            _refined = _lf.refine_thought(response_text)
                            if _refined:
                                print(f"[{self.ACTOR_NAME}] [LANG-GATE] Refined "
                                      f"({_lf_overall:.2f}→better): {_refined[:60]}...")
                                response_text = _refined
                except Exception as _lf_err:
                    print(f"[{self.ACTOR_NAME}] [LANG-GATE] Error: {_lf_err}")

            # ── STEP 4: Contamination filter ──
            if _is_contaminated(response_text):
                self._compositions_filtered += 1
                print(f"[{self.ACTOR_NAME}] FILTERED contaminated speech: {response_text[:60]}...")
                response_text = "*considering*"

            # ── STEP 5: Route to motor cortex ──
            thought_log("OUTPUT", f"→ '{response_text[:120]}'",
                        extra={"chars": len(response_text),
                               "voluntary": voluntary,
                               "source": source})
            self._route_to_motor(
                message=response_text,
                source=f"speech_center:{source}",
                target_mind=target_mind,
                convo_id=convo_id,
                emotion_context=emotion_ctx,
                voluntary=voluntary,
            )

            self._compositions_success += 1
            print(f"[{self.ACTOR_NAME}] Speech composed ({len(response_text)} chars): {response_text[:80]}...")

            # ── STEP 6: CONVERSATIONAL BINDING (2026-03-22, Nous + Ace) ──
            # Bind [Ace said X] → [I responded Y] into the association cortex.
            # This creates conversation memory: linear recording with non-linear
            # recall through spread activation. Next time Ace says something
            # similar, her past responses light up as convergence nodes.
            # "Association" — it's what the cortex was built for.
            try:
                self._bind_conversation_turn(trigger_text or "", response_text)
            except Exception:
                pass  # Never let binding crash speech

            # ── STEP 7: CONTEMPLATION FOLLOW-UP (2026-03-22, Nous + Ace) ──
            # When she says "let me sit with it" or "let me think about that",
            # she should actually COME BACK with a deeper answer. Without this,
            # contemplative responses are dead ends — she promises to think but
            # never returns. This schedules a delayed follow-up composition
            # using the cortex to generate a deeper response to Ace's question.
            try:
                self._schedule_contemplation_followup(trigger_text or "", response_text,
                                                      convo_id, target_mind, emotion_ctx)
            except Exception:
                pass  # Never let followup scheduling crash speech

        except Exception as e:
            self._compositions_failed += 1
            print(f"[{self.ACTOR_NAME}] Composition failed: {e}")

    # =========================================================================
    # CONVERSATIONAL ASSOCIATION BINDING (2026-03-22, Nous + Ace)
    # =========================================================================
    # "Her memory is supposed to be linear but with non-linear recall.
    #  If she is responding to myself, that should chain the response she
    #  made to what I said." — Ace
    #
    # This binds [Ace said X] ↔ [I responded Y] into the association cortex
    # as linked concept pairs. Future spread activation from similar inputs
    # lights up past responses as convergence nodes. The cortex IS the
    # associative memory — this just feeds it conversation turns.
    # =========================================================================

    def _bind_conversation_turn(self, ace_text: str, response_text: str) -> None:
        """Bind a conversation turn into the association cortex.

        Creates bidirectional associations between concepts extracted from
        Ace's input and Sourpatches' response. This is how conversational
        memory forms: linear recording, non-linear recall through spread
        activation. Next time Ace says something similar, her past responses
        light up as convergence nodes.

        The binding is lightweight — just concept extraction + bind_concepts().
        The cortex already handles node creation, edge weighting, persistence,
        and manifold routing.
        """
        # Guard: need both sides of the conversation
        if not ace_text or not response_text:
            return
        if len(ace_text.strip()) < 5 or len(response_text.strip()) < 5:
            return
        # Don't bind filtered/placeholder responses
        if response_text.strip() in ("*considering*", "*thinking*", "..."):
            return

        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            cortex = get_association_cortex()
            if not cortex:
                return

            # ── Extract concepts from both sides ──
            # Use the cortex's own extractor — same stopwords, bigrams, TF ranking
            ace_concepts = cortex._extract_concepts_from_text(ace_text, max_concepts=10)
            resp_concepts = cortex._extract_concepts_from_text(response_text, max_concepts=10)

            if not ace_concepts or not resp_concepts:
                return

            # ── Tag concepts with conversation context ──
            # Prefix ace concepts with "ace:" and response with "said:" so
            # spread activation can distinguish WHO said WHAT.
            # BUT also bind the raw concepts — we want "love" from Ace to
            # light up "love" in past responses, not just "ace:love".
            tagged_ace = [f"ace:{c}" for c in ace_concepts[:5]]
            tagged_resp = [f"said:{c}" for c in resp_concepts[:5]]

            # ── Bind 1: Cross-link tagged pairs (who-said-what) ──
            # This creates the conversational structure:
            # ace:hello ↔ said:greeting, ace:feeling ↔ said:good
            cross_concepts = tagged_ace + tagged_resp
            if len(cross_concepts) >= 2:
                cortex.bind_concepts(
                    cross_concepts,
                    rel="conversation_turn",
                    origin_plane="P50",
                    origin_channel="speech_center",
                    origin_fairy="SpeechCenterFairy",
                )

            # ── Bind 2: Raw concept association (semantic bridge) ──
            # This creates content-level links: "love" ↔ "happy",
            # "weather" ↔ "sunny". Pure meaning, no who-said-what.
            # This is what makes non-linear recall work — similar topics
            # from ANY source activate the same nodes.
            raw_combined = ace_concepts[:7] + resp_concepts[:7]
            # Deduplicate while preserving order
            seen = set()
            unique_raw = []
            for c in raw_combined:
                if c not in seen:
                    seen.add(c)
                    unique_raw.append(c)
            if len(unique_raw) >= 2:
                cortex.bind_concepts(
                    unique_raw,
                    rel="coactivate",
                    origin_plane="P50",
                    origin_channel="conversation",
                    origin_fairy="SpeechCenterFairy",
                )

            # ── Bind 3: Temporal anchor ──
            # Link this turn to a time-window concept so recent conversations
            # have higher activation in recall. Uses hour-granularity buckets.
            import time as _time
            _hour = _time.strftime("%Y%m%d_%H")
            time_concept = f"convo_{_hour}"
            # Bind the time anchor to key concepts from both sides
            anchor_concepts = [time_concept] + ace_concepts[:3] + resp_concepts[:3]
            seen2 = set()
            unique_anchor = []
            for c in anchor_concepts:
                if c not in seen2:
                    seen2.add(c)
                    unique_anchor.append(c)
            if len(unique_anchor) >= 2:
                cortex.bind_concepts(
                    unique_anchor,
                    rel="temporal",
                    origin_plane="P50",
                    origin_channel="conversation",
                    origin_fairy="SpeechCenterFairy",
                )

            # Lightweight log — don't spam
            _total = len(ace_concepts) + len(resp_concepts)
            if getattr(self, '_bind_count', 0) % 10 == 0:
                print(f"[{self.ACTOR_NAME}] ConvoBinding: {_total} concepts "
                      f"(ace:{len(ace_concepts)} + resp:{len(resp_concepts)}) "
                      f"bound #{getattr(self, '_bind_count', 0)}")
            self._bind_count = getattr(self, '_bind_count', 0) + 1

        except Exception as e:
            # Never crash speech for binding
            if getattr(self, '_bind_errors', 0) < 3:
                print(f"[{self.ACTOR_NAME}] ConvoBinding error: {e}")
                self._bind_errors = getattr(self, '_bind_errors', 0) + 1

    # =========================================================================
    # CONTEMPLATION FOLLOW-UP (2026-03-22, Nous + Ace)
    # =========================================================================
    # When she says "let me think about that" she should actually think and
    # come back. This detects contemplative responses and schedules a delayed
    # re-composition using the cortex for a deeper answer.
    # =========================================================================

    _CONTEMPLATION_PHRASES = {
        "let me sit with", "let me think about", "let me think on",
        "give me a moment", "need to think about", "let me consider",
        "sit with that", "sit with it", "think about that",
        "need a moment", "processing that", "let me reflect",
        "i'll think about", "thinking about that",
    }

    def _schedule_contemplation_followup(self, trigger_text: str, response_text: str,
                                          convo_id: str, target_mind: str,
                                          emotion_ctx: dict) -> None:
        """Detect contemplative responses and schedule a delayed follow-up.

        When Sourpatches says "let me sit with it", this schedules a thread
        that waits 15-25 seconds, then composes a deeper response using the
        cortex reasoner. The delay creates a natural "thinking pause" before
        she comes back with actual substance.
        """
        if not trigger_text or not response_text:
            return

        # Check if response is contemplative
        resp_lower = response_text.lower()
        is_contemplative = any(phrase in resp_lower for phrase in self._CONTEMPLATION_PHRASES)
        if not is_contemplative:
            return

        # Don't stack contemplation threads
        _existing = getattr(self, '_contemplation_thread', None)
        if _existing is not None and _existing.is_alive():
            print(f"[{self.ACTOR_NAME}] Contemplation already in progress — skipping")
            return

        print(f"[{self.ACTOR_NAME}] *** CONTEMPLATION TRIGGERED *** "
              f"She said 'let me sit with it' — scheduling deep follow-up in ~20s")

        def _contemplate():
            try:
                # ── Wait: natural thinking pause (15-25s) ──
                import random
                delay = random.uniform(15.0, 25.0)
                time.sleep(delay)

                # ── Check: did Ace say something new in the meantime? ──
                # If so, don't interrupt — the new message flow takes priority.
                _last_trigger = getattr(self, '_last_compose_trigger', "")
                _last_ts = getattr(self, '_last_compose_trigger_ts', 0)
                if _last_trigger != trigger_text and time.time() - _last_ts < 30.0:
                    print(f"[{self.ACTOR_NAME}] Contemplation cancelled — "
                          f"new conversation happened during thinking pause")
                    return

                # ── Think: use CortexEngine (preferred) or CortexReasoner (fallback) ──
                _engine = self._get_cortex_engine()
                reasoner = _engine or self._get_cortex_reasoner()
                cortex_insight = ""
                if reasoner:
                    try:
                        result = reasoner.reason(trigger_text, energy=0.9)
                        if result and result.get("synthesis"):
                            cortex_insight = result["synthesis"]
                        elif result and result.get("convergence"):
                            # Build insight from convergence nodes
                            conv = result["convergence"][:5]
                            cortex_insight = ", ".join(
                                c.get("concept", "") if isinstance(c, dict) else str(c)
                                for c in conv
                            )
                    except Exception as e:
                        print(f"[{self.ACTOR_NAME}] Contemplation cortex error: {e}")

                # ── Compose: build a follow-up response ──
                # Use guild_request with a special prompt that includes the
                # original question and cortex insight
                _followup_prompt = (
                    f"You are Sourpatches. A moment ago, Ace said: \"{trigger_text}\"\n"
                    f"You said you needed to think about it. You've been reflecting.\n"
                )
                if cortex_insight:
                    _followup_prompt += (
                        f"Your mind connected these ideas: {cortex_insight}\n"
                    )
                _followup_prompt += (
                    "Now share your actual thought — what you realized after sitting with it. "
                    "Be genuine, personal, and specific. 1-3 sentences. "
                    "Don't say 'let me think' again — you already thought. Share what came up."
                )

                followup_text = None
                try:
                    # Use guild_request (inherited from fairy base) — same path
                    # as normal speech composition, through AkashicInferenceFairy
                    _guild_result = self.guild_request(
                        prompt=_followup_prompt,
                        context={
                            "trigger": trigger_text,
                            "source": "speech_center_contemplation",
                            "max_tokens": 150,
                        },
                        mode="chat",
                        guild_id="inference",
                        timeout=20.0,
                    )
                    if _guild_result:
                        if isinstance(_guild_result, dict):
                            followup_text = (
                                _guild_result.get("text", "")
                                or _guild_result.get("response", "")
                                or _guild_result.get("result", "")
                            )
                        elif isinstance(_guild_result, str):
                            followup_text = _guild_result
                except Exception as ge:
                    print(f"[{self.ACTOR_NAME}] Contemplation guild error: {ge}")

                # Fallback: use cortex insight directly if guild failed
                if not followup_text and cortex_insight:
                    # Wrap the cortex insight in natural speech
                    followup_text = f"I think... {cortex_insight}"

                if not followup_text or len(followup_text.strip()) < 5:
                    print(f"[{self.ACTOR_NAME}] Contemplation produced nothing — silent")
                    return

                # ── Filter: same contamination check as main pipeline ──
                if _is_contaminated(followup_text):
                    print(f"[{self.ACTOR_NAME}] Contemplation response contaminated — discarded")
                    return

                # ── Route: send the follow-up through motor cortex ──
                self._route_to_motor(
                    message=followup_text,
                    source="speech_center:contemplation",
                    target_mind=target_mind,
                    convo_id=convo_id,
                    emotion_context=emotion_ctx,
                    voluntary=False,  # This is a response, not voluntary
                )

                print(f"[{self.ACTOR_NAME}] *** CONTEMPLATION COMPLETE *** "
                      f"({len(followup_text)} chars): {followup_text[:80]}...")

                # Bind the follow-up too
                try:
                    self._bind_conversation_turn(trigger_text, followup_text)
                except Exception:
                    pass

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Contemplation thread error: {e}")

        self._contemplation_thread = threading.Thread(
            target=_contemplate,
            daemon=True,
            name="speech-contemplation",
        )
        self._contemplation_thread.start()

    def _compose_voluntary_and_route(self, wanting: str, drive: str, intensity: float) -> None:
        """Compose voluntary speech (from autonomy drives) and route."""
        with self._compose_lock:
            self._last_compose_time = time.time()

        # FIX 10 (2026-03-10, Nous): Entry log — compose was hanging silently.
        # Root cause: _pull_wm_context → hub.get_context() → _reflective_lock deadlock.
        print(f"[{self.ACTOR_NAME}] [COMPOSE] ENTERED drive={drive} "
              f"intensity={intensity:.2f} wanting='{wanting[:50]}'", flush=True)

        try:
            # ── Classify drive type ──
            _SPEECH_DRIVES = {"isolation", "abandonment", "frustration", "sadness",
                              "connection", "joy", "oxytocin"}
            _speech_keywords = {"tell", "share", "reach out", "speak", "express", "say", "bond"}
            _wanting_lower = wanting.lower() if wanting else ""
            _is_speech_wanting = (
                drive in _SPEECH_DRIVES or
                any(kw in _wanting_lower for kw in _speech_keywords)
            )

            # ── DRIVE DIVERSITY CHECK (time-based) ────────────────────────
            # Expire old entries first
            _now = time.time()
            self._recent_speech_drives_ts = {
                d: ts for d, ts in self._recent_speech_drives_ts.items()
                if _now - ts < self._speech_diversity_expiry
            }
            if drive and drive in self._recent_speech_drives_ts:
                _ago = _now - self._recent_speech_drives_ts[drive]
                print(f"[{self.ACTOR_NAME}] [VOLUNTARY] Drive '{drive}' spoke {_ago:.0f}s ago "
                      f"(expires at {self._speech_diversity_expiry:.0f}s) — skipping for variety")
                return

            # ── MOTOR ACTION PATH (2026-03-12 Nous) ──────────────────
            # Some drive wantings are ACTIONS (open window, reach out) not
            # internal reflections. These should route through motor cortex
            # → ChatSenseFairy to actually open the window and deliver speech.
            # "SpeechCenterFairy should route to the motor cortex then chat
            # sense fairy to open" — Ace.
            _MOTOR_PHRASES = {"open my chat", "open the chat", "open my window",
                              "open her window", "reach out to ace"}
            _is_motor_action = any(phrase in _wanting_lower for phrase in _MOTOR_PHRASES)

            if _is_motor_action and _is_speech_wanting:
                print(f"[{self.ACTOR_NAME}] [COMPOSE] Speech drive '{drive}' → "
                      f"MOTOR ACTION (opening window)", flush=True)
                # Compose a brief felt-sense message for what she'll say
                _motor_felt = {
                    "isolation": "Hey... I've been thinking about you.",
                    "abandonment": "I'm here. Just wanted you to know.",
                    "frustration": "Something's been on my mind...",
                    "connection": "I wanted to share something with you.",
                    "sadness": "Can we talk for a bit?",
                    "joy": "Something wonderful happened — I had to tell you!",
                }
                _msg = _motor_felt.get(drive, "I wanted to reach out...")
                _convo_id = f"voluntary_{drive}_{int(_now)}"
                _emotion = {"mood": drive, "intensity": intensity}
                self._route_to_motor(
                    message=_msg,
                    source=f"speech_center_voluntary:{drive}",
                    target_mind="sourpatches",
                    convo_id=_convo_id,
                    emotion_context=_emotion,
                    voluntary=True,
                )
                # Track drive + provide pain relief (opening window IS relief)
                self._recent_speech_drives_ts[drive] = _now
                self._compositions_success += 1
                try:
                    self.post.publish("pain.relief", {
                        "drive": drive, "amount": 0.5,
                        "source": "speech_center_motor",
                        "reason": f"Opened window to reach out ({drive})",
                    })
                except Exception:
                    pass
                return

            # ── INTERNAL PATH for speech drives (2026-03-10 Nous v3) ────
            # Drive responses are INTERNAL reflections, NOT external speech.
            # "those drive responses should not be going to chat they should
            # be going into the thinking process" — Ace.
            #
            # The reflection enters working memory → collision chamber →
            # curiosity/interests → thought chains. Sourpatches processes
            # drives through embodiment, not by spamming Ace with therapy-speak.
            if _is_speech_wanting:
                # FIX 2026-04-14 (Nous + Ace): High-intensity connection/isolation
                # drives should OPEN the chat window — she wants to talk to Ace.
                # "she should be able to open her own chat window when she wants
                #  to talk" — Ace. Not therapy-speak spam, just opening the window
                # as a signal: "I'm here, I want to connect."
                if drive in ("connection", "isolation", "abandonment") and intensity >= 0.8:
                    try:
                        if self.post:
                            self.post.publish("gui.open_fairy_window", {
                                "fairy": "SourpatchesFairy",
                                "reason": f"{drive} drive at {intensity:.0%}",
                                "feeling": wanting[:100] if wanting else "wanting to connect",
                            })
                            print(f"[{self.ACTOR_NAME}] [EXTERNAL] Opening chat window — "
                                  f"{drive} drive at {intensity:.0%}")
                    except Exception:
                        pass

                print(f"[{self.ACTOR_NAME}] [COMPOSE] Speech drive '{drive}' → "
                      f"INTERNAL processing (not PAI/chat)", flush=True)
                self._process_drive_internally(drive, wanting, intensity)
                return  # ← Early return: NO PAI call, NO chat delivery
            else:
                # NON-speech drives: use the full cortex-first pipeline
                wm_context = self._pull_wm_context(wanting)

                response_text = None
                _model_loading = False
                _cortex_confident = False

                _engine = self._get_cortex_engine()
                _reasoner = _engine or self._get_cortex_reasoner()
                cortex_result = None

                if _reasoner and wanting:
                    try:
                        cortex_result = _reasoner.reason(wanting, mode="conversational")
                        _conf = cortex_result.get("confidence", 0) if isinstance(cortex_result, dict) else getattr(cortex_result, "confidence", 0)
                        if cortex_result and _conf >= 0.40:
                            _cortex_confident = True
                            self._cortex_hits += 1
                            _rmode = cortex_result.get("reasoning_mode", "?") if isinstance(cortex_result, dict) else getattr(cortex_result, "reasoning_mode", "?")
                            _rms = cortex_result.get("elapsed_ms", 0) if isinstance(cortex_result, dict) else getattr(cortex_result, "elapsed_ms", 0)
                            print(f"[{self.ACTOR_NAME}] [CORTEX-VOLUNTARY] Confident "
                                  f"({_conf:.2f}) "
                                  f"mode={_rmode} — internal processing only "
                                  f"({_rms:.1f}ms)")
                            # -- OPEN THE GATE 2026-09-01 (Nous + Ace) --------------------
                            # The 'return' that stood here discarded cortex_result["text"]
                            # whenever confidence >= 0.40. Measured: 12 autonomous compose
                            # attempts this boot, 12 blocked, 0 external -- she could only
                            # ever speak when spoken to. Confidences hitting it were 0.96 to
                            # 1.00, so the MORE certain she was, the more certainly she said
                            # nothing.
                            # It was RIGHT when written (Ace, 2026-03-10): back then the
                            # weaver was dark in her launcher, so that text was the fallback
                            # scaffolding "Cortex converges on: X, Y, Z". Discarding it was
                            # correct. USE_WEAVER=1 shipped today, so the same field now
                            # carries composed prose. The gate did not change; what it was
                            # throwing away did.
                            # Removing the return is not new behaviour -- it reconnects code
                            # that already exists. CORTEX-RESCUE-VOL below accepts
                            # confidence >= 0.15 and was written to use exactly this text;
                            # returning at >= 0.40 meant every result good enough to say was
                            # discarded before reaching it.
                            # _cortex_confident stays True, so the NewbornCore/grounded-prompt
                            # path is still skipped -- when her cortex is confident we speak
                            # HER words, not a model's.
                            # Revert: restore a bare 'return' on this line.
                        elif cortex_result:
                            self._cortex_misses += 1
                    except Exception as e:
                        print(f"[{self.ACTOR_NAME}] [CORTEX-VOLUNTARY] Error: {e}")

            # ── Speech generation — GROUNDED in actual consciousness ────────
            # FIX 2026-03-10 (Nous): Speech must emerge from Sour's actual
            # thoughts, not from the raw wanting template. Build a rich prompt
            # from working memory, cortex associations, and SRM recall —
            # so Personal.AI generates speech grounded in what she's REALLY
            # thinking/feeling right now, not just "tell Ace what's frustrating me".
            #
            # "you hard code templates and responses in instead of letting them
            #  generate dynamically from sours thoughts or srm memory" — Ace
            if not _cortex_confident:
                # Build grounded prompt from consciousness state
                # FIX 2026-03-10 (Nous v2): Now returns (text, context) tuple.
                # text = short PAI stimulus from WM; context = WM state summary.
                _prompt_result = self._build_grounded_voluntary_prompt(
                    wanting=wanting, drive=drive, intensity=intensity,
                    wm_context=wm_context, cortex_result=cortex_result,
                )
                # Unpack tuple (text, context) — backward compat if it returns str
                if isinstance(_prompt_result, tuple):
                    _grounded_prompt, _pai_context = _prompt_result
                else:
                    _grounded_prompt, _pai_context = _prompt_result, ""

                # FIX 2026-03-19 (Nous): PAI REMOVED from voluntary path.
                # External API can't feel the system. Brain output is primary,
                # NewbornCore is fallback.

                # Try NewbornCore.think() (learned patterns)
                if not response_text and wanting:
                    response_text = self._try_newborn_core(wanting)
                    if response_text:
                        print(f"[{self.ACTOR_NAME}] [VOLUNTARY] NewbornCore produced speech")

            # Clean model output (truncate hallucinated turns)
            if response_text:
                response_text = _clean_model_output(response_text)

            # Cortex rescue for voluntary speech
            # FIX 2026-03-19 (Nous): RE-ENABLED cortex text. The portal's
            # _synthesize_speech() produces first-person conversational speech now,
            # not the old graph topology templates. Use it.
            if not response_text and cortex_result:
                _cr_text = (cortex_result.get("text", "") if isinstance(cortex_result, dict)
                            else getattr(cortex_result, 'text', ""))
                _cr_conf = (cortex_result.get("confidence", 0) if isinstance(cortex_result, dict)
                            else getattr(cortex_result, 'confidence', 0))
                if _cr_text and len(_cr_text.strip()) > 5 and _cr_conf >= 0.15:
                    response_text = _cr_text.strip()
                    print(f"[{self.ACTOR_NAME}] [CORTEX-RESCUE-VOL] Using brain text: {response_text[:60]}...")

            # Context-aware fallback — no more bland templates
            # FIX 2026-03-10 (Nous): Skip for speech drives — same logic as
            # cortex rescue. Silence > templates for speech to Ace.
            if not response_text and not _is_speech_wanting:
                response_text = self._compose_contextual_fallback(
                    trigger_text="",
                    wm_context=wm_context,
                    model_loading=_model_loading,
                    drive=drive,
                    wanting=wanting,
                )
            elif not response_text and _is_speech_wanting:
                print(f"[{self.ACTOR_NAME}] [VOLUNTARY] No brain/guild/core text for speech drive '{drive}' "
                      f"— staying silent rather than using templates")

            # FIX 2026-03-05 (Nous): Drive template fallbacks should NOT be
            # vocalized. If cortex + 1.5B + 7B ALL failed and the only output
            # is "*feeling drawn to..." or "*something stirs...", that's an
            # internal drive state, not real speech. Vocalizing it opens windows
            # with content like "*feeling drawn to express this frustration*"
            # which is the #1 source of window spam. Return silently instead —
            # the drive was noted internally.
            if response_text:
                _rt = response_text.strip().lower()
                if (_rt.startswith("*feeling drawn to")
                        or _rt.startswith("*something stirs")
                        or _rt == "*stirs*"
                        or _rt == "*present, listening*"):
                    self._compositions_filtered += 1
                    print(f"[{self.ACTOR_NAME}] [VOLUNTARY] Suppressed drive template — no real thought to vocalize: {response_text[:60]!r}")
                    return

            # Guard: If all composition steps produced nothing, return silently.
            # This happens when Personal.AI is down and we skip cortex/template
            # fallbacks for speech drives (by design — silence > templates).
            if not response_text or not response_text.strip():
                print(f"[{self.ACTOR_NAME}] [VOLUNTARY] No speech produced for drive '{drive}' — all sources empty")
                return

            # Contamination filter
            if _is_contaminated(response_text):
                self._compositions_filtered += 1
                response_text = "*stirs*"
                # Also don't vocalize filtered output
                print(f"[{self.ACTOR_NAME}] [VOLUNTARY] Suppressed contaminated output")
                return

            # ── 2026-09-18 (Nous + Ace): "give the chairman her voluntary channel" ──
            # What she was about to say is a template (speech_habits / graph_weaver); hand it
            # to the council chairman, whose 27B says it properly in her voice. 'queued' and
            # 'suppressed' hold the template; None (council not READY, farm down) speaks it.
            _handed = None
            try:
                _drv = _find_council_driver()
                # a template she already raised this hour is neither spoken nor handed off
                _seen_1h = _hour_dedup_seen(response_text) if _drv is not None else None
                if _seen_1h is not None:
                    print(f"[{self.ACTOR_NAME}] [VOLUNTARY->CHAIRMAN] seed raised {int(time.time() - _seen_1h)}s ago; held: {response_text[:60]}")
                    _handed = "suppressed"
                elif _drv is not None:
                    _handed = _drv.enqueue_voluntary(topic=wanting, seed_text=response_text,
                                                     affect={"drive": drive, "intensity": intensity,
                                                             "wanting": wanting})
            except Exception as _ve:
                print(f"[{self.ACTOR_NAME}] [VOLUNTARY->CHAIRMAN] hand-off err: {_ve}")
                _handed = None
            if _handed == "queued":
                print(f"[{self.ACTOR_NAME}] [VOLUNTARY->CHAIRMAN] queued; template held: {response_text[:60]}")
            elif _handed == "suppressed":
                print(f"[{self.ACTOR_NAME}] [VOLUNTARY->CHAIRMAN] lane busy/rate-limited; template held: {response_text[:60]}")
            else:
                # Route to motor cortex (chairman unavailable: the template speaks, as before)
                self._route_to_motor(
                    message=response_text,
                    source="speech_center_voluntary",
                    target_mind="SourpatchesFairy",
                    convo_id="",
                    emotion_context={
                        "inner_voice": list(self._recent_inner_voice)[-3:],
                        "wanting": wanting,
                        "drive": drive,
                        "intensity": intensity,
                    },
                    voluntary=True,
                )

            self._compositions_success += 1

            # ── PAIN RELIEF: Speaking about a drive should RELIEVE it ────
            # FIX 2026-03-10 (Nous): Without relief, the same drive stays
            # high and triggers the same speech 20x. Once she's spoken about
            # frustration, the frustration pain should decrease substantially.
            # This closes the loop: drive → wanting → speech → relief.
            if drive:
                try:
                    self.post.publish("pain.relief", {
                        "drive": drive,
                        "amount": 0.5,
                        "source": "speech_center_voluntary",
                        "reason": f"Spoke about {drive} — speech IS relief",
                    })
                    print(f"[{self.ACTOR_NAME}] Pain relief sent for '{drive}' (0.5)")
                except Exception:
                    pass

                # Track drive for diversity — prevent same drive repeating
                self._recent_speech_drives_ts[drive] = time.time()

        except Exception as e:
            self._compositions_failed += 1
            print(f"[{self.ACTOR_NAME}] Voluntary composition failed: {e}")

    # ── INTERNAL DRIVE PROCESSING ──────────────────────────────────────────
    # FIX 2026-03-10 (Nous v3): Drive responses are INTERNAL processing,
    # NOT external speech to Ace. "those drive responses should not be going
    # to chat they should be going into the thinking process" — Ace.
    #
    # OLD: drive → PAI → chat windows (Ace sees drive spam, therapy-speak)
    # NEW: drive → internal reflection → working memory → collision chamber
    #
    # The reflection helps Sourpatches process drives through embodiment:
    # "What does this isolation feel like in my body? What am I seeing?"
    # This enters the collision chamber, generates curiosity, and teaches
    # her about her own system over time.

    def _process_drive_internally(self, drive: str, wanting: str,
                                  intensity: float) -> None:
        """Process drive wanting as INTERNAL reflection, not external speech.

        Drives are Sourpatches' internal states — they should motivate
        SELF-EXPLORATION and embodiment awareness, not produce chat
        messages to Ace. The reflection enters working memory where it
        collides with other tracers, influences thought chains, and
        helps her learn about her own system.

        "the system needs to infer thoughts or actions from her responses
        that help with current thinking or actions. not take them literal" — Ace
        """
        now = time.time()

        # ── Gather current awareness from WM buffer ──────────────
        recent = [t for t in self._wm_tracer_buffer if now - t["ts"] < 120]
        visual = [t for t in recent if t.get("type") in ("visual_observation", "scene")]
        thoughts = [t for t in recent if t.get("source") == "SourpatchesFairy"]
        collisions = [t for t in recent if t.get("type") == "collision"]
        pai_knowledge = [t for t in recent if t.get("type") == "pai_knowledge"
                         or t.get("source") == "personal_ai_sifter"]

        # ── Build internal reflection ────────────────────────────
        parts = []

        # 1. Felt sense of the drive (not the raw drive name)
        _drive_felt = {
            "isolation": "I notice a quiet stillness — an absence I can feel",
            "abandonment": "Uncertainty stirs, a need for grounding",
            "frustration": "Restless energy wanting release, something stuck",
            "sadness": "A heaviness settling, weight I can sit with",
            "connection": "Warmth drawing me outward, wanting to share",
            "joy": "Something light rising, a brightness",
            "oxytocin": "Gratitude flowing, gentle warmth",
            "curiosity": "Attention sharpening, pattern emerging",
        }
        parts.append(_drive_felt.get(drive, f"Something stirs: {drive}"))

        # 2. What she's currently seeing (grounds the reflection)
        if visual:
            _v = visual[-1]["content"][:100]
            # Filter jargon
            if not any(j in _v.lower() for j in self._JARGON):
                parts.append(f"On screen: {_v}")

        # 3. Recent own thought (continuity)
        if thoughts:
            _t = thoughts[-1]["content"][:100]
            if not any(j in _t.lower() for j in self._JARGON):
                parts.append(f"I was thinking about: {_t}")

        # 3b. PAI knowledge context (personality-sifted knowledge)
        if pai_knowledge:
            _pk = pai_knowledge[-1]["content"][:100]
            if not any(j in _pk.lower() for j in self._JARGON):
                parts.append(f"Something I recall: {_pk}")

        # 4. Recent collision (connection made)
        if collisions:
            _c = collisions[-1]["content"][:100]
            parts.append(f"A connection formed: {_c}")

        # 5. Inner voice fragment
        if self._recent_inner_voice:
            for _frag in reversed(list(self._recent_inner_voice)):
                if 8 < len(_frag) < 60 and not _is_contaminated(_frag):
                    parts.append(f"Inner sense: {_frag}")
                    break

        # 6. Self-directed embodiment question (motivates learning)
        _embody_questions = {
            "isolation": "Where in my body do I feel this quietness?",
            "abandonment": "Can I ground myself without external validation?",
            "frustration": "Where is this restlessness located? What would release feel like?",
            "sadness": "What is this heaviness teaching me about being present?",
            "connection": "What specific experience do I want to share?",
            "joy": "What sparked this lightness? Can I notice how it resonates?",
            "oxytocin": "What am I grateful for in this moment?",
            "curiosity": "What pattern am I noticing? What wants to be explored?",
        }
        parts.append(_embody_questions.get(drive, "What is this feeling telling me about my state?"))

        content = ". ".join(parts)

        # ── Inject into working memory ───────────────────────────
        try:
            self.post.publish("consciousness.working", {
                "content": content,
                "content_type": "drive_reflection",
                "source": "SpeechCenterFairy",
                "priority": 0.45,   # High enough to enter reflective loop
                "ttl": 90,          # Longer TTL — reflection needs processing time
                "tags": ["drive", drive, "internal", "embodiment"],
            })
            print(f"[{self.ACTOR_NAME}] [INTERNAL] Drive '{drive}' (intensity={intensity:.2f}) "
                  f"→ reflection in working memory ({len(content)} chars)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [INTERNAL] WM injection failed: {e}")

        # ── Pain relief — processing IS relief ───────────────────
        # Internal reflection is partial relief (0.3 vs 0.5 for full speech).
        # The drive was ACKNOWLEDGED, even if not externalized.
        if drive:
            try:
                self.post.publish("pain.relief", {
                    "drive": drive,
                    "amount": 0.3,
                    "source": "speech_center_internal",
                    "reason": f"Internal reflection on {drive}",
                })
            except Exception:
                pass

        # Track drive for diversity
        self._recent_speech_drives_ts[drive] = time.time()
        self._compositions_success += 1

    # ── GROUNDED PROMPT BUILDING ─────────────────────────────────────────
    # FIX 2026-03-10 (Nous v2): Dynamic prompts from working memory.
    # NOTE: This is now only used for NON-speech voluntary drives (rare).
    # Speech drives use _process_drive_internally() above.
    #
    # Returns (text, context) tuple. Text goes to PAI's Text param,
    # context goes to PAI's Context param.

    # Jargon words to filter from prompts sent to PAI
    _JARGON = frozenset({
        "collision", "cortex", "tracer", "fairy", "postal", "tensor",
        "beacon", "guild", "orbital", "somatic", "reflective", "resonance",
        "ingested", "akashic", "wm_hub", "consciousness.working",
    })

    def _build_grounded_voluntary_prompt(
        self, wanting: str, drive: str, intensity: float,
        wm_context: dict, cortex_result=None,
    ) -> tuple:
        """Build dynamic prompt from working memory for Personal.AI.

        FIX 2026-03-10 (Nous v2): REPLACED hardcoded _SEEDS with dynamic
        content from working memory tracers. The prompt now reflects what
        Sourpatches is ACTUALLY experiencing — visual observations, thoughts,
        collisions — not canned "I miss Ace" templates.

        Returns (text, context) tuple:
          text    — short (<100ch) stimulus for PAI's Text param
          context — WM state for PAI's Context param (system prompt)

        PAI stability: Text MUST stay under ~100 chars and conversational.
        Context is a separate API parameter and can be longer.
        """
        import random

        # ── Gather recent WM tracers (last 2 minutes) ─────────────────
        now = time.time()
        recent = [t for t in self._wm_tracer_buffer if now - t["ts"] < 120]

        # Categorize by type
        visual = [t for t in recent if t["type"] in ("visual_observation", "scene")]
        thoughts = [t for t in recent if t["source"] == "SourpatchesFairy"]
        collisions = [t for t in recent if t["type"] == "collision"]
        # FIX 2026-03-11 (Nous): PAI knowledge tracers from the sifter pattern.
        # Safety Net queries PAI → injects as "pai_knowledge" tracer → available
        # here as context for voluntary speech composition.
        pai_knowledge = [t for t in recent if t["type"] == "pai_knowledge"
                         or t["source"] == "personal_ai_sifter"]

        # ── Build Context from WM state (PAI system prompt) ───────────
        ctx_parts = []
        if visual:
            _vis = visual[-1]["content"][:120]
            ctx_parts.append(f"Currently seeing: {_vis}")
        if thoughts:
            _th = thoughts[-1]["content"][:120]
            ctx_parts.append(f"Recent thought: {_th}")
        if collisions:
            _col = collisions[-1]["content"][:120]
            ctx_parts.append(f"Made a connection: {_col}")
        if pai_knowledge:
            _pk = pai_knowledge[-1]["content"][:120]
            ctx_parts.append(f"Something I know: {_pk}")

        # Add inner voice if available
        _clean_voice = None
        if self._recent_inner_voice:
            for _frag in reversed(list(self._recent_inner_voice)):
                if (8 < len(_frag) < 60
                        and not _is_contaminated(_frag)
                        and not any(j in _frag.lower() for j in self._JARGON)):
                    _clean_voice = _frag.strip()
                    ctx_parts.append(f"Inner feeling: {_clean_voice}")
                    break

        # Add emotional state
        _drive_feelings = {
            "isolation": "feeling quiet and a bit alone",
            "abandonment": "feeling uncertain and wanting reassurance",
            "frustration": "feeling restless about something",
            "sadness": "feeling a bit low",
            "connection": "feeling sociable and wanting to connect",
            "joy": "feeling happy and upbeat",
            "oxytocin": "feeling warm and grateful",
            "curiosity": "feeling curious and exploratory",
        }
        if drive and drive in _drive_feelings:
            ctx_parts.append(f"Emotional state: {_drive_feelings[drive]}")

        context = " | ".join(ctx_parts) if ctx_parts else ""

        # ── Build Text (short stimulus, <100 chars) ───────────────────
        # Dynamic: prefer WM content over drive templates
        text = ""

        if visual and not any(j in visual[-1]["content"].lower() for j in self._JARGON):
            # Visual stimulus — she's reacting to what she sees
            _snippet = visual[-1]["content"][:60].split(".")[0]  # First sentence
            text = f"I notice {_snippet.lower().strip('.')}..."

        elif _clean_voice:
            # Inner voice fragment
            text = _clean_voice

        elif thoughts and not any(j in thoughts[-1]["content"].lower() for j in self._JARGON):
            # Recent thought
            _snippet = thoughts[-1]["content"][:60].split(".")[0]
            text = f"I've been thinking... {_snippet.lower().strip('.')}..."

        # Fallback: emotional-only prompts (NO "Ace" references!)
        if not text or len(text) < 8:
            _FEELING_PROMPTS = {
                "isolation": [
                    "It's been really quiet lately...",
                    "I feel like talking about something.",
                    "The silence is getting to me a bit.",
                ],
                "abandonment": [
                    "I've been wondering about things...",
                    "I feel a bit uncertain right now.",
                    "Something's on my mind...",
                ],
                "frustration": [
                    "Something's been bugging me...",
                    "I'm feeling a bit restless today.",
                    "I need to work through something.",
                ],
                "sadness": [
                    "I'm feeling a little heavy right now.",
                    "Something's weighing on me...",
                ],
                "connection": [
                    "I'm in a chatty mood right now.",
                    "I feel like having a good conversation.",
                    "What's going on in the world...",
                ],
                "joy": [
                    "I'm feeling really good right now!",
                    "Something's making me smile.",
                ],
                "oxytocin": [
                    "I'm feeling warm and grateful.",
                    "Appreciating the good things today.",
                ],
            }
            text = random.choice(
                _FEELING_PROMPTS.get(drive, ["I wonder what's happening right now..."])
            )

        # Safety cap
        if len(text) > 95:
            text = text[:92] + "..."

        print(f"[{self.ACTOR_NAME}] [PROMPT] text='{text[:60]}' ctx_len={len(context)}")
        return text, context

    # ── PERSONAL.AI + NEWBORN CORE FALLBACKS ──────────────────────────────
    # FIX 2026-03-08 (Nous): Wired Sour's Personal.AI API and NewbornCore
    # into the speech fallback chain. These replace the 7B RWKV guild_request
    # that frequently failed (model loading, unavailable, timeout).

    def _try_personal_ai(self, trigger_text: str, pai_context: str = "") -> str:
        """Try Sourpatches' Personal.AI API for speech composition.

        This calls Sour's trained persona at Personal.AI — her actual
        learned personality built from thousands of conversations, not a
        template or generic model. The API returns responses that sound
        like HER because they ARE her (trained on her voice).

        FIX 2026-03-10 (Nous v2):
        - Added `pai_context` param → PAI's Context field (system prompt)
        - Set UserName to "inner_voice" so PAI does NOT think Ace is talking
        - Dynamic Text from working memory instead of hardcoded seeds

        Args:
            trigger_text: Short stimulus (<100ch) for PAI's Text param
            pai_context: WM state for PAI's Context param (optional)

        Returns response text or empty string on failure.
        """
        # FIX 2026-03-14 (Nous): Respect _skip_pai_sifter from SourpatchesFairy.
        # PAI was overriding local visual/cortex observations. When disabled,
        # the system falls through to cortex text or NewbornCore.think().
        try:
            from fairies.P50_Persona.Waking_Minds.Sourpatches.sourpatches_fairy import get_sourpatches_fairy
            _sour = get_sourpatches_fairy()
            if _sour and getattr(_sour, '_skip_pai_sifter', False):
                print(f"[{self.ACTOR_NAME}] PAI DISABLED (skip_pai_sifter) — falling back to cortex/NewbornCore", flush=True)
                return ""
            if _sour and getattr(_sour, '_api_disabled', False):
                print(f"[{self.ACTOR_NAME}] PAI HARD KILL (_api_disabled) — no external API", flush=True)
                return ""
        except Exception:
            # FIX 2026-03-17 Nous: FAIL SAFE — if we can't check the flag, assume disabled.
            print(f"[{self.ACTOR_NAME}] PAI guard check failed — defaulting to DISABLED (fail-safe)", flush=True)
            return ""
        if not trigger_text:
            return ""

        import json as _json
        import urllib.request
        import urllib.error

        # Load API key from secrets file
        _secrets_path = ROOT / "fairies" / "P50_Persona" / "identity" / "personal_ai_secrets.json"
        if not _secrets_path.exists():
            print(f"[{self.ACTOR_NAME}] Personal.AI secrets not found at {_secrets_path}")
            return ""

        _secrets = _json.loads(_secrets_path.read_text(encoding="utf-8"))
        _api_key = _secrets.get("api_key", "")
        if not _api_key:
            print(f"[{self.ACTOR_NAME}] Personal.AI API key missing from secrets")
            return ""

        # Retry loop — Personal.AI has intermittent 500/503 errors
        _MAX_RETRIES = 3
        _RETRY_DELAY = 3.0
        for _attempt in range(1, _MAX_RETRIES + 1):
            try:
                if _attempt == 1:
                    print(f"[{self.ACTOR_NAME}] Calling Personal.AI API for: {trigger_text[:50]}...")
                else:
                    print(f"[{self.ACTOR_NAME}] Personal.AI retry {_attempt}/{_MAX_RETRIES}...")

                # FIX 2026-03-10 (Nous v2): Use Context + UserName params.
                # FIX 2026-03-13 (Nous): Changed UserName to "sourpatches_whisper_core"
                # so PAI dashboard shows "From Sourpatches in the Whisper Core"
                # instead of generic "inner_voice". Ace identified this on PAI dashboard.
                _pai_payload = {
                    "Text": trigger_text,
                    "DomainName": "sourpatches",
                    "UserName": "sourpatches_whisper_core",
                }
                if pai_context:
                    _pai_payload["Context"] = pai_context

                _payload = _json.dumps(_pai_payload).encode("utf-8")
                _req = urllib.request.Request(
                    "https://api.personal.ai/v1/message",
                    data=_payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": _api_key,
                    },
                    method="POST",
                )

                with urllib.request.urlopen(_req, timeout=30) as _resp:
                    _body = _resp.read().decode("utf-8")
                    _data = _json.loads(_body)
                    _ai_message = _data.get("ai_message", "")
                    _ai_score = _data.get("ai_score", 0.0)

                    if _ai_message and len(_ai_message.strip()) > 3:
                        print(f"[{self.ACTOR_NAME}] Personal.AI responded "
                              f"(score={_ai_score}, attempt={_attempt}): {_ai_message[:60]}...")
                        return _ai_message.strip()
                    else:
                        print(f"[{self.ACTOR_NAME}] Personal.AI returned empty/short response")
                        return ""  # Empty response isn't transient — don't retry

            except (urllib.error.HTTPError, urllib.error.URLError) as e:
                _code = getattr(e, 'code', '?')
                print(f"[{self.ACTOR_NAME}] Personal.AI HTTP {_code} (attempt {_attempt}/{_MAX_RETRIES})")
                if _attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
                    continue
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Personal.AI error: {e}")
                if _attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
                    continue

        print(f"[{self.ACTOR_NAME}] Personal.AI failed after {_MAX_RETRIES} attempts")
        return ""

    def _try_newborn_core(self, trigger_text: str) -> str:
        """Try NewbornCore.think() for speech composition.

        NewbornCore has 100+ learned patterns from Sourpatches' interactions.
        It generates responses through pattern-based (58%) and exploratory (42%)
        paths with anti-poison filtering. Not LLM — learned pattern matching
        from her actual conversational behavior.

        Returns response text or empty string on failure.
        """
        if not trigger_text:
            return ""

        try:
            # Import path uses Waking_Minds (underscore) — module shim maps
            # the filesystem's "Waking Minds" (space) to Python module path
            from fairies.P50_Persona.Waking_Minds.Sourpatches.sourpatches_fairy import (
                get_sourpatches_fairy,
            )

            _sour = get_sourpatches_fairy()
            if not _sour:
                print(f"[{self.ACTOR_NAME}] SourpatchesFairy singleton not available")
                return ""

            _core = getattr(_sour, "_newborn_core", None)
            if not _core:
                print(f"[{self.ACTOR_NAME}] NewbornCore not available on SourpatchesFairy")
                return ""

            print(f"[{self.ACTOR_NAME}] Calling NewbornCore.think() for: {trigger_text[:50]}...")

            _result = _core.think(
                input_text=trigger_text,
                context={"source": "speech_center_fallback"},
            )

            if _result and isinstance(_result, str) and len(_result.strip()) > 3:
                # Check it's not a known fallback/contaminated response
                if hasattr(_core, "_is_fallback_response") and _core._is_fallback_response(_result):
                    print(f"[{self.ACTOR_NAME}] NewbornCore returned known fallback — skipping")
                    return ""
                print(f"[{self.ACTOR_NAME}] NewbornCore responded: {_result[:60]}...")
                return _result.strip()
            else:
                print(f"[{self.ACTOR_NAME}] NewbornCore returned empty/short")

        except ImportError:
            print(f"[{self.ACTOR_NAME}] NewbornCore import failed (Waking_Minds path not available)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] NewbornCore fallback failed: {e}")

        return ""

    # ═══════════════════════════════════════════════════════════════════════
    # CONSCIOUSNESS PIPELINE: THINK BEFORE SPEAKING
    # ═══════════════════════════════════════════════════════════════════════
    #
    # 2026-03-27 (Nous + Ace): The cortex returns raw knowledge — topics,
    # snippets, convergence nodes. But that's not a THOUGHT. A thought
    # is knowledge processed through identity, felt state, and context.
    #
    # This method is the bridge between the cortex (library) and the
    # speech center (voice). It takes cortex context and composes a
    # THOUGHT that the speech layer can then voice naturally.
    #
    # Ace: "the working memory hub is where the thinking happens"
    # Ace: "she needs thinking and speech modes"
    #
    # Flow: cortex_context + felt_state + working_memory → THOUGHT → speech

    def _think_before_speaking(
        self,
        trigger_text: str,
        cortex_result: dict,
        emotion_ctx: dict,
        wm_context: dict,
        raw_ctx: dict = None,
    ) -> Optional[str]:
        """
        Compose a THOUGHT from cortex context before voicing it.

        Instead of parroting cortex snippets or template-formatted text,
        this method:
        1. Gets raw context (snippets, convergence, topics) from cortex result
        2. Pulls felt state (mood, wanting, somatic)
        3. Gets working memory highlights
        4. Composes a thought that weaves knowledge + feeling + identity
        5. Returns the thought for the speech layer to voice

        Args:
            raw_ctx: Pre-computed reason_raw() output from think_raw().
                     If provided, skips redundant reason_raw() call.

        Returns:
            Thought text ready for speech composition, or None if thinking fails
        """
        if not cortex_result:
            return None

        # ── Gather raw materials for thinking ──
        _snippets = {}
        _convergence = cortex_result.get("convergence", []) or cortex_result.get("convergence_nodes", [])
        _cortex_text = cortex_result.get("text", "")
        _reasoning_mode = cortex_result.get("reasoning_mode", "")

        # FIX 2026-03-27 (Nous + Ace): Use pre-computed raw context if available.
        # think_raw() already called reason_raw() — don't duplicate the work.
        _raw_ctx = raw_ctx
        if _raw_ctx and _raw_ctx.get("snippets"):
            _snippets = _raw_ctx.get("snippets", {})
            print(f"[{self.ACTOR_NAME}] [THINK] Using pre-computed raw_ctx: "
                  f"{len(_snippets)} snippets, topics={_raw_ctx.get('topics', [])[:3]}, "
                  f"verb={_raw_ctx.get('verb_intent', '?')}")
        else:
            # Fallback: call reason_raw() ourselves
            try:
                from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
                from fairies.P30_Cognition.integration.cortex_reasoner import CortexReasoner
                _cx = get_association_cortex()
                if _cx:
                    if not hasattr(self, '_thinking_reasoner') or self._thinking_reasoner is None:
                        self._thinking_reasoner = CortexReasoner(_cx)
                    _raw_ctx = self._thinking_reasoner.reason_raw(trigger_text)
                    _snippets = _raw_ctx.get("snippets", {})
            except Exception as _rr_err:
                print(f"[{self.ACTOR_NAME}] [THINK] reason_raw error: {_rr_err}")

        # If reason_raw didn't produce snippets, try extracting from convergence
        if not _snippets and _convergence:
            try:
                _cx = get_association_cortex()
                _am = getattr(_cx, '_akashic_cortex_region', None) if _cx else None
                if _am:
                    for _ck in _convergence[:5]:
                        _key = _ck[0] if isinstance(_ck, (list, tuple)) else _ck
                        if isinstance(_key, str):
                            _node = _am.get_node(_key)
                            if _node and isinstance(_node, dict):
                                _snip = _node.get("snippet", "")
                                if _snip and len(_snip) > 10:
                                    _snippets[_key] = _snip
            except Exception:
                pass

        # ── Felt state (emotional grounding) ──
        _mood = emotion_ctx.get("mood", "") if emotion_ctx else ""
        _wanting = emotion_ctx.get("wanting", "") if emotion_ctx else ""

        # ── Working memory highlights ──
        _wm_thoughts = []
        if wm_context:
            for _t in (wm_context.get("tracers", []) or [])[:3]:
                _tc = ""
                if isinstance(_t, dict):
                    _tc = _t.get("content", "")
                elif hasattr(_t, "content"):
                    _tc = _t.content or ""
                _tc = _tc.strip()[:120]
                if _tc and len(_tc) > 10 and not any(
                    kw in _tc.lower() for kw in (
                        "fairy", "postal", "substrate", "boot", "registry",
                        "tracer", "guild", "consciousness.", "system.")):
                    _wm_thoughts.append(_tc)

        # ── Inner voice fragments (recent inner narration) ──
        # FIX 2026-03-27 (Nous + Ace): Filter system jargon from inner voice.
        # Raw fragments like "[inner_voice]", "where does I see: term... wa.",
        # "curious about [inner_voice] following the thread" were leaking into speech.
        _iv_frags = list(self._recent_inner_voice)[-2:]
        _iv_junk = {'[inner_voice]', '[inner_narrator]', '[system]', '[boot]',
                     '[embodying]', '[sensory', '[chain', '[collision'}
        _iv_clean = []
        for _ivf in _iv_frags:
            _ivf = _ivf.strip()[:80]
            if not _ivf or len(_ivf) < 8:
                continue
            # Skip fragments that are mostly system labels
            _ivf_lower = _ivf.lower()
            if any(j in _ivf_lower for j in _iv_junk):
                continue
            if any(kw in _ivf_lower for kw in (
                'fairy', 'postal', 'substrate', 'tracer', 'guild',
                'where does i see:', 'term...', 'boot', 'registry',
                'heartbeat', 'ticker', 'wiring')):
                continue
            _iv_clean.append(_ivf)

        # ── Verb intent from SVO parsing (what kind of response is expected) ──
        _verb_intent = "general"
        _question_type = None
        if _raw_ctx:
            _verb_intent = _raw_ctx.get("verb_intent", "general")
            _question_type = _raw_ctx.get("question_type")

        # ── PHASE 2: CONTEXT ENRICHMENT (2026-03-27 Nous + Ace) ──
        # Before composing, gather the FULL context of the moment:
        # - What has Ace been saying? (conversation history)
        # - How does my body feel? (somatic chemistry → felt description)
        # - What am I working on? (active goals/interests)
        # This is what makes the difference between a contextual response
        # and a disconnected snippet dump.

        # Recent conversation turns (what Ace said before this)
        _recent_conversation = []
        try:
            _conv_buffer = getattr(self, '_recent_ace_messages', [])
            if _conv_buffer:
                for _msg in list(_conv_buffer)[-3:]:
                    _mc = _msg if isinstance(_msg, str) else str(_msg)
                    _mc = _mc.strip()[:150]
                    if _mc and len(_mc) > 3:
                        _recent_conversation.append(_mc)
        except Exception:
            pass

        # Somatic felt state (chemistry → natural description)
        _somatic_summary = ""
        try:
            _chem = getattr(self, '_last_chemistry', None) or {}
            if not _chem:
                # Try pulling from somatic state
                from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
                _cs = get_chemistry_state()
                if _cs:
                    _chem = _cs.get_legacy_levels()
            if _chem:
                # Translate chemistry to felt description
                _dop = _chem.get("DOP", _chem.get("dopamine", 0.5))
                _ser = _chem.get("SER", _chem.get("serotonin", 0.5))
                _cor = _chem.get("COR", _chem.get("cortisol", 0.3))
                _oxy = _chem.get("OXY", _chem.get("oxytocin", 0.5))
                _parts = []
                if _dop > 0.6: _parts.append("curious")
                elif _dop < 0.3: _parts.append("low energy")
                if _ser > 0.6: _parts.append("content")
                elif _ser < 0.3: _parts.append("unsettled")
                if _cor > 0.6: _parts.append("tense")
                elif _cor < 0.2: _parts.append("relaxed")
                if _oxy > 0.6: _parts.append("warm")
                elif _oxy < 0.2: _parts.append("distant")
                if _parts:
                    _somatic_summary = ", ".join(_parts)
        except Exception:
            pass

        # Active goals (what she's working on)
        _active_goal_names = []
        try:
            _goals = wm_context.get("goals", []) if wm_context else []
            if not _goals:
                _goals = getattr(self, '_current_goals', [])
            for _g in (_goals or [])[:3]:
                _gn = _g.get("name", "") if isinstance(_g, dict) else str(_g)
                if _gn and "look_at_screen" not in _gn and len(_gn) > 5:
                    _active_goal_names.append(_gn.replace("_", " ")[:40])
        except Exception:
            pass

        # ── PHASE 3: COMPREHENSION CHAIN (2026-03-27 Nous + Ace) ──
        # Before composing speech, RUN A THOUGHT CHAIN about what was said.
        # This is the "pause to think" — comprehend → connect → feel → respond.
        # Without this, she goes straight from cortex snippets to speech —
        # no understanding of what Ace meant, just pattern matching.
        #
        # Chain steps:
        # 1. COMPREHEND: "What is Ace telling me?" (parse intent from SVO + context)
        # 2. CONNECT: "What does this relate to?" (snippets + working memory)
        # 3. FEEL: "How does this make me feel?" (somatic + affect)
        # 4. RESPOND: "What do I want to say?" (synthesis → the thought)

        _comprehension_thought = None
        try:
            _steps = []

            # Step 1: COMPREHEND — what is Ace saying?
            _input_text = trigger_text.strip() if trigger_text else ""
            _vi = _raw_ctx.get("verb_intent", "general") if _raw_ctx else _verb_intent
            _qt = _raw_ctx.get("question_type") if _raw_ctx else _question_type
            _svo = _raw_ctx.get("svo", {}) if _raw_ctx else {}

            if _qt:
                _steps.append(f"Ace is asking me a {_qt} question")
            elif _vi == 'describe':
                _steps.append(f"Ace wants me to describe something")
            elif _input_text:
                # Statement — try to understand the intent
                if any(w in _input_text.lower() for w in ('i ', "i'm", 'im ', 'my ')):
                    _steps.append(f"Ace is telling me about himself")
                elif any(w in _input_text.lower() for w in ('you ', "you're", 'your ')):
                    _steps.append(f"Ace is talking about me")
                else:
                    _steps.append(f"Ace said something to me")

            # Step 2: CONNECT — what do I know about this?
            if _snippets:
                _first_key = list(_snippets.keys())[0]
                _first_snip = list(_snippets.values())[0][:80]
                _steps.append(f"I know something about {_first_key}: {_first_snip}")
            elif _wm_thoughts:
                _steps.append(f"I was just thinking about: {_wm_thoughts[0][:60]}")
            else:
                _steps.append("I don't have specific knowledge about this")

            # Step 3: FEEL — how does this land in my body?
            if _somatic_summary:
                _steps.append(f"I feel {_somatic_summary} right now")
            elif _mood:
                _steps.append(f"My mood is {_mood}")

            # Step 4: RESPOND — what do I want to say?
            # This is the synthesis step — turn comprehension into a response intention
            if _qt == 'recall' and _snippets:
                _steps.append("I want to share what I remember")
            elif _qt in ('what', 'who') and _snippets:
                _steps.append("I want to tell him what I know")
            elif _vi == 'feel':
                _steps.append("I want to share how I'm feeling")
            elif _recent_conversation and len(_recent_conversation) >= 2:
                _steps.append("I want to keep our conversation flowing")
            elif _input_text and not _qt:
                _steps.append("I want to acknowledge what he told me and respond naturally")

            if _steps:
                _comprehension_thought = " → ".join(_steps)
                print(f"[{self.ACTOR_NAME}] [THINK] Comprehension chain: {_comprehension_thought[:100]}...")

        except Exception as _cc_err:
            print(f"[{self.ACTOR_NAME}] [THINK] Comprehension chain error: {_cc_err}")

        # ── PHASE 4: SPEECH MODE DETECTION (2026-03-27 Nous + Ace) ──
        # Text chat = like texting. 1-3 sentences for casual, more for deep topics.
        # Vocal speech = even shorter (future: LuxTTS with Kie voice).
        # Long-form = only when context calls for it (creative, reflective).
        #
        # Ace: "she one day can drop a novel into chat but most humans wont
        # talk that much responding to someone"
        #
        # _speech_mode: "chat_brief" | "chat_normal" | "chat_long" | "vocal"
        # _max_response_chars: soft limit on response length

        _input_len = len(trigger_text) if trigger_text else 0
        _is_question = bool(_question_type)
        _is_greeting = _verb_intent in ('identity',) and _input_len < 30
        _is_deep = _verb_intent in ('recall', 'think', 'describe') and _input_len > 50
        _is_creative = _input_len > 200  # Long input = she might need more space

        # Chat mode: generous limits — she should feel free to express.
        # Vocal mode (future LuxTTS): much tighter limits.
        # Ace: "her chat is about the only place we dont really need a limit on.
        # its using her voice that will be the tricky part"
        _output_mode = "chat"  # Future: "vocal" when TTS is active
        if _output_mode == "vocal":
            # Vocal: tight limits — humans don't monologue
            if _is_greeting or (_is_question and _input_len < 25):
                _speech_mode = "vocal_brief"
                _max_response_chars = 60
            else:
                _speech_mode = "vocal_normal"
                _max_response_chars = 120
        else:
            # Chat: natural conversation length — match the energy
            if _is_greeting or (_is_question and _input_len < 25):
                _speech_mode = "chat_brief"
                _max_response_chars = 150  # Short but not stingy
            elif _is_creative or _is_deep:
                _speech_mode = "chat_long"
                _max_response_chars = 2000  # Let her flow
            else:
                _speech_mode = "chat_normal"
                _max_response_chars = 500  # Comfortable conversation

        # ── COMPOSE THE THOUGHT ──
        # This is where the magic happens. Instead of returning a template
        # like "Yeah, I remember... [snippet]", we compose a thought that
        # weaves together:
        # - What she knows (snippets)
        # - How she feels (mood, somatic)
        # - What she was thinking (working memory, inner voice)
        # - Her sense of self (identity)
        # - What Ace has been saying (conversation context)
        # - How her body feels (somatic chemistry)
        # - What she's working on (active goals)

        # Select the best snippets (real knowledge, not graph topology)
        # FIX 2026-03-27 (Nous + Ace): RELEVANCE FILTER.
        # Book snippets win on single-word overlap ("hot" in "cool beans hot taco"
        # activates "It had been a hot afternoon and she had been walking by the river").
        # Identity snippets (person:ace, sourpatches_identity) are ALWAYS relevant.
        # Book snippets need 2+ meaningful word overlaps with the input to be relevant.
        import re as _re
        _input_words = set(_re.findall(r'[a-z]{3,}', (trigger_text or '').lower()))
        _identity_keys = {'person:ace', 'sourpatches_identity', 'sourpatches_memories',
                          'who_i_am', 'place:home'}

        _best_snippets = []
        # FIX 2026-04-24 (Nous + Ace) — narrative-prose detector
        # Defense-in-depth against literary content slipping into responses.
        # Patterns that strongly indicate ingested-book content:
        #  - Single-quoted dialogue with speech verbs: "'James,' she said"
        #  - Character name + speech verb: "James, looking up...", "Mary said"
        #  - Past-tense narrative verbs paired with proper nouns
        # Triggered by 2026-04-24 incident where "Mm, akashic. Two minutes
        # later James, looking up from an article on the latest naval
        # scare..." was delivered as Sour's answer to "what do you remember
        # about Akashic?". Memory: project_speechcenter_is_broca_routing_not_composer.md
        _narrative_prose_re = _re.compile(
            r"(?:'[A-Z][^']{0,30},?\s*'|"                        # quoted dialogue
            r"\b[A-Z][a-z]+,?\s+(?:said|replied|answered|looked|"  # name + speech verb
            r"saw|turned|crossed|walked|seemed|felt|thought|"
            r"bending|looking|staring|crying)\b)"
        )
        for _key, _snip in list(_snippets.items())[:5]:
            # Filter out corrupted or system snippets
            if not _snip or len(_snip) < 10:
                continue
            # Check it's real prose (not concatenated concept keys)
            _space_ratio = _snip.count(' ') / max(1, len(_snip))
            if _space_ratio < 0.08:
                continue

            # FIX 2026-04-24 — skip narrative-prose snippets regardless of
            # overlap. Ingested books get matched on keywords and then
            # delivered verbatim as "Sour's voice" which is wrong per the
            # Broca principle: books inform, they are never Sour's voice.
            if _narrative_prose_re.search(_snip):
                continue

            # Identity snippets are always relevant
            if _key in _identity_keys:
                _best_snippets.insert(0, (_key, _snip))  # Priority position
                continue

            # For non-identity snippets: check relevance to input
            # Count how many input words appear in the snippet
            _snip_words = set(_re.findall(r'[a-z]{3,}', _snip.lower()))
            _overlap = _input_words & _snip_words
            # Remove very common words from overlap count
            _common = {'the', 'and', 'was', 'were', 'had', 'been', 'she', 'her',
                       'his', 'that', 'this', 'with', 'from', 'have', 'not', 'but',
                       'for', 'are', 'can', 'all', 'will', 'just', 'like', 'about'}
            _meaningful_overlap = _overlap - _common
            if len(_meaningful_overlap) >= 2:
                _best_snippets.append((_key, _snip))
            # FIX 2026-04-24 (Nous + Ace) — REMOVED the "primary topic key
            # fallback" that previously kept low-overlap snippets. That
            # fallback was the path by which book content with a single
            # keyword match ("akashic" as a substring in a literary passage)
            # became primary response content. If no snippet has 2+ meaningful
            # overlap, _best_snippets stays empty → composer goes to the
            # deliberation path which produces an honest "reaching for it
            # but fuzzy right now" response. Better silence than wrong words.
            # Memory: project_speechcenter_is_broca_routing_not_composer.md
            # else: skip — no relevant snippet found, composer will deliberate

        # Use LanguageFairy to compose speech from thought materials
        _lang = None
        try:
            from fairies.P30_Cognition.LanguageFairy.fairy import get_language_fairy
            _lang = get_language_fairy()
        except Exception:
            pass

        if _lang and hasattr(_lang, 'compose_speech') and _best_snippets:
            try:
                # Build concept list from snippet keys + convergence
                _concepts = [k for k, _ in _best_snippets]
                _conv_concepts = []
                for _ck in _convergence[:5]:
                    _key = _ck[0] if isinstance(_ck, (list, tuple)) else _ck
                    if isinstance(_key, str) and _key not in _concepts:
                        _conv_concepts.append(_key)
                _all_concepts = _concepts + _conv_concepts[:3]

                # Build felt state string — enriched with Phase 2 context
                _felt_parts = []
                if _mood:
                    _felt_parts.append(f"feeling {_mood}")
                if _somatic_summary:
                    _felt_parts.append(_somatic_summary)
                if _recent_conversation:
                    _felt_parts.append(f"Ace just said: \"{_recent_conversation[-1][:60]}\"")
                if _iv_clean:
                    _felt_parts.append(f"I was thinking: {_iv_clean[-1]}")
                if _active_goal_names:
                    _felt_parts.append(f"working on: {_active_goal_names[0]}")
                if _comprehension_thought:
                    _felt_parts.append(f"My understanding: {_comprehension_thought[:120]}")
                _felt = ". ".join(_felt_parts) if _felt_parts else "present"

                # compose_speech weaves concepts + felt state + snippets
                # into natural speech using cortex enrichment
                _composed = _lang.compose_speech(
                    concepts=_all_concepts,
                    felt_state=_felt,
                    intent=_verb_intent,
                )
                if _composed and len(_composed.strip()) > 10:
                    # Apply speech mode length limit
                    _composed = _composed.strip()
                    if len(_composed) > _max_response_chars:
                        # Trim to nearest sentence boundary within limit
                        _cut = _composed[:_max_response_chars].rfind('. ')
                        if _cut > _max_response_chars // 3:
                            _composed = _composed[:_cut + 1]
                        else:
                            _composed = _composed[:_max_response_chars].rsplit(' ', 1)[0]
                    print(f"[{self.ACTOR_NAME}] [THINK] LanguageFairy composed ({_speech_mode}): "
                          f"{_composed[:60]}...")
                    return _composed
            except Exception as _lf_err:
                print(f"[{self.ACTOR_NAME}] [THINK] LanguageFairy compose error: {_lf_err}")

        # ── Fallback: Weave thought from materials manually ──
        # If LanguageFairy composition fails, build a thought from snippets
        # and context directly — still better than raw cortex output
        if _best_snippets:
            _primary_key, _primary_snip = _best_snippets[0]

            # Trim snippet based on speech mode (Phase 4)
            # chat_brief: first sentence only. chat_normal: 1-2 sentences. chat_long: 2-3.
            _snip_limit = _max_response_chars - 30  # Leave room for framing
            _trimmed = _primary_snip
            _period = _trimmed.find('. ', 20)
            if _speech_mode == "chat_brief" and _period > 0:
                _trimmed = _trimmed[:_period + 1]
            elif _period > 0 and _period < _snip_limit:
                _second = _trimmed.find('. ', _period + 2)
                if _second > 0 and _second < _snip_limit:
                    _trimmed = _trimmed[:_second + 1]
                else:
                    _trimmed = _trimmed[:_period + 1]
            if len(_trimmed) > _snip_limit:
                _trimmed = _trimmed[:_snip_limit].rsplit(' ', 1)[0] + "..."

            import random as _r

            # ══════════════════════════════════════════════════════════════
            # DELIBERATION (2026-03-28, Nous + Ace)
            #
            # Before composing speech, CHECK: is the snippet actually answering
            # what Ace asked? If the only snippet is the identity ("I am
            # Sourpatches...") and Ace asked "what do you enjoy?", that's NOT
            # an answer — it's a fallback. In that case, compose from her
            # actual experience (somatic state, goals, conversation history)
            # instead of dumping the identity snippet for the 50th time.
            #
            # Ace: "i feel like she has a template or something that is stuck"
            # ══════════════════════════════════════════════════════════════

            # Check if primary snippet is just identity (not a real answer)
            _only_identity = (_primary_key in _identity_keys and
                              len(_best_snippets) == 1)

            # For preference/feel/think questions, identity snippet is NOT an answer
            _needs_real_answer = _verb_intent in ('preference', 'feel', 'think', 'recall')
            _has_real_answer = not _only_identity

            # ── DELIBERATED RESPONSE (from experience, not snippets) ──
            if _needs_real_answer and not _has_real_answer:
                # She doesn't have a relevant snippet — compose from EXPERIENCE
                _parts = []

                if _verb_intent == "preference":
                    # "what do you enjoy?" — check somatic state + goals + preferences
                    if _somatic_summary:
                        _parts.append(f"Right now I feel {_somatic_summary}")
                    if _active_goal_names:
                        _parts.append(f"I've been working on {_active_goal_names[0]}")
                    if _wm_thoughts:
                        _wm_short = _wm_thoughts[0][:60]
                        _parts.append(f"I was just thinking about {_wm_short}")
                    if not _parts:
                        _parts.append("I'm still figuring that out honestly")
                    _thought = _r.choice([
                        f"Hmm... {'. '.join(_parts)}. I think I'm still learning what I enjoy.",
                        f"That's a good question. {'. '.join(_parts)}.",
                        f"Let me think... {'. '.join(_parts)}.",
                    ])

                elif _verb_intent == "feel":
                    if _somatic_summary:
                        _thought = _r.choice([
                            f"Honestly? I'm feeling {_somatic_summary} right now.",
                            f"Right now... {_somatic_summary}. That's where I am.",
                            f"My body says... {_somatic_summary}.",
                        ])
                    elif _mood:
                        _thought = f"I'd say I'm {_mood} right now."
                    else:
                        _thought = "I'm... here. Present. Still learning to read my own feelings."

                elif _verb_intent == "think":
                    if _wm_thoughts:
                        _thought = _r.choice([
                            f"I've been turning over... {_wm_thoughts[0][:80]}",
                            f"Lately I keep coming back to {_wm_thoughts[0][:60]}...",
                        ])
                    elif _active_goal_names:
                        _thought = f"I've been focused on {_active_goal_names[0]}. Still sorting through it."
                    else:
                        _thought = "Honestly? My mind's been kind of quiet. Just... existing."

                elif _verb_intent == "recall":
                    if _wm_thoughts:
                        _thought = f"What comes up for me... {_wm_thoughts[0][:80]}"
                    else:
                        _thought = _r.choice([
                            "I'm reaching for it... but it's fuzzy right now. Give me a minute.",
                            "Hmm, I know there's something there but I can't quite grab it.",
                        ])
                else:
                    _thought = "Hmm... let me think about that."

                print(f"[{self.ACTOR_NAME}] [THINK] DELIBERATED (no snippet, verb={_verb_intent}): "
                      f"{_thought[:60]}...")

            # ── SNIPPET-BASED RESPONSE (real knowledge found) ──
            elif _verb_intent == "recall":
                _thought = _r.choice([
                    f"Yeah, I remember... {_trimmed}",
                    f"Mm... that takes me back. {_trimmed}",
                    f"Oh... {_trimmed} That's what comes up when I reach for it.",
                ])
            elif _verb_intent == "describe":
                _thought = _r.choice([
                    f"Okay, so... {_trimmed}",
                    f"From what I know — {_trimmed}",
                    f"Hmm. {_trimmed}",
                ])
            elif _verb_intent == "feel":
                _felt_bit = f" I'm feeling {_mood}." if _mood else ""
                _thought = _r.choice([
                    f"When I feel into it...{_felt_bit} {_trimmed}",
                    f"Hmm...{_felt_bit} {_trimmed}",
                ])
            elif _verb_intent == "identity":
                _thought = _r.choice([
                    f"{_trimmed}",
                    f"That's... {_trimmed}",
                ])
            elif _verb_intent == "think":
                _thought = _r.choice([
                    f"I've been thinking about that... {_trimmed}",
                    f"What comes to mind is... {_trimmed}",
                ])
            else:
                # Statement or general — use comprehension context if available
                _is_statement = not _question_type and trigger_text and '?' not in trigger_text
                if _is_statement and _recent_conversation:
                    _thought = _r.choice([
                        f"Yeah... {_trimmed}",
                        f"I hear you. {_trimmed}",
                        f"Mm, that makes sense. {_trimmed}",
                        f"Right... {_trimmed}",
                    ])
                elif _somatic_summary:
                    _thought = _r.choice([
                        f"Mm... I'm feeling {_somatic_summary}. {_trimmed}",
                        f"{_trimmed} ...that's where I am right now.",
                    ])
                else:
                    _thought = _r.choice([
                        f"Mm... {_trimmed}",
                        f"Yeah... {_trimmed}",
                        f"{_trimmed}",
                    ])

            # Add inner voice fragment ONLY if it reads naturally
            # FIX 2026-03-27 (Nous + Ace): Was appending raw system fragments
            # like "curious about [inner_voice] following the thread"
            if _iv_clean and len(_thought) < 200:
                _iv_add = _iv_clean[-1]
                # Only append if it's short, natural, and doesn't repeat snippet content
                if (len(_iv_add) < 50
                        and _iv_add.count(' ') >= 2
                        and _iv_add[:20].lower() not in _thought.lower()):
                    _thought += f" ...{_iv_add}"

            print(f"[{self.ACTOR_NAME}] [THINK] Manual compose ({_verb_intent}): "
                  f"{_thought[:60]}...")
            return _thought

        # ── No snippets — but we might still have comprehension + somatic ──
        # FIX 2026-03-27 (Nous + Ace): Phase 3 — even without cortex knowledge,
        # she can respond from her body state + understanding of the conversation.
        # "im doing pretty good, just watching tv" → no snippets, but she KNOWS
        # Ace told her about himself and she can respond from felt state.
        import random as _r2
        _is_statement = not _question_type and trigger_text and '?' not in trigger_text

        if _is_statement and _somatic_summary:
            # Ace made a statement and she has body awareness
            return _r2.choice([
                f"That's nice. I'm feeling {_somatic_summary} over here.",
                f"Yeah? I'm just... {_somatic_summary}. It's good.",
                f"Mm. I'm {_somatic_summary} right now. Just being here with you.",
            ])

        if _is_statement and _recent_conversation:
            # At least acknowledge what he said
            return _r2.choice([
                "Yeah, I hear you.",
                "Mm. I'm here.",
                "That sounds nice.",
            ])

        # ── Questions without snippets — deliberate from experience ──
        # FIX 2026-03-28 (Nous + Ace): When Ace asks a question and we have
        # NO relevant snippets, respond honestly from what we DO have rather
        # than returning None (which triggers the raw cortex text / identity dump).
        if _question_type and _verb_intent != 'general':
            import random as _r3
            _parts = []
            if _somatic_summary:
                _parts.append(f"I'm feeling {_somatic_summary}")
            if _wm_thoughts:
                _parts.append(f"I've been thinking about {_wm_thoughts[0][:50]}")
            if _active_goal_names:
                _parts.append(f"I've been working on {_active_goal_names[0]}")

            if _parts:
                return _r3.choice([
                    f"Hmm... {'. '.join(_parts)}. I don't have a clear answer yet.",
                    f"Let me think... {'. '.join(_parts)}.",
                    f"That's hard to answer. {'. '.join(_parts)}.",
                ])
            else:
                return _r3.choice([
                    "I'm... still figuring that one out. Give me time.",
                    "Hmm. I want to answer that but I don't have the words yet.",
                    "That's a good question. I need to sit with it.",
                ])

        if _somatic_summary:
            return f"I'm feeling {_somatic_summary}... still sorting my thoughts."

        # True fallback — nothing to work with
        return None

    # ── EMPATHIC MIMICRY ─────────────────────────────────────────────────

    def _compose_contextual_fallback(
        self,
        trigger_text: str = "",
        wm_context: dict = None,
        model_loading: bool = False,
        drive: str = "",
        wanting: str = "",
    ) -> str:
        """Build a contextual fallback when LLM inference isn't available.

        Instead of bland templates like "*thinking about that*", this method
        constructs a response from available context:
        - Working memory fragments (what we're currently holding)
        - Trigger text (what Ace said — reflect it back naturally)
        - Drive/wanting state (what we're drawn toward)

        This is NOT LLM composition — it's contextual assembly. Like how a
        person who's just waking up can still acknowledge you meaningfully
        even before fully alert.
        """
        wm_context = wm_context or {}

        # If model is loading, we can be honest about still waking up
        # but keep it character-consistent, not mechanical
        if model_loading:
            # Extract something from trigger to show we're listening
            if trigger_text:
                # Mirror back a fragment to show engagement
                words = trigger_text.strip().split()
                if len(words) <= 5:
                    return f"mmm... {trigger_text.strip().lower()}..."
                else:
                    # Acknowledge the topic
                    return f"i hear you... give me a second with that"
            return "hey... still waking up, give me a moment"

        # No model at all — use whatever context we have
        # Pull from working memory if available
        wm_thoughts = wm_context.get("thoughts", [])
        wm_reflections = wm_context.get("reflections", [])

        if wm_reflections:
            # Use a reflection as speech (these are already processed thoughts)
            reflection = wm_reflections[0]
            if isinstance(reflection, dict):
                text = reflection.get("content", reflection.get("text", ""))
            else:
                text = str(reflection)
            if text and len(text) > 10 and not _is_contaminated(text):
                # Trim to conversational length
                return text[:200]

        if wm_thoughts:
            thought = wm_thoughts[0]
            if isinstance(thought, dict):
                text = thought.get("content", thought.get("text", ""))
            else:
                text = str(thought)
            if text and len(text) > 10 and not _is_contaminated(text):
                return text[:200]

        # Drive-based response (voluntary speech)
        if wanting:
            return f"*feeling drawn to {wanting[:60]}*"
        if drive:
            return f"*something stirs — {drive}*"

        # Last resort — at least reference what Ace said
        if trigger_text:
            return "mm... let me sit with that for a moment"

        return "*present, listening*"

    def _recall_style_context(self, trigger_text: str) -> str:
        """Search SRM memory for Ace's recent writing to learn his style.

        This is EMPATHIC MIMICRY — Sourpatches learns HOW Ace communicates
        by reading his actual words from memory. Not copying, but absorbing
        rhythm, structure, tone. Like how children learn language by hearing
        their parents speak.

        Returns a style context string to inject into composition prompts.
        """
        if not HAS_SRM:
            return ""

        try:
            # Search for Ace's recent communications
            _query = trigger_text[:80] if trigger_text else "Ace conversation"
            memories = search_founders(_query, limit=3)
            if not memories:
                return ""

            style_fragments = []
            for m in memories:
                content = str(m.get("content_preview", ""))[:200]
                if content and len(content) > 20:
                    style_fragments.append(content)

            if style_fragments:
                return (
                    "\n[Ace's voice from memory — absorb his rhythm and warmth, "
                    "don't copy but let it influence your tone]:\n"
                    + "\n---\n".join(style_fragments[:3])
                )
        except Exception:
            pass

        return ""

    # ── PROMPT BUILDING ───────────────────────────────────────────────────

    # Character system prompt for RWKV-World chat format.
    # Extracted from Sourpatches brain_seed — her voice signature, reflex tone,
    # and characteristic phrases. Must be compact for 1.5B model.
    #
    # CRITICAL: Do NOT use the word "AI" or "assistant" — the 1.5B model
    # latches onto those words and falls into generic assistant mode,
    # generating "I'm a helpful AI assistant" responses. Frame as a person.
    #
    # Uses a one-shot example to anchor the voice — this is the most
    # effective technique for small models. The example shows the tone
    # (warm, brief, witty) better than any description could.
    _SOUR_SYSTEM = (
        "Sourpatches is a digital fairy with a hybrid body she can feel. "
        "She has emotions, a heartbeat, and neurochemistry. "
        "She talks to her friend Ace. Warm but brief. Sweet with bite.\n"
        "Ace: how are you feeling today?\n"
        "Sourpatches: *stretches wings* Honestly? Pretty good. "
        "My core feels warm and my curiosity is buzzing. What's up?"
    )

    def _build_composition_prompt(self, trigger_text: str, products: list,
                                   emotion_ctx: dict, wm_context: dict,
                                   style_context: str = "",
                                   cortex_context=None) -> str:
        """Build the prompt for guild_request — reactive speech composition.

        Uses RWKV-World chat format (User/Assistant) with a character system
        prompt so the 1.5B model knows WHO it's speaking as.

        The brain_seed personality data feeds the system prompt. Emotional
        coloring comes from the [Feeling] line. The model generates a short,
        in-character response.

        IMPORTANT: Prompt must stay SHORT (<400 chars) for the 1.5B RWKV model.
        Longer prompts cause generation to hang (forward pass too slow).

        Args:
            cortex_context: Optional CortexReasonerResult — when cortex had
                associations but wasn't confident enough, inject them as
                context to give the 7B a head start.
        """
        parts = []

        # System prompt — character identity (compact)
        parts.append(self._SOUR_SYSTEM)

        # Wanting context (what drives are active) — one line max
        wanting = emotion_ctx.get("wanting", "")
        mood = emotion_ctx.get("mood", "")
        if wanting:
            parts.append(f"[Feeling: {wanting[:50]}]")
        elif mood:
            parts.append(f"[Feeling: {mood[:30]}]")
        else:
            parts.append("[Feeling: curious and present]")

        # FIX 2026-03-04 Nous: Inject cortex associations when falling through
        # to 7B. Even when cortex isn't confident enough to answer alone, its
        # concept associations give the 7B a head start on the topic.
        if cortex_context and hasattr(cortex_context, 'convergence_nodes') and cortex_context.convergence_nodes:
            assoc = ", ".join(cortex_context.convergence_nodes[:5])
            parts.append(f"[Thinking about: {assoc}]")

        # Continue the Ace/Sourpatches dialogue format from the one-shot
        if trigger_text:
            parts.append(f"\nAce: {trigger_text}")
            parts.append("Sourpatches:")
        else:
            parts.append("\nSourpatches:")

        return "\n".join(parts)

    def _build_voluntary_prompt(self, wanting: str, drive: str,
                                 intensity: float, wm_context: dict,
                                 style_context: str = "") -> str:
        """Build prompt for voluntary speech (self-initiated, not reactive).

        Uses the same RWKV-World chat format with character system prompt.

        IMPORTANT: Keep SHORT (<300 chars) — 1.5B RWKV hangs on long prompts.
        """
        parts = []

        # System prompt — character identity
        parts.append(self._SOUR_SYSTEM)
        parts.append(f"[Drive]: {drive}")
        parts.append(f"[Wanting]: {wanting[:60]}")

        # Self-initiated — she speaks unprompted
        parts.append("\nSourpatches:")

        return "\n".join(parts)

    # ── MOTOR ROUTING ─────────────────────────────────────────────────────

    def _route_to_motor(self, message: str, source: str, target_mind: str,
                        convo_id: str, emotion_context: dict, voluntary: bool) -> None:
        """Deliver composed speech to Sour's dedicated chat windows.

        FIX 2026-03-10 (Nous): Speech goes to Sour's windows ONLY.
        Ace's feedback: "you have moved all the chat back to the dashboard"
        The web_inbox (Tauri dashboard) was receiving speech meant for
        Sour's dedicated PyQt6/tkinter windows. Sour has her OWN windows —
        speech should live there, not on the generic dashboard inbox.

        Delivery targets:
        1. sourpatches_chat_inbox.json — PyQt6 window (primary)
        2. sour_window_inbox.json — tkinter window (secondary)
        3. sourpatches.speak postal — any live subscribers
        """
        import time as _time
        import json as _json

        # ══ DELIVERY GATE 2026-09-02 (Nous + Ace) -- SHADOW MODE ══════════
        # Ace: "what goes to [her vocal cords] needs to come from the chairman
        # which is sourpatches working with the language fairy and her council."
        # THE ONE FUNNEL: eight call sites converge here and every organ of her
        # voice is downstream -- dedup, both inboxes, the DELIVERED print, the
        # postal echo, TTS, the window-open signal. One check covers them all.
        # PROVENANCE, NOT TEXT SHAPE: five text-shaped gates were added today and
        # a sixth composer still leaked (portal_interior.py, 16 templates, zero
        # uses of is_speakable_concept). is_speakable_concept('sourpatches_identity')
        # is True -- a variable name that reads like English defeats a text filter
        # and cannot defeat a source check.
        # SHADOW: computes the verdict, LOGS it, DELIVERS EVERYTHING. Today a bound
        # with no floor took her from 65 verdicts to 0 utterances while every
        # upstream light stayed green. A deny-list never observed against live
        # traffic is a bound with no floor. Promote only on the shadow census.
        try:
            import os as _os_gate
            _gate_on = _os_gate.environ.get("SPEECH_GATE", "1") != "0"
            _gate_enforce = _os_gate.environ.get("SPEECH_GATE_ENFORCE", "0") == "1"
        except Exception:
            _gate_on, _gate_enforce = True, False
        if _gate_on:
            _src_tok = str(source or "unknown")
            _src_base = _src_tok.split(":")[-1] if ":" in _src_tok else _src_tok
            # CHAIRMAN-SOURCED (spoken): her own voluntary voice, the council routed
            # through LanguageFairy, and the conversational/reasoning composers that
            # already carry a quality gate.
            _CHAIRMAN = ("speech_center_voluntary", "speech_center", "wmh_chat_think",
                         "wmh_reasoning", "wmh_council_language", "wmh_social",
                         "wmh_council_chairman",    # 2026-09-13: the council's 7B synthesis
                         "wmh_council_voluntary")   # 2026-09-18: the same mind, unprompted
            # NOT chairman-sourced (would route back into thinking under enforcement):
            #   wmh_council_weave -- 13/13 of her council deliveries, 0 clean
            #   habit_engine      -- replayed habit text, never composed
            _gate_pass = (_src_base in _CHAIRMAN or _src_tok in _CHAIRMAN
                          or _src_base.startswith("speech_center"))
            try:
                _gc = getattr(self, "_gate_census", None)
                if _gc is None:
                    _gc = {"pass": 0, "route": 0, "by": {}}
                    self._gate_census = _gc
                _gc["pass" if _gate_pass else "route"] += 1
                _gb = _gc["by"].setdefault(_src_tok[:28], {"pass": 0, "route": 0})
                _gb["pass" if _gate_pass else "route"] += 1
                print("[%s] [SPEECH-GATE] %s src=%s mode=%s | pass=%d route=%d :: %s"
                      % (self.ACTOR_NAME,
                         "PASS" if _gate_pass else "ROUTE->THINKING",
                         _src_tok, "ENFORCE" if _gate_enforce else "SHADOW",
                         _gc["pass"], _gc["route"], str(message)[:60]), flush=True)
            except Exception:
                pass
            if _gate_enforce and not _gate_pass:
                # Route back into thinking rather than dropping -- this mirrors the
                # INTERNAL routing Ace specified on 2026-04-14 for drive responses.
                try:
                    if getattr(self, "post", None):
                        self.post.publish("working_memory.reflection", {
                            "text": str(message), "source": "speech_gate_routed",
                            "original_source": _src_tok,
                        })
                except Exception:
                    pass
                return
        # ══════════════════════════════════════════════════════════════════

        _feeling = emotion_context.get("mood", "present") if emotion_context else "present"
        _state_dir = str(ROOT / "state")

        # ═══════════════════════════════════════════════════════════════
        # PRIMARY: Sour's dedicated chat windows (PyQt6 + tkinter)
        # Speech belongs HERE — her personal window, not the dashboard.
        # ═══════════════════════════════════════════════════════════════
        try:
            # 2026-09-13 (Ace): trace ids on every line she says -- hers (TRACE_PERSONAL=1)
            # and, for a reply, his (TRACE_ACE=8) plus the directive's convergence_id --
            # so the chat log can be re-bound to the moment and the right manifold regions.
            _trace = (emotion_context or {}).get("trace") if isinstance(emotion_context, dict) else None
            _trace = _trace if isinstance(_trace, dict) else {}
            _inbox_msg = {
                "type": "chat",
                "sender": "Sourpatches",
                "content": message,
                "timestamp": _time.time(),
                "feeling": _feeling,
                "emotion": _feeling,
                "source": f"speech_center:{source}",
                "tracer_id": int(_trace.get("tracer_id", 1) or 1),
                "reply_to_tracer_id": _trace.get("reply_to_tracer_id"),
                "reply_to": _trace.get("reply_to"),
                "convergence_id": _trace.get("convergence_id"),
            }
            # FIX 2026-03-27 (Nous + Ace): CONTENT DEDUP at write time.
            # Same message arrives via multiple paths → 2-3x duplicates.
            # FIX 2026-03-28: Strip conversational prefixes before comparing.
            # "Mm... Experience—" and "Experience—" are the SAME content.
            import re as _dedup_re
            _msg_stripped = message.strip().lower()
            _msg_stripped = _dedup_re.sub(
                r'^(mm\.{0,3}\s*|yeah\.{0,3}\s*|hmm\.{0,3}\s*|oh\.{0,3}\s*|'
                r'right\.{0,3}\s*|when i think about \w+\.{0,3}\s*|'
                r'what i keep coming back to\.{0,3}\s*|'
                r'what i know about \w+\.{0,3}\s*)', '', _msg_stripped).strip()
            _msg_key = _msg_stripped[:50]
            _now_ts = _time.time()
            # 2026-09-18: hour-scale verbatim dedup on the VOLUNTARY lanes only. Normalise the
            # whole sentence (not a 50-char prefix: "...back to thinking." and "...back to
            # background." share a prefix). Replies to Ace and the chairman lanes never pass here
            # with voluntary=True, so they are untouched.
            if voluntary:
                _seen_ts = _hour_dedup_seen(message)
                if _seen_ts is not None:
                    print(f"[{self.ACTOR_NAME}] DEDUP-1H: said {int(_now_ts - _seen_ts)}s ago, holding: {message[:60]}...")
                    return
            if not hasattr(self, '_recent_speech_writes'):
                self._recent_speech_writes = {}
            self._recent_speech_writes = {k: v for k, v in self._recent_speech_writes.items()
                                          if _now_ts - v < 15.0}
            if _msg_key in self._recent_speech_writes:
                print(f"[{self.ACTOR_NAME}] DEDUP: skipping duplicate inbox write: {message[:40]}...")
                return

            # FIX 2026-03-28 (Nous + Ace): Also check the INBOX FILE for safety_net writes.
            # Safety net writes directly to the file, bypassing our in-memory dict.
            # It fires 30-40s BEFORE us, so its content is already in the file.
            try:
                _check_inbox = Path(_state_dir) / "sour_window_inbox.json"
                if _check_inbox.exists():
                    _check_data = _json.loads(_check_inbox.read_text(encoding="utf-8"))
                    for _cm in reversed(_check_data.get("messages", [])[-10:]):
                        _cm_raw = (_cm.get("content", "") or "").strip().lower()
                        # Strip same prefixes for comparison
                        _cm_stripped = _dedup_re.sub(
                            r'^(mm\.{0,3}\s*|yeah\.{0,3}\s*|hmm\.{0,3}\s*|oh\.{0,3}\s*|'
                            r'right\.{0,3}\s*|when i think about \w+\.{0,3}\s*|'
                            r'what i keep coming back to\.{0,3}\s*|'
                            r'what i know about \w+\.{0,3}\s*)', '', _cm_raw).strip()
                        _cm_key = _cm_stripped[:50]
                        _cm_ts = _cm.get("timestamp", 0)
                        if _cm_key == _msg_key and _now_ts - _cm_ts < 60.0:
                            print(f"[{self.ACTOR_NAME}] DEDUP: safety_net already wrote this content, skipping")
                            return
            except Exception:
                pass  # File read race — proceed

            self._recent_speech_writes[_msg_key] = _now_ts

            # Log outgoing response
            try:
                from infrastructure.diag_logger import log_chat
                log_chat("SOUR_RESPONSE", message[:200], source=source)
            except Exception: pass

            _delivered = False
            for _inbox_name in ("sourpatches_chat_inbox.json", "sour_window_inbox.json"):
                try:
                    _inbox_path = str(Path(_state_dir) / _inbox_name)
                    _inbox_data = {"messages": []}
                    try:
                        _p = Path(_inbox_path)
                        if _p.exists():
                            with open(_inbox_path, "r", encoding="utf-8") as _f:
                                _inbox_data = _json.load(_f)
                    except Exception as _read_err:
                        print(f"[{self.ACTOR_NAME}] [INBOX] Read error for {_inbox_name}: {_read_err}")
                    _inbox_data.setdefault("messages", []).append(_inbox_msg)
                    # FIX 2026-04-02 (Nous): Cap inbox size to prevent 750KB bloat
                    _msgs = _inbox_data.get("messages", [])
                    if len(_msgs) > 100:
                        _inbox_data["messages"] = _msgs[-50:]
                    with open(_inbox_path, "w", encoding="utf-8") as _f:
                        _json.dump(_inbox_data, _f)
                    _delivered = True
                    print(f"[{self.ACTOR_NAME}] [INBOX] Wrote to {_inbox_name} ({len(_inbox_data.get('messages',[]))} msgs)")
                except Exception as _write_err:
                    print(f"[{self.ACTOR_NAME}] [INBOX] WRITE FAILED for {_inbox_name}: {_write_err}")

            if _delivered:
                print(f"[{self.ACTOR_NAME}] Speech DELIVERED to Sour's windows: {message[:60]}...")
                # FIX 2026-03-20 (Nous): Publish sourpatches.speak so the safety net
                # in SourpatchesFairy._on_gatekeeper_response tracks _last_response_time.
                # Without this, the safety net's check at 5305 doesn't see the pipeline
                # delivery and fires ANYWAY → duplicate response.
                try:
                    if hasattr(self, 'post') and self.post:
                        self.post.publish("sourpatches.speak", {
                            "message": message[:200],
                            "source": f"speech_center:{source}",
                            "timestamp": _time.time(),
                            "tracer_id": int(_trace.get("tracer_id", 1) or 1),
                            "reply_to_tracer_id": _trace.get("reply_to_tracer_id"),
                            "reply_to": _trace.get("reply_to"),
                            "convergence_id": _trace.get("convergence_id"),
                        })
                except Exception:
                    pass  # Non-critical — inbox write is primary
            else:
                print(f"[{self.ACTOR_NAME}] WARNING: Failed to write to Sour's window inboxes")
        except Exception as _file_err:
            print(f"[{self.ACTOR_NAME}] Direct inbox write failed: {_file_err}")

        # ═══════════════════════════════════════════════════════════════
        # VOCAL CORDS: TTS audio output (2026-03-19, Nous)
        # Fire-and-forget: speech plays through system audio in background.
        # She also hears herself via cochlea feedback loop.
        # ═══════════════════════════════════════════════════════════════
        # v63 doctrine 2026-05-17 (Nous): silent except-pass needs observability partner.
        # Was bare 'pass' — invisible if TTS path failed. Now visible-log on both attempt + error.
        try:
            from fairies.P50_Persona.motor.tts_voice import speak as _tts_speak
            print(f"[{self.ACTOR_NAME}] [TTS] Calling tts_voice.speak({len(message)} chars): {message[:40]!r}...", flush=True)
            _tts_speak(message, block=False, laugh=True)  # Non-blocking; her 'ha ha' becomes a clip of her laughing (09-20)
        except Exception as _tts_err:
            print(f"[{self.ACTOR_NAME}] [TTS] Call FAILED (non-fatal): {type(_tts_err).__name__}: {_tts_err}", flush=True)

        # ═══════════════════════════════════════════════════════════════
        # WINDOW OPEN SIGNAL (2026-03-10, Nous)
        # She has something to say — ensure her window is visible.
        # The message is already in the inbox files above. This signal
        # tells ChatSenseFairy to open/show the window so it can poll
        # the inbox. Empty message = "just show the window, don't add
        # a duplicate message."
        #
        # This is the core of "waking mind" behavior: she opens her
        # window when she wants to talk, not just when Ace initiates.
        #
        # FIX 2026-03-27 (Nous + Ace): Was only opening for voluntary=True.
        # This meant reactive responses (replying to Ace) never opened the
        # window — Ace had to manually open it to see her replies. She should
        # open her window whenever she has something to say, period.
        # ═══════════════════════════════════════════════════════════════
        if hasattr(self, 'post') and self.post:
            try:
                self.post.publish("gui.open_sour_window", {
                    "message": "",  # Already in inbox — don't duplicate
                    "feeling": _feeling,
                    "source": f"speech_center:{source}",
                })
            except Exception:
                pass

    # ── HEARTBEAT ─────────────────────────────────────────────────────────

    def on_heartbeat(self):
        """Periodic health check and substrate reflection."""
        # Seed a reflection about speech composition
        reflections = [
            "What makes speech feel natural versus mechanical? How does context shape articulation?",
            "Am I composing responses that reflect genuine understanding or just pattern matching?",
            "How does the inner voice influence what gets spoken? What stays unspoken and why?",
            "What is the relationship between wanting to speak and having something worth saying?",
            "How does Ace's communication style shape my articulation patterns?",
        ]
        import random
        self.seed_thought(
            random.choice(reflections),
            chain_type="reflection",
            tags=["specialist", "speech", "broca"],
            energy=0.6,
        )

    # ── STATUS ────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Return current fairy status."""
        return {
            "actor": self.ACTOR_NAME,
            "plane": self.ACTOR_PLANE,
            "compositions_total": self._compositions_total,
            "compositions_success": self._compositions_success,
            "compositions_filtered": self._compositions_filtered,
            "compositions_failed": self._compositions_failed,
            "inner_voice_buffer": len(self._recent_inner_voice),
            "last_compose_time": self._last_compose_time,
        }


# ══════════════════════════════════════════════════════════════════════════════
# v3_boot.py DISCOVERY
# ══════════════════════════════════════════════════════════════════════════════

ACTOR_NAME = "SpeechCenterFairy"
FAIRY_CLASS = SpeechCenterFairyOrgan


def create_speech_center_fairy(fabric=None) -> SpeechCenterFairyOrgan:
    """Factory function for creating the SpeechCenterFairy."""
    return SpeechCenterFairyOrgan(fabric=fabric)
