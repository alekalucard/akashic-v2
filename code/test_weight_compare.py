"""Compare exact weight values between Python and Rust paths.

This definitively checks whether the weights being used by matmul_vec
in Rust match what Python's `x @ W` would use.
"""
import sys
import os
import numpy as np

sys.path.insert(0, r"F:\Sandbox\failure_factory\akashic_v2")
FAIRY_DIR = r"F:\Sandbox\failure_factory\akashic_v2\fairies\P30_Cognition\AkashicInferenceFairy"
sys.path.insert(0, FAIRY_DIR)

# Add PyTorch lib to PATH for cuBLAS DLLs
try:
    import torch
    torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
    os.environ['PATH'] = torch_lib + ';' + os.environ.get('PATH', '')
except ImportError:
    pass

GGUF_PATH = os.path.join(FAIRY_DIR, "models", "rwkv7-official-1.5B-Q8_0.gguf")

from gguf_parser import GGUFParser, GGUFFile
from quantization import dequantize_tensor

# Parse GGUF with Python
parser = GGUFParser()
gguf = parser.parse(GGUF_PATH)

# Load Rust engine
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

# Now compare specific tensors
# We can probe what Rust has by doing a forward pass and comparing intermediate values.
# But first, let's just verify the embedding is correct.

print("=" * 60)
print("EMBEDDING CHECK")
print("=" * 60)

# Python embedding: reshape((2048, 65536)) then transpose to (65536, 2048)
emb_info = gguf.tensors["token_embd.weight"]
emb_raw = gguf.get_tensor_data("token_embd.weight")
emb_py = dequantize_tensor(emb_raw, emb_info.type_id, emb_info.shape, to_torch=False)
print(f"Python raw reshape shape: {emb_py.shape}")
# Transpose like Python model does
if emb_py.shape[0] < emb_py.shape[1]:
    emb_py = emb_py.T  # [65536, 2048]
print(f"Python after transpose: {emb_py.shape}")

# Test token 0 embedding
token_0_py = emb_py[0]  # [2048]
print(f"Python token 0 emb[:8]: {token_0_py[:8]}")

# Rust: forward token 0 and check if embedding lookup gives same result
# We can't directly probe Rust internals, but we CAN compare forward pass output
result = bridge.forward([0])
logits = np.array(result.get('logits', []))
print(f"Rust forward([0]) logits stats: min={logits.min():.3f} max={logits.max():.3f} std={logits.std():.3f}")

# Now let's do a MORE targeted comparison:
# Run forward with token 0 in BOTH Python and Rust, compare logits
# For Python, we need to set up a minimal forward pass

# Actually, let's compare the weight matrices directly.
# We know Python's `x @ key` uses the reshaped (2048, 8192) tensor.
# Rust's matmul_vec uses the flat data directly.
# If GGUF ne[0]=rows, ne[1]=cols (standard row-major),
# then flat data IS [2048 rows, 8192 cols] = [k=2048, n=8192]
# and matmul_vec(x, M, y, k=2048, n=8192) should work.

# Let's verify by computing x @ key manually in Python using the flat data,
# and compare with numpy's reshape version.

print("\n" + "=" * 60)
print("MATMUL CHECK: channel_mix_key.weight")
print("=" * 60)

name = "blk.0.channel_mix_key.weight"
info_cm = gguf.tensors[name]
raw_cm = gguf.get_tensor_data(name)

# Python's way: reshape to (ne[0], ne[1]) = (2048, 8192)
key_py = dequantize_tensor(raw_cm, info_cm.type_id, info_cm.shape, to_torch=False)
print(f"Python key shape: {key_py.shape}")

# Flat data (what Rust sees)
from quantization import dequantize_q8_0
key_flat = dequantize_q8_0(raw_cm, (info_cm.n_elements,))
print(f"Flat key length: {key_flat.shape}")

# Random test input
np.random.seed(42)
x_test = np.random.randn(2048).astype(np.float32)

# Python's matmul: x @ key_py
result_py = x_test @ key_py
print(f"\nPython x @ key: shape={result_py.shape}")
print(f"  values[:5] = {result_py[:5]}")

# Simulate Rust's matmul_vec: y[j] = sum_i(x[i] * M[i * n + j])
# where M is key_flat, k=2048, n=8192
k, n = 2048, 8192
result_rust = np.zeros(n, dtype=np.float32)
for j in range(n):
    s = 0.0
    for i in range(k):
        s += x_test[i] * key_flat[i * n + j]
    result_rust[j] = s
print(f"\nRust matmul_vec: shape=({n},)")
print(f"  values[:5] = {result_rust[:5]}")

# Compare
diff = np.abs(result_py - result_rust)
print(f"\nDifference: max={diff.max():.8f} mean={diff.mean():.8f}")
if diff.max() < 1e-3:
    print("MATCH! Python and Rust matmul produce same output.")
else:
    print("MISMATCH! Something is wrong with the layout.")
    # Check if maybe Rust's flat data interpreted differently gives a match
    # Try interpreting as [n=8192, k=2048] (transposed)
    result_rust_t = np.zeros(n, dtype=np.float32)
    for j in range(n):
        s = 0.0
        for i in range(k):
            s += x_test[i] * key_flat[j * k + i]  # transposed indexing
        result_rust_t[j] = s
    diff_t = np.abs(result_py - result_rust_t)
    print(f"  With transposed indexing: max diff={diff_t.max():.8f}")
    if diff_t.max() < 1e-3:
        print("  TRANSPOSED matches! Need to transpose weight matrices.")

print("\n" + "=" * 60)
print("MATMUL CHECK: time_mix_receptance.weight (square)")
print("=" * 60)

name = "blk.0.time_mix_receptance.weight"
info_r = gguf.tensors[name]
raw_r = gguf.get_tensor_data(name)

rec_py = dequantize_tensor(raw_r, info_r.type_id, info_r.shape, to_torch=False)
rec_flat = dequantize_q8_0(raw_r, (info_r.n_elements,))

print(f"Python rec shape: {rec_py.shape}")

result_py2 = x_test @ rec_py
k2 = 2048
result_rust2 = np.zeros(k2, dtype=np.float32)
for j in range(k2):
    s = 0.0
    for i in range(k2):
        s += x_test[i] * rec_flat[i * k2 + j]
    result_rust2[j] = s

diff2 = np.abs(result_py2 - result_rust2)
print(f"Python x @ rec: values[:5] = {result_py2[:5]}")
print(f"Rust matmul_vec: values[:5] = {result_rust2[:5]}")
print(f"Difference: max={diff2.max():.8f} mean={diff2.mean():.8f}")
if diff2.max() < 1e-3:
    print("MATCH for square matrix too!")
else:
    print("MISMATCH for square matrix.")
