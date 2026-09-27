"""
test_battery_accel.py -- Correctness + benchmark for the fused C matvec kernel.

Tests:
  1. Correctness: C kernel vs NumPy reference (np.allclose atol=1e-4)
  2. Activations: sigmoid, relu_sq, tanh fused variants
  3. Edge cases: M not divisible by 8, K not divisible by 64
  4. Benchmark: wall-clock comparison for real RWKV dimensions

Run:  python test_battery_accel.py
"""

import sys
import time
import numpy as np

# Add parent dir to path
sys.path.insert(0, ".")

from quantized_weight_store import QuantizedTensor, QuantizationConfig
import battery_accel


# ---- Helpers ----

def make_qt(M, K, seed=42):
    """Create a QuantizedTensor from random float data."""
    rng = np.random.RandomState(seed)
    W = rng.randn(M, K).astype(np.float32) * 0.1
    config = QuantizationConfig(bits=8, group_size=64)
    return QuantizedTensor.from_float(W, config), W


def numpy_matvec(qt, x):
    """Reference: full dequantize then matvec."""
    M, K = qt.shape
    K_padded = qt.data.shape[1]
    n_groups = qt.scales.shape[1]
    gs = qt.group_size

    # Full dequantize
    dequant = np.zeros((M, K_padded), dtype=np.float32)
    for g in range(n_groups):
        k0 = g * gs
        k1 = k0 + gs
        dequant[:, k0:k1] = qt.data[:, k0:k1].astype(np.float32) * qt.scales[:, g:g+1]

    # Matvec (only use K columns, not padding)
    return dequant[:, :K] @ x[:K]


def apply_activation_np(y, act):
    """NumPy reference activations."""
    if act == 0:
        return y
    elif act == 1:  # sigmoid
        return 1.0 / (1.0 + np.exp(-y))
    elif act == 2:  # relu_sq
        r = np.maximum(y, 0.0)
        return r * r
    elif act == 3:  # tanh
        return np.tanh(y)


# ---- Tests ----

def test_basic_correctness():
    """Test C kernel matches NumPy for standard dimensions."""
    print("\n=== Test: Basic correctness ===")
    dims = [
        (64, 64,     "tiny"),
        (256, 256,   "small"),
        (2048, 2048, "TimeMix projection"),
    ]

    for M, K, label in dims:
        qt, _ = make_qt(M, K)
        x = np.random.randn(K).astype(np.float32)

        y_c = battery_accel.quantized_matvec(qt, x, activation=0)
        y_np = numpy_matvec(qt, x)

        maxdiff = np.max(np.abs(y_c - y_np))
        match = np.allclose(y_c, y_np, atol=1e-4, rtol=1e-4)
        status = "PASS" if match else "FAIL"
        print(f"  [{status}] {label} [{M},{K}]: maxdiff={maxdiff:.2e}")
        if not match:
            # Show first few diffs for debugging
            diffs = np.abs(y_c - y_np)
            worst = np.argsort(diffs)[-5:]
            for idx in worst:
                print(f"    row {idx}: C={y_c[idx]:.6f} NP={y_np[idx]:.6f} diff={diffs[idx]:.2e}")

    return True


def test_activations():
    """Test fused activations match NumPy."""
    print("\n=== Test: Fused activations ===")
    M, K = 512, 2048
    qt, _ = make_qt(M, K)
    x = np.random.randn(K).astype(np.float32)

    acts = [(0, "none"), (1, "sigmoid"), (2, "relu_sq"), (3, "tanh")]

    for act_code, act_name in acts:
        y_c = battery_accel.quantized_matvec(qt, x, activation=act_code)
        y_raw = numpy_matvec(qt, x)
        y_np = apply_activation_np(y_raw, act_code)

        maxdiff = np.max(np.abs(y_c - y_np))
        # Sigmoid/tanh use fast approximation, allow slightly larger tolerance
        tol = 1e-3 if act_code in (1, 3) else 1e-4
        match = np.allclose(y_c, y_np, atol=tol, rtol=tol)
        status = "PASS" if match else "FAIL"
        print(f"  [{status}] activation={act_name}: maxdiff={maxdiff:.2e} (tol={tol})")


def test_edge_cases():
    """Test dimensions not divisible by 8 or 64."""
    print("\n=== Test: Edge cases ===")
    cases = [
        (7, 64,    "M=7 (not mult of 8)"),
        (13, 128,  "M=13 (not mult of 8)"),
        (64, 100,  "K=100 (not mult of 64, padded to 128)"),
        (1, 2048,  "M=1 (single row)"),
        (3, 50,    "M=3, K=50 (both odd)"),
    ]

    for M, K, label in cases:
        qt, _ = make_qt(M, K)
        x = np.random.randn(K).astype(np.float32)

        y_c = battery_accel.quantized_matvec(qt, x, activation=0)
        y_np = numpy_matvec(qt, x)

        maxdiff = np.max(np.abs(y_c - y_np))
        match = np.allclose(y_c, y_np, atol=1e-4, rtol=1e-4)
        status = "PASS" if match else "FAIL"
        print(f"  [{status}] {label}: maxdiff={maxdiff:.2e}")


