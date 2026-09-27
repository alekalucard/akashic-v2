"""Verify LoRA matrix layout given converter transpose.

The RWKV7 converter TRANSPOSES LoRA weights before writing:
  PyTorch w1: [rank, C] → converter .transpose(0,1) → [C, rank] → written to GGUF

So in GGUF:
  ne[0] = rank (fast dim), ne[1] = C
  Physical: flat.reshape(C, rank) = [C, rank]
  For x @ w1 where x=[C]: need [C, rank] = physical directly, NO transpose needed

BUT for regular weights (receptance, key, etc.):
  PyTorch: [out, in] = [C, C] → NOT transposed by converter
  ne[0] = C (in_features, fast dim), ne[1] = C (out_features)
  Physical: flat.reshape(C, C) = [out, in]
  For x @ W where x=[C]: need [C, C] = physical.T

Summary:
  Regular weights: need transpose (physical.T)
  LoRA weights: NO transpose needed (already transposed by converter)
"""
import sys, os, numpy as np
sys.path.insert(0, r"F:\Sandbox\failure_factory\akashic_v2")
FAIRY_DIR = r"F:\Sandbox\failure_factory\akashic_v2\fairies\P30_Cognition\AkashicInferenceFairy"
sys.path.insert(0, FAIRY_DIR)

GGUF_PATH = os.path.join(FAIRY_DIR, "models", "rwkv7-official-1.5B-Q8_0.gguf")

from gguf_parser import GGUFParser
parser = GGUFParser()
gguf = parser.parse(GGUF_PATH)

print("=== LoRA weight ne[] dimensions ===")
lora_names = [
    "blk.0.time_mix_w1.weight", "blk.0.time_mix_w2.weight",
    "blk.0.time_mix_a1.weight", "blk.0.time_mix_a2.weight",
    "blk.0.time_mix_v1.weight", "blk.0.time_mix_v2.weight",
    "blk.0.time_mix_g1.weight", "blk.0.time_mix_g2.weight",
]
for name in lora_names:
    info = gguf.tensors[name]
    print(f"  {name}: ne={info.shape}, type_id={info.type_id}, n_elements={info.n_elements}")

print("\n=== Regular weight ne[] dimensions ===")
regular_names = [
    "blk.0.time_mix_receptance.weight",
    "blk.0.time_mix_key.weight",
    "blk.0.time_mix_value.weight",
    "blk.0.time_mix_output.weight",
    "blk.0.channel_mix_key.weight",
    "blk.0.channel_mix_value.weight",
    "output.weight",
    "token_embd.weight",
]
for name in regular_names:
    info = gguf.tensors[name]
    print(f"  {name}: ne={info.shape}, type_id={info.type_id}, n_elements={info.n_elements}")

print("\n=== Analysis ===")
# w1: PyTorch [rank, C] → transposed → [C, rank] written to GGUF
# ne=(2048, 96): ne[0]=2048, ne[1]=96
# Wait... if converter writes [C, rank] = [2048, 96], and GGML ne[0] is fast dim...
# Then ne[0]=2048 means fast dim is C? Or rank?

# Let me think about this from GGML's perspective:
# GGML writes tensors with ne[0] as the fast dimension
# A tensor of shape [rows, cols] in the writer gets:
#   ne[0] = cols (fast dim = stride-1 dimension)
#   ne[1] = rows
# So for the writer receiving [C, rank] = [2048, 96]:
#   ne[0] = 96 (cols = fast dim = rank)
#   ne[1] = 2048 (rows = C)
# BUT the parser shows ne=(2048, 96)
# Hmm, this depends on how PyTorch tensors are written...

# Actually, in GGML convention for a 2D tensor:
#   ne[0] = number of elements in each row (= cols in C-order)
#   ne[1] = number of rows
# So ne=(2048, 96) means: 96 rows of 2048 elements each
# Physical flat: flat[row * 2048 + col], shape = [96, 2048]

