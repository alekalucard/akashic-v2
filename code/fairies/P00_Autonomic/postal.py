# ════════════════════════════════════════════════════════════════════════════════
# UNIFIED POSTAL HUB INTERFACE
# ════════════════════════════════════════════════════════════════════════════════
#
# "For us that is this postal system handling the user profiles." - Ace
#
# This module provides a UNIFIED interface to the postal system that works
# from ANY process - whether you're in server.py or in MCP.
#
# The key insight: Postal IS the user management system. Every fairy is a user.
# Registration is waking up. Messages are activities. Everything is tracked.
#
# Usage:
#     from fairies.P00_Autonomic.postal import get_postal_hub
#     post = get_postal_hub()
#     
#     # Register (wake up)
#     profile = post.register_fairy(my_fairy)
#     
#     # Send messages (all tracked to profile)
#     post.route("consciousness.thought", {"content": "..."})
#     
#     # Check connectivity
#     report = post.check_all_connectivity()
#
# ════════════════════════════════════════════════════════════════════════════════

import os
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Callable, List, Optional, Set, Union

from .fairy_profile import FairyProfile, FairyProfileRegistry, get_fairy_registry, FairyState


# ════════════════════════════════════════════════════════════════════════════════
# CONNECTIVITY STATUS - Are fairies properly linked?
# ════════════════════════════════════════════════════════════════════════════════

class ConnectivityStatus(Enum):
    """Status of a fairy's connectivity to the system."""
    FULLY_LINKED = "fully_linked"          # All expected connections work
    PARTIALLY_LINKED = "partially_linked"  # Some connections missing
    ISOLATED = "isolated"                  # No connections working
    NEEDS_ANALYSIS = "needs_analysis"      # Marked for investigation


@dataclass
class ConnectivityReport:
    """Report on a fairy's connectivity status."""
    actor_name: str
    actor_id: str
    status: ConnectivityStatus
    subscriptions_active: int = 0
    subscriptions_expected: int = 0
    intents_registered: int = 0
    last_message_sent: Optional[float] = None
    last_message_received: Optional[float] = None
    issues: List[str] = field(default_factory=list)
    
    @property
    def is_healthy(self) -> bool:
        return self.status == ConnectivityStatus.FULLY_LINKED


# ════════════════════════════════════════════════════════════════════════════════
# UNIFIED POSTAL HUB
# ════════════════════════════════════════════════════════════════════════════════

