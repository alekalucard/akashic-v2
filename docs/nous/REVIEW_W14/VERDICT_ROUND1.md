# W14 review — round 1 verdict

Recorded by the parent session from the reviewer's message (reviewer session `session_01WZwX7nbSkDo3VS3M4o9sTK`, read-only by
its brief, so it did not commit). Text as sent. Round 2 (after the builder's fixes) is in VERDICT_ROUND2.md on nous/w14-review-r2.

Reviewed: `git diff origin/nous/w2-return-to-sender origin/nous/w14-no-double` (commit 26ed44cb).
Status: core fix NOT refuted; suite has coverage gaps; "why rows differ" is undocumented.

| # | check | verdict | evidence |
|---|---|---|---|
| 1a | run_w14_matrix.py | HOLDS | both CONTROLs FAIL, FIX PASS (7 tests), M1–M6 FAIL |
| 1b | run_w2_matrix.py (byte-identical-when-off) | HOLDS | FIX PASS 21 tests; control + M1–M12 FAIL |
| 1c | cargo test --lib | HOLDS | 31 pass / 1 ignored; only the 2 pre-existing failures (envelope.rs:176, topic_bus.rs:530); w14_parity_table ok |
| 1d | test_w14_no_double.py vs main / W2 copies | HOLDS | main: 6F+1E of 7; W2: 5F+1E of 7 (only the self-compare test passes) |
| 2 | switch default | HOLDS | _python_fallback.py:843; checked by hand: unset, "", "0", " 1", "true" → False |
| 3 | other copies / other subscriber-list builders | HOLDS | 2-level lookup only at _python_fallback.py:1112-1118; pool_router.py:256 is exact-topic only (no double); tensor_fabric.py:397-416 picks one pool per handler |
| 4 | behaviour with switch OFF | HOLDS | diff = one attribute + `and not self._no_double` (:1115); CRLF 1734/1734 → 1739/1739; OFF enqueue sequence identical to W2, order included |
| 5a | parity-table values | HOLDS | measured `--table` matches the JSON; core with both prefix switches on = Rust column on every row |
| 5b | "say which rows differ and why" | OPEN | w14_parity_table.json:2-8 and the commit message give no reason; bridge R14/R15/R16/R19 differ from Rust under every switch combo |
| 5c | Rust test = USING_RUST path | HOLDS | subscribe_filtered(base,…,0,1,Some(intent)) + publish_routed(base,…) match lib.rs:130-146, 174-175 |
| 6 | own mutants | REFUTED (test gaps) | X4, X5, X6 pass both suites; X7 passes the W14 suite (see below) |

## Mutants
| id | mutant | W14 suite | W2 suite |
|---|---|---|---|
| X1 | de-duplicate subs by identity | pass (equivalent fix) | — |
| X2 | `not (no_double and len(parts)>=3)` | pass (equivalent fix) | — |
| X3 | read env at publish time | FAIL (caught) | — |
| X4 | switch on drops base-level subs for 5+ segment letters | pass — NOT caught | pass — NOT caught |
| X5 | new `_no_double` line written with LF | pass — NOT caught | pass — NOT caught |
| X6 | new metrics key on the OFF path | pass — NOT caught | pass — NOT caught |
| X7 | prefix-any-depth loop capped at depth 4 | pass — NOT caught | unknown: run printed no FIX line |

## Findings to fix
1. Document why the remaining rows differ: `_BaseTopicPostal.publish` (tensor_fabric.py:376-378) only looks at exact-intent and base-topic handlers on its own bridge. When it finds one, it delivers directly and never calls `PostalCore.publish`, so in Python mode the 2-level and prefix subscribers in R14/R15/R16/R19 get 0 deliveries whatever the switches. NO_DOUBLE only helps letters that fall through to the core.
2. Add table rows for the gaps: a base subscriber with a 5+ segment letter (catches X4), and a 6+ segment letter (catches X7).
3. Assert CRLF count == line count (catches X5).
4. Compare `pc._metrics` OFF vs the original (catches X6).
5. The pool router (server.py:7775, critical topics, exact-topic only) is not in the table; it doesn't double-deliver, but the table should note it as a separate gap from Rust.

(Builder's response, per its final report and round 2: all four suite gaps were closed as mutants M7-M10 and the reason for the bridge rows was documented; round 2 confirms them caught.)
