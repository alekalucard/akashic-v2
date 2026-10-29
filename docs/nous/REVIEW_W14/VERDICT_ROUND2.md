# W14 refutation review — round 2 verdict

Recorded by the parent session from the reviewer's message (reviewer session `session_01WZwX7k4cYehgwhWTfbU7TX`, read-only by
its brief, so it did not commit). Text as sent.

Diff: origin/nous/w2-return-to-sender..origin/nous/w14-no-double -- code/. Overall: NOT refuted. One OPEN test gap (lib.rs/PyO3).

| # | check | verdict | evidence |
|---|---|---|---|
| 1a | run_w14_matrix.py | HOLDS | both CONTROLs FAIL (5F+1E, 6F+1E), FIX PASS 8/8, M1-M10 all FAIL |
| 1b | run_w2_matrix.py (byte-identical-off vs main) | HOLDS | CONTROL FAIL (18), FIX PASS 21/21, all 12 mutants FAIL |
| 1c | cargo test --lib | HOLDS | 31 pass, only the 2 known main failures; w14_parity_table ok |
| 1d | test_w14 vs main / w2 copies | HOLDS | main 5F+2E, w2 5F+1E |
| 2 | switch default unset/""/"0"/" 1"/"true" OFF | HOLDS | _python_fallback.py:843 == "1"; test_only_exact_1 |
| 3 | other copies of lookup | HOLDS | only _python_fallback.py:1106,1116; bridge lookup picks pools only |
| 4 | OFF behaviour (order, metrics, CRLF) | HOLDS | TestSwitchOff identical to w2 base for RTS x PAD; CRLF kept |
| 5a | table _doc | HOLDS (wording) | every cell matches --table; bridge R14/15/16/19 = 0 confirmed |
| 5b | Rust test = USING_RUST path | OPEN | mirrors lib.rs:123-176 at TopicBus level; lib.rs never exercised |
| 6 | own mutants | OPEN (lib.rs) | caught: wants without ".", read-at-publish, high-volume skip. SURVIVE: lib.rs:147 intent->None, lib.rs:175 ignore pool |

Findings:
1. [OPEN] No test goes through lib.rs/PyO3. Either add a maturin/pyo3 test that drives _BaseTopicPostal with USING_RUST=True, or reword the claim as "TopicBus calls equivalent to lib.rs".
2. [OPEN, wording] The _doc's "STILL DIFFERS under every combo" list doesn't name the rows that differ only under some combos. With NO_DOUBLE off: R05/06/17/18. With PREFIX_ANY_DEPTH off: R08-R10/R21, plus core R14/R19.
3. [OPEN, scope] The bridge's own handler-to-pool lookup (tensor_fabric.py) is untested by W14. Harmless today.
4. [OPEN, disclosed] The pool_router CRITICAL fast path is not modelled.
