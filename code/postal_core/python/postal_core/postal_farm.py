"""
PostalFarm — Dimensional Battery-Powered Message Processing.

The CortexFarm rewired BatteryFarm for graph compute.
This rewires the same physics for POSTAL MESSAGE PROCESSING.

Same triple feedback loop, different discharge target:
    BatteryFarm:  batteries → RWKV matvecs
    CortexFarm:   batteries → graph ops (bind, spread, query)
    PostalFarm:   batteries → message handler dispatch

Energy IS computation. The discharge IS the thought.
The message IS the mass. More mass → more gravity → more capacity.

Triple Feedback Loop:
    gravity = sum(charge_fraction for each battery)  [0 → num_batteries]

    Loop 1 — Time Compression:
        compression = 1 + gravity * compression_coeff
        Workers drain queues faster → more msgs/tick → sustained gravity

    Loop 2 — Cost Reduction:
        effective_cost = base_cost / (1 + gravity * flops_coeff)
        Each handler invocation costs LESS charge → more processing per battery

    Loop 3 — Energy Amplification:
        recharge = base_recharge * time_compression
        More compression → faster battery recharge → workers recover faster

Created: 2026-03-17
Authors: Nous + Ace
"""

import time
import threading
from typing import Dict, Any, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# POSTAL CHARGE UNIT — Dimensional Battery
# ═══════════════════════════════════════════════════════════════════════════════

