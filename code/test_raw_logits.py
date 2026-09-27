"""Get raw logits from the engine to diagnose the distribution."""
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

# Reset state fresh
engine.reset_state()

# Call forward with a single token to get logits
# forward(token_ids, temperature=1.0, top_p=0.9) signature?
# Let's check
import inspect
print(f"forward signature: checking...")

# Try calling forward
token_id = 6699  # "The"
try:
    result = engine.forward([token_id])
    print(f"forward([{token_id}]) returned type: {type(result)}")
    if isinstance(result, dict):
        print(f"Keys: {result.keys()}")
        if 'logits' in result:
            logits = np.array(result['logits'])
            print(f"Logits shape: {logits.shape}")
            print(f"Logits range: [{logits.min():.3f}, {logits.max():.3f}]")
            print(f"Logits mean: {logits.mean():.3f}, std: {logits.std():.3f}")

            # Top 20 tokens
            top_20 = np.argsort(logits)[-20:][::-1]
            print(f"\nTop 20 tokens after 'The':")
            for rank, tid in enumerate(top_20):
                text = tokenizer.decode([int(tid)])
                print(f"  #{rank+1:2d}: token {tid:5d} logit={logits[tid]:8.3f}  text={repr(text)}")

            # Bottom 5
            bottom_5 = np.argsort(logits)[:5]
            print(f"\nBottom 5 tokens:")
            for rank, tid in enumerate(bottom_5):
                text = tokenizer.decode([int(tid)])
                print(f"  #{rank+1}: token {tid:5d} logit={logits[tid]:8.3f}  text={repr(text)}")

            # Softmax to see probabilities
            logits_shifted = logits - logits.max()
            probs = np.exp(logits_shifted) / np.exp(logits_shifted).sum()

            print(f"\nSoftmax probabilities:")
            print(f"  Max prob: {probs.max():.4f} at token {np.argmax(probs)}")
            print(f"  Top 10 tokens cover: {probs[np.argsort(probs)[-10:]].sum():.4f}")
            print(f"  Entropy: {-(probs * np.log(probs + 1e-10)).sum():.3f} nats")

            # Check if logits are numerically sane
            print(f"\n  Any NaN: {np.any(np.isnan(logits))}")
            print(f"  Any Inf: {np.any(np.isinf(logits))}")
            print(f"  Num zeros: {np.sum(logits == 0)}")
            print(f"  Logits > 10: {np.sum(logits > 10)}")
            print(f"  Logits < -10: {np.sum(logits < -10)}")
    elif isinstance(result, (list, tuple)):
        logits = np.array(result)
        print(f"forward returned array shape: {logits.shape}")
        print(f"Logits range: [{logits.min():.3f}, {logits.max():.3f}]")
    else:
        print(f"forward returned: {str(result)[:500]}")
except Exception as e:
    print(f"forward error: {e}")
    import traceback
    traceback.print_exc()

# Also try forward_cpu if available
try:
    engine.reset_state()
    result2 = engine.forward_cpu([token_id])
    print(f"\nforward_cpu returned type: {type(result2)}")
    if isinstance(result2, dict):
        print(f"Keys: {result2.keys()}")
except Exception as e:
    print(f"forward_cpu: {e}")

print("\n=== Done ===")
