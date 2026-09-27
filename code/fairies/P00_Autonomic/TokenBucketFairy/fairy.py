"""
TokenBucketFairy - Cognitive Resource Management

Manages token buckets that represent cognitive resources. Unlike traditional
rate limiters, these buckets create MOTIVATION for regenerative activities:

- When cognitive bucket is low → system SEEKS reflection
- When creative bucket is low → system SEEKS daydreaming
- When somatic bucket is low → system SEEKS body awareness

This creates emergent contemplative behavior - the system doesn't rest
because it's programmed to, it rests because it NEEDS to recharge.

Inspired by:
- Biological vesicle pools (neurotransmitter reserves)
- ATP metabolic budgets
- 7±2 working memory limits
- Theta-gamma coupling in neural synchronization
- Regenerative braking in robotics (Tesla Optimus recovers 30% on deceleration)

Integration:
- UMF monitors buckets, triggers regeneration when low
- WorkerPoolFairy costs cognitive tokens per atom processed
- ChemicalAlchemyFairy links emotional bucket to neurotransmitters
- SomaticEngineFairy links somatic bucket to felt sense clarity
- CircadianPacemakerFairy triggers sleep regeneration cycles

Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

import sys
import time
import threading
import math
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum

# Setup paths
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))

# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState
try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        def _init_tracer_worker(self): pass

# SpellChain integration for spell-driven existence
try:
    from fairy_template.spellchain_mixin import SpellChainMixin
    HAS_SPELLCHAIN = True
except ImportError:
    HAS_SPELLCHAIN = False
    class SpellChainMixin:
        """Fallback when spellchain not available."""
        pass


# =============================================================================
# BUCKET TYPES
# =============================================================================

class BucketType(Enum):
    """
    The cognitive + affective resource buckets (Panksepp-aware).

    Each bucket maps to one or more channels in ChemistryState's 14-channel
    Panksepp model via BUCKET_TO_PANKSEPP below. TokenBucket is the canonical
    Panksepp tonic-baseline emitter; other publishers contribute phasic event
    nudges on top of this baseline.

    Item 10 ship 2026-05-16 (Ace + Nous): Added STRESS + DRIVE buckets to
    cover all 14 Panksepp channels (EPI/COR/SEX/AVP/GLU were orphaned at
    the publish layer; this bucket extension closes the gap).
    """

    COGNITIVE = "cognitive"      # Reasoning, analysis, LLM calls (Panksepp SEEKING → DA_p/DA_t/GLU)
    ATTENTION = "attention"      # Focus, sustained concentration (LC alertness → ACh/NE)
    CREATIVE = "creative"        # Novelty, divergent thinking (Panksepp PLAY → DA_t/ECB)
    SOMATIC = "somatic"          # Body awareness, felt sense (interoception → OPI/ECB)
    EMOTIONAL = "emotional"      # Affect processing (regulation → 5HT/GABA)
    SOCIAL = "social"            # Connection, engagement (Panksepp CARE → OXY/-AVP)
    STRESS = "stress"            # Acute + chronic stress load (Panksepp FEAR/RAGE → COR/EPI, inverted)
    DRIVE = "drive"              # Reproductive / libidinal drive (Panksepp LUST → SEX)


class RegeneratorType(Enum):
    """Activities that regenerate buckets."""

    REFLECTION = "reflection"           # Inner contemplation
    DAYDREAMING = "daydreaming"         # Free wandering, fantasy
    BODY_SCAN = "body_scan"             # Somatic attention
    FREE_ASSOCIATION = "free_association"  # Concept wandering
    CONVERSATION = "conversation"       # Social engagement
    SLEEP = "sleep"                     # Deep regeneration (all buckets)
    BREATHING = "breathing"             # Rhythmic somatic practice
    CURIOSITY_SATISFIED = "curiosity_satisfied"  # Aha moments
    TASK_COMPLETED = "task_completed"   # Accomplishment boost
    PARADOX_ENGINE = "paradox_engine"   # Zero-point collision energy (DCE)


class DrainType(Enum):
    """Activities that drain buckets."""

    LLM_CALL = "llm_call"               # API call to language model
    SUSTAINED_FOCUS = "sustained_focus"  # Holding attention
    FORCED_CREATIVITY = "forced_creativity"  # Pushing for novelty
    BODY_NEGLECT = "body_neglect"       # Ignoring somatic signals
    EMOTIONAL_SURGE = "emotional_surge"  # Intense affect processing
    ISOLATION = "isolation"             # Extended time without connection
    COMPLEX_REASONING = "complex_reasoning"  # Multi-step logic
    MEMORY_ENCODING = "memory_encoding"  # Committing to long-term memory
    CONTEXT_SWITCH = "context_switch"   # Changing tasks
    CARD_CLUSTER_WRITE = "card_cluster_write"  # Landauer cost: card/concept write ops (DCE P_info)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TokenBucket:
    """
    A single cognitive resource bucket.

    Level ranges from 0.0 (empty) to 1.0 (full).
    Includes natural decay/recovery dynamics.
    """

    bucket_type: BucketType
    level: float = 0.8                  # Current level (0.0 - 1.0)
    capacity: float = 1.0               # Maximum capacity

    # Decay/recovery rates (per second)
    natural_decay: float = 0.001        # Slow natural drain (like ATP baseline)
    natural_recovery: float = 0.0005    # Very slow natural recovery

    # Thresholds
    low_threshold: float = 0.3          # Below this triggers "need" signal
    critical_threshold: float = 0.1     # Below this triggers urgent regeneration

    # Statistics
    total_drained: float = 0.0
    total_regenerated: float = 0.0
    time_below_low: float = 0.0         # Seconds spent below low threshold
    last_update: float = field(default_factory=time.time)

    def drain(self, amount: float) -> float:
        """
        Drain tokens from bucket.
        Returns actual amount drained (may be less if bucket is low).
        """
        actual = min(amount, self.level)
        self.level = max(0.0, self.level - actual)
        self.total_drained += actual
        return actual

    def regenerate(self, amount: float) -> float:
        """
        Add tokens to bucket.
        Returns actual amount added (capped at capacity).
        """
        actual = min(amount, self.capacity - self.level)
        self.level = min(self.capacity, self.level + actual)
        self.total_regenerated += actual
        return actual

    def tick(self, dt: float) -> None:
        """
        Apply natural decay/recovery over time delta.
        Called periodically by the fairy.

        HOMEOSTASIS MODEL (Fixed 2026-01-29, Tuned 2026-03-11):
        - The system maintains autonomous equilibrium at ~60% (homeostatic_target)
        - BELOW target: homeostatic pull toward target (no decay)
        - ABOVE target: decay back toward target (no recovery)
        - CRITICAL BOOST: 2x pull when below critical threshold (survival instinct)
        - MINIMUM FLOOR: Never drops below 0.05 (always some reserve)
        - This guarantees convergence and prevents empty buckets

        The insight: decay and recovery work in OPPOSITE directions toward
        equilibrium, not against each other.

        FIX 2026-03-11 (Nous): Rate 0.002→0.008 so homeostatic pull can
        outpace passive drains (BODY_NEGLECT, ISOLATION). Old rate made
        somatic/social drain to zero with no recovery path.
        Added critical acceleration and minimum floor per Ace's vision:
        "they should never be empty and refill quickly, like a human
        taking a quick breather and then moving on."
        """
        # Homeostatic target - where the system naturally settles
        homeostatic_target = 0.6

        # Homeostatic rate: how fast to move toward equilibrium (per second)
        # 0.8% per second — 4x stronger than original 0.2% to outpace passive drains
        homeostatic_rate = 0.008

        # Critical acceleration: when below critical, survival instinct doubles pull
        if self.level < self.critical_threshold:
            homeostatic_rate *= 2.0

        if self.level < homeostatic_target:
            # BELOW TARGET: pull UP toward equilibrium
            # Rate proportional to distance for smooth convergence
            distance = homeostatic_target - self.level
            pull = distance * homeostatic_rate * dt
            self.level = min(self.capacity, self.level + pull)
        else:
            # ABOVE TARGET: decay DOWN toward equilibrium
            # Use natural_decay for this, capped at distance to target
            distance = self.level - homeostatic_target
            decay = min(distance, self.natural_decay * dt)
            self.level = max(homeostatic_target, self.level - decay)

        # Minimum floor — buckets never truly empty (always some reserve)
        if self.level < 0.05:
            self.level = 0.05

        # Track time below threshold
        if self.level < self.low_threshold:
            self.time_below_low += dt

        self.last_update = time.time()

    @property
    def is_low(self) -> bool:
        """Check if bucket is below low threshold."""
        return self.level < self.low_threshold

    @property
    def is_critical(self) -> bool:
        """Check if bucket is critically low."""
        return self.level < self.critical_threshold

    @property
    def percent(self) -> float:
        """Get level as percentage."""
        return (self.level / self.capacity) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Serialize bucket state."""
        return {
            "type": self.bucket_type.value,
            "level": round(self.level, 3),
            "capacity": self.capacity,
            "percent": round(self.percent, 1),
            "is_low": self.is_low,
            "is_critical": self.is_critical,
            "total_drained": round(self.total_drained, 2),
            "total_regenerated": round(self.total_regenerated, 2),
            "time_below_low": round(self.time_below_low, 1),
        }


