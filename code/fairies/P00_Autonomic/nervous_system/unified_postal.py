
# ═══════════════════════════════════════════════════════════════════
# UNIFIED POSTAL - Simple send/receive for all fairies
# ═══════════════════════════════════════════════════════════════════

def _get_unified_postal():
    """Get the one true postal hub."""
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        return get_shared_postal_hub()
    except:
        return None

class UnifiedPostalMixin:
    """
    Drop-in replacement for complex _ShimPost.
    Provides simple send() and receive() that go through SharedPostalHub.
    """
    
    def __init__(self):
        self._postal = _get_unified_postal()
        self._subscriptions = {}
    
    def send(self, topic: str, payload: dict = None):
        """Send a message to a topic. That's it."""
        if self._postal:
            self._postal.route(topic, payload or {})
    
    def receive(self, topic: str, handler):
        """Subscribe to a topic with a handler. That's it."""
        if self._postal:
            self._postal.subscribe(topic, handler)
            self._subscriptions[topic] = handler
    
    def unsubscribe(self, topic: str):
        """Stop receiving from a topic."""
        if self._postal and topic in self._subscriptions:
            self._postal.unsubscribe(topic, self._subscriptions[topic])
            del self._subscriptions[topic]
    
    def register_with_directory(self, contract: dict):
        """Register this fairy with DirectoryFairy."""
        self.send("directory", {
            "opcode": "CONTRACT_UPSERT",
            "contract": contract
        })
    
    # Aliases for compatibility
    def publish(self, topic: str, payload: dict = None):
        return self.send(topic, payload)
    
    def subscribe(self, topic: str, handler):
        return self.receive(topic, handler)
    
    def to_DIRECTORY(self, opcode: str, payload: dict = None):
        """Legacy compatibility - sends to directory topic."""
        self.send("directory", {
            "opcode": opcode,
            "contract": payload or {},
            "payload": payload or {}
        })
