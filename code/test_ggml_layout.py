"""Diagnostic: Compare GGML tensor layout between Python and what Rust needs.

This answers the key question: when Python does `data.reshape(ne[0], ne[1])`,
what shape does the resulting tensor have, and does `x @ tensor` produce
the correct output?

We'll compare a specific non-square weight matrix (channel_mix_key) to
understand the exact mapping.
"""
import sys
import os
import numpy as np

sys.path.insert(0, r"F:\Sandbox\failure_factory\akashic_v2")
FAIRY_DIR = r"F:\Sandbox\failure_factory\akashic_v2\fairies\P30_Cognition\AkashicInferenceFairy"
sys.path.insert(0, FAIRY_DIR)

GGUF_PATH = os.path.join(FAIRY_DIR, "models", "rwkv7-official-1.5B-Q8_0.gguf")

from gguf_parser import GGUFParser, GGUFFile
from quantization import dequantize_tensor

# Parse GGUF
parser = GGUFParser()
gguf = parser.parse(GGUF_PATH)

# Pick a non-square tensor to diagnose layout
name = "blk.0.channel_mix_key.weight"
info = gguf.tensors[name]
print(f"\n=== {name} ===")
print(f"GGUF shape (ne[0], ne[1]): {info.shape}")
print(f"n_elements: {info.n_elements}")
print(f"type: {info.type_name}")

# Read raw data
raw = gguf.get_tensor_data(name)
print(f"Raw bytes: {len(raw)}")

# Dequantize to flat f32
flat = dequantize_tensor(raw, info.type_id, info.shape, to_torch=False)
print(f"Dequantized numpy shape: {flat.shape}")
print(f"Dequantized flat shape would be: ({info.n_elements},)")

# Also get the flat array before reshape
from quantization import dequantize_q8_0
flat_raw = dequantize_q8_0(raw, (info.n_elements,))  # Force 1D
print(f"Flat raw shape: {flat_raw.shape}")

# Show how Python reshapes it
reshaped = flat_raw.reshape(info.shape)
print(f"\nPython reshape({info.shape}): {reshaped.shape}")
print(f"  This means {reshaped.shape[0]} rows x {reshaped.shape[1]} cols")
print(f"  tensor[0, :5] = {reshaped[0, :5]}")
print(f"  tensor[:5, 0] = {reshaped[:5, 0]}")

# Now test: for channel_mix_key, Python does xk @ key
# If key shape is (2048, 8192), then xk @ key needs xk to be [..., 2048]
# and produces [..., 8192].
# In RWKV, the channel mix key projects from C=2048 to 4C=8192.
# So we need: xk [C] @ key [C, 4C] -> k [4C]
# This means key should be [2048, 8192] = [C, 4C]
print(f"\nFor `xk @ key` where xk is [C=2048]:")
print(f"  We need key to be [C=2048, 4C=8192]")
print(f"  Python's reshaped shape: {reshaped.shape}")

if reshaped.shape == (2048, 8192):
    print(f"  OK: Shape matches! Python can do xk @ key directly.")
elif reshaped.shape == (8192, 2048):
    print(f"  WRONG: Shape is transposed. Python would need key.T.")
else:
    print(f"  UNKNOWN: Unexpected shape.")

# Verify: does the Python model actually work with this shape?
# Test with a random input vector
x_test = np.random.randn(2048).astype(np.float32)
try:
    result = x_test @ reshaped
    print(f"  x @ reshaped: output shape = {result.shape}")
    print(f"  Output looks like: {result[:5]}")
except ValueError as e:
    print(f"  x @ reshaped FAILED: {e}")
    try:
        result = x_test @ reshaped.T
        print(f"  x @ reshaped.T: output shape = {result.shape}")
    except:
        pass

# Now check what Rust gets:
# Rust dequantizes to flat array (same as flat_raw), then calls set_tensor
# WITHOUT reshape. The flat data is stored as Vec<f32>.
# matmul_vec(x, M, y, k=2048, n=8192) treats M as [2048, 8192] row-major:
#   M[i, j] = M_flat[i * 8192 + j]
# But the GGML flat data has:
#   flat[i1 * ne[0] + i0]  (IF ne[0] is fast dim)
# OR:
#   flat[i0 * ne[1] + i1]  (IF ne[0] is slow dim and standard row-major)

# Let's test both interpretations with a simple probe
# If ne[0]=2048 is the FAST dim (GGML convention), data is stored as:
#   flat[i1 * 2048 + i0] where i0 ∈ [0, 2048), i1 ∈ [0, 8192)
#   = [8192 rows of 2048 elements]
# numpy reshape((2048, 8192)) interprets as [2048 rows of 8192 elements]
# These are DIFFERENT layouts — reshape does NOT correspond to the GGML layout.

