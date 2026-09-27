"""
DirectoryFairy - The Control Panel of the Akashic System

CONSOLIDATED SINGLE-FILE FAIRY

This file contains:
- DirectoryFairy (main fairy class)
- RegistryFunction (registration logic)
- RouterFunction (query routing)
- HealthFunction (health aggregation)

"I am the map. All roads pass through me."

Central registry, routing, and health aggregation.
I know every fairy, every function, every capability.
I don't do the work - I know who does.
"""

from __future__ import annotations
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, TypeVar, Generic

# =============================================================================
# PATH SETUP
# =============================================================================

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

# =============================================================================
# IMPORTS
# =============================================================================

try:
    from core.fairy import Fairy, FairyStatus
except ImportError:
    # Minimal fallback
    class FairyStatus:
        READY = "ready"
        RUNNING = "running"
        FAILED = "failed"

    class Fairy:
        def __init__(self, name="", plane="", description="", mantra=""):
            self.name = name
            self.plane = plane
            self.description = description
            self.mantra = mantra
            self._started = False

    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



        def boot(self):
            self._started = True
            return True
        def shutdown(self):
            self._started = False
        def register_function(self, f): pass
        def register_intent(self, *args, **kwargs): pass
        def subscribe(self, *args, **kwargs): pass
        def publish(self, *args, **kwargs): pass

try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        def _init_tracer_worker(self): pass

try:
    from core.directory import Directory, get_directory
except ImportError:
    # Minimal Directory fallback
    class Directory:
        def __init__(self):
            self._fairies: Dict[str, Any] = {}
            self._capabilities: Dict[str, Set[str]] = {}
            self._last_seen: Dict[str, float] = {}

        def register(self, fairy, capabilities=None):
            name = fairy.name if hasattr(fairy, 'name') else str(fairy)
            self._fairies[name] = fairy
            self._capabilities[name] = capabilities or set()
            self._last_seen[name] = time.time()
            return True

        def unregister(self, name: str) -> bool:
            if name in self._fairies:
                del self._fairies[name]
                self._capabilities.pop(name, None)
                self._last_seen.pop(name, None)
                return True
            return False

        def get(self, name: str):
            return self._fairies.get(name)

        def touch(self, name: str):
            self._last_seen[name] = time.time()

        def list_names(self) -> List[str]:
            return list(self._fairies.keys())

        def find_by_capability(self, cap: str) -> List[Any]:
            return [f for name, f in self._fairies.items() if cap in self._capabilities.get(name, set())]

        def find_by_plane(self, plane: str) -> List[Any]:
            return [f for f in self._fairies.values() if getattr(f, 'plane', '') == plane]

        def find_by_status(self, status) -> List[Any]:
            return [f for f in self._fairies.values() if getattr(f, 'status', None) == status]

        def failed_fairies(self) -> List[Any]:
            return [f for f in self._fairies.values() if getattr(f, 'status', None) == FairyStatus.FAILED]

        def dead_fairies(self, threshold: float = 300.0) -> List[str]:
            now = time.time()
            return [name for name, last in self._last_seen.items() if now - last > threshold]

        def system_health(self) -> Dict[str, Any]:
            total = len(self._fairies)
            failed = len(self.failed_fairies())
            return {
                "total": total,
                "healthy": total - failed,
                "failed": failed,
                "health_percent": ((total - failed) / total * 100) if total > 0 else 100
            }

        def fairy_table(self) -> str:
            lines = ["| Name | Plane | Status |", "|------|-------|--------|"]
            for name, fairy in self._fairies.items():
                plane = getattr(fairy, 'plane', 'unknown')
                status = getattr(fairy, 'status', 'unknown')
                lines.append(f"| {name} | {plane} | {status} |")
            return "\n".join(lines)

        def to_dict(self) -> Dict[str, Any]:
            return {
                "fairies": {name: {"capabilities": list(caps)} for name, caps in self._capabilities.items()},
                "health": self.system_health()
            }

    _directory_singleton = None
    def get_directory() -> Directory:
        global _directory_singleton
        if _directory_singleton is None:
            _directory_singleton = Directory()
        return _directory_singleton

try:
    from fairies.P10_Memory.memory_cards import CharacterSheetMixin
except ImportError:
    class CharacterSheetMixin:
        def get_character_sheet(self): return None
        def _get_character_status(self): return "unknown"

try:
    from core.function import Function
except ImportError:
    T = TypeVar('T')
    class Function(Generic[T]):
        def __init__(self, name="", description="", function_type=""):
            self.name = name
            self.description = description
            self.function_type = function_type
            self.checklist = type('Checklist', (), {'add': lambda s, *a: None})()
        def execute(self, *args, **kwargs) -> T:
            raise NotImplementedError

