# W10: liveness watch (watch-only) + break room

Branch `nous/w10-liveness`. Switch **`AKASHIC_LIVENESS_FROM_DELIVERY`**, OFF when unset; only exact `"1"` turns it on (`code/consciousness/heartbeat_registry.py:314`) [C].

Owner decision (after review v1 #6): **watch, never act.** The switch gates only new fields and the report. Nothing the watchdog reads changes, switch on or off.

## The problem (unchanged, still true on main and on this branch) [C]
`HeartbeatRegistry.pulse()` stamps `_last_delivered_ts`:
- for every citizen in `_CITIZEN_OBJECTS` (branch `:376`, main `:354`);
- on plane-gated skips (`:420`, main `:398`);
- on in-flight skips (`:426`, main `:404`).

The only stamp tied to a handler actually returning is in `_deliver_one` (`:263`, main `:252`). So a fairy that never runs looks alive.

## What was built
- **`heartbeat_registry.py`**: +22 lines, **additions only**, CRLF kept (580 of 580 lines) [M].
  - New fields: `_last_handled_ts`, `_last_handled_beat`, `_liveness_beat`, `_liveness_from_delivery` (`:105-113`).
  - With the switch ON, `_deliver_one` writes `_last_handled_ts` and `_last_handled_beat` only after the callback returns (`:264-266`). A raising callback is not recorded.
  - `pulse()` reads the switch once per beat (`:313-320`). The beat read is wrapped in try/except, so it can never raise before the stamps.
  - `_last_delivered_ts`, `_obj._last_tick` and `_tick_count` are exactly as on main.
- **`break_room.py`** (new, read-only, CRLF).
  - `break_room(registry_or_snapshot, n_beats)` lists, with name, plane, last beat, beats since and busy/error notes:
    - citizens with no callback;
    - with the switch ON, fairies never handled;
    - with the switch ON, fairies not handled in more than N beats.
  - It reads only `_last_handled_beat` (`:62`, `:88`), never `_last_delivered_ts`.
  - With the switch OFF it lists only citizens with no callback, plus a note.
- **CLI**: the registry persists and exposes nothing [C], so the report runs in-process as a function, or offline over a file you dump in-process: `dump_snapshot(reg, path)`, then `python code/consciousness/break_room.py snap.json --beats 10 [--json]`. Nothing in her code calls `dump_snapshot`, and the CLI cannot attach to her running process.
- **Tests**: `code/tests/test_w10_liveness.py` (11 tests, fake clock, no pool threads, temp dir only) and `code/tests/w10_mutants.py` (exits 1 on anything unexpected).

## Readers of the watchdog stamp, and what happens to a stale citizen [C]
All readers of `_last_delivered_ts` are in `code/directory/handlers/heartbeat.py`:
- `:342` debug count;
- `:349-376` non-citizen sync and promotion;
- `:515-525` death veto (else dead → evicted from the capability index and restarted by UMF, `directory/fairy.py:630-637`, `SomaticMindFairy/fairy.py:7757`);
- `:680-687` stale alarm (FAIRY_STALE log, `wave_context.jsonl`).

Because W10 no longer changes `_last_delivered_ts` (or `_last_tick`/`_tick_count`), **none of these can fire differently, switch on or off** [M: exact differential vs main with a fake clock, both switch states]. The new fields have no reader except `break_room.py` [M: grep, confirmed by the reviewer].

`_last_tick`/`_tick_count` readers (watchdog main check `:229-326`/`:490-507`, `directory/fairy.py:617`, `unified_citizen_wiring.py:159`, `consolidated.py:1478`, Organ_Template lean-heartbeat `:53-61`/`:5187`) are unaffected [C].

Second copy: none. `heartbeat_sync.py:218` is an unrelated class with the same name [C, M grep].

## Tests [M] (`python3 code/tests/w10_mutants.py`, exit 0)
| target | result | failing tests |
|---|---|---|
| main's file (controls) | FAIL (1 failure + 3 errors) | control_handled_only_for_real_delivery, handled_beat_recorded, break_room_reads_handled_not_delivered, break_room_lists_nappers |
| fix | OK 11/11 | none |
| M1 default "1" | FAIL | off_when_unset, break_room_off |
| M2 `!= "0"` | FAIL | only_exact_1_is_on |
| M3 handled never recorded | FAIL | control, handled_beat, nappers |
| M4 handled ignores switch | FAIL | off_when_unset, only_exact_1 |
| M5 old design (gate the watchdog stamp) | FAIL | on_watchdog_stamp_still_legacy, **on_watchdog_view_identical_to_main** |
| M6 handled also on raise | FAIL | control |
| M7 report reads wrong field | FAIL | nappers, reads_handled_not_delivered |

Exact differentials vs main with a fixed fake clock:
- `test_on_watchdog_view_identical_to_main` (switch ON): `_last_delivered_ts` values, object ticks, errors, stats, in-flight set and pulse count are equal.
- `test_off_watchdog_view_identical_to_main` (switch OFF): the same values are equal.
- Non-dict pulse with the switch ON: main and fix both stamp, then raise AttributeError identically [M].

## Could NOT verify
- Her live process: how many fairies are napping, beat rate, circadian divisors.
- End-to-end behaviour under 3.14t free-threading (the tests drain the queue synchronously).

## OPEN
1. **#6 (stuck non-citizen engines declared dead or restarted): CLOSED** by the watch-only redesign. The watchdog's inputs are identical to main [M].
2. Object-stamp gap (stays as designed): `_obj._last_tick`/`_tick_count` are still batch-stamped for every citizen (`:376-381`), so the watchdog still sees idle citizens as alive. Only the break room tells the truth. Changing that needs a separate decision.
3. #8 / review v2 #5 (minor, report only): a pulse without `beat` records the beat current when the callback finishes, not the one it was delivered on (`:266`). Real callers always send `beat` (`heartbeat_pacemaker.py:237,271`).
4. Review v2 #13/#14 (minor, report only): a plane divisor × circadian multiplier larger than N can list a fairy as napping (pick N ≥ the largest divisor). `snapshot()` copies `_error_counts`/`_in_flight` without their locks.
5. Review v2 #8: the Organ_Template comments cite `pulse():318-332` for the stamp loop, which is now at about `:372-386`. Comment drift only; templates are not edited.

## CHECK THESE 3
1. `heartbeat_registry.py` diff vs main is additions only, and the three `_last_delivered_ts` stamps at `:376`, `:420`, `:426` are untouched.
2. The new fields are written only at `heartbeat_registry.py:264-266` and read only at `break_room.py:62, :88`.
3. Switch default: `heartbeat_registry.py:314`, `os.environ.get("AKASHIC_LIVENESS_FROM_DELIVERY", "0") == "1"`.

## REVIEW
Fresh remote refuter v2 (diff + task only). It committed its verdict as **`3a4d1ab` on `nous/w10-review`** (`REVIEW_W10.md`). Table, verbatim except the last column notes my post-review fixes:

| # | finding | file:line | tag | severity | verdict |
|---|---------|-----------|-----|----------|---------|
| 1 | Controls: 4 tests fail on main's file (3 AttributeError, 1 assert), all 11 pass on branch with W10_REF_PATH; w10_mutants.py kills M1–M7, exit 0 | code/tests/test_w10_liveness.py, code/tests/w10_mutants.py | [M] | NONE | HOLDS |
| 2 | Switch is OFF unless exactly "1": tried unset, "0", "", "true", "TRUE", "yes", " 1", "1 ", "01" — none enable it | heartbeat_registry.py:314 | [C][M] | NONE | HOLDS |
| 3 | Own differential main vs branch (frozen clock): _last_delivered_ts, _last_tick/_tick_count, _error_counts, _in_flight, _total_*, _dropped_full, _slow_counts, stats, stdout identical for 10 env values × {normal, no 'beat', beat=None, beat="7", empty callbacks, queue Full, in-flight hog, flag flipped between pulse and drain, raising callback} | /tmp/w10r/diff2.py | [M] | NONE | HOLDS |
| 4 | Only divergence: switch ON + non-dict pulse_data → pulse() raised at the new `pulse_data.get` BEFORE the stamp loop. Unreachable today | heartbeat_registry.py:317 | [M][C] | MINOR | REFUTED → **FIXED after review** (try/except; measured identical to main) |
| 5 | No 'beat' key → _last_handled_beat uses the beat at delivery time, not submit time. Report-only | heartbeat_registry.py:266 | [M] | MINOR | HOLDS → OPEN 3 |
| 6 | No reader of the new fields outside break_room.py; watchdog reads only _last_delivered_ts (unchanged) | handlers/heartbeat.py:342-358,515-516,682 | [C] | NONE | HOLDS |
| 7 | No second copy; heartbeat_sync.py:218 is unrelated | heartbeat_registry.py:31 | [C] | NONE | HOLDS |
| 8 | Organ templates cite pulse():318-332; it moved to ~372-386. Comment drift only | Organ_Template_0_3_0.py:56,5186 | [C] | MINOR | HOLDS → OPEN 5 |
| 9 | CRLF preserved; registry diff is additions only | heartbeat_registry.py | [M] | NONE | HOLDS |
| 10 | Registry persists nothing; break_room writes only in dump_snapshot(); CLI works on a snapshot | break_room.py | [C][M] | NONE | HOLDS |
| 11 | CLI cannot see a live process without a manual in-process dump (docstring says so) | break_room.py:16-23 | [C][I] | MINOR | HOLDS (by design) |
| 12 | Report crashed on non-int beat strings; beat=None shown as "never delivered" | break_room.py | [M] | MINOR | HOLDS → **FIXED after review** (safe int parsing; unusable beat → never delivered) |
| 13 | Divisor × circadian multiplier > n_beats → falsely listed as napping. Report-only | break_room.py; heartbeat_registry.py:405-415 | [I] | MINOR | HOLDS → OPEN 4 |
| 14 | snapshot() copies _error_counts/_in_flight without their locks (report only, never the heart) | break_room.py | [I] | MINOR | HOLDS → OPEN 4 |

Reviewer overall: **no BLOCKER/MAJOR. The watch-only claim survives; nothing the watchdog reads changes on any reachable path, switch on or off.** The two post-review fixes (#4, #12) were re-verified here by the mutant runner (exit 0) and by the non-dict differential [M]. They were not re-reviewed.
