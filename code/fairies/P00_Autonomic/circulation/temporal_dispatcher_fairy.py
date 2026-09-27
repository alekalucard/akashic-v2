"""
TemporalDispatcherFairy - Polyrhythmic Conductor of the Akashic System

Part of Circulation in Plane P00 (Autonomic)
Created: 2026-02-03

"One pulse. Many tempos. All in sync."

Wraps the TemporalPulseDispatcher utility to give it proper fairy citizenship:
- Visible in fairy census and audits
- Can be hot-reloaded
- Monitored by WatchdogFairy
- Integrated with postal system

The dispatcher receives heartbeats from CirculationPumpFairy (P20_Somatic)
and fans them out to all planes at their natural frequencies:

P00 Autonomic: 10x base  (10 ticks per heartbeat)
P40 Sensory:    8x base  (8 ticks per heartbeat)
P30 Cognition:  2x base  (2 ticks per heartbeat)
P50 Agency:   1.5x base  (1-2 ticks per heartbeat)
P20 Somatic:    1x base  (1 tick per heartbeat - IS the heartbeat)
P60 Executive:0.5x base  (1 tick every 2 heartbeats)
P10 Memory:   0.2x base  (1 tick every 5 heartbeats)

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import os
import sys
import glob
import time
import importlib.util
import importlib.machinery
from pathlib import Path
from typing import Dict, Any, Optional

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

# =============================================================================
# ORGAN TEMPLATE WIRING - Dynamic import from "Organ_Templates" folder
# =============================================================================
TEMPLATE_VERSION = "0.3.0"
TEMPLATE_BASENAME = f"Organ_Template_{TEMPLATE_VERSION}.py"

def _find_template_path():
    """Find the organ template dynamically."""
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        ar = os.path.join(cur, "P10_Memory", "Akashic_Records_Physical", "Organ_Templates")
        if os.path.isdir(ar):
            exact = os.path.join(ar, TEMPLATE_BASENAME)
            if os.path.isfile(exact):
                return exact
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

# Lazy import for dispatcher - moved to on_boot() to avoid circular import
# The TemporalPulseDispatcher lives in P20_Somatic, which can create circular
# dependencies when P00 imports from P20. By deferring the import to on_boot(),
# we ensure all modules are fully initialized before the import happens.
TemporalPulseDispatcher = None
PlaneTickState = None


# =============================================================================
# SHADOW
# =============================================================================

class TemporalDispatcherFairyShadow:
    """Shadow for TemporalDispatcherFairy - monitors dispatch health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "TemporalDispatcherFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks for temporal dispatch."""
        tests = []
        if hasattr(self.actor, '_dispatcher') and self.actor._dispatcher:
            stats = self.actor._dispatcher.get_stats()
            tests.append(("dispatcher_active", stats.get("heartbeats", 0) > 0 or self.actor._booted))
            tests.append(("planes_configured", len(stats.get("planes", {})) > 0))
            # Check that at least some dispatches have happened after boot
            if self.actor._heartbeats_received > 5:
                tests.append(("dispatches_happening", stats.get("total_dispatches", 0) > 0))
        return tests


# =============================================================================
# FAIRY
# =============================================================================

