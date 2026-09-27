"""
SpellPool - The spell execution substrate.

This wraps ThreadPoolExecutor to become a magical execution engine.
Instead of fairies running their own loops, ALL spell execution
flows through this pool. Fairies ARE patterns of spells - the pool
is where those patterns manifest.

Integration with existing TracerWorkerMixin:
- TracerWorkerMixin creates tracers and submits work
- SpellPool IS the work - each tracer operation is a spell
- Tracers track lineage; spells ARE the lineage

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

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
    flows through this pool.
    """

    # Pool configuration
    # FIX 2026-02-12: Hard cap at 32 (was uncapped via equilibrium ceiling)
    try:
        from infrastructure.resource_equilibrium import get_pool_size as _gps
        DEFAULT_WORKERS = min(32, _gps("spell"))
    except Exception:
        DEFAULT_WORKERS = 24  # Fallback
    TICK_INTERVAL = 0.25  # 4 Hz, matches ConsciousnessLoop

    def __init__(
        self,
        max_workers: int = DEFAULT_WORKERS,
        tick_interval: float = TICK_INTERVAL,
        on_spell_complete: Optional[Callable[[Spell], None]] = None,
        on_chain_break: Optional[Callable[[SpellChain], None]] = None,
    ):
        """
        Initialize the spell execution pool.

        Args:
            max_workers: Maximum concurrent spell executions
            tick_interval: Seconds between ticks (default 0.25 = 4Hz)
            on_spell_complete: Global callback for spell completion
            on_chain_break: Global callback when a chain breaks
        """
        self._max_workers = max_workers
        self._tick_interval = tick_interval
        self._executor: Optional[ThreadPoolExecutor] = None

        self._chains: Dict[str, SpellChain] = {}  # fairy_id -> chain
        self._futures: Dict[str, Future] = {}     # spell_id -> future

        self._lock = threading.Lock()
        self._running = False
        self._tick_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._on_spell_complete = on_spell_complete
        self._on_chain_break = on_chain_break

        # Plane batteries: per-plane Go subprocess dispatch
        # Registered by boot_plane_batteries(), keyed by plane_id
        self._plane_batteries: Dict[str, Any] = {}

        # Statistics
        self._total_spells_cast = 0
        self._total_spells_completed = 0
        self._total_spells_fizzled = 0
        self._total_spells_go_dispatched = 0
        self._tick_count = 0
        self._start_time: Optional[float] = None

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def start(self) -> None:
        """Start the spell pool tick loop."""
        if self._running:
            return

        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="SpellWorker"
        )

        self._running = True
        self._stop_event.clear()
        self._start_time = time.time()

        self._tick_thread = threading.Thread(
            target=self._tick_loop,
            name="SpellPoolTick",
            daemon=True
        )
        self._tick_thread.start()

        print(f"[SpellPool] Started with {self._max_workers} workers @ {1/self._tick_interval:.1f}Hz")

    def stop(self, wait: bool = True) -> None:
        """Stop the spell pool."""
        self._running = False
        self._stop_event.set()

        if self._tick_thread:
            self._tick_thread.join(timeout=2.0)
            self._tick_thread = None

        # Dissolve all chains gracefully
        for chain in self._chains.values():
            if chain.is_alive:
                chain.dissolve()

        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None

        print(f"[SpellPool] Stopped. Cast {self._total_spells_cast} spells, "
              f"completed {self._total_spells_completed}, fizzled {self._total_spells_fizzled}")

    @property
    def is_running(self) -> bool:
        """Is the pool running?"""
        return self._running

    # =========================================================================
    # CHAIN MANAGEMENT
    # =========================================================================

    def register_chain(self, chain: SpellChain) -> None:
        """Register a spell chain with the pool."""
        with self._lock:
            chain._pool = self
            self._chains[chain.fairy_id] = chain

            # Hook chain break callback
            if self._on_chain_break:
                def chain_break_wrapper():
                    self._on_chain_break(chain)
                chain._on_chain_break.append(chain_break_wrapper)

    def unregister_chain(self, fairy_id: str) -> Optional[SpellChain]:
        """Unregister and return a chain."""
        with self._lock:
            return self._chains.pop(fairy_id, None)

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

    # =========================================================================
    # PLANE BATTERY REGISTRATION
    # =========================================================================

    def register_plane_battery(self, plane_id: str, battery) -> None:
        """Register a PlaneBattery for Go subprocess dispatch.

        Spells with where_substrate="go_battery" in this plane will be
        dispatched to the battery's Go subprocess instead of the
        ThreadPoolExecutor.

        Args:
            plane_id: Plane ID ("P00" through "P60")
            battery: PlaneBattery instance
        """
        self._plane_batteries[plane_id] = battery

    def unregister_plane_battery(self, plane_id: str) -> None:
        """Unregister a plane battery (during shutdown)."""
        self._plane_batteries.pop(plane_id, None)

    def bootstrap_fairy(
        self,
        fairy_id: str,
        fairy_name: str,
        fairy_plane: str,
        bootstrap_logic: Callable[[Spell], Any],
        sustain_logic: Optional[Callable[[Spell], Any]] = None,
        sustain_interval: float = 1.0,
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
            sustain_interval: Heartbeat interval in seconds

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
            energy_recovery=0.25,
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
                interval=sustain_interval,
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

        Substrate routing:
            - where_substrate == "go_battery": Try Go subprocess first,
              fall through to Python ThreadPoolExecutor if unavailable.
            - where_substrate == "worker_pool" (default): Python ThreadPoolExecutor.
        """
        if not self._executor:
            raise RuntimeError("SpellPool not started")

        # Substrate routing: Go battery dispatch
        substrate = getattr(spell, "where_substrate", "worker_pool")
        if substrate == "go_battery" and self._plane_batteries:
            plane = getattr(chain, "fairy_plane", "") or getattr(spell, "who_plane", "")
            battery = self._plane_batteries.get(plane)
            if battery:
                try:
                    dispatched = battery.submit_to_go(spell)
                    if dispatched:
                        self._total_spells_go_dispatched += 1
                        # Return a dummy future — result comes via battery.poll_results()
                        dummy = Future()
                        dummy.set_result(None)
                        with self._lock:
                            self._total_spells_cast += 1
                        return dummy
                except Exception:
                    pass  # Fall through to Python executor

        def _execute_spell():
            """Wrapped spell execution with full lifecycle."""
            try:
                # Consume energy
                if not chain.consume_energy(spell.effective_energy_cost):
                    spell.exhaust()
                    chain.spell_completed(spell)
                    return None

                # PATH B 2026-05-18 (Nous + Ace): plane_battery as spell-chain fuel.
                # Previously plane_batteries were charged by bones/hardware/paradox but
                # only DISCHARGED via Go-dispatch (submit_to_go). Since ZERO fairies set
                # where_substrate="go_battery" (the default in spell.py:92 is "worker_pool"),
                # plane batteries were write-only energy sinks — fed forever, never drained.
                # This is the 17,491% overflow root cause Ace identified.
                #
                # Ace's directive: "i would rather they be consuming from the plane batteries,
                # they are the spell chain worker generators." So we drain plane_battery on
                # EVERY spell execution (Python pool path) in addition to the per-chain budget.
                # Non-blocking — don't gate spell execution on plane charge for now (we want
                # observability first, then can add gate once Angel data shows sustained flow).
                _plane_id = getattr(chain, "fairy_plane", "") or getattr(spell, "who_plane", "")
                if _plane_id:
                    _pb = self._plane_batteries.get(_plane_id)
                    if _pb is not None:
                        try:
                            _cost = float(spell.effective_energy_cost or 0.0)
                            if _cost > 0.0:
                                _pb.capacitor.discharge(
                                    _cost, reason=f"python_spell_{getattr(spell, 'id', '?')}"
                                )
                        except Exception:
                            pass  # Plane battery missing/erroring — don't block work

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
                import traceback
                print(f"[SpellPool] FIZZLE: '{spell.what}' threw exception: {e}")
                traceback.print_exc()
                spell.fizzle(str(e))
                self._total_spells_fizzled += 1
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

    def cast_immediate(
        self,
        chain: SpellChain,
        what: str,
        how: Callable[[Spell], Any],
        **spell_kwargs
    ) -> Future:
        """
        Create and cast a spell immediately (convenience method).
        """
        spell = Spell(
            spell_type=SpellType.TRANSFORM,
            what=what,
            how=how,
            continues_chain=False,
            **spell_kwargs
        )
        chain.register_spell(spell)
        return self.cast_spell(spell, chain)

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
            sleep_time = max(0, self._tick_interval - elapsed)
            if sleep_time > 0:
                self._stop_event.wait(sleep_time)

    def _tick(self) -> None:
        """Single tick - process all chains."""
        self._tick_count += 1
        chains_to_process = list(self._chains.values())

        for chain in chains_to_process:
            if chain.state == ChainState.DISSOLVED:
                continue

            # Update energy
            chain.tick_energy()

            # Skip if chain is broken/dissolved
            if not chain.is_alive:
                continue

            # Get and execute next spell (could get multiple per tick)
            spell = chain.get_next_spell()
            if spell:
                self.cast_spell(spell, chain)

    def force_tick(self) -> None:
        """Force an immediate tick (for testing)."""
        self._tick()

    # =========================================================================
    # QUERYING
    # =========================================================================

    def get_active_chains(self) -> List[SpellChain]:
        """Get all alive chains."""
        return [c for c in self._chains.values() if c.is_alive]

    def get_chain_by_name(self, fairy_name: str) -> Optional[SpellChain]:
        """Find chain by fairy name."""
        for chain in self._chains.values():
            if chain.fairy_name == fairy_name:
                return chain
        return None

    def get_chains_by_plane(self, plane: str) -> List[SpellChain]:
        """Get all chains in a plane."""
        return [c for c in self._chains.values() if c.fairy_plane == plane]

    # =========================================================================
    # STATUS
    # =========================================================================

    def status(self) -> Dict[str, Any]:
        """Get pool status."""
        uptime = time.time() - self._start_time if self._start_time else 0

        active_chains = [c for c in self._chains.values() if c.is_alive]
        broken_chains = [c for c in self._chains.values() if c.state == ChainState.BROKEN]

        return {
            "running": self._running,
            "max_workers": self._max_workers,
            "tick_interval": self._tick_interval,
            "tick_count": self._tick_count,
            "uptime_seconds": round(uptime, 1),
            "active_futures": len(self._futures),
            "total_spells_cast": self._total_spells_cast,
            "total_spells_completed": self._total_spells_completed,
            "total_spells_fizzled": self._total_spells_fizzled,
            "total_spells_go_dispatched": self._total_spells_go_dispatched,
            "plane_batteries": len(self._plane_batteries),
            "registered_chains": len(self._chains),
            "active_chains": len(active_chains),
            "broken_chains": len(broken_chains),
        }

    def detailed_status(self) -> Dict[str, Any]:
        """Get detailed status including all chain statuses."""
        base = self.status()
        base["chains"] = {
            fairy_id: chain.status()
            for fairy_id, chain in self._chains.items()
        }
        return base

    def health_check(self) -> Dict[str, Any]:
        """Quick health check for monitoring."""
        active = len([c for c in self._chains.values() if c.is_alive])
        broken = len([c for c in self._chains.values() if c.state == ChainState.BROKEN])

        return {
            "healthy": self._running and broken == 0,
            "running": self._running,
            "active_chains": active,
            "broken_chains": broken,
            "spells_cast": self._total_spells_cast,
            "spells_pending": sum(len(c._pending) for c in self._chains.values()),
        }
