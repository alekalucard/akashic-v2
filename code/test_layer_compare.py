"""Compare intermediate values between Python and Rust for layer 0.

Runs token 0 through both engines and compares at each step to find
where the outputs first diverge.
"""
import sys
import os
import numpy as np

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
from quantization import dequantize_tensor, dequantize_q8_0

# Parse GGUF
parser = GGUFParser()
gguf = parser.parse(GGUF_PATH)

# ===================================================================
# Manually replicate the forward pass for token 0, layer 0 in Python
# using raw numpy (no torch) to match exactly what Rust does
# ===================================================================

C = 2048
H = 32
N = 64  # head_size = C / H

def get_weight(name):
    """Get dequantized weight as numpy array."""
    info = gguf.tensors[name]
    raw = gguf.get_tensor_data(name)
    return dequantize_tensor(raw, info.type_id, info.shape, to_torch=False)

def get_flat(name):
    """Get dequantized weight as flat 1D array (Rust representation)."""
    info = gguf.tensors[name]
    raw = gguf.get_tensor_data(name)
    # Use the general dequantizer then flatten
    arr = dequantize_tensor(raw, info.type_id, info.shape, to_torch=False)
    return arr.flatten()

def layer_norm(x, weight, bias, eps=1e-5):
    """Python layer norm matching Rust."""
    mean = x.mean()
    var = ((x - mean) ** 2).mean()
    inv_std = 1.0 / np.sqrt(var + eps)
    return (x - mean) * inv_std * weight + bias

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -80, 80)))

def matmul_vec_py(x, M_flat, k, n):
    """Simulate Rust matmul_vec: y = x @ M where M is [k, n] row-major."""
    M = M_flat[:k*n].reshape(k, n)
    return x @ M

def group_norm_py(x, num_groups, group_size, weight, bias, eps=64e-5):
    """Python group norm matching Rust."""
    result = x.copy()
    for g in range(num_groups):
        start = g * group_size
        end = start + group_size
        segment = result[start:end]
        mean = segment.mean()
        var = ((segment - mean) ** 2).mean()
        inv_std = 1.0 / np.sqrt(var + eps)
        result[start:end] = (segment - mean) * inv_std * weight[start:end] + bias[start:end]
    return result

# Load embedding
emb_info = gguf.tensors["token_embd.weight"]
emb_raw = gguf.get_tensor_data("token_embd.weight")
emb_py = dequantize_tensor(emb_raw, emb_info.type_id, emb_info.shape, to_torch=False)
if emb_py.shape[0] < emb_py.shape[1]:
    emb_py = emb_py.T  # [V, C]

# Embedding norm
emb_ln_w = get_flat("token_embd_norm.weight")[:C]
emb_ln_b = get_flat("token_embd_norm.bias")[:C]

# Layer 0 weights
ln1_w = get_flat("blk.0.attn_norm.weight")[:C]
ln1_b = get_flat("blk.0.attn_norm.bias")[:C]
ln2_w = get_flat("blk.0.attn_norm_2.weight")[:C]
ln2_b = get_flat("blk.0.attn_norm_2.bias")[:C]

# TimeMix weights
lerp_fused = get_flat("blk.0.time_mix_lerp_fused.weight")
tm_receptance = get_flat("blk.0.time_mix_receptance.weight")
tm_key = get_flat("blk.0.time_mix_key.weight")
tm_value = get_flat("blk.0.time_mix_value.weight")

tm_w0 = get_flat("blk.0.time_mix_w0.weight")[:C]
tm_w1 = get_flat("blk.0.time_mix_w1.weight")
tm_w2 = get_flat("blk.0.time_mix_w2.weight")

tm_a0 = get_flat("blk.0.time_mix_a0.weight")[:C]
tm_a1 = get_flat("blk.0.time_mix_a1.weight")
tm_a2 = get_flat("blk.0.time_mix_a2.weight")

