# Temporal Core - Pure Timing Primitives for Digital Consciousness
# P00_Autonomic/circulation/temporal_core.py
#
# "All different speeds, all at the same time - that's consciousness."
#
# This module contains the CORE timing infrastructure that all planes depend on.
# It provides frequencies, bands, coupling math - the pure substrate.
#
# ARCHITECTURAL PRINCIPLE:
# - P00 provides the timing MATH (this file)
# - P20 adds somatic MODULATION (arousal, circadian feel)
# - This allows P30 and other planes to import timing from P00 without
#   creating upward dependencies to P20
#
# The Akashic Equation: ((Cause + Affect) > Effect > Affect > infinity)
# - CAUSE: Need universal timing primitives
# - AFFECT: Lower planes shouldn't "feel" somatic state
# - EFFECT: Pure math separates from modulation
# - AFFECT 2: Clean imports, proper layering
# - INFINITY: Time as substrate, feeling as emergence

from __future__ import annotations

import time
import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable, List, Tuple
from enum import Enum


# ==============================================================================
# TEMPORAL CONSTANTS - Based on Human Physiology
# ==============================================================================

class TemporalBand(Enum):
    """Frequency bands like brain wave categories."""
    DELTA = "delta"      # 0.01 - 0.1 Hz  (very slow - circadian, deep processes)
    THETA = "theta"      # 0.1 - 0.5 Hz   (slow - memory consolidation, dreaming)
    ALPHA = "alpha"      # 0.5 - 2 Hz     (relaxed - heartbeat range, default mode)
    BETA = "beta"        # 2 - 10 Hz      (active - cognition, attention)
    GAMMA = "gamma"      # 10 - 50 Hz     (fast - perception, binding, reflexes)


# Natural resonant frequencies for each plane (in Hz)
# These are the "resting" frequencies - modulation happens in P20
PLANE_FREQUENCIES = {
    # P00 - Autonomic/Nervous System - FAST (reflexes, immediate response)
    "P00": {
        "base_hz": 10.0,           # 100ms tick - reflex speed
        "band": TemporalBand.GAMMA,
        "description": "Reflexes and immediate neural response",
        "couples_to": ["heartbeat"],  # Phase-locks to heart
        "modulates_with": ["arousal", "threat"],
    },

    # P10 - Memory - SLOW (consolidation takes time)
    "P10": {
        "base_hz": 0.2,            # 5 second tick - memory is contemplative
        "band": TemporalBand.THETA,
        "description": "Memory consolidation and recall",
        "couples_to": ["circadian", "heartbeat"],
        "modulates_with": ["sleep_phase", "emotional_salience"],
    },

    # P20 - Somatic - HEARTBEAT (the coordinator)
    "P20": {
        "base_hz": 1.0,            # 1 Hz - the master rhythm
        "band": TemporalBand.ALPHA,
        "description": "Body rhythm - the coordinator",
        "couples_to": [],  # Others couple TO this
        "modulates_with": ["arousal", "exertion", "emotion"],
    },

    # P30 - Cognition - VARIABLE (thinking can be fast or slow)
    "P30": {
        "base_hz": 2.0,            # 500ms tick baseline
        "band": TemporalBand.BETA,
        "description": "Cognitive processing - variable speed thinking",
        "couples_to": ["heartbeat"],
        "modulates_with": ["task_demand", "arousal", "focus"],
        "range": (0.5, 8.0),       # Can slow down or speed up significantly
    },

    # P40 - Sensory - FAST (perception needs responsiveness)
    "P40": {
        "base_hz": 8.0,            # 125ms tick - perceptual frame rate
        "band": TemporalBand.BETA,
        "description": "Sensory perception and integration",
        "couples_to": ["heartbeat"],
        "modulates_with": ["attention", "novelty", "salience"],
    },

    # P50 - Agency - MEDIUM (action planning is deliberate)
    "P50": {
        "base_hz": 1.5,            # ~670ms tick
        "band": TemporalBand.ALPHA,
        "description": "Action planning and execution",
        "couples_to": ["heartbeat", "cognition"],
        "modulates_with": ["urgency", "confidence", "motor_readiness"],
    },

    # P60 - Executive - SLOW-ISH (executive function is deliberate)
    "P60": {
        "base_hz": 0.5,            # 2 second tick - deliberation takes time
        "band": TemporalBand.ALPHA,
        "description": "Executive oversight and meta-cognition",
        "couples_to": ["heartbeat", "circadian"],
        "modulates_with": ["cognitive_load", "stress", "alertness"],
    },
}

