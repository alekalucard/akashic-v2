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

---

# Round 2 — origin/nous/w12-moment-hold @ c61a504 (message said 00b4acd; c61a504 is the tip reviewed)

| # | finding | severity | evidence |
|---|---------|----------|----------|
| R2-1 | Suite 24/24 on branch; controls fail on main (3 F + 21 E) and on saver-only 8b0eeca (2 F + 8 E) | NONE | [M] same three runs as round 1 |
| R2-2 | OFF unchanged: `_mh_restored` is set only by restore_into, so with the switch off `getattr(...,False)` is False → else = `self._consolidated_tracers &= _live`, main's line verbatim; on_boot adds only an import + env read, no print/I/O | NONE | [C] fairy.py:775-781, moment_hold_save.py:297; test asserts orelse text |
| R2-3 | NEW (from the #11 move): restore now runs BEFORE `_epi_persister` init (fairy.py:183 vs ~215-258). Subscriptions come next, and heartbeat ticks already run (round-1 #11), so moments are emitted while the persister is still None (manifold init / `from server import SYSTEM`). The first emit after a 60-moment restore evicts the oldest restored moment with `_evicted=None` (fairy.py:690-694): it is dropped and never written to the episodic manifold. In round 1 restore ran after the persister init, so this window did not exist | MAJOR | [C] lines cited; [I] needs ≥1 emit before persister init ends, plausible |
| R2-4 | #12 still open: the flag is read OUTSIDE the lock. If restore lands between reading `_mh_restored` (False) and the unlocked `&= _live` (empty), its tracers are wiped. Reproduced deterministically: 0 tracers kept → next cycle remembered 5 + day-stored 55 of the restored moments (= consolidation) | MINOR | [M] /tmp/w12atk/race2.py, which runs the branch's own `_consolidate_episodic` with a fake self |
| R2-5 | #11 placement is otherwise sound: there are no strands before the subscriptions (organ template on_boot is empty, l.4267), so `_maybe_emit_moment` returns at `active_channels < 1` (fairy.py:408) and the hold is empty at restore | NONE | [C] |
| R2-6 | #8/#9/#10/#14 still OPEN as stated (shared-marker race restored 8/8 binders this run; deleted marker → restored again) | MINOR | [M] atk.py |
| R2-7 | CR count 0/0/0 on all three files | NONE | [M] |

Fix suggestions: R2-3: restore after the persister init (round-1 spot) and keep #11 as a safe logged skip, or init the persister before the subscriptions (changes OFF order, so gate it). R2-4: choose the branch by the switch (`os.environ.get(RESTORE,"0")=="1"`), not by the flag, so every ON-mode prune holds the lock.

**Round-2 verdict: REFUTED** — R2-3 can drop restored moments (MAJOR); R2-4 leaves the #12 consolidation race open.

---

# Round 3 — origin/nous/w12-moment-hold @ dea2c2a

| # | finding | severity | evidence |
|---|---------|----------|----------|
| R3-1 | Suite 28/28 on branch; main's files: 5 F + 23 E; c61a504's module+fairy: 6 F (incl. the new R2-3 and R2-6 tests, plus 4 wiring controls) | NONE | [M] three runs |
| R3-2 | OFF path matches main at the AST level: unwrapping `with (lock if _MH_RESTORE_ON else nullcontext())` to its body, and `if _MH_RESTORE_ON:` to its else, makes EVERY MomentBinderFairy method AST-equal to origin/main. nullcontext never suppresses exceptions, so the append/evict lines behave as before; the only additions are 2 module constants (no I/O) | NONE | [M] AST diff script → `[]`; [C] fairy.py:47-48, 696 |
| R2-4 → closed | A restore landing between the snapshot and the prune (forced via a hooked lock on the 2nd acquire) keeps all 60 tracers; the next cycle remembered 0 and day-stored 0 | NONE | [M] /tmp/w12atk/race3.py running the branch's own `_consolidate_episodic` |
| R2-3 → closed | Restore is again the last step after the persister init; persister None → "skipped", no marker, hold empty (set left for a later boot) | NONE | [M] atk3.py; [C] moment_hold_save.py:295-298 |
| R2-6 → closed in-process | 8 binders racing one marker → exactly 1 restored; others "already restored". `_RESTORE_LOCK` is taken before the binder lock and the appender takes only the binder lock → no lock-order inversion | NONE | [M] atk3.py; [C] |
| R3-3 | #11 is back with the old placement: ticks + subscriptions run during the slow persister init (incl. `from server import SYSTEM`), so the hold is often non-empty at restore → safe logged skip, the set stays unconsumed, and the next boot likely skips the same way. Meets "prefer empty hold, else skip + log", but the feature may rarely or never fire in practice | MINOR | [C] fairy.py on_boot order; [I] |
| R3-4 | The persister guard only proves the persister EXISTS: `persist()` failures are still swallowed at the eviction site, so a restored moment can roll off unpersisted, exactly like any live moment on main | MINOR | [C] fairy.py ~706-711 |
| R3-5 | Switch read once at import: `.env` is applied at server.py:1556 (module top), before fairies are spawned → consistent. `restore_into` still re-reads the env; a mismatch can only turn the restore off | NONE | [C]; [I] |
| R3-6 | Still OPEN as declared: #8 (deleted marker → restore again), cross-process marker race, #10, #14 | MINOR | [M] atk3.py |
| R3-7 | CR count 0/0/0 | NONE | [M] |

**Round-3 verdict: NOT REFUTED** — no BLOCKER/MAJOR. OFF path AST-identical to main; R2-3, R2-4 and in-process R2-6 verified closed. Remaining: R3-3 (feature may seldom fire), R3-4, declared opens.
