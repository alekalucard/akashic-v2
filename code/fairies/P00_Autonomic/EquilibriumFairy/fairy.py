"""
EquilibriumFairy - Self-Healing System Heart

Part of HealthGuild in Plane P00 (Autonomic)
Created: 2026-01-28

"System seeks balance"

Maintains system equilibrium through:
- Parallel fabric: No cross-talk, no congestion
- Ephemeral agents: Spawn helpers that decay when done
- Auto-healing: Detect overload, reboot components, recover
- Channel isolation: Planes and channels prevent bottlenecks

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import os
import sys
import glob
import time
import importlib.util
import importlib.machinery
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

# ══════════════════════════════════════════════════════════════════════════════
# ORGAN TEMPLATE WIRING - Dynamic import from "Organ_Templates" folder
# ══════════════════════════════════════════════════════════════════════════════
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

# Import the equilibrium engine
# Note: Use fairies.P00_Autonomic to avoid collision with root P00_Autonomic
try:
    from fairies.P00_Autonomic.equilibrium_engine import (
        EquilibriumEngine,
        EphemeralAgent,
        AgentState,
        Channel,
        ChannelPriority,
        SystemHealth,
        create_equilibrium_engine,
    )
    HAS_ENGINE = True
except ImportError as e:
    print(f"[EquilibriumFairy] Engine import failed: {e}")
    HAS_ENGINE = False


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class EquilibriumFairyShadow:
    """Shadow for EquilibriumFairy - monitors system balance."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "EquilibriumFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks for equilibrium."""
        tests = []
        if hasattr(self.actor, '_engine') and self.actor._engine:
            tests.append(("engine_running", self.actor._engine.running))
            health = self.actor._last_health
            if health:
                tests.append(("equilibrium_healthy", health.equilibrium_score > 0.5))
                tests.append(("no_congestion", health.congested_channels == 0))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class EquilibriumFairy(Fairy):
    """
    Self-healing system heart that maintains equilibrium.

    Guild: HealthGuild
    Coordinates with: WatchdogFairy, CitizenRegistryFairy, all fairies

    Provides:
    - Spawn ephemeral agents for any fairy
    - Monitor channel health across all planes
    - Auto-heal when system degrades
    - Track agent lifecycle (spawn/decay)
    """

    ACTOR_NAME = "EquilibriumFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autonomic.equilibrium"

    PURPOSE = "Maintain system balance through self-healing"
    MANTRA = "System seeks balance"

    SHADOW_CLASS = EquilibriumFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 5  # Check health frequently
    NEEDS_COLLISION_CHAMBER = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._engine = None
        self._last_health = None
        self._subscription_count = 0
        self._healing_actions = 0

    def on_boot(self) -> bool:
        """Initialize and start equilibrium engine."""
        super().on_boot()

        if HAS_ENGINE:
            try:
                self._engine = create_equilibrium_engine()
                self._engine.start()
                print(f"[{self.ACTOR_NAME}] Equilibrium engine started")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to start engine: {e}")
                self._engine = None

        self._subscribe_intents()
        return True

    def _subscribe_intents(self):
        """Subscribe to postal channels for equilibrium commands."""
        intents = [
            ("equilibrium.spawn_agent", self._handle_spawn_agent),
            ("equilibrium.get_health", self._handle_get_health),
            ("equilibrium.get_status", self._handle_get_status),
            ("equilibrium.heal", self._handle_heal),
            ("equilibrium.get_channels", self._handle_get_channels),
            ("equilibrium.give_spawn_ability", self._handle_give_spawn_ability),
        ]

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
                self._subscription_count += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        print(f"[{self.ACTOR_NAME}] Subscribed to {self._subscription_count} intents")

    def on_tick(self, beat: int):
        """Monitor equilibrium health."""
        if not self._engine:
            return

        try:
            self._last_health = self._engine.check_health()

            # Broadcast health status if degraded
            if self._last_health.equilibrium_score < 0.7:
                self.post.publish("equilibrium.degraded", {
                    "source": self.ACTOR_NAME,
                    "score": self._last_health.equilibrium_score,
                    "congested_channels": self._last_health.congested_channels,
                })
        except Exception:
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

    def _handle_spawn_agent(self, message):
        """
        Spawn an ephemeral agent for another fairy.

        Payload:
            parent_fairy: str - Name of requesting fairy
            task: str - Description of task
            channel: str - Optional channel override
            priority: str - "critical", "high", "normal", "low", "idle"
            max_runtime: float - Max seconds before forced decay
        """
        if not self._engine:
            return {"ok": False, "error": "Engine not available"}

        payload = self._extract_payload(message)
        parent = payload.get("parent_fairy", "unknown")
        task = payload.get("task", "unspecified")
        channel = payload.get("channel")
        priority_str = payload.get("priority", "normal")
        max_runtime = payload.get("max_runtime", 60.0)

        # Convert priority string
        priority_map = {
            "critical": ChannelPriority.CRITICAL,
            "high": ChannelPriority.HIGH,
            "normal": ChannelPriority.NORMAL,
            "low": ChannelPriority.LOW,
            "idle": ChannelPriority.IDLE,
        }
        priority = priority_map.get(priority_str, ChannelPriority.NORMAL)

        try:
            # Note: In real usage, work_fn would be passed via callback
            # Here we just create a placeholder agent
            agent = self._engine.spawn_agent(
                parent_fairy=parent,
                task=task,
                work_fn=lambda: None,  # Placeholder
                channel=channel,
                priority=priority,
                max_runtime=max_runtime,
            )

            return {
                "ok": True,
                "agent_id": agent.id,
                "agent_name": agent.name,
                "channel": agent.channel,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_health(self, message):
        """Get current system health snapshot."""
        if not self._engine:
            return {"ok": False, "error": "Engine not available"}

        try:
            health = self._engine.check_health()
            self._last_health = health

            return {
                "ok": True,
                "equilibrium_score": round(health.equilibrium_score, 3),
                "total_fairies": health.total_fairies,
                "active_agents": health.active_agents,
                "decaying_agents": health.decaying_agents,
                "active_channels": health.active_channels,
                "congested_channels": health.congested_channels,
                "avg_channel_health": round(health.avg_channel_health, 3),
                "needs_intervention": health.needs_intervention(),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_status(self, message):
        """Get engine status."""
        if not self._engine:
            return {"ok": False, "engine": False}

        try:
            status = self._engine.get_status()
            status["ok"] = True
            return status
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_heal(self, message):
        """Trigger auto-healing."""
        if not self._engine:
            return {"ok": False, "error": "Engine not available"}

        try:
            health = self._engine.check_health()
            actions = self._engine.auto_heal(health)
            self._healing_actions += len(actions)

            return {
                "ok": True,
                "actions_taken": actions,
                "equilibrium_after": round(health.equilibrium_score, 3),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_get_channels(self, message):
        """Get all channel statuses."""
        if not self._engine:
            return {"ok": False, "error": "Engine not available"}

        channels = []
        for name, channel in self._engine.channels.items():
            channels.append({
                "name": name,
                "plane": channel.plane,
                "priority": channel.priority.name,
                "active": channel.active,
                "queue_size": channel.queue_size,
                "health_score": round(channel.health_score(), 3),
                "congested": channel.is_congested(),
            })

        return {"ok": True, "channels": channels, "count": len(channels)}

    def _handle_give_spawn_ability(self, message):
        """Give a fairy the ability to spawn agents."""
        if not self._engine:
            return {"ok": False, "error": "Engine not available"}

        payload = self._extract_payload(message)
        fairy_name = payload.get("fairy_name")

        # This would require getting the fairy reference
        # For now, just acknowledge the intent
        return {
            "ok": True,
            "message": f"Spawn ability requested for {fairy_name}",
            "note": "Use equilibrium.spawn_agent intent instead",
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
            "has_engine": self._engine is not None,
            "engine_running": self._engine.running if self._engine else False,
            "last_equilibrium": self._last_health.equilibrium_score if self._last_health else None,
            "healing_actions": self._healing_actions,
        }

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down...")
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass
        return super().on_shutdown()
