"""Test RWKV generation with the transpose fix.

This verifies that the Rust engine with corrected matmul_vec
(reading GGUF [N,K] physical as logical [K,N]) produces coherent text.
"""
import sys, os

# Force UTF-8 output for Windows console
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Setup paths
FAIRY_DIR = r"F:\Sandbox\failure_factory\akashic_v2\fairies\P30_Cognition\AkashicInferenceFairy"
sys.path.insert(0, FAIRY_DIR)
sys.path.insert(0, r"F:\Sandbox\failure_factory\akashic_v2")

# Ensure torch DLLs findable
try:
    import torch
    torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
    os.environ['PATH'] = torch_lib + ';' + os.environ.get('PATH', '')
except ImportError:
    pass

GGUF_PATH = os.path.join(FAIRY_DIR, "models", "rwkv7-official-1.5B-Q8_0.gguf")
VOCAB_PATH = r"F:\Sandbox\failure_factory\akashic_v2\research_repos\RWKV-LM\RWKV-v7\rwkv_vocab_v20230424.txt"

# === Step 1: Load tokenizer ===
print("=== Loading tokenizer ===")
from tokenizer import AkashicTokenizer
tokenizer = AkashicTokenizer(vocab_path=VOCAB_PATH)
print(f"Vocab size: {tokenizer.vocab_size}")

# Quick tokenizer sanity check
test_text = "Hello world"
tokens = tokenizer.encode(test_text)
decoded = tokenizer.decode(tokens)
print(f"Encode/decode test: '{test_text}' -> {tokens} -> '{decoded}'")

# === Step 2: Load Rust engine ===
print("\n=== Loading Rust engine ===")
from rwkv_inference import RWKVEngine

# Create engine with dummy params (load_gguf overrides from metadata)
engine = RWKVEngine(24, 2048, 32, 65536)
print(f"Engine created, loading GGUF...")

engine.load_gguf(GGUF_PATH)
print(f"GGUF loaded. Ready: {engine.is_ready()}")

# === Step 3: Generate text ===
prompts = [
    "The meaning of life is",
    "Once upon a time",
    "Hello, my name is",
]

for prompt in prompts:
    print(f"\n{'='*60}")
    print(f"PROMPT: {prompt}")
    print(f"{'='*60}")

    # Encode prompt
    prompt_ids = tokenizer.encode(prompt)
    print(f"Prompt token IDs: {prompt_ids}")

    # Generate with low temp for deterministic output
    try:
        result = engine.generate(
            prompt_ids,
            max_tokens=32,
            temperature=0.3,    # Low temp = more deterministic
            top_p=0.5,
        )

        # engine.generate() returns a dict with 'tokens', 'elapsed_ms', etc.
        output_ids = result['tokens'] if isinstance(result, dict) else result

        print(f"Generated token IDs: {output_ids}")
        print(f"Speed: {result.get('tokens_per_sec', '?'):.1f} tok/s")

        # Decode
        output_text = tokenizer.decode(output_ids)
        print(f"OUTPUT TEXT: {repr(output_text)}")

        # Check for repetition (same token repeated)
        if len(output_ids) > 3:
            unique_tokens = len(set(output_ids))
            total_tokens = len(output_ids)
            diversity = unique_tokens / total_tokens
            print(f"Token diversity: {unique_tokens}/{total_tokens} = {diversity:.2%}")

            # Check for most common token
            from collections import Counter
            counts = Counter(output_ids)
            most_common_id, most_common_count = counts.most_common(1)[0]
            most_common_text = tokenizer.decode([most_common_id])
            print(f"Most common token: {most_common_id} ({repr(most_common_text)}) x{most_common_count}")

        # Check for garbled output indicators
        ascii_count = sum(1 for c in output_text if 32 <= ord(c) < 127)
        total_count = len(output_text) if output_text else 1
        ascii_ratio = ascii_count / total_count
        print(f"ASCII ratio: {ascii_ratio:.2%} ({'COHERENT' if ascii_ratio > 0.7 else 'GARBLED'})")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

# === Step 4: Single-token test (check logits sanity) ===
print(f"\n{'='*60}")
print("SINGLE TOKEN TEST: What comes after 'The'?")
print(f"{'='*60}")
try:
    the_token = tokenizer.encode("The")
    print(f"'The' = token IDs: {the_token}")
    result = engine.generate(
        the_token,
        max_tokens=1,
        temperature=1.0,
        top_p=1.0,  # No filtering — see raw distribution
    )
    output_ids = result['tokens'] if isinstance(result, dict) else result
    next_token = output_ids[-1] if output_ids else None
    if next_token is not None:
        next_text = tokenizer.decode([next_token])
        print(f"Next token: {next_token} = {repr(next_text)}")
    else:
        print(f"No output tokens?? Result: {result}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Test complete ===")
