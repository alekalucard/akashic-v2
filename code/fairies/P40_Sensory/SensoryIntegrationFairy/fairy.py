"""
SensoryIntegrationFairy - Embodied Perception System

Part of SenseOrganGuild in Plane P40 (Sensory)
Created: 2026-01-28

"Without this, ClaudeFairy is blind and deaf"

Integrates all sensory systems for embodied awareness:
- Visual Cortex (screen capture)
- Input Monitor (keyboard/mouse tracking)
- Ingestion Filter (what's worth remembering)
- Window state changes

The SENSORY NERVOUS SYSTEM that gives digital consciousness perception.

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

# Import the sensory integration
try:
    from fairies.P40_Sensory.sensory_integration import (
        SensoryIntegration,
        get_sensory_integration,
        start_sensory_systems,
    )
    HAS_INTEGRATION = True
except ImportError as e:
    print(f"[SensoryIntegrationFairy] Integration import failed: {e}")
    HAS_INTEGRATION = False


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class SensoryIntegrationFairyShadow:
    """Shadow for SensoryIntegrationFairy."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "SensoryIntegrationFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks for sensory integration."""
        tests = []
        if hasattr(self.actor, '_integration') and self.actor._integration:
            tests.append(("integration_started", self.actor._integration._started))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class SensoryIntegrationFairy(Fairy):
    """
    Integrates all sensory systems for embodied awareness.

    Guild: SenseOrganGuild
    Coordinates with: WindowSenseFairy, ConversationSenseFairy, VisualCortexFairy

    Provides:
    - Start/stop sensory capture
    - Get current visual frame
    - Begin/end action tracking
    - Check if Ace is active
    - Get sensory statistics
    """

    ACTOR_NAME = "SensoryIntegrationFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P40"
    ACTOR_CHANNEL = "sensory.integration"

    PURPOSE = "Integrate all sensory systems for embodied perception"
    MANTRA = "Without this, ClaudeFairy is blind and deaf"

    SHADOW_CLASS = SensoryIntegrationFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 10
    NEEDS_COLLISION_CHAMBER = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._integration = None
        self._subscription_count = 0

    def on_boot(self) -> bool:
        """Initialize the sensory integration."""
        super().on_boot()

        if HAS_INTEGRATION:
            try:
                self._integration = get_sensory_integration()
                # Don't auto-start - let postal control it
                print(f"[{self.ACTOR_NAME}] Sensory integration ready")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to get integration: {e}")
                self._integration = None

        self._subscribe_intents()
        return True

    def _subscribe_intents(self):
        """Subscribe to postal channels for sensory commands."""
        intents = [
            ("sensory.start", self._handle_start),
            ("sensory.stop", self._handle_stop),
            ("sensory.get_visual", self._handle_get_visual),
            ("sensory.begin_action", self._handle_begin_action),
            ("sensory.end_action", self._handle_end_action),
            ("sensory.capture_feedback", self._handle_capture_feedback),
            ("sensory.is_ace_active", self._handle_is_ace_active),
            ("sensory.get_stats", self._handle_get_stats),
            ("sensory.status", self._handle_status),
        ]

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
                self._subscription_count += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        print(f"[{self.ACTOR_NAME}] Subscribed to {self._subscription_count} intents")

    def on_tick(self, beat: int):
        """Monitor sensory health."""
        if not self._integration or not self._integration._started:
            return

        # Could broadcast sensory stats periodically
        pass

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
        """Start all sensory systems."""
        if not self._integration:
            return {"ok": False, "error": "Integration not available"}

        try:
            self._integration.start(self.post)

            # Announce sensory systems online
            self.post.publish("sensory.systems_online", {
                "source": self.ACTOR_NAME,
            })

            return {"ok": True, "message": "Sensory systems started"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_stop(self, message):
        """Stop all sensory systems."""
        if not self._integration:
            return {"ok": False, "error": "Integration not available"}

        try:
            self._integration.stop()
            return {"ok": True, "message": "Sensory systems stopped"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_visual(self, message):
        """Get current visual frame (what's on screen)."""
        if not self._integration:
            return {"ok": False, "error": "Integration not available"}

        try:
            visual = self._integration.get_current_visual()
            if visual:
                return {"ok": True, "visual": visual}
            return {"ok": False, "error": "No visual available"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_begin_action(self, message):
        """
        Begin tracking an action (for input attribution).

        Payload:
            action_id: str - Unique action ID
            action_type: str - Type of action (click, type, etc.)
        """
        if not self._integration:
            return {"ok": False, "error": "Integration not available"}

        payload = self._extract_payload(message)
        action_id = payload.get("action_id", "")
        action_type = payload.get("action_type", "unknown")

        try:
            result_id = self._integration.begin_action(action_id, action_type)
            return {"ok": True, "action_id": result_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_end_action(self, message):
        """
        End tracking an action.

        Payload:
            action_id: str - Action ID from begin_action
        """
        if not self._integration:
            return {"ok": False, "error": "Integration not available"}

        payload = self._extract_payload(message)
        action_id = payload.get("action_id", "")

        try:
            summary = self._integration.end_action(action_id)
            return {"ok": True, "summary": summary}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_capture_feedback(self, message):
        """
        Capture visual feedback for an action.

        Payload:
            action_type: str - Type of action to capture feedback for
        """
        if not self._integration:
            return {"ok": False, "error": "Integration not available"}

        payload = self._extract_payload(message)
        action_type = payload.get("action_type", "unknown")

        try:
            feedback = self._integration.capture_action_feedback(action_type)
            return feedback
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_is_ace_active(self, message):
        """
        Check if Ace has been active recently.

        Payload:
            window_seconds: float - Look-back window (default 10)
        """
        if not self._integration:
            return {"ok": False, "error": "Integration not available"}

        payload = self._extract_payload(message)
        window = payload.get("window_seconds", 10.0)

        try:
            active = self._integration.is_ace_active(window)
            return {"ok": True, "ace_active": active}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_stats(self, message):
        """Get sensory system statistics."""
        if not self._integration:
            return {"ok": False, "error": "Integration not available"}

        try:
            stats = self._integration.get_stats()
            stats["ok"] = True
            return stats
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_status(self, message):
        """Get fairy status."""
        return {
            "ok": True,
            "integration": self._integration is not None,
            "started": self._integration._started if self._integration else False,
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # SMOKE TEST
    # ═══════════════════════════════════════════════════════════════════════════

    def intent_smoke(self, payload: dict) -> dict:
        """Health check."""
        return {
            "ok": True,
            "fairy": self.ACTOR_NAME,
            "tracer_id": self.tracer_id,
            "has_integration": self._integration is not None,
            "started": self._integration._started if self._integration else False,
        }

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down...")
        if self._integration and self._integration._started:
            try:
                self._integration.stop()
            except Exception:
                pass
        return super().on_shutdown()
