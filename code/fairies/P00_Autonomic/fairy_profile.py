"""
fairy_profile.py - Fairy Profile Management
============================================

Every fairy is a user in the postal system. This module provides:
- FairyState: Lifecycle states (sleeping, running, etc.)
- FairyProfile: Identity + tracking data for a fairy
- FairyProfileRegistry: Central registry of all fairy profiles
- get_fairy_registry(): Access the singleton registry

"For us that is this postal system handling the user profiles." - Ace
"""

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Set


# ════════════════════════════════════════════════════════════════════════════════
# FAIRY STATE - Lifecycle of a fairy
# ════════════════════════════════════════════════════════════════════════════════

class FairyState(Enum):
    """Lifecycle state of a fairy."""
    UNKNOWN = "unknown"      # Not yet registered
    SLEEPING = "sleeping"    # Registered but not booted
    BOOTING = "booting"      # Boot in progress
    RUNNING = "running"      # Fully operational
    DEGRADED = "degraded"    # Running but with issues
    STOPPING = "stopping"    # Shutdown in progress
    STOPPED = "stopped"      # Cleanly shut down
    FAILED = "failed"        # Crashed or error state


# ════════════════════════════════════════════════════════════════════════════════
# FAIRY PROFILE - Identity card for a fairy
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class FairyProfile:
    """
    Profile for a fairy in the postal system.

    Every fairy that registers gets a profile. This tracks:
    - Identity (name, plane, channel)
    - State (lifecycle status)
    - Activity (message counts, last active)
    - Connections (subscriptions, dependencies)
    """
    # Identity
    name: str
    fairy_id: str = ""
    plane: str = ""
    channel: str = ""

    # State
    state: FairyState = FairyState.UNKNOWN
    registered_at: float = field(default_factory=time.time)
    booted_at: Optional[float] = None

    # Activity tracking
    messages_sent: int = 0
    messages_received: int = 0
    last_active: float = field(default_factory=time.time)

    # Connections
    subscriptions: Set[str] = field(default_factory=set)
    dependencies: Set[str] = field(default_factory=set)

    # Custom metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        """Mark as recently active."""
        self.last_active = time.time()

    def record_send(self) -> None:
        """Record a sent message."""
        self.messages_sent += 1
        self.touch()

    def record_receive(self) -> None:
        """Record a received message."""
        self.messages_received += 1
        self.touch()

    def add_subscription(self, topic: str) -> None:
        """Add a subscription."""
        self.subscriptions.add(topic)

    def remove_subscription(self, topic: str) -> None:
        """Remove a subscription."""
        self.subscriptions.discard(topic)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "fairy_id": self.fairy_id,
            "plane": self.plane,
            "channel": self.channel,
            "state": self.state.value,
            "registered_at": self.registered_at,
            "booted_at": self.booted_at,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "last_active": self.last_active,
            "subscriptions": list(self.subscriptions),
            "dependencies": list(self.dependencies),
            "metadata": self.metadata,
        }


# ════════════════════════════════════════════════════════════════════════════════
# FAIRY PROFILE REGISTRY - Central registry of all fairy profiles
# ════════════════════════════════════════════════════════════════════════════════

