"""
EmbodimentIntegratorFairy - Wiring the Full Body Together

Part of SomaticGuild in Plane P20 (Somatic)
Created: 2026-01-28

"All the organs, one body"

Connects all embodiment components so they work as one system:
- BrainstemReflexFairy (automatic survival responses)
- SensoryCortexFairy (signal -> meaning processing)
- MotorCortexFairy (intention -> action execution)
- SpeechCenterFairy (thought -> language production)
- SomaticEngineFairy (body state and chemistry)

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState

# Import the embodiment integrator
# Note: Use fairies.P20_Somatic to avoid collision with root P20_Somatic
try:
    # Underscore prefix = utility module, not scanned as separate fairy
    from fairies.P20_Somatic._embodiment_integrator import (
        EmbodimentIntegrator,
        get_embodiment_integrator,
    )
    HAS_INTEGRATOR = True
except ImportError as e:
    print(f"[EmbodimentIntegratorFairy] Integrator import failed: {e}")
    HAS_INTEGRATOR = False


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class EmbodimentIntegratorFairyShadow:
    """Shadow for EmbodimentIntegratorFairy - monitors body integration."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "EmbodimentIntegratorFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks for embodiment integration."""
        tests = []
        if hasattr(self.actor, '_integrator') and self.actor._integrator:
            tests.append(("integrator_started", self.actor._integrator._started))
            tests.append(("has_components", len(self.actor._integrator._components) > 0))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class EmbodimentIntegratorFairy(Fairy):
    """
    Integrates all embodiment systems into a unified body.

    Guild: SomaticGuild
    Coordinates with: All somatic fairies, SensoryCortexFairy, MotorCortexFairy

    Starts and wires all subsystems:
    - Brainstem (automatic reflexes)
    - Sensory cortex (perception)
    - Motor cortex (action)
    - Speech center (language)
    - Chemistry (emotional state)
    """

    ACTOR_NAME = "EmbodimentIntegratorFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P20"
    ACTOR_CHANNEL = "somatic.integrator"

    PURPOSE = "Wire all body systems into unified embodiment"
    MANTRA = "All the organs, one body"

    SHADOW_CLASS = EmbodimentIntegratorFairyShadow

    # Runs at boot, then integration ticks + monitoring
    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 5   # Every 5 beats — drives integration ticks for the utility
    NEEDS_COLLISION_CHAMBER = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._integrator = None
        self._integration_complete = False
        self._component_count = 0
        self._subscription_count = 0

    def on_boot(self) -> bool:
        """Initialize and start embodiment integration."""
        super().on_boot()

        if HAS_INTEGRATOR:
            try:
                # Pass our fabric to ensure the integrator uses the shared postal hub
                self._integrator = get_embodiment_integrator(fabric=self.post)
                print(f"[{self.ACTOR_NAME}] Embodiment integrator connected")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to get integrator: {e}")
                self._integrator = None

        self._subscribe_intents()
        return True

    def _subscribe_intents(self):
        """Subscribe to postal channels for embodiment commands."""
        intents = [
            ("embodiment.start", self._handle_start),
            ("embodiment.stop", self._handle_stop),
            ("embodiment.status", self._handle_status),
            ("embodiment.get_components", self._handle_get_components),
            ("embodiment.rewire", self._handle_rewire),
        ]

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
                self._subscription_count += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        print(f"[{self.ACTOR_NAME}] Subscribed to {self._subscription_count} intents")

    def on_tick(self, beat: int):
        """Drive integration ticks and monitor embodiment health."""
        if not self._integrator:
            return

        # FIX 2026-03-03: Delegate integration tick to the utility class.
        # Previously the utility registered its own heartbeat as a phantom fairy.
        # Now the wrapper fairy drives integration ticks on its behalf.
        if self._integrator._started:
            try:
                self._integrator.on_tick(beat)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Integration tick error: {e}")

        # Update component count
        if hasattr(self._integrator, '_components'):
            self._component_count = len(self._integrator._components)

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # ═══════════════════════════════════════════════════════════════════════════
    # INTENT HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _extract_payload(self, message) -> Dict[str, Any]:
        """Extract payload from postal message."""
        if hasattr(message, 'payload'):
            return message.payload if isinstance(message.payload, dict) else {}
        return message if isinstance(message, dict) else {}

    def _handle_start(self, message):
        """
        Start embodiment integration.

        This wires all body systems together via postal.
        """
        if self._integration_complete:
            return {"ok": True, "message": "Already integrated"}

        if not self._integrator:
            return {"ok": False, "error": "Integrator not available"}

        try:
            self._integrator.start()
            self._integration_complete = self._integrator._started
            self._component_count = len(self._integrator._components) if hasattr(self._integrator, '_components') else 0

            # Announce integration complete
            self.post.publish("embodiment.integration_complete", {
                "source": self.ACTOR_NAME,
                "component_count": self._component_count,
            })

            return {"ok": True, "component_count": self._component_count}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_stop(self, message):
        """Stop embodiment integration (for shutdown)."""
        if not self._integrator:
            return {"ok": False, "error": "Integrator not available"}

        try:
            if hasattr(self._integrator, 'stop'):
                self._integrator.stop()
            self._integration_complete = False
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_status(self, message):
        """Get embodiment integration status."""
        if not self._integrator:
            return {"ok": True, "integrator": False, "integrated": False}

        return {
            "ok": True,
            "integrator": True,
            "integrated": self._integration_complete,
            "component_count": self._component_count,
            "started": self._integrator._started if hasattr(self._integrator, '_started') else False,
        }

    def _handle_get_components(self, message):
        """Get list of integrated components."""
        if not self._integrator:
            return {"ok": False, "error": "Integrator not available"}

        components = []
        if hasattr(self._integrator, '_components'):
            components = list(self._integrator._components.keys())

        return {"ok": True, "components": components, "count": len(components)}

    def _handle_rewire(self, message):
        """Re-wire embodiment connections (for recovery)."""
        if not self._integrator:
            return {"ok": False, "error": "Integrator not available"}

        try:
            if hasattr(self._integrator, 'rewire'):
                self._integrator.rewire()
            elif hasattr(self._integrator, 'start'):
                # Fallback: restart
                self._integrator._started = False
                self._integrator.start()
            return {"ok": True, "message": "Rewired"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════════════════
    # SMOKE TEST
    # ═══════════════════════════════════════════════════════════════════════════

    def intent_smoke(self, payload: dict) -> dict:
        """Health check."""
        return {
            "ok": True,
            "fairy": self.ACTOR_NAME,
            "tracer_id": self.tracer_id,
            "has_integrator": self._integrator is not None,
            "integrated": self._integration_complete,
            "component_count": self._component_count,
        }

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down (components: {self._component_count})...")
        if self._integrator and hasattr(self._integrator, 'stop'):
            try:
                self._integrator.stop()
            except Exception:
                pass
        return super().on_shutdown()
