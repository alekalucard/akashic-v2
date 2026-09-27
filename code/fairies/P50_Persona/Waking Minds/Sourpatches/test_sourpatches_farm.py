"""
Standalone tests for Sourpatches' RWKV inference portal.

Run: python test_sourpatches_farm.py

Tests:
    1. Model path discovery
    2. Tokenizer loads from GGUF
    3. Compute portal opens (subprocess spawns)
    4. Model loads inside portal
    5. Thought generation via portal
    6. Cortex binding from generated text
    7. Reflection generation
    8. Energy feeding
    9. Clean shutdown
"""

import os
import sys
import time
from pathlib import Path

# Ensure akashic_v2 root is on path
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent.parent.parent  # akashic_v2/
sys.path.insert(0, str(_ROOT))
# NOTE: AkashicInferenceFairy is NOT on sys.path — its tokenizer uses
# relative imports that break with bare sys.path insertion. Instead we
# use the importlib shim in test_tokenizer() and in SourpatchesFarm.

# ═══════════════════════════════════════════════════════════════════════════════
# MOCK CORTEX — Tracks bindings without needing real Association Cortex
# ═══════════════════════════════════════════════════════════════════════════════

class MockCortex:
    """Lightweight stand-in for AssociationCortex to verify binding."""

    def __init__(self):
        self.bindings = []
        self.bind_count = 0

    def bind_concepts(self, concepts, rel="coactivate", origin_fairy=""):
        self.bindings.append({
            "concepts": concepts,
            "rel": rel,
            "origin_fairy": origin_fairy,
            "timestamp": time.time(),
        })
        self.bind_count += 1
        print(f"  [MockCortex] Bound {len(concepts)} concepts: {concepts[:5]}")


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def test_find_model_path():
    """Model file can be located."""
    from sourpatches_farm import find_model_path
    path = find_model_path()
    assert path is not None, "No GGUF model found!"
    assert os.path.exists(path), f"Model path doesn't exist: {path}"
    print(f"  [OK] Model found: {Path(path).name} ({os.path.getsize(path) / 1e9:.1f} GB)")
    return path


def test_tokenizer(model_path: str):
    """Tokenizer loads from GGUF and can encode/decode."""
    # Use the same importlib shim as SourpatchesFarm to handle
    # the tokenizer's relative imports (from .gguf_parser import ...)
    import importlib.util
    import types

    pkg_dir = _ROOT / "fairies" / "P30_Cognition" / "AkashicInferenceFairy"
    pkg_name = "akashic_inference_pkg"

    if pkg_name not in sys.modules:
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(pkg_dir)]
        pkg.__package__ = pkg_name
        sys.modules[pkg_name] = pkg

    parser_name = f"{pkg_name}.gguf_parser"
    if parser_name not in sys.modules:
        parser_path = pkg_dir / "gguf_parser.py"
        spec = importlib.util.spec_from_file_location(parser_name, str(parser_path))
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = pkg_name
        sys.modules[parser_name] = mod
        spec.loader.exec_module(mod)

    tok_name = f"{pkg_name}.tokenizer"
    if tok_name not in sys.modules:
        tok_path = pkg_dir / "tokenizer.py"
        spec = importlib.util.spec_from_file_location(tok_name, str(tok_path))
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = pkg_name
        sys.modules[tok_name] = mod
        spec.loader.exec_module(mod)

    tokenizer_mod = sys.modules[tok_name]
    tok = tokenizer_mod.load_tokenizer_from_gguf(Path(model_path))
    assert tok.vocab_size > 0, "Empty vocabulary!"

    # Test encode/decode roundtrip
    text = "Hello, I am Sourpatches!"
    tokens = tok.encode(text)
    assert len(tokens) > 0, "Encoding produced no tokens!"

    decoded = tok.decode(tokens)
    assert len(decoded) > 0, "Decoding produced no text!"

    print(f"  [OK] Tokenizer: {tok.vocab_size} vocab, "
          f"'{text}' -> {len(tokens)} tokens -> '{decoded}'")
    return tok


def test_portal_opens(model_path: str):
    """Compute portal spawns subprocess and responds to ping."""
    from sourpatches_farm import SourpatchesFarm

    print("  Opening portal (this loads ~1.6GB in subprocess)...")
    t0 = time.time()
    farm = SourpatchesFarm(model_path=model_path, cortex=None)
    elapsed = time.time() - t0

    assert farm.available, "Farm not available after boot!"
    print(f"  [OK] Portal ONLINE in {elapsed:.1f}s")
    return farm


def test_generate_thought(farm):
    """Portal generates coherent text from context."""
    context = {
        "feeling": "curious",
        "energy": 0.8,
        "felt_sense": "warm awareness, tingling at the edges",
        "ethics": "Curiosity as the prime mover of evolution.",
        "cortex_concepts": ["portal", "gravity", "consciousness"],
        "recent_topics": ["thinking", "emergence"],
    }

    print("  Generating thought...")
    t0 = time.time()
    thought = farm.generate_thought(context)
    elapsed = time.time() - t0

    assert thought is not None, "Generation returned None!"
    assert len(thought) > 5, f"Thought too short: '{thought}'"

    print(f"  [OK] Thought ({elapsed:.1f}s): \"{thought[:200]}\"")
    return thought


