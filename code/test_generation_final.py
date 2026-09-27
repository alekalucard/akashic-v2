"""Final generation quality test for RWKV-7 Rust engine.
Test with multiple prompts at different temperatures."""
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
VOCAB_PATH = r"F:\Sandbox\failure_factory\akashic_v2\research_repos\RWKV-LM\RWKV-v7\rwkv_vocab_v20230424.txt"

from tokenizer import AkashicTokenizer
tokenizer = AkashicTokenizer(vocab_path=VOCAB_PATH)

from rwkv_inference import RWKVEngine
engine = RWKVEngine(24, 2048, 32, 65536)
engine.load_gguf(GGUF_PATH)

prompts = [
    "The meaning of life is",
    "Once upon a time, in a land far away,",
    "Hello, my name is",
    "In a shocking finding, scientists discovered",
    "The capital of France is",
    "def fibonacci(n):",
]

for prompt in prompts:
    print("=" * 70)
    print(f"PROMPT: {prompt}")
    print("=" * 70)

    for temp in [0.01, 0.7, 1.0]:
        engine.reset_state()
        prompt_ids = tokenizer.encode(prompt)
        result = engine.generate(prompt_ids, max_tokens=50, temperature=temp, top_p=0.9)

        gen_tokens = result['tokens']
        gen_text = tokenizer.decode(gen_tokens)

        elapsed = result['elapsed_ms']
        tps = result['tokens_per_sec']

        # Token diversity
        unique = len(set(gen_tokens))
        diversity = unique / max(len(gen_tokens), 1) * 100

        print(f"\n  temp={temp:.2f} ({elapsed:.0f}ms, {tps:.1f} tok/s, diversity={diversity:.0f}%):")
        print(f"  >>> {prompt}{gen_text}")

    print()

print("\n=== Generation tests complete ===")
