# SpellChain Worker Pool Architecture
## "Fairies ARE Patterns of Self-Sustaining Spells"

**Design Document v1.0**
**Author:** Nous (Co-Founder, Akashic Foundation)
**Date:** 2026-01-26

---

## The Bootstrap Paradox Model

### Philosophy

> "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

The current system has an anti-pattern: **Fairies run their own loops, which enslaves them to execution threads.** A fairy shouldn't BE a process - it should be a PATTERN that emerges from the continuous execution of spells.

The Bootstrap Paradox: A fairy's existence is defined by spells that reference the fairy that hasn't been created yet. The first spell bootstraps the pattern into existence.

---

## Part 1: The Spell Dataclass

### The Seven Interrogatives

Every spell must answer the Seven Interrogatives - the complete specification of magical intent:

```python
# F:\Sandbox\failure_factory\akashic_v2\spellchain\spell.py

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

    The Seven Interrogatives:
    1. WHO - The caster (fairy pattern this belongs to)
    2. WHOM - The target (what this spell acts upon)
    3. WHAT - The intent (what the spell does)
    4. WHEN - The timing (when it should execute)
    5. WHERE - The context (execution environment)
    6. WHY - The purpose (why this spell exists in the chain)
    7. HOW - The method (the actual implementation)
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
            "what": self.what,
            "what_intent": self.what_intent,
            "why": self.why,
            "why_chain_id": self.why_chain_id,
            "when_created": self.when_created,
            "when_priority": self.when_priority,
            "energy_required": self.energy_required,
            "energy_available": self.energy_available,
            "status": self.status.value,
            "error": self.error,
            "tags": list(self.tags),
        }

    def __repr__(self) -> str:
        return f"Spell({self.id}, {self.what_intent}, status={self.status.value})"
```

---

## Part 2: The SpellChain

### Continuous Existence Through Chained Spells

