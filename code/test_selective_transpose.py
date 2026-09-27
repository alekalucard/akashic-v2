"""Test forward pass with SELECTIVE transposition.

Based on the converter (convert_hf_to_gguf.py line 6526-6534):
  - Regular weights (receptance, key, value, output, cm_key, cm_value): NOT transposed by converter
  - LoRA weights (w1, w2, a1, a2, v1, v2, g1, g2): TRANSPOSED by converter

So in the GGUF file:
  Regular: stored as PyTorch nn.Linear convention [out_features, in_features]
  LoRA: ALREADY transposed before writing

For GGML ne[0] = fast dim, physical = flat.reshape(ne[1], ne[0]):
  Regular ne=(2048, 8192): physical=[8192, 2048]=[out, in] -> .T=[in, out] for x@W
  LoRA ne=(2048, 96): physical=[96, 2048]

But wait - if LoRA is pre-transposed, its PyTorch shape is [C, rank]=[2048, 96],
  and GGML stores with ne[0]=fast=96: ne=(96, 2048)? But parser shows ne=(2048, 96)!

This is confusing. Let me just test the combination that works.
The test_transpose_fix.py transposed EVERYTHING and got coherent but unstable output.
Maybe the instability comes from double-transposing LoRA matrices.

Strategy: Try these approaches for LoRA matrices:
  A) Transpose (same as regular): flat.reshape(ne[1], ne[0]).T
  B) Direct (no transpose): flat.reshape(ne[0], ne[1])
  C) Physical direct: flat.reshape(ne[1], ne[0]) -- physical layout without .T
"""
import sys, os, numpy as np, time

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

def get_weight_transposed(name):
    """For regular weights: physical.T = flat.reshape(ne[1], ne[0]).T"""
    flat = get_flat(name)
    info = gguf.tensors[name]
    ne0 = info.shape[0]
    ne1 = info.shape[1] if len(info.shape) > 1 else 1
    physical = flat.reshape(ne1, ne0)
    return physical.T.copy()

def get_weight_direct(name):
    """For pre-transposed weights: flat.reshape(ne[0], ne[1])"""
    flat = get_flat(name)
    info = gguf.tensors[name]
    ne0 = info.shape[0]
    ne1 = info.shape[1] if len(info.shape) > 1 else 1
    return flat.reshape(ne0, ne1).copy()

def get_weight_physical(name):
    """Physical layout: flat.reshape(ne[1], ne[0]) -- no transpose"""
    flat = get_flat(name)
    info = gguf.tensors[name]
    ne0 = info.shape[0]
    ne1 = info.shape[1] if len(info.shape) > 1 else 1
    return flat.reshape(ne1, ne0).copy()

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


