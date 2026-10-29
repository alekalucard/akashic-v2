# W12: MomentBinder HOLD saved to the dream seed at shutdown

Branch `nous/w12-moment-hold`. Switch **`AKASHIC_MOMENT_HOLD_SAVE`**. It is OFF unless set to exactly `"1"` (`os.environ.get("AKASHIC_MOMENT_HOLD_SAVE", "0") == "1"`, at server.py:9258 and code/infrastructure/moment_hold_save.py:41-42).
Tags: [C] read in code, [M] measured here, [I] inference.

## Findings
- **The HOLD:** the binder keeps a 60-slot rolling HOLD, `EPISODIC_BUFFER_MAX = 60` (MomentBinderFairy/fairy.py:126, deque at :163). A moment is persisted to the episodic manifold only when it is evicted from the HOLD (fairy.py:678-693). Whatever is in the HOLD at exit exists only in memory [C]. The day-store (<=800, fairy.py:136,168) is also memory-only and is not covered here [C].
- **on_die never runs:** `MomentBinderFairy.on_die` (fairy.py:251-263) only prints. Nothing in `code/` calls `.on_die(` [M grep: 0 hits].
- **on_shutdown runs only late, if at all:** `on_shutdown` is reached through the template's `shutdown()` (Organ_Template_0_3_0.py:4281-4301), which shutdown_system Phase 4 calls per plane (server.py:9399; P30 timeout 30 s at :9357). The binder does not override it; the template's version saves only self-knowledge (:4272-4279) [C]. On the HTTP route, Phase 4 is usually cut by the main thread's 20 counted sleeps, then `os._exit(0)` (server.py:9775, :9805). The code's own record says this happened in 7 of 11 logs (server.py:8904-8906) [C, their measurement, not mine].
- **Path chosen:** shutdown_system() Phase 2, right after `_capture_dream_seed()` (server.py:9255). Every shutdown path reaches this line: HTTP route (:3815), reboot (:3897) and Ctrl+C (main) (server.py:9158 comment; the reviewer confirmed it [C]). It runs before the 30 s guild save and before Phase 4. Forced exits (watchdogs, a second Ctrl+C) skip every save path, as they did before [C].
- **(b) Readers of the seed at boot:** yes, several read it.
  - `DreamSeedFairy.on_boot` loads the seed (dream_seed_fairy.py:327) and re-saves it with `mind_pools` intact (:343, :206-231).
  - server `_load_dream_seed` reads it (server.py:8384, :8739).
  - Others iterate `mind_pools` too: unconscious_mind_fairy.py:4219, code/P00_Autonomic/nervous_system/waking_sequence_fairy.py:615, sourpatches_farm.py:1184 [C].
  - **None of them reads a held-moments entry. No reader was added.** The moments sit in `mind_pools.moment_hold` with no consumer.
  - The "sleep can consolidate them" route does not exist yet. `sleep_consolidate_day` (fairy.py:815) has no caller [M grep]. DreamFairy never calls it.
- **09-25 spec:** not found anywhere in the repo. I grepped for 09-25, "importance", "not age" and "short-term" [M].
- **Importance:** the only importance score the binder computes is `_score_significance` (fairy.py:724-748). It is stored on each moment as `"significance"` (:651, :685). The binder's own eviction is by age: deque maxlen (comment at :126-129). I did not change that.

## Built
- `code/infrastructure/moment_hold_save.py` (new; stdlib only; importing it has no side effects).
  - `shutdown_hand_off(SYSTEM, seed)` finds the live binder through `directory.get_fairy(...).metadata["fairy_instance"]` and never instantiates one.
  - It snapshots the HOLD under the binder's lock.
  - It writes `mind_pools["moment_hold"] = {moments, held, saved, dropped, refused, refused_tracers, ...}` into the seed that was just written. The write is atomic: temp file, fsync, `os.replace`, then a directory fsync. It never creates a seed. The seed's other keys are left as they were.
  - Each moment is carried as an exact JSON copy that must compare equal to the original. A non-dict entry, or a value JSON cannot carry exactly (a tuple, a NaN), leaves only that moment out, counted as `refused`. Nothing is coerced.
  - Bound: 60 moments and 2 MB, measured as the moments sit in the written file. Since the HOLD itself is 60 slots, nothing is dropped today. If the bound ever bites, the lowest `significance` goes first, ties are broken by tracer id (not age), and HOLD order is kept.