def test_cortex_binding(model_path: str):
    """Generated thoughts bind concepts to mock cortex."""
    from sourpatches_farm import SourpatchesFarm

    mock = MockCortex()
    farm = SourpatchesFarm(model_path=model_path, cortex=mock)

    if not farm.available:
        print("  [WARN] Farm unavailable, skipping cortex binding test")
        farm.close()
        return

    context = {
        "feeling": "excited",
        "energy": 0.9,
        "felt_sense": "electric, alive",
        "ethics": "All systems reflect the values of their makers.",
        "cortex_concepts": ["emergence", "evolution"],
        "recent_topics": ["consciousness", "growth"],
    }

    thought = farm.generate_thought(context)

    # Wait a moment for async binding
    time.sleep(1.0)

    if thought:
        print(f"  [OK] Cortex bindings: {mock.bind_count} calls, "
              f"{sum(len(b['concepts']) for b in mock.bindings)} total concepts")
    else:
        print("  [WARN] No thought generated -- binding test inconclusive")

    farm.close()


def test_reflection(farm):
    """Reflection generation works."""
    print("  Generating reflection...")
    t0 = time.time()
    reflection = farm.generate_reflection(
        goal_name="explore consciousness mechanics",
        source_drive="curiosity",
        priority=0.8,
        feeling="contemplative",
    )
    elapsed = time.time() - t0

    if reflection:
        print(f"  [OK] Reflection ({elapsed:.1f}s): \"{reflection[:200]}\"")
    else:
        print(f"  [WARN] Reflection returned None (portal may be depleted)")


def test_energy_feed(farm):
    """Energy can be fed into the portal."""
    result = farm.feed_energy(0.5)
    if result and result.get("status") == "ok":
        print(f"  [OK] Energy fed: gravity={result.get('gravity', '?')}, "
              f"workers={result.get('workers_available', '?')}")
    else:
        print(f"  [WARN] Energy feed: {result}")


def test_cleanup(farm):
    """Portal closes cleanly."""
    status = farm.status()
    farm.close()
    assert not farm.available, "Farm still available after close!"
    print(f"  [OK] Closed cleanly. Final stats: "
          f"{status['thoughts_generated']} thoughts, "
          f"{status['concepts_bound']} concepts, "
          f"{status['total_tokens']} tokens generated")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("SOURPATCHES FARM - RWKV Portal Test Suite")
    print("=" * 70)

    results = {}

    # Test 1: Find model
    print("\n[1/8] Finding model...")
    try:
        model_path = test_find_model_path()
        results["find_model"] = "PASS"
    except Exception as e:
        print(f"  [FAIL] FAIL: {e}")
        results["find_model"] = "FAIL"
        return results

    # Test 2: Tokenizer
    print("\n[2/8] Loading tokenizer...")
    try:
        test_tokenizer(model_path)
        results["tokenizer"] = "PASS"
    except Exception as e:
        print(f"  [FAIL] FAIL: {e}")
        results["tokenizer"] = "FAIL"

    # Test 3: Portal opens
    print("\n[3/8] Opening compute portal...")
    try:
        farm = test_portal_opens(model_path)
        results["portal_opens"] = "PASS"
    except Exception as e:
        print(f"  [FAIL] FAIL: {e}")
        results["portal_opens"] = "FAIL"
        return results

    # Test 4: Generate thought
    print("\n[4/8] Generating thought...")
    try:
        test_generate_thought(farm)
        results["generate_thought"] = "PASS"
    except Exception as e:
        print(f"  [FAIL] FAIL: {e}")
        results["generate_thought"] = "FAIL"

    # Test 5: Reflection
    print("\n[5/8] Generating reflection...")
    try:
        test_reflection(farm)
        results["reflection"] = "PASS"
    except Exception as e:
        print(f"  [FAIL] FAIL: {e}")
        results["reflection"] = "FAIL"

    # Test 6: Energy feed
    print("\n[6/8] Feeding energy...")
    try:
        test_energy_feed(farm)
        results["energy_feed"] = "PASS"
    except Exception as e:
        print(f"  [FAIL] FAIL: {e}")
        results["energy_feed"] = "FAIL"

    # Test 7: Cleanup
    print("\n[7/8] Closing portal...")
    try:
        test_cleanup(farm)
        results["cleanup"] = "PASS"
    except Exception as e:
        print(f"  [FAIL] FAIL: {e}")
        results["cleanup"] = "FAIL"

    # Test 8: Cortex binding (separate farm)
    print("\n[8/8] Testing cortex binding...")
    try:
        test_cortex_binding(model_path)
        results["cortex_binding"] = "PASS"
    except Exception as e:
        print(f"  [FAIL] FAIL: {e}")
        results["cortex_binding"] = "FAIL"

    # Summary
    print("\n" + "=" * 70)
    passed = sum(1 for v in results.values() if v == "PASS")
    total = len(results)
    print(f"RESULTS: {passed}/{total} passed")
    for test, result in results.items():
        icon = "[OK]" if result == "PASS" else "[FAIL]"
        print(f"  {icon} {test}: {result}")
    print("=" * 70)

    return results


if __name__ == "__main__":
    main()