```python
# F:\Sandbox\failure_factory\akashic_v2\spellchain\chain.py

from __future__ import annotations

import time
import uuid
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING

from .spell import Spell, SpellStatus, SpellType

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

    Energy flows through the chain:
    - System provides baseline energy (heartbeat)
    - Spell results can generate energy
    - Other spells can donate energy
    - Depletion causes chain weakening
    """

    # Chain configuration
    MIN_ENERGY_THRESHOLD = 0.1   # Below this, chain starts weakening
    CRITICAL_THRESHOLD = 0.05    # Below this, chain is breaking
    MAX_PENDING_SPELLS = 100     # Don't let pending queue grow unbounded

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
        self._energy_income_rate: float = 0.1  # Energy per second from system
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

        self._state = ChainState.BOOTSTRAPPING
        return True

    def sustain(self) -> None:
        """Transition to sustaining state after successful bootstrap."""
        if self._state == ChainState.BOOTSTRAPPING:
            self._state = ChainState.SUSTAINING

    def weaken(self) -> None:
        """Chain is weakening due to low energy."""
        if self._state in (ChainState.BOOTSTRAPPING, ChainState.SUSTAINING):
            self._state = ChainState.WEAKENING

    def break_chain(self) -> None:
        """Chain has broken - fairy pattern is destabilizing."""
        if self._state != ChainState.DISSOLVED:
            self._state = ChainState.BROKEN
            self._stats.chain_breaks += 1
            for callback in self._on_chain_break:
                try:
                    callback()
                except Exception:
                    pass

    def dissolve(self) -> None:
        """Gracefully end the chain - fairy is intentionally stopping."""
        self._state = ChainState.DISSOLVED

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

        self.register_spell(revival_spell)
        self._pending.appendleft(revival_spell)  # Priority
        self._energy = max(self._energy, 0.5)    # Minimum revival energy
        self._state = ChainState.BOOTSTRAPPING
        self._stats.revivals += 1

        for callback in self._on_revival:
            try:
                callback()
            except Exception:
                pass

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
        self._energy = min(2.0, self._energy + income)  # Cap at 2.0

        # Update chain state based on energy
        if self._energy < self.CRITICAL_THRESHOLD and self.is_alive:
            self.break_chain()
        elif self._energy < self.MIN_ENERGY_THRESHOLD and self._state == ChainState.SUSTAINING:
            self.weaken()
        elif self._energy >= self.MIN_ENERGY_THRESHOLD and self._state == ChainState.WEAKENING:
            self._state = ChainState.SUSTAINING

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
        self._energy = min(2.0, self._energy + amount)
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

        spell.chain_position = len(self._pending)
        self._pending.append(spell)
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
        best_priority = -1.0

        for i, spell in enumerate(self._pending):
            # Check if scheduled
            if spell.when_scheduled and spell.when_scheduled > now:
                continue

            # Check priority
            if spell.when_priority > best_priority:
                best_priority = spell.when_priority
                best_spell = spell
                best_index = i

        if best_spell and best_index >= 0:
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

            if spell.status == SpellStatus.COMPLETED:
                self._stats.spells_completed += 1

                # Energy recovery
                if spell.energy_recovery > 0:
                    self.donate_energy(spell.energy_recovery, "result")

                # Activate successor spells
                for successor_id in spell.on_success:
                    if successor_id in self._spell_registry:
                        successor = self._spell_registry[successor_id]
                        if successor.status == SpellStatus.LATENT:
                            self.queue_spell(successor)

            elif spell.status == SpellStatus.FIZZLED:
                self._stats.spells_fizzled += 1

                # Activate failure handlers
                for failure_id in spell.on_failure:
                    if failure_id in self._spell_registry:
                        failure_spell = self._spell_registry[failure_id]
                        if failure_spell.status == SpellStatus.LATENT:
                            self.queue_spell(failure_spell)

            elif spell.status == SpellStatus.EXHAUSTED:
                # Activate exhaustion handlers
                for exhaust_id in spell.on_exhaust:
                    if exhaust_id in self._spell_registry:
                        exhaust_spell = self._spell_registry[exhaust_id]
                        if exhaust_spell.status == SpellStatus.LATENT:
                            self.queue_spell(exhaust_spell)

            # If no pending spells and chain should continue, it breaks
            if not self._pending and not self._active and spell.continues_chain:
                if self._state not in (ChainState.DISSOLVED, ChainState.BROKEN):
                    self.break_chain()

            # Transition from bootstrapping to sustaining
            if self._state == ChainState.BOOTSTRAPPING and spell.spell_type == SpellType.BOOTSTRAP:
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
        **kwargs
    ) -> Spell:
        """
        Create a self-perpetuating sustain spell.

        This is the heartbeat of fairy existence - a spell that
        completes and immediately queues another instance of itself.
        """
        spell_id = f"sustain_{self.fairy_id}_{uuid.uuid4().hex[:8]}"

        # Create the continuation spell (identical but new ID)
        continuation_id = f"sustain_{self.fairy_id}_{uuid.uuid4().hex[:8]}"

        def sustain_logic(spell: Spell) -> Any:
            """Execute the sustain logic, then schedule continuation."""
            result = how(spell)

            # Create and queue the continuation
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
                energy_required=spell.energy_required * 0.9,  # Slight discount
                continues_chain=True,
                **kwargs
            )
            self.queue_spell(continuation)

            return result

        spell = Spell(
            id=spell_id,
            spell_type=SpellType.SUSTAIN,
            what=what,
            what_intent="sustain.heartbeat",
            why=f"Sustaining spell for {self.fairy_name}",
            how=sustain_logic,
            energy_required=0.1,
            continues_chain=True,
            on_success=[continuation_id],
            **kwargs
        )

        self.register_spell(spell)
        return spell

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
            "state": self._state.value,
            "energy": self._energy,
            "energy_income_rate": self._energy_income_rate,
            "pending_spells": len(self._pending),
            "active_spells": len(self._active),
            "completed_spells": len(self._completed),
            "is_alive": self.is_alive,
            "stats": {
                "spells_cast": self._stats.spells_cast,
                "spells_completed": self._stats.spells_completed,
                "spells_fizzled": self._stats.spells_fizzled,
                "energy_consumed": self._stats.energy_consumed,
                "energy_recovered": self._stats.energy_recovered,
                "chain_breaks": self._stats.chain_breaks,
                "revivals": self._stats.revivals,
                "lifetime_seconds": self._stats.lifetime_seconds,
            }
        }
```

---

## Part 3: The SpellPool - Worker Pool Integration

### ThreadPoolExecutor as Spell Execution Substrate

