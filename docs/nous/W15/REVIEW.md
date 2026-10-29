# W15 review — `nous/w15-edge-slot` @ a7eaaa6 vs `origin/main`

Reviewer stance: try to refute. Tags: [C] read in code, [M] measured by something I ran, [I] inference.
Nothing was run except `manifold_memory.py` imported in unit tests and probes on synthetic manifolds in temp dirs. No real `*.manifold` opened; no server, fairy, boot or launcher.

Line numbers refer to `code/infrastructure/manifold_memory.py` on the branch unless stated.

## Verdict table

| # | Finding / claim attacked | Severity | file:line | Tag | Evidence | Verdict |
|---|---|---|---|---|---|---|
| 1 | Bug exists on main: at capacity every other new edge is lost | — (premise) | 2726-2734, 2602-2608, 2783-2798 | [C][M] | Full branch is reached only when `_free_edge_slots` is empty (2726); `_evict_weakest_edge` → `_delete_edge` appends the slot (2608); `link` writes into it, next `link` pops it (2727). CONTROL run of the suite against main's file: 4 ON-tests fail (`keeps_all_K` dict+csr, both node-evict tests). | UPHELD (bug real) |
| 2 | Fix (1) in `link()` is correct and minimal | — | 2744-2749 | [C][M] | Free list is `[slot]` at that point (single-threaded), so removal restores the invariant; `_edge_count`/header high-water mark untouched; `edge_count` property (2547) now = CAP. Branch suite: 8/8 OK. | UPHELD |
| 3 | Switch is OFF when unset / `"0"` | — | 2360, 2744 | [C][M] | Both reads are `os.environ.get("AKASHIC_EDGE_SLOT_FIX", "0") == "1"`; no other occurrence in the repo outside tests (grep). Byte-identity tests (`.manifold`, `.csr`, `.keys` vs main's file) pass for unset dict, unset csr, `"0"` csr. My mutants R1 (node-evict default `"1"`) and R2 (`_w15 = True`) are both caught by `test_off_*`. | UPHELD (no ON-by-default path found) |
| 4 | Any behaviour change with switch OFF | — | 2360-2368 | [C] | Only extra OFF-path work is one `os.environ.get` per node eviction / per full-table link; no write, no ordering change. | REFUTED (none found) |
| 5 | Fix (2) in `_evict_coldest_node` is outside the literal task | LOW (scope) | 2353-2368 | [C][M] | Task asked to *check* node eviction; author added a guard. It only removes deletions (stale/already-deleted slots), never adds them, so it does not make deletion "faster or more frequent" and does not touch which edge `_evict_weakest_edge` picks. Measured need: on main, a stale CSR entry deletes an unrelated live edge and double-frees (`test_on_node_evict_*` fail on main). | UPHELD (justified, but flag to Ace as a second behaviour under the same switch) |
| 6 | **Test gap: node-evict guard orientation not covered** | MEDIUM | 2364-2366; test_w15_edge_slot.py:244-250 | [M] | Mutant R4 (keep only `_er[0]==min_slot and _er[1]==neighbor_id`) passes all 8 tests. It is a real defect: `review_probe.py` P1 on R4 leaves live edge `(2,5)` after evicting node 5 (edges are stored canonical `a<b`, 2662, so the evicted node is often `_er[1]`). Tests only evict node 0 (`X` = lightest fill edge index 0 → `xs=0`), which is always the smaller endpoint. Branch code itself is correct (P1 on branch: no dangling edge). | OPEN (add a test evicting a node that is the larger endpoint) |
| 7 | Equivalent / surviving mutants | INFO | 2746-2747 | [M][I] | M6 (`clear()`), my R5 (`pop()` once) and R6 (redundant `min_slot in _er[:2]`) survive. All are equivalent under single-threaded `link` because the free list is exactly `[slot]`; author already notes M6. The `try/except ValueError` (2745-2749) is dead unless another thread mutates the list between `in` and `remove`. | UPHELD (counts hold; not a gap) |
| 8 | Reported counts | — | w15_mutants.py | [M] | Re-ran: CONTROL(main) rc=1 4 fails; FIX rc=0 8 OK; M1/M2 caught by 2 off-tests; M3 3 fails; M4 1; M5 3; M6 survives; M7 1; M8 1. Matches the runner design. Note M1/M2/M3 mutate only the `link` switch line, not the node-evict switch line (2360) — covered by my R1-R3. | UPHELD |
| 9 | Missed callers of `_delete_edge` / allocator copies | — | portal_interior.py:3469 | [C] | Only external caller is the portal lottery prune; it skips `flags == 1` records before deleting (portal_interior.py:3442), so no double free there, and it is not evict-for-reuse, so the free-list append is correct. No other `_free_edge_slots`, `_evict_weakest_edge`, `_evict_coldest_node` or `ManifoldMemory` class anywhere (grep incl. P00-P60, fairies, scripts, tools). `scripts/expand_manifold.py` writes edges raw, `tools/expand_manifold.py` goes through `link()` — neither has its own allocator. Free list is rebuilt from flags on open (828-835). | REFUTED (nothing missed) |
| 10 | Stale CSR/overflow aliasing in `link()` strengthen path and `get_neighbors` | MEDIUM (pre-existing) | 2670-2686, `_csr_get_neighbors` 1173 | [M] | Probe P2 (CSR, cap 2): after `(0,1)` is evicted and its slot reused by `(4,5)`, `link(n000,n001)` finds the stale CSR entry, **strengthens `(4,5)`** (0.90→0.95) and returns True without creating `(0,1)`; `get_neighbors(n000)` returns `n001` with `(4,5)`'s weight. Identical on main's file. The W15 guard fixes this aliasing only inside node eviction. Not a regression; the fix makes the slot hold its edge persistently, so the alias persists instead of being overwritten [I]. | OPEN (separate ticket; out of W15 scope) |
| 11 | Stale `.csr` companion reused after edits at capacity | LOW (pre-existing) | ~852 (per test comment) | [C] | Author's own test documents it; not re-measured. | OPEN (pre-existing, as author reported) |
| 12 | Thread safety of free-list edit | LOW | 2744-2749 | [I] | Same unlocked list as main's `pop()`/`append()`; fix adds no new lock and no new race class. | OPEN (not tested; same as main) |
| 13 | `test_off_zero` only covers the CSR path | INFO | test_w15_edge_slot.py:356-357 | [C] | No `"0"` dict-path case; low risk since the switch parse is path-independent. | UPHELD (minor gap) |

## Bottom line

I could not refute the core fix. It is correct, OFF by default, byte-identical to main when OFF, and it touches no other allocator. One real test gap (#6): the suite would not catch the node-evict guard losing its second orientation. Before merge, add a test that evicts a node that is the larger endpoint of a live edge. #10 is a pre-existing aliasing bug, also on main, and should get its own ticket.

## Reproduce

```
python3 code/tests/test_w15_edge_slot.py          # branch: 8 OK
python3 code/tests/w15_mutants.py                 # control + author mutants
python3 docs/nous/W15/review_mutants.py           # reviewer mutants R1-R6
AKASHIC_EDGE_SLOT_FIX=1 python3 -W ignore docs/nous/W15/review_probe.py code/infrastructure/manifold_memory.py
```

---

# Round 2 — `nous/w15-edge-slot` @ 9f77eb5

Author changed tests, the mutant runner and SUMMARY.md only. `git diff a7eaaa6 9f77eb5 -- code/infrastructure/` is empty [M], so the round-1 verdicts on the code (#1-#5, #9) still apply. Branch merged into `nous/w15-review` so that the reviewer scripts run against the new tests.

| # | Finding / claim attacked | Severity | file:line | Tag | Evidence | Verdict |
|---|---|---|---|---|---|---|
| R2-1 | `manifold_memory.py` unchanged since round 1 | — | — | [M] | empty diff a7eaaa6..9f77eb5 on `code/infrastructure/` | UPHELD |
| R2-2 | Branch suite passes | — | test_w15_edge_slot.py | [M] | `Ran 10 tests … OK`; both new tests are collected (`TestNodeEvictOn.test_on_node_evict_deletes_own_edges_both_orientations`, `TestSwitchOffIdentical.test_off_zero_dict`) | UPHELD |
| R2-3 | Control vs main still fails | — | w15_mutants.py | [M] | CONTROL(main) rc=1, the same 4 fails as round 1. The new orientation test **passes on main**, which is expected: main has no guard and deletes every listed slot. It is a guard-regression test, not a control. | UPHELD |
| R2-4 | #6 closed: orientation gap | was MEDIUM | test_w15_edge_slot.py:310-327 | [M] | Author M9 fails the new test. My R4 (keep only the `_er[0]==min_slot` clause) now fails it. I also added **R7** (keep only the `_er[1]==min_slot` clause): it fails too. Node 10 is the larger endpoint of 9-10 and the smaller of 10-11, so the test covers both orders. | REFUTED (gap closed) |
| R2-5 | #13 closed: `"0"` on dict path | was INFO | test_w15_edge_slot.py:379-380 | [M] | `test_off_zero_dict` passes on the branch (byte-identical to main) | REFUTED (gap closed) |
| R2-6 | Switch default on the node-evict line | — | manifold_memory.py:2360 | [M] | Author M10 and my R1 (default `"1"`) fail `test_off_unset_csr`. R2 (`True`) fails both `off_*_csr` tests. Note: the default-ON mutants are caught only on the CSR path, because the dict adjacency is never stale and the guard is a no-op there [I]. That is acceptable: on the dict path ON and OFF behave identically. | UPHELD |
| R2-7 | Mutant table reproduces | — | w15_mutants.py | [M] | M1 2, M2 2, M3 3, M4 2 (now also fails the orientation test, because its free-list count assert catches it), M5 3, M6 survives, M7 1, M8 1, M9 1, M10 1. Matches SUMMARY.md. | UPHELD |
| R2-8 | Surviving mutants | INFO | manifold_memory.py:2744-2749, 2364 | [M][I] | M6 (`clear()`), R5 (`pop()`) and R6 (redundant `min_slot in _er[:2]`) still survive. All are equivalent single-threaded, as in round 1 (#7). | UPHELD (not a gap) |
| R2-9 | New claim in SUMMARY: portal lottery never prunes on v2 files | LOW (pre-existing) | portal_interior.py:3438-3441 | [C] | `node_a, node_b, weight, rel_type, flags = record` unpacks a 7-field v2 record (`_read_edge` docstring, manifold_memory.py:2560-2564) → ValueError → `continue`. So the CSR lottery never reaches `_delete_edge`. This **refines round-1 #9**: that caller is not merely safe, it is dead on v2. Not W15 scope. | UPHELD (author's claim holds; separate ticket) |
| R2-10 | Still open from round 1 | — | — | — | #10 stale-CSR alias in `link()`/`get_neighbors`, #11 stale `.csr` reuse at constant count, #12 free-list thread safety. All pre-existing and recorded as OPEN in SUMMARY.md. | OPEN (unchanged) |

## Round 2 bottom line

Both test gaps from round 1 are closed and the code is unchanged. I found nothing new to refute in W15. What remains open is pre-existing on main and outside this change: #10, #11, #12, and R2-9.

Reproduce: same four commands as round 1. `review_mutants.py` now also runs R7.
