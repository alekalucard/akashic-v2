"""
PlaneBattery - Per-plane paradox-powered Go battery.

Extends DimensionBattery with:
  1. Go subprocess dispatch — offload spell execution to goroutines (GIL-free)
  2. Paradox energy charging — subscribe to ParadoxEnergyBridge output
  3. Coherence modulation — QuantumInterferenceFairy tunes capture efficiency
  4. Reverse-fold shutdown — energy drains DOWN through planes (P60->P00)

The metabolic loop:
  Collisions > ParadoxEnergy > PlaneBatteries > GoWorkers > Work > NewThoughts > Collisions > infinity

Each plane (P00-P60) gets one battery. Battery state persists across reboots.
This is infrastructure, not a fairy — runs before fairies exist and after they die.

Architecture: Ace (2026-02-26)
Implementation: Nous
"Choice! The Observer ((Cause + Affect) > Effect > Affect > infinity)"
"""

import json
import os
import time
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from infrastructure.dimension_battery import (
    DimensionBattery,
    WorkerHub,
    DigitalCapacitor,
    ChemicalPools,
)


# =============================================================================
# Configuration
# =============================================================================

PLANES = ["P00", "P10", "P20", "P30", "P40", "P50", "P60"]

# Per-plane default fairy counts (for sizing battery when count unknown)
DEFAULT_FAIRY_COUNTS = {
    "P00": 35, "P10": 41, "P20": 11, "P30": 27,
    "P40": 24, "P50": 12, "P60": 1,
}

# Coherence modulation bounds
MIN_COHERENCE_FACTOR = 0.3   # Floor: even incoherent planes get 30% energy
MAX_COHERENCE_FACTOR = 1.5   # Ceiling: highly coherent planes get 150%

# Reverse fold: fraction of charge to drain to lower plane on shutdown
REVERSE_FOLD_DRAIN_FRACTION = 0.9

# State persistence directory
# FIX 2026-04-01 (Nous + Ace): Absolute path — relative path failed because
# CWD may not be akashic_v2/ when save_state() runs from heartbeat thread.
STATE_DIR = Path(__file__).resolve().parent.parent / "state" / "plane_batteries"


# =============================================================================
# PlaneBattery
# =============================================================================