tm_v0 = get_flat("blk.0.time_mix_v0.weight")[:C]
tm_v1 = get_flat("blk.0.time_mix_v1.weight")
tm_v2 = get_flat("blk.0.time_mix_v2.weight")

tm_g1 = get_flat("blk.0.time_mix_g1.weight")
tm_g2 = get_flat("blk.0.time_mix_g2.weight")

tm_k_k = get_flat("blk.0.time_mix_k_k.weight")[:C]
tm_k_a = get_flat("blk.0.time_mix_k_a.weight")[:C]
tm_r_k = get_flat("blk.0.time_mix_r_k.weight")[:C]

tm_ln_w = get_flat("blk.0.time_mix_ln.weight")[:C]
tm_ln_b = get_flat("blk.0.time_mix_ln.bias")[:C]

tm_output = get_flat("blk.0.time_mix_output.weight")

# ChannelMix weights
cm_lerp_k = get_flat("blk.0.channel_mix_lerp_k.weight")[:C]
cm_key = get_flat("blk.0.channel_mix_key.weight")
cm_value = get_flat("blk.0.channel_mix_value.weight")

# Check lerp_fused shape
print(f"lerp_fused length: {len(lerp_fused)}")
print(f"Expected for stride=6: {C * 6} = {C*6}")
stride = 6 if len(lerp_fused) >= C * 6 else (5 if len(lerp_fused) >= C * 5 else 1)
print(f"Stride: {stride}")

# LoRA dimensions
rank_w = len(tm_w1) // C
rank_a = len(tm_a1) // C
rank_g = len(tm_g1) // C
print(f"LoRA ranks: w={rank_w}, a={rank_a}, g={rank_g}")

# ===================================================================
# STEP 1: Embedding lookup + LayerNorm
# ===================================================================
token_id = 6699  # "The"
x = emb_py[token_id].copy().astype(np.float32)
print(f"\n{'='*60}")
print("STEP 1: Embedding + LayerNorm")
print(f"  Token {token_id} raw embedding[:5] = {x[:5]}")

x = layer_norm(x, emb_ln_w, emb_ln_b)
print(f"  After emb LayerNorm[:5] = {x[:5]}")

# ===================================================================
# STEP 2: Layer 0 TimeMix - LN + token shifting
# ===================================================================
x_ln = layer_norm(x.copy(), ln1_w, ln1_b)
print(f"\n{'='*60}")
print("STEP 2: TimeMix LayerNorm")
print(f"  After LN1[:5] = {x_ln[:5]}")

# Token shift: x_prev = zeros (first token)
x_prev = np.zeros(C, dtype=np.float32)
xx = x_prev - x_ln  # = -x_ln for first token

# Lerp
xr = np.zeros(C, dtype=np.float32)
xw = np.zeros(C, dtype=np.float32)
xk = np.zeros(C, dtype=np.float32)
xv = np.zeros(C, dtype=np.float32)
xa = np.zeros(C, dtype=np.float32)
xg = np.zeros(C, dtype=np.float32)

for i in range(C):
    base = i * stride
    lr = sigmoid(lerp_fused[base + 0])
    lw = sigmoid(lerp_fused[base + 1])
    lk = sigmoid(lerp_fused[base + 2])
    lv = sigmoid(lerp_fused[base + 3])
    la = sigmoid(lerp_fused[base + 4])
    lg = sigmoid(lerp_fused[base + 5]) if stride >= 6 else 0.5

    xr[i] = x_ln[i] + xx[i] * lr
    xw[i] = x_ln[i] + xx[i] * lw
    xk[i] = x_ln[i] + xx[i] * lk
    xv[i] = x_ln[i] + xx[i] * lv
    xa[i] = x_ln[i] + xx[i] * la
    xg[i] = x_ln[i] + xx[i] * lg

print(f"\n{'='*60}")
print("STEP 3: Token shifting + lerp")
print(f"  xr[:5] = {xr[:5]}")
print(f"  xk[:5] = {xk[:5]}")