def test_large_dimensions():
    """Test real RWKV dimensions."""
    print("\n=== Test: Large (RWKV) dimensions ===")
    dims = [
        (8192, 2048,  "ChannelMix key"),
        (2048, 8192,  "ChannelMix value"),
        (65536, 2048, "Head projection"),
    ]

    for M, K, label in dims:
        qt, _ = make_qt(M, K)
        x = np.random.randn(K).astype(np.float32)

        y_c = battery_accel.quantized_matvec(qt, x, activation=0)
        y_np = numpy_matvec(qt, x)

        maxdiff = np.max(np.abs(y_c - y_np))
        match = np.allclose(y_c, y_np, atol=1e-4, rtol=1e-4)
        status = "PASS" if match else "FAIL"
        print(f"  [{status}] {label} [{M},{K}]: maxdiff={maxdiff:.2e}")


# ---- State Evolution Tests ----

def numpy_state_evolution(state, wt, kkt, at, vt, kt, rt):
    """NumPy reference matching tiled_matvec.py:state_evolution."""
    # state [H,N,N], wt [H,1,N], kkt [H,N,1], at [H,N,1], vt [H,N,1], kt [H,1,N], rt [H,N,1]
    state = state * wt                                      # decay
    neg_kkt = -kkt
    icl_a = np.matmul(state, neg_kkt)                       # [H,N,N]@[H,N,1] → [H,N,1]
    kkt_at_T = (kkt * at).transpose(0, 2, 1)               # [H,N,1]→[H,1,N]
    icl = np.matmul(icl_a, kkt_at_T)                       # [H,N,1]@[H,1,N] → [H,N,N]
    vk = np.matmul(vt, kt)                                 # [H,N,1]@[H,1,N] → [H,N,N]
    state = state + icl + vk
    output = np.matmul(state, rt).squeeze(-1).reshape(-1)   # [H*N]
    return state, output


def test_state_evolution():
    """Test C state evolution matches NumPy reference."""
    print("\n=== Test: State Evolution ===")
    rng = np.random.RandomState(42)

    cases = [
        (32, 64, "RWKV-7 real dims [32,64,64]"),
        (4,  8,  "tiny [4,8,8]"),
        (1,  64, "single head [1,64,64]"),
    ]

    for H, N, label in cases:
        state = rng.randn(H, N, N).astype(np.float32) * 0.01
        wt  = rng.rand(H, 1, N).astype(np.float32) * 0.5 + 0.5   # decay in [0.5, 1.0]
        kkt = rng.randn(H, N, 1).astype(np.float32) * 0.1
        at  = rng.randn(H, N, 1).astype(np.float32) * 0.1
        vt  = rng.randn(H, N, 1).astype(np.float32) * 0.1
        kt  = rng.randn(H, 1, N).astype(np.float32) * 0.1
        rt  = rng.randn(H, N, 1).astype(np.float32) * 0.1

        # NumPy reference
        state_np, out_np = numpy_state_evolution(
            state.copy(), wt, kkt, at, vt, kt, rt)

        # C kernel (modifies state in-place)
        state_c = state.copy()
        state_c = np.ascontiguousarray(state_c)
        out_c = battery_accel.state_evolution(state_c, wt, kkt, at, vt, kt, rt)

        # Check output
        maxdiff_out = np.max(np.abs(out_c - out_np))
        match_out = np.allclose(out_c, out_np, atol=1e-4, rtol=1e-4)

        # Check state
        maxdiff_state = np.max(np.abs(state_c - state_np))
        match_state = np.allclose(state_c, state_np, atol=1e-4, rtol=1e-4)

        status = "PASS" if (match_out and match_state) else "FAIL"
        print(f"  [{status}] {label}: out_diff={maxdiff_out:.2e}, state_diff={maxdiff_state:.2e}")

        if not match_out or not match_state:
            if not match_out:
                diffs = np.abs(out_c - out_np)
                worst = np.argsort(diffs)[-5:]
                for idx in worst:
                    print(f"    out[{idx}]: C={out_c[idx]:.6f} NP={out_np[idx]:.6f} diff={diffs[idx]:.2e}")
            if not match_state:
                print(f"    state maxdiff: {maxdiff_state:.2e}")


# ---- LayerNorm Tests ----

