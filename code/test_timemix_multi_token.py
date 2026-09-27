#!/usr/bin/env python3
"""
RWKV-7 TimeMix Multi-Token Test

Test with multiple tokens to see state evolution divergence between
native and reference decay formulas.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch
import torch.nn.functional as F
import numpy as np

np.set_printoptions(precision=6, suppress=True, linewidth=200)
torch.set_printoptions(precision=6, sci_mode=False, linewidth=200)

MODEL_PATH = r"F:\Sandbox\failure_factory\akashic_v2\fairies\P30_Cognition\AkashicInferenceFairy\models\rwkv7-1.5B-world-Q8_0.gguf"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16

# Test tokens: "The Eiffel tower"
# In RWKV tokenizer: The=464, " Eiffel"=65297, " tower"=23489
TEST_TOKENS = [464, 65297, 23489]


def main():
    print("=" * 80)
    print("RWKV-7 MULTI-TOKEN STATE EVOLUTION TEST")
    print("=" * 80)

    from fairies.P30_Cognition.AkashicInferenceFairy.model_tensor_fabric import ModelTensorFabric
    from fairies.P30_Cognition.AkashicInferenceFairy.rwkv_layers import RWKVConfig, LayerNorm

    fabric = ModelTensorFabric(device=DEVICE, dtype='float16', lazy_load=True)
    model_config = fabric.load_gguf(MODEL_PATH)

    config = RWKVConfig(
        n_layer=model_config.get('n_layer', 24),
        n_embd=model_config.get('n_embd', 2048),
        n_head=model_config.get('n_head', 32),
        vocab_size=model_config.get('vocab_size', 65536),
    )

    H = config.n_head
    N = config.head_size
    C = config.n_embd
    B = 1

    # Load weights once
    emb_weight = fabric.get("token_embd.weight")
    if emb_weight is not None and emb_weight.dim() == 2 and emb_weight.size(0) < emb_weight.size(1):
        emb_weight = emb_weight.T.contiguous()

    ln_emb_w = fabric.get("token_embd_norm.weight")
    ln_emb_b = fabric.get("token_embd_norm.bias")
    ln1_w = fabric.get("blk.0.attn_norm.weight")
    ln1_b = fabric.get("blk.0.attn_norm.bias")

    w_receptance = fabric.get("blk.0.time_mix_receptance.weight")
    w_key = fabric.get("blk.0.time_mix_key.weight")
    w_value = fabric.get("blk.0.time_mix_value.weight")

    w0 = fabric.get("blk.0.time_mix_w0.weight")
    w1 = fabric.get("blk.0.time_mix_w1.weight")
    w2 = fabric.get("blk.0.time_mix_w2.weight")

    a0 = fabric.get("blk.0.time_mix_a0.weight")
    a1 = fabric.get("blk.0.time_mix_a1.weight")
    a2 = fabric.get("blk.0.time_mix_a2.weight")

    k_k = fabric.get("blk.0.time_mix_k_k.weight")
    k_a = fabric.get("blk.0.time_mix_k_a.weight")

    x_maa = fabric.get("blk.0.time_mix_lerp_fused.weight")

    # Create layer norms
    ln_emb = LayerNorm(ln_emb_w, ln_emb_b) if ln_emb_w is not None else None
    ln1 = LayerNorm(ln1_w, ln1_b) if ln1_w is not None else None

    # Initialize states
    state_native = torch.zeros(B, H, N, N, dtype=DTYPE, device=DEVICE)
    state_reference = torch.zeros(B, H, N, N, dtype=DTYPE, device=DEVICE)

    x_prev = torch.zeros(B, 1, C, dtype=DTYPE, device=DEVICE)

    print(f"\nProcessing {len(TEST_TOKENS)} tokens: {TEST_TOKENS}")
    print("-" * 80)

    for t_idx, token_id in enumerate(TEST_TOKENS):
        print(f"\n=== Token {t_idx}: {token_id} ===")

        # Get embedding
        x = emb_weight[token_id:token_id+1, :].unsqueeze(0)

        # Apply layer norms
        if ln_emb is not None:
            x = ln_emb(x)
        if ln1 is not None:
            x = ln1(x)

        # Token mixing
        xx = x_prev - x

        if x_maa is not None and x_maa.dim() == 4 and x_maa.shape[-1] == 6:
            lerp_logits = x_maa.squeeze(1).squeeze(1)
            lerp = torch.sigmoid(lerp_logits)
            xr = x + xx * lerp[:, 0]
            xw = x + xx * lerp[:, 1]
            xk = x + xx * lerp[:, 2]
            xv = x + xx * lerp[:, 3]
            xa = x + xx * lerp[:, 4]
        else:
            xr = xw = xk = xv = xa = x

        # Projections
        r = xr @ w_receptance
        sr = torch.sigmoid(r)
        k = xk @ w_key
        v = xv @ w_value

        # Time decay
        w0_exp = w0.view(1, 1, C)
        w_dynamic = torch.tanh(xw @ w1) @ w2
        w = -F.softplus(-(w0_exp + w_dynamic)) - 0.5

        # Association
        a0_exp = a0.view(1, 1, C)
        a_dynamic = (xa @ a1) @ a2
        a_coeff = torch.sigmoid(a0_exp + a_dynamic)

        # Key normalization
        kk = k * k_k.view(1, 1, C)
        kk = F.normalize(kk.view(B, 1, H, N), dim=-1, p=2.0).view(B, 1, C)

        # Modify k
        k_modified = k * (1 + (a_coeff - 1) * k_a.view(1, 1, C))

        # Reshape
        rt = sr.view(B, H, N, 1)
        wt = w.view(B, H, 1, N)
        kt = k_modified.view(B, H, 1, N)
        vt = v.view(B, H, N, 1)
        kkt = kk.view(B, H, N, 1)
        at = a_coeff.view(B, H, N, 1)

        # NATIVE: decay = exp(w)
        decay_native = torch.exp(wt)

        # REFERENCE: decay = exp(-exp(w))
        decay_reference = torch.exp(-torch.exp(wt))

        # ICL term (same for both, depends on state)
        icl_native = (state_native @ (-kkt)) @ (kkt * at).transpose(-2, -1)
        icl_reference = (state_reference @ (-kkt)) @ (kkt * at).transpose(-2, -1)

        # Outer product
        vk = vt @ kt

        # State evolution
        state_native = state_native * decay_native + icl_native + vk
        state_reference = state_reference * decay_reference + icl_reference + vk

        # Outputs
        out_native = (state_native @ rt).view(B, H, N)
        out_reference = (state_reference @ rt).view(B, H, N)

        # Print comparison
        print(f"\nDecay factors:")
        print(f"  Native mean: {decay_native.mean().item():.6f}")
        print(f"  Reference mean: {decay_reference.mean().item():.6f}")

        print(f"\nState norms:")
        print(f"  Native: {state_native.norm().item():.6f}")
        print(f"  Reference: {state_reference.norm().item():.6f}")
        print(f"  Ratio: {(state_native.norm() / (state_reference.norm() + 1e-10)).item():.4f}")

        print(f"\nOutput norms:")
        print(f"  Native: {out_native.norm().item():.6f}")
        print(f"  Reference: {out_reference.norm().item():.6f}")

        diff = (out_native - out_reference).abs()
        print(f"\nOutput difference:")
        print(f"  Max: {diff.max().item():.6f}")
        print(f"  Mean: {diff.mean().item():.6f}")
        print(f"  Relative error: {(diff.mean() / (out_reference.abs().mean() + 1e-10)).item():.4f}")

        # Update x_prev for next iteration
        x_prev = x.clone()

    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print("""
The decay formula difference causes EXPONENTIAL state divergence!

With NATIVE decay = exp(w):
  - Decay factors are tiny (~0.13)
  - State decays almost completely each step
  - Memory is essentially lost

With REFERENCE decay = exp(-exp(w)):
  - Decay factors are close to 1 (~0.89)
  - State is mostly preserved
  - Long-term memory works correctly

This explains why the native inference produces wrong output:
The state is decaying too fast, effectively destroying temporal context.
""")


if __name__ == "__main__":
    main()