# ===================================================================
# STEP 3: R, K, V projections
# ===================================================================
r = matmul_vec_py(xr, tm_receptance, C, C)
k = matmul_vec_py(xk, tm_key, C, C)
v = matmul_vec_py(xv, tm_value, C, C)

print(f"\n{'='*60}")
print("STEP 4: R, K, V projections")
print(f"  r[:5] = {r[:5]}")
print(f"  k[:5] = {k[:5]}")
print(f"  v[:5] = {v[:5]}")

# Layer 0: v_first = v
v_first = v.copy()

# Gate: g = sigmoid(xg @ g1) @ g2
g_inner = matmul_vec_py(xg, tm_g1, C, rank_g)
g_inner = sigmoid(g_inner)
g = matmul_vec_py(g_inner, tm_g2, rank_g, C)
print(f"  g[:5] = {g[:5]}")

# No somatic adjustment (neutral)

# Time decay
w_inner = matmul_vec_py(xw, tm_w1, C, rank_w)
w_inner = np.tanh(w_inner)
w_dynamic = matmul_vec_py(w_inner, tm_w2, rank_w, C)
w = np.exp(-0.606531 * sigmoid(tm_w0 + w_dynamic))
print(f"  w[:5] = {w[:5]}")

# Association
a_inner = matmul_vec_py(xa, tm_a1, C, rank_a)
a_dynamic = matmul_vec_py(a_inner, tm_a2, rank_a, C)
a_coeff = sigmoid(tm_a0 + a_dynamic)
print(f"  a_coeff[:5] = {a_coeff[:5]}")

# Key normalization
kk = k * tm_k_k
for head in range(H):
    start = head * N
    end = start + N
    norm = np.sqrt(np.sum(kk[start:end]**2)).clip(min=1e-12)
    kk[start:end] /= norm
print(f"  kk[:5] = {kk[:5]}")

k_modified = k * (1.0 + (a_coeff - 1.0) * tm_k_a)
print(f"  k_modified[:5] = {k_modified[:5]}")

# ===================================================================
# STEP 4: State evolution (all zeros initially)
# ===================================================================
wkv_state = np.zeros(H * N * N, dtype=np.float32)
output = np.zeros(C, dtype=np.float32)

for head in range(H):
    h_start = head * N
    state_offset = head * N * N

    # ICL term: (state @ (-kk)) @ (kk * a_coeff)^T
    # State is all zeros for first token, so ICL = 0
    s_dot_kkt = np.zeros(N, dtype=np.float32)
    for i in range(N):
        s = 0.0
        for j in range(N):
            s += wkv_state[state_offset + i * N + j] * (-kk[h_start + j])
        s_dot_kkt[i] = s

    kkt_at = kk[h_start:h_start+N] * a_coeff[h_start:h_start+N]

    icl_term = np.outer(s_dot_kkt, kkt_at)

    # vk outer product
    vk = np.outer(v[h_start:h_start+N], k_modified[h_start:h_start+N])

    # State update: state = state * w + icl + vk
    for i in range(N):
        for j in range(N):
            idx = state_offset + i * N + j
            decay_val = w[h_start + j]
            wkv_state[idx] = wkv_state[idx] * decay_val + icl_term[i, j] + vk[i, j]

    # Output: state @ r
    for i in range(N):
        s = 0.0
        for j in range(N):
            s += wkv_state[state_offset + i * N + j] * r[h_start + j]
        output[h_start + i] = s

print(f"\n{'='*60}")
print("STEP 5: State evolution output")
print(f"  output[:5] = {output[:5]}")
print(f"  output stats: mean={output.mean():.6f} std={output.std():.6f}")

# GroupNorm
output_gn = group_norm_py(output, H, N, tm_ln_w, tm_ln_b)
print(f"  after GroupNorm[:5] = {output_gn[:5]}")