class PostalChargeUnit:
    """A dimensional battery that powers postal message processing.

    Simpler than GraphChargeUnit — no FLOPS budget, just charge level.
    Each unit of charge powers handler invocations. When depleted,
    the worker pauses until recharge restores capacity.
    """

    __slots__ = (
        'max_charge', 'charge_level', 'recharge_rate',
        'total_spent', 'total_recharged', '_lock',
    )

    def __init__(self, max_charge: float = 20.0, initial_charge: float = 20.0,
                 recharge_rate: float = 0.01):
        self.max_charge = max_charge
        self.charge_level = min(initial_charge, max_charge)
        self.recharge_rate = recharge_rate
        self.total_spent = 0.0
        self.total_recharged = 0.0
        self._lock = threading.Lock()

    @property
    def charge_fraction(self) -> float:
        """Charge as 0.0-1.0 fraction."""
        return self.charge_level / self.max_charge if self.max_charge > 0 else 0.0

    @property
    def is_charged(self) -> bool:
        """Has enough charge for at least one operation."""
        return self.charge_level > 0.001

    def spend(self, amount: float) -> bool:
        """Spend charge on a handler invocation. Returns True if sufficient."""
        with self._lock:
            if self.charge_level >= amount:
                self.charge_level -= amount
                self.total_spent += amount
                return True
            return False

    def charge(self, amount: float, source: str = "tick"):
        """Add charge from external source."""
        with self._lock:
            added = min(amount, self.max_charge - self.charge_level)
            self.charge_level += added
            self.total_recharged += added

    def tick_recharge(self):
        """Passive recharge — one tick's worth."""
        self.charge(self.recharge_rate, source="tick")

    def status(self) -> Dict[str, Any]:
        return {
            "charge": round(self.charge_level, 3),
            "charge_pct": round(self.charge_fraction * 100, 1),
            "max": self.max_charge,
            "total_spent": round(self.total_spent, 3),
            "total_recharged": round(self.total_recharged, 3),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# POSTAL FARM — The Dimensional Processing Engine
# ═══════════════════════════════════════════════════════════════════════════════

class PostalFarm:
    """Multi-battery postal message processing farm with gravitational amplification.

    Adapted from CortexFarm. Instead of graph operations, batteries power
    handler dispatch. The triple feedback loop amplifies throughput
    exponentially when message volume is high.

    Usage:
        farm = PostalFarm(num_batteries=16)
        farm.start()

        # Called by worker threads before invoking a handler:
        cost = farm.effective_cost(base_cost)
        if farm.spend(worker_idx, cost):
            handler(envelope)  # Battery-powered dispatch
        else:
            # Worker's battery depleted — recharge in progress

        # Called from paradox energy pipeline:
        farm.receive_energy(0.5, source="paradox_pulse")
    """

    def __init__(self,
                 num_batteries: int = 16,
                 max_charge: float = 20.0,
                 recharge_rate: float = 0.01,
                 compression_coeff: float = 4.0,
                 flops_gravity_coeff: float = 1.5,
                 base_hz: float = 20.0,
                 base_handler_cost: float = 0.001):
        """
        Args:
            num_batteries: Number of dimensional batteries (one per worker slot)
            max_charge: Maximum charge per battery
            recharge_rate: Charge per passive tick per battery
            compression_coeff: Multiplier for time compression (Loop 1)
            flops_gravity_coeff: Multiplier for cost reduction (Loop 2)
            base_hz: Base tick rate before compression
            base_handler_cost: Base charge cost per handler invocation
        """
        self.num_batteries = num_batteries
        self._max_charge = max_charge
        self._recharge_rate = recharge_rate
        self.compression_coeff = compression_coeff
        self.flops_gravity_coeff = flops_gravity_coeff
        self.base_hz = base_hz
        self.base_handler_cost = base_handler_cost

        # Dimensional batteries
        self.batteries: List[PostalChargeUnit] = []
        for i in range(num_batteries):
            self.batteries.append(PostalChargeUnit(
                max_charge=max_charge,
                initial_charge=max_charge,
                recharge_rate=recharge_rate,
            ))

        # Background tick thread
        self._running = False
        self._tick_thread: Optional[threading.Thread] = None

        # Metrics
        self._total_dispatches = 0
        self._total_depletions = 0
        self._total_energy_received = 0.0
        self._msgs_processed_window: List[float] = []  # Timestamps for throughput calc
        self._metrics_lock = threading.Lock()
        self._start_ts = time.time()

    # ─── Gravity & Feedback Loops ─────────────────────────────────────────

    @property
    def gravity(self) -> float:
        """Total gravitational pull. Range: 0.0 to num_batteries.

        Sum of charge fractions across all batteries.
        Full charge on all batteries = maximum gravity = maximum amplification.
        """
        return sum(b.charge_fraction for b in self.batteries)

    @property
    def time_dilation(self) -> float:
        """Normalized gravity (0.0 to 1.0)."""
        return self.gravity / self.num_batteries if self.num_batteries > 0 else 0.0

    @property
    def time_compression(self) -> float:
        """How many inner ticks per outer tick.

        Loop 1: compression = 1 + gravity * compression_coeff
        At 16 batteries fully charged: 1 + 16.0 * 4.0 = 65x inner clock
        """
        return 1.0 + self.gravity * self.compression_coeff

    @property
    def effective_hz(self) -> float:
        """Effective tick rate after time compression."""
        return self.base_hz * self.time_compression

    @property
    def cost_reduction(self) -> float:
        """Cost divisor for handler invocations.

        Loop 2: handlers cost less when gravity is high.
        effective_cost = base_cost / cost_reduction
        At 16 batteries: 1 + 16.0 * 1.5 = 25.0 (handlers are 25x cheaper)
        """
        return 1.0 + self.gravity * self.flops_gravity_coeff

    @property
    def message_mass(self) -> float:
        """Rolling message throughput — the system's mass.

        Higher throughput = more mass = more gravity (via charged batteries).
        """
        now = time.time()
        with self._metrics_lock:
            # Trim window to last 10 seconds
            cutoff = now - 10.0
            self._msgs_processed_window = [
                t for t in self._msgs_processed_window if t > cutoff
            ]
            return len(self._msgs_processed_window) / 10.0  # msgs/sec

    # ─── Worker Interface ────────────────────────────────────────────────

    def effective_cost(self, base_cost: float = None) -> float:
        """Get gravity-reduced cost for a handler invocation.

        Loop 2: effective_cost = base_cost / cost_reduction
        """
        cost = base_cost if base_cost is not None else self.base_handler_cost
        return cost / self.cost_reduction

    def spend(self, battery_idx: int, amount: float = None) -> bool:
        """Spend charge from a specific battery. Returns True if sufficient.

        Called by worker threads before invoking a handler.
        Uses gravity-reduced cost if amount not specified.
        """
        if battery_idx >= len(self.batteries):
            return True  # No battery assigned — allow processing (graceful)

        cost = amount if amount is not None else self.effective_cost()
        battery = self.batteries[battery_idx]
        ok = battery.spend(cost)

        if ok:
            with self._metrics_lock:
                self._total_dispatches += 1
                self._msgs_processed_window.append(time.time())
        else:
            with self._metrics_lock:
                self._total_depletions += 1

        return ok

    def is_battery_charged(self, battery_idx: int) -> bool:
        """Check if a worker's battery has charge."""
        if battery_idx >= len(self.batteries):
            return True
        return self.batteries[battery_idx].is_charged

    # ─── Energy Input (Loop 3) ────────────────────────────────────────────

    def receive_energy(self, amount: float, source: str = "paradox"):
        """Receive energy from external source (paradox pulse, etc.).

        Loop 3: Energy amplified by time compression before distribution.
        Batteries with lower charge get proportionally more energy.
        """
        amplified = amount * self.time_compression
        self._total_energy_received += amplified

        # Distribute weighted by need
        total_need = sum(
            b.max_charge - b.charge_level for b in self.batteries
        )
        if total_need <= 0:
            return

        for b in self.batteries:
            need = b.max_charge - b.charge_level
            if need > 0:
                share = amplified * (need / total_need)
                b.charge(share, source=source)

    # ─── Tick Loop (compressed time) ──────────────────────────────────────

    def start(self):
        """Start the farm's background tick loop for recharge."""
        if self._running:
            return
        self._running = True

        self._tick_thread = threading.Thread(
            target=self._tick_loop,
            daemon=True,
            name="postal-farm-tick",
        )
        self._tick_thread.start()
        print(f"[PostalFarm] Started: {self.num_batteries} batteries, "
              f"max_charge={self._max_charge}, "
              f"compression_coeff={self.compression_coeff}, "
              f"base_handler_cost={self.base_handler_cost}")

    def stop(self):
        """Stop the farm's background loop."""
        self._running = False

    def _tick_loop(self):
        """Background tick loop with time-compressed recharge.

        Loop 1: Time compression → more recharge ticks per outer tick.
        At gravity=16, compression=65x → 65 recharge iterations per outer tick.
        """
        import random as _rng
        interval = 1.0 / self.base_hz
        while self._running:
            try:
                compression = self.time_compression
                full_ticks = int(compression)
                frac = compression - full_ticks

                for _ in range(full_ticks):
                    for b in self.batteries:
                        b.tick_recharge()

                # Probabilistic fractional tick
                if _rng.random() < frac:
                    for b in self.batteries:
                        b.tick_recharge()

                time.sleep(interval)
            except Exception as e:
                print(f"[PostalFarm] Tick error: {e}")
                time.sleep(0.1)

    # ─── Status & Diagnostics ─────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Full farm status for monitoring and dashboard."""
        charged = sum(1 for b in self.batteries if b.is_charged)
        return {
            "num_batteries": self.num_batteries,
            "charged": charged,
            "gravity": round(self.gravity, 3),
            "time_compression": round(self.time_compression, 1),
            "cost_reduction": round(self.cost_reduction, 1),
            "effective_hz": round(self.effective_hz, 1),
            "message_mass": round(self.message_mass, 1),
            "running": self._running,
            "uptime_sec": round(time.time() - self._start_ts, 1),
            "totals": {
                "dispatches": self._total_dispatches,
                "depletions": self._total_depletions,
                "energy_received": round(self._total_energy_received, 4),
            },
            "batteries": [b.status() for b in self.batteries],
        }

    def summary(self) -> str:
        """One-line summary for logging."""
        charged = sum(1 for b in self.batteries if b.is_charged)
        return (
            f"[PostalFarm] {charged}/{self.num_batteries} charged, "
            f"gravity={self.gravity:.1f}, "
            f"compression={self.time_compression:.0f}x, "
            f"mass={self.message_mass:.0f} msg/s, "
            f"dispatches={self._total_dispatches}"
        )
