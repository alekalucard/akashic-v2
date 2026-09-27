"""Verify embedding layout using official gguf package as ground truth.

The official GGUFReader reverses ne dimensions:
  GGUF ne=(2048, 65536) → reader shape=(65536, 2048)

If the reader's shape is the CORRECT numpy shape, then:
  reader_data.reshape(65536, 2048)[token_id] should give correct embedding.

We compare this against our two candidate interpretations:
  A) Physical: flat.reshape(65536, 2048)  [ne[1], ne[0]] -- ne[0] is fast dim
  B) Old:      flat.reshape(2048, 65536).T [ne[0], ne[1]].T -- Python model's approach
"""
import sys, os, numpy as np
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

# === Method 1: Official gguf package ===
from gguf import GGUFReader
reader = GGUFReader(GGUF_PATH)

emb_tensor = None
head_tensor = None
w1_tensor = None
cm_key_tensor = None

for t in reader.tensors:
    if t.name == "token_embd.weight":
        emb_tensor = t
    elif t.name == "output.weight":
        head_tensor = t
    elif t.name == "blk.0.time_mix_w1.weight":
        w1_tensor = t
    elif t.name == "blk.0.channel_mix_key.weight":
        cm_key_tensor = t

print("=== Official GGUFReader shapes ===")
print(f"token_embd.weight: shape={emb_tensor.shape}, type={emb_tensor.tensor_type}")
print(f"output.weight:     shape={head_tensor.shape}, type={head_tensor.tensor_type}")
print(f"w1.weight:         shape={w1_tensor.shape}, type={w1_tensor.tensor_type}")
print(f"cm_key.weight:     shape={cm_key_tensor.shape}, type={cm_key_tensor.tensor_type}")

# For Q8_0, the raw data needs dequantization. Let's get it via our parser too.
from gguf_parser import GGUFParser
from quantization import dequantize_tensor

parser = GGUFParser()
gguf = parser.parse(GGUF_PATH)

# === Compare embedding token 6699 ===
token_id = 6699
C = 2048

# Our dequantized flat data
emb_info = gguf.tensors["token_embd.weight"]
emb_raw = gguf.get_tensor_data("token_embd.weight")
emb_flat = dequantize_tensor(emb_raw, emb_info.type_id, emb_info.shape, to_torch=False).flatten().astype(np.float32)

print(f"\n=== Embedding ne from GGUF: {emb_info.shape} ===")
print(f"Total elements: {len(emb_flat)}")

# Interpretation A: Physical layout [ne[1], ne[0]] = [65536, 2048]
emb_A = emb_flat.reshape(65536, 2048)
tok_A = emb_A[token_id]

# Interpretation B: Old approach [ne[0], ne[1]].T = [2048, 65536].T = [65536, 2048]
emb_B = emb_flat.reshape(2048, 65536).T  # Note: this is NOT contiguous
tok_B = emb_B[token_id].copy()  # Make contiguous

print(f"\nToken {token_id} embedding comparison:")
print(f"  A (physical [{65536},{2048}]):  first5={tok_A[:5]}, norm={np.linalg.norm(tok_A):.4f}")
print(f"  B (reshape.T):                  first5={tok_B[:5]}, norm={np.linalg.norm(tok_B):.4f}")
print(f"  Max diff A vs B: {np.max(np.abs(tok_A - tok_B)):.6f}")
print(f"  Are they same? {np.allclose(tok_A, tok_B)}")

# Also check token 0 and token 1
for tid in [0, 1, 2, 100]:
    a = emb_flat.reshape(65536, 2048)[tid]
    b = emb_flat.reshape(2048, 65536).T[tid].copy()
    diff = np.max(np.abs(a - b))
    print(f"  Token {tid}: max_diff={diff:.6f}, A_norm={np.linalg.norm(a):.4f}, B_norm={np.linalg.norm(b):.4f}")

# === Now the critical question: which matches what the official reader sees? ===
# The official reader gives raw Q8_0 bytes in reader shape order.
# But we can't directly compare Q8_0 raw bytes to dequantized values.
# Instead, let's look at what the official reader's data layout implies.
#
# The official reader shape for token_embd is (65536, padded_2048) for Q8_0.
# Q8_0 pads the fast dimension to block size 32. 2048 is already divisible by 32.
# So reader shape should be (65536, 2048) or (65536, 2176) depending on raw vs dequant.