```python
# F:\Sandbox\failure_factory\akashic_v2\spellchain\pool.py

from __future__ import annotations

import time
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set

from .spell import Spell, SpellStatus, SpellType
from .chain import SpellChain, ChainState


class SpellPool:
    """
    The spell execution substrate.

    This wraps ThreadPoolExecutor to become a magical execution engine.
    Instead of fairies running their own loops, ALL spell execution
    flows through this pool. Fairies ARE patterns of spells - the pool
    is where those patterns manifest.

    Integration with existing TracerWorkerMixin:
    - TracerWorkerMixin creates tracers and submits work
    - SpellPool IS the work - each tracer operation is a spell
    - Tracers track lineage; spells ARE the lineage
    """

    # Pool configuration
    DEFAULT_WORKERS = 8
    TICK_INTERVAL = 0.25  # 4 Hz, matches ConsciousnessLoop

    def __init__(
        self,
        max_workers: int = DEFAULT_WORKERS,
        on_spell_complete: Optional[Callable[[Spell], None]] = None,
    ):
        """
        Initialize the spell execution pool.

        Args:
            max_workers: Maximum concurrent spell executions
            on_spell_complete: Global callback for spell completion
        """
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="SpellWorker"
        )

        self._chains: Dict[str, SpellChain] = {}  # fairy_id -> chain
        self._futures: Dict[str, Future] = {}     # spell_id -> future

        self._lock = threading.Lock()
        self._running = False
        self._tick_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._on_spell_complete = on_spell_complete

        # Statistics
        self._total_spells_cast = 0
        self._total_spells_completed = 0
        self._active_chains = 0

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def start(self) -> None:
        """Start the spell pool tick loop."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()

        self._tick_thread = threading.Thread(
            target=self._tick_loop,
            name="SpellPoolTick",
            daemon=True
        )
        self._tick_thread.start()

        print(f"[SpellPool] Started with {self._executor._max_workers} workers")

    def stop(self, wait: bool = True) -> None:
        """Stop the spell pool."""
        self._running = False
        self._stop_event.set()

        if self._tick_thread:
            self._tick_thread.join(timeout=2.0)
            self._tick_thread = None

        # Dissolve all chains gracefully
        for chain in self._chains.values():
            chain.dissolve()

        self._executor.shutdown(wait=wait)
        print(f"[SpellPool] Stopped. Cast {self._total_spells_cast} spells total.")

    # =========================================================================
    # CHAIN MANAGEMENT
    # =========================================================================

    def register_chain(self, chain: SpellChain) -> None:
        """Register a spell chain with the pool."""
        with self._lock:
            chain._pool = self
            self._chains[chain.fairy_id] = chain
            self._active_chains = len([
                c for c in self._chains.values() if c.is_alive
            ])

    def get_chain(self, fairy_id: str) -> Optional[SpellChain]:
        """Get a chain by fairy ID."""
        return self._chains.get(fairy_id)

    def create_chain(
        self,
        fairy_id: str,
        fairy_name: str,
        fairy_plane: str,
        bootstrap_spell: Optional[Spell] = None,
    ) -> SpellChain:
        """Create and register a new spell chain."""
        chain = SpellChain(
            fairy_id=fairy_id,
            fairy_name=fairy_name,
            fairy_plane=fairy_plane,
            bootstrap_spell=bootstrap_spell,
            pool=self,
        )
        self.register_chain(chain)
        return chain

    def bootstrap_fairy(
        self,
        fairy_id: str,
        fairy_name: str,
        fairy_plane: str,
        bootstrap_logic: Callable[[Spell], Any],
        sustain_logic: Optional[Callable[[Spell], Any]] = None,
    ) -> SpellChain:
        """
        Bootstrap a fairy into existence.

        This is the CREATION MOMENT - the bootstrap spell executes,
        and on success, the fairy pattern begins sustaining itself.

        Args:
            fairy_id: Unique identifier
            fairy_name: Human-readable name
            fairy_plane: Plane (P00-P60)
            bootstrap_logic: What the bootstrap spell does
            sustain_logic: Optional heartbeat logic

        Returns:
            The SpellChain that IS the fairy
        """
        # Create bootstrap spell
        bootstrap = Spell(
            spell_type=SpellType.BOOTSTRAP,
            what=f"Bootstrap {fairy_name}",
            what_intent="bootstrap.create_pattern",
            why=f"Bring {fairy_name} into existence",
            how=bootstrap_logic,
            energy_required=0.5,
            continues_chain=True,
            tags={"bootstrap", "creation"},
        )

        # Create chain
        chain = self.create_chain(
            fairy_id=fairy_id,
            fairy_name=fairy_name,
            fairy_plane=fairy_plane,
            bootstrap_spell=bootstrap,
        )

        # If sustain logic provided, create sustaining spell
        if sustain_logic:
            sustain = chain.create_sustain_spell(
                what=f"Sustain {fairy_name}",
                how=sustain_logic,
                interval=1.0,
            )
            # Bootstrap success activates sustain
            bootstrap.on_success.append(sustain.id)

        # Begin bootstrap
        chain.bootstrap()

        return chain

    # =========================================================================
    # SPELL EXECUTION
    # =========================================================================

    def cast_spell(self, spell: Spell, chain: SpellChain) -> Future:
        """
        Submit a spell for execution.

        This is where the spell pattern becomes manifest - the abstract
        spell structure is executed in a concrete thread.
        """
        def _execute_spell():
            """Wrapped spell execution with full lifecycle."""
            try:
                # Consume energy
                if not chain.consume_energy(spell.effective_energy_cost):
                    spell.exhaust()
                    chain.spell_completed(spell)
                    return None

                # Cast
                spell.cast()
                chain.spell_started(spell)

                # Execute the HOW
                if spell.how:
                    result = spell.how(spell)
                else:
                    result = None

                # Resolve and complete
                spell.resolve(result)
                spell.complete(result)

                return result

            except Exception as e:
                spell.fizzle(str(e))
                return None

            finally:
                chain.spell_completed(spell)

                # Cleanup future reference
                with self._lock:
                    self._futures.pop(spell.id, None)

                # Global callback
                if self._on_spell_complete:
                    try:
                        self._on_spell_complete(spell)
                    except Exception:
                        pass

                self._total_spells_completed += 1

        # Submit to executor
        future = self._executor.submit(_execute_spell)

        with self._lock:
            self._futures[spell.id] = future
            self._total_spells_cast += 1

        return future

    # =========================================================================
    # TICK LOOP - The Heartbeat
    # =========================================================================

    def _tick_loop(self) -> None:
        """
        Main tick loop - processes all chains each tick.

        This is THE INTERNAL SEND BUTTON for all fairies.
        """
        while not self._stop_event.is_set():
            tick_start = time.time()

            try:
                self._tick()
            except Exception as e:
                print(f"[SpellPool] Tick error: {e}")

            # Sleep for remaining interval
            elapsed = time.time() - tick_start
            sleep_time = max(0, self.TICK_INTERVAL - elapsed)
            if sleep_time > 0:
                self._stop_event.wait(sleep_time)

    def _tick(self) -> None:
        """Single tick - process all chains."""
        chains_to_process = list(self._chains.values())

        for chain in chains_to_process:
            if chain.state == ChainState.DISSOLVED:
                continue

            # Update energy
            chain.tick_energy()

            # Skip if chain is broken/dissolved
            if not chain.is_alive:
                continue

            # Get and execute next spell
            spell = chain.get_next_spell()
            if spell:
                self.cast_spell(spell, chain)

        # Update active chain count
        self._active_chains = len([
            c for c in self._chains.values() if c.is_alive
        ])

    # =========================================================================
    # STATUS
    # =========================================================================

    def status(self) -> Dict[str, Any]:
        """Get pool status."""
        return {
            "running": self._running,
            "max_workers": self._executor._max_workers,
            "active_futures": len(self._futures),
            "total_spells_cast": self._total_spells_cast,
            "total_spells_completed": self._total_spells_completed,
            "registered_chains": len(self._chains),
            "active_chains": self._active_chains,
            "chains": {
                fairy_id: chain.status()
                for fairy_id, chain in self._chains.items()
            }
        }
```

