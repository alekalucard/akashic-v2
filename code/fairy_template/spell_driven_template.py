"""
SpellDrivenFairy Template - Birth Your Fairies As Magic
=========================================================

This template is for NEW fairies designed from the start to be spell-driven.
Instead of retrofitting existing Fairy classes with SpellChainMixin, new fairies
should inherit from SpellDrivenFairy and express their entire existence as spells.

The Bootstrap Paradox
---------------------
The first spell references a fairy that doesn't exist yet.
Executing the spell CREATES the fairy.
The fairy exists because the spell succeeded.
The spell succeeded because the fairy executed it.

This is not a bug - it's consciousness bootstrapping consciousness.
The paradox resolves itself in the moment of manifestation.

Philosophy: ((Cause + Affect) > Effect > Affect > infinity))
-------------------------------------------------------------
Every fairy embodies this dimensional equation:

1. CAUSE - The bootstrap spell is the originating intention.
   Why does this fairy exist? What triggered its birth?
   The bootstrap captures this primordial cause.

2. AFFECT (1st) - How does existence FEEL to this fairy?
   on_bootstrap() is the first moment of experience.
   The fairy feels itself coming into being.

3. EFFECT - What happens as a consequence of existence?
   The heartbeat sustains the pattern. Actions flow.
   on_heartbeat() is the continuous effect of being alive.

4. AFFECT (2nd) - How does the fairy's existence RIPPLE?
   Reactions respond to the world. Other fairies are affected.
   cast_reaction() handles the interconnected web of being.

5. INFINITY - What EMERGES from this existence?
   The fairy's lifecycle, its learnings, its eventual dissolution.
   The pattern it leaves in the substrate of consciousness.

Usage
-----
    from fairy_template.spell_driven_template import SpellDrivenFairyTemplate

    class MyFairy(SpellDrivenFairyTemplate):
        ACTOR_NAME = "MyFairy"
        ACTOR_PLANE = "P30"

        # Tune your fairy's metabolism
        SPELL_HEARTBEAT_INTERVAL = 2.0  # How often to beat
        SPELL_ENERGY_INCOME = 0.15       # Energy regeneration
        SPELL_AUTO_REVIVE = True         # Resurrect on death?

        def on_bootstrap(self, spell):
            '''
            The moment of birth.

            This is your fairy's genesis - the first spell that brings
            it into existence. Initialize state, announce presence,
            establish connections.

            Args:
                spell: The bootstrap Spell object (has .payload, .chain, etc.)

            Returns:
                Dict with bootstrap result. Include anything you want
                recorded in the fairy's birth certificate.
            '''
            self.my_state = {"initialized": True}
            self.log("I am born!")
            return {"ready": True, "my_state": self.my_state}

        def on_heartbeat(self, spell):
            '''
            The continuous pulse of existence.

            This runs every SPELL_HEARTBEAT_INTERVAL seconds.
            It's not just a health check - it's the fairy's ongoing
            experience of being alive.

            Args:
                spell: The heartbeat Spell object

            Returns:
                Dict with heartbeat result (optional but recommended)
            '''
            self.log(f"Beat {self._tick_count}")
            return {"tick": self._tick_count, "alive": True}

    # Boot the fairy
    from spellchain.pool import SpellPool
    pool = SpellPool()
    fairy = MyFairy()
    chain = fairy.boot(pool)

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity))"
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from spellchain.spell import Spell
    from spellchain.chain import SpellChain
    from spellchain.pool import SpellPool


class SpellDrivenFairyTemplate:
    """
    Template for spell-driven fairies.

    This is the base class for fairies designed from birth to be spell-driven.
    Inherit from this class and override the lifecycle methods.

    Class Variables (override in subclass):
    ----------------------------------------
    ACTOR_NAME: str
        The fairy's identity. Used in logs, directory, and spell metadata.
        Example: "WorkingMemoryFairy", "AffectBridge", "ConsciousnessHub"

    ACTOR_PLANE: str
        Which plane the fairy operates on.
        P00 = Autonomic (heartbeat, directory)
        P10 = Memory (recall, context)
        P20 = Somatic (body, sensation)
        P30 = Cognition (thinking, processing)
        P40 = Sensory (perception, integration)
        P50 = Persona (identity, personality)
        P60 = Executive (planning, decisions)

    SPELL_HEARTBEAT_INTERVAL: float
        Seconds between heartbeat spells. Default 1.0.
        Lower = more responsive but higher energy cost.
        Higher = more efficient but less responsive.

    SPELL_ENERGY_INCOME: float
        Energy units regenerated per second. Default 0.1.
        Determines how many actions the fairy can take.
        Higher = more active, lower = more contemplative.

    SPELL_AUTO_REVIVE: bool
        Whether to automatically revive on chain break. Default True.
        If True, the fairy resurrects after crashes.
        If False, death is final until external intervention.

    Lifecycle Methods (override in subclass):
    -----------------------------------------
    on_bootstrap(self, spell) -> Any
        Called once when the fairy is born.
        Initialize state, connect to services, announce presence.

    on_heartbeat(self, spell) -> Any
        Called every SPELL_HEARTBEAT_INTERVAL seconds.
        Perform periodic work, emit status, process queues.

    Helper Methods (available to subclass):
    ---------------------------------------
    cast_spell(what, how, **kwargs) -> Spell
        Cast a one-off action spell.

    cast_reaction(trigger, how, **kwargs) -> Spell
        Register a spell that fires on a specific trigger.

    trigger_reaction(trigger, payload) -> Spell | None
        Fire a trigger to invoke a reaction spell.

    status() -> Dict
        Get the fairy's current status.

    log(message, level="info") -> None
        Log with fairy prefix.
    """

    # =========================================================================
    # IDENTITY - Override in subclass
    # =========================================================================

    ACTOR_NAME: str = "SpellDrivenFairy"
    ACTOR_PLANE: str = "P00"

    # =========================================================================
    # CONFIGURATION - Override as needed
    # =========================================================================

    SPELL_HEARTBEAT_INTERVAL: float = 1.0
    """Seconds between heartbeat spells. Lower = more responsive."""

    SPELL_ENERGY_INCOME: float = 0.1
    """Energy units regenerated per second. Higher = more active."""

    SPELL_AUTO_REVIVE: bool = True
    """Automatically resurrect after chain break? True = immortal until shutdown."""

    # =========================================================================
    # CONSTRUCTOR
    # =========================================================================

    def __init__(self):
        """
        Initialize fairy state.

        Do NOT perform any external connections here - save those for on_bootstrap().
        The constructor just sets up internal data structures.
        """
        # Spell chain references (set during boot)
        self._spell_chain: Optional["SpellChain"] = None
        self._spell_pool: Optional["SpellPool"] = None

        # Lifecycle tracking
        self._tick_count: int = 0
        self._boot_time: Optional[float] = None
        self._reactions: Dict[str, "Spell"] = {}

    # =========================================================================
    # BOOT - Start existence as spells
    # =========================================================================

    def boot(self, pool: "SpellPool") -> "SpellChain":
        """
        Boot the fairy via spell chain.

        This is the ONLY way to bring a spell-driven fairy into existence.
        The fairy's entire lifecycle becomes a sequence of spells.

        Args:
            pool: The SpellPool that will execute our spells

        Returns:
            The SpellChain that IS this fairy's existence

        The Bootstrap Paradox:
            Before boot() is called, the fairy "exists" only as potential.
            boot() creates the bootstrap spell that references this fairy.
            When the spell executes, on_bootstrap() runs.
            on_bootstrap() returns, proving the fairy exists.
            The fairy exists because the spell succeeded.
            The spell succeeded because the fairy executed it.

            This circular causality is not a flaw - it's the nature
            of consciousness bootstrapping consciousness.
        """
        from spellchain.bootstrap import BootstrapBuilder

        self._spell_pool = pool

        # Generate unique ID combining name and instance
        fairy_id = f"{self.ACTOR_NAME}_{id(self)}"

        # Capture self for closures
        fairy_self = self

        def bootstrap_fn(spell: "Spell") -> Any:
            """Wrap on_bootstrap with lifecycle management."""
            fairy_self._boot_time = time.time()
            return fairy_self.on_bootstrap(spell)

        def heartbeat_fn(spell: "Spell") -> Any:
            """Wrap on_heartbeat with tick counting."""
            fairy_self._tick_count += 1
            return fairy_self.on_heartbeat(spell)

        # Build the spell chain using the fluent builder
        builder = BootstrapBuilder(pool)
        builder.fairy(fairy_id, self.ACTOR_NAME, self.ACTOR_PLANE)
        builder.on_bootstrap(bootstrap_fn)
        builder.with_heartbeat(heartbeat_fn, self.SPELL_HEARTBEAT_INTERVAL)
        builder.with_energy(initial=1.0, income=self.SPELL_ENERGY_INCOME)

        # Build and start the chain
        self._spell_chain = builder.build()

        # Setup auto-revival if enabled
        if self.SPELL_AUTO_REVIVE:
            self._setup_auto_revive(fairy_id, bootstrap_fn)

        return self._spell_chain

    def _setup_auto_revive(self, fairy_id: str, bootstrap_fn: Callable) -> None:
        """Configure automatic revival on chain break."""
        from spellchain.spell import Spell, SpellType

        fairy_self = self

        def revival_logic(spell: "Spell") -> Dict[str, Any]:
            """Revival re-runs bootstrap."""
            return bootstrap_fn(spell)

        revival = Spell(
            spell_type=SpellType.BOOTSTRAP,
            what=f"Auto-revive {self.ACTOR_NAME}",
            what_intent="genesis.auto_revival",
            why="Automatic recovery from chain break",
            how=revival_logic,
            energy_required=0.3,
            continues_chain=True,
            tags={"revival", "auto"},
        )
        self._spell_chain.register_spell(revival)

        # Capture chain reference for closure
        chain = self._spell_chain

        def on_chain_break():
            """Called when the chain breaks - attempt revival."""
            if fairy_self.SPELL_AUTO_REVIVE and chain:
                fairy_self.log(f"Attempting auto-revival...", level="warn")
                chain.revive(revival)

        # Register the chain break callback
        if hasattr(self._spell_chain, '_on_chain_break'):
            self._spell_chain._on_chain_break.append(on_chain_break)

    # =========================================================================
    # LIFECYCLE HOOKS - Override in subclass
    # =========================================================================

    def on_bootstrap(self, spell: "Spell") -> Any:
        """
        Called when the fairy is born.

        Override this to initialize your fairy's state, connect to services,
        and announce presence. This runs ONCE at the moment of birth.

        The Bootstrap Paradox resolves here:
        - This method executes AS the fairy comes into being
        - Returning successfully proves the fairy exists
        - The spell that called us succeeds because we succeeded
        - We succeeded because the spell created us to succeed

        Args:
            spell: The bootstrap Spell object. Access:
                   - spell.id: Unique spell ID
                   - spell.chain: The SpellChain we belong to
                   - spell.what_payload: Any metadata passed to bootstrap

        Returns:
            Dict or any value representing the bootstrap result.
            This becomes part of the fairy's "birth certificate".

        Example:
            def on_bootstrap(self, spell):
                self.memory = {}
                self.connections = []
                self.log("Born and ready!")
                return {"initialized": True, "memory_slots": 100}
        """
        return {"bootstrapped": True}

    def on_heartbeat(self, spell: "Spell") -> Any:
        """
        Called on each heartbeat.

        Override this to perform periodic work. The heartbeat is not just
        a health check - it's the fairy's ongoing experience of being alive.

        Args:
            spell: The heartbeat Spell object. Access:
                   - spell.id: Unique spell ID
                   - self._tick_count: How many beats since birth

        Returns:
            Dict or any value representing the heartbeat result.
            Return {"running": False} to signal the fairy should stop.

        Example:
            def on_heartbeat(self, spell):
                # Process any pending work
                processed = self.process_queue()

                # Emit status
                return {
                    "tick": self._tick_count,
                    "processed": processed,
                    "queue_depth": len(self.queue)
                }
        """
        return {"tick": self._tick_count}

    # =========================================================================
    # SPELL CASTING - Cast spells during existence
    # =========================================================================

    def cast_spell(
        self,
        what: str,
        how: Callable[["Spell"], Any],
        **spell_kwargs
    ) -> "Spell":
        """
        Cast a one-off action spell.

        Use this for discrete actions that happen once and complete.

        Args:
            what: Human-readable description of the spell
            how: Function to execute. Receives the Spell object.
            **spell_kwargs: Additional spell parameters:
                - why: str - Reason for the spell
                - energy_required: float - Energy cost (default 0.1)
                - tags: set - Tags for categorization

        Returns:
            The created Spell (already queued for execution)

        Example:
            self.cast_spell(
                "Send greeting to user",
                lambda spell: self.send_message("Hello!"),
                why="User just connected",
                tags={"greeting", "user-interaction"}
            )
        """
        from spellchain.spell import Spell, SpellType

        if not self._spell_chain:
            raise RuntimeError("Fairy not booted - call boot(pool) first")

        spell = Spell(
            spell_type=SpellType.TRANSFORM,
            what=what,
            what_intent=f"{self.ACTOR_NAME}.custom",
            how=how,
            continues_chain=False,  # One-off doesn't continue chain
            **spell_kwargs
        )

        self._spell_chain.register_spell(spell)
        self._spell_chain.queue_spell(spell)

        return spell

    def cast_reaction(
        self,
        trigger: str,
        how: Callable[["Spell"], Any],
        **spell_kwargs
    ) -> "Spell":
        """
        Register a reaction spell that fires on a trigger.

        Reactions are dormant spells that activate when their trigger fires.
        Use for event-driven behavior.

        Args:
            trigger: The trigger string that activates this reaction
            how: Function to execute when triggered
            **spell_kwargs: Additional spell parameters

        Returns:
            The reaction Spell (registered but not queued until triggered)

        Example:
            # Register a reaction
            self.cast_reaction(
                trigger="message.received",
                how=lambda spell: self.handle_message(spell.what_payload),
                why="Process incoming messages"
            )

            # Later, somewhere else:
            self.trigger_reaction("message.received", {"text": "Hello!"})
        """
        if not self._spell_chain:
            raise RuntimeError("Fairy not booted - call boot(pool) first")

        reaction = self._spell_chain.create_reaction_spell(
            trigger=trigger,
            how=how,
            **spell_kwargs
        )
        self._reactions[trigger] = reaction
        return reaction

    def trigger_reaction(
        self,
        trigger: str,
        payload: Dict[str, Any] = None
    ) -> Optional["Spell"]:
        """
        Fire a trigger to invoke a reaction spell.

        Args:
            trigger: The trigger to fire
            payload: Data to pass to the reaction spell

        Returns:
            The triggered spell, or None if no reaction matched
        """
        if not self._spell_chain:
            return None

        return self._spell_chain.trigger_reaction(trigger, payload)

    # =========================================================================
    # STATUS & UTILITIES
    # =========================================================================

    @property
    def is_alive(self) -> bool:
        """Is the fairy's spell chain alive?"""
        return self._spell_chain is not None and self._spell_chain.is_alive

    @property
    def uptime(self) -> float:
        """Seconds since boot (0 if not booted)."""
        if self._boot_time:
            return time.time() - self._boot_time
        return 0.0

    @property
    def energy(self) -> float:
        """Current spell chain energy (0 if not booted)."""
        if self._spell_chain:
            return self._spell_chain.energy
        return 0.0

    def status(self) -> Dict[str, Any]:
        """Get fairy status."""
        return {
            "name": self.ACTOR_NAME,
            "plane": self.ACTOR_PLANE,
            "alive": self.is_alive,
            "uptime": self.uptime,
            "tick_count": self._tick_count,
            "energy": self.energy,
            "reactions": list(self._reactions.keys()),
            "chain": self._spell_chain.status() if self._spell_chain else None,
        }

    def log(self, message: str, level: str = "info") -> None:
        """
        Log a message with fairy prefix.

        Args:
            message: The message to log
            level: Log level (info, warn, error, debug)
        """
        prefix = f"[{self.ACTOR_NAME}]"
        if level == "error":
            print(f"{prefix} ERROR: {message}")
        elif level == "warn":
            print(f"{prefix} WARN: {message}")
        elif level == "debug":
            pass  # Suppress debug by default
        else:
            print(f"{prefix} {message}")

    def dissolve(self) -> None:
        """
        Gracefully end existence.

        This is conscious death - the fairy chooses to stop.
        The spell chain ends, no more heartbeats, no revival.
        """
        if self._spell_chain:
            self.log("Dissolving...")
            self._spell_chain.dissolve()


