"""
Tracer Pool - Go-based worker pools with universal tracing for Akashic.

This provides Python bindings to the Go tracer pool via ctypes.

Usage:
    from tracer_pool import TracerPool, UniversalTracer

    # Initialize
    pool = TracerPool.global_instance()

    # Create a tracer
    tracer = pool.create_tracer("fairy_work", fairy_name="DirectoryFairy")

    # Submit work
    pool.submit("DirectoryFairy", lambda: do_work())

    # Get tracers for perfect recall
    tracers = pool.get_by_cluster("cluster_123")
"""

__version__ = "0.1.0"

import ctypes
import json
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import threading


# Determine library path
def _find_library():
    """Find the compiled Go library."""
    if platform.system() == "Windows":
        lib_name = "tracer_pool.dll"
    elif platform.system() == "Darwin":
        lib_name = "tracer_pool.dylib"
    else:
        lib_name = "tracer_pool.so"

    # Check common locations
    candidates = [
        Path(__file__).parent / lib_name,
        Path(__file__).parent.parent / lib_name,
        Path(__file__).parent.parent.parent / lib_name,
        Path(__file__).parent.parent.parent / "build" / lib_name,
    ]

    for path in candidates:
        if path.exists():
            return str(path)

    return None


# Try to load the Go library
_lib_path = _find_library()
_lib = None
_using_go = False

if _lib_path:
    try:
        _lib = ctypes.CDLL(_lib_path)
        _using_go = True

        # Set up function signatures
        _lib.TracerPoolInit.restype = ctypes.c_int
        _lib.CreateTracer.argtypes = [ctypes.c_char_p]
        _lib.CreateTracer.restype = ctypes.c_char_p
        _lib.CreateTracerFull.argtypes = [
            ctypes.c_char_p,  # tracerType
            ctypes.c_char_p,  # fairyName
            ctypes.c_char_p,  # clusterID
            ctypes.c_char_p,  # intent
            ctypes.c_char_p,  # payloadJSON
        ]
        _lib.CreateTracerFull.restype = ctypes.c_char_p
        _lib.TracerStart.argtypes = [ctypes.c_char_p]
        _lib.TracerComplete.argtypes = [ctypes.c_char_p]
        _lib.TracerFail.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        _lib.TracerSetProgress.argtypes = [ctypes.c_char_p, ctypes.c_double]
        _lib.TracerSpawn.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        _lib.TracerSpawn.restype = ctypes.c_char_p
        _lib.GetTracer.argtypes = [ctypes.c_char_p]
        _lib.GetTracer.restype = ctypes.c_char_p
        _lib.GetTracersByFairy.argtypes = [ctypes.c_char_p]
        _lib.GetTracersByFairy.restype = ctypes.c_char_p
        _lib.GetTracersByCluster.argtypes = [ctypes.c_char_p]
        _lib.GetTracersByCluster.restype = ctypes.c_char_p
        _lib.GetLineage.argtypes = [ctypes.c_char_p]
        _lib.GetLineage.restype = ctypes.c_char_p
        _lib.RegisterIdentity.argtypes = [
            ctypes.c_char_p,  # functionName
            ctypes.c_char_p,  # realName
            ctypes.c_char_p,  # plane
            ctypes.c_char_p,  # channel
            ctypes.c_char_p,  # aliasesJSON
        ]
        _lib.ResolveIdentity.argtypes = [ctypes.c_char_p]
        _lib.ResolveIdentity.restype = ctypes.c_char_p
        _lib.GetPoolStats.argtypes = [ctypes.c_char_p]
        _lib.GetPoolStats.restype = ctypes.c_char_p
        _lib.GetRegistryStats.restype = ctypes.c_char_p
        _lib.FreeString.argtypes = [ctypes.c_char_p]

        # Initialize
        _lib.TracerPoolInit()

    except Exception as e:
        print(f"Warning: Failed to load Go tracer library: {e}")
        _lib = None
        _using_go = False


USING_GO = _using_go


# =============================================================================
# TRACER TYPES (matching Go)
# =============================================================================

class TracerType:
    FAIRY_WORK = "fairy_work"
    FAIRY_THOUGHT = "fairy_thought"
    FAIRY_REFLECTION = "fairy_reflection"
    FAIRY_DECISION = "fairy_decision"
    FAIRY_ACTION = "fairy_action"
    GOAL = "goal"
    THOUGHT_CHAIN = "thought_chain"
    CHAIN_LINK = "chain_link"
    FILE_SYSTEM = "file_system"
    FILE_USER = "file_user"
    MEDIA = "media"
    LITERATURE = "literature"
    CONVERSATION = "conversation"
    TELEMETRY = "telemetry"
    COLLISION = "collision"
    MEMORY_OPERATION = "memory_operation"
    WORKER_TASK = "worker_task"
    POSTAL_MESSAGE = "postal_message"


class TracerStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# =============================================================================
# IDENTITY
# =============================================================================

@dataclass
class Identity:
    """Flexible identity supporting function names and real names."""
    function_name: str
    real_name: str = ""
    plane: str = "P00"
    channel: str = ""
    aliases: List[str] = field(default_factory=list)
    version: str = ""

    @property
    def display_name(self) -> str:
        return self.real_name if self.real_name else self.function_name

    def matches(self, name: str) -> bool:
        return name in [self.function_name, self.real_name] + self.aliases


# =============================================================================
# UNIVERSAL TRACER
# =============================================================================

@dataclass
class UniversalTracer:
    """Universal tracer for tracking work."""
    id: str
    tracer_type: str
    fairy_id: str = ""
    fairy_name: str = ""
    identity: Optional[Identity] = None
    chain_id: str = ""
    goal_id: str = ""
    parent_tracer_id: str = ""
    children_ids: List[str] = field(default_factory=list)
    cluster_id: str = ""
    related_cluster_ids: List[str] = field(default_factory=list)
    status: str = TracerStatus.PENDING
    progress: float = 0.0
    intent: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    @classmethod
    def from_json(cls, data: dict) -> "UniversalTracer":
        """Create from JSON dict."""
        return cls(
            id=data.get("id", ""),
            tracer_type=data.get("tracer_type", ""),
            fairy_id=data.get("fairy_id", ""),
            fairy_name=data.get("fairy_name", ""),
            chain_id=data.get("chain_id", ""),
            goal_id=data.get("goal_id", ""),
            parent_tracer_id=data.get("parent_tracer_id", ""),
            children_ids=data.get("children_ids", []),
            cluster_id=data.get("cluster_id", ""),
            related_cluster_ids=data.get("related_cluster_ids", []),
            status=data.get("status", TracerStatus.PENDING),
            progress=data.get("progress", 0.0),
            intent=data.get("intent", ""),
            payload=data.get("payload", {}),
            error=data.get("error", ""),
            tags=data.get("tags", []),
        )


# =============================================================================
# TRACER POOL (Python fallback if Go not available)
# =============================================================================

class _PythonFallbackPool:
    """Pure Python implementation for when Go isn't available."""

    def __init__(self):
        self._tracers: Dict[str, UniversalTracer] = {}
        self._by_fairy: Dict[str, List[str]] = {}
        self._by_cluster: Dict[str, List[str]] = {}
        self._identities: Dict[str, Identity] = {}
        self._lock = threading.RLock()
        self._id_counter = 0

    def _gen_id(self) -> str:
        with self._lock:
            self._id_counter += 1
            return f"py_{self._id_counter:08x}"

    def create_tracer(
        self,
        tracer_type: str,
        fairy_name: str = "",
        cluster_id: str = "",
        intent: str = "",
        payload: Optional[Dict] = None,
    ) -> UniversalTracer:
        import time
        tracer = UniversalTracer(
            id=self._gen_id(),
            tracer_type=tracer_type,
            fairy_name=fairy_name,
            cluster_id=cluster_id,
            intent=intent,
            payload=payload or {},
            created_at=time.time(),
        )
        with self._lock:
            self._tracers[tracer.id] = tracer
            if fairy_name:
                self._by_fairy.setdefault(fairy_name, []).append(tracer.id)
            if cluster_id:
                self._by_cluster.setdefault(cluster_id, []).append(tracer.id)
        return tracer

    def start_tracer(self, tracer_id: str):
        import time
        with self._lock:
            t = self._tracers.get(tracer_id)
            if t:
                t.status = TracerStatus.RUNNING
                t.started_at = time.time()

    def complete_tracer(self, tracer_id: str):
        import time
        with self._lock:
            t = self._tracers.get(tracer_id)
            if t:
                t.status = TracerStatus.COMPLETED
                t.completed_at = time.time()
                t.progress = 1.0

    def fail_tracer(self, tracer_id: str, error: str):
        import time
        with self._lock:
            t = self._tracers.get(tracer_id)
            if t:
                t.status = TracerStatus.FAILED
                t.completed_at = time.time()
                t.error = error

    def set_progress(self, tracer_id: str, progress: float):
        with self._lock:
            t = self._tracers.get(tracer_id)
            if t:
                t.progress = max(0.0, min(1.0, progress))

    def get_tracer(self, tracer_id: str) -> Optional[UniversalTracer]:
        with self._lock:
            return self._tracers.get(tracer_id)

    def get_by_fairy(self, fairy_name: str) -> List[UniversalTracer]:
        with self._lock:
            ids = self._by_fairy.get(fairy_name, [])
            return [self._tracers[i] for i in ids if i in self._tracers]

    def get_by_cluster(self, cluster_id: str) -> List[UniversalTracer]:
        with self._lock:
            ids = self._by_cluster.get(cluster_id, [])
            return [self._tracers[i] for i in ids if i in self._tracers]

    def spawn_tracer(self, parent_id: str, tracer_type: str) -> Optional[UniversalTracer]:
        with self._lock:
            parent = self._tracers.get(parent_id)
            if not parent:
                return None
            child = self.create_tracer(
                tracer_type=tracer_type,
                fairy_name=parent.fairy_name,
                cluster_id=parent.cluster_id,
            )
            child.parent_tracer_id = parent.id
            parent.children_ids.append(child.id)
            return child

    def register_identity(self, identity: Identity):
        with self._lock:
            self._identities[identity.function_name] = identity
            if identity.real_name:
                self._identities[identity.real_name] = identity
            for alias in identity.aliases:
                self._identities[alias] = identity

    def resolve_identity(self, name: str) -> Optional[Identity]:
        with self._lock:
            return self._identities.get(name)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_tracers": len(self._tracers),
                "total_fairies": len(self._by_fairy),
                "total_clusters": len(self._by_cluster),
                "total_identities": len(self._identities),
                "using_go": False,
            }


