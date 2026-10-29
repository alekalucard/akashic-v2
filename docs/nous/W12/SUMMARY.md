# W12: MomentBinder HOLD saved at shutdown (W12a) and put back at boot (W12b)

Branch `nous/w12-moment-hold`. Review branch `nous/w12-review` (docs/nous/W12/REVIEW.md, last commit 3490796).
Tags: [C] read in code, [M] measured here, [I] inference. MomentBinderFairy/fairy.py lines in **Findings** are origin/main's; elsewhere they are the branch's.

## Switches (both OFF unless exactly "1")
- `AKASHIC_MOMENT_HOLD_SAVE` controls the save at shutdown. It is read at server.py:9258 and moment_hold_save.py:41-42.
- `AKASHIC_MOMENT_HOLD_RESTORE` controls the restore at boot. It is read once at import (fairy.py:47) and again inside the reader (moment_hold_save.py:237-238).

## Findings
- **The HOLD:** the binder keeps a 60-slot rolling HOLD, `EPISODIC_BUFFER_MAX = 60` (fairy.py:126, deque at :163). A moment is persisted to the episodic manifold only when it is evicted (fairy.py:678-693), so the HOLD at exit exists only in memory [C]. The day-store (<=800, :136, :168) is also memory-only and is not covered here [C].
- **on_die never runs:** `on_die` (fairy.py:251-263) only prints, and nothing in `code/` calls `.on_die(` [M grep]. `on_shutdown` is the template's; it is reached only in shutdown_system Phase 4 (Organ_Template_0_3_0.py:4281-4301; server.py:9399) and saves nothing of the HOLD [C].
- **Phase 4 is usually cut:** the main thread's 20 counted sleeps, then `os._exit(0)`, cut it (server.py:9775, :9805). The code's own record says this happened in 7 of 11 logs (server.py:8904-8906) [C, their measurement].
- **Save point:** shutdown_system Phase 2, right after `_capture_dream_seed()` (server.py:9255). It is reached by the HTTP route, reboot and Ctrl+C (:3815, :3897, :9158) [C].
- **Seed readers at boot:** DreamSeedFairy.on_boot (dream_seed_fairy.py:327, re-saves at :343), server `_load_dream_seed` (server.py:8384), unconscious_mind_fairy.py:4219, waking_sequence_fairy.py:615 and sourpatches_farm.py:1184 [C]. None read the held moments; W12b is the only reader.
- **No caller:** `sleep_consolidate_day` (fairy.py:815) has no caller [M]. Per the owner it is NOT wired.
- **09-25 spec:** not in the repo [M grep].
- **Importance:** the only importance score is `_score_significance` (fairy.py:724-748), stored as `"significance"` (:685). It is used only if the save bound forces drops, which it does not today (cap 60 = HOLD size).

## Built
**W12a (save)**, `code/infrastructure/moment_hold_save.py`:
- `shutdown_hand_off` finds the binder through `directory.get_fairy(...).metadata["fairy_instance"]`.
- It writes `mind_pools["moment_hold"]` into the just-written seed: atomically (temp file, fsync, `os.replace`, directory fsync), bounded (60 moments / 2 MB as written; the lowest significance drops first; ties by tracer, never by age), and content-exact (a JSON copy that must compare equal; a bad entry is refused alone, never coerced). It never creates a seed.
- `code/server.py` gets +9 lines (9256-9264).

**W12b (restore)**, owner's decision: `MomentBinderFairy.on_boot` calls `restore_into` as its last step, after the episodic persister init (fairy.py:258-268).
- Moments go back as saved: the same dicts, oldest-first, `extend` into the same deque the binder appends to (fairy.py:696-705).
- It restores **only into an empty hold**; otherwise it skips, logs, and leaves the set unconsumed (moment_hold_save.py:300). It never cuts to the cap: a set that does not fit is skipped whole.
- It skips if there is no episodic persister (:295), so a restored moment can never roll off past a missing persister.
- **Once per set:** the set's sha256 id (`saved_ts` + moments) goes into the sidecar `state/moment_hold_restored.json`. That mark is written atomically **before** the fill (:309-310), under a module-level `_RESTORE_LOCK` (:234, :279), so one saved set goes into one binder per process.
  - Nothing is deleted, and the seed is never written: DreamSeedFairy.on_boot re-saves the seed from a stale copy (dream_seed_fairy.py:327/343), so an in-place mark could be lost.
  - An unreadable marker refuses the restore.
- **No consolidation:**
  - The restored tracers go into `_consolidated_tracers`, so the 60 s rememberer and the day-store skip them.
  - With the switch ON, the reviewed-tracer prune (fairy.py:781-787) and the eviction-capture + append (fairy.py:696) run under `_moment_lock`. With it OFF, `nullcontext` and the original line run.
- **OFF:** unwrapped to its OFF form, every MomentBinderFairy method is AST-equal to main. The only additions are 2 module constants with no I/O (reviewer R3-2 [M]).

