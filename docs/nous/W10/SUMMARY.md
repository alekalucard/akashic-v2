# W10: liveness from delivery, plus a break-room report

Branch `nous/w10-liveness`. Switch: **`AKASHIC_LIVENESS_FROM_DELIVERY`**. It is OFF when unset. Only the exact value `"1"` turns it on (`os.environ.get(NAME, "0") == "1"`, `code/consciousness/heartbeat_registry.py:312`) [C].

## What was wrong
- On main, `HeartbeatRegistry.pulse()` sets `_last_delivered_ts[name] = now` for **every citizen** in `_CITIZEN_OBJECTS`. It does this before any callback is queued (main `:354`, branch `:372`) [C].
- It sets it again when a fairy's work tick is skipped by plane gating (main `:398`, branch `:417`) [C].
- It sets it again when a fairy's previous callback is still running (main `:404`, branch `:424`) [C].
- The only stamp that means "the handler returned" is in `_deliver_one` (main `:252`, branch `:262`) [C].
- So a citizen with no callback, a callback that is always gated, or a callback stuck for minutes all look freshly delivered.

## What was built (4 files)
- **`code/consciousness/heartbeat_registry.py`** (+23/-3, CRLF kept: 581 lines and 581 CRs [M]).
  - With the switch ON, the three blanket stamps are skipped (`:371`, `:416`, `:423`).
  - `_deliver_one` still stamps on a successful return. It now also records which beat that was, in `_last_delivered_beat` (`:263-264`).
  - `pulse()` records the current beat in `_liveness_beat` (`:314-315`).
  - A callback that raises is not stamped, the same as before [C].
  - With the switch OFF, the same writes happen as on main. The only additions are one attribute write per beat (`:313`) and three unused fields in `__init__` (`:110-112`) [C].
- **Not changed on purpose:** the batch stamps of `_obj._last_tick` and `_obj._tick_count` (`:373-376`). They are the watchdog's main liveness signal (`code/directory/handlers/heartbeat.py:278-326`) and the input to its death veto (`:490-507`). Gating them would put every gated or callback-less citizen on the death and restart path. See OPEN 1.
- **`code/consciousness/break_room.py`** (new, read-only, CRLF). `break_room(registry_or_snapshot, n_beats)` lists, with name, plane, last beat, beats since and notes ("callback still running", "N callback errors"):
  - every citizen that has no heartbeat callback (switch ON or OFF);
  - with the switch ON, every fairy never delivered to;
  - with the switch ON, every fairy with no delivery in more than N beats.
  With the switch OFF the report says no delivery data is being collected and lists only the citizens with no callback.
- **How the CLI gets its data:** the registry persists nothing and exposes nothing. `heartbeat_registry.py` has no open, write or json call; `get_status()` has no timestamps; `server.py:5218-5229` only creates the registry and registers one fairy [C]. So the report runs in one of two ways:
  - **In-process**, as a function call.
  - **Offline**, over a snapshot file that you write in-process first with `dump_snapshot(registry, path)`. Then run `python code/consciousness/break_room.py snap.json --beats 10 [--json]`.
  Nothing in her code calls `dump_snapshot`. The CLI never attaches to her running process.
- **`code/tests/test_w10_liveness.py`**: 11 tests. They use a subclass with POOL_SIZE=0 (no worker threads), a stub for `fairy_template.citizen_registry`, and a temp dir only.
- **`code/tests/w10_mutants.py`**: runs the suite against main's file, the fix, and 7 mutants. It exits non-zero if anything is unexpected.

## Who reads `_last_delivered_ts`
All readers are in `code/directory/handlers/heartbeat.py` [C]. With the switch OFF, all of them get exactly main's data [M: differential test].

