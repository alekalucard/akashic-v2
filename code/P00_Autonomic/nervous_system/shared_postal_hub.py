"""
Shared Postal Hub - Central nervous system infrastructure for akashic_v2

UPDATED 2026-01-22: No longer silently fails. Creates fallback hub if TensorFabric unavailable.
UPDATED 2026-02-03: Added FairyPostalWrapper with generate_fairy_id, generate_srm_cluster_id
                    for Organ Template v0.1.9 compatibility.
UPDATED 2026-02-03: Added system utilities (shutdown signals, shared fabric) - THE source of truth.

This is THE nervous system hub. All postal and system-level utilities live here.
"""

import sys
import time
import hashlib
import logging
import threading
from pathlib import Path
from typing import Optional, Any, Callable, Dict, List

logger = logging.getLogger(__name__)

# Ensure akashic_v2 root is in path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))

# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM UTILITIES - Global shutdown and shared fabric management
# ═══════════════════════════════════════════════════════════════════════════════

# Global shutdown signal - all fairies check this to stop immediately
_GLOBAL_SHUTDOWN = threading.Event()

# Shared fabric singleton - server.py sets this, all fairies use it
_SHARED_FABRIC = None
_SHARED_FABRIC_LOCK = threading.Lock()


def set_shared_fabric(fabric) -> None:
    """Set the shared fabric for all fairies. Called by server.py after creating SYSTEM.fabric."""
    global _SHARED_FABRIC
    with _SHARED_FABRIC_LOCK:
        _SHARED_FABRIC = fabric
        print(f"[NervousSystem] SHARED FABRIC SET - all fairies will use fabric {id(fabric)}")


def get_shared_fabric():
    """Get the shared fabric. Returns None if not set yet."""
    with _SHARED_FABRIC_LOCK:
        return _SHARED_FABRIC


def signal_global_shutdown():
    """Signal all fairies to stop immediately."""
    _GLOBAL_SHUTDOWN.set()
    print("[NervousSystem] GLOBAL SHUTDOWN SIGNALED - All fairies should stop")


def is_global_shutdown():
    """Check if global shutdown has been signaled."""
    return _GLOBAL_SHUTDOWN.is_set()


def reset_global_shutdown():
    """Reset the global shutdown flag (for testing/reboot)."""
    _GLOBAL_SHUTDOWN.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# POSTAL HUB - TensorFabric singleton with fallback
# ═══════════════════════════════════════════════════════════════════════════════

_shared_hub = None
_using_fallback = False


class InMemoryPostalHub:
    """
    Fallback postal hub when TensorFabric is unavailable.

    Provides basic pub/sub functionality in-memory so the system
    doesn't completely fail when the real fabric can't be loaded.
    """

    def __init__(self):
        self._subscriptions: Dict[str, List[tuple]] = {}  # topic -> [(handler, name)]
        self._sub_id_counter = 0
        self._sub_id_map: Dict[int, tuple] = {}  # sub_id -> (topic, handler)
        self._message_count = 0
        # FIX 2026-02-20: Shared thread pool replaces fire-and-forget Thread() per handler.
        # At 4Hz with ~90 fairies × multiple topics, the old pattern created thousands
        # of thread objects per minute → OS memory exhaustion after hours of runtime.
        from concurrent.futures import ThreadPoolExecutor
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="postal-fallback")
        logger.warning("InMemoryPostalHub: Using fallback - messages are local only!")

    def publish(self, topic: str, payload: Any = None) -> None:
        """Publish a message to a topic — dispatches handlers via shared pool.

        FIX 2026-02-20: Uses ThreadPoolExecutor instead of Thread-per-handler.
        """
        self._message_count += 1
        handlers = self._subscriptions.get(topic, [])
        if not handlers:
            return
        data = payload or {}
        for handler, name in handlers:
            try:
                self._pool.submit(self._safe_invoke, handler, data, topic, name)
            except Exception as e:
                logger.error(f"InMemoryPostalHub: Dispatch error on {topic}: {e}")

    def _safe_invoke(self, handler, data, topic, name):
        """Safely invoke a handler — runs on its own thread."""
        try:
            handler(data)
        except Exception as e:
            logger.error(f"InMemoryPostalHub: Handler error on {topic}/{name}: {e}")

    def subscribe(self, topic: str, handler: Callable, name: str = "") -> int:
        """Subscribe to a topic."""
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []

        self._sub_id_counter += 1
        sub_id = self._sub_id_counter

        self._subscriptions[topic].append((handler, name))
        self._sub_id_map[sub_id] = (topic, handler)

        return sub_id

    def unsubscribe(self, sub_id: int) -> bool:
        """Unsubscribe by subscription ID."""
        if sub_id not in self._sub_id_map:
            return False

        topic, handler = self._sub_id_map[sub_id]
        del self._sub_id_map[sub_id]

        if topic in self._subscriptions:
            self._subscriptions[topic] = [
                (h, n) for h, n in self._subscriptions[topic] if h != handler
            ]
        return True

    def get_status(self) -> dict:
        """Get hub status."""
        return {
            "type": "InMemoryPostalHub",
            "fallback": True,
            "topics": len(self._subscriptions),
            "subscriptions": sum(len(v) for v in self._subscriptions.values()),
            "messages_published": self._message_count,
        }