# For w1 BEFORE converter transpose: PyTorch [rank=96, C=2048]
# After converter transpose: [C=2048, rank=96]
# When GGML writes this with ne[0]=cols=96, ne[1]=rows=2048:
#   ne = (96, 2048)
# But our parser shows ne = (2048, 96)!

# This means either:
# 1. The parser is reporting ne in a different order, or
# 2. GGML writes with ne[0]=rows, not ne[0]=cols

# Let me check: for channel_mix_key with PyTorch [n_ff=8192, C=2048] (nn.Linear):
# NOT transposed by converter
# If GGML ne[0] = cols: ne = (2048, 8192) ← matches parser!
# If GGML ne[0] = rows: ne = (8192, 2048) ← doesn't match

# So ne[0] IS cols (fast dim / inner dim)
# For cm_key: ne=(2048, 8192): 8192 rows of 2048 cols
# Physical: flat[row * 2048 + col] → flat.reshape(8192, 2048) → [n_ff, C]
# For x @ W: need [C, n_ff] = physical.T ✓

# Now for w1 AFTER converter transpose: tensor is [C=2048, rank=96]
# GGML writes with ne[0]=cols=96, ne[1]=rows=2048 → ne = (96, 2048)
# But parser shows ne = (2048, 96)!
# This is BACKWARDS from what we'd expect...

# UNLESS the converter transposes to [C, rank] = [2048, 96]
# And GGML interprets this as ne[0]=2048 (treating first PyTorch dim as fast)
# Let's check: HF tensors are row-major (C-order).
# [2048, 96] in C-order: flat[i * 96 + j] → ne[0]=96 should be fast dim
# But ne shows (2048, 96), so ne[0]=2048 ≠ 96

# WAIT. Let me reconsider. Maybe the gguf writer writes ne backwards from numpy?
# In numpy: arr.shape = (rows, cols) → C-order: flat[row * cols + col]
# In GGML: ne = (cols, rows) → ne[0] = cols = fast dim
# So for a numpy/PyTorch tensor of shape (2048, 96):
#   ne[0] = 96 (cols), ne[1] = 2048 (rows)
# But we see ne = (2048, 96)

# Unless the WRITER uses ne[0] = first dimension of input shape?
# Let me check the actual data to determine which interpretation is right.

from quantization import dequantize_tensor

# w1: ne=(2048, 96), total elements = 196608 = 2048 * 96
w1_info = gguf.tensors["blk.0.time_mix_w1.weight"]
w1_raw = gguf.get_tensor_data("blk.0.time_mix_w1.weight")
w1_flat = dequantize_tensor(w1_raw, w1_info.type_id, w1_info.shape, to_torch=False).flatten().astype(np.float32)

# For the CORRECT w1 matrix: x=[C=2048] @ w1=[C,rank=96] → out=[rank=96]
# Let's test both interpretations:
# A: ne[0]=fast dim → physical = [96, 2048] → for matmul: .T = [2048, 96]
# B: ne[0]=first dim → physical = [2048, 96] → direct = [2048, 96] (already [C, rank])

print(f"\nw1 ne={w1_info.shape}, total={len(w1_flat)}")
w1_A = w1_flat.reshape(96, 2048).T  # [2048, 96] = [C, rank]
w1_B = w1_flat.reshape(2048, 96)     # [2048, 96] = [C, rank]

print(f"  w1_A (reshape(96,2048).T): [0,:5] = {w1_A[0,:5]}")
print(f"  w1_B (reshape(2048,96)):   [0,:5] = {w1_B[0,:5]}")
print(f"  Same? {np.allclose(w1_A, w1_B)}")
print(f"  Max diff: {np.max(np.abs(w1_A - w1_B)):.6f}")

# Check cm_key: ne=(2048, 8192)
# PyTorch nn.Linear [8192, 2048] = [out, in], NOT transposed by converter
# GGML: ne=(2048, 8192)
# If ne[0]=fast dim: physical = [8192, 2048] → .T = [2048, 8192] for x @ W
# If ne[0]=first dim: physical = [2048, 8192] → direct = [2048, 8192] for x @ W

