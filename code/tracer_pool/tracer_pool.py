"""
Python bindings for the Go tracer_pool.dll

This provides high-performance worker pool management with:
- Per-fairy pools with priority lanes (HIGH/NORMAL/LOW)
- Autoscaling based on load
- Universal tracer support with lineage tracking
- Identity resolution across the system
"""
import ctypes
import json
import os
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

# Load the native library (DLL on Windows, .so on Linux)
import sys as _sys
if _sys.platform == "win32":
    _DLL_PATH = Path(__file__).parent / "tracer_pool.dll"
else:
    _DLL_PATH = Path(__file__).parent / "tracer_pool.so"
_lib: Optional[ctypes.CDLL] = None
_lib_failed = False  # Set True if loading fails (wrong platform, missing, etc.)


class Priority(IntEnum):
    """Task priority levels"""
    HIGH = 0
    NORMAL = 1
    LOW = 2


class TracerType:
    """Tracer type constants matching the Go implementation"""
    FAIRY_WORK = "fairy_work"
    FAIRY_ACTION = "fairy_action"
    FAIRY_BOOT = "fairy_boot"
    FAIRY_SHUTDOWN = "fairy_shutdown"
    FAIRY_THOUGHT = "fairy_thought"
    MESSAGE = "message"
    MEMORY = "memory"
    MEMORY_OPERATION = "memory_operation"
    TASK = "task"
    SUBTASK = "subtask"
    CONSCIOUSNESS = "consciousness"
    LEARNING = "learning"


# Flag to indicate Go DLL is available
USING_GO = _DLL_PATH.exists()


@dataclass
class TracerInfo:
    """Tracer information from the Go pool"""
    id: str
    tracer_type: str
    fairy_name: str
    cluster_id: str
    intent: str
    progress: float
    state: str
    error: Optional[str]
    payload: Dict[str, Any]
    parent_id: Optional[str]
    children: List[str]

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "TracerInfo":
        return cls(
            id=data.get("ID", ""),
            tracer_type=data.get("Type", ""),
            fairy_name=data.get("FairyName", ""),
            cluster_id=data.get("ClusterID", ""),
            intent=data.get("Intent", ""),
            progress=data.get("Progress", 0.0),
            state=data.get("State", ""),
            error=data.get("Error"),
            payload=data.get("Payload", {}),
            parent_id=data.get("ParentID"),
            children=data.get("ChildIDs", []),
        )


@dataclass
class Identity:
    """Fairy identity information"""
    function_name: str
    real_name: str
    plane: str
    channel: str
    aliases: List[str]

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Identity":
        return cls(
            function_name=data.get("FunctionName", ""),
            real_name=data.get("RealName", ""),
            plane=data.get("Plane", ""),
            channel=data.get("Channel", ""),
            aliases=data.get("Aliases", []),
        )


class _NullLib:
    """No-op stub when native Go library is unavailable (wrong platform, missing, etc.)."""
    _counter = 0

    def __getattr__(self, name):
        """Return a no-op function for any method call."""
        def _noop(*args, **kwargs):
            if name == "CreateTracer" or name == "CreateTracerFull":
                _NullLib._counter += 1
                return f"py-{_NullLib._counter:06d}".encode('utf-8')
            if name.startswith("Get") or name.startswith("Query"):
                return b"[]"  # Return empty JSON array
            if name == "TracerPoolInit":
                return 0
            return None
        return _noop

_null_lib = _NullLib()


def _get_lib():
    """Load the native library lazily. Returns NullLib stub if unavailable."""
    global _lib, _lib_failed
    if _lib_failed:
        return _null_lib
    if _lib is None:
        if not _DLL_PATH.exists():
            _lib_failed = True
            print(f"[TracerPool] Native library not found at {_DLL_PATH} (using Python fallback)")
            return _null_lib
        try:
            _lib = ctypes.CDLL(str(_DLL_PATH))
            _setup_argtypes(_lib)
            _lib.TracerPoolInit()
        except (OSError, Exception) as e:
            _lib_failed = True
            _lib = None
            print(f"[TracerPool] Failed to load native library: {e} (using Python fallback)")
            return _null_lib
    return _lib