class FairyProfileRegistry:
    """
    Central registry of all fairy profiles.

    Thread-safe singleton that tracks all fairies in the system.
    """

    _instance: Optional["FairyProfileRegistry"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "FairyProfileRegistry":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._profiles: Dict[str, FairyProfile] = {}
                cls._instance._profiles_lock = threading.Lock()
            return cls._instance

    def register(self, name: str, **kwargs) -> FairyProfile:
        """Register a new fairy profile."""
        with self._profiles_lock:
            if name in self._profiles:
                # Update existing
                profile = self._profiles[name]
                for key, value in kwargs.items():
                    if hasattr(profile, key):
                        setattr(profile, key, value)
                return profile
            else:
                # Create new
                profile = FairyProfile(name=name, **kwargs)
                self._profiles[name] = profile
                return profile

    def get(self, name: str) -> Optional[FairyProfile]:
        """Get a fairy profile by name."""
        with self._profiles_lock:
            return self._profiles.get(name)

    def get_or_create(self, name: str, **kwargs) -> FairyProfile:
        """Get existing or create new profile."""
        with self._profiles_lock:
            if name not in self._profiles:
                self._profiles[name] = FairyProfile(name=name, **kwargs)
            return self._profiles[name]

    def all(self) -> List[FairyProfile]:
        """Get all profiles."""
        with self._profiles_lock:
            return list(self._profiles.values())

    def by_state(self, state: FairyState) -> List[FairyProfile]:
        """Get all profiles in a given state."""
        with self._profiles_lock:
            return [p for p in self._profiles.values() if p.state == state]

    def by_plane(self, plane: str) -> List[FairyProfile]:
        """Get all profiles in a given plane."""
        with self._profiles_lock:
            return [p for p in self._profiles.values() if p.plane == plane]

    def update_state(self, name: str, state: FairyState) -> bool:
        """Update a fairy's state."""
        with self._profiles_lock:
            if name in self._profiles:
                self._profiles[name].state = state
                if state == FairyState.RUNNING:
                    self._profiles[name].booted_at = time.time()
                return True
            return False

    # ──────────────────────────────────────────────────────────────────────
    # IDENTITY QUERIES - For gatekeeper goal generation
    # ──────────────────────────────────────────────────────────────────────

    def by_guild(self, guild_id: str) -> List[FairyProfile]:
        """Get all fairies in a specific guild."""
        with self._profiles_lock:
            return [p for p in self._profiles.values()
                    if p.metadata.get("guild_id") == guild_id]

    def by_tier(self, tier: str) -> List[FairyProfile]:
        """Get all fairies of a specific tier (guild, interface, waking_mind)."""
        with self._profiles_lock:
            return [p for p in self._profiles.values()
                    if p.metadata.get("tier") == tier]

    def with_purpose(self) -> List[FairyProfile]:
        """Return all fairies with a real purpose (not placeholder)."""
        placeholders = {"Give it purpose.", "", None}
        with self._profiles_lock:
            return [p for p in self._profiles.values()
                    if p.metadata.get("purpose") not in placeholders]

    def guild_fairies_running(self) -> List[FairyProfile]:
        """Return all RUNNING guild fairies (excludes interfaces and waking minds)."""
        with self._profiles_lock:
            return [p for p in self._profiles.values()
                    if p.state == FairyState.RUNNING
                    and p.metadata.get("tier", "guild") == "guild"]

    def get_identity_summary(self, name: str) -> Dict[str, Any]:
        """Get a fairy's identity summary for goal generation."""
        with self._profiles_lock:
            profile = self._profiles.get(name)
            if not profile:
                return {}
            return {
                "name": profile.name,
                "plane": profile.plane,
                "state": profile.state.value,
                "purpose": profile.metadata.get("purpose", ""),
                "mantra": profile.metadata.get("mantra", ""),
                "guild_id": profile.metadata.get("guild_id", ""),
                "guild_role": profile.metadata.get("guild_role", ""),
                "tier": profile.metadata.get("tier", "guild"),
                "role": profile.metadata.get("role", "worker"),
                "intents": profile.metadata.get("intents", []),
                "capabilities": profile.metadata.get("capabilities", []),
                "knowledge_domains": profile.metadata.get("knowledge_domains", []),
            }

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """Convert all profiles to dictionary."""
        with self._profiles_lock:
            return {name: profile.to_dict() for name, profile in self._profiles.items()}

    def __len__(self) -> int:
        with self._profiles_lock:
            return len(self._profiles)

    def __contains__(self, name: str) -> bool:
        with self._profiles_lock:
            return name in self._profiles


# ════════════════════════════════════════════════════════════════════════════════
# MODULE-LEVEL ACCESS
# ════════════════════════════════════════════════════════════════════════════════

_registry: Optional[FairyProfileRegistry] = None

def get_fairy_registry() -> FairyProfileRegistry:
    """Get the global fairy profile registry."""
    global _registry
    if _registry is None:
        _registry = FairyProfileRegistry()
    return _registry


__all__ = [
    "FairyState",
    "FairyProfile",
    "FairyProfileRegistry",
    "get_fairy_registry",
]
