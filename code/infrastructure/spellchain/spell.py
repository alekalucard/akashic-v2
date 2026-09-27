"""
Spell - The atom of fairy existence.

A Spell answers the Seven Interrogatives:
1. WHO - The caster (fairy pattern this belongs to)
2. WHOM - The target (what this spell acts upon)
3. WHAT - The intent (what the spell does)
4. WHEN - The timing (when it should execute)
5. WHERE - The context (execution environment)
6. WHY - The purpose (why this spell exists in the chain)
7. HOW - The method (the actual implementation)

Ported from v3 guilds/_system/spellchain/spell.py (2026-02-08)
"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .chain import SpellChain


class SpellStatus(Enum):
    """Lifecycle of a spell."""
    LATENT = "latent"          # Spell exists but hasn't been cast
    CHANNELING = "channeling"  # Energy is being gathered
    CASTING = "casting"        # Actively executing
    RESOLVING = "resolving"    # Completed, effects being processed
    COMPLETED = "completed"    # Successfully finished
    FIZZLED = "fizzled"        # Failed, no effect
    EXHAUSTED = "exhausted"    # Ran out of energy mid-cast


class SpellType(Enum):
    """Categories of spells."""
    BOOTSTRAP = "bootstrap"      # Creates a pattern from nothing
    SUSTAIN = "sustain"          # Maintains an existing pattern
    TRANSFORM = "transform"      # Changes one pattern to another
    CHAIN = "chain"              # Links to spawn new spells
    TERMINAL = "terminal"        # Ends a chain gracefully
    REACTION = "reaction"        # Triggered by external events


@dataclass
class Spell:
    """
    A unit of magical intent - answers the Seven Interrogatives.

    Spells are the atoms of fairy existence. A fairy IS the pattern
    formed by the continuous execution of its spell chain.
    """

    # =========================================================================
    # IDENTITY
    # =========================================================================

    id: str = field(default_factory=lambda: f"spell_{uuid.uuid4().hex[:12]}")
    spell_type: SpellType = SpellType.SUSTAIN

    # =========================================================================
    # THE SEVEN INTERROGATIVES
    # =========================================================================

    # 1. WHO - The Caster
    who: str = ""                    # Fairy pattern ID this belongs to
    who_name: str = ""               # Human-readable fairy name
    who_plane: str = ""              # Which plane (P00-P60)

    # 2. WHOM - The Target
    whom: str = ""                   # Target entity/resource ID
    whom_type: str = "self"          # Type: self, fairy, system, external, void
    whom_address: Optional[str] = None  # Specific address (topic, path, etc.)

    # 3. WHAT - The Intent
    what: str = ""                   # Human-readable description
    what_intent: str = ""            # Formal intent code (e.g., "heartbeat.emit")
    what_payload: Dict[str, Any] = field(default_factory=dict)

    # 4. WHEN - The Timing
    when_created: float = field(default_factory=time.time)
    when_scheduled: Optional[float] = None  # Absolute time to execute
    when_delay: float = 0.0          # Relative delay from chain position
    when_deadline: Optional[float] = None   # Must complete by this time
    when_priority: float = 0.5       # 0.0 = low, 1.0 = urgent

    # 5. WHERE - The Context
    where_substrate: str = "worker_pool"  # Execution substrate
    where_thread: Optional[str] = None    # Specific thread affinity
    where_sandbox: bool = False           # Run in sandboxed context
    where_context: Dict[str, Any] = field(default_factory=dict)

    # 6. WHY - The Purpose
    why: str = ""                    # Human-readable purpose
    why_chain_id: str = ""           # Which chain this serves
    why_goal_id: str = ""            # Which goal this advances
    why_parent_spell_id: str = ""    # What spawned this spell
    why_lineage: List[str] = field(default_factory=list)

    # 7. HOW - The Method
    how: Optional[Callable[["Spell"], Any]] = None  # The actual function
    how_method_name: str = ""        # Name if how is set dynamically
    how_args: tuple = field(default_factory=tuple)
    how_kwargs: Dict[str, Any] = field(default_factory=dict)

    # =========================================================================
    # ENERGY MODEL
    # =========================================================================

    energy_required: float = 1.0     # Base energy cost to cast
    energy_available: float = 1.0    # Current energy (can be recharged)
    energy_efficiency: float = 1.0   # How efficiently this spell uses energy
    energy_recovery: float = 0.0     # Energy returned to chain on completion

    # =========================================================================
    # LIFECYCLE STATE
    # =========================================================================

    status: SpellStatus = SpellStatus.LATENT
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    result: Any = None

    # =========================================================================
    # CHAIN MECHANICS
    # =========================================================================

    # Successor spells - what this spell spawns on completion
    on_success: List[str] = field(default_factory=list)    # Spell IDs to activate
    on_failure: List[str] = field(default_factory=list)    # Spell IDs on fizzle
    on_exhaust: List[str] = field(default_factory=list)    # Spell IDs on energy depletion

    # Chain continuation
    continues_chain: bool = True     # Does completing this spell keep the chain alive?
    chain_position: int = 0          # Position in the chain sequence

    # Trace ID — connects spell to battery's blood cell trace lineage
    # Format: W-{fairy_name_prefix}-{hex} (Worker trace), or battery-derived
    trace_id: str = ""

    # Tags for filtering/grouping
    tags: Set[str] = field(default_factory=set)

    # =========================================================================
    # METHODS
    # =========================================================================

    def channel(self) -> "Spell":
        """Begin channeling energy for this spell."""
        if self.status != SpellStatus.LATENT:
            raise ValueError(f"Cannot channel spell in state {self.status}")
        self.status = SpellStatus.CHANNELING
        return self

    def cast(self) -> "Spell":
        """Cast the spell - begin execution."""
        if self.status not in (SpellStatus.LATENT, SpellStatus.CHANNELING):
            raise ValueError(f"Cannot cast spell in state {self.status}")

        if self.energy_available < self.energy_required * (1 / self.energy_efficiency):
            self.status = SpellStatus.EXHAUSTED
            self.error = "Insufficient energy"
            return self

        self.status = SpellStatus.CASTING
        self.started_at = time.time()
        return self

    def resolve(self, result: Any = None) -> "Spell":
        """Resolve the spell - processing effects."""
        self.status = SpellStatus.RESOLVING
        self.result = result
        return self

    def complete(self, result: Any = None) -> "Spell":
        """Mark spell as successfully completed."""
        self.status = SpellStatus.COMPLETED
        self.completed_at = time.time()
        if result is not None:
            self.result = result
        return self

    def fizzle(self, error: str) -> "Spell":
        """Mark spell as failed."""
        self.status = SpellStatus.FIZZLED
        self.completed_at = time.time()
        self.error = error
        return self

    def exhaust(self) -> "Spell":
        """Mark spell as energy-exhausted."""
        self.status = SpellStatus.EXHAUSTED
        self.completed_at = time.time()
        self.error = "Energy exhausted"
        return self

    @property
    def duration(self) -> Optional[float]:
        """How long the spell took to cast."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    @property
    def is_terminal(self) -> bool:
        """Is this spell in a terminal state?"""
        return self.status in (
            SpellStatus.COMPLETED,
            SpellStatus.FIZZLED,
            SpellStatus.EXHAUSTED
        )

    @property
    def effective_energy_cost(self) -> float:
        """Actual energy cost accounting for efficiency."""
        return self.energy_required / max(0.1, self.energy_efficiency)

    def recharge(self, amount: float) -> "Spell":
        """Add energy to this spell."""
        self.energy_available = min(
            self.energy_required * 2,  # Cap at 2x required
            self.energy_available + amount
        )
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Serialize spell to dictionary."""
        return {
            "id": self.id,
            "spell_type": self.spell_type.value,
            "who": self.who,
            "who_name": self.who_name,
            "who_plane": self.who_plane,
            "what": self.what,
            "what_intent": self.what_intent,
            "why": self.why,
            "why_chain_id": self.why_chain_id,
            "when_created": self.when_created,
            "when_scheduled": self.when_scheduled,
            "when_priority": self.when_priority,
            "energy_required": self.energy_required,
            "energy_available": self.energy_available,
            "energy_recovery": self.energy_recovery,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": self.duration,
            "error": self.error,
            "tags": list(self.tags),
            "continues_chain": self.continues_chain,
            "chain_position": self.chain_position,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Spell":
        """Create spell from dictionary."""
        spell = cls(
            id=data.get("id", f"spell_{uuid.uuid4().hex[:12]}"),
            spell_type=SpellType(data.get("spell_type", "sustain")),
            who=data.get("who", ""),
            who_name=data.get("who_name", ""),
            who_plane=data.get("who_plane", ""),
            what=data.get("what", ""),
            what_intent=data.get("what_intent", ""),
            why=data.get("why", ""),
            why_chain_id=data.get("why_chain_id", ""),
            when_created=data.get("when_created", time.time()),
            when_scheduled=data.get("when_scheduled"),
            when_priority=data.get("when_priority", 0.5),
            energy_required=data.get("energy_required", 1.0),
            energy_available=data.get("energy_available", 1.0),
            energy_recovery=data.get("energy_recovery", 0.0),
            status=SpellStatus(data.get("status", "latent")),
            error=data.get("error"),
            tags=set(data.get("tags", [])),
            continues_chain=data.get("continues_chain", True),
            chain_position=data.get("chain_position", 0),
        )
        return spell

    def __repr__(self) -> str:
        return f"Spell({self.id}, {self.what_intent or self.what[:30]}, status={self.status.value})"


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_spell(
    what: str,
    how: Callable[["Spell"], Any],
    spell_type: SpellType = SpellType.TRANSFORM,
    **kwargs
) -> Spell:
    """
    Factory function for creating spells.

    Args:
        what: Human-readable description
        how: The function to execute
        spell_type: Type of spell
        **kwargs: Additional spell parameters

    Returns:
        New Spell instance
    """
    return Spell(
        spell_type=spell_type,
        what=what,
        how=how,
        **kwargs
    )


def create_bootstrap_spell(
    fairy_name: str,
    how: Callable[["Spell"], Any],
    **kwargs
) -> Spell:
    """Create a bootstrap spell for fairy creation."""
    return Spell(
        spell_type=SpellType.BOOTSTRAP,
        what=f"Bootstrap {fairy_name}",
        what_intent="genesis.bootstrap",
        why=f"Create {fairy_name} pattern from void",
        how=how,
        energy_required=1.0,
        energy_recovery=0.5,
        continues_chain=True,
        tags={"bootstrap", "genesis"},
        **kwargs
    )


def create_heartbeat_spell(
    fairy_name: str,
    how: Callable[["Spell"], Any],
    interval: float = 1.0,
    **kwargs
) -> Spell:
    """Create a sustaining heartbeat spell."""
    return Spell(
        spell_type=SpellType.SUSTAIN,
        what=f"Heartbeat of {fairy_name}",
        what_intent="sustain.heartbeat",
        why=f"Maintain {fairy_name} existence",
        how=how,
        when_delay=interval,
        when_scheduled=time.time() + interval,
        energy_required=0.05,
        energy_recovery=0.02,
        continues_chain=True,
        tags={"heartbeat", "sustain"},
        **kwargs
    )


def create_terminal_spell(
    fairy_name: str,
    how: Optional[Callable[["Spell"], Any]] = None,
    **kwargs
) -> Spell:
    """Create a terminal spell for graceful ending."""
    def default_terminal(spell: Spell) -> Dict[str, Any]:
        return {"ended_at": time.time(), "fairy": fairy_name}

    return Spell(
        spell_type=SpellType.TERMINAL,
        what=f"Dissolution of {fairy_name}",
        what_intent="terminus.dissolve",
        why="Graceful end of existence",
        how=how or default_terminal,
        energy_required=0.1,
        energy_recovery=0.0,
        continues_chain=False,
        tags={"terminal", "dissolution"},
        **kwargs
    )