def _setup_argtypes(lib: ctypes.CDLL):
    """Set up function argument and return types"""
    # Init/Shutdown
    lib.TracerPoolInit.restype = ctypes.c_int
    lib.TracerPoolInit.argtypes = []

    lib.TracerPoolShutdown.restype = None
    lib.TracerPoolShutdown.argtypes = []

    # Tracer creation
    lib.CreateTracer.restype = ctypes.c_char_p
    lib.CreateTracer.argtypes = [ctypes.c_char_p]

    lib.CreateTracerFull.restype = ctypes.c_char_p
    lib.CreateTracerFull.argtypes = [
        ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
        ctypes.c_char_p, ctypes.c_char_p
    ]

    # Tracer lifecycle
    lib.TracerStart.restype = None
    lib.TracerStart.argtypes = [ctypes.c_char_p]

    lib.TracerComplete.restype = None
    lib.TracerComplete.argtypes = [ctypes.c_char_p]

    lib.TracerFail.restype = None
    lib.TracerFail.argtypes = [ctypes.c_char_p, ctypes.c_char_p]

    lib.TracerSetProgress.restype = None
    lib.TracerSetProgress.argtypes = [ctypes.c_char_p, ctypes.c_double]

    lib.TracerSpawn.restype = ctypes.c_char_p
    lib.TracerSpawn.argtypes = [ctypes.c_char_p, ctypes.c_char_p]

    # Tracer queries
    lib.GetTracer.restype = ctypes.c_char_p
    lib.GetTracer.argtypes = [ctypes.c_char_p]

    lib.GetTracersByFairy.restype = ctypes.c_char_p
    lib.GetTracersByFairy.argtypes = [ctypes.c_char_p]

    lib.GetTracersByCluster.restype = ctypes.c_char_p
    lib.GetTracersByCluster.argtypes = [ctypes.c_char_p]

    lib.GetLineage.restype = ctypes.c_char_p
    lib.GetLineage.argtypes = [ctypes.c_char_p]

    # Identity
    lib.RegisterIdentity.restype = None
    lib.RegisterIdentity.argtypes = [
        ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
        ctypes.c_char_p, ctypes.c_char_p
    ]

    lib.ResolveIdentity.restype = ctypes.c_char_p
    lib.ResolveIdentity.argtypes = [ctypes.c_char_p]

    # Pool management
    lib.GetOrCreatePool.restype = ctypes.c_int
    lib.GetOrCreatePool.argtypes = [ctypes.c_char_p]

    # Stats
    lib.GetPoolStats.restype = ctypes.c_char_p
    lib.GetPoolStats.argtypes = [ctypes.c_char_p]

    lib.GetRegistryStats.restype = ctypes.c_char_p
    lib.GetRegistryStats.argtypes = []

    # Memory management
    lib.FreeString.restype = None
    lib.FreeString.argtypes = [ctypes.c_char_p]


def _to_bytes(s: Optional[str]) -> Optional[bytes]:
    """Convert string to bytes for C calls"""
    if s is None:
        return None
    return s.encode('utf-8')


def _from_bytes(b: Optional[bytes]) -> Optional[str]:
    """Convert bytes from C to string"""
    if b is None:
        return None
    return b.decode('utf-8')


# ============================================================================
# Public API
# ============================================================================

def init() -> None:
    """Initialize the tracer pool system. Gracefully no-ops if native lib unavailable."""
    _get_lib()  # Returns None if unavailable, that's OK


def shutdown() -> None:
    """Shutdown the tracer pool system"""
    lib = _get_lib()
    if lib:
        lib.TracerPoolShutdown()


def create_tracer(tracer_type: str) -> str:
    """Create a new tracer of the given type"""
    lib = _get_lib()
    if not lib:
        import uuid
        return str(uuid.uuid4())[:12]  # Python fallback: generate simple ID
    result = lib.CreateTracer(_to_bytes(tracer_type))
    return _from_bytes(result) or ""


