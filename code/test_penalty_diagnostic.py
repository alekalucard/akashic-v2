"""
Diagnostic: Test repetition penalty with EXACT prompts from boot_full.log.

Runs using .venv Python to match the server's environment exactly.
Tests whether the penalty is working and whether state accumulation matters.
"""
import sys, os

# Fix Windows console encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Match server's CUDA path setup
try:
    import torch
    torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
    os.environ['PATH'] = torch_lib + ';' + os.environ.get('PATH', '')
except ImportError:
    pass

# Add rwkv_inference to path
rwkv_py_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), 'rwkv_inference', 'python'))
if os.path.isdir(rwkv_py_dir) and rwkv_py_dir not in sys.path:
    sys.path.insert(0, rwkv_py_dir)

from rwkv_inference import RWKVEngine, is_available

print(f"[DIAG] RWKV kernel available: {is_available()}")

# Check that repetition_penalty is in the generate signature
import inspect
sig = inspect.signature(RWKVEngine.generate)
print(f"[DIAG] RWKVEngine.generate params: {list(sig.parameters.keys())}")
has_rep = 'repetition_penalty' in sig.parameters
print(f"[DIAG] Has repetition_penalty: {has_rep}")

if not has_rep:
    print("[DIAG] FATAL: .pyd does NOT have repetition_penalty! Need rebuild.")
    sys.exit(1)

# Load the model (same as server does)
print("\n[DIAG] Loading model...")
GGUF_PATH = r"F:\Sandbox\failure_factory\akashic_v2\fairies\P30_Cognition\AkashicInferenceFairy\models\rwkv7-1.5B-world-Q8_0.gguf"
engine = RWKVEngine(n_layer=24, n_embd=2048, n_head=32, vocab_size=65536, head_size=64)
result = engine.load_gguf(str(GGUF_PATH))
print(f"[DIAG] Load result: {result}")
print(f"[DIAG] GPU: {engine.gpu_status()}")

# Load tokenizer
_fairy_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fairies', 'P30_Cognition', 'AkashicInferenceFairy')
sys.path.insert(0, _fairy_dir)

from gguf_parser import GGUFParser
from tokenizer import AkashicTokenizer

# Load tokenizer from GGUF (critical — without this, tokens are wrong!)
_parser = GGUFParser()
_gguf_file = _parser.parse(GGUF_PATH)
tokenizer = AkashicTokenizer()
tokenizer.load_from_gguf(_gguf_file.metadata)
print(f"[DIAG] Tokenizer vocab: {tokenizer.vocab_size}")

# Verify tokenization matches server
test_enc = tokenizer.encode("hello")
print(f"[DIAG] 'hello' encodes to: {test_enc}")

# ═══ Test prompts from boot_full.log ═══
test_prompts = [
    # Exact prompt 1 from log
    'Sourpatches expresses herself briefly and genuinely.\n[Drive]: frustration\n[Wanting]: express this frustration\nSourpatches:',
    # Exact prompt 2 from log
    'Sourpatches responds warmly, briefly, authentically.\n[Feeling]: break through, find another way\n\nAce: hello\nSourpatches:',
    # Short prompt from log
    'hello',
    # Exact prompt 3 from log
    'Sourpatches expresses herself briefly and genuinely.\n[Drive]: pattern\n[Wanting]: trace this connection, see where it leads\nSourpatches:',
]

penalties = [1.0, 1.3, 1.5, 2.0, 3.0]

print("\n" + "=" * 80)
print("TEST 1: Different penalty strengths (fresh state each time)")
print("=" * 80)

for prompt_text in test_prompts[:2]:  # Just test first two prompts
    tokens = tokenizer.encode(prompt_text)
    print(f"\n--- Prompt ({len(tokens)} tokens): {repr(prompt_text[:80])}...")

    for penalty in penalties:
        engine.reset_state()
        try:
            result = engine.generate(
                prompt_ids=tokens,
                max_tokens=30,
                temperature=0.56,
                top_p=0.765,
                stop_tokens=[],
                somatic=None,
                repetition_penalty=penalty,
            )
            gen_ids = result.get("tokens", [])
            gen_text = tokenizer.decode(gen_ids)
            tps = result.get("tokens_per_sec", 0)
            print(f"  penalty={penalty:.1f}: {repr(gen_text[:80])} ({tps:.0f} tok/s)")
        except Exception as e:
            print(f"  penalty={penalty:.1f}: ERROR: {e}")

print("\n" + "=" * 80)
print("TEST 2: State accumulation (NO reset between generations)")
print("=" * 80)

engine.reset_state()  # Start fresh
for i, prompt_text in enumerate(test_prompts):
    tokens = tokenizer.encode(prompt_text)
    # DO NOT reset state between calls!
    try:
        result = engine.generate(
            prompt_ids=tokens,
            max_tokens=30,
            temperature=0.56 if i % 2 == 0 else 0.84,
            top_p=0.765 if i % 2 == 0 else 0.935,
            stop_tokens=[],
            somatic=None,
            repetition_penalty=1.3,
        )
        gen_ids = result.get("tokens", [])
        gen_text = tokenizer.decode(gen_ids)
        tps = result.get("tokens_per_sec", 0)
        print(f"  [{i}] {repr(prompt_text[:50])}... → {repr(gen_text[:80])}")
    except Exception as e:
        print(f"  [{i}] ERROR: {e}")

print("\n" + "=" * 80)
print("TEST 3: State accumulation WITH reset between generations")
print("=" * 80)

for i, prompt_text in enumerate(test_prompts):
    tokens = tokenizer.encode(prompt_text)
    engine.reset_state()  # Reset EVERY time
    try:
        result = engine.generate(
            prompt_ids=tokens,
            max_tokens=30,
            temperature=0.56 if i % 2 == 0 else 0.84,
            top_p=0.765 if i % 2 == 0 else 0.935,
            stop_tokens=[],
            somatic=None,
            repetition_penalty=1.3,
        )
        gen_ids = result.get("tokens", [])
        gen_text = tokenizer.decode(gen_ids)
        tps = result.get("tokens_per_sec", 0)
        print(f"  [{i}] {repr(prompt_text[:50])}... → {repr(gen_text[:80])}")
    except Exception as e:
        print(f"  [{i}] ERROR: {e}")

print("\n[DIAG] Done!")
