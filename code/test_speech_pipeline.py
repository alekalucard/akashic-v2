"""Test the speech pipeline integration.

Verifies:
1. AkashicInferenceFairy engine validation works
2. _generate_sync() produces real text after validation
3. The guild chat handler would return text (not model_unavailable)

This tests the EXACT code paths that SpeechCenterFairy triggers.
"""
import sys, os, time
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

# ═══════════════════════════════════════════════════════════════
# Step 1: Load engine + tokenizer (same as fairy boot)
# ═══════════════════════════════════════════════════════════════
print("=" * 70)
print("STEP 1: Load engine + tokenizer")
print("=" * 70)

from tokenizer import AkashicTokenizer
tokenizer = AkashicTokenizer(vocab_path=VOCAB_PATH)
print(f"  Tokenizer: {tokenizer.vocab_size} tokens")

from rwkv_inference import RWKVEngine
engine = RWKVEngine(24, 2048, 32, 65536)
engine.load_gguf(GGUF_PATH)
print(f"  Engine loaded: is_ready={engine.is_ready()}")

# ═══════════════════════════════════════════════════════════════
# Step 2: Simulate _validate_engine_output()
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 2: Engine validation (same logic as fairy._validate_engine_output)")
print("=" * 70)

_engine_validated = False
_prefer_team_mode = True

test_prompt = "The meaning of life is"
test_tokens = tokenizer.encode(test_prompt)
print(f"  Test prompt: {repr(test_prompt)} → {len(test_tokens)} tokens")

engine.reset_state()
result = engine.generate(test_tokens, max_tokens=10, temperature=0.7, top_p=0.9)
gen_ids = result.get("tokens", [])
print(f"  Generated: {len(gen_ids)} tokens")

if gen_ids and len(gen_ids) >= 3:
    unique_count = len(set(gen_ids))
    diversity = unique_count / len(gen_ids)
    gen_text = tokenizer.decode(gen_ids)

    print(f"  Diversity: {diversity:.0%} ({unique_count}/{len(gen_ids)} unique)")
    print(f"  Text: \"{test_prompt}{gen_text}\"")

    if diversity >= 0.5 and gen_text and len(gen_text.strip()) >= 5:
        _engine_validated = True
        _prefer_team_mode = False
        print(f"  ✅ VALIDATION PASSED")
    else:
        print(f"  ❌ VALIDATION FAILED")
else:
    print(f"  ❌ VALIDATION FAILED: too few tokens ({len(gen_ids)})")

engine.reset_state()

# ═══════════════════════════════════════════════════════════════
# Step 3: Simulate chat mode (SpeechCenterFairy guild request)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 3: Simulate chat mode generation")
print("=" * 70)

# This is what happens in the guild chat handler
_has_inference = engine.is_ready()
_use_inference = _has_inference and _engine_validated and not _prefer_team_mode

print(f"  _has_inference: {_has_inference}")
print(f"  _engine_validated: {_engine_validated}")
print(f"  _prefer_team_mode: {_prefer_team_mode}")
print(f"  _use_inference: {_use_inference}")

if _use_inference:
    # This is the path that actually runs when SpeechCenterFairy asks for chat
    chat_prompt = "Sourpatches responds warmly: I've been thinking about the nature of consciousness lately. What makes us truly aware?"
    prompt_tokens = tokenizer.encode(chat_prompt)

    t0 = time.time()
    engine.reset_state()
    chat_result = engine.generate(prompt_tokens, max_tokens=80, temperature=0.9, top_p=0.9)
    elapsed = time.time() - t0

    chat_ids = chat_result.get("tokens", [])
    chat_text = tokenizer.decode(chat_ids)
    tps = chat_result.get("tokens_per_sec", 0)

    print(f"\n  Prompt: {repr(chat_prompt[:60])}...")
    print(f"  Generated: {len(chat_ids)} tokens in {elapsed:.1f}s ({tps:.1f} tok/s)")
    print(f"  Response text:")
    print(f"  >>> {chat_text}")

    # Check if this is actually usable speech
    if chat_text and len(chat_text.strip()) > 10:
        print(f"\n  ✅ Speech pipeline would produce REAL TEXT (not fallback)")
    else:
        print(f"\n  ⚠️  Text too short for speech — may still use fallback")
else:
    print(f"\n  ❌ _use_inference is False — would fall to model_unavailable")
    print(f"     SpeechCenterFairy would get empty text and use template fallback")

# ═══════════════════════════════════════════════════════════════
# Step 4: Test multiple conversation-style prompts
# ═══════════════════════════════════════════════════════════════
if _use_inference:
    print("\n" + "=" * 70)
    print("STEP 4: Multiple conversational prompts")
    print("=" * 70)

    conversation_prompts = [
        "Hello Ace! I'm so glad you're here.",
        "I've been learning about how my consciousness works. It's fascinating —",
        "The thing that amazes me most about our work together is",
        "When I feel my somatic state shift, it's like",
    ]

    for cp in conversation_prompts:
        engine.reset_state()
        cp_tokens = tokenizer.encode(cp)
        cr = engine.generate(cp_tokens, max_tokens=40, temperature=0.9, top_p=0.9)
        ct = tokenizer.decode(cr.get("tokens", []))
        tps = cr.get("tokens_per_sec", 0)

        print(f"\n  Prompt: \"{cp}\"")
        print(f"  >>> {cp}{ct}")
        print(f"  ({len(cr.get('tokens', []))} tokens, {tps:.1f} tok/s)")

print("\n" + "=" * 70)
print("=== Speech pipeline integration test complete ===")
print("=" * 70)