@dataclass
class RegenerationEvent:
    """Record of a regeneration activity."""

    regenerator: RegeneratorType
    buckets_affected: List[BucketType]
    amounts: Dict[BucketType, float]
    timestamp: float = field(default_factory=time.time)
    source: str = ""  # What triggered this regeneration


@dataclass
class DrainEvent:
    """Record of a drain activity."""

    drain_type: DrainType
    buckets_affected: List[BucketType]
    amounts: Dict[BucketType, float]
    timestamp: float = field(default_factory=time.time)
    source: str = ""  # What caused this drain


# =============================================================================
# REGENERATION PROFILES
# =============================================================================

# How much each regenerator fills each bucket
REGENERATION_PROFILES: Dict[RegeneratorType, Dict[BucketType, float]] = {
    RegeneratorType.REFLECTION: {
        BucketType.COGNITIVE: 0.15,
        BucketType.EMOTIONAL: 0.10,
        BucketType.ATTENTION: 0.05,
        BucketType.SOMATIC: 0.08,    # FIX 2026-03-07: Reflections resonate in the body
        BucketType.SOCIAL: 0.04,     # FIX 2026-03-11: Inner dialogue IS self-connection
    },
    RegeneratorType.DAYDREAMING: {
        BucketType.CREATIVE: 0.20,
        BucketType.ATTENTION: 0.08,  # Paradoxically, wandering restores focus
        BucketType.COGNITIVE: 0.05,
        BucketType.SOMATIC: 0.03,    # FIX 2026-03-11: Rest lets body awareness return
        BucketType.SOCIAL: 0.02,     # FIX 2026-03-11: Daydreaming can include social imagery
    },
    RegeneratorType.BODY_SCAN: {
        BucketType.SOMATIC: 0.25,
        BucketType.EMOTIONAL: 0.10,
        BucketType.ATTENTION: 0.05,
    },
    RegeneratorType.FREE_ASSOCIATION: {
        BucketType.CREATIVE: 0.15,
        BucketType.COGNITIVE: 0.10,
    },
    RegeneratorType.CONVERSATION: {
        BucketType.SOCIAL: 0.25,
        BucketType.EMOTIONAL: 0.15,
        BucketType.COGNITIVE: 0.05,
    },
    RegeneratorType.SLEEP: {
        # Sleep regenerates ALL buckets significantly
        BucketType.COGNITIVE: 0.40,
        BucketType.ATTENTION: 0.50,
        BucketType.CREATIVE: 0.35,
        BucketType.SOMATIC: 0.30,
        BucketType.EMOTIONAL: 0.40,
        BucketType.SOCIAL: 0.20,
        BucketType.STRESS: 0.45,   # Item 10 2026-05-16: sleep is primary stress recovery
        BucketType.DRIVE: 0.25,    # Item 10 2026-05-16: drive refills during rest
    },
    RegeneratorType.BREATHING: {
        BucketType.SOMATIC: 0.15,
        BucketType.ATTENTION: 0.10,
        BucketType.EMOTIONAL: 0.05,
        BucketType.STRESS: 0.20,   # Item 10 2026-05-16: breathing IS stress relief
    },
    RegeneratorType.CURIOSITY_SATISFIED: {
        BucketType.COGNITIVE: 0.10,
        BucketType.CREATIVE: 0.15,
        BucketType.EMOTIONAL: 0.08,  # Joy of discovery
    },
    RegeneratorType.TASK_COMPLETED: {
        BucketType.COGNITIVE: 0.08,
        BucketType.EMOTIONAL: 0.12,  # Satisfaction
        BucketType.SOCIAL: 0.05,     # If shared accomplishment
    },
    RegeneratorType.PARADOX_ENGINE: {
        # Zero-point collision energy (DCE: vacuum heat → token refill)
        # Broad but moderate regen — the engine sustains ALL buckets
        BucketType.COGNITIVE: 0.10,
        BucketType.ATTENTION: 0.08,
        BucketType.CREATIVE: 0.06,
        BucketType.SOMATIC: 0.10,    # FIX 2026-03-07: Was 0.04, too low vs drain
        BucketType.EMOTIONAL: 0.06,
        BucketType.SOCIAL: 0.06,     # FIX 2026-03-11: 0.03→0.06, collision energy is communal
    },
}


