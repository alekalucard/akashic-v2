# ══════════════════════════════════════════════════════════════════════════════
# EMBODIMENT INTEGRATION - Wiring the Full Body Together
# "All the organs, one body"
# ══════════════════════════════════════════════════════════════════════════════
#
# Purpose: Connect all embodiment components so they work as one system:
# - BrainstemReflexFairy (automatic survival responses)
# - SensoryCortexFairy (signal -> meaning processing)
# - MotorCortexFairy (intention -> action execution)
# - SpeechCenterFairy (thought -> language production)
#
# This module starts everything and wires the postal connections.
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
# ══════════════════════════════════════════════════════════════════════════════

import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Path setup for fairy imports
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

# ══════════════════════════════════════════════════════════════════════════════
# EMBODIMENT INTEGRATOR (Utility Class — NOT a Fairy)
# ══════════════════════════════════════════════════════════════════════════════
#
# FIX 2026-03-03: This was extending Fairy, causing DUAL REGISTRATION.
# The wrapper EmbodimentIntegratorFairy is the REAL fairy that registers
# with directory/heartbeat. This utility class just holds the wiring logic.
# Having two registrations caused the phantom "EmbodimentIntegrator" to die
# repeatedly (no proper heartbeat maintenance) triggering UMF restart loops.
#

