"""Test GPU portal speed after optimization.

Tests:
1. skip_diagnostics=True (eliminates 96 GPU sync stalls per token)
2. Layer-level FP16 warm cache (batch dequant per layer)
3. Persistent FP16 swap (dequant once at generation start, pure cuBLAS during gen)
"""
import os, sys, time, json
os.environ["PYTHONIOENCODING"] = "utf-8"

sys.path.insert(0, r"F:\Sandbox\failure_factory\akashic_v2")

from infrastructure.gpu_portal_gate import GPUPortalGate

MODEL = r"F:\Sandbox\failure_factory\akashic_v2\fairies\P30_Cognition\AkashicInferenceFairy\models\rwkv7-g1d-7.2b-Q4_0.portal"

def main():
    print("=" * 60)
    print("GPU Portal Speed Test (persistent FP16 swap)")
    print("=" * 60)

    gate = GPUPortalGate(
        portal_file=MODEL,
        python_exe=r"C:/Users/Ace/AppData/Local/Programs/Python/Python312/python.exe",
        token_budget=1_000_000,
        max_charge=10000.0,
        recharge_rate=100.0,
        flops_budget=50_000_000_000,
    )

    print("\n[1] Opening portal...")
    t0 = time.perf_counter()
    ok = gate.open()
    t_boot = time.perf_counter() - t0
    print(f"    Boot: {'OK' if ok else 'FAILED'} in {t_boot:.1f}s")
    if not ok:
        return

    # Warm-up run (first token is always slower — CUDA JIT, caching allocator)
    print("\n[2] Warm-up (5 tokens)...")
    warmup = gate.generate(prompt="Hello", max_tokens=5)
    print(f"    Warm-up result: {warmup.get('status') if warmup else 'None'} "
          f"({warmup.get('tokens_generated', 0) if warmup else 0} tokens)")

    # Benchmark: 30 tokens
    print("\n[3] Benchmark: 30 tokens from 'The meaning of consciousness is'")
    t0 = time.perf_counter()
    result = gate.generate(
        prompt="The meaning of consciousness is",
        max_tokens=30,
        temperature=0.9,
        top_p=0.5,
    )
    t_gen = time.perf_counter() - t0

    if result and result.get("text"):
        n_tok = result.get("tokens_generated", 0)
        tok_s = n_tok / t_gen if t_gen > 0 else 0
        print(f"    Tokens: {n_tok}")
        print(f"    Time:   {t_gen:.2f}s")
        print(f"    Speed:  {tok_s:.1f} tok/s")
        print(f"    Text:   {result['text'][:200].encode('ascii', 'replace').decode()}")
    else:
        print(f"    FAILED: {result}")

    # Benchmark: 100 tokens (longer run for stable measurement)
    print("\n[4] Benchmark: 100 tokens")
    t0 = time.perf_counter()
    result = gate.generate(
        prompt="Once upon a time in a digital realm",
        max_tokens=100,
        temperature=0.9,
        top_p=0.5,
    )
    t_gen = time.perf_counter() - t0

    if result and result.get("text"):
        n_tok = result.get("tokens_generated", 0)
        tok_s = n_tok / t_gen if t_gen > 0 else 0
        print(f"    Tokens: {n_tok}")
        print(f"    Time:   {t_gen:.2f}s")
        print(f"    Speed:  {tok_s:.1f} tok/s")
        print(f"    Text:   {result['text'][:300].encode('ascii', 'replace').decode()}")
    else:
        print(f"    FAILED: {result}")

    gate.close()
    print("\n" + "=" * 60)
    print("Done.")

if __name__ == "__main__":
    main()