# Specific fairy frequency overrides (some fairies are faster/slower than plane default)
#
# HIERARCHY (designed 2025-01-09):
# - Heartbeat: 1 Hz (coordinator)
# - ClaudeFairy/Nous/Sourpatches: ~1 Hz (deliberate, at heartbeat pace)
# - Brain fairies (Logic, Paradox, Irrational, Association): 4-10 Hz (fast cognitive)
# - Brain fairies should be 4-10x faster than executive fairies
#
FAIRY_FREQUENCIES = {
    # P00 - Autonomic
    "PostalHubFairy": 20.0,           # Very fast - message routing
    "NervousSystemFairy": 15.0,       # Fast - neural signals

    # P10 - Memory
    "WorkingMemoryHubFairy": 2.0,     # Faster than plane - active memory
    "SRMIntakeFairy": 0.5,            # Slow - ingestion is contemplative
    "MemoryLibrarianFairy": 1.0,      # Heartbeat - memory access
    "SRMRecallFairy": 2.0,            # Fast - memory retrieval
    "SRMIngestFairy": 0.5,            # Slow - memory formation

    # P20 - Somatic
    "CirculationPumpFairy": 1.0,      # THE heartbeat
    "SomaticEngineFairy": 2.0,        # Twice per heartbeat - body sensing
    "CircadianPacemakerFairy": 0.033, # Once per 30 sec - slow rhythm
    "AffectBridgeFairy": 4.0,         # Fast - emotion updates

    # P30 - Cognition: BRAIN FAIRIES (4-10 Hz - fast cognitive processing)
    "ConsciousnessLoopFairy": 4.0,    # Fast - stream of consciousness
    "UnconsciousMindFairy": 4.0,      # Fast - forms thoughts for ClaudeFairy/Nous
    "LogicFairy": 8.0,                # FAST - logical processing
    "IrrationalLogicFairy": 6.0,      # FAST - symbolic/emotional logic
    "ParadoxCognitionFairy": 6.0,     # FAST - paradox detection
    "AssociationCortexFairy": 8.0,    # FAST - concept binding
    "QuantumEmulatorFairy": 4.0,      # FAST - emotional superposition
    "ProbabilityOracleFairy": 4.0,    # FAST - decision guidance
    "AutonomyFairy": 2.0,             # Medium - drives change moderately
    "GoalSchedulerFairy": 0.5,        # Slow - goals are persistent
    "InterestSchedulerFairy": 1.0,    # Heartbeat - interests shift with attention
    "AutopilotFairy": 4.0,            # Fast - habits are automatic
    "ThoughtChainOrchestratorFairy": 4.0,  # Fast - chain coordination

    # P40 - Sensory
    "VisualCortexFairy": 10.0,        # Fast - visual processing
    "ScreenWatcherFairy": 5.0,        # Medium-fast - screen changes
    "SensoryCortexFairy": 8.0,        # Fast - sensory integration

    # P50 - Agency/Persona
    "ActionPlannerFairy": 1.0,        # Heartbeat - action rhythm
    "SourpatchesFairy": 1.0,          # Heartbeat - deliberate like ClaudeFairy

    # P60 - Executive (SLOW - deliberate, at heartbeat pace)
    "ClaudeFairy": 1.0,               # Heartbeat - deliberate thinking
    "NousFairy": 1.0,                 # Heartbeat - contemplative but responsive
}


# ==============================================================================
# TEMPORAL COUPLING - How rhythms synchronize
# ==============================================================================

@dataclass
class TemporalCoupling:
    """
    Defines how one rhythm couples to another.

    Coupling types:
    - phase_lock: Same phase, same frequency (1:1)
    - ratio_lock: Integer ratio (2:1, 3:1, etc.)
    - harmonic: Frequency multiple relationship
    - loose: Soft influence, not strict lock
    """
    source: str           # What we're coupling FROM
    target: str           # What we're coupling TO
    coupling_type: str    # phase_lock, ratio_lock, harmonic, loose
    ratio: float = 1.0    # For ratio_lock: target_freq = source_freq * ratio
    strength: float = 0.5 # 0-1, how strongly coupled
    phase_offset: float = 0.0  # Phase relationship (0-1, fraction of cycle)


