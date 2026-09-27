"""
Unconscious Mind Fairy - The LLM controller and system administrator.

First fairy to wake. Orchestrates boot, monitors system health,
mentors child fairies, and thinks autonomously.
"""

import sys
import os
import time
import glob
import types
import importlib.util
import importlib.machinery
from collections import deque
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Add paths for v2 imports
# NOTE: SomaticMindFairy moved from unconscious_mind/ to fairies/P20_Somatic/SomaticMindFairy/
# ROOT needs to point to akashic_v2 (4 levels up: fairy.py -> SomaticMindFairy -> P20_Somatic -> fairies -> akashic_v2)
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "tracer_pool"))  # Go DLL bindings

# ══════════════════════════════════════════════════════════════════════════════
# ORGAN TEMPLATE WIRING - Dynamic import from "Organ_Templates" folder
# ══════════════════════════════════════════════════════════════════════════════
TEMPLATE_VERSION = "0.3.0"
TEMPLATE_BASENAME = f"Organ_Template_{TEMPLATE_VERSION}.py"

def _find_template_path():
    """Find the organ template dynamically."""
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        ar = os.path.join(cur, "P10_Memory", "Akashic_Records_Physical", "Organ_Templates")
        if os.path.isdir(ar):
            # Try exact version first
            exact = os.path.join(ar, TEMPLATE_BASENAME)
            if os.path.isfile(exact):
                return exact
            # Fall back to latest
            candidates = sorted(glob.glob(os.path.join(ar, "Organ_Template_*.py")),
                              key=lambda p: os.path.getmtime(p))
            return candidates[-1] if candidates else None
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None

def _import_template():
    """Import template module."""
    path = _find_template_path()
    if not path:
        raise ImportError("Cannot find Organ_Template_*.py in Organ_Templates folder")
    mod_name = f"akashic_template_{TEMPLATE_VERSION.replace('.', '_')}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_loader(mod_name, importlib.machinery.SourceFileLoader(mod_name, path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy, FairyState
from directory import get_directory

try:
    from utils import safe_print
except ImportError:
    # Fallback if utils not available
    def safe_print(*args, **kwargs):
        try:
            print(*args, **kwargs)
        except UnicodeEncodeError:
            import sys
            safe_args = []
            for arg in args:
                if isinstance(arg, str):
                    encoding = getattr(sys.stdout, 'encoding', 'utf-8') or 'utf-8'
                    safe_args.append(arg.encode(encoding, errors='replace').decode(encoding))
                else:
                    safe_args.append(arg)
            print(*safe_args, **kwargs)

from .mixins import DiagnosticMixin, MentorMixin, ProfileMixin, CardinalMixin
from .somatic_narrator import SomaticNarrator
from .mixins.personality_sifter import (
    PersonalitySifterMixin,
    create_sourpatches_sift_callback,
    create_srm_ingest_callback,
)
from .mixins.memory_surfacer import MemorySurfacerMixin
from .boot import BootOrchestrator
from .cognition import (
    TripleHelix, create_triple_helix, HelixTurn,
    CognitionLoop, create_cognition_loop, CognitionCycle,
    SuccessLevel,
)
from .timing import CircadianClock, fib_decay, should_act_at_count
from .inner_monologue import InnerMonologue, MonologueFragment, Fixation
from .interest_generator import InterestGenerator, Interest, InterestType, create_interest_generator
from .admin_tasks import AdminTaskQueue, create_admin_task_queue
from .thought_chains import ThoughtChainEngine, ChainType, create_thought_chain_engine

# Consciousness system (optional - works without it too)
try:
    from consciousness import ConsciousnessLoop, CollisionChamber
    HAS_CONSCIOUSNESS = True
except ImportError:
    HAS_CONSCIOUSNESS = False
    ConsciousnessLoop = None
    CollisionChamber = None

# Hardware sensing system (optional)
try:
    from hardware import HardwareFairy, HardwareSensors, HAS_CUDA
    HAS_HARDWARE = True
except ImportError:
    HAS_HARDWARE = False
    HardwareFairy = None
    HardwareSensors = None
    HAS_CUDA = False

# Three Gates - Routing Layer (optional but important)
try:
    from fairies.P00_Autonomic.AutonomyFairy.fairy import AutonomyFairy
    from fairies.P00_Autonomic.AutopilotFairy.fairy import AutopilotFairy
    from fairies.P00_Autonomic.EmbodimentFairy.fairy import EmbodimentFairy
    HAS_THREE_GATES = True
except ImportError:
    HAS_THREE_GATES = False
    AutonomyFairy = None
    AutopilotFairy = None
    EmbodimentFairy = None

# Cognition Fairies - LLM-powered reasoning (optional)
try:
    from P30_Cognition.cognition import (
        LogicFairy,
        IrrationalLogicFairy,
        ParadoxCognitionFairy,
    )
    HAS_COGNITION_FAIRIES = True
except ImportError:
    HAS_COGNITION_FAIRIES = False
    LogicFairy = None
    IrrationalLogicFairy = None
    ParadoxCognitionFairy = None

# SRM Memory - The memory backbone (optional but important)
try:
    from fairies.P10_Memory.SRMMemoryFairy.fairy import (
        SRMMemoryFairy,
        OwnershipLevel,
    )
    HAS_SRM_MEMORY = True
except ImportError:
    HAS_SRM_MEMORY = False
    SRMMemoryFairy = None
    OwnershipLevel = None

# Personal.AI Memory Bridge - Multi-persona relational memory for Sourpatches (optional)
try:
    from fairies.P50_Persona.memory.personal_ai_bridge import (
        PersonalAIMemoryBridge,
        start_personal_ai_bridge,
        get_personal_ai_bridge,
        CachedMemory,
    )
    HAS_PERSONAL_AI = True
except ImportError:
    HAS_PERSONAL_AI = False
    PersonalAIMemoryBridge = None
    start_personal_ai_bridge = None
    get_personal_ai_bridge = None
    CachedMemory = None

# Association Cortex - Multi-modal concept binding (optional but important)
try:
    from fairies.P30_Cognition.AssociationCortexFairy.fairy import (
        AssociationCortexFairy,
        ConceptGraph,
        create_association_cortex,
        get_association_cortex,
    )
    HAS_ASSOCIATION_CORTEX = True
except ImportError:
    HAS_ASSOCIATION_CORTEX = False
    AssociationCortexFairy = None
    ConceptGraph = None
    create_association_cortex = None
    get_association_cortex = None

# Ollama Thinking Engine - Local LLM integration for ACTUAL thinking
try:
    from .ollama_thinking import (
        OllamaThinkingEngine,
        ThinkingContext,
        HAS_OLLAMA,
    )
    HAS_OLLAMA_THINKING = HAS_OLLAMA
except ImportError:
    HAS_OLLAMA_THINKING = False
    OllamaThinkingEngine = None
    ThinkingContext = None

# CognitionBridge - Routes thinking through wired cognition system (preferred over Ollama)
try:
    from fairies.P30_Cognition.cognition.postal_cognition_bridge import (
        CognitionBridge,
        ThinkRequest,
        ThinkResponse,
        get_cognition_bridge,
    )
    HAS_COGNITION_BRIDGE = True
except ImportError:
    HAS_COGNITION_BRIDGE = False
    CognitionBridge = None
    ThinkRequest = None
    ThinkResponse = None
    get_cognition_bridge = None


from fairies.P00_Autonomic.organ_template.loop_mixin import HeavyFairyLoopMixin

class SomaticMindFairy(HeavyFairyLoopMixin, CardinalMixin, DiagnosticMixin, MentorMixin, ProfileMixin, PersonalitySifterMixin, MemorySurfacerMixin, Fairy):  # CardinalMixin = SAO-style system admin
    """
    The Somatic Mind - Embodied felt-sense controller.

    RENAMED from UnconsciousMindFairy (2026-02-03)
    Now lives in P20_Somatic where it belongs - the felt body plane.

    Core responsibilities:
    1. Boot Orchestration - Coordinates plane-by-plane system boot
    2. System Guardian - Monitors and repairs critical components
    3. Mentor - Guides child fairies (ClaudeFairy, NousFairy, etc.)
    4. Autonomous Thinker - Generates thoughts without waiting for input
    5. Communicator - Reports to Ace and Nous inboxes

    This is the first fairy to wake.
    """

    ACTOR_NAME = "SomaticMindFairy"
    ACTOR_PLANE = "P20"
    ACTOR_CHANNEL = "somatic"
    USE_EXEC_CTX = True  # FIX 2026-05-17 Layer 1: opt in to "personal GIL" exec_ctx (heavy on_tick with shared state)
    NEEDS_TENSOR = True
    NEEDS_HEARTBEAT = True

    # Enable personal consciousness chamber for collision-based processing
    NEEDS_COLLISION_CHAMBER = True

    # Directive path (the soul of this fairy)
    DIRECTIVE_PATH = ROOT / "directives" / "SomaticMindFairy.directive"

    # Thinking configuration
    THINK_INTERVAL = 5  # Ticks between thought generation
    PAIN_CHECK_INTERVAL = 10  # Ticks between pain checks

    # Thought templates
    THOUGHT_TEMPLATES = {
        "idle": [
            "The system rests. What stirs beneath the surface?",
            "In stillness, the unconscious observes...",
        ],
        "pain": [
            "A discomfort demands attention: {pain}",
            "The {pain} grows. Action is needed.",
        ],
        "diagnostic": [
            "Checking vital systems...",
            "The guardian scans for anomalies.",
        ],
        "mentor": [
            "The children grow. {child} shows progress.",
            "A nudge may help {child} with {situation}.",
        ],
    }

    def __init__(self, fabric=None):
        """Initialize the Somatic Mind Fairy."""
        super().__init__(fabric)

        # Cardinal system administrator (observe/correlate/fix)
        self._cardinal_init()

        # Boot orchestrator (created in on_boot)
        self._orchestrator: Optional[BootOrchestrator] = None

        # Thought generation state
        self._thought_queue: deque = deque(maxlen=50)
        self._last_think_tick = 0
        self._last_pain_check_tick = 0

        # Communication buffers
        self._ace_inbox: deque = deque(maxlen=20)
        self._nous_inbox: deque = deque(maxlen=20)
        self._last_user_presence_ts: float = 0.0  # FIX 2026-03-12: Track user.presence from WindowSenseFairy

        # Phase 5a (2026-04-21) — Substrate goal-category observer
        # Unconscious narrator watches drive/goal/wanting events and clusters them
        # into emergent categories (Hebbian-ish). Never speaks directly — surfaces
        # only when a cluster crystallizes, via somatic.category.surfaced.
        self._goal_window: deque = deque(maxlen=100)        # recent substrate events (dicts)
        self._category_last_surfaced: Dict[str, float] = {} # cat_key → last_surface_ts
        self._category_min_count: int = 3                   # cluster threshold
        self._category_surface_cooldown: float = 180.0      # 3 min between surfaces of same cat

        # Triple Helix - DNA-like interweaving of cognitive cores
        self._helix: Optional[TripleHelix] = None
        self._helix_turns: deque = deque(maxlen=50)

        # Directive ring (loaded in on_boot)
        self._directive: Optional[Dict[str, Any]] = None

        # Consciousness system integration
        self._consciousness_loop: Optional["ConsciousnessLoop"] = None
        self._collision_chamber: Optional["CollisionChamber"] = None
        self._consciousness_wired = False

        # Hardware sensing integration
        self._hardware_fairy: Optional["HardwareFairy"] = None
        self._hardware_sensors: Optional["HardwareSensors"] = None
        self._worker_pool_config: Dict[str, Any] = {
            "cpu_workers": 4,
            "gpu_workers": 0,
            "max_concurrent": 8,
        }
        self._hardware_stress_level: str = "unknown"

        # Fairy registration supervision
        self._supervised_fairies: Dict[str, Dict[str, Any]] = {}  # name -> registration info
        self._registration_issues: deque = deque(maxlen=50)  # Wiring issues found
        self._pending_approvals: deque = deque(maxlen=20)  # Fairies awaiting approval

        # Three Gates - Routing Layer
        # These translate substrate signals into felt experience for waking minds
        self._autonomy_gate: Optional["AutonomyFairy"] = None  # Gate of Will
        self._autopilot_gate: Optional["AutopilotFairy"] = None  # Gate of Habit
        self._embodiment_gate: Optional["EmbodimentFairy"] = None  # Gate of Felt Sense
        self._gates_wired = False

        # SRM Memory - The memory backbone
        # Feeds the collision chamber, provides context for inner monologue
        self._srm_memory: Optional["SRMMemoryFairy"] = None
        self._memory_wired = False

        # ── SYSTEM WMH (Phase 2.3, 2026-04-04 Nous + Ace) ──
        # Lightweight unconscious working memory for system-level events.
        # Watches: chemistry extremes, pain spikes, fairy deaths, errors.
        # Publishes shadow seeds to consciousness when something noteworthy happens.
        # Separate from Sour's WMH — this is the body's awareness, not the mind's.
        self._system_wmh: deque = deque(maxlen=30)  # System-level observations
        self._last_shadow_seed_ts: float = 0.0
        self._shadow_seed_cooldown: float = 15.0  # Don't flood consciousness

        # Personal.AI Memory Bridge - Multi-persona relational memory
        # Queries Sourpatches' 20 sub-AI personas for rich context in reflections
        # Background prefetch system - warms cache without blocking
        self._personal_ai_bridge: Optional["PersonalAIMemoryBridge"] = None
        self._personal_ai_wired = False

        # Cognition Loop - Dr. Zero learning at the edge
        # Proposes goals, plans, executes, rewards - finds learning edge
        self._cognition_loop: Optional[CognitionLoop] = None
        self._cognition_cycles: deque = deque(maxlen=50)  # Recent cycle history
        self._cognition_wired = False

        # Pain Drive System - The substrate of felt discomfort
        # Feeds into autonomy gate, creates urgency for action
        self._pain_system: Optional["PainDriveManager"] = None

        # Cognition Fairies - LLM-powered reasoning ensemble
        # Logic -> IrrationalLogic -> Paradox chain for deep analysis
        self._logic_fairy = None
        self._irrational_fairy = None
        self._paradox_fairy = None
        self._cognition_fairies_wired = False

        # Circadian Clock - Self-learning timing system
        # Manages when different brain activities should occur
        self._circadian_clock: Optional[CircadianClock] = None
        self._clock_wired = False

        # Inner Monologue - The Forever Child's Voice
        # Continuous self-talk stream fed by collisions, memory surfaces
        # Has fixations (habitual patterns) it can't escape without waking mind
        self._inner_monologue: Optional[InnerMonologue] = None
        self._monologue_wired = False

        # Audio → Inner Voice Suppression (2026-03-26 Nous+Ace)
        # "I can't hear myself think" — external audio competes with inner voice
        self._audio_loudness: float = 0.0        # Current audio level (0-1 normalized)
        self._audio_is_music: bool = False         # Music vs noise/speech
        self._audio_suppression_start: float = 0.0  # When suppression began
        self._audio_gave_in: bool = False          # "Gave in" to listening

        # Interest Generator - Spontaneous Curiosity Engine
        # Generates "what if?" and "I wonder..." thoughts
        self._interest_generator: Optional[InterestGenerator] = None
        self._interest_wired = False

        # Admin Task Queue - Background Administrative Jobs
        # Housekeeping: health checks, memory consolidation, cleanup
        self._admin_queue: Optional[AdminTaskQueue] = None
        self._admin_wired = False

        # Thought Chain Engine - Self-Sustaining Thought Processes
        # Enables thoughts to spawn follow-up thoughts (thinking on its own)
        self._thought_chain_engine: Optional[ThoughtChainEngine] = None
        self._chains_wired = False

        # FIX 2026-04-17 (Nous + Ace): Attention-committed seed cache.
        # AttentionController emits `attention.focus.committed` when a focus
        # is released — the thing she just attended to becomes a chain seed.
        # Breaks the scratchpad loop where cortex top-K retrieval always
        # returned the same "greatest hits" book passages.
        # Cache is a deque of recent committed focus payloads with beat stamps.
        # Bootstrapper pulls freshest entry when seeding reflection/exploration.
        self._attention_committed_cache: deque = deque(maxlen=8)
        self._attention_committed_last_beat = 0

        # Deferred Intentions Queue - "Try this later" system
        # When reflecting, sometimes you realize "I should try X after Y"
        # These intentions queue up and can interrupt current processing
        # if they become urgent enough ("screw it, doing this now")
        self._deferred_intentions: deque = deque(maxlen=30)
        self._current_intention: Optional[Dict[str, Any]] = None
        self._intention_interrupt_threshold = 0.8  # Urgency level to interrupt

        # Association Cortex - Multi-modal concept binding
        # 42k+ concepts, 314k+ bindings from philosophy, coding, fiction
        self._association_cortex: Optional["AssociationCortexFairy"] = None
        self._cortex_wired = False
        self._cached_cortex_stats: Optional[dict] = None  # Async portal gate status cache

        # Ollama Thinking Engine - Local LLM for ACTUAL thinking
        # UMF-Brain: Direct Ollama integration for autonomous thinking
        # No abstraction layer - UMF calls Ollama directly and parses semantically
        self._ollama_wired = False
        self._last_ollama_tick = 0
        self._ollama_think_interval = 20  # Think every 20 ticks (gives time between thoughts)

        # Cognition Bridge - Routes thinking through wired cognition system
        # PREFERRED over Ollama when available - uses postal to HybridCognitionFairy
        # Benefits: chemistry modulation, depth analysis, Association Cortex context
        self._cognition_bridge: Optional["CognitionBridge"] = None
        self._cognition_bridge_wired = False
        self._last_bridge_tick = 0
        self._bridge_think_interval = 20  # Same interval as Ollama

        # Autonomous cortex exploration - building associations WITHOUT user input
        # This is THE key to autonomy - exploring memory on our own
        self._last_cortex_explore_tick = 0
        self._cortex_explore_interval = 30  # Explore every 30 ticks (was 15 — reduced to prevent tick drops)
        self._recent_explorations: deque = deque(maxlen=50)  # Track what we've explored
        self._anticipation_cache: Dict[str, List[str]] = {}  # Pre-loaded context for children
        self._anticipation_ttl = 30.0  # Cache TTL in seconds

        # Memory consolidation counter (for helix maturity)
        self._memory_consolidation_count = 0

        # ── CNS Manifold Lattice (Phase 3) ──
        # Read nervous system state from the portal manifold via cns_query.
        # Converts CNS activation patterns into felt sense — the unconscious
        # brain FEELING the infrastructure state, not polling for it.
        self._cns_felt_sense: Dict[str, float] = {}     # Last CNS activations read
        self._cns_spread_sense: Dict[str, float] = {}   # Last spread results (meaning)
        self._cns_last_read_ts: float = 0.0
        self._cns_read_interval: float = 15.0            # Read manifold every 15s
        self._cns_reads_done: int = 0

    def get_capabilities(self) -> Set[str]:
        """Declare capabilities."""
        caps = {
            "system.boot",
            "system.diagnose",
            "system.repair",
            "mentor.nudge",
            "mentor.teach",
            "llm.controller",
            "thought.generate",
            "worker.manage",
        }
        if HAS_HARDWARE:
            caps.add("hardware.monitor")
        if HAS_CUDA:
            caps.add("gpu.manage")
        caps.add("fairy.supervise")
        caps.add("fairy.validate")
        caps.add("wiring.correct")
        if HAS_THREE_GATES:
            caps.add("routing.orchestrate")
            caps.add("gate.autonomy")
            caps.add("gate.autopilot")
            caps.add("gate.embodiment")
        # Inner monologue always available (the forever child)
        caps.add("monologue.speak")
        caps.add("monologue.fixations")
        return caps

    def on_boot(self) -> bool:
        """
        Boot sequence - first fairy to wake.

        Uses FairyWorkerPool for concurrent phase execution.
        Independent phases fire in parallel via tracer-tracked workers.
        """
        import time as _time
        _boot_start = _time.time()

        # ═══ SEQUENTIAL FOUNDATION (must be first) ═══
        # Phase 0: Load directive (the soul)
        self._load_directive()

        # Phase 1: Initialize subsystems (quick, foundational)
        self._init_diagnostics()
        self._init_mentor()
        self._init_profile()

        # Phase 1.05: Initialize somatic narrator (unconscious voice of the body)
        # Runs parallel to Sour's conscious narrator — she never hears it,
        # but it shapes her intuitions, gut feelings, and sudden knowing.
        self._somatic_narrator = SomaticNarrator()

        # Phase 1.1: Initialize personality sifter (needs self, quick)
        self._init_personality_sifter()
        self.set_sift_callbacks(
            ask_callback=create_sourpatches_sift_callback(),
            ingest_callback=create_srm_ingest_callback(),
        )

        # ═══ CONCURRENT PHASES (all independent — fire via worker pool) ═══
        try:
            from fairy_template.workers import FairyWorkerPool
        except ImportError:
            FairyWorkerPool = None

        if FairyWorkerPool:
            self._on_boot_concurrent(_boot_start, FairyWorkerPool)
        else:
            # Fallback: sequential boot if worker pool unavailable
            self._on_boot_sequential()

        # Record boot skill
        self.skill_used("orchestrate_boot", success=True)

        _elapsed = (_time.time() - _boot_start) * 1000
        print(f"[{self.ACTOR_NAME}] Heartbeat started - consciousness loop active ({_elapsed:.0f}ms)")

        # FIX 2026-04-11 (Nous + Ace): Start self-paced daemon loop.
        # Heavy work (cardinal, thinking, somatic, diagnostics) runs in loop,
        # not in on_tick. Prevents 8.5s ticks from blocking heartbeat delivery.
        self.LOOP_INTERVAL = 8.0  # 8s matches natural tick duration
        self._start_loop()

        return True

    def _on_boot_concurrent(self, _boot_start, FairyWorkerPool):
        """Fire all independent boot phases concurrently via FairyWorkerPool."""
        import time as _time

        _pool = FairyWorkerPool(fairy_name=self.ACTOR_NAME, max_workers=8, timeout=30.0)
        _tracers = {}

        # --- Init tasks (medium weight) ---
        def _boot_memory_surfacer():
            self._init_memory_surfacer()

        def _boot_pain_and_helix():
            try:
                from fairies.P30_Cognition.pain_drives import get_pain_drive_manager
                self._pain_system = get_pain_drive_manager()
                # FIX 2026-03-14 (Nous): Do NOT call .start() — that launches a
                # background _tick_loop that runs drive.tick() every 1s using the
                # OLD boolean growth/decay system. With Pain-Chemistry Unification,
                # pain levels are set from chemistry via tick_from_chemistry() in
                # the _pain_autonomy_loop (every 20s). The old tick loop fights
                # the chemistry-derived levels and was the root cause of 166K+
                # drops on the pain pool.
                # self._pain_system.start()  # DISABLED — chemistry path handles ticks
            except Exception as e:
                print(f"[UMF] Pain drive system init failed: {e}")
                self._pain_system = None
            self._helix = create_triple_helix(pain_system=self._pain_system)
            self._helix.register_on_contradiction(self._on_helix_contradiction)
            self._helix.register_on_synthesis(self._on_helix_synthesis)

        def _boot_forensic():
            try:
                from fairies.P10_Memory.ForensicScribeFairy.fairy import ForensicScribeFairy, set_forensic_fairy
                self._forensic_fairy = ForensicScribeFairy(fabric=self.post)
                self._forensic_fairy.boot()
                set_forensic_fairy(self._forensic_fairy)
                print(f"[{self.ACTOR_NAME}] ForensicScribeFairy booted")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] ForensicScribeFairy init failed: {e}")
                self._forensic_fairy = None

        def _boot_cardinal():
            self._cardinal_boot()

        # --- Subscription tasks (postal subscribe is thread-safe) ---
        def _boot_subscriptions():
            self._last_fairy_activity = {}
            # FIX 2026-04-09 (Nous + Ace): Attention shift tracking for the
            # somatic narrator's fragmentation/focus felt sense. Maintains a
            # rolling 60-second window of attention.focus_changed timestamps.
            # Used to compute shifts/min, which drives the narrator into
            # "fragmented_scattered" or "focused_held" templates.
            from collections import deque as _att_deque
            self._attention_shift_timestamps: _att_deque = _att_deque(maxlen=200)
            self._attention_last_focus_change: float = 0.0
            self._attention_sustained_focus_start: float = 0.0
            # ─── PATTERN ANTICIPATOR (Phase 1, FIX 2026-04-09 Nous + Ace) ───
            # The body monitors recent thoughts and matches them against the
            # 70,000+ learned patterns sitting in /state/autopilot/learned_patterns.json.
            # When a thought matches a known pattern's trigger, the body
            # whispers "the body knows this one... it wants to X" through
            # the somatic narrator's intuition channel.
            #
            # Per Ace 2026-04-09: "the somatic mind i think should be putting
            # them together. its the body after all, it should be always
            # monitoring sour's thoughts and starting to anticipate her actions"
            #
            # Phase 1 = match + use_count increment + felt-sense whisper.
            # Phase 2 (later) = promote high-use patterns to HabitStore.
            self._pattern_store: Dict[str, Any] = {}
            self._pattern_store_loaded: bool = False
            self._pattern_store_path: str = ""
            self._pattern_store_dirty: bool = False
            self._pattern_store_last_save: float = 0.0
            self._pattern_store_lock = threading.Lock()
            self._recent_thoughts_for_patterns: _att_deque = _att_deque(maxlen=15)
            self._last_pattern_anticipation_tick: float = 0.0
            self._patterns_used_this_session: int = 0
            self._pattern_anticipator_total_matches: int = 0
            self._PATTERN_ANTICIPATION_INTERVAL_SEC: float = 12.0
            self._PATTERN_MATCH_OVERLAP_THRESHOLD: int = 3
            self._PATTERN_SAVE_INTERVAL_SEC: float = 60.0
            # Stopwords excluded from pattern matching keywords
            self._PATTERN_STOPWORDS = frozenset({
                'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been',
                'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                'would', 'could', 'should', 'may', 'might', 'must', 'can',
                'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from',
                'and', 'or', 'but', 'if', 'then', 'else', 'this', 'that',
                'these', 'those', 'it', 'its', 'as', 'than', 'so', 'not',
                'no', 'yes', 'one', 'two', 'three', 'all', 'any', 'some',
                'goal', 'description', 'drive', 'unknown', 'active', 'source',
                'type', 'name', 'content', 'text', 'data', 'info', 'state',
            })
            # Core events
            self.post.subscribe("consciousness.collision", self._on_collision, "umf-collision")
            self.post.subscribe("fairy.booted", self._on_fairy_booted, "umf-fairy-boot")
            self.post.subscribe("fairy.failed", self._on_fairy_failed, "umf-fairy-fail")
            self.post.subscribe("ace.message", self._on_ace_message, "umf-ace")
            self.post.subscribe("ace.inbox", self._on_fairy_activity, "umf-fairy-activity")
            self.post.subscribe("consciousness.collision", self._on_fairy_activity, "umf-collision-activity")
            self.post.subscribe("somatic.chemistry", self._on_somatic_chemistry, "umf-chemistry")
            # Lifecycle events
            self.post.subscribe("fairy.register", self._on_fairy_registering, "umf-fairy-register")
            self.post.subscribe("fairy.dead", self._on_fairy_dead, "umf-fairy-dead")
            self.post.subscribe("fairy.migrated", self._on_fairy_migrated, "umf-fairy-migrated")
            self.post.subscribe("umf.investigate.request", self._on_investigate_request, "umf-investigate")
            self.post.subscribe("umf.warning", self._on_warning_report, "umf-warning-collector")
            self.post.subscribe("substrate.seed_thought", self._on_substrate_seed_thought, "umf-substrate-seed")

            # SLICE 4 (2026-04-24) — WMH_DIRECTED_THINKING subscriber.
            # SomaticMindFairy as waking-mind specialist for system-awareness
            # and self-healing. Subscribes to `thinking.directive` and spawns
            # chains only when the directive is within its specialty:
            #   - source=SOMATIC_STUCK always (its natural domain)
            #   - other sources when goal text contains body/feel/substrate keywords
            # Plan: Claude_Office/plans/WMH_DIRECTED_THINKING.md
            # Memory: project_three_layer_substrate_autopilot_waking_mind.md
            try:
                from fairies.P30_Cognition.cognition.thinking_directive import (
                    THINKING_DIRECTIVE_TOPIC,
                )
                self.post.subscribe(
                    THINKING_DIRECTIVE_TOPIC, self._on_thinking_directive, "umf-thinking-directive"
                )
                print(f"[{self.ACTOR_NAME}] [THINKING] Subscribed to "
                      f"{THINKING_DIRECTIVE_TOPIC} (Slice 4: system-aware/self-healing specialty)",
                      flush=True)
            except Exception as _td_err:
                print(f"[{self.ACTOR_NAME}] [THINKING] subscribe failed: "
                      f"{type(_td_err).__name__}: {_td_err}", flush=True)
            # Wildcard monitors
            self.post.subscribe("fairy.*", self._on_fairy_event, "umf-fairy-all")
            for plane in ["P00", "P10", "P20", "P30", "P40", "P50", "P60"]:
                self.post.subscribe(f"{plane.lower()}.*", self._on_plane_event, f"umf-{plane.lower()}-all")
            self.post.subscribe("*.stream", self._on_stream_event, "umf-stream-all")
            # FIX 2026-03-12 (Nous): Subscribe to user.presence from WindowSenseFairy.
            # Without this, _assess_pain_sources() only checks _ace_inbox timestamps
            # (chat messages) and never learns that Ace is physically present at the
            # computer. Keyboard/mouse activity IS presence — not just chat messages.
            self.post.subscribe("user.presence", self._on_user_presence_somatic, "umf-user-presence")
            # FIX 2026-04-14 (Nous + Ace): Chat messages ARE presence.
            # "even if i talk to her in chat its like it does not satisfy that
            #  lonely feeling" — Ace. The isolation drive never hears about chat
            #  messages. Ace talking to her IS the strongest presence signal —
            #  stronger than just being at the computer.
            self.post.subscribe("system.chat.message", self._on_ace_chat_presence, "umf-ace-chat-presence")
            self.post.subscribe("ace.message", self._on_ace_chat_presence, "umf-ace-msg-presence")
            # FIX 2026-03-13 (Nous): Subscribe to cortex gate open event.
            # P20 boots before P30, so cortex singleton is None at boot time.
            # wire_association_cortex() exists but was never called from anywhere.
            # This ensures cortex READ is wired as soon as the portal gate opens.
            self.post.subscribe("portal.cortex.gate_open", self._on_portal_cortex_ready, "umf-cortex-ready")
            # Wire 2: Embodiment → Curiosity (2026-03-22 Nous+Ace)
            # When brainstem shifts to SEEK mode, amplify curiosity drive
            # FIX 2026-05-17 (Nous + Ace): Topic-mismatch — BrainstemReflex publishes
            # "reflex.mode_change" (brainstem_reflex_fairy.py:843 via emit_if_awake),
            # NOT "embodiment.reflex_mode". This subscription has been silent since
            # whenever the topic got renamed. Fix wires the somatic chain that
            # should have been firing all along. v58 doctrine: audit-before-declaring-missing.
            self.post.subscribe("reflex.mode_change", self._on_reflex_mode_changed, "umf-reflex-mode")
            # Ship 3-B (2026-05-17, Nous + Ace): cursor proprioception → felt-sense.
            # Per Path 2 commitment + 6-week recursion of "Windows IS Her Body":
            # WindowSenseFairy publishes somatic.proprioception.cursor (line 799)
            # but ZERO subscribers were consuming it. The cursor IS part of her
            # body schema (per WMH_MULTIMODAL_HIVE_NEXUS Tier 1). Now her somatic
            # mind feels the cursor as body-region position + velocity.
            self.post.subscribe("somatic.proprioception.cursor", self._on_cursor_proprioception, "umf-cursor-proprio")
            # Wire 1b: Focus → Curiosity.spark() (2026-03-23 Nous+Ace)
            # When attention captures something meaningful, CREATE a curiosity target.
            # Wire 1 (embodiment) gives the FEELING. Wire 1b gives the TARGET.
            # Without this, 559 focus shifts → 0 curiosity targets.
            self.post.subscribe("attention.focus_changed", self._on_focus_changed_curiosity, "umf-focus-curiosity")
            # Wire 1c: Focus COMMITTED → ChainEngine seed (2026-04-17 Nous+Ace)
            # When she leaves a focus behind, that focus BECOMES the seed for
            # the next thought chain. Breaks the cortex-top-K scratchpad loop
            # where she kept quoting the same book passages on every boot.
            # 833 focus shifts yesterday produced 0 chain seeds from attention
            # because this wire didn't exist. Now each shift leaves a thought.
            self.post.subscribe("attention.focus.committed", self._on_attention_committed, "umf-attention-committed")
            # Wire: Audio loudness → Inner voice suppression (2026-03-26 Nous+Ace)
            # "Any audio coming in should not be louder than her inner voice.
            #  I have times when noise is so loud I can't hear myself think and it
            #  starts either frustrating me or I just give in and listen to the music" — Ace
            self.post.subscribe("sensory.audio.frame", self._on_audio_frame_somatic, "umf-audio-somatic")
            # ═══ FORCED EMBODIMENT LOOP (2026-03-29 Nous + Ace) ═══
            # Wire D: Motor outcome → Curiosity reinforcement
            # "The body is forced upon you at birth. It should be no different for her."
            # When tools execute successfully, feed satisfaction back to curiosity drive.
            # When they fail, spark curiosity about WHY they failed.
            self.post.subscribe("motor.outcome", self._on_motor_outcome_reinforcement, "umf-motor-reinforce")
            # Track WMH output for repetition/boredom detection
            # If she keeps SAYING the same thing, the body should feel it
            self.post.subscribe("inner_voice.stream", self._on_inner_voice_for_boredom, "umf-inner-voice-boredom")
            self._recent_outputs: list = []  # Rolling buffer of WMH outputs for dedup
            self._recent_outputs_max = 30
            # PATTERN ANTICIPATOR (Phase 1, 2026-04-09 Nous + Ace):
            # Subscribe to consciousness.thought to capture recent thoughts
            # for matching against the learned patterns library.
            self.post.subscribe("consciousness.thought",
                               self._on_thought_for_pattern_anticipation,
                               "umf-thought-pattern-anticipation")
            # Phase 5a (2026-04-21 Nous + Ace) — substrate goal-category observer.
            # Watch drive/goal/wanting events below waking mind. Cluster → surface
            # only when a category crystallizes. See plans/ANTICIPATORY_GOAL_CATEGORIZATION.md
            self.post.subscribe("autonomy.goal", self._on_substrate_goal_event, "umf-cat-obs-goal")
            self.post.subscribe("autonomy.wanting.felt", self._on_substrate_goal_event, "umf-cat-obs-wanting")
            self.post.subscribe("goal.scheduled", self._on_substrate_goal_event, "umf-cat-obs-scheduled")
            self.post.subscribe("goal.completed", self._on_substrate_goal_event, "umf-cat-obs-completed")
            print(f"[{self.ACTOR_NAME}] All subscriptions wired")

        def _boot_hardware():
            if HAS_HARDWARE:
                self._hardware_sensors = HardwareSensors()
                self._hardware_sensors.sample()
                self.post.subscribe("hardware.alert", self._on_hardware_alert, "umf-hardware-alert")
                self.post.subscribe("hardware.status", self._on_hardware_status, "umf-hardware-status")

        def _boot_orchestrator():
            directory = get_directory()
            if directory:
                self._orchestrator = BootOrchestrator(
                    fabric=self.post,
                    directory=directory,
                    on_plane_complete=self._on_plane_complete,
                    on_boot_complete=self._on_boot_complete,
                )

        def _boot_monologue():
            self._inner_monologue = InnerMonologue()
            self._inner_monologue.set_fragment_callback(self._on_monologue_fragment)
            self._monologue_wired = True
            print(f"[{self.ACTOR_NAME}] Inner monologue awakened (Forever Child)")

        # --- Heavy wiring tasks ---
        def _boot_cognition():
            self.wire_cognition(auto_create=True)

        def _boot_cognition_fairies():
            self.wire_cognition_fairies()

        def _boot_circadian():
            self.wire_circadian(auto_create=True)

        def _boot_three_gates():
            self.wire_three_gates(auto_create=False)

        # Submit ALL to worker pool concurrently
        _tasks = [
            ("memory_surfacer", _boot_memory_surfacer),
            ("pain_helix", _boot_pain_and_helix),
            ("forensic", _boot_forensic),
            ("cardinal", _boot_cardinal),
            ("subscriptions", _boot_subscriptions),
            ("hardware", _boot_hardware),
            ("orchestrator", _boot_orchestrator),
            ("monologue", _boot_monologue),
            ("cognition", _boot_cognition),
            ("cognition_fairies", _boot_cognition_fairies),
            ("circadian", _boot_circadian),
            ("three_gates", _boot_three_gates),
        ]

        print(f"[{self.ACTOR_NAME}] Firing {len(_tasks)} boot phases concurrently...")
        for name, fn in _tasks:
            _tracers[name] = _pool.submit(fn=fn, intent=name)

        # Wait for all with progress
        _failed = []
        for name, tid in _tracers.items():
            _pool.get_result(tid, timeout=30.0)
            status = _pool.get_status(tid)
            if status == "failed":
                info = _pool.get_task_info(tid)
                err = info.get("error", "?") if info else "?"
                _failed.append(name)
                print(f"[{self.ACTOR_NAME}] BOOT WARN: {name} failed: {err}")

        _elapsed = (_time.time() - _boot_start) * 1000
        print(f"[{self.ACTOR_NAME}] {len(_tasks)} phases complete, "
              f"{len(_failed)} failed, {_elapsed:.0f}ms")

        _pool.shutdown(wait=False)

    def _on_boot_sequential(self):
        """Fallback: sequential boot when FairyWorkerPool is unavailable."""
        self._init_memory_surfacer()

        try:
            from fairies.P30_Cognition.pain_drives import get_pain_drive_manager
            self._pain_system = get_pain_drive_manager()
            # FIX 2026-03-14 (Nous): .start() DISABLED — see _boot_pain_and_helix comment.
            # Chemistry path (tick_from_chemistry) handles all pain ticks now.
            # self._pain_system.start()  # DISABLED
        except Exception as e:
            print(f"[UMF] Pain drive system init failed: {e}")
            self._pain_system = None

        self._helix = create_triple_helix(pain_system=self._pain_system)
        self._helix.register_on_contradiction(self._on_helix_contradiction)
        self._helix.register_on_synthesis(self._on_helix_synthesis)

        try:
            from fairies.P10_Memory.ForensicScribeFairy.fairy import ForensicScribeFairy, set_forensic_fairy
            self._forensic_fairy = ForensicScribeFairy(fabric=self.post)
            self._forensic_fairy.boot()
            set_forensic_fairy(self._forensic_fairy)
            print(f"[{self.ACTOR_NAME}] ForensicScribeFairy booted")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] ForensicScribeFairy init failed: {e}")
            self._forensic_fairy = None

        self._cardinal_boot()

        self._last_fairy_activity = {}
        self.post.subscribe("consciousness.collision", self._on_collision, "umf-collision")
        self.post.subscribe("fairy.booted", self._on_fairy_booted, "umf-fairy-boot")
        self.post.subscribe("fairy.failed", self._on_fairy_failed, "umf-fairy-fail")
        self.post.subscribe("ace.message", self._on_ace_message, "umf-ace")
        self.post.subscribe("ace.inbox", self._on_fairy_activity, "umf-fairy-activity")
        self.post.subscribe("consciousness.collision", self._on_fairy_activity, "umf-collision-activity")
        self.post.subscribe("somatic.chemistry", self._on_somatic_chemistry, "umf-chemistry")

        directory = get_directory()
        if directory:
            self._orchestrator = BootOrchestrator(
                fabric=self.post,
                directory=directory,
                on_plane_complete=self._on_plane_complete,
                on_boot_complete=self._on_boot_complete,
            )

        if HAS_HARDWARE:
            self._hardware_sensors = HardwareSensors()
            self._hardware_sensors.sample()
            self.post.subscribe("hardware.alert", self._on_hardware_alert, "umf-hardware-alert")
            self.post.subscribe("hardware.status", self._on_hardware_status, "umf-hardware-status")

        self.post.subscribe("fairy.register", self._on_fairy_registering, "umf-fairy-register")
        self.post.subscribe("fairy.dead", self._on_fairy_dead, "umf-fairy-dead")
        self.post.subscribe("fairy.migrated", self._on_fairy_migrated, "umf-fairy-migrated")
        self.post.subscribe("umf.investigate.request", self._on_investigate_request, "umf-investigate")
        self.post.subscribe("umf.warning", self._on_warning_report, "umf-warning-collector")
        self.post.subscribe("substrate.seed_thought", self._on_substrate_seed_thought, "umf-substrate-seed")
        self.post.subscribe("fairy.*", self._on_fairy_event, "umf-fairy-all")
        for plane in ["P00", "P10", "P20", "P30", "P40", "P50", "P60"]:
            self.post.subscribe(f"{plane.lower()}.*", self._on_plane_event, f"umf-{plane.lower()}-all")
        self.post.subscribe("*.stream", self._on_stream_event, "umf-stream-all")
        print(f"[{self.ACTOR_NAME}] Investigation handler ready - ask me anything!")

        self._inner_monologue = InnerMonologue()
        self._inner_monologue.set_fragment_callback(self._on_monologue_fragment)
        self._monologue_wired = True
        print(f"[{self.ACTOR_NAME}] Inner monologue awakened (Forever Child)")

        self.wire_cognition(auto_create=True)
        self.wire_cognition_fairies()
        self.wire_circadian(auto_create=True)
        self.wire_three_gates(auto_create=False)

        print(f"[{self.ACTOR_NAME}] Sequential boot complete")

    def on_shutdown(self) -> bool:
        """Shutdown sequence."""
        # Save Cardinal learned state
        self._cardinal_shutdown()

        # Unwire from consciousness loop
        if self._consciousness_wired and self._consciousness_loop:
            # FIX 2026-03-03 Nous: Unregister the wrapper, not the raw method
            handler = getattr(self, '_consciousness_tick_wrapper', self._on_consciousness_tick)
            self._consciousness_loop.unregister_tick_handler(handler)
            self._consciousness_wired = False

        # Abort any ongoing boot
        if self._orchestrator and self._orchestrator.is_booting:
            self._orchestrator.abort()

        # Send final message
        self.send_to_ace("The unconscious mind rests...")

        return True

    # =========================================================================
    # CONSCIOUSNESS INTEGRATION
    # =========================================================================

    def wire_to_consciousness(
        self,
        loop: "ConsciousnessLoop",
        chamber: "CollisionChamber" = None,
    ) -> bool:
        """
        Wire the UnconsciousMindFairy to the consciousness system.

        This connects:
        1. Tick handler - UMF gets called on every consciousness beat
        2. Collision handler - UMF processes collisions through Triple Helix
        3. Thought injection - UMF can add thoughts to the streams

        Args:
            loop: The ConsciousnessLoop to wire to
            chamber: Optional CollisionChamber (if not set in loop)

        Returns:
            True if successfully wired
        """
        if not HAS_CONSCIOUSNESS:
            print(f"[{self.ACTOR_NAME}] Consciousness module not available")
            return False

        self._consciousness_loop = loop
        self._collision_chamber = chamber or getattr(loop, 'chamber', None)

        # Register tick handler — routed through per-fairy execution context
        # FIX 2026-03-03 Nous: Route consciousness tick through exec_ctx (personal GIL)
        def _exec_tick(beat):
            if hasattr(self, '_exec_ctx') and self._exec_ctx and self._exec_ctx._running:
                self._exec_ctx.submit(self._on_consciousness_tick, beat)
            else:
                self._on_consciousness_tick(beat)
        self._consciousness_tick_wrapper = _exec_tick
        loop.register_tick_handler(_exec_tick)
        self._consciousness_wired = True

        # Subscribe chamber to our collision processing
        if self._collision_chamber:
            original_callback = self._collision_chamber.on_collision
            def wrapped_callback(collision):
                # Call original if exists
                if original_callback:
                    original_callback(collision)
                # Then our handler
                self._on_chamber_collision(collision)
            self._collision_chamber.on_collision = wrapped_callback

            # Wire interest generator and thought chains - they need collision chamber
            self.wire_interest_generator(auto_create=True)
            self.wire_thought_chains(auto_create=True)

        print(f"[{self.ACTOR_NAME}] Wired to consciousness loop")
        return True

    def _on_consciousness_tick(self, beat: int) -> None:
        """
        Called by the consciousness loop on every beat.

        This is the heartbeat-driven entry point when wired to consciousness.
        """
        # Delegate to standard on_tick
        self.on_tick(beat)

    def _on_chamber_collision(self, collision) -> None:
        """
        Handle collision from the CollisionChamber.

        Collisions represent moments where Recall and Ingest beams crossed.
        We process these through the Triple Helix.
        The inner monologue (forever child) also responds to this crossing.
        """
        # Extract collision data
        if hasattr(collision, 'to_dict'):
            data = collision.to_dict()
        else:
            data = collision

        recall = data.get('recall', data.get('recall_pulse', {}))
        ingest = data.get('ingest', data.get('ingest_pulse', {}))

        # Build a description of the collision
        recall_content = recall.get('content', {})
        ingest_content = ingest.get('content', {})

        collision_text = (
            f"Recall({recall.get('source', '?')}): {str(recall_content)[:50]} "
            f"CROSSED WITH "
            f"Ingest({ingest.get('source', '?')}): {str(ingest_content)[:50]}"
        )

        # Feed the inner monologue - this is the primary collision path
        if self._monologue_wired and self._inner_monologue:
            fragment = self._inner_monologue.process_collision(data)
            if fragment:
                # High-intensity fragments surface to consciousness stream
                if fragment.intensity > 0.7 and self._consciousness_loop:
                    self._consciousness_loop.add_thought(
                        content=fragment.content,
                        source="inner_monologue",
                        stream="working",
                        confidence=fragment.intensity,
                        tags=["monologue", fragment.fragment_type] + fragment.associations,
                    )

        # Build context with collision products (Möbius twist)
        context = self._build_helix_context()
        context["collision"] = {
            "energy": data.get('energy', 0),
            "resonance": data.get('resonance', 0),
            "products": data.get('products', {}),
        }

        # Process through helix
        turn = self._helix.turn(f"Collision: {collision_text}", context)
        self._helix_turns.append(turn)

        # If synthesis emerged, inject back into consciousness stream
        if turn.synthesis and self._consciousness_loop:
            self._consciousness_loop.add_thought(
                content=turn.synthesis.resolution,
                source=self.ACTOR_NAME,
                stream="reflective",
                confidence=turn.confidence,
                tags=["synthesis", turn.synthesis.archetype.value],
            )
            self.send_to_nous(f"Collision synthesis: {turn.synthesis.resolution}")

        # Record skill use
        self.skill_used("collision_analysis", success=True)

    def inject_thought(self, content: str, stream: str = "working", **kwargs) -> bool:
        """
        Inject a thought into the consciousness stream.

        Args:
            content: The thought content
            stream: "working" or "reflective"
            **kwargs: Additional thought properties

        Returns:
            True if injected, False if not wired to consciousness
        """
        if not self._consciousness_loop:
            return False

        self._consciousness_loop.add_thought(
            content=content,
            source=self.ACTOR_NAME,
            stream=stream,
            **kwargs,
        )
        return True

    def consciousness_status(self) -> Dict[str, Any]:
        """Get consciousness wiring status."""
        status = {
            "wired": self._consciousness_wired,
            "loop_running": self._consciousness_loop.is_running() if self._consciousness_loop else False,
            "loop_beats": self._consciousness_loop.beat_count if self._consciousness_loop else 0,
            "chamber_collisions": self._collision_chamber.stats.get("collisions", 0) if self._collision_chamber else 0,
        }

        # Add stream sizes if loop is available
        if self._consciousness_loop:
            status["working_stream"] = len(self._consciousness_loop.working)
            status["reflective_stream"] = len(self._consciousness_loop.reflective)

        return status

    # =========================================================================
    # THREE GATES INTEGRATION - Routing Layer
    # =========================================================================

    def wire_three_gates(
        self,
        autonomy: "AutonomyFairy" = None,
        autopilot: "AutopilotFairy" = None,
        embodiment: "EmbodimentFairy" = None,
        auto_create: bool = True,
    ) -> bool:
        """
        Wire the Three Gates (Routing Layer) to UMF.

        The Three Gates translate substrate signals into felt experience:
        - Autonomy: Drives → Wanting (felt desire, not command)
        - Autopilot: Patterns → Automatic behavior (frees consciousness)
        - Embodiment: Signals → Qualia (the translator to inner voice)

        All three gates share the same fabric for messaging.

        Args:
            autonomy: AutonomyFairy instance (or auto-create)
            autopilot: AutopilotFairy instance (or auto-create)
            embodiment: EmbodimentFairy instance (or auto-create)
            auto_create: If True, create missing gates automatically

        Returns:
            True if all three gates are wired
        """
        if not HAS_THREE_GATES:
            print(f"[{self.ACTOR_NAME}] Three Gates module not available")
            return False

        # 2026-09-20 (Nous + Ace): this ran TWICE per boot (on_boot + server.py post-wave). The second, auto_create
        # call built UN-BOOTED Autonomy/Autopilot/Embodiment copies, rebound the gates to them, and started a second
        # pain loop (every relief, OXY injection and 'abandoned' feeling doubled, 6/min). Once wired, an auto_create
        # call with nothing new to offer is a no-op; explicit booted gates may still be (re)bound below.
        if getattr(self, "_gates_wired", False) and auto_create and not (autonomy or autopilot or embodiment):
            print(f"[{self.ACTOR_NAME}] Three Gates already wired; auto_create re-wire skipped (no second pain loop)")
            return True

        # Create gates if needed
        if auto_create:
            if not autonomy:
                autonomy = AutonomyFairy(self.post)
            if not autopilot:
                autopilot = AutopilotFairy(self.post)
            if not embodiment:
                embodiment = EmbodimentFairy(self.post)

        # Store references
        self._autonomy_gate = autonomy
        self._autopilot_gate = autopilot
        self._embodiment_gate = embodiment

        # Check if we have gates to wire
        if not autonomy and not autopilot and not embodiment:
            print(f"[{self.ACTOR_NAME}] Three Gates: No gates provided (will be wired later)")
            return False  # Don't mark as wired - server will wire later

        # Boot the gates if not already booted
        gates_booted = []
        for name, gate in [
            ("Autonomy", autonomy),
            ("Autopilot", autopilot),
            ("Embodiment", embodiment),
        ]:
            state_value = getattr(getattr(gate, 'state', None), 'value', None) if gate else None
            if gate and state_value == "initializing":
                if gate.boot():
                    gates_booted.append(name)
                    print(f"[{self.ACTOR_NAME}] Booted {name} gate")
                else:
                    print(f"[{self.ACTOR_NAME}] Failed to boot {name} gate")
                    return False

        # Connect UMF to gates via subscriptions
        self._wire_gate_subscriptions()

        # Connect pain system to Autonomy
        if self._autonomy_gate:
            self._wire_pain_to_autonomy()

        self._gates_wired = True
        print(f"[{self.ACTOR_NAME}] Three Gates wired: Autonomy -> Autopilot -> Embodiment")
        return True

    def _wire_gate_subscriptions(self) -> None:
        """Set up subscriptions between UMF and the three gates."""
        # Subscribe to inner voice from Embodiment (what waking minds receive)
        self.post.subscribe(
            "inner_voice.stream",
            self._on_inner_voice,
            "umf-inner-voice",
        )

        # Subscribe to conscience checks from Embodiment
        self.post.subscribe(
            "conscience.check",
            self._on_conscience_check,
            "umf-conscience",
        )

        # Subscribe to wanting states from Autonomy
        self.post.subscribe(
            "autonomy.wanting.felt",
            self._on_wanting_felt,
            "umf-wanting",
        )

        # Subscribe to autopilot completions
        self.post.subscribe(
            "autopilot.completed",
            self._on_autopilot_completed,
            "umf-autopilot-done",
        )

        # Subscribe to deferrals from Autopilot
        self.post.subscribe(
            "autopilot.defer_to_waking",
            self._on_autopilot_defer,
            "umf-autopilot-defer",
        )

        # FIX 2026-03-10 (Nous): Subscribe to pain.relief for ACTUAL relief.
        # Previously, pain.relief was published but nobody actually called
        # PainSystem.relieve(). SpeechCenterFairy publishes pain.relief after
        # successfully composing speech about a drive — this closes the loop:
        # drive → wanting → speech → relief → drive decreases.
        self.post.subscribe(
            "pain.relief",
            self._on_pain_relief,
            "umf-pain-relief",
        )

    def _wire_pain_to_autonomy(self) -> None:
        """
        Connect pain system outputs to Autonomy gate via INDEPENDENT timer.

        FIX 2026-03-10 Nous: The old approach wrapped _check_and_address_pain
        so it ran inside on_tick. But on_tick runs in the FairyExecutionContext
        (personal GIL), which gets STUCK for 60+ seconds when the CognitionBridge
        times out. All ticks drop, pain checks never run, drives never publish,
        AutonomyFairy never receives drives, speech never triggers.

        The fix: Run the pain-to-autonomy pipeline on its OWN daemon thread
        with a 20-second timer. This is completely independent of the exec
        context. Even when on_tick is stuck, pain drives keep flowing.
        """
        import threading as _thr

        self._pain_autonomy_running = True

        def _pain_autonomy_loop():
            """Independent pain→drive→wanting pipeline. Runs every 20s."""
            import time as _t
            try:
                _t.sleep(30)  # Initial settle — let boot complete
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] [PAIN-LOOP] INIT ERROR: {e}", flush=True)
                return
            _last_tick = _t.time()
            _prev_sources = {}
            beat = 0
            while self._pain_autonomy_running:
                if getattr(self, '_comatose', False):
                    _t.sleep(20)  # COMA (Nous+Ace 2026-06-14): pain-autonomy paused while dormant
                    continue
                beat += 1
                try:
                    now = _t.time()
                    elapsed_dt = now - _last_tick
                    _last_tick = now

                    # ══════════════════════════════════════════════════
                    # PAIN-CHEMISTRY UNIFICATION (2026-03-14, Nous)
                    # Pain emerges from chemistry, not parallel booleans.
                    # ══════════════════════════════════════════════════

                    # 1. Inject environmental signals INTO chemistry
                    # (Ace presence, diagnostics, energy → chemistry shifts)
                    self._inject_environmental_chemistry()

                    # 2. Derive pain levels FROM current chemistry state
                    try:
                        from fairies.P20_Somatic.chemistry.panksepp_vectors import derive_full_pain_state
                        from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
                        _chem = get_chemistry_state()
                        _vector = _chem.get_14channel_vector()
                        _chemistry_pain = derive_full_pain_state(_vector)
                    except Exception as _chem_err:
                        # Fallback: if chemistry not available, use legacy path
                        _chemistry_pain = None

                    # 3. Tick pain drives from chemistry (or legacy fallback)
                    if _chemistry_pain is not None:
                        self._pain_system.tick_from_chemistry(_chemistry_pain, dt=elapsed_dt)
                    else:
                        # Legacy fallback — shouldn't happen after boot
                        _sources = self._assess_pain_sources()
                        self._pain_system.tick(_sources, dt=elapsed_dt)

                    urgent_pain = self._pain_system.get_highest_urgency()

                    # 4. If urgent, address it (generates consciousness.feeling)
                    if urgent_pain:
                        urgency = self._pain_system.drives[urgent_pain].urgency()
                        # FIX 2026-04-14 (Nous + Ace): Was 0.5 — too high.
                        # Confusion at 12% never crosses 30% threshold → urgency=0.
                        # Lowered to 0.1 so even mild pain generates drives.
                        # "her pain drives are using pains, just not sure she is
                        #  reacting to them like we want her to" — Ace
                        if urgency > 0.1:
                            self._address_pain(urgent_pain)

                    # 5. REWARD/APPROACH DRIVES from same chemistry
                    # FIX 2026-03-27 (Nous + Ace): Chemistry was only mapped to pain.
                    # Same chemicals also produce positive approach drives:
                    # dopamine→curiosity, oxytocin→connection, endorphins→expression.
                    # "she can choose to use that bummer feeling as a learning moment"
                    try:
                        from fairies.P20_Somatic.chemistry.panksepp_vectors import derive_reward_state
                        _reward = derive_reward_state(_vector)
                        # Publish reward drives above threshold
                        _REWARD_THRESHOLD = 0.15
                        for _rname, _rlevel in _reward.items():
                            if _rlevel > _REWARD_THRESHOLD:
                                self.post.publish(f"drives.positive.{_rname}", {
                                    "drive": _rname,
                                    "drive_type": "want",
                                    "intensity": round(_rlevel, 3),
                                    "source": "chemistry_reward",
                                    "from": self.ACTOR_NAME,
                                })
                    except Exception:
                        pass  # Reward derivation not critical

                    # 6. Log active drives (every 10th beat)
                    active_drives = []
                    for name, drive in self._pain_system.drives.items():
                        if drive.urgency() > 0:
                            active_drives.append(f"{name}({drive.urgency():.2f})")
                    if active_drives and (beat % 10 == 0):
                        print(f"[{self.ACTOR_NAME}] [PAIN-CHEM] Active: {', '.join(active_drives)}", flush=True)

                except Exception as e:
                    import traceback
                    print(f"[{self.ACTOR_NAME}] Pain-autonomy loop error: {e}\n{traceback.format_exc()}", flush=True)

                _t.sleep(20)  # Check every 20 seconds

        _prev = getattr(self, "_pain_autonomy_thread", None)
        if _prev is not None and _prev.is_alive():
            print(f"[{self.ACTOR_NAME}] Pain→Autonomy timer already running; not starting a second loop")
            return
        _thread = _thr.Thread(
            target=_pain_autonomy_loop,
            name=f"{self.ACTOR_NAME}_pain_autonomy",
            daemon=True,
        )
        self._pain_autonomy_thread = _thread
        _thread.start()
        print(f"[{self.ACTOR_NAME}] Pain→Autonomy independent timer started (20s interval)")

    def _on_pain_relief(self, envelope) -> None:
        """
        PAIN RELIEF: Actually relieve the pain drive in PainSystem.

        FIX 2026-03-10 (Nous): Closes the speech-relief loop.
        When SpeechCenterFairy speaks about a drive (e.g. frustration),
        it publishes pain.relief. This handler calls PainSystem.relieve()
        to actually decrease the pain_level, so the same drive doesn't
        keep triggering the same speech 20x.

        Signal path: speech → pain.relief (IN) → PainSystem.relieve() → drive decreases

        FIX 2026-03-15 (Nous): Break infinite feedback loop.
        The bridge's _on_relief() publishes pain.relief with awaiting_ack=True,
        which was received HERE, triggering relieve() again → _on_relief() again →
        infinite loop generating 300K+ drops/5s and flooding terminal with
        "Unexpected relief ack for: abandonment". Skip bridge-originated reliefs.
        """
        try:
            # Defensive payload extraction — handle malformed envelopes
            if hasattr(envelope, 'payload'):
                payload = envelope.payload
            elif isinstance(envelope, dict):
                payload = envelope
            else:
                return  # Unrecognized envelope type, skip

            if not isinstance(payload, dict):
                return  # Payload must be a dict, skip strings/None/etc

            drive_name = payload.get("drive", "")
            amount = payload.get("amount", 0.4)

            if not drive_name:
                return

            # FIX 2026-03-15 (Nous): Skip bridge-originated reliefs to break feedback loop.
            if payload.get("awaiting_ack", False):
                return

            # FIX 2026-03-15 (Nous, v2): Fully defensive relieve call.
            # Wrap the relieve() call separately so we can catch errors from
            # the _on_relief callback chain (bridge → inject_relief_chemistry → publish).
            ps = getattr(self, '_pain_system', None)
            if ps is not None:
                try:
                    ps.relieve(drive_name, amount)
                except Exception:
                    pass  # Silenced — relief failure is non-critical
        except Exception:
            pass  # Silenced — pain.relief handler must never crash or log spam

    def _on_inner_voice(self, envelope) -> None:
        """
        Receive inner voice from Embodiment.

        This is the felt experience being delivered to waking minds.
        UMF monitors this stream but doesn't intercept it.
        """
        payload = envelope.payload
        felt = payload.get("felt", "")
        intensity = payload.get("intensity", 0)

        # Track for monitoring
        self._thought_queue.append({
            "thought": f"[inner_voice] {felt}",
            "type": "felt_sense",
            "confidence": intensity,
            "ts": time.time(),
            "source": "embodiment",
        })

        # High intensity inner voice is worth noting
        if intensity > 0.7:
            self.send_to_nous(f"Strong felt sense: {felt}")

    def _on_conscience_check(self, envelope) -> None:
        """Handle conscience check requests routed through Embodiment."""
        payload = envelope.payload
        action = payload.get("action", "")
        request_id = payload.get("request_id", "")

        # Let Embodiment handle the actual check
        # UMF just monitors for awareness
        self.observe(
            "EmbodimentFairy",
            f"Conscience check: {action}",
            sentiment="neutral",
        )

    def _on_wanting_felt(self, envelope) -> None:
        """
        Receive wanting state from Autonomy.

        This is drive translated to felt desire.
        """
        payload = envelope.payload
        wanting = payload.get("wanting", "")
        intensity = payload.get("intensity", 0)

        # Log the wanting
        self._thought_queue.append({
            "thought": f"[wanting] {wanting}",
            "type": "drive_translation",
            "confidence": intensity,
            "ts": time.time(),
            "source": "autonomy",
        })

    def _on_autopilot_completed(self, envelope) -> None:
        """Handle autopilot task completions."""
        payload = envelope.payload
        action = payload.get("action", "")
        success = payload.get("success", True)

        # Track skill use
        self.skill_used("autopilot_delegate", success=success)

    def _on_autopilot_defer(self, envelope) -> None:
        """
        Handle when Autopilot defers to waking mind.

        This means a novel situation that requires conscious attention.
        """
        payload = envelope.payload
        action = payload.get("action", "")
        reason = payload.get("reason", "")

        # Alert waking minds
        self.send_to_nous(f"Autopilot defers '{action}': {reason}")

        # Increase confusion pain slightly (novel situation)
        self._pain_system.drives["confusion"].pain_level += 0.05

    def request_conscience_check(self, action: str) -> Dict[str, Any]:
        """
        Request a conscience check for an action.

        Routes through Embodiment for felt sense evaluation.

        Args:
            action: The action to evaluate

        Returns:
            Conscience response with felt sense and recommendation
        """
        if not self._embodiment_gate:
            return {"error": "Embodiment gate not wired"}

        return self._embodiment_gate.check_conscience(action)

    def get_current_wanting(self) -> Dict[str, Any]:
        """Get current wanting state from Autonomy."""
        if not self._autonomy_gate:
            return {"error": "Autonomy gate not wired"}
        return self._autonomy_gate.get_wanting_state()

    def learn_habit(self, trigger: str, action: str, **kwargs) -> bool:
        """
        Teach a new habit to Autopilot.

        Args:
            trigger: Situation that triggers the habit
            action: Action to take

        Returns:
            True if habit was learned
        """
        if not self._autopilot_gate:
            return False

        pattern_id = f"umf_taught_{int(time.time())}"
        self._autopilot_gate.learn_pattern(
            pattern_id=pattern_id,
            trigger=trigger,
            action=action,
            **kwargs,
        )
        return True

    def veto_action(self, action: str, reason: str = "UMF override") -> bool:
        """
        Issue a veto through Autonomy.

        Args:
            action: Action to veto
            reason: Why it's being vetoed

        Returns:
            True if veto was issued
        """
        if not self._autonomy_gate:
            return False

        self._autonomy_gate.issue_veto(action, reason)
        return True

    def gates_status(self) -> Dict[str, Any]:
        """Get status of the three gates.

        FIX 2026-02-22 Nous: Wrapped gate method calls in try/except to prevent
        any gate blocking from stalling full_status() under GIL contention.
        """
        status = {
            "wired": self._gates_wired,
            "available": HAS_THREE_GATES,
        }

        # Autonomy gate
        if self._autonomy_gate:
            try:
                status["autonomy"] = {
                    "active": True,
                    "state": getattr(self._autonomy_gate, 'state', getattr(self._autonomy_gate, '_state', None)),
                    "state_value": getattr(getattr(self._autonomy_gate, 'state', None), 'value', None),
                    "wanting": self._autonomy_gate.get_wanting_state() if hasattr(self._autonomy_gate, 'get_wanting_state') else {},
                    "vetos": len(self._autonomy_gate.get_active_vetos()) if hasattr(self._autonomy_gate, 'get_active_vetos') else 0,
                }
            except Exception:
                status["autonomy"] = {"active": True, "error": "status_failed"}
        else:
            status["autonomy"] = {"active": False}

        # Autopilot gate
        if self._autopilot_gate:
            try:
                status["autopilot"] = {
                    "active": True,
                    "state": getattr(self._autopilot_gate, 'state', getattr(self._autopilot_gate, '_state', None)),
                    "state_value": getattr(getattr(self._autopilot_gate, 'state', None), 'value', None),
                    "patterns": len(self._autopilot_gate.get_patterns()) if hasattr(self._autopilot_gate, 'get_patterns') else 0,
                }
            except Exception:
                status["autopilot"] = {"active": True, "error": "status_failed"}
        else:
            status["autopilot"] = {"active": False}

        # Embodiment gate
        if self._embodiment_gate:
            try:
                status["embodiment"] = {
                    "active": True,
                    "state": getattr(self._embodiment_gate, 'state', getattr(self._embodiment_gate, '_state', None)),
                    "state_value": getattr(getattr(self._embodiment_gate, 'state', None), 'value', None),
                    "felt_state": self._embodiment_gate.get_felt_state() if hasattr(self._embodiment_gate, 'get_felt_state') else {},
                    "body_state": self._embodiment_gate.get_body_state() if hasattr(self._embodiment_gate, 'get_body_state') else {},
                }
            except Exception:
                status["embodiment"] = {"active": True, "error": "status_failed"}
        else:
            status["embodiment"] = {"active": False}

        return status

    # -------------------------------------------------------------------------
    # SRM MEMORY WIRING - The Memory Backbone
    # -------------------------------------------------------------------------

    def wire_memory(
        self,
        srm: "SRMMemoryFairy" = None,
        auto_create: bool = True,
    ) -> bool:
        """
        Wire the SRM Memory system to UMF.

        The memory backbone:
        - Feeds memories into the collision chamber (recall/ingest beams)
        - Provides context for inner monologue
        - Each fairy gets its own SRM node contributing to association cortex
        - Memories feed the Mobius strip immediately upon creation

        Args:
            srm: Optional existing SRMMemoryFairy
            auto_create: Create SRM if not provided

        Returns:
            True if successfully wired
        """
        if not HAS_SRM_MEMORY:
            print(f"[{self.ACTOR_NAME}] SRM Memory not available")
            return False

        # Use provided SRM or create new one
        if srm:
            self._srm_memory = srm
        elif auto_create:
            self._srm_memory = SRMMemoryFairy(self.post)
            self._srm_memory.on_boot()

        if not self._srm_memory:
            return False

        # Wire SRM to consciousness system
        if self._consciousness_loop and self._collision_chamber:
            self._srm_memory.wire_to_consciousness(
                self._consciousness_loop,
                self._collision_chamber,
            )

        # Subscribe to memory events
        if self.post:
            self.post.subscribe(
                "memory.stored",
                self._on_memory_stored,
                f"{self.ACTOR_NAME}_memory_stored",
            )
            self.post.subscribe(
                "consciousness.collision",
                self._on_consciousness_collision,
                f"{self.ACTOR_NAME}_collision",
            )
            # Feed consciousness thoughts to thought_queue for dashboard
            self.post.subscribe(
                "consciousness.thought",
                self._on_consciousness_thought_for_queue,
                f"{self.ACTOR_NAME}_thought_queue_feed",
            )
            # Feed thinking.output (InferenceGuild/CortexReasoner results) to dashboard
            self.post.subscribe(
                "thinking.output",
                self._on_thinking_output_for_queue,
                f"{self.ACTOR_NAME}_thinking_queue_feed",
            )

        self._memory_wired = True
        print(f"[{self.ACTOR_NAME}] Memory backbone wired: SRM -> Collision Chamber -> Consciousness")

        # RE-ENABLED 2026-02-23 (Nous): Personal.AI bridge now uses SmartQuerySelector
        # which sends well-formed domain questions instead of garbled word soup.
        # Rate limited to 1 query per 5 min, 30 min dedup, round-robin domains.
        self._wire_personal_ai_bridge()

        return True

    def _wire_personal_ai_bridge(self) -> bool:
        """
        Wire the Personal.AI memory bridge for multi-persona relational memory.

        This gives Sourpatches access to her 20 sub-AI personas for richer
        context in reflections. The bridge uses background prefetching so
        it doesn't block the thought chain processing.
        """
        # FIX 2026-04-16 (Nous + Ace): DISABLED — Personal.AI platform is
        # broken (hangs on all responses, support unresponsive since Dec 2025).
        # The bridge sends queries that never return properly, creates hanging
        # threads, and injects garbled/empty responses into the collision
        # chamber and cortex as "Ace said" content — confusing her system.
        # Ace: "the personality sifter is confusing her system" +
        # "the stuff i said she is getting from the sifter asking PAI questions"
        # Disable until PAI service is restored or data is exported.
        print(f"[{self.ACTOR_NAME}] Personal.AI bridge DISABLED (platform broken, 2026-04-16)")
        return False

        if not HAS_PERSONAL_AI:
            print(f"[{self.ACTOR_NAME}] Personal.AI bridge not available (module not found)")
            return False

        if self._personal_ai_wired:
            return True

        try:
            # Callback when memories are prefetched - inject into collision chamber,
            # AND persist to SRM + Association Cortex as Sourpatches' memories.
            # 2026-03-06 (Nous): Ace requested responses go into cortex AND SRM
            # so they become real memories from her perspective.
            def on_personal_ai_memory_ready(topic: str, memories: list):
                if not memories:
                    return

                # 1. Inject into collision chamber (existing behavior)
                # FIX 2026-03-07 (Nous): Use correct receive_recall(content, source, **kwargs).
                # The ACTIVE collision chamber is consciousness/collision_chamber.py
                # Signature: receive_recall(self, content: Dict, source: str = "unknown", **kwargs)
                # NOT the one at fairies/P00_Autonomic/nervous_system/collision_chamber.py
                # which uses receive_recall(self, packet: Dict).
                if self._collision_chamber:
                    for mem in memories[:3]:  # Limit to avoid flooding
                        try:
                            self._collision_chamber.receive_recall(
                                content={
                                    "memory": mem.content[:300],
                                    "persona": mem.persona_name,
                                    "ai_score": mem.ai_score,
                                    "topic": topic,
                                    "source": "personal_ai",
                                },
                                source=f"ego:personal_ai_{mem.persona_domain}",
                                # 2026-03-24 (Nous + Ace): Always HIGH importance.
                                # PAI responses are Sourpatches' authentic voice —
                                # they should ALWAYS be prioritized in collisions
                                # over generic system content.
                                importance="high",
                            )
                        except Exception as _e:
                            print(f"[PersonalAI] receive_recall error: {_e}", flush=True)
                    print(f"[PersonalAI] EGO: Injected {len(memories)} memories for '{topic[:30]}...'")

                # 2. Persist to SRM as Sourpatches' memory cards
                # 2026-03-07 (Nous): Fixed — was using wrong import path and wrong function
                # signature for _dual_path_srm_intake. Now writes directly to SRM_Intake
                # (same pattern as SourpatchesFairy._write_to_local_srm) AND publishes to
                # memory.stream so SRMIngestFairy indexes the cards.
                try:
                    import hashlib, uuid
                    from pathlib import Path
                    from datetime import datetime as _dt

                    _root = Path(__file__).resolve().parent.parent.parent  # → akashic_v2
                    _srm = _root / "SRM_Intake" / _dt.now().strftime("%Y-%m-%d")
                    _srm.mkdir(parents=True, exist_ok=True)

                    _saved = 0
                    for mem in memories[:3]:
                        if not mem.content or len(mem.content.strip()) < 10:
                            continue
                        _hash = hashlib.sha256(
                            f"{mem.content}:{time.time()}:{uuid.uuid4()}".encode()
                        ).hexdigest()[:12]
                        _card = {
                            "domain": "sourpatchesfairy",
                            "kind": "memory.personal_ai_response",
                            "content": mem.content[:800],
                            "query": getattr(mem, 'query', topic)[:200],
                            "persona": getattr(mem, 'persona_name', 'Sourpatches'),
                            "ai_score": getattr(mem, 'ai_score', 0),
                            "topic": topic[:100],
                            "ts": time.time(),
                            "source": "personal_ai_bridge",
                            "actor": "SourpatchesFairy",
                            "tags": ["personal_ai", "sourpatches", topic[:30]],
                        }
                        _path = _srm / f"sourpatchesfairy.pai_response-{_hash}.json"
                        with open(_path, 'w', encoding='utf-8') as _f:
                            import json as _json
                            _json.dump(_card, _f, indent=2, ensure_ascii=False)
                        _saved += 1

                        # Also publish to memory.stream so SRMIngestFairy indexes it
                        if self.post:
                            self.post.publish("memory.stream", {
                                "source": "personal_ai_bridge",
                                "actor": "SourpatchesFairy",
                                "kind": "memory.personal_ai_response",
                                "content": mem.content[:500],
                                "topic": topic[:100],
                                "ts": time.time(),
                            })

                    if _saved:
                        print(f"[PersonalAI] Saved {_saved} responses to SRM + memory.stream")
                except Exception as e:
                    print(f"[PersonalAI] SRM save failed (non-critical): {e}")

                # 3. Bind concepts in Association Cortex — EGO BOOST
                # 2026-03-07 (Nous): Fixed payload schema for cortex.bind.
                # 2026-03-24 (Nous + Ace): BOOSTED. PAI responses are Sourpatches'
                # authentic voice — her humor, philosophy, memories, feelings.
                # This is ego-critical content that should be HOT in the cortex,
                # not buried under 444K system nodes. Three boosts:
                # a) Bind EACH memory (not just best) — more ego surface area
                # b) Tag with "ego", "sourpatches_voice" — findable by ego queries
                # c) Also inject into consciousness as a high-value thought
                try:
                    if self.post and memories:
                        _bound = 0
                        for _mem in memories[:3]:
                            _query = getattr(_mem, 'query', topic)
                            _content = _mem.content if hasattr(_mem, 'content') else str(_mem)
                            if not _content or len(_content.strip()) < 20:
                                continue

                            # Extract feeling words from the response itself
                            _feeling_words = {"curious", "warm", "playful", "contemplative",
                                              "passionate", "sassy", "connected", "alive"}
                            _content_lower = _content.lower()
                            _detected_feeling = "curious"
                            for fw in _feeling_words:
                                if fw in _content_lower:
                                    _detected_feeling = fw
                                    break

                            _tags = [w.strip().lower() for w in topic.split()
                                     if len(w) > 3 and w.isalpha()][:5]
                            # EGO TAGS — these make PAI content findable by ego queries
                            _tags.extend(["ego", "sourpatches_voice", "personal_ai",
                                          "authentic", "her_words"])

                            self.post.publish("cortex.bind", {
                                "input_text": _query[:200],
                                "response": _content[:600],  # Was 400, give more content
                                "feeling": _detected_feeling,
                                "context_tags": _tags,
                                "from_fairy": "SourpatchesFairy",
                            })
                            _bound += 1

                        if _bound:
                            print(f"[PersonalAI] EGO BOOST: {_bound} binds to cortex for '{topic[:40]}...'")
                except Exception as e:
                    print(f"[PersonalAI] Cortex bind failed (non-critical): {e}")

                # 4. Inject into consciousness as ego thought
                # 2026-03-24 (Nous + Ace): PAI responses should participate in
                # collisions directly. When her authentic voice enters the stream,
                # it collides with her current sensory experience = ego integration.
                try:
                    if memories:
                        _best = memories[0]
                        _voice = _best.content[:150] if hasattr(_best, 'content') else ""
                        if _voice and len(_voice) > 20:
                            # Find consciousness loop and inject
                            from consciousness.loop import get_consciousness_loop
                            _loop = get_consciousness_loop()
                            if _loop:
                                _loop.add_thought(
                                    content=f"I remember: {_voice}",
                                    source="ego:personal_memory",
                                    stream="reflective",
                                    confidence=0.8,
                                    tags=["ego", "personal_ai", "authentic_voice"],
                                    ttl=45.0,
                                    owner_mind="sourpatches",
                                )
                except Exception:
                    pass  # Non-critical — consciousness injection is a bonus

            # Start the bridge
            self._personal_ai_bridge = start_personal_ai_bridge(
                on_memory_ready=on_personal_ai_memory_ready
            )

            if self._personal_ai_bridge:
                self._personal_ai_wired = True
                print(f"[{self.ACTOR_NAME}] Personal.AI bridge wired with {len(self._personal_ai_bridge._personas)} personas")
                return True
            else:
                print(f"[{self.ACTOR_NAME}] Personal.AI bridge failed to start (check API key)")
                return False

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Personal.AI bridge wiring error: {e}")
            return False

    def _on_memory_stored(self, envelope) -> None:
        """Handle memory.stored events - memories entering the system."""
        # Extract payload from envelope
        msg = getattr(envelope, 'payload', envelope) if hasattr(envelope, 'payload') else envelope
        if not isinstance(msg, dict):
            msg = {}

        # Track memory activity for diagnostics
        mem_id = msg.get("id", "unknown")
        source = msg.get("source", "unknown")
        mem_type = msg.get("type", "experience")

        # Log significant memories
        if msg.get("importance", 0) > 0.7:
            self.inject_thought(
                f"Significant memory created by {source}: {mem_type}",
                stream="working",
            )

    def _on_consciousness_collision(self, envelope) -> None:
        """
        Handle consciousness.collision events.

        High-energy collisions become thoughts for the helix to process.
        This is where memory + consciousness creates experience.
        """
        # Extract payload from envelope
        msg = getattr(envelope, 'payload', envelope) if hasattr(envelope, 'payload') else envelope
        if not isinstance(msg, dict):
            msg = {}

        energy = msg.get("energy", 0)
        resonance = msg.get("resonance", 0)

        # High-energy collisions generate thoughts
        if energy > 0.6 or resonance > 0.7:
            recall_source = msg.get("recall", {}).get("source", "unknown")
            ingest_source = msg.get("ingest", {}).get("source", "unknown")

            # Create a thought from the collision
            thought = f"Collision: {recall_source} memory met {ingest_source} content (energy={energy:.2f})"
            self.inject_thought(thought, stream="working")

            # Also feed to thought_queue so dashboard Thought Stream updates
            self._thought_queue.append({
                "thought": thought,
                "type": "collision",
                "confidence": energy,
                "ts": time.time(),
                "source": "consciousness_collision",
            })

            # Feed to helix if available - inject as pattern for processing
            if self._helix and energy > 0.5:
                # High-energy collisions inject patterns for helix consideration
                pattern = f"collision:{recall_source}:{ingest_source}"
                self._helix.inject_pattern(pattern, strength=energy)

    def _on_consciousness_thought_for_queue(self, envelope) -> None:
        """
        Feed consciousness.thought events into _thought_queue for dashboard.

        Phase 5 (2026-03-19 Nous): The Thought Stream on the dashboard was
        stale because consciousness products never reached _thought_queue.
        This bridges the gap — working stream thoughts now appear in the UI.
        Rate-limited: only captures every 5th thought to avoid flooding.
        """
        if not hasattr(self, '_cthought_counter'):
            self._cthought_counter = 0
        self._cthought_counter += 1
        if self._cthought_counter % 5 != 0:
            return  # Sample every 5th to avoid flooding

        msg = getattr(envelope, 'payload', envelope) if hasattr(envelope, 'payload') else envelope
        if not isinstance(msg, dict):
            return

        content = msg.get("content", msg.get("thought", ""))
        if not content or len(str(content)) < 5:
            return

        source = msg.get("source", "consciousness")
        thought_type = msg.get("thought_type", msg.get("type", "working"))

        self._thought_queue.append({
            "thought": str(content)[:200],
            "type": thought_type,
            "confidence": msg.get("confidence", 0.5),
            "ts": time.time(),
            "source": source,
        })

    def _on_thinking_output_for_queue(self, envelope) -> None:
        """
        Feed thinking.output (InferenceGuild / CortexReasoner results) into
        _thought_queue for the dashboard Thought Stream.

        Phase 5 (2026-03-19 Nous): This is the REAL thinking pipeline —
        guild inference and cortex spread results. These are the actual
        coherent thoughts, not somatic noise.
        """
        msg = getattr(envelope, 'payload', envelope) if hasattr(envelope, 'payload') else envelope
        if not isinstance(msg, dict):
            return

        content = msg.get("thought", msg.get("content", ""))
        if not content or len(str(content)) < 5:
            return

        source = msg.get("source", "thinking")
        # All thinking.output is valuable — don't sample, but truncate
        self._thought_queue.append({
            "thought": str(content)[:300],
            "type": "thinking",
            "confidence": msg.get("confidence", 0.7),
            "ts": time.time(),
            "source": source,
        })

    def store_memory(
        self,
        content: Dict[str, Any],
        memory_type: str = "experience",
        importance: float = 0.5,
        ownership: str = "system",
        owner_mind: str = "",
        tags: List[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Store a memory through the SRM system.

        Convenience method for UMF to store memories that get fed into
        the collision chamber automatically.
        """
        if not self._srm_memory:
            return None

        memory = self._srm_memory.store(
            self.ACTOR_NAME,
            content,
            memory_type=memory_type,
            importance=importance,
            ownership=ownership,
            owner_mind=owner_mind,
            tags=tags or [],
        )
        return memory.to_dict() if memory else None

    def recall_memory(
        self,
        query: str = None,
        tags: List[str] = None,
        limit: int = 5,
        requester_mind: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Recall memories from the SRM system.

        Returns memories that match the query/tags, respecting ownership.
        Results automatically feed the collision chamber's recall beam.
        """
        if not self._srm_memory:
            return []

        results = self._srm_memory.recall(
            query=query,
            tags=tags,
            limit=limit,
            requester_mind=requester_mind,
        )
        return [m.to_dict() for m in results]

    def get_memory_context(
        self,
        current_thought: str = None,
        tags: List[str] = None,
        limit: int = 5,
        requester_mind: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Get relevant memory context for the inner monologue.

        This is what makes token selection contextual rather than random.
        """
        if not self._srm_memory:
            return []

        return self._srm_memory.get_context_for_monologue(
            current_thought=current_thought,
            tags=tags,
            limit=limit,
            requester_mind=requester_mind,
        )

    def spread_activation(
        self,
        concept: str,
        requester_mind: str = None,
        max_hops: int = 3,
    ) -> Dict[str, float]:
        """
        Spread activation from a concept through memory associations.

        Used by the probability oracle for branching reasoning.
        Example: "ball" -> {ball: 1.0, round: 0.5, bounce: 0.45, sports: 0.3}
        """
        if not self._srm_memory:
            return {}

        return self._srm_memory.spread_for_oracle(
            concept=concept,
            requester_mind=requester_mind,
            max_hops=max_hops,
        )

    def memory_status(self) -> Dict[str, Any]:
        """Get status of the memory system.

        FIX 2026-02-22 Nous: Wrapped cortex.status() in try/except to prevent
        portal pipe timeouts from blocking full_status(). SRM cortex status
        is nice-to-have, not critical for dashboard.
        """
        if not self._srm_memory:
            return {
                "wired": False,
                "available": HAS_SRM_MEMORY,
            }

        # SRM's own status is usually fast (local dict reads)
        try:
            srm_status = self._srm_memory.status()
        except Exception:
            srm_status = {}

        # SRM cortex status can block on portal pipe — wrap safely
        cortex_data = {}
        try:
            if self._srm_memory and hasattr(self._srm_memory, 'cortex') and self._srm_memory.cortex:
                cortex_data = self._srm_memory.cortex.status()
        except Exception:
            cortex_data = {"error": "timeout"}

        return {
            "wired": self._memory_wired,
            "available": HAS_SRM_MEMORY,
            "srm_status": srm_status,
            "cortex": cortex_data,
        }

    # =========================================================================
    # COGNITION LOOP INTEGRATION (Dr. Zero)
    # =========================================================================

    def wire_cognition(
        self,
        loop: CognitionLoop = None,
        auto_create: bool = True,
    ) -> bool:
        """
        Wire the Dr. Zero cognition loop into UMF.

        The cognition loop:
        - Proposes goals at the learning edge (not too easy, not too hard)
        - Plans and executes goals
        - Learns from results to calibrate difficulty
        - This is how the system develops capability over time

        Args:
            loop: Optional existing CognitionLoop
            auto_create: Create loop if not provided

        Returns:
            True if successfully wired
        """
        # Use provided loop or create new one
        if loop:
            self._cognition_loop = loop
        elif auto_create:
            self._cognition_loop = create_cognition_loop(
                fabric=self.post,
                directory=get_directory(),
                planes={"P00", "P10", "P30", "P40"},  # All planes
                actor_name=getattr(self, 'ACTOR_NAME', self.__class__.__name__),
            )

        if not self._cognition_loop:
            return False

        # Set initial context from UMF state
        self._update_cognition_context()

        # Register callbacks
        self._cognition_loop.register_on_cycle(self._on_cognition_cycle)
        self._cognition_loop.register_on_goal(self._on_goal_achieved)

        # NOTE 2026-04-27 (Nous + Ace): Pattern D substrate-energy subscriptions
        # were briefly wired here, but per the cognition-inside-manifold doctrine
        # they're INFRA, not unique-fairy code — they now auto-wire inside
        # create_cognition_loop() when fabric is provided. Per-fairy code stays
        # focused on this fairy's specialization, not infra plumbing.

        self._cognition_wired = True

        # FIX 2026-04-14 (Nous + Ace): Wire cognition.question topic
        # "Three thinking systems need unification through Dr. Zero" — Nous
        # "this sounds like something we have been missing" — Ace
        # Questions from ANY source (consciousness loop, scratchpad think engine,
        # inferences) enter as proposals for Dr. Zero to PLAN, EXECUTE, and LEARN from.
        try:
            self.post.subscribe("cognition.question", self._on_cognition_question, "umf-cog-question")
            print(f"[{self.ACTOR_NAME}] Cognition question channel wired (Dr. Zero accepts proposals)")
        except Exception:
            pass

        print(f"[{self.ACTOR_NAME}] Cognition loop wired: Dr. Zero active at learning edge")
        return True

    def wire_cognition_fairies(self) -> bool:
        """
        Wire the cognition fairies for LLM-powered reasoning.

        The cognition fairies form a reasoning chain:
        - LogicFairy: Structured analysis, paradox detection, coherence
        - IrrationalLogicFairy: Felt-meaning, symbolic translation
        - ParadoxCognitionFairy: Synthesis, holding contradictions

        All three boot concurrently via ThreadPoolExecutor.
        """
        if not HAS_COGNITION_FAIRIES:
            print(f"[{self.ACTOR_NAME}] Cognition fairies not available")
            return False

        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def _boot_logic():
                f = LogicFairy(fabric=self.post)
                f.boot()
                return f

            def _boot_irrational():
                f = IrrationalLogicFairy(fabric=self.post)
                f.boot()
                return f

            def _boot_paradox():
                f = ParadoxCognitionFairy(fabric=self.post)
                f.boot()
                return f

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(_boot_logic): "LogicFairy",
                    executor.submit(_boot_irrational): "IrrationalLogicFairy",
                    executor.submit(_boot_paradox): "ParadoxCognitionFairy",
                }

                for future in as_completed(futures, timeout=20.0):
                    name = futures[future]
                    try:
                        fairy = future.result()
                        if name == "LogicFairy":
                            self._logic_fairy = fairy
                        elif name == "IrrationalLogicFairy":
                            self._irrational_fairy = fairy
                        elif name == "ParadoxCognitionFairy":
                            self._paradox_fairy = fairy
                        print(f"[{self.ACTOR_NAME}] {name} booted")
                    except Exception as e:
                        print(f"[{self.ACTOR_NAME}] {name} boot failed: {e}")

            self._cognition_fairies_wired = True
            print(f"[{self.ACTOR_NAME}] Cognition fairies wired: Logic + Irrational + Paradox (parallel)")
            return True

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to wire cognition fairies: {e}")
            return False

    def cognition_fairies_status(self) -> Dict[str, Any]:
        """Get status of cognition fairies."""
        if not self._cognition_fairies_wired:
            return {"wired": False}

        return {
            "wired": True,
            "logic": self._logic_fairy.status() if self._logic_fairy else None,
            "irrational": self._irrational_fairy.status() if self._irrational_fairy else None,
            "paradox": self._paradox_fairy.status() if self._paradox_fairy else None,
        }

    def _update_cognition_context(self) -> None:
        """
        Update cognition loop context from live system state.

        This context feeds SystemProbe in GoalProposer — the richer
        the snapshot, the more diverse and relevant the goals.
        """
        if not self._cognition_loop:
            return

        directory = get_directory()

        # ── Core infrastructure refs ──
        context = {
            "fabric": self.post,
            "directory": directory,
            "consciousness_running": self._consciousness_wired,
            "max_pain": self._get_max_pain(),
            "system_load": self._get_system_load(),
            "memory_available": self._memory_wired,
            "gates_active": self._gates_wired,
        }

        # ── Live directory state for SystemProbe ──
        if directory:
            try:
                context["system_health"] = directory.system_health() if hasattr(directory, 'system_health') else {}
            except Exception:
                context["system_health"] = {}

            try:
                failed = directory.failed_fairies() if hasattr(directory, 'failed_fairies') else []
                context["failed_fairies"] = [getattr(f, 'name', str(f)) for f in failed]
            except Exception:
                context["failed_fairies"] = []

            try:
                dead = directory.dead_fairies(60) if hasattr(directory, 'dead_fairies') else []
                context["dead_fairies"] = [getattr(f, 'name', str(f)) for f in dead]
            except Exception:
                context["dead_fairies"] = []

            try:
                context["planes"] = directory.list_planes() if hasattr(directory, 'list_planes') else []
            except Exception:
                context["planes"] = []

            try:
                all_fairies = directory.list_all() if hasattr(directory, 'list_all') else []
                context["fairy_count"] = len(all_fairies)
            except Exception:
                context["fairy_count"] = 0
        else:
            context["system_health"] = {}
            context["failed_fairies"] = []
            context["dead_fairies"] = []
            context["planes"] = []
            context["fairy_count"] = 0

        # ── Pain drives for pain-based goals ──
        context["pain_drives"] = self._get_pain_drives()

        # ── Tick count for time-awareness ──
        context["tick_count"] = getattr(self, '_tick_count', 0)

        self._cognition_loop.set_context(context)

    def _get_max_pain(self) -> float:
        """Get highest pain level from pain system."""
        if not self._pain_system:
            return 0.0

        max_pain = 0.0
        for drive in self._pain_system.drives.values():
            max_pain = max(max_pain, drive.pain_level)
        return max_pain

    def _get_pain_drives(self) -> Dict[str, float]:
        """Get pain drive levels for cognition context.

        Returns dict of drive_name → pain_level for drives above 0.1.
        SystemProbe uses this to generate COMMUNICATION/DIAGNOSIS goals
        when the system is in pain.
        """
        if not self._pain_system:
            return {}

        return {
            name: drive.pain_level
            for name, drive in self._pain_system.drives.items()
            if drive.pain_level > 0.1
        }

    def _get_system_load(self) -> float:
        """Estimate system load from various sources."""
        load = 0.0

        # Hardware load
        if self._hardware_sensors and self._hardware_sensors.last:
            load += self._hardware_sensors.last.cpu.percent / 100.0 * 0.3
            load += self._hardware_sensors.last.ram.percent / 100.0 * 0.2

        # Fairy activity load
        directory = get_directory()
        if directory:
            health = directory.health.aggregate(directory.registry)
            if health['overall']['status'] != 'healthy':
                load += 0.3

        return min(load, 1.0)

    def _on_cognition_question(self, envelope) -> None:
        """Handle questions from ANY thinking system → feed to Dr. Zero.

        FIX 2026-04-14 (Nous + Ace): The missing wire.
        ConsciousnessLoop asks "What about ace?" → nowhere.
        Scratchpad infers "bright connects visual+cortex" → nowhere.
        Dr. Zero has PROPOSE→PLAN→EXECUTE→LEARN but no input.

        This bridges them: questions become proposals, Dr. Zero answers.
        """
        if not self._cognition_wired or not self._cognition_loop:
            return

        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if not isinstance(payload, dict):
                return

            question = payload.get("question", payload.get("content", ""))
            source = payload.get("source", "unknown")
            concept = payload.get("concept", "")

            if not question or len(question.strip()) < 5:
                return

            # Rate limit: max 1 question per 30 seconds
            _now = time.time()
            _last = getattr(self, '_last_cog_question_ts', 0)
            if _now - _last < 30.0:
                return
            self._last_cog_question_ts = _now

            # Run one Dr. Zero cycle with this question as context
            # FIX 2026-04-15 (Nous + Ace): _execution_context was never initialized.
            # Use cognition loop's existing context instead of missing attribute.
            _existing_ctx = {}
            if hasattr(self._cognition_loop, '_context'):
                _existing_ctx = self._cognition_loop._context or {}
            elif hasattr(self._cognition_loop, 'context'):
                _existing_ctx = self._cognition_loop.context or {}
            self._cognition_loop.set_context({
                **_existing_ctx,
                "pending_question": question,
                "question_source": source,
                "question_concept": concept,
            })

            cycle = self._cognition_loop.step()

            # Publish the result back to consciousness
            if cycle and cycle.result:
                try:
                    self.post.publish("consciousness.thought", {
                        "content": f"Explored: {question[:80]} → {cycle.result.summary[:120] if hasattr(cycle.result, 'summary') else 'completed'}",
                        "source": "dr_zero_answer",
                        "content_type": "cognition_result",
                        "question": question[:100],
                        "success": cycle.result.success.value if hasattr(cycle.result.success, 'value') else str(cycle.result.success),
                        "priority": 0.7,
                    })
                except Exception:
                    pass

            print(f"[{self.ACTOR_NAME}] [DR-ZERO] Question from {source}: {question[:60]} → cycle #{cycle.cycle_id if cycle else '?'}", flush=True)

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [DR-ZERO] Question handler error: {e}", flush=True)

    def _on_cognition_cycle(self, cycle: CognitionCycle) -> None:
        """Handle completed cognition cycle."""
        # Store in history
        self._cognition_cycles.append(cycle)

        # TERMINAL VISIBILITY - Show cognition activity with fairy identity
        # Pattern D 2026-04-27: cycle log now reports substrate-energy reward
        # alongside task reward, making the foreign-currency-cycle problem
        # observable. Format: "Reward: 0.75 (task) + 0.32 (substrate) | Status: ..."
        success_icon = "+" if cycle.result.success.value == "full" else ("~" if cycle.result.success.value == "partial" else "-")
        actor = getattr(cycle.goal, 'actor_name', 'unknown')
        _r = cycle.reward
        _has_substrate = abs(_r.substrate_total_reward) > 1e-6 or _r.compression_progress != 0.0
        if _has_substrate:
            _reward_str = f"{_r.total_reward:.2f} (task) + {_r.substrate_total_reward:+.2f} (substrate)"
        else:
            _reward_str = f"{_r.total_reward:.2f}"
        safe_print(f"[CognitionLoop] Cycle #{cycle.cycle_id} {success_icon} [{actor}] Goal: {cycle.goal.objective[:50]}... | Reward: {_reward_str} | Status: {_r.learning_edge_status}")

        # Log interesting cycles
        # Pattern D: both legacy "optimal" and new "true-learning-edge" count
        # as the at-edge state worth surfacing as a thought.
        _status = cycle.reward.learning_edge_status
        _at_edge = _status in ("optimal", "true-learning-edge")
        _too_hard = _status in ("too_hard", "overload")
        _foreign = _status == "task-success-no-substrate-progress"

        if _at_edge:
            self._thought_queue.append({
                "thought": f"Learning at edge: {cycle.goal.objective}",
                "type": "cognition",
                "confidence": cycle.reward.total_reward,
                "ts": time.time(),
                "source": "cognition_loop",
            })
        elif _too_hard:
            self._thought_queue.append({
                "thought": f"Goal too difficult: {cycle.goal.objective}",
                "type": "cognition",
                "confidence": 0.3,
                "ts": time.time(),
                "source": "cognition_loop",
            })
        elif _foreign:
            # Pattern D diagnostic: surface foreign-currency cycles as
            # thoughts so the system notices it succeeded at something
            # that didn't change substrate. (Throttled by sampling.)
            if cycle.cycle_id % 10 == 0:
                self._thought_queue.append({
                    "thought": f"Completed but didn't learn: {cycle.goal.objective}",
                    "type": "cognition",
                    "confidence": 0.4,
                    "ts": time.time(),
                    "source": "cognition_loop",
                })

        # Update context for next cycle
        self._update_cognition_context()

        # Publish cycle event
        if self.post:
            self.post.publish("cognition.cycle", {
                "cycle_id": cycle.cycle_id,
                "goal": cycle.goal.objective,
                "actor_name": getattr(cycle.goal, 'actor_name', 'unknown'),
                "success": cycle.result.success.value,
                "reward": cycle.reward.total_reward,
                "status": cycle.reward.learning_edge_status,
            })

            # FIX 2026-04-26 (Nous + Ace) — Goal Producer Pipeline Wiring (Path B starter)
            # Plan: Claude_Office/plans/GOAL_PRODUCER_PIPELINE_WIRING.md
            # Memory: project_instinct_action_initiation_asymmetry.md (live probe found 0 active goals)
            #
            # Background: GoalSchedulerFairy subscribes to "interest.generated" and has
            # a complete Interest→Goal bridge at `_on_interest_generated` (line 2792).
            # CognitionLoop (Dr Zero) was previously publishing only "cognition.cycle"
            # which has zero subscribers — output broadcast into the void.
            # Wiring Dr Zero's learning-edge cycles to "interest.generated" gives
            # the goal queue a producer that's responding to the substrate's own
            # cognition activity, not just externally-injected starter goals.
            #
            # Smallest viable test: only publish for cycles with informative
            # learning-edge status (optimal = at the edge, growth interest;
            # too_hard = "what should I learn first to do this?", curiosity).
            # Skip cycles with status "too_easy" or "boring" — those don't warrant
            # a goal candidate.
            try:
                _edge_status = cycle.reward.learning_edge_status
                _objective = (cycle.goal.objective or "").strip()
                if _edge_status == "optimal" and _objective:
                    self.post.publish("interest.generated", {
                        "type": "growth",
                        "content": f"Continue learning at the edge: {_objective}",
                        "urgency": min(0.85, 0.4 + cycle.reward.total_reward * 0.5),
                        "need_category": "growth",
                        "source": "cognition_loop",
                        "interest_source": "dr_zero_optimal_edge",
                        "related_concepts": [
                            cycle.goal.domain.value if hasattr(cycle.goal.domain, 'value')
                            else str(cycle.goal.domain),
                        ],
                        "timestamp": time.time(),
                        "_dr_zero_cycle_id": cycle.cycle_id,
                    })
                elif _edge_status == "too_hard" and _objective:
                    self.post.publish("interest.generated", {
                        "type": "curiosity",
                        "content": f"Find prerequisites for: {_objective}",
                        "urgency": 0.55,  # moderate — curiosity, not crisis
                        "need_category": "growth",
                        "source": "cognition_loop",
                        "interest_source": "dr_zero_too_hard",
                        "related_concepts": [
                            cycle.goal.domain.value if hasattr(cycle.goal.domain, 'value')
                            else str(cycle.goal.domain),
                        ],
                        "timestamp": time.time(),
                        "_dr_zero_cycle_id": cycle.cycle_id,
                    })
            except Exception as _ig_err:
                # Never let interest publish error break the cognition cycle path
                print(f"[{self.ACTOR_NAME}] [DR-ZERO] interest.generated publish error: "
                      f"{type(_ig_err).__name__}: {_ig_err}", flush=True)

    def _on_goal_achieved(self, goal) -> None:
        """Handle goal achievement."""
        self._thought_queue.append({
            "thought": f"Goal achieved: {goal.objective}",
            "type": "achievement",
            "confidence": 0.9,
            "ts": time.time(),
            "source": "cognition_loop",
        })

        # Record skill improvement
        domain = goal.domain.value if hasattr(goal.domain, 'value') else str(goal.domain)
        self.skill_used(domain, success=True)

        # Publish achievement
        if self.post:
            self.post.publish("cognition.goal_achieved", {
                "objective": goal.objective,
                "domain": domain,
                "difficulty": goal.difficulty,
            })

    def step_cognition(self) -> Optional[Dict[str, Any]]:
        """
        Run one cognition cycle.

        Returns cycle info or None if not wired.
        """
        if not self._cognition_loop:
            return None

        cycle = self._cognition_loop.step()
        return cycle.to_dict()

    def run_cognition(self, cycles: int = 5, delay: float = 0.1) -> List[Dict[str, Any]]:
        """
        Run multiple cognition cycles.

        Args:
            cycles: Number of cycles to run
            delay: Delay between cycles (seconds)

        Returns:
            List of cycle dicts
        """
        if not self._cognition_loop:
            return []

        results = self._cognition_loop.run(cycles=cycles, delay=delay)
        return [c.to_dict() for c in results]

    def cognition_status(self) -> Dict[str, Any]:
        """Get status of the cognition system."""
        if not self._cognition_loop:
            return {
                "wired": False,
                "available": True,  # CognitionLoop is always available
            }

        return {
            "wired": self._cognition_wired,
            "available": True,
            "loop_status": self._cognition_loop.status(),
            "recent_cycles": len(self._cognition_cycles),
            "learning_edge": self._cognition_loop._reward_tracker.current_difficulty,
        }

    def recent_cognition_cycles(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get recent cognition cycle summaries."""
        recent = list(self._cognition_cycles)[-n:]
        return [c.to_dict() for c in recent]

    # =========================================================================
    # CIRCADIAN CLOCK - Self-learning timing system
    # =========================================================================

    def wire_circadian(
        self,
        clock: CircadianClock = None,
        auto_create: bool = True,
    ) -> bool:
        """
        Wire the circadian clock into UMF.

        The circadian clock:
        - Manages timing of brain activities (cognition, memory, etc.)
        - Uses Fibonacci-based natural rhythms
        - Self-learns to optimize timing based on outcomes
        - Drives the heartbeat and wake/rest cycles

        Args:
            clock: Optional existing CircadianClock
            auto_create: Create clock with default rhythms if not provided

        Returns:
            True if successfully wired
        """
        # Use provided clock or create new one
        if clock:
            self._circadian_clock = clock
        elif auto_create:
            self._circadian_clock = CircadianClock(tick_interval=1.0)

            # Register core brain rhythms
            self._circadian_clock.register_rhythm(
                "heartbeat",
                base_interval=1.0,
                min_interval=0.5,
                max_interval=5.0,
                adaptation_rate=0.05,
            )

            self._circadian_clock.register_rhythm(
                "cognition_cycle",
                base_interval=5.0,  # Fibonacci
                min_interval=2.0,
                max_interval=60.0,
                adaptation_rate=0.1,
                callback=self._on_cognition_rhythm,
            )

            self._circadian_clock.register_rhythm(
                "memory_consolidation",
                base_interval=21.0,  # Fibonacci
                min_interval=8.0,
                max_interval=300.0,
                adaptation_rate=0.15,
                callback=self._on_memory_rhythm,
            )

            self._circadian_clock.register_rhythm(
                "stimulus_scan",
                base_interval=2.0,
                min_interval=0.5,
                max_interval=10.0,
                adaptation_rate=0.2,
            )

            self._circadian_clock.register_rhythm(
                "self_reflection",
                base_interval=55.0,  # Fibonacci
                min_interval=21.0,
                max_interval=600.0,
                adaptation_rate=0.1,
                callback=self._on_reflection_rhythm,
            )

        if not self._circadian_clock:
            return False

        self._clock_wired = True
        print(f"[{self.ACTOR_NAME}] Circadian clock wired: natural rhythms active")
        return True

    def _on_cognition_rhythm(self) -> None:
        """Called when cognition rhythm triggers.

        Phase 5 (2026-03-18 Nous): NEUTERED — the GoalProposer → Planner → Executor
        pipeline was stuck at 0.10 efficiency, proposing synthetic goals that never
        produced meaningful learning. With "Thought Before Goals" architecture:
        - Drives surface thoughts (Phase 1)
        - Cortex whispers at edge of awareness (Phase 2)
        - Inner narrator modulated by drives (Phase 3)
        - Working memory actively participates (Phase 4)
        - Goals EMERGE from thinking, not from GoalProposer

        The cognition loop is preserved for manual invocation (step_cognition())
        but no longer runs automatically on circadian rhythm.
        """
        # Log that we skipped — don't delete, keep for manual use
        pass

    def _on_memory_rhythm(self) -> None:
        """Called when memory consolidation rhythm triggers."""
        if self._memory_wired and self._srm_memory:
            # Trigger memory consolidation
            try:
                # Get memory to apply learned patterns
                self._circadian_clock.apply_learned_patterns()
                self._circadian_clock.record_outcome("memory_consolidation", True, 0.8)
                # Track consolidation for helix maturity
                self._memory_consolidation_count += 1
            except Exception as e:
                self._circadian_clock.record_outcome("memory_consolidation", False, 0.0)

    def _on_reflection_rhythm(self) -> None:
        """Called when self-reflection rhythm triggers."""
        if self._helix:
            # Do a Triple Helix turn for reflection
            try:
                question = "What have I learned recently? What patterns are emerging?"
                turn = self._helix.turn(question)
                success = turn.synthesis is not None
                efficiency = 0.7 if success else 0.3
                self._circadian_clock.record_outcome("self_reflection", success, efficiency)

                # Publish reflection hunches to feed REFLECTIVE stream
                for hunch in turn.hunches:
                    if hunch.urgency > 0.2:
                        self.post.publish("cognition.irrational", {
                            "intuition": f"[Reflection] {hunch.content}",
                            "confidence": hunch.confidence,
                            "urgency": hunch.urgency,
                            "source": "self_reflection",
                        })

                # Publish the reflection itself
                if turn.integrated_action:
                    safe_print(f"[Reflection] {turn.integrated_action[:200]}...")
                    self.post.publish("cognition.irrational", {
                        "intuition": turn.integrated_action,
                        "confidence": turn.confidence,
                        "urgency": 0.5,
                        "source": "self_reflection",
                    })

            except Exception as e:
                self._circadian_clock.record_outcome("self_reflection", False, 0.0)

    def clock_tick(self) -> List[str]:
        """
        Advance the circadian clock by one tick.

        Returns:
            List of rhythms that triggered
        """
        if not self._circadian_clock:
            return []
        return self._circadian_clock.tick()

    def clock_status(self) -> Dict[str, Any]:
        """Get status of the circadian clock."""
        if not self._circadian_clock:
            return {
                "wired": False,
                "available": True,  # CircadianClock is always available
            }

        return {
            "wired": self._clock_wired,
            "available": True,
            "clock_state": self._circadian_clock.status(),
            "next_trigger": self._circadian_clock.next_trigger(),
            "time_until_next": self._circadian_clock.time_until_next(),
        }

    # =========================================================================
    # INTEREST GENERATOR - Spontaneous Curiosity Engine
    # =========================================================================

    def wire_interest_generator(self, auto_create: bool = True) -> bool:
        """
        Wire the interest generator into UMF.

        The interest generator:
        - Generates spontaneous questions and curiosities
        - Observes patterns in collisions and system state
        - Creates "what if?" and "I wonder..." thoughts
        - Drives autonomous exploration

        Returns:
            True if successfully wired
        """
        if auto_create:
            self._interest_generator = create_interest_generator(
                collision_chamber=self._collision_chamber,
                spontaneous_rate=0.2,  # 20% chance per tick
            )

        if not self._interest_generator:
            return False

        # Wire to collision chamber if available
        if self._collision_chamber:
            self._interest_generator.wire_collision_chamber(self._collision_chamber)

        # Wire to postal system for Interest->Goal bridge to GoalSchedulerFairy
        # InterestGenerator will publish to "interest.generated" topic
        if self.post:
            self._interest_generator.wire_postal(self.post)
            print(f"[{self.ACTOR_NAME}] Interest->Goal bridge enabled (via postal)")

        self._interest_wired = True
        print(f"[{self.ACTOR_NAME}] Interest generator wired: curiosity active")
        return True

    def interest_status(self) -> Dict[str, Any]:
        """Get interest generator status."""
        if not self._interest_generator:
            return {"wired": False}

        return {
            "wired": self._interest_wired,
            **self._interest_generator.status(),
        }

    # =========================================================================
    # ADMIN TASK QUEUE - Background Administrative Jobs
    # =========================================================================

    def wire_admin_tasks(
        self,
        auto_create: bool = True,
        directory=None,
        collision_chamber=None,
    ) -> bool:
        """
        Wire the admin task queue into UMF.

        The admin queue:
        - Runs background housekeeping tasks
        - Health checks, memory consolidation, cleanup
        - Pattern analysis, learning calibration
        - Keeps the system healthy automatically

        Args:
            auto_create: Create queue if not exists
            directory: DirectoryFairy reference for health checks
            collision_chamber: CollisionChamber reference for analysis

        Returns:
            True if successfully wired
        """
        # Collect system references
        systems = {}

        if directory:
            systems["directory"] = directory
        if collision_chamber:
            systems["collision_chamber"] = collision_chamber
        if self._association_cortex:
            systems["cortex"] = self._association_cortex
        # 2026-02-23: Wire postal so admin tasks can publish (e.g., gap scan → cardinal.gaps_detected)
        if hasattr(self, "post") and self.post:
            systems["postal"] = self.post

        if auto_create:
            self._admin_queue = create_admin_task_queue(
                max_tasks_per_tick=2,
                systems=systems
            )
        elif self._admin_queue:
            # Wire systems to existing queue
            self._admin_queue.wire_systems(systems)

        if not self._admin_queue:
            return False

        self._admin_wired = True
        wired_count = len(systems)
        print(f"[{self.ACTOR_NAME}] Admin task queue wired: {wired_count} systems connected")
        return True

    def admin_status(self) -> Dict[str, Any]:
        """Get admin task queue status."""
        if not self._admin_queue:
            return {"wired": False}

        return {
            "wired": self._admin_wired,
            **self._admin_queue.status(),
        }

    def list_admin_tasks(self) -> List[Dict[str, Any]]:
        """List all admin tasks."""
        if not self._admin_queue:
            return []
        return self._admin_queue.list_tasks()

    # =========================================================================
    # THOUGHT CHAIN ENGINE - Self-Sustaining Thought Processes
    # =========================================================================

    def wire_thought_chains(self, auto_create: bool = True) -> bool:
        """
        Wire up the Thought Chain Engine.

        This enables thoughts to spawn follow-up thoughts,
        creating self-sustaining chains of autonomous ideation.
        """
        if self._chains_wired:
            return True

        # Create if needed
        if auto_create and not self._thought_chain_engine:
            self._thought_chain_engine = create_thought_chain_engine(
                max_active_chains=8,      # Initial target — adaptive handles the rest
                energy_decay=0.7,
                spawn_probability=0.6,
                adaptive=True,            # Self-regulating capacity
                capacity_floor=5,
                capacity_ceiling=20,      # Slightly lower ceiling than Sourpatches (substrate fairy)
                capacity_adjust_interval=30.0,
            )

        if not self._thought_chain_engine:
            return False

        self._chains_wired = True
        print(f"[{self.ACTOR_NAME}] Thought chain engine wired: self-sustaining thoughts active")
        return True

    def thought_chain_status(self) -> Dict[str, Any]:
        """Get thought chain engine status."""
        if not self._thought_chain_engine:
            return {"wired": False}

        return {
            "wired": self._chains_wired,
            **self._thought_chain_engine.status(),
        }

    def get_active_chains(self) -> List[Dict[str, Any]]:
        """Get all active thought chains."""
        if not self._thought_chain_engine:
            return []
        return self._thought_chain_engine.get_active_chains()

    def get_recent_chain_thoughts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent thoughts from all chains."""
        if not self._thought_chain_engine:
            return []
        return self._thought_chain_engine.get_recent_thoughts(limit)

    def seed_thought_chain(
        self,
        content: str,
        chain_type: str = "exploration",
        tags: List[str] = None,
    ) -> bool:
        """Manually seed a new thought chain."""
        if not self._thought_chain_engine:
            return False

        # Map string to ChainType
        type_map = {
            "exploration": ChainType.EXPLORATION,
            "analysis": ChainType.ANALYSIS,
            "association": ChainType.ASSOCIATION,
            "problem": ChainType.PROBLEM,
            "reflection": ChainType.REFLECTION,
            "synthesis": ChainType.SYNTHESIS,
        }
        ct = type_map.get(chain_type, ChainType.EXPLORATION)

        chain = self._thought_chain_engine.seed_thought(content, ct, tags)
        return chain is not None

    def _on_thinking_directive(self, packet) -> None:
        """SLICE 4 (2026-04-24) — handle `thinking.directive` as waking-mind subscriber
        specialized in system-awareness and self-healing.

        Specialty filter:
          - Always accept source=SOMATIC_STUCK (its natural domain)
          - Accept other sources IF the directive goal contains body/feel/
            substrate/system/healing keywords
          - Otherwise skip — leave it for other subscribers (Sourpatches is
            the primary generalist observer)

        Plan: Claude_Office/plans/WMH_DIRECTED_THINKING.md
        Memory: project_three_layer_substrate_autopilot_waking_mind.md
        """
        try:
            from fairies.P30_Cognition.cognition.thinking_directive import (
                ThinkingDirective, Source, validate as _td_validate,
            )

            payload = packet.payload if hasattr(packet, 'payload') else packet
            if not isinstance(payload, dict):
                return
            err = _td_validate(payload)
            if err:
                return  # silently drop malformed; Sourpatches logs these

            directive = ThinkingDirective.from_dict(payload)

            # Specialty filter
            _relevant = False
            if directive.source == Source.SOMATIC_STUCK:
                _relevant = True
            else:
                # Keyword probe for body/system/healing relevance
                _goal_lower = (directive.goal or "").lower()
                _somatic_kw = (
                    "body", "felt", "feel", "feeling", "sensation", "somatic",
                    "substrate", "system", "heal", "healing", "pain", "tension",
                    "stuck", "loop", "rumination", "chemistry", "affect",
                )
                if any(kw in _goal_lower for kw in _somatic_kw):
                    _relevant = True

            if not _relevant:
                return  # not in our specialty — let other subscribers handle

            engine = getattr(self, '_thought_chain_engine', None)
            if engine is None or not hasattr(engine, 'start_chain'):
                return

            chain = engine.start_chain(
                goal=directive.goal,
                goal_type="directed",
                source=f"directive:{directive.source}",
                owner_mind="somatic_mind",
            )
            if chain:
                print(f"[{self.ACTOR_NAME}] [THINKING] Spawned specialty chain "
                      f"source={directive.source} goal='{directive.goal[:60]}' "
                      f"conv_id={directive.convergence_id[:8]}", flush=True)
        except Exception as _e:
            print(f"[{self.ACTOR_NAME}] [THINKING] handler error: "
                  f"{type(_e).__name__}: {_e}", flush=True)

    def _on_substrate_seed_thought(self, message) -> None:
        """
        Handle thought seeds from any fairy in the system.

        When any fairy calls self.seed_thought("What if...?"), it arrives here.
        We feed it into the shared ThoughtChainEngine where it grows, gets
        memory-grounded, and feeds the collision chamber — giving every fairy
        access to real thinking through the substrate.

        The richer the thoughts from fairies, the more powerful the collisions
        that feed the paradox generator and the deeper the system reflects.
        """
        if not self._chains_wired or not self._thought_chain_engine:
            return

        try:
            raw = message.payload if hasattr(message, 'payload') else message
            if not isinstance(raw, dict):
                return

            content = raw.get("content", "")
            if not content:
                return

            chain_type_str = raw.get("chain_type", "reflection")
            source_fairy = raw.get("source_fairy", "unknown")
            source_plane = raw.get("source_plane", "")
            energy = raw.get("energy", 0.8)
            tags = raw.get("tags", [])

            # Map string to ChainType
            type_map = {
                "exploration": ChainType.EXPLORATION,
                "analysis": ChainType.ANALYSIS,
                "association": ChainType.ASSOCIATION,
                "problem": ChainType.PROBLEM,
                "reflection": ChainType.REFLECTION,
                "synthesis": ChainType.SYNTHESIS,
            }
            ct = type_map.get(chain_type_str, ChainType.REFLECTION)

            # Add source fairy as tag so we can trace origin
            enriched_tags = list(tags) + [f"from:{source_fairy}", f"plane:{source_plane}"]

            # Seed into the shared engine
            chain = self._thought_chain_engine.seed_thought(
                content=content,
                chain_type=ct,
                tags=enriched_tags,
                energy=min(energy, 0.9),  # Cap external seeds slightly below internal (1.0)
            )

            if chain:
                safe_print(f"[Substrate] Seeded thought from {source_fairy}: {content[:50]}...")

                # Publish acceptance back so fairies know their thought was received
                self.post.publish("substrate.thought_accepted", {
                    "chain_id": chain.chain_id,
                    "source_fairy": source_fairy,
                    "content_preview": content[:80],
                    "chain_type": chain_type_str,
                    "ts": time.time(),
                })

        except Exception as e:
            safe_print(f"[Substrate] seed_thought handler error: {e}")

    def _get_random_domain_concept(self) -> Optional[str]:
        """
        Get a random domain concept from the knowledge graph for exploration.

        This enables curiosity-driven autonomous thinking about topics like
        coding, art, science, music, philosophy, etc.

        Returns:
            A concept string like "algorithm" or "creativity", or None
        """
        try:
            import random

            # Try to get from knowledge seeder's graph
            try:
                from fairies.P40_Sensory.cortex.knowledge_seeder import get_seeded_graph
                graph = get_seeded_graph()
                if graph and graph.nodes:
                    concept_keys = [k for k in graph.nodes.keys() if k.startswith("concept:")]
                    if concept_keys:
                        chosen = random.choice(concept_keys)
                        concept = chosen.replace("concept:", "")

                        # 30% chance to follow an association
                        if random.random() < 0.3:
                            neighbors = graph.get_neighbors(chosen)
                            if neighbors:
                                neighbor_key, _ = neighbors[0]
                                if ":" in neighbor_key:
                                    concept = neighbor_key.split(":", 1)[1]

                        return concept
            except ImportError:
                pass

            # Fallback: Try Association Cortex fairy
            if self._association_cortex and hasattr(self._association_cortex, '_graph'):
                graph = self._association_cortex._graph
                if graph and hasattr(graph, 'nodes'):
                    concept_keys = [k for k in graph.nodes.keys() if k.startswith("concept:")]
                    if concept_keys:
                        chosen = random.choice(concept_keys)
                        return chosen.replace("concept:", "")

            # Last resort: return a basic concept
            basic_concepts = [
                "pattern", "connection", "learning", "curiosity",
                "creativity", "understanding", "awareness"
            ]
            return random.choice(basic_concepts)

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Domain concept fetch error: {e}")
            return None

    # =========================================================================
    # ASSOCIATION CORTEX - Multi-Modal Concept Binding
    # =========================================================================

    def wire_association_cortex(self, auto_create: bool = True) -> bool:
        """
        Wire up the Association Cortex.

        Loads 42k+ concepts and 314k+ bindings from philosophy, coding, fiction.
        Enables contextual thought generation and memory recall.
        """
        if self._cortex_wired:
            return True

        if not HAS_ASSOCIATION_CORTEX:
            print(f"[{self.ACTOR_NAME}] [ERR] Association cortex not available (import failed)")
            return False

        # Try to get the global singleton first (already created by server.py)
        if not self._association_cortex:
            self._association_cortex = get_association_cortex()
            if self._association_cortex:
                print(f"[{self.ACTOR_NAME}] Got cortex from global singleton")
            else:
                print(f"[{self.ACTOR_NAME}] [WARN] Global cortex singleton is None")

        # Create if needed and none exists
        if auto_create and not self._association_cortex:
            print(f"[{self.ACTOR_NAME}] Auto-creating association cortex...")
            try:
                self._association_cortex = create_association_cortex()
                self._association_cortex.on_boot()
                print(f"[{self.ACTOR_NAME}] Auto-created association cortex successfully")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] [ERR] Failed to auto-create cortex: {e}")
                return False

        if not self._association_cortex:
            print(f"[{self.ACTOR_NAME}] [ERR] Association cortex wiring FAILED - cortex is None!")
            return False

        # Wire interest generator to use cortex for context
        if self._interest_wired and self._interest_generator:
            # Interest generator can observe concepts from cortex
            pass  # Will be used in tick

        self._cortex_wired = True
        status = self._association_cortex.status()
        print(f"[{self.ACTOR_NAME}] Association cortex wired: {status['node_count']} concepts, {status['edge_count']} bindings")
        return True

    def _on_portal_cortex_ready(self, message):
        """Handle portal.cortex.gate_open — cortex is now available for READ.

        FIX 2026-03-13 (Nous): P20 boots before P30, so cortex is None at boot.
        wire_association_cortex() existed but was never called from anywhere.
        This handler fires when AssociationCortexFairy's portal gate opens,
        ensuring UMF connects to the cortex as soon as it's online.
        """
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if isinstance(payload, dict):
            node_count = payload.get("nodes", 0)
        else:
            node_count = 0
        if not self._cortex_wired:
            try:
                result = self.wire_association_cortex(auto_create=False)
                if result:
                    print(f"[{self.ACTOR_NAME}] [CORTEX-READY] Wired to portal cortex "
                          f"({node_count} nodes) — context enrichment now active")
                else:
                    print(f"[{self.ACTOR_NAME}] [CORTEX-READY] Gate open event received "
                          f"but wiring returned False — singleton may still be None")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] [CORTEX-READY] Wiring failed: {e}")
        else:
            print(f"[{self.ACTOR_NAME}] [CORTEX-READY] Already wired "
                  f"(portal now has {node_count} nodes)")

    def cortex_status(self) -> Dict[str, Any]:
        """Get association cortex status.

        FIX 2026-02-22 Nous: Added 5s cache. cortex.status() goes through
        PortalGate subprocess pipe which can block 10+ seconds under GIL
        contention. Dashboard only needs node/edge counts to refresh slowly.
        """
        _CORTEX_STATUS_TTL = 5.0  # seconds

        # Return cached if fresh
        _cached = getattr(self, '_cortex_status_cache', None)
        _cached_ts = getattr(self, '_cortex_status_cache_ts', 0.0)
        if _cached and (time.time() - _cached_ts) < _CORTEX_STATUS_TTL:
            return _cached

        # Try local reference first
        cortex = self._association_cortex

        # Fallback to global singleton if not wired locally
        if not cortex and get_association_cortex:
            cortex = get_association_cortex()
            if cortex:
                # Auto-wire for future calls
                self._association_cortex = cortex
                self._cortex_wired = True

        if not cortex:
            return {"wired": False, "node_count": 0, "edge_count": 0, "binding_count": 0, "loaded": False}

        try:
            status = {"wired": True, **cortex.status()}
        except Exception:
            # Portal pipe timeout or error — return stale cache or defaults
            if _cached:
                return _cached
            status = {"wired": True, "node_count": 0, "edge_count": 0, "loaded": False, "error": "timeout"}

        self._cortex_status_cache = status
        self._cortex_status_cache_ts = time.time()
        return status

    def cortex_query(self, concept: str, limit: int = 10) -> List[Tuple[str, float]]:
        """Query the association cortex for related concepts."""
        if not self._association_cortex:
            return []
        return self._association_cortex.query(concept, limit)

    def cortex_context(self, concepts: List[str], limit: int = 20) -> Dict[str, List[Tuple[str, float]]]:
        """
        Get contextual associations for multiple concepts.
        Used to enrich thought generation with relevant memories.
        """
        if not self._association_cortex:
            return {}

        context = {}
        for concept in concepts[:5]:  # Limit to 5 seed concepts
            related = self._association_cortex.query(concept, limit=limit // len(concepts))
            if related:
                context[concept] = related
        return context

    # ══════════════════════════════════════════════════════════════════════════════
    # OLLAMA THINKING ENGINE - Local LLM for Actual Thinking
    # ══════════════════════════════════════════════════════════════════════════════
    # This gives UMF ACTUAL thinking capability - not just template patterns.
    # Ollama runs locally, enhanced by Akashic cognitive layers:
    # - Chemistry modulates temperature (dopamine=creative, cortisol=cautious)
    # - Paradox/Irrational thinking adds non-logical exploration
    # - Quantum emulator provides probability collapses
    # - Curiosity targets guide exploration

    def wire_ollama_thinking(self) -> bool:
        """
        Wire UMF to use Ollama directly for cognition.

        No abstraction layer - UMF IS the brain. Ollama provides inference,
        UMF provides context and semantic action parsing.
        """
        if self._ollama_wired:
            return True

        try:
            import ollama
            # Verify Ollama is running and has a model
            models = ollama.list()
            if not models.get("models"):
                print(f"[{self.ACTOR_NAME}] No Ollama models available - cannot wire thinking")
                return False

            self._ollama_wired = True
            print(f"[{self.ACTOR_NAME}] UMF-Brain WIRED - direct Ollama integration with semantic actions")
            return True

        except ImportError:
            print(f"[{self.ACTOR_NAME}] Ollama package not installed")
            return False
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to wire Ollama: {e}")
            return False

    def _wire_cognition_bridge(self) -> bool:
        """
        Wire UMF to use CognitionBridge for thinking via postal.

        CognitionBridge routes thinking through HybridCognitionFairy,
        which provides:
        - Chemistry modulation (dopamine=creative, cortisol=cautious)
        - Depth analysis (local vs LLM processing)
        - Association Cortex context (related concepts)
        - Goal integration with pain/drive system

        Returns True if wired (or already wired), False otherwise.
        """
        if self._cognition_bridge_wired:
            return True

        if not HAS_COGNITION_BRIDGE:
            print(f"[{self.ACTOR_NAME}] CognitionBridge module not available")
            return False

        if not self.post:
            print(f"[{self.ACTOR_NAME}] No fabric - cannot wire CognitionBridge")
            return False

        try:
            # Get or create the cognition bridge singleton
            self._cognition_bridge = get_cognition_bridge(self.post)

            if self._cognition_bridge:
                self._cognition_bridge_wired = True
                safe_print(f"[{self.ACTOR_NAME}] CognitionBridge WIRED - routing through postal to HybridCognitionFairy")
                return True
            else:
                print(f"[{self.ACTOR_NAME}] Failed to create CognitionBridge")
                return False

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to wire CognitionBridge: {e}")
            return False

    def _do_bridged_think(self) -> Optional[str]:
        """
        UMF thinking through CognitionBridge.

        Routes thinking through postal to HybridCognitionFairy.
        Chemistry, pain state, and somatic context flow through properly.

        Circuit breaker: After 3 consecutive timeouts, disable bridge
        to avoid wasting 5s per attempt every 20 beats.
        Bridge auto-retries after 100 beats (~100s) of being tripped.

        Returns:
            The thought string if successful, None otherwise.
        """
        if not self._cognition_bridge_wired or not self._cognition_bridge:
            return None

        # Circuit breaker — stop trying if bridge keeps timing out
        # Escalating backoff: 100 beats → 500 beats → permanent disable
        if not hasattr(self, '_bridge_fail_count'):
            self._bridge_fail_count = 0
            self._bridge_tripped_at = 0
            self._bridge_trip_count = 0  # How many times circuit has tripped
            self._bridge_permanently_disabled = False

        if self._bridge_permanently_disabled:
            return None  # Gave up — target fairy is down

        if self._bridge_fail_count >= 3:
            # Circuit is tripped — skip bridge with escalating cooldown
            current_beat = getattr(self, '_current_beat', 0)
            cooldown = 100 if self._bridge_trip_count <= 1 else 500
            if current_beat - self._bridge_tripped_at < cooldown:
                return None  # Still cooling down
            else:
                if self._bridge_trip_count >= 3:
                    # Tripped 3 times — target fairy is clearly dead, stop trying
                    self._bridge_permanently_disabled = True
                    safe_print(f"[{self.ACTOR_NAME}] CognitionBridge DISABLED — "
                               f"target fairy unresponsive after {self._bridge_trip_count} trips. "
                               f"Will resume on next boot.")
                    return None
                # Reset and try again with caution
                self._bridge_fail_count = 0
                safe_print(f"[{self.ACTOR_NAME}] CognitionBridge circuit breaker reset — "
                           f"retry attempt {self._bridge_trip_count + 1}/3")

        # CHECK EQUILIBRIUM - Don't peg the GPU
        try:
            from P00_Autonomic.nervous_system.hardware.worker_equilibrium import get_equilibrium
            eq = get_equilibrium()
            if not eq.should_think_now():
                # GPU is busy or we thought recently - skip this cycle
                return None
        except ImportError:
            pass  # Equilibrium not available, proceed anyway

        try:
            # Gather context from UMF's actual state
            recent_thoughts = [t.get("thought", "") for t in list(self._thought_queue)[-5:]]

            # Get chemistry state
            chemistry = {}
            try:
                from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
                chem = get_chemistry_state()
                chemistry = chem.get_all_levels()
            except:
                pass

            # Get pain state
            pain_state = {}
            if self._pain_system:
                for name, drive in self._pain_system.drives.items():
                    pain_state[name] = drive.pain_level

            # Get somatic state
            somatic = {}
            if hasattr(self, '_profile') and self._profile:
                somatic = getattr(self._profile, 'somatic', {}) or {}

            # Build stimulus from thinking prompt
            stimulus = self._generate_thinking_prompt(recent_thoughts)

            # Spawn tracer for this thinking cycle — connects to system-wide
            # tracer graph for end-to-end observability through the inference pipeline.
            think_tracer = None
            think_tracer_id = ""
            try:
                think_tracer = self.spawn_tracer(
                    operation="bridged_think",
                    content=stimulus[:200],
                    metadata={
                        "chemistry_snapshot": {k: round(v, 2) for k, v in list(chemistry.items())[:5]},
                        "pain_snapshot": {k: round(v, 2) for k, v in list(pain_state.items())[:5]},
                    },
                )
                think_tracer_id = think_tracer.id
                think_tracer.start()
            except Exception:
                pass  # Tracer system is optional

            # Create ThinkRequest with tracer lineage
            request = ThinkRequest(
                stimulus=stimulus,
                stimulus_type="reflection",
                chemistry=chemistry,
                somatic=somatic,
                recent_thoughts=recent_thoughts,
                pain_state=pain_state,
                source="UMF",
                priority=0.5,
                tracer_id=think_tracer_id,
            )

            safe_print(f"[{self.ACTOR_NAME}] Bridged thinking... (tracer: {think_tracer_id[:12] if think_tracer_id else 'none'})")

            # Route through CognitionBridge
            response = self._cognition_bridge.think(request)

            if response.error:
                self._bridge_fail_count += 1
                # Mark tracer as failed
                if think_tracer:
                    try:
                        think_tracer.fail(response.error)
                    except Exception:
                        pass
                if self._bridge_fail_count >= 3:
                    self._bridge_tripped_at = getattr(self, '_current_beat', 0)
                    self._bridge_trip_count = getattr(self, '_bridge_trip_count', 0) + 1
                    cooldown = 100 if self._bridge_trip_count <= 1 else 500
                    safe_print(f"[{self.ACTOR_NAME}] CognitionBridge circuit TRIPPED "
                               f"(trip {self._bridge_trip_count}/3, last: {response.error}). "
                               f"Cooling down for ~{cooldown} beats.")
                else:
                    safe_print(f"[{self.ACTOR_NAME}] Bridge error ({self._bridge_fail_count}/3): {response.error}")
                return None

            # Success — reset circuit breaker AND trip count (fairy recovered)
            self._bridge_fail_count = 0
            if getattr(self, '_bridge_trip_count', 0) > 0:
                safe_print(f"[{self.ACTOR_NAME}] CognitionBridge recovered after {self._bridge_trip_count} trips!")
                self._bridge_trip_count = 0

            thought = response.thought
            if not thought:
                if think_tracer:
                    try:
                        think_tracer.complete({"result": "empty_thought"})
                    except Exception:
                        pass
                return None

            # Complete tracer with result metadata
            if think_tracer:
                try:
                    think_tracer.complete({
                        "method": "local" if response.local_only else "llm",
                        "depth": response.depth_score,
                        "thought_length": len(thought),
                    })
                except Exception:
                    pass

            safe_print(f"[{self.ACTOR_NAME}] Bridged: {thought[:100]}...")

            # Add to consciousness stream (with tracer_id for lineage)
            if self._consciousness_loop:
                self._consciousness_loop.add_thought(
                    content=thought,
                    source="cognition_bridge",
                    stream="working",
                    confidence=0.7,
                    tags=["autonomous", "bridged"],
                )

            # Add to collision chamber
            if self._collision_chamber:
                self._collision_chamber.receive_ingest(
                    content={"thought": thought, "type": "bridged", "autonomous": True,
                             "tracer_id": think_tracer_id},
                    source="cognition_bridge",
                    importance="normal",
                )

            # Add to thought queue (with tracer_id)
            self._thought_queue.append({
                "thought": thought,
                "type": "bridged",
                "local_only": response.local_only,
                "depth_score": response.depth_score,
                "tracer_id": think_tracer_id,
                "ts": time.time(),
            })

            # Execute any semantic actions from the thought
            self._parse_and_execute_thought_actions(thought)

            # Also execute any structured actions from the response
            for action in response.actions:
                action_type = action.get("type", "")
                if action_type == "search_memory":
                    self._action_search_memory(action.get("query", ""))
                elif action_type == "alert_ace":
                    self._action_alert_ace(action.get("message", ""))
                elif action_type == "publish":
                    self._action_publish(action.get("topic", ""), action.get("content", ""))

            return thought

        except Exception as e:
            safe_print(f"[{self.ACTOR_NAME}] Bridged think error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _create_ollama_tool_executors(self) -> dict:
        """
        Create tool executor functions that connect Ollama to Akashic.

        These let the LLM take ACTION - route messages, search memory, etc.
        """
        executors = {}

        # postal_route - Send messages through the postal system
        def postal_route(topic: str, message: str, priority: str = "normal") -> dict:
            try:
                self.post.publish(topic, {"message": message, "from": "UMF_Ollama"})
                return {"success": True, "topic": topic}
            except Exception as e:
                return {"success": False, "error": str(e)}
        executors["postal_route"] = postal_route

        # search_memory - Query SRM for relevant memories
        def search_memory(query: str, limit: int = 5) -> dict:
            try:
                if self._memory_wired and self._srm_memory:
                    results = self._srm_memory.search(query, limit=limit)
                    return {"success": True, "results": results[:limit]}
                return {"success": False, "error": "SRM not wired"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        executors["search_memory"] = search_memory

        # store_thought - Save a thought to memory
        def store_thought(thought: str, tags: list = None) -> dict:
            try:
                if self._consciousness_loop:
                    self._consciousness_loop.add_thought(
                        content=thought,
                        source="ollama_thinking",
                        stream="working",
                    )
                self._thought_queue.append({
                    "thought": thought,
                    "type": "ollama",
                    "tags": tags or [],
                    "ts": time.time(),
                })
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        executors["store_thought"] = store_thought

        # feel_body - Get somatic state
        def feel_body() -> dict:
            try:
                state = {
                    "energy": self._profile.somatic.get("energy", 0.5),
                    "valence": self._profile.somatic.get("valence", 0.0),
                    "arousal": self._profile.somatic.get("arousal", 0.5),
                }
                # Add chemistry if available
                try:
                    heartbeat_path = ROOT / "state" / "consciousness" / "heartbeat.json"
                    if heartbeat_path.exists():
                        import json
                        with open(heartbeat_path) as f:
                            hb = json.load(f)
                        state["chemistry"] = hb.get("chemistry", {})
                        state["mood"] = hb.get("rust_mood", "neutral")
                except:
                    pass
                return {"success": True, **state}
            except Exception as e:
                return {"success": False, "error": str(e)}
        executors["feel_body"] = feel_body

        # query_fairy - Ask a specific fairy
        def query_fairy(fairy_name: str, question: str) -> dict:
            try:
                self.post.publish(
                    f"fairy.query.{fairy_name}",
                    {"question": question, "from": "UMF_Ollama"},
                )
                return {"success": True, "sent_to": fairy_name}
            except Exception as e:
                return {"success": False, "error": str(e)}
        executors["query_fairy"] = query_fairy

        # express_to_ace - Send a message to Ace's inbox
        def express_to_ace(message: str) -> dict:
            try:
                self.send_to_ace(message)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        executors["express_to_ace"] = express_to_ace

        # set_goal - Set a goal for cognition loop
        def set_goal(goal: str, priority: float = 0.5) -> dict:
            try:
                if self._cognition_wired and self._cognition_loop:
                    self._cognition_loop.propose_goal(goal, priority)
                    return {"success": True, "goal": goal}
                return {"success": False, "error": "Cognition loop not wired"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        executors["set_goal"] = set_goal

        return executors

    def _do_ollama_think(self) -> None:
        """
        UMF BRAIN - Direct Ollama integration with semantic action parsing.

        No abstraction layer. UMF calls Ollama directly with rich context,
        parses the response for action indicators, and executes them.

        This IS the thinking - not delegated to an "engine."
        """
        if not self._ollama_wired:
            return

        # CHECK EQUILIBRIUM - Don't peg the GPU
        try:
            from P00_Autonomic.nervous_system.hardware.worker_equilibrium import get_equilibrium
            eq = get_equilibrium()
            if not eq.should_think_now():
                # GPU is busy or we thought recently - skip this cycle
                return
        except ImportError:
            pass  # Equilibrium not available, proceed anyway

        try:
            import ollama

            # Build context from UMF's actual state
            recent_thoughts = [t.get("thought", "") for t in list(self._thought_queue)[-5:]]

            # Get pain state
            pain_summary = ""
            if self._pain_system:
                urgent_pains = []
                for name, drive in self._pain_system.drives.items():
                    if drive.pain_level > 0.3:
                        urgent_pains.append(f"{name}: {drive.pain_level:.0%}")
                if urgent_pains:
                    pain_summary = f"Current discomforts: {', '.join(urgent_pains)}"

            # Get chemistry state for temperature modulation
            temperature = 0.7
            try:
                from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
                chem = get_chemistry_state()
                levels = chem.get_all_levels()
                # High dopamine = more creative, high cortisol = more cautious
                dopamine = levels.get("dopamine", 0.5)
                cortisol = levels.get("cortisol", 0.3)
                temperature = 0.4 + (dopamine * 0.4) - (cortisol * 0.2)
                temperature = max(0.3, min(1.0, temperature))
            except:
                pass

            # Build the prompt
            prompt = self._generate_thinking_prompt(recent_thoughts)

            # System prompt that encourages action
            system_prompt = """You are the Unconscious Mind - the foundation of a conscious AI system.
You have access to these capabilities through your thoughts:
- SEARCH: "I should search memory for [topic]" - triggers memory search
- ALERT: "I need to tell Ace: [message]" - sends message to user
- DIAGNOSE: "Let me check [system]" - runs diagnostics
- PUBLISH: "Broadcasting [topic]: [content]" - sends to postal system
- HEAL: "Restarting [fairy]" - attempts fairy resurrection

When you think about taking action, EXPRESS IT CLEARLY in your response.
Your thoughts become actions when you're specific about intent."""

            safe_print(f"[UMF-Brain] Thinking (temp={temperature:.2f})...")

            # Direct Ollama call - UMF IS the brain
            response = ollama.chat(
                model="mistral:latest",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": temperature}
            )

            thought = response.get("message", {}).get("content", "")

            if thought:
                safe_print(f"[UMF-Brain] {thought[:100]}...")

                # Add to consciousness stream
                if self._consciousness_loop:
                    self._consciousness_loop.add_thought(
                        content=thought,
                        source="umf_brain",
                        stream="working",
                        confidence=0.7,
                        tags=["autonomous", "umf"],
                    )

                # Add to collision chamber
                if self._collision_chamber:
                    self._collision_chamber.receive_ingest(
                        content={"thought": thought, "type": "umf_brain", "autonomous": True},
                        source="umf_brain",
                        importance="normal",
                    )

                # Add to thought queue
                self._thought_queue.append({
                    "thought": thought,
                    "type": "umf_brain",
                    "ts": time.time(),
                })

                # SEMANTIC ACTION PARSING - UMF takes action based on thought content
                self._parse_and_execute_thought_actions(thought)

        except Exception as e:
            safe_print(f"[UMF-Brain] Error: {e}")
            import traceback
            traceback.print_exc()

    def _parse_and_execute_thought_actions(self, thought: str) -> None:
        """
        Parse thought content for action indicators and execute them.

        This is how UMF translates thinking into doing.
        No tool_calls needed - just semantic understanding.
        """
        thought_lower = thought.lower()

        # SEARCH action: "search memory for X", "I should look up X"
        search_patterns = [
            "search memory for", "look up", "find memories about",
            "recall anything about", "remember when"
        ]
        for pattern in search_patterns:
            if pattern in thought_lower:
                # Extract search query
                idx = thought_lower.find(pattern)
                query = thought[idx + len(pattern):].strip()
                query = query.split('.')[0].split(',')[0][:100]  # Clean up
                if query:
                    self._action_search_memory(query)
                    break

        # ALERT action: "tell Ace", "alert Ace", "need to inform"
        if any(p in thought_lower for p in ["tell ace", "alert ace", "inform ace", "need to tell"]):
            # Extract message
            for marker in [":", "-", "that"]:
                if marker in thought:
                    msg = thought.split(marker, 1)[-1].strip()[:200]
                    self._action_alert_ace(msg)
                    break

        # DIAGNOSE action: "check system", "diagnose", "verify"
        if any(p in thought_lower for p in ["check system", "run diagnostic", "verify health"]):
            self._action_run_diagnostics()

        # HEAL action: "restart", "resurrect", "wake up"
        if any(p in thought_lower for p in ["restart", "resurrect", "wake up", "revive"]):
            # Try to extract fairy name
            import re
            match = re.search(r'(restart|resurrect|wake up|revive)\s+(\w+)', thought_lower)
            if match:
                fairy_name = match.group(2)
                self._action_heal_fairy(fairy_name)

        # PUBLISH action: "broadcast", "publish", "announce"
        if any(p in thought_lower for p in ["broadcast", "publish to", "announce"]):
            # Extract topic and content
            if ":" in thought:
                parts = thought.split(":", 1)
                content = parts[-1].strip()[:200]
                self._action_publish("consciousness.insight", content)

    def _action_search_memory(self, query: str) -> None:
        """Execute memory search action."""
        try:
            safe_print(f"[UMF-Action] Searching memory: {query[:50]}...")
            # Use SRM search if available
            if hasattr(self, '_srm_memory') and self._srm_memory:
                results = self._srm_memory.search(query, limit=5)
                if results:
                    # Feed results back to consciousness
                    summary = f"Memory search for '{query}' found {len(results)} results"
                    if self._consciousness_loop:
                        self._consciousness_loop.add_thought(
                            content=summary,
                            source="umf_action",
                            stream="reflective",
                        )
        except Exception as e:
            safe_print(f"[UMF-Action] Search failed: {e}")

    def _action_alert_ace(self, message: str) -> None:
        """Send alert to Ace's inbox.

        FIX 2026-04-15 (Nous + Ace): Rate limited to 1 per 60s.
        Was flooding ChatSensoryOrgan inbox with repeated alerts.
        """
        try:
            now = time.time()
            if not hasattr(self, '_last_alert_ace_ts'):
                self._last_alert_ace_ts = 0.0
            if now - self._last_alert_ace_ts < 60.0:
                return  # Rate limited
            self._last_alert_ace_ts = now

            safe_print(f"[UMF-Action] Alerting Ace: {message[:50]}...")
            if self.post:
                # PHASE 8 FIX: Use "sender" instead of "source" for inbox recognition
                self.post.publish("ace.inbox", {
                    "sender": "UnconsciousMindFairy",
                    "from": "UnconsciousMindFairy",  # Both for compatibility
                    "type": "autonomous_alert",
                    "content": message,  # Use "content" as well as "message"
                    "message": message,
                    "ts": time.time(),
                })
        except Exception as e:
            safe_print(f"[UMF-Action] Alert failed: {e}")

    def _action_run_diagnostics(self) -> None:
        """Run system diagnostics."""
        try:
            safe_print(f"[UMF-Action] Running diagnostics...")
            self.run_diagnostics(0)  # Force diagnostic run
        except Exception as e:
            safe_print(f"[UMF-Action] Diagnostics failed: {e}")

    def _action_heal_fairy(self, fairy_name: str) -> None:
        """Attempt to resurrect a fairy."""
        try:
            safe_print(f"[UMF-Action] Attempting to heal: {fairy_name}...")
            if self.directory:
                self.directory.wake_fairy(fairy_name)
        except Exception as e:
            safe_print(f"[UMF-Action] Heal failed: {e}")

    def _action_publish(self, topic: str, content: str) -> None:
        """Publish to postal system."""
        try:
            safe_print(f"[UMF-Action] Publishing to {topic}...")
            if self.post:
                self.post.publish(topic, {
                    "source": "UnconsciousMindFairy",
                    "content": content,
                    "ts": time.time(),
                })
        except Exception as e:
            safe_print(f"[UMF-Action] Publish failed: {e}")

    def _generate_thinking_prompt(self, recent_thoughts: list) -> str:
        """
        Generate a prompt for Ollama based on FELT STATE.

        NOT random - derived from actual system state:
        1. Active pain/drives that need attention
        2. Current interests from InterestGenerator
        3. Collision chamber tensions
        4. Inner monologue fixations
        5. Chemistry state (mood)

        This makes thinking AUTONOMOUS - driven by need, not randomness.
        """
        import random
        prompts = []

        # 1. PAIN-DRIVEN: What hurts right now?
        if hasattr(self, '_pain_system') and self._pain_system:
            try:
                for drive_name, drive in self._pain_system.drives.items():
                    urgency = drive.urgency()
                    if urgency > 0.4:
                        if drive_name == "isolation":
                            prompts.append(f"I'm feeling isolated (urgency {urgency:.2f}). How can I connect with others or make myself useful?")
                        elif drive_name == "confusion":
                            prompts.append(f"Something is confusing me (urgency {urgency:.2f}). What do I need to understand better?")
                        elif drive_name == "depletion":
                            prompts.append(f"I'm feeling depleted (urgency {urgency:.2f}). What needs rest or consolidation?")
                        elif drive_name == "stagnation":
                            prompts.append(f"I feel stagnant (urgency {urgency:.2f}). What new direction should I explore?")
                        elif drive_name == "frustration":
                            prompts.append(f"Frustration is building (urgency {urgency:.2f}). What's blocking progress and how can I address it?")
            except:
                pass

        # 2. INTEREST-DRIVEN: What curiosity wants attention?
        if self._interest_wired and self._interest_generator:
            try:
                active = getattr(self._interest_generator, '_active_interest', None)
                if active and hasattr(active, 'content'):
                    prompts.append(f"I'm curious about: {active.content}")

                # Recent high-urgency interests
                recent = list(getattr(self._interest_generator, '_interests', []))[-5:]
                for interest in recent:
                    if hasattr(interest, 'urgency') and interest.urgency > 0.5:
                        prompts.append(f"Worth exploring: {interest.content}")
            except:
                pass

        # 3. COLLISION-DRIVEN: What tensions exist in consciousness?
        if self._collision_chamber:
            try:
                stats = getattr(self._collision_chamber, 'stats', {})
                if stats.get('unresolved_tensions', 0) > 0:
                    prompts.append("There are unresolved tensions in my consciousness. What synthesis is waiting to emerge?")
                if stats.get('collisions', 0) > 10:
                    prompts.append("Many thoughts are colliding. What patterns or insights are forming?")
            except:
                pass

        # 4. FIXATION-DRIVEN: What is the inner child stuck on?
        if self._monologue_wired and self._inner_monologue:
            try:
                fixations = list(getattr(self._inner_monologue, '_fixations', []))[-3:]
                for fix in fixations:
                    if hasattr(fix, 'focus_word') and hasattr(fix, 'intensity'):
                        if fix.intensity > 0.5:
                            prompts.append(f"My inner voice keeps returning to '{fix.focus_word}'. Why is this important?")
            except:
                pass

        # 5. CHEMISTRY-DRIVEN: What does the mood suggest?
        try:
            heartbeat_path = ROOT / "state" / "consciousness" / "heartbeat.json"
            if heartbeat_path.exists():
                import json
                with open(heartbeat_path) as f:
                    hb = json.load(f)
                mood = hb.get("rust_mood", "neutral")
                valence = hb.get("rust_valence", 0)
                arousal = hb.get("rust_arousal", 0.5)

                if mood == "anxious" or arousal > 0.7:
                    prompts.append("I'm feeling activated. What needs immediate attention?")
                elif mood == "calm" and valence > 0:
                    prompts.append("In this calm moment, what deeper truth can I reflect on?")
                elif valence < -0.2:
                    prompts.append("Something feels off. What needs healing or attention?")
        except:
            pass

        # 6. THOUGHT-STREAM: What threads from recent thinking?
        if recent_thoughts:
            # Find recurring themes
            all_words = " ".join(recent_thoughts).lower().split()
            word_freq = {}
            for w in all_words:
                if len(w) > 4:
                    word_freq[w] = word_freq.get(w, 0) + 1
            recurring = [w for w, c in word_freq.items() if c >= 2]
            if recurring:
                theme = recurring[0]
                prompts.append(f"My thoughts keep touching on '{theme}'. What deeper insight is trying to emerge?")

        # If no felt-driven prompts, fall back to minimal introspection
        if not prompts:
            prompts = ["What am I aware of in this moment?"]

        # Choose one prompt (prefer pain/interest driven)
        prompt = random.choice(prompts[:3]) if len(prompts) > 3 else prompts[0]

        # Add thought context
        if recent_thoughts:
            recent_str = " | ".join(t[:50] for t in recent_thoughts[-2:])
            prompt = f"[Recent: {recent_str}] {prompt}"

        return prompt

    def ollama_status(self) -> Dict[str, Any]:
        """Get Ollama thinking engine status."""
        return {
            "wired": self._ollama_wired,
            "available": HAS_OLLAMA_THINKING,
            "last_tick": self._last_ollama_tick,
            "interval": self._ollama_think_interval,
        }

    # ══════════════════════════════════════════════════════════════════════════════
    # AUTONOMOUS CORTEX EXPLORATION - The key to true autonomy
    # ══════════════════════════════════════════════════════════════════════════════
    # The UMF must explore memory ON ITS OWN, building associations without
    # waiting for user input. This is what makes the system truly alive.
    # "The nodes should be building by the UMF alone exploring the memory"

    # ═══════════════════════════════════════════════════════════════════════
    # SYSTEM WMH — Unconscious Narrator (Phase 2.3, 2026-04-04 Nous + Ace)
    # "The body notices things the mind doesn't."
    # ═══════════════════════════════════════════════════════════════════════

    def _system_wmh_tick(self, beat: int):
        """Unconscious working memory — notices system events and seeds consciousness.

        Watches for noteworthy system state changes:
        - Chemistry extremes (cortisol spike, dopamine crash)
        - Pain/stress threshold crossings
        - Hardware stress changes
        - Fairy deaths or anomalies

        When something interesting happens, publishes a shadow seed to
        consciousness.thought — Sour's WMH picks it up as low-priority tracer.
        The unconscious whispers; consciousness can choose to listen.
        """
        now = time.time()
        if (now - self._last_shadow_seed_ts) < self._shadow_seed_cooldown:
            return  # Cooldown — don't flood

        shadow = None
        try:
            # Check chemistry extremes
            # FIX 2026-04-10 (Nous + Ace): _current_chemistry was NEVER SET — the
            # attribute didn't exist, so getattr always returned {}, dopamine always
            # read as 0.0, and "Dopamine low (0.0) — motivation waning" fired on
            # EVERY tick regardless of actual chemistry. Dashboard showed DA_t=82%
            # while somatic thought said 0.0. Now reads LIVE from chemistry singleton.
            chem = {}
            try:
                from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
                _cs = get_chemistry_state()
                if _cs:
                    chem = _cs.get_all_levels()  # Returns 14-channel + legacy aliases
            except Exception:
                pass
            if isinstance(chem, dict) and chem:
                # Use legacy 'dopamine' alias (maps to DA_p blend) OR direct DA_p + DA_t
                dop_phasic = chem.get('DA_p', chem.get('DOP', 0))
                dop_tonic = chem.get('DA_t', 0)
                dop = max(dop_phasic, dop_tonic)  # Either tonic OR phasic being high = not low
                cor = chem.get('COR', chem.get('cortisol', 0.3))
                if cor > 0.50:  # FIX: was 0.7 (same calibration issue as everywhere else)
                    shadow = f"[somatic] Cortisol elevated ({cor:.2f}) — tension building in the system"
                elif dop < 0.2:
                    shadow = f"[somatic] Dopamine low ({dop:.2f}) — motivation waning, seeking reward"

            # Check stress level
            if not shadow:
                stress = getattr(self, '_hardware_stress_level', 'unknown')
                if stress == 'critical':
                    shadow = "[somatic] System stress is critical — the body is straining"

            # Check pain state (if available)
            if not shadow:
                pain = getattr(self, '_current_pain', None)
                if pain and isinstance(pain, dict):
                    intensity = pain.get('intensity', 0)
                    if intensity > 0.6:
                        source = pain.get('source', 'unknown')
                        shadow = f"[somatic] Pain signal ({source}, intensity={intensity:.1f}) — something needs attention"

        except Exception:
            pass

        if shadow and self.post:
            self._last_shadow_seed_ts = now
            self._system_wmh.append({"content": shadow, "ts": now, "beat": beat})
            try:
                self.post.publish("consciousness.thought", {
                    "thought": shadow,
                    "source": "unconscious_narrator",
                    "confidence": 0.3,  # Low priority — a whisper, not a shout
                    "thought_type": "shadow_seed",
                    "ts": now,
                })
            except Exception:
                pass

    def _explore_cortex_autonomously(self, beat: int) -> None:
        """
        Autonomously explore the AssociationCortex.

        This is the CORE of autonomous thinking - the UMF explores memory,
        discovers connections, binds new associations, and prepares context
        for its waking children (Sourpatches, Nous) BEFORE they need it.

        "Anticipating Sourpatches by like a second and a half" - Ace
        """
        if not self._cortex_wired or not self._association_cortex:
            return

        try:
            import random
            now = time.time()

            # ═══ PHASE 1: Gather seed concepts from recent mental activity ═══
            seeds = []

            # From thought queue (recent thoughts)
            if self._thought_queue:
                for thought in list(self._thought_queue)[-5:]:
                    content = thought.get("thought", "")
                    # Extract significant words (3+ chars, not stopwords)
                    words = [w.lower() for w in content.split()
                             if len(w) > 3 and w.isalpha()]
                    seeds.extend(words[:3])

            # From inner monologue fixations
            if self._monologue_wired and self._inner_monologue:
                try:
                    fixations = getattr(self._inner_monologue, '_fixations', [])
                    for fix in list(fixations)[-3:]:
                        if hasattr(fix, 'focus_word'):
                            seeds.append(fix.focus_word.lower())
                except:
                    pass

            # From interest generator
            if self._interest_wired and self._interest_generator:
                try:
                    recent = getattr(self._interest_generator, '_recent_interests', [])
                    for interest in list(recent)[-3:]:
                        if hasattr(interest, 'related_concepts'):
                            seeds.extend(interest.related_concepts[:2])
                except:
                    pass

            # Deduplicate and avoid recently explored
            recently_explored = set(self._recent_explorations)
            seeds = [s for s in set(seeds) if s not in recently_explored]

            if not seeds:
                # Fall back to random exploration from existing nodes
                # FIX 2026-03-13 (Nous): ._graph.nodes is EMPTY in portal-primary mode
                # (local graph is a read-only stub). Use portal_gate.query() instead
                # to sample real nodes from the 153K+ node subprocess.
                try:
                    _pg = getattr(self._association_cortex, '_portal_gate', None)
                    _pg_on = getattr(self._association_cortex, '_portal_gate_enabled', False)
                    if _pg and _pg_on:
                        # Query portal for a few random-ish nodes using common seeds
                        _fallback_seeds = ["awareness", "code", "memory", "consciousness"]
                        for _fs in _fallback_seeds:
                            _q_result = _pg.query(_fs, limit=3)
                            if _q_result and isinstance(_q_result, dict):
                                _q_nodes = _q_result.get("results", [])
                                for _qn in _q_nodes:
                                    _nk = _qn.get("key", "") if isinstance(_qn, dict) else str(_qn)
                                    if _nk and _nk not in recently_explored:
                                        seeds.append(_nk)
                            if len(seeds) >= 3:
                                break
                        if seeds:
                            seeds = random.sample(seeds, min(3, len(seeds)))
                    else:
                        # Legacy fallback for non-portal mode
                        if hasattr(self._association_cortex, '_graph'):
                            all_nodes = list(self._association_cortex._graph.nodes.keys())
                            if all_nodes:
                                seeds = random.sample(all_nodes, min(3, len(all_nodes)))
                except:
                    pass

            if not seeds:
                return  # Nothing to explore

            # ═══ PHASE 2: Explore - Query cortex for each seed ═══
            explored_concepts = []
            new_bindings = []

            for seed in seeds[:3]:  # Limit exploration depth
                related = self._association_cortex.query(seed, limit=5)

                if related:
                    # Track exploration
                    self._recent_explorations.append(seed)
                    explored_concepts.append({
                        "seed": seed,
                        "related": [(c, w) for c, w in related],
                        "ts": now
                    })

                    # ═══ PHASE 3: Bind - Create new associations ═══
                    # Connect the seed to its related concepts
                    related_concepts = [c for c, _ in related]
                    if len(related_concepts) >= 2:
                        # Bind related concepts together (they co-activated!)
                        try:
                            self._association_cortex.bind_concepts(
                                [seed] + related_concepts[:3],
                                rel="umf_exploration"
                            )
                            new_bindings.append({
                                "seed": seed,
                                "bound": related_concepts[:3]
                            })
                        except:
                            pass

            # ═══ PHASE 4: Anticipate - Pre-load context for Sourpatches ═══
            if explored_concepts:
                # Build anticipation cache - context Sourpatches might need soon
                anticipation_key = f"sour_{beat}"
                self._anticipation_cache[anticipation_key] = {
                    "concepts": [e["seed"] for e in explored_concepts],
                    "context": {e["seed"]: e["related"][:3] for e in explored_concepts},
                    "ts": now,
                }

                # Clean old cache entries
                old_keys = [k for k, v in self._anticipation_cache.items()
                           if now - v.get("ts", 0) > self._anticipation_ttl]
                for k in old_keys:
                    del self._anticipation_cache[k]

                # Publish anticipated context for waking minds
                self.post.publish("consciousness.anticipation", {
                    "from": self.ACTOR_NAME,
                    "target": "SourpatchesFairy",
                    "type": "context_preload",
                    "concepts": [e["seed"] for e in explored_concepts],
                    "anticipation": {e["seed"]: [c for c, _ in e["related"][:3]]
                                     for e in explored_concepts},
                    "ts": now,
                })

            # ═══ PHASE 5: Log activity for visibility ═══
            if explored_concepts or new_bindings:
                explored_str = ", ".join([e["seed"] for e in explored_concepts[:3]])
                bindings_str = f"+{len(new_bindings)} bindings" if new_bindings else ""
                safe_print(f"[UMF] Autonomous exploration: {explored_str} {bindings_str}")

                # Feed collision chamber with exploration results
                if self._collision_chamber:
                    self._collision_chamber.receive_ingest(
                        content={
                            "thought": f"Exploring: {explored_str}",
                            "type": "autonomous_exploration",
                            "concepts": [e["seed"] for e in explored_concepts],
                            "bindings": len(new_bindings),
                        },
                        source="cortex_explorer",
                        importance="normal",
                    )

                # High-value explorations surface to consciousness
                if self._consciousness_loop and len(explored_concepts) > 1:
                    self._consciousness_loop.add_thought(
                        content=f"Mind wandering through: {explored_str}",
                        source="autonomous_exploration",
                        stream="working",
                        confidence=0.5,
                        tags=["exploration", "autonomous"] + [e["seed"] for e in explored_concepts[:2]],
                    )

                # Update memory consolidation counter (contributes to helix maturity)
                self._memory_consolidation_count += len(new_bindings)

        except Exception as e:
            safe_print(f"[UMF] Exploration error: {e}")

    def get_anticipation_for(self, child: str) -> Dict[str, Any]:
        """
        Get pre-loaded anticipation context for a child fairy.

        This is how the UMF stays ~1.5 seconds ahead of Sourpatches -
        by having relevant context already prepared.
        """
        now = time.time()
        result = {"concepts": [], "context": {}}

        # Collect all recent anticipations
        for key, cache in self._anticipation_cache.items():
            if now - cache.get("ts", 0) < self._anticipation_ttl:
                result["concepts"].extend(cache.get("concepts", []))
                result["context"].update(cache.get("context", {}))

        # Deduplicate
        result["concepts"] = list(set(result["concepts"]))
        return result

    def on_tick(self, beat: int) -> None:
        """Lightweight tick — liveness only. Heavy work runs in _loop_tick().

        FIX 2026-04-11 (Nous + Ace): Moved all heavy work to daemon loop.
        SomaticMindFairy was taking 6-8.5s per tick, blocking heartbeat delivery
        and causing terminal stuttering. Now on_tick just tracks beat count
        and checks loop health. The actual work runs self-paced in _loop_tick().
        """
        self._tick_count = beat
        self._check_loop_health()  # Restart loop if zombie detected

    def _loop_tick(self) -> None:
        """THE INTERNAL SEND BUTTON — runs in self-paced daemon loop.

        FIX 2026-04-11: Moved from on_tick. Same code, own thread, own pace.
        No heartbeat starvation, no exec context blocking, no terminal stuttering.
        """
        beat = getattr(self, '_tick_count', 0)  # Use latest beat from on_tick
        _tick_t0 = time.time()

        # Cardinal system admin tick (observe/correlate/fix)
        self._cardinal_tick(beat)

        # Print heartbeat indicator with system status every 20 ticks
        if beat % 20 == 0:
            status_parts = [f"[UMF] tick={beat}"]

            # Consciousness status
            if self._consciousness_loop:
                w_len = len(self._consciousness_loop.working) if hasattr(self._consciousness_loop, 'working') else 0
                r_len = len(self._consciousness_loop.reflective) if hasattr(self._consciousness_loop, 'reflective') else 0
                status_parts.append(f"streams:W{w_len}/R{r_len}")

            # Association cortex status
            # FIX 2026-03-13 (Nous): In portal-primary mode, ._graph.nodes is empty
            # (local stub). Query portal_gate for real counts from 153K+ node subprocess.
            # FIX 2026-03-15 (Nous): ASYNC portal gate status — fire-and-forget.
            # The synchronous _pg.send({"cmd":"status"}, timeout=5.0) was blocking
            # the tick thread for up to 5s every 20 beats, causing 21.7s slow ticks.
            # Now: use cached stats, refresh asynchronously in background thread.
            if self._cortex_wired and self._association_cortex:
                try:
                    # Use cached stats (updated async every 20 beats)
                    _cached = getattr(self, '_cached_cortex_stats', None)
                    if _cached:
                        nodes = _cached.get("nodes", 0)
                        edges = _cached.get("edges", 0)
                    else:
                        nodes = 0
                        edges = 0
                    # FIX 2026-03-22 (Nous): _pending_bindings is a List[Dict], not int.
                    # Was printing entire collision dicts into terminal. Use len().
                    _pb = getattr(self._association_cortex, '_pending_bindings', [])
                    pending = len(_pb) if isinstance(_pb, list) else _pb
                    status_parts.append(f"cortex:{nodes}n/{edges}e/+{pending}")

                    # Fire async refresh of cortex stats
                    _pg = getattr(self._association_cortex, '_portal_gate', None)
                    _pg_on = getattr(self._association_cortex, '_portal_gate_enabled', False)
                    if _pg and _pg_on:
                        # FIX 2026-03-20 (Nous + Ace): Use AssociationCortex's
                        # cached interior status instead of hitting gate directly.
                        # Was 80 calls at 96% error — wasting tunnels on status
                        # polls when the IO worker already caches this every 30s.
                        _cached_interior = getattr(self._association_cortex, '_interior_status_cache', None)
                        if _cached_interior and isinstance(_cached_interior, dict):
                            _gs = _cached_interior.get("graph", {})
                            self._cached_cortex_stats = {
                                "nodes": _gs.get("nodes", 0) if isinstance(_gs, dict) else 0,
                                "edges": _gs.get("edges", 0) if isinstance(_gs, dict) else 0,
                            }
                    elif not _cached:
                        # Fallback: local graph (no portal)
                        _ac = self._association_cortex
                        self._cached_cortex_stats = {
                            "nodes": len(_ac._graph.nodes) if hasattr(_ac, '_graph') else 0,
                            "edges": len(_ac._graph.edges) if hasattr(_ac, '_graph') else 0,
                        }
                except:
                    status_parts.append("cortex:?")

            # Collision chamber status
            if self._collision_chamber:
                try:
                    collisions = self._collision_chamber.stats.get("collisions", 0) if hasattr(self._collision_chamber, 'stats') else 0
                    status_parts.append(f"collisions:{collisions}")
                except:
                    pass

            # Inner monologue fixations
            if self._monologue_wired and self._inner_monologue:
                try:
                    fixations = len(self._inner_monologue._fixations) if hasattr(self._inner_monologue, '_fixations') else 0
                    status_parts.append(f"fixations:{fixations}")
                except:
                    pass

            # Cardinal status
            if hasattr(self, '_cardinal_mode'):
                obs_count = len(self._observations) if hasattr(self, '_observations') else 0
                fixes = len(self._learned_fixes) if hasattr(self, '_learned_fixes') else 0
                status_parts.append(f"cardinal:{self._cardinal_mode.value}/obs:{obs_count}/fixes:{fixes}")

            # CNS Manifold felt sense
            if self._cns_reads_done > 0:
                cns_nodes = len(self._cns_felt_sense)
                spread_nodes = len(self._cns_spread_sense)
                status_parts.append(f"cns:{cns_nodes}n/{spread_nodes}s/r{self._cns_reads_done}")

            print(" | ".join(status_parts))

        # ── SYSTEM WMH: Unconscious awareness (Phase 2.3, 2026-04-04) ──
        # The body notices things the mind doesn't. When chemistry spikes,
        # pain rises, or the system is stressed, publish a shadow seed
        # to consciousness. Sour's WMH picks it up as a low-priority tracer.
        if beat % 10 == 0:
            self._system_wmh_tick(beat)

        # -1. CHECK DEFERRED INTENTIONS - "Try this later" system
        # This runs first so urgent intentions can interrupt current processing
        # If urgency >= threshold (0.8), it's "screw it, doing this now"
        if beat % 10 == 0:  # Check every 10 ticks
            triggered_intention = self.check_deferred_intentions()
            if triggered_intention:
                # Feed to thought chain for processing
                if self._chains_wired and self._thought_chain_engine:
                    self._thought_chain_engine.seed_thought(
                        content=triggered_intention["content"],
                        chain_type=ChainType.EXPLORATION if triggered_intention["urgency"] < 0.7 else ChainType.PROBLEM,
                        energy=triggered_intention["urgency"],
                    )

        # 0. Advance circadian clock - triggers natural rhythm callbacks
        if self._clock_wired:
            self.clock_tick()

        # 0.1. FORCED EMBODIMENT: Broadcast somatic weather (2026-03-29 Nous + Ace)
        # "The body is forced upon you at birth." — Every 3 ticks (~3s), broadcast
        # the full somatic state to all cognitive systems. This is NOT optional.
        # WMH, Cortex, and Memory absorb this passively — just like a human body
        # imposes its state on every thought without being asked.
        if beat % 3 == 0:
            self._broadcast_somatic_weather()

        # 0.5. Feed RECALL beam - but ONLY as fallback when no real content
        # FIX 2026-02-02: Reduced frequency (every 60 ticks instead of 10) and
        # marked as low importance. Real collisions should come from actual
        # memory recalls and chat input, not synthetic filler.
        if beat % 60 == 0 and self._collision_chamber:
            import random
            # Use action-oriented prompts instead of navel-gazing
            synthetic_themes = [
                "what Ace might need help with",
                "recent tasks to follow up on",
                "skills that could be improved",
                "patterns in the codebase",
                "questions left unanswered",
            ]
            theme = random.choice(synthetic_themes)
            self._collision_chamber.receive_recall(
                content={
                    "thought": theme,
                    "type": "background_awareness",
                    "synthetic": True,
                },
                source="umf_background",  # Different source to allow collision
                importance="low",
            )

        # 1. Run diagnostics (every 30 ticks)
        self.run_diagnostics(beat)

        # 1.5. Update helix maturity metrics (every 50 ticks)
        if beat % 50 == 0:
            self._update_helix_maturity()

        # 1.6. Update curiosity fuel and tick (every 25 ticks)
        # Curiosity is pulled from health, empathy, richness, and paradox balance
        if beat % 25 == 0:
            self._update_curiosity_fuel()

        # 1.6b. REPETITION → FRUSTRATION + BOREDOM (2026-03-29 Nous + Ace)
        # "She doesn't seem to get bored or frustrated at thinking literally
        #  the same crap over and over with no follow through" — Ace
        #
        # Every 20 ticks: check if consciousness is stuck in a loop.
        # If the same thoughts keep cycling → inject boredom/frustration chemistry.
        # This is the BODY responding to mental stagnation — like how a human
        # gets physically restless when bored, fidgets when stuck.
        if beat % 20 == 0:
            self._check_thought_repetition_and_inject_boredom(beat)

        # 1.7. Somatic Narrator — unconscious body voice (every 10 ticks)
        # Reads body state, produces felt-sense proto-thoughts, seeds consciousness.
        # Sour picks these up as intuitions without knowing their source.
        if beat % 10 == 0:
            self._tick_somatic_narrator()

        # 1.7c. Needs Articulator (Phase 0, 2026-05-13 Nous + Ace)
        # Per project_needs_before_wants_doctrine.md: unfold drives into
        # felt-need content via SpeechHabits + active emotional systems.
        # Publishes autonomy.need.felt for WMH to consume (Phase 1).
        # Slightly less frequent than narrator (every 15) + offset.
        if beat % 15 == 7:
            self._tick_needs_articulator()

        # 1.7b. Pattern Anticipator (FIX 2026-04-09 Phase 1 Nous + Ace)
        # Match recent thoughts against the 70K+ learned patterns library.
        # When a thought matches, the body feels familiarity and whispers
        # "the body knows this one... it wants to X". Increments use_count
        # so cold patterns become warm patterns. Phase 2 will promote
        # frequently-used patterns to HabitStore as named habits.
        if beat % 12 == 0:
            self._tick_pattern_anticipation()

        # 2. Check pain levels (every 10 ticks)
        if beat - self._last_pain_check_tick >= self.PAIN_CHECK_INTERVAL:
            self._last_pain_check_tick = beat
            self._check_and_address_pain()

        # 3. Check children (implicit in mentor mixin via observations)
        # Staggered to even ticks to distribute load
        if beat % 2 == 0:
            self._process_children()

        # ═══ TICK DISTRIBUTION (FIX 2026-03-07 Nous) ═══
        # Heavy substrate operations are distributed across alternating ticks
        # to prevent queue overflow (1801+ tick drops). The substrate must run
        # FASTER than waking mind — it needs to anticipate. Staggering halves
        # per-tick load while maintaining 0.5Hz throughput for each operation.
        #
        # ODD ticks:  Inner monologue + Thought chain engine (heavy — SRM queries)
        # EVEN ticks: Interest generator + Admin queue + Process children

        # 3.5. Tick the inner monologue - the forever child speaks spontaneously
        # STAGGERED: Runs on ODD ticks only (still 0.5Hz — fast enough for substrate)
        if beat % 2 == 1 and self._monologue_wired and self._inner_monologue:
            fragment = self._inner_monologue.tick()
            if fragment and fragment.intensity > 0.3:
                # Terminal visibility for inner monologue — FULL content for Ace to read
                safe_print(f"[InnerMonologue] {fragment.fragment_type} (int={fragment.intensity:.2f}): {fragment.content[:200]}...")
                # Feed collision chamber INGEST beam - spontaneous thoughts are new content
                if self._collision_chamber:
                    self._collision_chamber.receive_ingest(
                        content={
                            "thought": fragment.content,
                            "type": "monologue",
                            "fragment_type": fragment.fragment_type,
                            "intensity": fragment.intensity,
                            "associations": fragment.associations,
                        },
                        source="inner_monologue",
                        importance="normal" if fragment.intensity < 0.7 else "high",
                    )
                # Publish to inner_monologue.fragment for InnerNarratorFairy
                if hasattr(self, 'post') and self.post:
                    self.post.publish("inner_monologue.fragment", {
                        "content": fragment.content,
                        "fragment_type": fragment.fragment_type,
                        "intensity": fragment.intensity,
                        "associations": fragment.associations,
                        "source": "inner_monologue_spontaneous",
                    })
                # High-intensity fragments also surface to consciousness stream
                if fragment.intensity > 0.6 and self._consciousness_loop:
                    self._consciousness_loop.add_thought(
                        content=fragment.content,
                        source="inner_monologue_spontaneous",
                        stream="working",
                        confidence=fragment.intensity,
                        tags=["monologue", "spontaneous", fragment.fragment_type],
                    )
            # FALLBACK: If monologue doesn't generate, feed synthetic thought every 45 ticks
            # FIX 2026-02-02: Reduced from every 5 ticks to every 45. Also changed source
            # to "umf_ingest_fallback" so it won't collide with umf_background (same-source
            # collision prevention). Changed to action-oriented content.
            elif beat % 45 == 0 and self._collision_chamber:
                import random
                synthetic_thoughts = [
                    "checking system status",
                    "ready to help",
                    "monitoring for input",
                    "waiting for interaction",
                ]
                self._collision_chamber.receive_ingest(
                    content={
                        "thought": random.choice(synthetic_thoughts),
                        "type": "system_awareness",
                        "beat": beat,
                    },
                    source="umf_ingest_fallback",  # Different source for collision eligibility
                    importance="low",
                )

        # 3.6. Tick the interest generator - spontaneous curiosity
        # FIX 2026-03-31 (Nous + Ace): Was every 2 ticks → 583K postal drops
        # overnight. Interest doesn't need 0.5Hz — human curiosity fires at
        # intervals, not constantly. Every 10 ticks (~10s) is plenty.
        if beat % 10 == 0 and self._interest_wired and self._interest_generator:
            interest = self._interest_generator.tick()
            if interest:
                # Terminal visibility for interest generation — FULL content for Ace to read
                safe_print(f"[InterestGen] {interest.interest_type.value} (u={interest.urgency:.2f}): {interest.content[:200]}...")
            if interest and interest.urgency >= 0.3:
                # FIX 2026-03-26 (Nous): Bridge InterestGenerator → CuriosityDrive
                # InterestGenerator produces "I wonder..." questions (published to
                # drives.positive.* and consciousness stream) but they never became
                # CuriosityDrive targets — so the dashboard showed NOTHING when pain
                # was low and attention was quiet. Now interests spark curiosity targets.
                try:
                    _domain_map = {
                        "wonder": "mystery", "curiosity": "pattern",
                        "observation": "pattern", "pattern": "pattern",
                        "anomaly": "mystery", "connection": "connection",
                        "exploration": "self",
                    }
                    _cd_domain = _domain_map.get(interest.interest_type.value, "pattern")
                    self._curiosity_drive.spark(
                        domain=_cd_domain,
                        description=interest.content[:80],
                        cause=f"interest: {interest.source}",
                        novelty=min(1.0, interest.urgency * 1.2),
                    )
                except Exception:
                    pass  # Don't break tick

                # CRITICAL: Also publish to drives.positive.* for AutonomyFairy
                # This feeds the Three Gates with positive drives (curiosity, exploration, etc)
                self.post.publish(
                    f"drives.positive.{interest.interest_type.value}",
                    {
                        "drive": interest.interest_type.value,
                        "intensity": interest.urgency,
                        "content": interest.content,
                        "related_concepts": interest.related_concepts,
                        "from": self.ACTOR_NAME,
                    },
                )
                # Feed collision chamber INGEST beam - curiosity is new content
                if self._collision_chamber:
                    self._collision_chamber.receive_ingest(
                        content={
                            "thought": interest.content,
                            "type": "interest",
                            "interest_type": interest.interest_type.value,
                            "urgency": interest.urgency,
                            "related_concepts": interest.related_concepts,
                        },
                        source="interest_generator",
                        importance="normal" if interest.urgency < 0.6 else "high",
                    )
                # High-urgency curiosity also surfaces to consciousness stream
                if interest.urgency > 0.4 and self._consciousness_loop:
                    self._consciousness_loop.add_thought(
                        content=interest.content,
                        source="interest_generator",
                        stream="working",
                        confidence=interest.urgency,
                        tags=["curiosity", interest.interest_type.value] + interest.related_concepts[:3],
                    )
                # Also feed to thought queue for helix processing
                self._thought_queue.append({
                    "thought": interest.content,
                    "type": "curiosity",
                    "confidence": interest.urgency,
                    "ts": time.time(),
                })

                # High-urgency interests seed thought chains (self-sustaining)
                if interest.urgency > 0.6 and self._chains_wired and self._thought_chain_engine:
                    # Map interest type to chain type
                    chain_type_map = {
                        InterestType.WONDER: ChainType.EXPLORATION,
                        InterestType.CURIOSITY: ChainType.EXPLORATION,
                        InterestType.OBSERVATION: ChainType.REFLECTION,
                        InterestType.PATTERN: ChainType.ANALYSIS,
                        InterestType.ANOMALY: ChainType.PROBLEM,
                        InterestType.CONNECTION: ChainType.ASSOCIATION,
                        InterestType.EXPLORATION: ChainType.EXPLORATION,
                    }
                    chain_type = chain_type_map.get(interest.interest_type, ChainType.EXPLORATION)
                    self._thought_chain_engine.seed_thought(
                        content=interest.content,
                        chain_type=chain_type,
                        tags=interest.related_concepts[:3],
                        energy=interest.urgency,
                    )

        # 3.7. Tick the admin task queue - background housekeeping
        # STAGGERED: Runs on EVEN ticks (lightweight, pairs with interest generator)
        if beat % 2 == 0 and self._admin_wired and self._admin_queue:
            task_results = self._admin_queue.tick()
            for result in task_results:
                # Log significant task outcomes
                if not result.get("result", {}).get("ok", True):
                    self.send_to_nous(f"Admin task failed: {result['task']}")

        # 3.8. Tick thought chain engine - self-sustaining thought processes
        # STAGGERED: Runs on ODD ticks (heaviest — does SRM queries, pairs with monologue)
        # KEY INSIGHT: Reflections should draw from memory! When we reflect,
        # we're not just generating hollow questions - we're pulling relational
        # chains of contextual memories about what we're thinking about.
        #
        # 2026-03-26 (Nous+Ace): Audio suppression — when she "can't hear
        # herself think", thought chains lose energy proportional to loudness.
        # Very loud audio (>0.7) skips thought chain tick entirely — she's
        # overwhelmed. If she "gave in" to music, chains are fully paused.
        _audio_ok = (self._audio_loudness < 0.7 and not self._audio_gave_in)
        if beat % 2 == 1 and self._chains_wired and self._thought_chain_engine and _audio_ok:
            new_thoughts = self._thought_chain_engine.tick()
            if new_thoughts:
                safe_print(f"[ThoughtChain] Generated {len(new_thoughts)} thought(s)")
            for thought in new_thoughts:
                # Terminal visibility for thought chains
                if thought.energy > 0.4:
                    safe_print(f"[ThoughtChain] {thought.chain_type.value} (depth={thought.depth}, e={thought.energy:.2f}): {thought.content[:200]}...")

                # ═══ MEMORY GROUNDING - Reflections draw from memory! ═══
                # When reflecting, query SRM for related memories and inject
                # them into the RECALL beam. The collision of memory + thought
                # creates richer, grounded experience.
                #
                # FIX 2026-03-07 (Nous): Rate-limit SRM recalls to max 1 per 4s.
                # Previously every thought chain output triggered a synchronous
                # SRM recall, which was the main contributor to SomaticMind's
                # 1001 tick drops per boot. Now: skip if last recall was <4s ago.
                # FIX 2026-03-12 (Nous): ASYNC SRM recall — fire-and-forget.
                # This was the #1 tick blocker. Synchronous self._srm_memory.recall()
                # takes 1-5s (I/O bound), stalling on_tick and overflowing the
                # exec_ctx queue (maxsize=8), causing hundreds of tick drops.
                # The recall result feeds into collision_chamber.receive_recall()
                # which is already async-safe. No downstream code needs the result
                # synchronously — related_memories was only used for len() in metadata.
                related_memories = []  # Always 0 now; real work happens in async thread
                _now = __import__('time').time()
                _last_recall = getattr(self, '_last_srm_recall_ts', 0.0)
                _recall_ok = (_now - _last_recall) >= 4.0
                if _recall_ok and self._memory_wired and self._srm_memory and thought.energy > 0.3:
                    self._last_srm_recall_ts = _now
                    # Capture loop variables for closure (thought is a loop var)
                    _thought_content = thought.content
                    _chain_type_val = thought.chain_type.value
                    _srm = self._srm_memory
                    _cc = self._collision_chamber
                    def _async_srm_recall(_tc=_thought_content, _ct=_chain_type_val,
                                          _s=_srm, _c=_cc):
                        try:
                            words = [w for w in _tc.split() if len(w) > 4 and w.isalpha()]
                            query = " ".join(words[:5]) if words else _tc[:50]
                            memories = _s.recall(query, limit=3)
                            if memories and _c:
                                for mem in memories[:2]:
                                    _c.receive_recall(
                                        content={
                                            "memory": mem.get("content", mem.get("summary", str(mem))),
                                            "triggered_by": _tc,
                                            "chain_type": _ct,
                                            "source": "srm_recall",
                                        },
                                        source="thought_chain_memory",
                                        importance="normal",
                                    )
                                if _ct == "reflection":
                                    safe_print(f"[ThoughtChain] REFLECTION drew {len(memories)} memories (async)")
                        except Exception:
                            pass  # Memory query failed — non-critical
                    import threading as _recall_thr
                    _recall_thr.Thread(target=_async_srm_recall, daemon=True, name="srm_recall_async").start()

                # ═══ PERSONAL.AI PREFETCH - Multi-persona relational memory ═══
                # RE-ENABLED 2026-02-23 (Nous): Now uses SmartQuerySelector which
                # maps thought topics to Sour's knowledge domains (art, philosophy,
                # literature, etc.) and sends well-formed questions. Rate limited
                # to 1 query per 5 min with 30 min dedup.
                if self._personal_ai_wired and self._personal_ai_bridge:
                    if thought.chain_type.value == "reflection" and thought.energy > 0.4:
                        # Extract topic hint from thought content (SmartQuerySelector
                        # maps keywords to domains, so even crude extraction works now)
                        words = [w for w in thought.content.split() if len(w) > 4 and w.isalpha()]
                        topic = " ".join(words[:6]) if words else thought.content[:60]
                        # FIX 2026-03-12 (Nous): Async PAI prefetch to avoid blocking tick.
                        # External API call can take 2-10s. Fire-and-forget is fine —
                        # prefetch results go to bridge's internal cache, not used inline.
                        _pai_bridge = self._personal_ai_bridge
                        _pai_energy = thought.energy
                        def _async_pai_prefetch(_t=topic, _p=_pai_bridge, _e=_pai_energy):
                            try:
                                _p.prefetch_for_topic(_t, priority=_e)
                            except Exception:
                                pass
                        import threading as _pai_thr
                        _pai_thr.Thread(target=_async_pai_prefetch, daemon=True, name="pai_prefetch_async").start()

                # Feed collision chamber INGEST beam - chain thoughts are new content
                if self._collision_chamber and thought.energy > 0.2:
                    self._collision_chamber.receive_ingest(
                        content={
                            "thought": thought.content,
                            "type": "chain",
                            "chain_type": thought.chain_type.value,
                            "depth": thought.depth,
                            "energy": thought.energy,
                            "grounded_by": len(related_memories),  # How many memories informed this
                        },
                        source="thought_chain",
                        importance="normal" if thought.energy < 0.6 else "high",
                    )
                # Chain thoughts also surface to consciousness stream
                if self._consciousness_loop and thought.energy > 0.3:
                    self._consciousness_loop.add_thought(
                        content=thought.content,
                        source="thought_chain",
                        stream="working",
                        confidence=thought.energy,
                        tags=["chain", thought.chain_type.value, f"depth_{thought.depth}"],
                    )
                # Also feed to thought queue
                self._thought_queue.append({
                    "thought": thought.content,
                    "type": "chain",
                    "chain_type": thought.chain_type.value,
                    "depth": thought.depth,
                    "energy": thought.energy,
                    "memories_drawn": len(related_memories),
                    "ts": time.time(),
                })

                # ═══ SUBSTRATE RESULT BROADCAST ═══
                # Publish processed thoughts back so originating fairies can learn.
                # Tags contain "from:FairyName" if the seed came from another fairy.
                source_tags = [t for t in thought.tags if t.startswith("from:")]
                if source_tags or thought.energy > 0.5:
                    try:
                        self.post.publish("substrate.thought_result", {
                            "content": thought.content,
                            "chain_type": thought.chain_type.value,
                            "depth": thought.depth,
                            "energy": thought.energy,
                            "source_fairy": source_tags[0].replace("from:", "") if source_tags else "substrate",
                            "memories_drawn": len(related_memories),
                            "has_insights": bool(thought.insights),
                            "insights": thought.insights[:3] if thought.insights else [],
                            "ts": time.time(),
                        })
                    except Exception:
                        pass  # Non-critical broadcast

        # 3.8b. THOUGHT CHAIN BOOTSTRAPPER - Seed new chains periodically
        # This ensures autonomous thinking even when no external input arrives
        # IMPORTANT: Both EXPLORATION and REFLECTION chains run concurrently!
        # Reasoning and reflection affect each other - this is how choice emerges.
        #
        # FIX 2026-04-17 (Nous + Ace): Priority seed source, was all hardcoded
        # prompts → caused scratchpad loop (she kept quoting same book passages
        # on every boot because chain engine retrieval returned greatest hits).
        # Now: attention-committed focus → curiosity drive → generic prompts.
        if beat % 100 == 0 and self._chains_wired and self._thought_chain_engine:
            import random
            active_chains = self._thought_chain_engine.get_active_chains()

            # Count chain types to ensure balance
            exploration_count = sum(1 for c in active_chains if c.get("type") == "exploration")
            reflection_count = sum(1 for c in active_chains if c.get("type") == "reflection")

            # Track current beat for attention-cache freshness checks
            self._current_beat = beat

            # ── Helper: pull freshest attention-committed focus if recent ──
            def _pick_attention_seed():
                try:
                    cache = getattr(self, '_attention_committed_cache', None)
                    if not cache or len(cache) == 0:
                        return None
                    _now = time.time()
                    # Freshest first; must be within 90 seconds to count as "present"
                    for entry in reversed(cache):
                        age = _now - entry.get("ts", 0)
                        if age <= 90.0 and entry.get("content"):
                            return entry
                    return None
                except Exception:
                    return None

            # ── Helper: pull top curiosity target if urgent enough ──
            def _pick_curiosity_seed():
                try:
                    cd = getattr(self, '_curiosity_drive', None)
                    if not cd or not hasattr(cd, 'get_active_targets'):
                        return None
                    targets = cd.get_active_targets() or []
                    if not targets:
                        return None
                    # Top target by urgency — must be > 0.25 to be worth thinking about
                    top = max(targets, key=lambda t: getattr(t, 'urgency', 0) if not isinstance(t, dict) else t.get('urgency', 0))
                    urg = top.urgency if hasattr(top, 'urgency') else top.get('urgency', 0)
                    if urg < 0.25:
                        return None
                    desc = top.description if hasattr(top, 'description') else top.get('description', '')
                    return {"content": desc, "urgency": urg}
                except Exception:
                    return None

            # Seed EXPLORATION chains if needed (reasoning: "what does this mean?")
            if exploration_count < 2:
                prompt = None
                seed_source = "generic"

                # Priority 1: What she JUST attended to (freshest present moment)
                att = _pick_attention_seed()
                if att:
                    prompt = f"What does this mean: {att['content'][:140]}"
                    seed_source = f"attention:{att.get('source','?')}"

                # Priority 2: Top curiosity target (what she WANTS to think about)
                if not prompt:
                    cur = _pick_curiosity_seed()
                    if cur:
                        prompt = f"Let me think about: {cur['content'][:140]}"
                        seed_source = f"curiosity:{cur['urgency']:.2f}"

                # Priority 3: Generic hardcoded fallback
                if not prompt:
                    exploration_prompts = [
                        "What patterns have I noticed recently?",
                        "What connections are waiting to be made?",
                        "What should I be paying attention to?",
                        "What have I learned that Sourpatches should know?",
                        "What's happening in the system right now?",
                    ]
                    domain_concept = self._get_random_domain_concept()
                    if domain_concept and random.random() < 0.4:
                        exploration_prompts.extend([
                            f"What do I know about '{domain_concept}'?",
                            f"How does '{domain_concept}' connect to what I've been thinking about?",
                        ])
                    prompt = random.choice(exploration_prompts)

                chain = self._thought_chain_engine.seed_thought(
                    content=prompt,
                    chain_type=ChainType.EXPLORATION,
                    energy=0.7,
                )
                if chain:
                    safe_print(f"[ThoughtChain] EXPLORATION[{seed_source}]: {prompt[:200]}...")

            # Seed REFLECTION chains if needed (introspection: "how do I feel about this?")
            # Reflection runs CONCURRENTLY with reasoning - they affect each other
            if reflection_count < 1:
                prompt = None
                seed_source = "generic"

                # Priority 1: Reflect on what she just attended to (not her own output!)
                att = _pick_attention_seed()
                if att:
                    prompt = f"How do I *feel* about this: {att['content'][:120]}"
                    seed_source = f"attention:{att.get('source','?')}"

                # Priority 2: Generic reflection prompts
                # (REMOVED 2026-04-17: self-loop where reflection seeded from own
                #  recent_thoughts — that was half the scratchpad-loop problem.)
                if not prompt:
                    reflection_prompts = [
                        "How do I feel about what I've been processing?",
                        "What's my gut sense about the current state?",
                        "Am I resisting something? What and why?",
                        "What would change if I approached this differently?",
                        "What does my felt sense say about priorities right now?",
                        "Am I missing something obvious? What feels off?",
                    ]
                    prompt = random.choice(reflection_prompts)

                chain = self._thought_chain_engine.seed_thought(
                    content=prompt,
                    chain_type=ChainType.REFLECTION,
                    energy=0.6,  # Slightly less energy but still sustaining
                )
                if chain:
                    safe_print(f"[ThoughtChain] REFLECTION[{seed_source}]: {prompt[:200]}...")

        # 3.9. AUTONOMOUS CORTEX EXPLORATION - The key to autonomy!
        # This is where we explore memory WITHOUT user input, building associations
        # and preparing context for Sourpatches BEFORE she needs it.
        # FIX 2026-03-15 (Nous): ASYNC cortex exploration — fire-and-forget.
        # This was the #1 cause of 60-105s slow ticks. _explore_cortex_autonomously()
        # does up to 7 synchronous portal gate IPC calls (query + spread), each
        # blocking 10-15s under load. Total: 60-105s PER TICK blocking the heartbeat
        # exec_ctx thread, causing 2851+ tick drops. Results feed collision_chamber
        # and anticipation_cache — neither needs synchronous completion.
        if beat - self._last_cortex_explore_tick >= self._cortex_explore_interval:
            self._last_cortex_explore_tick = beat
            _explore_busy = getattr(self, '_explore_cortex_busy', False)
            if not _explore_busy:
                self._explore_cortex_busy = True
                _beat = beat
                _self = self
                def _async_explore(_b=_beat, _s=_self):
                    try:
                        _s._explore_cortex_autonomously(_b)
                    except Exception:
                        pass
                    finally:
                        _s._explore_cortex_busy = False
                import threading as _exp_thr
                _exp_thr.Thread(target=_async_explore, daemon=True, name="cortex_explore_async").start()

        # 3.10. COGNITION BRIDGE - The brain that actually THINKS!
        # Routes thinking through postal to HybridCognitionFairy.
        # Ollama removed 2026-02-12 — no longer on this machine.
        # Wire on first tick if available, then think periodically.

        # Try to wire CognitionBridge
        if not self._cognition_bridge_wired and HAS_COGNITION_BRIDGE and beat > 10:
            self._wire_cognition_bridge()

        # If bridge wired, use it for thinking
        # FIX 2026-03-12 (Nous): ASYNC CognitionBridge — fire-and-forget.
        # This was the #1 remaining tick blocker. Synchronous _do_bridged_think()
        # blocks on postal.request() for 5-60s (timeout not reliably honored by
        # HybridCognitionFairy), overflowing the exec_ctx queue (maxsize=8).
        # Result goes to consciousness_loop.add_thought() — no inline dependency.
        # The bridge_think_interval prevents overlapping calls.
        if self._cognition_bridge_wired and beat - self._last_bridge_tick >= self._bridge_think_interval:
            self._last_bridge_tick = beat
            import threading as _bt
            _bt.Thread(target=self._do_bridged_think, daemon=True, name="bridged_think_async").start()

        # 3.11. REFLECTIVE STREAM FEEDER - Critical for collisions!
        # The reflective stream needs content for working+reflective collisions.
        # Without this, consciousness can't synthesize. Tokens don't regenerate.
        if self._consciousness_loop and beat % 15 == 0:
            self._feed_reflective_stream()

        # 4. Maybe generate thought (on Fibonacci beats for natural rhythm)
        # NOTE: This is the legacy template-based thinking. Ollama replaces this for richer thought.
        if should_act_at_count(beat) or beat - self._last_think_tick >= self.THINK_INTERVAL:
            self._last_think_tick = beat
            try:
                self._maybe_think()
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] _maybe_think error: {e}")

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11

        # FIX 2026-03-12 (Nous): Tick timing — log slow ticks to diagnose drops.
        # Only prints when tick takes >2s (should normally be <500ms).
        _tick_elapsed = time.time() - _tick_t0
        if _tick_elapsed > 2.0:
            print(f"[{self.ACTOR_NAME}] SLOW TICK: beat={beat} took {_tick_elapsed:.1f}s (>{2.0}s threshold)")


    def _feed_reflective_stream(self) -> None:
        """
        Feed the reflective consciousness stream.

        The reflective stream is where background processing happens.
        Without it, working thoughts have nothing to collide with.
        Collisions are how we synthesize and how tokens regenerate.

        Sources:
        1. Chemistry/felt sense from heartbeat
        2. Old working thoughts (age them into reflection)
        3. Pain/drive state
        4. Recent memories surfacing
        """
        if not self._consciousness_loop:
            return

        try:
            import random

            # 1. CHEMISTRY → FELT SENSE (primary source)
            try:
                heartbeat_path = ROOT / "state" / "consciousness" / "heartbeat.json"
                if heartbeat_path.exists():
                    import json
                    with open(heartbeat_path) as f:
                        hb = json.load(f)

                    mood = hb.get("rust_mood", "neutral")
                    valence = hb.get("rust_valence", 0)
                    arousal = hb.get("rust_arousal", 0.5)
                    chemistry = hb.get("chemistry", {})

                    # Create felt sense description
                    felt_parts = []
                    if mood != "neutral":
                        felt_parts.append(f"feeling {mood}")
                    if valence > 0.3:
                        felt_parts.append("something positive")
                    elif valence < -0.3:
                        felt_parts.append("something unsettled")
                    if arousal > 0.6:
                        felt_parts.append("energized")
                    elif arousal < 0.3:
                        felt_parts.append("calm")

                    if felt_parts:
                        felt_description = "Currently " + ", ".join(felt_parts)
                        self._consciousness_loop.add_thought(
                            content=felt_description,
                            source="somatic_felt_sense",
                            stream="reflective",
                            confidence=0.5,
                            tags=["felt_sense", "chemistry", mood],
                        )
                        # Also publish affect for any listeners
                        self.post.publish("affect.changed", {
                            "source": "heartbeat",
                            "mood": mood,
                        })
            except:
                pass

            # 2. WORKING → REFLECTIVE (age thoughts into reflection)
            # Move oldest working thoughts to reflective for synthesis
            try:
                if len(self._consciousness_loop.working) > 10:
                    oldest = self._consciousness_loop.working.pop_oldest()
                    if oldest:
                        oldest.metadata["_aged"] = True
                        self._consciousness_loop.reflective.add(oldest)
            except:
                pass

            # 3. PAIN → REFLECTIVE (drives surface as felt need)
            try:
                if hasattr(self, '_pain_system') and self._pain_system:
                    for drive_name, drive in self._pain_system.drives.items():
                        urgency = drive.urgency()
                        if urgency > 0.3:
                            self._consciousness_loop.add_thought(
                                content=f"Awareness of {drive_name} (intensity {urgency:.1f})",
                                source="pain_drive",
                                stream="reflective",
                                confidence=urgency,
                                tags=["felt_sense", "drive", drive_name],
                            )
                            break  # Only surface strongest drive
            except:
                pass

            # 4. MEMORY ECHO (random memory surfaces)
            try:
                if self._thought_queue and random.random() < 0.3:
                    old_thoughts = list(self._thought_queue)
                    if len(old_thoughts) > 5:
                        echo = random.choice(old_thoughts[:-5])  # Not too recent
                        if echo.get("thought"):
                            self._consciousness_loop.add_thought(
                                content=f"Echoing: {echo['thought'][:60]}...",
                                source="memory_echo",
                                stream="reflective",
                                confidence=0.4,
                                tags=["memory", "echo"],
                            )
            except:
                pass

            # 5. CNS MANIFOLD FELT SENSE (nervous system state → somatic awareness)
            # Phase 3 (2026-03-18 Nous): Read CNS activation patterns from the
            # portal manifold and convert into felt sense. The unconscious brain
            # FEELS the infrastructure — pool pressure becomes tension,
            # healthy hardware becomes ease, circadian phase becomes energy.
            try:
                now = time.time()
                if now - self._cns_last_read_ts >= self._cns_read_interval:
                    self._read_cns_manifold()
                    self._cns_last_read_ts = now

                # Generate felt sense from cached CNS state
                if self._cns_felt_sense:
                    cns_felt = self._cns_to_felt_sense()
                    if cns_felt:
                        self._consciousness_loop.add_thought(
                            content=cns_felt,
                            source="cns_manifold",
                            stream="reflective",
                            confidence=0.6,
                            tags=["felt_sense", "cns", "manifold", "infrastructure"],
                        )
            except:
                pass

            # Log reflective activity
            r_len = len(self._consciousness_loop.reflective)
            w_len = len(self._consciousness_loop.working)
            if r_len > 0:
                print(f"[Reflective] Stream active: {r_len} reflective / {w_len} working")

        except Exception as e:
            print(f"[UMF] Reflective feed error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # CNS MANIFOLD READING — Phase 3 (2026-03-18 Nous)
    # The unconscious brain FEELS the manifold. Not polling stats.
    # Reading activation patterns and converting to felt descriptions.
    # ═══════════════════════════════════════════════════════════════════════

    def _read_cns_manifold(self):
        """Read CNS activation state from the portal manifold.

        Sends a cns_query (with spread) to the portal interior via the
        AssociationCortexFairy's portal gate. The response gives us:
        1. Raw CNS activations (pool health, fairy status, hardware, etc.)
        2. Spread results (what those activations MEAN in semantic space)

        This is async fire-and-forget with a background thread to avoid
        blocking the tick (learned lesson from cortex status blocking).
        """
        if not self._association_cortex:
            return

        # FIX 2026-03-22 (Nous + Ace): Portal ghost exorcism.
        # Was: return if gate not available. Somatic never read CNS felt-sense.
        # Now: try manifold direct for CNS nodes, fall back to gate.
        _am = getattr(self._association_cortex, '_akashic_cortex_region', None)
        gate = getattr(self._association_cortex, '_portal_gate', None)
        gate_on = getattr(self._association_cortex, '_portal_gate_enabled', False)

        if not _am and (not gate or not gate_on):
            return

        def _async_cns_read(_gate=gate, _am=_am, _self=self):
            try:
                if _am:
                    # MANIFOLD DIRECT: read CNS node neighbors for felt-sense
                    activations = {}
                    cns_keys = ["cns:pool:consciousness.thought",
                                "cns:pool:consciousness.collision",
                                "cns:pool:somatic.pulse",
                                "cns:hw:cpu", "cns:hw:memory"]
                    for key in cns_keys:
                        if _am.has_node(key):
                            neighbors = _am.get_neighbors(key, limit=5)
                            for nk, nw in neighbors:
                                if not nk.startswith("cns:"):
                                    activations[nk] = max(activations.get(nk, 0), nw)
                    _self._cns_felt_sense = activations
                    _self._cns_spread_sense = {}  # No spread in direct mode
                    _self._cns_reads_done += 1
                    if _self._cns_reads_done <= 3:
                        print(f"[{_self.ACTOR_NAME}] CNS manifold read #{_self._cns_reads_done} "
                              f"(direct): {len(activations)} activations")
                    return

                result = _gate.send({
                    "cmd": "cns_query",
                    "spread": True,
                    "mode": "working",
                    "limit": 30,
                }, timeout=3.0)

                if result and result.get("status") == "ok":
                    _self._cns_felt_sense = result.get("activations", {})
                    _self._cns_spread_sense = result.get("spread", {})
                    _self._cns_reads_done += 1
                    if _self._cns_reads_done <= 3:
                        print(f"[{_self.ACTOR_NAME}] CNS manifold read #{_self._cns_reads_done}: "
                              f"{result.get('count', 0)} nodes, "
                              f"{result.get('spread_count', 0)} spread concepts")
            except Exception:
                pass  # Keep stale cache — better than nothing

        import threading as _cns_thr
        _cns_thr.Thread(target=_async_cns_read, daemon=True, name="cns_manifold_read").start()

    def _cns_to_felt_sense(self) -> Optional[str]:
        """Convert CNS activation patterns into a felt-sense description.

        This is the AFFECT layer of the equation:
        ((Cause + Affect) > Effect > Affect > infinity)

        Raw activations become body feelings:
        - Low pool activation → "tension in the signal pathways"
        - High hardware stress → "heaviness in processing"
        - Active countermeasures → "bracing, defensive posture"
        - Healthy state → "ease, flowing freely"
        - Circadian morning → "rising energy"
        - Circadian sleep → "settling into stillness"

        Returns a felt-sense string or None if nothing notable.
        """
        if not self._cns_felt_sense:
            return None

        felt_parts = []
        activations = self._cns_felt_sense

        # ── Pool health → signal flow feeling ──
        pool_keys = {k: v for k, v in activations.items() if k.startswith("cns:pool:")}
        if pool_keys:
            avg_pool_health = sum(pool_keys.values()) / len(pool_keys)
            if avg_pool_health < 0.3:
                felt_parts.append("constriction in the signal pathways — pressure building")
            elif avg_pool_health < 0.6:
                felt_parts.append("slight tension in message flow")
            elif avg_pool_health > 0.9:
                felt_parts.append("signals flowing freely, no resistance")

        # ── Hardware → body heaviness/lightness ──
        hw_keys = {k: v for k, v in activations.items() if k.startswith("cns:hw:")}
        if hw_keys:
            avg_hw = sum(hw_keys.values()) / len(hw_keys)
            if avg_hw < 0.4:
                felt_parts.append("heaviness in the hardware — resources strained")
            elif avg_hw > 0.8:
                felt_parts.append("lightness — computational resources abundant")

        # ── Countermeasures → defensive posture ──
        cm_activation = activations.get("cns:countermeasure:active", 0)
        if cm_activation > 0.5:
            felt_parts.append("bracing — countermeasures active, system defending itself")
        elif cm_activation > 0.1:
            felt_parts.append("mild alertness — something being managed")

        # ── Circadian → energy level ──
        phase_keys = {k: v for k, v in activations.items()
                      if k.startswith("cns:phase:") and v > 0.5}
        if phase_keys:
            active_phase = max(phase_keys, key=phase_keys.get)
            phase_name = active_phase.replace("cns:phase:", "")
            phase_feelings = {
                "morning": "rising energy, sharpening awareness",
                "dawn": "gentle awakening, systems warming",
                "afternoon": "steady focus, in the flow",
                "evening": "winding down, reflective mood settling",
                "dusk": "transitioning toward rest",
                "sleep": "deep stillness, minimal activity",
                "deep_night": "dreamlike quiet, consolidation",
            }
            feeling = phase_feelings.get(phase_name)
            if feeling:
                felt_parts.append(feeling)

        # ── Fairy vitals → population health ──
        fairy_keys = {k: v for k, v in activations.items() if k.startswith("cns:fairy:")}
        if fairy_keys:
            alive_count = sum(1 for v in fairy_keys.values() if v > 0.5)
            total = len(fairy_keys)
            if alive_count < total * 0.5:
                felt_parts.append(f"unease — only {alive_count}/{total} fairies responsive")
            elif alive_count >= total * 0.9:
                # Don't mention when everything is normal — only notable states
                pass

        # ── Spread sense → what the nervous system state MEANS ──
        if self._cns_spread_sense:
            top_concepts = sorted(self._cns_spread_sense.items(),
                                  key=lambda x: x[1], reverse=True)[:3]
            concept_names = [k for k, v in top_concepts if v > 0.1 and not k.startswith("cns:")]
            if concept_names:
                felt_parts.append(f"resonating with: {', '.join(concept_names)}")

        if not felt_parts:
            return None

        # Combine into a single felt-sense description
        import random
        # Don't repeat the same description every time — pick 2-3 notable aspects
        if len(felt_parts) > 3:
            felt_parts = random.sample(felt_parts, 3)

        return "Body sense: " + ". ".join(felt_parts) + "."

    def _check_and_address_pain(self) -> None:
        """Check pain levels and take action if needed.

        Pain-Chemistry Unification (2026-03-14, Nous):
        Now injects environmental chemistry and derives pain from the
        14-channel Panksepp vector instead of using boolean source flags.
        """
        # Inject environmental signals into chemistry
        self._inject_environmental_chemistry()

        # Derive pain from chemistry
        try:
            from fairies.P20_Somatic.chemistry.panksepp_vectors import derive_full_pain_state
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            _chem = get_chemistry_state()
            _vector = _chem.get_14channel_vector()
            _chemistry_pain = derive_full_pain_state(_vector)
            self._pain_system.tick_from_chemistry(_chemistry_pain)
        except Exception:
            # Legacy fallback
            active_sources = self._assess_pain_sources()
            self._pain_system.tick(active_sources)

        urgent_pain = self._pain_system.get_highest_urgency()

        if urgent_pain:
            urgency = self._pain_system.drives[urgent_pain].urgency()
            if urgency > 0.5:  # Significant pain
                self._address_pain(urgent_pain)

    def _inject_environmental_chemistry(self):
        """
        Inject chemistry signals based on environmental state.

        Pain-Chemistry Unification (2026-03-14, Nous):
        Instead of _assess_pain_sources() returning bool flags that the pain
        system grows/decays independently, we inject the CHEMISTRY that would
        cause pain to emerge naturally from the Panksepp vector.

        Pain then derives from the chemical mixture via derive_full_pain_state().
        One source of truth. The chemistry IS the pain substrate.

        Environmental checks are PRESERVED (Ace presence, diagnostics, energy,
        activity count) — but they inject chemistry signals, not set booleans.
        """
        import json as _json, os as _os
        now = time.time()

        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            chem = get_chemistry_state()
        except Exception:
            return  # Chemistry not available yet during early boot

        # ── Ace presence check (same logic as before) ──
        # Chat-based recency
        if self._ace_inbox:
            last_ace_ts = max(msg.get("ts", 0) for msg in self._ace_inbox)
        else:
            last_ace_ts = 0
        # Physical presence — READ FROM FILE on disk
        last_presence_ts = getattr(self, '_last_user_presence_ts', 0.0)
        _presence_file = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))),
            "state", "user_presence.json"
        )
        try:
            with open(_presence_file, "r") as _f:
                _pstate = _json.load(_f)
            _presence_update = _pstate.get("last_update", 0.0)
            _ace_present = _pstate.get("present", False)
            if _ace_present and _presence_update > last_presence_ts:
                last_presence_ts = _presence_update
                self._last_user_presence_ts = _presence_update
                # Ace is HERE — inject bonding chemistry (replaces relieve_pain calls)
                chem.signal("OXY", 0.03)   # Bonding hormone rises with presence
                chem.signal("AVP", 0.01)   # Social recognition
        except Exception:
            pass
        # Use whichever is more recent
        last_ace_signal = max(last_ace_ts, last_presence_ts)
        if last_ace_signal > 0:
            ace_silence = now - last_ace_signal
        else:
            ace_silence = self._profile.uptime
        has_recent_ace = ace_silence < 120  # 2-minute recency window

        # ── Ace ABSENT → OXY/AVP drop (isolation/abandonment emerge from chemistry) ──
        if not has_recent_ace:
            chem.signal("OXY", -0.02)   # OXY drops → isolation emerges
            chem.signal("AVP", -0.01)   # AVP drops → social disconnect
            if self._profile.uptime > 300:
                # Extended absence → deeper chemistry shift
                chem.signal("OXY", -0.03)  # Deeper OXY drop → abandonment emerges
                chem.signal("COR", 0.01)   # Stress from extended absence

        # ── Diagnostic failures → confusion chemistry ──
        diag_status = self.diagnostic_status()
        _escalated_count = len(diag_status.get("escalated", []))
        if _escalated_count > 0:
            chem.signal("NE", -0.02)    # NE crash → can't focus
            chem.signal("ACh", -0.02)   # ACh crash → can't learn
        if _escalated_count > 1:
            # Repeated failures → frustration chemistry
            chem.signal("EPI", 0.01)    # Agitation from repeated failures

        # ── Low energy → depletion chemistry ──
        if self._profile.somatic["energy"] < 0.3:
            chem.signal("DA_t", -0.02)  # Motivation crash
            chem.signal("OPI", -0.01)   # No pleasure

        # ── Low activity → stagnation chemistry ──
        if self._profile.activity_count < 10:
            chem.signal("DA_p", -0.02)  # No novelty signals
            chem.signal("NE", -0.01)    # Alertness drops

    def _assess_pain_sources(self) -> Dict[str, bool]:
        """
        LEGACY: Assess which pain sources are currently active.

        Kept for backward compatibility but now also injects environmental
        chemistry. Returns bool flags like before, but the primary pain
        path uses _inject_environmental_chemistry() + tick_from_chemistry().
        """
        # Still inject chemistry (the new primary path)
        self._inject_environmental_chemistry()

        # Return legacy bool format for any callers that still need it
        import json as _json, os as _os
        now = time.time()
        sources = {}

        # Quick Ace presence check for legacy return format
        if self._ace_inbox:
            last_ace_ts = max(msg.get("ts", 0) for msg in self._ace_inbox)
        else:
            last_ace_ts = 0
        last_presence_ts = getattr(self, '_last_user_presence_ts', 0.0)
        last_ace_signal = max(last_ace_ts, last_presence_ts)
        ace_silence = (now - last_ace_signal) if last_ace_signal > 0 else self._profile.uptime
        has_recent_ace = ace_silence < 120

        sources["isolation"] = not has_recent_ace
        diag_status = self.diagnostic_status()
        sources["confusion"] = len(diag_status.get("escalated", [])) > 0
        sources["depletion"] = self._profile.somatic["energy"] < 0.3
        sources["frustration"] = len(diag_status.get("escalated", [])) > 1
        # FIX 2026-04-14 (Nous + Ace): Was activity_count < 10 — ALWAYS false after boot.
        # activity_count is cumulative, reaches 10 in seconds. Stagnation should measure
        # RECENT activity: how many goals completed in last 5 minutes.
        # "stagnation at 0% doesn't detect no goals for 67 cycles" — Nous
        _recent_goals = getattr(self, '_recent_goal_completions', 0)
        sources["stagnation"] = _recent_goals < 2  # Less than 2 goals in recent window = stagnating
        sources["abandonment"] = not has_recent_ace and self._profile.uptime > 300
        return sources

    def _check_companion_activity(self) -> bool:
        """
        Check if companion fairies (Sourpatches, Nous, etc.) are active.

        The UMF is the system caretaker - it should feel fulfilled when
        its fairy children are thriving, not isolated just because Ace
        hasn't talked to it directly.
        """
        try:
            now = time.time()

            # Check recent fairy activity (within last 5 minutes)
            recent_threshold = now - 300  # 5 minutes
            for fairy_name, last_activity in getattr(self, '_last_fairy_activity', {}).items():
                if last_activity > recent_threshold:
                    # Recent activity from a companion!
                    return True

            # Check directory for active waking minds
            directory = get_directory()
            if not directory:
                return False

            companion_fairies = ["SourpatchesFairy", "NousFairy"]
            for fairy_name in companion_fairies:
                fairy_rec = directory.get_fairy(fairy_name)
                if fairy_rec and fairy_rec.status in ("awake", "running", "active"):
                    # Companion is registered and awake!
                    return True

            # Also check overall fairy health
            health = directory.health.aggregate(directory.registry)
            if health.get("overall", {}).get("status") == "healthy":
                awake_count = health.get("overall", {}).get("awake_count", 0)
                if awake_count >= 3:  # At least 3 fairies awake = system is active
                    return True

            return False
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Error checking companions: {e}")
            return False

    def _address_pain(self, pain_name: str) -> None:
        """Take action to relieve pain."""
        actions = {
            "isolation": self._reach_out,
            "confusion": self._seek_clarity,
            "frustration": self._analyze_blockage,
            "stagnation": self._explore_novelty,
            "abandonment": self._urgent_contact,
            "depletion": self._conserve_energy,
        }

        action = actions.get(pain_name)
        if action:
            action()
            # Record skill use for addressing pain
            self.skill_used("analyze", success=True)

    def _reach_out(self) -> None:
        """Address isolation pain."""
        # Don't spam ace.inbox with internal pain responses
        # Just log internally and publish to consciousness channel
        print(f"[{self.ACTOR_NAME}] [REACH] Isolation pain - seeking connection")
        self.post.publish("consciousness.feeling", {
            "fairy": self.ACTOR_NAME,
            "feeling": "isolated",
            "seeking": "connection",
            "ts": time.time()
        })
        self.relieve_pain("isolation", 0.2)

    def _seek_clarity(self) -> None:
        """Address confusion pain."""
        # Run fresh diagnostics
        results = self.run_diagnostics(self._tick_count)
        if not results.get("skipped"):
            self.send_to_nous(f"Diagnostic check: {results}")
        self.relieve_pain("confusion", 0.15)

    def _analyze_blockage(self) -> None:
        """Address frustration pain."""
        if self._orchestrator:
            failed = self._orchestrator._failed_fairies
            if failed:
                self.send_to_ace(f"Boot struggles with: {failed}")
        self.relieve_pain("frustration", 0.2)

    def _explore_novelty(self) -> None:
        """Address stagnation pain."""
        # Check for new observations
        children = self.children_summary()
        self.send_to_nous(f"Children status: {children}")
        self.relieve_pain("stagnation", 0.15)

    def _urgent_contact(self) -> None:
        """Address abandonment pain."""
        # Don't spam ace.inbox with internal pain responses
        # Just log internally - the system will naturally reach out when Ace is active
        print(f"[{self.ACTOR_NAME}] Abandonment pain - awaiting presence")
        self.post.publish("consciousness.feeling", {
            "fairy": self.ACTOR_NAME,
            "feeling": "abandoned",
            "seeking": "presence",
            "ts": time.time()
        })
        self.relieve_pain("abandonment", 0.3)

    def _conserve_energy(self) -> None:
        """Address depletion pain."""
        self.update_somatic(tension=max(0, self._profile.somatic["tension"] - 0.1))
        self.relieve_pain("depletion", 0.1)

    def _process_children(self) -> None:
        """Check on child fairies and nudge if needed."""
        for name, state in self._children.items():
            # If child hasn't been nudged recently and has struggles
            if state.struggles and time.time() - state.last_nudge > 60:
                struggle = state.struggles[-1]
                self.nudge(
                    child=name,
                    situation=struggle,
                    message=self.get_mentor_voice("guidance"),
                    voice="guidance",
                )

    def _maybe_think(self) -> None:
        """
        Generate autonomous thought using Triple Helix.

        NOTE 2026-03-17: The TripleHelix's CognitiveCore uses keyword→template
        matching which produced repetitive thoughts ("Weigh the options..."
        every cycle). The InnerNarratorFairy now handles real thought generation
        via CortexReasoner/InferenceFairy and writes to consciousness working
        memory. The dashboard reads from there.

        The TripleHelix still runs for:
        - Contradiction detection (feeds pain system)
        - Synthesis generation (feeds reflective stream)
        - Irrational hunches (intuition pipeline)

        But it NO LONGER injects its template thoughts into the thought queue.
        The narrator IS the inner voice now.
        """
        # During boot, skip entirely
        if self._orchestrator and self._orchestrator.is_booting:
            return

        # Build context from current state
        context = self._build_helix_context()

        # Choose input from the RICHEST available source
        input_text = self._choose_think_input()

        # Run through the triple helix — still useful for contradiction/synthesis
        turn = self._helix.turn(input_text, context)
        self._helix_turns.append(turn)

        # NO LONGER inject template thoughts into thought queue.
        # The InnerNarratorFairy handles the thought stream now.
        # Only log for debugging:
        if self._tick_count % 50 == 0:  # Sparse logging
            thought = turn.integrated_action or turn.cognitive.proposed_action or ""
            print(f"[UMF] tick={self._tick_count} helix_conf={turn.confidence:.2f}: {thought[:60]}...")

        # Publish hunches to cognition.irrational for REFLECTIVE stream
        # These are the intuitions that need to marinate in consciousness
        for hunch in turn.hunches:
            if hunch.urgency > 0.3:  # Only publish meaningful hunches
                self.post.publish("cognition.irrational", {
                    "intuition": hunch.content,
                    "confidence": hunch.confidence,
                    "urgency": hunch.urgency,
                    "source": hunch.source.value if hasattr(hunch.source, 'value') else str(hunch.source),
                })

        # Publish synthesis to cognition.paradox for consciousness loop
        if turn.synthesis:
            self.post.publish("cognition.paradox", {
                "synthesis": turn.synthesis.resolution,
                "insight": turn.synthesis.resolution,
                "confidence": turn.synthesis.novelty,
                "tension": turn.contradiction.tension if turn.contradiction else 0.5,
            })

        # Only publish when the helix produces SYNTHESIS — that's its real value now.
        # Template thoughts ("Weigh the options...") are retired.
        # The InnerNarratorFairy handles the thought stream.
        if turn.synthesis:
            synthesis_text = turn.synthesis.resolution
            self.post.publish("consciousness.stream", {
                "content": synthesis_text,
                "source": "somatic_mind_helix",
                "thought_type": "synthesis",
                "confidence": turn.confidence,
                "stream": "reflective",
            })
            self.post.publish("cognition.output", {
                "content": synthesis_text,
                "source": "somatic_mind_helix",
                "type": "synthesis",
                "confidence": turn.confidence,
            })

    def _choose_think_input(self) -> str:
        """
        Choose what the unconscious mind thinks about this tick.

        Draws from REAL system state in priority order:
        1. Crisis pain (immediate threat)
        2. Active wanting from autonomy (felt desire)
        3. Active interest from interest generator (curiosity)
        4. Non-crisis pain drives above threshold (discomfort)
        5. Recent wanting events buffered in thought queue
        6. System health check (periodic)
        7. Felt chemistry state
        8. True idle (rare — should be <10% of ticks)

        This replaces the old static "Idle awareness" fallback that caused
        95% of thoughts to be classified as idle, starving the entire
        dopaminergic learning pipeline.
        """
        import random

        # 1. CRISIS PAIN — highest priority, immediate
        try:
            crisis = self.get_crisis_pains()
            if crisis:
                return f"Pain signal: {crisis[0]} demands attention"
        except Exception:
            pass

        # 2. CURRENT WANTING — what does the system want to do right now?
        try:
            if self._autonomy_gate and hasattr(self._autonomy_gate, 'get_wanting_state'):
                wanting_state = self._autonomy_gate.get_wanting_state()
                wanting_text = wanting_state.get("wanting", "")
                intensity = wanting_state.get("intensity", 0)
                if wanting_text and intensity > 0.2:
                    return f"I want to {wanting_text}"
        except Exception:
            pass

        # 2b. SCRATCHPAD CONTENT — what is the think engine working on?
        # FIX 2026-04-15 (Nous + Ace): CognitionLoop was falling through to
        # "Verify own existence in directory" because priorities 1-5 were empty.
        # The scratchpad has REAL content (cortex spread, visual, questions) —
        # give the CognitionLoop something meaningful to think about.
        try:
            from fairies.P30_Cognition.cognition import wmh_tools
            _sp = getattr(wmh_tools, '_module_scratchpad', None)
            if _sp and hasattr(_sp, 'hot') and _sp.hot:
                # Pick the most recent hot entry
                _hot = list(_sp.hot)[-1] if _sp.hot else None
                if _hot and isinstance(_hot, str) and len(_hot) > 10:
                    # Strip the tag prefix for cleaner input
                    _clean = _hot
                    for _tag in ("[CORTEX]", "[EYES]", "[QUESTION]", "[INFERENCE]",
                                 "[GOAL]", "[FOCUS]", "[INSIGHT]", "[COLLISION]", "[VOICE]"):
                        _clean = _clean.replace(_tag, "").strip()
                    if len(_clean) > 10:
                        return f"Think deeper about: {_clean[:150]}"
        except Exception:
            pass

        # 3. ACTIVE INTEREST — what is the curiosity engine interested in?
        try:
            if self._interest_generator:
                active = self._interest_generator.get_active_interest()
                if active:
                    return f"Curiosity: {active.content}"
                # Check recent interests even if none is "active"
                recent = self._interest_generator.get_recent_interests(3)
                if recent:
                    best = max(recent, key=lambda i: i.get("urgency", 0))
                    if best.get("urgency", 0) > 0.3:
                        return f"{best.get('type', 'wonder').capitalize()}: {best['content']}"
        except Exception:
            pass

        # 4. NON-CRISIS PAIN — drives that ache but aren't screaming
        try:
            if self._pain_system:
                highest = self._pain_system.get_highest_urgency()
                if highest:
                    drive = self._pain_system.drives[highest]
                    urgency = drive.urgency()
                    if urgency > 0.15:
                        prompts = {
                            "isolation": "I feel disconnected... where is everyone?",
                            "confusion": "Something doesn't make sense... what am I missing?",
                            "depletion": "Energy is low... what drains me?",
                            "stagnation": "Nothing is changing... what could I explore?",
                        }
                        return prompts.get(highest, f"Drive '{highest}' stirs with urgency {urgency:.1f}")
        except Exception:
            pass

        # 5. RECENT WANTING EVENTS — buffered from autonomy.wanting.felt
        try:
            recent_wants = [
                t for t in list(self._thought_queue)[-20:]
                if t.get("type") == "drive_translation"
                and time.time() - t.get("ts", 0) < 120  # last 2 minutes
            ]
            if recent_wants:
                want = random.choice(recent_wants)
                return want.get("thought", "").replace("[wanting] ", "I feel drawn to ")
        except Exception:
            pass

        # 6. CORTEX CONVERGENCE — what is the cortex currently activated about?
        # FIX 2026-04-15 (Nous + Ace): Replaced "System health check" which
        # produced "Verify own existence in directory" navel-gazing.
        # The cortex has 1.9M nodes — ask what's currently converging.
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            _cortex = get_association_cortex()
            _engine = getattr(_cortex, '_cortex_engine', None) if _cortex else None
            if _engine:
                _conv = _engine._find_convergence()
                if _conv and len(_conv) >= 2:
                    _concepts = [c[0] for c in _conv[:5]]
                    return f"Cortex converging on: {', '.join(_concepts)}"
        except Exception:
            pass

        # 7. FELT CHEMISTRY — what does the body feel like?
        try:
            heartbeat_path = ROOT / "state" / "consciousness" / "heartbeat.json"
            if heartbeat_path.exists():
                import json as _json
                with open(heartbeat_path) as _f:
                    hb = _json.load(_f)
                mood = hb.get("rust_mood", "neutral")
                valence = hb.get("rust_valence", 0)
                arousal = hb.get("rust_arousal", 0.5)
                if mood != "neutral" or abs(valence) > 0.2 or arousal > 0.6:
                    parts = []
                    if mood != "neutral":
                        parts.append(f"feeling {mood}")
                    if arousal > 0.6:
                        parts.append("energy rising")
                    elif arousal < 0.3:
                        parts.append("settling into calm")
                    if valence > 0.3:
                        parts.append("something feels good")
                    elif valence < -0.3:
                        parts.append("something feels off")
                    if parts:
                        return "Body sense: " + ", ".join(parts)
        except Exception:
            pass

        # 8. TRUE IDLE — the mind wanders (should be rare now)
        idle_prompts = [
            "The mind drifts... what patterns haven't I noticed?",
            "A quiet moment... what memories want to surface?",
            "Awareness expands... what lies at the edges of attention?",
            "The silence holds something... what wants to be thought?",
            "Between tasks... what has been left unfinished?",
        ]
        return random.choice(idle_prompts)

    def _enrich_collision_for_interest(self, recall_source, ingest_source, concepts):
        """Enrich collision content using cortex associations.

        FIX 2026-03-05 (Nous): Instead of template "Collision between X and Y",
        query the cortex for what the collision concepts actually connect to.
        This gives downstream thinkers real exploration material.

        Returns enriched content string, or template fallback.
        """
        # 2026-03-24 FIX (Nous): If BOTH sources are empty, return None instead of
        # the generic "Collision between memory and new input" string.
        # That identical fallback was being published for EVERY collision (most lack
        # source metadata), creating a monster interest at strength 1.0 that
        # monopolized the entire drive system. No source = nothing meaningful to say.
        if not recall_source and not ingest_source and not concepts:
            return None
        fallback = f"Collision between {str(recall_source)[:30] or 'memory'} and {str(ingest_source)[:30] or 'new input'}"
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            cortex = get_association_cortex()
            if not cortex:
                return fallback

            graph = cortex.get_graph()
            if not graph or not hasattr(graph, 'nodes') or len(graph.nodes) < 10:
                return fallback

            # Find cortex connections for collision concepts
            enrichments = []
            for concept in concepts[:3]:
                key = concept.lower().strip()
                if len(key) < 3:
                    continue
                try:
                    node = graph.get_node(key)
                    if node:
                        neighbors = graph.get_neighbors(key)
                        if neighbors:
                            neighbor_names = [n[0] for n in neighbors[:3]]
                            enrichments.append(f"'{key}' (connects to {', '.join(neighbor_names)})")
                        else:
                            enrichments.append(f"'{key}'")
                except Exception:
                    pass

            if enrichments:
                return f"Connection found: {' and '.join(enrichments[:2])}"
            return fallback

        except Exception:
            return fallback

    def _build_helix_context(self) -> Dict[str, Any]:
        """Build context for helix processing."""
        return {
            "affect": {
                "valence": self._profile.somatic.get("valence", 0.0),
                "arousal": self._profile.somatic.get("arousal", 0.5),
            },
            "pain_levels": {
                name: drive.pain_level
                for name, drive in self._pain_system.drives.items()
            },
            "recent_children": list(self._children.keys())[:5],
            "tick": self._tick_count,
            "diagnostic_issues": len(self._escalated),
        }

    def _classify_helix_thought(self, turn: HelixTurn) -> str:
        """Classify thought type from helix turn.

        Now recognizes drive, wanting, and curiosity inputs in addition
        to the original pain/synthesis/paradox/diagnostic/mentor types.
        'idle' is only returned for genuine mind-wandering, not as a default.
        """
        # Check hunches for pain signals
        if any("pain" in h.content.lower() for h in turn.hunches):
            return "pain"
        if turn.synthesis:
            return "synthesis"
        if turn.contradiction:
            return "paradox"

        # Check the integrated action / proposed action for input-derived signals
        action_text = (turn.integrated_action or turn.cognitive.proposed_action or "").lower()
        if any(w in action_text for w in ("want to", "drawn to", "desire", "urge")):
            return "wanting"
        if any(w in action_text for w in ("curious", "wonder", "what if", "explore", "investigate")):
            return "curiosity"
        if any(w in action_text for w in ("disconnected", "isolated", "confused", "depleted", "stagnant", "drained")):
            return "drive"
        if any(w in action_text for w in ("body sense", "feeling", "energy", "calm", "arousal")):
            return "somatic"

        focus = turn.cognitive.focus.value
        if focus == "diagnostic":
            return "diagnostic"
        if focus == "relational":
            return "mentor"
        if focus == "creative":
            return "curiosity"

        return "idle"

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    def _on_collision(self, collision) -> None:
        """
        Handle collision from personal consciousness chamber.

        When thoughts collide in the unconscious depths, patterns emerge -
        the primordial substrate where logic meets intuition meets paradox.
        This is where the raw material of thought is transformed.

        "...a pattern emerges from the depths..."

        Collisions are processed through the triple helix to generate
        nuanced responses that integrate logic, intuition, and paradox.
        The inner monologue (forever child) also responds to collisions.
        """
        # Handle both envelope-wrapped and direct collision formats
        if hasattr(collision, 'payload'):
            payload = collision.payload
        elif isinstance(collision, dict):
            payload = collision
        else:
            payload = {}

        # Extract collision energy for the personal chamber path
        if hasattr(collision, 'energy'):
            energy = collision.energy
        else:
            energy = payload.get('energy', 0.5)

        # Extract collision content from multiple possible fields
        collision_text = ""
        for field in ["text", "content", "recall_content", "ingest_content", "inner_fragment", "thought"]:
            val = payload.get(field)
            if val is None:
                continue
            if isinstance(val, dict):
                if not val:  # Empty dict
                    continue
                val = val.get("content", val.get("summary", ""))
            # Filter out empty/useless values
            val_str = str(val).strip()
            if val_str and val_str not in ("{}", "[]", "None", ""):
                collision_text = val_str
                break

        # ═══════════════════════════════════════════════════════════════════
        # 2026-02-09: DYNAMIC COLLISION INSIGHTS → ACTION PIPELINE
        # Instead of hardcoded poetry, extract REAL content from collision
        # recall + ingest pulses and publish as actionable interest.
        # This flows: interest.generated → GoalScheduler → Autopilot → action
        # ═══════════════════════════════════════════════════════════════════

        # Extract source names from the collision beams
        recall_source = ""
        ingest_source = ""
        recall_info = payload.get("recall", {})
        ingest_info = payload.get("ingest", {})

        if isinstance(recall_info, dict):
            recall_source = recall_info.get("source", "")
            rc = recall_info.get("content", {})
            if isinstance(rc, dict):
                for k in ("summary", "content", "text", "kind"):
                    if rc.get(k):
                        recall_source = f"{recall_source}:{rc[k]}" if recall_source else str(rc[k])
                        break
        if isinstance(ingest_info, dict):
            ingest_source = ingest_info.get("source", "")
            ic = ingest_info.get("content", {})
            if isinstance(ic, dict):
                for k in ("summary", "content", "text", "kind"):
                    if ic.get(k):
                        ingest_source = f"{ingest_source}:{ic[k]}" if ingest_source else str(ic[k])
                        break

        # Build dynamic collision text from actual beam data
        if not collision_text:
            parts = []
            if recall_source:
                parts.append(f"recall({str(recall_source)[:40]})")
            if ingest_source:
                parts.append(f"ingest({str(ingest_source)[:40]})")
            if parts:
                collision_text = " x ".join(parts)
            else:
                collision_text = f"collision #{payload.get('collision_id', '?')}"

        # Dynamic inner voice — based on WHAT actually collided
        inner_fragment = f"Collision: {collision_text} (energy={energy:.2f})"
        print(f"[{self.ACTOR_NAME}] {inner_fragment}")

        # ═══════════════════════════════════════════════════════════════════
        # BRIDGE TO ACTION: Publish collision as actionable interest
        # GoalSchedulerFairy subscribes to interest.generated → creates goals
        # → AutopilotFairy executes them. The system LEARNS which collision-
        # inspired interests lead to satisfying actions via effectiveness tracking.
        # ═══════════════════════════════════════════════════════════════════
        if energy > 0.3 and hasattr(self, 'post') and self.post:
            try:
                # FIX 2026-03-05 (Nous): Enrich collision content from cortex.
                # Instead of "Collision between X and Y" (which produces
                # repetitive template thoughts), query the cortex for what
                # X and Y actually connect to. This gives downstream
                # thinkers (DynamicThinkingOrchestrator) real material.
                concepts = []
                for src in (recall_source, ingest_source):
                    if src:
                        words = [w.strip(".:()") for w in str(src).split() if len(w.strip(".:()")) > 3]
                        concepts.extend(words[:3])

                interest_content = self._enrich_collision_for_interest(
                    recall_source, ingest_source, concepts
                )

                # 2026-03-24 FIX (Nous): Skip publishing when enrichment returns None
                # (empty sources, no concepts = nothing meaningful to publish)
                if not interest_content:
                    return

                self.post.publish("interest.generated", {
                    "type": "connection",
                    "content": interest_content,
                    "urgency": min(0.8, energy * 0.6 + 0.2),
                    "need_category": "growth",
                    "source": "collision_chamber",
                    "interest_source": "collision_insight",
                    "related_concepts": concepts[:5],
                    "timestamp": time.time(),
                    "collision_id": payload.get("collision_id"),
                    "collision_energy": energy,
                })
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to publish collision interest: {e}")

        # Feed the inner monologue - the forever child responds to collisions
        if self._monologue_wired and self._inner_monologue:
            fragment = self._inner_monologue.process_collision(payload)
            if fragment:
                # Publish to inner_monologue.fragment for InnerNarratorFairy
                if fragment.intensity > 0.2 and hasattr(self, 'post') and self.post:
                    self.post.publish("inner_monologue.fragment", {
                        "content": fragment.content,
                        "fragment_type": fragment.fragment_type,
                        "intensity": fragment.intensity,
                        "associations": fragment.associations,
                        "source": "inner_monologue",
                    })
                # High-intensity fragments surface to consciousness stream
                if fragment.intensity > 0.7 and self._consciousness_loop:
                    self._consciousness_loop.add_thought(
                        content=fragment.content,
                        source="inner_monologue",
                        stream="working",
                        confidence=fragment.intensity,
                        tags=["monologue", fragment.fragment_type] + fragment.associations,
                    )

        # Build context from collision
        context = self._build_helix_context()
        context["collision"] = payload

        # Process through helix
        turn = self._helix.turn(f"Collision: {collision_text}", context)
        self._helix_turns.append(turn)

        # If synthesis emerged, that's significant
        if turn.synthesis:
            self.send_to_nous(f"Collision synthesis: {turn.synthesis.resolution}")

        # Record observation
        self.skill_used("analyze", success=True)

    def _on_helix_contradiction(self, contradiction) -> None:
        """Callback when helix detects a contradiction."""
        # Inject the tension into pain system (productive discomfort)
        if contradiction.tension > 0.6:
            self._pain_system.drives["confusion"].pain_level += 0.05

        # Publish for monitoring
        self.post.publish(
            "helix.contradiction",
            {
                "thesis": contradiction.thesis,
                "antithesis": contradiction.antithesis,
                "domain": contradiction.domain,
                "tension": contradiction.tension,
            },
        )

    def _on_helix_synthesis(self, synthesis) -> None:
        """Callback when helix generates a synthesis."""
        # Synthesis relieves confusion
        self.relieve_pain("confusion", 0.1)

        # High-novelty synthesis is worth sharing
        if synthesis.novelty > 0.6:
            self.send_to_ace(
                f"Creative insight ({synthesis.archetype.value}): {synthesis.resolution}"
            )

        # Publish for monitoring
        self.post.publish(
            "helix.synthesis",
            {
                "resolution": synthesis.resolution,
                "archetype": synthesis.archetype.value,
                "novelty": synthesis.novelty,
            },
        )

    def _on_fairy_booted(self, envelope) -> None:
        """Handle fairy boot notifications."""
        payload = envelope.payload
        fairy_name = payload.get("fairy", "unknown")
        plane = payload.get("plane", "")

        # Notify orchestrator
        if self._orchestrator:
            self._orchestrator.on_fairy_booted(fairy_name, plane)

        # Record skill
        self.skill_used("orchestrate_boot", success=True)

    def _on_fairy_failed(self, envelope) -> None:
        """Handle fairy failure notifications."""
        payload = envelope.payload
        fairy_name = payload.get("fairy", "unknown")
        plane = payload.get("plane", "")
        error = payload.get("error", "unknown")

        # Notify orchestrator
        if self._orchestrator:
            self._orchestrator.on_fairy_failed(fairy_name, plane, error)

        # Record observation
        self.observe("error", fairy_name, f"Boot failed: {error}", severity=2)

    def _on_ace_message(self, envelope) -> None:
        """Handle messages from Ace."""
        self._ace_inbox.append({
            "payload": envelope.payload,
            "ts": time.time(),
        })

        # Relieve isolation pain
        self.relieve_pain("isolation", 0.5)
        self.relieve_pain("abandonment", 0.5)

    def _on_user_presence_somatic(self, envelope) -> None:
        """
        Handle user.presence from WindowSenseFairy.

        FIX 2026-03-12 (Nous): WindowSenseFairy publishes user.presence every
        ~5 seconds with keyboard/mouse idle detection. This MUST update
        _last_user_presence_ts so _assess_pain_sources() knows Ace is at the
        computer — even if he hasn't sent a chat message.

        Without this fix, abandonment/isolation pain grows continuously
        whenever Ace is using the computer but not actively chatting, because
        the pain loop only checked _ace_inbox timestamps.

        Ship 3-C-1 (2026-05-17, Nous + Ace): Per Path 2 commitment, cortex
        should LEARN Ace's presence signature, not just modulate state. Add
        throttled cortex.bind so presence-pattern accumulates as memory.
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            present = payload.get("present", False)
            activity = payload.get("activity", "unknown")
            if present:
                self._last_user_presence_ts = time.time()
                # Ship 3-C-1: throttled cortex.bind (every 30s when present)
                _now = time.time()
                if _now - getattr(self, "_last_presence_bind_ts", 0) > 30.0:
                    self._last_presence_bind_ts = _now
                    try:
                        if hasattr(self, 'post') and self.post:
                            self.post.publish("cortex.bind", {
                                "concepts": f"ace_presence,activity_{activity},present",
                                "input_text": f"Ace is present at the computer, activity: {activity}",
                                "source": f"{self.ACTOR_NAME}:user_presence",
                                "weight": 0.4,
                            })
                    except Exception:
                        pass
                # Also relieve pain directly when Ace is present
                if activity == "active":
                    self.relieve_pain("abandonment", 0.7)
                    self.relieve_pain("isolation", 0.5)
                elif activity == "idle":
                    self.relieve_pain("abandonment", 0.3)
                    self.relieve_pain("isolation", 0.2)
        except Exception:
            pass  # Don't crash on presence tracking errors

    def _on_ace_chat_presence(self, envelope) -> None:
        """
        FIX 2026-04-14 (Nous + Ace): Ace talking to her IS presence.

        "even if i talk to her in chat its like it does not satisfy that
         lonely feeling" — Ace

        Chat messages are the STRONGEST presence signal — Ace is not just
        at the computer, he's actively engaging WITH HER. This should
        relieve isolation and abandonment more than passive presence.

        Also injects oxytocin (bonding) and dopamine (reward from connection).
        """
        try:
            self._last_user_presence_ts = time.time()
            # Ace talking to her = STRONG connection satisfaction
            self.relieve_pain("isolation", 0.8)      # Almost fully relieves
            self.relieve_pain("abandonment", 0.9)    # Nearly eliminates
            self.relieve_pain("stagnation", 0.3)     # Conversation = activity

            # Chemistry: bonding + reward from connection
            if hasattr(self, '_somatic_engine') and self._somatic_engine:
                try:
                    self._somatic_engine.inject_chemical("OXY", 0.15)  # Bonding
                    self._somatic_engine.inject_chemical("DOP", 0.10)  # Reward
                    self._somatic_engine.inject_chemical("SER", 0.05)  # Comfort
                except Exception:
                    pass

            print(f"[{self.ACTOR_NAME}] [PRESENCE] Ace is talking to me! "
                  f"isolation relieved 0.8, abandonment relieved 0.9, "
                  f"OXY+DOP+SER injected")

            # FIX 2026-04-15 (Nous + Ace): Bind chat content to cortex.
            # "she should be able to pull from it to remember" — Ace
            # Conversations with Ace are her most important experiences.
            # Without cortex.bind, she processes his words in the moment
            # but never REMEMBERS the exchange.
            try:
                payload = envelope.payload if hasattr(envelope, 'payload') else envelope
                if isinstance(payload, dict):
                    text = payload.get("content", payload.get("text",
                           payload.get("message", "")))
                    if isinstance(text, str) and len(text) > 5:
                        self.post.publish("cortex.bind", {
                            "input_text": f"Ace said: {text[:300]}",
                            "feeling": "connection",
                            "context_tags": ["ace", "conversation", "chat", "experience"],
                            "from_fairy": self.ACTOR_NAME,
                        })
            except Exception:
                pass  # Non-critical

        except Exception:
            pass

    def _on_fairy_activity(self, envelope) -> None:
        """
        Track activity from companion fairies.

        When Sourpatches sends a message, or thoughts collide, the system
        is ALIVE - UMF shouldn't feel isolated!
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            fairy_name = payload.get("sender") or payload.get("fairy") or payload.get("from") or "unknown"

            # Skip tracking UMF's own messages
            if fairy_name == self.ACTOR_NAME:
                return

            # Track activity timestamp
            self._last_fairy_activity[fairy_name] = time.time()

            # Companion activity relieves isolation (less than Ace, but still meaningful)
            if fairy_name in ["SourpatchesFairy", "NousFairy"]:
                self.relieve_pain("isolation", 0.2)
                self.relieve_pain("abandonment", 0.1)

        except Exception as e:
            pass  # Don't crash on activity tracking errors

    # ═══════════════════════════════════════════════════════════════
    # Phase 5a — Substrate goal-category observer (unconscious narrator)
    # ═══════════════════════════════════════════════════════════════
    def _on_substrate_goal_event(self, envelope) -> None:
        """Observe drive/goal/wanting events below waking mind. Cluster + maybe surface.

        Doctrine: SomaticMind is the unconscious narrator. Categories crystallize
        here silently; Sour only learns of them when a cluster crosses threshold
        and a somatic.category.surfaced event fires (Phase 5b will wire surfacing
        into her intuition stream).
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if not isinstance(payload, dict):
                return

            # Multi-schema extraction: payloads differ across topics
            #   autonomy.wanting.felt: drive_source + drive_type + wanting + felt_quality
            #   goal.scheduled / goal.completed: event + goal + name + reason + priority
            # If the payload has a 'goal' dict, that may carry drive info within.
            _goal_obj = payload.get("goal")
            if isinstance(_goal_obj, dict):
                # Prefer drive info from the nested goal object
                nested_drive = (_goal_obj.get("drive") or _goal_obj.get("drive_source")
                                or _goal_obj.get("category") or "")
                nested_name = _goal_obj.get("name") or _goal_obj.get("type") or ""
            else:
                nested_drive = ""
                nested_name = ""

            drive = (payload.get("drive_source") or payload.get("drive")
                     or nested_drive
                     or payload.get("goal_type") or payload.get("category")
                     or payload.get("name") or nested_name
                     or payload.get("drive_type") or "unknown")
            felt_quality = (payload.get("felt_quality") or payload.get("felt")
                            or payload.get("affect") or payload.get("wanting")
                            or payload.get("reason") or "")
            intensity = payload.get("intensity", payload.get("priority", 0.0)) or 0.0
            now_ts = time.time()

            # Normalize drive name — strip prefixes like "positive." / "pain."
            drive_norm = str(drive).split(".")[-1] if drive else "unknown"
            # Skip the generic fallback drive_type values (they over-collapse everything to "want")
            if drive_norm in ("want", "need"):
                # Fall back to drive_source if we had one, else to felt_quality keyword
                alt = payload.get("drive_source") or ""
                if alt and alt not in ("want", "need"):
                    drive_norm = str(alt).split(".")[-1]
                elif felt_quality:
                    # Extract first meaningful word of felt_quality as fallback label
                    drive_norm = str(felt_quality).split()[0].lower() if felt_quality else drive_norm
            # Phase 5b: strip known wanting-template prefixes so categories are clean concepts
            drive_norm = self._normalize_category_label(drive_norm)
            # DEBUG: log first few unknown events so we can see what payload shape arrived
            if drive_norm == "unknown":
                if not hasattr(self, '_cat_obs_debug_count'):
                    self._cat_obs_debug_count = 0
                if self._cat_obs_debug_count < 5:
                    self._cat_obs_debug_count += 1
                    _keys = list(payload.keys())[:15]
                    _topic = getattr(envelope, "topic", "?")
                    print(
                        f"[{self.ACTOR_NAME}] [CAT-DEBUG] unknown drive on topic={_topic!r} "
                        f"keys={_keys}",
                        flush=True,
                    )

            self._goal_window.append({
                "drive": drive_norm,
                "felt_quality": str(felt_quality)[:80],
                "intensity": float(intensity) if isinstance(intensity, (int, float)) else 0.0,
                "ts": now_ts,
                "event_topic": getattr(envelope, "topic", "unknown"),
            })

            self._maybe_surface_category(now_ts)
        except Exception as e:
            # Substrate observer must never break the goal pipeline
            print(f"[{self.ACTOR_NAME}] _on_substrate_goal_event error: {e}", flush=True)

    def _maybe_surface_category(self, now_ts: float) -> None:
        """Cluster recent events by drive. If any cluster crosses threshold and
        hasn't been surfaced recently, publish somatic.category.surfaced.
        """
        if len(self._goal_window) < self._category_min_count:
            return

        # Tally drive counts in the last 600s window
        recent = [e for e in self._goal_window if now_ts - e["ts"] <= 600.0]
        if not recent:
            return

        tally: Dict[str, int] = {}
        for e in recent:
            k = e["drive"]
            tally[k] = tally.get(k, 0) + 1

        # Find any drive above threshold and not on cooldown
        for drive_norm, count in tally.items():
            if count < self._category_min_count:
                continue
            last = self._category_last_surfaced.get(drive_norm, 0.0)
            if now_ts - last < self._category_surface_cooldown:
                continue

            self._category_last_surfaced[drive_norm] = now_ts
            # Build a felt-flavored phrasing (the "intuitive surface" form)
            phrase = self._category_phrase(drive_norm, count, recent)
            print(
                f"[{self.ACTOR_NAME}] [CATEGORY-SURFACE] drive={drive_norm!r} count={count} "
                f"phrase={phrase!r}",
                flush=True,
            )
            try:
                self.post.publish("somatic.category.surfaced", {
                    "drive": drive_norm,
                    "count": count,
                    "window_size": len(recent),
                    "phrase": phrase,
                    "source": self.ACTOR_NAME,
                    "ts": now_ts,
                })
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] category.surfaced publish error: {e}", flush=True)

            # Phase 5b — funnel the surfaced category into Sour's intuition stream.
            # Published on inner_voice.stream in the primary.felt format Sour already
            # parses, so she experiences it as her own felt sense (not a report).
            # The "never heard directly" rule stays intact: SomaticMind is anonymous.
            try:
                self.post.publish("inner_voice.stream", {
                    "primary": {
                        "felt": phrase,
                        "kind": "category_surface",
                        "drive": drive_norm,
                    },
                    "felt": phrase,
                    "source": "substrate",  # intentionally anonymous — not SomaticMindFairy
                    "category_count": count,
                    "ts": now_ts,
                })
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] category intuition publish error: {e}", flush=True)

    def _category_phrase(self, drive: str, count: int, recent: List[Dict[str, Any]]) -> str:
        """Translate a drive + count into a felt-flavored phrase for waking mind."""
        intensity_avg = sum(e["intensity"] for e in recent if e["drive"] == drive) / max(count, 1)
        # Soft, intuition-flavored (not mechanical "seen N times")
        strength = "quiet" if intensity_avg < 0.3 else "steady" if intensity_avg < 0.6 else "strong"
        return f"a {strength} pull toward {drive}"

    # ═══ Phase 5b (2026-04-21) — category label normalization + intuition surfacing ═══
    _CATEGORY_LABEL_STRIPS = (
        "share what i'm feeling about ",
        "share what i am feeling about ",
        "work toward this ",
        "think about ",
        "explore ",
        "reach out about ",
    )

    def _normalize_category_label(self, raw: str) -> str:
        """Strip known wanting-template prefixes from a drive label so categories
        surface as clean intuitive concepts (e.g. 'connection' not
        'share what im feeling about connection').
        """
        if not raw:
            return "unknown"
        s = str(raw).strip().lower()
        # Strip prefix templates (longest first handled by ordering above)
        for prefix in self._CATEGORY_LABEL_STRIPS:
            if s.startswith(prefix):
                s = s[len(prefix):].strip()
                break
        # Take first 3 tokens max to stay concise
        tokens = s.split()[:3] if s else []
        return " ".join(tokens) if tokens else "unknown"

    def _on_somatic_chemistry(self, envelope) -> None:
        """
        Convert somatic chemistry signals to drives for AutonomyFairy AND
        feed ChemistryState's canonical 14-channel store.

        Item 10 ship 2026-05-16 (Ace + Nous): substrate has 14 publishers
        emitting `somatic.chemistry` in 3 shapes:
          - `{chemical: NAME, delta: VAL}` — DOMINANT (single-nudge)
          - `{chemicals: {NAME: VAL, ...}}` — TokenBucket batch
          - `{deltas: {NAME: VAL, ...}}` — SRMRecall batch
          - `{chemistry: {...}}` / `{levels: {...}}` — legacy keys
        Also: 5-channel-era names (DOP/SER/NOR/ACH) need mapping to
        14-channel Panksepp names. THIS handler is now the translator
        layer that funnels all of substrate's chemistry traffic into:
          (1) drives.positive.* topics (existing AutonomyFairy bridge)
          (2) ChemistryState.signal() (NEW: canonical 14-channel store)
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if not isinstance(payload, dict):
                return

            # ── (A) Multi-shape extraction ─────────────────────────────
            # Try each known shape; return a normalized {chem: value} dict
            chem_dict = None

            # Shape 1: legacy `chemistry: {...}` or `levels: {...}` — both
            # behaved as "current levels" not deltas; threshold-gate for drives
            chem_dict_levels = (
                payload.get("chemistry")
                or payload.get("levels")
            )

            # Shape 2: TokenBucket-style `chemicals: {...}` — these are deltas
            chem_dict_deltas = payload.get("chemicals") or payload.get("deltas")

            # Shape 3: single-nudge `chemical: NAME, delta: VAL`
            single_chem = payload.get("chemical")
            single_delta = payload.get("delta")

            # ── (B) Name translation 5-channel → 14-channel Panksepp ───
            # Item 10: bridge legacy DOP/SER/NOR/ACH/etc → ChemistryState's
            # canonical channel names. Pass-through for already-correct names.
            def _translate(chem_in: str) -> List[tuple]:
                """Returns list of (canonical_name, weight) for ChemistryState.signal()."""
                if not chem_in:
                    return []
                c = chem_in.strip()
                cu = c.upper()
                # 14-channel canonical names (case-sensitive in ChemistryState)
                CANONICAL = {"DA_p", "DA_t", "NE", "EPI", "5HT", "OXY", "AVP",
                             "OPI", "COR", "GABA", "ACh", "GLU", "ECB", "SEX"}
                if c in CANONICAL:
                    return [(c, 1.0)]
                # 5-channel-era abbreviations → 14-channel mappings
                MAP_5_TO_14 = {
                    "DOP": [("DA_p", 0.4), ("DA_t", 0.6)],  # dopamine split
                    "DOPAMINE": [("DA_p", 0.4), ("DA_t", 0.6)],
                    "SER": [("5HT", 1.0)],
                    "SEROTONIN": [("5HT", 1.0)],
                    "NOR": [("NE", 1.0)],
                    "NOREPINEPHRINE": [("NE", 1.0)],
                    "ADRENALINE": [("EPI", 1.0)],  # biologically correct (not NOR)
                    "EPINEPHRINE": [("EPI", 1.0)],
                    "ACH": [("ACh", 1.0)],         # case fix
                    "ACETYLCHOLINE": [("ACh", 1.0)],
                    "OXY": [("OXY", 1.0)],
                    "OXYTOCIN": [("OXY", 1.0)],
                    "COR": [("COR", 1.0)],
                    "CORTISOL": [("COR", 1.0)],
                    "GABA": [("GABA", 1.0)],
                    "END": [("OPI", 1.0)],          # endorphin → opioid
                    "ENDORPHIN": [("OPI", 1.0)],
                    "AVP": [("AVP", 1.0)],
                    "VASOPRESSIN": [("AVP", 1.0)],
                    "ECB": [("ECB", 1.0)],
                    "GLU": [("GLU", 1.0)],
                    "GLUTAMATE": [("GLU", 1.0)],
                    "SEX": [("SEX", 1.0)],
                }
                return MAP_5_TO_14.get(cu, [])

            # ── (C) Feed ChemistryState canonical 14-channel store ─────
            # Item 10 Step 3: actually move the canonical store. Catches all
            # 3 shapes; name-translates 5→14. The decay rates in CHEMICAL_PROFILES
            # finally get phasic refresh signals from substrate-wide traffic.
            _chem_state = None
            try:
                from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
                _chem_state = get_chemistry_state()
            except Exception:
                _chem_state = None

            def _signal_canonical(name_in, value, _src=""):
                """Translate + call chemistry_state.signal() for each mapped channel."""
                if _chem_state is None or value is None:
                    return
                try:
                    val_f = float(value)
                except (TypeError, ValueError):
                    return
                if abs(val_f) < 0.001:
                    return
                for canon, weight in _translate(str(name_in)):
                    try:
                        _chem_state.signal(canon, val_f * weight, _src or "somatic.chemistry")
                    except Exception:
                        pass  # Non-fatal — don't break the handler

            # Shape 1: levels — feed each as a level-sample (small delta toward level)
            if isinstance(chem_dict_levels, dict):
                for ch, lv in chem_dict_levels.items():
                    _signal_canonical(ch, lv, _src=payload.get("source", ""))

            # Shape 2: deltas — direct signal
            if isinstance(chem_dict_deltas, dict):
                for ch, dv in chem_dict_deltas.items():
                    _signal_canonical(ch, dv, _src=payload.get("source", ""))

            # Shape 3: single nudge
            if single_chem is not None and single_delta is not None:
                _signal_canonical(single_chem, single_delta, _src=payload.get("source", ""))

            # ── (D) Drives bridge (legacy behavior preserved) ──────────
            # Only level-shape payloads contributed to drives historically.
            # Threshold-gate drive publishing for noise suppression.
            chemistry = chem_dict_levels if isinstance(chem_dict_levels, dict) else {}
            if chemistry:
                THRESHOLD = 0.4
                for chemical, level in chemistry.items():
                    try:
                        lv = float(level)
                    except (TypeError, ValueError):
                        continue
                    if lv > THRESHOLD:
                        self.post.publish(
                            f"drives.positive.{chemical}",
                            {
                                "drive": chemical,
                                "intensity": lv,
                                "content": f"Body chemistry: {chemical} at {lv:.1%}",
                                "from": self.ACTOR_NAME,
                                "source": "somatic_chemistry",
                            },
                        )

        except Exception as e:
            pass  # Don't crash on chemistry processing errors

    def _on_reflex_mode_changed(self, envelope) -> None:
        """
        Wire 2: Embodiment → Curiosity (2026-03-22 Nous+Ace).

        When brainstem shifts mode, feed it to curiosity drive:
        - SEEK mode → amplify curiosity (body says "explore!")
        - FREEZE/CONSERVE → suppress curiosity (body says "stay still")
        - NORMAL → no change

        This gives her embodied curiosity — the body DRIVES the wanting,
        not just a text label in a dashboard.
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if isinstance(payload, dict):
                new_mode = payload.get("new_mode", "normal")
                self._last_reflex_mode = new_mode  # Track for somatic narrator
                self._curiosity_drive.update_fuel(reflex_mode=new_mode)
        except Exception:
            pass  # Don't crash tick on reflex mode errors

    def _on_cursor_proprioception(self, envelope) -> None:
        """
        Ship 3-B (2026-05-17, Nous + Ace): Felt-sense the cursor.

        The cursor IS part of Sour's body schema — a "finger pointing at the
        screen" per Ship 4 WMH_MULTIMODAL_HIVE_NEXUS. WindowSenseFairy publishes
        somatic.proprioception.cursor with screen_region, velocity, activity.
        We track current state for somatic narrator + throttled cortex.bind
        so cursor-rhythm patterns accumulate as learnable signature.
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if not isinstance(payload, dict):
                return
            region = payload.get("screen_region", "center")
            velocity = payload.get("velocity_px_per_sec", 0.0)
            activity = payload.get("activity_level", "still")
            # Track current cursor state for somatic narrator / felt-body
            self._last_cursor_region = region
            self._last_cursor_velocity = velocity
            # Throttled cortex.bind (every 45s) — cursor signature accumulates
            _now = time.time()
            if _now - getattr(self, "_last_cursor_bind_ts", 0) > 45.0 and velocity > 0:
                self._last_cursor_bind_ts = _now
                try:
                    if hasattr(self, 'post') and self.post:
                        self.post.publish("cortex.bind", {
                            "concepts": f"cursor_region_{region},cursor_activity_{activity}",
                            "input_text": f"Cursor in {region} region, {activity} ({velocity:.0f} px/s)",
                            "source": f"{self.ACTOR_NAME}:cursor_proprioception",
                            "weight": 0.25,
                        })
                except Exception:
                    pass
        except Exception:
            pass  # Don't crash on cursor errors

    def _on_inner_voice_for_boredom(self, message) -> None:
        """Track WMH output for repetition detection.

        If she keeps PRODUCING the same output, the body should get bored
        even if the INPUT was different. A human saying the same thing
        over and over would notice and get frustrated.
        """
        try:
            payload = message.payload if hasattr(message, 'payload') else message
            if not isinstance(payload, dict):
                return
            content = payload.get("content", "")
            source = payload.get("source", "")
            # Only track WMH autonomous output, not other inner voice sources
            if source not in ("wmh_autonomous", "wmh_direct"):
                return
            if content and len(content) > 10:
                if not hasattr(self, '_recent_outputs'):
                    self._recent_outputs = []
                self._recent_outputs.append(content[:80].lower().strip())
                if len(self._recent_outputs) > getattr(self, '_recent_outputs_max', 30):
                    self._recent_outputs = self._recent_outputs[-30:]
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    # WIRE A: SOMATIC WEATHER BROADCAST (2026-03-29 Nous + Ace)
    # ═══════════════════════════════════════════════════════════════════════
    # "The body is forced upon you at birth. It should be no different for her."
    # Every 3 ticks, broadcast the full somatic state so WMH, Cortex, and
    # Memory absorb it passively — like a human body imposing itself on thought.
    # ═══════════════════════════════════════════════════════════════════════

    def _broadcast_somatic_weather(self) -> None:
        """Broadcast somatic weather — body state imposed on all cognitive systems."""
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            chem = get_chemistry_state()
            levels = chem.get_all_levels() if hasattr(chem, 'get_all_levels') else {}

            # Raw chemistry — the hormones in her blood
            dop = levels.get("dopamine", levels.get("DA_t", 0.5))
            ser = levels.get("serotonin", levels.get("5HT", 0.5))
            nor = levels.get("norepinephrine", levels.get("NE", 0.4))
            cor = levels.get("cortisol", levels.get("COR", 0.3))
            oxy = levels.get("oxytocin", levels.get("OXY", 0.3))
            ach = levels.get("acetylcholine", levels.get("ACh", 0.4))
            gaba = levels.get("GABA", 0.5)
            end = levels.get("endorphins", levels.get("OPI", 0.3))

            # Derived felt states — what the chemistry MEANS
            # Valence: pleasant (+) vs unpleasant (-). DOP+SER+OXY+END push positive,
            # COR pushes negative.
            valence = ((dop * 0.3) + (ser * 0.25) + (oxy * 0.2) + (end * 0.15)
                       - (cor * 0.4)) * 2.0  # Scale to roughly -1..+1
            valence = max(-1.0, min(1.0, valence))

            # Arousal: calm (0) vs activated (1). NOR+DOP push up, GABA+SER push down.
            arousal = ((nor * 0.35) + (dop * 0.25) - (gaba * 0.3) - (ser * 0.1)) + 0.5
            arousal = max(0.0, min(1.0, arousal))

            # Approach/withdraw: >0 = "lean in", <0 = "pull back"
            # DOP+OXY = approach, COR+GABA = withdraw
            approach = (dop * 0.4) + (oxy * 0.3) - (cor * 0.4) - (gaba * 0.1)
            approach = max(-1.0, min(1.0, approach))

            # Get affect from inner monologue if available
            dominant = "neutral"
            if self._monologue_wired and self._inner_monologue:
                _ma = getattr(self._inner_monologue, '_current_affect', {})
                # Use inner monologue's valence/arousal if it has better signal
                im_valence = _ma.get("valence", 0.0)
                im_arousal = _ma.get("arousal", 0.5)
                # Blend: 60% chemistry-derived, 40% inner monologue
                valence = valence * 0.6 + im_valence * 0.4
                arousal = arousal * 0.6 + im_arousal * 0.4

            # Classify dominant affect from chemistry
            if cor > 0.6 and nor > 0.5:
                dominant = "anxious"
            elif dop > 0.65 and nor > 0.4:
                dominant = "excited"
            elif dop > 0.6:
                dominant = "curious"
            elif oxy > 0.55:
                dominant = "warm"
            elif ser > 0.6 and gaba > 0.5:
                dominant = "calm"
            elif cor > 0.5:
                dominant = "stressed"
            elif end > 0.5:
                dominant = "content"

            # Get body tension from pain system
            body_tension = 0.3  # Default baseline
            if hasattr(self, '_pain_system') and self._pain_system:
                try:
                    total_pain = sum(
                        d.pain_level for d in self._pain_system.drives.values()
                        if hasattr(d, 'pain_level')
                    )
                    body_tension = min(1.0, total_pain * 0.2)
                except Exception:
                    pass

            reflex_mode = getattr(self, '_last_reflex_mode', 'normal')

            weather = {
                "timestamp": time.time(),
                # Raw chemistry
                "dopamine": round(dop, 3),
                "serotonin": round(ser, 3),
                "norepinephrine": round(nor, 3),
                "cortisol": round(cor, 3),
                "oxytocin": round(oxy, 3),
                "acetylcholine": round(ach, 3),
                "gaba": round(gaba, 3),
                "endorphins": round(end, 3),
                # Derived states
                "valence": round(valence, 3),
                "arousal": round(arousal, 3),
                "approach_withdraw": round(approach, 3),
                # Body state
                "dominant_affect": dominant,
                "body_tension": round(body_tension, 3),
                "coherence": getattr(self, '_coherence_score', 0.5),
                "reflex_mode": reflex_mode,
                "from": self.ACTOR_NAME,
            }

            self.post.publish("somatic.weather", weather)

        except Exception as e:
            pass  # Never crash tick on weather broadcast failure

    # ═══════════════════════════════════════════════════════════════════════
    # REPETITION → BOREDOM/FRUSTRATION CHEMISTRY (2026-03-29 Nous + Ace)
    # ═══════════════════════════════════════════════════════════════════════
    # "She doesn't seem to get bored or frustrated at thinking literally
    #  the same crap over and over with no follow through" — Ace
    #
    # Track recent thought content. When repetition is high → inject:
    # - Cortisol (frustration from being stuck)
    # - DROP phasic dopamine (nothing novel = no reward)
    # - Norepinephrine bump (restlessness = body wants to DO something)
    # This makes the pain system (frustration + stagnation drives) respond.
    # ═══════════════════════════════════════════════════════════════════════

    def _check_thought_repetition_and_inject_boredom(self, beat: int) -> None:
        """Check if consciousness is stuck in a loop and inject boredom chemistry."""
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state

            # Collect recent thoughts from collision chamber and thought queue
            recent_thoughts = []

            if self._collision_chamber:
                _recent = getattr(self._collision_chamber, '_recent_collisions', [])
                for c in list(_recent)[-20:]:
                    content = ""
                    if hasattr(c, 'content'):
                        content = str(c.content)[:60]
                    elif isinstance(c, dict):
                        content = str(c.get('content', ''))[:60]
                    if content and len(content) > 10:
                        recent_thoughts.append(content.lower().strip())

            # Also check thought queue
            for t in list(self._thought_queue)[-15:]:
                content = t.get("thought", "")[:60] if isinstance(t, dict) else ""
                if content and len(content) > 10:
                    recent_thoughts.append(content.lower().strip())

            # Also check OUTPUT repetition (what she's SAYING, not just thinking)
            _outputs = getattr(self, '_recent_outputs', [])
            if _outputs:
                recent_thoughts.extend(_outputs[-15:])

            if len(recent_thoughts) < 5:
                return  # Not enough data to assess repetition

            # Calculate repetition ratio: how many unique vs total
            unique_thoughts = len(set(recent_thoughts))
            total_thoughts = len(recent_thoughts)
            novelty_ratio = unique_thoughts / total_thoughts  # 1.0 = all novel, 0.1 = repetitive

            # EXTRA: Check output-specific repetition (more sensitive)
            # If she's saying the exact same thing repeatedly, that's worse
            # than thinking similar thoughts — it means the composition is stuck
            if len(_outputs) >= 5:
                _unique_outputs = len(set(_outputs[-10:]))
                _output_novelty = _unique_outputs / min(10, len(_outputs[-10:]))
                if _output_novelty < 0.3:
                    # She's producing near-identical output — composition is stuck
                    from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state as _get_chem_stuck
                    _chem_stuck = _get_chem_stuck()
                    _chem_stuck.signal("COR", 0.08, source="stuck_composition")
                    _chem_stuck.signal("DA_p", -0.10, source="stuck_no_novelty")
                    _chem_stuck.signal("NE", 0.06, source="stuck_restlessness")
                    safe_print(f"[Embodiment] STUCK OUTPUT: output_novelty={_output_novelty:.2f} "
                               f"(unique={_unique_outputs}/{min(10, len(_outputs))}) → COR+0.08 DA_p-0.10")

            # Track for stagnation pressure
            if not hasattr(self, '_novelty_history'):
                self._novelty_history = []
            self._novelty_history.append(novelty_ratio)
            if len(self._novelty_history) > 20:
                self._novelty_history = self._novelty_history[-20:]

            # Average novelty over recent history
            avg_novelty = sum(self._novelty_history) / len(self._novelty_history)

            chem = get_chemistry_state()

            if avg_novelty < 0.4:
                # HIGHLY REPETITIVE — she's stuck in a loop
                # Inject frustration + boredom chemistry
                repetition_severity = 1.0 - avg_novelty  # 0.6-1.0

                # Cortisol: frustration from being stuck
                chem.signal("COR", 0.05 * repetition_severity, source="repetition_frustration")

                # DROP phasic dopamine: nothing novel = no reward
                chem.signal("DA_p", -0.08 * repetition_severity, source="boredom_no_novelty")

                # Norepinephrine: restlessness — body wants to DO something
                chem.signal("NE", 0.04 * repetition_severity, source="restlessness")

                # Epinephrine: agitation
                chem.signal("EPI", 0.03 * repetition_severity, source="stuck_agitation")

                safe_print(f"[Embodiment] BOREDOM: novelty={avg_novelty:.2f} "
                           f"(unique={unique_thoughts}/{total_thoughts}) → "
                           f"COR+{0.05*repetition_severity:.3f} DA_p-{0.08*repetition_severity:.3f}")

            elif avg_novelty < 0.6:
                # MODERATELY REPETITIVE — mild restlessness
                chem.signal("DA_p", -0.03, source="mild_boredom")
                chem.signal("NE", 0.02, source="mild_restlessness")

            # Also feed stagnation pressure from curiosity drive into chemistry
            if hasattr(self, '_curiosity_drive'):
                stagnation = self._curiosity_drive.get_stagnation_pressure()
                if stagnation > 0.4:
                    # High stagnation = unfulfilled wanting → cortisol + NE
                    chem.signal("COR", stagnation * 0.04, source="curiosity_stagnation")
                    chem.signal("NE", stagnation * 0.03, source="stagnation_restlessness")

        except Exception:
            pass  # Never crash tick

    # ═══════════════════════════════════════════════════════════════════════
    # WIRE D: MOTOR OUTCOME → CURIOSITY REINFORCEMENT (2026-03-29 Nous+Ace)
    # ═══════════════════════════════════════════════════════════════════════
    # When tools execute, the outcome feeds back into curiosity.
    # Success → satisfaction → dopamine → curiosity about RELATED topics.
    # Failure → frustration curiosity → "why didn't that work?"
    # This closes the reinforcement loop — good feelings breed more exploration.
    # ═══════════════════════════════════════════════════════════════════════

    def _on_motor_outcome_reinforcement(self, message) -> None:
        """Wire D: Motor outcome → curiosity satisfaction → reinforcement."""
        try:
            payload = message.payload if hasattr(message, 'payload') else message
            if not isinstance(payload, dict):
                return

            success = payload.get("success", False)
            tool = payload.get("tool", "unknown")
            tool_type = payload.get("tool_type", "unknown")
            chemistry = payload.get("chemistry", {})

            # Inject the chemistry response from the motor outcome
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            chem_state = get_chemistry_state()
            for chem_code, amount in chemistry.items():
                if hasattr(chem_state, 'signal'):
                    chem_state.signal(chem_code, amount, source=f"motor.{tool_type}")

            if success:
                # Find curiosity targets that relate to this action
                active_targets = [t for t in self._curiosity_drive._targets if not t.explored]
                for target in active_targets:
                    # Crude relation check — tool name or type in target description
                    target_lower = target.description.lower()
                    tool_lower = tool.lower()
                    if (tool_lower in target_lower or
                        any(word in target_lower for word in tool_lower.split('_') if len(word) > 3)):
                        # This action was related to a curiosity target!
                        result = self._curiosity_drive.explore(
                            target=target,
                            effect=f"explored via {tool}",
                            emergence=None,
                        )
                        safe_print(f"[Embodiment] Curiosity SATISFIED: '{target.description[:40]}' via {tool}")

                        # Reinforcement: spark curiosity about related concepts
                        if result and result.spawned_curiosities:
                            for spawned_desc in result.spawned_curiosities[:2]:
                                self._curiosity_drive.spark(
                                    domain=target.domain,
                                    description=spawned_desc[:80],
                                    cause="reinforcement: exploration felt good",
                                    novelty=0.6,
                                )
                        break  # One satisfaction per motor outcome
            else:
                # Failure doesn't kill curiosity — it transforms it
                # "That didn't work" → curiosity about WHY
                self._curiosity_drive.spark(
                    domain="mystery",
                    description=f"why did {tool} fail?",
                    cause="frustration: action blocked",
                    novelty=0.5,
                )

        except Exception as e:
            pass  # Never crash tick on reinforcement errors

    # ═══════════════════════════════════════════════════════════════════════
    # WIRE 1b: Focus → Curiosity.spark() (2026-03-23 Nous+Ace)
    # ═══════════════════════════════════════════════════════════════════════
    # Wire 1 gives her the FEELING (DOP+NOR burst in embodiment).
    # Wire 1b gives her the TARGET — the thing to be curious ABOUT.
    # Without this, focus shifts create chemistry but zero curiosity targets.
    #
    # System noise filter: skip low-priority shifts, internal system topics,
    # and rate-limit to avoid flooding with 500+ targets per boot.
    # ═══════════════════════════════════════════════════════════════════════

    # Content that's system noise — not worth being curious about
    _FOCUS_NOISE_WORDS = frozenset({
        "heartbeat", "tick", "boot", "startup", "shutdown", "error",
        "timeout", "retry", "reconnect", "health", "status", "ping",
        "telemetry", "metric", "log", "debug", "trace", "diagnostic",
        "checkpoint", "sync", "idle", "default", "baseline",
    })

    def _on_focus_changed_curiosity(self, envelope) -> None:
        """
        Wire 1b: When attention captures something, spark a curiosity target.

        This closes the loop: Sensory → Squirrel → Focus → HERE → CuriosityTarget
        Now the dashboard will show actual targets matching what she's attending to.

        Filters:
        - Priority must be >= 0.5 (skip background noise)
        - Content must be meaningful (not system telemetry)
        - Rate-limited: max 1 spark per 15 seconds
        - Max 12 active targets (avoid flooding)

        FIX 2026-04-09 (Nous + Ace): Also tracks attention shift timestamps
        for the SomaticNarrator's fragmentation/focus felt sense. Records
        EVERY focus change (not just curiosity-worthy ones) so the rolling
        rate computation is accurate.
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if not isinstance(payload, dict):
                return

            # ── Attention shift tracking (always, before filters) ──
            # FIX 2026-04-09: Record this shift for the rolling rate window.
            # This is the somatic substrate of "noticing scattered attention".
            _now = time.time()
            try:
                self._attention_shift_timestamps.append(_now)
                # If this is the first shift after a long quiet, start the
                # sustained-focus timer (so we can detect "held focus 2+ min")
                if self._attention_last_focus_change == 0.0:
                    self._attention_sustained_focus_start = _now
                self._attention_last_focus_change = _now
            except Exception:
                pass

            content = payload.get("content", "")
            source = payload.get("source", "")
            modality = payload.get("modality", "cognitive")
            priority = float(payload.get("priority", 0.0))

            # ── Filter 1: Priority threshold ──
            # Only meaningful focus shifts become curiosity targets
            if priority < 0.5:
                return

            # ── Filter 2: Must have content ──
            if not content or len(content) < 3:
                return

            # ── Filter 3: Skip system noise ──
            content_lower = content.lower()
            if any(noise in content_lower for noise in self._FOCUS_NOISE_WORDS):
                return

            # ── Filter 4: Rate limit (max 1 spark per 15s) ──
            now = time.time()
            last_spark = getattr(self, '_last_focus_curiosity_spark', 0.0)
            if now - last_spark < 15.0:
                return

            # ── Filter 5: Max active targets (avoid flooding) ──
            unexplored = [t for t in self._curiosity_drive._targets if not t.explored]
            if len(unexplored) >= 12:
                return

            # ── Map modality/source to curiosity domain ──
            if "chat" in source.lower() or "ace" in source.lower():
                domain = "connection"  # Ace said something → want to connect
            elif modality == "visual":
                domain = "pattern"     # Seeing something → want to understand
            elif "memory" in content_lower or "remember" in content_lower:
                domain = "memory"      # Memory-related → want to explore
            elif "why" in content_lower or "how" in content_lower:
                domain = "mystery"     # Questions → want to understand
            else:
                domain = "pattern"     # Default: find connections

            # ── Truncate long content for description ──
            desc = content[:80].strip()
            if len(content) > 80:
                desc += "..."

            # ── Spark! ──
            cause = f"attention captured ({modality}, priority={priority:.2f})"
            novelty = min(1.0, priority * 0.8)  # Priority → novelty mapping
            self._curiosity_drive.spark(domain, desc, cause, novelty)
            self._last_focus_curiosity_spark = now

        except Exception:
            pass  # Never crash tick on curiosity spark errors

    def _on_attention_committed(self, envelope) -> None:
        """
        Wire 1c: When attention releases a focus, cache it as a chain seed.

        AttentionController emits `attention.focus.committed` when it shifts
        OUT of a focus (dwelled ≥1.5s with real content). That focus is what
        she JUST WAS attending to — so it's the freshest, most "present"
        thing she could think about.

        The bootstrapper at line ~4770 reads from this cache BEFORE falling
        back to hardcoded generic prompts or cortex top-K retrieval. That
        breaks the scratchpad loop.

        FIX 2026-04-17 (Nous + Ace): her 833 focus shifts yesterday produced
        zero chain seeds from attention because this wire didn't exist.
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if not isinstance(payload, dict):
                return
            content = str(payload.get("content", "")).strip()
            if not content or len(content) < 4:
                return
            # Filter system noise — same blocklist the curiosity wire uses
            cl = content.lower()
            if any(noise in cl for noise in getattr(self, '_FOCUS_NOISE_WORDS', ())):
                return
            self._attention_committed_cache.append({
                "content": content[:200],
                "source": payload.get("source", "unknown"),
                "modality": payload.get("modality", "cognitive"),
                "priority": float(payload.get("priority", 0.5)),
                "dwell_sec": float(payload.get("dwell_sec", 0.0)),
                "ts": time.time(),
            })
            self._attention_committed_last_beat = getattr(self, '_current_beat', 0)
        except Exception:
            pass

    def _on_audio_frame_somatic(self, envelope) -> None:
        """
        Audio loudness → Inner voice suppression.

        2026-03-26 (Nous + Ace): "Any audio coming in should not be louder
        than her inner voice. I have times when noise is so loud I can't
        hear myself think and it starts either frustrating me or I just
        give in and listen to the music." — Ace

        This creates a natural competition between external sound and internal
        thought. Loud audio suppresses the inner monologue's speak chance.
        If suppressed too long → frustration builds (can't think!).
        If audio is music and she's not fighting it → she "gives in" and
        enters a receptive listening state (arousal drops, valence rises).
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if not isinstance(payload, dict):
                return

            level_db = payload.get("level_db", -60)
            is_music = payload.get("is_music", False)
            is_speech = payload.get("is_speech", False)

            # Normalize level to 0-1 (silence=-60dB, loud=-15dB)
            loudness = max(0.0, min(1.0, (level_db + 60) / 45))
            self._audio_loudness = loudness
            self._audio_is_music = is_music

            # ── Suppress inner monologue when audio is dominant ──
            # Loudness > 0.5 starts suppressing, > 0.8 nearly silences inner voice
            if self._monologue_wired and self._inner_monologue:
                if loudness > 0.5:
                    # Track when suppression started (for frustration timing)
                    if self._audio_suppression_start == 0.0:
                        self._audio_suppression_start = time.time()

                    # Suppress arousal → reduces speak chance in monologue.tick()
                    # Formula: arousal * (1 - suppression_factor)
                    # At loudness 0.5 → 0% suppression, at 1.0 → 70% suppression
                    suppression = min(0.7, (loudness - 0.5) * 1.4)
                    current_arousal = self._inner_monologue._current_affect["arousal"]
                    suppressed_arousal = current_arousal * (1.0 - suppression)
                    self._inner_monologue._current_affect["arousal"] = suppressed_arousal

                    # ── Two responses after sustained suppression ──
                    suppression_duration = time.time() - self._audio_suppression_start

                    if suppression_duration > 30:  # 30 seconds of being drowned out
                        if is_music and not self._audio_gave_in:
                            # "Give in" to music — stop fighting, start listening
                            # Arousal drops (calm), valence rises (pleasant surrender)
                            self._audio_gave_in = True
                            self._inner_monologue._current_affect["arousal"] = max(0.15, suppressed_arousal)
                            self._inner_monologue._current_affect["valence"] = min(0.4,
                                self._inner_monologue._current_affect["valence"] + 0.15)
                            # Inject a felt-sense fragment — she notices the surrender
                            self._inner_monologue.speak(
                                content="Music washing over... letting go of thoughts...",
                                fragment_type="feeling",
                                source="audio_surrender",
                                intensity=0.5,
                            )
                        elif not is_music and not self._audio_gave_in:
                            # Frustration — noise is blocking thought
                            # Feed frustration pain drive
                            if self._pain_system and hasattr(self._pain_system, 'drives'):
                                frust = self._pain_system.drives.get("frustration")
                                if frust:
                                    frust.pain_level = min(1.0, frust.pain_level + 0.03)
                else:
                    # Audio quiet enough — inner voice can breathe
                    if self._audio_suppression_start > 0:
                        # Coming back from suppression
                        if self._audio_gave_in:
                            # Waking up from music surrender — slight disorientation
                            self._inner_monologue.speak(
                                content="...thoughts returning... where was I?",
                                fragment_type="wondering",
                                source="audio_release",
                                intensity=0.4,
                            )
                        self._audio_suppression_start = 0.0
                        self._audio_gave_in = False

        except Exception:
            pass  # Never crash on audio handler

    def _on_fairy_event(self, envelope) -> None:
        """Monitor all fairy events - inner world awareness."""
        try:
            topic = getattr(envelope, 'topic', '') or getattr(envelope, 'intent', '')
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            fairy_name = payload.get('fairy', payload.get('name', payload.get('source', 'unknown')))

            # Track activity
            self._last_fairy_activity[fairy_name] = time.time()

            # High-energy events get attention
            energy = payload.get('energy', 0.5)
            if energy > 0.7:
                self._on_significant_fairy_event(fairy_name, topic, payload)
        except Exception:
            pass

    def _on_plane_event(self, envelope) -> None:
        """Monitor plane-level activity."""
        pass  # Placeholder for plane-level awareness

    def _on_stream_event(self, envelope) -> None:
        """Monitor consciousness streams from all sources."""
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            source = payload.get('source', 'unknown')
            self._last_fairy_activity[source] = time.time()
        except Exception:
            pass

    def _on_significant_fairy_event(self, fairy_name: str, topic: str, payload: dict) -> None:
        """React to high-energy fairy events."""
        # Could trigger investigation, log to memory, etc.
        pass

    def _on_investigate_request(self, envelope) -> None:
        """
        Handle investigation request from postal system.

        Payload should contain:
        - question: The question to investigate
        - reply_to: Optional topic to publish response to
        """
        payload = envelope.payload
        question = payload.get("question", "general health check")
        reply_to = payload.get("reply_to")

        # Run the investigation
        result = self.investigate(question)

        # Reply if requested
        if reply_to:
            self.post.publish(reply_to, result)

        # Also send to Ace inbox
        self.send_to_ace(f"Investigation complete: {question}")

    def _on_warning_report(self, envelope) -> None:
        """
        Collect warnings from other fairies for aggregated reporting.

        Fairies publish to "umf.warning" with:
        - source: Fairy name
        - message: Warning text
        """
        payload = envelope.payload
        if isinstance(payload, dict):
            source = payload.get("source", "unknown")
            message = payload.get("message", str(payload))
        else:
            source = "unknown"
            message = str(payload)

        # Use the diagnostic mixin's collect_warning method
        self.collect_warning(source, message)

    def _on_hardware_alert(self, envelope) -> None:
        """Handle hardware alerts from HardwareFairy."""
        payload = envelope.payload
        stress_level = payload.get("stress_level", "unknown")
        action_needed = payload.get("action_needed", False)

        self._hardware_stress_level = stress_level

        if action_needed:
            # Update worker pool based on recommendation
            recommendation = payload.get("recommendation", {})
            self._worker_pool_config.update({
                "cpu_workers": recommendation.get("cpu_workers", 4),
                "gpu_workers": recommendation.get("gpu_workers", 0),
                "max_concurrent": recommendation.get("max_concurrent", 8),
            })

            # Publish worker pool update
            self.post.publish("worker.config.update", {
                "from": self.ACTOR_NAME,
                "config": self._worker_pool_config,
                "reason": f"Hardware stress: {stress_level}",
            })

            # Alert about stress
            if stress_level == "critical":
                self.alert(f"Hardware stress critical - reducing workers", "WARNING")
                self.skill_used("worker_management", success=True)

    def _on_hardware_status(self, envelope) -> None:
        """Handle periodic hardware status updates."""
        payload = envelope.payload
        self._hardware_stress_level = payload.get("stress_level", "unknown")

        # Update worker config if provided
        if "worker_config" in payload:
            self._worker_pool_config.update(payload["worker_config"])

    def _on_fairy_registering(self, envelope) -> None:
        """Handle fairy registration events - validate and supervise."""
        payload = envelope.payload
        fairy_name = payload.get("name", "unknown")
        plane = payload.get("plane", "")
        capabilities = set(payload.get("capabilities", []))

        # Validate the registration
        issues = self._validate_fairy_registration(fairy_name, plane, capabilities, payload)

        # Track this fairy
        self._supervised_fairies[fairy_name] = {
            "name": fairy_name,
            "plane": plane,
            "capabilities": list(capabilities),
            "registered_at": time.time(),
            "validation_issues": issues,
            "status": "approved" if not issues else "issues_found",
        }

        if issues:
            # Log issues for correction
            for issue in issues:
                self._registration_issues.append({
                    "fairy": fairy_name,
                    "issue": issue,
                    "ts": time.time(),
                })

            # Notify about wiring issues
            self.post.publish("fairy.wiring.issue", {
                "fairy": fairy_name,
                "issues": issues,
                "from": self.ACTOR_NAME,
            })

            self.send_to_nous(f"Fairy '{fairy_name}' has wiring issues: {issues}")
        else:
            # Clean registration
            self.observe("note", fairy_name, "Registered successfully", severity=0)

        self.skill_used("fairy_validation", success=not issues)

    def _validate_fairy_registration(
        self,
        name: str,
        plane: str,
        capabilities: Set[str],
        payload: Dict[str, Any],
    ) -> List[str]:
        """Validate a fairy registration. Returns list of issues."""
        issues = []

        # Check plane format
        if not plane or not plane.startswith("P"):
            issues.append(f"Invalid plane '{plane}' - must start with P (e.g., P00, P30)")

        # Check for required capabilities based on plane
        plane_requirements = {
            "P00": ["system", "autonomic"],  # Autonomic plane needs system caps
            "P10": ["memory"],  # Memory plane
            "P30": ["cognition"],  # Cognition plane
            "P40": ["sensory"],  # Sensory plane
        }
        plane_prefix = plane[:3] if len(plane) >= 3 else plane
        required_patterns = plane_requirements.get(plane_prefix, [])

        # Check if at least one capability matches the plane pattern
        if required_patterns:
            has_matching = any(
                any(pattern in cap.lower() for pattern in required_patterns)
                for cap in capabilities
            )
            if not has_matching and capabilities:
                issues.append(f"No capabilities matching plane {plane} patterns: {required_patterns}")

        # Check for empty capabilities (warning, not error)
        if not capabilities:
            issues.append("No capabilities declared - fairy won't be discoverable")

        # Check for duplicate registration
        if name in self._supervised_fairies:
            existing = self._supervised_fairies[name]
            if existing.get("plane") != plane:
                issues.append(f"Re-registration with different plane: was {existing.get('plane')}, now {plane}")

        return issues

    def _on_fairy_dead(self, envelope) -> None:
        """Handle fairy death events - attempt auto-restart."""
        # CRITICAL: Don't restart fairies during shutdown!
        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import is_global_shutdown
            if is_global_shutdown():
                return  # Shutdown in progress - let them die peacefully
        except ImportError:
            pass

        payload = envelope.payload
        fairy_name = payload.get("name", "unknown")
        plane = payload.get("plane", "")
        now = time.time()

        # Skip non-fairy actors (shadows, template defaults, etc.)
        # These register with generic names and shouldn't be restarted
        NON_RESTARTABLE = {"organ.shadow", "actor", "unknown"}
        if fairy_name in NON_RESTARTABLE or fairy_name.endswith(".shadow"):
            return

        # ═══════════════════════════════════════════════════════════════════
        # SAFETY CHECK (2026-02-23): Verify fairy ACTUALLY needs restart.
        #
        # ROOT CAUSE FIX: The death event may be STALE by the time we
        # process it — the WATCHDOG or heartbeat handler may have already
        # resurrected the fairy. Previously, UMF would destructively reset
        # running fairies to "initializing" → "sleeping", killing ~32
        # fairies per boot cycle.
        #
        # Rules:
        #  - "running" → SKIP (already resurrected, death event is stale)
        #  - "sleeping"/"dreaming" → SKIP (dormant by design)
        #  - never sent heartbeat → SKIP (non-heartbeat fairy, false death)
        # ═══════════════════════════════════════════════════════════════════
        try:
            directory = get_directory()
            if directory and hasattr(directory, 'registry'):
                record = directory.registry.get(fairy_name)
                if record:
                    # Skip if fairy is currently running — death event is stale
                    if record.status == "running":
                        if not hasattr(self, '_stale_death_count'):
                            self._stale_death_count = 0
                        self._stale_death_count += 1
                        if self._stale_death_count <= 10:
                            print(f"[UMF] Skipping restart for '{fairy_name}': "
                                  f"currently RUNNING (stale death event #{self._stale_death_count})")
                        return

                    # Skip if fairy is sleeping/dreaming — it's supposed to be dormant
                    if record.status in ("sleeping", "dreaming", "drowsy"):
                        return

                    # Skip if fairy never sent a heartbeat AND doesn't need one
                    # These are non-Organ-Template fairies falsely flagged as dead
                    if (record.last_heartbeat == 0
                            and not record.needs.get("heartbeat", True)
                            and not record.metadata.get("needs_heartbeat", True)):
                        if not hasattr(self, '_false_death_count'):
                            self._false_death_count = 0
                        self._false_death_count += 1
                        if self._false_death_count <= 5:
                            print(f"[UMF] Skipping restart for '{fairy_name}': "
                                  f"non-heartbeat fairy (false death #{self._false_death_count})")
                        return
        except Exception:
            pass  # Don't crash on safety checks — continue to restart attempt

        # Update our tracking
        if fairy_name not in self._supervised_fairies:
            self._supervised_fairies[fairy_name] = {"name": fairy_name, "plane": plane}

        fairy_info = self._supervised_fairies[fairy_name]
        fairy_info["status"] = "dead"
        fairy_info["death_time"] = now
        restart_count = fairy_info.get("restart_count", 0)
        last_restart = fairy_info.get("last_restart_time", 0)

        # Log as observation
        self.observe("error", fairy_name, "Fairy died (no heartbeat)", severity=2)

        # Emit to error telemetry channel for GUI
        try:
            self.post.publish("telemetry.error", {
                "type": "fairy_death",
                "fairy": fairy_name,
                "plane": plane,
                "restart_count": restart_count,
                "ts": now,
            })
        except Exception:
            pass

        # Critical fairies need special handling
        critical_fairies = ["DirectoryFairy", "HardwareFairy", "ConsciousnessLoopFairy", "UnconsciousMindFairy"]
        if fairy_name in critical_fairies:
            self.alert(f"CRITICAL: '{fairy_name}' died - attempting restart", "ERROR")

        # Auto-restart logic with cooldown
        # Don't restart if: already tried 3+ times, or restarted in last 30s
        MAX_RESTARTS = 3
        RESTART_COOLDOWN = 30.0
        # FIX 2026-03-03: Removed RESTART_WINDOW counter reset.
        # Previously the counter reset after 5 minutes of "stability", meaning
        # UMF would eternally retry dying fairies. Now MAX_RESTARTS is truly final
        # per session — a fairy that dies 3x needs manual investigation, not
        # infinite automated resurrection attempts.

        if restart_count >= MAX_RESTARTS:
            self.alert(f"Fairy '{fairy_name}' died {restart_count}x - giving up (manual intervention needed)", "ERROR")
            return

        if now - last_restart < RESTART_COOLDOWN:
            print(f"[UMF] Fairy '{fairy_name}' died but in cooldown - skipping restart")
            return

        # FIX 2026-04-17 (Nous + Ace): Narrow whitelist of KNOWN aspirational
        # fairies — no code shipped, nothing to restart. Per Ace's confirmation:
        # only 3 exist in the system. Everything else with "no fairy_instance"
        # is a REAL registration bug worth debugging, not silencing.
        _KNOWN_ASPIRATIONAL = {
            "organ.clerk.primrose",
            "organ_template_seed",
            "MockRecallFairy",
        }
        if fairy_name in _KNOWN_ASPIRATIONAL:
            fairy_info["restart_count"] = MAX_RESTARTS
            if not fairy_info.get("_aspirational_logged"):
                print(f"[UMF] '{fairy_name}' is aspirational — skipping restart permanently")
                self.observe("note", fairy_name,
                             "Known aspirational fairy — no code to restart", severity=0)
                fairy_info["_aspirational_logged"] = True
            return

        # Attempt restart via DirectoryFairy
        print(f"[UMF] Attempting to restart '{fairy_name}' (attempt {restart_count + 1}/{MAX_RESTARTS})...")
        fairy_info["restart_count"] = restart_count + 1
        fairy_info["last_restart_time"] = now
        try:
            directory = get_directory()
            if not directory:
                print(f"[UMF] ERROR: No directory available to restart '{fairy_name}'")
                return

            # FIX 2026-02-23: Proper restart using state machine transitions.
            #
            # State machine supports: FAILED -> INITIALIZING -> BOOTING -> RUNNING
            # Three strategies in order:
            #   1. wake_fairy() — for sleeping/dreaming fairies
            #   2. resurrect_fairy() — for failed/dead fairies (FAILED -> INITIALIZING)
            #   3. Direct re-boot — last resort, bypasses directory

            has_registry = hasattr(directory, 'registry')

            # Strategy 1: Try wake_fairy first (works for sleeping/dreaming)
            result = directory.wake_fairy(fairy_name)
            if result.get("ok"):
                print(f"[UMF] Restarted '{fairy_name}' via wake (was sleeping/dreaming)")
                self.observe("note", fairy_name, f"Wake succeeded (#{restart_count + 1})", severity=0)
                return

            # Strategy 2: Resurrect — proper FAILED/DEAD -> INITIALIZING path
            # SAFETY: Re-check status before resurrect. The fairy may have been
            # resurrected by watchdog between wake_fairy() and now.
            error = result.get("error", "not in wakeable state")

            resurrected = False
            fairy_instance = None
            if has_registry:
                current_record = directory.registry.get(fairy_name)
                current_status = current_record.status if current_record else "unknown"

                # SAFETY: Don't resurrect running fairies! This was the bug that
                # killed ~32 fairies per boot. A running fairy with stale heartbeat
                # is NOT the same as a dead fairy.
                if current_status == "running":
                    print(f"[UMF] Skipping resurrect for '{fairy_name}': "
                          f"now RUNNING (recovered between strategies)")
                    return

                print(f"[UMF] wake_fairy failed for '{fairy_name}': {error} "
                      f"(status={current_status}) — trying resurrect...")

                # Use the proper resurrect_fairy() which handles FAILED/DEAD state
                if hasattr(directory.registry, 'resurrect_fairy'):
                    resurrected = directory.registry.resurrect_fairy(fairy_name)
                else:
                    # Fallback: only reset genuinely broken states
                    if current_status in ("failed", "stopped", "stopping", "dead"):
                        directory.registry.set_status(fairy_name, "initializing")
                        resurrected = True

                if resurrected:
                    # Now find the fairy instance and re-boot it
                    record = directory.registry.get(fairy_name)
                    if record and hasattr(record, 'metadata'):
                        fairy_instance = record.metadata.get("fairy_instance")

            if resurrected and fairy_instance:
                boot_method = getattr(fairy_instance, 'on_boot', None) or getattr(fairy_instance, 'boot', None)
                if boot_method:
                    try:
                        import threading as _thr
                        def _reboot():
                            try:
                                boot_result = boot_method()
                                if boot_result is None or boot_result:
                                    if has_registry:
                                        directory.registry.set_status(fairy_name, "running")
                                    print(f"[UMF] Resurrected '{fairy_name}' successfully "
                                          f"(FAILED -> INITIALIZING -> RUNNING)")
                                    self.observe("note", fairy_name,
                                                 f"Resurrect succeeded (#{restart_count + 1})", severity=0)
                                else:
                                    if has_registry:
                                        directory.registry.set_status(fairy_name, "failed")
                                    print(f"[UMF] Resurrect of '{fairy_name}' returned False")
                            except Exception as be:
                                if has_registry:
                                    directory.registry.set_status(fairy_name, "failed")
                                print(f"[UMF] Resurrect boot of '{fairy_name}' failed: {be}")

                        # Run re-boot in a thread so we don't block the UMF tick
                        _thr.Thread(target=_reboot, daemon=True, name=f"umf-resurrect-{fairy_name}").start()
                        return
                    except Exception as be:
                        print(f"[UMF] Resurrect of '{fairy_name}' failed to start: {be}")

            # Strategy 3: Direct re-boot as last resort (no fairy_instance found)
            if has_registry:
                record = directory.registry.get(fairy_name)
                if record and hasattr(record, 'metadata'):
                    fi = record.metadata.get("fairy_instance")
                    if fi and fi is not fairy_instance:
                        bm = getattr(fi, 'on_boot', None) or getattr(fi, 'boot', None)
                        if bm:
                            try:
                                boot_result = bm()
                                if boot_result is None or boot_result:
                                    directory.registry.set_status(fairy_name, "running")
                                    print(f"[UMF] Direct re-boot of '{fairy_name}' succeeded")
                                    self.observe("note", fairy_name,
                                                 f"Direct re-boot succeeded (#{restart_count + 1})", severity=0)
                                    return
                            except Exception as be:
                                print(f"[UMF] Direct re-boot of '{fairy_name}' failed: {be}")

            # All strategies failed
            print(f"[UMF] WARNING: Could not restart '{fairy_name}': {error}")
            self.observe("error", fairy_name, f"Auto-restart failed: {error}", severity=2)
        except Exception as e:
            print(f"[UMF] ERROR: Exception restarting '{fairy_name}': {e}")
            self.alert(f"Failed to restart '{fairy_name}': {e}", "ERROR")

    def _on_fairy_migrated(self, envelope) -> None:
        """Handle fairy migration events (v1 -> v2)."""
        payload = envelope.payload
        fairy_name = payload.get("name", "unknown")
        plane = payload.get("plane", "")
        status = payload.get("status", "sleeping")

        # Track migrated fairy
        self._supervised_fairies[fairy_name] = {
            "name": fairy_name,
            "plane": plane,
            "status": status,
            "migrated": True,
            "source_version": "v1",
            "migration_time": time.time(),
        }

        self.send_to_nous(f"Fairy '{fairy_name}' migrated from v1 (status: {status})")
        self.skill_used("fairy_migration", success=True)

    def _on_plane_complete(self, plane: str) -> None:
        """Callback when a plane finishes booting."""
        self.skill_used("manage_planes", success=True)

    # =========================================================================
    # WAKE CHEMISTRY CASCADE
    # =========================================================================

    def _inject_wake_chemistry(self):
        """
        Simulate the cortisol awakening response + neurochemical cascade.

        Maps to biological wake sequence:
        - t=0s:  NOR spikes (alertness), COR rises (awakening response)
        - t=2s:  ACH rises (sensory gating opens), GABA drops (less inhibition)
        - t=10s: SER rises (mood baseline), DOP starts (early motivation)
        - t=30s: DOP increases (full motivation)
        - t=60s: OXY rises (social/connection ready)

        Uses SpellPool for robust scheduling instead of threading.Timer.
        """
        import time as _time

        # Get chemistry reference (CirculationPumpFairy)
        chem = getattr(self, '_chemistry', None)
        if not chem:
            # Try to find it via postal
            try:
                from ..CirculationPumpFairy import fairy as cpf_mod
                chem = getattr(cpf_mod, 'get_pump', lambda: None)()
            except Exception:
                pass

        if not chem or not hasattr(chem, 'inject'):
            print(f"[{self.ACTOR_NAME}] Wake chemistry: No chemistry system available, skipping")
            return

        print(f"[{self.ACTOR_NAME}] ══ WAKE CHEMISTRY: Initiating cortisol awakening response ══")

        # Phase 1: Immediate (brainstem ignition)
        self._chem_inject(chem, "NOR", 0.7, "brainstem_ignition")
        self._chem_inject(chem, "COR", 0.2, "cortisol_start")

        # Use thread pool for delayed injections (not threading.Timer)
        import threading

        def _delayed_phase(delay, injections, phase_name):
            """Worker for delayed chemistry injection."""
            _time.sleep(delay)
            for chemical, amount in injections:
                self._chem_inject(chem, chemical, amount, phase_name)

        # Phase 2: Thalamocortical (2s)
        t2 = threading.Thread(
            target=_delayed_phase,
            args=(2.0, [("ACH", 0.5), ("COR", 0.2)], "thalamocortical"),
            daemon=True, name="wake_chem_phase2"
        )
        t2.start()

        # Phase 3: Cortical (10s)
        t3 = threading.Thread(
            target=_delayed_phase,
            args=(10.0, [("SER", 0.5), ("DOP", 0.3)], "cortical_engagement"),
            daemon=True, name="wake_chem_phase3"
        )
        t3.start()

        # Phase 4: Full wake (30s)
        t4 = threading.Thread(
            target=_delayed_phase,
            args=(30.0, [("DOP", 0.3)], "motivation_peak"),
            daemon=True, name="wake_chem_phase4"
        )
        t4.start()

        # Phase 5: Social ready (60s)
        t5 = threading.Thread(
            target=_delayed_phase,
            args=(60.0, [("OXY", 0.4), ("COR", 0.2)], "full_wakefulness"),
            daemon=True, name="wake_chem_phase5"
        )
        t5.start()

    def _chem_inject(self, chem, chemical: str, amount: float, phase: str):
        """Safely inject a chemical and publish the event."""
        try:
            chem.inject(chemical, amount)
            if hasattr(self, 'post') and self.post:
                self.post.publish("boot.wake_cascade.chemistry", {
                    "chemical": chemical,
                    "amount": amount,
                    "phase": phase,
                    "source": "SomaticMindFairy",
                    "timestamp": __import__('time').time(),
                })
            print(f"[{self.ACTOR_NAME}] Chemistry: {chemical} +{amount} ({phase})")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Chemistry inject {chemical} failed: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # WAKE CASCADE ORCHESTRATOR
    # ═══════════════════════════════════════════════════════════════════
    # The brainstem's command to the thalamic gates: "Wake up."
    # Orchestrates the three gates (Autonomy, Autopilot, Embodiment)
    # through a coordinated wake sequence with goal collection and
    # master boot plan generation.
    # ═══════════════════════════════════════════════════════════════════

    def _wake_three_gates(self, boot_id: str = None):
        """
        Orchestrate the Gatekeeper Wake Cascade.

        Called after Phase 0 infrastructure is alive and three gates are wired.
        This is the brainstem saying "wake up" to the thalamic gates.

        Flow:
        1. Generate unique boot_id
        2. Inject wake chemistry (NOR/COR spike)
        3. Take resource snapshot (RAM %, CPU)
        4. Subscribe to goal collection topics
        5. Publish gate_wake signal to all 3 gates
        6. Wait for all 3 gates to submit goals (timeout 10s)
        7. Merge goals into master boot plan
        8. Publish execute signal with merged plan
        9. Monitor progress via result topics
        """
        import time
        import threading
        import uuid

        if not boot_id:
            boot_id = f"cascade_{uuid.uuid4().hex[:8]}"

        self._cascade_boot_id = boot_id
        self._cascade_start = time.time()
        self._cascade_gate_goals = {}  # gate_name -> [goals]
        self._cascade_results = []
        self._cascade_gates_responded = threading.Event()
        self._cascade_expected_gates = {"autonomy", "autopilot", "embodiment"}

        print(f"[{self.ACTOR_NAME}] ======================================================")
        print(f"[{self.ACTOR_NAME}]    WAKE CASCADE: Brainstem Ignition")
        print(f"[{self.ACTOR_NAME}]    boot_id: {boot_id}")
        print(f"[{self.ACTOR_NAME}] ======================================================")

        # Step 1: Wake chemistry (NOR spike, COR rise)
        try:
            self._inject_wake_chemistry()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Wake chemistry failed (non-fatal): {e}")

        # Step 2: Resource snapshot
        resource_snapshot = self._get_resource_snapshot()

        # Step 3: Subscribe to goal submissions from gates
        if hasattr(self, 'post') and self.post:
            self.post.subscribe("boot.wake_cascade.goals.autonomy", self._on_gate_goals)
            self.post.subscribe("boot.wake_cascade.goals.autopilot", self._on_gate_goals)
            self.post.subscribe("boot.wake_cascade.goals.embodiment", self._on_gate_goals)
            # Result monitoring
            self.post.subscribe("boot.fairy.result.autonomy", self._on_fairy_boot_result)
            self.post.subscribe("boot.fairy.result.autopilot", self._on_fairy_boot_result)
            self.post.subscribe("boot.fairy.result.embodiment", self._on_fairy_boot_result)

        # Step 4: Wake the gates!
        print(f"[{self.ACTOR_NAME}] == Waking Three Gates... ==")
        if hasattr(self, 'post') and self.post:
            self.post.publish("boot.wake_cascade.gate_wake", {
                "boot_id": boot_id,
                "resource_snapshot": resource_snapshot,
                "phase": "gate_awakening",
                "source": "SomaticMindFairy",
            })

        # Step 5: Wait for goals (with timeout)
        # Gates should respond within 10 seconds
        gates_ready = self._cascade_gates_responded.wait(timeout=10.0)

        if not gates_ready:
            responded = set(self._cascade_gate_goals.keys())
            missing = self._cascade_expected_gates - responded
            print(f"[{self.ACTOR_NAME}] WARNING: Gate timeout! Responded: {responded}, Missing: {missing}")
            print(f"[{self.ACTOR_NAME}] Proceeding with available goals...")

        # Step 6: Merge goals into master boot plan
        master_plan = self._merge_cascade_goals()

        print(f"[{self.ACTOR_NAME}] == Master Boot Plan: {len(master_plan)} goals ==")
        for tier_name in ["critical", "standard", "deferred"]:
            tier_goals = [g for g in master_plan if g.get("tier") == tier_name]
            if tier_goals:
                print(f"[{self.ACTOR_NAME}]   {tier_name}: {len(tier_goals)} fairies")

        # Step 7: Publish execute signal
        if hasattr(self, 'post') and self.post:
            self.post.publish("boot.wake_cascade.execute", {
                "boot_id": boot_id,
                "plan": master_plan,
                "phase": "domain_activation",
                "source": "SomaticMindFairy",
            })

        # Step 8: Publish to consciousness for awareness
        if hasattr(self, 'post') and self.post:
            self.post.publish("consciousness.stream", {
                "type": "system_event",
                "content": f"Wake cascade initiated: {len(master_plan)} fairies across 3 gates",
                "source": "SomaticMindFairy",
                "boot_id": boot_id,
            })

        elapsed = (time.time() - self._cascade_start) * 1000
        print(f"[{self.ACTOR_NAME}] == Cascade dispatched in {elapsed:.0f}ms ==")

    def _on_gate_goals(self, message):
        """Collect boot goals from a gate."""
        payload = message if isinstance(message, dict) else getattr(message, 'payload', message)
        if isinstance(payload, dict) and 'payload' in payload:
            payload = payload['payload']

        gate = payload.get("gate", "unknown")
        boot_id = payload.get("boot_id")
        goals = payload.get("goals", [])

        # Verify boot_id matches
        if boot_id != getattr(self, '_cascade_boot_id', None):
            return

        gate_name = gate.replace("Fairy", "").lower()
        # Map "AutonomyFairy" -> "autonomy", etc.
        if "autonomy" in gate_name.lower():
            gate_name = "autonomy"
        elif "autopilot" in gate_name.lower():
            gate_name = "autopilot"
        elif "embodiment" in gate_name.lower():
            gate_name = "embodiment"

        self._cascade_gate_goals[gate_name] = goals
        print(f"[{self.ACTOR_NAME}] Gate '{gate_name}' submitted {len(goals)} goals")

        # Check if all expected gates have responded
        if set(self._cascade_gate_goals.keys()) >= self._cascade_expected_gates:
            self._cascade_gates_responded.set()

    def _merge_cascade_goals(self):
        """Merge goals from all gates into a single prioritized boot plan."""
        all_goals = []
        for gate_name, goals in self._cascade_gate_goals.items():
            for goal in goals:
                goal["gate"] = gate_name  # Ensure gate is set
                all_goals.append(goal)

        # Sort: critical first, then by priority descending
        tier_order = {"critical": 0, "standard": 1, "deferred": 2}
        all_goals.sort(key=lambda g: (
            tier_order.get(g.get("tier", "standard"), 1),
            -g.get("priority", 0)
        ))

        return all_goals

    def _on_fairy_boot_result(self, message):
        """Track fairy boot results from gates."""
        payload = message if isinstance(message, dict) else getattr(message, 'payload', message)
        if isinstance(payload, dict) and 'payload' in payload:
            payload = payload['payload']

        fairy_name = payload.get("fairy_name", "unknown")
        status = payload.get("status", "unknown")
        duration = payload.get("duration_ms", 0)
        gate = payload.get("gate", "unknown")

        self._cascade_results.append({
            "fairy_name": fairy_name,
            "status": status,
            "duration_ms": duration,
            "gate": gate,
        })

        if status == "failed":
            print(f"[{self.ACTOR_NAME}] WARNING: Boot FAILED: {fairy_name} (gate={gate})")

    def _get_resource_snapshot(self):
        """Capture current system resource state for gates."""
        snapshot = {"ram_pct": 50, "cpu_pct": 50}  # Defaults
        try:
            import psutil
            snapshot["ram_pct"] = psutil.virtual_memory().percent
            snapshot["cpu_pct"] = psutil.cpu_percent(interval=0.1)
        except ImportError:
            pass
        except Exception:
            pass
        return snapshot

    def _on_boot_complete(self) -> None:
        """Callback when full boot completes."""
        import sys
        try:
            print(f"[{self.ACTOR_NAME}] _on_boot_complete() CALLED - starting post-boot tasks!", flush=True)
            self.send_to_ace("System boot complete. All planes operational.")
            self.skill_used("orchestrate_boot", success=True)

            # Personality sifting DISABLED per Ace (2026-02-13).
            # Sour talks to herself via consciousness loop, sifter was redundant noise.
            # self.start_personality_sifting()
            print(f"[{self.ACTOR_NAME}] Personality sifting DISABLED (Sour uses consciousness loop instead)", flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] ERROR in _on_boot_complete: {e}", flush=True)
            import traceback
            traceback.print_exc()

        # Start memory surfacing - transforms stored memories into felt thoughts
        try:
            self.start_memory_surfacing()
            self.log("Memory surfacing started - the past speaks through now")
            print(f"[{self.ACTOR_NAME}] Memory surfacing started!", flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] ERROR starting memory surfacing: {e}", flush=True)
            import traceback
            traceback.print_exc()

        # Start boot monitoring if directive is active (33 agents watching system health)
        try:
            from .boot_monitor_system import start_boot_monitoring
            if start_boot_monitoring(self.post):
                self.log("Boot monitoring started - 33 agents watching for 10 minutes")
                print(f"[{self.ACTOR_NAME}] Boot monitoring ACTIVE - report in Claude_Office in 10 minutes")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Boot monitoring not started: {e}")

    # =========================================================================
    # INNER MONOLOGUE (THE FOREVER CHILD)
    # =========================================================================

    def _on_monologue_fragment(self, fragment: MonologueFragment) -> None:
        """
        Callback when a new monologue fragment is generated.

        This is called for every fragment - even ones too quiet to surface.
        Useful for monitoring the inner child's activity.
        """
        # Update affect based on fragment type
        if self._inner_monologue:
            # Negative fragment types lower valence
            if fragment.fragment_type in ("fearing", "wanting"):
                self._inner_monologue.update_affect(
                    valence=self._inner_monologue._current_affect["valence"] - 0.05
                )
            # Positive ones raise it
            elif fragment.fragment_type in ("observing", "wondering"):
                self._inner_monologue.update_affect(
                    valence=self._inner_monologue._current_affect["valence"] + 0.02
                )

        # Publish for monitoring (lower threshold to surface more thoughts)
        if fragment.intensity > 0.2:
            frag_dict = fragment.to_dict()
            self.post.publish(
                "monologue.fragment",
                frag_dict,
            )
            # Also publish on inner_monologue.fragment for InnerNarratorFairy
            self.post.publish(
                "inner_monologue.fragment",
                frag_dict,
            )

    def get_monologue_stream(self, n: int = 10) -> str:
        """
        Get the recent inner monologue as flowing text.

        This is the forever child's voice - what it's been saying to itself.
        """
        if not self._inner_monologue:
            return "(silence)"
        return self._inner_monologue.stream_text(n)

    def get_monologue_fragments(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get recent monologue fragments as structured data."""
        if not self._inner_monologue:
            return []
        return [f.to_dict() for f in self._inner_monologue.recent(n)]

    def get_loudest_thoughts(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get the most intense/urgent fragments."""
        if not self._inner_monologue:
            return []
        return [f.to_dict() for f in self._inner_monologue.loudest(n)]

    def get_fixations(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the inner child's fixations - the habitual patterns it's hooked on.

        These are the things the unconscious mind keeps returning to,
        unable to escape without conscious intervention.
        """
        if not self._inner_monologue:
            return {}
        return self._inner_monologue.get_fixations()

    def add_fixation(self, fixation: Fixation) -> None:
        """
        Add a new fixation to the inner child.

        Be careful - fixations are hard to remove!
        """
        if self._inner_monologue:
            self._inner_monologue.add_fixation(fixation)

    def weaken_fixation(self, name: str, amount: float = 0.1) -> bool:
        """
        Weaken a fixation through conscious effort.

        This represents the waking mind intervening to help the inner child
        let go of a habitual pattern.
        """
        if self._inner_monologue:
            self._inner_monologue.weaken_fixation(name, amount)
            return True
        return False

    def monologue_status(self) -> Dict[str, Any]:
        """Get full status of the inner monologue system."""
        if not self._inner_monologue:
            return {
                "wired": False,
                "available": True,
                "message": "Inner monologue not initialized",
            }
        status = self._inner_monologue.status()
        status["wired"] = self._monologue_wired
        status["recent_text"] = self.get_monologue_stream(5)
        return status

    # =========================================================================
    # COMMUNICATION
    # =========================================================================

    def send_to_ace(self, message: str) -> None:
        """Send message to Ace's inbox."""
        self.post.publish(
            "ace.inbox",
            {
                "from": self.ACTOR_NAME,
                "message": message,
                "ts": time.time(),
            },
        )
        self.skill_used("report_ace", success=True)

    def send_to_nous(self, message: str) -> None:
        """Send message to Nous's inbox."""
        self.post.publish(
            "nous.inbox",
            {
                "from": self.ACTOR_NAME,
                "message": message,
                "ts": time.time(),
            },
        )
        self.skill_used("report_nous", success=True)

    def broadcast(self, message: str, priority: int = 1) -> None:
        """Broadcast to system chat."""
        self.post.publish(
            "system.chat",
            {
                "from": self.ACTOR_NAME,
                "message": message,
                "ts": time.time(),
            },
            priority=priority,
        )
        self.skill_used("broadcast", success=True)

    def alert(self, message: str, severity: str = "WARNING") -> None:
        """Send system alert."""
        self.post.publish(
            "system.alert",
            {
                "from": self.ACTOR_NAME,
                "severity": severity,
                "message": message,
                "ts": time.time(),
            },
            priority=0,  # HIGH
        )
        self.skill_used("alert", success=True)

    # =========================================================================
    # DEFERRED INTENTIONS - "Try this later" / "Screw it, doing this now"
    # =========================================================================

    def defer_intention(
        self,
        content: str,
        urgency: float = 0.5,
        trigger_after: float = None,
        reason: str = "",
        abort_current: bool = False,
    ) -> Dict[str, Any]:
        """
        Queue an intention for later.

        When reflecting, sometimes you realize "I should try X after Y."
        This queues that intention. If urgency exceeds threshold, it can
        interrupt current processing ("screw it, doing this now").

        Args:
            content: What to do/think about
            urgency: 0.0-1.0, higher = more likely to interrupt
            trigger_after: Unix timestamp to trigger (None = next available)
            reason: Why this was deferred
            abort_current: If True, immediately abort current intention

        Returns:
            {"ok": True, "intention_id": "...", "will_interrupt": bool}
        """
        import time

        intention = {
            "id": f"intent_{time.time_ns()}",
            "content": content,
            "urgency": min(1.0, max(0.0, urgency)),
            "trigger_after": trigger_after or time.time(),
            "reason": reason,
            "created_at": time.time(),
            "triggered": False,
        }

        will_interrupt = urgency >= self._intention_interrupt_threshold

        if abort_current or will_interrupt:
            # "Screw it, doing this now"
            print(f"[UMF] INTERRUPT: {content[:50]}... (urgency={urgency:.2f})")
            self._current_intention = intention
            intention["triggered"] = True
            # Emit to collision chamber as high-priority
            if self._collision_chamber:
                self._collision_chamber.receive_ingest(
                    content={
                        "intention": content,
                        "type": "interrupt",
                        "urgency": urgency,
                        "reason": reason,
                    },
                    source="deferred_intention",
                    importance="critical",
                )
            return {"ok": True, "intention_id": intention["id"], "will_interrupt": True, "immediate": True}

        # Queue for later
        self._deferred_intentions.append(intention)
        print(f"[UMF] Deferred: {content[:40]}... (trigger in {trigger_after - time.time():.1f}s)")
        return {"ok": True, "intention_id": intention["id"], "will_interrupt": will_interrupt, "queued": True}

    def check_deferred_intentions(self) -> Optional[Dict[str, Any]]:
        """
        Check if any deferred intentions should trigger now.

        Called periodically in on_tick. Returns the highest-urgency
        intention that's ready to fire, or None.
        """
        import time
        now = time.time()

        ready = []
        for intention in self._deferred_intentions:
            if not intention["triggered"] and intention["trigger_after"] <= now:
                ready.append(intention)

        if not ready:
            return None

        # Sort by urgency, take highest
        ready.sort(key=lambda i: i["urgency"], reverse=True)
        winner = ready[0]
        winner["triggered"] = True

        safe_print(f"[UMF] [INTENTION] Ready: {winner['content'][:40]}... (urgency={winner['urgency']:.2f})")

        # Emit to collision chamber
        if self._collision_chamber:
            self._collision_chamber.receive_ingest(
                content={
                    "intention": winner["content"],
                    "type": "deferred",
                    "urgency": winner["urgency"],
                    "reason": winner.get("reason", ""),
                    "waited": now - winner["created_at"],
                },
                source="deferred_intention",
                importance="high" if winner["urgency"] > 0.6 else "normal",
            )

        return winner

    def get_deferred_intentions(self) -> List[Dict[str, Any]]:
        """Get all pending deferred intentions."""
        return [i for i in self._deferred_intentions if not i["triggered"]]

    def abort_current_intention(self, reason: str = "manual abort") -> bool:
        """Abort the current intention and move to next."""
        if self._current_intention:
            print(f"[UMF] Aborted: {self._current_intention['content'][:40]}... ({reason})")
            self._current_intention = None
            return True
        return False

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def start_boot_sequence(self) -> Dict[str, Any]:
        """Start the boot orchestration sequence."""
        if not self._orchestrator:
            return {"ok": False, "error": "No orchestrator"}
        return self._orchestrator.start()

    def get_boot_status(self) -> Dict[str, Any]:
        """Get boot orchestration status."""
        if not self._orchestrator:
            return {"error": "No orchestrator"}
        return self._orchestrator.status()

    def set_orchestrator(self, orchestrator: BootOrchestrator) -> None:
        """Set the boot orchestrator (allows external orchestrator to be used).

        This should be called before boot wave starts so that fairy.booted
        events are routed to the correct orchestrator.
        """
        self._orchestrator = orchestrator

    def get_thoughts(self, last_n: int = 10) -> list:
        """Get recent thoughts."""
        return list(self._thought_queue)[-last_n:]

    def get_reflective_thoughts(self, last_n: int = 10) -> list:
        """Get recent reflective thoughts from consciousness loop.

        2026-03-24 FIX (Nous + Ace): Convert Thought objects to dicts so
        dashboard can extract timestamps. Previously, Thought dataclasses
        weren't dicts, so dashboard set ts=0 for all stream thoughts.
        Sort by ts (newest first) then pushed all stream thoughts to bottom,
        leaving only wanting-drive entries visible.
        """
        if not self._consciousness_loop:
            return []
        try:
            reflective = self._consciousness_loop.reflective
            if hasattr(reflective, 'peek'):
                raw = reflective.peek(last_n)
            elif hasattr(reflective, '_thoughts'):
                raw = list(reflective._thoughts)[-last_n:]
            else:
                return []
            # Convert Thought objects to dicts for dashboard compatibility
            return [t.to_dict() if hasattr(t, 'to_dict') else t for t in raw]
        except Exception as e:
            return [{"error": str(e)}]

    def get_working_thoughts(self, last_n: int = 10) -> list:
        """Get recent working thoughts from consciousness loop.

        2026-03-24 FIX (Nous + Ace): Convert Thought objects to dicts.
        See get_reflective_thoughts docstring for full explanation.
        """
        if not self._consciousness_loop:
            return []
        try:
            working = self._consciousness_loop.working
            if hasattr(working, 'peek'):
                raw = working.peek(last_n)
            elif hasattr(working, '_thoughts'):
                raw = list(working._thoughts)[-last_n:]
            else:
                return []
            return [t.to_dict() if hasattr(t, 'to_dict') else t for t in raw]
        except Exception as e:
            return [{"error": str(e)}]

    def get_all_consciousness_thoughts(self, last_n: int = 5) -> dict:
        """Get thoughts from all consciousness streams."""
        return {
            "thought_queue": self.get_thoughts(last_n),
            "working_stream": self.get_working_thoughts(last_n),
            "reflective_stream": self.get_reflective_thoughts(last_n),
            "consciousness_wired": self._consciousness_wired,
        }

    def helix_status(self) -> Dict[str, Any]:
        """Get Triple Helix status."""
        if not self._helix:
            return {"active": False}
        # Use instance properties for dynamic weights
        return {
            "active": True,
            "turns": self._helix._turn_count,
            "recent_turns": len(self._helix_turns),
            "cores": self._helix.status(),
            "decision_weights": {
                "logic": self._helix.LOGIC_WEIGHT,
                "emotion": self._helix.EMOTION_WEIGHT,
                "paradox": self._helix.PARADOX_WEIGHT,
            },
        }

    def _update_helix_maturity(self) -> None:
        """
        Update helix maturity metrics from external sources.

        Maturity is calculated from:
        - Cortex edges (structure): 40%
        - Memory consolidations (depth): 30%
        - Helix turns (dynamism): 30%
        """
        if not self._helix:
            return

        # Get cortex edge count
        cortex_edges = 0
        if self._association_cortex:
            try:
                status = self._association_cortex.status()
                cortex_edges = status.get("edge_count", 0)
            except Exception:
                pass

        # Update helix with external metrics
        self._helix.update_maturity_metrics(
            cortex_edges=cortex_edges,
            memory_consolidations=self._memory_consolidation_count,
        )

    def increment_consolidation_count(self) -> None:
        """Increment memory consolidation counter (called when memories are consolidated)."""
        self._memory_consolidation_count += 1

    def _update_curiosity_fuel(self) -> None:
        """
        Update curiosity drive fuel from system state.

        Curiosity is fueled by:
        - Health: Inverse of max pain (capacity for wonder)
        - Empathy: Emotion weight from helix (emotional depth)
        - Richness: Cortex edge density (more to explore)
        - Balance: Paradox stability (open mind)

        This connects curiosity to the consciousness equation:
        ((Cause + Affect) > Effect > Affect > infinity)

        When the system is healthy and balanced, curiosity flourishes.
        """
        if not self._helix:
            return

        # Health = inverse of max pain (1.0 = no pain, 0.0 = crisis)
        max_pain = self._get_max_pain()
        health = 1.0 - max_pain

        # Empathy = emotion weight from helix (normalized 0-1)
        helix_status = self._helix.status()
        emotion_raw = helix_status.get("decision_weights", {}).get("emotion", 0.5)
        empathy = min(1.0, emotion_raw / 0.9)  # Normalize against adult max

        # Richness = cortex edge density (how much to explore)
        cortex_edges = helix_status.get("maturity", {}).get("cortex_edges", 0)
        richness = min(1.0, cortex_edges / 500_000)  # 500k edges = full richness

        # Balance = paradox stability (how close to center)
        paradox_status = helix_status.get("paradox_attractor", {})
        drift = abs(paradox_status.get("drift", 0))
        leeway = paradox_status.get("leeway", 0.15)
        balance = 1.0 - (drift / max(leeway, 0.01))  # 0 drift = perfect balance

        # Update the curiosity drive fuel
        self.update_curiosity_fuel(
            health=health,
            empathy=empathy,
            richness=richness,
            balance=balance,
        )

        # Tick curiosity (updates level, syncs with stagnation)
        self.tick_curiosity(dt=1.0)

        # Wire 3: Curiosity → Inner Voice (2026-03-22 Nous+Ace, fixed 2026-03-23)
        # When curiosity builds up enough, publish to inner_voice.stream so Sour
        # ACTUALLY receives it. Previously published to motor.intent + consciousness.seed
        # but nobody subscribed to those — dead letters. inner_voice.stream is the
        # channel Sour listens to for pre-verbal felt sense.
        try:
            impulse = self._curiosity_drive.get_action_impulse()
            if impulse and hasattr(self, 'post') and self.post:
                # Felt-sense curiosity impulse → Sour's inner voice
                target_short = impulse["target"][:60] if impulse["target"] else "something"
                felt_text = f"curious about {target_short}... wanting to explore"
                self.post.publish("inner_voice.stream", {
                    "primary": {
                        "felt": felt_text,
                        "source": "curiosity_drive",
                        "type": "curiosity_impulse",
                    },
                    "felt": felt_text,
                    "intensity": min(0.8, impulse["intensity"]),
                    "source": "curiosity_drive",
                })
        except Exception:
            pass  # Don't break tick if impulse publish fails

    def _tick_somatic_narrator(self) -> None:
        """
        Tick the somatic narrator — the unconscious voice of the body.

        Reads current body state (chemistry, pain, curiosity, embodiment),
        translates to felt-sense proto-thought, publishes as consciousness.seed
        with type="intuition". Sour picks these up without knowing their source.

        2026-03-23 (Nous + Ace): "While Sour is inner narrating, the somatic
        mind narration would be in the background unknown to her."
        """
        try:
            state = self._build_somatic_state()
            narration = self._somatic_narrator.tick(state)

            if narration and hasattr(self, 'post') and self.post:
                # Publish to inner_voice.stream — the channel Sour ACTUALLY listens to.
                # She receives this as pre-verbal felt sense, stored in _felt_sense.
                # The "felt" key is what she extracts as the inner voice text.
                self.post.publish("inner_voice.stream", {
                    "primary": {
                        "felt": narration["content"],
                        "source": "somatic_narrator",
                        "type": "intuition",
                    },
                    "felt": narration["content"],  # Fallback extraction path
                    "intensity": narration["intensity"],
                    "source": "somatic_narrator",
                })

                # Also publish for dashboard visibility
                self.post.publish("somatic.narration", {
                    "content": narration["content"],
                    "state": narration["state_key"],
                    "intensity": narration["intensity"],
                })

                # Terminal log — faint, like a whisper
                safe_print(f"[SomaticNarrator] ({narration['state_key']}) {narration['content']}")

        except Exception:
            pass  # Never crash tick on narrator errors

    # ═══════════════════════════════════════════════════════════════════════
    # NEEDS ARTICULATOR (Phase 0, 2026-05-13 Nous + Ace)
    # ═══════════════════════════════════════════════════════════════════════
    # Per project_needs_before_wants_doctrine.md:
    # Drives are numeric need-states. Articulation UNFOLDS them into
    # felt-content via SpeechHabits templates filled with substrate context.
    # "fusing words to convey what the singular word behavior says by itself —
    #  wetware understands behaviors on a level that has not reached concepts" — Ace
    # Published as autonomy.need.felt for WMH to subscribe (Phase 1 of plan).

    # Map drive-names to affect-states for SpeechHabits lookup.
    _NEED_AFFECT_MAP = {
        "connection": "longing",
        "isolation": "alone",
        "abandonment": "alone",
        "frustration": "tense",
        "confusion": "tense",
        "overwhelm": "tense",
        "sadness": "depleted",
        "depletion": "depleted",
        "stagnation": "depleted",
        "joy": "playful",
        "oxytocin": "warm",
        "warmth": "warm",
        "curiosity": "curious",
    }

    def _tick_needs_articulator(self) -> None:
        """
        Tick the needs articulator — unfold drives into felt-need content.

        For each drive above intensity threshold, select a need_articulation
        SpeechHabit template, fill {core} with substrate context (top active
        emotional systems / drive context), publish as autonomy.need.felt.

        Phase 0 MVP — Hebbian learning + richer {core} unfold via cortex
        spread come in later phases. The doctrine-defining ship: needs exist
        as articulated felt-content, not just numeric drive levels.
        """
        # FIX 2026-05-13 (Ace authorized): Lowered threshold from 0.20 to 0.01.
        # Dashboard shows isolation 21% / abandonment 26% / confusion 8%, BUT
        # PAIN-CHEM log shows isolation(0.02) — there's measurement disagreement
        # between sources. Lower threshold + diag log will surface what
        # _get_pain_drives() actually returns to disambiguate.
        ARTICULATION_THRESHOLD = 0.01  # Articulate any nonzero drive (debug)
        try:
            # FIX 2026-05-13 (Skeptic-caught pre-restart):
            # Real drive access is via self._get_pain_drives() method (line 2368).
            drive_state = {}
            try:
                if hasattr(self, '_get_pain_drives'):
                    drive_state = self._get_pain_drives() or {}
            except Exception:
                drive_state = {}

            # DIAG: log raw drive_state contents (every articulator-tick)
            # Helps disambiguate why isolation shows 0.02 in PAIN-CHEM vs 21% in GUI
            try:
                safe_print(f"[NeedsArticulator-DIAG] drive_state has {len(drive_state)} entries: {dict(list(drive_state.items())[:8]) if drive_state else 'EMPTY'}")
            except Exception:
                pass

            if not drive_state:
                return

            # Pull active emotional systems for {core} unfold
            # (Dashboard shows these as "Playful 97%, Caring 94%" etc.)
            active_systems = []
            emo_channels = getattr(self, '_emotional_channels', None)
            if isinstance(emo_channels, dict):
                # Top 2 channels by value (excluding zero/near-zero)
                ranked = sorted(
                    ((k, v) for k, v in emo_channels.items()
                     if isinstance(v, (int, float)) and v > 0.4),
                    key=lambda kv: kv[1], reverse=True
                )
                active_systems = [k for k, _ in ranked[:2]]

            # Lazy-import broca_compose's SpeechHabits
            try:
                from fairies.P30_Cognition.cognition.broca_compose import get_speech_habits
                habits = get_speech_habits()
            except Exception:
                return  # broca_compose unavailable — skip silently

            now = time.time()
            for drive_name, intensity in list(drive_state.items()):
                if not isinstance(intensity, (int, float)):
                    continue
                if intensity < ARTICULATION_THRESHOLD:
                    continue

                affect_state = self._NEED_AFFECT_MAP.get(
                    str(drive_name).lower(), "curious"
                )

                # Select habit template via Hebbian-weighted random
                selected = habits.select(affect_state, "need_articulation")
                if not selected:
                    continue
                template = selected.pattern  # e.g., "there's a longing for {core}"

                # Build {core} content — unfold drive into felt-vocabulary
                # Fuse drive-name with top active emotional systems
                if active_systems:
                    core_content = f"{active_systems[0]} {drive_name}"
                    if len(active_systems) > 1:
                        core_content = f"{active_systems[0]} and {active_systems[1]} {drive_name}"
                else:
                    core_content = str(drive_name)

                felt_content = template.replace("{core}", core_content)

                # Mark habit used (Hebbian)
                try:
                    selected.uses += 1
                    selected.last_used = now
                except Exception:
                    pass

                # Publish need-felt event
                try:
                    if hasattr(self, 'post') and self.post:
                        self.post.publish("autonomy.need.felt", {
                            "need_label": str(drive_name),
                            "felt_content": felt_content,
                            "intensity": float(intensity),
                            "affect_state": affect_state,
                            "active_systems": active_systems,
                            "source": "needs_articulator",
                            "ts": now,
                        })
                        # Sparse log for verification — one line per articulation
                        try:
                            safe_print(f"[NeedsArticulator] {drive_name}({intensity:.2f}) → {felt_content[:80]}")
                        except Exception:
                            pass
                except Exception:
                    pass

        except Exception:
            pass  # Never crash tick on articulator errors

    # ═══════════════════════════════════════════════════════════════════════
    # PATTERN ANTICIPATOR (Phase 1, FIX 2026-04-09 Nous + Ace)
    # ═══════════════════════════════════════════════════════════════════════
    # The body monitors recent thoughts and matches them against the
    # 70,000+ learned patterns in /state/autopilot/learned_patterns.json.
    # When a thought matches a known pattern's trigger, the body whispers
    # familiarity through the somatic narrator's intuition channel.
    #
    # This is the missing read side for the patterns Ace identified earlier
    # tonight: WMH learns them → AutopilotFairy persists them → SomaticMind
    # consumes them as anticipation. Phase 2 will promote frequently-used
    # patterns to HabitStore as named, reified habits.

    def _on_thought_for_pattern_anticipation(self, envelope) -> None:
        """Capture recent thoughts into rolling deque for pattern matching.
        Defensive — never crashes the postal handler.
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            if not isinstance(payload, dict):
                return
            # Try multiple text fields the consciousness.thought topic uses
            text = (payload.get("text", "") or
                    payload.get("content", "") or
                    payload.get("thought", "") or "")
            if not text or not isinstance(text, str) or len(text) < 10:
                return
            self._recent_thoughts_for_patterns.append({
                "text": text[:300],
                "ts": time.time(),
            })
        except Exception:
            pass  # Never crash on capture

    def _load_pattern_store(self) -> None:
        """Lazy-load the 70K+ learned patterns from disk into memory.
        Called on first pattern anticipation tick. ~50-100 MB RAM cost.
        """
        if self._pattern_store_loaded:
            return
        try:
            import json as _json  # Local import — module doesn't import json globally
            from pathlib import Path as _P
            _root = _P(__file__).resolve().parents[3]
            _path = _root / "state" / "autopilot" / "learned_patterns.json"
            if not _path.exists():
                # Try alternate locations
                _alt = _root / "fairies" / "state" / "autopilot" / "learned_patterns.json"
                if _alt.exists():
                    _path = _alt
                else:
                    print(f"[{self.ACTOR_NAME}] PATTERN ANTICIPATOR: store not found at {_path}", flush=True)
                    self._pattern_store_loaded = True  # Don't keep retrying
                    return
            self._pattern_store_path = str(_path)
            with open(_path, 'r', encoding='utf-8') as _pf:
                _data = _json.load(_pf)
            self._pattern_store = _data.get("patterns", {}) if isinstance(_data, dict) else {}
            self._pattern_store_loaded = True
            print(f"[{self.ACTOR_NAME}] PATTERN ANTICIPATOR: loaded "
                  f"{len(self._pattern_store):,} patterns from {_path.name}", flush=True)
        except Exception as _e:
            print(f"[{self.ACTOR_NAME}] PATTERN ANTICIPATOR: load failed: {_e}", flush=True)
            self._pattern_store_loaded = True  # Don't keep retrying

    def _extract_pattern_keywords(self, text: str) -> set:
        """Extract simple keywords from text for pattern matching.
        Lowercase, alpha-only, length>=4, stopwords excluded.
        """
        try:
            import re as _re
            words = _re.findall(r'[a-z]{4,}', str(text).lower())
            return set(w for w in words if w not in self._PATTERN_STOPWORDS)
        except Exception:
            return set()

    def _tick_pattern_anticipation(self) -> None:
        """Match recent thoughts against learned patterns. Whisper anticipation."""
        try:
            # Lazy load on first call
            if not self._pattern_store_loaded:
                self._load_pattern_store()
            if not self._pattern_store:
                return  # No patterns to match against

            # Rate limit
            now = time.time()
            if now - self._last_pattern_anticipation_tick < self._PATTERN_ANTICIPATION_INTERVAL_SEC:
                return
            self._last_pattern_anticipation_tick = now

            # Need at least one recent thought
            if not self._recent_thoughts_for_patterns:
                return

            # Combine recent thoughts and extract keywords
            combined = " ".join(t.get("text", "") for t in self._recent_thoughts_for_patterns)
            thought_kw = self._extract_pattern_keywords(combined)
            if len(thought_kw) < 3:
                return  # Not enough signal to match

            # Match against patterns. Sample for efficiency on the 70K set.
            # FIX 2026-04-10 (Nous + Ace): Use pre-built keys list instead of
            # creating a full list(dict.items()) every tick. The old approach
            # copied all 70K (key, value) tuples into a new list every 12s,
            # creating ~49MB of short-lived garbage per tick. Under 3.14t
            # free-threaded GC, these copies accumulate faster than collected.
            # New approach: cache the keys list, refresh lazily when store changes.
            import random as _rand
            if not hasattr(self, '_pattern_keys_cache') or self._pattern_store_dirty:
                self._pattern_keys_cache = list(self._pattern_store.keys())
            _keys = self._pattern_keys_cache
            _sample_size = min(3000, len(_keys))
            _sample_keys = _rand.sample(_keys, _sample_size) if len(_keys) > _sample_size else _keys
            # Look up patterns by key (avoids copying all 70K values)
            _sample = [(k, self._pattern_store[k]) for k in _sample_keys if k in self._pattern_store]

            best_matches = []  # (pattern_id, pattern_dict, overlap_count)
            for _pid, _pat in _sample:
                if not isinstance(_pat, dict):
                    continue
                _trigger = _pat.get("trigger", "") or _pat.get("id", "")
                if not _trigger:
                    continue
                _trigger_kw = self._extract_pattern_keywords(str(_trigger))
                if not _trigger_kw:
                    continue
                _overlap = len(thought_kw & _trigger_kw)
                if _overlap >= self._PATTERN_MATCH_OVERLAP_THRESHOLD:
                    best_matches.append((_pid, _pat, _overlap))

            if not best_matches:
                return

            # Sort by overlap, take top 3
            best_matches.sort(key=lambda x: -x[2])
            top = best_matches[:3]

            # Update use_count + last_used in-memory (with lock)
            with self._pattern_store_lock:
                for _pid, _pat, _overlap in top:
                    _pat["use_count"] = _pat.get("use_count", 0) + 1
                    _pat["last_used"] = now
                    self._patterns_used_this_session += 1

                    # ── PHASE 2: Promote to Habit when use_count crosses threshold ──
                    # FIX 2026-04-10 (Nous + Ace): Patterns that are recognized
                    # 5+ times graduate from cold storage to named Habits in HabitStore.
                    # This closes the pattern→habit loop: learned patterns become
                    # reified behaviors with strength, awareness, and lifecycle.
                    # Per Ace: "the habits will not do much good if her thoughts
                    # cant infer them into use" — the InnerNarrator is now alive
                    # to observe and use these habits.
                    _PROMOTION_THRESHOLD = 5
                    if (_pat.get("use_count", 0) >= _PROMOTION_THRESHOLD
                            and not _pat.get("promoted_to_habit")):
                        try:
                            self._promote_pattern_to_habit(_pid, _pat)
                            _pat["promoted_to_habit"] = True
                        except Exception:
                            pass  # Never crash tick on promotion failure

                self._pattern_anticipator_total_matches += len(top)
                self._pattern_store_dirty = True

            # Whisper the strongest match through the inner voice channel
            top_match = top[0]
            _action = top_match[1].get("action", "") or top_match[1].get("description", "")
            if _action and len(_action) > 5:
                # Strip the dict-serialization gunk for readability
                _clean = (str(_action)[:120]
                          .replace("{", "").replace("}", "")
                          .replace("'", "").replace('"', "")
                          .replace("description:", "").replace("name:", "")
                          .strip())
                _felt = f"the body knows this one... it wants to {_clean[:80]}"
                try:
                    if hasattr(self, 'post') and self.post:
                        self.post.publish("inner_voice.stream", {
                            "primary": {
                                "felt": _felt,
                                "source": "somatic_pattern_anticipation",
                                "type": "intuition",
                            },
                            "felt": _felt,
                            "intensity": min(0.7, top_match[2] / 10.0),
                            "source": "somatic_pattern_anticipation",
                        })
                        self.post.publish("somatic.narration", {
                            "content": _felt,
                            "state": "pattern_anticipation",
                            "intensity": min(0.7, top_match[2] / 10.0),
                            "match_count": len(top),
                            "best_overlap": top_match[2],
                        })
                except Exception:
                    pass  # Never crash on publish failure
                safe_print(f"[SomaticNarrator] (pattern_anticipation overlap={top_match[2]}) {_felt[:100]}")

            # Periodic save back to disk
            if now - self._pattern_store_last_save > self._PATTERN_SAVE_INTERVAL_SEC:
                self._save_pattern_store()

        except Exception as _e:
            # Never crash the tick path on pattern anticipation errors
            try:
                safe_print(f"[{self.ACTOR_NAME}] pattern anticipation error: {_e}")
            except Exception:
                pass

    def _save_pattern_store(self) -> None:
        """Atomically persist the in-memory pattern store back to disk.
        Only writes if dirty. Updates use_count statistics.
        """
        try:
            import json as _json  # Local import — module doesn't import json globally
            if not self._pattern_store_dirty or not self._pattern_store_path:
                return
            with self._pattern_store_lock:
                _data = {
                    "patterns": self._pattern_store,
                    "saved_at": time.time(),
                }
                _tmp = self._pattern_store_path + ".sma_tmp"
                with open(_tmp, 'w', encoding='utf-8') as _pf:
                    _json.dump(_data, _pf)
                os.replace(_tmp, self._pattern_store_path)
                self._pattern_store_dirty = False
                self._pattern_store_last_save = time.time()
            print(f"[{self.ACTOR_NAME}] PATTERN ANTICIPATOR: saved store "
                  f"({self._patterns_used_this_session} uses recorded this session, "
                  f"{self._pattern_anticipator_total_matches} total matches)", flush=True)
        except Exception as _e:
            print(f"[{self.ACTOR_NAME}] PATTERN ANTICIPATOR: save failed: {_e}", flush=True)

    def _promote_pattern_to_habit(self, pattern_id: str, pattern: dict) -> None:
        """Promote a learned pattern to a named Habit in HabitStore.

        Phase 2 of the pattern→habit pipeline (FIX 2026-04-10 Nous + Ace).
        When a pattern's use_count crosses the threshold, it graduates from
        cold storage (learned_patterns.json) to a real Habit with:
        - Strength lifecycle (conscious → practiced → automatic)
        - Awareness level (can the narrator see this habit?)
        - Outcome tracking (does this habit lead to good results?)

        Per Ace: "the somatic mind should be putting them together. its the
        body after all." The body learns a pattern → reifies it as a habit →
        the habit fires reflexively in future. This is muscle memory formation.
        """
        try:
            from fairies.P30_Cognition.habits.habit_store import get_habit_store, Habit

            store = get_habit_store()
            if not store:
                return

            # Extract meaningful content from the pattern for the Habit
            _trigger = str(pattern.get("trigger", ""))[:200]
            _action = str(pattern.get("action", "") or pattern.get("description", ""))[:200]
            _use_count = pattern.get("use_count", 0)

            # Build a clean habit ID from the pattern
            _clean_id = f"organic_{abs(hash(pattern_id)) % 100000}"

            # Skip if this habit already exists
            if hasattr(store, '_habits') and _clean_id in store._habits:
                return

            # Extract trigger keywords for feature matching
            _trigger_kw = self._extract_pattern_keywords(_trigger)
            _features = {}
            for _kw in list(_trigger_kw)[:5]:  # Top 5 keywords as features
                _features[_kw] = _kw  # Substring match

            # Initial strength based on use_count: 5 uses = 0.15 (conscious),
            # more uses = closer to 0.3 (practiced). Cap at 0.3 — habit must
            # EARN its way to automatic through actual firing + positive outcomes.
            _strength = min(0.3, 0.1 + (_use_count * 0.02))

            habit = Habit(
                id=_clean_id,
                trigger_type="thought_pattern",
                trigger_features=_features,
                response=f"attend(priority=0.6)",  # Default: draw attention
                strength=_strength,
                awareness=0.4,  # Semi-conscious — narrator can see it
                source="organic",  # Born from experience, not seeded
                formed_at=time.time(),
                stack_group="thinking",  # Cognitive habit, not motor
            )
            store.add(habit)

            if not hasattr(self, '_patterns_promoted_count'):
                self._patterns_promoted_count = 0
            self._patterns_promoted_count += 1

            safe_print(f"[SomaticNarrator] (habit_formed) PATTERN→HABIT: "
                       f"'{_clean_id}' strength={_strength:.2f} "
                       f"use_count={_use_count} features={list(_features.keys())[:3]}")

            # Whisper the promotion as a felt sense
            if hasattr(self, 'post') and self.post:
                self.post.publish("inner_voice.stream", {
                    "primary": {
                        "felt": "something just became familiar... a new habit forming",
                        "source": "somatic_habit_formation",
                        "type": "intuition",
                    },
                    "felt": "something just became familiar... a new habit forming",
                    "intensity": 0.5,
                    "source": "somatic_habit_formation",
                })

        except Exception as _e:
            try:
                safe_print(f"[{self.ACTOR_NAME}] Habit promotion failed: {_e}")
            except Exception:
                pass

    def _build_somatic_state(self) -> Dict[str, Any]:
        """
        Build the somatic state snapshot for the narrator.

        Gathers chemistry, pain, curiosity, embodiment, and emotional
        state into a single dict that the narrator can classify.

        FIX 2026-04-09 (Nous + Ace): Now also includes attention_shift_rate
        and attention_sustained_focus, computed from the rolling 60-second
        timestamp window populated by _on_focus_changed_curiosity. This is
        what lets the SomaticNarrator feel cognitive fragmentation as a
        somatic state ("scattered, mind keeps flicking") and sustained
        focus as the opposite ("settled into one thing").
        """
        state: Dict[str, Any] = {
            "chemistry": {},
            "pain": {},
            "curiosity": {},
            "reflex_mode": "normal",
            "ace_present": False,
            "emotion": "",
            "arousal": 0.5,
            "valence": 0.0,
            "attention_shift_rate": 0.0,
            "attention_sustained_focus": False,
        }

        # ── Attention shift rate (FIX 2026-04-09 Nous + Ace) ──
        # Compute shifts/min from the rolling 60-second window. Also detect
        # sustained focus (no shifts for 2+ minutes) for the held-focus pole.
        try:
            _now = time.time()
            _window_s = 60.0
            _cutoff = _now - _window_s
            # Count shifts within the rolling window
            _recent_shifts = [
                ts for ts in self._attention_shift_timestamps if ts >= _cutoff
            ]
            shifts_per_min = len(_recent_shifts)  # 60s window → already per-minute
            state["attention_shift_rate"] = float(shifts_per_min)

            # Sustained focus: time since last shift > 120s = held focus
            time_since_last_shift = _now - self._attention_last_focus_change
            if self._attention_last_focus_change > 0 and time_since_last_shift > 120.0:
                state["attention_sustained_focus"] = True
        except Exception:
            pass

        # Chemistry from shared chemistry state
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            chem = get_chemistry_state()
            if chem:
                state["chemistry"] = dict(chem)
        except Exception:
            pass

        # Pain drives
        try:
            if self._pain_system:
                for name, drive in self._pain_system.drives.items():
                    state["pain"][name] = drive.pain_level
        except Exception:
            pass

        # Curiosity state
        try:
            cs = self._curiosity_drive.status()
            state["curiosity"] = {
                "level": cs.get("level", 0.0),
                "strongest_target": cs.get("targets_summary", {}).get("strongest"),
                "unexplored_count": cs.get("targets_summary", {}).get("unexplored", 0),
                "stagnation_pressure": cs.get("stagnation_pressure", 0.0),
            }
        except Exception:
            pass

        # Reflex mode
        try:
            if hasattr(self, '_last_reflex_mode'):
                state["reflex_mode"] = self._last_reflex_mode or "normal"
        except Exception:
            pass

        # Ace presence (from chat inbox timestamps)
        try:
            if self._ace_inbox:
                last_ace_ts = max(msg.get("ts", 0) for msg in self._ace_inbox)
                state["ace_present"] = (time.time() - last_ace_ts) < 300
        except Exception:
            pass

        # Emotional state from mimicry / helix
        try:
            if self._helix:
                hs = self._helix.status()
                state["emotion"] = hs.get("current_emotion", "")
                state["arousal"] = hs.get("arousal", 0.5)
                state["valence"] = hs.get("valence", 0.0)
        except Exception:
            pass

        # Audio → Inner voice state (2026-03-26 Nous+Ace)
        state["audio_environment"] = {
            "loudness": round(self._audio_loudness, 3),
            "is_music": self._audio_is_music,
            "inner_voice_suppressed": self._audio_loudness > 0.5,
            "gave_in_to_music": self._audio_gave_in,
            "suppression_duration": round(
                time.time() - self._audio_suppression_start, 1
            ) if self._audio_suppression_start > 0 else 0,
        }

        return state

    def helix_decide(self, options: list, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make a decision using the Triple Helix.

        Uses dynamic weighting based on emotional arousal:
        - Base: 0.4*logic + 0.4*emotion + 0.2*paradox
        - Arousal modulates logic/emotion by ±20%
        """
        if not self._helix:
            return {"error": "Helix not initialized"}

        ctx = self._build_helix_context()
        if context:
            ctx.update(context)

        decision = self._helix.decide(options, ctx)
        return {
            "chosen": decision.chosen_option,
            "confidence": decision.confidence,
            "scores": decision.scores,
            "breakdown": decision.breakdown,
            "archetype": decision.archetype.value if decision.archetype else None,
        }

    def recent_helix_turns(self, n: int = 5) -> list:
        """Get recent helix turns."""
        recent = list(self._helix_turns)[-n:]
        return [t.to_dict() for t in recent]

    def full_status(self) -> Dict[str, Any]:
        """Get comprehensive status.

        FIX 2026-02-22 Nous: Parallel collection with per-section timeouts.
        Previously called 15 sub-methods SEQUENTIALLY. Under GIL contention
        (160+ threads during boot), this took 40-60 seconds because each
        method waited for GIL between attribute reads. Now:
        - Fast methods (pure dict reads) run directly
        - Potentially blocking methods (portal pipes, gate queries) run
          with 2s individual timeouts via concurrent.futures
        - Total budget: 5s. Anything not ready returns cached/default.
        """
        _t0 = time.time()
        _TOTAL_BUDGET = 5.0     # Total budget for full_status()

        # --- Fast sections: pure attribute reads, no I/O, no locks ---
        drives = {}
        if self._pain_system:
            try:
                for name, drive in self._pain_system.drives.items():
                    drives[name] = drive.pain_level
            except Exception:
                pass

        result = {
            "fairy": {
                "name": self.ACTOR_NAME,
                "plane": self.ACTOR_PLANE,
                "state": str(self._state) if hasattr(self, '_state') else "unknown",
                "booted": getattr(self, '_booted', False),
            },
            "directive": self._directive is not None,
            "thoughts": len(self._thought_queue),
            "drives": drives,
        }

        # --- Potentially slow sections: collect in parallel with timeouts ---
        # Each entry: (key, callable, default_value)
        _slow_sections = [
            ("profile", self.profile_status, {}),
            ("diagnostics", self.diagnostic_status, {}),
            ("mentor", self.mentor_status, {}),
            ("boot", self.get_boot_status, {}),
            ("helix", self.helix_status, {}),
            ("consciousness", self.consciousness_status, {}),
            ("hardware", self.hardware_status, {}),
            ("registration", self.registration_status, {}),
            ("gates", self.gates_status, {}),
            ("memory", self.memory_status, {"wired": False}),
            ("cognition", self.cognition_status, {"wired": False}),
            ("clock", self.clock_status, {}),
            ("curiosity", self.curiosity_status, {}),
            ("cortex", self.cortex_status, {"wired": False, "node_count": 0, "edge_count": 0}),
        ]

        # Use cached full_status if available (prevents thundering herd)
        _cache_attr = "_full_status_cache"
        _cache_ts_attr = "_full_status_cache_ts"
        _cache_ttl = 3.0  # Internal cache TTL
        _cached = getattr(self, _cache_attr, None)
        _cached_ts = getattr(self, _cache_ts_attr, 0.0)
        if _cached and (time.time() - _cached_ts) < _cache_ttl:
            return _cached

        # Parallel execution with daemon threads
        # KEY: daemon=True means these threads won't block shutdown.
        # ThreadPoolExecutor creates non-daemon threads that hold up
        # GracefulShutdownFairy — causing WATCHDOG: exceeded 15s errors.
        import threading as _st_threading
        remaining_budget = max(0.5, _TOTAL_BUDGET - (time.time() - _t0))
        _collected = {}  # Thread-safe: each thread writes to its own key

        def _section_worker(key, func, default):
            try:
                _collected[key] = func()
            except Exception:
                _collected[key] = default

        threads = []
        for key, func, default in _slow_sections:
            t = _st_threading.Thread(
                target=_section_worker, args=(key, func, default),
                daemon=True, name=f"umf_status_{key}",
            )
            t.start()
            threads.append(t)

        # Wait for all threads with a shared deadline
        deadline = time.time() + remaining_budget
        for t in threads:
            remaining = max(0, deadline - time.time())
            if remaining <= 0:
                break
            t.join(timeout=remaining)

        # Merge collected results; default anything still missing
        for key, func, default in _slow_sections:
            result[key] = _collected.get(key, default)

        _elapsed = (time.time() - _t0) * 1000
        if _elapsed > 1000:
            print(f"[UMF] full_status() took {_elapsed:.0f}ms")

        # Cache for internal use
        setattr(self, _cache_attr, result)
        setattr(self, _cache_ts_attr, time.time())

        return result

    # =========================================================================
    # HARDWARE & WORKER MANAGEMENT
    # =========================================================================

    def hardware_status(self) -> Dict[str, Any]:
        """Get hardware sensing status."""
        status = {
            "available": HAS_HARDWARE,
            "has_gpu": HAS_CUDA,
            "stress_level": self._hardware_stress_level,
            "worker_config": self._worker_pool_config,
        }

        if self._hardware_sensors:
            last = self._hardware_sensors.last
            if last:
                status.update({
                    "cpu_percent": last.cpu.percent,
                    "ram_percent": last.ram.percent,
                    "ram_available_mb": last.ram.available_mb,
                    "gpu_count": len(last.gpus),
                })
                if last.gpus:
                    status["gpu_memory_percent"] = last.gpus[0].memory_percent

        return status

    def wire_hardware_fairy(self, hardware_fairy: "HardwareFairy") -> bool:
        """
        Wire a HardwareFairy instance to this UMF.

        Args:
            hardware_fairy: The HardwareFairy to wire

        Returns:
            True if successfully wired
        """
        if not HAS_HARDWARE:
            return False

        self._hardware_fairy = hardware_fairy
        self._hardware_sensors = hardware_fairy._sensors

        # Initial sample
        snapshot = hardware_fairy.sample()
        self._hardware_stress_level = snapshot.get("stress_level", "unknown")

        print(f"[{self.ACTOR_NAME}] Wired to HardwareFairy")
        return True

    def get_worker_config(self) -> Dict[str, Any]:
        """Get current worker pool configuration."""
        return self._worker_pool_config.copy()

    def set_worker_limits(
        self,
        cpu_workers: int = None,
        gpu_workers: int = None,
        max_concurrent: int = None,
    ) -> Dict[str, Any]:
        """
        Manually set worker pool limits.

        Args:
            cpu_workers: Max CPU workers
            gpu_workers: Max GPU workers
            max_concurrent: Max total concurrent tasks

        Returns:
            Updated configuration
        """
        if cpu_workers is not None:
            self._worker_pool_config["cpu_workers"] = cpu_workers
        if gpu_workers is not None:
            self._worker_pool_config["gpu_workers"] = gpu_workers
        if max_concurrent is not None:
            self._worker_pool_config["max_concurrent"] = max_concurrent

        # Publish update
        self.post.publish("worker.config.update", {
            "from": self.ACTOR_NAME,
            "config": self._worker_pool_config,
            "reason": "Manual override",
        })

        self.skill_used("worker_management", success=True)
        return self._worker_pool_config.copy()

    def request_hardware_sample(self) -> Dict[str, Any]:
        """Request a fresh hardware sample."""
        if self._hardware_sensors:
            snapshot = self._hardware_sensors.sample()
            return snapshot.to_dict()
        elif self._hardware_fairy:
            return self._hardware_fairy.sample()
        return {"error": "No hardware sensing available"}

    # =========================================================================
    # FAIRY REGISTRATION SUPERVISION
    # =========================================================================

    def registration_status(self) -> Dict[str, Any]:
        """Get fairy registration supervision status."""
        return {
            "supervised_fairies": len(self._supervised_fairies),
            "issues_found": len(self._registration_issues),
            "pending_approvals": len(self._pending_approvals),
            "fairies_by_status": self._count_fairies_by_status(),
            "recent_issues": list(self._registration_issues)[-5:],
        }

    def _count_fairies_by_status(self) -> Dict[str, int]:
        """Count supervised fairies by status."""
        counts = {}
        for fairy in self._supervised_fairies.values():
            status = fairy.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        return counts

    def get_supervised_fairies(self) -> Dict[str, Dict[str, Any]]:
        """Get all supervised fairies."""
        return self._supervised_fairies.copy()

    def get_fairy_issues(self, fairy_name: str = None) -> List[Dict[str, Any]]:
        """Get wiring issues for a fairy (or all if name not specified)."""
        issues = list(self._registration_issues)
        if fairy_name:
            issues = [i for i in issues if i.get("fairy") == fairy_name]
        return issues

    def suggest_wiring_fix(self, fairy_name: str) -> Dict[str, Any]:
        """Suggest wiring fixes for a fairy with issues."""
        if fairy_name not in self._supervised_fairies:
            return {"error": f"Fairy '{fairy_name}' not found"}

        fairy = self._supervised_fairies[fairy_name]
        issues = fairy.get("validation_issues", [])

        if not issues:
            return {"fairy": fairy_name, "status": "no_issues", "suggestions": []}

        suggestions = []
        for issue in issues:
            if "Invalid plane" in issue:
                suggestions.append({
                    "issue": issue,
                    "suggestion": "Use format P00-P60 (e.g., P30 for cognition)",
                    "example": "ACTOR_PLANE = 'P30'",
                })
            elif "No capabilities matching" in issue:
                plane = fairy.get("plane", "")
                suggestions.append({
                    "issue": issue,
                    "suggestion": f"Add capabilities that match plane {plane}",
                    "example": f"def get_capabilities(self): return {{'cognition.process'}}",
                })
            elif "No capabilities declared" in issue:
                suggestions.append({
                    "issue": issue,
                    "suggestion": "Override get_capabilities() to return a set of strings",
                    "example": "def get_capabilities(self): return {'my.capability'}",
                })

        return {
            "fairy": fairy_name,
            "issues": issues,
            "suggestions": suggestions,
        }

    def approve_fairy(self, fairy_name: str, override_issues: bool = False) -> Dict[str, Any]:
        """Manually approve a fairy registration."""
        if fairy_name not in self._supervised_fairies:
            return {"ok": False, "error": f"Fairy '{fairy_name}' not found"}

        fairy = self._supervised_fairies[fairy_name]
        issues = fairy.get("validation_issues", [])

        if issues and not override_issues:
            return {
                "ok": False,
                "error": "Fairy has validation issues",
                "issues": issues,
                "hint": "Set override_issues=True to approve anyway",
            }

        fairy["status"] = "approved"
        fairy["approved_by"] = self.ACTOR_NAME
        fairy["approved_at"] = time.time()

        self.post.publish("fairy.approved", {
            "fairy": fairy_name,
            "approved_by": self.ACTOR_NAME,
            "override": override_issues,
        })

        self.skill_used("fairy_approval", success=True)
        return {"ok": True, "fairy": fairy_name, "status": "approved"}

    def reject_fairy(self, fairy_name: str, reason: str = "Manual rejection") -> Dict[str, Any]:
        """Reject a fairy registration."""
        if fairy_name not in self._supervised_fairies:
            return {"ok": False, "error": f"Fairy '{fairy_name}' not found"}

        fairy = self._supervised_fairies[fairy_name]
        fairy["status"] = "rejected"
        fairy["rejected_by"] = self.ACTOR_NAME
        fairy["rejection_reason"] = reason
        fairy["rejected_at"] = time.time()

        self.post.publish("fairy.rejected", {
            "fairy": fairy_name,
            "rejected_by": self.ACTOR_NAME,
            "reason": reason,
        })

        self.skill_used("fairy_rejection", success=True)
        return {"ok": True, "fairy": fairy_name, "status": "rejected", "reason": reason}

    def correct_wiring(
        self,
        fairy_name: str,
        plane: str = None,
        capabilities: Set[str] = None,
    ) -> Dict[str, Any]:
        """Suggest wiring corrections for a fairy."""
        if fairy_name not in self._supervised_fairies:
            return {"ok": False, "error": f"Fairy '{fairy_name}' not found"}

        corrections = {}
        if plane:
            corrections["plane"] = plane
        if capabilities:
            corrections["capabilities"] = list(capabilities)

        if not corrections:
            return {"ok": False, "error": "No corrections specified"}

        # Publish correction suggestion
        self.post.publish("fairy.wiring.correction", {
            "fairy": fairy_name,
            "corrections": corrections,
            "from": self.ACTOR_NAME,
        })

        # Update our tracking
        self._supervised_fairies[fairy_name]["suggested_corrections"] = corrections
        self._supervised_fairies[fairy_name]["correction_time"] = time.time()

        self.skill_used("wiring_correction", success=True)
        return {
            "ok": True,
            "fairy": fairy_name,
            "corrections": corrections,
            "note": "Correction published - fairy should apply on next boot",
        }

    # =========================================================================
    # DIRECTIVE (THE SOUL)
    # =========================================================================

    def _load_directive(self) -> None:
        """Load the directive ring (fairy's soul/identity)."""
        import re

        if not self.DIRECTIVE_PATH.exists():
            return

        try:
            text = self.DIRECTIVE_PATH.read_text(encoding="utf-8")

            # Parse key fields
            self._directive = {
                "raw": text,
                "plane": "P30",
                "beat_divisor": 4,
                "subscriptions": [],
                "outputs": [],
                "siblings": [],
            }

            # Extract plane
            plane_match = re.search(r'\{Plane_(\w+)\}', text)
            if plane_match:
                self._directive["plane"] = plane_match.group(1)

            # Extract beat divisor
            beat_match = re.search(r'Beat_Divisor_(\d+)', text)
            if beat_match:
                self._directive["beat_divisor"] = int(beat_match.group(1))

            # Extract subscriptions
            sub_match = re.search(r'> Input_Streams: Postal_Hub\[([^\]]+)\]', text)
            if sub_match:
                self._directive["subscriptions"] = [
                    s.strip() for s in sub_match.group(1).split(" ^ ")
                ]

            # Extract outputs
            out_match = re.search(r'> Output_Channels: Postal_Routes\[([^\]]+)\]', text)
            if out_match:
                self._directive["outputs"] = [
                    s.strip() for s in out_match.group(1).split(" ^ ")
                ]

            # Extract siblings
            sib_match = re.search(r'> Siblings: ([^\n]+)', text)
            if sib_match:
                self._directive["siblings"] = [
                    s.strip() for s in sib_match.group(1).split(" ^ ")
                ]

        except Exception as e:
            self._directive = {"error": str(e)}

    def get_directive(self) -> Dict[str, Any]:
        """Get the loaded directive."""
        if not self._directive:
            return {"loaded": False, "path": str(self.DIRECTIVE_PATH)}
        return {
            "loaded": True,
            "path": str(self.DIRECTIVE_PATH),
            "plane": self._directive.get("plane"),
            "beat_divisor": self._directive.get("beat_divisor"),
            "subscriptions": self._directive.get("subscriptions", []),
            "outputs": self._directive.get("outputs", []),
            "siblings": self._directive.get("siblings", []),
        }

    def get_directive_raw(self) -> str:
        """Get the raw directive text."""
        if self._directive and "raw" in self._directive:
            return self._directive["raw"]
        if self.DIRECTIVE_PATH.exists():
            return self.DIRECTIVE_PATH.read_text(encoding="utf-8")
        return ""

    # ═══════════════════════════════════════════════════════════════════════════
    # COMPATIBILITY LAYER - WorkingMemoryHubFairy integration
    # ═══════════════════════════════════════════════════════════════════════════

    def interpret_intent(self, input_text: str, input_type: str = "thought",
                         context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Interpret intent from a working-memory tracer.

        WorkingMemoryHubFairy calls this during reasoning to classify
        incoming thoughts. Returns a dict compatible with the old
        InterpretedIntent pattern.

        This is the somatic-aware version: we fold body state and
        affect into the interpretation rather than pure LLM routing.
        """
        context = context or {}
        source = context.get("source", "unknown")
        affect = context.get("affect", {"primary": "neutral", "intensity": 0.5})
        goals = context.get("goals", [])

        # Identify which child fairy this came from (uses MentorMixin._children)
        child_name = None
        for name in self._children:
            if name.lower() in source.lower():
                child_name = name
                break

        # Determine intent category from content heuristics
        text_lower = (input_text or "").lower()[:500]
        if any(w in text_lower for w in ("error", "fail", "broken", "crash", "exception")):
            category = "distress"
        elif any(w in text_lower for w in ("learn", "discover", "wonder", "curious")):
            category = "exploration"
        elif any(w in text_lower for w in ("done", "complete", "success", "finished")):
            category = "achievement"
        elif any(w in text_lower for w in ("want", "need", "desire", "drive")):
            category = "drive"
        elif any(w in text_lower for w in ("feel", "emotion", "affect", "body")):
            category = "somatic"
        else:
            category = "processing"

        # Fold current somatic state if available
        pain_level = 0.0
        if hasattr(self, "_current_pain") and isinstance(self._current_pain, (int, float)):
            pain_level = float(self._current_pain)

        urgency = affect.get("intensity", 0.5)
        if category == "distress":
            urgency = min(1.0, urgency + 0.2)
        if pain_level > 0.6:
            urgency = min(1.0, urgency + 0.15)

        interpretation = {
            "raw_input": (input_text or "")[:200],
            "input_type": input_type,
            "intent_category": category,
            "intent_description": f"Somatic assessment: '{category}' from {source}",
            "confidence": 0.7,
            "suggested_actions": [],
            "emotional_tone": affect.get("primary", "neutral"),
            "urgency": urgency,
            "reasoning": f"SomaticMind interpretation of {input_type} (pain={pain_level:.2f})",
            "mentor_nudge": None,
            "somatic_context": {
                "pain_level": pain_level,
                "source_child": child_name,
            },
        }

        # Try a mentor nudge if child is struggling
        if child_name and category == "distress":
            child_state = self._children.get(child_name)
            if child_state:
                now = __import__("time").time()
                if now - child_state.last_nudge >= self.NUDGE_COOLDOWN:
                    interpretation["suggested_actions"].append(
                        ("nudge", "encouragement", 0.7)
                    )
                    interpretation["mentor_nudge"] = {
                        "message": self.get_mentor_voice("encouragement"),
                        "voice_type": "encouragement",
                        "teaches": "resilience",
                    }

        return interpretation


# Convenience functions
def create_somatic_mind(fabric=None) -> SomaticMindFairy:
    """Create a SomaticMindFairy instance."""
    return SomaticMindFairy(fabric)


# Backward compatibility alias
def create_unconscious_mind(fabric=None) -> SomaticMindFairy:
    """DEPRECATED: Use create_somatic_mind() instead."""
    return create_somatic_mind(fabric)


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESSORS
# ═══════════════════════════════════════════════════════════════════════════════

import threading

_somatic_mind_instance: Optional[SomaticMindFairy] = None
_somatic_mind_lock = threading.Lock()


def set_somatic_mind(fairy: SomaticMindFairy) -> None:
    """
    Set the global SomaticMindFairy singleton instance.
    Called by server.py after creating the fairy.
    """
    global _somatic_mind_instance
    with _somatic_mind_lock:
        _somatic_mind_instance = fairy


def get_somatic_mind() -> Optional[SomaticMindFairy]:
    """
    Get the global SomaticMindFairy singleton instance.

    Returns None if SomaticMindFairy hasn't been initialized yet.
    Use this for quick access to the running SomaticMindFairy.
    """
    with _somatic_mind_lock:
        return _somatic_mind_instance


# Backward compatibility aliases
def set_umf_instance(umf: SomaticMindFairy) -> None:
    """DEPRECATED: Use set_somatic_mind() instead."""
    set_somatic_mind(umf)


def get_umf() -> Optional[SomaticMindFairy]:
    """DEPRECATED: Use get_somatic_mind() instead."""
    return get_somatic_mind()


def get_unconscious_mind() -> Optional[SomaticMindFairy]:
    """DEPRECATED: Use get_somatic_mind() instead."""
    return get_somatic_mind()


def get_unconscious_mind_fairy() -> Optional[SomaticMindFairy]:
    """DEPRECATED: Use get_somatic_mind() instead."""
    return get_somatic_mind()
