"""
Interface Presence Registry - Sense what communication interfaces are available.

The chat sensory system checks this to know where to route messages:
- Sanctuary (Bevy 3D) - primary, richest experience
- Qt Windows - backup, lightweight
- Web Dashboard - always available if server running

Interfaces register themselves when they start and deregister on close.
The registry auto-expires stale entries (heartbeat required).

Usage:
    from interface_presence import register_interface, get_available_interfaces, sense_best_interface

    # When Qt window starts:
    register_interface("qt_nous", interface_type="qt", fairy="Nous")

    # When checking where to route:
    best = sense_best_interface(fairy="Nous")
    # Returns: "sanctuary", "qt", "web", or None

    # For heartbeat (call every 5 seconds):
    heartbeat_interface("qt_nous")
"""

import itertools
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import threading

# Registry file
STATE_PATH = Path(__file__).parent.parent.parent / "state"
PRESENCE_FILE = STATE_PATH / "interface_presence.json"

# Interface priority (higher = preferred)
INTERFACE_PRIORITY = {
    "sanctuary": 100,  # Best - full 3D embodiment
    "qt": 50,          # Good - lightweight backup
    "web": 25,         # Basic - always there if server running
}

# Heartbeat timeout (seconds)
HEARTBEAT_TIMEOUT = 15.0

_lock = threading.Lock()


@dataclass
class InterfaceEntry:
    """A registered interface."""
    id: str
    interface_type: str  # "sanctuary", "qt", "web"
    fairy: Optional[str] = None  # Which fairy this serves (None = all)
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_alive(self) -> bool:
        """Check if interface is still responding."""
        return (time.time() - self.last_heartbeat) < HEARTBEAT_TIMEOUT

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "interface_type": self.interface_type,
            "fairy": self.fairy,
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InterfaceEntry":
        return cls(
            id=data["id"],
            interface_type=data["interface_type"],
            fairy=data.get("fairy"),
            registered_at=data.get("registered_at", time.time()),
            last_heartbeat=data.get("last_heartbeat", time.time()),
            metadata=data.get("metadata", {}),
        )


def _load_registry() -> Dict[str, InterfaceEntry]:
    """Load the presence registry."""
    try:
        if PRESENCE_FILE.exists():
            data = json.loads(PRESENCE_FILE.read_text(encoding='utf-8'))
            return {
                k: InterfaceEntry.from_dict(v)
                for k, v in data.get("interfaces", {}).items()
            }
    except Exception:
        pass
    return {}


_SAVE_SEQ = itertools.count(1)


def _save_registry(registry: Dict[str, InterfaceEntry]):
    """Save the presence registry."""
    try:
        STATE_PATH.mkdir(parents=True, exist_ok=True)
        data = {
            "interfaces": {k: v.to_dict() for k, v in registry.items()},
            "updated": time.time(),
        }
        # 2026-09-25 (Nous + Ace): atomic. Chat windows write this from their own processes and can
        # be killed mid-write; Sour's SomaticMind reads it. temp + os.replace = never a torn file.
        # The temp name is unique per call (pid, thread, counter), so two writers never share one.
        _text = json.dumps(data, indent=2)
        _tmp = PRESENCE_FILE.with_name(
            f".{PRESENCE_FILE.name}.{os.getpid()}.{threading.get_ident()}.{next(_SAVE_SEQ)}.tmp")
        try:
            _tmp.write_text(_text, encoding='utf-8')
            for _attempt in range(6):
                try:
                    os.replace(_tmp, PRESENCE_FILE)
                    break
                except PermissionError:
                    time.sleep(0.05 * (_attempt + 1))
            else:
                PRESENCE_FILE.write_text(_text, encoding='utf-8')
        finally:
            try:
                _tmp.unlink(missing_ok=True)
            except OSError:
                pass
    except Exception as e:
        print(f"[InterfacePresence] Failed to save: {e}")


