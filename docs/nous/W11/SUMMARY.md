# W11 -- bind carryover + bind timing (branch nous/w11-bind-carryover)

## Headline: main already has most of W11 (built 2026-10-15)
main already has a full persist+replay layer for this exact queue, plus per-step timing. Both are switched by
`state/tardis_fix.json` (`b_persist`, `l0_timing`), which is OFF when the file is absent:
- the switch reader: code/infrastructure/tardis_fix.py [C]
- the persist/replay layer "B": code/infrastructure/tardis_backlog.py [C], with fairy hooks at fairy.py:6266, :6271-6273, :6307-6309, :6382, :6427-6437 [C]
- the timing layer "L0": code/infrastructure/tardis_timing.py, with laps at fairy.py:6169-6191 [C]

Writing a second persist system on the same queue would duplicate tested code and race it on `get_nowait`. So this branch
adds the two env switches on top of B/L0 and closes the gaps between B and the W11 spec.

## What exists (verified)
- Queue: Queue(maxsize=4096) at fairy.py:1989, filled at :4986-4997 [C].
- Shutdown:
  - The save-gated HTTP shutdown route calls signal_global_shutdown() at T0 (server.py:3704-3706) [C].
  - B's trigger thread waits on that Event (tardis_backlog.py:499-507) and sweeps the whole queue synchronously into `state/tardis_backlog/pending-*.jsonl` [C].
  - Reviewer measured 0.05 s per 4,096 items with B's default record and 0.20 s with my verbatim record [M]. Both are far inside the 45 s cap.
- File format and replay:
  - Lines are CRC-framed and appended with fsync. Each boot writes a new file opened with "xb" (:528) [C].
  - A torn tail is skipped, and an earlier file is never reopened for writing [M test].
  - Replay waits 60 s. It claims a file by atomic rename and checks a uuid ledger. It then feeds the SAME queue at a bounded rate (headroom 200, 20/s, held within 512 of the cap) and renames the file done-* [C].
- No dedup against the manifold, deliberately. Carried pairs were never written. A repeat link() is a reinforcement (+weight*0.5, manifold_memory.py:2681-2685), so deduping would drop real learning [C/I]. The reviewer agreed.
- Which instance holds the binds:
  - Only serial copy A (server.py:6349, manifold mode) holds unwritten binds. It writes 2 upserts + 1 link per pair on one thread (fairy.py:6134-6206) [C].
  - B's arm() refuses the region-less portal copy (tardis_backlog.py:351) [C]. Its queue drains to async portal IO at 2 Hz (fairy.py:6304) [C].
  - With K2 ON only A exists.

## Built: AKASHIC_BIND_CARRYOVER (OFF unless os.environ.get(..., "0") == "1")
1. It turns `b_persist` ON without the file (tardis_fix.py:96-112). It can only add ON: while it is set, the file cannot veto it.
2. Same fields: a queue item is written whole (`features` included, in its own key order) when it round-trips through JSON exactly and validates. Otherwise B writes its old record (tardis_backlog.py:629, :645-662). Pairs are unchanged either way [M].
3. Never delete: done-* files are not pruned (:1034), and the ledger keeps every uuid (:288).
4. The HTTP reboot route (server.py:3884) and Ctrl+C/SIGTERM (server.py:9790) never set the Event, so they lost the queue. Both now call `_w11_bind_carryover` (server.py:9136), which calls `persist_owner` (tardis_backlog.py:326), before shutdown_system().

