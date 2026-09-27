"""Quick diagnostic: test Rust forward pass with known input."""
import sys
import os
import time

# Add fairy path for imports
FAIRY_DIR = r"F:\Sandbox\failure_factory\akashic_v2\fairies\P30_Cognition\AkashicInferenceFairy"
sys.path.insert(0, r"F:\Sandbox\failure_factory\akashic_v2")
sys.path.insert(0, FAIRY_DIR)

# Add PyTorch lib to PATH for cuBLAS DLLs
try:
    import torch
    torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
    os.environ['PATH'] = torch_lib + ';' + os.environ.get('PATH', '')
    print(f"[Setup] Added PyTorch lib to PATH: {torch_lib}")
except ImportError:
    print("[Setup] PyTorch not available, GPU may not work")

# Actual model path (auto-detect picks the 'official' one)
GGUF_PATH = os.path.join(FAIRY_DIR, "models", "rwkv7-official-1.5B-Q8_0.gguf")

def test():
    from rust_inference_bridge import RustInferenceBridge
    from gguf_parser import get_model_info

    # Get config from GGUF
    info = get_model_info(GGUF_PATH)
    print(f"Model config: {info}")

    class Config:
        n_layer = info.get('n_layer', 24)
        n_embd = info.get('n_embd', 2048)
        n_head = info.get('n_head', 32)
        head_size = n_embd // max(n_head, 1)
        vocab_size = info.get('vocab_size', 65536)

    config = Config()
    print(f"Config: layers={config.n_layer} embd={config.n_embd} heads={config.n_head} "
          f"head_size={config.head_size} vocab={config.vocab_size}")

    # Init bridge
    bridge = RustInferenceBridge(config)

    # Load GGUF direct
    t0 = time.time()
    ok = bridge.load_gguf_direct(GGUF_PATH)
    print(f"Load: {ok} in {time.time()-t0:.1f}s")

    if not ok:
        print("GGUF load failed!")
        return

    print(f"Engine ready: {bridge.is_ready}")
    print(f"GPU: {bridge.gpu_status()}")

    # Load tokenizer -- use importlib trick to handle relative import
    from pathlib import Path
    import importlib
    # Make the fairy dir a proper package for the relative import
    sys.modules.pop('tokenizer', None)
    sys.modules.pop('gguf_parser', None)

    # Set up proper package context
    import types
    pkg = types.ModuleType('fairies.P30_Cognition.AkashicInferenceFairy')
    pkg.__path__ = [FAIRY_DIR]
    pkg.__package__ = 'fairies.P30_Cognition.AkashicInferenceFairy'
    sys.modules['fairies.P30_Cognition.AkashicInferenceFairy'] = pkg

    # Also need parent packages
    for pname in ['fairies', 'fairies.P30_Cognition']:
        if pname not in sys.modules:
            p = types.ModuleType(pname)
            p.__path__ = [os.path.join(r"F:\Sandbox\failure_factory\akashic_v2", *pname.split('.'))]
            p.__package__ = pname
            sys.modules[pname] = p

    from fairies.P30_Cognition.AkashicInferenceFairy.tokenizer import load_tokenizer_from_gguf
    tok = load_tokenizer_from_gguf(Path(GGUF_PATH))
    print(f"Tokenizer: {tok.vocab_size} tokens")

    # Test: simple forward pass
    test_prompt = "The capital of France is"
    tokens = tok.encode(test_prompt)
    print(f"\nPrompt: '{test_prompt}'")
    print(f"Tokens: {tokens}")

    # Forward each token to build state, then get logits from last
    print("\n--- Forward pass (token by token) ---")
    for i, token_id in enumerate(tokens):
        result = bridge.forward([token_id])
        if "error" in result:
            print(f"Forward error at token {i}: {result['error']}")
            return
        print(f"  Token {i}: id={token_id} -> logits len={len(result.get('logits', []))}")

    logits = result.get("logits", [])
    print(f"\nFinal logits: {len(logits)} values")

    if logits:
        import numpy as np
        logits = np.array(logits)
        print(f"Logits stats: min={logits.min():.3f} max={logits.max():.3f} "
              f"mean={logits.mean():.3f} std={logits.std():.3f}")

        # Top 10 tokens
        top_indices = np.argsort(logits)[-10:][::-1]
        print("\nTop 10 predictions:")
        for idx in top_indices:
            token_text = tok.decode([int(idx)])
            print(f"  {idx:6d}: {logits[idx]:8.3f}  '{token_text}'")

        # Check if logits are reasonable (not uniform/garbage)
        if logits.std() < 1.0:
            print("\n!! WARNING: Low logit variance — model may not be producing meaningful output!")
        elif logits.std() < 5.0:
            print(f"\n~~ Moderate variance ({logits.std():.2f}) — may need investigation")
        else:
            print(f"\n>> Logit variance looks healthy ({logits.std():.2f})")

        # Check if top prediction makes sense for "The capital of France is"
        top_token = tok.decode([int(top_indices[0])])
        print(f"\nTop prediction: '{top_token}'")
        if 'paris' in top_token.lower() or 'Par' in top_token:
            print(">> CORRECT! Model predicts Paris-related token.")
        else:
            print(f"~~ Expected 'Paris' but got '{top_token}' — may indicate weight issues")

    # Test generation
    print("\n--- Generation test ---")
    # Reset state first
    bridge.reset_state()
    generated = bridge.generate(
        prompt_ids=tokens,
        max_tokens=20,
        temperature=0.7,
        top_p=0.9,
    )
    if generated:
        text = tok.decode(generated)
        print(f"Generated ({len(generated)} tokens): '{text}'")
    else:
        print("No tokens generated!")

if __name__ == "__main__":
    test()
