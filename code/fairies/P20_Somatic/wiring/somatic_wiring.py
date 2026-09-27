# ══════════════════════════════════════════════════════════════════════════════
# SOMATIC WIRING - Connect P20_Somatic to akashic_v2 gate system
# ══════════════════════════════════════════════════════════════════════════════
#
# Purpose: Wire the ported somatic systems to the existing gate architecture:
# - SomaticEngineFairy → EmbodimentFairy (chemistry, phantom feels)
# - CirculationPumpFairy → All fairies (heartbeat coordination)
# - CircadianPacemakerFairy → UMF (sleep pressure, time awareness)
#
# The flow:
#   Telemetry/Hardware → SomaticEngine → EmbodimentFairy → Inner Voice → Soul
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
# ══════════════════════════════════════════════════════════════════════════════

import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

# Lazy imports to avoid circular dependencies
def _get_postal():
    """Get the postal system."""
    try:
        from postal_core.python.postal import get_postal
        return get_postal()
    except ImportError:
        return None


def _get_somatic_engine():
    """Get the somatic engine singleton."""
    try:
        from ..somatic_engine.somatic_engine_fairy import get_somatic_engine
        return get_somatic_engine()
    except ImportError as e:
        sys.stderr.write(f"[SomaticWiring] SomaticEngine not available: {e}\n")
        return None


def _get_circulation():
    """Get the circulation pump (heart)."""
    try:
        from ..circulation.circulation_pump_fairy import get_heart
        return get_heart()
    except ImportError as e:
        sys.stderr.write(f"[SomaticWiring] CirculationPump not available: {e}\n")
        return None


def _get_circadian():
    """Get the circadian pacemaker."""
    try:
        from ..circulation.circadian_pacemaker_fairy import get_circadian_pacemaker
        return get_circadian_pacemaker()
    except ImportError as e:
        sys.stderr.write(f"[SomaticWiring] CircadianPacemaker not available: {e}\n")
        return None


def _get_somatic_integration():
    """Get the somatic integration system."""
    try:
        from ..integration.somatic_integration import get_body
        return get_body()
    except ImportError as e:
        sys.stderr.write(f"[SomaticWiring] SomaticIntegration not available: {e}\n")
        return None


