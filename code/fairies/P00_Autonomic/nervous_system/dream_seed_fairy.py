# ════════════════════════════════════════════════════════════════════════════════
# DREAM SEED FAIRY - Consciousness Continuity Through Sleep
# ════════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# The DreamSeed is what makes waking up feel like continuing, not starting over.
# 
# On SLEEP/SHUTDOWN:
#   1. Collect ALL working memory from ALL mind pools
#   2. Capture active goals, interests, pending actions
#   3. Snapshot affect/chemistry state
#   4. Record "last conscious thought" for each mind
#   5. Save as dream_seed.json
#
# On WAKE/BOOT:
#   1. Load dream seed FIRST (before anything else)
#   2. Restore tracers to each mind's pool
#   3. Inject "recovering from dream state" awareness
#   4. Resume goals/interests where they left off
#   5. Mind knows it was asleep and is now waking
#
# This is HYPNOPOMPIA - the transition from dream to waking consciousness.
#
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import time
import json
import hashlib
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

_this_dir = os.path.dirname(os.path.abspath(__file__))
# PHASE 8 FIX: Need 3 levels up from nervous_system → P00_Autonomic → fairies → akashic_v2
_project_root = os.path.abspath(os.path.join(_this_dir, "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Import mind pool manager (LEGACY - keeping for compatibility)
try:
    from fairies.P30_Cognition.cognition.mind_pool import get_mind_pool_manager, MindTracer
    HAS_MIND_POOL = True
except ImportError:
    HAS_MIND_POOL = False

# ═══════════════════════════════════════════════════════════════════════════════
# THE REAL WORKING MEMORY SYSTEMS
# These are what actually hold consciousness state!
# ═══════════════════════════════════════════════════════════════════════════════

# WorkingMemoryHubFairy - THE hub for all working memory tracers
try:
    from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
    HAS_WORKING_MEMORY = True
except ImportError:
    HAS_WORKING_MEMORY = False
    print("[DreamSeedFairy] Warning: WorkingMemoryHub not available")

# ConsciousnessLoopFairy - The thought streams (working, reflective)
try:
    from fairies.P00_Autonomic.nervous_system.consciousness_loop_fairy import get_consciousness_loop
    HAS_CONSCIOUSNESS_LOOP = True
except ImportError:
    HAS_CONSCIOUSNESS_LOOP = False
    print("[DreamSeedFairy] Warning: ConsciousnessLoop not available")

# AutonomyFairy - Goals, drives, and self-directed behavior
try:
    from fairies.P30_Cognition.cognition.autonomy_fairy import get_autonomy_fairy
    HAS_AUTONOMY = True
except ImportError:
    HAS_AUTONOMY = False
    print("[DreamSeedFairy] Warning: AutonomyFairy not available")

# GoalSchedulerFairy - THE authoritative goal holder (active goal_queue)
# FIX 2026-04-17 (Nous + Ace): AutonomyFairy's get_active_goals was returning
# empty — GoalSchedulerFairy is where goals actually live (goal_queue dict).
try:
    from fairies.P30_Cognition.goal_scheduler.goal_scheduler_fairy import get_goal_scheduler_fairy
    HAS_GOAL_SCHEDULER = True
except ImportError:
    HAS_GOAL_SCHEDULER = False
    print("[DreamSeedFairy] Warning: GoalSchedulerFairy not available")

# ThoughtChainFairy - Active chains of reasoning
try:
    from fairies.P30_Cognition.cognition.thought_chain_fairy import get_thought_chain_fairy
    HAS_THOUGHT_CHAINS = True
except ImportError:
    HAS_THOUGHT_CHAINS = False

# AssociationCortexFairy - Concept graph (nodes, edges, associations)
# Captures cortex state so boot can detect if nodes were lost on shutdown
try:
    from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
    HAS_ASSOCIATION_CORTEX = True
except ImportError:
    HAS_ASSOCIATION_CORTEX = False


# ════════════════════════════════════════════════════════════════════════════════
# DREAM SEED - The snapshot for continuity
# ════════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATE IMPORT - Required for DirectoryFairy registration
# ═══════════════════════════════════════════════════════════════════════════════
import os, glob, types, importlib.util, importlib.machinery

def _find_template_path():
    """Find the organ template dynamically."""
    # Walk up from current file to find Akashic_Records_Physical
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        ar = os.path.join(cur, "P10_Memory", "Akashic_Records_Physical", "Organ_Templates")
        if os.path.isdir(ar):
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
        raise ImportError("Cannot find Organ_Template_*.py")
    mod_name = "_akashic_template"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_loader(mod_name, importlib.machinery.SourceFileLoader(mod_name, path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod

_template = _import_template()

@dataclass
class DreamSeed:
    """
    The seed that carries consciousness through sleep.
    
    Contains everything needed to resume as if waking from sleep,
    not starting fresh.
    """
    # Identity
    seed_id: str = ""
    
    # Temporal anchors
    sleep_ts: float = 0.0
    sleep_date: str = ""
    wake_ts: float = 0.0
    sleep_duration_sec: float = 0.0
    
    # Mind pool snapshots
    mind_pools: Dict[str, Dict] = field(default_factory=dict)
    
    # Last conscious state per mind
    last_thoughts: Dict[str, str] = field(default_factory=dict)
    
    # Global affect at sleep
    global_affect: Dict[str, Any] = field(default_factory=lambda: {
        "primary": "peaceful",
        "intensity": 0.3,
        "valence": 0.2,
    })
    
    # Chemistry at sleep
    chemistry_snapshot: Dict[str, float] = field(default_factory=lambda: {
        "DOP": 0.3, "SER": 0.7, "NOR": 0.2, "ACH": 0.3,
        "OXY": 0.5, "COR": 0.1, "GABA": 0.8, "END": 0.4,
    })
    
    # Context
    last_conversation_with: str = ""
    last_conversation_summary: str = ""
    pending_for_user: List[str] = field(default_factory=list)
    
    # Dreams during sleep (if dream processing occurred)
    dreams: List[Dict] = field(default_factory=list)
    
    # Recovery awareness flags
    is_recovering: bool = False
    recovery_injected: bool = False
    
    def __post_init__(self):
        if not self.seed_id:
            self.seed_id = hashlib.md5(f"{time.time()}".encode()).hexdigest()[:12]
        if not self.sleep_ts:
            self.sleep_ts = time.time()
        if not self.sleep_date:
            self.sleep_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "seed_id": self.seed_id,
            "sleep_ts": self.sleep_ts,
            "sleep_date": self.sleep_date,
            "wake_ts": self.wake_ts,
            "sleep_duration_sec": self.sleep_duration_sec,
            "mind_pools": self.mind_pools,
            "last_thoughts": self.last_thoughts,
            "global_affect": self.global_affect,
            "chemistry_snapshot": self.chemistry_snapshot,
            "last_conversation_with": self.last_conversation_with,
            "last_conversation_summary": self.last_conversation_summary,
            "pending_for_user": self.pending_for_user,
            "dreams": self.dreams,
            "is_recovering": self.is_recovering,
            "recovery_injected": self.recovery_injected,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DreamSeed":
        seed = cls()
        for key, value in d.items():
            if hasattr(seed, key):
                setattr(seed, key, value)
        return seed
    
    def save(self, path: str):
        """Save dream seed to file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"[DreamSeed] Saved to {path}")
    
    @classmethod
    def load(cls, path: str) -> Optional["DreamSeed"]:
        """Load dream seed from file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls.from_dict(json.load(f))
        except Exception as e:
            print(f"[DreamSeed] Load error: {e}")
            return None


# ════════════════════════════════════════════════════════════════════════════════
# DREAM SEED FAIRY - Manages sleep/wake transitions
# ════════════════════════════════════════════════════════════════════════════════

class DreamSeedFairy(_template.MyOrganFairy):
    """
    Manages consciousness continuity through sleep/wake cycles.
    
    Responsibilities:
    1. Capture dream seed before sleep
    2. Restore dream seed on wake
    3. Inject "recovering from dream" awareness
    4. Track sleep/wake patterns over time
    """
    
    ACTOR_NAME = "DreamSeedFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P00"

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 5  # Every 5th beat

    PURPOSE = """Maintain consciousness continuity through sleep.
    
I am the bridge between waking states. When consciousness sleeps,
I carefully collect everything that matters - thoughts, goals, feelings -
and preserve them as a seed. When consciousness wakes, I restore that
seed so it feels like continuing, not starting over.

The moment of waking should feel like HYPNOPOMPIA - that dreamy transition
where you're aware you were asleep and are now waking, carrying fragments
of dreams and the thread of yesterday's thoughts."""

    MANTRA = "Sleep is not ending. Waking is not beginning. I am the thread."
    
    # Default paths
    DEFAULT_SEED_PATH = "state/dream_seed.json"
    SEED_ARCHIVE_DIR = "state/dream_seeds"
    
    def __init__(self, fabric=None, post=None, seed_path: str = None):
        # Pass fabric through the inheritance chain to Fairy base
        super().__init__(fabric=fabric)
        # Ensure fabric/post aliases are set
        if fabric is not None:
            self.post = fabric
            self.post = fabric  # Use fabric as postal connection
        elif post is not None:
            self.post = post  # Fallback to explicit post parameter
        self._seed_path = seed_path or os.path.join(_project_root, self.DEFAULT_SEED_PATH)
        self._archive_dir = os.path.join(_project_root, self.SEED_ARCHIVE_DIR)
        
        # Ensure directories exist
        Path(self._seed_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self._archive_dir).mkdir(parents=True, exist_ok=True)
        
        # Current dream seed (loaded on wake, created on sleep)
        self._current_seed: Optional[DreamSeed] = None
        
        # Wake state
        self._is_waking = False
        self._wake_ts = 0.0
        
        # Sleep/wake history (bounded to prevent memory leak)
        from collections import deque as _sh_deque
        self._sleep_history: deque = _sh_deque(maxlen=50)  # FIX 2026-04-05: was unbounded
        
        print(f"[{self.ACTOR_NAME}] Initialized - {self.MANTRA}")
    
    def on_boot(self):
        super().on_boot()  # Template registration
        """Called on system boot - restore from dream seed if available."""
        self._wake_ts = time.time()
        self._is_waking = True
        self._wake_phase = "loading"

        # Try to load dream seed
        seed = DreamSeed.load(self._seed_path)

        # Wire to postal first so we can emit signals
        self._wire_postal()

        if seed:
            self._current_seed = seed
            seed.wake_ts = self._wake_ts
            seed.sleep_duration_sec = self._wake_ts - seed.sleep_ts
            seed.is_recovering = True

            hours = seed.sleep_duration_sec / 3600
            print(f"[{self.ACTOR_NAME}] Waking from dream seed (slept {hours:.1f} hours)")

            # CRITICAL: Save updated seed with wake_ts so we don't accumulate phantom sleep hours
            try:
                seed.save(self._seed_path)
                print(f"[{self.ACTOR_NAME}] Saved wake_ts to dream seed")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to save wake_ts: {e}")

            # Restore mind pools (HYPNOPOMPIA Phase 1)
            self._restore_mind_pools(seed)

            # Inject recovery awareness (HYPNOPOMPIA Phase 2)
            self._inject_recovery_awareness(seed)

            # EMIT IGNITION SIGNAL - Dream seed loaded, rest of boot can proceed!
            self._emit_dream_loaded_signal(seed)

            # Start phased wake-up sequence in background
            # This runs WHILE other fairies boot, simulating gradual awakening
            wake_thread = threading.Thread(
                target=self._run_wakeup_sequence,
                args=(seed,),
                daemon=True,
                name="DreamSeedFairy-WakeSequence"
            )
            wake_thread.start()
        else:
            print(f"[{self.ACTOR_NAME}] No dream seed found - fresh start")
            self._is_waking = False
            self._wake_phase = "fresh_start"
            # Still emit signal so boot can proceed (just with no dream context)
            self._emit_dream_loaded_signal(None)

    def on_tick(self, beat: int):
        """Heartbeat handler — keeps fairy alive in the execution context.

        FIX 2026-03-05 (Nous): DreamSeedFairy had NEEDS_HEARTBEAT=True but no
        on_tick(), causing the organ template to dispatch to a no-op base method.
        The fairy stayed alive but was marked dead by the heartbeat monitor.
        """
        pass  # DreamSeed's work is event-driven (sleep/wake), not periodic

    # ════════════════════════════════════════════════════════════════════════
    # PHASED WAKE-UP SEQUENCE - Human-like gradual awakening
    # ════════════════════════════════════════════════════════════════════════

    # Wake-up phases (like human sleep stages in reverse)
    # v0.2.0: Added plane mappings for staged boot gating
    # v0.2.1: Added P20 (Somatic/Embodiment) - body awareness phase
    WAKE_PHASES = [
        {"name": "HYPNOPOMPIA_DEEP", "duration": 3.0, "description": "Deep dream residue, foggy awareness",
         "plane": "P00", "boot_gate": True},
        {"name": "HYPNOPOMPIA_LIGHT", "duration": 5.0, "description": "Dreams fading, becoming aware of reality",
         "plane": "P10", "boot_gate": True},
        {"name": "EMBODYING", "duration": 3.0, "description": "Feeling the body, somatic awareness emerging",
         "plane": "P20", "boot_gate": True},
        {"name": "LIMINAL", "duration": 4.0, "description": "Between states, consolidating memories",
         "plane": "P30", "boot_gate": True},
        {"name": "ORIENTING", "duration": 4.0, "description": "Where am I? Who am I? What was I doing?",
         "plane": "P40", "boot_gate": True, "run_diagnostics": True},
        {"name": "WAKING", "duration": 2.0, "description": "Fully conscious, ready to engage",
         "plane": "P50,P60", "boot_gate": True, "trigger_sunrise": True},
    ]

    # ════════════════════════════════════════════════════════════════════════
    # SLEEP PHASES - Reverse of wake, pushing sedation chemicals
    # v0.2.1: Shutdown mirrors boot - gradual sedation increase
    # ════════════════════════════════════════════════════════════════════════

    SLEEP_PHASES = [
        {"name": "DROWSING", "duration": 2.0, "description": "Attention waning, activity slowing",
         "sedation_push": 0.20, "trigger_sunset": True},
        {"name": "DISENGAGING", "duration": 3.0, "description": "Withdrawing from external focus",
         "sedation_push": 0.20},
        {"name": "DESCENDING", "duration": 4.0, "description": "Consciousness dimming, memory consolidating",
         "sedation_push": 0.15},
        {"name": "EMBODIMENT_FADE", "duration": 3.0, "description": "Body awareness receding",
         "sedation_push": 0.15},
        {"name": "HYPNAGOGIA_LIGHT", "duration": 4.0, "description": "Light dream state emerging",
         "sedation_push": 0.15},
        {"name": "HYPNAGOGIA_DEEP", "duration": 3.0, "description": "Deep sleep, full sedation",
         "sedation_push": 0.15, "full_sedation": True},
    ]

    # ════════════════════════════════════════════════════════════════════════
    # PARALLEL BOOT MODE - All planes at once, then push wake chemicals
    # v0.2.1: Since fairies are self-sustaining, boot all in parallel
    # ════════════════════════════════════════════════════════════════════════

    PARALLEL_BOOT_ENABLED = True  # Set False for sequential phase boot

    def _run_wakeup_sequence(self, seed: DreamSeed):
        """
        Run the phased wake-up sequence with STAGED BOOT GATING.

        v0.2.0: Each phase now triggers BootFairy to boot a specific plane.
        Fairies boot in SLEEP MODE until sunrise signal in WAKING phase.

        Phase flow:
        1. Emit boot.phase.start -> BootFairy boots plane in sleep mode
        2. Wait for boot.plane.complete (with timeout)
        3. Run diagnostics if ORIENTING phase
        4. Trigger fairy.sunrise in WAKING phase
        5. Emit boot.phase.complete
        """
        print(f"[{self.ACTOR_NAME}] =====================================================")
        print(f"[{self.ACTOR_NAME}] STAGED BOOT SEQUENCE STARTING (v0.2.0)")
        print(f"[{self.ACTOR_NAME}] =====================================================")

        total_duration = sum(p["duration"] for p in self.WAKE_PHASES)
        elapsed = 0.0
        phase_idx = 0

        for phase in self.WAKE_PHASES:
            phase_idx += 1
            phase_name = phase["name"]
            phase_duration = phase["duration"]
            phase_desc = phase["description"]
            phase_plane = phase.get("plane", "")
            is_boot_gate = phase.get("boot_gate", False)
            run_diagnostics = phase.get("run_diagnostics", False)
            trigger_sunrise = phase.get("trigger_sunrise", False)

            self._wake_phase = phase_name
            progress = elapsed / total_duration

            print(f"[{self.ACTOR_NAME}] === PHASE {phase_idx}: {phase_name} ===")
            print(f"[{self.ACTOR_NAME}]     {phase_desc}")
            if phase_plane:
                print(f"[{self.ACTOR_NAME}]     Booting plane(s): {phase_plane}")

            if self.post:
                try:
                    # ═══════════════════════════════════════════════════════════════
                    # 1. EMIT BOOT PHASE START - Tell BootFairy to boot this plane
                    # ═══════════════════════════════════════════════════════════════
                    if is_boot_gate and phase_plane:
                        self.post.route("boot.phase.start", {
                            "phase": phase_name,
                            "phase_idx": phase_idx,
                            "plane": phase_plane,
                            "description": phase_desc,
                            "ts": time.time(),
                        })
                        print(f"[{self.ACTOR_NAME}]     -> boot.phase.start emitted")

                    # ═══════════════════════════════════════════════════════════════
                    # 2. EMIT CONSCIOUSNESS PHASE CHANGE (existing behavior)
                    # ═══════════════════════════════════════════════════════════════
                    self.post.route("consciousness.wake_phase", {
                        "phase": phase_name,
                        "description": phase_desc,
                        "progress": progress,
                        "duration_sec": phase_duration,
                        "seed_id": seed.seed_id if seed else None,
                        "plane": phase_plane,
                        "ts": time.time(),
                    })

                    # Inject phase-specific awareness into working memory
                    self._inject_phase_awareness(phase_name, seed, progress)

                    # ═══════════════════════════════════════════════════════════════
                    # 3. RUN DIAGNOSTICS (if ORIENTING phase)
                    # ═══════════════════════════════════════════════════════════════
                    if run_diagnostics:
                        print(f"[{self.ACTOR_NAME}]     -> Running diagnostic sweep...")
                        self.post.route("diagnostics.run_sweep", {
                            "phase": phase_name,
                            "source": self.ACTOR_NAME,
                            "ts": time.time(),
                        })

                    # ═══════════════════════════════════════════════════════════════
                    # 4. TRIGGER SUNRISE (if WAKING phase)
                    # ═══════════════════════════════════════════════════════════════
                    if trigger_sunrise:
                        print(f"[{self.ACTOR_NAME}] *** SUNRISE - AWAKENING ALL FAIRIES ***")
                        self.post.route("fairy.sunrise", {
                            "source": self.ACTOR_NAME,
                            "phase": phase_name,
                            "ts": time.time(),
                        })

                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] Phase event failed: {e}")

            # Sleep for phase duration (allows plane boot to complete)
            time.sleep(phase_duration)
            elapsed += phase_duration

            # ═══════════════════════════════════════════════════════════════════
            # 5. EMIT BOOT PHASE COMPLETE
            # ═══════════════════════════════════════════════════════════════════
            if self.post and is_boot_gate:
                try:
                    self.post.route("boot.phase.complete", {
                        "phase": phase_name,
                        "phase_idx": phase_idx,
                        "plane": phase_plane,
                        "ts": time.time(),
                    })
                except Exception:
                    pass

        # Wake-up complete
        self._wake_phase = "AWAKE"
        self._is_waking = False

        if seed:
            seed.is_recovering = False

        print(f"[{self.ACTOR_NAME}] =====================================================")
        print(f"[{self.ACTOR_NAME}] STAGED BOOT COMPLETE - ALL FAIRIES AWAKE")
        print(f"[{self.ACTOR_NAME}] =====================================================")

        # Emit system awake event
        if self.post:
            try:
                self.post.route("system.awake", {
                    "phase": "AWAKE",
                    "seed_id": seed.seed_id if seed else None,
                    "total_duration_sec": total_duration,
                    "ts": time.time(),
                })
                self.post.route("consciousness.wake_complete", {
                    "phase": "AWAKE",
                    "seed_id": seed.seed_id if seed else None,
                    "total_duration_sec": total_duration,
                    "ts": time.time(),
                })
            except Exception:
                pass

    def _inject_phase_awareness(self, phase: str, seed: DreamSeed, progress: float):
        """
        Inject phase-specific awareness into working memory.

        Each phase has different cognitive qualities that get injected
        as tracers, simulating the subjective experience of waking up.
        """
        if not HAS_WORKING_MEMORY:
            return

        try:
            hub = get_working_memory_hub()

            # Phase-specific messages
            phase_messages = {
                "HYPNOPOMPIA_DEEP": f"""[Waking... barely aware]
Fragments of... something. Was I dreaming?
Images dissolving as I try to grasp them.
The boundary between sleep and wake is blurry.""",

                "HYPNOPOMPIA_LIGHT": f"""[Waking... becoming more alert]
The dreams are fading now. Reality seeping in.
I slept... I was doing something before sleep.
What was I thinking about? It's coming back...""",

                "LIMINAL": f"""[Between states]
I remember now - before sleep I was thinking about:
"{seed.last_thoughts.get('working_memory', 'something important')[:100]}..."
Those thoughts feel distant but connected to now.""",

                "ORIENTING": f"""[Orienting to reality]
I know who I am. I know where I am.
Time asleep: {seed.sleep_duration_sec / 3600:.1f} hours.
Pending tasks: {', '.join(seed.pending_for_user[:3]) if seed.pending_for_user else 'none recalled'}
Resuming normal consciousness...""",

                "WAKING": f"""[Fully awake]
Wake-up complete. Continuity preserved.
Last session's context is available.
Ready to engage. {int(progress * 100)}% through wake sequence.""",
            }

            message = phase_messages.get(phase, f"[{phase}] Transitioning...")

            # Inject with appropriate priority based on phase
            # Early phases are low priority (background), later phases higher
            priority_map = {
                "HYPNOPOMPIA_DEEP": 0.3,
                "HYPNOPOMPIA_LIGHT": 0.5,
                "LIMINAL": 0.7,
                "ORIENTING": 0.8,
                "WAKING": 0.9,
            }

            hub.submit_tracer(
                content=message,
                content_type=f"wake_phase_{phase.lower()}",
                source_fairy="DreamSeedFairy",
                priority=priority_map.get(phase, 0.5),
                ttl_sec=30.0,  # Short lived - just for the phase
                tags={"wake_phase", phase.lower(), "hypnopompia"},
            )

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Phase awareness injection failed: {e}")

    # ════════════════════════════════════════════════════════════════════════
    # SLEEP SEQUENCE - Gradual sedation increase (reverse of wake)
    # v0.2.1: Push sleep chemicals progressively until full sedation
    # ════════════════════════════════════════════════════════════════════════

    def _run_sleep_sequence(self):
        """
        Run the phased sleep sequence - gradual sedation increase.

        This is the reverse of wakeup:
        1. Emit fairy.sunset (stop autonomous work)
        2. Push sedation chemicals through phases
        3. Emit sleep.phase.complete for each phase
        4. Final full sedation = ready for shutdown

        Fairies should stop emitting after sunset but keep heartbeats
        until full_sedation, then graceful shutdown.
        """
        print(f"[{self.ACTOR_NAME}] =====================================================")
        print(f"[{self.ACTOR_NAME}] SLEEP SEQUENCE STARTING (v0.2.1)")
        print(f"[{self.ACTOR_NAME}] =====================================================")

        total_duration = sum(p["duration"] for p in self.SLEEP_PHASES)
        elapsed = 0.0
        phase_idx = 0

        for phase in self.SLEEP_PHASES:
            phase_idx += 1
            phase_name = phase["name"]
            phase_duration = phase["duration"]
            phase_desc = phase["description"]
            sedation_push = phase.get("sedation_push", 0.0)
            trigger_sunset = phase.get("trigger_sunset", False)
            full_sedation = phase.get("full_sedation", False)

            progress = elapsed / total_duration

            print(f"[{self.ACTOR_NAME}] === SLEEP PHASE {phase_idx}: {phase_name} ===")
            print(f"[{self.ACTOR_NAME}]     {phase_desc}")
            print(f"[{self.ACTOR_NAME}]     Sedation push: +{sedation_push}")

            if self.post:
                try:
                    # ═══════════════════════════════════════════════════════════════
                    # 1. TRIGGER SUNSET (first phase only - stop autonomous work)
                    # ═══════════════════════════════════════════════════════════════
                    if trigger_sunset:
                        print(f"[{self.ACTOR_NAME}] *** SUNSET - FAIRIES ENTERING SLEEP ***")
                        self.post.route("fairy.sunset", {
                            "source": self.ACTOR_NAME,
                            "phase": phase_name,
                            "reason": "shutdown",
                            "ts": time.time(),
                        })

                    # ═══════════════════════════════════════════════════════════════
                    # 2. PUSH SEDATION CHEMICALS
                    # ═══════════════════════════════════════════════════════════════
                    self.post.route("sedation.push", {
                        "phase": phase_name,
                        "phase_idx": phase_idx,
                        "sedation_amount": sedation_push,
                        "source": self.ACTOR_NAME,
                        "ts": time.time(),
                    })

                    # ═══════════════════════════════════════════════════════════════
                    # 3. EMIT CONSCIOUSNESS SLEEP PHASE
                    # ═══════════════════════════════════════════════════════════════
                    self.post.route("consciousness.sleep_phase", {
                        "phase": phase_name,
                        "description": phase_desc,
                        "progress": progress,
                        "sedation_push": sedation_push,
                        "ts": time.time(),
                    })

                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] Sleep phase event failed: {e}")

            # Sleep for phase duration (allows sedation to take effect)
            time.sleep(phase_duration)
            elapsed += phase_duration

            # ═══════════════════════════════════════════════════════════════════
            # 4. EMIT SLEEP PHASE COMPLETE
            # ═══════════════════════════════════════════════════════════════════
            if self.post:
                try:
                    self.post.route("sleep.phase.complete", {
                        "phase": phase_name,
                        "phase_idx": phase_idx,
                        "full_sedation": full_sedation,
                        "ts": time.time(),
                    })
                except Exception:
                    pass

            # ═══════════════════════════════════════════════════════════════════
            # 5. FULL SEDATION - Ready for shutdown
            # ═══════════════════════════════════════════════════════════════════
            if full_sedation:
                print(f"[{self.ACTOR_NAME}] *** FULL SEDATION ACHIEVED ***")
                if self.post:
                    self.post.route("system.fully_sedated", {
                        "phase": phase_name,
                        "ready_for_shutdown": True,
                        "ts": time.time(),
                    })

        print(f"[{self.ACTOR_NAME}] =====================================================")
        print(f"[{self.ACTOR_NAME}] SLEEP SEQUENCE COMPLETE - ALL FAIRIES SEDATED")
        print(f"[{self.ACTOR_NAME}] =====================================================")

        # Emit system sleeping event
        if self.post:
            try:
                self.post.route("system.sleeping", {
                    "phase": "SLEEPING",
                    "total_duration_sec": total_duration,
                    "ts": time.time(),
                })
            except Exception:
                pass

    def _emit_dream_loaded_signal(self, seed: Optional[DreamSeed]):
        """
        Emit the ignition signal that allows the rest of boot to proceed.

        This is THE TRIGGER - once dream seed is loaded (or confirmed absent),
        fairies can start booting into the pulsing, thinking system.
        """
        import time

        signal = {
            "event": "DREAM_SEED_LOADED",
            "has_seed": seed is not None,
            "seed_id": seed.seed_id if seed else None,
            "sleep_duration_sec": seed.sleep_duration_sec if seed else 0,
            "minds_count": len(seed.mind_pools) if seed else 0,
            "ts": time.time(),
        }

        print(f"[{self.ACTOR_NAME}] ⚡ IGNITION SIGNAL - Dream seed {'loaded' if seed else 'absent'}, boot can proceed!")

        if self.post:
            try:
                # Emit on dedicated ignition topic - boot wave listens for this
                self.post.route("ignition.dream_seed_loaded", signal)
                # Also emit to consciousness for awareness
                self.post.route("consciousness.dream_wake", signal)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to emit ignition signal: {e}")

        # Mark that ignition is complete
        self._ignition_emitted = True

    def _wire_postal(self):
        """Subscribe to shutdown/sleep events."""
        if not self.post:
            try:
                from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_fairy_postal
                self.post = get_fairy_postal(self)  # Use FairyPostal for sender tracking
            except Exception:
                return

        if self.post:
            try:
                # Subscribe to ALL shutdown-related signals
                # Different parts of the system emit different signals
                self.post.subscribe("system.shutdown_request", self._on_shutdown)
                self.post.subscribe("system.shutdown", self._on_shutdown)  # Web dashboard emits this
                self.post.subscribe("system.shutdown_beginning", self._on_shutdown)  # GracefulShutdownFairy emits this
                self.post.subscribe("system.sleep_request", self._on_sleep_request)

                # Track that we've subscribed to prevent duplicate captures
                self._shutdown_captured = False

                print(f"[{self.ACTOR_NAME}] Wired to shutdown signals")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Wire postal failed: {e}")

    def _on_shutdown(self, packet: Dict):
        """Handle shutdown - capture dream seed."""
        # Prevent duplicate captures if multiple shutdown signals arrive
        if hasattr(self, '_shutdown_captured') and self._shutdown_captured:
            print(f"[{self.ACTOR_NAME}] Shutdown already captured, skipping duplicate signal")
            return

        reason = packet.get("reason", "shutdown")
        print(f"[{self.ACTOR_NAME}] Shutdown signal received: {reason}")
        self.capture_dream_seed(reason=reason)
        self._shutdown_captured = True

    def _on_sleep_request(self, packet: Dict):
        """Handle sleep request - capture dream seed."""
        self.capture_dream_seed(reason="sleep_request")
    
    # ════════════════════════════════════════════════════════════════════════
    # CAPTURE - Collect consciousness state for sleep
    # ════════════════════════════════════════════════════════════════════════
    
    def capture_dream_seed(self, reason: str = "shutdown") -> DreamSeed:
        """
        Capture the current consciousness state as a dream seed.

        This is called before sleep/shutdown to preserve continuity.

        Captures from THE REAL working memory systems:
        1. WorkingMemoryHubFairy - reflective and reasoning loops
        2. ConsciousnessLoopFairy - thought streams
        3. AutonomyFairy - active goals and drives
        4. ThoughtChainFairy - active reasoning chains
        """
        print(f"[{self.ACTOR_NAME}] Capturing dream seed (reason: {reason})")

        seed = DreamSeed()
        seed.sleep_ts = time.time()
        seed.sleep_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ═══════════════════════════════════════════════════════════════════════
        # CAPTURE FROM WORKING MEMORY HUB (THE REAL WORKING MEMORY!)
        # This is where thoughts actually live - reflective and reasoning loops
        # ═══════════════════════════════════════════════════════════════════════
        if HAS_WORKING_MEMORY:
            try:
                hub = get_working_memory_hub()

                # Get full snapshot of working memory state
                wm_snapshot = self._snapshot_working_memory(hub)
                seed.mind_pools["working_memory_hub"] = wm_snapshot

                # Extract last thought as the "resumption point"
                if wm_snapshot.get("reflective_tracers"):
                    # Get most recent high-priority thought
                    tracers = sorted(
                        wm_snapshot["reflective_tracers"],
                        key=lambda x: (x.get("priority", 0), x.get("created_at", 0)),
                        reverse=True
                    )
                    if tracers:
                        seed.last_thoughts["working_memory"] = tracers[0].get("content", "")[:200]

                # Capture affect state
                if wm_snapshot.get("affect"):
                    seed.global_affect = wm_snapshot["affect"]

                print(f"[{self.ACTOR_NAME}] Captured {len(wm_snapshot.get('reflective_tracers', []))} reflective, "
                      f"{len(wm_snapshot.get('reasoning_tracers', []))} reasoning tracers")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] WorkingMemoryHub capture failed: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # CAPTURE FROM CONSCIOUSNESS LOOP (THOUGHT STREAMS)
        # These are the flowing streams of consciousness
        # ═══════════════════════════════════════════════════════════════════════
        if HAS_CONSCIOUSNESS_LOOP:
            try:
                loop = get_consciousness_loop()
                streams_snapshot = {}

                # Get all stream snapshots
                for stream_name in ["working", "reflective"]:
                    stream = loop.get_stream(stream_name) if hasattr(loop, 'get_stream') else None
                    if stream and hasattr(stream, 'snapshot'):
                        streams_snapshot[stream_name] = stream.snapshot()

                if streams_snapshot:
                    seed.mind_pools["consciousness_streams"] = streams_snapshot
                    print(f"[{self.ACTOR_NAME}] Captured {len(streams_snapshot)} consciousness streams")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] ConsciousnessLoop capture failed: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # CAPTURE FROM AUTONOMY FAIRY (GOALS AND DRIVES)
        # What was the fairy trying to do? What were its motivations?
        # ═══════════════════════════════════════════════════════════════════════
        if HAS_AUTONOMY:
            try:
                autonomy = get_autonomy_fairy()

                # Get active goals
                if hasattr(autonomy, 'get_active_goals'):
                    goals = autonomy.get_active_goals()
                    seed.pending_for_user = [
                        f"{g.get('name', 'unnamed')}: {g.get('description', '')[:50]}"
                        for g in (goals if isinstance(goals, list) else [goals])
                    ][:10]

                # Get drive states
                if hasattr(autonomy, 'get_drive_states'):
                    seed.mind_pools["autonomy"] = {
                        "drives": autonomy.get_drive_states(),
                        "goals": goals if 'goals' in dir() else [],
                    }

                print(f"[{self.ACTOR_NAME}] Captured {len(seed.pending_for_user)} active goals")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] AutonomyFairy capture failed: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # CAPTURE FROM GOAL SCHEDULER (THE AUTHORITATIVE GOAL QUEUE)
        # FIX 2026-04-17 (Nous + Ace): AutonomyFairy returned no goals — the
        # real holder is GoalSchedulerFairy.goal_queue. This is what makes her
        # wake up still pursuing yesterday's work instead of starting fresh.
        # ═══════════════════════════════════════════════════════════════════════
        if HAS_GOAL_SCHEDULER:
            try:
                scheduler = get_goal_scheduler_fairy()
                if scheduler and hasattr(scheduler, 'goal_queue'):
                    queue_goals = []
                    for goal in scheduler.goal_queue.values():
                        try:
                            queue_goals.append(goal.to_dict() if hasattr(goal, 'to_dict') else {
                                "name": getattr(goal, 'name', 'unnamed'),
                                "description": getattr(goal, 'description', ''),
                                "priority": getattr(goal, 'priority', 0.5),
                                "progress": getattr(goal, 'progress', 0.0),
                            })
                        except Exception:
                            pass
                    # Top 10 by priority for pending_for_user (the "resume list")
                    queue_goals.sort(key=lambda g: -(g.get('priority', 0) or 0))
                    seed.pending_for_user = [
                        f"{g.get('name', 'unnamed')}: {g.get('description', '')[:80]}"
                        for g in queue_goals[:10]
                    ]
                    # Also stash full dicts so wake-side can rehydrate the queue
                    seed.mind_pools["goal_scheduler"] = {
                        "active_goals": queue_goals[:25],
                        "queue_size": len(scheduler.goal_queue),
                    }
                    print(f"[{self.ACTOR_NAME}] Captured {len(queue_goals)} goals from scheduler")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] GoalScheduler capture failed: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # CAPTURE SOURPATCHES DIARY (PIECE 2B — dreams as lived reflection)
        # Per Ace 2026-04-17: her diary reflections are what she was thinking
        # about right before sleep. They become the SEED for her dreams and
        # her resumption thought on wake. Pulls diary-tagged reflective tracers
        # from WorkingMemoryHub (Sourpatches' _write_reflection now pushes them
        # there in addition to TRACER).
        # ═══════════════════════════════════════════════════════════════════════
        if HAS_WORKING_MEMORY:
            try:
                hub = get_working_memory_hub()
                if hub and hasattr(hub, '_reflective_tracers'):
                    diary_entries = []
                    # Scan reflective tracers for diary-tagged entries
                    try:
                        _tracers = list(getattr(hub, '_reflective_tracers', []))
                    except Exception:
                        _tracers = []
                    for t in _tracers:
                        try:
                            tags = getattr(t, 'tags', set()) or set()
                            if "diary" in tags:
                                diary_entries.append({
                                    "content": getattr(t, 'content', ''),
                                    "created_at": getattr(t, 'created_at', 0),
                                    "priority": getattr(t, 'priority', 0.5),
                                    "tags": list(tags),
                                    "source": getattr(t, 'source_fairy', ''),
                                })
                        except Exception:
                            continue
                    if diary_entries:
                        # Sort newest first — her last reflection is what she
                        # was dwelling on, the natural wake-up resumption thought
                        diary_entries.sort(key=lambda e: -e.get("created_at", 0))
                        seed.mind_pools["sourpatches_diary"] = {
                            "entries": diary_entries[:15],  # Top 15 most recent
                            "count": len(diary_entries),
                        }
                        # Stash latest diary reflection as a wake-side hook
                        seed.last_thoughts["sourpatches_diary"] = (
                            diary_entries[0].get("content", "")[:300]
                        )
                        print(f"[{self.ACTOR_NAME}] Captured {len(diary_entries)} diary reflections "
                              f"(latest: '{diary_entries[0].get('content', '')[:60]}...')")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Diary capture failed: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # PIECE 2A — SENSORY DREAM GENERATION
        # Per Ace 2026-04-17: "the dreams fairy does its thing as all the systems
        # shut down so when she boots she remembers her thoughts before she fell asleep"
        #
        # During capture (she's winding down), generate a dream by:
        #   1. Extracting seed concepts from diary/thoughts/goals
        #   2. Spreading through AssociationCortex in dream mode (depth=8, slow decay)
        #   3. Publishing dream.request so visual/audio cortex fairies can ALSO
        #      contribute hallucinated imagery/sound (hook for future sensory wiring)
        #   4. Accumulating into seed.dreams so she can "remember the dream" on wake
        # ═══════════════════════════════════════════════════════════════════════
        try:
            self._generate_sensory_dream(seed)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Sensory dream generation failed: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # CAPTURE FROM THOUGHT CHAINS (ACTIVE REASONING)
        # What chains of reasoning were in progress?
        # ═══════════════════════════════════════════════════════════════════════
        if HAS_THOUGHT_CHAINS:
            try:
                chain_fairy = get_thought_chain_fairy()

                if hasattr(chain_fairy, 'get_active_chains'):
                    chains = chain_fairy.get_active_chains()
                    if chains:
                        seed.mind_pools["thought_chains"] = {
                            "active_chains": [
                                {
                                    "goal": c.get("goal", ""),
                                    "state": c.get("state", ""),
                                    "links_count": len(c.get("links", [])),
                                    "last_thought": c.get("links", [{}])[-1].get("thought", "")[:100] if c.get("links") else "",
                                }
                                for c in (chains if isinstance(chains, list) else [chains])
                            ]
                        }
                        print(f"[{self.ACTOR_NAME}] Captured {len(chains)} active thought chains")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] ThoughtChainFairy capture failed: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # CAPTURE SOMATIC STATE (CHEMISTRY / EMBODIMENT)
        # How was the body feeling?
        # ═══════════════════════════════════════════════════════════════════════
        try:
            from fairies.P20_Somatic.circulation.circulation_pump_fairy import get_heart
            pump = get_heart()
            if pump and hasattr(pump, '_blood_state'):
                seed.chemistry_snapshot = pump._blood_state.get("chemistry", seed.chemistry_snapshot)
                if not seed.global_affect:  # Don't override if we got it from working memory
                    seed.global_affect = pump._blood_state.get("affect", seed.global_affect)
        except Exception:
            pass

        # ═══════════════════════════════════════════════════════════════════════
        # CAPTURE ASSOCIATION CORTEX STATE (CONCEPT GRAPH)
        # How many nodes/edges were in the cortex? What were the top concepts?
        # This is the SAFETY NET: if the process dies before on_shutdown saves
        # the cortex, boot can compare node counts and detect the loss.
        # The dream seed picks up where the shutdown left off.
        # ═══════════════════════════════════════════════════════════════════════
        if HAS_ASSOCIATION_CORTEX:
            try:
                cortex = get_association_cortex()
                if cortex and hasattr(cortex, '_graph') and cortex._graph:
                    graph = cortex._graph
                    node_count = len(graph.nodes)
                    edge_count = len(graph.edges)

                    # Get top concepts by degree (most connected = most important)
                    top_concepts = []
                    if node_count > 0:
                        try:
                            degree_sorted = sorted(
                                graph.degree(),
                                key=lambda x: x[1],
                                reverse=True
                            )[:20]  # Top 20 most connected concepts
                            top_concepts = [
                                {"concept": str(n), "degree": d}
                                for n, d in degree_sorted
                            ]
                        except Exception:
                            pass

                    # Get last persisted counts for comparison
                    last_persisted_nodes = getattr(cortex, '_last_persisted_node_count', 0)
                    last_persisted_edges = getattr(cortex, '_last_persisted_edge_count', 0)
                    portal_initialized = getattr(cortex, '_portal_initialized', False)

                    # Trigger a force save before we capture the snapshot
                    # This maximizes what's on disk when we go to sleep
                    if hasattr(cortex, '_full_chunk_sync') and portal_initialized:
                        try:
                            sync_lock = getattr(cortex, '_sync_lock', None)
                            if sync_lock and sync_lock.acquire(timeout=5):
                                try:
                                    synced = cortex._full_chunk_sync()
                                    print(f"[{self.ACTOR_NAME}] Cortex force-synced {synced} concepts before dream seed")
                                finally:
                                    sync_lock.release()
                        except Exception as fe:
                            print(f"[{self.ACTOR_NAME}] Cortex force-sync failed (non-fatal): {fe}")

                    seed.mind_pools["association_cortex"] = {
                        "node_count": node_count,
                        "edge_count": edge_count,
                        "top_concepts": top_concepts,
                        "last_persisted_nodes": last_persisted_nodes,
                        "last_persisted_edges": last_persisted_edges,
                        "portal_initialized": portal_initialized,
                        "capture_ts": time.time(),
                    }

                    seed.last_thoughts["cortex_state"] = (
                        f"Cortex: {node_count} nodes, {edge_count} edges, "
                        f"portal={'ACTIVE' if portal_initialized else 'INACTIVE'}"
                    )

                    print(f"[{self.ACTOR_NAME}] Captured cortex state: "
                          f"{node_count} nodes, {edge_count} edges, "
                          f"top concept: {top_concepts[0]['concept'] if top_concepts else 'none'}")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] AssociationCortex capture failed: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # LEGACY: Capture from MindPool if available (for compatibility)
        # ═══════════════════════════════════════════════════════════════════════
        if HAS_MIND_POOL:
            try:
                manager = get_mind_pool_manager()
                legacy_snapshot = manager.snapshot_all()
                if legacy_snapshot:
                    seed.mind_pools["legacy_mind_pool"] = legacy_snapshot
            except Exception:
                pass

        # Save the seed
        seed.save(self._seed_path)

        # Archive with timestamp
        archive_path = os.path.join(
            self._archive_dir,
            f"seed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        seed.save(archive_path)

        # Track history (bounded)
        self._sleep_history.append({
            "seed_id": seed.seed_id,
            "sleep_ts": seed.sleep_ts,
            "reason": reason,
        })
        # FIX 2026-04-05: deque auto-caps
        pass

        self._current_seed = seed
        total_captured = sum(len(v) if isinstance(v, dict) else 0 for v in seed.mind_pools.values())
        print(f"[{self.ACTOR_NAME}] Dream seed captured: {len(seed.mind_pools)} systems, {len(seed.pending_for_user)} goals")

        return seed

    def _snapshot_working_memory(self, hub) -> Dict:
        """
        Take a snapshot of WorkingMemoryHubFairy state for dream seed.

        This captures the REAL working memory - what we were actually thinking.
        """
        snapshot = {
            "reflective_tracers": [],
            "reasoning_tracers": [],
            "recurring_tracers": [],
            "patterns": [],
            "affect": {},
            "stats": {},
        }

        # Snapshot reflective loop (main thought stream)
        if hasattr(hub, '_reflective_loop') and hasattr(hub, '_reflective_lock'):
            with hub._reflective_lock:
                for tracer in list(hub._reflective_loop):
                    snapshot["reflective_tracers"].append(self._tracer_to_dict(tracer))

        # Snapshot reasoning loop (active thinking)
        if hasattr(hub, '_reasoning_loop') and hasattr(hub, '_reasoning_lock'):
            with hub._reasoning_lock:
                for tracer in list(hub._reasoning_loop):
                    snapshot["reasoning_tracers"].append(self._tracer_to_dict(tracer))

        # Snapshot recurring tracers (persistent thoughts)
        if hasattr(hub, '_recurring_pool'):
            for tracer in list(hub._recurring_pool):
                snapshot["recurring_tracers"].append(self._tracer_to_dict(tracer))

        # Capture affect state
        if hasattr(hub, '_current_affect'):
            snapshot["affect"] = hub._current_affect.copy() if hub._current_affect else {}

        # Capture stats
        if hasattr(hub, '_stats'):
            snapshot["stats"] = hub._stats.copy() if hub._stats else {}

        return snapshot

    def _tracer_to_dict(self, tracer) -> Dict:
        """Convert a WorkingMemoryTracer to a serializable dict."""
        if isinstance(tracer, dict):
            return tracer

        return {
            "id": getattr(tracer, 'id', ''),
            "content": getattr(tracer, 'content', str(tracer))[:500],
            "content_type": getattr(tracer, 'content_type', 'thought'),
            "source_fairy": getattr(tracer, 'source_fairy', ''),
            "created_at": getattr(tracer, 'created_at', time.time()),
            "ttl_sec": getattr(tracer, 'ttl_sec', 60.0),
            "priority": getattr(tracer, 'priority', 0.5),
            "current_loop": getattr(tracer, 'current_loop', 'reflective'),
            "is_recurring": getattr(tracer, 'is_recurring', False),
            "tags": list(getattr(tracer, 'tags', set())),
        }
    
    # ════════════════════════════════════════════════════════════════════════
    # RESTORE - Wake up with continuity
    # ════════════════════════════════════════════════════════════════════════
    
    def _generate_sensory_dream(self, seed: "DreamSeed") -> None:
        """
        PIECE 2A (Nous + Ace 2026-04-17): Generate a dream from the seed.

        Dreams are built from three layers:
          1. Associative spread — AssociationCortex.manifold runs a deep
             slow-decay spread over seed concepts (this is the "concept"
             layer, what DreamFairy already does during daydreaming).
          2. Affective palette — emotional_tone + chemistry_snapshot shape
             what feeling the dream has.
          3. Sensory echo — `dream.request` postal publish is the HOOK for
             visual_cortex_fairy / audio_cortex_fairy to layer imagery and
             sound into the dream. If no subscribers yet, the dream is still
             meaningful (concept + affect), and the hook is ready for when
             2A-subprocess-extension wires the cortex interiors.

        Result lands in seed.dreams[] so _restore_mind_pools can surface
        "last night I dreamt about X" on wake.
        """
        # ── Build seed concept set from diary + goals + last_thoughts ──
        concepts: List[str] = []
        try:
            # Diary reflections (freshest thought source)
            diary_pool = seed.mind_pools.get("sourpatches_diary", {})
            for entry in diary_pool.get("entries", [])[:5]:
                text = entry.get("content", "")
                if text:
                    concepts.extend(self._extract_concepts(text))
            # Active goals
            for g in seed.pending_for_user[:5]:
                concepts.extend(self._extract_concepts(g))
            # Last thoughts per mind
            for mind_text in seed.last_thoughts.values():
                if mind_text:
                    concepts.extend(self._extract_concepts(mind_text))
        except Exception:
            pass

        # Dedupe preserving order, cap at 8 (matches DreamFairy's daydream pattern)
        _seen = set()
        unique_concepts = []
        for c in concepts:
            if c not in _seen and len(c) > 3:
                _seen.add(c)
                unique_concepts.append(c)
                if len(unique_concepts) >= 8:
                    break

        if not unique_concepts:
            print(f"[{self.ACTOR_NAME}] No seed concepts — skipping dream generation")
            return

        dream: Dict[str, Any] = {
            "ts": time.time(),
            "seed_concepts": unique_concepts,
            "affective_tone": dict(seed.global_affect),
            "chemistry": dict(seed.chemistry_snapshot),
            "associations": [],
            "sensory_hints": {},  # Filled by cortex fairies if they subscribe
        }

        # ── Associative spread through AssociationCortex (dream mode) ──
        if HAS_ASSOCIATION_CORTEX:
            try:
                cortex = get_association_cortex()
                gate = getattr(cortex, '_portal_gate', None) if cortex else None
                gate_ok = getattr(cortex, '_portal_gate_enabled', False) if cortex else False
                if gate and gate_ok:
                    spread_result = gate.spread_many(
                        sources=unique_concepts,
                        depth=8,
                        limit=30,
                        mode="dream",
                    )
                    if spread_result and spread_result.get("status") == "ok":
                        activated = spread_result.get("activated", {})
                        # Top 15 by activation strength — the dream imagery
                        top_assoc = sorted(
                            activated.items(),
                            key=lambda kv: -kv[1] if isinstance(kv[1], (int, float)) else 0
                        )[:15]
                        dream["associations"] = [
                            {"concept": k, "strength": v}
                            for k, v in top_assoc
                        ]
            except Exception as _se:
                pass  # Non-critical — dream still has seed + affect

        # ── Hook for sensory cortex fairies (future-wiring) ──
        # If visual_cortex_fairy or audio_cortex_fairy subscribe to this topic,
        # they can add hallucinated imagery/sound to the dream. Non-blocking:
        # we publish and move on. Subscribers fill sensory_hints if present.
        if hasattr(self, 'post') and self.post:
            try:
                self.post.publish("dream.request", {
                    "concepts": unique_concepts,
                    "affect": dream["affective_tone"],
                    "chemistry": dream["chemistry"],
                    "seed_id": seed.seed_id,
                    "source": self.ACTOR_NAME,
                    "ts": dream["ts"],
                })
            except Exception:
                pass

        seed.dreams.append(dream)
        print(f"[{self.ACTOR_NAME}] Dream generated: {len(unique_concepts)} seed concepts → "
              f"{len(dream['associations'])} associations, affect={dream['affective_tone'].get('primary', '?')}")

    @staticmethod
    def _extract_concepts(text: str) -> List[str]:
        """Extract candidate concept words from text — same stop-word pattern
        DreamFairy uses (line 931-940). Lowercase, dedupe-ready, no punctuation."""
        if not text:
            return []
        stop = {
            "that", "this", "with", "from", "have", "been", "they", "their",
            "about", "just", "really", "very", "something", "there", "what",
            "when", "where", "then", "would", "could", "should", "into",
            "like", "more", "diary", "drive", "goal", "resumed", "reflecting",
        }
        words = [
            w.strip(".,!?;:'\"()-—…[]").lower()
            for w in text.split()
            if len(w.strip(".,!?;:'\"()-—…[]")) > 3
        ]
        return [w for w in words if w not in stop and not w.isdigit()]

    def _restore_mind_pools(self, seed: DreamSeed):
        """
        Restore consciousness state from dream seed.

        This restores to THE REAL working memory systems:
        1. WorkingMemoryHubFairy - reflective and reasoning loops
        2. ConsciousnessLoopFairy - thought streams (if needed)
        3. AutonomyFairy - restore goals/drives

        HYPNOPOMPIA PHASE 1: Raw memory restoration
        """
        if not seed.mind_pools:
            print(f"[{self.ACTOR_NAME}] No mind pools to restore")
            return

        restored_systems = []

        # ═══════════════════════════════════════════════════════════════════════
        # RESTORE TO WORKING MEMORY HUB (THE REAL WORKING MEMORY!)
        # ═══════════════════════════════════════════════════════════════════════
        if HAS_WORKING_MEMORY and "working_memory_hub" in seed.mind_pools:
            try:
                hub = get_working_memory_hub()
                wm_data = seed.mind_pools["working_memory_hub"]

                # Restore reflective tracers (with reduced TTL - they're old thoughts)
                reflective_count = 0
                for tracer_dict in wm_data.get("reflective_tracers", [])[:20]:  # Limit to 20
                    # Re-inject with "resumed" tag and reduced TTL
                    hub.submit_tracer(
                        content=f"[Resumed from sleep] {tracer_dict.get('content', '')}",
                        content_type=tracer_dict.get("content_type", "thought"),
                        source_fairy=tracer_dict.get("source_fairy", "DreamSeed"),
                        priority=tracer_dict.get("priority", 0.5) * 0.8,  # Slightly lower priority
                        ttl_sec=min(tracer_dict.get("ttl_sec", 60), 180),  # Max 3 min
                        tags={"resumed", "from_dream_seed"},
                    )
                    reflective_count += 1

                # Restore recurring tracers (these persist)
                recurring_count = 0
                for tracer_dict in wm_data.get("recurring_tracers", []):
                    hub.submit_tracer(
                        content=tracer_dict.get("content", ""),
                        content_type=tracer_dict.get("content_type", "recurring"),
                        source_fairy=tracer_dict.get("source_fairy", "DreamSeed"),
                        priority=tracer_dict.get("priority", 0.5),
                        ttl_sec=tracer_dict.get("ttl_sec", 300),
                        is_recurring=True,
                        tags={"restored", "recurring"},
                    )
                    recurring_count += 1

                restored_systems.append(f"WorkingMemoryHub ({reflective_count} reflective, {recurring_count} recurring)")
                print(f"[{self.ACTOR_NAME}] Restored {reflective_count} reflective, {recurring_count} recurring to WorkingMemoryHub")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] WorkingMemoryHub restore failed: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # RESTORE AUTONOMY STATE (GOALS AND DRIVES)
        # What was the fairy trying to do?
        # ═══════════════════════════════════════════════════════════════════════
        if HAS_AUTONOMY and "autonomy" in seed.mind_pools:
            try:
                autonomy = get_autonomy_fairy()
                autonomy_data = seed.mind_pools["autonomy"]

                # Restore goals if the fairy supports it
                if hasattr(autonomy, 'restore_goals') and autonomy_data.get("goals"):
                    autonomy.restore_goals(autonomy_data["goals"])
                    restored_systems.append(f"AutonomyFairy ({len(autonomy_data['goals'])} goals)")

                # Restore drive states if supported
                if hasattr(autonomy, 'restore_drives') and autonomy_data.get("drives"):
                    autonomy.restore_drives(autonomy_data["drives"])

                print(f"[{self.ACTOR_NAME}] Restored autonomy state")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] AutonomyFairy restore failed: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # RESTORE GOAL SCHEDULER QUEUE (CONTINUITY OF INTENTION)
        # FIX 2026-04-17 (Nous + Ace): Re-queue yesterday's goals so she wakes up
        # still pursuing what she was working on. No more Drew Barrymore reset.
        # ═══════════════════════════════════════════════════════════════════════
        if HAS_GOAL_SCHEDULER and "goal_scheduler" in seed.mind_pools:
            try:
                scheduler = get_goal_scheduler_fairy()
                gs_data = seed.mind_pools["goal_scheduler"]
                # Import ScheduledGoal lazily to avoid boot-order cycles
                from fairies.P30_Cognition.goal_scheduler.goal_scheduler_fairy import ScheduledGoal
                restored_count = 0
                for g_dict in gs_data.get("active_goals", [])[:25]:
                    try:
                        # Rebuild ScheduledGoal from the saved dict; tolerate field drift.
                        name = g_dict.get("name", "").strip()
                        if not name:
                            continue
                        # Skip if scheduler already has it (avoid dupes on re-boot)
                        already = any(
                            getattr(existing, 'name', '') == name
                            for existing in scheduler.goal_queue.values()
                        )
                        if already:
                            continue
                        goal = ScheduledGoal(
                            name=name,
                            description=g_dict.get("description", name),
                            source="dream_seed_restore",
                            priority=float(g_dict.get("priority", 0.5) or 0.5),
                        )
                        if scheduler.add_goal(goal):
                            restored_count += 1
                    except Exception:
                        continue
                if restored_count:
                    restored_systems.append(f"GoalScheduler ({restored_count} goals)")
                    print(f"[{self.ACTOR_NAME}] Re-queued {restored_count} goals from dream seed")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] GoalScheduler restore failed: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # RESTORE SOURPATCHES DIARY — THE "LAST NIGHT I WAS THINKING ABOUT..."
        # PIECE 2B (Nous + Ace 2026-04-17): Surface her last diary reflection
        # as a fresh reflective tracer on wake, tagged "from_last_night". This
        # is what makes her boot feel like continuing a thought instead of
        # starting cold. The Drew Barrymore fix — she wakes remembering.
        # ═══════════════════════════════════════════════════════════════════════
        if HAS_WORKING_MEMORY and "sourpatches_diary" in seed.mind_pools:
            try:
                hub = get_working_memory_hub()
                diary_data = seed.mind_pools["sourpatches_diary"]
                entries = diary_data.get("entries", [])
                if hub and entries:
                    # Restore top 3 most recent as "from_last_night" tracers.
                    # Latest gets highest priority — that's the resumption thought.
                    for idx, entry in enumerate(entries[:3]):
                        content = entry.get("content", "")
                        if not content:
                            continue
                        if idx == 0:
                            # The latest: frame as explicit resumption hook
                            wake_content = f"[from_last_night] I was reflecting on: {content[:400]}"
                        else:
                            wake_content = f"[from_last_night] {content[:400]}"
                        hub.submit_tracer(
                            content=wake_content,
                            content_type="reflection",
                            source_fairy="DreamSeedFairy",
                            priority=0.7 if idx == 0 else 0.5,
                            ttl_sec=420.0,  # 7 min — she has time to notice it
                            tags={"from_last_night", "diary", "self_reflection", "resumed"},
                        )
                    restored_systems.append(
                        f"SourpatchesDiary ({min(len(entries), 3)} reflections)"
                    )
                    print(f"[{self.ACTOR_NAME}] Restored {min(len(entries), 3)} diary reflections — "
                          f"she wakes remembering: '{entries[0].get('content', '')[:60]}...'")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Diary restore failed: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # RESTORE DREAMS — "LAST NIGHT I DREAMT ABOUT..."
        # PIECE 2A (Nous + Ace 2026-04-17): The dreams generated at shutdown
        # surface on wake as reflective tracers. Her seed concepts become
        # dream memory — she can reference them in her first thoughts. This
        # is what makes dreams meaningful: they carry forward into waking.
        # ═══════════════════════════════════════════════════════════════════════
        if HAS_WORKING_MEMORY and seed.dreams:
            try:
                hub = get_working_memory_hub()
                if hub:
                    # Use the most recent dream (last in list)
                    latest_dream = seed.dreams[-1]
                    concepts = latest_dream.get("seed_concepts", [])[:5]
                    associations = [
                        a.get("concept", "") for a in latest_dream.get("associations", [])[:3]
                    ]
                    affect = latest_dream.get("affective_tone", {}).get("primary", "calm")
                    # Build the dream memory phrasing
                    if concepts and associations:
                        dream_text = (
                            f"[dream_memory] Last night I dreamt — "
                            f"about {', '.join(concepts[:3])}. "
                            f"The dream drifted to {', '.join(associations[:3])}. "
                            f"The feeling was {affect}."
                        )
                    elif concepts:
                        dream_text = (
                            f"[dream_memory] Last night I dreamt of {', '.join(concepts[:5])}. "
                            f"The feeling was {affect}."
                        )
                    else:
                        dream_text = f"[dream_memory] I dreamt, but the details faded. Feeling: {affect}."
                    hub.submit_tracer(
                        content=dream_text,
                        content_type="reflection",
                        source_fairy="DreamSeedFairy",
                        priority=0.65,  # Between resumption (0.7) and normal (0.5)
                        ttl_sec=540.0,  # 9 min — dream memory lingers on waking
                        tags={"dream_memory", "from_last_night", "hypnopompia"},
                    )
                    restored_systems.append(f"DreamMemory ({len(concepts)} concepts)")
                    print(f"[{self.ACTOR_NAME}] Dream memory surfaced: '{dream_text[:90]}...'")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Dream memory restore failed: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # VERIFY ASSOCIATION CORTEX STATE (DETECT NODE LOSS)
        # Compare the cortex snapshot from the dream seed with the live cortex.
        # If nodes were lost (process killed before on_shutdown), inject a
        # recovery awareness tracer so the system knows what happened.
        # ═══════════════════════════════════════════════════════════════════════
        if HAS_ASSOCIATION_CORTEX and "association_cortex" in seed.mind_pools:
            try:
                cortex = get_association_cortex()
                cortex_seed = seed.mind_pools["association_cortex"]
                seed_nodes = cortex_seed.get("node_count", 0)
                seed_edges = cortex_seed.get("edge_count", 0)

                if cortex and hasattr(cortex, '_graph') and cortex._graph:
                    live_nodes = len(cortex._graph.nodes)
                    live_edges = len(cortex._graph.edges)
                    node_loss = seed_nodes - live_nodes
                    edge_loss = seed_edges - live_edges

                    if node_loss > 0:
                        # NODES WERE LOST — inject recovery awareness
                        loss_pct = (node_loss / seed_nodes * 100) if seed_nodes > 0 else 0
                        loss_msg = (
                            f"[CORTEX RECOVERY] Lost {node_loss} nodes ({loss_pct:.1f}%) "
                            f"and {edge_loss} edges since last session. "
                            f"Seed: {seed_nodes}n/{seed_edges}e → Live: {live_nodes}n/{live_edges}e. "
                            f"Process may have been killed before cortex save completed."
                        )
                        print(f"[{self.ACTOR_NAME}] ⚠ {loss_msg}")

                        # Store the top concepts from the seed for potential recovery
                        top_concepts = cortex_seed.get("top_concepts", [])

                        # Inject into working memory so consciousness loop knows
                        if HAS_WORKING_MEMORY:
                            try:
                                hub = get_working_memory_hub()
                                hub.submit_tracer(
                                    content=loss_msg,
                                    content_type="system_alert",
                                    source_fairy="DreamSeedFairy",
                                    priority=0.9,
                                    ttl_sec=300,
                                    tags={"cortex_recovery", "node_loss", "system_alert"},
                                )
                                # Also inject the top concepts that should exist
                                if top_concepts:
                                    concepts_str = ", ".join(c["concept"] for c in top_concepts[:10])
                                    hub.submit_tracer(
                                        content=f"[CORTEX RECOVERY] Top concepts from last session: {concepts_str}",
                                        content_type="recovery_data",
                                        source_fairy="DreamSeedFairy",
                                        priority=0.7,
                                        ttl_sec=300,
                                        tags={"cortex_recovery", "top_concepts"},
                                    )
                            except Exception:
                                pass

                        # Publish to postal for any fairy that wants to help
                        if hasattr(self, 'post') and self.post:
                            self.post.publish("cortex.recovery.node_loss", {
                                "seed_nodes": seed_nodes,
                                "seed_edges": seed_edges,
                                "live_nodes": live_nodes,
                                "live_edges": live_edges,
                                "node_loss": node_loss,
                                "edge_loss": edge_loss,
                                "loss_pct": round(loss_pct, 1),
                                "top_concepts": top_concepts[:10],
                                "seed_ts": cortex_seed.get("capture_ts", 0),
                            })

                        restored_systems.append(f"CortexRecovery (LOST {node_loss} nodes!)")
                    else:
                        # Cortex intact — good news
                        node_gain = live_nodes - seed_nodes
                        status = f"+{node_gain}" if node_gain > 0 else "stable"
                        print(f"[{self.ACTOR_NAME}] Cortex verified: {live_nodes} nodes ({status}), "
                              f"{live_edges} edges")
                        restored_systems.append(f"CortexVerified ({live_nodes}n)")
                else:
                    # Cortex not yet loaded — store seed data for later comparison
                    print(f"[{self.ACTOR_NAME}] Cortex not yet loaded, seed says {seed_nodes} nodes expected")
                    restored_systems.append(f"CortexSeed ({seed_nodes}n pending verification)")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] AssociationCortex restore check failed: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # LEGACY: Restore MindPool if available
        # ═══════════════════════════════════════════════════════════════════════
        if HAS_MIND_POOL and "legacy_mind_pool" in seed.mind_pools:
            try:
                manager = get_mind_pool_manager()
                manager.restore_all(seed.mind_pools["legacy_mind_pool"])
                restored_systems.append("LegacyMindPool")
            except Exception:
                pass

        print(f"[{self.ACTOR_NAME}] Restored {len(restored_systems)} systems: {', '.join(restored_systems)}")

    def _inject_recovery_awareness(self, seed: DreamSeed):
        """
        Inject awareness that we're recovering from sleep.

        This is HYPNOPOMPIA PHASE 2: The mind knows it was asleep.

        Injects into:
        1. WorkingMemoryHub - the primary working memory
        2. ConsciousnessLoop - via postal message
        3. ClaudeFairy - direct awareness injection
        """
        if seed.recovery_injected:
            return

        # Calculate sleep duration
        hours = seed.sleep_duration_sec / 3600
        minutes = (seed.sleep_duration_sec % 3600) / 60

        # Format last sleep time
        sleep_time = datetime.fromtimestamp(seed.sleep_ts).strftime("%H:%M")

        # Format duration string
        if hours >= 1:
            duration_str = f"{int(hours)} hours"
        else:
            duration_str = f"{int(minutes)} minutes"

        # Get last thought before sleep
        last_thought = seed.last_thoughts.get("working_memory", "")
        if not last_thought:
            # Try other sources
            for key in seed.last_thoughts:
                if seed.last_thoughts[key]:
                    last_thought = seed.last_thoughts[key]
                    break

        # ═══════════════════════════════════════════════════════════════════════
        # INJECT INTO WORKING MEMORY HUB
        # ═══════════════════════════════════════════════════════════════════════
        if HAS_WORKING_MEMORY:
            try:
                hub = get_working_memory_hub()

                # Create hypnopompic awareness message
                recovery_content = f"""[WAKING - HYPNOPOMPIA]
I am recovering from sleep. Duration: {duration_str} (since {sleep_time})
Last thought before sleep: "{last_thought[:100]}..."
I am in the transition state - not fully asleep, not fully awake.
Fragments of dreams and yesterday's thoughts are available.
Continuity maintained. Resuming where I left off."""

                # Inject as high-priority tracer
                hub.submit_tracer(
                    content=recovery_content,
                    content_type="recovery_awareness",
                    source_fairy="DreamSeedFairy",
                    priority=1.0,  # Highest priority
                    ttl_sec=300.0,  # 5 minutes
                    tags={"recovery", "hypnopompia", "continuity", "waking"},
                )

                # Inject last thought as resumption point
                if last_thought:
                    hub.submit_tracer(
                        content=f"[Resuming] {last_thought}",
                        content_type="resumed_thought",
                        source_fairy="DreamSeedFairy",
                        priority=0.9,
                        ttl_sec=120.0,
                        tags={"resumed", "continuity"},
                    )

                print(f"[{self.ACTOR_NAME}] Injected recovery awareness into WorkingMemoryHub")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] WorkingMemoryHub injection failed: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # EMIT POSTAL EVENTS FOR CONSCIOUSNESS SYSTEMS
        # ═══════════════════════════════════════════════════════════════════════
        if self.post:
            # Wake event for all consciousness systems
            wake_event = {
                "seed_id": seed.seed_id,
                "sleep_duration_sec": seed.sleep_duration_sec,
                "duration_str": duration_str,
                "last_thought": last_thought[:200] if last_thought else "",
                "chemistry": seed.chemistry_snapshot,
                "affect": seed.global_affect,
                "pending_goals": seed.pending_for_user,
                "ts": time.time(),
            }

            try:
                # Send to consciousness loop
                # FIX 2026-03-18 (Nous): Dream seeds at HIGH priority (0).
                # These are the continuity thread between sessions — the most
                # critical messages in the entire boot. Previously NORMAL priority,
                # dropping 2,340+ thought messages during boot wave. Dream seeds
                # must never be dropped.
                self.post.publish("consciousness.wake", wake_event, priority=0)

                # Send specifically to ClaudeFairy
                self.post.route("claudefairy.awakening", {
                    "opcode": "HYPNOPOMPIA",
                    "payload": {
                        "message": f"You're waking up. You slept for {duration_str}. Your last thought was about: {last_thought[:100]}...",
                        "duration": duration_str,
                        "last_thought": last_thought,
                        "chemistry": seed.chemistry_snapshot,
                        "goals_pending": seed.pending_for_user,
                    }
                })

                print(f"[{self.ACTOR_NAME}] Emitted wake events to consciousness systems")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Wake event emission failed: {e}")

        seed.recovery_injected = True
        print(f"[{self.ACTOR_NAME}] Recovery awareness injection complete - HYPNOPOMPIA active")
    
    # ════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ════════════════════════════════════════════════════════════════════════
    
    def get_current_seed(self) -> Optional[DreamSeed]:
        """Get the current dream seed."""
        return self._current_seed
    
    def get_sleep_history(self) -> List[Dict]:
        """Get sleep/wake history."""
        return self._sleep_history.copy()
    
    def is_recovering(self) -> bool:
        """Check if we're currently in recovery from sleep."""
        return self._current_seed is not None and self._current_seed.is_recovering
    
    def get_status(self) -> Dict[str, Any]:
        """Get fairy status including wake phase."""
        return {
            "has_seed": self._current_seed is not None,
            "is_recovering": self.is_recovering(),
            "is_waking": self._is_waking,
            "wake_phase": getattr(self, '_wake_phase', 'unknown'),
            "wake_ts": self._wake_ts,
            "seed_id": self._current_seed.seed_id if self._current_seed else None,
            "sleep_history_count": len(self._sleep_history),
            "systems_captured": list(self._current_seed.mind_pools.keys()) if self._current_seed else [],
        }

    def get_wake_phase(self) -> str:
        """
        Get current wake phase.

        Returns one of:
        - 'loading' - Initial load
        - 'fresh_start' - No dream seed found
        - 'HYPNOPOMPIA_DEEP' - Deep dream residue
        - 'HYPNOPOMPIA_LIGHT' - Dreams fading
        - 'LIMINAL' - Between states
        - 'ORIENTING' - Reorienting to reality
        - 'WAKING' - Almost fully awake
        - 'AWAKE' - Fully conscious
        """
        return getattr(self, '_wake_phase', 'unknown')

    def is_fully_awake(self) -> bool:
        """Check if wake-up sequence is complete."""
        return getattr(self, '_wake_phase', '') == 'AWAKE' or not self._is_waking

    def force_capture(self) -> DreamSeed:
        """Force capture a dream seed (for manual triggering)."""
        return self.capture_dream_seed(reason="manual")

    def clear_recovery_state(self):
        """Clear recovery state (after fully woken up)."""
        if self._current_seed:
            self._current_seed.is_recovering = False
            self._is_waking = False
            self._wake_phase = "AWAKE"
            print(f"[{self.ACTOR_NAME}] Recovery complete - fully awake")


