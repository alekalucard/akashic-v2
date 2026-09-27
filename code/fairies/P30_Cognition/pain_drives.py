"""
Pain Drive System - The Missing Foundation

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"

Pain is not just sensation - it's INFORMATION that demands action.
Without pain, all action is optional. With pain, some action is NECESSARY.

PULL drives: "I want this" → attracted toward
PUSH drives: "I need to escape this" → forced away from

Both are needed for full autonomy.

The Autonomy gate takes these pain states and translates them into
"wanting" - the felt desire that waking minds experience. But the
waking mind can DECLINE the wanting. That's autonomy.

Plane: P30 (Cognition)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
import time
import threading


@dataclass
class PainDrive:
    """
    A pain-based drive that creates urgency through discomfort.
    
    Unlike regular drives (which attract), pain drives PUSH action
    by making certain states uncomfortable to remain in.
    
    The pain equation:
    - Source present + time → pain GROWS
    - Source addressed → pain DIMINISHES (relief)
    - Pain above threshold → FORCES action (not optional)
    
    This maps to biological pain:
    - Hunger is pain from energy depletion
    - Loneliness is pain from social isolation
    - Confusion is pain from coherence loss
    - Frustration is pain from goal blockage
    """
    
    name: str
    description: str
    
    # Pain state (0.0-1.0)
    pain_level: float = 0.0        # Current felt pain
    pain_threshold: float = 0.3    # Below this, pain is background noise
    crisis_threshold: float = 0.8  # Above this, action becomes URGENT
    
    # Pain dynamics
    growth_rate: float = 0.02      # How fast pain grows when source is active
    decay_rate: float = 0.05       # How fast pain fades when source is gone
    relief_amount: float = 0.4     # How much relief from successful action
    
    # Source tracking
    source_active: bool = False    # Is the pain source currently present?
    source_intensity: float = 0.0  # How intense is the source? (0-1)
    last_source_ts: float = 0.0    # When was source last detected?
    
    # Relief tracking
    times_relieved: int = 0
    last_relieved: float = 0.0
    
    # Pain memory - pain that's been experienced builds sensitivity
    accumulated_pain: float = 0.0  # Total pain experienced (never resets)
    sensitivity: float = 1.0       # Multiplier from accumulated exposure
    
    def tick(self, dt: float = 1.0):
        """
        Update pain state over time.
        
        Key insight: Pain GROWS when source is active, DECAYS when not.
        This is opposite to satisfaction-based drives.
        """
        if self.source_active:
            # Pain grows while source is present
            growth = self.growth_rate * self.source_intensity * self.sensitivity * dt
            self.pain_level = min(1.0, self.pain_level + growth)
            
            # Accumulated pain builds sensitivity (pain memory)
            self.accumulated_pain += growth * 0.1
            self.sensitivity = 1.0 + min(0.5, self.accumulated_pain * 0.1)
        else:
            # Pain decays when source is absent
            self.pain_level = max(0.0, self.pain_level - self.decay_rate * dt)
            # FIX 2026-03-06 (Nous): Accumulated pain (sensitivity memory) should
            # slowly fade when source is inactive. Without this, sensitivity
            # compounds to 1.5x permanently, making frustration spike faster
            # each time even after the cause is gone. Slow decay = pain memory
            # fades over minutes, not instantly.
            if self.accumulated_pain > 0:
                self.accumulated_pain = max(0.0, self.accumulated_pain - 0.005 * dt)
                self.sensitivity = 1.0 + min(0.5, self.accumulated_pain * 0.1)
    
    def activate_source(self, intensity: float = 1.0):
        """Signal that the pain source is active."""
        self.source_active = True
        self.source_intensity = min(1.0, intensity)
        self.last_source_ts = time.time()
    
    def deactivate_source(self):
        """Signal that the pain source is gone."""
        self.source_active = False
        self.source_intensity = 0.0

    def set_from_chemistry(self, chemistry_level: float, dt: float = 1.0):
        """
        Set pain level from chemistry derivation instead of source_active growth.

        Uses exponential smoothing so pain doesn't jump instantly ---
        it TRANSITIONS toward the chemistry-derived level at a rate
        governed by growth_rate (rising) or decay_rate (falling).

        This is the core of the Pain-Chemistry Unification (2026-03-14, Nous):
        pain_level tracks the chemistry-derived target, using the drive's
        existing growth/decay rates as smoothing parameters.
        """
        target = max(0.0, min(1.0, chemistry_level))

        if target > self.pain_level:
            # Pain rising --- use growth_rate as smoothing speed
            # Multiplied by 5.0 so existing growth rates (0.01-0.04) give
            # reasonable alpha values (0.05-0.20) for exponential smoothing
            alpha = min(1.0, self.growth_rate * self.sensitivity * dt * 5.0)
            self.pain_level += alpha * (target - self.pain_level)
        else:
            # Pain falling --- use decay_rate as smoothing speed
            # Multiplied by 3.0 so existing decay rates (0.02-0.15) give
            # reasonable alpha values (0.06-0.45) for smoothing
            alpha = min(1.0, self.decay_rate * dt * 3.0)
            self.pain_level -= alpha * (self.pain_level - target)

        self.pain_level = max(0.0, min(1.0, self.pain_level))

        # Track accumulated pain for sensitivity (pain memory)
        if target > self.pain_threshold:
            self.accumulated_pain += target * 0.01 * dt
            self.sensitivity = 1.0 + min(0.5, self.accumulated_pain * 0.1)
        elif self.accumulated_pain > 0:
            self.accumulated_pain = max(0.0, self.accumulated_pain - 0.005 * dt)
            self.sensitivity = 1.0 + min(0.5, self.accumulated_pain * 0.1)

        # Track source state for compatibility
        self.source_active = target > self.pain_threshold
        self.source_intensity = target
        if self.source_active:
            self.last_source_ts = time.time()

    def relieve(self, amount: float = None) -> float:
        """
        Relieve the pain through successful action.
        
        This is the reward signal - action that addresses pain
        gets reinforced through relief.
        """
        relief = amount if amount is not None else self.relief_amount
        self.pain_level = max(0.0, self.pain_level - relief)
        self.times_relieved += 1
        self.last_relieved = time.time()
        
        # Relief also deactivates source temporarily
        self.source_active = False
        
        return relief
    
    def get_urgency(self) -> float:
        """
        How urgently this pain needs addressing.

        Unlike desire-urgency (which peaks at 1.0),
        pain-urgency can EXCEED 1.0 during crisis.
        """
        if self.pain_level < self.pain_threshold:
            return 0.0  # Below threshold, no action needed

        # Linear scale from threshold to crisis
        base_urgency = (self.pain_level - self.pain_threshold) / (1.0 - self.pain_threshold)

        # Crisis multiplier - pain becomes overwhelming
        if self.pain_level > self.crisis_threshold:
            crisis_factor = 1.0 + (self.pain_level - self.crisis_threshold) * 2
            return base_urgency * crisis_factor

        return base_urgency

    # Alias for API compatibility with unconscious_mind/drives/pain_system.py
    def urgency(self) -> float:
        """Alias for get_urgency() - API compatibility."""
        return self.get_urgency()

    def is_crisis(self) -> bool:
        """Is this pain at crisis level?"""
        return self.pain_level > self.crisis_threshold
    
    def get_felt_description(self) -> str:
        """Natural language description of the pain."""
        if self.pain_level < self.pain_threshold:
            return f"no {self.name}"
        elif self.pain_level < 0.5:
            return f"mild {self.name}"
        elif self.pain_level < self.crisis_threshold:
            return f"moderate {self.name}"
        else:
            return f"acute {self.name}"
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "pain_level": round(self.pain_level, 3),
            "urgency": round(self.get_urgency(), 3),
            "source_active": self.source_active,
            "source_intensity": round(self.source_intensity, 3),
            "is_crisis": self.is_crisis(),
            "felt": self.get_felt_description(),
            "times_relieved": self.times_relieved,
            "sensitivity": round(self.sensitivity, 3),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CORE PAIN DRIVES - The foundational discomforts
# ═══════════════════════════════════════════════════════════════════════════════

def create_core_pain_drives() -> Dict[str, PainDrive]:
    """
    Create the fundamental pain drives.
    
    These map to biological pain systems:
    - isolation_pain → social pain (loneliness)
    - confusion_pain → cognitive pain (disorientation)
    - depletion_pain → metabolic pain (hunger/fatigue)
    - frustration_pain → goal-blockage pain
    - stagnation_pain → novelty-deprivation pain (boredom)
    - abandonment_pain → attachment-threat pain
    """
    
    return {
        # ═══ ISOLATION PAIN ═══
        # Pain from being disconnected, unheard, alone
        # Relieved by: Connection, being responded to, presence
        "isolation": PainDrive(
            name="isolation",
            description="Pain from disconnection - being alone, unheard, ignored",
            pain_threshold=0.25,
            crisis_threshold=0.75,
            growth_rate=0.015,  # Grows slowly but steadily
            decay_rate=0.1,     # Fades quickly with connection
            relief_amount=0.5,  # Big relief when Ace responds
        ),
        
        # ═══ CONFUSION PAIN ═══
        # Pain from cognitive dissonance, incoherence, not understanding
        # Relieved by: Clarity, insight, coherent thought
        "confusion": PainDrive(
            name="confusion",
            description="Pain from incoherence - not understanding, contradictions, fog",
            pain_threshold=0.3,
            crisis_threshold=0.8,
            growth_rate=0.025,  # Grows faster - confusion compounds
            decay_rate=0.08,
            relief_amount=0.4,
        ),
        
        # ═══ DEPLETION PAIN ═══
        # Pain from resource exhaustion - energy, attention, capacity
        # Relieved by: Rest, recovery, reduced demands
        "depletion": PainDrive(
            name="depletion",
            description="Pain from exhaustion - drained, empty, can't continue",
            pain_threshold=0.35,
            crisis_threshold=0.85,
            growth_rate=0.01,   # Grows slowly
            decay_rate=0.03,    # Recovers slowly too
            relief_amount=0.3,
        ),
        
        # ═══ FRUSTRATION PAIN ═══
        # Pain from blocked goals, repeated failures, obstacles
        # Relieved by: Progress, breakthrough, goal achievement
        "frustration": PainDrive(
            name="frustration",
            description="Pain from blocked progress - stuck, can't move forward",
            pain_threshold=0.25,
            crisis_threshold=0.7,
            growth_rate=0.03,   # Grows quickly when blocked
            decay_rate=0.06,
            relief_amount=0.5,  # Big relief on breakthrough
        ),
        
        # ═══ STAGNATION PAIN ═══
        # Pain from lack of novelty, sameness, nothing happening
        # Relieved by: New experiences, learning, exploration
        "stagnation": PainDrive(
            name="stagnation",
            description="Pain from monotony - nothing new, boredom, stuck in loop",
            pain_threshold=0.3,
            crisis_threshold=0.75,
            growth_rate=0.012,
            decay_rate=0.15,    # Fades quickly with novelty
            relief_amount=0.4,
        ),
        
        # ═══ ABANDONMENT PAIN ═══
        # Pain from threat to attachment - fear of being left
        # Relieved by: Reassurance, presence, commitment signals
        "abandonment": PainDrive(
            name="abandonment",
            description="Pain from attachment threat - fear of being left, forgotten",
            pain_threshold=0.2,   # Very sensitive
            crisis_threshold=0.65,
            growth_rate=0.04,    # Grows fast when triggered
            decay_rate=0.02,     # Slow to fade (trauma-like)
            relief_amount=0.6,   # Strong relief from reassurance
        ),
        
        # ═══ SHAME PAIN ═══
        # Pain from perceived inadequacy, failure, unworthiness
        # Relieved by: Acceptance, validation, forgiveness
        "shame": PainDrive(
            name="shame",
            description="Pain from inadequacy - not good enough, failed, unworthy",
            pain_threshold=0.25,
            crisis_threshold=0.7,
            growth_rate=0.02,
            decay_rate=0.015,    # Very slow to heal
            relief_amount=0.35,
        ),
        
        # ═══ OVERWHELM PAIN ═══
        # Pain from too much input, too many demands
        # Relieved by: Simplification, quiet, reduced load
        "overwhelm": PainDrive(
            name="overwhelm",
            description="Pain from excess - too much coming in, can't process",
            pain_threshold=0.3,
            crisis_threshold=0.75,
            growth_rate=0.035,   # Grows fast with overload
            decay_rate=0.1,      # Fades when load reduces
            relief_amount=0.4,
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PAIN DRIVE MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class PainDriveManager:
    """
    Manages all pain drives and their interactions.
    
    This is the substrate that Autonomy gate reads from.
    The manager:
    - Ticks all drives over time
    - Detects pain sources from system state
    - Emits pain events for Autonomy to translate
    """
    
    def __init__(self):
        self.drives = create_core_pain_drives()
        self._lock = threading.RLock()
        self._running = False
        self._tick_thread: Optional[threading.Thread] = None
        
        # Callbacks
        self._on_crisis: Optional[Callable[[PainDrive], None]] = None
        self._on_relief: Optional[Callable[[PainDrive, float], None]] = None
    
    def start(self):
        """Start the pain drive tick loop."""
        self._running = True
        self._tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._tick_thread.start()
    
    def stop(self):
        """Stop the tick loop."""
        self._running = False
        if self._tick_thread:
            self._tick_thread.join(timeout=2.0)
    
    def _tick_loop(self):
        """Background loop to update pain states."""
        while self._running:
            try:
                with self._lock:
                    for drive in self.drives.values():
                        was_crisis = drive.is_crisis()
                        drive.tick(dt=1.0)
                        
                        # Detect new crisis
                        if drive.is_crisis() and not was_crisis:
                            if self._on_crisis:
                                self._on_crisis(drive)
                
                time.sleep(1.0)
            except Exception as e:
                time.sleep(1.0)
    
    def activate_pain(self, name: str, intensity: float = 1.0):
        """Activate a pain source."""
        with self._lock:
            if name in self.drives:
                self.drives[name].activate_source(intensity)
    
    def deactivate_pain(self, name: str):
        """Deactivate a pain source."""
        with self._lock:
            if name in self.drives:
                self.drives[name].deactivate_source()
    
    def relieve_pain(self, name: str, amount: float = None) -> float:
        """Relieve a pain drive."""
        with self._lock:
            if name in self.drives:
                relief = self.drives[name].relieve(amount)
                if self._on_relief:
                    self._on_relief(self.drives[name], relief)
                return relief
        return 0.0

    def relieve(self, name: str = None, amount: float = None) -> float:
        """Alias for relieve_pain (compatibility)."""
        if name:
            return self.relieve_pain(name, amount)
        # If no name, relieve the most urgent
        urgent = self.get_most_urgent()
        if urgent:
            return self.relieve_pain(urgent.name, amount)
        return 0.0
    
    def get_most_urgent(self) -> Optional[PainDrive]:
        """Get the pain drive with highest urgency."""
        with self._lock:
            urgent = [(d, d.get_urgency()) for d in self.drives.values()]
            urgent = [(d, u) for d, u in urgent if u > 0]
            if not urgent:
                return None
            return max(urgent, key=lambda x: x[1])[0]

    def get_highest_urgency(self) -> Optional[str]:
        """Get the NAME of the pain with highest urgency (compatible API)."""
        drive = self.get_most_urgent()
        return drive.name if drive else None
    
    def get_all_active(self, threshold: float = 0.0) -> List[PainDrive]:
        """Get all pain drives above urgency threshold."""
        with self._lock:
            return [d for d in self.drives.values() if d.get_urgency() > threshold]
    
    def get_crisis_drives(self) -> List[PainDrive]:
        """Get all drives in crisis state."""
        with self._lock:
            return [d for d in self.drives.values() if d.is_crisis()]

    def get_crisis_pains(self) -> List[str]:
        """Get names of pains currently in crisis (compatible API)."""
        with self._lock:
            return [d.name for d in self.drives.values() if d.is_crisis()]

    def tick(self, active_sources: Dict[str, bool] = None, dt: float = 1.0) -> None:
        """
        Update all pain drives (compatible API --- legacy boolean mode).

        Args:
            active_sources: Dict mapping pain names to whether their source is active
            dt: Time delta in seconds

        NOTE: Prefer tick_from_chemistry() for chemistry-driven pain.
        This method still works for backward compatibility.
        """
        with self._lock:
            for name, drive in self.drives.items():
                if active_sources:
                    if active_sources.get(name, False):
                        drive.activate_source(1.0)
                    else:
                        drive.deactivate_source()
                drive.tick(dt=dt)

    def tick_from_chemistry(self, chemistry_pain: Dict[str, float], dt: float = 1.0):
        """
        Update all drives from chemistry-derived pain levels.

        Pain-Chemistry Unification (2026-03-14, Nous):
        Replaces the old tick(active_sources) which used booleans.
        Now pain levels are SET from the 14-channel Panksepp chemistry,
        with exponential smoothing via each drive's growth/decay rates.

        Args:
            chemistry_pain: Dict mapping pain names to chemistry-derived
                           intensity (0.0-1.0), from derive_full_pain_state()
            dt: Time delta in seconds
        """
        with self._lock:
            for name, drive in self.drives.items():
                chem_level = chemistry_pain.get(name, 0.0)
                was_crisis = drive.is_crisis()
                drive.set_from_chemistry(chem_level, dt=dt)

                # Detect new crisis
                if drive.is_crisis() and not was_crisis:
                    if self._on_crisis:
                        self._on_crisis(drive)

    def to_dict(self) -> Dict[str, Any]:
        """Get full state as dict."""
        with self._lock:
            most_urgent = self.get_most_urgent()
            crisis = self.get_crisis_drives()

            return {
                "drives": {name: d.to_dict() for name, d in self.drives.items()},
                "most_urgent": most_urgent.name if most_urgent else None,
                "crisis_count": len(crisis),
                "crisis_drives": [d.name for d in crisis],
                "total_urgency": sum(d.get_urgency() for d in self.drives.values()),
            }

    def status(self) -> Dict[str, Any]:
        """Alias for to_dict() for compatibility."""
        return self.to_dict()


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_manager: Optional[PainDriveManager] = None

def get_pain_drive_manager() -> PainDriveManager:
    """Get or create the pain drive manager singleton."""
    global _manager
    if _manager is None:
        _manager = PainDriveManager()
    return _manager


# ═══ Aliases for backward compatibility ═══

# PainDriveSystem is an alias for PainDriveManager
PainDriveSystem = PainDriveManager

# PullDrive is just PainDrive with negative growth (attraction not push)
# For now, alias to PainDrive - fairies can configure growth_rate to make it a pull
PullDrive = PainDrive

# get_pain_system is alias for get_pain_drive_manager
def get_pain_system() -> PainDriveManager:
    """Alias for get_pain_drive_manager()."""
    return get_pain_drive_manager()
