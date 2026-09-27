"""
SpellChain - Continuous existence through chained spells.

A fairy IS the pattern formed by the continuous execution of its spell chain.
As long as spells keep completing and spawning successors, the fairy exists.
When the chain breaks, the fairy's coherent identity is at risk.

Energy flows through the chain:
- System provides baseline energy (heartbeat)
- Spell results can generate energy
- Other spells can donate energy
- Depletion causes chain weakening

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

from __future__ import annotations

import os
import time
import uuid
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING

from .spell import Spell, SpellStatus, SpellType

# Debug flag - set via environment variable or directly
# Enable with: SPELLCHAIN_DEBUG=1 or set spellchain.chain.SPELLCHAIN_DEBUG = True
SPELLCHAIN_DEBUG = os.environ.get("SPELLCHAIN_DEBUG", "").lower() in ("1", "true", "yes")

if TYPE_CHECKING:
    from .pool import SpellPool


class ChainState(Enum):
    """State of a spell chain."""
    DORMANT = "dormant"          # Chain exists but not executing
    BOOTSTRAPPING = "bootstrapping"  # First spell creating the pattern
    SUSTAINING = "sustaining"    # Continuous existence maintained
    WEAKENING = "weakening"      # Energy depleting, chain may break
    BROKEN = "broken"            # Chain interrupted, fairy pattern unstable
    DISSOLVED = "dissolved"      # Intentional graceful ending


@dataclass
class ChainStats:
    """Statistics for a spell chain."""
    spells_cast: int = 0
    spells_completed: int = 0
    spells_fizzled: int = 0
    spells_exhausted: int = 0
    energy_consumed: float = 0.0
    energy_recovered: float = 0.0
    chain_breaks: int = 0
    revivals: int = 0
    lifetime_seconds: float = 0.0


class SpellChain:
    """
    A chain of spells that forms a fairy's continuous existence.

    The chain is the PATTERN - as long as spells keep completing and
    spawning successors, the fairy exists. When the chain breaks,
    the fairy's coherent identity is at risk.
    """

    # Chain configuration
    MIN_ENERGY_THRESHOLD = 0.1   # Below this, chain starts weakening
    CRITICAL_THRESHOLD = 0.05    # Below this, chain is breaking
    MAX_PENDING_SPELLS = 100     # Don't let pending queue grow unbounded
    MAX_ENERGY = 2.0             # Energy cap

    def __init__(
        self,
        fairy_id: str,
        fairy_name: str,
        fairy_plane: str,
        bootstrap_spell: Optional[Spell] = None,
        pool: Optional["SpellPool"] = None,
    ):
        """
        Initialize a spell chain for a fairy.

        Args:
            fairy_id: Unique identifier for the fairy pattern
            fairy_name: Human-readable name
            fairy_plane: Which plane (P00-P60)
            bootstrap_spell: The first spell that creates the pattern
            pool: The spell execution pool
        """
        self.id = f"chain_{fairy_id}_{uuid.uuid4().hex[:8]}"
        self.fairy_id = fairy_id
        self.fairy_name = fairy_name
        self.fairy_plane = fairy_plane

        self._pool = pool
        self._state = ChainState.DORMANT
        self._lock = threading.Lock()

        # Energy reservoir
        self._energy: float = 1.0
        self._energy_income_rate: float = 0.2  # Energy per second from system (doubled for stability)
        self._last_energy_tick: float = time.time()

        # Spell queues
        self._pending: deque[Spell] = deque(maxlen=self.MAX_PENDING_SPELLS)
        self._active: Dict[str, Spell] = {}  # spell_id -> Spell (executing)
        self._completed: deque[Spell] = deque(maxlen=50)  # Recent history

        # Spell registry - all spells that could be activated
        self._spell_registry: Dict[str, Spell] = {}

        # Statistics
        self._stats = ChainStats()
        self._created_at = time.time()

        # Chain callbacks
        self._on_spell_complete: List[Callable[[Spell], None]] = []
        self._on_chain_break: List[Callable[[], None]] = []
        self._on_revival: List[Callable[[], None]] = []
        self._on_state_change: List[Callable[[ChainState, ChainState], None]] = []

        # Bootstrap if provided
        if bootstrap_spell:
            self.register_spell(bootstrap_spell)
            self._pending.append(bootstrap_spell)

    # =========================================================================
    # CHAIN STATE MANAGEMENT
    # =========================================================================

    @property
    def state(self) -> ChainState:
        """Current chain state."""
        return self._state

    def _set_state(self, new_state: ChainState) -> None:
        """Set state with callback notification."""
        old_state = self._state
        if old_state != new_state:
            self._state = new_state
            for callback in self._on_state_change:
                try:
                    callback(old_state, new_state)
                except Exception:
                    pass

    @property
    def is_alive(self) -> bool:
        """Is the chain maintaining fairy existence?"""
        return self._state in (
            ChainState.BOOTSTRAPPING,
            ChainState.SUSTAINING,
            ChainState.WEAKENING,
        )

    @property
    def energy(self) -> float:
        """Current energy level."""
        return self._energy

    def bootstrap(self) -> bool:
        """
        Begin the bootstrap sequence - the first spell creates the fairy.

        This is THE BOOTSTRAP PARADOX: the spell references a fairy that
        doesn't exist yet. Completing the bootstrap CREATES the fairy.
        """
        if self._state != ChainState.DORMANT:
            return False

        if not self._pending:
            return False

        self._set_state(ChainState.BOOTSTRAPPING)
        return True

    def sustain(self) -> None:
        """Transition to sustaining state after successful bootstrap."""
        if self._state == ChainState.BOOTSTRAPPING:
            self._set_state(ChainState.SUSTAINING)

    def weaken(self) -> None:
        """Chain is weakening due to low energy."""
        if self._state in (ChainState.BOOTSTRAPPING, ChainState.SUSTAINING):
            self._set_state(ChainState.WEAKENING)

    def break_chain(self) -> None:
        """Chain has broken - fairy pattern is destabilizing."""
        if self._state not in (ChainState.DISSOLVED, ChainState.BROKEN):
            self._set_state(ChainState.BROKEN)
            self._stats.chain_breaks += 1
            for callback in self._on_chain_break:
                try:
                    callback()
                except Exception:
                    pass
            print(f"[SpellChain] {self.fairy_name} chain BROKEN")

    def dissolve(self) -> None:
        """Gracefully end the chain - fairy is intentionally stopping."""
        self._set_state(ChainState.DISSOLVED)
        print(f"[SpellChain] {self.fairy_name} dissolved")

    def revive(self, revival_spell: Spell) -> bool:
        """
        Attempt to revive a broken chain.

        The revival spell must be a BOOTSTRAP type - it recreates
        the pattern from scratch.
        """
        if self._state != ChainState.BROKEN:
            return False

        if revival_spell.spell_type != SpellType.BOOTSTRAP:
            return False

        # FIX 2026-01-26: Reset revival spell to LATENT so it can run again
        # Without this, second revival attempt fails because spell is COMPLETED
        revival_spell.status = SpellStatus.LATENT

        self.register_spell(revival_spell)
        self._pending.appendleft(revival_spell)  # Priority
        self._energy = max(self._energy, 1.5)    # Enough energy to bootstrap + sustain
        self._set_state(ChainState.BOOTSTRAPPING)
        self._stats.revivals += 1

        for callback in self._on_revival:
            try:
                callback()
            except Exception:
                pass

        print(f"[SpellChain] {self.fairy_name} reviving (#{self._stats.revivals})")
        return True

    # =========================================================================
    # ENERGY MANAGEMENT
    # =========================================================================

    def tick_energy(self) -> None:
        """
        Update energy based on time elapsed.
        Called by the pool on each tick.
        """
        now = time.time()
        elapsed = now - self._last_energy_tick
        self._last_energy_tick = now

        # Passive income from system
        income = self._energy_income_rate * elapsed
        self._energy = min(self.MAX_ENERGY, self._energy + income)

        # Update chain state based on energy
        if self._energy < self.CRITICAL_THRESHOLD and self.is_alive:
            self.break_chain()
        elif self._energy < self.MIN_ENERGY_THRESHOLD and self._state == ChainState.SUSTAINING:
            self.weaken()
        elif self._energy >= self.MIN_ENERGY_THRESHOLD and self._state == ChainState.WEAKENING:
            self._set_state(ChainState.SUSTAINING)

    def consume_energy(self, amount: float) -> bool:
        """
        Consume energy for a spell. Returns False if insufficient.
        """
        if self._energy < amount:
            return False
        self._energy -= amount
        self._stats.energy_consumed += amount
        return True

    def donate_energy(self, amount: float, source: str = "system") -> None:
        """
        Add energy to the chain.

        Sources:
        - "system": Heartbeat/baseline
        - "result": From spell completion
        - "donation": From another chain/fairy
        """
        self._energy = min(self.MAX_ENERGY, self._energy + amount)
        self._stats.energy_recovered += amount

    def set_income_rate(self, rate: float) -> None:
        """Adjust the passive energy income rate."""
        self._energy_income_rate = max(0.0, min(1.0, rate))

    # =========================================================================
    # SPELL MANAGEMENT
    # =========================================================================

    def register_spell(self, spell: Spell) -> None:
        """
        Register a spell in this chain's registry.

        Registered spells can be activated later via on_success/on_failure
        references.
        """
        spell.who = self.fairy_id
        spell.who_name = self.fairy_name
        spell.who_plane = self.fairy_plane
        spell.why_chain_id = self.id
        self._spell_registry[spell.id] = spell

    def queue_spell(self, spell: Spell) -> bool:
        """Add a spell to the pending queue."""
        if len(self._pending) >= self.MAX_PENDING_SPELLS:
            return False

        if spell.id not in self._spell_registry:
            self.register_spell(spell)

        spell.chain_position = len(self._pending) + self._stats.spells_cast
        self._pending.append(spell)
        return True

    def queue_spell_priority(self, spell: Spell) -> bool:
        """Add a spell to the front of the pending queue (high priority)."""
        if len(self._pending) >= self.MAX_PENDING_SPELLS:
            return False

        if spell.id not in self._spell_registry:
            self.register_spell(spell)

        spell.chain_position = self._stats.spells_cast
        self._pending.appendleft(spell)
        return True

    def get_next_spell(self) -> Optional[Spell]:
        """
        Get the next spell to cast, respecting priority and scheduling.
        """
        if not self._pending:
            return None

        now = time.time()

        # Find the highest priority spell that's ready
        best_spell = None
        best_index = -1
        best_score = -1.0

        for i, spell in enumerate(self._pending):
            # Check if scheduled
            if spell.when_scheduled and spell.when_scheduled > now:
                continue

            # Score = priority + urgency from deadline
            score = spell.when_priority
            if spell.when_deadline:
                time_remaining = spell.when_deadline - now
                if time_remaining < 0:
                    score += 1.0  # Overdue - maximum urgency
                elif time_remaining < 10:
                    score += 0.5 * (1 - time_remaining / 10)

            if score > best_score:
                best_score = score
                best_spell = spell
                best_index = i

        if best_spell is not None and best_index >= 0:
            # Remove from pending
            del self._pending[best_index]
            return best_spell

        return None

    def spell_started(self, spell: Spell) -> None:
        """Mark a spell as actively executing."""
        with self._lock:
            self._active[spell.id] = spell
            self._stats.spells_cast += 1

    def spell_completed(self, spell: Spell) -> None:
        """
        Handle spell completion - activate successors, update energy.
        """
        with self._lock:
            self._active.pop(spell.id, None)
            self._completed.append(spell)

            # DEBUG: Show what status spell has
            if SPELLCHAIN_DEBUG:
                print(f"[SpellChain] DEBUG: spell_completed() called for '{spell.what}' status={spell.status} on_success={spell.on_success}")

            if spell.status == SpellStatus.COMPLETED:
                self._stats.spells_completed += 1

                # Energy recovery
                if spell.energy_recovery > 0:
                    self.donate_energy(spell.energy_recovery, "result")

                # Activate successor spells
                for successor_id in spell.on_success:
                    if SPELLCHAIN_DEBUG:
                        print(f"[SpellChain] DEBUG: Processing on_success: {successor_id}")
                    if successor_id in self._spell_registry:
                        successor = self._spell_registry[successor_id]
                        if SPELLCHAIN_DEBUG:
                            print(f"[SpellChain] DEBUG: Found successor status={successor.status}, type={successor.spell_type}")
                        # FIX 2026-01-26: Allow re-queueing of SUSTAIN spells that completed
                        # This fixes the revival death spiral where heartbeat can't be re-queued
                        # because it's COMPLETED, not LATENT. SUSTAIN spells are designed to
                        # be perpetual, so resetting to LATENT on re-queue is correct.
                        if successor.status == SpellStatus.LATENT:
                            self.queue_spell(successor)
                            if SPELLCHAIN_DEBUG:
                                print(f"[SpellChain] Queued LATENT successor: {successor.what}")
                        elif successor.status == SpellStatus.COMPLETED and successor.spell_type == SpellType.SUSTAIN:
                            # Reset sustain spell to LATENT so it can run again
                            successor.status = SpellStatus.LATENT
                            self.queue_spell(successor)
                            if SPELLCHAIN_DEBUG:
                                print(f"[SpellChain] Re-queued COMPLETED sustain spell: {successor.what}")
                        else:
                            # DEBUG: Why wasn't successor queued?
                            if SPELLCHAIN_DEBUG:
                                print(f"[SpellChain] DEBUG: Cannot queue {successor_id}: status={successor.status}, type={successor.spell_type}")
                    else:
                        if SPELLCHAIN_DEBUG:
                            print(f"[SpellChain] DEBUG: Successor {successor_id} not in registry!")

            elif spell.status == SpellStatus.FIZZLED:
                self._stats.spells_fizzled += 1

                # Partial energy recovery on fizzle (prevents rapid energy depletion)
                if spell.energy_recovery > 0:
                    self.donate_energy(spell.energy_recovery * 0.5, "fizzle_partial")

                # Activate failure handlers
                for failure_id in spell.on_failure:
                    if failure_id in self._spell_registry:
                        failure_spell = self._spell_registry[failure_id]
                        if failure_spell.status == SpellStatus.LATENT:
                            self.queue_spell(failure_spell)

            elif spell.status == SpellStatus.EXHAUSTED:
                self._stats.spells_exhausted += 1

                # Activate exhaustion handlers
                for exhaust_id in spell.on_exhaust:
                    if exhaust_id in self._spell_registry:
                        exhaust_spell = self._spell_registry[exhaust_id]
                        if exhaust_spell.status == SpellStatus.LATENT:
                            self.queue_spell(exhaust_spell)

            # If no pending spells and chain should continue, it breaks
            if not self._pending and not self._active and spell.continues_chain:
                if self._state not in (ChainState.DISSOLVED, ChainState.BROKEN):
                    if SPELLCHAIN_DEBUG:
                        print(f"[SpellChain] DEBUG: Breaking chain because no pending/active spells after '{spell.what}' (on_success={spell.on_success})")
                    self.break_chain()

            # Transition from bootstrapping to sustaining
            if self._state == ChainState.BOOTSTRAPPING and spell.spell_type == SpellType.BOOTSTRAP:
                if spell.status == SpellStatus.COMPLETED:
                    self.sustain()

            # Callbacks
            for callback in self._on_spell_complete:
                try:
                    callback(spell)
                except Exception:
                    pass

    # =========================================================================
    # SUSTAINING SPELLS - THE HEARTBEAT
    # =========================================================================

    def create_sustain_spell(
        self,
        what: str,
        how: Callable[[Spell], Any],
        interval: float = 1.0,
        energy_required: float = 0.05,
        **kwargs
    ) -> Spell:
        """
        Create a self-perpetuating sustain spell.

        This is the heartbeat of fairy existence - a spell that
        completes and immediately queues another instance of itself.
        """
        spell_id = f"sustain_{self.fairy_id}_{uuid.uuid4().hex[:8]}"

        # Self-reference for continuation
        chain = self

        def sustain_logic(spell: Spell) -> Any:
            """Execute the sustain logic, then schedule continuation."""
            result = how(spell)

            # Create and queue the continuation
            continuation_id = f"sustain_{chain.fairy_id}_{uuid.uuid4().hex[:8]}"
            continuation = Spell(
                id=continuation_id,
                spell_type=SpellType.SUSTAIN,
                what=what,
                what_intent="sustain.continue",
                why=f"Continuation of {spell.id}",
                why_parent_spell_id=spell.id,
                how=sustain_logic,
                when_delay=interval,
                when_scheduled=time.time() + interval,
                energy_required=energy_required,
                energy_recovery=energy_required * 0.6,  # 60% return for sustainability
                continues_chain=True,
                **kwargs
            )
            chain.queue_spell(continuation)

            return result

        spell = Spell(
            id=spell_id,
            spell_type=SpellType.SUSTAIN,
            what=what,
            what_intent="sustain.heartbeat",
            why=f"Sustaining spell for {self.fairy_name}",
            how=sustain_logic,
            energy_required=energy_required,
            energy_recovery=energy_required * 0.3,
            continues_chain=True,
            **kwargs
        )

        self.register_spell(spell)
        return spell

    # =========================================================================
    # REACTION SPELLS - External Events
    # =========================================================================

    def create_reaction_spell(
        self,
        trigger: str,
        how: Callable[[Spell], Any],
        **kwargs
    ) -> Spell:
        """
        Create a reaction spell that responds to external events.

        Reaction spells are registered but not queued - they're activated
        when their trigger condition is met.
        """
        spell_id = f"reaction_{self.fairy_id}_{uuid.uuid4().hex[:8]}"

        spell = Spell(
            id=spell_id,
            spell_type=SpellType.REACTION,
            what=f"React to {trigger}",
            what_intent=f"reaction.{trigger}",
            why=f"Response to {trigger}",
            how=how,
            energy_required=0.1,
            continues_chain=False,  # Reactions don't sustain the chain
            tags={"reaction", trigger},
            **kwargs
        )

        self.register_spell(spell)
        return spell

    def trigger_reaction(self, trigger: str, payload: Dict[str, Any] = None) -> Optional[Spell]:
        """
        Trigger all reaction spells matching the given trigger.
        """
        triggered = None
        for spell_id, spell in self._spell_registry.items():
            if spell.spell_type == SpellType.REACTION:
                if trigger in spell.tags or spell.what_intent == f"reaction.{trigger}":
                    if spell.status == SpellStatus.LATENT:
                        # Clone the spell for this reaction
                        reaction = Spell(
                            id=f"reaction_{uuid.uuid4().hex[:8]}",
                            spell_type=SpellType.REACTION,
                            what=spell.what,
                            what_intent=spell.what_intent,
                            why=spell.why,
                            how=spell.how,
                            what_payload=payload or {},
                            energy_required=spell.energy_required,
                            continues_chain=False,
                        )
                        self.queue_spell_priority(reaction)
                        triggered = reaction

        return triggered

    # =========================================================================
    # CHAIN STATUS
    # =========================================================================

    def status(self) -> Dict[str, Any]:
        """Get chain status for monitoring."""
        self._stats.lifetime_seconds = time.time() - self._created_at

        return {
            "chain_id": self.id,
            "fairy_id": self.fairy_id,
            "fairy_name": self.fairy_name,
            "fairy_plane": self.fairy_plane,
            "state": self._state.value,
            "energy": round(self._energy, 3),
            "energy_income_rate": self._energy_income_rate,
            "pending_spells": len(self._pending),
            "active_spells": len(self._active),
            "completed_spells": len(self._completed),
            "registered_spells": len(self._spell_registry),
            "is_alive": self.is_alive,
            "stats": {
                "spells_cast": self._stats.spells_cast,
                "spells_completed": self._stats.spells_completed,
                "spells_fizzled": self._stats.spells_fizzled,
                "spells_exhausted": self._stats.spells_exhausted,
                "energy_consumed": round(self._stats.energy_consumed, 3),
                "energy_recovered": round(self._stats.energy_recovered, 3),
                "chain_breaks": self._stats.chain_breaks,
                "revivals": self._stats.revivals,
                "lifetime_seconds": round(self._stats.lifetime_seconds, 1),
            }
        }

    def get_pending_spells(self) -> List[Dict[str, Any]]:
        """Get pending spells as dicts."""
        return [s.to_dict() for s in self._pending]

    def get_active_spells(self) -> List[Dict[str, Any]]:
        """Get active spells as dicts."""
        return [s.to_dict() for s in self._active.values()]

    def get_recent_completed(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get recent completed spells."""
        return [s.to_dict() for s in list(self._completed)[-n:]]