class UnifiedPostalHub:
    """
    Unified postal interface that works from any process.
    
    Wraps either SharedPostalHub (in server.py) or PostalBridgeClient (in MCP)
    and adds user-profile semantics on top.
    """
    
    def __init__(self, backend):
        """
        Initialize with a backend (SharedPostalHub or PostalBridgeClient).
        
        Args:
            backend: The underlying postal implementation
        """
        self._backend = backend
        self._registry = get_fairy_registry()
        self._current_fairy_id: Optional[str] = None  # Who "we" are in this process
        self._needs_analysis: Set[str] = set()  # Fairies marked for analysis
        self._lock = threading.Lock()
    
    # ═══════════════════════════════════════════════════════════════════════
    # FAIRY REGISTRATION (User Login/Logout)
    # ═══════════════════════════════════════════════════════════════════════
    
    def register_fairy(self, fairy_or_contract: Union[FairyProfile, Dict, Any]) -> FairyProfile:
        """
        Register a fairy - they're waking up to live!
        
        This is the equivalent of "logging in" - the fairy becomes an active
        citizen of the system with a tracked profile.
        
        Args:
            fairy_or_contract: FairyProfile, dict, or fairy instance
            
        Returns:
            FairyProfile for the registered fairy
        """
        profile = self._registry.register(fairy_or_contract)
        
        # If backend supports it, also register there
        if hasattr(self._backend, 'register_fairy'):
            try:
                self._backend.register_fairy(profile.to_dict())
            except Exception as e:
                print(f"[UnifiedPostal] Backend registration note: {e}")
        
        # Route wake event
        self.route("fairy.wake", {
            "actor_name": profile.actor_name,
            "actor_id": profile.actor_id,
            "plane": profile.plane,
            "channel": profile.channel,
        })
        
        return profile
    
    def unregister_fairy(self, actor_id: str) -> Optional[FairyProfile]:
        """
        Unregister a fairy - they're going to sleep.
        
        Args:
            actor_id: The fairy's unique ID
            
        Returns:
            The fairy's final profile state
        """
        profile = self._registry.unregister(actor_id)
        
        if profile:
            # Route sleep event
            self.route("fairy.sleep", {
                "actor_name": profile.actor_name,
                "actor_id": profile.actor_id,
            })
            
            # If backend supports it, also unregister there
            if hasattr(self._backend, 'unregister_fairy'):
                try:
                    self._backend.unregister_fairy(actor_id)
                except Exception:
                    pass
        
        return profile
    
    def get_citizen(self, actor_name: str) -> Optional[FairyProfile]:
        """Get a fairy's profile by name."""
        return self._registry.get_by_name(actor_name)
    
    def list_citizens(self) -> List[str]:
        """List all awake fairy names."""
        return [p.actor_name for p in self._registry.list_awake()]
    
    # ═══════════════════════════════════════════════════════════════════════
    # MESSAGE ROUTING (User Activity)
    # ═══════════════════════════════════════════════════════════════════════
    
    def route(self, topic: str, payload: Dict[str, Any], sender_id: str = None) -> int:
        """
        Route a message through the postal system.
        
        All messages are tracked to the sender's profile.
        
        Args:
            topic: Topic to route to
            payload: Message payload
            sender_id: Optional sender fairy ID (for tracking)
            
        Returns:
            Number of recipients
        """
        # Track activity if we know the sender
        if sender_id:
            profile = self._registry.get(sender_id)
            if profile:
                profile.record_message_sent(topic)
        
        # Add provenance to payload
        if sender_id:
            payload = {**payload, "_sender_id": sender_id}
        
        # Route through backend
        if hasattr(self._backend, 'route'):
            return self._backend.route(topic, payload)
        return 0
    
    def subscribe(self, topic: str, callback: Callable, subscriber_id: str = None):
        """
        Subscribe to a topic.
        
        Args:
            topic: Topic to subscribe to
            callback: Handler function
            subscriber_id: Optional fairy ID to track subscription
        """
        # Track subscription in profile
        if subscriber_id:
            profile = self._registry.get(subscriber_id)
            if profile:
                profile.subscriptions.add(topic)
        
        # Wrap callback to track received messages
        def tracked_callback(data):
            if subscriber_id:
                profile = self._registry.get(subscriber_id)
                if profile:
                    sender = data.get("_sender_id") if isinstance(data, dict) else None
                    profile.record_message_received(topic, sender)
            return callback(data)
        
        # Subscribe through backend
        if hasattr(self._backend, 'subscribe'):
            self._backend.subscribe(topic, tracked_callback)
        elif hasattr(self._backend, 'receive'):
            self._backend.receive(topic, tracked_callback)
    
    def receive(self, topic: str, callback: Callable, subscriber_id: str = None):
        """Alias for subscribe."""
        return self.subscribe(topic, callback, subscriber_id)
    
    # ═══════════════════════════════════════════════════════════════════════
    # LANE SHORTCUTS (Convenience Methods)
    # ═══════════════════════════════════════════════════════════════════════
    
    def to_TELEMETRY(self, pkt: Dict) -> int:
        return self.route("telemetry", pkt)
    
    def to_PLAN(self, pkt: Dict) -> int:
        return self.route("plan", pkt)
    
    def to_COGNITION(self, pkt: Dict) -> int:
        return self.route("cognition", pkt)
    
    def to_SOMATIC(self, pkt: Dict) -> int:
        return self.route("somatic", pkt)
    
    def to_CHEMISTRY(self, pkt: Dict) -> int:
        return self.route("chemistry", pkt)
    
    def to_MEMORY(self, pkt: Dict) -> int:
        return self.route("memory", pkt)
    
    def to_TRACER(self, pkt: Dict) -> int:
        return self.route("tracer", pkt)
    
    def to_DIRECTORY(self, pkt: Dict) -> int:
        return self.route("directory", pkt)

    def to_CONSCIOUSNESS(self, pkt: Dict) -> int:
        return self.route("consciousness.stream", pkt)

    # ═══════════════════════════════════════════════════════════════════════
    # INTENT SYSTEM (User Actions)
    # ═══════════════════════════════════════════════════════════════════════
    
    def use_intent(self, target_actor: str, intent: str, payload: Dict = None,
                   caller_id: str = None) -> Optional[Any]:
        """
        Invoke an intent on another fairy.
        
        Args:
            target_actor: Name of fairy to call
            intent: Intent name to invoke
            payload: Parameters for the intent
            caller_id: Optional caller fairy ID (for tracking)
            
        Returns:
            Result from intent, or None
        """
        payload = payload or {}
        
        # Track the invocation
        if caller_id:
            caller_profile = self._registry.get(caller_id)
            if caller_profile:
                caller_profile.add_collaborator(target_actor)
                caller_profile.log_activity("INVOKE", f"{target_actor}.{intent}")
        
        # Try to find target profile and call intent directly
        target_profile = self._registry.get_by_name(target_actor)
        if target_profile and intent in target_profile.intents:
            target_profile.record_intent_invoked(intent, caller_id)
            try:
                return target_profile.intents[intent](payload)
            except Exception as e:
                print(f"[UnifiedPostal] Intent {target_actor}.{intent} error: {e}")
                return None
        
        # Fall back to backend if it supports intents
        if hasattr(self._backend, 'use_intent'):
            return self._backend.use_intent(target_actor, intent, payload)
        
        # Last resort: route as message
        self.route(f"intent.{target_actor}.{intent}", {
            "intent": intent,
            "payload": payload,
            "caller": caller_id,
        })
        return None
    
    # ═══════════════════════════════════════════════════════════════════════
    # CONNECTIVITY CHECKS (System Health)
    # ═══════════════════════════════════════════════════════════════════════
    
    def check_fairy_connectivity(self, actor_name: str) -> ConnectivityReport:
        """
        Check connectivity status for a specific fairy.
        
        Args:
            actor_name: Name of fairy to check
            
        Returns:
            ConnectivityReport with status and issues
        """
        profile = self._registry.get_by_name(actor_name)
        
        if not profile:
            return ConnectivityReport(
                actor_name=actor_name,
                actor_id="unknown",
                status=ConnectivityStatus.ISOLATED,
                issues=["Fairy not registered"],
            )
        
        issues = []
        
        # Check if marked for analysis
        if profile.actor_id in self._needs_analysis:
            return ConnectivityReport(
                actor_name=actor_name,
                actor_id=profile.actor_id,
                status=ConnectivityStatus.NEEDS_ANALYSIS,
                subscriptions_active=len(profile.subscriptions),
                intents_registered=len(profile.intents),
                issues=["Marked for analysis"],
            )
        
        # Check state
        if profile.state != FairyState.AWAKE:
            issues.append(f"Not awake (state: {profile.state.value})")
        
        # Check for subscriptions
        if len(profile.subscriptions) == 0:
            issues.append("No subscriptions registered")
        
        # Check activity
        if profile.messages_sent == 0 and profile.messages_received == 0:
            time_since_wake = time.time() - profile.wake_time
            if time_since_wake > 60:  # Idle for over a minute
                issues.append(f"No message activity in {time_since_wake:.0f}s")
        
        # Determine status
        if len(issues) == 0:
            status = ConnectivityStatus.FULLY_LINKED
        elif "Not awake" in str(issues):
            status = ConnectivityStatus.ISOLATED
        else:
            status = ConnectivityStatus.PARTIALLY_LINKED
        
        return ConnectivityReport(
            actor_name=actor_name,
            actor_id=profile.actor_id,
            status=status,
            subscriptions_active=len(profile.subscriptions),
            intents_registered=len(profile.intents),
            last_message_sent=profile.activity_log[-1]["ts"] if profile.activity_log else None,
            issues=issues,
        )
    
    def check_all_connectivity(self) -> Dict[str, ConnectivityReport]:
        """
        Check connectivity for all registered fairies.
        
        Returns:
            Dict mapping actor_name to ConnectivityReport
        """
        reports = {}
        for profile in self._registry.list_all():
            reports[profile.actor_name] = self.check_fairy_connectivity(profile.actor_name)
        return reports
    
    def get_isolated_fairies(self) -> List[str]:
        """Get list of isolated or needs-analysis fairy names."""
        isolated = []
        for profile in self._registry.list_all():
            report = self.check_fairy_connectivity(profile.actor_name)
            if report.status in (ConnectivityStatus.ISOLATED, ConnectivityStatus.NEEDS_ANALYSIS):
                isolated.append(profile.actor_name)
        return isolated
    
    def mark_for_analysis(self, actor_name: str, reason: str = ""):
        """
        Mark a fairy for connectivity analysis.
        
        Args:
            actor_name: Fairy to mark
            reason: Why they need analysis
        """
        profile = self._registry.get_by_name(actor_name)
        if profile:
            with self._lock:
                self._needs_analysis.add(profile.actor_id)
            profile.log_activity("MARKED_FOR_ANALYSIS", reason)
            print(f"[UnifiedPostal] {actor_name} marked for analysis: {reason}")
    
    def clear_analysis_mark(self, actor_name: str):
        """Clear the analysis mark for a fairy."""
        profile = self._registry.get_by_name(actor_name)
        if profile:
            with self._lock:
                self._needs_analysis.discard(profile.actor_id)
            profile.log_activity("ANALYSIS_CLEARED", "Connectivity verified")
    
    # ═══════════════════════════════════════════════════════════════════════
    # STATS AND DIAGNOSTICS
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_stats(self) -> Dict[str, Any]:
        """Get combined stats from registry and backend."""
        stats = {
            "registry": self._registry.get_stats(),
            "needs_analysis": list(self._needs_analysis),
        }
        
        if hasattr(self._backend, 'get_stats'):
            stats["backend"] = self._backend.get_stats()
        
        return stats
    
    def list_topics(self) -> List[str]:
        """List all known topics."""
        if hasattr(self._backend, 'list_topics'):
            return self._backend.list_topics()
        return []
    
    # ═══════════════════════════════════════════════════════════════════════
    # BACKEND PASSTHROUGH
    # ═══════════════════════════════════════════════════════════════════════
    
    def __getattr__(self, name):
        """Pass through unknown attributes to backend."""
        return getattr(self._backend, name)


