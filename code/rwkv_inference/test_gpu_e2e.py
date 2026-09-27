"""
End-to-end GPU acceleration test for RWKV-7 inference kernel.

Tests:
1. GPU detection and cuBLAS initialization
2. Weight upload to VRAM
3. GPU-accelerated forward pass
4. GPU generation benchmark
"""
import os, sys, time, gc

# === Step 0: Set up CUDA DLL path ===
try:
    import torch
    torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
    os.environ['PATH'] = torch_lib + ';' + os.environ.get('PATH', '')
    print(f"[Setup] Added torch lib to PATH: {torch_lib}")
except ImportError:
    print("[Setup] PyTorch not found, CUDA DLLs may not be available")

# Add project root to path for imports
PROJECT_ROOT = r"F:\Sandbox\failure_factory\akashic_v2"
sys.path.insert(0, PROJECT_ROOT)

print(f"\n{'='*60}")
print(f"=== GPU END-TO-END TEST ===")
print(f"{'='*60}")
print(f"Time: {time.strftime('%H:%M:%S')}\n")

# === Step 1: Import and GPU detection ===
print("--- Step 1: Import rwkv_inference ---")
import rwkv_inference
from rwkv_inference import RWKVEngine
import numpy as np

# === Step 2: Load GGUF and create engine with correct dimensions ===
print("\n--- Step 2: Load GGUF + create engine ---")
GGUF_PATH = os.path.join(
    PROJECT_ROOT,
    "fairies", "P30_Cognition", "AkashicInferenceFairy", "models",
    "rwkv7-official-1.5B-Q8_0.gguf"
)

if not os.path.exists(GGUF_PATH):
    print(f"ERROR: GGUF file not found: {GGUF_PATH}")
    sys.exit(1)

print(f"GGUF: {GGUF_PATH}")
print(f"Size: {os.path.getsize(GGUF_PATH) / (1024*1024):.1f} MB")

from fairies.P30_Cognition.AkashicInferenceFairy.model_tensor_fabric import ModelTensorFabric

fabric = ModelTensorFabric(
    device="cpu",
    dtype="float16",
    max_memory_gb=12.0,
    lazy_load=True,
)
fabric.load_gguf(GGUF_PATH)

# Probe embedding to get actual vocab size
emb_probe = fabric.get("token_embd.weight")
vocab_size = 65536  # default
if emb_probe is not None and emb_probe.dim() == 2:
    vocab_size = max(emb_probe.size(0), emb_probe.size(1))
    print(f"Inferred vocab_size={vocab_size} from embedding {tuple(emb_probe.shape)}")
del emb_probe

# Create engine with correct dimensions
engine = RWKVEngine(
    n_layer=24,
    n_embd=2048,
    n_head=32,
    vocab_size=vocab_size,
)
print(f"Engine: {engine}")
gpu_status = engine.gpu_status()
print(f"GPU status: {gpu_status}")

if "not available" in gpu_status.lower() or "cpu" in gpu_status.lower():
    print("\n*** WARNING: GPU NOT AVAILABLE — test will use CPU fallback ***\n")

# === Step 3: Transfer weights ===
print("\n--- Step 3: Transfer weights to Rust + GPU ---")
t_load_start = time.perf_counter()
tensor_count = 0
total_params = 0

def to_f32_numpy(tensor, name):
    """Convert tensor to contiguous flat f32 numpy array (same as RustBridge)."""
    return tensor.detach().float().cpu().contiguous().flatten().numpy()

# Global weights
for name in [
    "token_embd.weight", "token_embd_norm.weight", "token_embd_norm.bias",
    "output.weight", "output_norm.weight", "output_norm.bias",
]:
    tensor = fabric.get(name)
    if tensor is not None:
        if name == "token_embd.weight" and tensor.dim() == 2 and tensor.size(0) < tensor.size(1):
            tensor = tensor.T.contiguous()
            print(f"Transposed {name}: now {tuple(tensor.shape)}")
        arr = to_f32_numpy(tensor, name)
        engine.load_weight_numpy(name, arr)
        tensor_count += 1
        total_params += arr.size
        del arr, tensor

