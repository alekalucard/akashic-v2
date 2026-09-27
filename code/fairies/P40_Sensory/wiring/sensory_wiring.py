# ══════════════════════════════════════════════════════════════════════════════
# SENSORY WIRING - Connect P40_Sensory to akashic_v2 gate system
# ══════════════════════════════════════════════════════════════════════════════
#
# Purpose: Wire the ported sensory systems to the existing gate architecture:
# - VisualCortexFairy → EmbodimentFairy (visual salience, novelty)
# - SensoryCortexFairy → EmbodimentFairy (felt sense integration)
# - TelemetryVisionFairy → UMF (inner eye)
#
# The flow:
#   Hardware/Input → Sensory Cortex → Embodiment Gate → Inner Voice → Soul
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
# ══════════════════════════════════════════════════════════════════════════════

import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


def _get_postal():
    """Get the postal system."""
    try:
        from postal_core.python.postal import get_postal
        return get_postal()
    except ImportError:
        return None


def _get_visual_cortex():
    """Get the visual cortex singleton."""
    try:
        from ..cortex.visual_cortex_fairy import get_visual_cortex
        return get_visual_cortex()
    except ImportError as e:
        sys.stderr.write(f"[SensoryWiring] VisualCortex not available: {e}\n")
        return None


def _get_sensory_cortex():
    """Get the sensory cortex singleton."""
    try:
        from ..cortex.sensory_cortex_fairy import get_sensory_cortex
        return get_sensory_cortex()
    except ImportError as e:
        sys.stderr.write(f"[SensoryWiring] SensoryCortex not available: {e}\n")
        return None


def _get_telemetry_vision():
    """Get the telemetry vision (inner eye) singleton."""
    try:
        from ..telemetry_vision.telemetry_vision_fairy import get_inner_eye
        return get_inner_eye()
    except ImportError as e:
        sys.stderr.write(f"[SensoryWiring] TelemetryVision not available: {e}\n")
        return None


def _get_motor_cortex():
    """Get the motor cortex singleton."""
    try:
        from ..cortex.motor_cortex_fairy import get_motor_cortex
        return get_motor_cortex()
    except ImportError as e:
        sys.stderr.write(f"[SensoryWiring] MotorCortex not available: {e}\n")
        return None


