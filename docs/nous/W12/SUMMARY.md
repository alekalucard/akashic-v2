# W12c: the reader fires

Branch `nous/w12-moment-hold`. Previous tip 354f36a; W12c code commit 414327b; no review fixes were needed. This builds option (a) of OPEN 2 below (R3-3), which is now closed. Line numbers below are from the branch.

**Built.** With `AKASHIC_MOMENT_HOLD_RESTORE=1`, `on_boot` now calls `_mh_persister_then_restore()` right after `super().on_boot()` (fairy.py:192-193) and before the first subscription (fairy.py:195) [C].
- That method runs (1) the episodic persister init, AST-equal to on_boot's own block (fairy.py:273-310 vs :222-259; a test keeps them equal), then (2) `restore_into` (fairy.py:311-319) [C].
- on_boot's own persister block then sees `_epi_persister` set and does nothing. If the early init failed, the block tries once more after the subscriptions, exactly as on the tip [C, M].
- The trailing restore block at the end of on_boot (tip fairy.py:255-265) is gone [C].
- Every restore guarantee is unchanged, because `moment_hold_save.py` is unchanged: empty hold only, once per set, one binder, no persister means skip with the set left unconsumed, nothing deleted, no consolidation, moments exactly as saved [C].

**Why the hold is empty at restore time.** `_episodic_buffer.append` exists at one site only, `_maybe_emit_moment` (fairy.py:753). That runs from `on_tick` (:443) [C].
- The heartbeat is registered before `on_boot`, in `_wire_infrastructure` (Organ_Template_0_3_0.py:4386, called at :3565, before on_boot at :3586). So `on_tick` can fire during on_boot [C].
- But `_maybe_emit_moment` returns early when no channel holds a strand (fairy.py:466), and the channel buffers are filled only by the handlers that on_boot subscribes (fairy.py:344-416) [C].
- `__init__` starts no thread (fairy.py:145-178), and `super().on_boot()` only emits FACET_READY (Organ_Template_0_3_0.py:4267-4270) [C].
- So nothing can append before the subscriptions. Measured by test: a tick during the init appends 0 [M].
- There is no second copy: `class MomentBinderFairy` exists only in code/fairies/P30_Cognition/MomentBinderFairy/fairy.py, and nothing under code/P30_Cognition has one [M grep].

**Switch.** `_MH_RESTORE_ON = os.environ.get("AKASHIC_MOMENT_HOLD_RESTORE", "0") == "1"` (fairy.py:47), read once at import [C].
- OFF means the gated call is skipped, and on_boot runs today's order: super, 11 subscribes, persister [M, for unset, "0", "", "true", "yes", "on", "1 ", " 1", "01", "2"].
- With the `if _MH_RESTORE_ON:` step removed, on_boot hashes the same as origin/main's and as the tip's: sha256(ast.unparse) = 66a484f2..., identical on Python 3.11, 3.12 and 3.13 [M].

**Cost (moving the persister earlier).** With the switch ON, the 11 subscriptions now wait for the whole persister init [C]. That init does:
- the imports;
- `from server import SYSTEM` (fairy.py:239);
- `create_region` on the first run only, which zero-fills 200k nodes / 800k edges (akashic_manifold.py:631-690; manifold_memory.py:604-619);
- `graph("episodic", write=True)`, which opens the region (akashic_manifold.py:700-720). That goes to `_open_existing` and then `_rebuild_indices`, a Python loop over all 200,000 node slots plus the edges (manifold_memory.py:638-652, :782, :828).
- Plus the restore itself: a seed read, sha256, and one fsync'd marker write [C].

The duration on her machine is not measured: probably sub-second to a few seconds [I]. On the tip the same work ran right after the subscriptions, so total boot time is the same. Only the subscribe moment moves later [C/I].

**Letters in that window are not seen by this fairy.** I found no replay or retained message in `TensorFabric.subscribe` (tensor_fabric.py:1075-1100) [C]. I did not check the Rust postal core [I]. See OPEN W12c-1.

**Tests [M]** (`python3 code/tests/test_w12_moment_hold.py`)
- **Branch:** 36/36. These are the 28 W12a/b tests plus 8 new ones. One W12b test, `test_control_on_boot_calls_restore`, is REWRITTEN for the new placement; the old version asserted "restore is on_boot's last step".
- **CONTROL** `test_control_restore_fires_when_a_moment_arrives_during_init`: a letter plus a tick land inside the persister init, and the test runs the real on_boot, on_tick and `_maybe_emit_moment` over fakes.
  - On the tip's fairy.py it FAILS: `restore=skipped: hold already has 1 moment(s)`.
  - On the branch all 60 are restored exactly as saved. The next live moment lands after them, and the evicted oldest saved moment goes to the persister.
