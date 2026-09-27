"""Test forward pass with TRANSPOSED weight matrices.

GGML stores weight matrices in [output_dim, input_dim] layout (ne[0]=input_dim fast).
The correct matmul is: y = x @ W_physical.T
where W_physical = flat.reshape(output_dim, input_dim)

This is equivalent to: y[j] = sum_i(x[i] * flat[j * input_dim + i])

For our matmul_vec that does y[j] = sum_i(x[i] * M[i*n+j]):
We need to restructure it to: y[j] = sum_i(x[i] * M[j*k+i])
Or equivalently, reshape flat as (input_dim, output_dim) via transpose.
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

from gguf_parser import GGUFParser
from quantization import dequantize_tensor

parser = GGUFParser()
gguf = parser.parse(GGUF_PATH)

C = 2048; H = 32; N = 64; n_layer = 24

def get_flat(name):
    info = gguf.tensors[name]
    raw = gguf.get_tensor_data(name)
    return dequantize_tensor(raw, info.type_id, info.shape, to_torch=False).flatten().astype(np.float32)

def get_transposed(name, rows, cols):
    """Get weight matrix as [cols, rows] (input_dim, output_dim) for correct matmul.

    GGML stores as [output_dim, input_dim] physically (ne[0]=input_dim is fast).
    Physical flat: flat[out * input_dim + inp]
    We need: W[inp, out] = flat[out * input_dim + inp]
    = flat.reshape(output_dim, input_dim).T = [input_dim, output_dim]
    """
    flat = get_flat(name)
    info = gguf.tensors[name]
    ne0, ne1 = info.shape[0], info.shape[1] if len(info.shape) > 1 else 1
    # ne[0] = fast dim (input_dim), ne[1] = slow dim (output_dim)
    # Physical shape: [ne[1], ne[0]] = [output_dim, input_dim]
    # We want [input_dim, output_dim] = .T
    physical = flat.reshape(ne1, ne0)  # [output_dim, input_dim]
    return physical.T.copy()  # [input_dim, output_dim] - contiguous copy

def layer_norm(x, w, b, eps=1e-5):
    m = x.mean()
    v = ((x - m) ** 2).mean()
    return (x - m) / np.sqrt(v + eps) * w + b

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -80, 80)))

def group_norm(x, ng, gs, w, b, eps=64e-5):
    r = x.copy()
    for g in range(ng):
        s = g * gs; e = s + gs; seg = r[s:e]
        m = seg.mean(); v = ((seg - m) ** 2).mean()
        r[s:e] = (seg - m) / np.sqrt(v + eps) * w[s:e] + b[s:e]
    return r

# ===== Load ALL weights with TRANSPOSED matrices =====
print("Loading weights with TRANSPOSED convention...")
t0 = time.time()

# Embedding: ne=(2048, 65536). Physical: [65536, 2048].
# For lookup: emb[token] = row of physical = flat[token*2048 : (token+1)*2048]
emb_raw = gguf.get_tensor_data("token_embd.weight")
emb_info = gguf.tensors["token_embd.weight"]
emb_flat = dequantize_tensor(emb_raw, emb_info.type_id, emb_info.shape, to_torch=False).flatten().astype(np.float32)
# Physical: [65536, 2048] = [V, C]
emb = emb_flat.reshape(65536, 2048)  # Correct: each row is one token embedding
print(f"Embedding shape: {emb.shape}")

# Verify: first 5 values of token 0
emb_test_reshaped = emb_flat.reshape(2048, 65536)  # Old wrong way
emb_test_transposed = emb_flat.reshape(65536, 2048)  # New correct way (GGML physical)
print(f"Token 0 (old reshape then .T): {emb_test_reshaped.T[0, :5]}")
print(f"Token 0 (physical layout):     {emb_test_transposed[0, :5]}")
# These should be different! The old way does reshape(2048,65536).T[0] = column 0 of reshaped
# The new way does reshape(65536,2048)[0] = first 2048 contiguous values

emb_ln_w = get_flat("token_embd_norm.weight")[:C]
emb_ln_b = get_flat("token_embd_norm.bias")[:C]
head_ln_w = get_flat("output_norm.weight")[:C]
head_ln_b = get_flat("output_norm.bias")[:C]

# Output head: ne=(2048, 65536). Physical: [65536, 2048] = [V, C]
# logits = x @ head where head should be [C, V]
# Physical is [V, C], so head = physical.T = [C, V]
head_flat = get_flat("output.weight")
head_weight = head_flat.reshape(65536, 2048).T  # [C, V] = [2048, 65536]
print(f"Head weight shape (transposed): {head_weight.shape}")

layers = []
for L in range(n_layer):
    p = f"blk.{L}."

    # 1D tensors (no transpose needed)
    ln1_w = get_flat(f"{p}attn_norm.weight")[:C]
    ln1_b = get_flat(f"{p}attn_norm.bias")[:C]
    ln2_w = get_flat(f"{p}attn_norm_2.weight")[:C]
    ln2_b = get_flat(f"{p}attn_norm_2.bias")[:C]
    w0 = get_flat(f"{p}time_mix_w0.weight")[:C]
    a0 = get_flat(f"{p}time_mix_a0.weight")[:C]
    v0 = get_flat(f"{p}time_mix_v0.weight")[:C]
    k_k = get_flat(f"{p}time_mix_k_k.weight")[:C]
    k_a = get_flat(f"{p}time_mix_k_a.weight")[:C]
    r_k = get_flat(f"{p}time_mix_r_k.weight")[:C]
    ln_w = get_flat(f"{p}time_mix_ln.weight")[:C]
    ln_b = get_flat(f"{p}time_mix_ln.bias")[:C]
    cm_lerp_k = get_flat(f"{p}channel_mix_lerp_k.weight")[:C]

    # Lerp fused: ne=(2048,1,1,6). Physical layout: [6, 1, 1, 2048]
    # Component-major: flat[comp*2048 + channel]
    lerp = get_flat(f"{p}time_mix_lerp_fused.weight")

    # 2D weight matrices: TRANSPOSE (physical [out, in] → need [in, out])
    # For x @ W: need W to be [input_dim, output_dim]
    receptance = get_transposed(f"{p}time_mix_receptance.weight", C, C)  # [C, C]
    key = get_transposed(f"{p}time_mix_key.weight", C, C)  # [C, C]
    value = get_transposed(f"{p}time_mix_value.weight", C, C)  # [C, C]
    output_w = get_transposed(f"{p}time_mix_output.weight", C, C)  # [C, C]

    # LoRA matrices
    w1_info = gguf.tensors[f"{p}time_mix_w1.weight"]
    rank_w = w1_info.shape[1] if len(w1_info.shape) > 1 else w1_info.n_elements // C
    a1_info = gguf.tensors[f"{p}time_mix_a1.weight"]
    rank_a = a1_info.shape[1] if len(a1_info.shape) > 1 else a1_info.n_elements // C
    g1_info = gguf.tensors[f"{p}time_mix_g1.weight"]
    rank_g = g1_info.shape[1] if len(g1_info.shape) > 1 else g1_info.n_elements // C
    v1_info = gguf.tensors[f"{p}time_mix_v1.weight"]
    rank_v = v1_info.shape[1] if len(v1_info.shape) > 1 else v1_info.n_elements // C

    w1 = get_transposed(f"{p}time_mix_w1.weight", C, rank_w)  # [C, rank]
    w2 = get_transposed(f"{p}time_mix_w2.weight", rank_w, C)  # [rank, C]
    a1 = get_transposed(f"{p}time_mix_a1.weight", C, rank_a)
    a2 = get_transposed(f"{p}time_mix_a2.weight", rank_a, C)
    v1 = get_transposed(f"{p}time_mix_v1.weight", C, rank_v)
    v2 = get_transposed(f"{p}time_mix_v2.weight", rank_v, C)
    g1 = get_transposed(f"{p}time_mix_g1.weight", C, rank_g)
    g2 = get_transposed(f"{p}time_mix_g2.weight", rank_g, C)

    # ChannelMix
    cm_key_info = gguf.tensors[f"{p}channel_mix_key.weight"]
    n_ff = cm_key_info.shape[1] if len(cm_key_info.shape) > 1 else cm_key_info.n_elements // C
    cm_key = get_transposed(f"{p}channel_mix_key.weight", C, n_ff)  # [C, n_ff]
    cm_value = get_transposed(f"{p}channel_mix_value.weight", n_ff, C)  # [n_ff, C]

    layer = {
        'ln1_w': ln1_w, 'ln1_b': ln1_b, 'ln2_w': ln2_w, 'ln2_b': ln2_b,
        'lerp': lerp, 'receptance': receptance, 'key': key, 'value': value,
        'output': output_w, 'w0': w0, 'w1': w1, 'w2': w2,
        'a0': a0, 'a1': a1, 'a2': a2, 'v0': v0, 'v1': v1, 'v2': v2,
        'g1': g1, 'g2': g2, 'k_k': k_k, 'k_a': k_a, 'r_k': r_k,
        'ln_w': ln_w, 'ln_b': ln_b, 'cm_lerp_k': cm_lerp_k,
        'cm_key': cm_key, 'cm_value': cm_value,
        'rank_w': rank_w, 'rank_a': rank_a, 'rank_g': rank_g, 'rank_v': rank_v,
        'n_ff': n_ff,
    }
    layers.append(layer)

print(f"Loaded all weights in {time.time()-t0:.1f}s")
print(f"LoRA ranks: w={layers[0]['rank_w']}, a={layers[0]['rank_a']}, g={layers[0]['rank_g']}, v={layers[0]['rank_v']}")
print(f"n_ff={layers[0]['n_ff']}")

# ===== Forward pass =====
token_id = 6699  # "The"
print(f"\nForward pass for token {token_id} with TRANSPOSED weights + component-major lerp")

att_shifts = [np.zeros(C, dtype=np.float32) for _ in range(n_layer)]
ffn_shifts = [np.zeros(C, dtype=np.float32) for _ in range(n_layer)]
wkv_states = [np.zeros(H * N * N, dtype=np.float32) for _ in range(n_layer)]
v_first = None

x = emb[token_id].copy()
x = layer_norm(x, emb_ln_w, emb_ln_b)

t0 = time.time()
for layer_id in range(n_layer):
    L = layers[layer_id]
    x_ln = layer_norm(x.copy(), L['ln1_w'], L['ln1_b'])
    x_prev = att_shifts[layer_id]
    xx = x_prev - x_ln
    att_shifts[layer_id] = x_ln.copy()

    # Channel-major lerp (stride=6, as stored by Python reshape convention)
    lerp = L['lerp']
    stride = 6
    lr = sigmoid(np.array([lerp[i*stride+0] for i in range(C)], dtype=np.float32))
    lw = sigmoid(np.array([lerp[i*stride+1] for i in range(C)], dtype=np.float32))
    lk = sigmoid(np.array([lerp[i*stride+2] for i in range(C)], dtype=np.float32))
    lv = sigmoid(np.array([lerp[i*stride+3] for i in range(C)], dtype=np.float32))
    la = sigmoid(np.array([lerp[i*stride+4] for i in range(C)], dtype=np.float32))
    lg = sigmoid(np.array([lerp[i*stride+5] for i in range(C)], dtype=np.float32))
    xr = x_ln + xx * lr
    xw = x_ln + xx * lw
    xk = x_ln + xx * lk
    xv = x_ln + xx * lv
    xa = x_ln + xx * la
    xg = x_ln + xx * lg

    # Now using properly transposed weights: x @ W gives correct result
    r = xr @ L['receptance']  # [C] @ [C, C] -> [C]
    k = xk @ L['key']
    v = xv @ L['value']

    if layer_id == 0:
        v_first = v.copy()
    elif v_first is not None:
        vg_inner = xv @ L['v1']  # [C] @ [C, rank] -> [rank]
        vg = vg_inner @ L['v2']  # [rank] @ [rank, C] -> [C]
        gate = sigmoid(L['v0'] + vg)
        v = v + (v_first - v) * gate

    g_inner = xg @ L['g1']  # [C] @ [C, rank] -> [rank]
    g_inner = sigmoid(g_inner)
    g = g_inner @ L['g2']  # [rank] @ [rank, C] -> [C]

    w_inner = xw @ L['w1']
    w_inner = np.tanh(w_inner)
    w_dynamic = w_inner @ L['w2']
    w = np.exp(-0.606531 * sigmoid(L['w0'] + w_dynamic))

    a_inner = xa @ L['a1']
    a_dynamic = a_inner @ L['a2']
    a_coeff = sigmoid(L['a0'] + a_dynamic)

    kk = k * L['k_k']
    for head in range(H):
        s = head * N; e = s + N
        norm = np.sqrt(np.sum(kk[s:e]**2)).clip(min=1e-12)
        kk[s:e] /= norm

    k_mod = k * (1.0 + (a_coeff - 1.0) * L['k_a'])

    output = np.zeros(C, dtype=np.float32)
    wkv = wkv_states[layer_id]
    for head in range(H):
        hs = head * N; so = head * N * N
        s_dot_kkt = np.zeros(N, dtype=np.float32)
        for i in range(N):
            s = 0.0
            for j in range(N):
                s += wkv[so + i*N + j] * (-kk[hs + j])
            s_dot_kkt[i] = s
        kkt_at = kk[hs:hs+N] * a_coeff[hs:hs+N]
        icl = np.outer(s_dot_kkt, kkt_at)
        vk = np.outer(v[hs:hs+N], k_mod[hs:hs+N])
        for i in range(N):
            for j in range(N):
                idx = so + i*N + j
                wkv[idx] = wkv[idx] * w[hs+j] + icl[i,j] + vk[i,j]
        for i in range(N):
            s = 0.0
            for j in range(N):
                s += wkv[so + i*N + j] * r[hs + j]
            output[hs + i] = s

    output = group_norm(output, H, N, L['ln_w'], L['ln_b'])
    residual = np.zeros(C, dtype=np.float32)
    for head in range(H):
        s = head * N
        rksum = np.sum(r[s:s+N] * k_mod[s:s+N] * L['r_k'][s:s+N])
        residual[s:s+N] = rksum * v[s:s+N]
    output = output + residual
    output = output * g
    projected = output @ L['output']  # [C] @ [C, C] -> [C]
    x = x + projected

    # ChannelMix
    x_ln2 = layer_norm(x.copy(), L['ln2_w'], L['ln2_b'])
    x_prev_cm = ffn_shifts[layer_id]
    xx_cm = x_prev_cm - x_ln2
    xk_cm = x_ln2 + xx_cm * sigmoid(L['cm_lerp_k'])
    ffn_shifts[layer_id] = x_ln2.copy()
    key_out = xk_cm @ L['cm_key']  # [C] @ [C, n_ff] -> [n_ff]
    key_out = np.maximum(key_out, 0.0) ** 2
    cm_out = key_out @ L['cm_value']  # [n_ff] @ [n_ff, C] -> [C]
    x = x + cm_out

    if layer_id % 6 == 0:
        print(f"  Layer {layer_id}: mean={x.mean():.6f} std={x.std():.6f}")

print(f"Forward pass in {time.time()-t0:.1f}s")

x = layer_norm(x, head_ln_w, head_ln_b)
logits = x @ head_weight  # [C] @ [C, V] -> [V]

print(f"\nLogits: min={logits.min():.3f} max={logits.max():.3f} std={logits.std():.3f}")

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

print("\nTop 10 with TRANSPOSED weights + channel-major lerp:")
for idx in top:
    text = tok.decode([int(idx)])
    print(f"  {idx:6d}: {logits[idx]:8.3f}  {repr(text)}")
