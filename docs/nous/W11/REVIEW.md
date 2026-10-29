# W11 adversarial review: `nous/w11-bind-carryover` (dd483ad)

Reviewer worked only from `git diff origin/main...origin/nous/w11-bind-carryover` and the W11 task text.
Tags: **[C]** read in code (file:line on the branch), **[M]** measured by something I ran, **[I]** inference.
Nothing was booted: no server.py, no fairy, no launcher, no real `*.manifold`. All data was synthetic, in temp dirs.

## What the diff actually is
It does not add a new carryover. It **adds env switches to the existing TARDIS-B persist/replay layer** (`tardis_backlog.py`, built 10-15) plus four extras:
1. `tardis_fix.on()` returns True when `AKASHIC_BIND_CARRYOVER=1` (b_persist) or `AKASHIC_BIND_TIMING=1` (l0_timing) [C tardis_fix.py:96,111].
2. With carryover ON, queue items are written verbatim (every field, own key order) when they survive a JSON round trip exactly; otherwise they fall back to today's record [C tardis_backlog.py:627-630,644-660].
3. With carryover ON, `done-*` files are never pruned [C tardis_backlog.py:1032].
4. `persist_owner()` plus a server.py hook on the reboot and Ctrl+C routes, which never set the shutdown Event [C server.py:3884,9790,9136].
5. With timing ON, `l.evict` / `u.evict` laps split the eviction scan out of `l.new` / `u.new` [C manifold_memory.py:2280-2285,2736-2741].