- **Tip's fairy.py:** 3 F + 1 E. **main's fairy.py:** 7 F + 1 E; the OFF-order tests pass there.
- **Tip's test file on the new code:** 27/28. The 1 failure is the deliberately changed placement test.
- **Mutants:** all 8 killed:
  - restore before the persister;
  - subscriptions still before the restore;
  - switch read as `!= "0"`;
  - the call not gated;
  - the copied init drifts;
  - the gate placed before `super().on_boot()`;
  - the early path skips the persister;
  - restore into a non-empty hold allowed (moment_hold_save.py).
- **Line endings:** 0 CR before and after in every touched file.

**Could NOT verify.**
- A real boot. Not run, by the session rules.
- How long the persister init really takes on her tree.
- Whether the Rust postal core replays to late subscribers.
- Whether `from server import SYSTEM` re-imports server.py when the server runs as `__main__`. This is unchanged by W12c but now sits before the subscriptions [I].

**OPEN (W12c)**
1. Letters on the 11 topics published between the old and new subscribe moments are missed by the binder when the switch is ON. Those moments simply have fewer strands. Not buffered, by design.
2. The persister init now exists twice (on_boot and `_mh_persister_then_restore`), so OFF stays AST-equal to main. Drift is caught by `test_early_persister_init_is_on_boots_own`.
3. If the early init fails, the restore waits for a later boot, even if on_boot's retry succeeds a moment later.

**CHECK THESE 3**
1. fairy.py:192-193: the only gated step, and it sits before the subscriptions at :195.
2. fairy.py:262-319: persister init and then restore. Is the copy truly identical to :222-259?
3. fairy.py:466 with :344-416: is "no subscription, so no strand, so no append" really the only route into the hold?

## REVIEW (W12c)
Fresh remote session session_01WZwX7m1FuyXR9p83a26CsC. It was given only the diff and the task, and told to REFUTE. Verdict: **NOT REFUTED** (1 round). Nothing needed fixing, so no second round.

| # | finding | severity |
|---|---|---|
| 1 | 36/36 on the branch [M] | NONE |
| 2 | On 354f36a's fairy.py: CONTROL fails, plus 3 more (the persister-failure test, the placement test, and the drift guard, which errors because there is no copy there) [M] | NONE |
| 3 | On main's fairy.py: 7 F + 1 E, including the CONTROL [M] | NONE |
| 4 | The tip's test file on the new code: 1/28 fails, `test_control_on_boot_calls_restore`, because the restore moved on purpose (fairy.py:192) [M/C] | NONE |
| 5 | The switch is OFF for unset, "0", "", "true", " 1", "1 " and "01". Only "1" turns it on (fairy.py:47, moment_hold_save.py:238) [M] | NONE |
| 6 | OFF: on_boot with the `_MH_RESTORE_ON` blocks stripped is AST-equal to main's and to 354f36a's. The removed tail block was ON-only [M/C] | NONE |
| 7 | The only append is fairy.py:753. Channel buffers are filled only by the handlers subscribed in on_boot (:344-416). `__init__` starts no thread [C] | NONE |
| 8 | The heartbeat is wired before on_boot (Organ_Template:4356, :4386), but `_maybe_emit_moment` returns at fairy.py:466 when the buffers are empty. NEEDS_AFFECT/NEEDS_GOALS template subscriptions are off for this fairy (template :4528-4535, :2257/:2259; fairy.py:113-115). wake() calls the same on_boot [C/I] | NONE |
| 9 | No second copy: there is no MomentBinder under top-level code/P*. working_memory_hub's `_episodic_buffer` is unrelated [C/M] | NONE |
| 10 | The persister init is duplicated (fairy.py:273-310). The drift guard catches any divergence, but an edit still has to be made in two places [C/I] | MINOR (OPEN W12c-2) |
| 11 | No replay on subscribe (tensor_fabric.py:231-242). With the switch ON, letters published during the init are lost [C/I] | MINOR (OPEN W12c-1) |
| 12 | Early init fails, so the restore skips and the set stays unconsumed. on_boot's own block retries the init, but the restore waits for the next boot [C] | NONE (OPEN W12c-3) |
| 13 | 0 CR, before and after [M] | NONE |

---

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