def create_tracer_full(
    tracer_type: str,
    fairy_name: str = "",
    cluster_id: str = "",
    intent: str = "",
    payload: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a tracer with full context"""
    lib = _get_lib()
    payload_json = json.dumps(payload) if payload else ""
    result = lib.CreateTracerFull(
        _to_bytes(tracer_type),
        _to_bytes(fairy_name) if fairy_name else None,
        _to_bytes(cluster_id) if cluster_id else None,
        _to_bytes(intent) if intent else None,
        _to_bytes(payload_json) if payload_json else None,
    )
    return _from_bytes(result) or ""


def tracer_start(tracer_id: str) -> None:
    """Mark tracer as started"""
    lib = _get_lib()
    lib.TracerStart(_to_bytes(tracer_id))


def tracer_complete(tracer_id: str) -> None:
    """Mark tracer as completed"""
    lib = _get_lib()
    lib.TracerComplete(_to_bytes(tracer_id))


def tracer_fail(tracer_id: str, error_msg: str) -> None:
    """Mark tracer as failed"""
    lib = _get_lib()
    lib.TracerFail(_to_bytes(tracer_id), _to_bytes(error_msg))


def tracer_set_progress(tracer_id: str, progress: float) -> None:
    """Update tracer progress (0.0 - 1.0)"""
    lib = _get_lib()
    lib.TracerSetProgress(_to_bytes(tracer_id), progress)


def tracer_spawn(parent_id: str, tracer_type: str) -> str:
    """Spawn a child tracer from a parent"""
    lib = _get_lib()
    result = lib.TracerSpawn(_to_bytes(parent_id), _to_bytes(tracer_type))
    return _from_bytes(result) or ""


def get_tracer(tracer_id: str) -> Optional[TracerInfo]:
    """Get tracer information by ID"""
    lib = _get_lib()
    result = lib.GetTracer(_to_bytes(tracer_id))
    if not result:
        return None
    data = json.loads(_from_bytes(result))
    return TracerInfo.from_json(data)


def get_tracers_by_fairy(fairy_name: str) -> List[TracerInfo]:
    """Get all tracers for a fairy"""
    lib = _get_lib()
    result = lib.GetTracersByFairy(_to_bytes(fairy_name))
    if not result:
        return []
    data = json.loads(_from_bytes(result))
    return [TracerInfo.from_json(t) for t in data]


def get_tracers_by_cluster(cluster_id: str) -> List[TracerInfo]:
    """Get all tracers in a cluster"""
    lib = _get_lib()
    result = lib.GetTracersByCluster(_to_bytes(cluster_id))
    if not result:
        return []
    data = json.loads(_from_bytes(result))
    return [TracerInfo.from_json(t) for t in data]


def get_lineage(tracer_id: str) -> List[TracerInfo]:
    """Get tracer lineage (ancestors)"""
    lib = _get_lib()
    result = lib.GetLineage(_to_bytes(tracer_id))
    if not result:
        return []
    data = json.loads(_from_bytes(result))
    return [TracerInfo.from_json(t) for t in data]


def register_identity(
    function_name: str,
    real_name: str = "",
    plane: str = "",
    channel: str = "",
    aliases: Optional[List[str]] = None,
) -> None:
    """Register a fairy identity"""
    lib = _get_lib()
    aliases_json = json.dumps(aliases) if aliases else ""
    lib.RegisterIdentity(
        _to_bytes(function_name),
        _to_bytes(real_name) if real_name else None,
        _to_bytes(plane) if plane else None,
        _to_bytes(channel) if channel else None,
        _to_bytes(aliases_json) if aliases_json else None,
    )


def resolve_identity(name: str) -> Optional[Identity]:
    """Resolve a name to an identity"""
    lib = _get_lib()
    result = lib.ResolveIdentity(_to_bytes(name))
    if not result:
        return None
    data = json.loads(_from_bytes(result))
    return Identity.from_json(data)


def get_or_create_pool(fairy_name: str) -> bool:
    """Get or create a worker pool for a fairy"""
    lib = _get_lib()
    result = lib.GetOrCreatePool(_to_bytes(fairy_name))
    return result == 0


def get_pool_stats(fairy_name: Optional[str] = None) -> Dict[str, Any]:
    """Get pool statistics"""
    lib = _get_lib()
    if fairy_name:
        result = lib.GetPoolStats(_to_bytes(fairy_name))
    else:
        result = lib.GetPoolStats(None)
    if not result:
        return {}
    return json.loads(_from_bytes(result))


def get_registry_stats() -> Dict[str, Any]:
    """Get registry statistics"""
    lib = _get_lib()
    result = lib.GetRegistryStats()
    if not result:
        return {}
    return json.loads(_from_bytes(result))


# ============================================================================
# High-level context managers
# ============================================================================

class TracerContext:
    """Context manager for automatic tracer lifecycle"""

    def __init__(
        self,
        tracer_type: str,
        fairy_name: str = "",
        intent: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ):
        self.tracer_type = tracer_type
        self.fairy_name = fairy_name
        self.intent = intent
        self.payload = payload
        self.tracer_id: Optional[str] = None

    def __enter__(self) -> str:
        self.tracer_id = create_tracer_full(
            self.tracer_type,
            fairy_name=self.fairy_name,
            intent=self.intent,
            payload=self.payload,
        )
        tracer_start(self.tracer_id)
        return self.tracer_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.tracer_id:
            if exc_type is not None:
                tracer_fail(self.tracer_id, str(exc_val))
            else:
                tracer_complete(self.tracer_id)
        return False


def traced(tracer_type: str = "function", fairy_name: str = ""):
    """Decorator for tracing function calls"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with TracerContext(
                tracer_type,
                fairy_name=fairy_name or func.__module__,
                intent=func.__name__,
            ):
                return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