# Residual: (r * k_modified * r_k).sum_per_head * v
residual = np.zeros(C, dtype=np.float32)
for head in range(H):
    start = head * N
    rksum = np.sum(r[start:start+N] * k_modified[start:start+N] * tm_r_k[start:start+N])
    for i in range(N):
        residual[start + i] = rksum * v[start + i]

output_final = output_gn + residual
print(f"  after residual[:5] = {output_final[:5]}")

# Gate
output_gated = output_final * g
print(f"  after gate[:5] = {output_gated[:5]}")

# Output projection
tm_projected = matmul_vec_py(output_gated, tm_output, C, C)
print(f"  TimeMix projected[:5] = {tm_projected[:5]}")

# Residual connection
x_after_tm = x + tm_projected
print(f"  x after TimeMix residual[:5] = {x_after_tm[:5]}")

# ===================================================================
# STEP 5: ChannelMix
# ===================================================================
x_ln2 = layer_norm(x_after_tm.copy(), ln2_w, ln2_b)
# Token shift: x_prev = zeros (first token)
x_prev_cm = np.zeros(C, dtype=np.float32)
xx_cm = x_prev_cm - x_ln2
xk_cm = x_ln2 + xx_cm * sigmoid(cm_lerp_k)

n_ff = len(cm_key) // C
print(f"\n{'='*60}")
print(f"STEP 6: ChannelMix (n_ff={n_ff})")

key_out = matmul_vec_py(xk_cm, cm_key, C, n_ff)
key_out = np.maximum(key_out, 0.0) ** 2  # squared ReLU
cm_out = matmul_vec_py(key_out, cm_value, n_ff, C)
print(f"  cm output[:5] = {cm_out[:5]}")

x_after_cm = x_after_tm + cm_out
print(f"  x after ChannelMix[:5] = {x_after_cm[:5]}")

print(f"\n{'='*60}")
print("SUMMARY: Python layer 0 output")
print(f"  x_final[:5] = {x_after_cm[:5]}")
print(f"  x_final stats: mean={x_after_cm.mean():.6f} std={x_after_cm.std():.6f}")

# ===================================================================
# Now compare with Rust
# ===================================================================
print(f"\n{'='*60}")
print("RUST COMPARISON")
print(f"{'='*60}")

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

# Forward token 0
result = bridge.forward([token_id])
logits = np.array(result.get('logits', []))
print(f"Rust logits stats: min={logits.min():.3f} max={logits.max():.3f} std={logits.std():.3f}")

# Now also check what happens with just the head projection on our Python output
# If Python's layer 0 output differs from Rust, we know the divergence is in the layers
# But we can't easily extract Rust's intermediate values...

# Instead, let's check if the EMBEDDING is correct
# Rust embedding for token 6699 should match
print(f"\nPython embedding (after LN) for token {token_id}:")
x_check = emb_py[token_id].copy().astype(np.float32)
x_check = layer_norm(x_check, emb_ln_w, emb_ln_b)
print(f"  [:5] = {x_check[:5]}")

# The key question: does our Python replication of layer 0 give different logits?
# Let's compute head projection from Python's x_after_cm after all 24 layers...
# We can't easily do all 24 layers but we CAN check if Rust and Python agree on layer 0
# by adding a debug output to Rust (or by comparing final logits from a 1-layer model)

print("\nNOTE: To definitively compare, we'd need Rust to output intermediate values.")
print("But we CAN compare the lerp_fused access pattern, which is a common source of bugs.")
print(f"\nlerp_fused length: {len(lerp_fused)}")
print(f"lerp_fused[:12] (first 2 channels): {lerp_fused[:12]}")
print(f"Expected layout: [ch0_r, ch0_w, ch0_k, ch0_v, ch0_a, ch0_g, ch1_r, ch1_w, ...]")

# Check: is the GGUF shape for lerp_fused (2048, 1, 1, 6)?
lerp_info = gguf.tensors["blk.0.time_mix_lerp_fused.weight"]
print(f"\nGGUF shape for lerp_fused: {lerp_info.shape}")
print(f"n_elements: {lerp_info.n_elements}")