def run_forward(lora_mode="transposed"):
    """Run full forward pass.

    lora_mode:
      "transposed" = transpose LoRA same as regular weights
      "direct" = flat.reshape(ne[0], ne[1]) -- no transpose
      "physical" = flat.reshape(ne[1], ne[0]) -- physical without transpose
    """
    print(f"\n{'='*60}")
    print(f"LoRA mode: {lora_mode}")
    print(f"Regular weights: always transposed (physical.T)")
    print(f"{'='*60}")

    t0 = time.time()

    # Embedding: physical layout [V, C]
    emb_flat = get_flat("token_embd.weight")
    emb = emb_flat.reshape(65536, 2048)

    emb_ln_w = get_flat("token_embd_norm.weight")[:C]
    emb_ln_b = get_flat("token_embd_norm.bias")[:C]
    head_ln_w = get_flat("output_norm.weight")[:C]
    head_ln_b = get_flat("output_norm.bias")[:C]
    head_flat = get_flat("output.weight")
    head_weight = head_flat.reshape(65536, 2048).T  # [C, V]

    # Select LoRA loader
    if lora_mode == "transposed":
        get_lora = get_weight_transposed
    elif lora_mode == "direct":
        get_lora = get_weight_direct
    elif lora_mode == "physical":
        get_lora = get_weight_physical

    layers = []
    for L in range(n_layer):
        p = f"blk.{L}."

        layer = {
            'ln1_w': get_flat(f"{p}attn_norm.weight")[:C],
            'ln1_b': get_flat(f"{p}attn_norm.bias")[:C],
            'ln2_w': get_flat(f"{p}attn_norm_2.weight")[:C],
            'ln2_b': get_flat(f"{p}attn_norm_2.bias")[:C],
            'lerp': get_flat(f"{p}time_mix_lerp_fused.weight"),
            # Regular weights: ALWAYS transposed
            'receptance': get_weight_transposed(f"{p}time_mix_receptance.weight"),
            'key': get_weight_transposed(f"{p}time_mix_key.weight"),
            'value': get_weight_transposed(f"{p}time_mix_value.weight"),
            'output': get_weight_transposed(f"{p}time_mix_output.weight"),
            # 1D weights
            'w0': get_flat(f"{p}time_mix_w0.weight")[:C],
            'a0': get_flat(f"{p}time_mix_a0.weight")[:C],
            'v0': get_flat(f"{p}time_mix_v0.weight")[:C],
            'k_k': get_flat(f"{p}time_mix_k_k.weight")[:C],
            'k_a': get_flat(f"{p}time_mix_k_a.weight")[:C],
            'r_k': get_flat(f"{p}time_mix_r_k.weight")[:C],
            'ln_w': get_flat(f"{p}time_mix_ln.weight")[:C],
            'ln_b': get_flat(f"{p}time_mix_ln.bias")[:C],
            'cm_lerp_k': get_flat(f"{p}channel_mix_lerp_k.weight")[:C],
            # LoRA weights: mode-dependent
            'w1': get_lora(f"{p}time_mix_w1.weight"),
            'w2': get_lora(f"{p}time_mix_w2.weight"),
            'a1': get_lora(f"{p}time_mix_a1.weight"),
            'a2': get_lora(f"{p}time_mix_a2.weight"),
            'v1': get_lora(f"{p}time_mix_v1.weight"),
            'v2': get_lora(f"{p}time_mix_v2.weight"),
            'g1': get_lora(f"{p}time_mix_g1.weight"),
            'g2': get_lora(f"{p}time_mix_g2.weight"),
            # ChannelMix: regular weights (TRANSPOSED)
            'cm_key': get_weight_transposed(f"{p}channel_mix_key.weight"),
            'cm_value': get_weight_transposed(f"{p}channel_mix_value.weight"),
        }
        layers.append(layer)

    print(f"Loaded weights in {time.time()-t0:.1f}s")

    # Check shapes
    L0 = layers[0]
    print(f"  receptance: {L0['receptance'].shape}")
    print(f"  w1: {L0['w1'].shape}")
    print(f"  w2: {L0['w2'].shape}")
    print(f"  g1: {L0['g1'].shape}")
    print(f"  cm_key: {L0['cm_key'].shape}")
    print(f"  cm_value: {L0['cm_value'].shape}")

    # Forward pass
    token_id = 6699
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

        # Channel-major lerp (stride=6)
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

        r = xr @ L['receptance']
        k = xk @ L['key']
        v = xv @ L['value']

        if layer_id == 0:
            v_first = v.copy()
        elif v_first is not None:
            vg_inner = xv @ L['v1']
            vg = vg_inner @ L['v2']
            gate = sigmoid(L['v0'] + vg)
            v = v + (v_first - v) * gate

        g_inner = xg @ L['g1']
        g_inner = sigmoid(g_inner)
        g = g_inner @ L['g2']

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
        projected = output @ L['output']
        x = x + projected

        x_ln2 = layer_norm(x.copy(), L['ln2_w'], L['ln2_b'])
        x_prev_cm = ffn_shifts[layer_id]
        xx_cm = x_prev_cm - x_ln2
        xk_cm = x_ln2 + xx_cm * sigmoid(L['cm_lerp_k'])
        ffn_shifts[layer_id] = x_ln2.copy()
        key_out = xk_cm @ L['cm_key']
        key_out = np.maximum(key_out, 0.0) ** 2
        cm_out = key_out @ L['cm_value']
        x = x + cm_out

        if layer_id % 6 == 0:
            print(f"  Layer {layer_id}: mean={x.mean():.6f} std={x.std():.6f}")

    print(f"Forward in {time.time()-t0:.1f}s")

    x = layer_norm(x, head_ln_w, head_ln_b)
    logits = x @ head_weight

    print(f"Logits: min={logits.min():.3f} max={logits.max():.3f} std={logits.std():.3f}")

    top = np.argsort(logits)[-10:][::-1]

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

    print(f"Top 10 (lora_mode={lora_mode}):")
    for idx in top:
        text = tok.decode([int(idx)])
        print(f"  {idx:6d}: {logits[idx]:8.3f}  {repr(text)}")

    return logits


# Run with different LoRA modes
logits_T = run_forward("transposed")    # Same as test_transpose_fix.py
logits_D = run_forward("direct")         # LoRA as flat.reshape(ne[0], ne[1])
logits_P = run_forward("physical")       # LoRA as flat.reshape(ne[1], ne[0])

# Compare
print("\n=== Comparison ===")
d_TD = np.abs(logits_T - logits_D).max()
d_TP = np.abs(logits_T - logits_P).max()
d_DP = np.abs(logits_D - logits_P).max()
print(f"Max diff Transposed vs Direct: {d_TD:.4f}")
print(f"Max diff Transposed vs Physical: {d_TP:.4f}")
print(f"Max diff Direct vs Physical: {d_DP:.4f}")
