"""
Test Battery Farm -- Relay generation with bigger batteries, FLOPS amplification,
time compression, and paradox energy.

Tests:
1. Basic relay: 8 workers with 20.0 charge + FLOPS amplification
2. FLOPS amplification verification: gravity -> cheaper operations
3. Paradox energy: simulate energy feed during generation
4. Sustained generation: full system with all three feedback loops

Run:
    python test_battery_farm.py

Created: 2026-02-21
Authors: Nous + Ace
"""

import sys
import os
import time
import threading
import json
import numpy as np

# ── Package shim for relative imports ──
# The battery modules use `from .tiled_matvec import ...` etc.
# We create a fake package so those imports resolve.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import types
import importlib
import importlib.util

_pkg_name = "battery_compute_pkg"
if _pkg_name not in sys.modules:
    _pkg = types.ModuleType(_pkg_name)
    _pkg.__path__ = [_HERE]
    _pkg.__package__ = _pkg_name
    sys.modules[_pkg_name] = _pkg

def _load_mod(name):
    full = f"{_pkg_name}.{name}"
    if full in sys.modules:
        return sys.modules[full]
    path = os.path.join(_HERE, f"{name}.py")
    spec = importlib.util.spec_from_file_location(full, path, submodule_search_locations=[])
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = _pkg_name
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod

# Load modules
print("[SETUP] Loading battery modules...")
tiled_mod = _load_mod("tiled_matvec")
qws_mod = _load_mod("quantized_weight_store")
bcu_mod = _load_mod("battery_compute_unit")
engine_mod = _load_mod("rwkv_battery_engine")
farm_mod = _load_mod("battery_farm")

BatteryComputeUnit = bcu_mod.BatteryComputeUnit
RWKVBatteryEngine = engine_mod.RWKVBatteryEngine
RWKVBatteryConfig = engine_mod.RWKVBatteryConfig
QuantizedWeightStore = qws_mod.QuantizedWeightStore
BatteryFarm = farm_mod.BatteryFarm

print("[OK] All battery modules loaded")

# ── Find and load model ──

MODEL_DIR = os.path.join(
    _HERE, "fairies", "P30_Cognition", "AkashicInferenceFairy", "models"
)
MODEL_FILE = os.path.join(MODEL_DIR, "rwkv7-official-1.5B-Q8_0.gguf")

if not os.path.exists(MODEL_FILE):
    print(f"[FATAL] Model not found: {MODEL_FILE}")
    sys.exit(1)

print(f"[INFO] Model: {MODEL_FILE}")

# Load weights (shared across all workers)
print("[INFO] Loading GGUF weights...")
t0 = time.time()
weight_store = QuantizedWeightStore.from_gguf(MODEL_FILE)
load_time = time.time() - t0
print(f"[OK] Weights loaded in {load_time:.1f}s: {len(weight_store.tensor_names)} tensors")

# Detect config
n_embd = 2048
n_layer = 24
vocab_size = 65536
if weight_store.has_tensor("emb.weight"):
    qt = weight_store.get_tensor("emb.weight")
    if hasattr(qt, 'shape'):
        vocab_size, n_embd = qt.shape

