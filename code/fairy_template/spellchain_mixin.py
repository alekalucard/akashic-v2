"""
SpellChainMixin - Bridge existing fairies to spell-chain-driven existence.

This mixin gives ANY fairy (Organ Template or consolidated) its own
self-sustaining heartbeat via spell chain. The fairy becomes self-supporting:
- Own heartbeat (sustain spell) synced to circadian rhythm
- Emits fairy.heartbeat via the shared echo queue (DirectoryFairy sees it alive)
- Emits shadow.health for health monitoring
- Draws energy from DimensionBattery (blood cell mode)
- Supports other fairies via spell chain interconnection

The Architecture:
    CirculationPumpFairy → somatic.pulse → DimensionBattery.tick() → _pump_chains()
        → SpellChain.get_next_spell() → sustain spell executes
            → emit heartbeat → echo queue → DirectoryFairy sees alive
            → emit shadow.health → postal → health monitoring

Without this mixin, fairies passively wait for heartbeat.pulse from
ConsciousnessLoop and echo it. WITH this mixin, fairies generate their
OWN heartbeat from their spell chain — they are self-sustaining.

Usage:
    class MyFairy(SpellChainMixin, Fairy):
        ...
        def on_boot(self):
            super().on_boot()
            # After standard boot, convert to spell-driven existence
            pool = get_spell_pool()
            if pool:
                self.boot_as_spells(pool)

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

from __future__ import annotations

import time
import threading
import queue
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.spellchain.chain import SpellChain
    from infrastructure.spellchain.pool import SpellPool
    from infrastructure.dimension_battery import DimensionBattery


class SpellChainMixin:
    """
    Mixin that gives any fairy spell-chain-driven self-sustaining existence.

    Drop this into the MRO of any fairy class to give it:
    - Its own SpellChain with sustain spells (heartbeat)
    - Energy management via DimensionBattery
    - Postal heartbeat emission (fairy.heartbeat + shadow.health)
    - Circadian rhythm sync

    The fairy remains compatible with its existing lifecycle (on_boot, on_tick, etc.)
    but gains autonomous heartbeat generation.

    Key Properties:
        spell_chain: The fairy's SpellChain (None until boot_as_spells called)
        spell_alive: Whether the spell chain is sustaining
        spell_energy: Current energy level

    Key Methods:
        boot_as_spells(pool, battery=None): Convert to spell-driven existence
        dissolve_spells(): Gracefully end spell-driven existence
        cast_fairy_spell(what, how, **kw): Cast a one-off spell
    """

    # Configuration — override in subclass to tune metabolism
    SPELL_HEARTBEAT_INTERVAL: float = 2.0
    """Seconds between heartbeat sustain spells. Syncs with circadian."""

    SPELL_ENERGY_INCOME: float = 0.1
    """Energy regeneration per second. Higher = more active fairy."""

    SPELL_AUTO_REVIVE: bool = True
    """Automatically revive on chain break? Most fairies should be True."""

    SPELL_INITIAL_ENERGY: float = 1.0
    """Starting energy for the chain."""

    # =========================================================================
    # STATE
    # =========================================================================

    _spell_chain: Optional["SpellChain"] = None
    _spell_pool: Optional["SpellPool"] = None
    _spell_battery: Optional["DimensionBattery"] = None
    _spell_boot_time: Optional[float] = None
    _spell_tick_count: int = 0
    _spell_booted: bool = False

    # =========================================================================
    # BOOT — Convert to spell-driven existence
    # =========================================================================

    def boot_as_spells(
        self,
        pool: "SpellPool",
        battery: Optional["DimensionBattery"] = None,
    ) -> Optional["SpellChain"]:
        """
        Convert this fairy to spell-driven existence.

        Creates a SpellChain, registers sustain spells (heartbeat),
        and optionally wires to a DimensionBattery for energy management.

        This should be called from on_boot() AFTER the fairy's standard
        initialization is complete.

        Args:
            pool: The global SpellPool (from get_spell_pool())
            battery: Optional DimensionBattery for energy management.
                     If None, chain runs in standalone energy mode.

        Returns:
            The SpellChain, or None if boot_as_spells failed.
        """
        if self._spell_booted:
            return self._spell_chain

        try:
            from infrastructure.spellchain.chain import SpellChain
            from infrastructure.spellchain.spell import Spell, SpellType
        except ImportError:
            # Infrastructure not available — degrade gracefully
            try:
                from spellchain.chain import SpellChain
                from spellchain.spell import Spell, SpellType
            except ImportError:
                self._log_spell("SpellChain infrastructure not available — skipping")
                return None

        actor_name = getattr(self, 'ACTOR_NAME', 'UnknownFairy')
        actor_plane = getattr(self, 'ACTOR_PLANE', 'P00')

        try:
            # Create the spell chain
            chain = SpellChain(
                fairy_id=f"{actor_name}_{id(self)}",
                fairy_name=actor_name,
                fairy_plane=actor_plane,
                pool=pool,
            )

            # Set energy parameters
            chain.set_income_rate(self.SPELL_ENERGY_INCOME)
            if hasattr(chain, '_energy'):
                chain._energy = min(self.SPELL_INITIAL_ENERGY, chain.MAX_ENERGY)

            # Create the sustain heartbeat spell
            fairy_self = self

            def heartbeat_logic(spell):
                """The fairy's self-sustaining heartbeat.

                This runs every SPELL_HEARTBEAT_INTERVAL seconds,
                emitting postal heartbeat + shadow health.
                This IS the fairy's life force — not an echo of someone else's.
                """
                fairy_self._spell_tick_count += 1
                fairy_self._emit_spell_heartbeat()
                fairy_self._emit_spell_shadow_health()

                # Call fairy's on_spell_heartbeat if defined
                if hasattr(fairy_self, 'on_spell_heartbeat'):
                    try:
                        fairy_self.on_spell_heartbeat(spell)
                    except Exception:
                        pass

                return {
                    "tick": fairy_self._spell_tick_count,
                    "energy": chain.energy if chain else 0,
                    "alive": True,
                }

            sustain = chain.create_sustain_spell(
                what=f"{actor_name} heartbeat",
                how=heartbeat_logic,
                interval=self.SPELL_HEARTBEAT_INTERVAL,
                energy_required=0.03,  # Low cost — heartbeat should be cheap
            )

            # Bootstrap the chain (queues the sustain spell)
            chain.bootstrap()

            # Register with battery if provided (blood cell mode)
            if battery is not None:
                try:
                    battery.register_chain(f"{actor_name}_{id(self)}", chain)
                    self._spell_battery = battery
                    self._log_spell(f"Registered with battery (blood cell mode)")
                except Exception as e:
                    self._log_spell(f"Battery registration failed: {e} — standalone mode")

            # Register with pool
            try:
                if hasattr(pool, '_chains'):
                    pool._chains[chain.fairy_id] = chain
            except Exception:
                pass

            self._spell_chain = chain
            self._spell_pool = pool
            self._spell_boot_time = time.time()
            self._spell_booted = True

            self._log_spell(
                f"Spell-driven existence active "
                f"(interval={self.SPELL_HEARTBEAT_INTERVAL}s, "
                f"energy={self.SPELL_INITIAL_ENERGY})"
            )

            return chain

        except Exception as e:
            self._log_spell(f"boot_as_spells FAILED: {e}")
            return None

    # =========================================================================
    # HEARTBEAT EMISSION — The bridge to postal system
    # =========================================================================

    def _emit_spell_heartbeat(self):
        """Emit fairy.heartbeat via the shared echo queue.

        This is the critical bridge: spell chain sustain spell executes,
        and the fairy's heartbeat gets published to DirectoryFairy via
        the same echo queue mechanism used by the organ template.

        This means spell-chain-driven fairies are visible to DirectoryFairy
        just like manually-echoing fairies — but the heartbeat originates
        from within, not from an external clock.
        """
        actor_name = getattr(self, 'ACTOR_NAME', 'UnknownFairy')
        actor_plane = getattr(self, 'ACTOR_PLANE', 'P00')
        post = getattr(self, 'post', None)

        if post is None:
            return

        echo_payload = {
            "name": actor_name,
            "plane": actor_plane,
            "beat": self._spell_tick_count,
            "ts": time.time(),
            "source": "spell_chain",  # Mark as self-generated
        }

        # Try to use the organ template's shared echo queue (best path)
        # This avoids creating N threads — all fairies share one echo worker.
        echo_queue = getattr(self.__class__, '_echo_queue', None)
        if echo_queue is None:
            # Walk MRO to find the echo queue from any parent class
            for cls in type(self).__mro__:
                eq = getattr(cls, '_echo_queue', None)
                if eq is not None:
                    echo_queue = eq
                    break

        if echo_queue is not None:
            try:
                echo_queue.put_nowait((post, echo_payload))
                return
            except Exception:
                pass  # Queue full or unavailable — fall through

        # Fallback: direct publish (may block briefly but keeps fairy alive)
        try:
            post.publish("fairy.heartbeat", echo_payload)
        except Exception:
            pass

    def _emit_spell_shadow_health(self):
        """Emit shadow.health status via postal system.

        This lets the health monitoring system see the fairy's
        spell-chain-based vitality, not just echo-based liveness.
        """
        actor_name = getattr(self, 'ACTOR_NAME', 'UnknownFairy')
        post = getattr(self, 'post', None)

        if post is None:
            return

        chain = self._spell_chain
        health_payload = {
            "actor": actor_name,
            "ts": time.time(),
            "spell_alive": chain.is_alive if chain else False,
            "spell_energy": chain.energy if chain else 0,
            "spell_ticks": self._spell_tick_count,
            "spell_state": chain.state.value if chain and hasattr(chain, 'state') else "unknown",
            "source": "spell_chain",
        }

        # Include monitoring trace IDs if available
        trace_ids = getattr(self, '_spell_trace_ids', None)
        if trace_ids:
            health_payload["trace_ids"] = trace_ids

        try:
            post.publish("shadow.health", health_payload)
        except Exception:
            pass

    # =========================================================================
    # SPELL CASTING — Cast additional spells during existence
    # =========================================================================

    def cast_fairy_spell(
        self,
        what: str,
        how,
        energy_required: float = 0.1,
        **kwargs,
    ):
        """Cast a one-off spell on this fairy's chain.

        Use this for discrete actions: process a message, run inference,
        handle an event. The spell executes once and completes.

        Args:
            what: Human-readable description
            how: Callable that receives the Spell object
            energy_required: Energy cost
            **kwargs: Additional Spell parameters

        Returns:
            The Spell, or None if chain not active
        """
        if not self._spell_chain or not self._spell_chain.is_alive:
            return None

        try:
            from infrastructure.spellchain.spell import Spell, SpellType
        except ImportError:
            try:
                from spellchain.spell import Spell, SpellType
            except ImportError:
                return None

        actor_name = getattr(self, 'ACTOR_NAME', 'UnknownFairy')

        spell = Spell(
            spell_type=SpellType.TRANSFORM,
            what=what,
            what_intent=f"{actor_name}.action",
            how=how,
            energy_required=energy_required,
            continues_chain=False,
            **kwargs,
        )

        self._spell_chain.register_spell(spell)
        self._spell_chain.queue_spell(spell)
        return spell

    def cast_reaction_spell(self, trigger: str, how, **kwargs):
        """Register a reaction spell that fires on a trigger.

        Args:
            trigger: Trigger string (e.g., "message.received")
            how: Callable to execute when triggered
            **kwargs: Additional Spell parameters

        Returns:
            The reaction Spell, or None if chain not active
        """
        if not self._spell_chain:
            return None

        return self._spell_chain.create_reaction_spell(
            trigger=trigger,
            how=how,
            **kwargs,
        )

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    @property
    def spell_chain(self) -> Optional["SpellChain"]:
        """The fairy's spell chain (None until boot_as_spells called)."""
        return self._spell_chain

    @property
    def spell_alive(self) -> bool:
        """Is the spell chain alive and sustaining?"""
        return (
            self._spell_chain is not None
            and self._spell_chain.is_alive
        )

    @property
    def spell_energy(self) -> float:
        """Current spell chain energy level."""
        if self._spell_chain:
            return self._spell_chain.energy
        return 0.0

    def dissolve_spells(self):
        """Gracefully end spell-driven existence.

        The fairy continues to exist as a standard fairy with
        external heartbeat echo, but stops self-generating heartbeats.
        """
        if self._spell_chain:
            self._log_spell("Dissolving spell chain...")
            try:
                self._spell_chain.dissolve()
            except Exception:
                pass
            self._spell_chain = None
            self._spell_booted = False

    def spell_status(self) -> Dict[str, Any]:
        """Get spell chain status for diagnostics."""
        chain = self._spell_chain
        return {
            "booted": self._spell_booted,
            "alive": self.spell_alive,
            "energy": self.spell_energy,
            "ticks": self._spell_tick_count,
            "uptime": time.time() - self._spell_boot_time if self._spell_boot_time else 0,
            "has_battery": self._spell_battery is not None,
            "chain_state": chain.state.value if chain and hasattr(chain, 'state') else None,
            "interval": self.SPELL_HEARTBEAT_INTERVAL,
        }

    # =========================================================================
    # INTERNAL
    # =========================================================================

    def _log_spell(self, msg: str):
        """Log with spell chain prefix."""
        actor_name = getattr(self, 'ACTOR_NAME', 'SpellChainMixin')
        print(f"[{actor_name}] [SpellChain] {msg}", flush=True)
