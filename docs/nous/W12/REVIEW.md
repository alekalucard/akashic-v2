# W12b review — moment hold restore (origin/nous/w12-moment-hold @ 55f1fad vs 8b0eeca)

| # | finding | severity | evidence |
|---|---------|----------|----------|
| 1 | Branch suite passes 23/23; every CONTROL fails on main (module/fairy absent) AND on saver-only base 8b0eeca (1 FAIL + 8 ERROR, all W12b tests) | NONE | [M] `python3 -I code/tests/test_w12_moment_hold.py`; W12_SERVER/W12_FAIRY/W12_MODULE reruns |
| 2 | Switch default is OFF: unset, "0", "1 ", "TRUE", "yes", "01" all return "off", no marker, hold empty | NONE | [C] moment_hold_save.py:234, fairy.py:251; [M] /tmp/w12atk/atk.py |
| 3 | Switch OFF: only `import os as _mh_os` + one env read added to on_boot; no print, no I/O, no state touched | NONE | [C] fairy.py:250-251; [I] os already in sys.modules |
| 4 | No second copy, no other caller: restore_into / AKASHIC_MOMENT_HOLD_RESTORE only in fairies/P30_Cognition/MomentBinderFairy/fairy.py; no MomentBinder under top-level code/P30_Cognition | NONE | [M] grep -rln over code/ |
| 5 | DreamSeedFairy.on_boot re-save (non-atomic open('w'), dream_seed_fairy.py:233-238/343) keeps mind_pools intact → same set id → "already restored" | NONE | [M] atk.py re-save with extra wake_ts |
| 6 | Truncated seed mid-write → error, no marker written, no restore that boot (lost, never doubled) | NONE | [M] atk.py |
| 7 | Exact content/order, cap respected (cap 59 → skipped whole), non-empty hold → skipped, concurrent appender → skipped | NONE | [M] atk.py; [C] moment_hold_save.py:282-293 |
| 8 | Marker file deleted → same saved set restored again (no in-seed backstop) | MINOR | [M] atk.py "marker DELETED: restored 60"; [I] needs external deletion of gitignored state/ |
| 9 | Marker read (l.275) is outside any cross-binder lock → 8 binders sharing one marker: 5 restored the same set (each hold still gets it once) | MINOR | [M] atk.py Barrier race; [I] needs two binders in one code tree at once |
| 10 | Empty/corrupt marker → restore refused on every boot until fixed by hand (fail-safe, but silent beyond a log line) | MINOR | [M] atk.py; [C] moment_hold_save.py:_read_marker |
| 11 | Heartbeat is wired before on_boot (Organ_Template_0_3_0.py:3565 → on_boot later; no boot gate before on_tick ~5117), so on_tick can emit into the hold during the slow manifold init → restore often finds a non-empty hold and skips (safe, but feature may rarely fire) | MINOR | [C] those lines; [I] not run |
| 12 | `_consolidated_tracers &= _live` runs OUTSIDE the lock after the snapshot (fairy.py:769-774); a restore landing in that gap has its tracers wiped → restored moments get reviewed/remembered/day-stored on the next 60 s cycle (= consolidation) | MINOR | [C] fairy.py:769-774, moment_hold_save.py:296; [I] narrow window, not reproduced |
| 13 | Restore writes to `_consolidated_tracers` (outside the hold) to suppress consolidation; tracerless moments add `None` | NONE | [C] moment_hold_save.py:294-296; [M] atk.py `{None}` |
| 14 | Marker write + fsync happens while holding `_moment_lock` → ingest handlers block briefly at boot | MINOR | [C] moment_hold_save.py:282-292 |
| 15 | No call to sleep_consolidate_day/_consolidate_episodic/_remember_moment from restore; restored moments only reach the episodic manifold on eviction, as every hold moment does, and were never persisted before shutdown | NONE | [C] diff; fairy.py:690-701; [I] |
| 16 | Line endings: 0 CR in all 3 files, branch and main | NONE | [M] grep -c $'\r' |

**Verdict: NOT REFUTED** — no BLOCKER/MAJOR; switch-off path is inert. Worth fixing before turning it on: #11 (restore before subscriptions/ticks) and #12 (take the lock around `&=`).