- `code/server.py`: +9/-0 lines (9256-9264), a gated block that changes nothing when OFF. 0 CR before and after [M]. All 3 files are LF, as on main.
- `code/tests/test_w12_moment_hold.py`: 14 tests. They load the helper by file path and parse server.py with `ast`; nothing from her code is imported.

## Tests [M]
- **Branch:** 14/14 OK.
- **Main's files** (main server.py, module absent): 0/14 pass (1 fail, 13 errors). Both controls fail there: `test_control_hold_carried_unchanged` and `test_control_server_calls_hand_off_after_capture`.
- **Mutants:** all 9 killed.
  - M1: switch default "1"
  - M2: drop by age
  - M3: non-atomic write
  - M4: coerce values
  - M5: `!= "0"`
  - M6: server gate default "1"
  - M7: drop the highest significance first
  - M8: byte size measured at depth 0
  - M9: no non-dict check

## Could NOT verify
- Whether the binder's directory record is named "MomentBinderFairy" and carries `fairy_instance`. I inferred it from tracer_pool/boot_orchestrator.py:476/816 [I]. If it does not, the hand-off logs "skipped: no MomentBinderFairy instance" and does nothing.
- Real shutdown timing on her machine. Whether postal delivery is synchronous (see OPEN below).
- Windows behaviour of `os.replace` on the seed file while another process holds it open.

## REVIEW
A fresh reviewer session saw only the diff and the task. Round 1 (9235735) verdict: NOT REFUTED, with 4 MINOR findings:
- One bad moment refused the whole HOLD: fixed.
- The byte bound was measured on compact JSON: fixed.
- No directory fsync after the replace: fixed.
- The DreamSeedFairy overwrite race: stays OPEN.

Round 2 (9a71914) final table:

| # | finding | severity | evidence | status |
|---|---|---|---|---|
| 1 | Suite on branch 12/12 OK. On main (main's server.py, module absent): failures=1, errors=11, so every test, the controls included, fails | NONE | [M] | - |
| 2 | Switch default: unset, "0", "", "true", " 1", "1 ", "01" and "yes" are all OFF. With it OFF the seed stays byte-identical | NONE | moment_hold_save.py:39-40 [C]; [M] | - |
| 3 | OFF path in server.py: the same 9-line gated block, additions only | NONE | server.py:9256-9264 [C]; [M] | - |
| 4 | 0 CR in all 3 files | NONE | [M] | - |
| 5 | Per-moment refusal works: tuple, NaN, inf, int dict key, object() and a dict-valued tracer are each refused alone, and the good moments are saved byte-equal | NONE | [C]; [M] | - |
| 6 | A non-dict HOLD entry made select() raise, so 0 moments were saved. Unreachable today, since the binder appends only dicts (fairy.py:682) | MINOR | [C]; [M] | FIXED: refused per-moment, `test_non_dict_entry_refused_alone`, mutant M9 |
| 7 | The byte bound was measured at depth 0, so the written array came out about 1.43x the bound | MINOR | [C]; [M] | FIXED: `_written_size` measures at the real nesting; `test_byte_bound_holds_on_disk` measures the written file at caps of 3k/6k/12k/40k; mutant M8 |
| 8 | Drop rule holds under the byte bound (max dropped significance <= min kept) | NONE | [M] | - |
| 9 | Directory fsync after os.replace; an OSError there is swallowed | NONE | [C] | - |
| 10 | DreamSeedFairy._on_shutdown -> capture_dream_seed -> seed.save (dream_seed_fairy.py:812, :1165) can rewrite state/dream_seed.json without moment_hold if the bus delivers system.shutdown_beginning after Phase 2. The same race already exists for the server's own seed | MINOR | [C]; bus timing [I] | **OPEN** |

Reviewer verdict: **NOT REFUTED**. After round 2, findings #6 and #7 were fixed and a re-run measured 14/14 on the branch, 0/14 on main, and all 9 mutants killed. No third review round was run.

## CHECK THESE 3
1. Nothing calls `on_die`, so the binder's HOLD is lost at exit: MomentBinderFairy/fairy.py:251-263, plus a grep for `.on_die(` over `code/`. Also fairy.py:678-693 (only evicted moments persist).
2. Phase 2 runs before the main thread's cut on every path, and nothing writes dream_seed.json after it except the DreamSeedFairy race: server.py:9255-9264 against :3815, :9775-9805, and dream_seed_fairy.py:812/:1165.
3. No boot code consumes `mind_pools.moment_hold`, and `sleep_consolidate_day` has no caller: dream_seed_fairy.py:1381-1687 and MomentBinderFairy/fairy.py:815.