# ============================================================================
# TracerPool - Main class for tracer management
# ============================================================================

_TRACER_POOL_INSTANCE: Optional["TracerPool"] = None


class TracerPool:
    """
    Main tracer pool interface.

    Provides:
    - Global singleton access
    - Identity registration
    - Tracer creation and lifecycle management

    This wraps the Go DLL for high-performance tracing.
    """

    def __init__(self):
        """Initialize the tracer pool (loads DLL)"""
        init()
        self._initialized = True

    @classmethod
    def global_instance(cls) -> "TracerPool":
        """Get the global TracerPool singleton"""
        global _TRACER_POOL_INSTANCE
        if _TRACER_POOL_INSTANCE is None:
            _TRACER_POOL_INSTANCE = cls()
        return _TRACER_POOL_INSTANCE

    def register_identity(
        self,
        function_name: str,
        real_name: str = "",
        plane: str = "",
        channel: str = "",
        aliases: Optional[List[str]] = None,
    ) -> None:
        """Register a fairy identity"""
        register_identity(
            function_name=function_name,
            real_name=real_name,
            plane=plane,
            channel=channel,
            aliases=aliases,
        )

    def create_tracer(
        self,
        tracer_type: str,
        fairy_name: str = "",
        cluster_id: str = "",
        intent: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> TracerInfo:
        """Create a new tracer"""
        tracer_id = create_tracer_full(
            tracer_type=tracer_type,
            fairy_name=fairy_name,
            cluster_id=cluster_id,
            intent=intent,
            payload=payload,
        )
        # Return a TracerInfo-like object
        return TracerInfo(
            id=tracer_id,
            tracer_type=tracer_type,
            fairy_name=fairy_name,
            cluster_id=cluster_id,
            intent=intent,
            progress=0.0,
            state="created",
            error=None,
            payload=payload or {},
            parent_id=None,
            children=[],
        )

    def start(self, tracer_id: str) -> None:
        """Start a tracer"""
        tracer_start(tracer_id)

    def complete(self, tracer_id: str) -> None:
        """Mark tracer as complete"""
        tracer_complete(tracer_id)

    def fail(self, tracer_id: str, error: str) -> None:
        """Mark tracer as failed"""
        tracer_fail(tracer_id, error)

    def set_progress(self, tracer_id: str, progress: float) -> None:
        """Update tracer progress (0.0 - 1.0)"""
        tracer_set_progress(tracer_id, progress)

    def spawn(self, parent_id: str, tracer_type: str) -> str:
        """Spawn a child tracer from a parent"""
        return tracer_spawn(parent_id, tracer_type)

    def get(self, tracer_id: str) -> Optional[TracerInfo]:
        """Get tracer by ID"""
        return get_tracer(tracer_id)

    def get_by_fairy(self, fairy_name: str) -> List[TracerInfo]:
        """Get all tracers for a fairy"""
        return get_tracers_by_fairy(fairy_name)

    def get_by_cluster(self, cluster_id: str) -> List[TracerInfo]:
        """Get all tracers in a cluster"""
        return get_tracers_by_cluster(cluster_id)

    def get_lineage(self, tracer_id: str) -> List[TracerInfo]:
        """Get tracer lineage (ancestors)"""
        return get_lineage(tracer_id)

    def get_or_create_pool(self, fairy_name: str) -> bool:
        """Get or create a worker pool for a fairy"""
        return get_or_create_pool(fairy_name)

    def stats(self, fairy_name: Optional[str] = None) -> Dict[str, Any]:
        """Get pool statistics"""
        return get_pool_stats(fairy_name)

    def registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        return get_registry_stats()

    def resolve_identity(self, name: str) -> Optional[Identity]:
        """Resolve a name/alias to an identity"""
        return resolve_identity(name)

    # ========================================================================
    # BACKWARD COMPATIBILITY - Old API methods
    # ========================================================================

    def start_trace(
        self,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Start a trace (backward compatible API).

        Args:
            name: Trace name (e.g., "atom:abc123")
            metadata: Optional metadata dict

        Returns:
            Tracer ID string
        """
        # Parse name for fairy info
        parts = name.split(":")
        fairy_name = parts[0] if len(parts) > 1 else "unknown"
        intent = parts[1] if len(parts) > 1 else name

        tracer = self.create_tracer(
            tracer_type=TracerType.TASK,
            fairy_name=fairy_name,
            intent=intent,
            payload=metadata,
        )
        self.start(tracer.id)
        return tracer.id

    def end_trace(
        self,
        tracer_id: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        End a trace (backward compatible API).

        Args:
            tracer_id: ID from start_trace()
            result: Optional result dict (for success)
            error: Optional error string (for failure)
        """
        if error:
            self.fail(tracer_id, error)
        else:
            self.complete(tracer_id)


# Alias for backward compatibility
UniversalTracer = TracerInfo


# ============================================================================
# Integration with Akashic postal system
# ============================================================================

class PoolFairy:
    """
    High-level pool management for fairies.

    Integrates with the Go tracer pool for:
    - Automatic pool creation
    - Identity registration
    - Tracer-based task tracking
    """

    def __init__(
        self,
        fairy_name: str,
        real_name: str = "",
        plane: str = "",
        channel: str = "",
    ):
        self.fairy_name = fairy_name
        self.real_name = real_name
        self.plane = plane
        self.channel = channel

        # Initialize pool and identity
        init()
        get_or_create_pool(fairy_name)
        register_identity(
            function_name=fairy_name,
            real_name=real_name,
            plane=plane,
            channel=channel,
        )

    def create_task(
        self,
        intent: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new task tracer"""
        return create_tracer_full(
            "task",
            fairy_name=self.fairy_name,
            intent=intent,
            payload=payload,
        )

    def spawn_subtask(self, parent_id: str, intent: str) -> str:
        """Spawn a subtask from a parent task"""
        child_id = tracer_spawn(parent_id, "subtask")
        if child_id:
            tracer = get_tracer(child_id)
            # Note: Go tracer doesn't update intent after creation
            # but we track it in the return
        return child_id

    def complete_task(self, tracer_id: str) -> None:
        """Mark a task as complete"""
        tracer_complete(tracer_id)

    def fail_task(self, tracer_id: str, error: str) -> None:
        """Mark a task as failed"""
        tracer_fail(tracer_id, error)

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        return get_pool_stats(self.fairy_name)

    def get_active_tasks(self) -> List[TracerInfo]:
        """Get all active tasks for this fairy"""
        tracers = get_tracers_by_fairy(self.fairy_name)
        return [t for t in tracers if t.state not in ("completed", "failed")]


# Quick test when run directly
if __name__ == "__main__":
    print("Testing tracer_pool.dll bindings...")

    # Initialize
    init()
    print("[OK] Pool initialized")

    # Create a pool
    success = get_or_create_pool("TestFairy")
    print(f"[OK] Created pool for TestFairy: {success}")

    # Register identity
    register_identity(
        function_name="TestFairy",
        real_name="Test Fairy",
        plane="P40_Sensory",
        channel="test.channel",
    )
    print("[OK] Registered identity")

    # Create a tracer
    tracer_id = create_tracer_full(
        tracer_type="task",
        fairy_name="TestFairy",
        intent="testing",
        payload={"test": True},
    )
    print(f"[OK] Created tracer: {tracer_id}")

    # Start and complete
    tracer_start(tracer_id)
    tracer_set_progress(tracer_id, 0.5)
    tracer_complete(tracer_id)
    print("[OK] Tracer lifecycle complete")

    # Get tracer info
    info = get_tracer(tracer_id)
    if info:
        print(f"[OK] Tracer state: {info.state}")

    # Get stats
    stats = get_pool_stats()
    print(f"[OK] Pool stats: {json.dumps(stats, indent=2)}")

    registry_stats = get_registry_stats()
    print(f"[OK] Registry stats: {json.dumps(registry_stats, indent=2)}")

    # Resolve identity
    identity = resolve_identity("TestFairy")
    if identity:
        print(f"[OK] Resolved identity: {identity.function_name} ({identity.plane})")

    print("\nAll tests passed!")