# =============================================================================
# MAIN API
# =============================================================================

class TracerPool:
    """
    Main tracer pool interface.

    Uses Go implementation if available, falls back to Python.
    """

    _instance: Optional["TracerPool"] = None
    _lock = threading.Lock()

    def __init__(self):
        if USING_GO:
            self._fallback = None
        else:
            self._fallback = _PythonFallbackPool()

    @classmethod
    def global_instance(cls) -> "TracerPool":
        """Get the global tracer pool instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @property
    def using_go(self) -> bool:
        return USING_GO

    def create_tracer(
        self,
        tracer_type: str,
        fairy_name: str = "",
        cluster_id: str = "",
        intent: str = "",
        payload: Optional[Dict] = None,
    ) -> UniversalTracer:
        """Create a new universal tracer."""
        if USING_GO:
            payload_json = json.dumps(payload or {}).encode()
            result = _lib.CreateTracerFull(
                tracer_type.encode(),
                fairy_name.encode() if fairy_name else None,
                cluster_id.encode() if cluster_id else None,
                intent.encode() if intent else None,
                payload_json,
            )
            if result:
                tracer_id = result.decode()
                _lib.FreeString(result)
                return UniversalTracer(
                    id=tracer_id,
                    tracer_type=tracer_type,
                    fairy_name=fairy_name,
                    cluster_id=cluster_id,
                    intent=intent,
                    payload=payload or {},
                )
            raise RuntimeError("Failed to create tracer")
        else:
            return self._fallback.create_tracer(
                tracer_type, fairy_name, cluster_id, intent, payload
            )

    def start(self, tracer_id: str):
        """Mark tracer as started."""
        if USING_GO:
            _lib.TracerStart(tracer_id.encode())
        else:
            self._fallback.start_tracer(tracer_id)

    def complete(self, tracer_id: str):
        """Mark tracer as completed."""
        if USING_GO:
            _lib.TracerComplete(tracer_id.encode())
        else:
            self._fallback.complete_tracer(tracer_id)

    def fail(self, tracer_id: str, error: str = ""):
        """Mark tracer as failed."""
        if USING_GO:
            _lib.TracerFail(tracer_id.encode(), error.encode())
        else:
            self._fallback.fail_tracer(tracer_id, error)

    def set_progress(self, tracer_id: str, progress: float):
        """Update tracer progress (0.0 to 1.0)."""
        if USING_GO:
            _lib.TracerSetProgress(tracer_id.encode(), progress)
        else:
            self._fallback.set_progress(tracer_id, progress)

    def spawn(self, parent_id: str, tracer_type: str) -> Optional[UniversalTracer]:
        """Spawn a child tracer."""
        if USING_GO:
            result = _lib.TracerSpawn(parent_id.encode(), tracer_type.encode())
            if result:
                child_id = result.decode()
                _lib.FreeString(result)
                return UniversalTracer(id=child_id, tracer_type=tracer_type)
            return None
        else:
            return self._fallback.spawn_tracer(parent_id, tracer_type)

    def get(self, tracer_id: str) -> Optional[UniversalTracer]:
        """Get a tracer by ID."""
        if USING_GO:
            result = _lib.GetTracer(tracer_id.encode())
            if result:
                data = json.loads(result.decode())
                _lib.FreeString(result)
                return UniversalTracer.from_json(data)
            return None
        else:
            return self._fallback.get_tracer(tracer_id)

    def get_by_fairy(self, fairy_name: str) -> List[UniversalTracer]:
        """Get all tracers for a fairy (by any name)."""
        if USING_GO:
            result = _lib.GetTracersByFairy(fairy_name.encode())
            if result:
                data = json.loads(result.decode())
                _lib.FreeString(result)
                return [UniversalTracer.from_json(t) for t in data]
            return []
        else:
            return self._fallback.get_by_fairy(fairy_name)

    def get_by_cluster(self, cluster_id: str) -> List[UniversalTracer]:
        """Get all tracers for an SRM cluster (perfect recall)."""
        if USING_GO:
            result = _lib.GetTracersByCluster(cluster_id.encode())
            if result:
                data = json.loads(result.decode())
                _lib.FreeString(result)
                return [UniversalTracer.from_json(t) for t in data]
            return []
        else:
            return self._fallback.get_by_cluster(cluster_id)

    def get_lineage(self, tracer_id: str) -> List[UniversalTracer]:
        """Get full parent->child lineage for a tracer."""
        if USING_GO:
            result = _lib.GetLineage(tracer_id.encode())
            if result:
                data = json.loads(result.decode())
                _lib.FreeString(result)
                return [UniversalTracer.from_json(t) for t in data]
            return []
        else:
            # Simplified for fallback
            return []

    def register_identity(
        self,
        function_name: str,
        real_name: str = "",
        plane: str = "P00",
        channel: str = "",
        aliases: Optional[List[str]] = None,
    ):
        """Register a fairy identity for name resolution."""
        identity = Identity(
            function_name=function_name,
            real_name=real_name,
            plane=plane,
            channel=channel,
            aliases=aliases or [],
        )
        if USING_GO:
            aliases_json = json.dumps(aliases or []).encode()
            _lib.RegisterIdentity(
                function_name.encode(),
                real_name.encode() if real_name else None,
                plane.encode(),
                channel.encode() if channel else None,
                aliases_json,
            )
        else:
            self._fallback.register_identity(identity)

    def resolve_identity(self, name: str) -> Optional[Identity]:
        """Look up an identity by any name."""
        if USING_GO:
            result = _lib.ResolveIdentity(name.encode())
            if result:
                data = json.loads(result.decode())
                _lib.FreeString(result)
                return Identity(
                    function_name=data.get("function_name", ""),
                    real_name=data.get("real_name", ""),
                    plane=data.get("plane", ""),
                    channel=data.get("channel", ""),
                    aliases=data.get("aliases", []),
                )
            return None
        else:
            return self._fallback.resolve_identity(name)

    def stats(self) -> Dict[str, Any]:
        """Get pool and registry statistics."""
        if USING_GO:
            result = _lib.GetRegistryStats()
            if result:
                data = json.loads(result.decode())
                _lib.FreeString(result)
                data["using_go"] = True
                return data
            return {"using_go": True}
        else:
            return self._fallback.stats()

    def shutdown(self):
        """Shutdown the tracer pool."""
        if USING_GO:
            _lib.TracerPoolShutdown()


# Convenience exports
def create_tracer(tracer_type: str, **kwargs) -> UniversalTracer:
    """Create a tracer using the global pool."""
    return TracerPool.global_instance().create_tracer(tracer_type, **kwargs)


def get_by_fairy(fairy_name: str) -> List[UniversalTracer]:
    """Get tracers by fairy name."""
    return TracerPool.global_instance().get_by_fairy(fairy_name)


def get_by_cluster(cluster_id: str) -> List[UniversalTracer]:
    """Get tracers by SRM cluster (perfect recall)."""
    return TracerPool.global_instance().get_by_cluster(cluster_id)


__all__ = [
    "TracerPool",
    "UniversalTracer",
    "Identity",
    "TracerType",
    "TracerStatus",
    "create_tracer",
    "get_by_fairy",
    "get_by_cluster",
    "USING_GO",
]
