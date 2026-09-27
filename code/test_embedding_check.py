"""Check if embedding lookup and weights are correct by comparing
Rust engine internals against numpy calculations."""
import sys, os
import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

FAIRY_DIR = r"F:\Sandbox\failure_factory\akashic_v2\fairies\P30_Cognition\AkashicInferenceFairy"
sys.path.insert(0, FAIRY_DIR)
sys.path.insert(0, r"F:\Sandbox\failure_factory\akashic_v2")

try:
    import torch
    torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
    os.environ['PATH'] = torch_lib + ';' + os.environ.get('PATH', '')
except ImportError:
    pass

GGUF_PATH = os.path.join(FAIRY_DIR, "models", "rwkv7-official-1.5B-Q8_0.gguf")

# Load GGUF directly to get raw tensors
from rwkv_inference import RWKVEngine
engine = RWKVEngine(24, 2048, 32, 65536)
engine.load_gguf(GGUF_PATH)

# Check: does the engine expose weight inspection?
print(f"Engine methods: {[m for m in dir(engine) if not m.startswith('_')]}")

# Now load the GGUF with Python too to cross-reference
# Use gguf library if available
try:
    from gguf import GGUFReader as PyGGUFReader
    print("\nUsing gguf Python library for cross-reference...")
    py_reader = PyGGUFReader(GGUF_PATH)

    # Find token_embd.weight
    for tensor_info in py_reader.tensors:
        name = tensor_info.name
        if name == "token_embd.weight":
            print(f"\ntoken_embd.weight:")
            print(f"  Shape (ne): {tensor_info.shape}")
            print(f"  Type: {tensor_info.tensor_type}")

            # Dequantize and check embedding for token 6699 ("The")
            data = tensor_info.data  # This may need dequantization
            print(f"  Raw data type: {type(data)}, len: {len(data)}")
            break
except ImportError:
    print("gguf Python library not available, skipping cross-reference")

# Alternative: load with llama.cpp Python bindings or manual parsing
# For now, let's use the Rust engine's numpy interface if available

# The key test: compare forward pass of token "The" (6699)
# against a Python RWKV reference implementation
print("\n=== Checking RWKV reference implementation ===")
ref_path = r"F:\Sandbox\failure_factory\akashic_v2\research_repos\RWKV-LM\RWKV-v7"
sys.path.insert(0, ref_path)

# Check what reference files exist
for f in os.listdir(ref_path):
    if f.endswith('.py'):
        print(f"  {f}")

# Try to use rwkv_v7_numpy.py as reference
numpy_ref = os.path.join(ref_path, "rwkv_v7_numpy.py")
if os.path.exists(numpy_ref):
    print(f"\nFound numpy reference: {numpy_ref}")
    # Check if it can load our GGUF... probably not directly
    # It likely needs .pth format

# Check for model files
model_dir = os.path.join(FAIRY_DIR, "models")
print(f"\nModel files in {model_dir}:")
for f in os.listdir(model_dir):
    fpath = os.path.join(model_dir, f)
    size_mb = os.path.getsize(fpath) / (1024*1024)
    print(f"  {f} ({size_mb:.1f} MB)")

# Let's try a different approach: use the RWKV converter's tensor name mapping
# to verify our set_tensor mapping is correct
print("\n=== Checking GGUF tensor names vs our mapping ===")

# Parse GGUF just for tensor names and shapes
from rwkv_inference import RWKVEngine as _RE
# We can check tensor shapes from the GGUF metadata
# Let's parse the GGUF header manually to list tensor names + shapes
import struct

with open(GGUF_PATH, 'rb') as f:
    magic = f.read(4)
    version = struct.unpack('<I', f.read(4))[0]
    tensor_count = struct.unpack('<Q', f.read(8))[0]
    kv_count = struct.unpack('<Q', f.read(8))[0]
    print(f"GGUF v{version}: {tensor_count} tensors, {kv_count} KV pairs")

# Actually let's just check a few specific tensor shapes from the Python gguf lib
try:
    from gguf import GGUFReader as PyGGUFReader
    py_reader = PyGGUFReader(GGUF_PATH)

    # Check key tensors
    check_names = [
        "token_embd.weight",
        "output.weight",
        "blk.0.time_mix_receptance.weight",
        "blk.0.time_mix_key.weight",
        "blk.0.time_mix_w1.weight",
        "blk.0.time_mix_w2.weight",
        "blk.0.time_mix_g1.weight",
        "blk.0.time_mix_g2.weight",
        "blk.0.time_mix_a1.weight",
        "blk.0.time_mix_a2.weight",
        "blk.0.time_mix_v1.weight",
        "blk.0.time_mix_v2.weight",
        "blk.0.time_mix_lerp_fused.weight",
        "blk.0.channel_mix_key.weight",
        "blk.0.channel_mix_value.weight",
    ]

    print(f"\nKey tensor shapes:")
    for tensor_info in py_reader.tensors:
        if tensor_info.name in check_names:
            print(f"  {tensor_info.name}: shape={list(tensor_info.shape)}")
except ImportError:
    pass
except Exception as e:
    print(f"Error reading tensors: {e}")

print("\n=== Done ===")
