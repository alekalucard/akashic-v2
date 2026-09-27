"""
GPU vs CPU correctness comparison.
Compare sgemv output on a single layer to find the numerical issue.
"""
import os, sys, time, gc
import torch
import numpy as np

torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
os.environ['PATH'] = torch_lib + ';' + os.environ.get('PATH', '')

PROJECT_ROOT = r"F:\Sandbox\failure_factory\akashic_v2"
sys.path.insert(0, PROJECT_ROOT)

from rwkv_inference import RWKVEngine

GGUF_PATH = os.path.join(
    PROJECT_ROOT,
    "fairies", "P30_Cognition", "AkashicInferenceFairy", "models",
    "rwkv7-official-1.5B-Q8_0.gguf"
)

from fairies.P30_Cognition.AkashicInferenceFairy.model_tensor_fabric import ModelTensorFabric

print("=== GPU vs CPU CORRECTNESS TEST ===")

# Load fabric
fabric = ModelTensorFabric(device="cpu", dtype="float16", max_memory_gb=12.0, lazy_load=True)
fabric.load_gguf(GGUF_PATH)

# Create two engines - but we can only have one GPU engine...
# Instead, let's just run the same engine and compare the logits
# between forward (GPU) and check against a manual CPU calculation

# Create engine
emb_probe = fabric.get("token_embd.weight")
vocab_size = max(emb_probe.size(0), emb_probe.size(1))
del emb_probe

engine = RWKVEngine(n_layer=24, n_embd=2048, n_head=32, vocab_size=vocab_size)
print(f"GPU: {engine.gpu_status()}")

# Quick check: what does the CPU forward give us?
# Build a CPU-only engine by rebuilding without CUDA
# Actually we can't do that easily. Let's instead look at what the GPU
# does with a simple known vector.

# Let's manually extract a weight matrix and multiply on CPU, then compare with GPU
print("\n--- Manual CPU matmul vs GPU sgemv for Receptance layer 0 ---")

# Get the weight matrix from the fabric
R_weight = fabric.get("blk.0.time_mix_receptance.weight")
print(f"R_weight shape: {R_weight.shape}, dtype: {R_weight.dtype}")

R_f32 = R_weight.detach().float().numpy()
print(f"R_f32 shape: {R_f32.shape}")
print(f"R_f32 range: [{R_f32.min():.6f}, {R_f32.max():.6f}]")
print(f"R_f32 mean: {R_f32.mean():.6f}, std: {R_f32.std():.6f}")

# Create a simple input vector
x = np.random.randn(2048).astype(np.float32) * 0.1  # Small input

# CPU matmul: y = x @ M (x is [K], M is [K, N] row-major, y is [N])
# M is stored as flat [K*N] in Rust. The GGUF weight is 2D.
# How is it stored in Rust? As flat row-major.
R_flat = R_f32.flatten()
print(f"R_flat length: {len(R_flat)}")

# CPU: y[j] = sum_i(x[i] * M[i*N + j])
K, N = R_f32.shape
print(f"Matrix dims: K={K}, N={N}")

# Manual CPU matmul
y_cpu = np.zeros(N, dtype=np.float32)
for i in range(K):
    y_cpu += x[i] * R_f32[i, :]

print(f"\nCPU matmul result:")
print(f"  y_cpu range: [{y_cpu.min():.6f}, {y_cpu.max():.6f}]")
print(f"  y_cpu mean: {y_cpu.mean():.6f}, std: {y_cpu.std():.6f}")

# Also compute using numpy matmul for verification
y_np = x @ R_f32
print(f"\nNumpy @ result:")
print(f"  y_np range: [{y_np.min():.6f}, {y_np.max():.6f}]")
print(f"  y_np mean: {y_np.mean():.6f}, std: {y_np.std():.6f}")

# Check: does x @ R agree with manual?
diff = np.max(np.abs(y_cpu - y_np))
print(f"  CPU manual vs numpy diff: {diff:.8f}")

# Now the question is: what does the GPU sgemv get?
# We need to understand the weight storage.
# In Rust, the weight is stored as a flat Vec<f32> from R_flat.
# R_flat = R_f32.flatten() which for a [K, N] matrix gives row-major [K*N].
# The GPU sgemv treats it as col-major A[N, K] and does A^T * x.
# Col-major A[N, K] has A[col, row] = data[col + row*N] = row-major M[row, col].
# So they should agree!

# But wait - what if the original weight is [N, K] instead of [K, N]?
# In GGUF, the R_weight might be [output_dim, input_dim] = [2048, 2048] for square,
# but for rectangular matrices like ChannelMix key [C, 4C], the orientation matters.

# Let's check the ChannelMix key weight
CM_key = fabric.get("blk.0.channel_mix_key.weight")
print(f"\n--- ChannelMix Key weight ---")
print(f"Shape: {CM_key.shape}, dtype: {CM_key.dtype}")
# Is it [C, 4C] = [2048, 8192] or [4C, C] = [8192, 2048]?
# The CPU code does: matmul_vec(xk, cm_key, out, C, 4C)
# meaning x is [C], M is [C, 4C], y is [4C]

# Check the output.weight (head)
head_weight = fabric.get("output.weight")
print(f"\n--- Head weight ---")
print(f"Shape: {head_weight.shape}, dtype: {head_weight.dtype}")
# CPU does: matmul_vec(x, head, logits, C, V)
# x is [C=2048], M is [C, V=65536], y is [V]
# So head should be [2048, 65536]

# If head is [65536, 2048], then CPU is using it wrong direction
# and GPU would be wrong too, or vice versa.

# Let's test: what happens if we do x @ head.T vs x @ head?
head_f32 = head_weight.detach().float().numpy()
print(f"Head f32 shape: {head_f32.shape}")

if head_f32.shape[0] == 2048:
    print("Head is [C, V] = [2048, 65536] — correct for y = x @ M")
elif head_f32.shape[0] == 65536:
    print("Head is [V, C] = [65536, 2048] — TRANSPOSED! CPU matmul_vec would be wrong")
    print("  CPU treats flat data as [K=2048, N=65536] row-major")
    print("  But actual data is [65536, 2048] row-major")
    print("  So CPU reads row 0 of [65536, 2048] as the first 65536 floats")
    print("  when it should be reading columns of the first 2048 rows")

print("\n=== DONE ===")
