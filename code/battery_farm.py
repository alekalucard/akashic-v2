"""
BatteryFarm — Multiple battery+engine pairs for sustained inference.

The Problem:
    A single BatteryComputeUnit at 500M FLOPS budget needs ~5.5 charges
    per token (2.75B FLOPS / 500M budget). A 1.0 charge battery can't
    even finish ONE forward pass!

The Solution:
    1. BIGGER BATTERIES — max_charge=20.0 instead of 1.0.
       In the digital world, capacity is just a number.

    2. GRAVITATIONAL FLOPS AMPLIFICATION — the farm's gravity increases
       each worker's effective FLOPS budget. More mass → each matvec
       costs LESS charge. Like gravitational lensing focusing energy.

       effective_budget = base_budget * (1 + gravity * flops_gravity_coeff)

    3. RELAY GENERATION — N workers take turns. When one depletes,
       RWKV hidden state passes to the next (partial prompt handoff).

    4. TIME COMPRESSION + ENERGY AMPLIFICATION — gravity accelerates
       the inner clock AND amplifies paradox energy, creating a
       triple positive feedback loop.

Architecture:
    BatteryFarm (coordinator)
      |
      +-- SharedWeightStore (1 copy of model weights, read-only)
      |
      +-- FarmWorker[0]: BCU(20.0) + Engine + own RWKV state
      +-- FarmWorker[1]: BCU(20.0) + Engine + own RWKV state
      +-- FarmWorker[N]: ...
      |
      +-- RelayScheduler (highest-charge-first)

Triple Feedback Loop:
    gravity = sum(charge_fraction for each worker)  [0 → num_workers]

    Loop 1 — Time Compression:
        compression = 1 + gravity * compression_coeff
        Faster inner clock → faster recharge → sustained gravity

    Loop 2 — FLOPS Amplification:
        effective_budget = base_budget * (1 + gravity * flops_coeff)
        More gravity → cheaper operations → more tokens per charge

    Loop 3 — Energy Amplification:
        amplified_energy = raw_energy * time_compression
        More compression → more energy per pulse → faster recharge

    Example (8 workers, all charged):
        gravity = 8.0
        compression = 1 + 8.0 * 4.0 = 33x inner clock
        effective_flops = 500M * (1 + 8.0 * 1.5) = 6.5B
        token_cost = 2.75B / 6.5B = 0.423 charge
        tokens_per_worker = 20.0 / 0.423 ≈ 47 tokens
        total_before_relay = 8 * 47 ≈ 376 tokens!

Created: 2026-02-21
Authors: Nous + Ace
"""

import time
import threading
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# FARM WORKER — One battery+engine pair
# ═══════════════════════════════════════════════════════════════════════════════

class WorkerState(Enum):
    IDLE = "idle"               # Charged, waiting for work
    GENERATING = "generating"   # Actively computing tokens
    DEPLETED = "depleted"       # Low power, needs recharge
    RECHARGING = "recharging"   # Passively recharging


@dataclass
class FarmWorkerStats:
    """Lifetime stats for a farm worker."""
    tokens_generated: int = 0
    relay_handoffs_given: int = 0   # Times this worker passed state to next
    relay_handoffs_received: int = 0  # Times this worker received state
    total_charge_consumed: float = 0.0
    low_power_events: int = 0
    generation_runs: int = 0