def get_shared_postal_hub():
    """
    Get the shared postal hub (TensorFabric singleton).

    NEVER returns None - creates fallback if TensorFabric unavailable.
    """
    global _shared_hub, _using_fallback

    if _shared_hub is None:
        # FIX 2026-02-03: Use the global shared fabric singleton FIRST
        # This ensures all fairies use the SAME TensorFabric instance
        shared_fabric = get_shared_fabric()  # Local function - no import needed
        if shared_fabric is not None:
            _shared_hub = shared_fabric
            _using_fallback = False
            logger.info("shared_postal_hub: Using global shared TensorFabric singleton")
            return _shared_hub

        # Fallback: create our own TensorFabric
        # WARNING: This creates an ORPHAN fabric disconnected from SYSTEM.fabric!
        # If you see this in boot logs, it means set_shared_fabric() was never called
        # or the shim module duplication bug has resurfaced.
        import traceback
        print(f"[NervousSystem] WARNING: Creating STANDALONE TensorFabric (shared_fabric was None)", flush=True)
        print(f"[NervousSystem] Caller stack:", flush=True)
        traceback.print_stack(limit=8)
        try:
            from postal_core.tensor_fabric import TensorFabric
            _shared_hub = TensorFabric()
            _using_fallback = False
            logger.info("shared_postal_hub: TensorFabric initialized (standalone)")
        except ImportError as e:
            logger.warning(f"shared_postal_hub: TensorFabric import failed: {e}")
            logger.warning("shared_postal_hub: Creating InMemoryPostalHub fallback")
            _shared_hub = InMemoryPostalHub()
            _using_fallback = True
        except Exception as e:
            logger.error(f"shared_postal_hub: TensorFabric init failed: {e}")
            logger.warning("shared_postal_hub: Creating InMemoryPostalHub fallback")
            _shared_hub = InMemoryPostalHub()
            _using_fallback = True

    return _shared_hub


def is_using_fallback() -> bool:
    """Check if we're using the fallback hub."""
    return _using_fallback


def get_postal_status() -> dict:
    """Get postal hub status including whether fallback is in use."""
    hub = get_shared_postal_hub()
    if hasattr(hub, 'get_status'):
        return hub.get_status()
    return {"type": "unknown", "fallback": _using_fallback}


