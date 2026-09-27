"""
Registration Handler - Handle fairy registration and unregistration.
"""

import time
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import FairyRegistry, FairyRecord
    from ..capability_index import CapabilityIndex
    from tracer_pool import TracerPool


class RegistrationHandler:
    """
    Handles fairy registration and unregistration.

    Listens to:
    - fairy.register - New fairy registration
    - fairy.unregister - Fairy shutdown

    Updates:
    - FairyRegistry with new/removed records
    - CapabilityIndex with capabilities
    """

    def __init__(
        self,
        registry: "FairyRegistry",
        capability_index: "CapabilityIndex",
        pool: Optional["TracerPool"] = None,
    ):
        self.registry = registry
        self.capability_index = capability_index
        self.pool = pool

    def on_register(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle fairy registration.

        Expected payload:
        {
            "name": str,           # Fairy name (required)
            "plane": str,          # P00, P10, etc. (required)
            "channel": str,        # Communication channel (optional)
            "capabilities": [...], # List of capabilities (optional)
            "metadata": {...},     # Additional metadata (optional)
        }
        """
        from ..registry import FairyRecord

        # Handle both TensorEnvelope and raw dict
        if hasattr(envelope, 'payload'):
            payload = envelope.payload
        elif isinstance(envelope, dict):
            payload = envelope.get("payload", envelope)
        else:
            payload = envelope

        name = payload.get("name") or payload.get("actor_name")
        plane = payload.get("plane")

        if not name or not plane:
            return {"ok": False, "error": "name and plane are required"}

        # Create record with full contract data (Phase 2 - Postal Backbone)
        record = FairyRecord(
            name=name,
            plane=plane,
            channel=payload.get("channel", ""),
            capabilities=set(payload.get("capabilities", [])),
            registered_at=time.time(),
            last_heartbeat=time.time(),
            status="running",
            metadata=payload.get("metadata", {}),
            # Routing fields from full contract
            subscriptions=set(payload.get("subscriptions", [])),
            intents=payload.get("intents", []),
            tracer_id=payload.get("tracer_id", ""),
            contract=payload,  # Store the full contract
            needs=payload.get("needs", {}),
            mail_id=payload.get("mail", {}).get("mail_id", "") if isinstance(payload.get("mail"), dict) else "",
        )

        # Register (also updates routing table)
        self.registry.register(record)

        # Update capability index
        if record.capabilities:
            self.capability_index.add(name, record.capabilities)

        # Create tracer if pool available
        if self.pool:
            try:
                self.pool.register_identity(
                    function_name=name,
                    plane=plane,
                    channel=record.channel,
                )
            except:
                pass  # Ignore tracer errors

        return {
            "ok": True,
            "name": name,
            "plane": plane,
            "capabilities": list(record.capabilities),
        }

    def on_unregister(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle fairy unregistration.

        Expected payload:
        {
            "name": str,  # Fairy name (required)
        }
        """
        # Handle both TensorEnvelope and raw dict
        if hasattr(envelope, 'payload'):
            payload = envelope.payload
        elif isinstance(envelope, dict):
            payload = envelope.get("payload", envelope)
        else:
            payload = envelope
        name = payload.get("name")

        if not name:
            return {"ok": False, "error": "name is required"}

        # Remove from capability index first
        self.capability_index.remove(name)

        # Unregister
        record = self.registry.unregister(name)

        if record:
            return {
                "ok": True,
                "name": name,
                "was_registered": True,
            }
        else:
            return {
                "ok": True,
                "name": name,
                "was_registered": False,
            }

    def on_update_capabilities(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a fairy's capabilities.

        Expected payload:
        {
            "name": str,
            "capabilities": [...],  # New capabilities
            "add": [...],           # Capabilities to add (alternative)
            "remove": [...],        # Capabilities to remove (alternative)
        }
        """
        # Handle both TensorEnvelope and raw dict
        if hasattr(envelope, 'payload'):
            payload = envelope.payload
        elif isinstance(envelope, dict):
            payload = envelope.get("payload", envelope)
        else:
            payload = envelope
        name = payload.get("name")

        if not name:
            return {"ok": False, "error": "name is required"}

        record = self.registry.get(name)
        if not record:
            return {"ok": False, "error": "fairy not registered"}

        # Full replacement
        if "capabilities" in payload:
            record.capabilities = set(payload["capabilities"])
        else:
            # Incremental update
            if "add" in payload:
                record.capabilities.update(payload["add"])
            if "remove" in payload:
                record.capabilities -= set(payload["remove"])

        # Update index
        self.capability_index.add(name, record.capabilities)

        return {
            "ok": True,
            "name": name,
            "capabilities": list(record.capabilities),
        }