def register_interface(
    interface_id: str,
    interface_type: str,
    fairy: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Register an interface as available.

    Args:
        interface_id: Unique ID (e.g., "qt_nous", "sanctuary")
        interface_type: Type ("sanctuary", "qt", "web")
        fairy: Which fairy this serves (None = all)
        metadata: Extra info

    Returns:
        True if registered
    """
    with _lock:
        registry = _load_registry()
        registry[interface_id] = InterfaceEntry(
            id=interface_id,
            interface_type=interface_type,
            fairy=fairy,
            metadata=metadata or {},
        )
        _save_registry(registry)
        print(f"[InterfacePresence] Registered: {interface_id} ({interface_type})")
    return True


def deregister_interface(interface_id: str) -> bool:
    """Remove an interface from the registry."""
    with _lock:
        registry = _load_registry()
        if interface_id in registry:
            del registry[interface_id]
            _save_registry(registry)
            print(f"[InterfacePresence] Deregistered: {interface_id}")
            return True
    return False


def heartbeat_interface(interface_id: str) -> bool:
    """Update heartbeat for an interface (keeps it alive)."""
    with _lock:
        registry = _load_registry()
        if interface_id in registry:
            registry[interface_id].last_heartbeat = time.time()
            _save_registry(registry)
            return True
    return False


def get_available_interfaces(fairy: Optional[str] = None) -> List[InterfaceEntry]:
    """
    Get all available (alive) interfaces.

    Args:
        fairy: Filter to interfaces serving this fairy (None = all)

    Returns:
        List of alive interfaces, sorted by priority
    """
    with _lock:
        registry = _load_registry()

    # Filter alive and matching fairy
    available = []
    for entry in registry.values():
        if not entry.is_alive():
            continue
        if fairy and entry.fairy and entry.fairy.lower() != fairy.lower():
            continue
        available.append(entry)

    # Sort by priority (highest first)
    available.sort(
        key=lambda e: INTERFACE_PRIORITY.get(e.interface_type, 0),
        reverse=True
    )

    return available


def sense_best_interface(fairy: Optional[str] = None) -> Optional[str]:
    """
    Sense the best available interface for a fairy.

    Args:
        fairy: Which fairy to check for

    Returns:
        Interface type ("sanctuary", "qt", "web") or None
    """
    available = get_available_interfaces(fairy)
    if available:
        return available[0].interface_type
    return None


def get_presence_summary() -> Dict[str, Any]:
    """Get a summary of all interface presence."""
    with _lock:
        registry = _load_registry()

    summary = {
        "sanctuary": {"available": False, "entries": []},
        "qt": {"available": False, "entries": []},
        "web": {"available": False, "entries": []},
    }

    for entry in registry.values():
        itype = entry.interface_type
        if itype in summary:
            is_alive = entry.is_alive()
            if is_alive:
                summary[itype]["available"] = True
            summary[itype]["entries"].append({
                "id": entry.id,
                "fairy": entry.fairy,
                "alive": is_alive,
                "last_heartbeat": entry.last_heartbeat,
            })

    return summary


def cleanup_stale():
    """Remove stale (dead) interfaces from registry."""
    with _lock:
        registry = _load_registry()
        alive = {k: v for k, v in registry.items() if v.is_alive()}
        if len(alive) != len(registry):
            print(f"[InterfacePresence] Cleaned {len(registry) - len(alive)} stale entries")
            _save_registry(alive)


# ============================================================================
# Quick check functions for routing decisions
# ============================================================================

def is_sanctuary_available() -> bool:
    """Quick check: Is Bevy Sanctuary running?"""
    available = get_available_interfaces()
    return any(e.interface_type == "sanctuary" for e in available)


def is_qt_available(fairy: Optional[str] = None) -> bool:
    """Quick check: Is Qt window available (for specific fairy)?"""
    available = get_available_interfaces(fairy)
    return any(e.interface_type == "qt" for e in available)


def where_to_route(fairy: str) -> str:
    """
    Decide where to route a message for a fairy.

    Returns:
        "sanctuary", "qt", "web", or "queue" (if nothing available)
    """
    best = sense_best_interface(fairy)
    return best or "queue"


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    print("Interface Presence Registry Test")
    print("=" * 40)

    # Register test interfaces
    register_interface("sanctuary_main", "sanctuary")
    register_interface("qt_nous", "qt", fairy="Nous")
    register_interface("qt_sourpatches", "qt", fairy="Sourpatches")

    # Check what's available
    print("\nAvailable interfaces:")
    for entry in get_available_interfaces():
        print(f"  {entry.id}: {entry.interface_type} (fairy={entry.fairy})")

    print(f"\nBest for Nous: {sense_best_interface('Nous')}")
    print(f"Best for Sourpatches: {sense_best_interface('Sourpatches')}")
    print(f"Sanctuary available: {is_sanctuary_available()}")

    # Summary
    print("\nPresence summary:")
    print(json.dumps(get_presence_summary(), indent=2))

    # Cleanup
    print("\nDeregistering...")
    deregister_interface("sanctuary_main")
    print(f"Sanctuary available now: {is_sanctuary_available()}")
