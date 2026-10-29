# W10 review (nous/w10-liveness) — independent refutation attempt

Tags: [C] read in code, [M] measured, [I] inference. Line numbers are on the branch.

| # | finding | file:line | tag | severity | verdict |
|---|---------|-----------|-----|----------|---------|
| 1 | Controls: 4 tests fail on main's file (3 AttributeError, 1 assert), all 11 pass on branch with W10_REF_PATH; w10_mutants.py kills M1–M7, exit 0 | code/tests/test_w10_liveness.py, code/tests/w10_mutants.py | [M] | NONE | HOLDS |
| 2 | Switch is OFF unless exactly "1": tried unset, "0", "", "true", "TRUE", "yes", " 1", "1 ", "01" — none enable it | code/consciousness/heartbeat_registry.py:314 | [C][M] | NONE | HOLDS |
| 3 | Own differential main vs branch (POOL_SIZE=0, manual drain, frozen clock): _last_delivered_ts, _obj._last_tick/_tick_count, _error_counts, _in_flight, _total_*, _dropped_full, _slow_counts, stats, stdout identical for all 10 env values × {normal, no 'beat', beat=None, beat="7", empty callbacks, queue Full, in-flight hog, flag flipped between pulse and drain, raising callback} | /tmp/w10r/diff2.py (scratch) | [M] | NONE | HOLDS |
| 4 | Only divergence found: switch ON + non-dict pulse_data → pulse() raises at the new `pulse_data.get` BEFORE the citizen stamp loop, so _last_delivered_ts/_last_tick are NOT stamped (main stamps, then raises). Unreachable: both callers pass a dict with int beat | heartbeat_registry.py:317; heartbeat_pacemaker.py:237,271 | [M][C] | MINOR | REFUTED (unreachable today) |
| 5 | With no 'beat' key, _last_handled_beat falls back to _liveness_beat read at DELIVERY time, not submit time → a lagging fairy can look 1+ beats fresher (measured: delivered pulse-2 data recorded as beat 3). Report-only; real callers always send beat | heartbeat_registry.py:266 | [M] | MINOR | HOLDS |
| 6 | No reader of _last_handled_ts/_last_handled_beat/_liveness_* outside break_room.py; watchdog reads only _last_delivered_ts (unchanged) | directory/handlers/heartbeat.py:342-358,515-516,682 | [C] | NONE | HOLDS |
| 7 | No second copy: only one HeartbeatRegistry with _deliver_one; fairies/P20_Somatic/circulation/heartbeat_sync.py:218 is an unrelated sync-tracker class. No heartbeat_registry under code/P*_ or archived templates | code/consciousness/heartbeat_registry.py:31 | [C] | NONE | HOLDS |
| 8 | Organ templates cite `heartbeat_registry.pulse():318-332` for the stamp loop; it moved to ~372-386 (+11 lines). Comment drift only; templates need Ace's permission to edit | fairies/P00_Autonomic/organ_template/Organ_Template_0_3_0.py:56,5186 | [C] | MINOR | HOLDS |
| 9 | CRLF preserved (561/561 → 580/580 lines CRLF; new files all CRLF); registry diff is additions only (0 removed lines) | heartbeat_registry.py | [M] | NONE | HOLDS |
| 10 | Registry persists nothing (no open/dump/sqlite); break_room writes only in dump_snapshot() when called; CLI reads a snapshot file and works (text + --json, OFF note, in-flight/error annotations) | break_room.py:62-66,120-133 | [C][M] | NONE | HOLDS |
| 11 | CLI cannot see a live process: no one calls dump_snapshot(), so the "small CLI" only works after a manual in-process dump (docstring says so) | break_room.py:16-23 | [C][I] | MINOR | HOLDS |
| 12 | Report crashes on non-int beat strings (int("7.5") ValueError); beat=None reported as "never delivered" instead of unknown | break_room.py:51,95-97 | [M] | MINOR | HOLDS |
| 13 | Plane gating × circadian multiplier can push a fairy's divisor above n_beats → falsely listed as napping. Report-only, cannot reach watchdog | break_room.py:93; heartbeat_registry.py:405-415 | [I] | MINOR | HOLDS |
| 14 | snapshot() copies _error_counts/_in_flight without their locks; under 3.14t a concurrent write could raise in the report (never in the heart) | break_room.py:57-58 | [I] | MINOR | HOLDS |

**Overall: no BLOCKER/MAJOR — the watch-only claim survives; nothing the watchdog reads changes on any reachable path, switch on or off. Ship; MINORs are optional follow-ups.**
