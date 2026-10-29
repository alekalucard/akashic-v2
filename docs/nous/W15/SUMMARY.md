# W15 -- edge slot double use at capacity

Branch `nous/w15-edge-slot`. Switch **`AKASHIC_EDGE_SLOT_FIX`** (OFF when unset: `os.environ.get("AKASHIC_EDGE_SLOT_FIX", "0") == "1"`).
File changed: `code/infrastructure/manifold_memory.py` (+25 lines, LF endings, 0 CR before/after). Tests: `code/tests/test_w15_edge_slot.py`, runner `code/tests/w15_mutants.py`.

## Found
- Bug confirmed [C]: full table -> `link()` else-branch `_evict_weakest_edge()` (manifold_memory.py:2734-2737) -> `_delete_edge` appends slot to `_free_edge_slots` (:2608) -> new edge written in that slot (:2751) -> next new edge pops it (:2726-2727) and overwrites. [M] main: K=10 new edges at capacity 20 -> **5 of 10 survive** (record scan and verified index), but in-session `get_neighbors` reports **10 of 10** because the lost edges' index entries point at the overwriting edge's slot (phantoms).
- Header `edge_count` (:21, :711) is a high-water mark; `edge_count` property (:2534) = `_edge_count - len(free)`; on main it is off by one at capacity (19 vs 20 live) [M]; with fix 20 [M].
- Node allocator: `_evict_coldest_node` (:2324-2372) does NOT put the reused node slot on `_free_node_slots` -> no node double use [C]. But its edge-deletion loop (:2353-2368) follows CSR/overflow entries that `_delete_edge` never prunes on the CSR path (:2610-2613 only touch the dict). [M] on main it (a) deleted a LIVE unrelated new edge (K survivors 5->4) and (b) freed an already-freed slot twice (duplicate on free list -> same double use). Fixed behind the same switch: only delete a slot whose record is this node's live edge.
- No second allocator copy: only `manifold_memory.py` has `_free_edge_slots` / slot allocation [C, grep]. portal_interior.py:265 `link` is dict-based; AssociationCortexFairy fairy.py:1011 `_evict_weak_edges` is dict-based; no top-level P*_ copy of manifold_memory. portal_interior.py:3469 calls `mm._delete_edge` (genuine delete, slot correctly freed). Side note [C]: portal_interior.py:3439 unpacks a 7-field v2 edge record into 5 names -> ValueError -> `continue`, so that lottery never prunes on v2 files.

## Built (switch ON only)
1. link() evict branch (:2738-2749): remove the reused slot from `_free_edge_slots`. Eviction choice unchanged (test asserts the K lightest fill edges are the ones gone).
2. `_evict_coldest_node` (:2354-2367): skip neighbor entries whose edge record is deleted or not (min_slot, neighbor). Only skips wrong deletions; never adds one.