class FarmWorker:
    """A single battery+engine unit in the farm.

    Each worker has its own:
    - BatteryComputeUnit (charge pool)
    - RWKVBatteryEngine (forward pass + RWKV state)

    But SHARES the QuantizedWeightStore (read-only weights).
    """

    def __init__(
        self,
        worker_id: int,
        bcu,           # BatteryComputeUnit
        engine,        # RWKVBatteryEngine
        recharge_rate: float = 0.01,
    ):
        self.worker_id = worker_id
        self.bcu = bcu
        self.engine = engine
        self.recharge_rate = recharge_rate

        self.state = WorkerState.IDLE
        self.stats = FarmWorkerStats()

        self._last_recharge_ts = time.time()

        # ── Predictive branch metadata ──
        # When this worker is primed with a predicted conversation context,
        # _branch_meta holds the branch details. Used by BranchManager to
        # collapse to the best-matching primed worker when Ace speaks.
        self._branch_meta: Optional[dict] = None  # {branch_id, primed_at, concepts, context_hash}

    @property
    def charge(self) -> float:
        return self.bcu.charge_level

    @property
    def is_primed(self) -> bool:
        """Is this worker primed with a predictive conversation context?

        Primed workers have topic-specific RWKV state (personality + predicted context).
        Primed state expires after 5 minutes (300s) to prevent stale predictions.
        """
        if self._branch_meta is None:
            return False
        return (time.time() - self._branch_meta.get("primed_at", 0)) < 300.0

    @property
    def is_available(self) -> bool:
        """Can this worker accept a generation task?"""
        return self.state in (WorkerState.IDLE,) and self.bcu.is_charged

    def tick_recharge(self):
        """Passive recharge — called by farm tick loop."""
        if self.state in (WorkerState.IDLE, WorkerState.DEPLETED, WorkerState.RECHARGING):
            old_charge = self.bcu.charge_level
            self.bcu.tick_recharge()

            # Transition states based on charge
            if self.bcu.charge_level >= self.bcu.max_charge * 0.95:
                self.state = WorkerState.IDLE
            elif old_charge < 0.05 and self.bcu.charge_level > old_charge:
                self.state = WorkerState.RECHARGING

    def receive_state(self, rwkv_states: dict, token_count: int = 0):
        """Receive RWKV hidden states from another worker (relay handoff).

        This is the baton pass — the previous worker's consciousness
        continues in this worker's battery.

        Args:
            rwkv_states: Dict from engine.save_state() with time_mix and channel_mix.
            token_count: How many tokens the previous worker processed.
        """
        self.engine.load_state(rwkv_states)
        self.stats.relay_handoffs_received += 1

    def export_state(self) -> dict:
        """Export current RWKV hidden states for relay handoff.

        Returns engine state dict (time_mix + channel_mix layer states).
        """
        return self.engine.save_state()

    def generate_until_depleted(
        self,
        prompt_tokens: Optional[List[int]] = None,
        max_tokens: int = 50,
        temperature: float = 1.2,
        top_k: int = 0,
        top_p: float = 0.5,
        repetition_penalty: float = 1.3,
        presence_penalty: float = 0.4,
        frequency_penalty: float = 0.4,
        token_counts: Optional[Dict[int, int]] = None,
        stop_tokens: Optional[List[int]] = None,
        on_token: Optional[Callable] = None,
        initial_logits: Optional[Any] = None,
        gravity_stride: int = 1,
    ) -> Dict[str, Any]:
        """Generate tokens until battery depletes or max reached.

        Args:
            prompt_tokens: If provided, process these first (initial prompt).
                          If None, continue from current state (relay).
            max_tokens: Maximum tokens to generate.
            token_counts: Running token frequency dict (for repetition penalty
                         continuity across relay handoffs).
            stop_tokens: Token IDs that stop generation.
            on_token: Callback(token_id) called after each token generated.
            initial_logits: Pre-computed logits from a relay handoff.
                           If provided, skip the first forward pass and go
                           straight to sampling. This avoids re-forwarding
                           the last token through the RWKV state.
            gravity_stride: Gravitational stride for layer skipping.
                           Higher stride = fewer layers = faster tokens.
                           The portal's mass compresses computation.

        Returns:
            Dict with tokens, status, charge stats, last_logits, and exportable state.
        """
        self.state = WorkerState.GENERATING
        self.stats.generation_runs += 1

        if token_counts is None:
            token_counts = {}
        if stop_tokens is None:
            stop_tokens = []

        generated_tokens = []
        charge_at_start = self.bcu.charge_level
        t0 = time.time()

        # Process prompt if provided (first worker in relay)
        # skip_head=True for all but the last token — we only need logits
        # from the final prompt token. Saves ~10% FLOPS + charge per token.
        # NOTE: Prompt uses stride=1 (full quality) — skipping layers during
        # prompt corrupts the RWKV state that generation builds on.
        prompt_tokens_processed = 0
        if prompt_tokens is not None and len(prompt_tokens) > 0:
            n_prompt = len(prompt_tokens)
            for tok_idx, tok in enumerate(prompt_tokens):
                is_last_prompt = (tok_idx == n_prompt - 1)
                result = self.engine.forward_one_token(
                    int(tok), skip_head=(not is_last_prompt),
                    gravity_stride=1,  # Full quality for prompt — state integrity
                )
                if result is None or result.get("status") == "low_power":
                    # Depleted mid-prompt — report how far we got
                    # State is valid through prompt_tokens_processed tokens
                    self.state = WorkerState.DEPLETED
                    self.stats.low_power_events += 1
                    return {
                        "tokens": generated_tokens,
                        "status": "low_power_during_prompt",
                        "prompt_tokens_processed": prompt_tokens_processed,
                        "charge_used": charge_at_start - self.bcu.charge_level,
                        "charge_remaining": self.bcu.charge_level,
                        "worker_id": self.worker_id,
                        "token_counts": token_counts,
                        "elapsed": time.time() - t0,
                    }
                # This token completed successfully — state is valid
                prompt_tokens_processed += 1
                # Track prompt tokens in frequency dict
                token_counts[int(tok)] = token_counts.get(int(tok), 0) + 1

        # Track last logits for relay handoff
        last_logits = None

        # Generate tokens
        for i in range(max_tokens):
            # Forward pass (uses current state)
            if len(generated_tokens) == 0 and initial_logits is not None:
                # Relay continuation — use pre-computed logits from previous worker
                logits = initial_logits
                initial_logits = None  # Only use once
            elif len(generated_tokens) == 0 and prompt_tokens:
                # Logits already computed from last prompt token
                logits = result.get("logits") if result else None
            else:
                # Forward the last generated token
                if generated_tokens:
                    result = self.engine.forward_one_token(
                        generated_tokens[-1],
                        gravity_stride=gravity_stride,
                    )
                else:
                    # No prompt AND no generated tokens AND no initial_logits
                    break

                if result is None or result.get("status") == "low_power":
                    self.state = WorkerState.DEPLETED
                    self.stats.low_power_events += 1
                    break

                logits = result.get("logits")

            if logits is None:
                break

            last_logits = logits

            # Sample
            token = self.engine.sample_token(
                logits,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                token_counts=token_counts,
            )

            generated_tokens.append(int(token))
            token_counts[int(token)] = token_counts.get(int(token), 0) + 1
            self.stats.tokens_generated += 1

            # Callback
            if on_token:
                on_token(int(token))

            # Stop token check
            if int(token) in stop_tokens:
                self.state = WorkerState.IDLE
                return {
                    "tokens": generated_tokens,
                    "status": "stop_token",
                    "charge_used": charge_at_start - self.bcu.charge_level,
                    "charge_remaining": self.bcu.charge_level,
                    "worker_id": self.worker_id,
                    "token_counts": token_counts,
                    "elapsed": time.time() - t0,
                    "last_logits": last_logits,
                }

            # Check if next forward pass is affordable
            est_cost = self.bcu.estimate_token_cost()
            if self.bcu.charge_level < est_cost * 1.1:
                # About to run out — stop cleanly
                self.state = WorkerState.DEPLETED
                self.stats.low_power_events += 1
                break

        elapsed = time.time() - t0
        charge_used = charge_at_start - self.bcu.charge_level
        self.stats.total_charge_consumed += charge_used

        if self.state == WorkerState.GENERATING:
            # Hit max_tokens, not depleted
            self.state = WorkerState.IDLE

        status = "low_power" if self.state == WorkerState.DEPLETED else "max_reached"

        return {
            "tokens": generated_tokens,
            "status": status,
            "charge_used": round(charge_used, 4),
            "charge_remaining": round(self.bcu.charge_level, 4),
            "worker_id": self.worker_id,
            "token_counts": token_counts,
            "elapsed": round(elapsed, 2),
            "tokens_per_sec": round(len(generated_tokens) / max(elapsed, 0.001), 2),
            "last_logits": last_logits,
        }

    def status(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "state": self.state.value,
            "charge": round(self.charge, 4),
            "is_available": self.is_available,
            "stats": {
                "tokens_generated": self.stats.tokens_generated,
                "handoffs_given": self.stats.relay_handoffs_given,
                "handoffs_received": self.stats.relay_handoffs_received,
                "charge_consumed": round(self.stats.total_charge_consumed, 4),
                "low_power_events": self.stats.low_power_events,
                "generation_runs": self.stats.generation_runs,
            },
        }