# CRITICAL: If GGUF shape is (2048, 1, 1, 6) and GGUF is standard row-major (ne[0]=rows),
# then the flat layout is: [2048 rows of (1 * 1 * 6) = 6 elements]
# which means: flat[i * 6 + component] for channel i, component (r,w,k,v,a,g)
# This matches Rust's access: lerp_fused[i * stride + 0..5]

# But wait - for 4D tensors, the GGUF shape might be stored differently!
# Let's check: with shape (2048, 1, 1, 6), the standard C row-major would be:
# ne[0]=2048 is outermost, ne[3]=6 is innermost
# flat index = i0 * ne[1]*ne[2]*ne[3] + i1 * ne[2]*ne[3] + i2 * ne[3] + i3
#            = i0 * 1*1*6 + 0 + 0 + i3
#            = i0 * 6 + i3
# This means: flat[channel * 6 + component] — matches stride=6 access! Good.

# BUT WAIT: What if GGUF actually stores ne[0]=6 as innermost (GGML convention)?
# Then flat[i3 * ne[2]*ne[1]*ne[0] + ... ] = flat[i3 * 2048 + channel]
# = component-major layout: all R values, then all W values, etc.
# Let's test both interpretations!

print(f"\n{'='*60}")
print("LERP_FUSED LAYOUT TEST")
print(f"{'='*60}")

# Interpretation 1: Row-major (ne[0]=2048 is outermost), stride=6
# flat[ch * 6 + component]
interp1_ch0 = lerp_fused[0:6]  # Channel 0: r, w, k, v, a, g
interp1_ch1 = lerp_fused[6:12]  # Channel 1
print(f"Interp 1 (ch-major, stride=6):")
print(f"  ch0 = {interp1_ch0}")
print(f"  ch1 = {interp1_ch1}")

# Interpretation 2: GGML column-major (ne[0]=2048 is innermost), stride=2048
# flat[component * 2048 + ch]
if len(lerp_fused) >= 6 * 2048:
    interp2_ch0 = [lerp_fused[comp * 2048 + 0] for comp in range(6)]
    interp2_ch1 = [lerp_fused[comp * 2048 + 1] for comp in range(6)]
    print(f"\nInterp 2 (component-major, stride=2048):")
    print(f"  ch0 = {interp2_ch0}")
    print(f"  ch1 = {interp2_ch1}")

    # The sigmoid of these should be in (0,1) for valid lerp ratios
    print(f"\n  sigmoid(interp1_ch0) = {sigmoid(np.array(interp1_ch0))}")
    print(f"  sigmoid(interp2_ch0) = {sigmoid(np.array(interp2_ch0))}")

    # Valid lerp ratios should be spread out, not all ~0 or ~1
    interp1_sig = sigmoid(np.array([lerp_fused[ch * 6 + comp] for ch in range(C) for comp in range(6)]).reshape(C, 6))
    interp2_sig = sigmoid(np.array([lerp_fused[comp * C + ch] for ch in range(C) for comp in range(6)]).reshape(C, 6))

    print(f"\n  Interp 1 sigmoid stats per component:")
    for comp, name in enumerate(['r', 'w', 'k', 'v', 'a', 'g']):
        vals = interp1_sig[:, comp]
        print(f"    {name}: mean={vals.mean():.4f} std={vals.std():.4f} min={vals.min():.4f} max={vals.max():.4f}")

    print(f"\n  Interp 2 sigmoid stats per component:")
    for comp, name in enumerate(['r', 'w', 'k', 'v', 'a', 'g']):
        vals = interp2_sig[:, comp]
        print(f"    {name}: mean={vals.mean():.4f} std={vals.std():.4f} min={vals.min():.4f} max={vals.max():.4f}")

# The interpretation with more reasonable stats (varied means, not all at extremes) is correct.