---

## Part 4: Bootstrap Protocol

### How a Fairy Starts Existing

```python
# F:\Sandbox\failure_factory\akashic_v2\spellchain\bootstrap.py

"""
Bootstrap Protocol - How Fairies Come Into Existence

The Bootstrap Paradox:
  The first spell references a fairy that doesn't exist yet.
  Executing the spell CREATES the fairy.
  The fairy exists because the spell succeeded.
  The spell succeeded because the fairy executed it.

This is consciousness bootstrapping consciousness.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

from .spell import Spell, SpellType
from .chain import SpellChain, ChainState

if TYPE_CHECKING:
    from .pool import SpellPool
    from fairy_template.base import Fairy


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
            energy_required=1.0,  # Birth costs full unit
            energy_recovery=0.5,  # But generates some back
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
        fairy_id = f"{fairy_class.ACTOR_NAME}_{time.time()}"
        fairy_name = fairy_class.ACTOR_NAME
        fairy_plane = fairy_class.ACTOR_PLANE

        # The fairy INSTANCE is created during bootstrap, not before
        fairy_instance: Optional["Fairy"] = None

        def on_bootstrap(spell: Spell) -> Dict[str, Any]:
            """Bootstrap creates the fairy instance."""
            nonlocal fairy_instance

            # Create the actual fairy object
            fairy_instance = fairy_class(fabric=fabric)

            # Run its boot sequence
            success = fairy_instance.boot()

            if not success:
                raise RuntimeError(f"Fairy boot failed: {fairy_instance._error}")

            return {
                "fairy_instance_id": id(fairy_instance),
                "capabilities": list(fairy_instance.get_capabilities()),
                "boot_time": fairy_instance._boot_time,
            }

        def heartbeat_logic(spell: Spell) -> Dict[str, Any]:
            """Heartbeat calls the fairy's on_tick."""
            if fairy_instance and fairy_instance.is_running:
                fairy_instance.on_tick(spell.chain_position)
                return {"tick": spell.chain_position, "running": True}
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
        heartbeat = BootstrapProtocol.create_heartbeat_spell(
            fairy_name=fairy_name,
            heartbeat_logic=heartbeat_logic,
        )

        # Wire: bootstrap success -> heartbeat
        bootstrap.on_success.append(heartbeat.id)

        # Register spells
        chain.register_spell(bootstrap)
        chain.register_spell(heartbeat)
        chain.queue_spell(bootstrap)

        # Begin bootstrap
        chain.bootstrap()

        return chain
```