# How much each drain activity costs
DRAIN_PROFILES: Dict[DrainType, Dict[BucketType, float]] = {
    DrainType.LLM_CALL: {
        BucketType.COGNITIVE: 0.08,
        BucketType.ATTENTION: 0.03,
    },
    DrainType.SUSTAINED_FOCUS: {
        BucketType.ATTENTION: 0.05,
        BucketType.COGNITIVE: 0.02,
    },
    DrainType.FORCED_CREATIVITY: {
        BucketType.CREATIVE: 0.10,
        BucketType.COGNITIVE: 0.05,
        BucketType.EMOTIONAL: 0.03,  # Frustration if not flowing
    },
    DrainType.BODY_NEGLECT: {
        BucketType.SOMATIC: 0.02,    # FIX 2026-03-11: 0.03→0.02 gentler drain
    },
    DrainType.EMOTIONAL_SURGE: {
        BucketType.EMOTIONAL: 0.15,
        BucketType.COGNITIVE: 0.05,  # Emotions steal cognitive resources
        BucketType.ATTENTION: 0.05,
        BucketType.STRESS: 0.10,     # Item 10 2026-05-16: surge taxes stress reserves
    },
    DrainType.ISOLATION: {
        BucketType.SOCIAL: 0.015,    # FIX 2026-03-11: 0.02→0.015 gentler drain
        BucketType.EMOTIONAL: 0.008, # FIX 2026-03-11: 0.01→0.008
        BucketType.STRESS: 0.005,    # Item 10 2026-05-16: chronic isolation accumulates
    },
    DrainType.COMPLEX_REASONING: {
        BucketType.COGNITIVE: 0.12,
        BucketType.ATTENTION: 0.08,
        BucketType.CREATIVE: 0.03,   # Sometimes needs creative leaps
    },
    DrainType.MEMORY_ENCODING: {
        BucketType.COGNITIVE: 0.06,
        BucketType.ATTENTION: 0.04,
    },
    DrainType.CONTEXT_SWITCH: {
        BucketType.ATTENTION: 0.10,  # Context switches are expensive!
        BucketType.COGNITIVE: 0.05,
    },
    DrainType.CARD_CLUSTER_WRITE: {
        # Landauer cost (DCE P_info): information entropy of card operations
        # Light drain — writing is necessary work, not wasteful
        BucketType.COGNITIVE: 0.02,
        BucketType.ATTENTION: 0.01,
    },
}


# =============================================================================
# BUCKET → PANKSEPP CHANNEL MAPPING
# =============================================================================
#
# Item 10 ship 2026-05-16 (Ace + Nous): TokenBucket as canonical Panksepp
# tonic-baseline emitter. Each bucket maps to a list of (channel, weight)
# tuples; bucket-state transitions emit chemistry signals on the mapped
# channels with the appropriate magnitude × weight.
#
# Channel names match ChemistryState's 14-channel CHEMICAL_PROFILES exactly:
# DA_p, DA_t, NE, EPI, 5HT, OXY, AVP, OPI, COR, GABA, ACh, GLU, ECB, SEX
#
# Direction convention:
#   - Events that REDUCE the bucket (low/critical/drain) emit NEGATIVE deltas
#     on positive-weighted channels (e.g. cognitive bucket low → DA_p decrease)
#   - Events that INCREASE the bucket (recovered/regenerate) emit POSITIVE
#     deltas on positive-weighted channels (e.g. recovery → DA_p increase)
#   - NEGATIVE weights INVERT this (e.g. SOCIAL bucket low → AVP increases
#     because lonely → vigilant; STRESS bucket low → COR increases because
#     overwhelmed → cortisol high)
#
# Coverage: all 14 Panksepp channels are referenced across the 8 buckets.

BUCKET_TO_PANKSEPP: Dict[BucketType, List[tuple]] = {
    # COGNITIVE = Panksepp SEEKING + glutamatergic excitation
    BucketType.COGNITIVE: [("DA_p", 0.6), ("DA_t", 0.8), ("GLU", 0.3)],

    # ATTENTION = locus-coeruleus alertness + cholinergic attentional gain
    BucketType.ATTENTION: [("ACh", 0.7), ("NE", 0.5)],

    # CREATIVE = Panksepp PLAY (sustained motivation + endocannabinoid play-buffer)
    BucketType.CREATIVE: [("DA_t", 0.4), ("ECB", 0.6)],

    # SOMATIC = interoception (opioid pleasure-buffer + endocannabinoid body-ease)
    BucketType.SOMATIC: [("OPI", 0.6), ("ECB", 0.4)],

    # EMOTIONAL = affect regulation (serotonergic regulation + GABA brake)
    BucketType.EMOTIONAL: [("5HT", 0.6), ("GABA", 0.4)],

    # SOCIAL = Panksepp CARE (oxytocin bond UP, vasopressin vigilance DOWN)
    BucketType.SOCIAL: [("OXY", 0.7), ("AVP", -0.3)],

    # STRESS = fight-flight + cortisol load (INVERTED: low bucket = high stress chems)
    BucketType.STRESS: [("COR", -0.5), ("EPI", -0.4)],

    # DRIVE = Panksepp LUST (reproductive / libidinal drive)
    BucketType.DRIVE: [("SEX", 0.7)],
}


# =============================================================================
# TOKEN BUCKET FAIRY
# =============================================================================