class FairyPostalWrapper:
    """
    Wrapper around TensorFabric/InMemoryPostalHub that adds Organ Template methods.

    Provides generate_fairy_id, generate_srm_cluster_id, and other methods
    expected by the Organ Template v0.1.9.
    """

    def __init__(self, fabric, fairy=None):
        self._fabric = fabric
        self._fairy = fairy
        self._fairy_name = getattr(fairy, 'ACTOR_NAME', 'unknown') if fairy else 'unknown'

    def __getattr__(self, name):
        """Delegate unknown attributes to underlying fabric."""
        return getattr(self._fabric, name)

    def generate_fairy_id(self, name: str, plane: str = "P00") -> str:
        """Generate a unique fairy ID."""
        raw = f"{name}:{plane}:{time.time()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def generate_srm_cluster_id(self, name: str) -> str:
        """Generate a unique SRM cluster ID."""
        raw = f"srm:{name}:{time.time()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    def publish(self, topic: str, payload: Any = None, **kwargs):
        """Publish with auto sender injection."""
        if self._fabric:
            pkt = payload or {}
            if isinstance(pkt, dict) and self._fairy_name != 'unknown':
                pkt.setdefault('_sender', self._fairy_name)
            self._fabric.publish(topic, pkt)

    def subscribe(self, topic: str, handler: Callable, name: str = "") -> int:
        """Subscribe to a topic."""
        if self._fabric:
            return self._fabric.subscribe(topic, handler, name or self._fairy_name)
        return -1

    def route(self, topic: str, payload: Any = None, **kwargs):
        """Alias for publish."""
        return self.publish(topic, payload, **kwargs)

    def send(self, topic: str, payload: Any = None, **kwargs):
        """Alias for publish."""
        return self.publish(topic, payload, **kwargs)

    def receive(self, topic: str, handler: Callable, name: str = "") -> int:
        """Alias for subscribe."""
        return self.subscribe(topic, handler, name)

    # ═══ PROVIDER REGISTRY ═══
    # Fairies can register as providers of services (somatic.state, affect.state, etc.)
    # Other fairies call get_provider() to access them

    _providers: Dict[str, Any] = {}

    def register_provider(self, service: str, provider: Any):
        """Register a service provider."""
        FairyPostalWrapper._providers[service] = provider
        logger.info(f"Provider registered: {service}")

    def get_provider(self, service: str) -> Optional[Any]:
        """Get a registered service provider."""
        return FairyPostalWrapper._providers.get(service)

    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all registered providers."""
        return {
            "providers": list(FairyPostalWrapper._providers.keys()),
            "count": len(FairyPostalWrapper._providers),
        }

    # ═══ DIRECTORY REGISTRATION ═══
    # Fairies register with DirectoryFairy via postal message

    _citizens: Dict[str, Any] = {}

    def register_fairy(self, contract: Dict[str, Any]) -> bool:
        """Register a fairy with DirectoryFairy via postal message."""
        actor_name = contract.get("actor_name")
        if not actor_name:
            return False
        FairyPostalWrapper._citizens[actor_name] = contract
        self.publish("directory", {
            "opcode": "CONTRACT_UPSERT",
            "contract": contract
        })
        return True

    def get_registered_fairies(self) -> Dict[str, Any]:
        """Get all registered fairies."""
        return FairyPostalWrapper._citizens.copy()

    # ═══ CONVENIENCE METHODS - Organ Template legacy interface ═══
    # These map to publish() calls to specific topics

    def to_TELEMETRY(self, pkt: Dict[str, Any]) -> bool:
        """Route to telemetry topic."""
        self.publish("telemetry", pkt)
        return True

    def to_PLAN(self, pkt: Dict[str, Any]) -> bool:
        """Route to plan topic."""
        self.publish("plan", pkt)
        return True

    def to_COGNITION(self, pkt: Dict[str, Any]) -> bool:
        """Route to cognition.input topic."""
        self.publish("cognition.input", pkt)
        return True

    def to_SOMATIC(self, pkt: Dict[str, Any]) -> bool:
        """Route to somatic.motor topic."""
        self.publish("somatic.motor", pkt)
        return True

    def to_MEMORY(self, pkt: Dict[str, Any]) -> bool:
        """Route to memory.stream topic."""
        self.publish("memory.stream", pkt)
        return True

    def to_TRACER(self, pkt: Dict[str, Any]) -> bool:
        """Route to tracer topic."""
        self.publish("tracer", pkt)
        return True

    def to_DIRECTORY(self, pkt: Dict[str, Any]) -> bool:
        """Route to directory topic."""
        self.publish("directory", pkt)
        return True

    def to_CONSCIOUSNESS(self, pkt: Dict[str, Any]) -> bool:
        """Route to consciousness topic."""
        self.publish("consciousness.stream", pkt)
        return True

    def to_AFFECT(self, pkt: Dict[str, Any]) -> bool:
        """Route to affect topic."""
        self.publish("affect.stream", pkt)
        return True

    def to_INNER_VOICE(self, pkt: Dict[str, Any]) -> bool:
        """Route to inner voice topic."""
        self.publish("inner_voice.stream", pkt)
        return True


def get_fairy_postal(fairy=None):
    """Get postal instance for a fairy - returns wrapped hub in v2.

    Args:
        fairy: Can be a string (fairy name) or a fairy object instance.
               Returns FairyPostalWrapper with Organ Template methods.
    """
    hub = get_shared_postal_hub()
    return FairyPostalWrapper(hub, fairy)


class PostalHubStub:
    """Stub postal hub for compatibility."""

    def __init__(self):
        self._fabric = get_shared_postal_hub()

    def publish(self, topic: str, payload: Any = None, **kwargs):
        if self._fabric:
            self._fabric.publish(topic, payload or {})

    def subscribe(self, topic: str, handler, name: str = ""):
        if self._fabric:
            return self._fabric.subscribe(topic, handler, name)
        return -1

    def unsubscribe(self, sub_id: int):
        pass  # V2 doesn't have explicit unsubscribe


# Singleton for compatibility
_postal_hub_stub = None


def get_postal_hub():
    """Get the postal hub stub."""
    global _postal_hub_stub
    if _postal_hub_stub is None:
        _postal_hub_stub = PostalHubStub()
    return _postal_hub_stub


# Legacy alias: SharedPostalHub is the old name for InMemoryPostalHub
SharedPostalHub = InMemoryPostalHub