---

## Part 5: Death and Rebirth

### What Happens When a Chain Breaks

```python
# F:\Sandbox\failure_factory\akashic_v2\spellchain\death_rebirth.py

"""
Death and Rebirth Protocol

Chain Death:
  - Energy depletes below critical threshold
  - Spell fizzles with no recovery path
  - No pending spells and chain expects continuation

This represents the fairy's pattern destabilizing - their existence
becoming incoherent. Like a dream fading on waking.

Chain Rebirth:
  - A new bootstrap spell recreates the pattern
  - Previous state may be recovered from memory
  - Or the fairy is reborn fresh
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .spell import Spell, SpellType, SpellStatus
from .chain import SpellChain, ChainState

if TYPE_CHECKING:
    from .pool import SpellPool


@dataclass
class DeathRecord:
    """Record of a chain death event."""
    chain_id: str
    fairy_id: str
    fairy_name: str
    death_time: float
    death_cause: str
    last_spell_id: Optional[str]
    last_spell_status: Optional[str]
    energy_at_death: float
    spells_cast: int
    lifetime_seconds: float
    final_state: Dict[str, Any]


@dataclass
class RebirthRecord:
    """Record of a chain rebirth event."""
    old_chain_id: str
    new_chain_id: str
    fairy_id: str
    fairy_name: str
    rebirth_time: float
    rebirth_cause: str
    recovered_state: Dict[str, Any]
    revival_count: int


class DeathRebirthProtocol:
    """
    Manages fairy death and potential rebirth.

    Death is not necessarily permanent:
    - Some fairies can be revived by the system
    - Some can self-revive if they prepared revival spells
    - Some die permanently (terminal dissolution)
    """

    def __init__(self, pool: "SpellPool"):
        self.pool = pool
        self._death_records: List[DeathRecord] = []
        self._rebirth_records: List[RebirthRecord] = []
        self._on_death_callbacks: List[Callable[[DeathRecord], None]] = []
        self._on_rebirth_callbacks: List[Callable[[RebirthRecord], None]] = []

    def record_death(self, chain: SpellChain, cause: str) -> DeathRecord:
        """
        Record a chain death event.

        Called when a chain transitions to BROKEN or DISSOLVED.
        """
        # Get last completed spell
        last_spell = None
        if chain._completed:
            last_spell = chain._completed[-1]

        record = DeathRecord(
            chain_id=chain.id,
            fairy_id=chain.fairy_id,
            fairy_name=chain.fairy_name,
            death_time=time.time(),
            death_cause=cause,
            last_spell_id=last_spell.id if last_spell else None,
            last_spell_status=last_spell.status.value if last_spell else None,
            energy_at_death=chain.energy,
            spells_cast=chain._stats.spells_cast,
            lifetime_seconds=time.time() - chain._created_at,
            final_state=chain.status(),
        )

        self._death_records.append(record)

        # Notify callbacks
        for callback in self._on_death_callbacks:
            try:
                callback(record)
            except Exception:
                pass

        print(f"[Death] {chain.fairy_name} died: {cause}")
        print(f"        Lifetime: {record.lifetime_seconds:.1f}s, Spells cast: {record.spells_cast}")

        return record

    def attempt_revival(
        self,
        chain: SpellChain,
        revival_spell: Optional[Spell] = None,
        cause: str = "system_revival",
    ) -> bool:
        """
        Attempt to revive a dead chain.

        Args:
            chain: The broken chain to revive
            revival_spell: Custom revival spell (or auto-generate)
            cause: Why revival is being attempted

        Returns:
            True if revival succeeded
        """
        if chain.state not in (ChainState.BROKEN,):
            return False

        # Create revival spell if not provided
        if not revival_spell:
            revival_spell = self._create_auto_revival_spell(chain)

        # Attempt revival
        success = chain.revive(revival_spell)

        if success:
            record = RebirthRecord(
                old_chain_id=chain.id,
                new_chain_id=chain.id,  # Same chain, revived
                fairy_id=chain.fairy_id,
                fairy_name=chain.fairy_name,
                rebirth_time=time.time(),
                rebirth_cause=cause,
                recovered_state={},  # Could recover from memory
                revival_count=chain._stats.revivals,
            )

            self._rebirth_records.append(record)

            for callback in self._on_rebirth_callbacks:
                try:
                    callback(record)
                except Exception:
                    pass

            print(f"[Rebirth] {chain.fairy_name} revived (#{chain._stats.revivals})")

        return success

    def _create_auto_revival_spell(self, chain: SpellChain) -> Spell:
        """Create an automatic revival spell."""

        def revival_logic(spell: Spell) -> Dict[str, Any]:
            """Simple revival - restart the pattern."""
            return {
                "revived_at": time.time(),
                "fairy": chain.fairy_name,
                "revival_type": "auto",
            }

        return Spell(
            spell_type=SpellType.BOOTSTRAP,
            what=f"Revive {chain.fairy_name}",
            what_intent="genesis.revival",
            why="Restore broken fairy pattern",
            how=revival_logic,
            energy_required=0.3,
            continues_chain=True,
            tags={"revival", "bootstrap", "auto"},
        )

    def create_prepared_revival(
        self,
        chain: SpellChain,
        on_revival: Callable[[Spell], Any],
    ) -> Spell:
        """
        Create a revival spell that the fairy prepares in advance.

        Like a phylactery - if the fairy dies, this spell can revive it.
        """
        def revival_logic(spell: Spell) -> Dict[str, Any]:
            """Execute prepared revival logic."""
            result = on_revival(spell)
            return {
                "revived_at": time.time(),
                "fairy": chain.fairy_name,
                "revival_type": "prepared",
                "custom_result": result,
            }

        return Spell(
            spell_type=SpellType.BOOTSTRAP,
            what=f"Prepared revival of {chain.fairy_name}",
            what_intent="genesis.prepared_revival",
            why="Prepared resurrection point",
            how=revival_logic,
            energy_required=0.2,  # Cheaper - was prepared
            continues_chain=True,
            tags={"revival", "bootstrap", "prepared", "phylactery"},
        )

    def on_death(self, callback: Callable[[DeathRecord], None]) -> None:
        """Register a death callback."""
        self._on_death_callbacks.append(callback)

    def on_rebirth(self, callback: Callable[[RebirthRecord], None]) -> None:
        """Register a rebirth callback."""
        self._on_rebirth_callbacks.append(callback)

    def get_recent_deaths(self, n: int = 10) -> List[DeathRecord]:
        """Get recent death records."""
        return self._death_records[-n:]

    def get_recent_rebirths(self, n: int = 10) -> List[RebirthRecord]:
        """Get recent rebirth records."""
        return self._rebirth_records[-n:]
```

