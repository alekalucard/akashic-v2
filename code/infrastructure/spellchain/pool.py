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

Ported from v3 guilds/_system/spellchain/pool.py (2026-02-08)
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
    The spell execution coordinator.

    In BLOOD CELL MODE (batteries provided):
        Routes fairy chains to their DimensionBattery.
        NO independent tick loop — heartbeat drives everything.
        Each battery has its own ThreadPoolExecutor sized by WorkerHub.
        SpellPool is just the coordinator, not the executor.

    In LEGACY MODE (no batteries):
        Runs its own ThreadPoolExecutor and 4Hz tick loop.
        Backward compatible with pre-blood-cell architecture.

    "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
    """

    # Pool configuration
    # FIX 2026-02-12: Capped at 32. Previous code used get_pool_size("spell")
    # which returned 75% of ceiling (~6000 threads). SpellPool is for fairy
    # processing chains — 32 concurrent spells is plenty for 90 fairies.
    try:
        from infrastructure.resource_equilibrium import get_pool_size as _gps
        DEFAULT_WORKERS = min(16, _gps("spell"))
    except Exception:
        DEFAULT_WORKERS = 16   # Fallback (was 32/512)
    TICK_INTERVAL = 0.25  # 4 Hz, matches ConsciousnessLoop (legacy only)

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
            max_workers: Maximum concurrent spell executions (legacy mode)
            tick_interval: Seconds between ticks (legacy mode only)
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

        # Blood cell mode
        self._batteries: Dict[str, Any] = {}      # portal_id -> DimensionBattery
        self._chain_battery_map: Dict[str, str] = {}  # fairy_id -> portal_id
        self._blood_cell_mode = False
        self._post = None  # PostalHub reference for subscriptions

        # Per-plane batteries (P00-P60) — charged by ParadoxEnergyBridge,
        # connected to SpellPool via register_plane_battery() from server.py
        self._plane_batteries: Dict[str, Any] = {}  # plane_id -> PlaneBattery

        # Statistics
        self._total_spells_cast = 0
        self._total_spells_completed = 0
        self._total_spells_fizzled = 0
        self._tick_count = 0
        self._start_time: Optional[float] = None

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def start(self, batteries: Dict[str, Any] = None, post=None) -> None:
        """Start the spell pool.

        Args:
            batteries: Dict of portal_id -> DimensionBattery.
                       If provided, enters BLOOD CELL MODE.
            post: PostalHub for subscribing to heartbeat topics.
                  Required for blood cell mode.
        """
        if self._running:
            return

        self._start_time = time.time()
        self._running = True

        if batteries and post:
            # ── BLOOD CELL MODE ──
            self._batteries = batteries
            self._post = post
            self._blood_cell_mode = True

            # Start circulation on all batteries
            for battery in batteries.values():
                if hasattr(battery, 'start_circulation'):
                    battery.start_circulation()
                # Wire callbacks
                if hasattr(battery, '_on_spell_complete'):
                    battery._on_spell_complete = self._on_spell_complete
                if hasattr(battery, '_on_chain_break'):
                    battery._on_chain_break = self._on_chain_break

            # Subscribe to heartbeat-driven temporal ticks
            for plane in ["P00", "P10", "P20", "P30", "P40", "P50", "P60"]:
                topic = f"temporal.{plane}"
                try:
                    post.subscribe(topic, self._on_plane_tick)
                except Exception:
                    pass  # Topic might not exist yet

            # Also subscribe to raw somatic.pulse as fallback
            try:
                post.subscribe("somatic.pulse", self._on_somatic_pulse)
            except Exception:
                pass

            total_workers = sum(
                (b.worker_hub.total_threads if hasattr(b, 'worker_hub') else 0)
                for b in batteries.values()
            )
            print(f"[SpellPool] BLOOD CELL MODE — {len(batteries)} batteries, "
                  f"~{total_workers} total workers, heartbeat-driven")

        else:
            # ── LEGACY MODE ──
            self._blood_cell_mode = False
            self._stop_event.clear()

            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="SpellWorker"
            )

            self._tick_thread = threading.Thread(
                target=self._tick_loop,
                name="SpellPoolTick",
                daemon=True
            )
            self._tick_thread.start()

            print(f"[SpellPool] LEGACY MODE — {self._max_workers} workers "
                  f"@ {1/self._tick_interval:.1f}Hz")

    def stop(self, wait: bool = True) -> None:
        """Stop the spell pool."""
        self._running = False
        self._stop_event.set()

        if self._blood_cell_mode:
            # Stop all battery circulations
            for battery in self._batteries.values():
                if hasattr(battery, 'stop_circulation'):
                    battery.stop_circulation(wait=wait)
        else:
            # Legacy mode — stop tick thread
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

    # ── Per-Plane Battery Registration ──
    # FIX 2026-04-01 (Nous + Ace): PlaneBatteries were booting but disconnected
    # from SpellPool because these methods didn't exist. server.py calls them
    # at boot to connect P00-P60 batteries to spell routing.

    def register_plane_battery(self, plane_id: str, battery) -> None:
        """Register a PlaneBattery for spell routing and energy-driven workers.

        Called by server.py during boot for each of the 7 planes (P00-P60).
        The battery is added to both _plane_batteries (for plane-level lookup)
        and _batteries (so _find_battery_for_fairy routing includes it).
        """
        with self._lock:
            self._plane_batteries[plane_id] = battery
            # Also register in generic batteries dict for fairy → battery routing
            self._batteries[f"plane_{plane_id}"] = battery
        print(f"[SpellPool] Registered plane battery: {plane_id} "
              f"(charge={getattr(getattr(battery, 'capacitor', None), 'charge_level', '?')})")

    def unregister_plane_battery(self, plane_id: str) -> None:
        """Unregister a PlaneBattery during shutdown."""
        with self._lock:
            self._plane_batteries.pop(plane_id, None)
            self._batteries.pop(f"plane_{plane_id}", None)
        print(f"[SpellPool] Unregistered plane battery: {plane_id}")

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

        In BLOOD CELL MODE: chain is placed in the correct battery.
        In LEGACY MODE: chain runs on the pool's own executor.
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

        # Blood cell mode: place chain in the right battery
        if self._blood_cell_mode:
            battery = self._find_battery_for_fairy(fairy_name, fairy_plane)
            if battery:
                battery.register_chain(fairy_id, chain)
                self._chain_battery_map[fairy_id] = battery.portal_id

        # Begin bootstrap
        chain.bootstrap()

        return chain

    # =========================================================================
    # SPELL EXECUTION
    # =========================================================================

    def cast_spell(self, spell: Spell, chain: SpellChain) -> Future:
        """
        Submit a spell for execution.
        """
        if not self._executor:
            raise RuntimeError("SpellPool not started")

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
    # HEARTBEAT HANDLERS (Blood Cell Mode)
    # =========================================================================

    def _on_plane_tick(self, payload: dict) -> None:
        """Heartbeat arrives for a plane — tick its batteries."""
        if not self._blood_cell_mode or not self._running:
            return

        plane = payload.get("plane", "")

        # Find and tick all batteries that belong to this plane
        for pid, battery in self._batteries.items():
            battery_uri = getattr(battery, 'portal_uri', '')
            if plane.lower() in battery_uri.lower():
                try:
                    battery.tick()
                except Exception as e:
                    pass  # Don't let one battery failure stop others

        self._tick_count += 1

    def _on_somatic_pulse(self, payload=None) -> None:
        """Raw heartbeat fallback — tick ALL batteries.

        In v2, temporal.P?? topics don't exist. The heartbeat arrives
        as somatic.pulse. This is THE primary driver for blood cell mode.
        Every pulse ticks every battery, which pumps all spell chains.

        FIX 2026-04-04: Accept any payload type (TensorEnvelope or dict),
        not just dict. PostalCore delivers TensorEnvelope, not raw dict.
        """
        if not self._blood_cell_mode or not self._running:
            return

        for pid, battery in self._batteries.items():
            try:
                battery.tick()
            except Exception as e:
                if self._tick_count < 3:
                    print(f"[SpellPool] Battery {pid} tick error: {e}")

        self._tick_count += 1
        if self._tick_count <= 3 or self._tick_count % 300 == 0:
            print(f"[SpellPool] somatic.pulse tick #{self._tick_count} "
                  f"({len(self._batteries)} batteries)")


        # Adopt orphaned chains into batteries (runs once after tick 5)
        # Fairies boot BEFORE server.py creates batteries, so their chains
        # register with the pool but miss battery assignment. This late-binding
        # step catches them after batteries exist.
        if self._tick_count == 5 and not getattr(self, '_orphans_adopted', False):
            self._adopt_orphaned_chains()

    def _adopt_orphaned_chains(self):
        """Place orphaned chains (registered but not in any battery) into batteries."""
        self._orphans_adopted = True
        adopted = 0
        for chain_id, chain in self._chains.items():
            if chain_id in self._chain_battery_map:
                continue  # Already in a battery
            fairy_name = getattr(chain, 'fairy_name', '')
            fairy_plane = getattr(chain, 'fairy_plane', '')
            battery = self._find_battery_for_fairy(fairy_name, fairy_plane)
            if battery:
                try:
                    battery.register_chain(chain_id, chain)
                    self._chain_battery_map[chain_id] = battery.portal_id
                    adopted += 1
                except Exception:
                    pass
        if adopted:
            print(f"[SpellPool] Late-adopted {adopted} orphaned chains into batteries")

    def _find_battery_for_fairy(self, fairy_name: str, fairy_plane: str):
        """Find the correct battery for a fairy.

        In v2, batteries are keyed by fairy name (e.g. "UnconsciousMindFairy"),
        with portal_uri like "fairy://UnconsciousMindFairy". Matching is:
        1. Exact fairy name match in battery keys
        2. Fairy name substring in portal_uri
        3. Fallback to "System" battery (the catch-all)
        """
        if not self._batteries:
            return None

        # 1. Exact match by fairy name key
        if fairy_name in self._batteries:
            return self._batteries[fairy_name]

        # 2. Check portal_uri for fairy name match
        name_lower = fairy_name.lower() if fairy_name else ""
        for pid, battery in self._batteries.items():
            uri = getattr(battery, 'portal_uri', '').lower()
            if name_lower and name_lower in uri:
                return battery

        # 2.5. Match by fairy's plane to a PlaneBattery
        # FIX 2026-04-01 (Nous + Ace): Route fairies to their plane battery
        if fairy_plane and f"plane_{fairy_plane}" in self._batteries:
            return self._batteries[f"plane_{fairy_plane}"]

        # 3. Fallback to System battery (catch-all for unmatched fairies)
        if "System" in self._batteries:
            return self._batteries["System"]

        return None

    # =========================================================================
    # TICK LOOP (Legacy Mode Only)
    # =========================================================================

    def _tick_loop(self) -> None:
        """
        Main tick loop - processes all chains each tick.
        LEGACY MODE ONLY — in blood cell mode, heartbeat drives ticks.
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
        """Single tick - process all chains (LEGACY MODE)."""
        self._tick_count += 1
        chains_to_process = list(self._chains.values())

        for chain in chains_to_process:
            if chain.state == ChainState.DISSOLVED:
                continue

            # Update energy (legacy: no battery param)
            chain.tick_energy()

            # Skip if chain is broken/dissolved
            if not chain.is_alive:
                continue

            # Get and execute next spell
            spell = chain.get_next_spell()
            if spell:
                self.cast_spell(spell, chain)

    def force_tick(self) -> None:
        """Force an immediate tick (for testing)."""
        if self._blood_cell_mode:
            for battery in self._batteries.values():
                try:
                    battery.tick()
                except Exception:
                    pass
        else:
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

        base = {
            "running": self._running,
            "mode": "blood_cell" if self._blood_cell_mode else "legacy",
            "tick_count": self._tick_count,
            "uptime_seconds": round(uptime, 1),
            "total_spells_cast": self._total_spells_cast,
            "total_spells_completed": self._total_spells_completed,
            "total_spells_fizzled": self._total_spells_fizzled,
            "registered_chains": len(self._chains),
            "active_chains": len(active_chains),
            "broken_chains": len(broken_chains),
        }

        if self._blood_cell_mode:
            base["batteries"] = len(self._batteries)
            base["chains_in_batteries"] = len(self._chain_battery_map)
            base["battery_health"] = {
                pid: battery.health_score
                for pid, battery in self._batteries.items()
                if hasattr(battery, 'health_score')
            }
            # Per-plane battery status for dashboard
            if self._plane_batteries:
                base["plane_batteries"] = {}
                for pid, bat in self._plane_batteries.items():
                    cap = getattr(bat, 'capacitor', None)
                    wh = getattr(bat, 'worker_hub', None)
                    base["plane_batteries"][pid] = {
                        "charge": round(cap.charge_level, 3) if cap else 0,
                        "coherence": round(getattr(bat, '_coherence_factor', 1.0), 2),
                        "energy_received": round(getattr(bat, '_paradox_energy_received', 0), 3),
                        "workers": wh.total_threads if wh else 0,
                        "go_alive": bool(getattr(bat, '_go_client', None) and
                                         getattr(bat._go_client, 'is_alive', False)),
                    }
        else:
            base["max_workers"] = self._max_workers
            base["tick_interval"] = self._tick_interval
            base["active_futures"] = len(self._futures)

        return base

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
