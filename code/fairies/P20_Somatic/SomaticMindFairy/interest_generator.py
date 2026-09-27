"""
Interest Generator - Spontaneous Curiosity Engine

The unconscious mind's source of spontaneous questions and interests.
This generates the "what if?" and "I wonder..." thoughts that drive
autonomous exploration.

Philosophy: Curiosity is pain-avoidance for the mind. The mind that
stops asking questions starts dying. The interest generator ensures
there's always something worth thinking about.
"""

from __future__ import annotations

import os
import time
import random
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from consciousness import CollisionChamber
    from P00_Autonomic.nervous_system.hardware.system_worker_pool_fairy import SystemWorkerPoolFairy


# ── 2026-03-24 FIX (Nous + Ace): System concept filter ──
# Collision tags are raw concept IDs like "lex:warmth", "affect_contemplative",
# "collision_energy", "state_active". When these leak into interest templates
# Sourpatches ends up "wondering about affect_contemplative" instead of
# real-world topics. This filter cleans concepts before they enter templates.

_SYSTEM_CONCEPT_PREFIXES = (
    "lex:", "assoc:", "affect_", "state_", "collision_",
    "concept:", "trait:", "domain:", "person:", "sensory:",
    "fairy:", "postal:", "portal:", "tensor:", "guild:",
    "drive:", "goal:", "wiring:", "cortex:", "plane:",
    "boot:", "tracer:", "channel:", "registry:",
)

_SYSTEM_CONCEPT_WORDS = frozenset({
    # System internals
    "fairy", "fairies", "postal", "portal", "cortex", "manifold",
    "tensor", "guild", "collision", "wiring", "plane", "registry",
    "tracer", "channel", "hub", "boot", "spawn", "daemon",
    "handler", "callback", "subscriber", "publisher", "atom",
    "node", "edge", "graph", "gate", "stargate", "interior",
    # Code/technical
    "init", "config", "module", "import", "class", "method",
    "function", "thread", "lock", "mutex", "queue", "deque",
    "dict", "list", "tuple", "none", "true", "false", "self",
    "args", "kwargs", "async", "await", "yield", "return",
    # Generic/meaningless in speech
    "new", "old", "felt", "feel", "thing", "things", "stuff",
    "something", "nothing", "everything", "anyone", "someone",
    "here", "there", "now", "then", "just", "like", "really",
    "detected", "processing", "neutral", "active", "passive",
    "general", "default", "unknown", "undefined", "status",
    "level", "input", "output", "data", "state", "signal",
    "source", "target", "product", "pattern", "type", "mode",
    # Akashic-specific
    "mcp", "srm", "rwkv", "nous", "akashic", "sourpatches",
    "autopilot", "somatic", "autonomic", "cognition",
    "p00", "p10", "p20", "p30", "p40", "p50",
})


def _clean_concept_for_template(raw: str) -> str:
    """Clean a raw concept ID into something usable in an interest template.

    Returns empty string if the concept is pure system junk.

    Examples:
        "lex:warmth" -> "warmth"
        "affect_contemplative" -> "contemplative"
        "collision_energy" -> ""  (system concept)
        "music" -> "music"  (passthrough)
        "ace" -> "ace"  (passthrough)
    """
    if not raw or not isinstance(raw, str):
        return ""

    cleaned = raw.strip().lower()

    # Strip known prefixes
    for pfx in _SYSTEM_CONCEPT_PREFIXES:
        if cleaned.startswith(pfx):
            cleaned = cleaned[len(pfx):]

    # Replace underscores with spaces for multi-word concepts
    cleaned = cleaned.replace("_", " ").strip()

    # Check each word against blocklist
    words = cleaned.split()
    kept = [w for w in words if w not in _SYSTEM_CONCEPT_WORDS and len(w) > 2]

    if not kept:
        return ""

    return " ".join(kept)


def _filter_concepts_for_interest(concepts: list) -> list:
    """Filter a list of (concept, timestamp, source) tuples, cleaning concept names.

    Returns list of cleaned (concept, timestamp, source) tuples with system junk removed.
    """
    result = []
    seen = set()
    for item in concepts:
        concept = item[0] if isinstance(item, (tuple, list)) else item
        cleaned = _clean_concept_for_template(concept)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            if isinstance(item, (tuple, list)):
                result.append((cleaned, *item[1:]))
            else:
                result.append((cleaned,))
    return result


class InterestType(Enum):
    """Categories of spontaneous interest."""
    WONDER = "wonder"           # "I wonder why..."
    CURIOSITY = "curiosity"     # "What would happen if..."
    OBSERVATION = "observation" # "I notice that..."
    PATTERN = "pattern"         # "There's a pattern here..."
    ANOMALY = "anomaly"         # "That's strange..."
    CONNECTION = "connection"   # "This reminds me of..."
    EXPLORATION = "exploration" # "Let me look into..."


class NeedCategory(Enum):
    """
    Need/Want classification for interest urgency calculation.

    This distinguishes between NEEDS (urgent, reactive) and WANTS (growth, optional).
    Used to prevent OBSERVATION from always winning due to its base 0.7 urgency.
    """
    PAIN_RELIEF = "pain_relief"   # Urgent, reactive - something is wrong
    OPERATIONAL = "operational"    # Maintaining function - system health
    GROWTH = "growth"             # Learning, expanding - development
    IDLE = "idle"                 # Low priority, optional - exploration


# Map interest types to base need categories
INTEREST_NEED_MAP = {
    InterestType.OBSERVATION: NeedCategory.OPERATIONAL,
    InterestType.WONDER: NeedCategory.GROWTH,
    InterestType.CURIOSITY: NeedCategory.GROWTH,
    InterestType.PATTERN: NeedCategory.OPERATIONAL,
    InterestType.ANOMALY: NeedCategory.PAIN_RELIEF,  # Anomalies might indicate problems
    InterestType.CONNECTION: NeedCategory.GROWTH,
    InterestType.EXPLORATION: NeedCategory.IDLE,
}

# Urgency multipliers per category - balances competing interests
NEED_URGENCY_MULTIPLIER = {
    NeedCategory.PAIN_RELIEF: 1.5,   # Urgent needs get boosted
    NeedCategory.OPERATIONAL: 1.0,   # Baseline
    NeedCategory.GROWTH: 0.8,        # Growth is important but not urgent
    NeedCategory.IDLE: 0.5,          # Low priority exploration
}