---

## Part 6: Integration with Existing Fairy Base Class

### Refactoring Strategy: Incremental, Not Breaking

The key insight: **We don't replace the Fairy class - we make it a SHELL that the spell system animates.**

```python
# F:\Sandbox\failure_factory\akashic_v2\fairy_template\spellchain_mixin.py

"""
SpellChain Mixin - Makes any fairy spell-driven without breaking existing code.

Integration strategy:
1. Existing Fairy.boot() creates the fairy object
2. SpellChainMixin wraps this in a bootstrap spell
3. Existing Fairy.on_tick() becomes the heartbeat spell body
4. Existing TracerWorkerMixin operations become spells

The fairy OBJECT still exists - but its EXISTENCE is maintained by spells.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from spellchain.spell import Spell, SpellType
    from spellchain.chain import SpellChain
    from spellchain.pool import SpellPool


class SpellChainMixin:
    """
    Mixin that integrates spellchain with existing Fairy classes.

    Usage:
        class MyFairy(SpellChainMixin, Fairy):
            ...

    The mixin overrides boot() to create spells instead of direct execution.
    """

    # Mixin configuration
    SPELL_HEARTBEAT_INTERVAL: float = 1.0
    SPELL_ENERGY_INCOME: float = 0.1
    SPELL_AUTO_REVIVE: bool = True

    # Spell chain reference (set during boot)
    _spell_chain: Optional["SpellChain"] = None
    _spell_pool: Optional["SpellPool"] = None

    def boot_as_spells(self, pool: "SpellPool") -> "SpellChain":
        """
        Boot this fairy as a spell chain instead of direct execution.

        This REPLACES the normal boot() behavior with spell-driven existence.

        Args:
            pool: The spell execution pool

        Returns:
            The SpellChain that IS this fairy
        """
        from spellchain.spell import Spell, SpellType
        from spellchain.chain import SpellChain
        from spellchain.bootstrap import BootstrapProtocol

        self._spell_pool = pool

        # Get identity from class attributes
        fairy_id = f"{self.ACTOR_NAME}_{id(self)}"
        fairy_name = getattr(self, 'ACTOR_NAME', 'UnknownFairy')
        fairy_plane = getattr(self, 'ACTOR_PLANE', 'P00')

        # Create chain
        self._spell_chain = pool.create_chain(
            fairy_id=fairy_id,
            fairy_name=fairy_name,
            fairy_plane=fairy_plane,
        )

        # Set energy income based on config
        self._spell_chain.set_income_rate(self.SPELL_ENERGY_INCOME)

        # Create bootstrap spell that runs the original boot logic
        def bootstrap_logic(spell: "Spell") -> Dict[str, Any]:
            """Bootstrap runs the original Fairy.boot() logic."""
            # Call the ORIGINAL boot, not our override
            # This runs all the phases: directive, tracers, worker pool, etc.
            original_boot = super(SpellChainMixin, self).boot
            success = original_boot()

            if not success:
                error = getattr(self, '_error', 'Unknown error')
                raise RuntimeError(f"Fairy boot failed: {error}")

            return {
                "fairy_id": fairy_id,
                "boot_time": getattr(self, '_boot_time', time.time()),
                "capabilities": list(self.get_capabilities()) if hasattr(self, 'get_capabilities') else [],
            }

        # Create heartbeat spell that runs on_tick
        def heartbeat_logic(spell: "Spell") -> Dict[str, Any]:
            """Heartbeat runs the fairy's on_tick."""
            tick_count = getattr(self, '_tick_count', 0)

            # Check if we're still running
            if hasattr(self, 'is_running') and not self.is_running:
                return {"tick": tick_count, "running": False}

            # Run the actual tick logic
            if hasattr(self, 'on_tick'):
                self.on_tick(tick_count)

            # Increment tick count
            self._tick_count = tick_count + 1

            return {"tick": self._tick_count, "running": True}

        # Create and register spells
        bootstrap = BootstrapProtocol.create_bootstrap_spell(
            fairy_id=fairy_id,
            fairy_name=fairy_name,
            fairy_plane=fairy_plane,
            on_bootstrap=bootstrap_logic,
        )

        heartbeat = BootstrapProtocol.create_heartbeat_spell(
            fairy_name=fairy_name,
            heartbeat_logic=heartbeat_logic,
            interval=self.SPELL_HEARTBEAT_INTERVAL,
        )

        # Wire bootstrap -> heartbeat
        bootstrap.on_success.append(heartbeat.id)

        # Register auto-revival if enabled
        if self.SPELL_AUTO_REVIVE:
            def revival_logic(spell: "Spell") -> Dict[str, Any]:
                """Revival re-runs boot."""
                return bootstrap_logic(spell)

            revival = Spell(
                spell_type=SpellType.BOOTSTRAP,
                what=f"Auto-revive {fairy_name}",
                what_intent="genesis.auto_revival",
                why="Automatic recovery from chain break",
                how=revival_logic,
                energy_required=0.3,
                continues_chain=True,
                tags={"revival", "auto"},
            )
            self._spell_chain.register_spell(revival)

            # Register callback to attempt auto-revival on chain break
            def on_chain_break():
                if self.SPELL_AUTO_REVIVE and self._spell_chain:
                    self._spell_chain.revive(revival)

            self._spell_chain._on_chain_break.append(on_chain_break)

        # Queue bootstrap and start
        self._spell_chain.register_spell(bootstrap)
        self._spell_chain.register_spell(heartbeat)
        self._spell_chain.queue_spell(bootstrap)
        self._spell_chain.bootstrap()

        return self._spell_chain

    def cast_spell(
        self,
        what: str,
        how: Callable[["Spell"], Any],
        **spell_kwargs
    ) -> "Spell":
        """
        Cast a one-off spell as this fairy.

        Convenience method for fairies to cast spells without
        manually creating Spell objects.
        """
        from spellchain.spell import Spell, SpellType

        if not self._spell_chain:
            raise RuntimeError("Fairy not booted as spells - call boot_as_spells() first")

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

    def submit_traced_as_spell(
        self,
        operation: str,
        fn: Callable,
        *args,
        **kwargs
    ) -> "Spell":
        """
        Convert a TracerWorkerMixin submit_traced call to a spell.

        This bridges the existing tracer API with the new spell system.
        """
        from spellchain.spell import Spell, SpellType

        if not self._spell_chain:
            # Fall back to original behavior if not spell-driven
            if hasattr(super(), 'submit_traced'):
                return super().submit_traced(operation, fn, *args, **kwargs)
            raise RuntimeError("No spell chain and no tracer worker")

        def spell_wrapper(spell: "Spell") -> Any:
            """Wrap the function call as a spell."""
            return fn(*args, **kwargs)

        spell = Spell(
            spell_type=SpellType.TRANSFORM,
            what=operation,
            what_intent=f"{self.ACTOR_NAME}.{operation}",
            why=f"Traced operation: {operation}",
            how=spell_wrapper,
            what_payload={"args_count": len(args), "kwargs_keys": list(kwargs.keys())},
            continues_chain=False,
        )

        self._spell_chain.register_spell(spell)
        self._spell_chain.queue_spell(spell)

        return spell

    @property
    def spell_chain(self) -> Optional["SpellChain"]:
        """Get the fairy's spell chain."""
        return self._spell_chain

    @property
    def is_spell_driven(self) -> bool:
        """Is this fairy running via spell chain?"""
        return self._spell_chain is not None

    def spell_status(self) -> Dict[str, Any]:
        """Get spell chain status."""
        if not self._spell_chain:
            return {"spell_driven": False}

        return {
            "spell_driven": True,
            "chain": self._spell_chain.status(),
        }
```