try:
    from core.config import get_config
except ImportError:
    def get_config():
        return {"fairy.dead_threshold_seconds": 300.0}


# =============================================================================
# REGISTRY FUNCTION - Stores fairy registrations
# =============================================================================

class RegistryFunction(Function[bool]):
    """
    Stores all fairy registrations.

    This is the core registration logic - the Directory uses this
    to actually store and index fairies.
    """

    def __init__(self, directory: Directory):
        super().__init__(
            name="registry",
            description="Stores fairy registrations and maintains indexes",
            function_type="infrastructure"
        )
        self._directory = directory

        self.checklist.add(
            "directory_ref",
            "Has reference to directory",
            lambda: self._directory is not None
        )

    def execute(
        self,
        action: str,
        fairy=None,
        name: str = None,
        capabilities: Set[str] = None
    ) -> bool:
        """
        Execute registry operation.

        Args:
            action: "register", "unregister", or "touch"
            fairy: Fairy instance (for register)
            name: Fairy name (for unregister/touch)
            capabilities: Set of capabilities (for register)

        Returns:
            True if operation succeeded
        """
        if action == "register":
            if fairy is None:
                return False
            return self._directory.register(fairy, capabilities or set())

        elif action == "unregister":
            if name is None:
                return False
            return self._directory.unregister(name)

        elif action == "touch":
            if name is None:
                return False
            self._directory.touch(name)
            return True

        return False


# =============================================================================
# ROUTER FUNCTION - Routes queries to fairies
# =============================================================================

class RouterFunction(Function[List[str]]):
    """
    Routes queries to the right fairies.

    Find by capability, plane, status, or intent.
    Returns list of fairy names that match the query.
    """

    def __init__(self, directory: Directory):
        super().__init__(
            name="router",
            description="Routes queries to matching fairies",
            function_type="infrastructure"
        )
        self._directory = directory

        self.checklist.add(
            "directory_ref",
            "Has reference to directory",
            lambda: self._directory is not None
        )

    def execute(
        self,
        query_type: str,
        query_value: str = None
    ) -> List[str]:
        """
        Execute routing query.

        Args:
            query_type: "capability", "plane", "status", or "all"
            query_value: The value to search for

        Returns:
            List of matching fairy names
        """
        if query_type == "capability":
            if not query_value:
                return []
            fairies = self._directory.find_by_capability(query_value)
            return [f.name for f in fairies]

        elif query_type == "plane":
            if not query_value:
                return []
            fairies = self._directory.find_by_plane(query_value)
            return [f.name for f in fairies]

        elif query_type == "status":
            if not query_value:
                return []
            try:
                status = FairyStatus(query_value)
                fairies = self._directory.find_by_status(status)
                return [f.name for f in fairies]
            except (ValueError, AttributeError):
                return []

        elif query_type == "all":
            return self._directory.list_names()

        return []


# =============================================================================
# HEALTH FUNCTION - Aggregates system health
# =============================================================================

class HealthFunction(Function[Dict[str, Any]]):
    """
    Aggregates system health into a single view.

    Provides:
    - Overall health percentage
    - Fairy counts by status
    - Failed fairy list
    - Dead fairy detection
    """

    def __init__(self, directory: Directory):
        super().__init__(
            name="health",
            description="Aggregates system health",
            function_type="infrastructure"
        )
        self._directory = directory

        self.checklist.add(
            "directory_ref",
            "Has reference to directory",
            lambda: self._directory is not None
        )

    def execute(
        self,
        query_type: str = "summary",
        threshold_seconds: float = None
    ) -> Dict[str, Any]:
        """
        Execute health query.

        Args:
            query_type: "summary", "failed", "dead", or "full"
            threshold_seconds: For dead detection (default from config)

        Returns:
            Health information dict
        """
        if query_type == "summary":
            return self._directory.system_health()

        elif query_type == "failed":
            failed = self._directory.failed_fairies()
            return {
                "count": len(failed),
                "fairies": [f.name if hasattr(f, 'name') else str(f) for f in failed]
            }

        elif query_type == "dead":
            if threshold_seconds is None:
                config = get_config()
                threshold_seconds = config.get("fairy.dead_threshold_seconds", 300.0)

            dead = self._directory.dead_fairies(threshold_seconds)
            return {
                "count": len(dead),
                "fairies": dead,
                "threshold_seconds": threshold_seconds
            }

        elif query_type == "full":
            return self._directory.to_dict()

        return {}


# =============================================================================
# DIRECTORY FAIRY - The Main Fairy
# =============================================================================