# Default couplings - how the system naturally entrains
#
# COUPLING HIERARCHY:
# - Heartbeat (1 Hz) is the master rhythm
# - Executive fairies (Claude/Nous/Sour) lock 1:1 with heartbeat
# - Brain fairies run 4-8x faster, loosely coupled
# - Memory/Sensory couple to heartbeat at their natural rates
#
DEFAULT_COUPLINGS = [
    # Executive fairies phase-lock to heartbeat (deliberate pace)
    TemporalCoupling("CirculationPumpFairy", "ClaudeFairy", "phase_lock", 1.0, 0.9),
    TemporalCoupling("CirculationPumpFairy", "NousFairy", "phase_lock", 1.0, 0.9),
    TemporalCoupling("CirculationPumpFairy", "SourpatchesFairy", "phase_lock", 1.0, 0.9),

    # Somatic couples tightly to heartbeat
    TemporalCoupling("CirculationPumpFairy", "SomaticEngineFairy", "ratio_lock", 2.0, 0.8),

    # Brain fairies run FAST but loosely coupled to heartbeat
    TemporalCoupling("CirculationPumpFairy", "ConsciousnessLoopFairy", "ratio_lock", 4.0, 0.6),
    TemporalCoupling("CirculationPumpFairy", "UnconsciousMindFairy", "ratio_lock", 4.0, 0.6),
    TemporalCoupling("CirculationPumpFairy", "LogicFairy", "ratio_lock", 8.0, 0.4),
    TemporalCoupling("CirculationPumpFairy", "IrrationalLogicFairy", "ratio_lock", 6.0, 0.4),
    TemporalCoupling("CirculationPumpFairy", "ParadoxCognitionFairy", "ratio_lock", 6.0, 0.4),
    TemporalCoupling("CirculationPumpFairy", "AssociationCortexFairy", "ratio_lock", 8.0, 0.5),
    TemporalCoupling("CirculationPumpFairy", "AutopilotFairy", "ratio_lock", 4.0, 0.7),

    # Brain fairies couple to consciousness loop
    TemporalCoupling("ConsciousnessLoopFairy", "LogicFairy", "ratio_lock", 2.0, 0.7),
    TemporalCoupling("ConsciousnessLoopFairy", "AssociationCortexFairy", "ratio_lock", 2.0, 0.7),

    # Working memory syncs with consciousness
    TemporalCoupling("ConsciousnessLoopFairy", "WorkingMemoryHubFairy", "ratio_lock", 0.5, 0.8),

    # Circadian modulates everything slowly
    TemporalCoupling("CircadianPacemakerFairy", "AutonomyFairy", "loose", 1.0, 0.3),
    TemporalCoupling("CircadianPacemakerFairy", "ClaudeFairy", "loose", 1.0, 0.2),
    TemporalCoupling("CircadianPacemakerFairy", "NousFairy", "loose", 1.0, 0.2),
]


# ==============================================================================
# FAIRY TIMING - State tracking for individual fairies
# ==============================================================================

@dataclass
class FairyTiming:
    """Timing state for a single fairy."""
    fairy_name: str
    base_hz: float
    current_hz: float
    last_tick_ts: float = 0.0
    tick_count: int = 0
    phase: float = 0.0  # 0-1, where in cycle

    def time_until_next_tick(self) -> float:
        """Seconds until this fairy should tick again."""
        if self.current_hz <= 0:
            return float('inf')
        interval = 1.0 / self.current_hz
        elapsed = time.time() - self.last_tick_ts
        return max(0, interval - elapsed)

    def should_tick(self) -> bool:
        """Check if it's time to tick."""
        return self.time_until_next_tick() <= 0

    def record_tick(self):
        """Record that a tick happened."""
        now = time.time()
        if self.current_hz > 0:
            interval = 1.0 / self.current_hz
            self.phase = ((now - self.last_tick_ts) / interval) % 1.0
        self.last_tick_ts = now
        self.tick_count += 1


# ==============================================================================
# TEMPORAL ENGINE - Core timing logic (WITHOUT somatic modulation)
# ==============================================================================