# ════════════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ════════════════════════════════════════════════════════════════════════════════

_unified_hub: Optional[UnifiedPostalHub] = None
_hub_lock = threading.Lock()


def _running_in_server() -> bool:
    """Check if we're running in the server.py process."""
    # Check for server.py / ebookmain marker
    if os.environ.get("AKASHIC_SERVER") or os.environ.get("AKASHIC_EBOOKMAIN"):
        return True
    
    # Check if SharedPostalHub is already initialized
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import _shared_postal_hub
        return _shared_postal_hub is not None
    except ImportError:
        return False


def get_postal_hub() -> UnifiedPostalHub:
    """
    Get the unified postal hub - works from ANY process.
    
    In server.py: Returns UnifiedPostalHub wrapping SharedPostalHub
    In MCP/other: Returns UnifiedPostalHub wrapping PostalBridgeClient
    
    Returns:
        UnifiedPostalHub instance (singleton)
    """
    global _unified_hub
    
    if _unified_hub is None:
        with _hub_lock:
            if _unified_hub is None:
                if _running_in_server():
                    # We're in server.py - use direct postal hub
                    from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
                    backend = get_shared_postal_hub()
                    print("[Postal] Using SharedPostalHub (server.py)")
                else:
                    # We're in MCP or other process - use bridge
                    try:
                        from fairies.P00_Autonomic.postal_bridge.bridge_client import get_bridge_client
                        backend = get_bridge_client()
                        backend.connect(verify=False)  # Don't block on verification
                        print("[Postal] Using PostalBridgeClient (MCP/external)")
                    except Exception as e:
                        print(f"[Postal] Bridge failed, using stub: {e}")
                        backend = StubPostalHub()
                
                _unified_hub = UnifiedPostalHub(backend)
    
    return _unified_hub


class StubPostalHub:
    """Stub for when no backend is available."""
    
    def route(self, topic: str, payload: Dict) -> int:
        print(f"[StubPostal] Would route to {topic}: {payload}")
        return 0
    
    def subscribe(self, topic: str, callback: Callable):
        print(f"[StubPostal] Would subscribe to {topic}")
    
    def get_stats(self) -> Dict:
        return {"status": "stub", "connected": False}
    
    def list_topics(self) -> List[str]:
        return []


# ════════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ════════════════════════════════════════════════════════════════════════════════

__all__ = [
    'ConnectivityStatus',
    'ConnectivityReport',
    'UnifiedPostalHub',
    'get_postal_hub',
]