class SensoryWiring:
    """
    Central wiring hub for sensory systems.

    Connects:
    - VisualCortexFairy (human vision processing)
    - SensoryCortexFairy (felt sense integration)
    - TelemetryVisionFairy (internal/fairy vision)
    - MotorCortexFairy (action/output)

    To:
    - EmbodimentFairy (felt sense translation)
    - UnconsciousMindFairy (novelty, salience)
    - AutopilotFairy (habitual actions)
    """

    def __init__(self, postal=None):
        self._postal = postal or _get_postal()
        self._wired = False

        # Component references
        self._visual_cortex = None
        self._sensory_cortex = None
        self._telemetry_vision = None
        self._motor_cortex = None

        # Subscription handles
        self._subscriptions = []

        # State cache
        self._last_salience = 0.0
        self._last_novelty = 0.0
        self._last_visual_frame = None

        sys.stderr.write("[SensoryWiring] Wiring hub created\n")

    def wire(self) -> bool:
        """
        Wire all sensory systems to the gate architecture.

        Returns True if wiring succeeded.
        """
        if self._wired:
            sys.stderr.write("[SensoryWiring] Already wired\n")
            return True

        sys.stderr.write("[SensoryWiring] ════════════════════════════════════════\n")
        sys.stderr.write("[SensoryWiring] Wiring P40_Sensory to Gate System\n")
        sys.stderr.write("[SensoryWiring] ════════════════════════════════════════\n")

        # Get components
        self._visual_cortex = _get_visual_cortex()
        self._sensory_cortex = _get_sensory_cortex()
        self._telemetry_vision = _get_telemetry_vision()
        self._motor_cortex = _get_motor_cortex()

        # Wire visual cortex → postal
        if self._visual_cortex:
            self._wire_visual_cortex()
            sys.stderr.write("[SensoryWiring] [OK] VisualCortex wired\n")

        # Wire sensory cortex → postal
        if self._sensory_cortex:
            self._wire_sensory_cortex()
            sys.stderr.write("[SensoryWiring] [OK] SensoryCortex wired\n")

        # Wire telemetry vision → postal
        if self._telemetry_vision:
            self._wire_telemetry_vision()
            sys.stderr.write("[SensoryWiring] [OK] TelemetryVision wired\n")

        # Wire motor cortex → postal
        if self._motor_cortex:
            self._wire_motor_cortex()
            sys.stderr.write("[SensoryWiring] [OK] MotorCortex wired\n")

        # Subscribe to gate signals
        self._wire_gate_subscriptions()

        self._wired = True
        sys.stderr.write("[SensoryWiring] ════════════════════════════════════════\n")
        sys.stderr.write("[SensoryWiring] Wiring COMPLETE\n")
        sys.stderr.write("[SensoryWiring] ════════════════════════════════════════\n")

        return True

    def _wire_visual_cortex(self):
        """Wire VisualCortexFairy outputs to postal topics."""
        if not self._postal or not self._visual_cortex:
            return

        # When salience changes, publish to embodiment
        def on_salience(salience: float, objects: List[Dict]):
            self._last_salience = salience
            try:
                self._postal.publish("visual.salience", {
                    "salience": salience,
                    "objects": objects,
                    "ts": time.time(),
                })
                # High salience is felt
                if salience > 0.7:
                    self._postal.publish("umf.signal.visual", {
                        "type": "high_salience",
                        "salience": salience,
                        "source": "VisualCortexFairy",
                    })
            except Exception as e:
                sys.stderr.write(f"[SensoryWiring] Salience publish error: {e}\n")

        # When novelty detected
        def on_novelty(novelty: float, what: str):
            self._last_novelty = novelty
            try:
                self._postal.publish("sensory.novelty", {
                    "novelty": novelty,
                    "description": what,
                    "ts": time.time(),
                })
                # Novelty is always interesting
                if novelty > 0.5:
                    self._postal.publish("umf.signal.novelty", {
                        "type": "novelty_detected",
                        "novelty": novelty,
                        "what": what,
                        "source": "VisualCortexFairy",
                    })
            except Exception as e:
                sys.stderr.write(f"[SensoryWiring] Novelty publish error: {e}\n")

        # Register callbacks
        try:
            if hasattr(self._visual_cortex, 'on_salience_change'):
                self._visual_cortex.on_salience_change(on_salience)
            if hasattr(self._visual_cortex, 'on_novelty'):
                self._visual_cortex.on_novelty(on_novelty)
        except Exception as e:
            sys.stderr.write(f"[SensoryWiring] Visual callback error: {e}\n")

    def _wire_sensory_cortex(self):
        """Wire SensoryCortexFairy outputs to postal topics."""
        if not self._postal or not self._sensory_cortex:
            return

        # When felt state changes
        def on_felt_state(state: Dict):
            try:
                self._postal.publish("sensory.felt_state", {
                    "state": state,
                    "ts": time.time(),
                })
                # Send to embodiment for translation
                self._postal.publish("umf.signal.sensory", {
                    "type": "felt_state",
                    "state": state,
                    "source": "SensoryCortexFairy",
                })
            except Exception as e:
                sys.stderr.write(f"[SensoryWiring] Felt state publish error: {e}\n")

        # When distress detected
        def on_distress(level: float, source: str):
            try:
                self._postal.publish("sensory.distress", {
                    "level": level,
                    "source": source,
                    "ts": time.time(),
                })
                # Distress needs immediate attention
                if level > 0.6:
                    self._postal.publish("umf.signal.urgent", {
                        "type": "distress",
                        "level": level,
                        "source": source,
                    })
            except Exception as e:
                sys.stderr.write(f"[SensoryWiring] Distress publish error: {e}\n")

        # Register callbacks
        try:
            if hasattr(self._sensory_cortex, 'on_felt_state_change'):
                self._sensory_cortex.on_felt_state_change(on_felt_state)
            if hasattr(self._sensory_cortex, 'on_distress'):
                self._sensory_cortex.on_distress(on_distress)
        except Exception as e:
            sys.stderr.write(f"[SensoryWiring] Sensory callback error: {e}\n")

    def _wire_telemetry_vision(self):
        """Wire TelemetryVisionFairy outputs to postal topics."""
        if not self._postal or not self._telemetry_vision:
            return

        # When inner eye sees something
        def on_vision(frame: Dict):
            self._last_visual_frame = frame
            try:
                self._postal.publish("telemetry.vision", {
                    "frame": frame,
                    "ts": time.time(),
                })
            except Exception as e:
                sys.stderr.write(f"[SensoryWiring] Vision publish error: {e}\n")

        # Register callback
        try:
            if hasattr(self._telemetry_vision, 'on_frame'):
                self._telemetry_vision.on_frame(on_vision)
        except Exception as e:
            sys.stderr.write(f"[SensoryWiring] Telemetry callback error: {e}\n")

    def _wire_motor_cortex(self):
        """Wire MotorCortexFairy outputs to postal topics."""
        if not self._postal or not self._motor_cortex:
            return

        # When action completes
        def on_action_complete(action: str, success: bool):
            try:
                self._postal.publish("motor.action_complete", {
                    "action": action,
                    "success": success,
                    "ts": time.time(),
                })
                # Notify autopilot of completion
                self._postal.publish("autopilot.action_result", {
                    "action": action,
                    "success": success,
                    "source": "MotorCortexFairy",
                })
            except Exception as e:
                sys.stderr.write(f"[SensoryWiring] Action publish error: {e}\n")

        # Register callback
        try:
            if hasattr(self._motor_cortex, 'on_action_complete'):
                self._motor_cortex.on_action_complete(on_action_complete)
        except Exception as e:
            sys.stderr.write(f"[SensoryWiring] Motor callback error: {e}\n")

    def _wire_gate_subscriptions(self):
        """Subscribe to signals from the gate system."""
        if not self._postal:
            return

        # Listen for action requests from autopilot
        try:
            self._postal.subscribe(
                "autopilot.action.request",
                self._on_action_request,
            )
            self._subscriptions.append("autopilot.action.request")
        except Exception as e:
            sys.stderr.write(f"[SensoryWiring] Subscription error: {e}\n")

        # Listen for focus requests
        try:
            self._postal.subscribe(
                "attention.focus.request",
                self._on_focus_request,
            )
            self._subscriptions.append("attention.focus.request")
        except Exception as e:
            sys.stderr.write(f"[SensoryWiring] Subscription error: {e}\n")

    def _on_action_request(self, envelope):
        """Handle action request from autopilot."""
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        action = payload.get("action")

        if self._motor_cortex and hasattr(self._motor_cortex, 'execute'):
            try:
                self._motor_cortex.execute(action)
            except Exception as e:
                sys.stderr.write(f"[SensoryWiring] Action execute error: {e}\n")

    def _on_focus_request(self, envelope):
        """Handle attention focus request."""
        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
        target = payload.get("target")

        if self._visual_cortex and hasattr(self._visual_cortex, 'focus_on'):
            try:
                self._visual_cortex.focus_on(target)
            except Exception as e:
                sys.stderr.write(f"[SensoryWiring] Focus error: {e}\n")

    def get_status(self) -> Dict[str, Any]:
        """Get wiring status."""
        return {
            "wired": self._wired,
            "visual_cortex": self._visual_cortex is not None,
            "sensory_cortex": self._sensory_cortex is not None,
            "telemetry_vision": self._telemetry_vision is not None,
            "motor_cortex": self._motor_cortex is not None,
            "subscriptions": self._subscriptions,
            "last_salience": self._last_salience,
            "last_novelty": self._last_novelty,
        }

    def start_all(self, postal=None) -> bool:
        """Start all sensory systems and wire them."""
        if postal:
            self._postal = postal

        # Start visual cortex
        if self._visual_cortex and hasattr(self._visual_cortex, 'start'):
            try:
                self._visual_cortex.start(self._postal)
            except Exception as e:
                sys.stderr.write(f"[SensoryWiring] Visual start error: {e}\n")

        # Start telemetry vision
        if self._telemetry_vision and hasattr(self._telemetry_vision, 'start'):
            try:
                self._telemetry_vision.start(self._postal)
            except Exception as e:
                sys.stderr.write(f"[SensoryWiring] Telemetry start error: {e}\n")

        # Wire everything
        return self.wire()


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON AND CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

_WIRING: Optional[SensoryWiring] = None


def get_sensory_wiring() -> SensoryWiring:
    """Get or create the sensory wiring singleton."""
    global _WIRING
    if _WIRING is None:
        _WIRING = SensoryWiring()
    return _WIRING


def wire_sensory_to_gates(postal=None) -> bool:
    """Wire sensory systems to the gate architecture."""
    wiring = get_sensory_wiring()
    if postal:
        wiring._postal = postal
    return wiring.wire()


def start_sensory_systems(postal=None) -> bool:
    """Start all sensory systems."""
    wiring = get_sensory_wiring()
    return wiring.start_all(postal)


def get_sensory_status() -> Dict[str, Any]:
    """Get current sensory wiring status."""
    return get_sensory_wiring().get_status()