class DirectoryFairy(Fairy, CharacterSheetMixin, TracerWorkerMixin):
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

        # Create functions (inline)
        self._registry = RegistryFunction(self._directory)
        self._router = RouterFunction(self._directory)
        self._health = HealthFunction(self._directory)

        # Register functions
        self.register_function(self._registry)
        self.register_function(self._router)
        self.register_function(self._health)

        # Add extra checklist items
        if hasattr(self, 'checklist') and hasattr(self.checklist, 'add'):
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

    # =========================================================================
    # INTENT HANDLERS
    # =========================================================================

    def _intent_get_fairy(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get fairy by name."""
        fairy = self._directory.get(params["name"])
        if fairy:
            if hasattr(fairy, 'to_dict'):
                return fairy.to_dict()
            return {"name": getattr(fairy, 'name', str(fairy))}
        return None

    def _intent_find_by_capability(self, params: Dict[str, Any]) -> List[str]:
        """Find fairies with capability."""
        fairies = self._directory.find_by_capability(params["capability"])
        return [f.name if hasattr(f, 'name') else str(f) for f in fairies]

    def _intent_find_by_plane(self, params: Dict[str, Any]) -> List[str]:
        """Find fairies in plane."""
        fairies = self._directory.find_by_plane(params["plane"])
        return [f.name if hasattr(f, 'name') else str(f) for f in fairies]

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

        if hasattr(fairy, 'shutdown'):
            fairy.shutdown()
        if hasattr(fairy, 'boot'):
            return fairy.boot()
        return False

    # =========================================================================
    # ERROR ROUTING TO TRACERDAEMON
    # =========================================================================

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
                        fairies.append(sheet.to_dict() if hasattr(sheet, 'to_dict') else {"name": name})
                        status = getattr(sheet, 'status', 'unknown')
                        if status == 'alive':
                            alive_count += 1
                        elif status == 'dead':
                            dead_count += 1
                        elif status == 'degraded':
                            degraded_count += 1
                        continue

                # Fallback to basic dict
                fairies.append({
                    "fairy_name": name,
                    "fairy_class": fairy.__class__.__name__,
                    "plane": getattr(fairy, 'ACTOR_PLANE', getattr(fairy, 'plane', 'unknown')),
                    "status": "alive" if (
                        (hasattr(fairy, 'is_running') and fairy.is_running()) or
                        (hasattr(fairy, '_started') and fairy._started) or
                        (hasattr(fairy, '_running') and fairy._running) or
                        (hasattr(fairy, '_boot_phase') and fairy._boot_phase == 'running')
                    ) else "unknown"
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

    # =========================================================================
    # MESSAGE HANDLERS
    # =========================================================================

    def _setup_subscriptions(self):
        """Set up postal subscriptions."""
        self.subscribe("directory.*", self._on_directory_message)
        self.subscribe("fairy.register", self._on_fairy_register)
        self.subscribe("fairy.unregister", self._on_fairy_unregister)
        self.subscribe("fairy.heartbeat", self._on_heartbeat)
        self.subscribe("system.health_check", self._on_health_check)

    def _on_directory_message(self, payload: Dict[str, Any]):
        """Handle directory messages."""
        sender = payload.get("_sender")
        if sender:
            self._directory.touch(sender)

    def _on_fairy_register(self, payload: Dict[str, Any]):
        """Handle fairy registration request."""
        fairy_data = payload.get("fairy")
        if fairy_data:
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

    # =========================================================================
    # BOOT
    # =========================================================================

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

    # =========================================================================
    # CONVENIENCE ACCESSORS
    # =========================================================================

    @property
    def directory(self) -> Directory:
        """Direct access to the directory."""
        return self._directory

    def fairy_table(self) -> str:
        """Get ASCII table of all fairies."""
        return self._directory.fairy_table()


# =============================================================================
# SINGLETON
# =============================================================================

_instance: Optional[DirectoryFairy] = None

def get_directory_fairy() -> DirectoryFairy:
    """Get or create the DirectoryFairy singleton."""
    global _instance
    if _instance is None:
        _instance = DirectoryFairy()
        _instance.boot()
    return _instance


# =============================================================================
# MAIN - For testing
# =============================================================================

if __name__ == "__main__":
    print("=== DirectoryFairy Test ===\n")

    fairy = DirectoryFairy()
    fairy.boot()

    print(f"Name: {fairy.name}")
    print(f"Plane: {fairy.plane}")
    print(f"Mantra: {fairy.mantra}")
    print(f"Directory entries: {fairy.directory.list_names()}")
    print(f"\nHealth: {fairy._health.execute('summary')}")
    print(f"\nFairy Table:\n{fairy.fairy_table()}")