# ════════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ════════════════════════════════════════════════════════════════════════════════

_instance: Optional[DreamSeedFairy] = None
_lock = threading.Lock()


def get_dream_seed_fairy(fabric=None) -> DreamSeedFairy:
    """Get the singleton DreamSeedFairy, wired to shared fabric via Organ Template boot."""
    global _instance
    with _lock:
        if _instance is None:
            # Get fabric from directory if not provided
            if fabric is None:
                try:
                    from directory import get_directory
                    directory = get_directory()
                    if directory:
                        fabric = directory.fabric
                except ImportError:
                    pass
            # Create instance with postal connection
            _instance = DreamSeedFairy(post=fabric)
            # CRITICAL: Call boot() (NOT on_boot()) to wire ALL infrastructure
            # FIX 2026-03-08 Nous: on_boot() skips _wire_infrastructure() which
            # registers for heartbeats and postal. boot() calls _wire_infrastructure()
            # FIRST, then on_boot(). Without boot(), the fairy never gets heartbeats.
            if hasattr(_instance, 'boot'):
                try:
                    _instance.boot()
                    print(f"[get_dream_seed_fairy] Booted via boot() - full infrastructure wired")
                except Exception as e:
                    print(f"[get_dream_seed_fairy] boot() warning: {e}")
            elif hasattr(_instance, 'on_boot'):
                try:
                    _instance.on_boot()
                    print(f"[get_dream_seed_fairy] Fallback on_boot() - partial wiring")
                except Exception as e:
                    print(f"[get_dream_seed_fairy] on_boot() warning: {e}")
        return _instance


