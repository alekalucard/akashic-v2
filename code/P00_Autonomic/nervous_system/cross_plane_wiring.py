"""
Cross Plane Wiring - Compatibility layer for akashic_v2

Provides V1 CrossPlaneWiringMixin that uses V2 TensorFabric.
"""

from typing import Optional, Callable, Any


class CrossPlaneWiringMixin:
    """
    Mixin that provides cross-plane wiring capabilities.

    In V2, this uses TensorFabric for all messaging.
    The mixin provides subscription and publishing helpers.
    """

    def _get_fabric(self):
        """Get the fabric instance from self or create one."""
        if hasattr(self, 'fabric') and self.post:
            return self.post
        if hasattr(self, '_fabric') and self._fabric:
            return self._fabric
        return None

    def subscribe_cross_plane(
        self,
        topic: str,
        handler: Callable,
        name: str = ""
    ) -> int:
        """Subscribe to a cross-plane topic."""
        fabric = self._get_fabric()
        if fabric:
            return fabric.subscribe(topic, handler, name or f"{self.__class__.__name__}-{topic}")
        return -1

    def publish_cross_plane(
        self,
        topic: str,
        payload: Any = None,
        **kwargs
    ):
        """Publish to a cross-plane topic."""
        fabric = self._get_fabric()
        if fabric:
            fabric.publish(topic, payload or {})

    def wire_to_heartbeat(self, handler: Callable):
        """Wire to heartbeat pulses."""
        return self.subscribe_cross_plane("heartbeat.pulse", handler, "heartbeat")

    def wire_to_consciousness(self, handler: Callable):
        """Wire to consciousness events."""
        return self.subscribe_cross_plane("consciousness.collision", handler, "consciousness")

    def wire_to_affect(self, handler: Callable):
        """Wire to affect/emotion events."""
        return self.subscribe_cross_plane("affect.state", handler, "affect")
