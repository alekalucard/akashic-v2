#!/usr/bin/env python3
"""
RWKV-7 TimeMix Detailed Tracing Script

Objective: Trace EXACTLY what happens in layer 0's TimeMix for input "Hello" (token 33155)
to identify where values diverge from expected behavior.
"""

import sys
import os

# Add the path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch
import torch.nn.functional as F
import numpy as np

np.set_printoptions(precision=6, suppress=True, linewidth=200)
torch.set_printoptions(precision=6, sci_mode=False, linewidth=200)

# Configuration
MODEL_PATH = r"F:\Sandbox\failure_factory\akashic_v2\fairies\P30_Cognition\AkashicInferenceFairy\models\rwkv7-1.5B-world-Q8_0.gguf"
TOKEN_ID = 33155  # "Hello"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16

print("=" * 80)
print("RWKV-7 TIMEMIX LAYER 0 DETAILED TRACE")
print("=" * 80)
print(f"Model: {MODEL_PATH}")
print(f"Token: {TOKEN_ID} ('Hello')")
print(f"Device: {DEVICE}")
print(f"Dtype: {DTYPE}")
print("=" * 80)


def trace_stat(name: str, tensor: torch.Tensor, show_values: int = 5):
    """Print comprehensive statistics for a tensor."""
    t = tensor.detach().float()
    print(f"\n--- {name} ---")
    print(f"  Shape: {list(tensor.shape)}")
    print(f"  Dtype: {tensor.dtype}")
    print(f"  Norm (L2): {t.norm().item():.6f}")
    print(f"  Mean: {t.mean().item():.6f}")
    print(f"  Std: {t.std().item():.6f}")
    print(f"  Min: {t.min().item():.6f}")
    print(f"  Max: {t.max().item():.6f}")
    flat = t.flatten()
    if show_values > 0:
        print(f"  First {show_values}: {flat[:show_values].cpu().numpy()}")
        print(f"  Last {show_values}: {flat[-show_values:].cpu().numpy()}")


