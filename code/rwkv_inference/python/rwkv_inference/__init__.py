"""
RWKV-7 Inference Kernel for Akashic Consciousness System.

Compiled Rust forward pass replacing the pure-Python layer loop.
Provides 10-100x speedup for real-time chat generation.

Usage:
    from rwkv_inference import RWKVEngine

    engine = RWKVEngine(n_layer=24, n_embd=2048, n_head=32, vocab_size=65536)
    engine.load_weights(weight_dict)  # {name: [f32 values]}

    # Single forward pass
    result = engine.forward([token_id], somatic={"arousal": 0.6, "confidence": 0.8})
    logits = result["logits"]

    # Full generation
    result = engine.generate(
        prompt_ids=[1, 2, 3],
        max_tokens=40,
        temperature=0.9,
        top_p=0.9,
        somatic={"arousal": 0.6}
    )
    tokens = result["tokens"]
    print(f"{result['tokens_per_sec']:.1f} tok/s")
"""

__version__ = "0.1.0"

try:
    from rwkv_inference._native import RWKVEngine
    RUST_AVAILABLE = True
except ImportError as e:
    RUST_AVAILABLE = False
    _import_error = str(e)

    class RWKVEngine:
        """Stub — Rust kernel not compiled. Build with: maturin develop --release"""
        def __init__(self, *args, **kwargs):
            raise ImportError(
                f"rwkv_inference Rust kernel not available: {_import_error}\n"
                f"Build with: cd rwkv_inference && maturin develop --release"
            )


def is_available() -> bool:
    """Check if the compiled Rust kernel is available."""
    return RUST_AVAILABLE
