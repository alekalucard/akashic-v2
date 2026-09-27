"""
Test the battery engine sampling with proper anti-repetition measures.

This verifies the fix for the repetition collapse issue
where greedy decoding caused the model to loop on ' ' tokens.
"""
import sys, os, time
import numpy as np

# Force UTF-8 output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Fix relative imports: create a proper fake package ──
V2_DIR = r"F:\Sandbox\failure_factory\akashic_v2"
sys.path.insert(0, V2_DIR)

import types
import importlib.util

# Create a fake package so relative imports (.tiled_matvec etc.) resolve
PKG = "_battery_pkg"
pkg_mod = types.ModuleType(PKG)
pkg_mod.__path__ = [V2_DIR]
pkg_mod.__package__ = PKG
sys.modules[PKG] = pkg_mod

def _load_as_submodule(name):
    """Load V2_DIR/{name}.py as _battery_pkg.{name}"""
    fqn = f"{PKG}.{name}"
    filepath = os.path.join(V2_DIR, f"{name}.py")
    spec = importlib.util.spec_from_file_location(fqn, filepath,
        submodule_search_locations=[])
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = PKG
    sys.modules[fqn] = mod
    setattr(pkg_mod, name, mod)  # pkg.name = mod
    spec.loader.exec_module(mod)
    return mod

# Load in dependency order (no-deps first)
tiled = _load_as_submodule("tiled_matvec")
qws_mod = _load_as_submodule("quantized_weight_store")
bcu_mod = _load_as_submodule("battery_compute_unit")
engine_mod = _load_as_submodule("rwkv_battery_engine")

RWKVBatteryEngine = engine_mod.RWKVBatteryEngine
RWKVBatteryConfig = engine_mod.RWKVBatteryConfig
QuantizedWeightStore = qws_mod.QuantizedWeightStore
BatteryComputeUnit = bcu_mod.BatteryComputeUnit

print("[OK] All battery modules loaded")

# ── Load tokenizer ──
FAIRY_DIR = os.path.join(V2_DIR, "fairies", "P30_Cognition", "AkashicInferenceFairy")
sys.path.insert(0, FAIRY_DIR)

from gguf_parser import GGUFParser
from tokenizer import AkashicTokenizer

GGUF_PATH = os.path.join(FAIRY_DIR, "models", "rwkv7-official-1.5B-Q8_0.gguf")

if not os.path.exists(GGUF_PATH):
    # Try alternative name
    GGUF_PATH = os.path.join(FAIRY_DIR, "models", "rwkv7-1.5B-world-Q8_0.gguf")

print(f"[INFO] Model: {GGUF_PATH}")
print(f"[INFO] Exists: {os.path.exists(GGUF_PATH)}")

if not os.path.exists(GGUF_PATH):
    print("[FATAL] No GGUF model found!")
    sys.exit(1)

# Parse GGUF and load tokenizer
parser = GGUFParser()
gguf_file = parser.parse(GGUF_PATH)
tokenizer = AkashicTokenizer()
tokenizer.load_from_gguf(gguf_file.metadata)
print(f"[OK] Tokenizer: {tokenizer.vocab_size} tokens")

# ── Load weights ──
print("[INFO] Loading GGUF weights...")
t0 = time.time()
weight_store = QuantizedWeightStore.from_gguf(GGUF_PATH)
print(f"[OK] Weights loaded in {time.time()-t0:.1f}s: {len(weight_store.tensor_names)} tensors")

# ── Create engine ──
config = RWKVBatteryConfig(n_layer=24, n_embd=2048, n_head=32, vocab_size=65536)

# Generous battery for testing (won't deplete mid-generation)
bcu = BatteryComputeUnit(
    flops_budget=int(500e6),
    initial_charge=100.0,    # lots of charge
    max_charge=100.0,
    recharge_rate=10.0,      # fast recharge
)

print("[INFO] Building engine (24 layers)...")
t0 = time.time()
engine = RWKVBatteryEngine(config=config, weights=weight_store, compute=bcu)
engine.init_all_states()
print(f"[OK] Engine built in {time.time()-t0:.1f}s")

# ═══════════════════════════════════════════════════════════════
# TEST 1: Single token predictions (sanity check)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("TEST 1: Single-token predictions (should be diverse)")
print("=" * 70)

test_prompts = {
    "Hello": None,
    "I think": None,
    "1+1=": None,
    "The sky is": None,
}