## Built: AKASHIC_BIND_TIMING (OFF unless == "1")
It turns `l0_timing` ON and splits the full-table eviction scans out as their own laps, `l.evict` / `u.evict`
(manifold_memory.py:2280-2285, :2736-2741). L0 still prints one line per window, not "every N pairs" (main's behaviour).

## Cause of the 0.4-0.8 s per pair (synthetic temp manifold, 4-core Linux)
- Not full: 0.03-0.05 ms per pair [M].
- EDGE table full: `_evict_weakest_edge` (:2777) is a Python loop over every edge. It cost 41 / 81 / 175 ms per pair at 100k / 200k / 400k edges [M].
- NODE table full: `_evict_coldest_node` (:2338) cost 100 / 196 / 400 ms per pair at 100k / 200k / 400k nodes [M].
- At her about 1-2M rows this extrapolates to about 0.4-1 s [I]. Whether her tables are full cannot be seen from here.
- **NEW BUG (OPEN, not fixed):** `_delete_edge` appends the evicted slot to `_free_edge_slots` (:2609), and link() also uses that slot (:2739). So the next new edge overwrites the one just written [M: n9-n10 lost on a temp manifold]. At capacity, every other new edge is silently lost.

## Tests: code/tests/test_w11_bind_carryover.py, runner code/tests/w11_mutation_run.py (temp dirs only)
22 tests [M]:
- branch: 22/22 pass
- main: 10 fail, all 9 CONTROLs among them
- mutants M1-M10 (env defaults flipped, gates inverted or removed, hooks moved after os._exit / after shutdown_system): each caught by at least 1 test
- with both env vars unset, the reviewer's persisted records are byte-identical to main's [M]

## Could NOT verify
- Live timing or queue depth on her box, and whether her tables are full.
- Postal fan-out to both cortex copies.
- That the reboot and Ctrl+C routes reach the hook in wall time; the placement test checks order only.
- Losses that remain: binds arriving after the last sweep, the up to 4 pairs mid-write at os._exit, the boot-watchdog exit (server.py:4598) and the second Ctrl+C (:9662).

## CHECK THESE 3
1. The edge-eviction double-slot bug: manifold_memory.py:2609 together with :2739.
2. With both env vars unset, behaviour is main's: tardis_fix.py:99-112, tardis_backlog.py:131-138/:288/:629/:1034, manifold_memory.py:367-374, server.py:9136-9141.
3. Only copy A owns the queue: tardis_backlog.py:351, server.py:6349 (fairy.py:2205 vs :2323).

## REVIEW
A fresh remote session (session_01WZwX7nNBHJwMB5U3XkKdj5) worked from the diff and the task only. It ran 2 rounds; the full
report is on branch nous/w11-review (6f13222). FINAL VERDICT: no BLOCKER, no MAJOR.

| # | finding | severity | status |
|---|---|---|---|
| 1 | OFF = main on every path; persisted records byte-identical (sha bd2e088a) | NONE | CONFIRMED |
| 2 | Controls fail on main; mutants M1-M10 caught | NONE | CONFIRMED |
| 3 | Hook placement was untested (its N1 survived) | MINOR | FIXED round 2. Residual OPEN: ordinal, not temporal (a sleep(30) before the hook survives) |
| 4 | Only serial A can own the queue | NONE | CONFIRMED |
| 5 | Exactly once (lock, claim by rename, ledger) | NONE | CONFIRMED |
| 6 | Append+fsync to a new "xb" file, not tmp+rename | MINOR | OPEN by design (tmp+rename would lose the whole file to os._exit) |
| 7 | Fallback record alters item fields (not pairs) | MINOR | OPEN (main's behaviour) |
| 8 | Env=1 overrides a malformed or false tardis_fix.json | MINOR | OPEN by design; to turn it off, unset the env var |
| 9 | Never-delete vs 256-uuid ledger allowed a double replay | MINOR | FIXED. OPEN: never-delete holds only while the env var is set; OFF re-prunes to 16 / 256 like main |
| 10 | Verbatim sweep 4x slower, file 1.9x larger, bounded | MINOR | OPEN, accepted |
| 11 | No manifold dedup; smaller replay batches bias reinforcement counts; a slow writer defers loss rather than curing it | MINOR (was MAJOR) | OPEN by design |
| 12 | Boot watchdog :4598 and second Ctrl+C :9662 not covered | MINOR | OPEN, accepted |
| 13 | Eviction laps partition the old l.new / u.new exactly | NONE | CONFIRMED |
| 14 | No second copy of the changed modules | NONE | CONFIRMED |