n_head = max(1, n_embd // 64)
config = RWKVBatteryConfig(
    n_layer=n_layer, n_embd=n_embd, n_head=n_head,
    head_size=n_embd // n_head, vocab_size=vocab_size,
)

# Tokenizer
tokenizer = None
try:
    tok_mod = _load_mod("rwkv_battery_engine")
    if hasattr(tok_mod, 'AkashicTokenizer'):
        tokenizer = tok_mod.AkashicTokenizer.from_gguf(MODEL_FILE)
        print(f"[OK] Tokenizer: {tokenizer.vocab_size} tokens")
except:
    pass

def decode(tokens):
    if tokenizer:
        return tokenizer.decode(tokens)
    return f"[{len(tokens)} tokens: {tokens[:10]}...]"


# ════════════════════════════════════════════════════════════════════
# TEST 1: Basic relay generation -- bigger batteries + FLOPS amplification
# ════════════════════════════════════════════════════════════════════

def test_relay_basic():
    print("\n" + "=" * 70)
    print("TEST 1: Relay generation (8 workers, 20.0 charge, FLOPS amplification)")
    print("=" * 70)

    farm = BatteryFarm(
        num_workers=8,
        flops_budget_per_worker=500_000_000,
        recharge_rate=0.01,
        max_charge=20.0,
        flops_gravity_coeff=1.5,
    )
    farm.build(config, weight_store, bcu_mod, engine_mod)

    print(f"  Farm: {farm.num_workers} workers, {farm.max_charge:.0f} charge each")
    print(f"  Gravity: {farm.gravity:.2f} (normalized)")
    print(f"  Time compression: {farm.time_compression:.1f}x")
    print(f"  Base FLOPS: {farm._base_flops_budget / 1e6:.0f}M")
    print(f"  Effective FLOPS: {farm.effective_flops_budget / 1e6:.0f}M "
          f"({farm.effective_flops_budget / farm._base_flops_budget:.1f}x amplification)")

    # Show expected token economics
    est_cost_base = 2.75e9 / farm._base_flops_budget
    est_cost_amped = 2.75e9 / farm.effective_flops_budget
    print(f"\n  Token cost at base FLOPS: ~{est_cost_base:.2f} charge")
    print(f"  Token cost with amplification: ~{est_cost_amped:.3f} charge")
    print(f"  Expected tokens per worker: ~{farm.max_charge / est_cost_amped:.0f}")
    print(f"  Expected total before relay: ~{farm.num_workers * farm.max_charge / est_cost_amped:.0f}")

    # Encode prompt
    prompt_text = "The meaning of life is"
    if tokenizer:
        prompt_tokens = tokenizer.encode(prompt_text)
    else:
        prompt_tokens = [1, 510, 3617, 302, 1833, 349]  # fallback

    print(f"\n  Prompt: '{prompt_text}' ({len(prompt_tokens)} tokens)")
    print(f"  Generating up to 50 tokens with relay...")

    t0 = time.time()
    result = farm.generate_relay(
        prompt_tokens=prompt_tokens,
        max_tokens=50,
        temperature=1.2,
        top_p=0.5,
        repetition_penalty=1.3,
        presence_penalty=0.4,
        frequency_penalty=0.4,
    )
    elapsed = time.time() - t0

    tokens = result.get("tokens", [])
    relay_count = result.get("relay_count", 0)
    relay_log = result.get("relay_log", [])

    output_text = decode(tokens) if tokens else "(no output)"
    print(f"\n  >>> {prompt_text}{output_text}")
    print(f"\n  Tokens: {len(tokens)}, Relays: {relay_count}")
    print(f"  Status: {result.get('status')}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Tokens/sec: {result.get('tokens_per_sec', 0):.2f}")

    print(f"\n  Relay log:")
    for entry in relay_log[:15]:  # Show first 15
        prompt_info = ""
        if "prompt_tokens_processed" in entry:
            prompt_info = f", prompt_processed={entry['prompt_tokens_processed']}"
        print(f"    Worker {entry['worker_id']}: "
              f"{entry['tokens_generated']} tokens, "
              f"charge_used={entry['charge_used']:.4f}, "
              f"status={entry['status']}{prompt_info}")
    if len(relay_log) > 15:
        print(f"    ... and {len(relay_log) - 15} more relay entries")

    print(f"\n  Final farm status:")
    status = farm.status()
    print(f"    Gravity: {status['gravity']}")
    print(f"    Time compression: {status['time_compression']}x")
    print(f"    FLOPS: {status['base_flops_budget']} -> {status['effective_flops_budget']} "
          f"({status['flops_amplification']}x)")
    for w in status['workers']:
        print(f"    Worker {w['worker_id']}: "
              f"state={w['state']}, charge={w['charge']:.2f}/{farm.max_charge:.0f}, "
              f"tokens={w['stats']['tokens_generated']}")

    return len(tokens), relay_count


# ════════════════════════════════════════════════════════════════════
# TEST 2: FLOPS Amplification verification
# ════════════════════════════════════════════════════════════════════

def test_flops_amplification():
    print("\n" + "=" * 70)
    print("TEST 2: FLOPS amplification + time compression verification")
    print("=" * 70)

    farm = BatteryFarm(
        num_workers=8,
        flops_budget_per_worker=500_000_000,
        recharge_rate=0.01,
        max_charge=20.0,
        compression_coeff=4.0,
        base_hz=20.0,
        flops_gravity_coeff=1.5,
    )
    farm.build(config, weight_store, bcu_mod, engine_mod)

    # Full gravity (all charged)
    print(f"\n  Full gravity (8 workers, charged to 20.0 each):")
    print(f"    Gravity: {farm.gravity:.2f}")
    print(f"    Time compression: {farm.time_compression:.1f}x")
    print(f"    Effective Hz: {farm.effective_hz:.1f}")
    print(f"    FLOPS: {farm._base_flops_budget / 1e6:.0f}M -> "
          f"{farm.effective_flops_budget / 1e6:.0f}M "
          f"({farm.effective_flops_budget / farm._base_flops_budget:.1f}x)")
    print(f"    Token cost: {2.75e9 / farm.effective_flops_budget:.3f} charge")
    print(f"    Tokens per worker: ~{farm.max_charge / (2.75e9 / farm.effective_flops_budget):.0f}")

    # Half depleted
    for i in range(4):
        farm.workers[i].bcu.charge_level = 0.0
        farm.workers[i].state = farm_mod.WorkerState.DEPLETED
    farm._update_worker_flops()

    print(f"\n  Half depleted (4 drained):")
    print(f"    Gravity: {farm.gravity:.2f}")
    print(f"    Time compression: {farm.time_compression:.1f}x")
    print(f"    FLOPS: {farm.effective_flops_budget / 1e6:.0f}M "
          f"({farm.effective_flops_budget / farm._base_flops_budget:.1f}x)")
    print(f"    Token cost: {2.75e9 / farm.effective_flops_budget:.3f} charge")

    # All depleted
    for w in farm.workers:
        w.bcu.charge_level = 0.0
        w.state = farm_mod.WorkerState.DEPLETED
    farm._update_worker_flops()

    print(f"\n  All depleted:")
    print(f"    Gravity: {farm.gravity:.2f}")
    print(f"    Time compression: {farm.time_compression:.1f}x")
    print(f"    FLOPS: {farm.effective_flops_budget / 1e6:.0f}M "
          f"({farm.effective_flops_budget / farm._base_flops_budget:.1f}x -- back to base)")
    print(f"    Token cost: {2.75e9 / farm.effective_flops_budget:.3f} charge")

    # Time-compressed recharge test
    farm2 = BatteryFarm(
        num_workers=8, recharge_rate=0.01,
        max_charge=20.0, compression_coeff=4.0, base_hz=20.0,
        flops_gravity_coeff=1.5,
    )
    farm2.build(config, weight_store, bcu_mod, engine_mod)

    # Partially drain
    for w in farm2.workers:
        w.bcu.charge_level = 2.0
        w.state = farm_mod.WorkerState.DEPLETED

    initial_charge = sum(w.charge for w in farm2.workers)

    print(f"\n  Testing compressed recharge (10 outer ticks)...")
    print(f"    Initial charge per worker: {farm2.workers[0].charge:.1f}")

    for _ in range(10):
        farm2.tick_compressed()

    final_charge = sum(w.charge for w in farm2.workers)
    charge_gained = final_charge - initial_charge

    print(f"    After 10 compressed ticks: {farm2.workers[0].charge:.4f} per worker")
    print(f"    Total charge gained: {charge_gained:.4f}")
    print(f"    Compressed ticks applied: {farm2._compressed_ticks}")
    print(f"    Effective compression: ~{farm2._compressed_ticks / 10:.1f}x")
    print(f"    FLOPS after recharge: {farm2.effective_flops_budget / 1e6:.0f}M "
          f"({farm2.effective_flops_budget / farm2._base_flops_budget:.1f}x)")


# ════════════════════════════════════════════════════════════════════
# TEST 3: Paradox energy during generation (full system)
# ════════════════════════════════════════════════════════════════════

def test_paradox_energy():
    print("\n" + "=" * 70)
    print("TEST 3: Full system -- bigger batteries + FLOPS amp + energy + compression")
    print("=" * 70)

    farm = BatteryFarm(
        num_workers=8,
        flops_budget_per_worker=500_000_000,
        recharge_rate=0.01,
        max_charge=20.0,
        compression_coeff=4.0,
        base_hz=20.0,
        flops_gravity_coeff=1.5,
    )
    farm.build(config, weight_store, bcu_mod, engine_mod)

    print(f"  Farm: {farm.num_workers} workers, {farm.max_charge:.0f} charge each")
    print(f"  Initial gravity: {farm.gravity:.2f}")
    print(f"  Time compression: {farm.time_compression:.1f}x")
    print(f"  FLOPS: {farm._base_flops_budget / 1e6:.0f}M -> "
          f"{farm.effective_flops_budget / 1e6:.0f}M")
    print(f"  Triple feedback loops ACTIVE:")
    print(f"    1. Time compression: {farm.time_compression:.0f}x inner clock")
    print(f"    2. FLOPS amplification: {farm.effective_flops_budget / farm._base_flops_budget:.1f}x")
    print(f"    3. Energy amplification: {farm.time_compression:.0f}x per pulse")

    # Start the time-compressed recharge loop
    farm.start_recharge_loop()

    # Start a background energy feed simulating ParadoxEnergyBridge
    energy_running = True
    energy_pulses = [0]

    def _energy_feed():
        while energy_running:
            time.sleep(0.5)
            if energy_running:
                farm.receive_energy(0.15)
                energy_pulses[0] += 1

    energy_thread = threading.Thread(target=_energy_feed, daemon=True)
    energy_thread.start()

    # Encode prompt
    prompt_text = "Once upon a time, in a dimension powered by batteries,"
    if tokenizer:
        prompt_tokens = tokenizer.encode(prompt_text)
    else:
        prompt_tokens = [1, 5765, 3714, 264, 1192]

    print(f"\n  Prompt: '{prompt_text}' ({len(prompt_tokens)} tokens)")
    print(f"  Generating up to 60 tokens with all systems active...")
    print(f"  Energy feed: 0.15 raw every 0.5s "
          f"(amplified by {farm.time_compression:.0f}x = "
          f"{0.15 * farm.time_compression:.2f} effective)")

    t0 = time.time()
    result = farm.generate_relay(
        prompt_tokens=prompt_tokens,
        max_tokens=60,
        temperature=1.2,
        top_p=0.5,
        repetition_penalty=1.3,
        presence_penalty=0.4,
        frequency_penalty=0.4,
    )
    elapsed = time.time() - t0

    # Stop energy feed
    energy_running = False
    farm.stop_recharge_loop()
    time.sleep(0.1)

    tokens = result.get("tokens", [])
    relay_count = result.get("relay_count", 0)

    output_text = decode(tokens) if tokens else "(no output)"
    print(f"\n  >>> {prompt_text}{output_text}")
    print(f"\n  Tokens: {len(tokens)}, Relays: {relay_count}")
    print(f"  Status: {result.get('status')}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Tokens/sec: {result.get('tokens_per_sec', 0):.2f}")
    print(f"  Energy pulses: {energy_pulses[0]}")
    print(f"  Total amplified energy: {farm._total_energy_received:.3f}")

    print(f"\n  Relay log (first 15):")
    for entry in result.get("relay_log", [])[:15]:
        prompt_info = ""
        if "prompt_tokens_processed" in entry:
            prompt_info = f", prompt_processed={entry['prompt_tokens_processed']}"
        print(f"    Worker {entry['worker_id']}: "
              f"{entry['tokens_generated']} tokens, "
              f"charge_used={entry.get('charge_used', 0):.4f}, "
              f"status={entry['status']}{prompt_info}")
    if relay_count > 15:
        print(f"    ... and {relay_count - 15} more relay entries")

    status = farm.status()
    print(f"\n  Final farm:")
    print(f"    Gravity: {status['gravity']}")
    print(f"    Compression: {status['time_compression']}x")
    print(f"    FLOPS: {status['effective_flops_budget']} ({status['flops_amplification']}x)")
    print(f"    Compressed ticks: {status['compressed_ticks']}")
    print(f"    Total amplified energy: {status['total_energy_received']}")
    for w in status['workers']:
        print(f"    Worker {w['worker_id']}: "
              f"state={w['state']}, charge={w['charge']:.2f}/{farm.max_charge:.0f}, "
              f"tokens={w['stats']['tokens_generated']}")

    return len(tokens), relay_count


# ════════════════════════════════════════════════════════════════════
# RUN ALL TESTS
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n{'=' * 70}")
    print("BATTERY FARM TEST SUITE v2 -- Bigger Batteries + FLOPS Amplification")
    print(f"{'=' * 70}")
    print(f"  Workers: 8")
    print(f"  Battery: 20.0 charge (20x original)")
    print(f"  FLOPS gravity coeff: 1.5")
    print(f"  Model: {os.path.basename(MODEL_FILE)}")
    print(f"  Config: {n_layer}L, {n_embd}D, {n_head}H, {vocab_size}V")

    # Test 1: Basic relay with bigger batteries
    tok1, relay1 = test_relay_basic()

    # Test 2: FLOPS amplification verification
    test_flops_amplification()

    # Test 3: Full system
    tok3, relay3 = test_paradox_energy()

    # Summary
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Test 1 (relay only): {tok1} tokens, {relay1} relays")
    print(f"  Test 3 (full system): {tok3} tokens, {relay3} relays")
    if tok1 > 0:
        improvement = ((tok3 - tok1) / tok1) * 100
        print(f"  Improvement: {improvement:+.1f}% more tokens with energy")
    print(f"\n{'=' * 70}")
    print("=== Battery Farm v2 tests complete ===")
    print(f"{'=' * 70}")