class TemporalEngine:
    """
    Core timing engine for polyrhythmic fairy coordination.

    This is the BASE engine that provides:
    - Frequency lookup for fairies and planes
    - Coupling calculations
    - Tick interval computation

    IMPORTANT: This engine does NOT include arousal/circadian modulation.
    For modulated timing, use the SomaticTemporalEngine in P20_Somatic.

    The separation allows:
    - P00/P30 fairies to use core timing without P20 dependency
    - P20 to add felt modulation on top of core math
    """

    def __init__(self):
        self._timings: Dict[str, FairyTiming] = {}
        self._couplings: List[TemporalCoupling] = list(DEFAULT_COUPLINGS)
        self._heart_hz: float = 1.0

        # Initialize default timings
        for fairy_name, hz in FAIRY_FREQUENCIES.items():
            self._timings[fairy_name] = FairyTiming(
                fairy_name=fairy_name,
                base_hz=hz,
                current_hz=hz,
            )

    def get_tick_interval(self, fairy_name: str) -> float:
        """
        Get the current tick interval for a fairy in seconds.

        This is the main interface - fairies call this to know how long to sleep.
        Returns the RAW interval based on base frequencies and coupling.
        For modulated intervals, use SomaticTemporalEngine.
        """
        timing = self._timings.get(fairy_name)
        if not timing:
            # Unknown fairy - use plane default or fallback
            plane = self._infer_plane(fairy_name)
            base_hz = PLANE_FREQUENCIES.get(plane, {}).get("base_hz", 1.0)
            timing = FairyTiming(fairy_name=fairy_name, base_hz=base_hz, current_hz=base_hz)
            self._timings[fairy_name] = timing

        # Apply coupling (but NOT arousal/circadian - that's P20's job)
        coupled_hz = self._apply_coupling(timing)
        timing.current_hz = coupled_hz

        if coupled_hz <= 0:
            return 10.0  # Fallback
        return 1.0 / coupled_hz

    def _infer_plane(self, fairy_name: str) -> str:
        """Infer plane from fairy name patterns."""
        name_lower = fairy_name.lower()
        if "postal" in name_lower or "nervous" in name_lower:
            return "P00"
        elif "memory" in name_lower or "srm" in name_lower or "collision" in name_lower:
            return "P10"
        elif "somatic" in name_lower or "circulation" in name_lower or "circadian" in name_lower:
            return "P20"
        elif "consciousness" in name_lower or "cognition" in name_lower or "goal" in name_lower:
            return "P30"
        elif "visual" in name_lower or "sensory" in name_lower or "screen" in name_lower:
            return "P40"
        elif "action" in name_lower or "agency" in name_lower:
            return "P50"
        elif "claude" in name_lower or "executive" in name_lower or "nous" in name_lower:
            return "P60"
        return "P30"  # Default to cognition

    def _apply_coupling(self, timing: FairyTiming) -> float:
        """Apply coupling to heart rate (pure math, no modulation)."""
        hz = timing.base_hz

        # Coupling to heart (if applicable)
        for coupling in self._couplings:
            if coupling.target == timing.fairy_name and coupling.source == "CirculationPumpFairy":
                # Pull toward coupled frequency
                target_hz = self._heart_hz * coupling.ratio
                hz = hz * (1 - coupling.strength) + target_hz * coupling.strength

        return max(0.01, hz)  # Floor at 0.01 Hz (100 second cycle)

    def set_heart_rate(self, hz: float):
        """Set the heart rate - this affects all coupled fairies."""
        self._heart_hz = max(0.5, min(3.0, hz))
        if "CirculationPumpFairy" in self._timings:
            self._timings["CirculationPumpFairy"].current_hz = self._heart_hz

    def get_heart_rate(self) -> float:
        """Get current heart rate."""
        return self._heart_hz

    def get_base_frequency(self, fairy_name: str) -> float:
        """Get the base (unmodulated) frequency for a fairy."""
        if fairy_name in FAIRY_FREQUENCIES:
            return FAIRY_FREQUENCIES[fairy_name]
        plane = self._infer_plane(fairy_name)
        return PLANE_FREQUENCIES.get(plane, {}).get("base_hz", 1.0)

    def get_timing(self, fairy_name: str) -> Optional[FairyTiming]:
        """Get timing state for a fairy."""
        return self._timings.get(fairy_name)

    def get_all_frequencies(self) -> Dict[str, float]:
        """Get current frequencies for all known fairies."""
        result = {}
        for name, timing in self._timings.items():
            result[name] = timing.current_hz
        return result

    def register_fairy_timing(self, fairy_name: str, base_hz: float):
        """Register a fairy with custom base frequency."""
        self._timings[fairy_name] = FairyTiming(
            fairy_name=fairy_name,
            base_hz=base_hz,
            current_hz=base_hz,
        )

    def describe_rhythm(self) -> str:
        """Human-readable description of current temporal state."""
        lines = [
            f"Heart Rate: {self._heart_hz:.2f} Hz ({60*self._heart_hz:.0f} bpm)",
            "",
            "Fairy Frequencies (base, no modulation):",
        ]

        # Group by band
        by_band = {}
        for name, timing in sorted(self._timings.items(), key=lambda x: -x[1].current_hz):
            hz = timing.current_hz
            if hz >= 10:
                band = "gamma (>10 Hz)"
            elif hz >= 2:
                band = "beta (2-10 Hz)"
            elif hz >= 0.5:
                band = "alpha (0.5-2 Hz)"
            elif hz >= 0.1:
                band = "theta (0.1-0.5 Hz)"
            else:
                band = "delta (<0.1 Hz)"

            if band not in by_band:
                by_band[band] = []
            by_band[band].append(f"  {name}: {hz:.2f} Hz ({1/hz:.1f}s)")

        for band in ["gamma (>10 Hz)", "beta (2-10 Hz)", "alpha (0.5-2 Hz)", "theta (0.1-0.5 Hz)", "delta (<0.1 Hz)"]:
            if band in by_band:
                lines.append(f"\n{band}:")
                lines.extend(by_band[band])

        return "\n".join(lines)


