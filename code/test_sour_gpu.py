"""Quick test: SourpatchesFarm with GPUPortalGate."""
import os, sys, time
os.environ["PYTHONIOENCODING"] = "utf-8"

sys.path.insert(0, r"F:\Sandbox\failure_factory\akashic_v2")
# Ensure the Sourpatches directory is importable
sys.path.insert(0, r"F:\Sandbox\failure_factory\akashic_v2\fairies\P50_Persona\Waking Minds\Sourpatches")

from sourpatches_farm import SourpatchesFarm

def main():
    print("=" * 60)
    print("SourpatchesFarm GPU Portal Test")
    print("=" * 60)

    t0 = time.perf_counter()
    farm = SourpatchesFarm(use_gpu=True)
    t_boot = time.perf_counter() - t0
    print(f"\nBoot: {t_boot:.1f}s, available={farm.available}")

    if not farm.available:
        print("FAILED — farm not available")
        return

    # Test thought generation
    print("\n[1] Generating thought...")
    t0 = time.perf_counter()
    thought = farm.generate_thought({
        "feeling": "curious",
        "energy": 0.8,
        "felt_sense": "warm awareness",
        "ethics": "Curiosity as the prime mover of evolution.",
        "cortex_concepts": ["consciousness", "warmth"],
    })
    t_thought = time.perf_counter() - t0
    print(f"    Time: {t_thought:.1f}s")
    print(f"    Result: {repr(thought[:120]) if thought else 'None'}")

    # Test speech generation
    print("\n[2] Generating speech...")
    t0 = time.perf_counter()
    speech = farm.generate_speech(
        "User: How are you feeling right now?\n\nAssistant:",
        max_tokens=50,
    )
    t_speech = time.perf_counter() - t0
    print(f"    Time: {t_speech:.1f}s")
    print(f"    Result: {repr(speech[:120]) if speech else 'None'}")

    # Status
    print("\n[3] Status:")
    status = farm.status()
    for k, v in status.items():
        if not isinstance(v, dict):
            print(f"    {k}: {v}")

    farm.close()
    print("\n" + "=" * 60)
    print("Done.")

if __name__ == "__main__":
    main()