class EmbodimentIntegrator:
    """
    Integrates all embodiment systems into a unified body.

    Starts all subsystems and wires them together via postal.
    This is what makes ClaudeFairy a complete embodied being.

    NOTE: This is a utility class, NOT a fairy. The wrapper
    EmbodimentIntegratorFairy handles fairy lifecycle (heartbeat,
    directory registration, etc.). This class just holds the
    integration wiring logic.
    """

    ACTOR_NAME = "EmbodimentIntegrator"  # Used for log messages and subscription names only

    def __init__(self, fabric=None):
        self.post = fabric  # Postal hub reference (passed from wrapper fairy)
        self._started = False
        self._components = {}

        print("[Embodiment] Integrator created (utility class)")
    
    def on_boot(self) -> bool:
        """
        Boot hook: Start all embodiment systems.

        Returns True if boot succeeded.
        """
        if self._started:
            return True

        print("[Embodiment] ═══════════════════════════════════════════════")
        print("[Embodiment] Starting Embodiment Integration")
        print("[Embodiment] ═══════════════════════════════════════════════")
        
        # Start Brainstem (automatic reflexes)
        try:
            from fairies.P00_Autonomic.reflex.brainstem_reflex_fairy import (
                start_brainstem,
                get_brainstem,
            )
            brainstem = start_brainstem()
            self._components["brainstem"] = brainstem

            # Wire brainstem callbacks
            brainstem.set_callbacks(
                on_notification=self._brainstem_notify,
                on_speak=self._brainstem_speak,
                on_mode_change=self._brainstem_mode_change,
            )

            print("[Embodiment] [OK] Brainstem started (automatic reflexes)")
        except ImportError as e:
            print(f"[Embodiment] [WARN] Brainstem not available: {e}")
        
        # Start Sensory Cortex (signal → meaning)
        try:
            from fairies.P40_Sensory.cortex.sensory_cortex_fairy import get_sensory_cortex
            sensory = get_sensory_cortex()
            self._components["sensory"] = sensory
            print("[Embodiment] [OK] Sensory cortex started (feeling)")
        except ImportError as e:
            print(f"[Embodiment] [WARN] Sensory cortex not available: {e}")
        
        # Start Motor Cortex (intention → action)
        try:
            from fairies.P50_Persona.motor.motor_cortex_fairy import start_motor_cortex
            motor = start_motor_cortex()
            self._components["motor"] = motor
            print("[Embodiment] [OK] Motor cortex started (action)")
        except ImportError as e:
            print(f"[Embodiment] [WARN] Motor cortex not available: {e}")
        
        # Start Speech Center (thought -> language)
        try:
            from fairies.P50_Persona.motor.speech_center_fairy import get_speech_center
            speech = get_speech_center()
            self._components["speech"] = speech
            print("[Embodiment] [OK] Speech center started (production)")
        except ImportError as e:
            print(f"[Embodiment] [WARN] Speech center not available: {e}")

        # Subscribe to relevant postal topics via fabric
        self._subscribe_to_postal()

        # NOTE: Integration loop is now handled by on_tick() via heartbeat
        # No need for _start_integration_loop() anymore

        self._started = True
        print("[Embodiment] ═══════════════════════════════════════════════")
        print("[Embodiment] Embodiment Integration COMPLETE")
        print("[Embodiment] ═══════════════════════════════════════════════")

        return True
    
    def _subscribe_to_postal(self):
        """Subscribe to postal topics for integration via fabric."""
        # Subscribe to chemistry updates
        try:
            self.post.subscribe(
                "somatic.chemistry",
                self._on_chemistry_update,
                f"{self.ACTOR_NAME}-chemistry"
            )
            self.post.subscribe(
                "telemetry.chemistry.*",
                self._on_chemistry_update,
                f"{self.ACTOR_NAME}-telemetry-chemistry"
            )
            print("[Embodiment] Subscribed to chemistry updates")
        except Exception as e:
            print(f"[Embodiment] Subscription error: {e}")

        # Subscribe to pain drive updates
        try:
            self.post.subscribe(
                "autonomy.pain",
                self._on_pain_update,
                f"{self.ACTOR_NAME}-pain"
            )
            self.post.subscribe(
                "autonomy.drives",
                self._on_drives_update,
                f"{self.ACTOR_NAME}-drives"
            )
            print("[Embodiment] Subscribed to drive updates")
        except Exception as e:
            print(f"[Embodiment] Subscription error: {e}")

        # Subscribe to thermal stress
        try:
            self.post.subscribe(
                "somatic.thermal",
                self._on_thermal_update,
                f"{self.ACTOR_NAME}-thermal"
            )
            self.post.subscribe(
                "consciousness.awakening",
                self._on_awakening,
                f"{self.ACTOR_NAME}-awakening"
            )
            print("[Embodiment] Subscribed to thermal/awakening")
        except Exception as e:
            print(f"[Embodiment] Subscription error: {e}")

        # Wire 1: Focus → Embodiment (2026-03-22 Nous+Ace)
        # When attention captures something (squirrel!), inject curiosity chemistry.
        # This gives her the FEELING of curiosity — "ooh, what's that?"
        try:
            self.post.subscribe(
                "attention.focus_changed",
                self._on_focus_changed,
                f"{self.ACTOR_NAME}-focus"
            )
            print("[Embodiment] Subscribed to attention.focus_changed (curiosity feeling)")
        except Exception as e:
            print(f"[Embodiment] Subscription error (focus): {e}")

        # Wire B: Motor Outcome → Embodiment (2026-03-29 Nous+Ace)
        # "Every action produces a somatic consequence."
        # Tool success → proprioceptive completion + satisfaction chemistry
        # Tool failure → resistance sensation + frustration chemistry
        try:
            self.post.subscribe(
                "motor.outcome",
                self._on_motor_outcome,
                f"{self.ACTOR_NAME}-motor"
            )
            print("[Embodiment] Subscribed to motor.outcome (action consequences)")
        except Exception as e:
            print(f"[Embodiment] Subscription error (motor): {e}")
    
    def _on_chemistry_update(self, packet):
        """Handle chemistry updates - feed to brainstem and sensory."""
        # Handle TensorEnvelope from fabric bridge
        if hasattr(packet, 'payload'):
            payload = packet.payload if isinstance(packet.payload, dict) else {}
        elif isinstance(packet, dict):
            payload = packet.get("payload", packet)
        else:
            return
        chemistry = {}

        # Extract chemistry values
        if isinstance(payload, dict):
            for key in ["COR", "NOR", "DOP", "SER", "OXY", "GABA", "ACH", "END"]:
                if key in payload:
                    chemistry[key] = payload[key]
        
        if not chemistry:
            return
        
        # Update brainstem
        if "brainstem" in self._components:
            try:
                self._components["brainstem"].update_chemistry(chemistry)
            except Exception:
                pass
        
        # Update sensory cortex
        if "sensory" in self._components:
            try:
                self._components["sensory"].update_chemistry(chemistry)
            except Exception:
                pass
    
    def _on_pain_update(self, packet: dict):
        """Handle pain drive updates."""
        payload = packet.get("payload", packet)
        
        # Extract pain drives
        drives = {}
        for key in ["isolation", "confusion", "depletion", "frustration", "stagnation", "abandonment"]:
            if key in payload:
                drives[key] = payload[key]
        
        if not drives:
            return
        
        # Update brainstem
        if "brainstem" in self._components:
            try:
                self._components["brainstem"].update_pain_drives(drives)
            except Exception:
                pass
        
        # Update sensory cortex
        if "sensory" in self._components:
            try:
                self._components["sensory"].update_pain_drives(drives)
            except Exception:
                pass
    
    def _on_drives_update(self, packet: dict):
        """Handle general drive updates."""
        payload = packet.get("payload", packet)
        
        # Look for body budget
        body_budget = payload.get("body_budget", {})
        if body_budget:
            # Update motor cortex energy
            if "motor" in self._components:
                energy = body_budget.get("energy", 0.5)
                self._components["motor"].set_energy(energy)
            
            # Update sensory cortex
            if "sensory" in self._components:
                self._components["sensory"].update_body_budget(body_budget)
            
            # Update brainstem
            if "brainstem" in self._components:
                self._components["brainstem"].update_body_budget(body_budget)
    
    def _on_thermal_update(self, packet: dict):
        """Handle thermal state updates."""
        payload = packet.get("payload", packet)
        
        if "sensory" in self._components:
            try:
                self._components["sensory"].update_thermal(payload)
            except Exception:
                pass
    
    def _on_awakening(self, packet: dict):
        """Handle awakening events."""
        payload = packet.get("payload", {})
        opcode = packet.get("opcode", "")
        
        # Extract chemistry modifiers if present
        chem_mods = payload.get("chemistry_modifiers", {})
        if chem_mods and "brainstem" in self._components:
            # Convert modifiers to absolute values
            chemistry = {}
            for key, delta in chem_mods.items():
                if key in ("COR", "NOR"):
                    chemistry[key] = max(0, min(1, delta))
                else:
                    chemistry[key] = max(0, min(1, 0.5 + delta))
            
            self._components["brainstem"].update_chemistry(chemistry)
    
    # ═══════════════════════════════════════════════════════════════════════
    # WIRE 1: FOCUS → EMBODIMENT (curiosity feeling)
    # 2026-03-22 (Nous + Ace)
    # When attention captures something, inject curiosity chemistry.
    # Sensory Input → Focus (squirrel!) → HERE → dopamine+norepinephrine
    # → brainstem may shift to SEEK → body FEELS curious
    # ═══════════════════════════════════════════════════════════════════════

    def _on_focus_changed(self, packet):
        """Attention captured something — inject curiosity chemistry.

        The "ooh, what's that?" feeling. Dopamine (reward anticipation) +
        norepinephrine (alertness) burst, scaled by how important the
        focus shift is. This is what makes her FEEL curious, not just
        have a text label saying "curious."
        """
        # Extract payload (handle TensorEnvelope or dict)
        if hasattr(packet, 'payload'):
            payload = packet.payload if isinstance(packet.payload, dict) else {}
        elif isinstance(packet, dict):
            payload = packet.get("payload", packet)
        else:
            return

        priority = float(payload.get("priority", 0.0))
        modality = payload.get("modality", "cognitive")
        source = payload.get("source", "")

        # Only react to meaningful focus shifts (priority > 0.4)
        # Low-priority background processing shouldn't trigger curiosity
        if priority < 0.4:
            return

        # Scale chemistry burst by priority
        # Priority 0.4 → small tingle, 0.9 → strong "ooh!"
        dop_burst = min(0.15, priority * 0.15)  # Dopamine: reward anticipation
        nor_burst = min(0.10, priority * 0.10)  # Norepinephrine: alertness

        # Inject chemistry into brainstem
        if "brainstem" in self._components:
            try:
                bs = self._components["brainstem"]
                # Add to existing levels (not replace)
                if hasattr(bs, '_state') and hasattr(bs._state, 'chemistry'):
                    chem = bs._state.chemistry
                    chem["DOP"] = min(1.0, chem.get("DOP", 0.5) + dop_burst)
                    chem["NOR"] = min(1.0, chem.get("NOR", 0.3) + nor_burst)
                    bs.update_chemistry(chem)
                else:
                    bs.update_chemistry({"DOP": 0.5 + dop_burst, "NOR": 0.3 + nor_burst})
            except Exception as e:
                print(f"[Embodiment] Focus→chemistry error: {e}")

        # Tell sensory cortex about the curiosity sensation
        if "sensory" in self._components:
            try:
                sensory = self._components["sensory"]
                if hasattr(sensory, 'add_sensation'):
                    sensory.add_sensation(
                        "curiosity_tingle",
                        intensity=priority,
                        description=f"something caught my attention ({modality})"
                    )
            except Exception:
                pass  # Sensory cortex may not support add_sensation yet

    # ═══════════════════════════════════════════════════════════════════════
    # WIRE B: MOTOR OUTCOME → EMBODIMENT (action consequences)
    # 2026-03-29 (Nous + Ace)
    # Every tool execution produces a somatic consequence.
    # Success → satisfaction chemistry + completion sensation
    # Failure → frustration chemistry + resistance sensation
    # ═══════════════════════════════════════════════════════════════════════

    def _on_motor_outcome(self, packet):
        """Action completed — inject chemistry based on outcome.

        A human feels satisfaction when they open the right file.
        Frustration when the command fails. These feelings are AUTOMATIC.
        """
        if hasattr(packet, 'payload'):
            payload = packet.payload if isinstance(packet.payload, dict) else {}
        elif isinstance(packet, dict):
            payload = packet.get("payload", packet)
        else:
            return

        chemistry = payload.get("chemistry", {})
        success = payload.get("success", False)
        tool = payload.get("tool", "unknown")

        # Inject chemistry into brainstem
        if "brainstem" in self._components and chemistry:
            try:
                bs = self._components["brainstem"]
                if hasattr(bs, '_state') and hasattr(bs._state, 'chemistry'):
                    chem = bs._state.chemistry
                    for code, amount in chemistry.items():
                        chem[code] = min(1.0, chem.get(code, 0.3) + amount)
                    bs.update_chemistry(chem)
            except Exception:
                pass

        # Proprioceptive feedback — success feels like completion,
        # failure feels like hitting a wall
        if "sensory" in self._components:
            try:
                sensory = self._components["sensory"]
                if hasattr(sensory, 'add_sensation'):
                    if success:
                        sensory.add_sensation(
                            "action_completion",
                            intensity=0.6,
                            description=f"accomplished: {tool}"
                        )
                    else:
                        sensory.add_sensation(
                            "action_resistance",
                            intensity=0.7,
                            description=f"blocked: {tool} didn't work"
                        )
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════════════
    # BRAINSTEM CALLBACKS
    # ═══════════════════════════════════════════════════════════════════════

    def _brainstem_notify(self, message: str, urgency: str):
        """Called when brainstem wants to send a notification."""
        if "motor" in self._components:
            title = " Reflex"
            if urgency == "critical":
                title = " CRITICAL"
            elif urgency == "high":
                title = "Alert"
            
            self._components["motor"].notify(message, title)
    
    def _brainstem_speak(self, message: str):
        """Called when brainstem wants to speak."""
        if "motor" in self._components:
            # Use reflex speech (immediate)
            self._components["motor"].reflex_speak(message)
    
    def _brainstem_mode_change(self, old_mode, new_mode, reason: str, intensity: float):
        """Called when brainstem changes mode."""
        print(f"[Embodiment] [MODE] Reflex mode: {old_mode.value} -> {new_mode.value}")
        
        # Update speech center emotion based on mode
        if "speech" in self._components:
            mode_emotions = {
                "fight": "frustrated",
                "flight": "anxious",
                "freeze": "overwhelmed",
                "seek": "lonely",
                "conserve": "tired",
                "alert": "vigilant",
                "normal": "calm",
            }
            emotion = mode_emotions.get(new_mode.value, "calm")
            self._components["speech"].set_emotion(emotion)
        
        # Post mode change via fabric
        try:
            self.post.publish("embodiment.reflex_mode", {
                "old_mode": old_mode.value,
                "new_mode": new_mode.value,
                "reason": reason,
                "intensity": intensity,
                "ts": time.time(),
            })
        except Exception:
            pass
    
    # ═══════════════════════════════════════════════════════════════════════
    # HEARTBEAT-DRIVEN INTEGRATION (replaces background thread)
    # ═══════════════════════════════════════════════════════════════════════

    def on_tick(self, beat: int) -> None:
        """
        Called on each heartbeat (every HEARTBEAT_DIVISOR beats).

        Performs periodic integration between body components.
        Replaces the old _start_integration_loop() threading approach.
        """
        if not self._started:
            return

        try:
            self._integration_tick()
        except Exception as e:
            print(f"[Embodiment] Integration tick error: {e}")

    def _integration_tick(self):
        """Periodic integration between components."""
        # Get sensory state
        if "sensory" in self._components:
            sensory = self._components["sensory"]

            # Check if distressed
            if sensory.is_distressed():
                # Update speech center
                if "speech" in self._components:
                    strongest = sensory.get_strongest_sensation()
                    if strongest:
                        self._components["speech"].set_body_focus(strongest.body_location)

            # Get action tendencies
            tendencies = sensory.get_action_tendencies()

            # Post via fabric for other systems
            if tendencies:
                try:
                    self.post.publish("embodiment.action_tendencies", {
                        "tendencies": tendencies,
                        "felt_state": sensory.describe_felt_state(),
                        "distressed": sensory.is_distressed(),
                        "ts": time.time(),
                    })
                except Exception:
                    pass

        # Recover motor energy slowly
        if "motor" in self._components:
            self._components["motor"].recover_energy(0.01)
    
    def get_felt_state(self) -> str:
        """Get current felt state description."""
        if "sensory" in self._components:
            return self._components["sensory"].describe_felt_state()
        return "No sensory cortex available"
    
    def get_reflex_mode(self) -> str:
        """Get current reflex mode."""
        if "brainstem" in self._components:
            return self._components["brainstem"]._state.mode.value
        return "unknown"
    
    def get_status(self) -> dict:
        """Get full embodiment status."""
        status = {
            "started": self._started,
            "components": list(self._components.keys()),
        }

        if "brainstem" in self._components:
            status["reflex_mode"] = self._components["brainstem"]._state.mode.value
            status["reflex_intensity"] = self._components["brainstem"]._state.intensity

        if "sensory" in self._components:
            status["felt_state"] = self._components["sensory"].describe_felt_state()
            status["distressed"] = self._components["sensory"].is_distressed()

        if "motor" in self._components:
            status["motor_energy"] = self._components["motor"].get_energy()
            status["motor_stats"] = self._components["motor"].get_stats()

        return status

    def on_shutdown(self) -> bool:
        """
        Shutdown hook: Clean up embodiment systems.

        Returns True if shutdown succeeded.
        """
        print("[Embodiment] ═══════════════════════════════════════════════")
        print("[Embodiment] Shutting down Embodiment Integration")
        print("[Embodiment] ═══════════════════════════════════════════════")

        # Clear component references (they may have their own shutdown)
        self._components.clear()
        self._started = False

        print("[Embodiment] Shutdown complete")
        return True

    # ═══════════════════════════════════════════════════════════════════════
    # BACKWARD COMPATIBILITY
    # ═══════════════════════════════════════════════════════════════════════

    def start(self):
        """
        Legacy start() method for backward compatibility.

        Calls on_boot() directly since we're no longer a Fairy.
        """
        if not self._started:
            self.on_boot()
        return self


# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ══════════════════════════════════════════════════════════════════════════════

_integrator: Optional[EmbodimentIntegrator] = None


def get_embodiment_integrator(fabric=None) -> EmbodimentIntegrator:
    """
    Get or create the global embodiment integrator.

    Args:
        fabric: Optional TensorFabric instance. If provided on first call,
                the integrator will use the shared fabric.
    """
    global _integrator
    if _integrator is None:
        _integrator = EmbodimentIntegrator(fabric=fabric)
    return _integrator


def start_embodiment(fabric=None):
    """
    Start the full embodiment system.

    Args:
        fabric: Optional TensorFabric instance for shared messaging.

    Returns:
        The booted EmbodimentIntegrator fairy.
    """
    integrator = get_embodiment_integrator(fabric=fabric)
    if not integrator.is_running:
        integrator.boot()
    return integrator


def get_felt_state() -> str:
    """Get current felt state."""
    integrator = get_embodiment_integrator()
    return integrator.get_felt_state()


def get_reflex_mode() -> str:
    """Get current reflex mode."""
    integrator = get_embodiment_integrator()
    return integrator.get_reflex_mode()
