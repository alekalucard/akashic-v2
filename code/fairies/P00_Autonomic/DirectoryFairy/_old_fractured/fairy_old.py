# DirectoryFairy - The Control Panel
#
# Central registry, routing, and health aggregation.
# See DIRECTIVE.md for full documentation.

from __future__ import annotations
from typing import Dict, Any, Optional, List

import sys
from pathlib import Path

# Add core to path for imports
core_path = Path(__file__).parent.parent.parent.parent / "core"
sys.path.insert(0, str(core_path))

from core.fairy import Fairy, FairyStatus
try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        def _init_tracer_worker(self): pass
from core.directory import Directory, get_directory

# Import CharacterSheetMixin for self-reporting
try:
    from fairies.P10_Memory.memory_cards import CharacterSheetMixin
except ImportError:
    class CharacterSheetMixin:
        def get_character_sheet(self): return None
        def _get_character_status(self): return "unknown"

# Import local functions
from .functions.registry import RegistryFunction
from .functions.router import RouterFunction
from .functions.health import HealthFunction


class DirectoryFairy(Fairy, CharacterSheetMixin):
    """
    The Control Panel of the Akashic system.

    I know every fairy, every function, every capability.
    I don't do the work - I know who does.
    """

    # Registration (required for Fifth Ring)
    ACTOR_NAME = "DirectoryFairy"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "directory"

    PURPOSE = "Know every fairy and route every request"
    MANTRA = "I am the map. All roads pass through me."

    # Heartbeat enabled - directory is critical infrastructure
    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 3

    def __init__(self):
        super().__init__(
            name="DirectoryFairy",
            plane="P00",
            description="Central registry, routing, and control panel for the entire system",
            mantra="I am the map. All roads pass through me."
        )
        self._init_tracer_worker()

        # Create the directory singleton (we ARE the directory)
        self._directory = get_directory()

        # TracerDaemon reference for error routing
        self._tracer_daemon = None
        self._error_count = 0

        # Create functions
        self._registry = RegistryFunction(self._directory)
        self._router = RouterFunction(self._directory)
        self._health = HealthFunction(self._directory)

        # Register functions
        self.register_function(self._registry)
        self.register_function(self._router)
        self.register_function(self._health)

        # Add extra checklist items
        self.checklist.add(
            "directory_ready",
            "Directory singleton initialized",
            lambda: self._directory is not None
        )

        # Register intents
        self._register_intents()

    def _register_intents(self):
        """Register all intents this fairy provides."""

        self.register_intent(
            "get_fairy",
            "Get a fairy by name",
            self._intent_get_fairy,
            required_params=["name"]
        )

        self.register_intent(
            "find_by_capability",
            "Find fairies with a given capability",
            self._intent_find_by_capability,
            required_params=["capability"]
        )

        self.register_intent(
            "find_by_plane",
            "Find fairies in a given plane",
            self._intent_find_by_plane,
            required_params=["plane"]
        )

        self.register_intent(
            "system_health",
            "Get aggregate system health",
            self._intent_system_health
        )

        self.register_intent(
            "list_all",
            "List all fairy names",
            self._intent_list_all
        )

        self.register_intent(
            "restart_fairy",
            "Restart a failed fairy",
            self._intent_restart_fairy,
            required_params=["name"]
        )

    # ═══════════════════════════════════════════════════════════════════════
    # INTENT HANDLERS
    # ═══════════════════════════════════════════════════════════════════════

    def _intent_get_fairy(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get fairy by name."""
        fairy = self._directory.get(params["name"])
        if fairy:
            return fairy.to_dict()
        return None

    def _intent_find_by_capability(self, params: Dict[str, Any]) -> List[str]:
        """Find fairies with capability."""
        fairies = self._directory.find_by_capability(params["capability"])
        return [f.name for f in fairies]

    def _intent_find_by_plane(self, params: Dict[str, Any]) -> List[str]:
        """Find fairies in plane."""
        fairies = self._directory.find_by_plane(params["plane"])
        return [f.name for f in fairies]

    def _intent_system_health(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get system health."""
        return self._directory.system_health()

    def _intent_list_all(self, params: Dict[str, Any]) -> List[str]:
        """List all fairy names."""
        return self._directory.list_names()

    def _intent_restart_fairy(self, params: Dict[str, Any]) -> bool:
        """Restart a fairy."""
        fairy = self._directory.get(params["name"])
        if not fairy:
            return False

        fairy.shutdown()
        return fairy.boot()

    # ═══════════════════════════════════════════════════════════════════════
    # ERROR ROUTING TO TRACERDAEMON
    # ═══════════════════════════════════════════════════════════════════════

    def report_error(self, error_payload: Dict[str, Any]) -> bool:
        """
        Route an error to TracerDaemon.

        Error payload should include:
        - fairy_id: ID of the fairy that had the error
        - fairy_name: Name of the fairy
        - error_type: Type of error (exception, timeout, etc.)
        - error_message: The error message
        - timestamp: When it occurred (optional, defaults to now)

        Returns True if error was routed successfully.
        """
        import time

        # Track our own error count
        self._error_count += 1

        # Ensure timestamp
        if 'timestamp' not in error_payload:
            error_payload['timestamp'] = time.time()

        # Update fairy's error count in directory
        fairy_name = error_payload.get('fairy_name')
        if fairy_name:
            fairy = self._directory.get(fairy_name)
            if fairy and hasattr(fairy, '_error_count'):
                fairy._error_count = getattr(fairy, '_error_count', 0) + 1

        # Get TracerDaemon if we don't have it
        if not self._tracer_daemon:
            self._tracer_daemon = self._directory.get("tracer.daemon")

        # Route to TracerDaemon
        if self._tracer_daemon:
            try:
                # Use ingest_health_packet which TracerDaemon supports
                if hasattr(self._tracer_daemon, 'ingest_health_packet'):
                    self._tracer_daemon.ingest_health_packet({
                        "src_organ": error_payload.get('fairy_name', 'unknown'),
                        "src_plane": error_payload.get('plane', 'P00'),
                        "error_type": error_payload.get('error_type', 'unknown'),
                        "error_message": error_payload.get('error_message', ''),
                        "timestamp": error_payload.get('timestamp'),
                        "severity": error_payload.get('severity', 'error')
                    })
                    return True
            except Exception as e:
                print(f"[DirectoryFairy] Failed to route error to TracerDaemon: {e}")

        # Fallback: publish to postal if available
        try:
            if hasattr(self, 'publish'):
                self.publish("fairy.error", error_payload)
                return True
        except Exception:
            pass

        return False

    def get_status_screen(self) -> Dict[str, Any]:
        """
        Generate status display for GUI.
        Returns aggregated status of all fairies.
        """
        from datetime import datetime

        fairies = []
        alive_count = 0
        dead_count = 0
        degraded_count = 0

        for name in self._directory.list_names():
            fairy = self._directory.get(name)
            if fairy:
                # Try to get CharacterSheet if available
                if hasattr(fairy, 'get_character_sheet'):
                    sheet = fairy.get_character_sheet()
                    if sheet:
                        fairies.append(sheet.to_dict())
                        if sheet.status == 'alive':
                            alive_count += 1
                        elif sheet.status == 'dead':
                            dead_count += 1
                        elif sheet.status == 'degraded':
                            degraded_count += 1
                        continue

                # Fallback to basic dict
                fairies.append({
                    "fairy_name": name,
                    "fairy_class": fairy.__class__.__name__,
                    "plane": getattr(fairy, 'ACTOR_PLANE', 'unknown'),
                    "status": "alive" if hasattr(fairy, '_started') and fairy._started else "unknown"
                })
                alive_count += 1

        return {
            "timestamp": datetime.now().isoformat(),
            "total_fairies": len(fairies),
            "alive": alive_count,
            "dead": dead_count,
            "degraded": degraded_count,
            "fairies": fairies
        }

    # ═══════════════════════════════════════════════════════════════════════
    # MESSAGE HANDLERS
    # ═══════════════════════════════════════════════════════════════════════

    def _setup_subscriptions(self):
        """Set up postal subscriptions."""
        self.subscribe("directory.*", self._on_directory_message)
        self.subscribe("fairy.register", self._on_fairy_register)
        self.subscribe("fairy.unregister", self._on_fairy_unregister)
        self.subscribe("fairy.heartbeat", self._on_heartbeat)
        self.subscribe("system.health_check", self._on_health_check)

    def _on_directory_message(self, payload: Dict[str, Any]):
        """Handle directory messages."""
        # Touch sender
        sender = payload.get("_sender")
        if sender:
            self._directory.touch(sender)

    def _on_fairy_register(self, payload: Dict[str, Any]):
        """Handle fairy registration request."""
        fairy_data = payload.get("fairy")
        capabilities = set(payload.get("capabilities", []))

        if fairy_data:
            # This would need to reconstruct the fairy or receive the actual object
            # For now, log the attempt
            print(f"[DirectoryFairy] Registration request: {fairy_data.get('name', 'unknown')}")

    def _on_fairy_unregister(self, payload: Dict[str, Any]):
        """Handle fairy unregistration."""
        name = payload.get("name")
        if name:
            self._directory.unregister(name)

    def _on_heartbeat(self, payload: Dict[str, Any]):
        """Handle fairy heartbeat."""
        sender = payload.get("_sender")
        if sender:
            self._directory.touch(sender)

    def _on_health_check(self, payload: Dict[str, Any]):
        """Handle health check request."""
        self.publish("system.health_response", {
            "health": self._directory.system_health(),
            "fairy_table": self._directory.fairy_table()
        })

    # ═══════════════════════════════════════════════════════════════════════
    # BOOT
    # ═══════════════════════════════════════════════════════════════════════

    def boot(self) -> bool:
        """Boot the DirectoryFairy."""
        # Set up subscriptions first
        self._setup_subscriptions()

        # Register self with directory
        self._directory.register(self, capabilities={
            "registry", "routing", "health_aggregation", "control_panel"
        })

        # Call parent boot
        return super().boot()

    # ═══════════════════════════════════════════════════════════════════════
    # CONVENIENCE ACCESSORS
    # ═══════════════════════════════════════════════════════════════════════

    @property
    def directory(self) -> Directory:
        """Direct access to the directory."""
        return self._directory

    def fairy_table(self) -> str:
        """Get ASCII table of all fairies."""
        return self._directory.fairy_table()