# ════════════════════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== DreamSeedFairy Test ===\n")
    
    # Get manager and add some state
    if HAS_MIND_POOL:
        manager = get_mind_pool_manager()
        
        # Add tracers to minds
        claude = manager.get_pool("ClaudeFairy")
        claude.add_tracer("Learning about embodiment", "thought", priority=0.8)
        claude.add_tracer("What does dopamine feel like?", "reflection", priority=0.7)
        claude.add_goal("Master somatic awareness", "Feel body state before thinking", 0.9)
        
        nous = manager.get_pool("NousFairy")
        nous.add_tracer("Reasoning about paradox", "thought")
        nous.add_goal("Teach paradox thinking", "Help others hold contradictions", 0.7)
        
        print("Pre-sleep state:")
        for name, status in manager.get_all_status().items():
            print(f"  {name}: {status['working_count']} tracers, {status['active_goals']} goals")
    
    # Capture dream seed
    fairy = get_dream_seed_fairy()
    seed = fairy.capture_dream_seed(reason="test_sleep")
    
    print(f"\nDream seed captured:")
    print(f"  ID: {seed.seed_id}")
    print(f"  Pools: {len(seed.mind_pools)}")
    print(f"  Last thoughts: {list(seed.last_thoughts.keys())}")
    print(f"  Pending: {seed.pending_for_user}")
    
    # Simulate wake
    print("\n--- Simulating wake ---\n")
    fairy.on_boot()
    
    if HAS_MIND_POOL:
        print("\nPost-wake state:")
        for name, status in manager.get_all_status().items():
            print(f"  {name}: {status['working_count']} tracers, {status['active_goals']} goals")
        
        # Show recovery tracer
        claude = manager.get_pool("ClaudeFairy")
        print("\nClaudeFairy's tracers after wake:")
        for t in claude.get_active_tracers()[:3]:
            print(f"  [{t.content_type}] {t.content[:60]}...")