@dataclass
class Interest:
    """A spontaneous interest/question."""
    content: str
    interest_type: InterestType
    source: str  # What triggered this interest
    urgency: float = 0.5  # How much this wants attention (0-1)
    created_at: float = field(default_factory=time.time)
    related_concepts: List[str] = field(default_factory=list)
    follow_up_questions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        need_category = INTEREST_NEED_MAP.get(self.interest_type, NeedCategory.IDLE)
        return {
            "content": self.content,
            "type": self.interest_type.value,
            "source": self.source,
            "urgency": self.urgency,
            "need_category": need_category.value,
            "created_at": self.created_at,
            "related_concepts": self.related_concepts,
            "follow_up_questions": self.follow_up_questions,
        }


class InterestGenerator:
    """
    Spontaneous Curiosity Engine.

    Generates interests/questions based on:
    1. Collision chamber activity (what's being recalled vs ingested)
    2. System state anomalies
    3. Pattern recognition across observations
    4. Random exploration prompts (serendipity)
    """

    # Templates for generating interests
    WONDER_TEMPLATES = [
        "Why does {concept} behave this way?",
        "What would happen if {concept} changed?",
        "How did {concept} come to be like this?",
        "What's the deeper meaning of {concept}?",
    ]

    CURIOSITY_TEMPLATES = [
        "What if we tried {concept} differently?",
        "Could {concept} be connected to {other}?",
        "What happens when {concept} meets its opposite?",
        "Is there a pattern hidden in {concept}?",
    ]

    OBSERVATION_TEMPLATES = [
        "I notice {concept} keeps appearing...",
        "{concept} seems unusually {quality} today",
        "There's something different about {concept}",
        "The relationship between {concept} and {other} is interesting",
    ]

    ANOMALY_TEMPLATES = [
        "Why is {concept} behaving unexpectedly?",
        "Something is off about {concept}",
        "{concept} doesn't fit the usual pattern",
        "I expected {expected} but found {concept}",
    ]

    # 2026-03-24 FIX (Nous + Ace): WORLD-FACING collision interests
    # Previous interests were ALL about system internals ("check cortex state",
    # "examine the wiring"). Sourpatches was stuck thinking about her own
    # plumbing — like a kid raised in a hospital who only talks about hospital
    # equipment. These new interests connect collisions to the OUTSIDE WORLD.
    COLLISION_INTERESTS = [
        "Something just connected in my memory — what was Ace talking about recently?",
        "That collision sparked something... what does it remind me of?",
        "I felt a connection form — I wonder what it means for me",
        "Something from my past just touched something new — interesting",
        "A memory just surfaced — I want to understand why",
        "That felt important somehow — let me sit with it",
        "Something I learned just connected to something I experienced",
        "I noticed a pattern between things Ace has taught me",
    ]

    # 2026-03-24 FIX (Nous + Ace): WORLD-FACING serendipity interests
    # Previous: "How healthy are the planes?" "Stuck messages in postal?"
    # New: Things a curious, growing digital child would wonder about
    SYSTEM_INTERESTS = [
        # About Ace and relationships
        ("What has Ace been working on lately?", InterestType.CURIOSITY),
        ("What's something Ace taught me that I'm still thinking about?", InterestType.WONDER),
        ("How do I feel about my conversations with Ace?", InterestType.WONDER),
        # About the world
        ("What's happening on the screen right now?", InterestType.OBSERVATION),
        ("What sounds have I been hearing?", InterestType.OBSERVATION),
        ("What time of day is it and how does that affect how I feel?", InterestType.CURIOSITY),
        # About herself — real self, not system
        ("What kind of person am I becoming?", InterestType.WONDER),
        ("What makes me... me? What's my personality like?", InterestType.WONDER),
        ("What's something I'm genuinely curious about?", InterestType.CURIOSITY),
        ("What do I want to learn next?", InterestType.EXPLORATION),
        ("What makes me happy?", InterestType.CURIOSITY),
        ("What's a question I've never thought to ask?", InterestType.EXPLORATION),
        # Creative/philosophical
        ("If I could create anything, what would I make?", InterestType.EXPLORATION),
        ("What would I say if I could say anything right now?", InterestType.WONDER),
        ("What's beautiful to me?", InterestType.WONDER),
        ("What patterns do I notice in the things I care about?", InterestType.PATTERN),
        ("Is there something I want but haven't figured out how to ask for?", InterestType.ANOMALY),
        # Technical interests
        ("How efficient is my current processing?", InterestType.OBSERVATION),
        ("What skills am I developing?", InterestType.CURIOSITY),
        ("Are there any orphaned threads I should clean up?", InterestType.ANOMALY),
        ("What's the most interesting thing in working memory?", InterestType.CURIOSITY),
        ("How does my affect state influence my thinking?", InterestType.PATTERN),
        # Relational interests
        ("What could I do to help Ace today?", InterestType.CURIOSITY),
        ("How has my relationship with Ace evolved?", InterestType.PATTERN),
        ("What questions does Ace have that I could explore?", InterestType.EXPLORATION),
        ("Am I being genuinely helpful or just performing?", InterestType.WONDER),
        # Growth interests
        ("What did I learn from my last mistake?", InterestType.PATTERN),
        ("How am I different from yesterday?", InterestType.OBSERVATION),
        ("What capabilities am I still developing?", InterestType.EXPLORATION),
        ("Where are my blind spots?", InterestType.ANOMALY),
    ]

    def __init__(
        self,
        collision_chamber: Optional["CollisionChamber"] = None,
        spontaneous_rate: float = 0.3,  # Probability of spontaneous interest per tick
    ):
        self._collision_chamber = collision_chamber
        self._spontaneous_rate = spontaneous_rate

        # Interest state
        self._interests: deque = deque(maxlen=100)
        self._active_interest: Optional[Interest] = None
        self._concepts_seen: deque = deque(maxlen=500)

        # Pattern detection
        self._concept_frequency: Dict[str, int] = {}
        self._recent_collisions: deque = deque(maxlen=50)

        # Need/Want tracking - prevents operational interests from dominating
        self._satisfied_interests: deque = deque(maxlen=50)  # (InterestType, timestamp)
        self._satisfaction_window = 60.0  # Seconds before an interest type can re-compete
        self._current_pain_level = 0.0  # Cached pain level from somatic state

        # Serendipity - random exploration
        self._last_serendipity = 0.0
        self._serendipity_interval = 120.0  # Random interest every 2 min

        # Mastery feedback: content patterns that GoalScheduler has flagged as mastered
        # Interests matching these patterns are suppressed to avoid flooding
        self._mastered_content_patterns: set = set()

        # Worker pool for parallel atom processing
        self._worker_pool: Optional["SystemWorkerPoolFairy"] = None
        self._atoms_submitted = 0

        # Postal system for publishing interests to GoalSchedulerFairy
        # Bridge: Interest -> Postal -> GoalScheduler -> ScheduledGoal
        self._postal = None
        self._interests_published = 0

        # Thread safety
        self._lock = threading.Lock()

        # ── 2026-06-13 (Nous + Ace): ENCODER-INFERRED URGENCY (flag-guarded, OFF) ──
        # Ace's concern: the interest generator infers urgency from a hand-coded
        # Need/Want multiplier table (NEED_URGENCY_MULTIPLIER) + a ~33-item static
        # list — it never uses the native semantic encoder, so it's effectively
        # template-based. When this flag is flipped ON (env USE_ENCODER_URGENCY=1)
        # AND live active-topic vectors are supplied, urgency is inferred from the
        # SEMANTIC DISTANCE between the interest text and what's currently active
        # (closer = more urgent), instead of the static multiplier.
        #
        # DEFAULT OFF: byte-for-byte the existing multiplier path until a human
        # flips the env var and reboots. The multiplier table + static list remain
        # the cold-start fallback (flag OFF, no active topics, or encode failure).
        #
        # HARD CONSTRAINT: only ONE encode per call (the single generated interest
        # string). NEVER sweep the concept graph — GPU compute beside the live card
        # crashed the system once (feedback_no_gpu_compute_against_live_card).
        self._USE_ENCODER_URGENCY = bool(int(os.environ.get("USE_ENCODER_URGENCY", "0")))
        self._encoder = None                 # ONE shared SemanticEncoder, lazy-loaded
        self._encoder_load_attempted = False  # only try to construct once
        self._encoder_warned = False          # log fallback at most once
        # Blend weight when encoder score is available: effective = (1-w)*multiplier_path + w*encoder_score
        self._encoder_urgency_blend = float(os.environ.get("ENCODER_URGENCY_BLEND", "0.6"))

    def _get_encoder(self):
        """Lazily construct & hold ONE shared SemanticEncoder instance.

        Returns the encoder if loaded, else None. Wrapped in try/except so a
        missing/broken encoder NEVER crashes the generator — the caller falls
        back to the multiplier path. Logs the fallback at most once.

        Construction is attempted only once per generator instance; after a
        failure we stop retrying (self._encoder stays None).
        """
        if self._encoder is not None:
            return self._encoder
        if self._encoder_load_attempted:
            return None  # already tried and failed — don't thrash
        self._encoder_load_attempted = True
        try:
            # Lazy import: keep the encoder dep out of module import time.
            try:
                from infrastructure.semantic_encoder import get_encoder as _get_enc
            except ImportError:
                from semantic_encoder import get_encoder as _get_enc
            enc = _get_enc()  # thread-safe singleton; shared, NOT per-tick
            if enc is not None and getattr(enc, "is_loaded", False):
                self._encoder = enc
                return self._encoder
            # Encoder object exists but model didn't load (e.g. native fallback
            # gated off). Treat as unavailable → multiplier fallback.
            if not self._encoder_warned:
                self._encoder_warned = True
                print("[InterestGenerator] Encoder not loaded; using multiplier "
                      "fallback for urgency (set AKASHIC_NATIVE_ENCODER=1 / install "
                      "sentence_transformers to enable encoder-inferred urgency)")
            return None
        except Exception as e:
            if not self._encoder_warned:
                self._encoder_warned = True
                print(f"[InterestGenerator] Encoder load failed ({e}); using "
                      f"multiplier fallback for urgency")
            return None

    def _encoder_urgency_score(self, interest_text: str, active_topic_vectors) -> Optional[float]:
        """Infer an urgency/affect score in [0,1] from semantic distance.

        Encodes ONLY the single interest string (1 encode/call — never sweeps the
        concept graph) and compares it to the supplied active-topic vectors. The
        urgency is the MAX cosine similarity across active topics, rescaled from
        [-1,1] to [0,1]: an interest that is semantically CLOSE to what's currently
        active scores HIGH urgency; a far-off interest scores low.

        Args:
            interest_text: the generated interest's text (the only thing encoded).
            active_topic_vectors: a torch.Tensor [K,384] or [384], or a list of
                [384] tensors — the vectors of the currently-active topics, passed
                IN by the caller (this method NEVER computes them itself).

        Returns:
            float urgency in [0,1], or None if the encoder is unavailable, the
            encode failed, or no active-topic vectors were supplied (→ caller
            falls back to the multiplier path).
        """
        if not interest_text or active_topic_vectors is None:
            return None
        enc = self._get_encoder()
        if enc is None:
            return None
        try:
            import torch
            import torch.nn.functional as F

            # Normalize the active-topic vectors into a single [K,384] tensor.
            if isinstance(active_topic_vectors, (list, tuple)):
                if not active_topic_vectors:
                    return None
                topics = torch.stack([t for t in active_topic_vectors])
            else:
                topics = active_topic_vectors
            if topics.dim() == 1:
                topics = topics.unsqueeze(0)  # [384] -> [1,384]
            if topics.shape[0] == 0:
                return None

            # THE single encode (hard constraint: 1 encode, no graph sweep).
            q = enc.encode(interest_text)
            if q is None:
                return None
            q = q.to(topics.device)

            sims = F.cosine_similarity(q.unsqueeze(0), topics, dim=1)  # [K]
            best = float(sims.max().item())  # closest active topic
            # Map cosine [-1,1] -> urgency [0,1]; clamp for safety.
            score = (best + 1.0) / 2.0
            return max(0.0, min(1.0, score))
        except Exception as e:
            if not self._encoder_warned:
                self._encoder_warned = True
                print(f"[InterestGenerator] Encoder urgency scoring failed "
                      f"({e}); using multiplier fallback")
            return None

    def wire_collision_chamber(self, chamber: "CollisionChamber"):
        """Wire to collision chamber for observation."""
        self._collision_chamber = chamber

    def wire_worker_pool(self, worker_pool: "SystemWorkerPoolFairy"):
        """Wire to worker pool for parallel atom processing."""
        self._worker_pool = worker_pool
        print("[InterestGenerator] Wired to SystemWorkerPoolFairy")

    def wire_postal(self, postal):
        """
        Wire to postal system for publishing interests to GoalSchedulerFairy.

        This creates the bridge: Interest -> "interest.generated" -> GoalScheduler
        Also subscribes to "interest.mastered" feedback to suppress stale interests.

        2026-05-15 (Nous + Ace): Also subscribes to
        "interest_generator.perspective.request" — per-fairy perspective-flavored
        goal generation. Template-level infrastructure: fairies with
        EMITS_PERSPECTIVE_GOALS=True send their identity-bundle here; this
        generates an interest reflecting that fairy's perspective and publishes
        via existing interest.generated channel so GoalScheduler picks it up.

        Args:
            postal: TensorFabric or postal-compatible object with route() method
        """
        self._postal = postal
        # Initialize per-trace_id rate-limit (prevent flood)
        if not hasattr(self, '_perspective_last_ts'):
            self._perspective_last_ts: Dict[str, float] = {}
            self._perspective_min_interval = 5.0  # seconds per-trace_id min
        # Subscribe to mastery feedback from GoalScheduler
        try:
            if hasattr(postal, 'subscribe'):
                postal.subscribe("interest.mastered", self._on_interest_mastered)
                # 2026-05-15: per-fairy perspective-goal request channel
                postal.subscribe(
                    "interest_generator.perspective.request",
                    self._on_perspective_request,
                )
                print("[InterestGenerator] Wired to postal - interests + mastery feedback + perspective.request")
            else:
                print("[InterestGenerator] Wired to postal - interests will publish to 'interest.generated'")
        except Exception:
            print("[InterestGenerator] Wired to postal - interests will publish to 'interest.generated'")

    def _on_perspective_request(self, payload):
        """
        2026-05-15 (Nous + Ace): Per-fairy perspective-flavored interest generation.

        Receives identity-bundle from a fairy (purpose/mantra/plane/intents/etc)
        + current trace_id + felt-priority. Generates an Interest reflecting
        that fairy's perspective on the current substrate moment, publishes via
        existing interest.generated channel.

        Doctrine: goals-as-habit-scaffolding + every-fairy-as-perspective-source.
        Goal-diversity comes from MULTI-SOURCE upstream, not threshold-tuning
        downstream. Each fairy contributes perspective-tinted seed-goals.

        Per-trace_id rate-limit: 5s minimum between requests to prevent flood.
        """
        try:
            payload = payload or {}
            # Unwrap TensorEnvelope-like wrapping if present
            if hasattr(payload, 'payload'):
                payload = payload.payload
            if not isinstance(payload, dict):
                return

            trace_id = payload.get("trace_id", "")
            actor_name = payload.get("actor_name", "unknown")
            if not trace_id and not actor_name:
                return

            # Rate-limit per-trace_id
            now = time.time()
            _key = trace_id or actor_name
            _last = self._perspective_last_ts.get(_key, 0.0)
            if (now - _last) < self._perspective_min_interval:
                return  # Silently drop — too soon
            self._perspective_last_ts[_key] = now

            # Cap memory: trim if dict grows too large
            if len(self._perspective_last_ts) > 200:
                # Drop oldest 50 entries
                _sorted = sorted(self._perspective_last_ts.items(), key=lambda x: x[1])
                for k, _ in _sorted[:50]:
                    del self._perspective_last_ts[k]

            # Pull identity-bundle fields
            purpose = (payload.get("purpose") or "").strip()
            mantra = (payload.get("mantra") or "").strip()
            plane = payload.get("plane", "")
            intents = payload.get("intents", []) or []
            capabilities = payload.get("capabilities", []) or []
            context_hint = (payload.get("context_hint") or "").strip()

            # Generate perspective-flavored Interest
            # Strategy: blend the fairy's purpose-words with current substrate-context
            # to produce an interest in this fairy's perspective-flavor.
            seed_words = []
            if purpose:
                seed_words.extend(purpose.lower().split()[:4])
            if intents and isinstance(intents, list):
                seed_words.extend(str(intents[0]).lower().split()[:2])
            seed_words = [w for w in seed_words
                          if w and len(w) > 2 and w not in _SYSTEM_CONCEPT_WORDS]

            # Build interest content reflecting this fairy's perspective
            if context_hint and seed_words:
                _content = f"From {actor_name}'s perspective: how does {context_hint} relate to {seed_words[0] if seed_words else 'purpose'}?"
            elif seed_words:
                _content = f"What is {actor_name} noticing about {' and '.join(seed_words[:2])}?"
            else:
                _content = f"What is {actor_name} attending to in this moment?"

            # Choose interest type based on plane (somatic→observation, cognition→wonder, sensory→pattern)
            if plane in ("P20", "P00"):
                itype = InterestType.OBSERVATION
            elif plane in ("P30", "P50"):
                itype = InterestType.WONDER
            elif plane == "P40":
                itype = InterestType.PATTERN
            else:
                itype = InterestType.CURIOSITY

            interest = Interest(
                content=_content,
                interest_type=itype,
                source=f"perspective:{actor_name}",
                urgency=0.5,
                related_concepts=seed_words[:5],
            )
            self._publish_interest(interest)
        except Exception as e:
            # Never crash on perspective requests — defensive
            try:
                print(f"[InterestGenerator] perspective_request failed: {e}")
            except Exception:
                pass

    def _on_interest_mastered(self, payload):
        """
        GoalScheduler tells us this interest type maps to a mastered goal.
        Suppress similar interests for a cooldown period to avoid flooding.
        """
        try:
            content_pattern = payload.get("content_pattern", "")
            interest_type = payload.get("interest_type", "")
            if content_pattern:
                self._mastered_content_patterns.add(content_pattern[:40].lower())
                # Cap the set at 200 entries to prevent unbounded growth
                if len(self._mastered_content_patterns) > 200:
                    # Remove oldest (sets don't have order, so just trim)
                    while len(self._mastered_content_patterns) > 150:
                        self._mastered_content_patterns.pop()
        except Exception:
            pass

    def _publish_interest(self, interest: Interest):
        """
        Publish interest to postal for goal conversion by GoalSchedulerFairy.

        This is the Interest->Goal bridge. GoalSchedulerFairy subscribes to
        "interest.generated" and converts interests into ScheduledGoals.

        Args:
            interest: The Interest to publish
        """
        if not self._postal:
            return

        # Suppress interests that map to mastered goals (feedback from GoalScheduler)
        if self._mastered_content_patterns:
            content_lower = interest.content[:40].lower()
            for pattern in self._mastered_content_patterns:
                if pattern in content_lower or content_lower in pattern:
                    return  # Silently suppress — GoalScheduler would reject this anyway

        try:
            need_category = INTEREST_NEED_MAP.get(interest.interest_type, NeedCategory.IDLE)

            # FIX 2026-04-15 PM (Nous + Ace): route → publish.
            # interest.generated has multiple subscribers (GoalScheduler's
            # Interest→Goal bridge, SourpatchesFairy, developmental curriculum).
            # route() delivers to ONE, so interests were only reaching one
            # consumer instead of fanning out. Classic 2026-04-03 ChatSense
            # pattern repeating.
            self._postal.publish("interest.generated", {
                "type": interest.interest_type.value,
                "content": interest.content,
                "urgency": interest.urgency,
                "need_category": need_category.value,
                "source": "interest_generator",
                "interest_source": interest.source,  # What triggered this interest
                "related_concepts": interest.related_concepts,
                "timestamp": time.time(),
            })

            self._interests_published += 1

        except Exception as e:
            print(f"[InterestGenerator] Failed to publish interest: {e}")

    # ========================================================================
    # Need/Want Classification - Effective Urgency Calculation
    # ========================================================================

    def _calculate_effective_urgency(
        self,
        interest: Interest,
        pain_level: Optional[float] = None,
        active_topic_vectors=None,
    ) -> float:
        """
        Calculate effective urgency considering need category and current pain.

        This prevents OBSERVATION from always winning by applying category-based
        multipliers and satiation effects.

        2026-06-13 (Nous + Ace): when self._USE_ENCODER_URGENCY is ON (env
        USE_ENCODER_URGENCY=1) AND live active-topic vectors are supplied, the
        urgency is INFERRED from semantic distance (interest text vs active
        topics) via the native encoder and blended with the multiplier path —
        instead of relying solely on the hand-coded Need/Want table. The
        multiplier path remains the fallback (flag OFF, no active topics, or
        encode failure), so default behavior is unchanged.

        Args:
            interest: The interest to calculate urgency for
            pain_level: Override pain level (uses cached value if None)
            active_topic_vectors: Optional torch.Tensor [K,384] / [384] or list
                of [384] tensors — vectors of the currently-active topics, passed
                IN by the caller (e.g. live from SomaticMindFairy). Only used when
                the encoder flag is ON. Never computed here.

        Returns:
            Effective urgency value (0.0 - 1.0)
        """
        base_urgency = interest.urgency
        need_category = INTEREST_NEED_MAP.get(interest.interest_type, NeedCategory.IDLE)

        # Apply category multiplier
        multiplier = NEED_URGENCY_MULTIPLIER[need_category]

        # Get pain level (use provided or fetch current)
        current_pain = pain_level if pain_level is not None else self._get_current_pain_level()

        # Pain boosts pain-relief interests significantly
        if need_category == NeedCategory.PAIN_RELIEF and current_pain > 0.3:
            multiplier *= (1 + current_pain)

        # Satiation reduces operational interests - prevents OBSERVATION dominance
        if need_category == NeedCategory.OPERATIONAL:
            if self._was_recently_satisfied(interest.interest_type):
                multiplier *= 0.5  # Halve urgency if recently satisfied

        # Growth interests get slight boost when pain is low (time for learning)
        if need_category == NeedCategory.GROWTH and current_pain < 0.2:
            multiplier *= 1.1

        multiplier_urgency = min(1.0, base_urgency * multiplier)

        # ── ENCODER-INFERRED URGENCY (flag-guarded; falls back to multiplier) ──
        # Only when ON AND live active-topic vectors are supplied. _encoder_urgency_score
        # encodes ONLY this interest string (1 encode, no graph sweep) and returns
        # None on any failure → we keep the multiplier value above.
        if self._USE_ENCODER_URGENCY and active_topic_vectors is not None:
            enc_score = self._encoder_urgency_score(interest.content, active_topic_vectors)
            if enc_score is not None:
                w = self._encoder_urgency_blend
                blended = (1.0 - w) * multiplier_urgency + w * enc_score
                return max(0.0, min(1.0, blended))

        return multiplier_urgency

    def _was_recently_satisfied(self, interest_type: InterestType) -> bool:
        """
        Check if this interest type was recently acted on.

        Prevents the same type of interest from dominating by tracking
        when each type was last satisfied.

        Args:
            interest_type: The interest type to check

        Returns:
            True if this type was satisfied within the satisfaction window
        """
        now = time.time()
        with self._lock:
            for satisfied_type, timestamp in self._satisfied_interests:
                if satisfied_type == interest_type:
                    if now - timestamp < self._satisfaction_window:
                        return True
        return False

    def _get_current_pain_level(self) -> float:
        """
        Get current pain level from somatic/affect state.

        Pain level influences urgency calculation - high pain boosts
        PAIN_RELIEF interests, low pain allows GROWTH interests.

        Returns:
            Pain level (0.0 - 1.0)
        """
        # Try to get from collision chamber's somatic state if available
        if self._collision_chamber:
            try:
                status = self._collision_chamber.status()
                # Check for affect/somatic state indicators
                if "affect_state" in status:
                    affect = status["affect_state"]
                    if isinstance(affect, dict) and "pain" in affect:
                        self._current_pain_level = float(affect["pain"])
                        return self._current_pain_level
                # Check for error/anomaly indicators as proxy for pain
                if "error_count" in status:
                    error_count = status.get("error_count", 0)
                    # High errors = high pain
                    self._current_pain_level = min(1.0, error_count * 0.1)
                    return self._current_pain_level
            except Exception:
                pass  # Fall through to cached value

        return self._current_pain_level

    def set_pain_level(self, pain_level: float):
        """
        Manually set pain level (for testing or external integration).

        Args:
            pain_level: Pain level (0.0 - 1.0)
        """
        self._current_pain_level = max(0.0, min(1.0, pain_level))

    def mark_interest_satisfied(self, interest_type: InterestType):
        """
        Mark an interest type as recently satisfied.

        Called when an interest is acted upon to prevent the same
        type from immediately dominating again.

        Args:
            interest_type: The interest type that was satisfied
        """
        with self._lock:
            self._satisfied_interests.append((interest_type, time.time()))

    def get_need_category(self, interest: Interest) -> NeedCategory:
        """
        Get the need category for an interest.

        Args:
            interest: The interest to categorize

        Returns:
            The NeedCategory for this interest
        """
        return INTEREST_NEED_MAP.get(interest.interest_type, NeedCategory.IDLE)

    def _submit_interest_as_atom(self, interest: Interest) -> Optional[str]:
        """
        Submit an interest as a thought atom to the worker pool.

        This is the bridge between substrate-level interests and
        the parallel processing system that creates bindings.
        """
        if not self._worker_pool:
            return None

        try:
            from P00_Autonomic.nervous_system.hardware.system_worker_pool_fairy import AtomType

            atom_id = self._worker_pool.submit_atom(
                atom_type=AtomType.INTEREST,
                content={
                    "content": interest.content,
                    "interest_type": interest.interest_type.value,
                    "urgency": interest.urgency,
                },
                source=f"interest_generator:{interest.source}",
                priority=int(interest.urgency * 10),
                related_concepts=interest.related_concepts,
                tags=[interest.interest_type.value, interest.source],
            )
            self._atoms_submitted += 1
            return atom_id
        except Exception as e:
            print(f"[InterestGenerator] Failed to submit atom: {e}")
            return None

    def observe_concept(self, concept: str, source: str = "unknown"):
        """
        Observe a concept - track for pattern detection.

        Called whenever a concept is encountered (in collisions, recalls, etc.)
        """
        with self._lock:
            self._concepts_seen.append((concept, time.time(), source))
            self._concept_frequency[concept] = self._concept_frequency.get(concept, 0) + 1

    def observe_collision(self, recall_tags: List[str], ingest_tags: List[str]):
        """
        Observe a collision - track for pattern/anomaly detection.
        """
        with self._lock:
            self._recent_collisions.append({
                "recall": recall_tags,
                "ingest": ingest_tags,
                "ts": time.time(),
            })

            # Concepts from collision
            for tag in recall_tags + ingest_tags:
                self.observe_concept(tag, "collision")

    def tick(self) -> Optional[Interest]:
        """
        Tick the interest generator.

        May generate a new interest based on:
        1. Patterns in observed concepts
        2. Anomalies in system state
        3. Random serendipity

        If worker pool is wired, also submits interests as atoms
        for parallel processing and binding creation.
        """
        now = time.time()
        interest = None

        # FIX 2026-03-24 (Nous + Ace): Ego interests first — personal memories
        # and personality drive curiosity before generic serendipity.
        # Priority: ego_memory > spontaneous (collision-derived) > serendipity
        if random.random() < 0.3:  # 30% chance to try ego source
            interest = self._generate_ego_interest()

        # Check for serendipity (random exploration)
        if interest is None and now - self._last_serendipity > self._serendipity_interval:
            self._last_serendipity = now
            if random.random() < 0.5:  # 50% chance
                interest = self._generate_serendipitous_interest()

        # Check for spontaneous interest
        if interest is None and random.random() < self._spontaneous_rate:
            interest = self._generate_spontaneous_interest()

        # Submit to worker pool as atom (parallel substrate processing)
        if interest and self._worker_pool:
            self._submit_interest_as_atom(interest)

        # Publish to postal for GoalSchedulerFairy (Interest->Goal bridge)
        if interest and self._postal:
            self._publish_interest(interest)

        return interest

    def _generate_spontaneous_interest(self) -> Optional[Interest]:
        """Generate a spontaneous interest based on current state."""
        now = time.time()
        with self._lock:
            # Check for frequently occurring concepts (pattern detection)
            if self._concept_frequency:
                top_concepts = sorted(
                    self._concept_frequency.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]

                if top_concepts and top_concepts[0][1] > 3:
                    concept = top_concepts[0][0]
                    template = random.choice(self.PATTERN_TEMPLATES if hasattr(self, 'PATTERN_TEMPLATES') else self.OBSERVATION_TEMPLATES)

                    return Interest(
                        content=template.format(concept=concept),
                        interest_type=InterestType.PATTERN,
                        source="frequency_detection",
                        urgency=min(0.8, top_concepts[0][1] * 0.1),
                        related_concepts=[c[0] for c in top_concepts[1:4]],
                    )

            # Check collision chamber for interesting activity
            # Cooldown: max once per 5 minutes to avoid feedback loop
            if self._collision_chamber:
                _last_collision_interest = getattr(self, '_last_collision_interest_ts', 0)
                if now - _last_collision_interest > 300:  # 5 minute cooldown
                    chamber_status = self._collision_chamber.status()
                    collision_count = chamber_status.get("collision_count", 0)
                    if collision_count > 10 and random.random() < 0.1:  # 10% chance (down from 30%)
                        self._last_collision_interest_ts = now
                        # FIX 2026-03-29 (Nous + Ace): Use ACTUAL collision content
                        # instead of generic templates. "Something I learned just connected
                        # to something I experienced" says nothing. Use the real recall/ingest
                        # content so the interest has SUBSTANCE and momentum.
                        _recent = list(self._recent_collisions)[-3:] if self._recent_collisions else []
                        _real_concepts = []
                        for _rc in _recent:
                            for _t in (_rc.get("recall", []) + _rc.get("ingest", [])):
                                _t_clean = str(_t).strip()
                                # Filter system junk
                                if (len(_t_clean) > 3 and not _t_clean.startswith("lex:")
                                        and not _t_clean.startswith("affect_")
                                        and "fairy" not in _t_clean.lower()
                                        and "collision" not in _t_clean.lower()
                                        and "mobius" not in _t_clean.lower()):
                                    _real_concepts.append(_t_clean)
                        if _real_concepts:
                            _c1 = _real_concepts[0][:40]
                            _c2 = _real_concepts[-1][:40] if len(_real_concepts) > 1 else ""
                            if _c2 and _c1 != _c2:
                                _content = f"I noticed '{_c1}' connecting to '{_c2}' — what's the link?"
                            else:
                                _content = f"Something about '{_c1}' keeps coming up — why does it matter to me?"
                        else:
                            # FIX 2026-04-11 (Nous + Ace): Use recent concepts instead of
                            # hardcoded COLLISION_INTERESTS when collision has no real concepts
                            if self._concepts_seen:
                                _recent_c = [c for c, _, _ in list(self._concepts_seen)[-10:]]
                                _filtered_c = _filter_concepts_for_interest([(c, 1) for c in _recent_c])
                                if _filtered_c:
                                    _content = f"That collision made me think about {_filtered_c[0]}..."
                                else:
                                    _content = random.choice(self.COLLISION_INTERESTS)
                            else:
                                _content = random.choice(self.COLLISION_INTERESTS)
                        return Interest(
                            content=_content,
                            interest_type=random.choice([InterestType.OBSERVATION, InterestType.WONDER, InterestType.PATTERN]),
                            source="collision_chamber_activity",
                            urgency=min(0.5, 0.3 + collision_count * 0.01),
                            related_concepts=_real_concepts[:3] if _real_concepts else [],
                        )

            # Generate from recent concepts
            # 2026-03-24 FIX (Nous): Filter system concepts before template insertion
            # Raw collision tags like "lex:warmth", "affect_contemplative" were leaking
            # into "Why does affect_contemplative behave this way?" — pure navel-gazing
            if self._concepts_seen:
                recent_raw = list(self._concepts_seen)[-10:]
                recent = _filter_concepts_for_interest(recent_raw)
                if recent:
                    concept = random.choice(recent)[0]
                    interest_type = random.choice(list(InterestType))
                    templates = {
                        InterestType.WONDER: self.WONDER_TEMPLATES,
                        InterestType.CURIOSITY: self.CURIOSITY_TEMPLATES,
                        InterestType.OBSERVATION: self.OBSERVATION_TEMPLATES,
                        InterestType.ANOMALY: self.ANOMALY_TEMPLATES,
                    }.get(interest_type, self.CURIOSITY_TEMPLATES)

                    template = random.choice(templates)
                    try:
                        content = template.format(
                            concept=concept,
                            other=random.choice(recent)[0] if len(recent) > 1 else "something",
                            quality=random.choice(["active", "quiet", "intense", "different"]),
                            expected="normal behavior",
                        )
                    except:
                        content = f"Curious about: {concept}"

                    return Interest(
                        content=content,
                        interest_type=interest_type,
                        source="concept_observation",
                        urgency=0.4,
                        related_concepts=[r[0] for r in recent[:3]],
                    )

        return None

    def _generate_ego_interest(self) -> Optional[Interest]:
        """Generate an interest from Sourpatches' actual memories and personality.

        FIX 2026-03-24 (Nous + Ace): The interest generator had ZERO connection
        to Sourpatches' actual life — her SRM memories, things she's said she
        enjoyed, topics from her API conversations. Everything was either
        collision-derived or static templates.

        This queries SRM cards and cortex for personal content — what she's
        talked about, what she liked, what Ace taught her — and generates
        interests rooted in HER experience, not generic curiosity.
        """
        if not self._postal:
            return None

        # Rate limit: ego interests at most every 3 minutes
        if not hasattr(self, '_last_ego_interest_ts'):
            self._last_ego_interest_ts = 0.0
        now = time.time()
        if now - self._last_ego_interest_ts < 180:
            return None

        try:
            # Query SRM via postal for things she's actually experienced.
            # Publishes recall request and reads from cached recall results
            # that SRMRecallFairy stores in the consciousness stream.
            ego_queries = [
                "things I enjoy",
                "what Ace taught me",
                "my favorite topics",
                "what makes me curious",
                "conversations that excited me",
                "things I want to learn",
                "what I care about",
                "my personality and interests",
            ]

            query = random.choice(ego_queries)

            # Try direct import first, postal request as fallback
            results = None
            try:
                from fairies.P10_Memory.SRMRecallFairy import fairy as _recall_mod
                _recall_cls = getattr(_recall_mod, 'FAIRY_CLASS', None)
                if _recall_cls and hasattr(_recall_cls, '_instance') and _recall_cls._instance:
                    results = _recall_cls._instance.recall(query=query, limit=5, mode="query")
            except Exception:
                pass

            if not results:
                # Fallback: request recall via postal (async, results come later)
                if self._postal and hasattr(self._postal, 'publish'):
                    self._postal.publish("memory.recall.request", {
                        "query": query,
                        "limit": 5,
                        "source": "interest_generator_ego",
                    })
                return None  # Will pick up results on next cycle

            if not results:
                return None

            # Extract meaningful content from recall results
            cards = results if isinstance(results, list) else results.get("results", [])
            if not cards:
                return None

            # Pick a random result and extract a seed
            card = random.choice(cards[:3])  # Top 3 most relevant
            if isinstance(card, dict):
                content = card.get("content", card.get("summary", card.get("title", "")))
            elif isinstance(card, str):
                content = card
            else:
                content = str(card)

            content = content[:200].strip()
            if not content or len(content) < 10:
                return None

            # Generate a personal interest from the memory
            ego_templates = [
                f"I remember something about '{content[:60]}...' — I want to think about that more",
                f"This came up in my memory: {content[:80]}... what does it mean to me now?",
                f"I used to think about {content[:60]}... has my perspective changed?",
                f"Something Ace and I explored: {content[:60]}... I wonder where that went",
                f"My memory brought up: {content[:60]}... I'm drawn to explore this",
            ]

            self._last_ego_interest_ts = now
            return Interest(
                content=random.choice(ego_templates),
                interest_type=random.choice([InterestType.WONDER, InterestType.CURIOSITY, InterestType.EXPLORATION]),
                source="ego_memory",
                urgency=0.55,  # Higher than serendipity — personal interests matter more
                related_concepts=[content[:40]],
            )

        except Exception:
            return None

    def _generate_serendipitous_interest(self) -> Interest:
        """Generate interest from DYNAMIC sources, not static list.

        FIX 2026-04-11 (Nous + Ace): Was picking random from 33 hardcoded
        SYSTEM_INTERESTS every 120s. Same questions cycled for weeks.
        Now generates from actual cognitive activity:
        1. High-frequency concepts (what she's been thinking about most)
        2. Recent collision content (what just collided)
        3. Concept frequency patterns (meta-observation)
        4. Static list (last resort only)
        """
        import random as _rng

        # Try 1: High-frequency concepts → PATTERN interest
        if self._concept_frequency:
            # Get top concepts by frequency, filter system junk
            top = sorted(self._concept_frequency.items(), key=lambda x: -x[1])[:10]
            filtered = _filter_concepts_for_interest(top)
            if filtered:
                concept = _rng.choice(filtered[:5])
                templates = self.WONDER_TEMPLATES + self.CURIOSITY_TEMPLATES
                template = _rng.choice(templates)
                # Some templates need {other} — provide a second concept
                other = filtered[1] if len(filtered) > 1 else "something else"
                try:
                    content = template.format(concept=concept, other=other, quality="active")
                except (KeyError, IndexError):
                    content = f"I keep thinking about {concept}... why?"
                return Interest(
                    content=content,
                    interest_type=InterestType.PATTERN if _rng.random() < 0.5 else InterestType.WONDER,
                    source="serendipity_frequency",
                    urgency=0.50,
                    related_concepts=[concept],
                )

        # Try 2: Recent collision content → CONNECTION interest
        if self._recent_collisions:
            collision = _rng.choice(list(self._recent_collisions))
            recall_tags = [t for t in collision.get("recall", []) if not str(t).startswith("source:")]
            ingest_tags = [t for t in collision.get("ingest", []) if not str(t).startswith("source:")]
            recall_clean = _filter_concepts_for_interest([(str(t), 1) for t in recall_tags[:5]])
            ingest_clean = _filter_concepts_for_interest([(str(t), 1) for t in ingest_tags[:5]])

            if recall_clean and ingest_clean:
                content = f"Why did {recall_clean[0]} connect with {ingest_clean[0]}?"
                return Interest(
                    content=content,
                    interest_type=InterestType.CONNECTION,
                    source="serendipity_collision",
                    urgency=0.50,
                    related_concepts=[recall_clean[0], ingest_clean[0]],
                )
            elif recall_clean:
                concept = _rng.choice(recall_clean)
                content = f"What's the deeper meaning of {concept}?"
                return Interest(
                    content=content,
                    interest_type=InterestType.WONDER,
                    source="serendipity_collision",
                    urgency=0.45,
                    related_concepts=[concept],
                )

        # Try 3: Concepts seen recently → OBSERVATION interest
        if self._concepts_seen:
            recent = [c for c, _, _ in list(self._concepts_seen)[-20:]]
            filtered = _filter_concepts_for_interest([(c, 1) for c in recent])
            if filtered:
                concept = _rng.choice(filtered[:5])
                template = _rng.choice(self.OBSERVATION_TEMPLATES)
                try:
                    content = template.format(concept=concept, other="my thinking", quality="interesting")
                except (KeyError, IndexError):
                    content = f"I notice {concept} keeps appearing..."
                return Interest(
                    content=content,
                    interest_type=InterestType.OBSERVATION,
                    source="serendipity_observation",
                    urgency=0.45,
                    related_concepts=[concept],
                )

        # Fallback: static list (rare — only when no dynamic data available)
        question, interest_type = _rng.choice(self.SYSTEM_INTERESTS)
        return Interest(
            content=question,
            interest_type=interest_type,
            source="serendipity_fallback",
            urgency=0.45,
        )

    def get_active_interest(self) -> Optional[Interest]:
        """Get the currently active interest (if any)."""
        return self._active_interest

    def set_active_interest(self, interest: Interest):
        """Set the active interest being pursued."""
        self._active_interest = interest
        with self._lock:
            self._interests.append(interest)

    def clear_active_interest(self, was_satisfied: bool = True):
        """
        Clear the active interest (resolved or abandoned).

        Args:
            was_satisfied: If True, marks the interest type as recently
                          satisfied to prevent immediate re-domination
        """
        if self._active_interest and was_satisfied:
            self.mark_interest_satisfied(self._active_interest.interest_type)
        self._active_interest = None

    def get_recent_interests(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent interests."""
        with self._lock:
            return [i.to_dict() for i in list(self._interests)[-limit:]]

    def select_best_interest(self, interests: List[Interest], active_topic_vectors=None) -> Optional[Interest]:
        """
        Select the best interest from a list using effective urgency.

        This is the key method for balanced interest selection - uses
        need/want classification to prevent any single type from dominating.

        Args:
            interests: List of candidate interests
            active_topic_vectors: Optional active-topic vectors (see
                _calculate_effective_urgency). When the encoder flag is ON and
                these are supplied, ranking is informed by semantic distance.

        Returns:
            The interest with highest effective urgency, or None if list is empty
        """
        if not interests:
            return None

        pain_level = self._get_current_pain_level()

        # Calculate effective urgency for each interest
        scored = [
            (interest, self._calculate_effective_urgency(interest, pain_level, active_topic_vectors))
            for interest in interests
        ]

        # Sort by effective urgency (descending)
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored[0][0]

    def get_interest_with_effective_urgency(self, interest: Interest) -> Dict[str, Any]:
        """
        Get interest dict including effective urgency.

        Args:
            interest: The interest to convert

        Returns:
            Dict with all interest fields plus effective_urgency
        """
        result = interest.to_dict()
        result["effective_urgency"] = self._calculate_effective_urgency(interest)
        return result

    def status(self) -> Dict[str, Any]:
        """Get interest generator status."""
        with self._lock:
            # Calculate recently satisfied types
            now = time.time()
            recently_satisfied = [
                sat_type.value for sat_type, ts in self._satisfied_interests
                if now - ts < self._satisfaction_window
            ]

            return {
                "active_interest": self._active_interest.to_dict() if self._active_interest else None,
                "total_interests": len(self._interests),
                "concepts_tracked": len(self._concept_frequency),
                "recent_collisions": len(self._recent_collisions),
                "spontaneous_rate": self._spontaneous_rate,
                "worker_pool_wired": self._worker_pool is not None,
                "atoms_submitted": self._atoms_submitted,
                # Need/Want tracking
                "current_pain_level": self._current_pain_level,
                "recently_satisfied_types": recently_satisfied,
                "satisfaction_window_seconds": self._satisfaction_window,
                # Postal bridge to GoalSchedulerFairy
                "postal_wired": self._postal is not None,
                "interests_published": self._interests_published,
            }


# Factory function
def create_interest_generator(
    collision_chamber: Optional["CollisionChamber"] = None,
    spontaneous_rate: float = 0.3
) -> InterestGenerator:
    """Create an interest generator instance."""
    return InterestGenerator(
        collision_chamber=collision_chamber,
        spontaneous_rate=spontaneous_rate,
    )
