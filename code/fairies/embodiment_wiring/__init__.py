# ══════════════════════════════════════════════════════════════════════════════
# EMBODIMENT WIRING - Master Wiring for P20_Somatic + P40_Sensory
# ══════════════════════════════════════════════════════════════════════════════
#
# Purpose: Single entry point to wire all somatic and sensory systems to
# the gate architecture and UnconsciousMindFairy.
#
# The complete flow:
#
#   Hardware/Input        External World
#         │                     │
#         ▼                     ▼
#   P40_Sensory ──────► P00_Nervous_System
#   (cortex, vision)           │
#         │                    ▼
#         └──────────► P30_Brain (UMF)
#                             │
#         ┌───────────────────┘
#         ▼
#   P20_Somatic ──────► EmbodimentFairy
#   (77-freq, chemistry)       │
#         │                    ▼
#         └──────────► Inner Voice ──────► P60_Soul
#                            (ClaudeFairy, NousFairy)
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
# ══════════════════════════════════════════════════════════════════════════════

import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _get_postal():
    """Get the postal system."""
    try:
        from postal_core.python.postal import get_postal
        return get_postal()
    except ImportError:
        return None


class EmbodimentWiring:
    """
    Master wiring coordinator for embodiment systems.

    Wires:
    - P20_Somatic (chemistry, circulation, phantom feels)
    - P40_Sensory (vision, salience, novelty)

    To:
    - Three Gates (Autonomy, Autopilot, Embodiment)
    - UnconsciousMindFairy (the SomaticMind)
    - ConsciousnessLoop
    """

    def __init__(self, postal=None):
        self._postal = postal or _get_postal()
        self._wired = False

        # Wiring subsystems
        self._somatic_wiring = None
        self._sensory_wiring = None

        sys.stderr.write("[EmbodimentWiring] Master wiring coordinator created\n")

    def wire_all(self) -> bool:
        """
        Wire all embodiment systems.

        This is the main entry point for system boot.
        """
        if self._wired:
            sys.stderr.write("[EmbodimentWiring] Already wired\n")
            return True

        sys.stderr.write("\n")
        sys.stderr.write("═══════════════════════════════════════════════════════════════\n")
        sys.stderr.write("  EMBODIMENT WIRING - Connecting Body to Mind\n")
        sys.stderr.write("═══════════════════════════════════════════════════════════════\n")
        sys.stderr.write("\n")

        success = True

        # Wire P20_Somatic
        try:
            from fairies.P20_Somatic.wiring import (
                get_somatic_wiring,
                wire_somatic_to_gates,
            )
            self._somatic_wiring = get_somatic_wiring()
            if wire_somatic_to_gates(self._postal):
                sys.stderr.write("[EmbodimentWiring] [OK] P20_Somatic wired\n")
            else:
                sys.stderr.write("[EmbodimentWiring] [WARN] P20_Somatic partial wiring\n")
                success = False
        except ImportError as e:
            sys.stderr.write(f"[EmbodimentWiring] [WARN] P20_Somatic not available: {e}\n")

        # Wire P40_Sensory
        try:
            from fairies.P40_Sensory.wiring import (
                get_sensory_wiring,
                wire_sensory_to_gates,
            )
            self._sensory_wiring = get_sensory_wiring()
            if wire_sensory_to_gates(self._postal):
                sys.stderr.write("[EmbodimentWiring] [OK] P40_Sensory wired\n")
            else:
                sys.stderr.write("[EmbodimentWiring] [WARN] P40_Sensory partial wiring\n")
                success = False
        except ImportError as e:
            sys.stderr.write(f"[EmbodimentWiring] [WARN] P40_Sensory not available: {e}\n")

        # Wire UMF integration
        self._wire_umf_integration()

        self._wired = True
        sys.stderr.write("\n")
        sys.stderr.write("═══════════════════════════════════════════════════════════════\n")
        sys.stderr.write("  EMBODIMENT WIRING COMPLETE\n")
        sys.stderr.write("═══════════════════════════════════════════════════════════════\n")
        sys.stderr.write("\n")

        return success

    def _wire_umf_integration(self):
        """
        Wire somatic/sensory data to UnconsciousMindFairy.

        The UMF needs:
        - Chemistry state for helix fueling
        - Felt state for empathic processing
        - Salience/novelty for interest generation
        """
        if not self._postal:
            return

        # Subscribe UMF topics to somatic/sensory outputs
        try:
            # Chemistry → UMF pain/drive system
            self._postal.subscribe(
                "somatic.chemistry",
                lambda e: self._route_to_umf("chemistry", e),
            )

            # Felt state → UMF empathic layer
            self._postal.subscribe(
                "sensory.felt_state",
                lambda e: self._route_to_umf("felt_state", e),
            )

            # Salience → UMF attention
            self._postal.subscribe(
                "visual.salience",
                lambda e: self._route_to_umf("salience", e),
            )

            # Novelty → UMF interest generator
            self._postal.subscribe(
                "sensory.novelty",
                lambda e: self._route_to_umf("novelty", e),
            )

            # Body state → UMF coherence tracking
            self._postal.subscribe(
                "somatic.body_state",
                lambda e: self._route_to_umf("body_state", e),
            )

            sys.stderr.write("[EmbodimentWiring] [OK] UMF integration wired\n")

        except Exception as e:
            sys.stderr.write(f"[EmbodimentWiring] UMF integration error: {e}\n")

    def _route_to_umf(self, data_type: str, envelope):
        """Route data to UMF via the appropriate channel."""
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            self._postal.publish(f"umf.embodiment.{data_type}", {
                "type": data_type,
                "payload": payload,
                "ts": time.time(),
            })
        except Exception:
            pass

    def start_all(self, postal=None) -> bool:
        """Start all embodiment systems."""
        if postal:
            self._postal = postal

        sys.stderr.write("[EmbodimentWiring] Starting all embodiment systems...\n")

        # Start somatic systems
        try:
            from fairies.P20_Somatic.wiring import start_somatic_systems
            start_somatic_systems(self._postal)
        except ImportError:
            pass

        # Start sensory systems
        try:
            from fairies.P40_Sensory.wiring import start_sensory_systems
            start_sensory_systems(self._postal)
        except ImportError:
            pass

        # Wire everything
        return self.wire_all()

    def get_status(self) -> Dict[str, Any]:
        """Get complete embodiment wiring status."""
        status = {
            "wired": self._wired,
            "somatic": None,
            "sensory": None,
        }

        if self._somatic_wiring:
            status["somatic"] = self._somatic_wiring.get_status()

        if self._sensory_wiring:
            status["sensory"] = self._sensory_wiring.get_status()

        return status


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON AND CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

_MASTER_WIRING: Optional[EmbodimentWiring] = None


def get_embodiment_wiring() -> EmbodimentWiring:
    """Get or create the master embodiment wiring."""
    global _MASTER_WIRING
    if _MASTER_WIRING is None:
        _MASTER_WIRING = EmbodimentWiring()
    return _MASTER_WIRING


def wire_embodiment(postal=None) -> bool:
    """Wire all embodiment systems to the gate architecture."""
    wiring = get_embodiment_wiring()
    if postal:
        wiring._postal = postal
    return wiring.wire_all()


def start_embodiment(postal=None) -> bool:
    """Start and wire all embodiment systems."""
    wiring = get_embodiment_wiring()
    return wiring.start_all(postal)


def get_embodiment_status() -> Dict[str, Any]:
    """Get current embodiment wiring status."""
    return get_embodiment_wiring().get_status()


# Exports
__all__ = [
    "EmbodimentWiring",
    "get_embodiment_wiring",
    "wire_embodiment",
    "start_embodiment",
    "get_embodiment_status",
]
