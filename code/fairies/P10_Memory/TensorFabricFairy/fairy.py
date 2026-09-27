"""
TensorFabricFairy - Multi-Dimensional Parallel Memory Access

Part of MemoryEngineGuild in Plane P10 (Memory)
Created: 2026-01-28

Memory organized as a tensor (multi-dimensional array) where:
  - Dimension 1: Plane (P00-P60) - functional domain
  - Dimension 2: Channel (0-76) - the 77 emotion channels
  - Dimension 3: Time (temporal slices)
  - Dimension 4: Type (affect, semantic, temporal from triple helix)

This allows:
  - Parallel reads across different planes (no blocking)
  - Channel isolation (no cross-talk)
  - Time-windowed access
  - Type-specific queries

Fairies can read/write to their slice without affecting others.
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Set

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState

# Import the existing tensor memory fabric
# Note: Use fairies.P10_Memory to avoid collision with root P10_Memory
try:
    from fairies.P10_Memory.tensor_memory_fabric import (
        TensorMemoryFabric,
        MemoryCell,
        get_global_tensor_fabric,  # Fixed: was get_tensor_fabric
    )
    HAS_FABRIC = True
except ImportError as e:
    print(f"[TensorFabricFairy] Fabric import failed: {e}")
    HAS_FABRIC = False


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class TensorFabricFairyShadow:
    """Shadow for TensorFabricFairy - monitors memory dimensions."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "TensorFabricFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks for the tensor fabric."""
        tests = []
        if hasattr(self.actor, '_fabric') and self.actor._fabric:
            tests.append(("fabric_has_cells", self.actor._cell_count > 0))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class TensorFabricFairy(Fairy):
    """
    Multi-dimensional parallel memory access.

    Guild: MemoryEngineGuild
    Coordinates with: MemoryEngineFairy, WorkingMemoryFairy, SRMMemoryFairy

    Provides 4D memory access:
    - Plane (P00-P60): Functional domain isolation
    - Channel (0-76): Emotion channel isolation
    - Time: Temporal windowed access
    - Type: affect/semantic/temporal from triple helix
    """

    ACTOR_NAME = "TensorFabricFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.tensor"

    PURPOSE = "Provide parallel multi-dimensional memory access"
    MANTRA = "Each fairy reads its own slice without blocking others"

    SHADOW_CLASS = TensorFabricFairyShadow

    # Lighter footprint
    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 15  # Every 15 beats
    NEEDS_COLLISION_CHAMBER = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._tensor_fabric = None
        self._cell_count = 0
        self._subscription_count = 0

    def on_boot(self) -> bool:
        """Initialize the tensor fabric."""
        super().on_boot()

        if HAS_FABRIC:
            try:
                self._tensor_fabric = get_global_tensor_fabric()
                self._cell_count = self._tensor_fabric.total_cells if hasattr(self._tensor_fabric, 'total_cells') else 0
                print(f"[{self.ACTOR_NAME}] Connected to tensor fabric ({self._cell_count} cells)")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to get fabric: {e}")
                self._tensor_fabric = None

        self._subscribe_intents()
        return True

    def _subscribe_intents(self):
        """Subscribe to postal channels for tensor fabric commands."""
        intents = [
            ("memory.tensor.write", self._handle_write),
            ("memory.tensor.read", self._handle_read),
            ("memory.tensor.query", self._handle_query),
            ("memory.tensor.slice", self._handle_slice),
            ("memory.tensor.status", self._handle_status),
            ("memory.tensor.decay", self._handle_decay),
        ]

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
                self._subscription_count += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        print(f"[{self.ACTOR_NAME}] Subscribed to {self._subscription_count} intents")

    def on_tick(self, beat: int):
        """Periodic maintenance - run decay on old memories."""
        if not self._tensor_fabric:
            return

        # Run decay every minute
        if beat % 60 == 0:
            try:
                if hasattr(self._tensor_fabric, 'decay_all'):
                    decayed = self._tensor_fabric.decay_all()
                    if decayed > 0:
                        print(f"[{self.ACTOR_NAME}] Decayed {decayed} weak memories")
            except Exception:
                pass

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # ═══════════════════════════════════════════════════════════════════════════
    # INTENT HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _extract_payload(self, message) -> Dict[str, Any]:
        """Extract payload from postal message."""
        if hasattr(message, 'payload'):
            return message.payload if isinstance(message.payload, dict) else {}
        return message if isinstance(message, dict) else {}

    def _handle_write(self, message):
        """
        Write a memory cell to the tensor.

        Payload:
            content: Any - The memory content
            plane: str - Plane coordinate (P00-P60)
            channel: int - Emotion channel (0-76)
            mem_type: str - Memory type (affect, semantic, temporal)
            author: str - Creating fairy name
            tags: List[str] - Optional tags
        """
        payload = self._extract_payload(message)
        content = payload.get("content")
        plane = payload.get("plane", "P10")
        channel = payload.get("channel", 0)
        mem_type = payload.get("mem_type", "semantic")
        author = payload.get("author") or payload.get("source", "unknown")

        if content is None:
            return {"ok": False, "error": "content required"}

        if not self._tensor_fabric:
            return {"ok": False, "error": "Tensor fabric not available"}

        try:
            cell_id = self._tensor_fabric.write(
                content=content,
                plane=plane,
                channel=channel,
                mem_type=mem_type,
                author=author,
                tags=set(payload.get("tags", [])),
            )
            self._cell_count += 1
            return {"ok": True, "cell_id": cell_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_read(self, message):
        """
        Read a memory cell by ID.

        Payload:
            cell_id: str - Memory cell ID
            reinforce: bool - Whether to strengthen on access (default True)
        """
        payload = self._extract_payload(message)
        cell_id = payload.get("cell_id")
        reinforce = payload.get("reinforce", True)

        if not cell_id:
            return {"ok": False, "error": "cell_id required"}

        if not self._tensor_fabric:
            return {"ok": False, "error": "Tensor fabric not available"}

        try:
            cell = self._tensor_fabric.read(cell_id, reinforce=reinforce)
            if cell:
                return {
                    "ok": True,
                    "cell": {
                        "id": cell.id,
                        "content": cell.content,
                        "plane": cell.plane,
                        "channel": cell.channel,
                        "mem_type": cell.mem_type,
                        "strength": cell.strength,
                        "author": cell.author,
                    }
                }
            return {"ok": False, "error": "Cell not found"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_query(self, message):
        """
        Query memory cells.

        Payload:
            plane: str - Filter by plane
            channel: int - Filter by channel
            mem_type: str - Filter by type
            tags: List[str] - Filter by tags
            time_window: float - Only cells from last N seconds
            limit: int - Max results
        """
        payload = self._extract_payload(message)

        if not self._tensor_fabric:
            return {"ok": False, "error": "Tensor fabric not available"}

        try:
            cells = self._tensor_fabric.query(
                plane=payload.get("plane"),
                channel=payload.get("channel"),
                mem_type=payload.get("mem_type"),
                tags=set(payload.get("tags", [])) if payload.get("tags") else None,
                time_window=payload.get("time_window"),
                limit=payload.get("limit", 50),
            )
            return {
                "ok": True,
                "cells": [{"id": c.id, "content": c.content, "strength": c.strength} for c in cells],
                "count": len(cells),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_slice(self, message):
        """
        Get a slice of the tensor (all cells matching coordinates).

        Payload:
            plane: str - Plane to slice
            channel: int - Channel to slice (optional)
        """
        payload = self._extract_payload(message)
        plane = payload.get("plane")

        if not plane:
            return {"ok": False, "error": "plane required"}

        if not self._tensor_fabric:
            return {"ok": False, "error": "Tensor fabric not available"}

        try:
            slice_data = self._tensor_fabric.get_slice(
                plane=plane,
                channel=payload.get("channel"),
            )
            return {"ok": True, "slice": slice_data}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_status(self, message):
        """Get tensor fabric status."""
        if not self._tensor_fabric:
            return {"ok": True, "fabric": False, "cell_count": 0}

        try:
            stats = self._tensor_fabric.get_stats() if hasattr(self._tensor_fabric, 'get_stats') else {}
            return {
                "ok": True,
                "fabric": True,
                "cell_count": self._cell_count,
                "stats": stats,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_decay(self, message):
        """Manually trigger memory decay."""
        if not self._tensor_fabric:
            return {"ok": False, "error": "Tensor fabric not available"}

        try:
            if hasattr(self._tensor_fabric, 'decay_all'):
                decayed = self._tensor_fabric.decay_all()
                return {"ok": True, "decayed": decayed}
            return {"ok": False, "error": "Decay not supported"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════════════════
    # SMOKE TEST
    # ═══════════════════════════════════════════════════════════════════════════

    def intent_smoke(self, payload: dict) -> dict:
        """Health check."""
        return {
            "ok": True,
            "fairy": self.ACTOR_NAME,
            "tracer_id": self.tracer_id,
            "has_fabric": self._tensor_fabric is not None,
            "cell_count": self._cell_count,
        }

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down (cells: {self._cell_count})...")
        return super().on_shutdown()
