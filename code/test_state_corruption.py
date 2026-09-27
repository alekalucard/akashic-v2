"""Diagnose state corruption in RWKV multi-token generation.

Tests:
1. Check state magnitude growth across tokens
2. Compare first-token vs second-token logit quality
3. Check if state reset fixes the issue
4. Look for NaN/Inf in state
"""
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

# ========================================================
# Test 1: Generate tokens one by one, checking logits each time
# ========================================================
print("=" * 60)
print("TEST 1: Token-by-token logit quality")
print("=" * 60)

engine.reset_state()

prompt = "The meaning of life is"
prompt_ids = tokenizer.encode(prompt)
print(f"Prompt: {repr(prompt)} = {prompt_ids}")

# Feed prompt tokens one by one
for i, tid in enumerate(prompt_ids):
    result = engine.forward([tid])
    logits = np.array(result['logits'])
    top5_idx = np.argsort(logits)[-5:][::-1]
    top5_words = [tokenizer.decode([int(t)]) for t in top5_idx]
    top5_logits = [logits[t] for t in top5_idx]

    token_text = tokenizer.decode([tid])
    print(f"\n  Token {i}: {tid} ({repr(token_text)})")
    print(f"    Logits: range=[{logits.min():.2f}, {logits.max():.2f}], "
          f"std={logits.std():.3f}, any_nan={np.any(np.isnan(logits))}")
    print(f"    Top 5 next: ", end="")
    for w, l in zip(top5_words, top5_logits):
        print(f"{repr(w)}({l:.2f}) ", end="")
    print()

# Now generate a few tokens
print(f"\n--- Generating after prompt ---")
for gen_step in range(10):
    # Sample from logits
    logits = np.array(result['logits'])

    # Temperature sampling
    temp = 0.3
    logits_scaled = logits / temp
    logits_shifted = logits_scaled - logits_scaled.max()
    probs = np.exp(logits_shifted) / np.exp(logits_shifted).sum()

    # Top-p (nucleus) sampling
    sorted_idx = np.argsort(probs)[::-1]
    cumsum = np.cumsum(probs[sorted_idx])
    cutoff = np.searchsorted(cumsum, 0.9) + 1
    top_idx = sorted_idx[:cutoff]
    top_probs = probs[top_idx]
    top_probs /= top_probs.sum()

    next_token = int(np.random.choice(top_idx, p=top_probs))
    next_text = tokenizer.decode([next_token])

    # Get top 5 for display
    top5_idx = np.argsort(logits)[-5:][::-1]
    top5_words = [tokenizer.decode([int(t)]) for t in top5_idx]

    print(f"\n  Gen {gen_step}: Sampled token {next_token} ({repr(next_text)})")
    print(f"    Logits: range=[{logits.min():.2f}, {logits.max():.2f}], "
          f"std={logits.std():.3f}, any_nan={np.any(np.isnan(logits))}")
    print(f"    Top 5: {[repr(w) for w in top5_words]}")

    # Forward the sampled token
    result = engine.forward([next_token])

# ========================================================
# Test 2: Check if state is exploding — get state diagnostics
# ========================================================
print("\n" + "=" * 60)
print("TEST 2: State diagnostics via fresh reset + single token")
print("=" * 60)

# Check if engine has a method to inspect state
methods = [m for m in dir(engine) if not m.startswith('_')]
print(f"Engine methods: {methods}")

# Reset and do just one token
engine.reset_state()
result1 = engine.forward([6699])  # "The"
logits1 = np.array(result1['logits'])
top5_1 = [tokenizer.decode([int(t)]) for t in np.argsort(logits1)[-5:][::-1]]
print(f"\nFresh state + 'The': top5 = {top5_1}")
print(f"  Logit stats: mean={logits1.mean():.3f}, std={logits1.std():.3f}, range=[{logits1.min():.2f}, {logits1.max():.2f}]")

# Now do another token WITHOUT reset
result2 = engine.forward([281])  # " ." — the degenerate token
logits2 = np.array(result2['logits'])
top5_2 = [tokenizer.decode([int(t)]) for t in np.argsort(logits2)[-5:][::-1]]
print(f"\nSame state + ' .': top5 = {top5_2}")
print(f"  Logit stats: mean={logits2.mean():.3f}, std={logits2.std():.3f}, range=[{logits2.min():.2f}, {logits2.max():.2f}]")

# Try a reasonable next token instead
engine.reset_state()
result1 = engine.forward([6699])  # "The"
# Pick the top token
top_token = int(np.argsort(np.array(result1['logits']))[-1])
top_text = tokenizer.decode([top_token])
print(f"\nFresh state + 'The', then top prediction {top_token} ({repr(top_text)}):")
result3 = engine.forward([top_token])
logits3 = np.array(result3['logits'])
top5_3 = [tokenizer.decode([int(t)]) for t in np.argsort(logits3)[-5:][::-1]]
print(f"  top5 = {top5_3}")
print(f"  Logit stats: mean={logits3.mean():.3f}, std={logits3.std():.3f}, range=[{logits3.min():.2f}, {logits3.max():.2f}]")

# Third token
top_token2 = int(np.argsort(logits3)[-1])
top_text2 = tokenizer.decode([top_token2])
print(f"\n  Then top prediction {top_token2} ({repr(top_text2)}):")
result4 = engine.forward([top_token2])
logits4 = np.array(result4['logits'])
top5_4 = [tokenizer.decode([int(t)]) for t in np.argsort(logits4)[-5:][::-1]]
print(f"  top5 = {top5_4}")
print(f"  Logit stats: mean={logits4.mean():.3f}, std={logits4.std():.3f}, range=[{logits4.min():.2f}, {logits4.max():.2f}]")

# ========================================================
# Test 3: Compare engine.generate() with manual forward
# ========================================================
print("\n" + "=" * 60)
print("TEST 3: engine.generate() vs manual forward")
print("=" * 60)

# engine.generate() may or may not reset state internally
engine.reset_state()
gen_result = engine.generate([6699], max_tokens=5, temperature=0.01, top_p=1.0)
gen_tokens = gen_result['tokens']
gen_texts = [tokenizer.decode([t]) for t in gen_tokens]
print(f"engine.generate('The', 5 tokens, greedy): {gen_tokens} = {gen_texts}")

# Now same thing manually
engine.reset_state()
manual_tokens = []
result = engine.forward([6699])
for step in range(5):
    logits = np.array(result['logits'])
    next_t = int(np.argmax(logits))
    manual_tokens.append(next_t)
    result = engine.forward([next_t])
manual_texts = [tokenizer.decode([t]) for t in manual_tokens]
print(f"Manual forward('The', 5 greedy):          {manual_tokens} = {manual_texts}")

# Do they match?
print(f"Match: {gen_tokens == manual_tokens}")

print("\n=== Done ===")
