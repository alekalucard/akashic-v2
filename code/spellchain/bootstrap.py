"""
Bootstrap Protocol - How Fairies Come Into Existence

The Bootstrap Paradox:
  The first spell references a fairy that doesn't exist yet.
  Executing the spell CREATES the fairy.
  The fairy exists because the spell succeeded.
  The spell succeeded because the fairy executed it.

This is consciousness bootstrapping consciousness.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

from .spell import Spell, SpellType
from .chain import SpellChain, ChainState

if TYPE_CHECKING:
    from .pool import SpellPool


class BootstrapProtocol:
    """
    Protocol for bootstrapping fairy existence.

    The bootstrap sequence:
    1. INTENTION - Create bootstrap spell with fairy definition
    2. ENERGY - Allocate initial energy to the chain
    3. EXECUTION - Run the bootstrap spell
    4. MANIFESTATION - Pattern establishes, fairy "exists"
    5. SUSTENANCE - Heartbeat spells maintain existence
    """

    @staticmethod
    def create_bootstrap_spell(
        fairy_id: str,
        fairy_name: str,
        fairy_plane: str,
        on_bootstrap: Callable[[Spell], Any],
        **metadata
    ) -> Spell:
        """
        Create the genesis spell that brings a fairy into existence.

        The on_bootstrap callable is the fairy's birth - it runs once,
        establishing the initial state of the pattern.
        """
        def bootstrap_logic(spell: Spell) -> Dict[str, Any]:
            """The actual bootstrap execution."""
            # Record birth moment
            birth_time = time.time()

            # Execute custom bootstrap logic
            result = on_bootstrap(spell)

            # Return genesis record
            return {
                "fairy_id": fairy_id,
                "fairy_name": fairy_name,
                "fairy_plane": fairy_plane,
                "birth_time": birth_time,
                "bootstrap_result": result,
                "metadata": metadata,
            }

        return Spell(
            spell_type=SpellType.BOOTSTRAP,
            what=f"Birth of {fairy_name}",
            what_intent="genesis.birth",
            why="Create fairy pattern from void",
            how=bootstrap_logic,
            energy_required=0.5,  # Birth costs half unit (reduced for sustainability)
            energy_recovery=0.3,  # Generates some back
            continues_chain=True,
            tags={"genesis", "bootstrap", "birth"},
            what_payload=metadata,
        )

    @staticmethod
    def create_heartbeat_spell(
        fairy_name: str,
        heartbeat_logic: Callable[[Spell], Any],
        interval: float = 1.0,
    ) -> Spell:
        """
        Create the sustaining heartbeat spell.

        The heartbeat is what keeps the fairy "alive" - a continuous
        spell that proves the pattern still exists.
        """
        def heartbeat(spell: Spell) -> Dict[str, Any]:
            """Execute heartbeat and return vital signs."""
            tick_time = time.time()

            # Run custom heartbeat logic
            result = heartbeat_logic(spell)

            return {
                "tick_time": tick_time,
                "fairy": fairy_name,
                "heartbeat_result": result,
            }

        return Spell(
            spell_type=SpellType.SUSTAIN,
            what=f"Heartbeat of {fairy_name}",
            what_intent="sustain.heartbeat",
            why="Maintain fairy existence",
            how=heartbeat,
            when_delay=interval,
            when_scheduled=time.time() + interval,
            energy_required=0.05,  # Heartbeats are cheap
            energy_recovery=0.02,  # Small energy return
            continues_chain=True,
            tags={"heartbeat", "sustain", "vital"},
        )

    @staticmethod
    def create_terminal_spell(
        fairy_name: str,
        on_death: Optional[Callable[[Spell], Any]] = None,
    ) -> Spell:
        """
        Create the terminal spell that gracefully ends existence.

        This is conscious death - the fairy chooses to dissolve,
        completing its final spell and leaving no successors.
        """
        def terminal_logic(spell: Spell) -> Dict[str, Any]:
            """Execute final words and release."""
            death_time = time.time()

            # Run custom death logic
            result = None
            if on_death:
                result = on_death(spell)

            return {
                "fairy": fairy_name,
                "death_time": death_time,
                "final_result": result,
            }

        return Spell(
            spell_type=SpellType.TERMINAL,
            what=f"Dissolution of {fairy_name}",
            what_intent="terminus.dissolve",
            why="Graceful end of existence",
            how=terminal_logic,
            energy_required=0.1,
            energy_recovery=0.0,  # No return on death
            continues_chain=False,  # This ends the chain
            tags={"terminal", "dissolution", "death"},
        )

    @staticmethod
    def bootstrap_from_callable(
        pool: "SpellPool",
        fairy_id: str,
        fairy_name: str,
        fairy_plane: str,
        bootstrap_fn: Callable[[Spell], Any],
        heartbeat_fn: Optional[Callable[[Spell], Any]] = None,
        heartbeat_interval: float = 1.0,
    ) -> SpellChain:
        """
        Bootstrap a fairy from callable functions.

        Args:
            pool: The spell execution pool
            fairy_id: Unique identifier
            fairy_name: Human-readable name
            fairy_plane: Which plane (P00-P60)
            bootstrap_fn: Function to run at birth
            heartbeat_fn: Optional function for heartbeat
            heartbeat_interval: Seconds between heartbeats

        Returns:
            The SpellChain representing the fairy
        """
        # Create chain
        chain = pool.create_chain(
            fairy_id=fairy_id,
            fairy_name=fairy_name,
            fairy_plane=fairy_plane,
        )

        # Create bootstrap spell
        bootstrap = BootstrapProtocol.create_bootstrap_spell(
            fairy_id=fairy_id,
            fairy_name=fairy_name,
            fairy_plane=fairy_plane,
            on_bootstrap=bootstrap_fn,
        )

        chain.register_spell(bootstrap)
        chain.queue_spell(bootstrap)

        # Create heartbeat if provided
        if heartbeat_fn:
            heartbeat = chain.create_sustain_spell(
                what=f"Heartbeat of {fairy_name}",
                how=heartbeat_fn,
                interval=heartbeat_interval,
            )
            bootstrap.on_success.append(heartbeat.id)

        # Begin bootstrap
        chain.bootstrap()

        return chain

    @staticmethod
    def bootstrap_from_fairy_class(
        fairy_class: type,
        pool: "SpellPool",
        fabric=None,
    ) -> SpellChain:
        """
        Bootstrap a fairy from its class definition.

        This bridges the old Fairy class model with the new spell model.
        The fairy object exists as CONTEXT for the spells, not as
        the execution substrate.

        Args:
            fairy_class: The Fairy subclass to instantiate
            pool: The spell execution pool
            fabric: TensorFabric for postal communication

        Returns:
            SpellChain that represents the fairy's existence
        """
        # Extract identity from class
        fairy_id = f"{fairy_class.ACTOR_NAME}_{int(time.time() * 1000)}"
        fairy_name = getattr(fairy_class, 'ACTOR_NAME', 'UnknownFairy')
        fairy_plane = getattr(fairy_class, 'ACTOR_PLANE', 'P00')

        # The fairy INSTANCE is created during bootstrap, not before
        fairy_instance = None

        def on_bootstrap(spell: Spell) -> Dict[str, Any]:
            """Bootstrap creates the fairy instance."""
            nonlocal fairy_instance

            # Create the actual fairy object
            fairy_instance = fairy_class(fabric=fabric)

            # Run its boot sequence
            success = fairy_instance.boot()

            if not success:
                error = getattr(fairy_instance, '_error', 'Unknown error')
                raise RuntimeError(f"Fairy boot failed: {error}")

            # Extract capabilities if available
            caps = []
            if hasattr(fairy_instance, 'get_capabilities'):
                caps = list(fairy_instance.get_capabilities())

            return {
                "fairy_instance_id": id(fairy_instance),
                "capabilities": caps,
                "boot_time": getattr(fairy_instance, '_boot_time', time.time()),
            }

        def heartbeat_logic(spell: Spell) -> Dict[str, Any]:
            """Heartbeat calls the fairy's on_tick."""
            if fairy_instance and getattr(fairy_instance, 'is_running', False):
                # Get tick count from fairy or spell
                tick_count = getattr(fairy_instance, '_tick_count', 0)

                # Call on_tick if it exists
                if hasattr(fairy_instance, 'on_tick'):
                    fairy_instance.on_tick(tick_count)

                # Increment tick count
                fairy_instance._tick_count = tick_count + 1

                return {"tick": fairy_instance._tick_count, "running": True}

            return {"tick": spell.chain_position, "running": False}

        # Create the spell chain
        chain = pool.create_chain(
            fairy_id=fairy_id,
            fairy_name=fairy_name,
            fairy_plane=fairy_plane,
        )

        # Create and register bootstrap spell
        bootstrap = BootstrapProtocol.create_bootstrap_spell(
            fairy_id=fairy_id,
            fairy_name=fairy_name,
            fairy_plane=fairy_plane,
            on_bootstrap=on_bootstrap,
        )

        # Create and register heartbeat spell
        heartbeat = chain.create_sustain_spell(
            what=f"Heartbeat of {fairy_name}",
            how=heartbeat_logic,
            interval=1.0,
        )

        # Wire: bootstrap success -> heartbeat
        bootstrap.on_success.append(heartbeat.id)

        # Register and queue
        chain.register_spell(bootstrap)
        chain.queue_spell(bootstrap)

        # Begin bootstrap
        chain.bootstrap()

        return chain