## 1. Tests, controls, mutants
- Branch: 19/19 pass [M `python3 -I code/tests/test_w11_bind_carryover.py`].
- Main tree (main's `infrastructure/{__init__,tardis_fix,tardis_backlog,tardis_timing,manifold_memory}.py` + `server.py`): 8 fail, 11 pass. **All 7 CONTROL tests fail**, as does `test_replay_bookkeeping_key_not_carried` (unmarked, also W11-only) [M].
- `w11_mutation_run.py <main_tree>`: main fails 8, branch 0, and **every one of M1-M7 fails at least one test** [M].
- My own mutants [M `mut2.py`, scratch]:
  - **N1: reboot hook moved after `os._exit(0)` (unreachable). SURVIVES (0 failures).** `_server_fn()` only checks that the call names `{reboot, ctrl_c}` appear somewhere in the AST [C test_w11_bind_carryover.py:340-354]. The test never checks where the hook sits, so a hook placed too late or unreachable passes. Moving the Ctrl+C call after `shutdown_system()` would survive the same way [I].
  - N2 (ENV_ALIAS values swapped): caught by 4 tests.
  - N3 (verbatim without `_valid_item`, so an item with a bad concept would be rejected whole at replay): caught by 1 test.
  - N5 (verbatim skips the seq advance): caught by 1 test.
  - N4 (verbatim moved before the concept filter): survives but is an **equivalent mutant**. `_valid_item` rejects every item the filter would change, so the output is the same [I].

## 2. Switch defaults (both env vars unset)
- `env_on()` is False unless the value is exactly `"1"`, and then `on()` takes main's code path unchanged [C tardis_fix.py:99-115]. The only extra work is one `dict.get` per call, plus `os.environ.get` for aliased keys. A1 (`a1_fastlink`, on every link) has no alias [C :96].
- **File turns b_persist + l0_timing ON, env unset:** `_carry()` is False, so `item_record` / `_finish_current` run main's code. I measured the persisted records for 500 synthetic items (with bad concepts, `feeling=None`, metadata, `_tf_replay` keys): **byte-identical to main, sha256 bd2e088a…, 96,550 bytes on both** [M offeq.py].
- With l0 armed and `AKASHIC_BIND_TIMING` unset, `_w11e` is None, so the laps are main's. `stats()` adds only keys that are present (`if k in w`), so the extra tuple entries in `DEEP_*` don't change the log line [C manifold_memory.py:2280; tardis_timing.py:278; M test_off_no_new_laps].
- The server hook returns before importing anything [C server.py:9140-9141]. `persist_owner` returns False [C tardis_backlog.py:327-328].
- Result: no path changes behaviour with the switches OFF. That covers task point 5.

## 3. Callers
- `tardis_fix.on` is called from fairy.py:92 (`_tf_on`), tardis_backlog.py:126 (`_sw`), tardis_timing.py:345 (a1 only) and manifold_memory.py:341 (A1) [C grep]. Nothing calls `switch()` directly outside tardis_fix, so the env switch reaches every gate.
- `_finish_current` is called only from `_replay_file` and `_release_current`. `item_record` is called only from `_sweep`. Both are covered.
- Exit routes in server.py:
  - The HTTP shutdown route sets the Event [C :3706].
  - Reboot is hooked [C :3884].
  - Ctrl+C / SIGTERM (same handler, :9681-9682) are hooked [C :9790].
  - The SDFIX exit [C :9111] comes after the Event.
  - The watchdog `os._exit(1)` at :3894 (reboot) comes after the hook.
  - The **boot watchdog** [C :4598] and the **second Ctrl+C force exit** [C :9662] are not covered. The queue is small at boot and a forced exit is intended, so the gap is acceptable [I].
- `graceful_shutdown_fairy.py:309` (15 s watchdog `os._exit(1)`) can cut `shutdown_system()` before the cortex `on_shutdown` persist [C]. The early hook is what covers this case, which is real value [I].

## 4. Second copies
- The four `infrastructure/tardis_*` and `manifold_memory.py` modules each exist once [M find].
- There are **two `shared_postal_hub.py` files** (top-level `P00_Autonomic/…` and `fairies/P00_Autonomic/…`), and they differ [M diff].
  - `_shutdown_source()` reads the top-level one first, and that is the one server.py signals [C tardis_backlog.py:299; server.py:3705]. This predates W11 and is unchanged.
- The top-level `P30_Cognition/` has no AssociationCortexFairy copy [M ls].

## 5. Correctness claims
- **Which instance holds the binds:** server.py sets `_akashic_cortex_region` only on serial copy A [C server.py:6378,6425]. `arm()` refuses a copy with no region [C tardis_backlog.py:349], so cascade copy B (PortalGate) never owns the queue. When K2 leaves only A, A owns. Holds.
- **Exactly once:**
  - `persist_now` is guarded by `_persist_started` under a lock [C :484,701]. The hook, the Event and `on_shutdown` therefore persist once.
  - Items leave the queue through `get_nowait`, and a claim happens by atomic rename before the file is read.
  - The uuid ledger rejects a done file that is put back [M roundtrip test].
- **Fields and order:** verbatim records keep every non-`_tf_` field in insertion order, and replay hands back items equal to the originals [M test_control_persist_then_replay_roundtrip]. Items that can't be represented (tuple, NaN, int keys, `feeling=None`) fall back to today's record. **The pairs survive, but the item fields do not**: `str(None)` becomes `"None"`, and values are truncated to 256 characters [C :632-636]. That fallback is pre-existing behaviour.
- **Crash mid-write:** each boot writes a new `pending-*` file opened with `"xb"` [C :527], so an earlier file is never opened for writing [M torn-tail test]. The write is append+fsync, not tmp+rename. A crash mid-sweep leaves a partial file whose complete records replay. Items already drained into memory are lost, exactly as today. This is **not "atomic"** in the strict sense of the task [I].
- **Cost [M probe.py, 4,096 items shaped like fairy.py:4986]:**
  - The synchronous first sweep goes from 0.048 s to **0.195 s (4x)** and the file from 1.15 MB to **2.14 MB (1.9x)**. Cause: the extra `features` field and three JSON encodes per item (round-trip check, `max_line` check, append).
  - Still bounded. The 50,000-record cap binds before the 32 MB cap at about 520 B/item [I].
- **Never delete:** done-* files grow without bound (about 1-2 MB per boot) [C :1032]. The uuid ledger keeps only 256 entries [C :60,288]. So a done file older than 256 replays that someone renames back by hand **would replay twice** (manual action only) [I].
- **Switch precedence:** with env=1, a malformed `tardis_fix.json` (which fails every key closed) still reads b_persist ON [M probe.py]. An explicit `"b_persist": false` in the file can't veto the env either. Ace's file is no longer the off switch while the env var is set. This is documented ("can only add ON") but is an operator trap [C tardis_fix.py:93-95].
- **Dedup against what is already written:** none, beyond ownership and the ledger. Replayed items are re-batched at up to 20/s (headroom 200; trickle 1 per 10 s otherwise), so per-batch pair dedup can differ from the live run. The weight sums of the replayed pairs then differ from what a live write would have produced [C fairy.py:6370-6390; tardis_backlog.py CFG] [I].
- **Steady state:** the writer runs at 0.4-0.8 s/pair. While the live queue sits above 200, replay trickles at 1 item per 10 s, so carryover **defers** loss and the 50k cap eventually drops the oldest (counted `over_cap`, not silent). The module docstring admits this [C tardis_backlog.py:20-24] [I].
- **Timing laps:** `u.new`+`u.evict` (and `l.new`+`l.evict`) partition main's old `u.new` (`l.new`) wall time exactly; stats divide by `pairs`, so the second `l.new` add per call doesn't skew ms/pair [C tardis_timing.py:95-108,262-280; M test_control_eviction_laps_on]. Logging is per window (`flushes_per_line`/`max_silence_s`), not "every N pairs" as the task worded it (pre-existing L0) [C tardis_timing.py:40].

## VERDICT
| # | finding | severity | evidence (file:line + tag) | status |
|---|---|---|---|---|
| 1 | Both env vars unset means main's behaviour on every path, including when the file turns b_persist / l0_timing ON (persisted records byte-identical) | NONE | tardis_fix.py:111 [C]; tardis_backlog.py:627,1032 [C]; offeq sha bd2e088a… [M] | CONFIRMED-ok |
| 2 | All 7 CONTROL tests fail on main; all 7 author mutants are caught | NONE | w11_mutation_run.py [M] | CONFIRMED-ok |
| 3 | Server-hook placement is untested: mutant N1 (reboot hook unreachable after `os._exit`) passes all 19 tests | MINOR | test_w11_bind_carryover.py:340-354 [C]; mut2 N1 [M] | REFUTED-change |
| 4 | Only serial A (has `_akashic_cortex_region`) can own B; portal copy B is refused | NONE | server.py:6378,6425; tardis_backlog.py:349 [C] | CONFIRMED-ok |
| 5 | Exactly once across Event, `on_shutdown` and the new hook (`_persist_started` under lock; claim by rename; ledger) | NONE | tardis_backlog.py:484,701,918 [C]; roundtrip test [M] | CONFIRMED-ok |
| 6 | Persist file is append+fsync into a new `xb` file, not tmp+rename: previous files are intact, but the task's "atomic" isn't literally met (a crash leaves a partial replayable file) | MINOR | tardis_backlog.py:521-527 [C]; torn-tail test [M] | REFUTED-change |
| 7 | Verbatim mode keeps fields and order when representable; the fallback still alters item fields (`"None"`, truncated to 256 chars), though pairs are unchanged | MINOR | tardis_backlog.py:632-636,644-660 [C]; roundtrip [M] | CONFIRMED-ok |
| 8 | Env=1 overrides a malformed or explicitly false `tardis_fix.json`; Ace's file can no longer turn B OFF while the env var is set | MINOR | tardis_fix.py:93-95,111 [C]; probe [M] | CONFIRMED-ok |
| 9 | Never-delete: `done-*` files grow without bound; the 256-entry uuid ledger lets a hand-restored old done file replay twice | MINOR | tardis_backlog.py:60,288,1032 [C] [I] | REFUTED-change |
| 10 | Verbatim makes the synchronous first sweep 4x slower (0.05 to 0.20 s per 4,096 items) and the file 1.9x larger; still bounded | MINOR | tardis_backlog.py:644-660 [C]; probe.py [M] | CONFIRMED-ok |
| 11 | No dedup against the manifold beyond ownership; replay re-batches, so link weights can differ from a live write; with the writer at 0.4-0.8 s/pair the backlog is deferred, not cured (cap drops the oldest, counted) | MAJOR | tardis_backlog.py:20-24, CFG; fairy.py:6370-6390 [C] [I] | REFUTED-change |
| 12 | Exit routes: shutdown (Event), reboot and Ctrl+C/SIGTERM are covered; boot watchdog :4598 and second Ctrl+C :9662 are not (acceptable) | MINOR | server.py:3706,3884,9790,4598,9662 [C] | CONFIRMED-ok |
| 13 | Eviction laps partition the old `l.new` / `u.new` exactly; OFF adds no lap and doesn't change the log line | NONE | manifold_memory.py:2280-2285,2736-2741; tardis_timing.py:278 [C]; Timing tests [M] | CONFIRMED-ok |
| 14 | No second copy of the changed modules; two `shared_postal_hub.py` files exist (pre-existing; the canonical one is read first) | NONE | find/diff [M]; server.py:3705 [C] | CONFIRMED-ok |
