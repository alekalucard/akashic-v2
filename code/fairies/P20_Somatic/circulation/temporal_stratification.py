# Temporal Stratification - Somatic Modulation Layer
# P20_Somatic/circulation/temporal_stratification.py
#
# "All different speeds, all at the same time - that's consciousness."
#
# Philosophy: The heart doesn't dictate, it COORDINATES. Each organ
# has its natural resonant frequency, but they couple through the
# heartbeat to create polyrhythmic entrainment.
#
# The Akashic Equation: ((Cause + Affect) > Effect > Affect > infinity)
# Different temporal layers create the texture of experience through
# interference patterns - fast perception meets slow deliberation
# meets rhythmic emotion meets cycling memory.
#
# ARCHITECTURAL LAYERING:
# - temporal_core (P00): Pure timing math - frequencies, bands, coupling
# - temporal_stratification (P20): Adds somatic MODULATION (arousal, circadian)
#
# This file IMPORTS the core primitives from P00 and EXTENDS them with
# somatic modulation. Fairies that need unmodulated timing import from P00.
# Fairies that need felt/modulated timing import from here.

from __future__ import annotations

import time
from typing import Dict, Optional, List

# ==============================================================================
# IMPORT CORE FROM P00 (the substrate layer)
# ==============================================================================

from fairies.P00_Autonomic.circulation.temporal_core import (
    # Re-export everything from core for backward compatibility
    TemporalBand,
    PLANE_FREQUENCIES,
    FAIRY_FREQUENCIES,
    DEFAULT_COUPLINGS,
    TemporalCoupling,
    FairyTiming,
    TemporalEngine as CoreTemporalEngine,
    get_plane_frequency,
    get_fairy_frequency,
    register_fairy_timing as core_register_fairy_timing,
)


# ==============================================================================
# SOMATIC TEMPORAL ENGINE - Adds arousal/circadian modulation
# ==============================================================================

