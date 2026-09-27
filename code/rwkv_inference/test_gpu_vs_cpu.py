"""
GPU vs CPU A/B comparison test.
Runs forward_cpu() and forward() (GPU) on the same token and compares debug output.
"""
import os, sys, time, gc
import torch
import numpy as np

torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
os.environ['PATH'] = torch_lib + ';' + os.environ.get('PATH', '')

PROJECT_ROOT = r"F:\Sandbox\failure_factory\akashic_v2"
sys.path.insert(0, PROJECT_ROOT)

from rwkv_inference import RWKVEngine
from fairies.P30_Cognition.AkashicInferenceFairy.model_tensor_fabric import ModelTensorFabric

GGUF_PATH = os.path.join(
    PROJECT_ROOT,
    "fairies", "P30_Cognition", "AkashicInferenceFairy", "models",
    "rwkv7-official-1.5B-Q8_0.gguf"
)

print("=== GPU vs CPU COMPARISON TEST ===")

# Load fabric
fabric = ModelTensorFabric(device="cpu", dtype="float16", max_memory_gb=12.0, lazy_load=True)
fabric.load_gguf(GGUF_PATH)

# Probe vocab size
emb_probe = fabric.get("token_embd.weight")
vocab_size = max(emb_probe.size(0), emb_probe.size(1))
del emb_probe
print(f"vocab_size={vocab_size}")

# Create engine
engine = RWKVEngine(n_layer=24, n_embd=2048, n_head=32, vocab_size=vocab_size)
print(f"GPU: {engine.gpu_status()}")

def to_f32_numpy(tensor, name):
    return tensor.detach().float().cpu().contiguous().flatten().numpy()

# Load weights
for name in [
    "token_embd.weight", "token_embd_norm.weight", "token_embd_norm.bias",
    "output.weight", "output_norm.weight", "output_norm.bias",
]:
    tensor = fabric.get(name)
    if tensor is not None:
        if name == "token_embd.weight" and tensor.dim() == 2 and tensor.size(0) < tensor.size(1):
            tensor = tensor.T.contiguous()
        arr = to_f32_numpy(tensor, name)
        engine.load_weight_numpy(name, arr)
        del arr, tensor

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
    for component in layer_components:
        name = f"blk.{layer_id}.{component}"
        tensor = fabric.get(name)
        if tensor is not None:
            arr = to_f32_numpy(tensor, name)
            engine.load_weight_numpy(name, arr)
            del arr, tensor
    gc.collect()
    if layer_id % 12 == 0 or layer_id == 23:
        print(f"Layer {layer_id} loaded")

engine.finalize_weights()
del fabric
gc.collect()

# Test token
TOKEN = 1

# --- Run 1: CPU forward ---
print("\n" + "="*60)
print("=== CPU FORWARD (token={}) ===".format(TOKEN))
print("="*60)
engine.reset_state()
result_cpu = engine.forward_cpu([TOKEN])
logits_cpu = result_cpu["logits"]
print(f"\nCPU logits: min={min(logits_cpu):.3f} max={max(logits_cpu):.3f} std={np.std(logits_cpu):.3f}")

# --- Run 2: GPU forward ---
print("\n" + "="*60)
print("=== GPU FORWARD (token={}) ===".format(TOKEN))
print("="*60)
engine.reset_state()
result_gpu = engine.forward([TOKEN])
logits_gpu = result_gpu["logits"]
print(f"\nGPU logits: min={min(logits_gpu):.3f} max={max(logits_gpu):.3f} std={np.std(logits_gpu):.3f}")

# --- Compare ---
print("\n" + "="*60)
print("=== COMPARISON ===")
print("="*60)
logits_cpu = np.array(logits_cpu)
logits_gpu = np.array(logits_gpu)
diff = np.abs(logits_gpu - logits_cpu)
ratio = np.std(logits_gpu) / max(np.std(logits_cpu), 1e-12)
print(f"Logits diff: max={diff.max():.3f} mean={diff.mean():.3f}")
print(f"Magnitude ratio (GPU/CPU std): {ratio:.2f}x")

# Check top-5 predictions
cpu_top5 = np.argsort(logits_cpu)[-5:][::-1]
gpu_top5 = np.argsort(logits_gpu)[-5:][::-1]
print(f"CPU top-5 tokens: {list(cpu_top5)}")
print(f"GPU top-5 tokens: {list(gpu_top5)}")
print(f"Top-5 match: {set(cpu_top5) == set(gpu_top5)}")

print("\n=== DONE ===")