| reader | what it does with a stale name | when the switch is ON |
|---|---|---|
| `:342-343` | prints a debug count | nothing changes |
| `:349-376` tertiary check | a non-citizen (`:359`) delivered to within `timeout_sec` (300 s, `:39`) gets its heartbeat synced and is promoted to running | a stale non-citizen is not synced, so it can become a death candidate |
| `:515-525` death veto | a death candidate is spared if delivery was less than 300 s ago | no veto. After 3 checks (`:44`) it is marked dead (`:606`). `DirectoryFairy._on_dead_fairy` then **evicts** it from capability_index and publishes `fairy.dead` (`code/directory/fairy.py:630-637`). SomaticMindFairy **auto-restarts** it (`code/fairies/P20_Somatic/SomaticMindFairy/fairy.py:666, :7757`). The freeze-wave filter (`heartbeat.py:542-564`) can still suppress 10 or more simultaneous deaths. |
| `:680-687` stale check | a running fairy silent for more than 180 s (`:94`) is spared the FAIRY_STALE alarm if delivery was less than 180 s ago | the **alarm** fires: a FAIRY_STALE log line, and if 3 or more go stale at once, an entry in `state/wave_context.jsonl` (`:721-752`) |

Who is newly exposed when the switch is ON [I]: only fairies whose object check fails. In practice:
- non-citizen engines whose callback raises every beat, runs longer than 180/300 s, or is never queued because the queue is full;
- citizens stored as `None`.

Citizens with a real object are still batch-stamped through `_last_tick`/`_tick_count`, so the main check keeps them alive. With the switch OFF, none of the restart, evict or alarm paths can fire differently from main.

## Who reads `_last_tick` / `_tick_count` (not affected by W10) [C]
- the watchdog's main check and diagnostics (`handlers/heartbeat.py:229-326`, `:490-507`);
- `directory/fairy.py:617-627`;
- `fairies/P00_Autonomic/unified_citizen_wiring.py:159-161`;
- `fairy_template/consolidated.py:1478`;
- `Organ_Template_0_3_0.py:53-61` and `:5187-5205` (`AKASHIC_LEAN_HEARTBEAT` relies on the batch stamp);
- about 6 fairies that compute their own `dt`.

None of them is affected, because those writes are unchanged.

## Is there a second copy?
No [M: grep]. `_last_delivered_ts` and `_now_liveness` appear only in the registry and in `handlers/heartbeat.py`. `fairies/P20_Somatic/circulation/heartbeat_sync.py:218` is an unrelated class that happens to share the name. The top-level `P10_Memory/.../Organ_Template_0.3.0.py` only registers callbacks and writes `_last_tick`.

## Tests [M] (`python3 code/tests/w10_mutants.py`, switch unset; exit 0)
| target | result | failing tests |
|---|---|---|
| main's file (controls) | FAILED (4 failures, 1 error) | control_citizen_not_stamped, gated_not_stamped, in_flight_not_stamped, real_delivery_with_beat, break_room_lists_nappers |
| fix | OK 11/11 | none |
| M1: gated skip still stamps | FAIL | gated_beat_not_stamped |
| M2: default `"1"` (ON when unset) | FAIL | off_when_unset, off_differential_vs_main, break_room_off |
| M3: `!= "0"` | FAIL | only_exact_1_is_on |
| M4: in-flight skip still stamps | FAIL | in_flight_skip_not_stamped |
| M5: `_obj` stamps gated too | FAIL | object_tick_stamps_unchanged |
| M6: beat not recorded | FAIL | real_delivery_with_beat, break_room_lists_nappers |
| M7: citizen loop still stamps | FAIL | control_citizen_without_callback_not_stamped |

Switch-off identical: `test_off_differential_vs_main` runs the same scenario on main's file and on the branch file. Stamped names, error counts, object ticks, stats, in-flight set and pulse count are all equal [M].

## Could NOT verify
- Anything about her live process: how many fairies are actually napping, whether any citizen is stored as None, whether switching ON causes restarts in practice.
- The watchdog and restart chain end to end: I read it but did not run it (running fairies is forbidden here).
- Timing under 3.14t free-threading: the tests drain the queue synchronously.

