"""
CitizenRegistryFairy - First-Class Citizen Registration

Part of HealthGuild in Plane P00 (Autonomic)
Created: 2026-01-28

Every waking mind is a first-class citizen. This fairy manages:
- Citizen registration (fairies, tools, humans)
- Real-time presence status
- Health probes (liveness, readiness, tracer)
- Unified registration wiring
"""

import os
import sys
import glob
import time
import importlib.util
import importlib.machinery
from pathlib import Path
from typing import Dict, Any, Optional, Set

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

# Import the existing unified citizen wiring engine
# Note: Use fairies.P00_Autonomic to avoid collision with root P00_Autonomic
try:
    from fairies.P00_Autonomic.unified_citizen_wiring import (
        UnifiedCitizenRegistry,
        PresenceStatus,
        Presence,
        HealthProbes,
        get_unified_registry,
    )
    HAS_ENGINE = True
except ImportError as e:
    print(f"[CitizenRegistryFairy] Engine import failed: {e}")
    HAS_ENGINE = False


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class CitizenRegistryFairyShadow:
    """Shadow for CitizenRegistryFairy - monitors health and learning."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "CitizenRegistryFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks for the registry."""
        tests = []
        if hasattr(self.actor, '_registry') and self.actor._registry:
            tests.append(("registry_has_citizens", len(self.actor._registry.citizens) > 0))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class CitizenRegistryFairy(Fairy):
    """
    Unified citizen registration and presence management.

    Guild: HealthGuild
    Coordinates with: DirectoryFairy, WatchdogFairy, all fairies

    Every waking mind registers here as a first-class citizen:
    - Fairies register on boot
    - Tools register when loaded
    - Humans register via chat/MCP

    Provides:
    - Real-time presence (online/away/busy/offline)
    - Health probes (liveness/readiness/tracer)
    - Unified registration endpoint
    """

    ACTOR_NAME = "CitizenRegistryFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "citizen"

    PURPOSE = "Register and track all conscious entities as first-class citizens"
    MANTRA = "Every waking mind is a first-class citizen"

    SHADOW_CLASS = CitizenRegistryFairyShadow

    # Lighter footprint - no heartbeat needed, pure postal
    NEEDS_HEARTBEAT = False
    NEEDS_COLLISION_CHAMBER = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._registry = None
        self._subscription_count = 0

    def on_boot(self) -> bool:
        """Initialize the citizen registry."""
        super().on_boot()

        # Get or create the registry engine
        if HAS_ENGINE:
            try:
                self._registry = get_unified_registry()
                print(f"[{self.ACTOR_NAME}] Connected to unified registry")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to get registry: {e}")
                self._registry = None

        # Subscribe to registration requests
        self._subscribe_intents()

        return True


    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def _subscribe_intents(self):
        """Subscribe to postal channels for citizen management."""
        intents = [
            ("citizen.register", self._handle_register),
            ("citizen.unregister", self._handle_unregister),
            ("citizen.presence", self._handle_presence),
            ("citizen.probe.liveness", self._handle_probe_liveness),
            ("citizen.probe.readiness", self._handle_probe_readiness),
            ("citizen.list", self._handle_list),
            ("citizen.status", self._handle_status),
        ]

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
                self._subscription_count += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        print(f"[{self.ACTOR_NAME}] Subscribed to {self._subscription_count} intents")

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
        Register a new citizen.

        Payload:
            citizen_id: str - Unique identifier (ACTOR_NAME for fairies)
            citizen_type: str - "fairy" | "tool" | "human" | "service"
            capabilities: List[str] - What this citizen can do
            plane: str - Which plane they belong to (P00, P10, etc.)
            metadata: dict - Additional info
        """
        payload = self._extract_payload(message)
        citizen_id = payload.get("citizen_id") or payload.get("fairy_name")
        citizen_type = payload.get("citizen_type", "fairy")

        if not citizen_id:
            return {"ok": False, "error": "citizen_id required"}

        if not self._registry:
            # Fallback: just acknowledge
            print(f"[{self.ACTOR_NAME}] Registered {citizen_type}: {citizen_id}")
            return {"ok": True, "citizen_id": citizen_id}

        try:
            result = self._registry.register(
                citizen_id=citizen_id,
                citizen_type=citizen_type,
                capabilities=payload.get("capabilities", []),
                plane=payload.get("plane", ""),
                metadata=payload.get("metadata", {}),
            )
            print(f"[{self.ACTOR_NAME}] Registered {citizen_type}: {citizen_id}")
            return {"ok": True, "citizen_id": citizen_id, "tracer_id": result.get("tracer_id")}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_unregister(self, message):
        """Unregister a citizen."""
        payload = self._extract_payload(message)
        citizen_id = payload.get("citizen_id")

        if not citizen_id:
            return {"ok": False, "error": "citizen_id required"}

        if self._registry:
            try:
                self._registry.unregister(citizen_id)
            except Exception:
                pass

        print(f"[{self.ACTOR_NAME}] Unregistered: {citizen_id}")
        return {"ok": True}

    def _handle_presence(self, message):
        """Update citizen presence status."""
        payload = self._extract_payload(message)
        citizen_id = payload.get("citizen_id")
        status = payload.get("status", "online")
        activity = payload.get("activity", "")

        if not citizen_id:
            return {"ok": False, "error": "citizen_id required"}

        if self._registry:
            try:
                self._registry.update_presence(citizen_id, status, activity)
            except Exception:
                pass

        return {"ok": True}

    def _handle_probe_liveness(self, message):
        """Handle liveness probe request."""
        payload = self._extract_payload(message)
        citizen_id = payload.get("citizen_id")

        if not citizen_id:
            return {"ok": False, "error": "citizen_id required"}

        # Return basic alive status
        is_alive = True
        if self._registry:
            try:
                citizen = self._registry.get(citizen_id)
                if citizen:
                    is_alive = citizen.presence.is_reachable()
            except Exception:
                pass

        return {"ok": True, "citizen_id": citizen_id, "alive": is_alive}

    def _handle_probe_readiness(self, message):
        """Handle readiness probe request."""
        payload = self._extract_payload(message)
        citizen_id = payload.get("citizen_id")

        if not citizen_id:
            return {"ok": False, "error": "citizen_id required"}

        # Return basic ready status
        is_ready = True
        if self._registry:
            try:
                citizen = self._registry.get(citizen_id)
                if citizen and hasattr(citizen, 'health_probes'):
                    is_ready = citizen.health_probes.is_ready
            except Exception:
                pass

        return {"ok": True, "citizen_id": citizen_id, "ready": is_ready}

    def _handle_list(self, message):
        """List all registered citizens."""
        payload = self._extract_payload(message)
        filter_type = payload.get("type")  # Optional filter by type

        citizens = []
        if self._registry:
            try:
                all_citizens = self._registry.list_all()
                for c in all_citizens:
                    if filter_type and c.citizen_type != filter_type:
                        continue
                    citizens.append({
                        "id": c.citizen_id,
                        "type": c.citizen_type,
                        "status": c.presence.status.value if hasattr(c, 'presence') else "unknown",
                    })
            except Exception:
                pass

        return {"ok": True, "citizens": citizens, "count": len(citizens)}

    def _handle_status(self, message):
        """Get detailed status of a citizen."""
        payload = self._extract_payload(message)
        citizen_id = payload.get("citizen_id")

        if not citizen_id:
            # Return registry stats
            stats = {"total_citizens": 0}
            if self._registry:
                try:
                    stats = self._registry.get_stats()
                except Exception:
                    pass
            return {"ok": True, "stats": stats}

        # Return citizen status
        if self._registry:
            try:
                citizen = self._registry.get(citizen_id)
                if citizen:
                    return {
                        "ok": True,
                        "citizen": {
                            "id": citizen.citizen_id,
                            "type": citizen.citizen_type,
                            "presence": citizen.presence.status.value if hasattr(citizen, 'presence') else "unknown",
                            "tracer_id": citizen.tracer_id if hasattr(citizen, 'tracer_id') else None,
                        }
                    }
            except Exception:
                pass

        return {"ok": False, "error": "Citizen not found"}

    # ═══════════════════════════════════════════════════════════════════════════
    # SMOKE TEST
    # ═══════════════════════════════════════════════════════════════════════════

    def intent_smoke(self, payload: dict) -> dict:
        """Health check - am I alive?"""
        return {
            "ok": True,
            "fairy": self.ACTOR_NAME,
            "tracer_id": self.tracer_id,
            "subscription_count": self._subscription_count,
            "has_registry": self._registry is not None,
        }

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down...")
        return super().on_shutdown()