for prompt_text in test_prompts:
    bcu.charge_level = 100.0  # reset charge
    engine.init_all_states()
    tokens = tokenizer.encode(prompt_text)

    # Process prompt
    for tok in tokens:
        result = engine.forward_one_token(tok)

    logits = result.get("logits")
    if logits is not None:
        # Show top-5 predictions
        top5 = np.argsort(logits)[-5:][::-1]
        probs = np.exp(logits - np.max(logits))
        probs /= np.sum(probs)

        preds = []
        for idx in top5:
            text = tokenizer.decode([int(idx)])
            preds.append(f"{repr(text)}({probs[idx]*100:.1f}%)")
        print(f"  '{prompt_text}' → {', '.join(preds)}")

# ═══════════════════════════════════════════════════════════════
# TEST 2: Multi-token generation WITH sampling (the fix)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("TEST 2: Multi-token generation with anti-repetition sampling")
print("=" * 70)

gen_prompts = [
    "The meaning of life is",
    "Hello, my name is",
    "Once upon a time,",
]

sampling_configs = [
    {"name": "greedy (old)", "temperature": 0.01, "top_p": 1.0, "top_k": 0,
     "repetition_penalty": 1.0, "presence_penalty": 0.0, "frequency_penalty": 0.0},
    {"name": "default (new)", "temperature": 1.0, "top_p": 0.3, "top_k": 0,
     "repetition_penalty": 1.2, "presence_penalty": 0.3, "frequency_penalty": 0.3},
    {"name": "creative", "temperature": 1.2, "top_p": 0.5, "top_k": 0,
     "repetition_penalty": 1.3, "presence_penalty": 0.4, "frequency_penalty": 0.4},
]

MAX_GEN = 20  # tokens per test

for prompt_text in gen_prompts:
    print(f"\n--- Prompt: '{prompt_text}' ---")
    prompt_ids = tokenizer.encode(prompt_text)

    for cfg in sampling_configs:
        bcu.charge_level = 100.0
        engine.init_all_states()

        t0 = time.time()
        result = engine.generate(
            prompt_tokens=prompt_ids,
            max_tokens=MAX_GEN,
            temperature=cfg["temperature"],
            top_k=cfg["top_k"],
            top_p=cfg["top_p"],
            repetition_penalty=cfg["repetition_penalty"],
            presence_penalty=cfg["presence_penalty"],
            frequency_penalty=cfg["frequency_penalty"],
        )
        elapsed = time.time() - t0

        gen_tokens = result.get("tokens", [])
        gen_text = tokenizer.decode(gen_tokens)
        unique = len(set(gen_tokens))
        diversity = unique / max(len(gen_tokens), 1) * 100

        status = result.get("status", "?")
        print(f"  [{cfg['name']:14s}] ({elapsed:.1f}s, {len(gen_tokens)}tok, "
              f"div={diversity:.0f}%, {status})")
        print(f"    >>> {prompt_text}{gen_text}")

# ═══════════════════════════════════════════════════════════════
# TEST 3: Repetition detection
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("TEST 3: Repetition detection (old greedy vs new sampling)")
print("=" * 70)

prompt_text = "Hello"
prompt_ids = tokenizer.encode(prompt_text)

for label, params in [
    ("GREEDY (broken)", dict(temperature=0.01, top_p=1.0, repetition_penalty=1.0,
                              presence_penalty=0.0, frequency_penalty=0.0)),
    ("SAMPLED (fixed)", dict(temperature=1.0, top_p=0.3, repetition_penalty=1.2,
                              presence_penalty=0.3, frequency_penalty=0.3)),
]:
    bcu.charge_level = 100.0
    engine.init_all_states()

    result = engine.generate(
        prompt_tokens=prompt_ids,
        max_tokens=30,
        top_k=0,
        **params,
    )

    gen_tokens = result.get("tokens", [])
    gen_text = tokenizer.decode(gen_tokens)

    # Count repeated consecutive tokens
    consecutive_repeats = 0
    max_repeat = 0
    for i in range(1, len(gen_tokens)):
        if gen_tokens[i] == gen_tokens[i-1]:
            consecutive_repeats += 1
            max_repeat = max(max_repeat, consecutive_repeats)
        else:
            consecutive_repeats = 0

    unique = len(set(gen_tokens))
    print(f"\n  [{label}]")
    print(f"    Tokens: {len(gen_tokens)}, Unique: {unique}, Max consecutive repeat: {max_repeat}")
    print(f"    >>> Hello{gen_text}")

print("\n" + "=" * 70)
print("=== Battery sampling test complete ===")
print("=" * 70)