## OPEN
1. With the switch ON, "liveness stamped only when the handler ran" applies to `_last_delivered_ts` only, not to `_obj._last_tick`/`_tick_count`. So a citizen object that does nothing still passes the watchdog's main check. Gating those stamps too needs its own switch and a watchdog change first.
2. (review #6, MAJOR before anyone switches ON) Non-citizen engines lose the busy-fairy protection from the 2026-04-15 fix:
   - a callback running more than 180 s gives FAIRY_STALE (`handlers/heartbeat.py:682`);
   - more than 300 s on 3 checks gives death, eviction and a UMF restart (`:515`).
   This is the honest outcome, but it is a behaviour change. It is not fixed: any "fix" would re-add a stamp that is not a delivery.
3. (review #8, minor) With the switch ON, a pulse without a `beat` key records the beat current when the callback finishes, not the one it was delivered on (`heartbeat_registry.py:263-264`). The pacemaker does send `beat` (`heartbeat_pacemaker.py:272`) [C].

## CHECK THESE 3
1. With the switch OFF, stamping is the same as main: `code/consciousness/heartbeat_registry.py:312, :371, :416, :423`.
2. With the switch ON, the death veto loses its blanket input, so a stuck non-citizen engine can be evicted and restarted: `code/directory/handlers/heartbeat.py:515-525` → `code/directory/fairy.py:630-637` → `code/fairies/P20_Somatic/SomaticMindFairy/fairy.py:7757`.
3. Citizens with a real object stay alive with the switch ON because `_last_tick`/`_tick_count` are still batch-stamped: `heartbeat_registry.py:373-376`, read at `handlers/heartbeat.py:282-292, :490-507`.

## REVIEW
A fresh remote session reviewed the change. It saw only the diff and the task, not my reasoning. It ran two passes; this is the final (second-pass) table, verbatim:

| # | finding | file:line | tag | severity | verdict |
|---|---|---|---|---|---|
| 1 | Main's file: 5 of 11 tests fail (citizen control, gated, in-flight, nappers, real-delivery ERROR). Branch file: 11/11 OK. | tests/test_w10_liveness.py | [M] | NONE | HOLDS |
| 2 | w10_mutants.py: MAIN fails 5, FIX passes, M1-M6 each fail 1-3 tests. Two gaps: it always exits 0, so CI can't use it, and it has no mutant that removes the citizen-loop guard (`if not _lfd: _last_delivered_ts[_name]`). My earlier mutant for that guard was killed by the control test. | tests/w10_mutants.py:33-38; heartbeat_registry.py:371 | [M] | MINOR | HOLDS → FIXED after review (exit code + M7) |
| 3 | Switch-off comparison with main, re-run: unset, "0", "", "true", " 1", "1 ", "01", "TRUE", "yes" x {normal, no callbacks, no 'beat' key, queue Full}: all identical. Flipping on then off converges back to main. | heartbeat_registry.py:312 | [M] | NONE | HOLDS |
| 4 | New commit touches only those 3 files. heartbeat_registry.py byte-identical to 0014c7f. Ignoring CR, break_room.py and the test file have no content change. | diff 0014c7f..1c46ac7 | [M] | NONE | HOLDS |
| 5 | CRLF now complete: break_room 134/134, test 196/196, mutants 38/38. Old #10 fixed. | - | [M] | NONE | HOLDS |
| 6 | Still open, only matters once switched on: engines that are not citizens lose the busy-fairy protection (stale warning after 180s; past 300s, three checks in a row, no veto, death list). Code unchanged. List it as OPEN in SUMMARY. | handlers/heartbeat.py:515,682 | [C]+[I] | MAJOR (before turning it on) | HOLDS for OFF → **OPEN 2** |
| 7 | Still true: _obj._last_tick and _tick_count are stamped for every citizen even when on. Deliberate and tested (M5 kills the mutant). | heartbeat_registry.py:373-378 | [C] | MINOR | HOLDS → **OPEN 1** |
| 8 | Still open, only when on: a pulse with no 'beat' key records the beat current at finish, not the one delivered. | heartbeat_registry.py:263 | [C]+[I] | MINOR | HOLDS → **OPEN 3** |
| 9 | Fields read, second copy, break-room CLI: unchanged from pass 1 (no missed caller or copy; the CLI only reads a snapshot file). | - | [C] | NONE | HOLDS |

Reviewer's overall verdict: could not refute it. Switch off = main, controls fail on main, fix passes, every mutant is killed. Resolve #6 before switching on.