def main():
    # =========================================================================
    # STEP 1: Load Model
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 1: LOADING MODEL")
    print("=" * 80)

    from fairies.P30_Cognition.AkashicInferenceFairy.model_tensor_fabric import ModelTensorFabric
    from fairies.P30_Cognition.AkashicInferenceFairy.rwkv_layers import RWKVConfig, LayerNorm

    fabric = ModelTensorFabric(device=DEVICE, dtype='float16', lazy_load=True)
    model_config = fabric.load_gguf(MODEL_PATH)

    print(f"\nModel config: {model_config}")

    config = RWKVConfig(
        n_layer=model_config.get('n_layer', 24),
        n_embd=model_config.get('n_embd', 2048),
        n_head=model_config.get('n_head', 32),
        vocab_size=model_config.get('vocab_size', 65536),
    )

    H = config.n_head
    N = config.head_size
    C = config.n_embd

    print(f"\nConfig:")
    print(f"  n_layer: {config.n_layer}")
    print(f"  n_embd: {config.n_embd}")
    print(f"  n_head: {config.n_head}")
    print(f"  head_size: {config.head_size}")

    # =========================================================================
    # STEP 2: Get Token Embedding
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 2: TOKEN EMBEDDING")
    print("=" * 80)

    emb_weight = fabric.get("token_embd.weight")
    if emb_weight is not None and emb_weight.dim() == 2 and emb_weight.size(0) < emb_weight.size(1):
        emb_weight = emb_weight.T.contiguous()

    trace_stat("Embedding table", emb_weight)

    # Get embedding for "Hello" token
    x = emb_weight[TOKEN_ID:TOKEN_ID+1, :].unsqueeze(0)  # [1, 1, C]
    trace_stat("Raw token embedding (Hello)", x)

    # Apply embedding layer norm (RWKV-7 uses LayerNorm with bias)
    ln_emb_w = fabric.get("token_embd_norm.weight")
    ln_emb_b = fabric.get("token_embd_norm.bias")

    if ln_emb_w is not None:
        ln = LayerNorm(ln_emb_w, ln_emb_b)
        x = ln(x)
        trace_stat("After embedding LayerNorm", x)

    # =========================================================================
    # STEP 3: Load Layer 0 TimeMix Weights
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 3: LAYER 0 TIMEMIX WEIGHTS")
    print("=" * 80)

    prefix = "blk.0"

    # First, apply attn_norm (ln1) to input
    ln1_w = fabric.get(f"{prefix}.attn_norm.weight")
    ln1_b = fabric.get(f"{prefix}.attn_norm.bias")

    if ln1_w is not None:
        ln1 = LayerNorm(ln1_w, ln1_b)
        x_normed = ln1(x)
        trace_stat("After attn_norm (ln1) - INPUT TO TIMEMIX", x_normed)
    else:
        x_normed = x
        print("WARNING: No attn_norm found!")

    # Load TimeMix weights
    w_receptance = fabric.get(f"{prefix}.time_mix_receptance.weight")
    w_key = fabric.get(f"{prefix}.time_mix_key.weight")
    w_value = fabric.get(f"{prefix}.time_mix_value.weight")
    w_output = fabric.get(f"{prefix}.time_mix_output.weight")

    w0 = fabric.get(f"{prefix}.time_mix_w0.weight")
    w1 = fabric.get(f"{prefix}.time_mix_w1.weight")
    w2 = fabric.get(f"{prefix}.time_mix_w2.weight")

    a0 = fabric.get(f"{prefix}.time_mix_a0.weight")
    a1 = fabric.get(f"{prefix}.time_mix_a1.weight")
    a2 = fabric.get(f"{prefix}.time_mix_a2.weight")

    g1 = fabric.get(f"{prefix}.time_mix_g1.weight")
    g2 = fabric.get(f"{prefix}.time_mix_g2.weight")

    k_k = fabric.get(f"{prefix}.time_mix_k_k.weight")
    k_a = fabric.get(f"{prefix}.time_mix_k_a.weight")
    r_k = fabric.get(f"{prefix}.time_mix_r_k.weight")

    ln_x_w = fabric.get(f"{prefix}.time_mix_ln.weight")
    ln_x_b = fabric.get(f"{prefix}.time_mix_ln.bias")

    x_maa = fabric.get(f"{prefix}.time_mix_lerp_fused.weight")

    # Print weight stats
    trace_stat("w_receptance", w_receptance)
    trace_stat("w_key", w_key)
    trace_stat("w_value", w_value)
    trace_stat("w0 (time_decay base)", w0)
    trace_stat("a0 (association base)", a0)
    trace_stat("k_k", k_k)
    trace_stat("x_maa (lerp_fused)", x_maa)

    # =========================================================================
    # STEP 4: Token Mixing / Lerp
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 4: TOKEN MIXING (LERP)")
    print("=" * 80)

    B, T, _ = x_normed.size()

    # For T=1, x_prev is zeros (no previous token)
    x_prev = torch.zeros_like(x_normed)
    xx = x_prev - x_normed  # Time shift difference (negative of x for first token)

    trace_stat("xx (x_prev - x)", xx)

    if x_maa is not None and x_maa.dim() == 4 and x_maa.shape[-1] == 6:
        print(f"\nx_maa shape: {x_maa.shape}")

        # Extract lerp ratios
        lerp_logits = x_maa.squeeze(1).squeeze(1)  # [C, 6]
        print(f"lerp_logits shape: {lerp_logits.shape}")

        # CRITICAL: Check if these need sigmoid!
        print(f"\nlerp_logits stats (BEFORE sigmoid):")
        for i, name in enumerate(['r', 'w', 'k', 'v', 'a', 'g']):
            col = lerp_logits[:, i]
            print(f"  {name}: mean={col.mean().item():.4f}, min={col.min().item():.4f}, max={col.max().item():.4f}")

        lerp = torch.sigmoid(lerp_logits)

        print(f"\nlerp stats (AFTER sigmoid):")
        for i, name in enumerate(['r', 'w', 'k', 'v', 'a', 'g']):
            col = lerp[:, i]
            print(f"  {name}: mean={col.mean().item():.4f}, min={col.min().item():.4f}, max={col.max().item():.4f}")

        # Compute lerped inputs
        xr = x_normed + xx * lerp[:, 0]
        xw = x_normed + xx * lerp[:, 1]
        xk = x_normed + xx * lerp[:, 2]
        xv = x_normed + xx * lerp[:, 3]
        xa = x_normed + xx * lerp[:, 4]
        xg = x_normed + xx * lerp[:, 5]

        trace_stat("xr (for receptance)", xr)
        trace_stat("xk (for key)", xk)
    else:
        print("WARNING: No fused lerp found or wrong shape!")
        xr = xw = xk = xv = xa = xg = x_normed

    # =========================================================================
    # STEP 5: R, K, V Projections
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 5: R, K, V PROJECTIONS")
    print("=" * 80)

    # Receptance
    r = xr @ w_receptance if w_receptance is not None else xr
    trace_stat("r (before sigmoid)", r)

    sr = torch.sigmoid(r)
    trace_stat("sr = sigmoid(r)", sr)

    # Key
    k = xk @ w_key if w_key is not None else xk
    trace_stat("k (raw key)", k)

    # Value
    v = xv @ w_value if w_value is not None else xv
    trace_stat("v (raw value)", v)

    # Gate
    if g1 is not None and g2 is not None:
        g = torch.sigmoid((xg @ g1) @ g2)
        trace_stat("g (gate)", g)
    else:
        g = torch.ones_like(x_normed)
        print("WARNING: No gate LoRA found!")

    # =========================================================================
    # STEP 6: Time Decay (w)
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 6: TIME DECAY (w)")
    print("=" * 80)

    if w0 is not None and w1 is not None and w2 is not None:
        trace_stat("w0 (base decay)", w0)
        trace_stat("w1 (LoRA down)", w1)
        trace_stat("w2 (LoRA up)", w2)

        w0_exp = w0.view(1, 1, C)
        w_dynamic = torch.tanh(xw @ w1) @ w2
        trace_stat("tanh(xw @ w1) @ w2 (dynamic)", w_dynamic)

        # RWKV-7 formula: w = -softplus(-(w0 + w_dynamic)) - 0.5
        w_sum = w0_exp + w_dynamic
        trace_stat("w0 + w_dynamic", w_sum)

        w = -F.softplus(-w_sum) - 0.5
        trace_stat("w = -softplus(-(w0+dynamic)) - 0.5", w)

        # CRITICAL: Compare with reference formula
        # Reference: w = torch.exp(-torch.exp(w.view(...)))
        # Note: The reference applies exp(-exp(w)) to get decay factor
        # Our formula gives w in log space, so exp(w) should give decay

        print("\n>>> DECAY FACTOR COMPARISON <<<")
        decay_native = torch.exp(w)
        trace_stat("exp(w) - Native decay factor", decay_native)

        # What if reference uses different formula?
        # Reference line 270: w = -F.softplus(-(self.w0 + torch.tanh(xw @ self.w1) @ self.w2)) - 0.5
        # Reference line 179: w = torch.exp(-torch.exp(w.view(...)))
        # The reference passes w to RWKV7_OP, which then does exp(-exp(w))!

        decay_reference = torch.exp(-torch.exp(w))
        trace_stat("exp(-exp(w)) - Reference decay factor", decay_reference)
    else:
        print("WARNING: Missing decay LoRA weights!")
        w = torch.full((B, T, C), -1.0, device=x_normed.device, dtype=x_normed.dtype)

    # =========================================================================
    # STEP 7: Association Coefficient (a)
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 7: ASSOCIATION COEFFICIENT (a)")
    print("=" * 80)

    if a0 is not None and a1 is not None and a2 is not None:
        trace_stat("a0 (base association)", a0)

        a0_exp = a0.view(1, 1, C)
        a_dynamic = (xa @ a1) @ a2
        trace_stat("(xa @ a1) @ a2 (dynamic)", a_dynamic)

        a_coeff = torch.sigmoid(a0_exp + a_dynamic)
        trace_stat("a_coeff = sigmoid(a0 + dynamic)", a_coeff)
    else:
        print("WARNING: Missing association LoRA weights!")
        a_coeff = torch.ones(B, T, C, device=x_normed.device, dtype=x_normed.dtype) * 0.5

    # =========================================================================
    # STEP 8: Key Normalization (kk)
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 8: KEY NORMALIZATION (kk)")
    print("=" * 80)

    if k_k is not None:
        trace_stat("k_k weight", k_k)

        kk = k * k_k.view(1, 1, C)
        trace_stat("k * k_k (before norm)", kk)

        # L2 normalize per head
        kk_reshaped = kk.view(B, T, H, N)
        kk_normed = F.normalize(kk_reshaped, dim=-1, p=2.0)
        kk = kk_normed.view(B, T, C)
        trace_stat("kk (after L2 norm per head)", kk)
    else:
        kk = F.normalize(k.view(B, T, H, N), dim=-1, p=2.0).view(B, T, C)
        trace_stat("kk (normalized without k_k)", kk)

    # Modify k for state update
    if k_a is not None:
        trace_stat("k_a weight", k_a)
        k_modified = k * (1 + (a_coeff - 1) * k_a.view(1, 1, C))
        trace_stat("k * (1 + (a-1) * k_a)", k_modified)
    else:
        k_modified = k

    # =========================================================================
    # STEP 9: STATE EVOLUTION (THE CORE)
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 9: STATE EVOLUTION (CORE RWKV-7)")
    print("=" * 80)

    # Initialize state
    state = torch.zeros(B, H, N, N, dtype=x_normed.dtype, device=x_normed.device)
    trace_stat("Initial state", state)

    # Reshape for heads
    r_h = sr.view(B, T, H, N)
    w_h = w.view(B, T, H, N)
    k_h = k_modified.view(B, T, H, N)
    v_h = v.view(B, T, H, N)
    kk_h = kk.view(B, T, H, N)
    a_h = a_coeff.view(B, T, H, N)

    # Single timestep (t=0)
    t = 0
    rt = r_h[:, t, :, :].view(B, H, N, 1)      # [B, H, N, 1]
    wt = w_h[:, t, :, :].view(B, H, 1, N)      # [B, H, 1, N]
    kt = k_h[:, t, :, :].view(B, H, 1, N)      # [B, H, 1, N]
    vt = v_h[:, t, :, :].view(B, H, N, 1)      # [B, H, N, 1]
    kkt = kk_h[:, t, :, :].view(B, H, N, 1)    # [B, H, N, 1]
    at = a_h[:, t, :, :].view(B, H, N, 1)      # [B, H, N, 1]

    print("\n--- Reshaped tensors for state evolution ---")
    trace_stat("rt [B,H,N,1]", rt)
    trace_stat("wt [B,H,1,N]", wt)
    trace_stat("kt [B,H,1,N]", kt)
    trace_stat("vt [B,H,N,1]", vt)
    trace_stat("kkt [B,H,N,1]", kkt)
    trace_stat("at [B,H,N,1]", at)

    # NATIVE implementation decay
    print("\n--- NATIVE STATE EVOLUTION ---")
    decay_native = torch.exp(wt)
    trace_stat("Native: decay = exp(wt)", decay_native)

    # ICL term: state @ (-kk) @ (kk * a).T
    icl_term_native = (state @ (-kkt)) @ (kkt * at).transpose(-2, -1)
    trace_stat("Native: ICL term = state @ (-kk) @ (kk*a).T", icl_term_native)

    # Outer product: v @ k
    vk_native = vt @ kt
    trace_stat("Native: vk = v @ k", vk_native)

    # State evolution
    state_native = state * decay_native + icl_term_native + vk_native
    trace_stat("Native: new_state = state*decay + icl + vk", state_native)

    # Output
    out_native = (state_native @ rt).view(B, H, N)
    trace_stat("Native: output = state @ r", out_native)

    # REFERENCE implementation
    print("\n--- REFERENCE STATE EVOLUTION ---")
    # Reference: w = torch.exp(-torch.exp(w))
    decay_ref = torch.exp(-torch.exp(wt))
    trace_stat("Reference: decay = exp(-exp(wt))", decay_ref)

    # Reference: a=-kk, b=kk*a
    # state = state * w + state @ aa @ bb + vv @ kk
    # where aa = a.view(B,H,N,1), bb = b.view(B,H,1,N)
    aa_ref = (-kkt)  # [B, H, N, 1]
    bb_ref = (kkt * at).transpose(-2, -1)  # [B, H, 1, N]

    icl_term_ref = state @ aa_ref @ bb_ref
    trace_stat("Reference: ICL = state @ aa @ bb", icl_term_ref)

    state_ref = state * decay_ref + icl_term_ref + vk_native
    trace_stat("Reference: new_state", state_ref)

    out_ref = (state_ref @ rt).view(B, H, N)
    trace_stat("Reference: output = state @ r", out_ref)

    # =========================================================================
    # STEP 10: Compare outputs
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 10: OUTPUT COMPARISON")
    print("=" * 80)

    print("\n>>> KEY FINDING: DECAY FACTOR DIFFERENCE <<<")
    print(f"Native decay (exp(w)) mean: {decay_native.mean().item():.6f}")
    print(f"Reference decay (exp(-exp(w))) mean: {decay_ref.mean().item():.6f}")
    print(f"Ratio: {(decay_native.mean() / decay_ref.mean()).item():.6f}")

    print("\n>>> OUTPUT DIFFERENCE <<<")
    print(f"Native output norm: {out_native.norm().item():.6f}")
    print(f"Reference output norm: {out_ref.norm().item():.6f}")

    diff = (out_native - out_ref).abs()
    print(f"Absolute difference: max={diff.max().item():.6f}, mean={diff.mean().item():.6f}")

    # =========================================================================
    # STEP 11: Apply GroupNorm and complete output
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 11: GROUPNORM AND FINAL OUTPUT")
    print("=" * 80)

    out_native_flat = out_native.view(B * T, C)

    if ln_x_w is not None:
        out_normed = F.group_norm(
            out_native_flat.unsqueeze(-1),
            num_groups=H,
            weight=ln_x_w,
            bias=ln_x_b,
            eps=64e-5
        ).squeeze(-1)
        trace_stat("After GroupNorm", out_normed)
    else:
        out_normed = out_native_flat
        print("WARNING: No GroupNorm weights found!")

    out_final = out_normed.view(B, T, C)

    # r_k residual
    if r_k is not None:
        trace_stat("r_k weight", r_k)
        r_k_exp = r_k.view(1, 1, H, N)
        residual = ((r_h * k_h * r_k_exp).sum(dim=-1, keepdim=True) * v_h).view(B, T, C)
        trace_stat("r_k residual", residual)
        out_final = out_final + residual

    # Gate
    out_final = out_final * g
    trace_stat("After gate", out_final)

    # Output projection
    if w_output is not None:
        out_projected = out_final @ w_output
        trace_stat("Final TimeMix output (after output projection)", out_projected)
    else:
        out_projected = out_final

    print("\n" + "=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)
    print("""
CRITICAL FINDING: The decay formula differs between implementations!

NATIVE (rwkv_layers.py):
    decay = exp(w)
    where w = -softplus(-(w0 + dynamic)) - 0.5

REFERENCE (rwkv_v7_demo.py):
    decay = exp(-exp(w))
    where w = -softplus(-(w0 + dynamic)) - 0.5

The reference applies an ADDITIONAL exp(-exp(...)) transformation!
This is because the reference passes w directly to RWKV7_OP, which
then applies the double-exp transformation (line 179).

FIX: In rwkv_layers.py line 490, change:
    decay = torch.exp(wt)
TO:
    decay = torch.exp(-torch.exp(wt))
""")


if __name__ == "__main__":
    main()