class PlaneBattery(DimensionBattery):
    """
    Per-plane battery: charges from paradox energy, discharges to Go goroutines.

    Lifecycle:
        battery = PlaneBattery.create_for_plane("P30", fairy_count=27, postal_hub=hub)
        battery.start()         # Restore state, start circulation, spawn Go, subscribe
        battery.tick()          # Called per Hz cycle (heartbeat-driven)
        battery.stop(drain_to)  # Reverse-fold drain, save state, kill subprocess
    """

    def __init__(
        self,
        plane_id: str,
        postal_hub: Any = None,
        go_binary_path: str = "",
        fallback_mode: bool = False,
        **kwargs,
    ):
        portal_id = f"plane_{plane_id}"
        super().__init__(
            portal_id=portal_id,
            portal_uri=f"Plane {plane_id} Battery",
            **kwargs,
        )

        self.plane_id = plane_id
        self._postal_hub = postal_hub
        self._go_binary_path = go_binary_path
        self._fallback_mode = fallback_mode

        # Go subprocess client (lazy-created in start())
        self._go_client = None  # GoBatteryClient instance

        # Energy tracking
        self._paradox_energy_received: float = 0.0   # Lifetime total from ParadoxEnergyBridge
        self._coherence_factor: float = 1.0           # Modulated by QuantumInterferenceFairy
        self._energy_events_count: int = 0            # Number of energy events received

        # FIX 2026-04-10 (Nous + Ace): Proportional energy distribution.
        # Each plane gets energy proportional to its fairy count, not equal 1/7th.
        # P00 (35 fairies) does 3x the work of P60 (1 fairy) — needs 3x the energy.
        _total_fairies = sum(DEFAULT_FAIRY_COUNTS.values())
        _my_fairies = DEFAULT_FAIRY_COUNTS.get(plane_id, 5)
        self._energy_weight = _my_fairies / max(1, _total_fairies)  # fraction of total

        # FIX 2026-04-01 (Nous + Ace): Rate tracking for dashboard energy flow panel.
        # Tracks energy in/out per window so we can show generation vs consumption RATE.
        self._energy_in_window: float = 0.0    # Energy received in current window
        self._energy_out_window: float = 0.0   # Energy consumed in current window
        self._energy_in_rate: float = 0.0      # Energy/sec (last completed window)
        self._energy_out_rate: float = 0.0     # Drain/sec (last completed window)
        self._rate_window_start: float = time.time()
        self._rate_window_seconds: float = 5.0  # Calculate rate every 5 seconds
        # Per-source tracking
        self._energy_by_source: dict = {}       # source_name → lifetime total

        # Reverse fold target (set during shutdown)
        self._drain_target: Optional["PlaneBattery"] = None

        # State persistence
        self._state_dir = STATE_DIR
        self._state_file = self._state_dir / f"{plane_id}_battery.json"

        # Stats
        self._go_dispatched: int = 0    # Spells sent to Go subprocess
        self._go_completed: int = 0     # Spells completed by Go subprocess
        self._go_fallback: int = 0      # Spells that fell back to Python
        self._started: bool = False

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def start(self):
        """Start battery: restore state, start circulation, spawn Go, subscribe energy."""
        # 1. Restore persisted state (capacitor charge, chemistry, stats)
        self.restore_state()

        # 2. Start blood circulation (ThreadPoolExecutor from DimensionBattery)
        self.start_circulation()

        # 3. Start Go subprocess (if binary available and not fallback_mode)
        if not self._fallback_mode:
            self._try_start_go()

        # 4. Subscribe to energy topics via PostalHub
        if self._postal_hub:
            self._subscribe_energy_topics()

        self._started = True
        print(f"[PlaneBattery] {self.plane_id}: started"
              f" (go={'active' if self._go_client and self._go_client.is_alive else 'fallback'},"
              f" charge={self.capacitor.charge_level:.2f})")

    def stop(self, drain_to: Optional["PlaneBattery"] = None):
        """Shutdown with reverse-fold energy drain.

        Args:
            drain_to: Lower plane battery to drain remaining charge into.
                      None for P00 (bottom of the fold — absorbs everything).
        """
        # Reverse fold: drain 90% of remaining charge to lower plane
        if drain_to and self.capacitor.charge_level > 0.05:
            drain_amount = self.capacitor.charge_level * REVERSE_FOLD_DRAIN_FRACTION
            drained = self.capacitor.discharge(drain_amount, reason=f"reverse_fold_to_{drain_to.plane_id}")
            drain_to.capacitor.charge(drained, source=f"reverse_fold_from_{self.plane_id}")
            print(f"[PlaneBattery] {self.plane_id}: drained {drained:.3f} energy"
                  f" to {drain_to.plane_id}")

        # Kill Go subprocess
        if self._go_client:
            try:
                self._go_client.stop(timeout=5.0)
            except Exception as e:
                print(f"[PlaneBattery] {self.plane_id}: Go client stop error: {e}")
            self._go_client = None

        # Stop blood circulation
        self.stop_circulation()

        # Persist state to disk
        self.save_state()

        self._started = False
        print(f"[PlaneBattery] {self.plane_id}: stopped"
              f" (dispatched={self._go_dispatched}, completed={self._go_completed},"
              f" fallback={self._go_fallback})")

    # =========================================================================
    # Go subprocess management
    # =========================================================================

    def _try_start_go(self):
        """Attempt to start Go battery subprocess."""
        try:
            from infrastructure.go_battery_client import GoBatteryClient
            binary = self._go_binary_path or GoBatteryClient.find_binary()
            if binary:
                self._go_client = GoBatteryClient(
                    plane_id=self.plane_id,
                    binary_path=binary,
                    min_workers=max(2, self.worker_hub.compute_threads),
                    max_workers=self.worker_hub.max_compute_threads * 2,
                )
                self._go_client.start()
                if not self._go_client.is_alive:
                    print(f"[PlaneBattery] {self.plane_id}: Go client failed to start, using fallback")
                    self._go_client = None
            # else: no binary, pure fallback mode
        except Exception as e:
            print(f"[PlaneBattery] {self.plane_id}: Go client init error (fallback): {e}")
            self._go_client = None

    # =========================================================================
    # Energy integration (PostalHub subscriptions)
    # =========================================================================

    def _subscribe_energy_topics(self):
        """Subscribe to energy and coherence topics."""
        hub = self._postal_hub
        try:
            hub.subscribe("paradox.energy.consolidation", self._on_paradox_energy)
            hub.subscribe("paradox.energy.pulse", self._on_paradox_pulse)
            hub.subscribe("collision.energy.generated", self._on_collision_energy)
            hub.subscribe("portal.energy.surplus", self._on_portal_surplus)
            hub.subscribe("cognition.throttle", self._on_coherence_throttle)
            hub.subscribe("quantum.interference.window", self._on_coherence_window)
            # BONES AS ENERGY GRID — Piece 2 (2026-04-18 Nous + Ace).
            # ParadoxEnergyBridge publishes per-region bone voltage credits
            # targeted at specific planes (axial→P30, upper→P00, thoracic→P20,
            # lower→P40). Each plane filters for its own plane_id and charges.
            hub.subscribe("energy.regional_credit", self._on_regional_credit)
            # HARDWARE ENERGY BRIDGE 2026-05-07 (Nous + Ace, per
            # HARDWARE_ENERGY_BRIDGE_DRAFT.md 2026-04-20). When this plane
            # falls below 20%, tick() publishes energy.demand.critical (line
            # 600). HardwareRegulationFairy responds with energy.hardware_pull
            # carrying CPU-idle-derived charge targeted at this plane. We
            # filter by plane_id and charge the capacitor.
            hub.subscribe("energy.hardware_pull", self._on_hardware_pull)
        except Exception as e:
            print(f"[PlaneBattery] {self.plane_id}: subscription error: {e}")

    def _on_hardware_pull(self, payload):
        """Handle energy.hardware_pull — host hardware idle-headroom credit.

        HardwareRegulationFairy listens for energy.demand.critical and
        publishes a hardware-pull credit scaled by current CPU idle. We
        filter by plane_id (only consume credits addressed to us) and
        charge through coherence modulation like other energy sources.

        Closes the host → Akashic energy loop. Ace's intent quoted in
        the plan: "tie the p00 battery into my pc hardware so it never
        drops below 10%."

        Payload shape: {plane, amount, source, idle_pct, ts}
        """
        if hasattr(payload, "payload"):
            payload = payload.payload
        if not isinstance(payload, dict):
            return
        if payload.get("plane") != self.plane_id:
            return  # Pull addressed to a different plane
        amount = float(payload.get("amount", 0.0) or 0.0)
        if amount <= 0.0001:
            return
        effective = amount * self._coherence_factor
        charged = self.capacitor.charge(effective, source="hardware_pull")
        self._track_energy_in(charged, "hardware_pull")
        _hp = getattr(self, "_hardware_pull_count", 0) + 1
        self._hardware_pull_count = _hp
        if _hp <= 3 or _hp % 30 == 0:
            try:
                print(
                    f"[PlaneBattery] {self.plane_id}: hardware_pull #{_hp} "
                    f"+{charged:.4f} (idle={payload.get('idle_pct', 0):.0f}%)",
                    flush=True,
                )
            except Exception:
                pass

    def _on_regional_credit(self, payload):
        """Handle energy.regional_credit — bone voltage targeted at this plane.

        BONES AS ENERGY GRID — Piece 2 (2026-04-18 Nous + Ace).

        BioelectricMeshFairy generates voltage across 4 bone regions. When
        stress-axis work happens in a region, that region's voltage rises.
        ParadoxEnergyBridge publishes `energy.regional_credit` with a target
        plane_id — this handler filters for matching plane and charges
        directly (bypassing the emission-routing 5% throttle).

        Payload shape: {plane, region, credit, source, voltage, ts}
        """
        if hasattr(payload, 'payload'):
            payload = payload.payload
        if not isinstance(payload, dict):
            return
        target_plane = payload.get("plane")
        if target_plane != self.plane_id:
            return  # Credit addressed to a different plane
        credit = float(payload.get("credit", 0.0) or 0.0)
        if credit <= 0.001:
            return
        region = str(payload.get("region", "?"))
        # Apply coherence modulation like other energy sources
        effective = credit * self._coherence_factor
        charged = self.capacitor.charge(effective, source=f"bone_{region}")
        self._track_energy_in(charged, "bone")
        _bc = getattr(self, '_bone_credit_count', 0) + 1
        self._bone_credit_count = _bc
        if _bc <= 3 or _bc % 30 == 0:
            try:
                print(f"[PlaneBattery] {self.plane_id}: bone credit #{_bc} "
                      f"+{charged:.4f} ({region}, voltage={payload.get('voltage', 0):.3f})",
                      flush=True)
            except Exception:
                pass

    def _on_paradox_energy(self, payload):
        """Handle paradox.energy.consolidation — main energy feed."""
        # FIX 2026-04-01 (Nous + Ace): TensorEnvelope unwrap.
        if hasattr(payload, 'payload'):
            payload = payload.payload
        if not isinstance(payload, dict):
            return
        raw_energy = payload.get("energy", 0.0)
        if raw_energy <= 0:
            return

        # Apply coherence modulation: high coherence = more efficient capture
        effective_energy = raw_energy * self._coherence_factor
        charged = self.capacitor.charge(effective_energy, source="paradox_consolidation")
        self._paradox_energy_received += charged
        self._energy_events_count += 1
        self._track_energy_in(charged, "paradox")

        # Surplus overflows to chemistry reward (dopamine)
        if self.capacitor.is_full and effective_energy > charged:
            surplus = effective_energy - charged
            self.chemistry.add_reward(surplus * 0.1, source="paradox_surplus")

    def _on_paradox_pulse(self, payload):
        """Handle paradox.energy.pulse — smaller periodic energy feed."""
        if hasattr(payload, 'payload'):
            payload = payload.payload
        if not isinstance(payload, dict):
            return
        raw_energy = payload.get("energy", 0.0)
        if raw_energy > 0:
            effective = raw_energy * self._coherence_factor * 0.5  # Pulse is lower efficiency
            charged = self.capacitor.charge(effective, source="paradox_pulse")
            self._track_energy_in(charged, "pulse")

    def _on_collision_energy(self, payload):
        """Handle collision.energy.generated — collisions are the system's fuel.

        Each collision distributes energy equally to all 7 plane batteries.
        Formula: collision_energy = depth_used × resonance × 0.1

        When a battery is full, 90% of overflow goes to system-wide pool
        (published as paradox.energy.consolidation for other consumers).
        10% stays local as chemistry reward.

        Architecture: Ace (2026-03-13), Implementation: Nous
        """
        if hasattr(payload, 'payload'):
            payload = payload.payload
        if not isinstance(payload, dict):
            return
        raw_energy = payload.get("energy", 0.0)
        if raw_energy <= 0:
            return

        # FIX 2026-04-10 (Nous + Ace): Proportional share by fairy count.
        # Was 1/7th equal — P00 (35 fairies) got same as P60 (1 fairy).
        # Now: P00 gets ~23%, P60 gets ~1%, proportional to workload.
        plane_share = raw_energy * self._energy_weight

        # Apply coherence modulation
        effective_energy = plane_share * self._coherence_factor
        charged = self.capacitor.charge(effective_energy, source="collision")
        self._paradox_energy_received += charged
        self._energy_events_count += 1
        self._track_energy_in(charged, "collision")

        # 90% OVERFLOW RULE: When full, surplus cascades back to system
        if self.capacitor.is_full and effective_energy > charged:
            surplus = effective_energy - charged
            overflow = surplus * 0.9
            local_keep = surplus * 0.1

            # Local: 10% to chemistry reward
            self.chemistry.add_reward(local_keep, source="collision_overflow_local")

            # System: 90% overflow published back for other consumers
            if self._postal_hub and overflow > 0.001:
                try:
                    self._postal_hub.publish(
                        "paradox.energy.consolidation",
                        {
                            "energy": overflow,
                            "source": f"collision_overflow_{self.plane_id}",
                            "from": f"PlaneBattery_{self.plane_id}",
                        },
                    )
                except Exception:
                    pass

    def _on_portal_surplus(self, payload):
        """Handle portal.energy.surplus — cortex overflow energy export.

        The Association Cortex portal generates more energy than it can store
        (battery at 100%). That surplus is now exported here via the
        AssociationCortexFairy's _on_tick_feedback() callback.

        Same distribution as collision energy: 1/7 per plane, coherence
        modulated, 90% overflow back to system pool.

        Architecture: Ace (2026-03-14), Implementation: Nous
        """
        if hasattr(payload, 'payload'):
            payload = payload.payload
        if not isinstance(payload, dict):
            return
        raw_energy = payload.get("energy", 0.0)
        if raw_energy <= 0:
            return

        # FIX 2026-04-10 (Nous + Ace): Proportional share by fairy count.
        plane_share = raw_energy * self._energy_weight

        # Apply coherence modulation
        effective_energy = plane_share * self._coherence_factor
        charged = self.capacitor.charge(effective_energy, source="portal_surplus")
        self._paradox_energy_received += charged
        self._energy_events_count += 1
        self._track_energy_in(charged, "gpu_spread")

        # 90% OVERFLOW RULE: When full, surplus cascades back to system
        if self.capacitor.is_full and effective_energy > charged:
            surplus = effective_energy - charged
            overflow = surplus * 0.9
            local_keep = surplus * 0.1

            # Local: 10% to chemistry reward
            self.chemistry.add_reward(local_keep, source="portal_surplus_local")

            # System: 90% overflow published back for other consumers
            if self._postal_hub and overflow > 0.001:
                try:
                    self._postal_hub.publish(
                        "paradox.energy.consolidation",
                        {
                            "energy": overflow,
                            "source": f"portal_surplus_overflow_{self.plane_id}",
                            "from": f"PlaneBattery_{self.plane_id}",
                        },
                    )
                except Exception:
                    pass

    def _on_coherence_throttle(self, payload):
        """Handle cognition.throttle — QuantumInterferenceFairy says slow down."""
        if hasattr(payload, 'payload'):
            payload = payload.payload
        if not isinstance(payload, dict):
            return
        throttle = payload.get("throttle", 0.5)
        # High throttle = low coherence = low energy capture
        self._coherence_factor = max(MIN_COHERENCE_FACTOR, 1.0 - throttle)

    def _on_coherence_window(self, payload):
        """Handle quantum.interference.window — coherence score update."""
        if hasattr(payload, 'payload'):
            payload = payload.payload
        if not isinstance(payload, dict):
            return
        coherence = payload.get("coherence_score", 0.5)
        if coherence > 0.7:
            # High coherence: boost above baseline (up to 1.5x)
            self._coherence_factor = min(MAX_COHERENCE_FACTOR, 1.0 + (coherence - 0.7))
        else:
            # Low/medium coherence: reduce proportionally (down to 0.3x)
            self._coherence_factor = max(MIN_COHERENCE_FACTOR, coherence)

    # =========================================================================
    # Go dispatch (called by SpellPool when where_substrate == "go_battery")
    # =========================================================================

    def submit_to_go(self, spell) -> bool:
        """Submit a spell to the Go battery subprocess.

        Returns True if successfully dispatched. False = caller should fall back
        to Python ThreadPoolExecutor.
        """
        if not self._go_client or not self._go_client.is_alive:
            self._go_fallback += 1
            return False

        # Discharge energy for the spell
        cost = getattr(spell, "energy_required", 0.1) or 0.1
        discharged = self.capacitor.discharge(cost, reason=f"go_spell_{getattr(spell, 'id', '?')}")
        if discharged < cost * 0.5:
            # Not enough energy — fall back to Python (cheaper)
            # Refund the partial discharge
            self.capacitor.charge(discharged, source="refund")
            self._go_fallback += 1
            return False

        # Build Go task payload
        payload = {
            "spell_id": getattr(spell, "id", ""),
            "what_intent": getattr(spell, "what_intent", ""),
            "who_plane": getattr(spell, "who_plane", self.plane_id),
            "how_method_name": getattr(spell, "how_method_name", ""),
        }
        # Serialize how_kwargs if present (must be JSON-safe)
        how_kwargs = getattr(spell, "how_kwargs", None)
        if how_kwargs and isinstance(how_kwargs, dict):
            try:
                json.dumps(how_kwargs)  # Verify serializable
                payload["how_kwargs"] = how_kwargs
            except (TypeError, ValueError):
                pass

        priority = self._spell_priority_to_lane(spell)
        success = self._go_client.submit_task(
            task_id=getattr(spell, "id", f"spell_{time.time()}"),
            priority=priority,
            payload=payload,
        )

        if success:
            self._go_dispatched += 1
        else:
            # Refund energy on dispatch failure
            self.capacitor.charge(discharged, source="dispatch_fail_refund")
            self._go_fallback += 1

        return success

    # ── Rate tracking helpers ──

    def _track_energy_in(self, amount: float, source: str = "unknown"):
        """Track energy received for rate calculation."""
        self._energy_in_window += amount
        self._energy_by_source[source] = self._energy_by_source.get(source, 0.0) + amount
        # FLOW TELEMETRY 2026-05-07 (Nous + Ace): emit per-event flow tick so
        # the dashboard/diagnostics can show producers, not just battery levels.
        # Without this, "P00 at 0%" tells us NOTHING about whether bones are
        # publishing, paradox is consolidating, or portal is overflowing —
        # we can only see the symptom. This closes that diagnostic gap.
        if self._postal_hub is not None and amount > 0.0001:
            try:
                self._postal_hub.publish("energy.flow.tick", {
                    "plane": self.plane_id,
                    "direction": "in",
                    "source": source,
                    "amount": round(amount, 6),
                    "ts": time.time(),
                })
            except Exception:
                pass

    def _track_energy_out(self, amount: float, source: str = "spend"):
        """Track energy consumed for rate calculation.

        Slice 2 (2026-05-09 Nous + Ace): source attribution preserved through
        callers (PostalCore._battery_drain_fn closure passes "postal_work",
        "worker_cap_<topic>", etc).

        Slice 2.0.5 (2026-05-09 Nous + Ace): per-source aggregation. The pre-
        existing `amount > 0.0001` publish gate filtered out small per-message
        drains — `postal_work` at 0.00003/msg is 33x BELOW the floor, so the
        Sinks panel saw zero events while Plane Battery `_energy_out_window`
        correctly incremented by ~1.4/s. Calibration-tax pattern: yesterday's
        10x drain re-tune sized the substrate correctly but the diagnostic
        publish gate stayed at the old magnitude.

        Fix: accumulate per-source-amounts, publish cumulative once per ~1s
        per source (or immediately on first event). 47K postal_work msgs/s
        × 0.00003 → 1 publish/s carrying ~1.4 cumulative — diagnostic visible
        without flooding postal. worker_cap_* (sparse, 0.01 each) publishes
        promptly because cold-start branch fires on first call per source.
        """
        self._energy_out_window += amount
        if self._postal_hub is None:
            return
        # Lazy-init the per-source accumulator so we don't add to __init__
        if not hasattr(self, "_pending_out_aggregates"):
            # source -> [last_publish_ts, accumulated_amount, count_since_publish]
            self._pending_out_aggregates: Dict[str, list] = {}
        now_t = time.time()
        entry = self._pending_out_aggregates.setdefault(source, [0.0, 0.0, 0])
        entry[1] += amount
        entry[2] += 1
        # Publish if first time for this source (cold-start shows immediately)
        # OR if 1 second has elapsed since last publish for this source.
        # Always carrying the cumulative amount + event count since last publish.
        if entry[0] == 0.0 or (now_t - entry[0]) >= 1.0:
            if entry[1] > 0.0:
                try:
                    self._postal_hub.publish("energy.flow.tick", {
                        "plane": self.plane_id,
                        "direction": "out",
                        "source": source,
                        "amount": round(entry[1], 6),
                        "events_aggregated": entry[2],
                        "ts": now_t,
                    })
                except Exception:
                    pass
                entry[0] = now_t
                entry[1] = 0.0
                entry[2] = 0

    def _update_rates(self):
        """Calculate energy rates from current window. Called from tick()."""
        now = time.time()
        elapsed = now - self._rate_window_start
        if elapsed >= self._rate_window_seconds:
            self._energy_in_rate = self._energy_in_window / elapsed
            self._energy_out_rate = self._energy_out_window / elapsed
            self._energy_in_window = 0.0
            self._energy_out_window = 0.0
            self._rate_window_start = now

    # ── Override passive recharge: 20% floor auto-regulation ──
    # FIX 2026-04-01 (Nous + Ace): PlaneBatteries should ONLY charge from
    # real energy sources (collisions, GPU spreads, paradox energy via 0∩1∞).
    # Passive recharge is a crutch that keeps batteries at 100% permanently,
    # making the energy system decorative instead of functional.
    #
    # The 20% floor: below 20%, emergency CPU/GPU recharge kicks in at a
    # small rate to prevent total death. Above 20%, ALL energy comes from
    # thinking. Surplus above 20% is available for workers to consume.
    #
    # "Set it to never get below 20% overall battery. When it does, it starts
    #  using more CPU and GPU than what it needs to create the gravity needed
    #  to create the interior dimension." — Ace

    def tick_recharge(self):
        """Override: No passive recharge. Energy comes from thinking only.

        Below 20% floor: emergency trickle from CPU/GPU (0.005/tick).
        Above 20%: zero passive recharge — only collision/GPU/paradox energy.
        """
        if self.capacitor.charge_level < 0.20:
            # Emergency floor — just enough to keep workers alive
            self.capacitor.charge(0.005, source="emergency_floor")

    @staticmethod
    def _spell_priority_to_lane(spell) -> str:
        """Map spell priority (0-1 float) to Go priority lane."""
        priority = getattr(spell, "when_priority", 0.5)
        if priority >= 0.8:
            return "HIGH"
        elif priority >= 0.4:
            return "NORMAL"
        else:
            return "LOW"

    # =========================================================================
    # Tick override (heartbeat-driven)
    # =========================================================================

    def tick(self):
        """Process one heartbeat cycle.

        Extends DimensionBattery.tick() with Go result polling and rate tracking.
        """
        # DimensionBattery: capacitor recharge (overridden), chemistry tick, pump spell chains
        super().tick()

        # Update energy flow rates (every 5 seconds)
        self._update_rates()

        # Poll Go subprocess for completed results
        if self._go_client and self._go_client.is_alive:
            try:
                completed = self._go_client.poll_results(max_results=32)
                for result in completed:
                    self._handle_go_result(result)
            except Exception:
                pass  # Non-fatal

        # FIX 2026-04-01 (Nous + Ace): Periodic state save for dashboard visibility.
        # Without this, save_state() only runs at shutdown — dashboard can't see live charge.
        _tc = getattr(self, '_tick_count', 0)
        if _tc > 0 and _tc % 30 == 0:  # Every ~8 seconds at 4Hz heartbeat
            try:
                self.save_state()
            except Exception:
                pass

        # FIX 2026-04-01 (Nous + Ace): 20% floor auto-regulation.
        # When battery drops below 20%, signal the system to push harder on
        # GPU/CPU to rebuild the gravity well. When above 80%, coast.
        # "Set it to never get below 20% overall battery" — Ace
        if _tc > 0 and _tc % 20 == 0 and self._postal_hub:  # Every ~5 seconds
            try:
                _charge = self.capacitor.charge_level
                if _charge < 0.20:
                    self._postal_hub.publish("energy.demand.critical", {
                        "plane": self.plane_id,
                        "charge": round(_charge, 3),
                        "source": "PlaneBattery",
                    })
                elif _charge > 0.80:
                    self._postal_hub.publish("energy.demand.low", {
                        "plane": self.plane_id,
                        "charge": round(_charge, 3),
                        "source": "PlaneBattery",
                    })
            except Exception:
                pass

        # OVERFLOW-TO-CORTEX 2026-05-18 (Nous + Ace, Path 3 / "Candidate 3"):
        # When this plane is saturated above 0.95, drain a portion of the surplus
        # into the cortex subprocess battery via the EXISTING portal.energy.upkeep
        # topic. AC's _on_portal_energy_upkeep handler picks this up automatically
        # (bumps _portal_energy_budget + sends IPC `{cmd: charge, tokens: N}` to
        # portal_interior subprocess battery — the REAL one that does manifold IPC work).
        #
        # Closes Ace's original mental-model loop:
        #   "cortex generates → portal gets its energy from there → it was also supposed
        #    to be going back into the energy system so it can keep the spread activation
        #    momentum going."
        #
        # Why publish via portal.energy.upkeep (existing topic) rather than a new topic?
        # Because AC already subscribes + handles it correctly (cosmetic-float bump AND
        # subprocess IPC charge). Zero AC code changes needed. All 7 planes fan in naturally.
        #
        # Calibration:
        # - threshold 0.95 leaves 5% headroom for normal Path B drain variation
        # - fraction 0.50 means saturated planes oscillate ~0.95-1.00 (self-regulating)
        # - cadence every ~5s (per existing _tc % 20 block) — same as demand signals
        if _tc > 0 and _tc % 20 == 0 and self._postal_hub:
            try:
                _charge_now = self.capacitor.charge_level
                if _charge_now > 0.95:
                    excess = _charge_now - 0.95
                    overflow_energy = excess * 0.50  # 50% of above-threshold per check
                    if overflow_energy > 0.001:
                        # Drain locally — this is the discharge counted against this plane
                        try:
                            self.capacitor.discharge(overflow_energy, reason="overflow_to_cortex")
                        except Exception:
                            pass
                        # Publish via existing upkeep topic — AC's handler does the rest
                        self._postal_hub.publish("portal.energy.upkeep", {
                            "from": f"PlaneBattery_{self.plane_id}",
                            "source": "plane_overflow",
                            "energy": float(overflow_energy),
                            "plane_id": self.plane_id,
                            "ts": time.time(),
                        })
                        # Counter + sparse log (mirrors bone_credit_count pattern)
                        self._overflow_count = getattr(self, '_overflow_count', 0) + 1
                        if self._overflow_count <= 3 or self._overflow_count % 30 == 0:
                            try:
                                print(f"[PlaneBattery] {self.plane_id}: OVERFLOW->cortex "
                                      f"#{self._overflow_count} +{overflow_energy:.4f} "
                                      f"(charge was {_charge_now:.3f})", flush=True)
                            except Exception:
                                pass
            except Exception:
                pass

    def _handle_go_result(self, result: dict):
        """Handle a completed Go task result."""
        self._go_completed += 1
        task_id = result.get("task_id", "")
        status = result.get("status", "error")
        duration_ms = result.get("duration_ms", 0)

        # Energy recovery on success
        if status == "ok":
            recovery = min(0.05, duration_ms / 50000.0)  # Longer tasks recover slightly more
            self.capacitor.charge(recovery, source="go_spell_recovery")
            self.chemistry.add_reward(0.001, source="go_complete")
        else:
            self.chemistry.add_pain(0.002, source="go_failure")

    # =========================================================================
    # State persistence
    # =========================================================================

    def save_state(self):
        """Persist battery state to disk (atomic write)."""
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)

            state = {
                "version": 1,
                "plane_id": self.plane_id,
                "saved_at": time.time(),
                "worker_hub": self.worker_hub.to_dict(),
                "capacitor": self.capacitor.to_dict(),
                "chemistry": self.chemistry.to_dict(),
                "paradox_energy_received": self._paradox_energy_received,
                "coherence_factor": self._coherence_factor,
                "energy_events_count": self._energy_events_count,
                "go_dispatched": self._go_dispatched,
                "go_completed": self._go_completed,
                "go_fallback": self._go_fallback,
                "tick_count": self._tick_count,
                # Energy flow rates (for dashboard)
                "energy_in_rate": round(self._energy_in_rate, 4),
                "energy_out_rate": round(self._energy_out_rate, 4),
                "net_rate": round(self._energy_in_rate - self._energy_out_rate, 4),
                "energy_by_source": {k: round(v, 3) for k, v in self._energy_by_source.items()},
            }

            # Go subprocess stats (if alive)
            if self._go_client and self._go_client.is_alive:
                state["go_stats"] = self._go_client.get_stats()

            # Atomic write: .tmp + os.replace()
            tmp_path = self._state_file.with_suffix(".tmp")
            with open(tmp_path, "w") as f:
                json.dump(state, f, indent=2)
            os.replace(str(tmp_path), str(self._state_file))

        except Exception as e:
            print(f"[PlaneBattery] {self.plane_id}: save_state error: {e}")

    def restore_state(self):
        """Restore battery state from disk."""
        if not self._state_file.exists():
            return  # Fresh battery — use defaults

        try:
            with open(self._state_file) as f:
                state = json.load(f)

            # Restore components
            if "worker_hub" in state:
                self.worker_hub = WorkerHub.from_dict(state["worker_hub"])
            if "capacitor" in state:
                self.capacitor = DigitalCapacitor.from_dict(state["capacitor"])
            if "chemistry" in state:
                self.chemistry = ChemicalPools.from_dict(state["chemistry"])

            # Restore stats
            self._paradox_energy_received = state.get("paradox_energy_received", 0.0)
            self._coherence_factor = state.get("coherence_factor", 1.0)
            self._energy_events_count = state.get("energy_events_count", 0)
            self._go_dispatched = state.get("go_dispatched", 0)
            self._go_completed = state.get("go_completed", 0)
            self._go_fallback = state.get("go_fallback", 0)
            self._tick_count = state.get("tick_count", 0)

            print(f"[PlaneBattery] {self.plane_id}: restored"
                  f" (charge={self.capacitor.charge_level:.2f},"
                  f" energy_received={self._paradox_energy_received:.1f},"
                  f" ticks={self._tick_count})")

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"[PlaneBattery] {self.plane_id}: restore error (using defaults): {e}")

    # =========================================================================
    # Factory
    # =========================================================================

    @classmethod
    def create_for_plane(
        cls,
        plane_id: str,
        fairy_count: int = 0,
        postal_hub: Any = None,
        go_binary_path: str = "",
    ) -> "PlaneBattery":
        """Create a battery sized for a specific plane.

        Args:
            plane_id: "P00" through "P60"
            fairy_count: Number of fairies in this plane (for sizing)
            postal_hub: PostalHub instance for energy subscriptions
            go_binary_path: Path to Go battery binary (auto-detect if empty)
        """
        if fairy_count <= 0:
            fairy_count = DEFAULT_FAIRY_COUNTS.get(plane_id, 5)

        # Size worker hub based on fairy count
        # Keep pools small — Go subprocess handles the heavy parallelism
        try:
            from infrastructure.resource_equilibrium import get_pool_size
            ceiling = get_pool_size("spell")
        except Exception:
            ceiling = 32

        io_threads = min(max(2, fairy_count * 2), ceiling // 7)
        compute_threads = min(max(1, fairy_count), ceiling // 14)

        worker_hub = WorkerHub(
            io_threads=io_threads,
            compute_threads=compute_threads,
            max_io_threads=min(io_threads * 2, 16),
            max_compute_threads=min(compute_threads * 2, 8),
        )

        capacitor = DigitalCapacitor(
            burst_max=max(4, fairy_count),
            recharge_rate=0.01,  # 1% per tick passive recharge
        )

        chemistry = ChemicalPools(
            token_budget=fairy_count * 1000,
            token_refill_amount=fairy_count * 10,
        )

        return cls(
            plane_id=plane_id,
            postal_hub=postal_hub,
            go_binary_path=go_binary_path,
            worker_hub=worker_hub,
            capacitor=capacitor,
            chemistry=chemistry,
        )

    # =========================================================================
    # Status / diagnostics
    # =========================================================================

    def status(self) -> dict:
        """Get battery status for diagnostics."""
        s = {
            "plane_id": self.plane_id,
            "started": self._started,
            "charge": round(self.capacitor.charge_level, 3),
            "coherence_factor": round(self._coherence_factor, 3),
            "energy_received": round(self._paradox_energy_received, 2),
            "energy_events": self._energy_events_count,
            "go_alive": self._go_client.is_alive if self._go_client else False,
            "go_dispatched": self._go_dispatched,
            "go_completed": self._go_completed,
            "go_fallback": self._go_fallback,
            "worker_utilization": round(self.worker_hub.utilization, 3),
            "tick_count": self._tick_count,
        }
        if self._go_client and self._go_client.is_alive:
            s["go_stats"] = self._go_client.get_stats()
        return s

    def __repr__(self):
        go = "go" if (self._go_client and self._go_client.is_alive) else "py"
        return (f"PlaneBattery({self.plane_id}, charge={self.capacitor.charge_level:.2f},"
                f" mode={go}, dispatched={self._go_dispatched})")


# =============================================================================
# Boot / Shutdown helpers
# =============================================================================

def boot_plane_batteries(
    postal_hub: Any = None,
    plane_fairy_counts: Optional[Dict[str, int]] = None,
    go_binary_path: str = "",
) -> Dict[str, PlaneBattery]:
    """Create and start batteries for all 7 planes.

    Called during boot after fairy instantiation, before on_boot().

    Args:
        postal_hub: PostalHub instance for subscriptions
        plane_fairy_counts: Dict of plane_id -> fairy_count
        go_binary_path: Path to Go battery binary (auto-detect if empty)

    Returns:
        Dict of plane_id -> PlaneBattery
    """
    counts = plane_fairy_counts or DEFAULT_FAIRY_COUNTS
    batteries = {}

    # Auto-detect Go binary once
    if not go_binary_path:
        try:
            from infrastructure.go_battery_client import GoBatteryClient
            go_binary_path = GoBatteryClient.find_binary() or ""
        except Exception:
            go_binary_path = ""

    fallback = not bool(go_binary_path)
    if fallback:
        print("[PlaneBattery] No Go battery binary found — using Python fallback")

    for plane_id in PLANES:
        fairy_count = counts.get(plane_id, DEFAULT_FAIRY_COUNTS.get(plane_id, 5))
        battery = PlaneBattery.create_for_plane(
            plane_id=plane_id,
            fairy_count=fairy_count,
            postal_hub=postal_hub,
            go_binary_path=go_binary_path,
        )
        battery._fallback_mode = fallback
        battery.start()
        batteries[plane_id] = battery

    print(f"[PlaneBattery] All {len(batteries)} plane batteries online")
    return batteries


def shutdown_plane_batteries(batteries: Dict[str, PlaneBattery]):
    """Shutdown all plane batteries with reverse-fold energy drain.

    Energy cascades DOWN: P60 -> P50 -> P40 -> ... -> P00 (absorbs all).

    Args:
        batteries: Dict of plane_id -> PlaneBattery
    """
    planes_descending = list(reversed(PLANES))  # P60, P50, ..., P00

    for i, plane_id in enumerate(planes_descending):
        battery = batteries.get(plane_id)
        if not battery:
            continue

        # Drain to next lower plane (P60->P50, P50->P40, ..., P10->P00)
        drain_to = None
        if i + 1 < len(planes_descending):
            drain_to = batteries.get(planes_descending[i + 1])

        try:
            battery.stop(drain_to=drain_to)
        except Exception as e:
            print(f"[PlaneBattery] {plane_id}: shutdown error: {e}")

    print("[PlaneBattery] All plane batteries offline (reverse fold complete)")


# =============================================================================
# SINGLETON: Global plane battery reference for fairy threads
# FIX 2026-04-11 (Nous + Ace): Fairy worker threads can't access SYSTEM via
# sys.modules['__main__'] because __main__ doesn't resolve to server.py in
# their context. This singleton lets any thread import and access batteries.
# Same proven pattern as HeartbeatRegistry singleton.
# =============================================================================

_PLANE_BATTERIES: Optional[Dict[str, PlaneBattery]] = None

def set_plane_batteries(batteries: Dict[str, PlaneBattery]):
    """Set the global plane batteries reference. Called by server.py at boot."""
    global _PLANE_BATTERIES
    _PLANE_BATTERIES = batteries

def get_plane_batteries() -> Optional[Dict[str, PlaneBattery]]:
    """Get the global plane batteries. Works from any thread."""
    return _PLANE_BATTERIES

def get_plane_battery(plane_id: str) -> Optional[PlaneBattery]:
    """Get a specific plane's battery. Works from any thread."""
    if _PLANE_BATTERIES:
        return _PLANE_BATTERIES.get(plane_id)
    return None