## Tests [M] (tip dea2c2a + SUMMARY commit)
- **Suite:** 28/28 on the branch; 0/28 on main's files (5 F + 23 E).
- **Controls:** all 4 fail on main:
  - `test_control_hold_carried_unchanged`
  - `test_control_server_calls_hand_off_after_capture`
  - `test_control_restore_exact_order_once`
  - `test_control_on_boot_calls_restore`
- **R2 tests:** the new R2-3 and R2-6 tests fail on the previous tip c61a504 and pass now.
- **Mutants:** all 22 killed.
  - Save (M1-M9): switch default, age drop, high-significance drop, non-atomic write, value coercion, `!= "0"`, server gate, depth-0 byte size, no non-dict check.
  - Restore (R1-R10): restore default, non-empty hold, reversed order, no consumed check, fill before mark, no consolidation skip, cut to cap, mark in seed, no persister check, no restore lock.
  - Fairy (F1-F3): fairy switch default, prune without the lock, append never locked.

## REVIEW
- **W12a reviewer:** 2 rounds, NOT REFUTED. Its fixes landed: per-moment refusal, the byte bound measured at real nesting, directory fsync, the non-dict entry. Remaining: OPEN-1 below.
- **W12b reviewer** (session_01WZwX7kBX2f1z6AcsYYcC7q): R1 NOT REFUTED (abc12f9), R2 **REFUTED** (c999650: the restore ran before the persister, MAJOR; the flag-based lock), R3 **NOT REFUTED** (3490796). Final table, against dea2c2a:

| # | finding | severity |
|---|---|---|
| R3-1 | 28/28 on branch; main 5F+23E; c61a504 6F, including the R2-3/R2-6 tests [M] | NONE |
| R3-2 | OFF matches main: methods AST-equal once unwrapped; nullcontext doesn't swallow exceptions; 2 constants, no I/O [M/C] | NONE |
| R2-4 | Closed: a restore forced between snapshot and prune keeps all 60 tracers; next cycle remembers 0 and day-stores 0 [M] | NONE |
| R2-3 | Closed: no persister -> skip, no marker, hold empty [M] | NONE |
| R2-6 | Closed in-process: 8 binders, exactly 1 restored; lock order _RESTORE_LOCK then the binder lock [M/C] | NONE |
| R3-3 | The restore may seldom fire: the hold is often non-empty after the slow persister init (safe skip, logged, set unconsumed) [C/I] | MINOR, OPEN |
| R3-4 | persist() failures are swallowed, so a restored moment can roll off unpersisted, like any live moment on main [C] | MINOR, OPEN |
| R3-5 | The import-time switch read is consistent: server.py loads .env at :1556, before fairies [C/I] | NONE |
| R3-6 | #8 (marker deleted by hand -> restores again), cross-process marker race, #10 (corrupt marker blocks), #14 (marker I/O under _moment_lock) [M] | MINOR, OPEN |
| R3-7 | 0 CR in all files [M] | NONE |

## OPEN
1. **W12a race:** a late `DreamSeedFairy._on_shutdown` save (dream_seed_fairy.py:812/:1165) can overwrite the seed without `moment_hold`. The same race exists for the server's own seed.
2. **R3-3, the restore may seldom fire.** What would make it fire reliably (NOT built):
   - (a) with the switch ON, init the persister before the subscriptions in on_boot, so the hold is still empty at restore time; or
   - (b) allow restoring into a non-empty hold when saved + live <= cap, by prepending the saved (older) moments so time order holds and nothing is evicted. The owner preferred empty-only, so this needs his call.
3. **R3-4:** persist() errors are swallowed (pre-existing, fairy.py append site).
4. **R3-6:**
   - A marker deleted by hand restores the set again.
   - Two processes sharing one `state/` dir are not serialised (one server per tree [I]).
   - A corrupt marker blocks restores until it is fixed (deliberate: it cannot prove "not yet restored").
   - The marker is written while holding `_moment_lock` (once, at boot).
5. **Sleep consolidation** of restored moments is the owner's design; nothing is wired.

## Could NOT verify
- That the binder's directory record carries `fairy_instance` under "MomentBinderFairy" (boot_orchestrator.py:476/816) [I].
- Real boot and shutdown timing, including how long the persister init takes. That timing decides how often R3-3 skips.
- Windows `os.replace` behaviour while the seed is open elsewhere.

## CHECK THESE 3
1. Nothing calls `on_die`, so the HOLD is lost at exit: fairy.py:251-263 (main), plus a grep for `.on_die(`, and :678-693.
2. The save point runs before the main thread's cut on every path: server.py:9255-9264 vs :3815, :9775-9805.
3. The restore happens once, only into an empty hold, after the persister, with the mark before the fill: moment_hold_save.py:279-310 and fairy.py:258-268.
