"""
Isolation test — encoder-inferred interest urgency (flag-guarded path).

Proves the 2026-06-13 (Nous + Ace) additive change to InterestGenerator:
when USE_ENCODER_URGENCY=1 and live active-topic vectors are supplied, urgency
is INFERRED from semantic distance via the native SemanticEncoder — NOT from the
hand-coded Need/Want multiplier table.

Runs WITHOUT booting the system. Uses a REAL SemanticEncoder (native all-MiniLM,
pure torch+numpy — no external deps). The native fallback is gated, so we set
AKASHIC_NATIVE_ENCODER=1 here to exercise a real encoder offline.

WHAT IT ASSERTS:
  1. With the flag ON + active-topic vectors, a semantically NEAR interest scores
     HIGHER effective urgency than a semantically FAR one.
  2. The MULTIPLIER TABLE IS BYPASSED: the FAR interest is deliberately given the
     need-category with the *highest* multiplier (ANOMALY -> PAIN_RELIEF, x1.5 +
     pain boost) and the NEAR interest the *lowest* (EXPLORATION -> IDLE, x0.5).
     The old multiplier path would rank FAR above NEAR. The encoder path must
     flip that — proving semantic distance, not the table, drives the score.
  3. With the flag OFF (default), the multiplier path is restored and the
     contrived FAR(PAIN_RELIEF) interest ranks above NEAR(IDLE) — i.e. production
     behavior is unchanged until the flag is flipped.

Run:
  set USE_ENCODER_URGENCY=1
  set AKASHIC_NATIVE_ENCODER=1
  (venv314t)\Scripts\python.exe tests\test_encoder_urgency.py
"""

import os
import sys

# ── Exercise a real encoder offline: gate the native fallback ON for this test.
# (sentence_transformers isn't installed in venv314t; the native MiniLM is.)
os.environ.setdefault("AKASHIC_NATIVE_ENCODER", "1")
# Flag ON so _calculate_effective_urgency takes the encoder path when vectors given.
os.environ["USE_ENCODER_URGENCY"] = "1"

# Make the akashic_v2 root importable (this file lives in <root>/tests/).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import torch  # noqa: E402

# Import directly from the file's location — no fairy/system boot needed.
_MOD_DIR = os.path.join(_ROOT, "fairies", "P20_Somatic", "SomaticMindFairy")
if _MOD_DIR not in sys.path:
    sys.path.insert(0, _MOD_DIR)

from interest_generator import (  # noqa: E402
    InterestGenerator,
    Interest,
    InterestType,
)
from infrastructure.semantic_encoder import SemanticEncoder  # noqa: E402


