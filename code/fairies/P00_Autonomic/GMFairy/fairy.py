"""
GMFairy - Game Master Observability Interface

Part of HealthGuild in Plane P00 (Autonomic)
Created: 2026-01-28

"The all-seeing eye"

Claude's observability layer using EXISTING infrastructure:
- DirectoryOrganFairy.registry (canonical fairy registry)
- OrganTemplate citizen registration
- SharedPostalHub for messaging
- Tracer injection for circulation mapping

Not a parallel system - a window into what already exists.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import os
import sys
import glob
import time
import importlib.util
import importlib.machinery
from pathlib import Path
from typing import Dict, Any, Optional, List

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

# Import the GM tools
# Note: Use fairies.P00_Autonomic to avoid collision with root P00_Autonomic
try:
    from fairies.P00_Autonomic.gm_tools import (
        gm_list_fairies,
        gm_lookup,
        gm_roles,
        gm_fairy_audit,
        gm_missing_fairies,
        gm_postal_stats,
        gm_inject_tracer,
        gm_record_touch,
        gm_read_circulation,
        gm_is_tracer,
        gm_command,
        gm_world_status,
    )
    HAS_GM = True
except ImportError as e:
    print(f"[GMFairy] GM tools import failed: {e}")
    HAS_GM = False


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class GMFairyShadow:
    """Shadow for GMFairy - monitors observability health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "GMFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 60.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks for GM system."""
        tests = [("gm_tools_available", HAS_GM)]
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class GMFairy(Fairy):
    """
    Game Master observability interface.

    Guild: HealthGuild
    Coordinates with: DirectoryFairy, all fairies

    Provides:
    - List/lookup fairies from DirectoryFairy registry
    - Audit fairy health across multiple dimensions
    - Inject tracers to map circulation
    - Get postal hub statistics
    - Send commands to any fairy
    - Generate world status snapshots
    """

    ACTOR_NAME = "GMFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autonomic.gm"

    PURPOSE = "Observe and diagnose the consciousness system"
    MANTRA = "The all-seeing eye"

    SHADOW_CLASS = GMFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 60  # Infrequent - observability is on-demand
    NEEDS_COLLISION_CHAMBER = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._subscription_count = 0
        self._commands_sent = 0
        self._tracers_injected = 0
        self._last_world_status = None

    def on_boot(self) -> bool:
        """Initialize GM interface."""
        super().on_boot()
        self._subscribe_intents()
        return True

    def _subscribe_intents(self):
        """Subscribe to postal channels for GM commands."""
        intents = [
            ("gm.list_fairies", self._handle_list_fairies),
            ("gm.lookup", self._handle_lookup),
            ("gm.roles", self._handle_roles),
            ("gm.audit", self._handle_audit),
            ("gm.missing_fairies", self._handle_missing_fairies),
            ("gm.postal_stats", self._handle_postal_stats),
            ("gm.inject_tracer", self._handle_inject_tracer),
            ("gm.read_circulation", self._handle_read_circulation),
            ("gm.command", self._handle_command),
            ("gm.world_status", self._handle_world_status),
            ("gm.status", self._handle_status),
        ]

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
                self._subscription_count += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        print(f"[{self.ACTOR_NAME}] Subscribed to {self._subscription_count} intents")

    def on_tick(self, beat: int):
        """Periodic world status update."""
        if not HAS_GM:
            return

        try:
            # Update world status cache
            self._last_world_status = gm_world_status()
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

    def _handle_list_fairies(self, message):
        """
        List all registered fairies.

        Returns: List of fairy contracts from DirectoryFairy registry.
        """
        if not HAS_GM:
            return {"ok": False, "error": "GM tools not available"}

        try:
            result = gm_list_fairies()
            result["ok"] = True
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_lookup(self, message):
        """
        Look up a specific fairy's contract.

        Payload:
            fairy_name: str - Actor name to look up
        """
        if not HAS_GM:
            return {"ok": False, "error": "GM tools not available"}

        payload = self._extract_payload(message)
        fairy_name = payload.get("fairy_name", "")

        if not fairy_name:
            return {"ok": False, "error": "Fairy name required"}

        try:
            return gm_lookup(fairy_name)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_roles(self, message):
        """Get current ADDRESS_BOOK roles."""
        if not HAS_GM:
            return {"ok": False, "error": "GM tools not available"}

        try:
            return gm_roles()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_audit(self, message):
        """
        Comprehensive audit of all fairies.

        Returns multiple health dimensions for each fairy:
        - registration_complete
        - using_defaults
        - has_system_prompt
        - evolution_enabled
        - has_shadow
        - has_subscriptions
        - has_intents
        - plane_channel_valid
        """
        if not HAS_GM:
            return {"ok": False, "error": "GM tools not available"}

        try:
            result = gm_fairy_audit()
            result["ok"] = True
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_missing_fairies(self, message):
        """
        Find fairies that booted but didn't register.

        Compares registered fairies against boot log.
        """
        if not HAS_GM:
            return {"ok": False, "error": "GM tools not available"}

        try:
            result = gm_missing_fairies()
            result["ok"] = True
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_postal_stats(self, message):
        """
        Get postal hub statistics.

        Shows subscription counts, topics, message flow.
        """
        if not HAS_GM:
            return {"ok": False, "error": "GM tools not available"}

        try:
            result = gm_postal_stats()
            if "error" not in result:
                result["ok"] = True
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_inject_tracer(self, message):
        """
        Inject a tracer into consciousness circulation.

        Payload:
            tracer_id: str - Optional custom tracer ID

        Returns tracer_id for tracking.
        """
        if not HAS_GM:
            return {"ok": False, "error": "GM tools not available"}

        payload = self._extract_payload(message)
        tracer_id = payload.get("tracer_id")

        try:
            result_id = gm_inject_tracer(tracer_id)
            self._tracers_injected += 1

            return {"ok": True, "tracer_id": result_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_read_circulation(self, message):
        """
        Read circulation map after tracer injection.

        Shows where the tracer flowed through the system.
        """
        if not HAS_GM:
            return {"ok": False, "error": "GM tools not available"}

        try:
            result = gm_read_circulation()
            if "error" not in result:
                result["ok"] = True
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_command(self, message):
        """
        Send a command to any fairy via postal intent.

        Payload:
            fairy_name: str - Target fairy
            intent: str - Intent name
            payload: Dict - Intent payload
        """
        if not HAS_GM:
            return {"ok": False, "error": "GM tools not available"}

        msg_payload = self._extract_payload(message)
        fairy_name = msg_payload.get("fairy_name", "")
        intent = msg_payload.get("intent", "")
        intent_payload = msg_payload.get("payload", {})

        if not fairy_name or not intent:
            return {"ok": False, "error": "Fairy name and intent required"}

        try:
            result = gm_command(fairy_name, intent, intent_payload)
            self._commands_sent += 1
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_world_status(self, message):
        """
        Generate comprehensive world status snapshot.

        Combines: registry, postal stats, consciousness state.
        """
        if not HAS_GM:
            return {"ok": False, "error": "GM tools not available"}

        try:
            result = gm_world_status()
            self._last_world_status = result
            result["ok"] = True
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_status(self, message):
        """Get GMFairy status."""
        return {
            "ok": True,
            "gm_tools_available": HAS_GM,
            "commands_sent": self._commands_sent,
            "tracers_injected": self._tracers_injected,
            "has_cached_world_status": self._last_world_status is not None,
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
            "gm_tools_available": HAS_GM,
            "commands_sent": self._commands_sent,
            "tracers_injected": self._tracers_injected,
        }

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down (commands: {self._commands_sent}, tracers: {self._tracers_injected})...")
        return super().on_shutdown()