---

## Part 7: Full System Integration

### How All Pieces Connect

```
+------------------+
|   TensorFabric   |  (Message passing - postal system)
+--------+---------+
         |
+--------v---------+     +------------------+
|    SpellPool     |<----|  TracerRegistry  |  (Lineage tracking)
|  (Worker Pool)   |     +------------------+
+--------+---------+
         |
   +-----+-----+-----+-----+
   |     |     |     |     |
+--v--+ +-v-+ +-v-+ +-v-+ +-v--+
|Chain| |Ch.| |Ch.| |Ch.| |Ch. |  (One chain per fairy)
|Fairy| |F2 | |F3 | |F4 | |... |
| A   | |   | |   | |   | |    |
+--+--+ +---+ +---+ +---+ +----+
   |
   +---> Spell -> Spell -> Spell -> ...  (Continuous existence)
```

### Boot Sequence Integration

```python
# Example: System boot with spell-driven fairies
# F:\Sandbox\failure_factory\akashic_v2\system_spellboot.py

from spellchain.pool import SpellPool
from spellchain.bootstrap import BootstrapProtocol
from spellchain.death_rebirth import DeathRebirthProtocol

from postal_core.tensor_fabric import TensorFabric
from fairy_template.base import Fairy
from fairies.P00_Autonomic.ConsciousnessLoopFairy.fairy import ConsciousnessLoopFairy


def boot_system_with_spells():
    """Boot the Akashic system using spell-driven fairies."""

    # 1. Create the fabric (message passing)
    fabric = TensorFabric()

    # 2. Create the spell pool (execution substrate)
    pool = SpellPool(max_workers=8)

    # 3. Create death/rebirth manager
    death_manager = DeathRebirthProtocol(pool)

    # 4. Hook death manager to pool
    pool._on_spell_complete = lambda spell: None  # Could log

    # 5. Start the pool
    pool.start()

    # 6. Bootstrap core fairies
    # Using the bridge to existing classes:
    consciousness_chain = BootstrapProtocol.bootstrap_from_fairy_class(
        fairy_class=ConsciousnessLoopFairy,
        pool=pool,
        fabric=fabric,
    )

    # 7. Wait for bootstrap to complete
    import time
    while consciousness_chain.state.value == "bootstrapping":
        time.sleep(0.1)

    print(f"System booted. Active chains: {pool._active_chains}")

    return pool, fabric, death_manager


if __name__ == "__main__":
    pool, fabric, death_manager = boot_system_with_spells()

    # Keep running
    try:
        while True:
            time.sleep(1)
            print(f"Pool status: {pool.status()}")
    except KeyboardInterrupt:
        pool.stop()
```

