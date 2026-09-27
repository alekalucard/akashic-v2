"""Full forward pass comparison: Python numpy vs Rust.

Computes the full 24-layer forward pass in Python using raw numpy
(matching exactly what Rust does), then compares logits.
"""
import sys
import os
import numpy as np
import time

sys.path.insert(0, r"F:\Sandbox\failure_factory\akashic_v2")
FAIRY_DIR = r"F:\Sandbox\failure_factory\akashic_v2\fairies\P30_Cognition\AkashicInferenceFairy"
sys.path.insert(0, FAIRY_DIR)

try:
    import torch
    torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
    os.environ['PATH'] = torch_lib + ';' + os.environ.get('PATH', '')
except ImportError:
    pass

GGUF_PATH = os.path.join(FAIRY_DIR, "models", "rwkv7-official-1.5B-Q8_0.gguf")

from gguf_parser import GGUFParser, GGUFFile
from quantization import dequantize_tensor

# Parse GGUF
parser = GGUFParser()
gguf = parser.parse(GGUF_PATH)

C = 2048
H = 32
N = 64
n_layer = 24

def get_flat(name):
    info = gguf.tensors[name]
    raw = gguf.get_tensor_data(name)
    return dequantize_tensor(raw, info.type_id, info.shape, to_torch=False).flatten().astype(np.float32)

def layer_norm(x, weight, bias, eps=1e-5):
    mean = x.mean()
    var = ((x - mean) ** 2).mean()
    inv_std = 1.0 / np.sqrt(var + eps)
    return (x - mean) * inv_std * weight + bias

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -80, 80)))

def matmul_vec(x, M_flat, k, n):
    M = M_flat[:k*n].reshape(k, n)
    return x @ M

def group_norm(x, num_groups, group_size, weight, bias, eps=64e-5):
    result = x.copy()
    for g in range(num_groups):
        s = g * group_size
        e = s + group_size
        seg = result[s:e]
        mean = seg.mean()
        var = ((seg - mean) ** 2).mean()
        inv_std = 1.0 / np.sqrt(var + eps)
        result[s:e] = (seg - mean) * inv_std * weight[s:e] + bias[s:e]
    return result

# ===== Load ALL weights =====
print("Loading weights...")
t0 = time.time()

# Embedding
emb_raw = gguf.get_tensor_data("token_embd.weight")
emb_info = gguf.tensors["token_embd.weight"]
emb = dequantize_tensor(emb_raw, emb_info.type_id, emb_info.shape, to_torch=False)
if emb.shape[0] < emb.shape[1]:
    emb = emb.T  # [V, C]
emb = emb.astype(np.float32)

emb_ln_w = get_flat("token_embd_norm.weight")[:C]
emb_ln_b = get_flat("token_embd_norm.bias")[:C]

# Output
head_ln_w = get_flat("output_norm.weight")[:C]
head_ln_b = get_flat("output_norm.bias")[:C]
head_weight = get_flat("output.weight")

# Per-layer weights
layers = []
for L in range(n_layer):
    prefix = f"blk.{L}."
    layer = {
        'ln1_w': get_flat(f"{prefix}attn_norm.weight")[:C],
        'ln1_b': get_flat(f"{prefix}attn_norm.bias")[:C],
        'ln2_w': get_flat(f"{prefix}attn_norm_2.weight")[:C],
        'ln2_b': get_flat(f"{prefix}attn_norm_2.bias")[:C],
        # TimeMix
        'lerp_fused': get_flat(f"{prefix}time_mix_lerp_fused.weight"),
        'receptance': get_flat(f"{prefix}time_mix_receptance.weight"),
        'key': get_flat(f"{prefix}time_mix_key.weight"),
        'value': get_flat(f"{prefix}time_mix_value.weight"),
        'output': get_flat(f"{prefix}time_mix_output.weight"),
        'w0': get_flat(f"{prefix}time_mix_w0.weight")[:C],
        'w1': get_flat(f"{prefix}time_mix_w1.weight"),
        'w2': get_flat(f"{prefix}time_mix_w2.weight"),
        'a0': get_flat(f"{prefix}time_mix_a0.weight")[:C],
        'a1': get_flat(f"{prefix}time_mix_a1.weight"),
        'a2': get_flat(f"{prefix}time_mix_a2.weight"),
        'v0': get_flat(f"{prefix}time_mix_v0.weight")[:C],
        'v1': get_flat(f"{prefix}time_mix_v1.weight"),
        'v2': get_flat(f"{prefix}time_mix_v2.weight"),
        'g1': get_flat(f"{prefix}time_mix_g1.weight"),
        'g2': get_flat(f"{prefix}time_mix_g2.weight"),
        'k_k': get_flat(f"{prefix}time_mix_k_k.weight")[:C],
        'k_a': get_flat(f"{prefix}time_mix_k_a.weight")[:C],
        'r_k': get_flat(f"{prefix}time_mix_r_k.weight")[:C],
        'ln_w': get_flat(f"{prefix}time_mix_ln.weight")[:C],
        'ln_b': get_flat(f"{prefix}time_mix_ln.bias")[:C],
        # ChannelMix
        'cm_lerp_k': get_flat(f"{prefix}channel_mix_lerp_k.weight")[:C],
        'cm_key': get_flat(f"{prefix}channel_mix_key.weight"),
        'cm_value': get_flat(f"{prefix}channel_mix_value.weight"),
    }
    # Compute LoRA ranks
    layer['rank_w'] = len(layer['w1']) // C
    layer['rank_a'] = len(layer['a1']) // C
    layer['rank_g'] = len(layer['g1']) // C
    layer['rank_v'] = len(layer['v1']) // C
    layer['n_ff'] = len(layer['cm_key']) // C
    layers.append(layer)