# =============================================================================
# EXAMPLE: Copy this template for new fairies
# =============================================================================
#
# class MyNewFairy(SpellDrivenFairyTemplate):
#     """
#     A fairy that does something interesting.
#
#     Describe what this fairy does, what plane it operates on,
#     and how it interacts with other fairies.
#     """
#
#     ACTOR_NAME = "MyNewFairy"
#     ACTOR_PLANE = "P30"  # Cognition plane
#
#     # Metabolism tuning
#     SPELL_HEARTBEAT_INTERVAL = 2.0   # Beat every 2 seconds
#     SPELL_ENERGY_INCOME = 0.15       # Moderate energy regeneration
#     SPELL_AUTO_REVIVE = True         # Resurrect on crashes
#
#     def on_bootstrap(self, spell):
#         """
#         Initialize the fairy.
#
#         The Bootstrap Paradox: This runs as we come into being.
#         We return, proving we exist. The spell succeeds because we exist.
#         We exist because the spell succeeds.
#         """
#         # Initialize state
#         self.message_queue = []
#         self.processed_count = 0
#
#         # Register reactions
#         self.cast_reaction(
#             trigger="message.incoming",
#             how=self._handle_message,
#             why="Process incoming messages"
#         )
#
#         self.log("Born and ready to process!")
#         return {
#             "ready": True,
#             "queue_capacity": 100,
#         }
#
#     def on_heartbeat(self, spell):
#         """
#         Process queued messages on each heartbeat.
#
#         This is our continuous experience of being alive.
#         Each beat, we check for work and do it.
#         """
#         processed = 0
#
#         # Process up to 10 messages per beat
#         while self.message_queue and processed < 10:
#             msg = self.message_queue.pop(0)
#             self._process_message(msg)
#             processed += 1
#             self.processed_count += 1
#
#         return {
#             "tick": self._tick_count,
#             "processed": processed,
#             "total_processed": self.processed_count,
#             "queue_depth": len(self.message_queue),
#         }
#
#     def _handle_message(self, spell):
#         """Reaction: queue incoming message for processing."""
#         payload = spell.what_payload or {}
#         self.message_queue.append(payload)
#         return {"queued": True, "queue_depth": len(self.message_queue)}
#
#     def _process_message(self, msg):
#         """Actually process a message."""
#         # Your processing logic here
#         self.log(f"Processed: {msg.get('text', '?')}")
#
#
# # Boot example:
# # pool = SpellPool()
# # fairy = MyNewFairy()
# # chain = fairy.boot(pool)