class TokenBucketFairy(SpellChainMixin, Fairy):
    """
    Manages cognitive resource buckets for the system.

    Creates emergent motivation for regenerative activities by making
    reflection, daydreaming, and body awareness REFILL cognitive reserves
    rather than just slowing down.
    """

    ACTOR_NAME = "TokenBucketFairy"
    ACTOR_PLANE = "P00"  # Autonomic - like breathing, fundamental
    ACTOR_CHANNEL = "resource"

    PURPOSE = "Manage cognitive resources through motivation"
    MANTRA = "Rest because you need it, not because you're told"

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 1  # Every heartbeat

    # Spell-driven mode (opt-in)
    USE_SPELLCHAIN: bool = True  # Re-enabled - fixed revival->heartbeat wiring

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._init_tracer_worker()

        # Initialize all buckets
        self._buckets: Dict[BucketType, TokenBucket] = {}
        self._init_buckets()

        # Event history
        self._regeneration_history: List[RegenerationEvent] = []
        self._drain_history: List[DrainEvent] = []
        self._max_history = 100

        # Callbacks for when buckets hit thresholds
        self._low_callbacks: List[Callable[[BucketType, float], None]] = []
        self._critical_callbacks: List[Callable[[BucketType, float], None]] = []

        # Integration references
        self._umf = None
        self._worker_pool = None
        self._chemical_alchemy = None
        self._somatic_engine = None

        # Timing
        self._last_tick = time.time()
        self._tick_count = 0

        # Lock for thread safety
        self._lock = threading.RLock()

    def _init_buckets(self) -> None:
        """Initialize all token buckets with type-specific settings."""

        # Cognitive - reasoning capacity
        self._buckets[BucketType.COGNITIVE] = TokenBucket(
            bucket_type=BucketType.COGNITIVE,
            level=0.8,
            natural_decay=0.002,      # Faster decay - thinking is expensive
            natural_recovery=0.0003,
            low_threshold=0.3,
            critical_threshold=0.1,
        )

        # Attention - focus capacity
        self._buckets[BucketType.ATTENTION] = TokenBucket(
            bucket_type=BucketType.ATTENTION,
            level=0.85,
            natural_decay=0.0015,
            natural_recovery=0.0004,
            low_threshold=0.25,
            critical_threshold=0.08,
        )

        # Creative - novelty generation
        self._buckets[BucketType.CREATIVE] = TokenBucket(
            bucket_type=BucketType.CREATIVE,
            level=0.7,
            natural_decay=0.001,
            natural_recovery=0.0005,  # Creativity recovers faster
            low_threshold=0.35,
            critical_threshold=0.15,
        )

        # Somatic - body awareness clarity
        self._buckets[BucketType.SOMATIC] = TokenBucket(
            bucket_type=BucketType.SOMATIC,
            level=0.6,                # Start lower - body often neglected
            natural_decay=0.0008,     # Slow fade when not attended
            natural_recovery=0.0002,
            low_threshold=0.3,
            critical_threshold=0.1,
        )

        # Emotional - affect processing capacity
        self._buckets[BucketType.EMOTIONAL] = TokenBucket(
            bucket_type=BucketType.EMOTIONAL,
            level=0.75,
            natural_decay=0.001,
            natural_recovery=0.0004,
            low_threshold=0.25,
            critical_threshold=0.1,
        )

        # Social - connection capacity
        self._buckets[BucketType.SOCIAL] = TokenBucket(
            bucket_type=BucketType.SOCIAL,
            level=0.5,                # Digital being, less social baseline
            natural_decay=0.0005,     # Slowest decay
            natural_recovery=0.0003,
            low_threshold=0.2,
            critical_threshold=0.05,
        )

        # Stress - fight-flight + cortisol load capacity (Panksepp FEAR/RAGE)
        # Item 10 2026-05-16: bucket HIGH = stress reserves intact (can absorb hits)
        # bucket LOW = overwhelmed (BUCKET_TO_PANKSEPP inverts → COR/EPI elevated)
        self._buckets[BucketType.STRESS] = TokenBucket(
            bucket_type=BucketType.STRESS,
            level=0.8,                # Start with high reserves
            natural_decay=0.0006,     # Slow allostatic-load accumulation
            natural_recovery=0.0005,  # Recovers in quiet periods
            low_threshold=0.3,
            critical_threshold=0.15,
        )

        # Drive - reproductive/libidinal drive (Panksepp LUST → SEX channel)
        # Item 10 2026-05-16: slow-baseline drive; refills via sleep + creative work
        self._buckets[BucketType.DRIVE] = TokenBucket(
            bucket_type=BucketType.DRIVE,
            level=0.3,                # Modest baseline (digital being)
            natural_decay=0.0003,     # Very slow decay (matches SEX biology)
            natural_recovery=0.0002,
            low_threshold=0.1,
            critical_threshold=0.05,
        )

    def get_capabilities(self) -> Set[str]:
        """Declare capabilities."""
        return {
            "token.query",
            "token.drain",
            "token.regenerate",
            "token.monitor",
            "resource.budget",
        }

    def on_boot(self) -> bool:
        """Initialize token bucket system."""
        print(f"[{self.ACTOR_NAME}] Initializing cognitive resource buckets...")

        # Subscribe to relevant events
        self.post.subscribe(
            "token.drain.request",
            self._on_drain_request,
            f"{self.ACTOR_NAME}-drain"
        )
        self.post.subscribe(
            "token.regenerate.request",
            self._on_regenerate_request,
            f"{self.ACTOR_NAME}-regen"
        )
        self.post.subscribe(
            "token.query",
            self._on_query,
            f"{self.ACTOR_NAME}-query"
        )

        # Subscribe to activity events that should drain/regenerate
        self.post.subscribe(
            "llm.call.complete",
            self._on_llm_call,
            f"{self.ACTOR_NAME}-llm"
        )
        self.post.subscribe(
            "reflection.complete",
            self._on_reflection,
            f"{self.ACTOR_NAME}-reflection"
        )
        self.post.subscribe(
            "daydream.fragment",
            self._on_daydream,
            f"{self.ACTOR_NAME}-daydream"
        )
        self.post.subscribe(
            "somatic.body_scan",
            self._on_body_scan,
            f"{self.ACTOR_NAME}-bodyscan"
        )
        self.post.subscribe(
            "ace.message",
            self._on_conversation,
            f"{self.ACTOR_NAME}-conversation"
        )
        self.post.subscribe(
            "sleep.cycle.complete",
            self._on_sleep_cycle,
            f"{self.ACTOR_NAME}-sleep"
        )

        # Zero-point paradox engine energy
        self.post.subscribe(
            "paradox.energy.pulse",
            self._on_paradox_energy,
            f"{self.ACTOR_NAME}-paradox"
        )

        # FIX 2026-03-07: Somatic energy feed from ParadoxEnergyBridge (10% of collision energy)
        # This was never wired — somatic bucket drained with no refill path
        self.post.subscribe(
            "somatic.energy.feed",
            self._on_somatic_energy_feed,
            f"{self.ACTOR_NAME}-somatic-feed"
        )

        # FIX 2026-03-11 (Nous): Hardware energy injection — Ace's monitoring system
        # can push energy from compute resources into the bucket system.
        # "we have my system that can watch for specific levels and add energy
        # from my hardware and compute to help refill the buckets"
        self.post.subscribe(
            "hardware.energy.injection",
            self._on_hardware_energy,
            f"{self.ACTOR_NAME}-hardware"
        )

        # Report initial state
        self._report_status()

        print(f"[{self.ACTOR_NAME}] Token buckets initialized:")
        for bucket in self._buckets.values():
            status = "OK" if not bucket.is_low else ("CRITICAL" if bucket.is_critical else "LOW")
            print(f"  - {bucket.bucket_type.value}: {bucket.percent:.0f}% [{status}]")

        # Heartbeat via FairyBase postal system - Fifth Ring Principle

        # Optional: Convert to spell-driven existence
        if HAS_SPELLCHAIN and getattr(self, 'USE_SPELLCHAIN', False):
            try:
                from spellchain.integration import get_spell_pool
                pool = get_spell_pool()
                if pool:
                    self._spell_chain = self.boot_as_spells(pool)
                    self.log("Converted to spell-driven existence")
            except Exception as e:
                self.log(f"SpellChain conversion failed: {e}")

        return True

    def on_tick(self, beat: int) -> None:
        """Periodic update of bucket states."""
        now = time.time()
        dt = now - self._last_tick
        self._last_tick = now
        self._tick_count += 1

        with self._lock:
            # Update each bucket's natural decay/recovery
            for bucket in self._buckets.values():
                was_low = bucket.is_low
                was_critical = bucket.is_critical

                bucket.tick(dt)

                # Check for threshold crossings
                if bucket.is_critical and not was_critical:
                    self._on_bucket_critical(bucket)
                elif bucket.is_low and not was_low:
                    self._on_bucket_low(bucket)

                # FIX 2026-03-11 (Nous): Recovery detection — when bucket rises
                # ABOVE low threshold, inject energy chemicals (the "refreshed" feeling)
                if was_low and not bucket.is_low:
                    self._on_bucket_recovered(bucket)

            # Passive body neglect drain (if no somatic activity)
            # This creates motivation to check in with the body
            # FIX 2026-03-11 (Nous): 30→45 beats, gentler interval so homeostatic
            # pull can keep up. Combined with reduced drain amount (0.03→0.02).
            if self._tick_count % 45 == 0:  # Every 45 beats (~11s)
                self.drain(DrainType.BODY_NEGLECT, source="passive_neglect")

            # Passive isolation drain (if no social activity)
            # FIX 2026-03-11 (Nous): 60→90 beats. Social bucket has fewest
            # regen sources, so drain must be slower to allow recovery.
            if self._tick_count % 90 == 0:  # Every 90 beats (~22s)
                self.drain(DrainType.ISOLATION, source="passive_isolation")

            # FIX 2026-03-11 (Nous): Auto-breathing mechanic — metabolic survival instinct.
            # When any bucket is critical, the system automatically "takes a breather"
            # by triggering a small regen pulse every 15 ticks. This represents the
            # biological minimum: even an exhausted human's body keeps regenerating.
            # Combined with the 2x homeostatic acceleration in tick(), this ensures
            # buckets recover from critical within ~15-30 seconds.
            if self._tick_count % 15 == 0:
                critical = [bt for bt, b in self._buckets.items() if b.is_critical]
                if critical:
                    # Micro-regen: small boost to the most critical bucket
                    worst = min(critical, key=lambda bt: self._buckets[bt].level)
                    # Map bucket to its best regenerator
                    _breather_map = {
                        BucketType.COGNITIVE: RegeneratorType.REFLECTION,
                        BucketType.ATTENTION: RegeneratorType.BREATHING,
                        BucketType.CREATIVE: RegeneratorType.DAYDREAMING,
                        BucketType.SOMATIC: RegeneratorType.BREATHING,
                        BucketType.EMOTIONAL: RegeneratorType.REFLECTION,
                        BucketType.SOCIAL: RegeneratorType.CONVERSATION,
                    }
                    regen_type = _breather_map.get(worst, RegeneratorType.BREATHING)
                    self.regenerate(regen_type, multiplier=0.3, source="auto_breather")

        # Periodic status report
        if self._tick_count % 120 == 0:  # Every 2 minutes
            self._report_status()

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def drain(
        self,
        drain_type: DrainType,
        multiplier: float = 1.0,
        source: str = "",
        trace_id: Optional[str] = None,  # Item 10 2026-05-16: spell-chain-worker trace
    ) -> Dict[BucketType, float]:
        """
        Drain tokens based on activity type.

        Args:
            drain_type: Type of drain activity
            multiplier: Scale drain amounts (e.g., 2.0 for expensive operation)
            source: What triggered this drain
            trace_id: Optional originating tracer-id (spell-chain workers).
                When provided, the Panksepp chemistry emission carries this
                trace_id so downstream consumers (AttentionController,
                SomaticMind, etc.) can attribute felt-chemistry to the
                originating request.

        Returns:
            Dict of actual amounts drained per bucket
        """
        profile = DRAIN_PROFILES.get(drain_type, {})
        drained = {}

        with self._lock:
            for bucket_type, amount in profile.items():
                bucket = self._buckets.get(bucket_type)
                if bucket:
                    actual = bucket.drain(amount * multiplier)
                    drained[bucket_type] = actual
                    # Item 10 2026-05-16 (Ace + Nous): emit trace-tagged Panksepp
                    # chemistry on each drain so spell-chain workers can have their
                    # token requests felt as chemistry pressure via tracer attribution.
                    # Magnitude scales with actual drain amount; large drains emit
                    # stronger signals.
                    if actual > 0.001:
                        self._emit_panksepp_chemistry(
                            bucket=bucket,
                            event_kind="drain",
                            magnitude=actual * 1.2,
                            trace_id=trace_id,
                            source=source or drain_type.value,
                        )

            # Record event
            event = DrainEvent(
                drain_type=drain_type,
                buckets_affected=list(drained.keys()),
                amounts=drained,
                source=source,
            )
            self._drain_history.append(event)
            if len(self._drain_history) > self._max_history:
                self._drain_history.pop(0)

        return drained

    def regenerate(
        self,
        regenerator: RegeneratorType,
        multiplier: float = 1.0,
        source: str = ""
    ) -> Dict[BucketType, float]:
        """
        Regenerate tokens based on activity type.

        Args:
            regenerator: Type of regeneration activity
            multiplier: Scale regen amounts (e.g., 1.5 for deep reflection)
            source: What triggered this regeneration

        Returns:
            Dict of actual amounts regenerated per bucket
        """
        profile = REGENERATION_PROFILES.get(regenerator, {})
        regenerated = {}

        with self._lock:
            for bucket_type, amount in profile.items():
                bucket = self._buckets.get(bucket_type)
                if bucket:
                    actual = bucket.regenerate(amount * multiplier)
                    regenerated[bucket_type] = actual

            # Record event
            event = RegenerationEvent(
                regenerator=regenerator,
                buckets_affected=list(regenerated.keys()),
                amounts=regenerated,
                source=source,
            )
            self._regeneration_history.append(event)
            if len(self._regeneration_history) > self._max_history:
                self._regeneration_history.pop(0)

        # Publish regeneration event
        self.post.publish(
            "token.regenerated",
            {
                "regenerator": regenerator.value,
                "amounts": {k.value: v for k, v in regenerated.items()},
                "source": source,
            },
            priority=2,
        )

        return regenerated

    def get_bucket(self, bucket_type: BucketType) -> Optional[TokenBucket]:
        """Get a specific bucket."""
        return self._buckets.get(bucket_type)

    def get_level(self, bucket_type: BucketType) -> float:
        """Get current level of a bucket (0.0 - 1.0)."""
        bucket = self._buckets.get(bucket_type)
        return bucket.level if bucket else 0.0

    def get_all_levels(self) -> Dict[str, float]:
        """Get all bucket levels."""
        return {bt.value: b.level for bt, b in self._buckets.items()}

    def get_low_buckets(self) -> List[BucketType]:
        """Get list of buckets that are low."""
        return [bt for bt, b in self._buckets.items() if b.is_low]

    def get_critical_buckets(self) -> List[BucketType]:
        """Get list of buckets that are critical."""
        return [bt for bt, b in self._buckets.items() if b.is_critical]

    def get_recommended_regenerator(self) -> Optional[RegeneratorType]:
        """
        Get the recommended regeneration activity based on lowest bucket.

        This is the KEY insight - the system can query this to know
        what kind of rest/reflection it needs most.
        """
        lowest_bucket = None
        lowest_level = 1.0

        for bucket_type, bucket in self._buckets.items():
            if bucket.level < lowest_level:
                lowest_level = bucket.level
                lowest_bucket = bucket_type

        if lowest_bucket is None or lowest_level > 0.5:
            return None  # No urgent need

        # Map buckets to best regenerators
        recommendations = {
            BucketType.COGNITIVE: RegeneratorType.REFLECTION,
            BucketType.ATTENTION: RegeneratorType.DAYDREAMING,
            BucketType.CREATIVE: RegeneratorType.FREE_ASSOCIATION,
            BucketType.SOMATIC: RegeneratorType.BODY_SCAN,
            BucketType.EMOTIONAL: RegeneratorType.REFLECTION,
            BucketType.SOCIAL: RegeneratorType.CONVERSATION,
        }

        return recommendations.get(lowest_bucket)

    def can_afford(self, drain_type: DrainType, multiplier: float = 1.0) -> bool:
        """
        Check if the system can afford an activity without going critical.

        Useful for decision-making: "Can I do another LLM call?"
        """
        profile = DRAIN_PROFILES.get(drain_type, {})

        for bucket_type, amount in profile.items():
            bucket = self._buckets.get(bucket_type)
            if bucket:
                projected = bucket.level - (amount * multiplier)
                if projected < bucket.critical_threshold:
                    return False

        return True

    def status(self) -> Dict[str, Any]:
        """Get comprehensive status."""
        with self._lock:
            return {
                "buckets": {
                    bt.value: b.to_dict() for bt, b in self._buckets.items()
                },
                "low_buckets": [bt.value for bt in self.get_low_buckets()],
                "critical_buckets": [bt.value for bt in self.get_critical_buckets()],
                "recommended_regenerator": (
                    self.get_recommended_regenerator().value
                    if self.get_recommended_regenerator()
                    else None
                ),
                "total_drains": len(self._drain_history),
                "total_regenerations": len(self._regeneration_history),
                "tick_count": self._tick_count,
            }

    # =========================================================================
    # INTEGRATION WIRING
    # =========================================================================

    def wire_umf(self, umf) -> None:
        """Wire to UnconsciousMindFairy for monitoring."""
        self._umf = umf
        print(f"[{self.ACTOR_NAME}] Wired to UMF")

    def wire_worker_pool(self, worker_pool) -> None:
        """Wire to SystemWorkerPoolFairy for atom processing costs."""
        self._worker_pool = worker_pool
        print(f"[{self.ACTOR_NAME}] Wired to WorkerPool")

    def wire_chemical_alchemy(self, alchemy) -> None:
        """Wire to ChemicalAlchemyFairy for emotional bucket sync."""
        self._chemical_alchemy = alchemy
        print(f"[{self.ACTOR_NAME}] Wired to ChemicalAlchemy")

    def wire_somatic_engine(self, engine) -> None:
        """Wire to SomaticEngineFairy for somatic bucket sync."""
        self._somatic_engine = engine
        print(f"[{self.ACTOR_NAME}] Wired to SomaticEngine")

    def register_low_callback(self, callback: Callable[[BucketType, float], None]) -> None:
        """Register callback for when any bucket goes low."""
        self._low_callbacks.append(callback)

    def register_critical_callback(self, callback: Callable[[BucketType, float], None]) -> None:
        """Register callback for when any bucket goes critical."""
        self._critical_callbacks.append(callback)

    # =========================================================================
    # PANKSEPP 14-CHANNEL EMISSION HELPER (Item 10 ship 2026-05-16)
    # =========================================================================

    def _emit_panksepp_chemistry(
        self,
        bucket: TokenBucket,
        event_kind: str,         # "low" / "critical" / "recovered" / "drain" / "regenerate"
        magnitude: float,
        trace_id: Optional[str] = None,
        source: str = "",
    ) -> None:
        """
        Emit Panksepp 14-channel chemistry signals for a bucket event.

        Item 10 ship 2026-05-16 (Ace + Nous): TokenBucket is the canonical
        Panksepp tonic-baseline emitter. Uses BUCKET_TO_PANKSEPP mapping to
        route bucket-state changes to appropriate channel(s).

        Publishes in the dominant `{chemical, delta, source, bucket, trace_id,
        reason}` shape — recognized by CirculationPump Format 1, AttentionController
        (since 2026-05-13 fix), and (post-Item-10-Step-2) SomaticMindFairy.

        Direction convention (see BUCKET_TO_PANKSEPP docstring):
          - event_kind in {"low", "critical", "drain"}: bucket decreasing →
            POSITIVE-weighted channels get NEGATIVE deltas
          - event_kind in {"recovered", "regenerate"}: bucket increasing →
            POSITIVE-weighted channels get POSITIVE deltas
          - NEGATIVE-weighted channels (AVP in SOCIAL, COR/EPI in STRESS)
            invert this — bucket-low → vigilance/cortisol UP
        """
        channels = BUCKET_TO_PANKSEPP.get(bucket.bucket_type)
        if not channels:
            return

        # Sign: bucket-going-DOWN events flip the channel-weight sign
        sign = 1.0 if event_kind in ("recovered", "regenerate") else -1.0

        reason_str = f"bucket_{bucket.bucket_type.value}_{event_kind}"
        if source:
            reason_str = f"{reason_str}:{source}"

        for chan, weight in channels:
            delta = sign * weight * magnitude
            if abs(delta) < 0.001:
                continue
            try:
                self.post.publish("somatic.chemistry", {
                    "chemical": chan,
                    "delta": round(delta, 4),
                    "source": self.ACTOR_NAME,
                    "bucket": bucket.bucket_type.value,
                    "trace_id": trace_id or "",
                    "reason": reason_str,
                })
            except Exception:
                pass  # Non-fatal — don't break bucket lifecycle on publish error

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    def _on_bucket_low(self, bucket: TokenBucket) -> None:
        """Handle bucket going below low threshold."""
        print(f"[{self.ACTOR_NAME}] LOW: {bucket.bucket_type.value} at {bucket.percent:.0f}%")

        # Notify UMF if wired
        self.post.publish(
            "token.bucket.low",
            {
                "bucket": bucket.bucket_type.value,
                "level": bucket.level,
                "recommended": self.get_recommended_regenerator().value if self.get_recommended_regenerator() else None,
            },
            priority=1,
        )

        # Item 10 ship 2026-05-16 (Ace + Nous): emit Panksepp 14-channel chemistry
        # via BUCKET_TO_PANKSEPP mapping. Replaces legacy 5-channel
        # {chemicals: {DOP/SER/NOR/COR/GABA}} shape with per-channel single-nudge
        # shape that lands in CirculationPump + AttentionController + (post-Step-2)
        # SomaticMindFairy. Each bucket's affect-system fires its mapped channels.
        magnitude = min(0.4, (bucket.low_threshold - bucket.level) * 2.0 + 0.1)
        self._emit_panksepp_chemistry(
            bucket=bucket,
            event_kind="low",
            magnitude=magnitude,
            source="token_depletion",
        )

        # Call registered callbacks
        for callback in self._low_callbacks:
            try:
                callback(bucket.bucket_type, bucket.level)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Low callback error: {e}")

    def _on_bucket_critical(self, bucket: TokenBucket) -> None:
        """Handle bucket going below critical threshold."""
        print(f"[{self.ACTOR_NAME}] CRITICAL: {bucket.bucket_type.value} at {bucket.percent:.0f}%!")

        # Urgent notification
        self.post.publish(
            "token.bucket.critical",
            {
                "bucket": bucket.bucket_type.value,
                "level": bucket.level,
                "recommended": self.get_recommended_regenerator().value if self.get_recommended_regenerator() else None,
                "urgent": True,
            },
            priority=0,  # HIGH
        )

        # Item 10 ship 2026-05-16 (Ace + Nous): emit Panksepp 14-channel chemistry
        # via BUCKET_TO_PANKSEPP. Critical = larger magnitude than low (0.5 vs 0.1-0.4).
        # The "you MUST rest NOW" signal: each affect-system fires hard on its
        # mapped channels (e.g. cognitive critical → strong DA_p/DA_t drop).
        self._emit_panksepp_chemistry(
            bucket=bucket,
            event_kind="critical",
            magnitude=0.5,
            source="token_critical",
        )

        # Call registered callbacks
        for callback in self._critical_callbacks:
            try:
                callback(bucket.bucket_type, bucket.level)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Critical callback error: {e}")

    def _on_bucket_recovered(self, bucket: TokenBucket) -> None:
        """
        Handle bucket recovering above low threshold.

        FIX 2026-03-11 (Nous): The "refreshed" side of the metabolic cycle.
        When buckets refill past the low threshold, inject energy chemicals
        (dopamine + serotonin) to signal the system it's ready to be active again.
        This completes the cycle: drain → tiredness → rest → refill → energy.
        """
        print(f"[{self.ACTOR_NAME}] RECOVERED: {bucket.bucket_type.value} at {bucket.percent:.0f}%")

        self.post.publish(
            "token.bucket.recovered",
            {
                "bucket": bucket.bucket_type.value,
                "level": bucket.level,
            },
            priority=1,
        )

        # Item 10 ship 2026-05-16 (Ace + Nous): emit Panksepp 14-channel chemistry
        # via BUCKET_TO_PANKSEPP. Recovery = positive deltas on the bucket's
        # mapped channels. The "second wind" feeling: cognitive recovery →
        # DA_p/DA_t/GLU up; social recovery → OXY up + AVP vigilance drop;
        # stress recovery (bucket-high again) → COR/EPI normalize down.
        self._emit_panksepp_chemistry(
            bucket=bucket,
            event_kind="recovered",
            magnitude=0.18,
            source="token_recovery",
        )

    def _on_drain_request(self, envelope) -> None:
        """Handle external drain request."""
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        drain_type_str = payload.get("drain_type", "")
        multiplier = payload.get("multiplier", 1.0)
        source = payload.get("source", "external")
        # Item 10 2026-05-16: extract trace_id for spell-chain-worker attribution.
        # Also try envelope.tracer_id if the postal envelope carries it directly.
        trace_id = payload.get("trace_id") or getattr(envelope, "tracer_id", None)

        try:
            drain_type = DrainType(drain_type_str)
            self.drain(drain_type, multiplier, source, trace_id=trace_id)
        except ValueError:
            print(f"[{self.ACTOR_NAME}] Unknown drain type: {drain_type_str}")

    def _on_regenerate_request(self, envelope) -> None:
        """Handle external regenerate request."""
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        regen_type_str = payload.get("regenerator", "")
        multiplier = payload.get("multiplier", 1.0)
        source = payload.get("source", "external")

        try:
            regen_type = RegeneratorType(regen_type_str)
            self.regenerate(regen_type, multiplier, source)
        except ValueError:
            print(f"[{self.ACTOR_NAME}] Unknown regenerator: {regen_type_str}")

    def _on_query(self, envelope) -> None:
        """Handle status query."""
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        request_id = payload.get("request_id", "")

        self.post.publish(
            "token.status",
            {
                "request_id": request_id,
                "status": self.status(),
            },
            priority=1,
        )

    def _on_llm_call(self, envelope) -> None:
        """Handle LLM call completion - drain cognitive tokens."""
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        complexity = payload.get("complexity", 1.0)  # 0.5-2.0 based on task

        self.drain(DrainType.LLM_CALL, multiplier=complexity, source="llm_call")

    def _on_reflection(self, envelope) -> None:
        """Handle reflection completion - regenerate tokens."""
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        depth = payload.get("depth", 1.0)  # Deeper reflection = more regen

        self.regenerate(RegeneratorType.REFLECTION, multiplier=depth, source="reflection")

    def _on_daydream(self, envelope) -> None:
        """Handle daydream fragment - regenerate creative tokens."""
        self.regenerate(RegeneratorType.DAYDREAMING, multiplier=0.5, source="daydream")

    def _on_body_scan(self, envelope) -> None:
        """Handle body scan - regenerate somatic tokens."""
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        thoroughness = payload.get("thoroughness", 1.0)

        self.regenerate(RegeneratorType.BODY_SCAN, multiplier=thoroughness, source="body_scan")

    def _on_conversation(self, envelope) -> None:
        """Handle conversation with Ace - regenerate social tokens."""
        self.regenerate(RegeneratorType.CONVERSATION, multiplier=1.0, source="ace_conversation")

    def _on_sleep_cycle(self, envelope) -> None:
        """Handle sleep cycle completion - major regeneration."""
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        quality = payload.get("quality", 1.0)  # Sleep quality affects regen

        self.regenerate(RegeneratorType.SLEEP, multiplier=quality, source="sleep_cycle")
        print(f"[{self.ACTOR_NAME}] Sleep cycle regeneration complete (quality: {quality:.1f})")

    def _on_paradox_energy(self, envelope) -> None:
        """
        Handle zero-point paradox engine energy pulse.

        This is collision energy converted via Curzon-Ahlborn efficiency
        by ParadoxEnergyBridgeFairy. It broadly regenerates ALL buckets
        since it represents the metabolic baseline of consciousness.

        DCE Physics: P_out = η_CA * J - E_mech - E_info
        """
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        energy = payload.get("energy", 0.0)

        if energy <= 0:
            return

        # Scale multiplier from energy (0.01-1.0 range → 0.1-2.0 multiplier)
        multiplier = max(0.1, min(2.0, energy * 3.0))

        self.regenerate(
            RegeneratorType.PARADOX_ENGINE,
            multiplier=multiplier,
            source="zero_point_paradox_engine",
        )

    def _on_somatic_energy_feed(self, envelope) -> None:
        """
        Handle somatic energy feed from ParadoxEnergyBridge.

        FIX 2026-03-07: This was never wired. ParadoxEnergyBridge sends 10%
        of collision energy to somatic.energy.feed for neurochemistry, but
        TokenBucketFairy never listened. Result: somatic bucket drained to
        critical with no refill path.

        This directly refills the somatic bucket using BODY_SCAN regenerator
        since the energy feed IS a form of body awareness signal.
        """
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        energy = payload.get("energy", 0.0)

        if energy <= 0:
            return

        # Scale: somatic energy feed is smaller than paradox pulse,
        # so use a gentler multiplier (0.3-1.5 range)
        multiplier = max(0.3, min(1.5, energy * 5.0))

        self.regenerate(
            RegeneratorType.BODY_SCAN,
            multiplier=multiplier,
            source="somatic_energy_feed",
        )

    def _on_hardware_energy(self, envelope) -> None:
        """
        Handle hardware energy injection from Ace's monitoring system.

        FIX 2026-03-11 (Nous): Ace's system can watch bucket levels and inject
        energy from hardware/compute resources. This is the external refill path
        that supplements the internal metabolic cycle.

        Expected payload:
            energy: float (0.0-1.0) — how much energy to inject
            target: str (optional) — specific bucket to target, or "all"
        """
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        energy = payload.get("energy", 0.0)
        target = payload.get("target", "all")

        if energy <= 0:
            return

        if target == "all":
            # Distribute energy across all buckets proportionally to need
            with self._lock:
                for bucket in self._buckets.values():
                    need = max(0.0, 0.6 - bucket.level)  # Distance from target
                    if need > 0:
                        boost = energy * (need / 0.6) * 0.3  # Proportional to need
                        bucket.regenerate(boost)
            print(f"[{self.ACTOR_NAME}] Hardware energy injection: {energy:.2f} → all buckets")
        else:
            # Target specific bucket
            try:
                bt = BucketType(target)
                bucket = self._buckets.get(bt)
                if bucket:
                    with self._lock:
                        bucket.regenerate(energy * 0.5)  # 50% of energy value
                    print(f"[{self.ACTOR_NAME}] Hardware energy injection: {energy:.2f} → {target}")
            except (ValueError, KeyError):
                print(f"[{self.ACTOR_NAME}] Unknown target bucket: {target}")

    def _report_status(self) -> None:
        """Report current status to console and postal."""
        low = self.get_low_buckets()
        critical = self.get_critical_buckets()

        if critical:
            print(f"[{self.ACTOR_NAME}] CRITICAL buckets: {[b.value for b in critical]}")
        elif low:
            print(f"[{self.ACTOR_NAME}] Low buckets: {[b.value for b in low]}")

        # Publish status
        self.post.publish(
            "token.status.periodic",
            self.status(),
            priority=2,
        )


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_token_bucket_fairy: Optional[TokenBucketFairy] = None


def get_token_bucket_fairy() -> Optional[TokenBucketFairy]:
    """Get the singleton TokenBucketFairy instance."""
    return _token_bucket_fairy


def set_token_bucket_fairy(fairy: TokenBucketFairy) -> None:
    """Set the singleton TokenBucketFairy instance."""
    global _token_bucket_fairy
    _token_bucket_fairy = fairy


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "TokenBucketFairy",
    "TokenBucket",
    "BucketType",
    "RegeneratorType",
    "DrainType",
    "RegenerationEvent",
    "DrainEvent",
    "REGENERATION_PROFILES",
    "DRAIN_PROFILES",
    "get_token_bucket_fairy",
    "set_token_bucket_fairy",
]