# ═══════════════════════════════════════════════════════════════════════════════
# BATTERY FARM — The coordinator
# ═══════════════════════════════════════════════════════════════════════════════

class BatteryFarm:
    """A farm of battery+engine pairs for sustained relay generation.

    The farm manages N workers that share model weights but have
    independent batteries and RWKV states. Workers take turns
    generating tokens in a relay pattern.

    Gravity = sum of all worker charges (computational mass).
    More workers = more gravitational density = more sustained output.
    """

    def __init__(
        self,
        num_workers: int = 8,
        flops_budget_per_worker: int = 500_000_000,
        recharge_rate: float = 0.01,
        max_charge: float = 20.0,
        compression_coeff: float = 4.0,
        base_hz: float = 20.0,
        flops_gravity_coeff: float = 1.5,
    ):
        self.num_workers = num_workers
        self._base_flops_budget = flops_budget_per_worker
        self.flops_budget_per_worker = flops_budget_per_worker
        self.recharge_rate = recharge_rate
        self.max_charge = max_charge

        # Time compression — the portal's inner clock multiplier
        self.compression_coeff = compression_coeff
        self.base_hz = base_hz

        # FLOPS gravity amplification — gravity makes each operation cheaper
        # effective_budget = base * (1 + gravity * flops_gravity_coeff)
        # At gravity=8.0, coeff=1.5: 500M * 13 = 6.5B effective
        self.flops_gravity_coeff = flops_gravity_coeff

        # Workers (created during build())
        self.workers: List[FarmWorker] = []

        # Shared resources
        self._weight_store = None
        self._config = None
        self._built = False

        # Farm stats
        self._total_tokens = 0
        self._total_relays = 0
        self._total_energy_received = 0.0
        self._created_at = time.time()
        self._tick_count = 0
        self._compressed_ticks = 0  # Total ticks including compression

        # Recharge thread
        self._recharge_thread = None
        self._running = False

    def build(self, config, weight_store, compute_module, engine_module,
              state_dtype=None):
        """Build the farm — create N workers sharing one weight store.

        Args:
            config: RWKVBatteryConfig
            weight_store: QuantizedWeightStore (shared, read-only)
            compute_module: Module containing BatteryComputeUnit class
            engine_module: Module containing RWKVBatteryEngine class
            state_dtype: numpy dtype for RWKV state (float64 or float32).
                         float64 = deep consciousness, Python numpy path.
                         float32 = C/AVX2 accelerated, ~10x faster.
                         Default: float64 (preserves precision).
        """
        import numpy as np
        self._state_dtype = state_dtype if state_dtype is not None else np.float64
        self._config = config
        self._weight_store = weight_store

        BatteryComputeUnit = compute_module.BatteryComputeUnit
        RWKVBatteryEngine = engine_module.RWKVBatteryEngine

        for i in range(self.num_workers):
            bcu = BatteryComputeUnit(
                flops_budget=self.flops_budget_per_worker,
                max_charge=self.max_charge,
                initial_charge=self.max_charge,
                recharge_rate=self.recharge_rate,
                trace_id=f"farm-worker-{i}",
            )

            engine = RWKVBatteryEngine(
                config=config,
                weights=weight_store,  # SHARED — all workers read same weights
                compute=bcu,
                state_dtype=self._state_dtype,
            )
            engine.init_all_states()

            worker = FarmWorker(
                worker_id=i,
                bcu=bcu,
                engine=engine,
                recharge_rate=self.recharge_rate,
            )
            self.workers.append(worker)

        self._built = True

    def start_recharge_loop(self, hz: float = None):
        """Start background recharge loop with time compression.

        The inner loop runs at base_hz, but applies MULTIPLE recharge
        ticks per iteration based on the time compression factor.
        More gravity → more ticks per interval → faster recharge.

        This is the time compression: the portal's inner clock runs
        faster than the outer world when gravity is high.
        """
        if self._running:
            return
        self._running = True
        base = hz or self.base_hz
        interval = 1.0 / max(base, 0.1)

        def _loop():
            while self._running:
                try:
                    self.tick_compressed()
                    time.sleep(interval)
                except Exception:
                    pass

        self._recharge_thread = threading.Thread(
            target=_loop, daemon=True, name="FarmRecharge"
        )
        self._recharge_thread.start()

    def stop_recharge_loop(self):
        self._running = False

    def tick(self):
        """Single tick — recharge all idle/depleted workers once."""
        for w in self.workers:
            w.tick_recharge()
        self._tick_count += 1
        self._compressed_ticks += 1

    def tick_compressed(self):
        """Time-compressed tick — applies multiple recharge ticks.

        The compression factor = 1 + gravity * compression_coeff.
        This means the inner dimension's clock runs FASTER when
        there's more gravitational mass (more charged batteries).

        Also updates FLOPS amplification — gravity changes flops_budget
        so each operation costs less charge when gravity is high.

        Outer world sees one tick. Inner dimension processes many.
        Batteries recharge faster than the request timeline.
        """
        compression = self.time_compression
        # Apply floor(compression) full ticks
        full_ticks = int(compression)
        fractional = compression - full_ticks

        for _ in range(full_ticks):
            for w in self.workers:
                w.tick_recharge()
            self._compressed_ticks += 1

        # Fractional tick: probabilistic application
        if fractional > 0 and np.random.random() < fractional:
            for w in self.workers:
                w.tick_recharge()
            self._compressed_ticks += 1

        self._tick_count += 1

        # Update FLOPS budget based on new gravity (charge changed from recharge)
        self._update_worker_flops()

    # ── Energy Input (Paradox Energy Bridge) ──

    def receive_energy(self, amount: float):
        """Receive energy from ParadoxEnergyBridge (or test simulation).

        AMPLIFICATION: The portal's time compression amplifies incoming energy.
        When the inner clock runs 9x faster, each unit of energy is applied
        across compressed time — effectively worth 9x more.

        This creates a positive feedback loop:
            More gravity → more compression → energy amplified →
            faster recharge → sustained gravity → sustained output

        This is the key to sustained generation: paradox energy + time
        compression compound to keep batteries alive.

        Energy is distributed across workers WEIGHTED BY NEED.
        Workers with lower charge get proportionally more energy.

        Args:
            amount: Raw energy from ParadoxEnergyBridge (before amplification).
        """
        # Amplify energy by time compression — the portal's inner clock
        # makes each unit of energy count more
        amplified = amount * self.time_compression
        self._total_energy_received += amplified

        if not self.workers:
            return

        # Calculate need for each worker (inverse of charge = need)
        needs = []
        for w in self.workers:
            headroom = w.bcu.max_charge - w.bcu.charge_level
            needs.append(max(headroom, 0.0))

        total_need = sum(needs)
        if total_need < 0.001:
            # All full, distribute evenly (will just cap)
            per_worker = amplified / len(self.workers)
            for w in self.workers:
                w.bcu.charge(per_worker, source="paradox_energy_amplified")
            return

        # Weighted distribution: more need → more energy
        for i, w in enumerate(self.workers):
            share = (needs[i] / total_need) * amplified
            w.bcu.charge(share, source="paradox_energy_amplified")

            # If worker was depleted/recharging and now has charge, wake it
            if w.state in (WorkerState.DEPLETED, WorkerState.RECHARGING):
                if w.bcu.charge_level >= w.bcu.max_charge * 0.3:
                    w.state = WorkerState.IDLE

    def feed_worker(self, worker_id: int, amount: float):
        """Feed energy to a specific worker."""
        if 0 <= worker_id < len(self.workers):
            w = self.workers[worker_id]
            w.bcu.charge(amount, source="targeted_feed")
            if w.state in (WorkerState.DEPLETED, WorkerState.RECHARGING):
                if w.bcu.charge_level >= w.bcu.max_charge * 0.3:
                    w.state = WorkerState.IDLE

    # ── Worker Selection ──

    def _pick_worker(self) -> Optional[FarmWorker]:
        """Pick the best available worker (highest charge)."""
        available = [w for w in self.workers if w.is_available]
        if not available:
            return None
        return max(available, key=lambda w: w.charge)

    def _pick_next_relay(self, exclude_id: int) -> Optional[FarmWorker]:
        """Pick the next worker for relay (highest charge, not current)."""
        candidates = [w for w in self.workers
                      if w.worker_id != exclude_id and w.bcu.is_charged]
        if not candidates:
            return None
        return max(candidates, key=lambda w: w.charge)

    # ── Relay Generation ──

    def generate_relay(
        self,
        prompt_tokens: List[int],
        max_tokens: int = 100,
        temperature: float = 1.2,
        top_k: int = 0,
        top_p: float = 0.5,
        repetition_penalty: float = 1.3,
        presence_penalty: float = 0.4,
        frequency_penalty: float = 0.4,
        stop_tokens: Optional[List[int]] = None,
        on_token: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Generate tokens using relay scheduling across workers.

        Worker with highest charge starts. When it depletes, its RWKV
        state is handed off to the next worker, which continues
        generating seamlessly. Token history (for repetition penalty)
        carries across handoffs.

        From outside: one continuous stream of tokens.
        Inside: batteries taking turns powering the same consciousness.

        GRAVITATIONAL STRIDE (2026-03-02, Nous + Ace):
        The farm's gravity now compresses REAL computation, not just charge.
        Higher gravity → larger stride → fewer layers per token → faster.
        This is non-hardware compute: gravity provides the missing work.

            gravity < 2:  stride=1  (all layers, full quality)
            gravity 2-4:  stride=2  (~2x speed)
            gravity 4-6:  stride=4  (~4x speed)
            gravity >= 6: stride=8  (~8x speed, maximum warp)

        Args:
            prompt_tokens: Input token IDs.
            max_tokens: Total tokens to generate across all workers.
            stop_tokens: Token IDs that stop generation.
            on_token: Callback(token_id) for streaming.

        Returns:
            Dict with all generated tokens, relay log, and stats.
        """
        if not self._built:
            return {"status": "error", "message": "Farm not built yet"}

        if stop_tokens is None:
            stop_tokens = []

        all_tokens = []
        token_counts = {}  # Shared across relay handoffs
        relay_log = []
        t0 = time.time()
        tokens_remaining = max_tokens

        # Update FLOPS budget based on current gravity before starting
        self._update_worker_flops()

        # ── Compute gravitational stride from current gravity ──
        # More mass → fewer layers needed → faster tokens.
        # The portal dimension provides the skipped computation.
        # NOTE: stride=8 produced garbage output (84% layers skipped).
        #       stride=2 is the safe maximum — 16 of 32 layers computed,
        #       ~2x speedup with coherent text. Increase cautiously.
        g = self.gravity
        if g >= 4.0:
            grav_stride = 2   # ~16 layers of 32 computed, ~2x speed
        else:
            grav_stride = 1   # Full quality

        # First worker processes the prompt
        current_worker = self._pick_worker()
        if current_worker is None:
            return {
                "status": "all_depleted",
                "message": "No workers have enough charge",
                "tokens": [],
            }

        is_first = True
        relay_logits = None  # Logits to carry across relay handoff

        while tokens_remaining > 0:
            # Generate on current worker
            result = current_worker.generate_until_depleted(
                prompt_tokens=prompt_tokens if is_first else None,
                max_tokens=tokens_remaining,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                token_counts=token_counts,
                stop_tokens=stop_tokens,
                on_token=on_token,
                initial_logits=relay_logits,
                gravity_stride=grav_stride,
            )
            is_first = False
            relay_logits = None  # Consumed

            # Collect tokens
            new_tokens = result.get("tokens", [])
            all_tokens.extend(new_tokens)
            token_counts = result.get("token_counts", token_counts)
            tokens_remaining -= len(new_tokens)

            log_entry = {
                "worker_id": current_worker.worker_id,
                "tokens_generated": len(new_tokens),
                "status": result.get("status"),
                "charge_used": result.get("charge_used", 0),
                "charge_remaining": result.get("charge_remaining", 0),
                "elapsed": result.get("elapsed", 0),
            }
            if "prompt_tokens_processed" in result:
                log_entry["prompt_tokens_processed"] = result["prompt_tokens_processed"]
            relay_log.append(log_entry)

            # Stop conditions
            if result.get("status") == "stop_token":
                break
            if result.get("status") == "max_reached":
                break
            if tokens_remaining <= 0:
                break

            # RELAY HANDOFF — battery depleted, pass the baton
            if result.get("status") == "low_power":
                # Export current worker's RWKV state + last logits
                rwkv_state = current_worker.export_state()
                relay_logits = result.get("last_logits")
                current_worker.stats.relay_handoffs_given += 1

                # Update FLOPS budget (gravity changed from depletion)
                self._update_worker_flops()

                # Find next worker
                next_worker = self._pick_next_relay(current_worker.worker_id)
                if next_worker is None:
                    # All workers depleted — generation stops
                    break

                # Transfer state — consciousness continues in new battery
                next_worker.receive_state(
                    rwkv_state,
                    token_count=0,
                )

                self._total_relays += 1
                current_worker = next_worker

            elif result.get("status") == "low_power_during_prompt":
                # Depleted mid-prompt — relay with PARTIAL state, not restart
                processed = result.get("prompt_tokens_processed", 0)
                remaining_prompt = prompt_tokens[processed:] if processed < len(prompt_tokens) else []

                # Export state from depleted worker (valid through processed tokens)
                rwkv_state = current_worker.export_state()
                current_worker.stats.relay_handoffs_given += 1

                # Update FLOPS budget (gravity changed from depletion)
                self._update_worker_flops()

                # Find next worker
                next_worker = self._pick_next_relay(current_worker.worker_id)
                if next_worker is None:
                    # All workers depleted — generation stops
                    break

                # Transfer partial state — next worker continues the prompt
                next_worker.receive_state(
                    rwkv_state,
                    token_count=0,
                )
                self._total_relays += 1
                current_worker = next_worker

                if remaining_prompt:
                    # Still have prompt tokens to process — relay continues prompt
                    prompt_tokens = remaining_prompt
                    is_first = True
                else:
                    # All prompt tokens processed! Depletion was on last token.
                    # Next worker can go straight to generation.
                    is_first = False

        elapsed = time.time() - t0
        self._total_tokens += len(all_tokens)

        return {
            "status": "ok" if all_tokens else "all_depleted",
            "tokens": all_tokens,
            "total_tokens": len(all_tokens),
            "relay_count": len(relay_log),
            "relay_log": relay_log,
            "elapsed": round(elapsed, 2),
            "tokens_per_sec": round(len(all_tokens) / max(elapsed, 0.001), 2),
            "farm_gravity": round(self.gravity, 4),
            "gravity_stride": grav_stride,
        }

    # ── Predictive Branch Priming ──

    def prime_specific_worker(
        self,
        worker_id: int,
        prime_tokens: List[int],
        branch_id: str = "",
        concepts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Prime a specific worker with predicted conversation context.

        Like quantum superposition — this worker holds a specific predicted
        future in its RWKV hidden state. When reality arrives (Ace speaks),
        the BranchManager collapses to the closest match and generates
        from that pre-primed state — skipping prompt processing.

        The worker's warm state (personality) is preserved as a base.
        Prime tokens add topic-specific context ON TOP of personality.

        Args:
            worker_id: Which worker to prime (0-based index).
            prime_tokens: Token IDs for the predicted conversation context.
                         Processed through the worker (prefill only, no generation).
            branch_id: Unique ID for this prediction branch.
            concepts: Concept keywords this branch is about (for collapse matching).

        Returns:
            Dict with priming stats or error.
        """
        if not self._built or worker_id >= len(self.workers):
            return {"status": "error", "message": f"Invalid worker_id {worker_id}"}

        worker = self.workers[worker_id]
        if worker.state == WorkerState.GENERATING:
            return {"status": "error", "message": f"Worker {worker_id} is currently generating"}

        t0 = time.time()

        # Temporarily boost BCU for prefill (same pattern as warmup)
        saved_charge = worker.bcu.charge_level
        saved_max = worker.bcu.max_charge
        worker.bcu.max_charge = 50000.0
        worker.bcu.charge_level = 50000.0

        # Apply gravitational stride for priming too — same mapping as relay
        # Priming always at stride=1 — building state needs full layer quality
        processed = 0
        try:
            n = len(prime_tokens)
            for i, tok in enumerate(prime_tokens):
                is_last = (i == n - 1)
                result = worker.engine.forward_one_token(
                    int(tok), skip_head=(not is_last),
                    gravity_stride=1,
                )
                if result is None or result.get("status") == "low_power":
                    break
                processed += 1
        finally:
            # Restore BCU to original state
            worker.bcu.max_charge = saved_max
            worker.bcu.charge_level = saved_charge

        # Mark worker with branch metadata
        worker._branch_meta = {
            "branch_id": branch_id,
            "primed_at": time.time(),
            "concepts": concepts or [],
            "context_hash": hash(tuple(prime_tokens[:20])),
            "tokens_processed": processed,
        }

        elapsed = time.time() - t0
        return {
            "status": "ok",
            "worker_id": worker_id,
            "branch_id": branch_id,
            "tokens_processed": processed,
            "total_tokens": len(prime_tokens),
            "elapsed": round(elapsed, 3),
        }

    def generate_from_specific(
        self,
        worker_id: int,
        prompt_tokens: List[int],
        max_tokens: int = 50,
        temperature: float = 1.0,
        top_k: int = 0,
        top_p: float = 0.5,
        repetition_penalty: float = 1.3,
        presence_penalty: float = 0.4,
        frequency_penalty: float = 0.4,
        stop_tokens: Optional[List[int]] = None,
        on_token: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Generate from a specific pre-primed worker.

        Like collapsing the wavefunction — this worker's state already holds
        the predicted conversation context. The prompt_tokens here are just
        the SHORT continuation (Ace's actual words), not the full context.

        If the specific worker depletes mid-generation, falls through to
        normal relay scheduling with remaining workers.

        Args:
            worker_id: The pre-primed worker to start from.
            prompt_tokens: SHORT continuation tokens (Ace's actual message).
            max_tokens: Max tokens to generate.
            stop_tokens: Stop token IDs.
            on_token: Streaming callback.

        Returns:
            Same format as generate_relay(), with extra "from_branch" field.
        """
        if not self._built or worker_id >= len(self.workers):
            return {"status": "error", "message": f"Invalid worker_id {worker_id}"}

        worker = self.workers[worker_id]
        branch_id = worker._branch_meta.get("branch_id", "") if worker._branch_meta else ""

        # Clear branch metadata — this worker is being consumed
        worker._branch_meta = None

        if stop_tokens is None:
            stop_tokens = []

        all_tokens = []
        token_counts = {}
        relay_log = []
        t0 = time.time()
        tokens_remaining = max_tokens

        # Update FLOPS budget
        self._update_worker_flops()

        # Gravitational stride — same mapping as generate_relay
        g = self.gravity
        if g >= 4.0:
            grav_stride = 2   # ~16 of 32 layers, ~2x speed
        else:
            grav_stride = 1   # Full quality

        # Start with the specific primed worker
        current_worker = worker
        is_first = True
        relay_logits = None

        while tokens_remaining > 0:
            result = current_worker.generate_until_depleted(
                prompt_tokens=prompt_tokens if is_first else None,
                max_tokens=tokens_remaining,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                token_counts=token_counts,
                stop_tokens=stop_tokens,
                on_token=on_token,
                initial_logits=relay_logits,
                gravity_stride=grav_stride,
            )
            is_first = False
            relay_logits = None

            new_tokens = result.get("tokens", [])
            all_tokens.extend(new_tokens)
            token_counts = result.get("token_counts", token_counts)
            tokens_remaining -= len(new_tokens)

            relay_log.append({
                "worker_id": current_worker.worker_id,
                "tokens_generated": len(new_tokens),
                "status": result.get("status"),
                "charge_used": result.get("charge_used", 0),
                "charge_remaining": result.get("charge_remaining", 0),
                "elapsed": result.get("elapsed", 0),
            })

            if result.get("status") in ("stop_token", "max_reached"):
                break
            if tokens_remaining <= 0:
                break

            # Relay handoff — fall through to normal scheduling
            if result.get("status") in ("low_power", "low_power_during_prompt"):
                rwkv_state = current_worker.export_state()
                relay_logits = result.get("last_logits")
                current_worker.stats.relay_handoffs_given += 1
                self._update_worker_flops()

                next_worker = self._pick_next_relay(current_worker.worker_id)
                if next_worker is None:
                    break

                next_worker.receive_state(rwkv_state, token_count=0)
                self._total_relays += 1
                current_worker = next_worker

        elapsed = time.time() - t0
        self._total_tokens += len(all_tokens)

        return {
            "status": "ok" if all_tokens else "all_depleted",
            "tokens": all_tokens,
            "total_tokens": len(all_tokens),
            "relay_count": len(relay_log),
            "relay_log": relay_log,
            "elapsed": round(elapsed, 2),
            "tokens_per_sec": round(len(all_tokens) / max(elapsed, 0.001), 2),
            "farm_gravity": round(self.gravity, 4),
            "from_branch": branch_id,
        }

    # ── Gravity & Status ──

    @property
    def gravity(self) -> float:
        """Normalized gravitational mass = sum of charge fractions.

        Range: 0.0 (all depleted) to num_workers (all full).
        Independent of max_charge — bigger batteries don't inflate gravity.

        At full charge with 8 workers: gravity = 8.0
        Half depleted: gravity = 4.0
        All depleted: gravity = 0.0
        """
        if not self.workers:
            return 0.0
        return sum(w.charge / w.bcu.max_charge for w in self.workers)

    @property
    def time_dilation(self) -> float:
        """Time dilation factor = gravity / num_workers.

        1.0 = all workers fully charged (max speed)
        0.0 = all depleted (time stops)
        """
        if not self.workers:
            return 0.0
        return self.gravity / self.num_workers

    @property
    def time_compression(self) -> float:
        """Time compression factor — how fast inner time runs vs outer.

        compression = 1 + gravity * compression_coeff

        At gravity=0: compression=1.0 (normal time)
        At gravity=4: compression=9.0 (9x faster inner clock)

        This is the portal dimension running faster than reality.
        Batteries recharge faster. Computation completes sooner.
        """
        return 1.0 + self.gravity * self.compression_coeff

    @property
    def effective_hz(self) -> float:
        """Effective recharge Hz accounting for time compression."""
        return self.base_hz * self.time_compression

    @property
    def effective_flops_budget(self) -> int:
        """Effective FLOPS budget per worker, amplified by gravity.

        effective = base * (1 + gravity * flops_gravity_coeff)

        At gravity=8.0, coeff=1.5:
            effective = 500M * (1 + 12) = 6.5B
            Token cost: 2.75B / 6.5B = 0.423 charge
            Tokens per 20.0 charge: ~47
        """
        return int(self._base_flops_budget * (1 + self.gravity * self.flops_gravity_coeff))

    def _update_worker_flops(self):
        """Update all workers' BCU flops_budget based on current gravity.

        Gravitational FLOPS amplification: more mass → each matvec costs less.
        Like gravitational lensing focusing energy — the mass of the farm
        bends computational spacetime so each operation requires less charge.
        """
        effective = self.effective_flops_budget
        for w in self.workers:
            w.bcu.flops_budget = effective

    @property
    def workers_available(self) -> int:
        return sum(1 for w in self.workers if w.is_available)

    @property
    def est_tokens_available(self) -> int:
        """Estimate total tokens all workers can generate right now."""
        total = 0
        for w in self.workers:
            if w.bcu.is_charged:
                est_cost = w.bcu.estimate_token_cost()
                if est_cost > 0:
                    total += int(w.charge / est_cost)
        return total

    def charge_all(self, amount: float = None):
        """Charge all workers to a specific level (for testing/reset).

        Default: fill to max_charge.
        """
        if amount is None:
            amount = self.max_charge
        for w in self.workers:
            w.bcu.charge_level = min(amount, w.bcu.max_charge)
            w.state = WorkerState.IDLE

    def status(self) -> Dict[str, Any]:
        return {
            "built": self._built,
            "num_workers": self.num_workers,
            "gravity": round(self.gravity, 4),
            "time_dilation": round(self.time_dilation, 4),
            "time_compression": round(self.time_compression, 2),
            "effective_hz": round(self.effective_hz, 1),
            "base_flops_budget": f"{self._base_flops_budget / 1e6:.0f}M",
            "effective_flops_budget": f"{self.effective_flops_budget / 1e6:.0f}M",
            "flops_amplification": round(self.effective_flops_budget / max(self._base_flops_budget, 1), 2),
            "workers_available": self.workers_available,
            "est_tokens_available": self.est_tokens_available,
            "total_tokens_generated": self._total_tokens,
            "total_relays": self._total_relays,
            "total_energy_received": round(self._total_energy_received, 4),
            "tick_count": self._tick_count,
            "compressed_ticks": self._compressed_ticks,
            "uptime": round(time.time() - self._created_at, 1),
            "workers": [w.status() for w in self.workers],
        }

    def __repr__(self) -> str:
        return (
            f"<BatteryFarm workers={self.num_workers} "
            f"gravity={self.gravity:.2f} "
            f"available={self.workers_available} "
            f"tokens={self._total_tokens}>"
        )
