# W11 adversarial review: `nous/w11-bind-carryover` (FINAL, round 2 at head 0550718)

Round 1 reviewed dd483ad. Round 2 re-ran all six steps against 0550718 (fix commit for #3 and #9).
Tags: **[C]** read in code (branch file:line), **[M]** measured by something I ran, **[I]** inference.
Nothing was booted: no server.py, no fairy, no launcher, no real `*.manifold`. All data synthetic, in temp dirs.

## What the change is
The diff adds env switches to the **existing** TARDIS-B persist/replay layer instead of writing a new carryover:
- `AKASHIC_BIND_CARRYOVER=1` turns b_persist ON; `AKASHIC_BIND_TIMING=1` turns l0_timing ON [C tardis_fix.py:96,111].
- Verbatim queue records [C tardis_backlog.py:628,645].
- `done-*` files are never pruned [C :1033], and from round 2 neither is the ledger [C :288].
- `persist_owner()` plus server hooks on reboot and Ctrl+C [C server.py:3884,9790,9136].
- `l.evict` / `u.evict` timing laps [C manifold_memory.py:2280-2285,2736-2741].

## Round 2: steps 1-6 against 0550718
**1. Tests** [M]
- Branch: 22/22 pass.
- Main tree: 10 fail. That is **all 9 CONTROLs** (including the 2 new ones: `test_control_ledger_keeps_every_uuid`, `test_control_hooks_run_before_shutdown_system`) plus `test_replay_bookkeeping_key_not_carried`.
- `w11_mutation_run.py`: **M1-M10 each fail at least one test.**

My mutants [M scratch `mut2.py`]:

| Mutant | Result | Caught by |
|---|---|---|
| **N1** (round 1): reboot hook unreachable after `os._exit` | **now CAUGHT** | `test_control_hooks_run_before_shutdown_system` |
| R2: ledger read capped to 256 | CAUGHT | ledger control |
| R3: ledger_add under carryover drops earlier uuids | CAUGHT | ledger control |
| R4: replay never consults the ledger | CAUGHT | roundtrip control |
| R5: reboot hook wrapped in `if False:` | CAUGHT | placement control |
| **R1: reboot hook kept in place but behind `time.sleep(30)`** | **SURVIVES** | — |

On R1: the placement test is ordinal (AST siblings), not temporal. On the reboot route the main thread cuts at about 20 s [C server.py:9780], so a hook delayed past that is dead. Low realism: nobody adds a sleep there by accident. A static test can't pin timing, so I accept the gap [I].

**2. Switch defaults**
- The only production change in round 2 is gated on `_carry()` [C tardis_backlog.py:288]. With env unset the ledger trims to 256 exactly like main [M test_off_ledger_trims_like_today].
- With the file turning b_persist + l0_timing ON and env unset, the persisted records are again **byte-identical to main (sha256 bd2e088a…, 96,550 B)** [M offeq.py].

**3. Callers**
- `_ledger_add` has a single caller [C tardis_backlog.py:919]; `_ledger_read` is called only by `_ledger_add` and the replay check.
- No other changes; the round-1 caller map holds: every `tardis_fix.on` gate is reached, and the exit routes are as in #12.

**4. Second copies**: unchanged. Each changed module exists once; the two `shared_postal_hub.py` files predate W11 [M find/diff].

**5. Switch-OFF behaviour changes**: none found [M offeq; C :288].

**6. Claims**
- Owner is serial A only [C server.py:6378,6425; tardis_backlog.py:349].
- Exactly-once still holds via `_persist_started` under lock, claim by rename, and the now-unbounded ledger [C :484,701,919].
- **New (MINOR):** turning carryover OFF later re-applies main's pruning. The next done file prunes `done-*` to 16, and the next ledger write trims to 256. "Never delete" therefore holds **only while the env var is set** [C :288,1033] [I]. That is consistent with OFF = main.
- Ledger growth is about 36 B per replayed file, negligible [I].
- A corrupt `ledger.json` reads as [] and loses all replay protection. This predates W11, and the write is tmp+fsync+replace so it is unlikely [C :277-295].

## Do the author's reasons for leaving #6, #8 and #11 open hold?
**#6: append+fsync into a new `"xb"` file instead of tmp+rename. HOLDS.**
- The server leaves through `os._exit`, which can land at any moment, and the 180 s sweeper keeps appending late arrivals [C tardis_backlog.py:763-775].
- With tmp+rename, an exit before the final rename loses the **whole** file. With CRC-framed append, an exit loses at most the torn last line [C `_enc`/`_dec` :148-176; M torn-tail test].
- "A crash leaves the previous file intact" is met: each boot writes a new name and older files are never opened for writing [C :527].
- Residual [I]: on the reboot route both the main thread [C server.py:9796-9805] and the reboot thread spawn a new server. A new process could in principle claim a still-appending pending file. Replay waits 60 s, and the old process is gone in about 43 s or less, so this is improbable.

**#8: the env can only add ON. HOLDS, by design.**
- The off switch is to unset the env var in the launcher; the file stays authoritative only when the env var is unset [C tardis_fix.py:93-95].
- The operator trap remains: a malformed or `false` file does not veto the env. This should be stated in the launcher or README for Ace.

**#11: no dedup against manifold contents, because a repeat bind is a reinforcement. HOLDS. Downgraded from MAJOR to MINOR.**
- Ownership guarantees every carried pair was **never written** [C tardis_backlog.py:8-19,484].
- Dedup against existing manifold edges would therefore *drop* legitimate reinforcements, which loses binds and violates the task's no-loss rule [I].
- Residual: replay feeds about 10 items per 0.5 s flush, while live drains up to 200 [C fairy.py:6344; CFG max_rate]. So in-batch per-tracer pair collapse [C fairy.py:6370-6390] is weaker on replay, and a pair repeated across items can be linked more times than a large live batch would. That is a bias in reinforcement counts, not a loss [I].
- Writer throughput (0.4-0.8 s/pair), which makes carryover defer rather than cure, is outside W11's scope. Loss at the 50k cap is counted (`over_cap`), not silent [C :20-24].

## FINAL VERDICT
| # | finding | severity | evidence (file:line + tag) | status | round-2 status |
|---|---|---|---|---|---|
| 1 | Env unset means main's behaviour on every path, including when the file turns b_persist/l0_timing ON | NONE | tardis_fix.py:111; tardis_backlog.py:288,628,1033 [C]; sha bd2e088a… [M] | CONFIRMED-ok | re-verified at 0550718 |
| 2 | All CONTROLs fail on main; every author mutant is caught | NONE | w11_mutation_run.py: 9 controls, M1-M10 [M] | CONFIRMED-ok | re-verified (22 tests, 10 mutants) |
| 3 | Server-hook placement untested (N1 survived) | MINOR | test_w11_bind_carryover.py `_hook_placement` [C]; N1 caught, R5 caught [M] | CONFIRMED-ok | FIXED. Residual: ordinal not temporal (R1 sleep-30 survives), accepted |
| 4 | Only serial A can own B; portal copy refused | NONE | server.py:6378,6425; tardis_backlog.py:349 [C] | CONFIRMED-ok | unchanged |
| 5 | Exactly once (persist lock, claim by rename, ledger) | NONE | tardis_backlog.py:484,701,919 [C]; roundtrip, R4 caught [M] | CONFIRMED-ok | holds; ledger now unbounded under carryover |
| 6 | Append+fsync to a new `xb` file, not tmp+rename | MINOR | tardis_backlog.py:521-527,763-775 [C]; torn-tail [M] | CONFIRMED-ok | OPEN by design: reason HOLDS (tmp+rename loses the whole file to `os._exit`) |
| 7 | Verbatim keeps fields and order; fallback alters item fields, not pairs | MINOR | tardis_backlog.py:633-637,645-661 [C] | CONFIRMED-ok | unchanged |
| 8 | Env=1 overrides a malformed or `false` `tardis_fix.json` | MINOR | tardis_fix.py:93-95,111 [C]; probe [M] | CONFIRMED-ok | OPEN by design: reason HOLDS; document for the operator |
| 9 | Never-delete vs 256-uuid ledger allowed a double replay of a hand-restored file | MINOR | tardis_backlog.py:288,1033 [C]; R2/R3/M8 caught [M] | CONFIRMED-ok | FIXED. New: carryover OFF later re-prunes `done-*` to 16 and the ledger to 256 (= main) |
| 10 | Verbatim sweep 4x slower (0.05 to 0.20 s per 4,096) and file 1.9x larger; bounded | MINOR | tardis_backlog.py:645-661 [C]; probe.py [M] | CONFIRMED-ok | unchanged |
| 11 | No dedup against manifold contents; replay re-batching biases reinforcement counts; writer speed defers loss rather than curing it | MINOR (was MAJOR) | tardis_backlog.py:8-24; fairy.py:6344,6370-6390 [C] [I] | CONFIRMED-ok | OPEN by design: reason HOLDS (dedup would drop real reinforcements) |
| 12 | Exit routes: shutdown (Event), reboot and Ctrl+C/SIGTERM covered; boot watchdog :4598 and second Ctrl+C :9662 not | MINOR | server.py:3706,3884,9790,4598,9662 [C] | CONFIRMED-ok | unchanged |
| 13 | Eviction laps partition the old `l.new` / `u.new`; OFF adds no lap or log change | NONE | manifold_memory.py:2280-2285,2736-2741; tardis_timing.py:278 [C]; Timing tests [M] | CONFIRMED-ok | unchanged |
| 14 | No second copy of the changed modules (two pre-existing postal hubs) | NONE | find/diff [M] | CONFIRMED-ok | unchanged |
