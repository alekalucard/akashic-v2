"""Slice 5 smoke test — exercises the council.verdict → [QUESTION] seeding loop.

Tests all four gates:
  1. confidence threshold (top_confidence < 0.5 rejected)
  2. noise next_step filter ("observe more" rejected)
  3. dedup against existing scratchpad questions
  4. rate-limit (3 hops/30s window cap)

Plus the formatter translation map.

Doesn't need full WMH boot — uses __new__ to skip __init__, then calls
methods directly with a stub scratchpad + postal hub.
"""

import sys
import os
import time
from types import SimpleNamespace

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import only the WMH class — skip boot()
from fairies.P30_Cognition.cognition.working_memory_hub_fairy import WorkingMemoryHubFairy


class StubScratchpad:
    def __init__(self):
        self.entries = []
    def write(self, text, tier="hot"):
        self.entries.append((text, tier))
    def get_questions(self):
        return [e[0] for e in self.entries if e[0].startswith("[QUESTION]")]


class StubPostalHub:
    def __init__(self):
        self.published = []
    def publish(self, topic, payload):
        self.published.append((topic, payload))
    def subscribe(self, topic, handler):
        pass


def make_envelope(payload):
    return SimpleNamespace(payload=payload)


def make_wmh():
    """Skip __init__, create empty instance, attach stubs."""
    wmh = WorkingMemoryHubFairy.__new__(WorkingMemoryHubFairy)
    wmh._scratchpad = StubScratchpad()
    wmh.post = StubPostalHub()
    return wmh


def test_format_next_step():
    print("[TEST 1] Formatter translation map")
    wmh = make_wmh()
    f = wmh._format_next_step_as_question

    cases = [
        ("act on observation", "What action does this observation call for right now?"),
        ("ground in body, then re-ask", "What does the body know about this that the mind has missed?"),
        ("build on: emotion grounds the inference", "How does 'emotion grounds the inference' extend further?"),
        ("the world is curving", "What if the world is curving?"),
        ("does this shape repeat?", "does this shape repeat?"),
        ("", ""),
        ("build on:", ""),
    ]
    fails = 0
    for inp, expected in cases:
        got = f(inp)
        ok = (got == expected)
        marker = "OK" if ok else "FAIL"
        print(f"  [{marker}] '{inp}' -> '{got}' (expected '{expected}')")
        if not ok:
            fails += 1
    return fails == 0


def test_high_confidence_seeds():
    print("[TEST 2] High-confidence verdict seeds [QUESTION]")
    wmh = make_wmh()
    wmh._on_council_verdict(make_envelope({
        "question_id": "q1",
        "next_step": "build on: emotion is gravity",
        "top_confidence": 0.78,
        "top_seat": "somatic",
    }))
    questions = wmh._scratchpad.get_questions()
    cog_q_pubs = [p for p in wmh.post.published if p[0] == "cognition.question"]
    print(f"  scratchpad questions={len(questions)} cognition.question pubs={len(cog_q_pubs)}")
    if questions:
        print(f"    -> {questions[0]}")
    ok = (len(questions) == 1 and len(cog_q_pubs) == 1)
    print(f"  [{'OK' if ok else 'FAIL'}]")
    return ok


def test_low_confidence_rejected():
    print("[TEST 3] Low-confidence verdict (0.3) rejected")
    wmh = make_wmh()
    wmh._on_council_verdict(make_envelope({
        "question_id": "q2",
        "next_step": "build on: weak signal",
        "top_confidence": 0.3,
    }))
    ok = (len(wmh._scratchpad.entries) == 0)
    print(f"  scratchpad entries={len(wmh._scratchpad.entries)} (expected 0)")
    print(f"  [{'OK' if ok else 'FAIL'}]")
    return ok


def test_noise_next_step_rejected():
    print("[TEST 4] Noise next_step ('observe more') rejected")
    wmh = make_wmh()
    wmh._on_council_verdict(make_envelope({
        "question_id": "q3",
        "next_step": "observe more",
        "top_confidence": 0.85,
    }))
    wmh._on_council_verdict(make_envelope({
        "question_id": "q4",
        "next_step": "explore the question more",
        "top_confidence": 0.85,
    }))
    wmh._on_council_verdict(make_envelope({
        "question_id": "q5",
        "next_step": "answer the question",
        "top_confidence": 0.85,
    }))
    ok = (len(wmh._scratchpad.entries) == 0)
    print(f"  scratchpad entries={len(wmh._scratchpad.entries)} (expected 0)")
    print(f"  [{'OK' if ok else 'FAIL'}]")
    return ok


def test_dedup_against_existing_questions():
    print("[TEST 5] Dedup against existing scratchpad [QUESTION]")
    wmh = make_wmh()
    # Pre-seed with the question that would be generated
    wmh._scratchpad.write("[QUESTION] What if the world is curving?", tier="hot")
    wmh._on_council_verdict(make_envelope({
        "question_id": "q6",
        "next_step": "the world is curving",
        "top_confidence": 0.85,
    }))
    # Should still only have the original entry — verdict was deduped
    new_questions = [
        e for e in wmh._scratchpad.entries
        if e[0] != "[QUESTION] What if the world is curving?"
    ]
    ok = (len(new_questions) == 0)
    print(f"  total entries={len(wmh._scratchpad.entries)} new={len(new_questions)} (expected new=0)")
    print(f"  [{'OK' if ok else 'FAIL'}]")
    return ok


def test_rate_limit_3_hops():
    print("[TEST 6] Rate limit: 3 hops/30s window")
    wmh = make_wmh()
    for i in range(5):
        wmh._on_council_verdict(make_envelope({
            "question_id": f"q-rate-{i}",
            "next_step": f"build on: distinct topic {i}",
            "top_confidence": 0.8,
        }))
    questions = wmh._scratchpad.get_questions()
    ok = (len(questions) == 3)
    print(f"  questions seeded={len(questions)} (expected 3)")
    for q in questions:
        print(f"    -> {q}")
    print(f"  [{'OK' if ok else 'FAIL'}]")
    return ok


def test_empty_payload_no_crash():
    print("[TEST 7] Empty/malformed payload doesn't crash")
    wmh = make_wmh()
    try:
        wmh._on_council_verdict(make_envelope({}))
        wmh._on_council_verdict(make_envelope({"top_confidence": "not a number"}))
        wmh._on_council_verdict(None)
        wmh._on_council_verdict({"payload": {"next_step": "build on: ok", "top_confidence": 0.8}})
        ok = True
    except Exception as e:
        print(f"  CRASH: {e}")
        ok = False
    print(f"  [{'OK' if ok else 'FAIL'}]")
    return ok


def main():
    results = [
        ("formatter", test_format_next_step()),
        ("high_conf_seeds", test_high_confidence_seeds()),
        ("low_conf_rejected", test_low_confidence_rejected()),
        ("noise_rejected", test_noise_next_step_rejected()),
        ("dedup_existing", test_dedup_against_existing_questions()),
        ("rate_limit_3", test_rate_limit_3_hops()),
        ("malformed_safe", test_empty_payload_no_crash()),
    ]
    passed = sum(1 for (_, ok) in results if ok)
    total = len(results)
    print()
    print(f"=== Slice 5 smoke: {passed}/{total} passed ===")
    for name, ok in results:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