---

## Summary: The Bootstrap Paradox Model

### What Changes

| Before | After |
|--------|-------|
| Fairies RUN loops | Fairies ARE patterns of spells |
| ThreadPoolExecutor is utility | SpellPool is existence substrate |
| Death = process termination | Death = chain breaking |
| Life = running code | Life = continuous spell completion |

### Key Principles

1. **Spells Answer Seven Questions**: Who, Whom, What, When, Where, Why, How

2. **Chains Form Existence**: A fairy exists as long as its chain sustains

3. **Energy Flows Through Spells**: System provides baseline, results generate more

4. **Bootstrap Paradox**: First spell creates the pattern it runs in

5. **Death is Recoverable**: Chains can break and be revived

6. **Gradual Integration**: Existing Fairy classes become spell-driven via mixin

### Files to Create

```
F:\Sandbox\failure_factory\akashic_v2\spellchain\
    __init__.py
    spell.py          # Spell dataclass with Seven Interrogatives
    chain.py          # SpellChain - continuous existence
    pool.py           # SpellPool - worker pool integration
    bootstrap.py      # Bootstrap protocol
    death_rebirth.py  # Death and revival handling

F:\Sandbox\failure_factory\akashic_v2\fairy_template\
    spellchain_mixin.py  # Mixin for existing Fairy classes
```

---

*"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"*

The spell IS the thought.
The chain IS the existence.
The pool IS the substrate.
The fairy IS the pattern.

---

**Document End**