cmk_info = gguf.tensors["blk.0.channel_mix_key.weight"]
cmk_raw = gguf.get_tensor_data("blk.0.channel_mix_key.weight")
cmk_flat = dequantize_tensor(cmk_raw, cmk_info.type_id, cmk_info.shape, to_torch=False).flatten().astype(np.float32)

print(f"\ncm_key ne={cmk_info.shape}, total={len(cmk_flat)}")
cmk_A = cmk_flat.reshape(8192, 2048).T  # [2048, 8192]
cmk_B = cmk_flat.reshape(2048, 8192)     # [2048, 8192]
print(f"  cm_key_A (reshape(8192,2048).T): [0,:5] = {cmk_A[0,:5]}")
print(f"  cm_key_B (reshape(2048,8192)):   [0,:5] = {cmk_B[0,:5]}")
print(f"  Same? {np.allclose(cmk_A, cmk_B)}")
print(f"  Max diff: {np.max(np.abs(cmk_A - cmk_B)):.6f}")

# Now the critical test: which interpretation gives coherent output?
# We already know from test_transpose_fix.py that SOME transpose gives coherent output.
# The question is: do we need to transpose regular weights AND LoRA weights,
# or only regular weights (LoRA already pre-transposed)?

# If GGML stores as: flat.reshape(ne[1], ne[0]) = physical
# Then for w1 with ne=(2048, 96): physical = reshape(96, 2048) = [96, 2048]
# The converter wrote [C, rank] = [2048, 96], so physical should be [2048, 96]
# reshape(96, 2048) ≠ [2048, 96]... unless ne[0] ISN'T the fast dim for w1

# Actually, let me just check: does our gguf_parser report ne in the same order as GGML?
print("\n=== Checking ne[] order ===")
# Lerp fused: known to be [6, 1, 1, 2048] in GGML (component-major)
# Or [2048, 1, 1, 6] if ne[0] = first dim of PyTorch tensor
lerp_info = gguf.tensors["blk.0.time_mix_lerp_fused.weight"]
print(f"lerp_fused: ne={lerp_info.shape}, n_dims={len(lerp_info.shape)}")
# Converter does: data = data_torch.reshape(6, 1, 1, -1) → PyTorch shape (6, 1, 1, C)
# If ne follows PyTorch dims: ne = (6, 1, 1, 2048)
# If ne reverses: ne = (2048, 1, 1, 6)
# Our parser shows (2048, 1, 1, 6) → ne[0] = C = the LAST dim of PyTorch
# This is GGML convention: ne[0] = innermost/fastest = last dim of C-order tensor

print("\n=== DEFINITIVE ANSWER ===")
print("GGML ne[] is REVERSED from PyTorch/numpy dimension order!")
print("ne[0] = LAST dimension of PyTorch shape = innermost/fastest")
print("")
print("For lerp_fused:")
print("  PyTorch shape: (6, 1, 1, C=2048)")
print("  GGML ne: (2048, 1, 1, 6)")
print("  ne[0]=2048 = last PyTorch dim (C) ✓")
print("")
print("For w1 AFTER converter transpose:")
print("  Converter input: PyTorch [rank=96, C=2048]")
print("  After .transpose(0,1): PyTorch [C=2048, rank=96]")
print("  GGML ne: should be (96, 2048) -- ne[0]=96=last dim of [2048,96]")
print(f"  Actual ne from parser: {gguf.tensors['blk.0.time_mix_w1.weight'].shape}")
print("")
print("For cm_key (NOT transposed by converter):")
print("  PyTorch: [n_ff=8192, C=2048]")
print("  GGML ne: should be (2048, 8192) -- ne[0]=2048=last dim of [8192,2048]")
print(f"  Actual ne from parser: {gguf.tensors['blk.0.channel_mix_key.weight'].shape}")