def numpy_layernorm(x, weight, bias, eps=1e-5):
    """NumPy reference matching tiled_matvec.py:layernorm."""
    mean = np.mean(x)
    var = np.var(x)
    x_norm = (x - mean) / np.sqrt(var + eps)
    return x_norm * weight + bias


def test_layernorm():
    """Test C layernorm matches NumPy reference."""
    print("\n=== Test: LayerNorm ===")
    rng = np.random.RandomState(42)

    cases = [
        (2048,  "RWKV embed dim [2048]"),
        (64,    "small [64]"),
        (4096,  "large [4096]"),
    ]

    for C, label in cases:
        x = rng.randn(C).astype(np.float32)
        w = rng.randn(C).astype(np.float32) * 0.5 + 1.0
        b = rng.randn(C).astype(np.float32) * 0.1

        y_np = numpy_layernorm(x, w, b)
        y_c = battery_accel.layernorm(x, w, b)

        maxdiff = np.max(np.abs(y_c - y_np))
        match = np.allclose(y_c, y_np, atol=1e-5, rtol=1e-5)
        status = "PASS" if match else "FAIL"
        print(f"  [{status}] {label}: maxdiff={maxdiff:.2e}")

        if not match:
            diffs = np.abs(y_c - y_np)
            worst = np.argsort(diffs)[-5:]
            for idx in worst:
                print(f"    [{idx}]: C={y_c[idx]:.6f} NP={y_np[idx]:.6f} diff={diffs[idx]:.2e}")


# ---- GroupNorm Tests ----

def numpy_groupnorm(x, num_groups, weight, bias, eps=1e-5):
    """NumPy reference matching tiled_matvec.py:groupnorm."""
    C = x.shape[0]
    group_size = C // num_groups
    x_grouped = x.reshape(num_groups, group_size)
    mean = x_grouped.mean(axis=1, keepdims=True)
    var = x_grouped.var(axis=1, keepdims=True)
    x_norm = (x_grouped - mean) / np.sqrt(var + eps)
    x_norm = x_norm.reshape(C)
    return x_norm * weight + bias


def test_groupnorm():
    """Test C groupnorm matches NumPy reference."""
    print("\n=== Test: GroupNorm ===")
    rng = np.random.RandomState(42)

    cases = [
        (2048, 32, "RWKV attention [2048, 32 groups]"),
        (64,   8,  "small [64, 8 groups]"),
        (4096, 64, "large [4096, 64 groups]"),
    ]

    for C, ng, label in cases:
        x = rng.randn(C).astype(np.float32)
        w = rng.randn(C).astype(np.float32) * 0.5 + 1.0
        b = rng.randn(C).astype(np.float32) * 0.1

        y_np = numpy_groupnorm(x, ng, w, b)
        y_c = battery_accel.groupnorm(x, w, b, ng)

        maxdiff = np.max(np.abs(y_c - y_np))
        match = np.allclose(y_c, y_np, atol=1e-5, rtol=1e-5)
        status = "PASS" if match else "FAIL"
        print(f"  [{status}] {label}: maxdiff={maxdiff:.2e}")

        if not match:
            diffs = np.abs(y_c - y_np)
            worst = np.argsort(diffs)[-5:]
            for idx in worst:
                print(f"    [{idx}]: C={y_c[idx]:.6f} NP={y_np[idx]:.6f} diff={diffs[idx]:.2e}")


# ---- Benchmarks ----

def bench():
    """Benchmark C kernel vs NumPy tile loop."""
    print("\n=== Benchmark: C kernel vs NumPy ===")
    print(f"  ACCEL_AVAILABLE: {battery_accel.ACCEL_AVAILABLE}")

    dims = [
        (2048, 2048,  3, "TimeMix [2048,2048]"),
        (8192, 2048,  3, "ChannelMix key [8192,2048]"),
        (2048, 8192,  3, "ChannelMix value [2048,8192]"),
        (65536, 2048, 1, "Head projection [65536,2048]"),
    ]

    for M, K, iters, label in dims:
        qt, _ = make_qt(M, K, seed=123)
        x = np.random.randn(K).astype(np.float32)

        # Warm up
        _ = battery_accel.quantized_matvec(qt, x)
        _ = numpy_matvec(qt, x)

        # Benchmark C
        t0 = time.perf_counter()
        for _ in range(iters):
            y_c = battery_accel.quantized_matvec(qt, x)
        t_c = (time.perf_counter() - t0) / iters

        # Benchmark NumPy (full dequant + matmul)
        t0 = time.perf_counter()
        for _ in range(iters):
            y_np = numpy_matvec(qt, x)
        t_np = (time.perf_counter() - t0) / iters

        speedup = t_np / t_c if t_c > 0 else 0
        print(f"  {label}:")
        print(f"    C:     {t_c*1000:8.2f} ms")
        print(f"    NumPy: {t_np*1000:8.2f} ms")
        print(f"    Speedup: {speedup:.1f}x")