# Per-layer weights
layer_components = [
    "attn_norm.weight", "attn_norm.bias",
    "attn_norm_2.weight", "attn_norm_2.bias",
    "ffn_norm.weight", "ffn_norm.bias",
    "time_mix_receptance.weight", "time_mix_key.weight",
    "time_mix_value.weight", "time_mix_output.weight",
    "time_mix_w0.weight", "time_mix_w1.weight", "time_mix_w2.weight",
    "time_mix_decay.weight", "time_mix_decay_w1.weight", "time_mix_decay_w2.weight",
    "time_mix_a0.weight", "time_mix_a1.weight", "time_mix_a2.weight",
    "time_mix_v0.weight", "time_mix_v1.weight", "time_mix_v2.weight",
    "time_mix_g1.weight", "time_mix_g2.weight",
    "time_mix_k_k.weight", "time_mix_k_a.weight", "time_mix_r_k.weight",
    "time_mix_ln.weight", "time_mix_ln.bias",
    "time_mix_lerp_fused.weight", "time_mix_x_maa.weight",
    "channel_mix_key.weight", "channel_mix_value.weight",
    "channel_mix_lerp_k.weight", "channel_mix_x_maa.weight",
]

for layer_id in range(24):
    layer_start = time.perf_counter()
    layer_tensors = 0
    for component in layer_components:
        name = f"blk.{layer_id}.{component}"
        tensor = fabric.get(name)
        if tensor is not None:
            arr = to_f32_numpy(tensor, name)
            engine.load_weight_numpy(name, arr)
            tensor_count += 1
            total_params += arr.size
            layer_tensors += 1
            del arr, tensor
    gc.collect()
    layer_ms = (time.perf_counter() - layer_start) * 1000
    if layer_id % 6 == 0 or layer_id == 23:
        print(f"Layer {layer_id}: {layer_tensors} tensors in {layer_ms:.0f}ms")

# Finalize — this also uploads to GPU
engine.finalize_weights()
t_load = time.perf_counter() - t_load_start
param_m = total_params / 1e6
print(f"Loaded {tensor_count} tensors ({param_m:.1f}M params) in {t_load:.1f}s")
print(f"GPU status after finalize: {engine.gpu_status()}")

# Free fabric
del fabric
gc.collect()

# === Step 4: Forward pass test ===
print(f"\n--- Step 4: Forward pass ---")
# Warmup
engine.forward([0])

# Timed forward pass
t0 = time.perf_counter()
result = engine.forward([1])
t_fwd = (time.perf_counter() - t0) * 1000

logits = result["logits"]
print(f"Forward: {t_fwd:.1f}ms, logits={len(logits)}")
print(f"Logits: min={min(logits):.3f} max={max(logits):.3f} mean={np.mean(logits):.5f} std={np.std(logits):.3f}")
top_idx = np.argsort(logits)[-5:][::-1]
top_vals = [logits[i] for i in top_idx]
print(f"Top-5: tokens={list(top_idx)} logits={[f'{v:.2f}' for v in top_vals]}")

# === Step 5: Generation benchmark (30 tokens) ===
print(f"\n--- Step 5: Generation benchmark (30 tokens) ---")
engine.reset_state()

# Feed prompt
t0 = time.perf_counter()
result_gen30 = engine.generate([0, 1, 2, 3, 4], max_tokens=30, temperature=1.0, top_p=0.9)
t_gen30 = time.perf_counter() - t0
gen_30 = result_gen30["tokens"]
tps_30 = len(gen_30) / t_gen30
print(f"Generated {len(gen_30)} tokens in {t_gen30:.1f}s ({tps_30:.1f} tok/s)")
print(f"Tokens: {gen_30[:10]}...")

# === Step 6: Generation benchmark (50 tokens) ===
print(f"\n--- Step 6: Generation benchmark (50 tokens) ---")
engine.reset_state()

t0 = time.perf_counter()
result_gen50 = engine.generate([0, 1, 2, 3, 4], max_tokens=50, temperature=1.0, top_p=0.9)
t_gen50 = time.perf_counter() - t0
gen_50 = result_gen50["tokens"]
tps_50 = len(gen_50) / t_gen50
print(f"Generated {len(gen_50)} tokens in {t_gen50:.1f}s ({tps_50:.1f} tok/s)")

# === Step 7: Metrics ===
print(f"\n--- Step 7: Metrics ---")
metrics = engine.get_metrics()
print(f"Metrics: {metrics}")

# === Summary ===
print(f"\n{'='*60}")
print(f"  GPU ACCELERATION TEST SUMMARY")
print(f"{'='*60}")
print(f"  GPU status:      {engine.gpu_status()}")
print(f"  Forward pass:    {t_fwd:.1f}ms")
print(f"  Gen 30 tokens:   {tps_30:.1f} tok/s")
print(f"  Gen 50 tokens:   {tps_50:.1f} tok/s")
print(f"  CPU baseline:    2.4 tok/s")
print(f"  Speedup:         {tps_50/2.4:.1f}x")
print(f"{'='*60}")
print(f"Complete at {time.strftime('%H:%M:%S')}")
