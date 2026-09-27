"""
WatchdogFairy - Autonomic System Recovery

Part of HealthGuild in Plane P00 (Autonomic)
Created: 2026-01-28

Like the autonomic nervous system - monitors vitals and takes action
without conscious intervention. Reboots components, not the whole system.

The Equation: ((Cause + Affect) > Effect > Affect > infinity)
When equilibrium breaks, the watchdog restores it.
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

# Import the existing watchdog engine
# Note: Use fairies.P00_Autonomic to avoid collision with root P00_Autonomic
try:
    from fairies.P00_Autonomic.autonomic_watchdog import (
        AutonomicWatchdog,
        ComponentState,
        ComponentHealth,
    )
    HAS_ENGINE = True
except ImportError as e:
    print(f"[WatchdogFairy] Engine import failed: {e}")
    HAS_ENGINE = False


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class WatchdogFairyShadow:
    """Shadow for WatchdogFairy - meta-monitors the monitor."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "WatchdogFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 60.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks - is the watchdog watching?"""
        tests = []
        if hasattr(self.actor, '_watchdog') and self.actor._watchdog:
            tests.append(("watchdog_running", self.actor._watchdog.running))
            tests.append(("has_components", len(self.actor._watchdog.components) > 0))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class WatchdogFairy(Fairy):
    """
    Autonomic nervous system for the Akashic system.

    Guild: HealthGuild
    Coordinates with: CitizenRegistryFairy, all fairies

    Monitors component health and triggers auto-recovery:
    - Heartbeat monitoring
    - Degradation detection
    - Auto-reboot of failed components
    - Circuit breaker for cascading failures
    """

    ACTOR_NAME = "WatchdogFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "watchdog"

    PURPOSE = "Monitor system health and restore equilibrium automatically"
    MANTRA = "When equilibrium breaks, restore it without conscious intervention"

    SHADOW_CLASS = WatchdogFairyShadow

    # Needs heartbeat to run periodic checks
    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 5  # Check every 5 beats (~5 seconds)
    NEEDS_COLLISION_CHAMBER = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._watchdog = None
        self._subscription_count = 0
        self._last_check_time = 0
        self._reboot_count = 0

    def on_boot(self) -> bool:
        """Initialize the watchdog system."""
        super().on_boot()

        # Create the watchdog engine
        if HAS_ENGINE:
            try:
                self._watchdog = AutonomicWatchdog()
                self._watchdog.auto_reboot_enabled = True

                # Set callbacks
                self._watchdog.on_component_degraded.append(self._on_component_degraded)
                self._watchdog.on_component_rebooted.append(self._on_component_rebooted)
                self._watchdog.on_system_state_change.append(self._on_system_state_change)

                # Don't start background thread - we'll tick via heartbeat
                print(f"[{self.ACTOR_NAME}] Watchdog engine initialized")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to create watchdog: {e}")
                self._watchdog = None

        # Subscribe to watchdog intents
        self._subscribe_intents()

        return True

    def _subscribe_intents(self):
        """Subscribe to postal channels for watchdog commands."""
        intents = [
            ("watchdog.register", self._handle_register),
            ("watchdog.heartbeat", self._handle_heartbeat),
            ("fairy.heartbeat", self._handle_heartbeat),  # Also listen to fairy heartbeats!
            ("watchdog.status", self._handle_status),
            ("watchdog.reboot", self._handle_reboot),
            ("watchdog.error", self._handle_error),
        ]

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
                self._subscription_count += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        print(f"[{self.ACTOR_NAME}] Subscribed to {self._subscription_count} intents")

    def on_tick(self, beat: int):
        """Periodic health check tick."""
        # Handle both int and TensorEnvelope (defensive)
        if hasattr(beat, 'payload'):
            beat = beat.payload.get('beat', 0) if isinstance(beat.payload, dict) else 0
        beat = int(beat) if beat else 0

        if not self._watchdog:
            return

        now = time.time()

        # Run component check
        try:
            states = self._watchdog.check_components()

            # Emit health summary periodically
            if beat % 10 == 0:  # Every 10 ticks (~10 seconds)
                healthy = sum(1 for s in states.values() if s == ComponentState.HEALTHY)
                total = len(states)
                if total > 0:
                    health_pct = healthy / total * 100
                    self.post.publish("watchdog.health_summary", {
                        "healthy": healthy,
                        "total": total,
                        "health_percent": health_pct,
                        "system_state": self._watchdog.system_state.value,
                        "source": self.ACTOR_NAME,
                    })
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Check failed: {e}")

        self._last_check_time = now

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # ═══════════════════════════════════════════════════════════════════════════
    # CALLBACKS
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_component_degraded(self, name: str, state: ComponentState):
        """Called when a component becomes degraded."""
        print(f"[{self.ACTOR_NAME}] DEGRADED: {name} -> {state.value}")
        self.post.publish("watchdog.alert", {
            "type": "degraded",
            "component": name,
            "state": state.value,
            "source": self.ACTOR_NAME,
        })

    def _on_component_rebooted(self, name: str, success: bool):
        """Called when a component is rebooted."""
        self._reboot_count += 1
        status = "SUCCESS" if success else "FAILED"
        print(f"[{self.ACTOR_NAME}] REBOOT {status}: {name}")
        self.post.publish("watchdog.alert", {
            "type": "reboot",
            "component": name,
            "success": success,
            "total_reboots": self._reboot_count,
            "source": self.ACTOR_NAME,
        })

    def _on_system_state_change(self, old_state: ComponentState, new_state: ComponentState):
        """Called when system-wide state changes."""
        print(f"[{self.ACTOR_NAME}] SYSTEM: {old_state.value} -> {new_state.value}")
        self.post.publish("watchdog.system_state", {
            "old_state": old_state.value,
            "new_state": new_state.value,
            "source": self.ACTOR_NAME,
        })

    # ═══════════════════════════════════════════════════════════════════════════
    # INTENT HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _extract_payload(self, message) -> Dict[str, Any]:
        """Extract payload from postal message."""
        if hasattr(message, 'payload'):
            return message.payload if isinstance(message.payload, dict) else {}
        return message if isinstance(message, dict) else {}

    def _handle_register(self, message):
        """
        Register a component for monitoring.

        Payload:
            name: str - Component identifier (usually ACTOR_NAME)
            heartbeat_interval: float - Expected heartbeat interval (default 10s)
            max_misses: int - Reboot after this many misses (default 3)
        """
        payload = self._extract_payload(message)
        name = payload.get("name") or payload.get("fairy_name")

        if not name:
            return {"ok": False, "error": "name required"}

        if not self._watchdog:
            print(f"[{self.ACTOR_NAME}] Registered (no engine): {name}")
            return {"ok": True, "name": name}

        try:
            component = self._watchdog.register_component(
                name=name,
                heartbeat_interval=payload.get("heartbeat_interval", 10.0),
                max_misses=payload.get("max_misses", 3),
            )
            print(f"[{self.ACTOR_NAME}] Registered for monitoring: {name}")
            return {"ok": True, "name": name}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_heartbeat(self, message):
        """Receive heartbeat from a component."""
        payload = self._extract_payload(message)
        name = payload.get("name") or payload.get("source") or payload.get("fairy_name")

        if not name:
            return

        if self._watchdog:
            self._watchdog.heartbeat(name, payload.get("extra"))

    def _handle_status(self, message):
        """Get watchdog status."""
        payload = self._extract_payload(message)
        component_name = payload.get("name")

        if not self._watchdog:
            return {"ok": True, "engine": False, "reboot_count": self._reboot_count}

        if component_name:
            # Status of specific component
            if component_name in self._watchdog.components:
                comp = self._watchdog.components[component_name]
                return {
                    "ok": True,
                    "component": component_name,
                    "state": comp.state.value,
                    "last_heartbeat": comp.last_heartbeat,
                    "consecutive_misses": comp.consecutive_misses,
                    "reboot_count": comp.reboot_count,
                }
            return {"ok": False, "error": "Component not found"}

        # Overall status
        states = {name: comp.state.value for name, comp in self._watchdog.components.items()}
        return {
            "ok": True,
            "system_state": self._watchdog.system_state.value,
            "component_count": len(self._watchdog.components),
            "components": states,
            "reboot_count": self._reboot_count,
            "auto_reboot_enabled": self._watchdog.auto_reboot_enabled,
        }

    def _handle_reboot(self, message):
        """Manually trigger a component reboot."""
        payload = self._extract_payload(message)
        name = payload.get("name")

        if not name:
            return {"ok": False, "error": "name required"}

        if not self._watchdog:
            return {"ok": False, "error": "Watchdog not available"}

        if name not in self._watchdog.components:
            return {"ok": False, "error": "Component not found"}

        try:
            comp = self._watchdog.components[name]
            if comp.reboot_fn:
                success = comp.reboot_fn()
                return {"ok": True, "rebooted": name, "success": success}
            return {"ok": False, "error": "No reboot function registered"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_error(self, message):
        """Report an error from a component."""
        payload = self._extract_payload(message)
        name = payload.get("name") or payload.get("source")
        error = payload.get("error", "Unknown error")

        if name and self._watchdog:
            self._watchdog.report_error(name, error)

    # ═══════════════════════════════════════════════════════════════════════════
    # SMOKE TEST
    # ═══════════════════════════════════════════════════════════════════════════

    def intent_smoke(self, payload: dict) -> dict:
        """Health check - am I alive?"""
        return {
            "ok": True,
            "fairy": self.ACTOR_NAME,
            "tracer_id": self.tracer_id,
            "has_engine": self._watchdog is not None,
            "component_count": len(self._watchdog.components) if self._watchdog else 0,
            "reboot_count": self._reboot_count,
        }

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down...")
        if self._watchdog:
            self._watchdog.running = False
        return super().on_shutdown()
