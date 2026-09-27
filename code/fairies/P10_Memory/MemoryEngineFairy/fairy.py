"""
MemoryEngineFairy - Boot Consciousness From Memory Cards

Part of MemoryEngineGuild in Plane P10 (Memory)
Created: 2026-01-28

The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)

Philosophy:
  "The system doesn't HAVE memory. The system IS memory."
  "The memory engine doesn't just store things; it boots the system from that
   unified state. No separate boot sequence, no loading delays, no state
   reconstruction overhead."

The Memory Engine:
  1. Stores all cards (the entire system as memory)
  2. Resolves dependencies between cards
  3. Boots by loading and activating cards
  4. The system "wakes up" already knowing what it is
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

# Import the existing memory engine
# Note: Use fairies.P10_Memory to avoid collision with root P10_Memory
try:
    from fairies.P10_Memory.memory_engine import (
        MemoryEngine,
        MemoryIndex,
        get_engine as get_memory_engine,  # Alias for backward compat
        boot_from_memory,
    )
    HAS_ENGINE = True
except ImportError as e:
    print(f"[MemoryEngineFairy] Engine import failed: {e}")
    HAS_ENGINE = False

# Import card types
try:
    from fairies.P10_Memory.memory_cards import CardType, CardState
    HAS_CARDS = True
except ImportError:
    HAS_CARDS = False


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryEngineFairyShadow:
    """Shadow for MemoryEngineFairy - monitors card health and boot status."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "MemoryEngineFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks for the memory engine."""
        tests = []
        if hasattr(self.actor, '_engine') and self.actor._engine:
            tests.append(("engine_has_cards", self.actor._card_count > 0))
            tests.append(("engine_booted", self.actor._boot_complete))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryEngineFairy(Fairy):
    """
    Boot consciousness from memory cards.

    Guild: MemoryEngineGuild
    Coordinates with: WorkingMemoryFairy, SRMMemoryFairy, BackupFairy

    The system IS memory. This fairy manages:
    - Memory card storage and indexing
    - Dependency resolution between cards
    - Boot sequence from card state
    - Card activation and deactivation
    """

    ACTOR_NAME = "MemoryEngineFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.engine"

    PURPOSE = "Boot consciousness from unified memory state"
    MANTRA = "The system doesn't HAVE memory. The system IS memory."

    SHADOW_CLASS = MemoryEngineFairyShadow

    # Memory engine needs heartbeat for periodic maintenance
    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 10  # Every 10 beats (~10 seconds)
    NEEDS_COLLISION_CHAMBER = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._engine = None
        self._card_count = 0
        self._boot_complete = False
        self._subscription_count = 0

    def on_boot(self) -> bool:
        """Initialize the memory engine."""
        super().on_boot()

        # Get or create the memory engine
        if HAS_ENGINE:
            try:
                self._engine = get_memory_engine()
                self._card_count = len(self._engine.index.by_id) if hasattr(self._engine, 'index') else 0
                print(f"[{self.ACTOR_NAME}] Connected to memory engine ({self._card_count} cards)")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to get engine: {e}")
                self._engine = None

        # Subscribe to memory engine intents
        self._subscribe_intents()

        return True

    def _subscribe_intents(self):
        """Subscribe to postal channels for memory engine commands."""
        intents = [
            ("memory.engine.store", self._handle_store),
            ("memory.engine.load", self._handle_load),
            ("memory.engine.query", self._handle_query),
            ("memory.engine.boot", self._handle_boot),
            ("memory.engine.status", self._handle_status),
            ("memory.engine.activate", self._handle_activate),
            ("memory.engine.deactivate", self._handle_deactivate),
        ]

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
                self._subscription_count += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        print(f"[{self.ACTOR_NAME}] Subscribed to {self._subscription_count} intents")

    def on_tick(self, beat):
        """Periodic maintenance tick."""
        # Handle TensorEnvelope wrapper
        if hasattr(beat, 'payload'):
            beat = beat.payload.get('beat', 0) if isinstance(beat.payload, dict) else 0
        beat = int(beat) if beat else 0

        if not self._engine:
            return

        # Update card count periodically
        if beat % 30 == 0:  # Every 30 beats
            try:
                if hasattr(self._engine, 'index'):
                    self._card_count = len(self._engine.index.by_id)
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

    def _handle_store(self, message):
        """
        Store a memory card.

        Payload:
            card_type: str - Type of card (fairy, config, state, etc.)
            name: str - Card name
            data: dict - Card data
            dependencies: List[str] - Card IDs this depends on
            tags: List[str] - Tags for indexing
        """
        payload = self._extract_payload(message)
        name = payload.get("name")
        card_type = payload.get("card_type", "data")

        if not name:
            return {"ok": False, "error": "name required"}

        if not self._engine:
            return {"ok": False, "error": "Memory engine not available"}

        try:
            card_id = self._engine.store(
                name=name,
                card_type=card_type,
                data=payload.get("data", {}),
                dependencies=payload.get("dependencies", []),
                tags=payload.get("tags", []),
            )
            self._card_count = len(self._engine.index.by_id)
            return {"ok": True, "card_id": card_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_load(self, message):
        """
        Load a memory card by ID or name.

        Payload:
            card_id: str - Card ID
            name: str - Card name (alternative to card_id)
        """
        payload = self._extract_payload(message)
        card_id = payload.get("card_id")
        name = payload.get("name")

        if not self._engine:
            return {"ok": False, "error": "Memory engine not available"}

        try:
            if card_id:
                card = self._engine.load(card_id)
            elif name:
                card = self._engine.load_by_name(name)
            else:
                return {"ok": False, "error": "card_id or name required"}

            if card:
                return {"ok": True, "card": card.to_dict() if hasattr(card, 'to_dict') else str(card)}
            return {"ok": False, "error": "Card not found"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_query(self, message):
        """
        Query memory cards.

        Payload:
            card_type: str - Filter by type
            plane: str - Filter by plane
            tags: List[str] - Filter by tags
            limit: int - Max results
        """
        payload = self._extract_payload(message)

        if not self._engine:
            return {"ok": False, "error": "Memory engine not available"}

        try:
            cards = self._engine.query(
                card_type=payload.get("card_type"),
                plane=payload.get("plane"),
                tags=payload.get("tags"),
                limit=payload.get("limit", 100),
            )
            return {
                "ok": True,
                "cards": [c.to_dict() if hasattr(c, 'to_dict') else {"id": c.id, "name": c.name} for c in cards],
                "count": len(cards),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_boot(self, message):
        """
        Trigger boot sequence from memory cards.

        Payload:
            plane: str - Boot specific plane (optional)
            force: bool - Force re-boot even if already booted
        """
        payload = self._extract_payload(message)

        if not self._engine:
            return {"ok": False, "error": "Memory engine not available"}

        if self._boot_complete and not payload.get("force"):
            return {"ok": True, "message": "Already booted", "card_count": self._card_count}

        try:
            result = self._engine.boot(plane=payload.get("plane"))
            self._boot_complete = True
            self._card_count = len(self._engine.index.by_id)

            # Announce boot complete
            self.post.publish("memory.engine.boot_complete", {
                "source": self.ACTOR_NAME,
                "card_count": self._card_count,
                "result": result,
            })

            return {"ok": True, "booted": True, "card_count": self._card_count}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_status(self, message):
        """Get memory engine status."""
        if not self._engine:
            return {"ok": True, "engine": False, "card_count": 0}

        try:
            stats = self._engine.get_stats() if hasattr(self._engine, 'get_stats') else {}
            return {
                "ok": True,
                "engine": True,
                "card_count": self._card_count,
                "boot_complete": self._boot_complete,
                "stats": stats,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_activate(self, message):
        """Activate a memory card."""
        payload = self._extract_payload(message)
        card_id = payload.get("card_id")

        if not card_id:
            return {"ok": False, "error": "card_id required"}

        if not self._engine:
            return {"ok": False, "error": "Memory engine not available"}

        try:
            result = self._engine.activate(card_id)
            return {"ok": True, "activated": card_id, "result": result}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handle_deactivate(self, message):
        """Deactivate a memory card."""
        payload = self._extract_payload(message)
        card_id = payload.get("card_id")

        if not card_id:
            return {"ok": False, "error": "card_id required"}

        if not self._engine:
            return {"ok": False, "error": "Memory engine not available"}

        try:
            result = self._engine.deactivate(card_id)
            return {"ok": True, "deactivated": card_id, "result": result}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════════════════
    # SMOKE TEST
    # ═══════════════════════════════════════════════════════════════════════════

    def intent_smoke(self, payload: dict) -> dict:
        """Health check - am I alive?"""
        return {
            "ok": True,
            "fairy": self.ACTOR_NAME,
            "tracer_id": self.tracer_id,
            "has_engine": self._engine is not None,
            "card_count": self._card_count,
            "boot_complete": self._boot_complete,
        }

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down (cards: {self._card_count})...")
        return super().on_shutdown()