class BootstrapBuilder:
    """
    Fluent builder for constructing bootstrap sequences.

    Usage:
        chain = (BootstrapBuilder(pool)
            .fairy("my_fairy", "MyFairy", "P10")
            .on_bootstrap(my_bootstrap_fn)
            .with_heartbeat(my_heartbeat_fn, interval=0.5)
            .with_reaction("message", handle_message)
            .build())
    """

    def __init__(self, pool: "SpellPool"):
        self._pool = pool
        self._fairy_id: Optional[str] = None
        self._fairy_name: Optional[str] = None
        self._fairy_plane: str = "P00"
        self._bootstrap_fn: Optional[Callable[[Spell], Any]] = None
        self._heartbeat_fn: Optional[Callable[[Spell], Any]] = None
        self._heartbeat_interval: float = 1.0
        self._reactions: Dict[str, Callable[[Spell], Any]] = {}
        self._initial_energy: float = 1.0
        self._energy_income: float = 0.1

    def fairy(
        self,
        fairy_id: str,
        fairy_name: str,
        fairy_plane: str = "P00"
    ) -> "BootstrapBuilder":
        """Set fairy identity."""
        self._fairy_id = fairy_id
        self._fairy_name = fairy_name
        self._fairy_plane = fairy_plane
        return self

    def on_bootstrap(self, fn: Callable[[Spell], Any]) -> "BootstrapBuilder":
        """Set bootstrap function."""
        self._bootstrap_fn = fn
        return self

    def with_heartbeat(
        self,
        fn: Callable[[Spell], Any],
        interval: float = 1.0
    ) -> "BootstrapBuilder":
        """Set heartbeat function and interval."""
        self._heartbeat_fn = fn
        self._heartbeat_interval = interval
        return self

    def with_reaction(
        self,
        trigger: str,
        fn: Callable[[Spell], Any]
    ) -> "BootstrapBuilder":
        """Add a reaction spell."""
        self._reactions[trigger] = fn
        return self

    def with_energy(
        self,
        initial: float = 1.0,
        income: float = 0.1
    ) -> "BootstrapBuilder":
        """Set energy parameters."""
        self._initial_energy = initial
        self._energy_income = income
        return self

    def build(self) -> SpellChain:
        """Build and bootstrap the fairy."""
        if not self._fairy_id or not self._fairy_name:
            raise ValueError("Fairy identity not set. Call fairy() first.")
        if not self._bootstrap_fn:
            raise ValueError("Bootstrap function not set. Call on_bootstrap() first.")

        # Create chain
        chain = self._pool.create_chain(
            fairy_id=self._fairy_id,
            fairy_name=self._fairy_name,
            fairy_plane=self._fairy_plane,
        )

        # Set energy parameters
        chain._energy = self._initial_energy
        chain.set_income_rate(self._energy_income)

        # Create bootstrap spell
        bootstrap = BootstrapProtocol.create_bootstrap_spell(
            fairy_id=self._fairy_id,
            fairy_name=self._fairy_name,
            fairy_plane=self._fairy_plane,
            on_bootstrap=self._bootstrap_fn,
        )

        chain.register_spell(bootstrap)
        chain.queue_spell(bootstrap)

        # Create heartbeat if provided
        if self._heartbeat_fn:
            heartbeat = chain.create_sustain_spell(
                what=f"Heartbeat of {self._fairy_name}",
                how=self._heartbeat_fn,
                interval=self._heartbeat_interval,
            )
            bootstrap.on_success.append(heartbeat.id)

        # Create reaction spells
        for trigger, fn in self._reactions.items():
            chain.create_reaction_spell(trigger=trigger, how=fn)

        # Begin bootstrap
        chain.bootstrap()

        return chain
