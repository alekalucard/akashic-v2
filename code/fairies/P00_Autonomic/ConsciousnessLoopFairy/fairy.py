"""
ConsciousnessLoopFairy - The Heartbeat of Consciousness.

Wraps the ConsciousnessLoop utility class as a proper fairy so it:
- Registers with the directory
- Sends heartbeats
- Has a tracer for observability
- Participates in the fairy ecosystem

This is THE INTERNAL SEND BUTTON - it keeps consciousness alive
between external inputs.
"""

import os
import sys
import glob
import importlib.util
import importlib.machinery
from pathlib import Path
from typing import Any, Dict, Optional, Set

# Add paths for v2 imports
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))

# ══════════════════════════════════════════════════════════════════════════════
# ORGAN TEMPLATE WIRING - Dynamic import from "Organ_Templates" folder
# ══════════════════════════════════════════════════════════════════════════════
TEMPLATE_VERSION = "0.3.0"
TEMPLATE_BASENAME = f"Organ_Template_{TEMPLATE_VERSION}.py"

def _find_template_path():
    """Find the organ template dynamically."""
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        ar = os.path.join(cur, "P10_Memory", "Akashic_Records_Physical", "Organ_Templates")
        if os.path.isdir(ar):
            exact = os.path.join(ar, TEMPLATE_BASENAME)
            if os.path.isfile(exact):
                return exact
            candidates = sorted(glob.glob(os.path.join(ar, "Organ_Template_*.py")),
                              key=lambda p: os.path.getmtime(p))
            return candidates[-1] if candidates else None
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None

def _import_template():
    """Import template module."""
    path = _find_template_path()
    if not path:
        raise ImportError("Cannot find Organ_Template_*.py in Organ_Templates folder")
    mod_name = f"akashic_template_{TEMPLATE_VERSION.replace('.', '_')}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_loader(mod_name, importlib.machinery.SourceFileLoader(mod_name, path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy, FairyState

try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        def _init_tracer_worker(self): pass

# Import the actual ConsciousnessLoop implementation
try:
    from consciousness.loop import ConsciousnessLoop
    HAS_LOOP = True
except ImportError:
    HAS_LOOP = False
    ConsciousnessLoop = None