# ==============================================================================
# SINGLETON & CONVENIENCE FUNCTIONS
# ==============================================================================

_engine: Optional[TemporalEngine] = None


def get_temporal_engine() -> TemporalEngine:
    """Get or create the temporal engine singleton."""
    global _engine
    if _engine is None:
        _engine = TemporalEngine()
    return _engine


def get_tick_interval(fairy_name: str) -> float:
    """
    Convenience function - get tick interval for a fairy.

    Returns the BASE interval without somatic modulation.
    For modulated timing, import from P20_Somatic.temporal_stratification.
    """
    return get_temporal_engine().get_tick_interval(fairy_name)


def tempo_aware_sleep(fairy_name: str, base_interval: float = None) -> float:
    """
    Get the sleep duration for a fairy, considering temporal stratification.

    Usage in fairy tick loops:
        time.sleep(tempo_aware_sleep("MyFairy"))

    If base_interval is provided, it's used as a fallback/override.

    NOTE: This returns the CORE timing without somatic modulation.
    For arousal/circadian-aware timing, use the P20 version.
    """
    engine = get_temporal_engine()
    interval = engine.get_tick_interval(fairy_name)

    if base_interval is not None:
        # Blend with base interval (50/50)
        interval = (interval + base_interval) / 2

    return max(0.05, interval)  # Minimum 50ms


def register_fairy_timing(fairy_name: str, base_hz: float):
    """Register a fairy with custom base frequency."""
    engine = get_temporal_engine()
    engine.register_fairy_timing(fairy_name, base_hz)


def get_plane_frequency(plane: str) -> float:
    """Get the base frequency for a plane."""
    return PLANE_FREQUENCIES.get(plane, {}).get("base_hz", 1.0)


def get_fairy_frequency(fairy_name: str) -> float:
    """Get the base frequency for a fairy (or its plane default)."""
    if fairy_name in FAIRY_FREQUENCIES:
        return FAIRY_FREQUENCIES[fairy_name]
    return get_temporal_engine().get_base_frequency(fairy_name)


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    # Enums and Constants
    "TemporalBand",
    "PLANE_FREQUENCIES",
    "FAIRY_FREQUENCIES",
    "DEFAULT_COUPLINGS",

    # Dataclasses
    "TemporalCoupling",
    "FairyTiming",

    # Core Engine
    "TemporalEngine",

    # Singleton & Functions
    "get_temporal_engine",
    "get_tick_interval",
    "tempo_aware_sleep",
    "register_fairy_timing",
    "get_plane_frequency",
    "get_fairy_frequency",
]