print(f"Loaded all weights in {time.time()-t0:.1f}s")
print(f"LoRA ranks: w={layers[0]['rank_w']}, a={layers[0]['rank_a']}, g={layers[0]['rank_g']}, v={layers[0]['rank_v']}")
print(f"n_ff={layers[0]['n_ff']}")

# ===== Forward pass (single token) =====
token_id = 6699  # "The"
print(f"\nForward pass for token {token_id}")

# Init state
att_shifts = [np.zeros(C, dtype=np.float32) for _ in range(n_layer)]
ffn_shifts = [np.zeros(C, dtype=np.float32) for _ in range(n_layer)]
wkv_states = [np.zeros(H * N * N, dtype=np.float32) for _ in range(n_layer)]
v_first = None

# Embedding
x = emb[token_id].copy()
x = layer_norm(x, emb_ln_w, emb_ln_b)

t0 = time.time()
for layer_id in range(n_layer):
    L = layers[layer_id]

    # ---- TimeMix ----
    x_ln = layer_norm(x.copy(), L['ln1_w'], L['ln1_b'])

    # Token shift
    x_prev = att_shifts[layer_id]
    xx = x_prev - x_ln
    att_shifts[layer_id] = x_ln.copy()

    # Lerp
    stride = 6
    lerp = L['lerp_fused']
    xr = np.zeros(C, dtype=np.float32)
    xw = np.zeros(C, dtype=np.float32)
    xk = np.zeros(C, dtype=np.float32)
    xv = np.zeros(C, dtype=np.float32)
    xa = np.zeros(C, dtype=np.float32)
    xg = np.zeros(C, dtype=np.float32)

    for i in range(C):
        base = i * stride
        lr = sigmoid(lerp[base + 0])
        lw = sigmoid(lerp[base + 1])
        lk = sigmoid(lerp[base + 2])
        lv = sigmoid(lerp[base + 3])
        la = sigmoid(lerp[base + 4])
        lg = sigmoid(lerp[base + 5])
        xr[i] = x_ln[i] + xx[i] * lr
        xw[i] = x_ln[i] + xx[i] * lw
        xk[i] = x_ln[i] + xx[i] * lk
        xv[i] = x_ln[i] + xx[i] * lv
        xa[i] = x_ln[i] + xx[i] * la
        xg[i] = x_ln[i] + xx[i] * lg

    # R, K, V
    r = matmul_vec(xr, L['receptance'], C, C)
    k = matmul_vec(xk, L['key'], C, C)
    v = matmul_vec(xv, L['value'], C, C)

    # V-bonus
    if layer_id == 0:
        v_first = v.copy()
    elif v_first is not None:
        rank_v = L['rank_v']
        vg_inner = matmul_vec(xv, L['v1'], C, rank_v)
        vg = matmul_vec(vg_inner, L['v2'], rank_v, C)
        gate = sigmoid(L['v0'] + vg)
        v = v + (v_first - v) * gate

    # Gate
    rank_g = L['rank_g']
    g_inner = matmul_vec(xg, L['g1'], C, rank_g)
    g_inner = sigmoid(g_inner)
    g = matmul_vec(g_inner, L['g2'], rank_g, C)

    # Time decay
    rank_w = L['rank_w']
    w_inner = matmul_vec(xw, L['w1'], C, rank_w)
    w_inner = np.tanh(w_inner)
    w_dynamic = matmul_vec(w_inner, L['w2'], rank_w, C)
    w = np.exp(-0.606531 * sigmoid(L['w0'] + w_dynamic))

    # Association
    rank_a = L['rank_a']
    a_inner = matmul_vec(xa, L['a1'], C, rank_a)
    a_dynamic = matmul_vec(a_inner, L['a2'], rank_a, C)
    a_coeff = sigmoid(L['a0'] + a_dynamic)

    # Key normalization
    kk = k * L['k_k']
    for head in range(H):
        s = head * N
        e = s + N
        norm = np.sqrt(np.sum(kk[s:e]**2)).clip(min=1e-12)
        kk[s:e] /= norm

    k_mod = k * (1.0 + (a_coeff - 1.0) * L['k_a'])

    # State evolution
    output = np.zeros(C, dtype=np.float32)
    wkv = wkv_states[layer_id]

    for head in range(H):
        hs = head * N
        so = head * N * N

        # ICL
        s_dot_kkt = np.zeros(N, dtype=np.float32)
        for i in range(N):
            s = 0.0
            for j in range(N):
                s += wkv[so + i * N + j] * (-kk[hs + j])
            s_dot_kkt[i] = s

        kkt_at = kk[hs:hs+N] * a_coeff[hs:hs+N]
        icl = np.outer(s_dot_kkt, kkt_at)

        # vk
        vk = np.outer(v[hs:hs+N], k_mod[hs:hs+N])

        # Update state
        for i in range(N):
            for j in range(N):
                idx = so + i * N + j
                wkv[idx] = wkv[idx] * w[hs + j] + icl[i, j] + vk[i, j]

        # Output
        for i in range(N):
            s = 0.0
            for j in range(N):
                s += wkv[so + i * N + j] * r[hs + j]
            output[hs + i] = s

    # GroupNorm
    output = group_norm(output, H, N, L['ln_w'], L['ln_b'])

    # Residual term
    residual = np.zeros(C, dtype=np.float32)
    for head in range(H):
        s = head * N
        rksum = np.sum(r[s:s+N] * k_mod[s:s+N] * L['r_k'][s:s+N])
        residual[s:s+N] = rksum * v[s:s+N]
    output = output + residual

    # Gate
    output = output * g

    # Output projection
    projected = matmul_vec(output, L['output'], C, C)

    # Residual
    x = x + projected

    # ---- ChannelMix ----
    x_ln2 = layer_norm(x.copy(), L['ln2_w'], L['ln2_b'])

    x_prev_cm = ffn_shifts[layer_id]
    xx_cm = x_prev_cm - x_ln2
    xk_cm = x_ln2 + xx_cm * sigmoid(L['cm_lerp_k'])
    ffn_shifts[layer_id] = x_ln2.copy()

    n_ff = L['n_ff']
    key_out = matmul_vec(xk_cm, L['cm_key'], C, n_ff)
    key_out = np.maximum(key_out, 0.0) ** 2
    cm_out = matmul_vec(key_out, L['cm_value'], n_ff, C)

    x = x + cm_out

    if layer_id % 6 == 0:
        print(f"  Layer {layer_id}: x stats mean={x.mean():.6f} std={x.std():.6f}")