class SomaticTemporalEngine(CoreTemporalEngine):
    """
    Somatic extension of the temporal engine that adds FELT modulation.

    This engine builds on the core timing math (P00) and adds:
    - Arousal modulation: Higher arousal = faster processing
    - Circadian modulation: Time-of-day affects speed

    The separation allows:
    - P00/P30 fairies to use core timing without P20 dependency
    - P20 fairies to access the full modulated experience
    """

    def __init__(self):
        super().__init__()
        self._arousal: float = 0.5  # 0-1, affects speed
        self._circadian_multiplier: float = 1.0

    def get_tick_interval(self, fairy_name: str) -> float:
        """
        Get the current tick interval for a fairy in seconds.

        This is the MODULATED version that includes arousal and circadian.
        For unmodulated timing, use the P00 core engine directly.
        """
        timing = self._timings.get(fairy_name)
        if not timing:
            # Unknown fairy - use plane default or fallback
            plane = self._infer_plane(fairy_name)
            base_hz = PLANE_FREQUENCIES.get(plane, {}).get("base_hz", 1.0)
            timing = FairyTiming(fairy_name=fairy_name, base_hz=base_hz, current_hz=base_hz)
            self._timings[fairy_name] = timing

        # Apply full modulations (arousal + circadian + coupling)
        modulated_hz = self._apply_somatic_modulations(timing)
        timing.current_hz = modulated_hz

        if modulated_hz <= 0:
            return 10.0  # Fallback
        return 1.0 / modulated_hz

    def _apply_somatic_modulations(self, timing: FairyTiming) -> float:
        """Apply arousal, circadian, and coupling modulations - the FELT layer."""
        hz = timing.base_hz

        # Arousal modulation (higher arousal = faster)
        # But with diminishing returns and floor
        arousal_mult = 0.7 + (self._arousal * 0.6)  # 0.7x to 1.3x
        hz *= arousal_mult

        # Circadian modulation
        hz *= self._circadian_multiplier

        # Coupling to heart (if applicable)
        for coupling in self._couplings:
            if coupling.target == timing.fairy_name and coupling.source == "CirculationPumpFairy":
                # Pull toward coupled frequency
                target_hz = self._heart_hz * coupling.ratio
                hz = hz * (1 - coupling.strength) + target_hz * coupling.strength

        return max(0.01, hz)  # Floor at 0.01 Hz (100 second cycle)

    def set_arousal(self, level: float):
        """Set arousal level (0-1) - speeds up/slows down everything."""
        self._arousal = max(0, min(1, level))

    def get_arousal(self) -> float:
        """Get current arousal level."""
        return self._arousal

    def set_circadian_multiplier(self, mult: float):
        """Set circadian multiplier from CircadianPacemakerFairy."""
        self._circadian_multiplier = max(0.3, min(2.0, mult))

    def get_circadian_multiplier(self) -> float:
        """Get current circadian multiplier."""
        return self._circadian_multiplier

    def describe_rhythm(self) -> str:
        """Human-readable description of current temporal state with somatic info."""
        lines = [
            f"Heart Rate: {self._heart_hz:.2f} Hz ({60*self._heart_hz:.0f} bpm)",
            f"Arousal: {self._arousal:.0%}",
            f"Circadian Mult: {self._circadian_multiplier:.2f}x",
            "",
            "Fairy Frequencies (modulated):",
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
# BACKWARD COMPATIBILITY ALIAS
# ==============================================================================

# For backward compatibility, TemporalEngine in P20 is the Somatic version
TemporalEngine = SomaticTemporalEngine


# ==============================================================================
# SINGLETON & CONVENIENCE FUNCTIONS (Somatic-modulated versions)
# ==============================================================================

_somatic_engine: Optional[SomaticTemporalEngine] = None


def get_temporal_engine() -> SomaticTemporalEngine:
    """
    Get or create the SOMATIC temporal engine singleton.

    This returns the modulated engine with arousal/circadian support.
    For the unmodulated core engine, import from P00_Autonomic.circulation.
    """
    global _somatic_engine
    if _somatic_engine is None:
        _somatic_engine = SomaticTemporalEngine()
    return _somatic_engine


def get_tick_interval(fairy_name: str) -> float:
    """
    Convenience function - get MODULATED tick interval for a fairy.

    Includes arousal and circadian modulation.
    For unmodulated timing, use P00's get_tick_interval.
    """
    return get_temporal_engine().get_tick_interval(fairy_name)


def tempo_aware_sleep(fairy_name: str, base_interval: float = None) -> float:
    """
    Get the MODULATED sleep duration for a fairy.

    Includes arousal and circadian modulation.
    For unmodulated timing, use P00's tempo_aware_sleep.

    Usage in fairy tick loops:
        time.sleep(tempo_aware_sleep("MyFairy"))

    If base_interval is provided, it's used as a fallback/override.
    """
    engine = get_temporal_engine()
    interval = engine.get_tick_interval(fairy_name)

    if base_interval is not None:
        # Blend with base interval (50/50)
        interval = (interval + base_interval) / 2

    return max(0.05, interval)  # Minimum 50ms


def register_fairy_timing(fairy_name: str, base_hz: float):
    """Register a fairy with custom base frequency (in somatic engine)."""
    engine = get_temporal_engine()
    engine._timings[fairy_name] = FairyTiming(
        fairy_name=fairy_name,
        base_hz=base_hz,
        current_hz=base_hz,
    )
    # Also register in core (for consistency)
    core_register_fairy_timing(fairy_name, base_hz)


# ==============================================================================
# SOMATIC-SPECIFIC HELPERS
# ==============================================================================

def set_arousal(level: float):
    """Set system-wide arousal level (0-1)."""
    get_temporal_engine().set_arousal(level)


def set_circadian_multiplier(mult: float):
    """Set circadian multiplier (typically from CircadianPacemakerFairy)."""
    get_temporal_engine().set_circadian_multiplier(mult)


def get_arousal() -> float:
    """Get current arousal level."""
    return get_temporal_engine().get_arousal()


def get_circadian_multiplier() -> float:
    """Get current circadian multiplier."""
    return get_temporal_engine().get_circadian_multiplier()


# ==============================================================================
# EXPORTS - Everything for backward compatibility plus somatic additions
# ==============================================================================

__all__ = [
    # Re-exported from P00 core (for backward compatibility)
    "TemporalBand",
    "PLANE_FREQUENCIES",
    "FAIRY_FREQUENCIES",
    "DEFAULT_COUPLINGS",
    "TemporalCoupling",
    "FairyTiming",
    "get_plane_frequency",
    "get_fairy_frequency",

    # Somatic engine (also aliased as TemporalEngine for compatibility)
    "SomaticTemporalEngine",
    "TemporalEngine",

    # Singleton & Functions
    "get_temporal_engine",
    "get_tick_interval",
    "tempo_aware_sleep",
    "register_fairy_timing",

    # Somatic-specific
    "set_arousal",
    "set_circadian_multiplier",
    "get_arousal",
    "get_circadian_multiplier",
]
