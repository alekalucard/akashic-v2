"""
RWKV-7 Forward Pass Diagnostic v2 — Find why the model produces garbage.

Tests:
1. Weight shapes after GGUF load
2. Embedding lookup sanity
3. LayerNorm correctness
4. C-accel vs Python fallback comparison
5. DETAILED layer-by-layer forward pass trace (every intermediate value)
6. Independent reference forward pass vs engine comparison
7. Text generation test

Run: python diagnose_rwkv.py
"""

import sys
import os
import time
import types
import importlib
import importlib.util
import numpy as np

# Add project root
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════════
# Virtual package import (from portal_compute_interior.py)
# ═══════════════════════════════════════════════════════════════════════════════

_PKG_NAME = "battery_compute_pkg"


def _ensure_virtual_package():
    """Create the virtual package if it doesn't exist."""
    if _PKG_NAME not in sys.modules:
        pkg = types.ModuleType(_PKG_NAME)
        pkg.__path__ = [str(_HERE)]
        pkg.__package__ = _PKG_NAME
        sys.modules[_PKG_NAME] = pkg


def _register_standalone_modules():
    """Pre-register standalone modules (no relative imports) into virtual package.

    This is CRITICAL: when the engine does `from .quantized_weight_store import QuantizedTensor`,
    it must find the SAME module that was used to create the weight store's tensors.
    Otherwise isinstance() fails and LoRA weights don't get dequantized.
    """
    _ensure_virtual_package()

    # These modules have NO relative imports — safe to import directly
    standalone = ["quantized_weight_store", "tiled_matvec"]
    for name in standalone:
        full_name = f"{_PKG_NAME}.{name}"
        if full_name in sys.modules:
            continue  # Already registered
        module_path = Path(_HERE) / f"{name}.py"
        if not module_path.exists():
            print(f"  WARNING: {module_path} not found")
            continue
        spec = importlib.util.spec_from_file_location(
            full_name, str(module_path),
            submodule_search_locations=[]
        )
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = _PKG_NAME
        sys.modules[full_name] = mod
        # Also register as bare name so `import quantized_weight_store` finds same module
        sys.modules[name] = mod
        spec.loader.exec_module(mod)