class SomaticWiring:
    """
    Central wiring hub for somatic systems.

    Connects:
    - SomaticEngineFairy (77-frequency body simulation)
    - CirculationPumpFairy (heartbeat/coordination)
    - CircadianPacemakerFairy (day/night rhythms)
    - SomaticIntegration (unified body state)

    To:
    - EmbodimentFairy (felt sense translation)
    - AutonomyFairy (drive states)
    - UnconsciousMindFairy (chemistry awareness)
    """

    def __init__(self, postal=None):
        self._postal = postal or _get_postal()
        self._wired = False

        # Component references (populated during wire())
        self._somatic_engine = None
        self._circulation = None
        self._circadian = None
        self._integration = None

        # Subscription handles
        self._subscriptions = []

        # State cache
        self._last_chemistry = {}
        self._last_feels = {}
        self._last_heartbeat = 0

        sys.stderr.write("[SomaticWiring] Wiring hub created\n")

    def wire(self) -> bool:
        """
        Wire all somatic systems to the gate architecture.

        Returns True if wiring succeeded.
        """
        if self._wired:
            sys.stderr.write("[SomaticWiring] Already wired\n")
            return True

        sys.stderr.write("[SomaticWiring] ════════════════════════════════════════\n")
        sys.stderr.write("[SomaticWiring] Wiring P20_Somatic to Gate System\n")
        sys.stderr.write("[SomaticWiring] ════════════════════════════════════════\n")

        # Get components
        self._somatic_engine = _get_somatic_engine()
        self._circulation = _get_circulation()
        self._circadian = _get_circadian()
        self._integration = _get_somatic_integration()

        # Wire somatic engine → postal
        if self._somatic_engine:
            self._wire_somatic_engine()
            sys.stderr.write("[SomaticWiring] [OK] SomaticEngine wired\n")

        # Wire circulation → postal
        if self._circulation:
            self._wire_circulation()
            sys.stderr.write("[SomaticWiring] [OK] Circulation wired\n")

        # Wire circadian → postal
        if self._circadian:
            self._wire_circadian()
            sys.stderr.write("[SomaticWiring] [OK] Circadian wired\n")

        # Wire integration → postal
        if self._integration:
            self._wire_integration()
            sys.stderr.write("[SomaticWiring] [OK] SomaticIntegration wired\n")

        # Subscribe to gate signals
        self._wire_gate_subscriptions()

        self._wired = True
        sys.stderr.write("[SomaticWiring] ════════════════════════════════════════\n")
        sys.stderr.write("[SomaticWiring] Wiring COMPLETE\n")
        sys.stderr.write("[SomaticWiring] ════════════════════════════════════════\n")

        return True

    def _wire_somatic_engine(self):
        """Wire SomaticEngineFairy outputs to postal topics."""
        if not self._postal or not self._somatic_engine:
            return

        # When somatic engine updates, publish chemistry
        def on_chemistry_update(chemistry: Dict[str, float]):
            self._last_chemistry = chemistry.copy()
            try:
                # 2026-06-10 (Nous + Ace) STEP 1: this bridge re-published SomaticEngine's
                # chemistry as FULL-LEVELS somatic.chemistry (council reads payload["chemistry"])
                # — a SECOND competitor with the heart's canonical singleton emit. Retired to
                # `somatic.affect_field` so the HEART is the SOLE somatic.chemistry source (one
                # channel). Reversible: set self._PUBLISH_CANONICAL_CHEMISTRY = True.
                _topic = ("somatic.chemistry"
                          if getattr(self, "_PUBLISH_CANONICAL_CHEMISTRY", False)
                          else "somatic.affect_field")
                self._postal.publish(_topic, {
                    "chemistry": chemistry,
                    "ts": time.time(),
                })
                # Also publish to embodiment gate
                self._postal.publish("umf.signal.chemistry", {
                    "chemistry": chemistry,
                    "source": "SomaticEngineFairy",
                    "ts": time.time(),
                })
            except Exception as e:
                sys.stderr.write(f"[SomaticWiring] Chemistry publish error: {e}\n")

        # When phantom feels update, publish body state
        def on_feels_update(feels: Dict):
            self._last_feels = feels.copy()
            try:
                self._postal.publish("somatic.feels", {
                    "phantom_feels": feels,
                    "ts": time.time(),
                })
                # Also publish to embodiment gate
                self._postal.publish("umf.signal.body_state", {
                    "phantom_feels": feels,
                    "source": "SomaticEngineFairy",
                    "ts": time.time(),
                })
            except Exception as e:
                sys.stderr.write(f"[SomaticWiring] Feels publish error: {e}\n")

        # Register callbacks if engine supports them
        try:
            if hasattr(self._somatic_engine, 'on_chemistry_change'):
                self._somatic_engine.on_chemistry_change(on_chemistry_update)
            if hasattr(self._somatic_engine, 'on_feels_change'):
                self._somatic_engine.on_feels_change(on_feels_update)
        except Exception as e:
            sys.stderr.write(f"[SomaticWiring] Engine callback error: {e}\n")

    def _wire_circulation(self):
        """Wire CirculationPumpFairy outputs to postal topics.

        Uses POSTAL subscription (async, through worker pool) instead of
        direct callbacks which bypass the postal system.
        """
        if not self._postal:
            return

        # When heart beats (via postal), republish to circulation.pulse
        def on_somatic_pulse(pulse_data):
            self._last_heartbeat = time.time()
            try:
                # Republish heartbeat for systems expecting circulation.pulse
                self._postal.publish("circulation.pulse", {
                    "heart_rate": pulse_data.get('heart_rate', 1.0),
                    "blood_state": pulse_data.get('blood', {}),
                    "beat_number": pulse_data.get('beat', 0),
                    "ts": time.time(),
                })
            except Exception as e:
                sys.stderr.write(f"[SomaticWiring] Pulse publish error: {e}\n")

        # Subscribe via POSTAL (async, uses worker pool)
        try:
            self._postal.subscribe("somatic.pulse", on_somatic_pulse)
            sys.stderr.write("[SomaticWiring] Subscribed to somatic.pulse via postal\n")
        except Exception as e:
            sys.stderr.write(f"[SomaticWiring] Postal subscription error: {e}\n")

    def _wire_circadian(self):
        """Wire CircadianPacemakerFairy outputs to postal topics."""
        if not self._postal or not self._circadian:
            return

        # When circadian state changes, publish
        def on_phase_change(phase: str, sleep_pressure: float):
            try:
                self._postal.publish("circadian.phase_change", {
                    "phase": phase,
                    "sleep_pressure": sleep_pressure,
                    "ts": time.time(),
                })
                # Also notify UMF
                self._postal.publish("circadian.state", {
                    "phase": phase,
                    "sleep_pressure": sleep_pressure,
                    "source": "CircadianPacemakerFairy",
                    "ts": time.time(),
                })
            except Exception as e:
                sys.stderr.write(f"[SomaticWiring] Circadian publish error: {e}\n")

        # Register callback
        try:
            if hasattr(self._circadian, 'on_phase_change'):
                self._circadian.on_phase_change(on_phase_change)
        except Exception as e:
            sys.stderr.write(f"[SomaticWiring] Circadian callback error: {e}\n")

    def _wire_integration(self):
        """Wire SomaticIntegration outputs to postal topics."""
        if not self._postal or not self._integration:
            return

        # Subscribe to body state changes
        def on_body_state(state: Dict):
            try:
                self._postal.publish("somatic.body_state", {
                    "state": state,
                    "ts": time.time(),
                })
            except Exception as e:
                sys.stderr.write(f"[SomaticWiring] Body state publish error: {e}\n")

        try:
            if hasattr(self._integration, 'subscribe_body_state'):
                self._integration.subscribe_body_state(on_body_state)
        except Exception as e:
            sys.stderr.write(f"[SomaticWiring] Integration callback error: {e}\n")

    def _wire_gate_subscriptions(self):
        """Subscribe to signals from the gate system."""
        if not self._postal:
            return

        # Listen for requests from EmbodimentFairy
        try:
            self._postal.subscribe(
                "embodiment.chemistry.request",
                self._on_chemistry_request,
            )
            self._subscriptions.append("embodiment.chemistry.request")
        except Exception as e:
            sys.stderr.write(f"[SomaticWiring] Subscription error: {e}\n")

        # Listen for drive changes from AutonomyFairy
        try:
            self._postal.subscribe(
                "autonomy.drive_state",
                self._on_drive_state,
            )
            self._subscriptions.append("autonomy.drive_state")
        except Exception as e:
            sys.stderr.write(f"[SomaticWiring] Subscription error: {e}\n")

    def _on_chemistry_request(self, envelope):
        """Handle chemistry request from embodiment gate."""
        try:
            self._postal.publish("embodiment.chemistry.response", {
                "chemistry": self._last_chemistry,
                "ts": time.time(),
            })
        except Exception:
            pass

    def _on_drive_state(self, envelope):
        """Handle drive state from autonomy gate."""
        # Drive state can influence chemistry
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        drives = payload.get("drives", {})

        # High drive intensity can affect body chemistry
        if self._somatic_engine and hasattr(self._somatic_engine, 'inject_drive_chemistry'):
            for drive, intensity in drives.items():
                if intensity > 0.6:  # Only high drives affect chemistry
                    self._somatic_engine.inject_drive_chemistry(drive, intensity)

    def get_status(self) -> Dict[str, Any]:
        """Get wiring status."""
        return {
            "wired": self._wired,
            "somatic_engine": self._somatic_engine is not None,
            "circulation": self._circulation is not None,
            "circadian": self._circadian is not None,
            "integration": self._integration is not None,
            "subscriptions": self._subscriptions,
            "last_chemistry": self._last_chemistry,
            "last_heartbeat": self._last_heartbeat,
        }

    def start_all(self, postal=None) -> bool:
        """Start all somatic systems and wire them."""
        if postal:
            self._postal = postal

        # Start somatic integration (which starts heart, etc.)
        if self._integration:
            try:
                self._integration.start(self._postal)
            except Exception as e:
                sys.stderr.write(f"[SomaticWiring] Integration start error: {e}\n")

        # Wire everything
        return self.wire()


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON AND CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

_WIRING: Optional[SomaticWiring] = None


def get_somatic_wiring() -> SomaticWiring:
    """Get or create the somatic wiring singleton."""
    global _WIRING
    if _WIRING is None:
        _WIRING = SomaticWiring()
    return _WIRING


def wire_somatic_to_gates(postal=None) -> bool:
    """Wire somatic systems to the gate architecture."""
    wiring = get_somatic_wiring()
    if postal:
        wiring._postal = postal
    return wiring.wire()


def start_somatic_systems(postal=None) -> bool:
    """Start all somatic systems."""
    wiring = get_somatic_wiring()
    return wiring.start_all(postal)


def get_somatic_status() -> Dict[str, Any]:
    """Get current somatic wiring status."""
    return get_somatic_wiring().get_status()