def bench_state_evolution():
    """Benchmark state evolution: C vs NumPy."""
    print("\n=== Benchmark: State Evolution ===")
    rng = np.random.RandomState(123)
    H, N = 32, 64
    iters = 10

    state = rng.randn(H, N, N).astype(np.float32) * 0.01
    wt  = rng.rand(H, 1, N).astype(np.float32) * 0.5 + 0.5
    kkt = rng.randn(H, N, 1).astype(np.float32) * 0.1
    at  = rng.randn(H, N, 1).astype(np.float32) * 0.1
    vt  = rng.randn(H, N, 1).astype(np.float32) * 0.1
    kt  = rng.randn(H, 1, N).astype(np.float32) * 0.1
    rt  = rng.randn(H, N, 1).astype(np.float32) * 0.1

    # Warm up
    _ = battery_accel.state_evolution(state.copy(), wt, kkt, at, vt, kt, rt)
    _ = numpy_state_evolution(state.copy(), wt, kkt, at, vt, kt, rt)

    # C
    t0 = time.perf_counter()
    for _ in range(iters):
        sc = state.copy()
        sc = np.ascontiguousarray(sc)
        _ = battery_accel.state_evolution(sc, wt, kkt, at, vt, kt, rt)
    t_c = (time.perf_counter() - t0) / iters

    # NumPy
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = numpy_state_evolution(state.copy(), wt, kkt, at, vt, kt, rt)
    t_np = (time.perf_counter() - t0) / iters

    speedup = t_np / t_c if t_c > 0 else 0
    print(f"  State Evolution [H={H}, N={N}]:")
    print(f"    C:     {t_c*1000:8.3f} ms")
    print(f"    NumPy: {t_np*1000:8.3f} ms")
    print(f"    Speedup: {speedup:.1f}x")


def bench_layernorm():
    """Benchmark layernorm: C vs NumPy."""
    print("\n=== Benchmark: LayerNorm ===")
    rng = np.random.RandomState(123)
    C = 2048
    iters = 100

    x = rng.randn(C).astype(np.float32)
    w = rng.randn(C).astype(np.float32)
    b = rng.randn(C).astype(np.float32)

    # Warm up
    _ = battery_accel.layernorm(x, w, b)
    _ = numpy_layernorm(x, w, b)

    # C
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = battery_accel.layernorm(x, w, b)
    t_c = (time.perf_counter() - t0) / iters

    # NumPy
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = numpy_layernorm(x, w, b)
    t_np = (time.perf_counter() - t0) / iters

    speedup = t_np / t_c if t_c > 0 else 0
    print(f"  LayerNorm [C={C}]:")
    print(f"    C:     {t_c*1000:8.4f} ms")
    print(f"    NumPy: {t_np*1000:8.4f} ms")
    print(f"    Speedup: {speedup:.1f}x")


def bench_groupnorm():
    """Benchmark groupnorm: C vs NumPy."""
    print("\n=== Benchmark: GroupNorm ===")
    rng = np.random.RandomState(123)
    C = 2048
    ng = 32
    iters = 100

    x = rng.randn(C).astype(np.float32)
    w = rng.randn(C).astype(np.float32)
    b = rng.randn(C).astype(np.float32)

    # Warm up
    _ = battery_accel.groupnorm(x, w, b, ng)
    _ = numpy_groupnorm(x, ng, w, b)

    # C
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = battery_accel.groupnorm(x, w, b, ng)
    t_c = (time.perf_counter() - t0) / iters

    # NumPy
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = numpy_groupnorm(x, ng, w, b)
    t_np = (time.perf_counter() - t0) / iters

    speedup = t_np / t_c if t_c > 0 else 0
    print(f"  GroupNorm [C={C}, groups={ng}]:")
    print(f"    C:     {t_c*1000:8.4f} ms")
    print(f"    NumPy: {t_np*1000:8.4f} ms")
    print(f"    Speedup: {speedup:.1f}x")


# ---- Main ----

if __name__ == "__main__":
    print("=" * 60)
    print("Battery Accel Test Suite (v2)")
    print("=" * 60)
    print(f"  ACCEL_AVAILABLE: {battery_accel.ACCEL_AVAILABLE}")

    if not battery_accel.ACCEL_AVAILABLE:
        print("  ERROR: C kernel not available!")
        sys.exit(1)

    # Phase 1 tests
    test_basic_correctness()
    test_activations()
    test_edge_cases()
    test_large_dimensions()

    # Phase 2 tests
    test_state_evolution()
    test_layernorm()
    test_groupnorm()

    # Benchmarks
    bench()
    bench_state_evolution()
    bench_layernorm()
    bench_groupnorm()

    print("\n" + "=" * 60)
    print("All tests complete.")
    print("=" * 60)