## Tests (synthetic, temp dir, N=64 nodes, capacity 20, K=10) [M]
| target | result |
|---|---|
| CONTROL (main's file) | 4 of 10 FAIL: on_dict_keeps_all_K, on_csr_keeps_all_K, node_evict_no_collateral, node_evict_no_double_free |
| FIX (branch) | 10/10 OK; K survive 10/10 by record, verified index, get_neighbors, reopen (dict + CSR paths) |
| OFF unset / "0" (dict + CSR) | manifold, .csr and .keys bytes identical to main after the same ops (incl. node eviction, deterministic clock); counts identical (5,5,10) |
| M1 default "1" / M2 `!= "0"` default "1" | FAIL (off-identical tests) |
| M3 wrong switch name / M5 off-by-one removal | FAIL (keep-all-K) |
| M4 stop freeing in `_delete_edge` | FAIL (genuine delete) |
| M7 guard flag only / M8 guard endpoints only | FAIL (collateral / double-free) |
| M9 guard one orientation only (reviewer's R4) / M10 node-evict switch default "1" | FAIL (both-orientations test / off-identical) |
| M6 `clear()` whole free list | SURVIVES -- equivalent single-threaded (list == [slot] in that branch); differs only under concurrent frees |

## Could NOT verify / OPEN
- OPEN (pre-existing, same on main, not fixed): `.csr` freshness is keyed only on the ACTIVE edge count (:852). At capacity that count never changes, so a reopen loads a stale `.csr`: [M] after reopen, 10/10 edges in records but **0/10 findable** by get_neighbors until `.csr` is rebuilt. Also occurs below capacity whenever deletes equal creates between opens.
- OPEN (pre-existing, same on main): CSR-path stale entries after any edge delete -> `get_neighbors` phantom neighbor, and `link()` strengthen loop (:2674-2692) can strengthen the WRONG edge (reused slot) and not create the requested one [M: link(n000,n001) after eviction raised weight of slot 0 = edge 30-45, pair not created].
- Multi-process/multi-handle behaviour (portal_interior's separate handle sharing the mmap, :658-699) not exercised; free lists are per handle.
- Live file not available; 63% full claim not checked.

## CHECK THESE 3
1. manifold_memory.py:2744-2749 -- slot removed from free list only in the at-capacity branch, switch default "0".
2. manifold_memory.py:2360-2367 -- node-eviction guard never skips a genuine edge of the evicted node (endpoint test both orders).
3. manifold_memory.py:852 -- stale `.csr` reuse at constant active count (OPEN; makes the fixed edges invisible after reopen until rebuild).

## REVIEW
Fresh remote session `session_01WZwX7kq5EGTpkFchGnitvh`, given only the diff + task, asked to refute. Verdict committed to branch `nous/w15-review` (docs/nous/W15/REVIEW.md). Its table, condensed:

| # | Finding | Sev | Verdict | Action |
|---|---|---|---|---|
| 1 | Bug real on main (control fails 4 tests) | - | UPHELD | - |
| 2 | link() fix correct, minimal | - | UPHELD | - |
| 3 | Switch OFF when unset/"0" | - | UPHELD | - |
| 4 | Behaviour change with switch OFF | - | REFUTED (none) | - |
| 5 | Node-evict guard is beyond the literal task | LOW | UPHELD (justified; second behaviour under same switch) | noted for owner |
| 6 | Test gap: guard orientation (mutant R4 survived) | MED | OPEN at review | FIXED: test_on_node_evict_deletes_own_edges_both_orientations + mutant M9 now fails |
| 7 | Equivalent mutants (M6 clear, pop once) | INFO | UPHELD | - |
| 8 | Reported counts reproduce | - | UPHELD | - |
| 9 | Missed callers / allocator copies | - | REFUTED (none) | - |
| 10 | Stale CSR alias in link() strengthen + get_neighbors | MED, pre-existing | OPEN | separate ticket |
| 11 | Stale .csr reuse at constant count (:852) | LOW, pre-existing | OPEN | separate ticket |
| 12 | Free-list thread safety | LOW | OPEN (same as main) | - |
| 13 | No "0" dict-path OFF test | INFO | UPHELD | FIXED: test_off_zero_dict |

### REVIEW round 2 (nous/w15-review @ 087c181, against 9f77eb5)
| # | Finding | Verdict |
|---|---|---|
| R2-1 | manifold_memory.py unchanged since round 1 | UPHELD |
| R2-2 | Branch suite 10/10 OK | UPHELD |
| R2-3 | CONTROL vs main: same 4 tests fail (orientation test passes on main; it guards a regression, it is not a control) | UPHELD |
| R2-4 | #6 orientation gap: M9, R4 and new R7 all fail | CLOSED |
| R2-5 | #13 "0" dict path: test_off_zero_dict byte-identical | CLOSED |
| R2-6 | Node-evict switch default: M10/R1/R2 caught (CSR path only; on the dict path the guard is a no-op) | UPHELD |
| R2-7 | Mutant counts reproduce M1-M10 | UPHELD |
| R2-8 | M6, R5, R6 survive: equivalent when single-threaded | UPHELD (not a gap) |
| R2-9 | portal_interior.py:3438-3441: unpacking 5 names from a 7-field v2 record raises ValueError, so the lottery never prunes on v2 | OPEN (pre-existing, separate ticket) |
| #10 | Stale-CSR alias in link() strengthen / get_neighbors | OPEN (pre-existing) |
| #11 | Stale .csr reused at constant active count (:852) | OPEN (pre-existing) |
| #12 | Free-list thread safety | OPEN (pre-existing, same as main) |
Reviewer bottom line: nothing new to refute in W15. Its round-2 reply went to the parent session, not to me; it was relayed.
