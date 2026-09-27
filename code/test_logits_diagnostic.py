"""Diagnose RWKV logits — check if the forward pass produces sane probability distributions."""
import sys, os
import numpy as np

# Force UTF-8 output
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
VOCAB_PATH = r"F:\Sandbox\failure_factory\akashic_v2\research_repos\RWKV-LM\RWKV-v7\rwkv_vocab_v20230424.txt"

from tokenizer import AkashicTokenizer
tokenizer = AkashicTokenizer(vocab_path=VOCAB_PATH)

from rwkv_inference import RWKVEngine
engine = RWKVEngine(24, 2048, 32, 65536)
engine.load_gguf(GGUF_PATH)

# Get raw logits for "The"
prompt_ids = tokenizer.encode("The")
print(f"Prompt: 'The' = token IDs: {prompt_ids}")

# Use forward_single to get raw logits (if available)
# The generate method applies sampling, we need raw logits
# Let's check what methods the engine exposes
print(f"\nEngine methods: {[m for m in dir(engine) if not m.startswith('_')]}")

# Try generate with max_tokens=1 and temperature=1.0 to see what token comes out
# Also try with temperature very low (greedy)
for temp in [0.01, 0.5, 1.0]:
    result = engine.generate(prompt_ids, max_tokens=1, temperature=temp, top_p=1.0)
    out_ids = result['tokens'] if isinstance(result, dict) else result
    if out_ids:
        last_token = out_ids[-1]
        text = tokenizer.decode([last_token])
        print(f"Temp={temp:.2f}: token {last_token} = {repr(text)}")

# Generate a longer sequence at temp=0.01 (greedy) to see deterministic output
print(f"\n--- Greedy decode (temp=0.01) from 'The meaning of life is' ---")
prompt_ids = tokenizer.encode("The meaning of life is")
result = engine.generate(prompt_ids, max_tokens=20, temperature=0.01, top_p=1.0)
out_ids = result['tokens'] if isinstance(result, dict) else result
print(f"Token IDs: {out_ids}")
for i, tid in enumerate(out_ids):
    text = tokenizer.decode([tid])
    print(f"  [{i}] token {tid:5d} = {repr(text)}")

# Check if there's a forward method that returns logits
if hasattr(engine, 'forward') or hasattr(engine, 'forward_single'):
    print("\n--- Engine has forward method, getting raw logits ---")
    # Try to get raw logits
    try:
        logits = engine.forward_single(prompt_ids[0])
        logits_np = np.array(logits)
        print(f"Logits shape: {logits_np.shape}")
        print(f"Logits range: [{logits_np.min():.3f}, {logits_np.max():.3f}]")
        print(f"Logits mean: {logits_np.mean():.3f}, std: {logits_np.std():.3f}")

        # Top-10 tokens
        top_10 = np.argsort(logits_np)[-10:][::-1]
        print(f"\nTop 10 tokens:")
        for rank, tid in enumerate(top_10):
            text = tokenizer.decode([int(tid)])
            print(f"  #{rank+1}: token {tid} = {repr(text):20s} logit={logits_np[tid]:.3f}")
    except Exception as e:
        print(f"forward_single error: {e}")

# Also check the state — is it getting corrupted?
print(f"\n--- State check: Reset and regenerate ---")
# The engine should reset state between generate calls (or we need to check)
# Try encoding just "Hello" twice and see if we get same result
for trial in range(2):
    result = engine.generate([33155], max_tokens=5, temperature=0.01, top_p=1.0)
    out_ids = result['tokens'] if isinstance(result, dict) else result
    texts = [tokenizer.decode([t]) for t in out_ids]
    print(f"  Trial {trial+1}: {out_ids} = {texts}")

print("\n=== Diagnostic complete ===")