print(f"\nOfficial reader raw data shape: {emb_tensor.data.shape}")
print(f"Official reader tensor shape: {emb_tensor.shape}")

# === Test a known-good weight matrix (smaller) ===
# blk.0.time_mix_w1.weight: ne=(2048, 96)
# Official reader: shape should be (96, 2048) or similar
w1_info = gguf.tensors["blk.0.time_mix_w1.weight"]
w1_raw = gguf.get_tensor_data("blk.0.time_mix_w1.weight")
w1_flat = dequantize_tensor(w1_raw, w1_info.type_id, w1_info.shape, to_torch=False).flatten().astype(np.float32)

print(f"\n=== w1 weight: ne={w1_info.shape}, total={len(w1_flat)} ===")
print(f"Official reader shape: {w1_tensor.shape}")

# For w1 with ne=(2048, 96):
# If ne[0]=2048 is fast dim: physical=[96, 2048], want [2048, 96] for x@W
w1_A = w1_flat.reshape(96, 2048).T  # Physical [96, 2048] → transposed [2048, 96]
# If ne[0]=2048 is row count: [2048, 96] directly
w1_B = w1_flat.reshape(2048, 96)

print(f"  A (physical.T [2048,96]): first_row[:5]={w1_A[0,:5]}")
print(f"  B (direct [2048,96]):     first_row[:5]={w1_B[0,:5]}")
print(f"  Max diff: {np.max(np.abs(w1_A - w1_B)):.6f}")

# === Test channel_mix_key: ne=(2048, 8192) ===
cmk_info = gguf.tensors["blk.0.channel_mix_key.weight"]
cmk_raw = gguf.get_tensor_data("blk.0.channel_mix_key.weight")
cmk_flat = dequantize_tensor(cmk_raw, cmk_info.type_id, cmk_info.shape, to_torch=False).flatten().astype(np.float32)

print(f"\n=== channel_mix_key: ne={cmk_info.shape}, total={len(cmk_flat)} ===")
print(f"Official reader shape: {cm_key_tensor.shape}")

# Interpretation A: ne[0]=fast, physical=[8192, 2048], transpose=[2048, 8192]
cmk_A = cmk_flat.reshape(8192, 2048).T  # [2048, 8192]
# Interpretation B: ne[0]=rows, [2048, 8192] directly
cmk_B = cmk_flat.reshape(2048, 8192)

print(f"  A (physical.T [2048,8192]): [0,:5]={cmk_A[0,:5]}")
print(f"  B (direct [2048,8192]):     [0,:5]={cmk_B[0,:5]}")
print(f"  Max diff: {np.max(np.abs(cmk_A - cmk_B)):.6f}")

# === For a definitive answer, compare with original PyTorch weights if available ===
# The RWKV7 model's channel_mix_key in PyTorch is nn.Linear(C, n_ff, bias=False)
# nn.Linear stores weight as [out_features, in_features] = [n_ff, C] = [8192, 2048]
# When this is written to GGUF with ne=(C, n_ff)=(2048, 8192):
#   If physical layout is [ne[1], ne[0]] = [8192, 2048] = PyTorch's original layout
#   Then physical.T = [2048, 8192] is what we need for x @ W
#
# This is CONSISTENT WITH interpretation A!
print("\n=== CONCLUSION ===")
print("GGML convention: ne[0] = INNERMOST/FASTEST dimension")
print("For ne=(2048, 8192): physical flat layout is [8192, 2048]")
print("  = [output_dim, input_dim] = PyTorch nn.Linear weight convention")
print("For matmul y = x @ W: need W as [input_dim, output_dim]")
print("  = physical.T = flat.reshape(ne[1], ne[0]).T")
print()
print("For embedding ne=(2048, 65536):")
print("  Physical: [65536, 2048] = [vocab, embed_dim]")
print("  Lookup: physical[token_id] = flat[token_id * 2048 : (token_id+1) * 2048]")
print("  = flat.reshape(65536, 2048) -- CORRECT for A")
print()
print("For output head ne=(2048, 65536):")
print("  Physical: [65536, 2048] = [vocab, embed_dim]")
print("  logits = x @ physical.T  where physical.T = [2048, 65536]")
print("  = flat.reshape(65536, 2048).T")