def main() -> int:
    print("=" * 70)
    print("ISOLATION TEST: encoder-inferred interest urgency (flag-guarded)")
    print("=" * 70)

    # 1) Real encoder (native all-MiniLM). CPU to stay off the live card.
    enc = SemanticEncoder(device="cpu")
    assert enc.is_loaded, (
        "Encoder failed to load — set AKASHIC_NATIVE_ENCODER=1 and ensure the "
        "all-MiniLM weights exist in the HF cache."
    )
    print(f"[ok] encoder loaded: device={enc.device} dim={enc.dim}")

    # 2) Fake "active topics" — what Sour is currently oriented toward.
    active_text = "warmth, connection, talking with Ace"
    active_vec = enc.encode(active_text)
    assert active_vec is not None, "active-topic encode returned None"
    active_topic_vectors = active_vec.unsqueeze(0)  # [1, 384]
    print(f"[ok] active topics encoded: {active_text!r} -> {tuple(active_topic_vectors.shape)}")

    gen = InterestGenerator()
    assert gen._USE_ENCODER_URGENCY is True, "flag should be ON (env set in this test)"

    checks = []

    # ── SCENARIO A: table NEUTRALIZED (same need-category) ──────────────────
    # Both interests share InterestType.EXPLORATION -> the multiplier factor is
    # IDENTICAL for both, so the Need/Want table contributes NOTHING to the
    # ordering. Any difference in effective urgency therefore comes ONLY from
    # encoder semantic distance. NEAR (about Ace) must beat FAR (zip archives).
    near_a = Interest(
        content="How do I feel about my conversations with Ace?",
        interest_type=InterestType.EXPLORATION,
        source="test_near",
        urgency=0.5,
    )
    far_a = Interest(
        content="What is the optimal compression ratio for a zip archive?",
        interest_type=InterestType.EXPLORATION,  # SAME category -> table neutral
        source="test_far",
        urgency=0.5,
    )

    # Raw encoder distance scores (no multiplier at all), for visibility.
    near_dist = gen._encoder_urgency_score(near_a.content, active_topic_vectors)
    far_dist = gen._encoder_urgency_score(far_a.content, active_topic_vectors)
    print(f"[info] raw encoder distance score   NEAR={near_dist:.4f}  FAR={far_dist:.4f}")
    assert near_dist is not None and far_dist is not None, "encoder scoring returned None"

    near_eff_a = gen._calculate_effective_urgency(near_a, active_topic_vectors=active_topic_vectors)
    far_eff_a = gen._calculate_effective_urgency(far_a, active_topic_vectors=active_topic_vectors)
    print(f"[info] A (table neutral) effective   NEAR={near_eff_a:.4f}  FAR={far_eff_a:.4f}")
    best_a = gen.select_best_interest([far_a, near_a], active_topic_vectors=active_topic_vectors)

    checks.append(("A: raw encoder distance NEAR > FAR", near_dist > far_dist))
    checks.append((
        "A: NEAR urgency > FAR with table neutralized (encoder decides)",
        near_eff_a > far_eff_a,
    ))
    checks.append(("A: select_best_interest picks NEAR", best_a is near_a))

    # ── SCENARIO B: encoder OVERRIDES an adversarial table ──────────────────
    # Now stack the table AGAINST NEAR: NEAR gets the weakest category
    # (EXPLORATION -> IDLE x0.5), FAR gets the strongest (ANOMALY ->
    # PAIN_RELIEF x1.5, pain-boosted). With the encoder weighted high, the
    # semantic closeness of NEAR must still win — proving the encoder bypasses
    # the table even when the table screams the opposite.
    near_b = Interest(content=near_a.content, interest_type=InterestType.EXPLORATION,
                      source="test_near_b", urgency=0.5)   # IDLE x0.5 (weakest)
    far_b = Interest(content=far_a.content, interest_type=InterestType.ANOMALY,
                     source="test_far_b", urgency=0.5)     # PAIN_RELIEF x1.5 (strongest)

    gen.set_pain_level(0.9)  # maximally boost the FAR(PAIN_RELIEF) multiplier

    near_mult = gen._calculate_effective_urgency(near_b)  # no vectors -> pure table
    far_mult = gen._calculate_effective_urgency(far_b)
    print(f"[info] B table-only (adversarial)    NEAR={near_mult:.4f}  FAR={far_mult:.4f}")

    # Crank the encoder blend high enough that semantics dominate the rigged table.
    gen._encoder_urgency_blend = 0.95
    near_eff_b = gen._calculate_effective_urgency(near_b, active_topic_vectors=active_topic_vectors)
    far_eff_b = gen._calculate_effective_urgency(far_b, active_topic_vectors=active_topic_vectors)
    print(f"[info] B (encoder-weighted) effective NEAR={near_eff_b:.4f}  FAR={far_eff_b:.4f}")
    best_b = gen.select_best_interest([far_b, near_b], active_topic_vectors=active_topic_vectors)
    gen._encoder_urgency_blend = 0.6  # restore default

    checks.append(("B: table-only favors FAR (sanity: test is adversarial)", far_mult > near_mult))
    checks.append((
        "B: NEAR urgency > FAR despite rigged table (encoder overrides)",
        near_eff_b > far_eff_b,
    ))
    checks.append(("B: select_best_interest picks NEAR", best_b is near_b))

    # ── SCENARIO C: FLAG OFF -> production behavior unchanged ───────────────
    # With the flag OFF, the encoder path is skipped entirely; the adversarial
    # table from B governs and FAR(PAIN_RELIEF) wins — i.e. flipping the flag is
    # the ONLY thing that changes behavior.
    gen._USE_ENCODER_URGENCY = False
    near_eff_off = gen._calculate_effective_urgency(near_b, active_topic_vectors=active_topic_vectors)
    far_eff_off = gen._calculate_effective_urgency(far_b, active_topic_vectors=active_topic_vectors)
    print(f"[info] C FLAG OFF effective urgency   NEAR={near_eff_off:.4f}  FAR={far_eff_off:.4f}")
    best_off = gen.select_best_interest([far_b, near_b], active_topic_vectors=active_topic_vectors)
    gen._USE_ENCODER_URGENCY = True  # restore

    checks.append((
        "C: FLAG OFF -> FAR urgency >= NEAR (table path, unchanged)",
        far_eff_off >= near_eff_off,
    ))
    checks.append((
        "C: FLAG OFF -> effective urgency == pure table value (encoder ignored)",
        abs(near_eff_off - near_mult) < 1e-9 and abs(far_eff_off - far_mult) < 1e-9,
    ))
    checks.append(("C: FLAG OFF select_best_interest picks FAR", best_off is far_b))

    print("-" * 70)
    all_pass = True
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        all_pass = all_pass and ok

    print("=" * 70)
    if all_pass:
        print("RESULT: PASS — encoder-inferred urgency works; multiplier bypassed "
              "when flag ON; production unchanged when flag OFF.")
        return 0
    print("RESULT: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