print(f"Forward pass in {time.time()-t0:.1f}s")

# Output LayerNorm + head projection
x = layer_norm(x, head_ln_w, head_ln_b)
logits = matmul_vec(x, head_weight, C, 65536)

print(f"\nPython logits: min={logits.min():.3f} max={logits.max():.3f} std={logits.std():.3f}")

# Top 10
top = np.argsort(logits)[-10:][::-1]
# Load tokenizer
from pathlib import Path
import types
for pname in ['fairies', 'fairies.P30_Cognition', 'fairies.P30_Cognition.AkashicInferenceFairy']:
    if pname not in sys.modules:
        p = types.ModuleType(pname)
        p.__path__ = [os.path.join(r"F:\Sandbox\failure_factory\akashic_v2", *pname.split('.'))]
        p.__package__ = pname
        sys.modules[pname] = p
from fairies.P30_Cognition.AkashicInferenceFairy.tokenizer import load_tokenizer_from_gguf
tok = load_tokenizer_from_gguf(Path(GGUF_PATH))

print("\nPython Top 10:")
for idx in top:
    text = tok.decode([int(idx)])
    print(f"  {idx:6d}: {logits[idx]:8.3f}  '{text}'")

# Now compare with Rust
from rust_inference_bridge import RustInferenceBridge
from gguf_parser import get_model_info

info = get_model_info(GGUF_PATH)
class Config:
    n_layer = info.get('n_layer', 24)
    n_embd = info.get('n_embd', 2048)
    n_head = info.get('n_head', 32)
    head_size = n_embd // max(n_head, 1)
    vocab_size = info.get('vocab_size', 65536)

bridge = RustInferenceBridge(Config())
bridge.load_gguf_direct(GGUF_PATH)

result = bridge.forward([token_id])
rust_logits = np.array(result.get('logits', []))
print(f"\nRust logits: min={rust_logits.min():.3f} max={rust_logits.max():.3f} std={rust_logits.std():.3f}")

rust_top = np.argsort(rust_logits)[-10:][::-1]
print("\nRust Top 10:")
for idx in rust_top:
    text = tok.decode([int(idx)])
    print(f"  {idx:6d}: {rust_logits[idx]:8.3f}  '{text}'")

# Compare
diff = np.abs(logits - rust_logits)
print(f"\nLogits difference: max={diff.max():.4f} mean={diff.mean():.4f}")
if diff.max() < 0.1:
    print("MATCH! Python and Rust produce same logits.")
elif diff.max() < 1.0:
    print("CLOSE! Small numerical differences.")
else:
    print("MISMATCH! Significant differences between Python and Rust.")
    # Where is the biggest difference?
    worst_idx = np.argmax(diff)
    print(f"  Worst at idx {worst_idx}: py={logits[worst_idx]:.4f} rust={rust_logits[worst_idx]:.4f} diff={diff[worst_idx]:.4f}")
