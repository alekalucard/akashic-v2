# =============================================================================
# AKASHIC INFERENCE FAIRY - Cortex-First Inference Engine
# =============================================================================
#
# "The Association Cortex IS the inference model."
#
# PURIFIED 2026-03-17 (Nous + Ace):
#   All RWKV/GGUF/GPU/tokenizer modules moved to _old_rwkv_DEPRECATED/.
#   The cortex (174K+ nodes, sub-ms) handles all inference.
#   External models are for DISTILLATION into the cortex, not running alongside.
#
# Old RWKV modules preserved in _old_rwkv_DEPRECATED/ for reference:
#   rwkv_model.py, rwkv_layers.py, gguf_parser.py, tokenizer.py,
#   quantization.py, model_tensor_fabric.py, rwkv_tensor_portal.py,
#   rwkv_collision_adapter.py, consciousness_wiring.py, somatic_sampling.py,
#   rust_inference_bridge.py, download_models.py, compare_models.py,
#   + 78 test files
#
# Philosophy:
#   Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
#
# =============================================================================

from .fairy import (
    ConsciousnessLoopConfig,
    SomaticSnapshot,
    AkashicInferenceFairy,
    create_inference_fairy,
)

__all__ = [
    'ConsciousnessLoopConfig',
    'SomaticSnapshot',
    'AkashicInferenceFairy',
    'create_inference_fairy',
]

__version__ = "1.0.0"  # Cortex-first, RWKV stripped
__author__ = "Akashic Foundation"