# But there's another possibility: GGUF might store ne[0] as the FIRST (outermost)
# dimension, not the innermost. Let me check by looking at the actual data pattern.

print(f"\n=== Layout probe ===")
print(f"flat_raw[:5] = {flat_raw[:5]}")
print(f"flat_raw[2048:2053] = {flat_raw[2048:2053]}")

# If ne[0]=2048 is the fast dim, then flat_raw[0:2048] is column 0 of a [8192, 2048] matrix
# If ne[0]=2048 is the slow dim (standard row-major), then flat_raw[0:2048] is row 0 of a [2048, 8192] matrix
# The reshape will be correct in the second case, wrong in the first.

# Let's use a definitive test: compare with another tensor that has a known structure
# token_embd.weight should have recognizable patterns
emb_name = "token_embd.weight"
emb_info = gguf.tensors[emb_name]
print(f"\n=== {emb_name} ===")
print(f"GGUF shape: {emb_info.shape}")
# For embedding, shape is typically (vocab_size, embd_dim) or (embd_dim, vocab_size)
# If we look up token 0's embedding, it should be a continuous slice

emb_raw = gguf.get_tensor_data(emb_name)
emb_flat = dequantize_q8_0(emb_raw, (emb_info.n_elements,))

emb_ne0, emb_ne1 = emb_info.shape
print(f"ne[0]={emb_ne0}, ne[1]={emb_ne1}")
print(f"Total elements: {emb_flat.shape[0]}")

# Interpretation 1: ne[0] is fast dim (GGML standard)
# Token 0's embedding = flat_raw[0:ne[0]] = flat_raw[0:2048] (first ne[0] elements)
# This is emb[i0=0..2047, i1=0]... that's a column, not a row!
# Token 0's full embedding in this interp would need gathering:
# emb[0, :] = flat[i1*ne[0] + 0] for i1 in range(ne[1])... scattered every ne[0] elements

# Interpretation 2: ne[0] is slow dim (row-major)
# Token 0's embedding = flat_raw[0:ne[1]] = flat_raw[0:65536]... that's the whole vocab!
# That can't be right either.

# Actually for embedding with ne[0]=2048, ne[1]=65536:
# Interpretation 1 (GGML: ne[0] fast): emb_shape = [65536, 2048] physically
#   Token t's embedding = flat[t*2048 : (t+1)*2048]
# Interpretation 2 (row-major: ne[0] is rows): emb_shape = [2048, 65536] physically
#   Token t's embedding = flat[t::2048]... scattered. Makes no sense.

# Let's check by looking at the rwkv_model.py embedding usage:
# Line 170-176: if emb.size(0) < emb.size(1): self.emb = emb.T.contiguous()
# After reshape((2048, 65536)), emb.size(0)=2048 < emb.size(1)=65536, so Python TRANSPOSES!
# This means Python recognizes that reshape((ne[0], ne[1])) gives the WRONG shape for embeddings.

# After transpose: emb becomes [65536, 2048] — token lookup via emb[token_id] gives [2048] vector.
# So the physical GGML layout IS [65536 rows of 2048 = V rows of C], matching Interpretation 1.

# For weight matrices, Python does xk @ key with key reshaped to (2048, 8192).
# The physical data is actually [8192, 2048] in GGML (Interpretation 1).
# numpy reshape((2048, 8192)) reinterprets [8192*2048 flat] as [2048 rows, 8192 cols].
# This is NOT a proper transpose — it's a REINTERPRETATION of the flat data.

# The question is: does this reinterpretation happen to be equivalent to a transpose?
# For a matrix A stored as [R rows, C cols] row-major:
#   A[r, c] = flat[r * C + c]
# Transpose B = A^T has shape [C, R]:
#   B[c, r] = A[r, c] = flat[r * C + c]
# numpy reshape gives:
#   reshaped[i, j] = flat[i * ne[1] + j] = flat[i * 8192 + j]
# For GGML data stored as [ne[1]=8192 rows, ne[0]=2048 cols]:
#   GGML_matrix[i1, i0] = flat[i1 * 2048 + i0]
# The transpose would be [2048, 8192]:
#   transposed[i0, i1] = GGML_matrix[i1, i0] = flat[i1 * 2048 + i0]
# But reshaped[i, j] = flat[i * 8192 + j]
# For reshaped to equal transposed: i * 8192 + j == i1 * 2048 + i0
# where i0 = i, i1 = j... so i * 8192 + j vs j * 2048 + i
# These are DIFFERENT unless ne[0] == ne[1] (square matrices)!

print(f"\n=== CRITICAL CONCLUSION ===")
print(f"numpy reshape((ne[0], ne[1])) is NOT a proper transpose of GGML data for non-square matrices!")
print(f"Python embedding code confirms this — it transposes after reshape.")
print(f"So Python's weight matrices ARE garbled by reshape... unless the GGML convention")
print(f"actually stores data in standard row-major order (ne[0] = rows, ne[1] = cols).")
print()
print(f"Let's do the DEFINITIVE test: check embedding token 0")