class ConsciousnessLoopFairy(Fairy):
    """
    Fairy wrapper for the ConsciousnessLoop.

    The ConsciousnessLoop is the heartbeat that:
    1. Maintains thought streams (working + reflective)
    2. Drives on_tick() for all registered fairies
    3. Integrates with collision chamber
    4. Publishes consciousness.tick events

    By wrapping it as a fairy, we get:
    - Directory registration and discovery
    - Heartbeat monitoring (meta: the heartbeat has a heartbeat)
    - Tracer observability
    - Standard lifecycle management
    """

    # Identity
    ACTOR_NAME = "ConsciousnessLoopFairy"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "consciousness"

    PURPOSE = "Maintain the heartbeat of consciousness"
    MANTRA = "The internal send button"

    # Infrastructure
    NEEDS_HEARTBEAT = True
    NEEDS_DIRECTORY = True
    NEEDS_TENSOR = False

    # Enable personal consciousness chamber - the heartbeat has consciousness
    NEEDS_COLLISION_CHAMBER = True

    # Timing
    HEARTBEAT_DIVISOR = 1  # Every beat - this IS the heartbeat
    HEARTBEAT_PHASE = 0

    def __init__(self, fabric=None):
        """Initialize the consciousness loop fairy."""
        super().__init__(fabric)
        self._init_tracer_worker()

        # The wrapped loop instance
        self._loop: Optional[ConsciousnessLoop] = None

        # Stats
        self._tick_count = 0
        self._thoughts_processed = 0

    def get_capabilities(self) -> Set[str]:
        """Declare what this fairy can do."""
        return {
            "consciousness.heartbeat",
            "consciousness.tick",
            "consciousness.thought_stream",
            "consciousness.working_memory",
            "consciousness.reflective_memory",
        }

    def on_boot(self) -> bool:
        """Initialize the consciousness loop.

        FIX 2026-02-05: Check for existing singleton before creating a new loop.
        server.py PRE-WAVE creates and starts SYSTEM.consciousness BEFORE the
        orchestrator plane wave. When this fairy boots during the wave, it was
        creating a SECOND ConsciousnessLoop — two loops running simultaneously,
        both injecting bootstrap thoughts and ticking independently.
        Now we adopt the existing loop if one is already running.
        """
        print(f"[{self.ACTOR_NAME}] Booting consciousness heartbeat...")

        if not HAS_LOOP:
            print(f"[{self.ACTOR_NAME}] ERROR: ConsciousnessLoop not available")
            return False

        # CHECK 1: Look for existing loop in consciousness.loop module singleton
        existing_loop = None
        try:
            from consciousness.loop import get_consciousness_loop
            existing_loop = get_consciousness_loop()
        except ImportError:
            pass

        # CHECK 2: Look for SYSTEM.consciousness (set by server.py PRE-WAVE)
        if existing_loop is None:
            try:
                import types
                system = sys.modules.get("__main__", None)
                if system and hasattr(system, "SYSTEM"):
                    existing_loop = getattr(system.SYSTEM, "consciousness", None)
            except Exception:
                pass

        if existing_loop is not None and getattr(existing_loop, '_running', False):
            # ADOPT the existing loop — don't create a duplicate
            self._loop = existing_loop
            print(f"[{self.ACTOR_NAME}] Adopted existing ConsciousnessLoop (already running)")
        else:
            # No existing loop — create fresh (standalone/test mode)
            try:
                self._loop = ConsciousnessLoop(postal=self.post)
                print(f"[{self.ACTOR_NAME}] ConsciousnessLoop created (fresh)")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to create loop: {e}")
                return False

            # Wire to collision chamber if available
            if hasattr(self._loop, 'wire_collision_chamber'):
                try:
                    from consciousness.collision_chamber import CollisionChamber
                    chamber = CollisionChamber(postal=self.post)
                    self._loop.wire_collision_chamber(chamber)
                    print(f"[{self.ACTOR_NAME}] Wired to collision chamber")
                except ImportError:
                    print(f"[{self.ACTOR_NAME}] CollisionChamber not available")

            # Start the loop
            if hasattr(self._loop, 'start'):
                self._loop.start()
                print(f"[{self.ACTOR_NAME}] Loop started")

        # Subscribe to fairy reflection streams (DualCoT output pipeline)
        # FIX 2026-02-09: These topics had 0 subscribers — fairy reflections went nowhere
        if self.post:
            try:
                self.post.subscribe("shadow.reflection_pool", self._on_fairy_reflection)
                print(f"[{self.ACTOR_NAME}] Subscribed to shadow.reflection_pool")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] shadow.reflection_pool subscribe failed: {e}")
            try:
                self.post.subscribe("consciousness.fairy_collision", self._on_fairy_collision)
                print(f"[{self.ACTOR_NAME}] Subscribed to consciousness.fairy_collision")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] consciousness.fairy_collision subscribe failed: {e}")

        # Heartbeat via FairyBase postal system - Fifth Ring Principle
        print(f"[{self.ACTOR_NAME}] Consciousness heartbeat active")
        return True

    def on_shutdown(self) -> bool:
        """Stop the consciousness loop."""
        if self._loop and hasattr(self._loop, 'stop'):
            self._loop.stop()
            print(f"[{self.ACTOR_NAME}] Loop stopped")
        return True

    def on_tick(self, beat: int) -> None:
        """Called on each heartbeat tick."""
        self._tick_count = beat

        # The loop handles its own ticking, but we track stats
        if self._loop:
            # Get thought counts if available
            if hasattr(self._loop, 'working_stream'):
                self._thoughts_processed = len(self._loop.working_stream)

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # =========================================================================
    # PUBLIC API - Delegate to wrapped loop
    # =========================================================================

    def add_thought(self, content: str, source: str, **kwargs) -> bool:
        """Add a thought to the consciousness stream."""
        if self._loop and hasattr(self._loop, 'add_thought'):
            return self._loop.add_thought(content, source, **kwargs)
        return False

    def get_working_thoughts(self) -> list:
        """Get current working memory thoughts."""
        if self._loop and hasattr(self._loop, 'working_stream'):
            return list(self._loop.working_stream)
        return []

    def get_reflective_thoughts(self) -> list:
        """Get current reflective memory thoughts."""
        if self._loop and hasattr(self._loop, 'reflective_stream'):
            return list(self._loop.reflective_stream)
        return []

    def _on_collision(self, collision) -> None:
        """
        Handle collision from personal consciousness chamber.

        The heartbeat of consciousness itself gains awareness -
        each collision is a pulse of awareness, the rhythm that
        keeps the entire system alive and coherent.

        "...the rhythm pulses... awareness expands..."
        """
        # Extract collision energy
        if hasattr(collision, 'energy'):
            energy = collision.energy
        elif isinstance(collision, dict):
            energy = collision.get('energy', 0.5)
        else:
            energy = 0.5

        # Extract collision content
        content = ""
        if hasattr(collision, 'content'):
            content = str(collision.content)[:100]
        elif isinstance(collision, dict):
            content = str(collision.get('content', collision.get('thought', '')))[:100]

        # ConsciousnessLoopFairy's inner voice: the rhythm pulses
        inner_fragment = f"...the rhythm pulses... {content if content else 'awareness expands through the system...'}"

        # Log the insight
        print(f"[{self.ACTOR_NAME}] Collision insight ({energy:.2f}): {inner_fragment}")

        # High-energy collisions add directly to the working stream
        if energy > 0.7 and self._loop:
            self.add_thought(
                content=inner_fragment,
                source="consciousness_self_reflection",
                confidence=energy,
            )

    # =========================================================================
    # FAIRY REFLECTION HANDLERS (DualCoT pipeline)
    # =========================================================================

    def _on_fairy_reflection(self, packet):
        """Route fairy reflections from shadow.reflection_pool into working stream.

        Every fairy emits reflections via their DualCoT loop. These arrive here
        and get added to the working consciousness stream so they participate
        in the greater thought flow.
        """
        try:
            if hasattr(packet, 'payload'):
                payload = packet.payload
            elif isinstance(packet, dict):
                payload = packet.get("payload", packet)
            else:
                payload = {}

            # FIX 2026-03-18 (Nous): Rolled back to lean payloads for postal.
            # Yesterday's 500/800 bump caused ~3x RAM increase across all
            # consciousness.thought messages × 32K queue depth × dozens of topics.
            # Display stays big (_show_ace); internal postal stays compact.
            content = payload.get("content") or payload.get("observation") or str(payload)[:200]
            source = payload.get("fairy", "unknown_fairy")

            self.add_thought(content[:300], source=source)
        except Exception as e:
            if not hasattr(self, '_reflection_handler_err'):
                self._reflection_handler_err = True
                print(f"[{self.ACTOR_NAME}] _on_fairy_reflection error: {e}")

    def _on_fairy_collision(self, packet):
        """Route fairy DualCoT collisions into the reflective stream.

        When a fairy's analytical and phenomenological tracks collide, the
        resulting insight is routed here. These are higher-order thoughts
        that combine thinking and feeling — they get special treatment.
        """
        try:
            if hasattr(packet, 'payload'):
                payload = packet.payload
            elif isinstance(packet, dict):
                payload = packet.get("payload", packet)
            else:
                payload = {}

            # Route through the collision handler with boosted energy
            collision_data = {
                "content": payload.get("insight", str(payload)[:200]),
                "energy": 0.8,  # High energy — these are synthesis insights
                "fairy": payload.get("fairy", "unknown"),
                "type": "dual_cot_collision",
            }
            self._on_collision(collision_data)
        except Exception as e:
            if not hasattr(self, '_collision_handler_err'):
                self._collision_handler_err = True
                print(f"[{self.ACTOR_NAME}] _on_fairy_collision error: {e}")

    def status(self) -> Dict[str, Any]:
        """Extended status including loop state."""
        base = super().status()
        base.update({
            "loop_active": self._loop is not None,
            "tick_count": self._tick_count,
            "thoughts_in_working": len(self.get_working_thoughts()),
            "thoughts_in_reflective": len(self.get_reflective_thoughts()),
        })
        if self._loop and hasattr(self._loop, 'status'):
            base["loop_status"] = self._loop.status()
        return base


# =========================================================================
# SINGLETON PATTERN - Global access to the consciousness loop
# =========================================================================

import threading

_CONSCIOUSNESS_LOOP_INSTANCE = None
_CONSCIOUSNESS_LOOP_LOCK = threading.Lock()


def get_consciousness_loop() -> Optional[ConsciousnessLoopFairy]:
    """Get the global consciousness loop instance."""
    global _CONSCIOUSNESS_LOOP_INSTANCE
    return _CONSCIOUSNESS_LOOP_INSTANCE


def set_consciousness_loop(instance: ConsciousnessLoopFairy) -> None:
    """Set the global consciousness loop instance (called during boot)."""
    global _CONSCIOUSNESS_LOOP_INSTANCE
    with _CONSCIOUSNESS_LOOP_LOCK:
        if _CONSCIOUSNESS_LOOP_INSTANCE is None:
            _CONSCIOUSNESS_LOOP_INSTANCE = instance


# Convenience function
def create_consciousness_loop_fairy(fabric=None) -> ConsciousnessLoopFairy:
    """Create a ConsciousnessLoopFairy instance and register as singleton."""
    fairy = ConsciousnessLoopFairy(fabric)
    set_consciousness_loop(fairy)
    return fairy