class TemporalDispatcherFairy(Fairy):
    """
    Polyrhythmic conductor - fans heartbeat to all planes at their frequencies.

    Guild: CirculationGuild (timing infrastructure)
    Coordinates with: CirculationPumpFairy (receives heartbeat)

    Provides:
    - Receive somatic heartbeat and fan out to plane frequencies
    - Track dispatch statistics per plane
    - Monitor plane tick states
    - Subscribe to temporal.{plane} to receive plane-specific ticks

    The heart (CirculationPumpFairy) beats at ~1 Hz.
    This fairy translates that single pulse into the polyrhythmic
    symphony that drives each plane at its natural tempo.
    """

    ACTOR_NAME = "TemporalDispatcherFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autonomic"

    PURPOSE = "Distribute heartbeat to all planes at their harmonic frequencies"
    MANTRA = "One pulse. Many tempos. All in sync."

    SHADOW_CLASS = TemporalDispatcherFairyShadow

    # This fairy IS part of the heartbeat infrastructure,
    # so it doesn't need heartbeat ticks itself
    NEEDS_HEARTBEAT = False
    NEEDS_COLLISION_CHAMBER = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._dispatcher = None  # Type: Optional[TemporalPulseDispatcher] (lazy import)
        self._heartbeats_received = 0
        self._last_heartbeat_time = 0.0
        self._booted = False

    def on_boot(self) -> bool:
        """Initialize the temporal pulse dispatcher and subscribe to heartbeat."""
        super().on_boot()

        # Lazy import to avoid circular dependency (P00 -> P20 -> P00)
        # This import is deferred to on_boot() when all modules are initialized
        global TemporalPulseDispatcher, PlaneTickState
        try:
            from fairies.P20_Somatic.circulation.temporal_pulse_dispatcher import (
                TemporalPulseDispatcher as _TPD,
                PlaneTickState as _PTS,
            )
            TemporalPulseDispatcher = _TPD
            PlaneTickState = _PTS
            has_dispatcher = True
        except ImportError as e:
            print(f"[{self.ACTOR_NAME}] Dispatcher import failed: {e}")
            has_dispatcher = False

        if has_dispatcher:
            try:
                # Create the dispatcher with our postal connection
                # We don't use worker_pool here to keep it simple -
                # the dispatcher handles parallel dispatch internally
                self._dispatcher = TemporalPulseDispatcher(
                    post=self.post,
                    worker_pool=None
                )
                print(f"[{self.ACTOR_NAME}] Temporal dispatcher initialized")

                # Subscribe to receive heartbeats from CirculationPumpFairy
                self._subscribe_to_heartbeat()
                self._booted = True

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to initialize dispatcher: {e}")
                self._dispatcher = None
                return False
        else:
            print(f"[{self.ACTOR_NAME}] Dispatcher not available - running in stub mode")

        return True

    def _subscribe_to_heartbeat(self):
        """Subscribe to the somatic heartbeat channel."""
        try:
            self.post.subscribe(
                "somatic.pulse",
                self._on_somatic_pulse,
                f"{self.ACTOR_NAME}-somatic"
            )
            print(f"[{self.ACTOR_NAME}] Subscribed to somatic.pulse")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to subscribe to somatic.pulse: {e}")

    def _on_somatic_pulse(self, message):
        """
        Handle incoming somatic pulse from CirculationPumpFairy.

        FIX 2026-02-06: Renamed from _on_heartbeat to _on_somatic_pulse to avoid
        collision with Organ Template's _on_heartbeat() which handles heartbeat.pulse
        and echoes liveness to DirectoryFairy. The previous name shadowed the base
        class method, preventing liveness echoes → TemporalDispatcherFairy marked dead.

        This is the core rhythm - we receive the single heartbeat pulse
        and dispatch it to all planes at their natural frequencies.
        """
        if not self._dispatcher:
            return

        try:
            # Extract pulse data from message
            if hasattr(message, 'payload'):
                pulse_data = message.payload if isinstance(message.payload, dict) else {}
            else:
                pulse_data = message if isinstance(message, dict) else {}

            # Record timing
            now = time.time()
            self._heartbeats_received += 1
            self._last_heartbeat_time = now

            # Delegate to the dispatcher - this fans out to all planes
            self._dispatcher.on_heartbeat(pulse_data)

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Error processing heartbeat: {e}")

    # =========================================================================
    # MONITORING METHODS
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """
        Get dispatch statistics.

        Returns:
            Dict with:
            - heartbeats: Total heartbeats received by this fairy
            - dispatcher_stats: Stats from the underlying dispatcher
            - last_heartbeat: Timestamp of last heartbeat
        """
        stats = {
            "fairy": self.ACTOR_NAME,
            "tracer_id": getattr(self, 'tracer_id', None),
            "heartbeats_received": self._heartbeats_received,
            "last_heartbeat": self._last_heartbeat_time,
            "booted": self._booted,
        }

        if self._dispatcher:
            dispatcher_stats = self._dispatcher.get_stats()
            stats["dispatcher"] = dispatcher_stats
        else:
            stats["dispatcher"] = None

        return stats

    def get_plane_states(self) -> Dict[str, Dict[str, Any]]:
        """
        Get current tick states for all planes.

        Returns:
            Dict mapping plane name to:
            - ticks: Total ticks dispatched to this plane
            - hz: Natural frequency of this plane
            - multiplier: How many ticks per base heartbeat
            - accumulated: Fractional ticks pending
        """
        if not self._dispatcher:
            return {}

        states = {}
        for plane_name, state in self._dispatcher._planes.items():
            states[plane_name] = {
                "ticks": state.tick_count,
                "hz": state.base_hz,
                "multiplier": state.multiplier,
                "accumulated": state.accumulated,
                "last_tick": state.last_tick,
            }
        return states

    # =========================================================================
    # INTENT HANDLERS
    # =========================================================================

    def intent_smoke(self, payload: dict) -> dict:
        """Health check for MCP tools."""
        return {
            "ok": True,
            "fairy": self.ACTOR_NAME,
            "tracer_id": getattr(self, 'tracer_id', None),
            "has_dispatcher": self._dispatcher is not None,
            "heartbeats_received": self._heartbeats_received,
            "planes": list(self._dispatcher._planes.keys()) if self._dispatcher else [],
        }

    def intent_get_stats(self, payload: dict) -> dict:
        """Get dispatch statistics via intent."""
        return {"ok": True, **self.get_stats()}

    def intent_get_plane_states(self, payload: dict) -> dict:
        """Get plane tick states via intent."""
        return {"ok": True, "planes": self.get_plane_states()}

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down...")
        self._dispatcher = None
        self._booted = False
        return super().on_shutdown()


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = ["TemporalDispatcherFairy", "TemporalDispatcherFairyShadow"]