# If GGML stores [V, C] physically (ne[0]=C is fast dim):
#   Token 0 embedding = flat[0:C] = flat[0:2048]
# If GGML stores [C, V] physically (standard row-major):
#   Token 0 embedding is NOT contiguous

emb_option1 = emb_flat[0:2048]  # GGML fast-dim convention
print(f"Option 1 (ne[0] fast, token 0 = first 2048): mean={emb_option1.mean():.6f}, std={emb_option1.std():.6f}")

# For option 2, token 0 is scattered
emb_reshape = emb_flat.reshape(2048, 65536)
emb_option2 = emb_reshape[:, 0]  # Column 0 = token 0 in row-major
print(f"Option 2 (row-major, token 0 = column 0): mean={emb_option2.mean():.6f}, std={emb_option2.std():.6f}")

# Check: variance should be reasonable for a real embedding
# One of these will look like a proper embedding vector, the other won't
print(f"\nOption 1 values: {emb_option1[:8]}")
print(f"Option 2 values: {emb_option2[:8]}")

# Also check: Python transposes embedding to [65536, 2048] and uses emb[token_id]
# which is the same as emb_flat.reshape(2048, 65536).T[token_id]
# = emb_flat.reshape(2048, 65536).T[0] for token 0
# = emb_flat.reshape(2048, 65536)[:, 0]  = Option 2!
# But this is the TRANSPOSED version. Python's code says:
#   emb = tensor.reshape(ne[0], ne[1])  # (2048, 65536)
#   if emb.size(0) < emb.size(1): emb = emb.T  # becomes (65536, 2048)
#   emb[0] = emb[0, :] = 2048 values = the first ROW of transposed matrix
# Let's see what emb.T[0] gives us:
emb_transposed = emb_reshape.T  # (65536, 2048)
print(f"\nPython's emb.T[0] (token 0 after Python's transpose):")
print(f"  values: {emb_transposed[0, :8]}")
print(f"  mean={emb_transposed[0].mean():.6f}, std={emb_transposed[0].std():.6f}")

# Compare with Rust's approach:
# Rust stores embedding flat. For token lookup: emb[token_id * C .. (token_id+1) * C]
# This gets flat[0:2048] for token 0 = Option 1
print(f"\nRust flat[0:2048] (token 0 via flat slice):")
print(f"  values: {emb_flat[:8]}")
print(f"  mean={emb_flat[:2048].mean():.6f}, std={emb_flat[:2048].std():.6f}")

# If Option 1 == Python's emb.T[0], then GGML stores ne[0] as fast dim
# and the flat data layout is [ne[1] rows, ne[0] cols]
# which means Rust's flat slice is correct for embedding, and
# Python's reshape + transpose is also correct for embedding.
print(f"\n=== Match check ===")
match_1_py = np.allclose(emb_flat[:2048], emb_transposed[0])
match_2_py = np.allclose(emb_option2, emb_transposed[0])
print(f"Rust flat[0:2048] == Python emb.T[0]: {match_1_py}")
print(f"Option 2 (column 0) == Python emb.T[0]: {match_2_py}")

if match_1_py:
    print("\n>>> CONFIRMED: GGML ne[0] IS the fast/contiguous dimension!")
    print(">>> Flat data layout: [ne[1] rows, ne[0] cols] = [V, C] for embedding")
    print(">>> Rust embedding lookup flat[token*C : (token+1)*C] is CORRECT")
    print(">>> Python reshape((ne[0], ne[1])) = reshape((C, V)) is WRONG layout")
    print(">>>   but Python fixes it with .T for embedding")
    print()
    print(">>> For weight matrices: Python does NOT transpose after reshape!")
    print(">>>   reshape((ne[0], ne[1])) on data that's physically [ne[1], ne[0]]")
    print(">>>   This is NOT a proper mathematical transpose for non-square matrices.")
    print(">>>   It's a GARBLED reinterpretation.")
    print()
    print(">>> But wait — does Python's model actually produce correct output?")
    print(">>> If yes, then maybe GGML IS using standard row-major for weight matrices")
    print(">>> and ONLY embedding has the ne[0]=fast-dim convention?")
    print(">>> Or maybe the GGML convention is actually ne[0]=ROWS (standard row-major)")
    print(">>> and embedding is stored as [C, V] = [2048, 65536] where each 'row' of 65536")
    print(">>> is NOT an embedding, which is why Python transposes it.")
elif match_2_py:
    print("\n>>> Standard row-major: ne[0] is rows, ne[1] is cols")
    print(">>> numpy reshape works correctly")
else:
    print("\n>>> Neither interpretation matches — something else is going on")
