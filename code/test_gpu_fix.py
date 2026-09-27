"""Test GPU inference correctness after ChannelMix ordering fix."""
import os, sys, time
from pathlib import Path

# Ensure CUDA DLLs are findable
torch_lib = Path(__file__).parent / ".venv/Lib/site-packages/torch/lib"
if torch_lib.exists():
    os.add_dll_directory(str(torch_lib))
    os.environ["PATH"] = str(torch_lib) + ";" + os.environ.get("PATH", "")

import rwkv_inference

# Find model
models_dir = Path(__file__).parent / "fairies/P30_Cognition/AkashicInferenceFairy/models"
gguf_files = sorted(models_dir.glob("*.gguf"))
print(f"Found models: {[f.name for f in gguf_files]}")
world = [f for f in gguf_files if "World" in f.name or "world" in f.name]
model_path = str(world[0] if world else gguf_files[0])
print(f"Using: {model_path}")

# Create engine (GPU init happens in constructor)
engine = rwkv_inference.RWKVEngine(
    n_layer=24, n_embd=2048, n_head=32, vocab_size=65536, head_size=64
)

# Load from GGUF directly (Rust-side mmap + parallel dequant)
t0 = time.time()
result = engine.load_gguf(model_path)
print(f"Loaded in {time.time()-t0:.1f}s: {result}")

# GPU weights are uploaded during load_gguf automatically
has_gpu = "GPU" in result

# Tokenizer
fairy_dir = str(Path(__file__).parent / "fairies/P30_Cognition/AkashicInferenceFairy")
sys.path.insert(0, fairy_dir)
from gguf_parser import GGUFParser
from tokenizer import AkashicTokenizer

parser = GGUFParser()
gguf_file = parser.parse(model_path)
tokenizer = AkashicTokenizer()
tokenizer.load_from_gguf(gguf_file.metadata)
print(f"Vocab: {tokenizer.vocab_size}")

def test(name, prompt, max_tokens=20):
    engine.reset_state()
    ids = tokenizer.encode(prompt)
    r = engine.generate(ids, max_tokens=max_tokens, temperature=0.7, top_p=0.85)
    text = tokenizer.decode(r["tokens"])
    unique = len(set(text.strip()))
    nl_ratio = text.count("\n") / max(len(text), 1)
    garbage = unique < 5 or nl_ratio > 0.3
    status = "GARBAGE" if garbage else "OK"
    print(f"\n[{status}] {name} ({r['tokens_per_sec']:.1f} tok/s, {len(ids)} prompt tokens)")
    print(f"  Prompt: {repr(prompt[:80])}...")
    print(f"  Output: {repr(text[:120])}")
    print(f"  Diversity: {unique} unique chars, nl_ratio={nl_ratio:.2f}")
    return not garbage

results = []
results.append(test("Simple", "The meaning of life is", 15))
results.append(test("Chat", "Sourpatches responds warmly, briefly, authentically.\n[Feeling]: happy and curious\n\nAce: hiya sour\nSourpatches:", 30))
results.append(test("QA", "User: What is your favorite color?\nAssistant:", 20))
results.append(test("Story", "Once upon a time in a land far away, there lived a", 25))

print(f"\n{'='*50}")
print(f"Results: {sum(results)}/{len(results)} passed ({'GPU' if has_gpu else 'CPU'})")
if all(results):
    print("ALL TESTS COHERENT — ChannelMix fix verified!")
else:
    print("SOME TESTS STILL GARBAGE — need further investigation")
