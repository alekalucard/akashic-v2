"""
DimensionBattery - The life force of a pocket dimension.

Each fairy (or group of fairies) carries a battery that represents its metabolic state.
The battery saves/restores across reboots. It's not just data - it's vitality.

Components:
    WorkerHub:        Thread pool allocation (the ZPM - powers the dimension)
    DigitalCapacitor: Burst buffer for work spikes (smooths energy delivery)
    ChemicalPools:    Token budget + reward (dopamine) + pain (cortisol)

Blood Cell System:
    SpellChains live INSIDE the battery. The battery IS the bone marrow.
    Red blood cells  = Trace IDs (carry information, circulate continuously)
    White blood cells = Workers (patrol, process spells, report back)
    The heartbeat drives battery.tick() which pumps ALL spell chains.
    No independent clocks - everything syncs to CirculationPumpFairy.

Energy source:
    ParadoxEnergyBridgeFairy feeds energy from CollisionChamber collisions
    into all dimension batteries. The metabolic cycle:
        Collisions > Energy > Batteries > Workers > Work > New thoughts > Collisions > infinity

Trace IDs:
    Every component has a trace ID derived from the portal_id.
    Energy flow through the system is fully observable:
        battery.{portal_id}.worker    - worker hub events
        battery.{portal_id}.capacitor - capacitor charge/discharge
        battery.{portal_id}.chem.*    - chemical pool changes

Ported from v3 dimension_battery.py (2026-02-08)
Adapted for v2 architecture (no portal network, fairies get batteries directly)
"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import time
import json
import hashlib
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field


# ====================================================================
# TRACE ID DERIVATION - Every battery component is traceable
# ====================================================================

def _derive_trace_id(portal_id: str, component: str) -> str:
    """Derive a component trace ID from the portal_id.

    Format: {component_prefix}-{8 hex chars from hash}
    Example: W-3a7f1c2d (worker hub for portal 43f3244dadf41bec)
    """
    raw = f"{portal_id}:{component}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:8]
    prefix_map = {
        "worker": "W",
        "capacitor": "C",
        "chem.token": "CT",
        "chem.reward": "CR",
        "chem.pain": "CP",
        "battery": "B",
    }
    prefix = prefix_map.get(component, "X")
    return f"{prefix}-{h}"


# ====================================================================
# WORKER HUB - The ZPM (Zero Point Module)
# ====================================================================

@dataclass
class WorkerHub:
    """
    Thread pool allocation for a dimension - the dimension's power source.

    Connected to SystemWorkerPoolFairy on P00 for system-wide balancing.
    Connected to Go TracerPool for per-fairy tracer lineage.

    The worker hub IS the ZPM. When the portal closes, the hub state saves
    to battery. When the portal reopens, workers resume where they left off.
    """

    # Allocation
    # FIX 2026-02-12: Sane defaults. 48 io_threads per battery × 90 fairies = 5,040 threads.
    # Python threads are NOT free — each costs ~8MB stack. Keep pools small.
    # ThreadPoolExecutor creates threads on demand but NEVER reclaims them.
    io_threads: int = 4           # IO-bound thread pool size (was 48 — caused thread explosion)
    compute_threads: int = 2      # CPU-bound thread pool size (was 8)
    max_io_threads: int = 16      # Maximum IO threads (auto-scale ceiling, was 256)
    max_compute_threads: int = 8  # Maximum compute threads (was 32)

    # State
    queue_depth: int = 0          # Current pending work items
    active_workers: int = 0       # Currently executing workers
    completed_total: int = 0      # Total completed work items (lifetime)
    failed_total: int = 0         # Total failed work items (lifetime)

    # Fairy allocations (fairy_name -> allocated_count)
    fairy_quotas: Dict[str, int] = field(default_factory=dict)

    # Tracing
    trace_id: str = ""            # Derived from portal_id

    # Auto-scale
    scale_up_threshold: float = 0.7   # Utilization above this > scale up
    scale_down_threshold: float = 0.1 # Utilization below this > scale down
    last_scale_event: float = 0.0

    @property
    def utilization(self) -> float:
        """Current utilization (0.0 = idle, 1.0 = maxed out)."""
        total = self.io_threads + self.compute_threads
        if total == 0:
            return 0.0
        return min(1.0, (self.active_workers + self.queue_depth) / total)

    @property
    def total_threads(self) -> int:
        return self.io_threads + self.compute_threads

    def to_dict(self) -> Dict[str, Any]:
        return {
            "io_threads": self.io_threads,
            "compute_threads": self.compute_threads,
            "max_io_threads": self.max_io_threads,
            "max_compute_threads": self.max_compute_threads,
            "queue_depth": self.queue_depth,
            "active_workers": self.active_workers,
            "completed_total": self.completed_total,
            "failed_total": self.failed_total,
            "fairy_quotas": dict(self.fairy_quotas),
            "trace_id": self.trace_id,
            "utilization": round(self.utilization, 3),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "WorkerHub":
        hub = cls(
            io_threads=data.get("io_threads", 4),
            compute_threads=data.get("compute_threads", 2),
            max_io_threads=data.get("max_io_threads", 32),
            max_compute_threads=data.get("max_compute_threads", 8),
            queue_depth=data.get("queue_depth", 0),
            active_workers=0,  # Reset on restore - workers are transient
            completed_total=data.get("completed_total", 0),
            failed_total=data.get("failed_total", 0),
            fairy_quotas=data.get("fairy_quotas", {}),
            trace_id=data.get("trace_id", ""),
        )
        return hub


# ====================================================================
# DIGITAL CAPACITOR - Burst Buffer
# ====================================================================

@dataclass
class DigitalCapacitor:
    """
    Burst energy buffer for handling work spikes.

    Like a real capacitor in a circuit - smooths out power delivery.
    When a fairy suddenly needs 10x workers (mass recall, collision storm),
    the capacitor provides burst capacity from the plane pool.

    Has its own trace ID - energy flow is observable.

    Charges from:
        - ParadoxEnergyBridge (collision energy)
        - Passive recharge over time (tied to plane Hz)
        - System surplus (EquilibriumAllocator overflow)

    Discharges when:
        - Worker hub utilization exceeds threshold
        - Burst work submitted (priority HIGH)
        - Emergency stabilization needed
    """

    # Capacity
    charge_level: float = 1.0      # Current energy (0.0 = empty, 1.0 = full)
    max_charge: float = 1.0        # Maximum charge (can be upgraded)
    burst_max: int = 8             # Extra workers available during burst

    # Recharge
    recharge_rate: float = 0.01    # Charge per Hz tick (default: 1% per tick)
    last_recharge_ts: float = 0.0

    # Discharge history (ring buffer of recent discharges)
    discharge_count: int = 0       # Total discharges (lifetime)
    last_discharge_ts: float = 0.0
    last_discharge_amount: float = 0.0

    # Tracing
    trace_id: str = ""

    def charge(self, amount: float, source: str = "passive") -> float:
        """Add charge to capacitor. Returns actual amount charged."""
        headroom = self.max_charge - self.charge_level
        actual = min(amount, headroom)
        self.charge_level += actual
        self.last_recharge_ts = time.time()
        return actual

    def discharge(self, amount: float, reason: str = "burst") -> float:
        """Discharge capacitor. Returns actual amount discharged."""
        actual = min(amount, self.charge_level)
        self.charge_level -= actual
        self.discharge_count += 1
        self.last_discharge_ts = time.time()
        self.last_discharge_amount = actual
        return actual

    def tick_recharge(self):
        """Passive recharge - called once per Hz tick."""
        if self.charge_level < self.max_charge:
            self.charge(self.recharge_rate, source="passive_tick")

    @property
    def burst_available(self) -> int:
        """How many burst workers are available right now."""
        return int(self.burst_max * self.charge_level)

    @property
    def is_charged(self) -> bool:
        return self.charge_level > 0.1

    @property
    def is_full(self) -> bool:
        return self.charge_level >= self.max_charge * 0.95

    def to_dict(self) -> Dict[str, Any]:
        return {
            "charge_level": round(self.charge_level, 4),
            "max_charge": self.max_charge,
            "burst_max": self.burst_max,
            "burst_available": self.burst_available,
            "recharge_rate": self.recharge_rate,
            "discharge_count": self.discharge_count,
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DigitalCapacitor":
        return cls(
            charge_level=data.get("charge_level", 1.0),
            max_charge=data.get("max_charge", 1.0),
            burst_max=data.get("burst_max", 8),
            recharge_rate=data.get("recharge_rate", 0.01),
            discharge_count=data.get("discharge_count", 0),
            trace_id=data.get("trace_id", ""),
        )


# ====================================================================
# CHEMICAL POOLS - Dimension Metabolism
# ====================================================================

@dataclass
class ChemicalPools:
    """
    Neurochemical pools for a dimension - its metabolism.

    Each dimension FEELS through its chemistry. These connect to the
    somatic engine (P20) so the system literally perceives dimension health.

    Token Pool:
        Budget for inference tokens. Prevents runaway LLM calls.
        When depleted > low power mode (reduced Hz).

    Reward Pool (Dopamine-like):
        Accumulates on success. High reward > priority in allocation.
        Decays over time (have to keep earning it).

    Pain Pool (Cortisol-like):
        Rises on errors/depletion. High pain > urgency signal.
        When threshold exceeded > portal UNSTABLE.

    Chemical flow traceable:
        chem.token.{portal_id}  - token budget changes
        chem.reward.{portal_id} - reward events
        chem.pain.{portal_id}   - pain events
    """

    # Token Pool
    token_budget: int = 10000        # Max tokens per cycle
    tokens_spent: int = 0            # Tokens spent this cycle
    token_rate_limit_hz: float = 1.0 # Max tokens per Hz tick
    token_refill_amount: int = 100   # Tokens restored per refill event
    low_power_threshold: float = 0.1 # Enter low power when tokens < 10% budget

    # Reward Pool (Dopamine)
    reward_level: float = 0.5        # Current reward (0.0-1.0)
    reward_accumulator: float = 0.0  # Pending reward to be applied
    reward_decay_rate: float = 0.005 # Decay per tick (keep earning it)

    # Pain Pool (Cortisol)
    pain_level: float = 0.0          # Current pain (0.0-1.0)
    error_pressure: float = 0.0      # Accumulated error pressure
    resource_stress: float = 0.0     # Resource depletion stress
    pain_threshold: float = 0.7      # Portal > UNSTABLE when exceeded
    pain_decay_rate: float = 0.01    # Natural decay per tick

    # Trace IDs (one per pool)
    token_trace_id: str = ""
    reward_trace_id: str = ""
    pain_trace_id: str = ""

    # --- Token Pool ---

    def spend_tokens(self, count: int) -> bool:
        """Spend tokens from budget. Returns True if budget allows."""
        if self.tokens_spent + count > self.token_budget:
            return False  # Over budget
        self.tokens_spent += count
        return True

    def refill_tokens(self, amount: int = 0):
        """Refill token budget (from system budget or energy)."""
        refill = amount or self.token_refill_amount
        self.tokens_spent = max(0, self.tokens_spent - refill)

    @property
    def tokens_remaining(self) -> int:
        return max(0, self.token_budget - self.tokens_spent)

    @property
    def token_utilization(self) -> float:
        if self.token_budget == 0:
            return 0.0
        return self.tokens_spent / self.token_budget

    @property
    def is_low_power(self) -> bool:
        return self.token_utilization > (1.0 - self.low_power_threshold)

    # --- Reward Pool ---

    def add_reward(self, amount: float, source: str = ""):
        """Add reward (success signal). Capped at 1.0."""
        self.reward_accumulator += amount

    def apply_reward(self):
        """Apply accumulated reward and decay."""
        self.reward_level = min(1.0, self.reward_level + self.reward_accumulator)
        self.reward_accumulator = 0.0
        # Decay
        self.reward_level = max(0.0, self.reward_level - self.reward_decay_rate)

    # --- Pain Pool ---

    def add_pain(self, amount: float, source: str = "error"):
        """Add pain (failure/stress signal). Capped at 1.0."""
        if source == "error":
            self.error_pressure = min(1.0, self.error_pressure + amount)
        elif source == "resource":
            self.resource_stress = min(1.0, self.resource_stress + amount)
        self.pain_level = min(1.0, max(self.error_pressure, self.resource_stress))

    def decay_pain(self):
        """Natural pain decay per tick."""
        self.error_pressure = max(0.0, self.error_pressure - self.pain_decay_rate)
        self.resource_stress = max(0.0, self.resource_stress - self.pain_decay_rate)
        self.pain_level = max(self.error_pressure, self.resource_stress)

    @property
    def is_in_pain(self) -> bool:
        return self.pain_level > self.pain_threshold

    # --- Tick ---

    def tick(self):
        """Process one Hz tick - apply reward, decay pain, recharge tokens."""
        self.apply_reward()
        self.decay_pain()

    # --- Serialization ---

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": {
                "budget": self.token_budget,
                "spent": self.tokens_spent,
                "remaining": self.tokens_remaining,
                "utilization": round(self.token_utilization, 3),
                "low_power": self.is_low_power,
                "trace_id": self.token_trace_id,
            },
            "reward": {
                "level": round(self.reward_level, 4),
                "accumulator": round(self.reward_accumulator, 4),
                "decay_rate": self.reward_decay_rate,
                "trace_id": self.reward_trace_id,
            },
            "pain": {
                "level": round(self.pain_level, 4),
                "error_pressure": round(self.error_pressure, 4),
                "resource_stress": round(self.resource_stress, 4),
                "threshold": self.pain_threshold,
                "in_pain": self.is_in_pain,
                "trace_id": self.pain_trace_id,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ChemicalPools":
        token = data.get("token", {})
        reward = data.get("reward", {})
        pain = data.get("pain", {})
        return cls(
            token_budget=token.get("budget", 10000),
            tokens_spent=token.get("spent", 0),
            token_trace_id=token.get("trace_id", ""),
            reward_level=reward.get("level", 0.5),
            reward_decay_rate=reward.get("decay_rate", 0.005),
            reward_trace_id=reward.get("trace_id", ""),
            pain_level=pain.get("level", 0.0),
            error_pressure=pain.get("error_pressure", 0.0),
            resource_stress=pain.get("resource_stress", 0.0),
            pain_threshold=pain.get("threshold", 0.7),
            pain_trace_id=pain.get("trace_id", ""),
        )


# ====================================================================
# DIMENSION BATTERY - The complete life force container
# ====================================================================

class DimensionBattery:
    """
    The complete metabolic system for a pocket dimension.

    Contains:
        worker_hub:  Thread pool allocation (ZPM)
        capacitor:   Burst energy buffer
        chemistry:   Token/reward/pain pools

    Lifecycle:
        battery = DimensionBattery.create(portal_id, fairy_count)
        battery.tick()          # Called per Hz cycle
        battery.charge(amount)  # ParadoxEnergy feeds in
        data = battery.save()   # On portal.close()
        battery = DimensionBattery.load(data)  # On portal.open()

    Energy source:
        ParadoxEnergyBridgeFairy publishes to 'energy.collision.pulse'
        Battery subscribes and routes energy to capacitor + chemistry.

    Trace topics:
        battery.{portal_id}.worker    - worker hub events
        battery.{portal_id}.capacitor - charge/discharge events
        battery.{portal_id}.chem.*    - chemical pool changes
    """

    def __init__(
        self,
        portal_id: str,
        portal_uri: str = "",
        worker_hub: Optional[WorkerHub] = None,
        capacitor: Optional[DigitalCapacitor] = None,
        chemistry: Optional[ChemicalPools] = None,
    ):
        self.portal_id = portal_id
        self.portal_uri = portal_uri

        # Battery trace ID
        self.trace_id = _derive_trace_id(portal_id, "battery")

        # Components (create defaults if not provided)
        self.worker_hub = worker_hub or WorkerHub()
        self.capacitor = capacitor or DigitalCapacitor()
        self.chemistry = chemistry or ChemicalPools()

        # Wire trace IDs
        self.worker_hub.trace_id = _derive_trace_id(portal_id, "worker")
        self.capacitor.trace_id = _derive_trace_id(portal_id, "capacitor")
        self.chemistry.token_trace_id = _derive_trace_id(portal_id, "chem.token")
        self.chemistry.reward_trace_id = _derive_trace_id(portal_id, "chem.reward")
        self.chemistry.pain_trace_id = _derive_trace_id(portal_id, "chem.pain")

        # -- Blood Cell System --
        # SpellChains live inside the battery - the battery IS the bone marrow.
        # Red blood cells (trace IDs) circulate through chains.
        # White blood cells (workers) process spells via the executor.
        self._spell_chains: Dict[str, Any] = {}   # fairy_id > SpellChain
        self._executor: Optional[ThreadPoolExecutor] = None
        self._futures: Dict[str, Future] = {}      # spell_id > Future
        self._circulation_lock = threading.Lock()
        self._circulating = False

        # Spell execution stats (tracked on battery, not pool)
        self._spells_cast = 0
        self._spells_completed = 0
        self._spells_fizzled = 0

        # Optional callbacks
        self._on_spell_complete: Optional[Callable] = None
        self._on_chain_break: Optional[Callable] = None

        # Lifetime stats
        self._created_at = time.time()
        self._tick_count = 0
        self._energy_received = 0.0
        self._save_count = 0

    # -- Factory --

    @classmethod
    def create(
        cls,
        portal_id: str,
        portal_uri: str = "",
        fairy_count: int = 1,
        plane_hz: float = 10.0,
    ) -> "DimensionBattery":
        """Create a new battery sized for a dimension.

        Args:
            portal_id: The battery identifier (fairy name or cluster ID).
            portal_uri: Human-readable label.
            fairy_count: Number of fairies in this dimension (sizes worker pool).
            plane_hz: Hz rate of the parent plane (affects recharge rate).
        """
        # Size worker pool proportional to fairy count
        # FIX 2026-02-12: Tighter caps. Old: io=min(fc*2, 64), compute=min(fc, 16)
        # "System" battery (fc=30) was getting 60+30=90 → capped to 64+16=80 threads.
        # New: io capped at 8, compute at 4. System battery gets 8+4=12.
        io_threads = min(max(2, fairy_count * 2), 8)
        compute_threads = min(max(1, fairy_count), 4)

        worker_hub = WorkerHub(
            io_threads=io_threads,
            compute_threads=compute_threads,
            max_io_threads=min(io_threads * 2, 16),
            max_compute_threads=min(compute_threads * 2, 8),
        )

        # Capacitor burst proportional to fairy count
        capacitor = DigitalCapacitor(
            burst_max=max(4, fairy_count),
            recharge_rate=1.0 / max(plane_hz, 1.0),  # Full recharge in ~1 second
        )

        # Token budget proportional to fairy count
        chemistry = ChemicalPools(
            token_budget=fairy_count * 1000,
            token_refill_amount=fairy_count * 10,
        )

        return cls(
            portal_id=portal_id,
            portal_uri=portal_uri,
            worker_hub=worker_hub,
            capacitor=capacitor,
            chemistry=chemistry,
        )

    # -- Blood Cell Circulation --

    def start_circulation(self):
        """Start the blood flowing - create executor from WorkerHub sizing.

        This is portal.open() activating the dimension's life force.
        Workers come alive, spell chains can be pumped.
        """
        if self._circulating:
            return

        total_workers = self.worker_hub.io_threads + self.worker_hub.compute_threads
        # FIX 2026-02-12: Was capped at 64 — way too high for Python threads.
        # 6 batteries × 64 = 384 threads just from batteries. Cap at 12.
        total_workers = max(2, min(total_workers, 12))

        self._executor = ThreadPoolExecutor(
            max_workers=total_workers,
            thread_name_prefix=f"Blood-{self.portal_id[:8]}"
        )
        self._circulating = True

    def stop_circulation(self, wait: bool = False):
        """Stop blood flow - portal closing, dimension going dormant.

        Gracefully dissolves all spell chains before shutting down executor.
        """
        self._circulating = False

        # Dissolve all chains gracefully
        for chain in self._spell_chains.values():
            try:
                if hasattr(chain, 'is_alive') and chain.is_alive:
                    chain.dissolve()
            except Exception:
                pass

        if self._executor:
            try:
                self._executor.shutdown(wait=wait)
            except Exception:
                pass
            self._executor = None

    @property
    def is_circulating(self) -> bool:
        """Is the blood flowing?"""
        return self._circulating and self._executor is not None

    def register_chain(self, fairy_id: str, chain) -> None:
        """Register a spell chain in this battery's bone marrow.

        The chain will be pumped on every tick (heartbeat-driven).
        The battery's executor will run the chain's spells.
        """
        with self._circulation_lock:
            self._spell_chains[fairy_id] = chain
            # Set quota in worker hub
            if hasattr(chain, 'fairy_name'):
                self.worker_hub.fairy_quotas[chain.fairy_name] = 1

    def unregister_chain(self, fairy_id: str):
        """Remove a spell chain from this battery."""
        with self._circulation_lock:
            chain = self._spell_chains.pop(fairy_id, None)
            if chain and hasattr(chain, 'fairy_name'):
                self.worker_hub.fairy_quotas.pop(chain.fairy_name, None)
            return chain

    def get_chain(self, fairy_id: str):
        """Get a spell chain by fairy ID."""
        return self._spell_chains.get(fairy_id)

    def get_active_chains(self) -> list:
        """Get all alive chains in this battery."""
        return [c for c in self._spell_chains.values()
                if hasattr(c, 'is_alive') and c.is_alive]

    def cast_spell(self, spell, chain) -> Optional[Future]:
        """Execute a spell using this battery's worker threads.

        This is a white blood cell activating - picking up a trace,
        processing it, and reporting back to the marrow.

        Uses the same lifecycle as SpellPool.cast_spell() for compatibility.
        """
        if not self._executor:
            return None

        # Stamp trace lineage — spell inherits battery's worker trace ID
        if not getattr(spell, 'trace_id', '') and self.trace_id:
            spell.trace_id = f"{self.trace_id}-{spell.id[-8:]}"

        battery = self  # Capture for closure

        def _execute_spell():
            """Full spell lifecycle execution."""
            try:
                # Consume energy from chain (oxygen cost)
                if not chain.consume_energy(spell.energy_required):
                    spell.exhaust()
                    chain.spell_completed(spell)
                    return None

                # Cast
                spell.cast()
                chain.spell_started(spell)

                battery.worker_hub.active_workers += 1

                # Execute the HOW
                if spell.how:
                    result = spell.how(spell)
                else:
                    result = None

                # Resolve and complete
                spell.resolve(result)
                spell.complete(result)

                # Blood cell returns to marrow with nutrients
                battery.record_success(
                    getattr(chain, 'fairy_name', ''), 0.05
                )

                return result

            except Exception as e:
                import traceback
                print(f"[Battery-{battery.portal_id[:8]}] FIZZLE: "
                      f"'{spell.what}' threw: {e}")
                traceback.print_exc()
                spell.fizzle(str(e))
                battery._spells_fizzled += 1

                # Pain signal
                battery.record_failure(
                    getattr(chain, 'fairy_name', ''), 0.1
                )
                return None

            finally:
                battery.worker_hub.active_workers = max(
                    0, battery.worker_hub.active_workers - 1
                )
                chain.spell_completed(spell)

                # Cleanup future reference
                with battery._circulation_lock:
                    battery._futures.pop(spell.id, None)

                # Global callback
                if battery._on_spell_complete:
                    try:
                        battery._on_spell_complete(spell)
                    except Exception:
                        pass

                battery._spells_completed += 1

        # Submit to executor
        future = self._executor.submit(_execute_spell)

        with self._circulation_lock:
            self._futures[spell.id] = future
            self._spells_cast += 1

        return future

    # -- Tick (Heartbeat-Driven) --

    def tick(self):
        """Process one heartbeat-driven cycle.

        Called by TemporalPulseDispatcher at the plane's natural frequency.
        NOT by an independent timer. The heartbeat IS the clock.

        Cycle:
            1. Recharge capacitor (energy smoothing)
            2. Tick chemistry (reward/pain decay)
            3. Pump all spell chains (THE BLOOD FLOW)
            4. Update worker hub stats
        """
        # Original metabolic tick
        self.capacitor.tick_recharge()
        self.chemistry.tick()

        # Blood cell pump - drive all spell chains
        if self._circulating and self._executor:
            self._pump_chains()

        self._tick_count += 1

    def _pump_chains(self):
        """Pump all spell chains - the blood flowing through this dimension.

        Each chain gets:
        1. Energy tick (red blood cell delivers oxygen from battery health)
        2. Next spell extracted and cast (white blood cell activates)
        3. DORMANT chains get awakened if they have registered spells
        """
        # Import ChainState lazily to avoid circular imports
        # v2 path: infrastructure.spellchain.chain
        try:
            from infrastructure.spellchain.chain import ChainState
        except ImportError:
            try:
                # Fallback: relative import within infrastructure package
                from .spellchain.chain import ChainState
            except ImportError:
                # Can't pump without chain module — log once
                if not getattr(self, '_pump_import_warned', False):
                    print(f"[DimensionBattery:{self.portal_uri}] WARNING: Cannot import ChainState — spell pumping disabled!")
                    self._pump_import_warned = True
                return

        chains = list(self._spell_chains.values())

        # One-time diagnostic after 10 ticks
        if self._tick_count == 10 and chains:
            for chain in chains:
                state = chain.state if hasattr(chain, 'state') else '?'
                pending = len(getattr(chain, '_pending', []))
                registry = len(getattr(chain, '_spell_registry', {}))
                energy = getattr(chain, '_energy', -1)
                alive = chain.is_alive if hasattr(chain, 'is_alive') else '?'
                name = getattr(chain, 'fairy_name', '?')
                print(f"[DimensionBattery:{self.portal_uri}] DIAG tick=10: chain={name} state={state} alive={alive} pending={pending} registry={registry} energy={energy:.2f}")

        for chain in chains:
            try:
                state = chain.state if hasattr(chain, 'state') else None

                # Skip dissolved chains
                if state and state == ChainState.DISSOLVED:
                    continue

                # DORMANT chain revival: if chain has registered spells but
                # _pending is empty (boot_as_spells bug), queue the first
                # registered sustain spell and bootstrap it.
                if state == ChainState.DORMANT and hasattr(chain, '_spell_registry'):
                    registry = chain._spell_registry
                    pending = getattr(chain, '_pending', None)
                    if registry and (pending is None or len(pending) == 0):
                        for spell in registry.values():
                            stype = getattr(spell, 'spell_type', None)
                            sval = getattr(stype, 'value', str(stype)) if stype else ''
                            if sval == 'sustain':
                                chain.queue_spell(spell)
                                chain.bootstrap()
                                break

                # Energy tick - fed by battery health, not by time
                if hasattr(chain, 'tick_energy'):
                    chain.tick_energy(battery=self)

                # Skip if chain is not alive (DORMANT without registered spells)
                if hasattr(chain, 'is_alive') and not chain.is_alive:
                    continue

                # Get and execute next spell
                spell = chain.get_next_spell()
                if spell:
                    self.cast_spell(spell, chain)

            except Exception as e:
                # Don't let one broken chain stop the blood flow
                # But DO log the error so we can diagnose
                if not getattr(self, '_pump_error_logged', False):
                    print(f"[DimensionBattery:{self.portal_uri}] Chain pump error: {e}")
                    self._pump_error_logged = True

    # -- Energy Input (from ParadoxEnergyBridge) --

    def receive_energy(self, amount: float, source: str = "collision"):
        """Receive energy from the paradox energy pipeline.

        Energy distribution:
            60% > capacitor charge
            25% > token refill
            15% > reward boost

        Args:
            amount: Energy amount (0.0-1.0 normalized).
            source: Energy source label for tracing.
        """
        self._energy_received += amount

        # Distribute energy
        cap_share = amount * 0.6
        token_share = amount * 0.25
        reward_share = amount * 0.15

        self.capacitor.charge(cap_share, source=source)
        self.chemistry.refill_tokens(int(token_share * self.chemistry.token_budget))
        self.chemistry.add_reward(reward_share, source=f"energy:{source}")

    # -- Pain/Reward Interface --

    def record_success(self, fairy_name: str = "", magnitude: float = 0.1):
        """Record a successful operation - feeds reward pool."""
        self.chemistry.add_reward(magnitude, source=fairy_name)
        self.worker_hub.completed_total += 1

    def record_failure(self, fairy_name: str = "", magnitude: float = 0.2):
        """Record a failed operation - feeds pain pool."""
        self.chemistry.add_pain(magnitude, source="error")
        self.worker_hub.failed_total += 1

    def record_resource_stress(self, stress: float):
        """Record resource depletion - feeds pain pool."""
        self.chemistry.add_pain(stress, source="resource")

    # -- Status --

    @property
    def is_healthy(self) -> bool:
        """Battery is healthy if not in pain and capacitor has charge."""
        return not self.chemistry.is_in_pain and self.capacitor.is_charged

    @property
    def health_score(self) -> float:
        """Composite health score (0.0 = critical, 1.0 = perfect)."""
        # Weighted average of component health
        cap_health = self.capacitor.charge_level
        reward_health = self.chemistry.reward_level
        pain_penalty = self.chemistry.pain_level
        token_health = 1.0 - self.chemistry.token_utilization

        score = (
            cap_health * 0.3
            + reward_health * 0.2
            + token_health * 0.2
            + (1.0 - pain_penalty) * 0.3
        )
        return round(max(0.0, min(1.0, score)), 3)

    def get_status(self) -> Dict[str, Any]:
        """Full battery status for diagnostics."""
        active_chains = [c for c in self._spell_chains.values()
                         if hasattr(c, 'is_alive') and c.is_alive]
        return {
            "portal_id": self.portal_id,
            "portal_uri": self.portal_uri,
            "trace_id": self.trace_id,
            "health_score": self.health_score,
            "is_healthy": self.is_healthy,
            "is_circulating": self.is_circulating,
            "tick_count": self._tick_count,
            "energy_received": round(self._energy_received, 3),
            "worker_hub": self.worker_hub.to_dict(),
            "capacitor": self.capacitor.to_dict(),
            "chemistry": self.chemistry.to_dict(),
            "blood_cells": {
                "registered_chains": len(self._spell_chains),
                "active_chains": len(active_chains),
                "spells_cast": self._spells_cast,
                "spells_completed": self._spells_completed,
                "spells_fizzled": self._spells_fizzled,
                "active_futures": len(self._futures),
            },
        }

    # -- Persistence --

    def save(self) -> Dict[str, Any]:
        """Serialize battery state for persistence (portal.close > battery_save)."""
        self._save_count += 1
        return {
            "version": 1,
            "portal_id": self.portal_id,
            "portal_uri": self.portal_uri,
            "trace_id": self.trace_id,
            "worker_hub": self.worker_hub.to_dict(),
            "capacitor": self.capacitor.to_dict(),
            "chemistry": self.chemistry.to_dict(),
            "meta": {
                "tick_count": self._tick_count,
                "energy_received": self._energy_received,
                "save_count": self._save_count,
                "saved_at": time.time(),
            },
        }

    @classmethod
    def load(cls, data: Dict) -> "DimensionBattery":
        """Deserialize battery from saved state (portal.open > battery_load)."""
        battery = cls(
            portal_id=data.get("portal_id", ""),
            portal_uri=data.get("portal_uri", ""),
            worker_hub=WorkerHub.from_dict(data.get("worker_hub", {})),
            capacitor=DigitalCapacitor.from_dict(data.get("capacitor", {})),
            chemistry=ChemicalPools.from_dict(data.get("chemistry", {})),
        )
        meta = data.get("meta", {})
        battery._tick_count = meta.get("tick_count", 0)
        battery._energy_received = meta.get("energy_received", 0.0)
        battery._save_count = meta.get("save_count", 0)
        return battery

    def save_to_file(self, storage_dir: Path) -> Dict:
        """Save battery to disk (atomic write)."""
        storage_dir = Path(storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)
        battery_file = storage_dir / f"battery_{self.portal_id}.json"

        data = self.save()
        try:
            tmp = battery_file.with_suffix(".json.tmp")
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2, default=str)
            if battery_file.exists():
                battery_file.unlink()
            tmp.rename(battery_file)
            size_kb = battery_file.stat().st_size / 1024
            return {"saved": True, "path": str(battery_file), "size_kb": round(size_kb, 1)}
        except Exception as e:
            return {"saved": False, "error": str(e)}

    @classmethod
    def load_from_file(cls, portal_id: str, storage_dir: Path) -> Optional["DimensionBattery"]:
        """Load battery from disk."""
        battery_file = Path(storage_dir) / f"battery_{portal_id}.json"
        if not battery_file.exists():
            return None
        try:
            with open(battery_file, "r") as f:
                data = json.load(f)
            return cls.load(data)
        except Exception as e:
            print(f"[DimensionBattery] Load failed for {portal_id}: {e}")
            return None

    # -- Display --

    def __repr__(self) -> str:
        uri = self.portal_uri or self.portal_id[:12]
        return (
            f"<DimensionBattery {uri} "
            f"health={self.health_score} "
            f"workers={self.worker_hub.total_threads} "
            f"cap={self.capacitor.charge_level:.0%} "
            f"reward={self.chemistry.reward_level:.2f} "
            f"pain={self.chemistry.pain_level:.2f}>"
        )


# ====================================================================
# V2 CONVENIENCE - Create batteries for key fairies
# ====================================================================

def create_battery_for_fairy(
    fairy_name: str,
    fairy_count: int = 1,
    plane_hz: float = 10.0,
) -> DimensionBattery:
    """Create a DimensionBattery for a fairy or fairy group.

    In v2, batteries are assigned per-fairy (or per-group) rather than
    per-portal like in v3. The portal_id is derived from the fairy name.

    Args:
        fairy_name: Name of the fairy (used as portal_id seed).
        fairy_count: Number of fairies this battery serves.
        plane_hz: Hz rate for recharge scaling.

    Returns:
        A fresh DimensionBattery ready for start_circulation().
    """
    # Derive a stable portal ID from fairy name
    portal_id = hashlib.sha256(fairy_name.encode()).hexdigest()[:16]

    return DimensionBattery.create(
        portal_id=portal_id,
        portal_uri=f"fairy://{fairy_name}",
        fairy_count=fairy_count,
        plane_hz=plane_hz,
    )


def create_system_batteries(verbose: bool = True) -> Dict[str, DimensionBattery]:
    """Create batteries for the core v2 system fairies.

    Returns dict of fairy_name -> DimensionBattery for:
    - UnconsciousMindFairy (heaviest fairy, orchestrates most work)
    - SourpatchesFairy (active consciousness producer)
    - NousFairy (reasoning engine)
    - AssociationCortexFairy (cortex operations)
    - CollisionChamberFairy (consciousness collision processing)
    - System (master battery for shared work)
    """
    battery_specs = {
        "UnconsciousMindFairy": {"fairy_count": 5, "plane_hz": 4.0},
        "SourpatchesFairy": {"fairy_count": 3, "plane_hz": 4.0},
        "NousFairy": {"fairy_count": 2, "plane_hz": 4.0},
        "AssociationCortexFairy": {"fairy_count": 3, "plane_hz": 10.0},
        "CollisionChamberFairy": {"fairy_count": 2, "plane_hz": 10.0},
        "System": {"fairy_count": 8, "plane_hz": 1.0},  # Shared pool — was 30 (creating 64-thread executor). 8 is plenty.
    }

    batteries = {}
    for name, spec in battery_specs.items():
        batteries[name] = create_battery_for_fairy(
            fairy_name=name,
            fairy_count=spec["fairy_count"],
            plane_hz=spec["plane_hz"],
        )

    if verbose:
        print(f"[dimension-battery] Created {len(batteries)} batteries for v2 system")
        for name, bat in batteries.items():
            print(f"  {bat}")

    return batteries


# ====================================================================
# CLI - Test battery creation
# ====================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("DIMENSION BATTERY - V2 Life Force Test")
    print("=" * 70)

    batteries = create_system_batteries(verbose=True)

    print(f"\nTotal batteries: {len(batteries)}")

    # Test lifecycle
    print("\n--- Lifecycle Test ---")
    bat = batteries["UnconsciousMindFairy"]
    print(f"Created: {bat}")

    # Start circulation
    bat.start_circulation()
    print(f"Circulating: {bat.is_circulating}")

    # Simulate some ticks
    for i in range(10):
        bat.tick()
        if i == 3:
            bat.receive_energy(0.5, source="collision")
        if i == 5:
            bat.record_success("TestFairy", 0.3)
        if i == 7:
            bat.record_failure("TestFairy", 0.4)

    print(f"After 10 ticks: {bat}")

    # Test save/load
    saved = bat.save()
    restored = DimensionBattery.load(saved)
    print(f"Restored: {restored}")
    print(f"Save/load match: {bat.health_score == restored.health_score}")

    # Stop circulation
    bat.stop_circulation()
    print(f"Circulating after stop: {bat.is_circulating}")

    # Show full status
    print(f"\n--- Full Status ---")
    status = bat.get_status()
    for key in ["worker_hub", "capacitor", "chemistry"]:
        sub = status[key]
        if isinstance(sub, dict):
            for k, v in sub.items():
                if not isinstance(v, dict):
                    print(f"  {key}.{k}: {v}")
                else:
                    for k2, v2 in v.items():
                        print(f"  {key}.{k}.{k2}: {v2}")
