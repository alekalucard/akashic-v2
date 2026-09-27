"""
Postal Shim - Backward compatibility for old Organ Template postal interface.

Provides self.post with convenience methods like:
- self.post.to_TELEMETRY(pkt)
- self.post.to_COGNITION(pkt)
- self.post.to_SOMATIC(pkt)
etc.

This maps to the V2 Fairy's self.publish() method.
"""

from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import FairyBase


class PostalShim:
    """
    Provides the old self.post interface for V2 fairies.

    Usage in fairy:
        self.post.to_TELEMETRY({"opcode": "STATUS", "payload": {...}})

    Maps to:
        self.publish("telemetry", {"opcode": "STATUS", "payload": {...}})
    """

    def __init__(self, fairy: "FairyBase"):
        self._fairy = fairy

    def publish(self, topic: str, payload: Dict[str, Any], priority: int = 1) -> bool:
        """Publish to a topic with automatic source attribution."""
        try:
            # Auto-inject source if not present (tracer attribution)
            fairy_name = getattr(self._fairy, 'ACTOR_NAME', 'Unknown')
            if "source" not in payload:
                payload = dict(payload)  # Don't mutate original
                payload["source"] = fairy_name

            # DEBUG: Trace memory-related publishes
            if "memory" in topic.lower():
                fabric_id = id(self._fairy.fabric) if hasattr(self._fairy, 'fabric') and self._fairy.fabric else 'None'
                print(f"[PostalShim DEBUG] {fairy_name} publishing to '{topic}' via fabric {fabric_id}")

            if hasattr(self._fairy, 'publish'):
                self._fairy.publish(topic, payload, priority)
            elif hasattr(self._fairy, 'fabric') and self._fairy.fabric:
                self._fairy.fabric.publish(topic, payload, priority=priority, source=fairy_name)
            else:
                # DEBUG: Log when we can't publish
                print(f"[PostalShim WARNING] Cannot publish to '{topic}' - no fairy.publish or fairy.fabric!")
                return False
            return True
        except Exception as e:
            # DEBUG: Log exceptions instead of swallowing them!
            print(f"[PostalShim ERROR] Failed to publish to '{topic}': {e}")
            return False

    def route(self, topic: str, payload: Dict[str, Any], priority: int = 1) -> bool:
        """Alias for publish."""
        return self.publish(topic, payload, priority)

    def subscribe(self, topic: str, handler, name: str = None) -> bool:
        """
        Subscribe to a topic with a handler callback.

        Delegates to the fairy's fabric.subscribe() method.

        Args:
            topic: Topic pattern to subscribe to
            handler: Callback function(message) to handle incoming messages
            name: Optional subscriber name (defaults to {ACTOR_NAME}-{topic})

        Returns:
            True if subscription succeeded, False otherwise
        """
        try:
            if hasattr(self._fairy, 'fabric') and self._fairy.fabric:
                # Generate subscriber name from fairy + topic if not provided
                if name is None:
                    actor_name = getattr(self._fairy, 'ACTOR_NAME', 'Unknown')
                    name = f"{actor_name}-{topic}"
                self._fairy.fabric.subscribe(topic, handler, name)
                return True
            return False
        except Exception:
            return False

    def unsubscribe(self, topic: str) -> bool:
        """
        Unsubscribe from a topic.

        Args:
            topic: Topic to unsubscribe from

        Returns:
            True if unsubscription succeeded, False otherwise
        """
        try:
            if hasattr(self._fairy, 'fabric') and self._fairy.fabric:
                if hasattr(self._fairy.fabric, 'unsubscribe'):
                    self._fairy.fabric.unsubscribe(topic)
                    return True
            return False
        except Exception:
            return False

    # =========================================================================
    # CONVENIENCE METHODS - Match PostalTunnelClient/Organ Template interface
    # =========================================================================

    def to_TELEMETRY(self, pkt: Dict[str, Any]) -> bool:
        """Route to telemetry topic."""
        return self.publish("telemetry", pkt)

    def to_PLAN(self, pkt: Dict[str, Any]) -> bool:
        """Route to plan topic."""
        return self.publish("plan", pkt)

    def to_COGNITION(self, pkt: Dict[str, Any]) -> bool:
        """Route to cognition.input topic."""
        return self.publish("cognition.input", pkt)

    def to_SOMATIC(self, pkt: Dict[str, Any]) -> bool:
        """Route to somatic.motor topic."""
        return self.publish("somatic.motor", pkt)

    def to_MEMORY(self, pkt: Dict[str, Any]) -> bool:
        """Route to memory.stream topic."""
        return self.publish("memory.stream", pkt)

    def to_TRACER(self, pkt: Dict[str, Any]) -> bool:
        """Route to tracer topic."""
        return self.publish("tracer", pkt)

    def to_DIRECTORY(self, pkt: Dict[str, Any]) -> bool:
        """Route to directory topic."""
        return self.publish("directory", pkt)

    def to_CONSCIOUSNESS(self, pkt: Dict[str, Any]) -> bool:
        """Route to consciousness topic."""
        return self.publish("consciousness.stream", pkt)

    def to_AFFECT(self, pkt: Dict[str, Any]) -> bool:
        """Route to affect topic."""
        return self.publish("affect.stream", pkt)

    def to_INNER_VOICE(self, pkt: Dict[str, Any]) -> bool:
        """Route to inner voice topic."""
        return self.publish("inner_voice.stream", pkt)

    @property
    def is_connected(self) -> bool:
        """Check if connected to fabric."""
        return hasattr(self._fairy, 'fabric') and self._fairy.fabric is not None

    @property
    def fabric(self):
        """
        Expose the underlying fairy's fabric.

        This is needed for fairies that check `self.post.fabric` to verify
        connectivity (e.g., Sourpatches' _subscribe_consciousness_streams).
        """
        if hasattr(self._fairy, 'fabric'):
            return self._fairy.fabric
        return None


class PostalMixin:
    """
    Mixin that adds self.post to V2 fairies for backward compatibility.

    Include this in your fairy class hierarchy to get the old postal interface:

        class MyFairy(PostalMixin, Fairy):
            def on_boot(self):
                self.post.to_TELEMETRY({"opcode": "BOOT_OK"})
    """

    _post_shim: PostalShim = None

    @property
    def post(self) -> PostalShim:
        """Get the postal shim for backward-compatible posting."""
        if self._post_shim is None:
            self._post_shim = PostalShim(self)
        return self._post_shim

    @post.setter
    def post(self, value):
        """
        Allow setting post for backward compatibility.

        Some fairies do `self.post = None` in __init__ expecting it to be
        set later by fabric. We accept this but ignore None values since
        the property getter creates the shim on-demand anyway.
        """
        if value is not None:
            # If someone passes a real PostalShim or compatible object, store it
            self._post_shim = value
        # If None, we just ignore it - the getter will create a shim on demand