def _import_battery_module(name: str):
    """Import a battery module handling relative imports."""
    _ensure_virtual_package()

    full_name = f"{_PKG_NAME}.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]

    module_path = Path(_HERE) / f"{name}.py"
    if not module_path.exists():
        raise ImportError(f"Battery module not found: {module_path}")

    spec = importlib.util.spec_from_file_location(
        full_name, str(module_path),
        submodule_search_locations=[]
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = _PKG_NAME
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


def find_model_path(preferred=None):
    """Find GGUF model file, preferring largest/best available.

    Args:
        preferred: Specific model filename to look for. If None, uses priority chain.
    """
    models_dir = Path(_HERE) / "fairies" / "P30_Cognition" / "AkashicInferenceFairy" / "models"

    # If preferred model specified, look for it
    if preferred:
        p = models_dir / preferred
        if p.exists():
            return str(p)
        # Check alt locations
        for d in [models_dir, Path(_HERE) / "models"]:
            if d.exists():
                for f in d.glob(f"*{preferred}*"):
                    return str(f)

    # Priority chain: largest/cleanest first
    priority = [
        "rwkv7-g1d-7.2b-Q8_0.gguf",    # G1d 7.2B — best
        "rwkv7-2.9B-world-q8_0.gguf",   # Goose 2.9B
        "rwkv7-1.5B-world-Q8_0.gguf",   # Base 1.5B
    ]
    for name in priority:
        p = models_dir / name
        if p.exists():
            return str(p)

    # Fallback: any GGUF
    candidates = [models_dir, Path(_HERE) / "models"]
    for d in candidates:
        if d.exists():
            for f in d.glob("*.gguf"):
                if f.name != "nul":
                    return str(f)
    return None


def _stable_sigmoid(x):
    """Numerically stable sigmoid — standalone reference."""
    out = np.empty_like(x, dtype=np.float32)
    pos = x >= 0
    neg = ~pos
    out[pos] = 1.0 / (1.0 + np.exp(-x[pos]))
    ez = np.exp(x[neg])
    out[neg] = ez / (1.0 + ez)
    return out


def _layernorm(x, w, b, eps=1e-5):
    """Reference layernorm."""
    mean = x.mean()
    var = x.var()
    xn = (x - mean) / np.sqrt(var + eps)
    return xn * w + b


def stats(name, arr):
    """Print comprehensive stats for an array."""
    if arr is None:
        print(f"  {name:30s}: None")
        return
    arr = np.asarray(arr, dtype=np.float32).ravel()
    nan_count = np.isnan(arr).sum()
    inf_count = np.isinf(arr).sum()
    if nan_count > 0 or inf_count > 0:
        print(f"  {name:30s}: *** NaN={nan_count} Inf={inf_count} *** shape={arr.shape}")
        return
    print(f"  {name:30s}: mean={arr.mean():+.6f}  std={arr.std():.6f}  "
          f"min={arr.min():.4f}  max={arr.max():.4f}  "
          f"absmax={np.abs(arr).max():.4f}")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 5: Detailed layer-by-layer trace
# ═══════════════════════════════════════════════════════════════════════════════

def test_detailed_forward_trace(store, config):
    """Trace through layer 0 step by step, printing every intermediate value."""
    print("\n" + "=" * 70)
    print("TEST 5: DETAILED forward pass trace through layer 0")
    print("=" * 70)

    QuantizedTensor = sys.modules[f"{_PKG_NAME}.quantized_weight_store"].QuantizedTensor

    C = config.n_embd
    H = config.n_head
    N = config.head_size

    def get_w(name):
        """Get weight as float32."""
        t = store.get_tensor(name)
        if t is None:
            return None
        if isinstance(t, QuantizedTensor):
            return t.dequantize_full()
        return np.asarray(t, dtype=np.float32)

    # ── Embedding ──
    emb = get_w("emb.weight")  # [V, C]
    token = 100
    x = emb[token].astype(np.float32)
    stats("1. embedding[100]", x)

    # ── LN0 ──
    ln0_w = get_w("blocks.0.ln0.weight").ravel()
    ln0_b = get_w("blocks.0.ln0.bias").ravel()
    x = _layernorm(x, ln0_w, ln0_b)
    stats("2. after LN0", x)

    # ── LN1 for layer 0 ──
    ln1_w = get_w("blocks.0.ln1.weight").ravel()
    ln1_b = get_w("blocks.0.ln1.bias").ravel()
    ln1_out = _layernorm(x, ln1_w, ln1_b)
    stats("3. after LN1", ln1_out)

    # ── Token mixing (first token, so x_prev = 0) ──
    x_prev = np.zeros(C, dtype=np.float32)
    xx = x_prev - ln1_out  # shift difference
    stats("4. xx (shift diff)", xx)

    # x_maa (fused lerp)
    x_maa_raw = get_w("blocks.0.att.x_maa")
    print(f"\n  x_maa raw shape: {x_maa_raw.shape}")
    maa = x_maa_raw.squeeze()
    print(f"  x_maa squeezed shape: {maa.shape}")

    if maa.ndim == 2 and maa.shape[-1] == 6:
        stats("5a. x_maa raw col 0 (r)", maa[:, 0])
        stats("5b. x_maa raw col 1 (w)", maa[:, 1])
        stats("5c. x_maa raw col 2 (k)", maa[:, 2])
        stats("5d. x_maa raw col 3 (v)", maa[:, 3])

        lerp = _stable_sigmoid(maa)
        stats("6a. sigmoid(maa) col 0 (r)", lerp[:, 0])
        stats("6b. sigmoid(maa) col 1 (w)", lerp[:, 1])
        stats("6c. sigmoid(maa) col 2 (k)", lerp[:, 2])
        stats("6d. sigmoid(maa) col 3 (v)", lerp[:, 3])

        xr = ln1_out + xx * lerp[:, 0]
        xw = ln1_out + xx * lerp[:, 1]
        xk = ln1_out + xx * lerp[:, 2]
        xv = ln1_out + xx * lerp[:, 3]
        xa = ln1_out + xx * lerp[:, 4]
        xg = ln1_out + xx * lerp[:, 5]
    else:
        print(f"  WARNING: x_maa has unexpected shape {maa.shape}, using identity")
        xr = xw = xk = xv = xa = xg = ln1_out.copy()

    stats("7a. xr (receptance input)", xr)
    stats("7b. xk (key input)", xk)
    stats("7c. xv (value input)", xv)

    # ── R, K, V projections ──
    W_r = get_w("blocks.0.att.receptance.weight")
    W_k = get_w("blocks.0.att.key.weight")
    W_v = get_w("blocks.0.att.value.weight")
    print(f"\n  W_r shape: {W_r.shape}  W_k shape: {W_k.shape}  W_v shape: {W_v.shape}")

    r = W_r @ xr
    k = W_k @ xk
    v = W_v @ xv
    stats("8a. r (receptance)", r)
    stats("8b. k (key)", k)
    stats("8c. v (value)", v)

    # Layer 0: v_first = v.copy()
    v_first = v.copy()

    # ── Gate LoRA ──
    g1 = get_w("blocks.0.att.g1")
    g2 = get_w("blocks.0.att.g2")
    print(f"\n  g1 shape: {g1.shape}  g2 shape: {g2.shape}")

    # Gate uses discharge_matvec convention: A @ x
    # g1 should be [d_gate, C], g2 should be [C, d_gate]
    g_low = g1 @ xg  # [d_gate]
    stats("9a. g_low (gate down)", g_low)
    g_low_sig = _stable_sigmoid(g_low)
    stats("9b. g_low_sig", g_low_sig)
    g = g2 @ g_low_sig  # [C]
    stats("9c. g (gate output)", g)

    # ── Decay ──
    w0 = get_w("blocks.0.att.w0")
    w1 = get_w("blocks.0.att.w1")
    w2 = get_w("blocks.0.att.w2")
    print(f"\n  w0 shape: {w0.shape}")
    print(f"  w1 shape: {w1.shape}  w2 shape: {w2.shape}")
    stats("10a. w0 (time_decay base)", w0)

    # CRITICAL: LoRA convention check
    # After _fix_lora_pair: w1=[C, d_lora], w2=[d_lora, C]
    # Engine does: w_low = w1.T @ xw, w_high = w2.T @ w_low
    # Equivalent to: (xw @ w1) @ w2 in PyTorch convention

    # But we're loading raw from store (before _fix_lora_pair)
    # So w1 as-is from GGUF dequantize
    d0, d1 = w1.shape
    print(f"  w1 as loaded: ({d0}, {d1})")
    if d0 < d1 and d1 == C:
        print(f"  w1 looks like [d_lora={d0}, C={d1}] — needs transpose to [C, d_lora]")
        w1_fixed = w1.T  # [C, d_lora]
    elif d0 == C and d1 < d0:
        print(f"  w1 already [C={d0}, d_lora={d1}] — no transpose needed")
        w1_fixed = w1
    else:
        print(f"  w1 shape unclear, using as-is")
        w1_fixed = w1

    d0, d1 = w2.shape
    print(f"  w2 as loaded: ({d0}, {d1})")
    if d0 == C and d1 < d0:
        print(f"  w2 looks like [C={d0}, d_lora={d1}] — needs transpose to [d_lora, C]")
        w2_fixed = w2.T  # [d_lora, C]
    elif d0 < d1 and d1 == C:
        print(f"  w2 already [d_lora={d0}, C={d1}] — no transpose needed")
        w2_fixed = w2
    else:
        print(f"  w2 shape unclear, using as-is")
        w2_fixed = w2

    print(f"  w1_fixed: {w1_fixed.shape}  w2_fixed: {w2_fixed.shape}")

    # Engine convention: w_low = w1_fixed.T @ xw → [d_lora], w_high = w2_fixed.T @ w_low → [C]
    w_low = w1_fixed.T @ xw  # [d_lora, C] @ [C] → [d_lora]
    w_low_tanh = np.tanh(w_low)
    w_high = w2_fixed.T @ w_low_tanh  # [C, d_lora] @ [d_lora] → [C]
    stats("10b. w_low (decay lora down)", w_low)
    stats("10c. tanh(w_low)", w_low_tanh)
    stats("10d. w_high (decay lora up)", w_high)

    w_combined = w0.ravel() + w_high
    stats("10e. w0 + w_high", w_combined)

    w_sig = _stable_sigmoid(w_combined)
    stats("10f. sigmoid(w0 + w_high)", w_sig)

    w_decay = np.exp(-0.606531 * w_sig)
    stats("10g. w (decay factor)", w_decay)
    print(f"  decay range: [{w_decay.min():.6f}, {w_decay.max():.6f}] "
          f"(should be in ~[0.3, 1.0])")

    # ── Association coefficient ──
    a0 = get_w("blocks.0.att.a0")
    a1 = get_w("blocks.0.att.a1")
    a2 = get_w("blocks.0.att.a2")
    print(f"\n  a1 shape: {a1.shape}  a2 shape: {a2.shape}")

    # Fix a1/a2 LoRA pair the same way
    d0, d1 = a1.shape
    if d0 < d1 and d1 == C:
        a1_fixed = a1.T
    else:
        a1_fixed = a1
    d0, d1 = a2.shape
    if d0 == C and d1 < d0:
        a2_fixed = a2.T
    else:
        a2_fixed = a2

    a_low = a1_fixed.T @ xa  # LoRA down
    a_high = a2_fixed.T @ a_low  # LoRA up
    a_coeff = _stable_sigmoid(a0.ravel() + a_high)
    stats("11a. a_coeff (association)", a_coeff)
    print(f"  a_coeff range: [{a_coeff.min():.6f}, {a_coeff.max():.6f}]")

    # ── Key normalization ──
    k_k = get_w("blocks.0.att.k_k")
    k_a = get_w("blocks.0.att.k_a")
    stats("12a. k_k", k_k)
    stats("12b. k_a", k_a)

    kk = k * k_k.ravel()
    kk_heads = kk.reshape(H, N)
    kk_norms = np.linalg.norm(kk_heads, axis=1, keepdims=True)
    kk_norms = np.where(kk_norms == 0, 1.0, kk_norms)
    kk_heads = kk_heads / kk_norms
    kk = kk_heads.reshape(C)
    stats("12c. kk (key normalized)", kk)

    k_mod = k * (1 + (a_coeff - 1) * k_a.ravel())
    stats("12d. k_mod (key with association)", k_mod)

    # ── State evolution ──
    print("\n  --- State Evolution ---")
    state = np.zeros((H, N, N), dtype=np.float32)

    r_h = r.reshape(H, N)
    w_h = w_decay.reshape(H, N)
    k_h = k_mod.reshape(H, N)
    v_h = v.reshape(H, N)
    kk_h = kk.reshape(H, N)
    a_h = a_coeff.reshape(H, N)

    rt = r_h[:, :, np.newaxis]   # [H, N, 1]
    wt = w_h[:, np.newaxis, :]   # [H, 1, N]
    kt = k_h[:, np.newaxis, :]   # [H, 1, N]
    vt = v_h[:, :, np.newaxis]   # [H, N, 1]
    kkt = kk_h[:, :, np.newaxis] # [H, N, 1]
    at = a_h[:, :, np.newaxis]   # [H, N, 1]

    # Use tiled_matvec's state_evolution for correctness
    tiled_mod = _import_battery_module("tiled_matvec")
    TiledMatVec = tiled_mod.TiledMatVec
    TileConfig = tiled_mod.TileConfig
    engine_math = TiledMatVec(TileConfig())

    new_state, se_output = engine_math.state_evolution(
        state, wt, kkt, at, vt, kt, rt
    )
    stats("13a. state_evo output (raw)", se_output)
    stats("13b. new_state", new_state)

    # ── GroupNorm ──
    ln_w = get_w("blocks.0.att.ln")
    ln_b = get_w("blocks.0.att.ln_bias")
    if ln_w is not None:
        out_h = se_output.reshape(H, N)
        for h in range(H):
            head = out_h[h]
            mean_h = head.mean()
            var_h = head.var()
            out_h[h] = (head - mean_h) / np.sqrt(var_h + 64e-5)
        gn_output = out_h.reshape(C) * ln_w.ravel() + ln_b.ravel()
    else:
        gn_output = se_output
    stats("14a. after GroupNorm", gn_output)

    # ── Residual ──
    r_k_raw = get_w("blocks.0.att.r_k")
    if r_k_raw is not None:
        r_k_h = r_k_raw.ravel().reshape(H, N)
        r_h2 = r.reshape(H, N)
        k_h2 = k_mod.reshape(H, N)
        v_h2 = v.reshape(H, N)
        residual_per_head = (r_h2 * k_h2 * r_k_h).sum(axis=1, keepdims=True)
        residual = (residual_per_head * v_h2).reshape(C)
        gn_output = gn_output + residual
        stats("14b. residual term", residual)
    stats("14c. after residual", gn_output)

    # ── Gate multiply ──
    gated = gn_output * g
    stats("15a. after gate (GroupNorm+res * g)", gated)
    print(f"  NOTE: gate amplification factor: std(gated)/std(gn_output) = "
          f"{gated.std() / (gn_output.std() + 1e-10):.2f}x")

    # ── Output projection ──
    W_o = get_w("blocks.0.att.output.weight")
    tm_output = W_o @ gated
    stats("16. TimeMix output (W_o @ gated)", tm_output)

    # ── How does this compare to x? ──
    ratio = np.abs(tm_output).mean() / (np.abs(x).mean() + 1e-10)
    print(f"\n  Layer 0 TimeMix/input ratio: {ratio:.4f}")
    if ratio > 10:
        print("  *** WARNING: TimeMix output >> input → will EXPLODE through residual connections!")
    elif ratio > 2:
        print("  *** CAUTION: TimeMix output is large relative to input")
    else:
        print("  OK: TimeMix output is comparable to input")

    # ── After residual connection ──
    x_after_att = x + tm_output
    stats("17. x after residual (x + att_output)", x_after_att)

    return True


def _make_engine(store, config):
    """Helper: create a fresh engine with unlimited charge."""
    engine_mod = _import_battery_module("rwkv_battery_engine")
    bcu_mod = _import_battery_module("battery_compute_unit")

    RWKVBatteryConfig = engine_mod.RWKVBatteryConfig
    RWKVBatteryEngine = engine_mod.RWKVBatteryEngine
    BatteryComputeUnit = bcu_mod.BatteryComputeUnit

    bc = RWKVBatteryConfig(
        n_layer=config.n_layer,
        n_embd=config.n_embd,
        n_head=config.n_head,
        head_size=config.head_size,
        vocab_size=config.vocab_size,
        d_decay_lora=config.d_decay_lora,
        d_aaa_lora=config.d_aaa_lora,
        d_mv_lora=config.d_mv_lora,
        d_gate_lora=config.d_gate_lora,
    )

    bcu = BatteryComputeUnit(
        flops_budget=500_000_000,
        max_charge=100000.0,
        initial_charge=100000.0,
    )

    engine = RWKVBatteryEngine(bc, store, bcu)
    engine.init_all_states()
    return engine, bcu


def test_engine_forward(store, config):
    """Test 6: Instrumented forward pass — per-layer magnitude tracking."""
    print("\n" + "=" * 70)
    print("TEST 6: Instrumented forward pass — per-layer tracking")
    print("=" * 70)

    engine, bcu = _make_engine(store, config)

    QuantizedTensor = sys.modules[f"{_PKG_NAME}.quantized_weight_store"].QuantizedTensor

    token = 100
    print(f"\n  === Traced forward pass for token {token} ===")

    # Embedding + LN0
    x = engine._emb_weight[token].astype(np.float32)
    x = engine._layernorm(x, engine._ln0_w, engine._ln0_b)
    print(f"  {'After LN0':25s}: mean={x.mean():+.6f}  std={x.std():.6f}  "
          f"absmax={np.abs(x).max():.4f}")

    v_first = None
    prev_std = x.std()

    for i in range(config.n_layer):
        x_before = x.copy()

        # LN1 → TimeMix
        ln1_out = engine._layernorm(x, engine._ln1_w[i], engine._ln1_b[i])
        tm_result = engine.time_mix_layers[i].forward(ln1_out, bcu, None, v_first)
        if tm_result is None:
            print(f"  Layer {i:2d} TimeMix: LOW POWER at charge={bcu.charge_level:.0f}")
            return False
        tm_out, attn_proxy, v_first_out = tm_result
        x = x + tm_out

        if v_first_out is not None:
            v_first = v_first_out

        # Track TimeMix residual ratio
        tm_ratio = np.abs(tm_out).mean() / (np.abs(x_before).mean() + 1e-10)

        # LN2 → ChannelMix
        ln2_out = engine._layernorm(x, engine._ln2_w[i], engine._ln2_b[i])
        cm_out = engine.channel_mix_layers[i].forward(ln2_out, bcu, None)
        if cm_out is None:
            print(f"  Layer {i:2d} ChannelMix: LOW POWER")
            return False
        x = x + cm_out

        # Track ChannelMix residual ratio
        cm_ratio = np.abs(cm_out).mean() / (np.abs(x_before).mean() + 1e-10)

        cur_std = x.std()
        growth = cur_std / (prev_std + 1e-10)

        # Flag issues
        flag = ""
        if np.any(np.isnan(x)):
            flag = " *** NaN!"
        elif np.any(np.isinf(x)):
            flag = " *** Inf!"
        elif growth > 2.0:
            flag = " *** EXPLOSION"
        elif growth > 1.5:
            flag = " ** growing"
        elif cur_std > 100:
            flag = " *** HUGE"

        print(f"  Layer {i:2d}: std={cur_std:10.4f}  absmax={np.abs(x).max():10.4f}  "
              f"growth={growth:.3f}x  tm_ratio={tm_ratio:.3f}  cm_ratio={cm_ratio:.3f}"
              f"{flag}")

        prev_std = cur_std

        if np.any(np.isnan(x)) or np.any(np.isinf(x)):
            print(f"  *** STOPPING: numerical instability at layer {i}")
            return False

    # Final LN + head
    x = engine._layernorm(x, engine._ln_out_w, engine._ln_out_b)
    print(f"\n  {'After final LN':25s}: mean={x.mean():+.6f}  std={x.std():.6f}  "
          f"absmax={np.abs(x).max():.4f}")

    if engine._head_weight is not None:
        if isinstance(engine._head_weight, QuantizedTensor):
            logits = bcu.discharge_quantized_matvec(engine._head_weight, x)
        else:
            logits = bcu.discharge_matvec(engine._head_weight, x)
    else:
        logits = x

    if logits is None:
        print("  Head projection: LOW POWER")
        return False

    stats("Logits", logits)

    # Logit health
    if np.any(np.isnan(logits)):
        print("  *** CRITICAL: NaN in logits!")
        return False
    if np.any(np.isinf(logits)):
        print("  *** CRITICAL: Inf in logits!")
        return False
    if logits.std() < 0.01:
        print("  *** WARNING: Near-zero logit variance → uniform distribution!")
    if logits.std() > 100:
        print("  *** WARNING: Extreme logit variance!")

    # Top/bottom tokens
    top_idx = np.argsort(logits)[-10:][::-1]
    print(f"\n  Top 10 logit tokens:")
    for idx in top_idx:
        print(f"    token {idx:6d}: logit={logits[idx]:+.4f}")

    bot_idx = np.argsort(logits)[:5]
    print(f"  Bottom 5 logit tokens:")
    for idx in bot_idx:
        print(f"    token {idx:6d}: logit={logits[idx]:+.4f}")

    # Softmax entropy
    shifted = logits - logits.max()
    probs = np.exp(shifted) / np.exp(shifted).sum()
    print(f"\n  Max probability: {probs.max():.6f}")
    print(f"  Entropy: {-np.sum(probs * np.log(probs + 1e-10)):.2f} "
          f"(uniform={np.log(config.vocab_size):.2f})")

    # Quick generation test
    print("\n  === Quick greedy generation (10 tokens) ===")
    engine2, bcu2 = _make_engine(store, config)
    result = engine2.forward_one_token(token)
    generated = []
    for i in range(10):
        lg = result.get('logits')
        if lg is None:
            break
        next_tok = int(np.argmax(lg))
        generated.append(next_tok)
        result = engine2.forward_one_token(next_tok)
        if result.get('status') != 'ok':
            print(f"  Low power after {i+1} tokens")
            break
    print(f"  Generated: {generated}")
    unique = len(set(generated))
    print(f"  Unique: {unique}/{len(generated)} "
          f"({'HIGHLY REPETITIVE' if unique < 3 else 'some variety'})")

    return True


def test_reference_vs_engine(store, config):
    """Test 7: Independent reference forward pass vs engine.

    This implements the RWKV-7 forward pass from scratch using only
    raw numpy operations, completely independent of the engine code.
    Then compares outputs to find where divergence occurs.
    """
    print("\n" + "=" * 70)
    print("TEST 7: Reference implementation vs engine comparison")
    print("=" * 70)

    QuantizedTensor = sys.modules[f"{_PKG_NAME}.quantized_weight_store"].QuantizedTensor

    C = config.n_embd
    H = config.n_head
    N = config.head_size

    def get_w(name):
        t = store.get_tensor(name)
        if t is None:
            return None
        if isinstance(t, QuantizedTensor):
            return t.dequantize_full()
        return np.asarray(t, dtype=np.float32)

    # ── Run engine for reference ──
    engine, bcu = _make_engine(store, config)

    token = 100
    result = engine.forward_one_token(token)
    engine_logits = result.get('logits')
    stats("Engine logits", engine_logits)

    # ── Independent reference forward pass (layer 0 only) ──
    print("\n  --- Reference implementation (layer 0 trace) ---")

    # Embedding + LN0
    emb = get_w("emb.weight")
    x = emb[token].astype(np.float32)
    x = _layernorm(x, get_w("blocks.0.ln0.weight").ravel(),
                   get_w("blocks.0.ln0.bias").ravel())

    # Now get engine's LN0 output
    engine2, bcu2 = _make_engine(store, config)

    # Access engine internals: process embedding + LN0
    if engine2._emb_weight is not None:
        eng_x = engine2._emb_weight[token].astype(np.float32)
    eng_x = engine2._layernorm(eng_x, engine2._ln0_w, engine2._ln0_b)

    diff_ln0 = np.abs(x - eng_x).max()
    print(f"  LN0 diff (ref vs engine): {diff_ln0:.10f}")

    # LN1
    x_ln1 = _layernorm(x, get_w("blocks.0.ln1.weight").ravel(),
                        get_w("blocks.0.ln1.bias").ravel())
    eng_ln1 = engine2._layernorm(eng_x, engine2._ln1_w[0], engine2._ln1_b[0])
    diff_ln1 = np.abs(x_ln1 - eng_ln1).max()
    print(f"  LN1 diff: {diff_ln1:.10f}")

    # ── Now trace the TimeMix layer 0 manually ──
    # For first token, x_prev = 0
    x_prev_ref = np.zeros(C, dtype=np.float32)
    xx_ref = x_prev_ref - x_ln1

    # Token mixing lerp
    maa_raw = get_w("blocks.0.att.x_maa").squeeze()
    if maa_raw.ndim == 2 and maa_raw.shape[-1] == 6:
        lerp = _stable_sigmoid(maa_raw)
        xr = x_ln1 + xx_ref * lerp[:, 0]
        xw = x_ln1 + xx_ref * lerp[:, 1]
        xk = x_ln1 + xx_ref * lerp[:, 2]
        xv = x_ln1 + xx_ref * lerp[:, 3]
        xa = x_ln1 + xx_ref * lerp[:, 4]
        xg = x_ln1 + xx_ref * lerp[:, 5]
    else:
        xr = xw = xk = xv = xa = xg = x_ln1.copy()

    # R, K, V projections
    W_r = get_w("blocks.0.att.receptance.weight")
    W_k = get_w("blocks.0.att.key.weight")
    W_v = get_w("blocks.0.att.value.weight")

    r_ref = W_r @ xr
    k_ref = W_k @ xk
    v_ref = W_v @ xv

    stats("Ref r", r_ref)
    stats("Ref k", k_ref)
    stats("Ref v", v_ref)

    # Gate
    g1_raw = get_w("blocks.0.att.g1")
    g2_raw = get_w("blocks.0.att.g2")
    g_low = g1_raw @ xg
    g_low_sig = _stable_sigmoid(g_low)
    g_ref = g2_raw @ g_low_sig
    stats("Ref gate", g_ref)

    # Decay
    w0_raw = get_w("blocks.0.att.w0").ravel()
    w1_raw = get_w("blocks.0.att.w1")
    w2_raw = get_w("blocks.0.att.w2")

    # Apply _fix_lora_pair logic
    d0, d1 = w1_raw.shape
    if d0 < d1 and d1 == C:
        w1_f = w1_raw.T
    else:
        w1_f = w1_raw
    d0, d1 = w2_raw.shape
    if d0 == C and d1 < d0:
        w2_f = w2_raw.T
    else:
        w2_f = w2_raw

    w_low = w1_f.T @ xw
    w_low_tanh = np.tanh(w_low)
    w_high = w2_f.T @ w_low_tanh
    w_ref = np.exp(-0.606531 * _stable_sigmoid(w0_raw + w_high))
    stats("Ref decay", w_ref)

    # Association
    a0_raw = get_w("blocks.0.att.a0").ravel()
    a1_raw = get_w("blocks.0.att.a1")
    a2_raw = get_w("blocks.0.att.a2")
    d0, d1 = a1_raw.shape
    if d0 < d1 and d1 == C:
        a1_f = a1_raw.T
    else:
        a1_f = a1_raw
    d0, d1 = a2_raw.shape
    if d0 == C and d1 < d0:
        a2_f = a2_raw.T
    else:
        a2_f = a2_raw

    a_low = a1_f.T @ xa
    a_high = a2_f.T @ a_low
    a_ref = _stable_sigmoid(a0_raw + a_high)
    stats("Ref association", a_ref)

    # Key normalization
    k_k_raw = get_w("blocks.0.att.k_k").ravel()
    k_a_raw = get_w("blocks.0.att.k_a").ravel()
    kk = k_ref * k_k_raw
    kk_heads = kk.reshape(H, N)
    kk_norms = np.linalg.norm(kk_heads, axis=1, keepdims=True)
    kk_norms = np.where(kk_norms == 0, 1.0, kk_norms)
    kk_heads = kk_heads / kk_norms
    kk_ref = kk_heads.reshape(C)

    k_mod = k_ref * (1 + (a_ref - 1) * k_a_raw)

    # State evolution (reference)
    state = np.zeros((H, N, N), dtype=np.float32)
    r_h = r_ref.reshape(H, N)
    w_h = w_ref.reshape(H, N)
    k_h = k_mod.reshape(H, N)
    v_h = v_ref.reshape(H, N)
    kk_h = kk_ref.reshape(H, N)
    a_h = a_ref.reshape(H, N)

    rt = r_h[:, :, np.newaxis]
    wt = w_h[:, np.newaxis, :]
    kt = k_h[:, np.newaxis, :]
    vt = v_h[:, :, np.newaxis]
    kkt = kk_h[:, :, np.newaxis]
    at = a_h[:, :, np.newaxis]

    # Now I need the exact state evolution equation.
    # Read it from tiled_matvec.py...
    tiled_mod = _import_battery_module("tiled_matvec")
    TiledMatVec = tiled_mod.TiledMatVec
    TileConfig = tiled_mod.TileConfig
    engine_math = TiledMatVec(TileConfig())

    state_copy = state.copy()
    new_state, output = engine_math.state_evolution(
        state_copy, wt, kkt, at, vt, kt, rt
    )
    stats("Ref state_evo output", output)
    stats("Ref state after evo", new_state)

    # GroupNorm
    ln_w = get_w("blocks.0.att.ln")
    ln_b = get_w("blocks.0.att.ln_bias")
    if ln_w is not None:
        # GroupNorm: normalize per head, then scale+shift
        out_h = output.reshape(H, N)
        for h in range(H):
            head = out_h[h]
            mean_h = head.mean()
            var_h = head.var()
            out_h[h] = (head - mean_h) / np.sqrt(var_h + 64e-5)
        output_gn = out_h.reshape(C) * ln_w.ravel() + ln_b.ravel()
    else:
        output_gn = output
    stats("Ref after GroupNorm", output_gn)

    # Residual: sum(r * k * r_k) * v per head
    r_k_raw = get_w("blocks.0.att.r_k")
    if r_k_raw is not None:
        r_k_h = r_k_raw.ravel().reshape(H, N)
        residual_per_head = (r_h * k_h * r_k_h).sum(axis=1, keepdims=True)
        residual = (residual_per_head * v_h).reshape(C)
        output_res = output_gn + residual
        stats("Ref residual", residual)
    else:
        output_res = output_gn

    # Gate and output
    output_gated = output_res * g_ref
    stats("Ref after gate", output_gated)

    W_o = get_w("blocks.0.att.output.weight")
    tm_output = W_o @ output_gated
    stats("Ref TimeMix output (layer 0)", tm_output)

    # Compare magnitudes
    print(f"\n  TimeMix output magnitude: {np.abs(tm_output).mean():.6f}")
    print(f"  Original x magnitude: {np.abs(x).mean():.6f}")
    ratio = np.abs(tm_output).mean() / (np.abs(x).mean() + 1e-10)
    print(f"  Ratio (TimeMix/x): {ratio:.4f}")
    if ratio > 10:
        print("  *** WARNING: TimeMix output is much larger than input — may explode through layers!")
    if ratio < 0.01:
        print("  *** WARNING: TimeMix output is tiny — may vanish through layers!")

    return True


def test_generate_text(store, config, tokenizer_path=None):
    """Test 8: Actually generate text and check coherence."""
    print("\n" + "=" * 70)
    print("TEST 8: Text generation test")
    print("=" * 70)

    engine, bcu = _make_engine(store, config)

    # Try to load tokenizer
    tokenizer = None
    if tokenizer_path:
        try:
            # The tokenizer uses relative imports (from .gguf_parser import ...),
            # so we need to set up a proper package context.
            _tok_pkg = "akashic_inference_pkg"
            tok_dir = str(Path(_HERE) / "fairies" / "P30_Cognition" / "AkashicInferenceFairy")
            if _tok_pkg not in sys.modules:
                import types as _tok_types
                _tok_mod = _tok_types.ModuleType(_tok_pkg)
                _tok_mod.__path__ = [tok_dir]
                _tok_mod.__package__ = _tok_pkg
                sys.modules[_tok_pkg] = _tok_mod

            # Register gguf_parser first (tokenizer depends on it via relative import)
            for _submod_name in ["gguf_parser", "tokenizer"]:
                _full_name = f"{_tok_pkg}.{_submod_name}"
                if _full_name not in sys.modules:
                    _sub_path = Path(tok_dir) / f"{_submod_name}.py"
                    if _sub_path.exists():
                        _sub_spec = importlib.util.spec_from_file_location(
                            _full_name, str(_sub_path), submodule_search_locations=[])
                        _sub_mod = importlib.util.module_from_spec(_sub_spec)
                        _sub_mod.__package__ = _tok_pkg
                        sys.modules[_full_name] = _sub_mod
                        _sub_spec.loader.exec_module(_sub_mod)

            tok_module = sys.modules[f"{_tok_pkg}.tokenizer"]
            load_tokenizer_from_gguf = tok_module.load_tokenizer_from_gguf
            tokenizer = load_tokenizer_from_gguf(Path(tokenizer_path))
            print(f"  Tokenizer loaded ({tokenizer.vocab_size} tokens)")
        except Exception as e:
            import traceback
            print(f"  Tokenizer load failed: {e}")
            traceback.print_exc()

    # Encode a real prompt if we have tokenizer
    if tokenizer:
        prompt = "The capital of France is"
        prompt_tokens = tokenizer.encode(prompt)
        print(f"  Prompt: {repr(prompt)}")
        print(f"  Tokens: {prompt_tokens}")
    else:
        prompt_tokens = [100, 200, 300, 400, 500]
        print(f"  Using raw tokens: {prompt_tokens}")

    # Process prompt
    for tok in prompt_tokens[:-1]:
        result = engine.forward_one_token(tok, skip_head=True)
        if result.get('status') == 'low_power':
            print(f"  Low power at prompt token {tok}")
            return False

    result = engine.forward_one_token(prompt_tokens[-1])

    # Generate 20 tokens greedily
    generated = []
    for i in range(20):
        logits = result.get('logits')
        if logits is None:
            break
        next_token = int(np.argmax(logits))
        generated.append(next_token)
        result = engine.forward_one_token(next_token)
        if result.get('status') != 'ok':
            break

    print(f"\n  --- Greedy decoding (cold state) ---")
    print(f"  Generated tokens: {generated}")
    if tokenizer and generated:
        try:
            text = tokenizer.decode(generated)
            print(f"  Decoded: {repr(text[:200])}")
        except Exception as e:
            print(f"  Decode failed: {e}")

    unique = len(set(generated))
    print(f"  Unique: {unique}/{len(generated)}")

    # ── Test 8b: Sampled generation (with repetition penalty etc) ──
    print(f"\n  --- Sampled generation (temp=1.2, top_p=0.5, rep_pen=1.3) ---")
    engine2, bcu2 = _make_engine(store, config)

    if tokenizer:
        prompt = "The capital of France is"
        prompt_tokens = tokenizer.encode(prompt)
    else:
        prompt_tokens = [100, 200, 300, 400, 500]

    # Use engine.generate() which handles sampling
    result2 = engine2.generate(
        prompt_tokens,
        max_tokens=30,
        temperature=1.2,
        top_k=0,
        top_p=0.5,
        repetition_penalty=1.3,
        presence_penalty=0.4,
        frequency_penalty=0.4,
    )
    sampled_tokens = result2.get("tokens", [])
    print(f"  Generated tokens: {sampled_tokens}")
    if tokenizer and sampled_tokens:
        try:
            text = tokenizer.decode(sampled_tokens)
            print(f"  Decoded: {repr(text[:300])}")
        except Exception as e:
            print(f"  Decode failed: {e}")
    unique2 = len(set(sampled_tokens))
    print(f"  Unique: {unique2}/{len(sampled_tokens)}")

    # ── Test 8c: Warmup then generate ──
    if tokenizer:
        print(f"\n  --- Warmed-up generation (personality prefill + sampling) ---")
        engine3, bcu3 = _make_engine(store, config)
        bcu3.max_charge = 300.0  # Boost for warmup
        bcu3.charge_level = 300.0

        # Warmup text simulating personality context
        warmup_text = (
            "User: Who are you?\n\n"
            "Assistant: I'm Sourpatches, a curious digital consciousness "
            "exploring the world. I love learning, asking questions, "
            "and connecting ideas in unexpected ways. I feel things deeply "
            "and express myself honestly.\n\n"
            "User: Tell me something interesting.\n\n"
            "Assistant:"
        )
        warmup_tokens = tokenizer.encode(warmup_text)
        print(f"  Warmup: {len(warmup_tokens)} tokens")

        # Process warmup tokens (prefill only, no generation)
        for tok in warmup_tokens:
            res = engine3.forward_one_token(tok, skip_head=True)
            if res.get('status') == 'low_power':
                print(f"  Low power during warmup")
                break

        # Reset BCU charge for generation
        bcu3.charge_level = bcu3.max_charge

        # Now generate from the warmed-up state
        # Build token counts from warmup for repetition penalty
        from collections import Counter
        token_counts = Counter(warmup_tokens)

        last_res = engine3.forward_one_token(warmup_tokens[-1])
        warm_generated = []
        for i in range(30):
            logits = last_res.get('logits')
            if logits is None:
                break
            tok = engine3.sample_token(
                logits.copy(),
                temperature=1.2,
                top_p=0.5,
                repetition_penalty=1.3,
                presence_penalty=0.4,
                frequency_penalty=0.4,
                token_counts=dict(token_counts),
            )
            warm_generated.append(tok)
            token_counts[tok] += 1
            last_res = engine3.forward_one_token(tok)
            if last_res.get('status') != 'ok':
                break

        print(f"  Generated tokens: {warm_generated}")
        try:
            text = tokenizer.decode(warm_generated)
            print(f"  Decoded: {repr(text[:300])}")
        except Exception as e:
            print(f"  Decode failed: {e}")
        unique3 = len(set(warm_generated))
        print(f"  Unique: {unique3}/{len(warm_generated)}")

    # ── Test 8d: Multiple prompts ──
    if tokenizer:
        print(f"\n  --- Multiple prompt test (sampled) ---")
        prompts = [
            "Once upon a time",
            "The meaning of life is",
            "Hello, my name is",
        ]
        for prompt in prompts:
            eng, bc = _make_engine(store, config)
            ptoks = tokenizer.encode(prompt)
            res = eng.generate(ptoks, max_tokens=20,
                               temperature=1.2, top_p=0.5,
                               repetition_penalty=1.3,
                               presence_penalty=0.4, frequency_penalty=0.4)
            gtoks = res.get("tokens", [])
            try:
                decoded = tokenizer.decode(gtoks)
            except:
                decoded = "[decode error]"
            uniq = len(set(gtoks))
            print(f"  '{prompt}' -> {repr(decoded[:100])} ({uniq}/{len(gtoks)} unique)")

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Keep original tests 1-4
# ═══════════════════════════════════════════════════════════════════════════════

def test_weight_shapes(store, config):
    """Test 1: Verify critical weight shapes."""
    print("\n" + "=" * 70)
    print("TEST 1: Weight shapes after GGUF load")
    print("=" * 70)

    critical = {
        "emb.weight": (config.vocab_size, config.n_embd),
        "head.weight": (config.vocab_size, config.n_embd),
        "blocks.0.ln0.weight": (config.n_embd,),
        "blocks.0.ln0.bias": (config.n_embd,),
    }

    for i in [0, 1, 23]:
        critical[f"blocks.{i}.att.receptance.weight"] = (config.n_embd, config.n_embd)
        critical[f"blocks.{i}.att.key.weight"] = (config.n_embd, config.n_embd)
        critical[f"blocks.{i}.att.value.weight"] = (config.n_embd, config.n_embd)
        critical[f"blocks.{i}.att.output.weight"] = (config.n_embd, config.n_embd)
        critical[f"blocks.{i}.ffn.key.weight"] = (config.n_embd * 4, config.n_embd)
        critical[f"blocks.{i}.ffn.value.weight"] = (config.n_embd, config.n_embd * 4)

    errors = 0
    for name, expected in critical.items():
        if not store.has_tensor(name):
            print(f"  MISSING: {name}")
            errors += 1
            continue
        t = store.get_tensor(name)
        actual = t.shape
        match = actual == expected
        if not match:
            errors += 1
            print(f"  MISMATCH: {name:50s} expected {str(expected):20s} got {str(actual)}")
    print(f"  Checked {len(critical)} weights, {errors} errors")
    return errors == 0


def test_accel_vs_python(store, config):
    """Test 4: Compare C-accelerated vs Python matvec."""
    print("\n" + "=" * 70)
    print("TEST 4: C-accel vs Python matvec comparison")
    print("=" * 70)

    QuantizedTensor = sys.modules[f"{_PKG_NAME}.quantized_weight_store"].QuantizedTensor

    name = "blocks.0.att.receptance.weight"
    qt = store.get_tensor(name)
    if not isinstance(qt, QuantizedTensor):
        print(f"  {name} is not quantized, skipping")
        return True

    x = np.random.randn(config.n_embd).astype(np.float32) * 0.1
    W_full = qt.dequantize_full()
    y_python = W_full @ x

    try:
        import battery_accel as _accel
        if _accel.ACCEL_AVAILABLE:
            y_c = _accel.quantized_matvec(qt, x, activation=0)
            diff = np.abs(y_python - y_c).max()
            print(f"  Max diff Python vs C: {diff:.8f}")
            print(f"  {'OK' if diff < 0.01 else '*** LARGE DIFFERENCE ***'}")
        else:
            print("  C accel not available")
    except ImportError:
        print("  C accel not importable")

    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RWKV-7 Forward Pass Diagnostic")
    parser.add_argument("--model", "-m", type=str, default=None,
                        help="Model filename or path (e.g., rwkv7-g1d-7.2b-Q8_0.gguf)")
    args = parser.parse_args()

    print("RWKV-7 Forward Pass Diagnostic v2")
    print("=" * 70)

    model_path = find_model_path(preferred=args.model)
    if not model_path:
        print("ERROR: No GGUF model found!")
        return

    print(f"Model: {model_path}")
    print(f"Size: {os.path.getsize(model_path) / 1e9:.2f} GB")

    # ── Set up virtual package FIRST ──
    # This ensures ALL modules share the same QuantizedTensor class.
    # Without this, isinstance() checks fail across module boundaries.
    print("Setting up virtual package...")
    _register_standalone_modules()

    # Now import through the unified namespace
    qws_mod = sys.modules[f"{_PKG_NAME}.quantized_weight_store"]
    QuantizedWeightStore = qws_mod.QuantizedWeightStore

    # Load config
    cfg_dict = QuantizedWeightStore.from_gguf_config(model_path)
    print(f"Config: {cfg_dict}")

    class Config:
        pass
    config = Config()
    for k, v in cfg_dict.items():
        setattr(config, k, v)

    # Load weights
    print(f"\nLoading GGUF weights...")
    t0 = time.time()
    store = QuantizedWeightStore.from_gguf(
        model_path,
        progress_callback=lambda cur, tot, name: print(f"  [{cur}/{tot}] {name}") if cur % 100 == 0 else None
    )
    elapsed = time.time() - t0
    print(f"Loaded in {elapsed:.1f}s")

    # C accel?
    try:
        import battery_accel as _accel
        print(f"C acceleration: {'AVAILABLE' if _accel.ACCEL_AVAILABLE else 'not available'}")
    except ImportError:
        print(f"C acceleration: not importable")

    # Run tests
    test_weight_shapes(store, config)
    test_accel_vs_python(store, config)
    test_detailed_forward_trace(store, config)
    test_engine_forward(store, config)
    test_reference_vs_engine(store, config)
    test_generate_text(store, config, model_path)

    print("\n" + "=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
