"""Test the Python RWKV model directly (via rwkv_model.py + rwkv_layers.py).

This runs the ACTUAL Python reference model to check if IT produces correct output.
If it does, then the reshape interpretation is correct and the issue is in our
numpy/Rust implementation. If it also gives garbage, the GGUF file or loader is wrong.
"""
import sys
import os
import numpy as np
import time

sys.path.insert(0, r"F:\Sandbox\failure_factory\akashic_v2")
FAIRY_DIR = r"F:\Sandbox\failure_factory\akashic_v2\fairies\P30_Cognition\AkashicInferenceFairy"
sys.path.insert(0, FAIRY_DIR)

# Need PyTorch
import torch
torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
os.environ['PATH'] = torch_lib + ';' + os.environ.get('PATH', '')

GGUF_PATH = os.path.join(FAIRY_DIR, "models", "rwkv7-official-1.5B-Q8_0.gguf")

# Load the model using the Python model classes
from gguf_parser import GGUFParser, get_model_info
from model_tensor_fabric import ModelTensorFabric
from rwkv_model import RWKVModel
from rwkv_layers import RWKVConfig

# Get model info
info = get_model_info(GGUF_PATH)
print(f"Model info: {info}")

config = RWKVConfig(
    n_layer=info.get('n_layer', 24),
    n_embd=info.get('n_embd', 2048),
    n_head=info.get('n_head', 32),
    head_size=info.get('n_embd', 2048) // max(info.get('n_head', 32), 1),
    vocab_size=info.get('vocab_size', 65536),
)
print(f"Config: layers={config.n_layer} embd={config.n_embd} head={config.n_head} hs={config.head_size} vocab={config.vocab_size}")

# Create fabric and load GGUF
print("\nLoading model via Python fabric...")
t0 = time.time()

# Parse GGUF
parser = GGUFParser()
gguf = parser.parse(GGUF_PATH)

# Create fabric with CPU for testing
fabric = ModelTensorFabric(
    device='cpu',
    dtype='float32',
    lazy_load=True,
    max_memory_gb=16.0,
    use_portal=False,
)
fabric.load_gguf(GGUF_PATH)

# Build model
model = RWKVModel(config, fabric=fabric)
print(f"Model loaded in {time.time()-t0:.1f}s")

# Forward pass for token "The" (6699)
token_id = 6699
print(f"\nForward pass for token {token_id} using Python model")

input_ids = torch.tensor([[token_id]])  # [1, 1]
t0 = time.time()

with torch.no_grad():
    logits, info = model.forward(input_ids)

print(f"Forward in {time.time()-t0:.1f}s")
print(f"Logits shape: {logits.shape}")

logits_np = logits[0, 0].cpu().numpy()
print(f"Logits: min={logits_np.min():.3f} max={logits_np.max():.3f} std={logits_np.std():.3f}")

# Top 10
top = np.argsort(logits_np)[-10:][::-1]

# Load tokenizer
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

print("\nPython Model Top 10:")
for idx in top:
    text = tok.decode([int(idx)])
    print(f"  {idx:6d}: {logits_np[idx]:8.3f}  {repr(text)}")
