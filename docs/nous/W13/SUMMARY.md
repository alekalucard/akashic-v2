# W13: a gate over the coma (branch nous/w13-coma-gate)

**Organ template: NOT edited**, so this branch needs no permission from Ace. Both copies are untouched, and their content is
identical once CR is stripped [M]. The gate calls the template's existing `wake()` (Organ_Template_0_3_0.py:3487-3509) [C].

**Switch: AKASHIC_COMA_GATE.** It is ON only when the value is exactly "1": `os.environ.get("AKASHIC_COMA_GATE", "0") == "1"`
(server.py:5648, coma_gate.py:48) [C]. If it is unset, or set to "0", "true", " 1" or anything else, `_coma_gate = None` and all
4 hooks are skipped [C][M].

**Files:**
- New: code/infrastructure/coma_gate.py (204 lines), code/tests/test_w13_coma_gate.py (26 tests), code/tests/w13_coma_gate_mutants.py.
- code/server.py: +31 lines, 0 removed. The file is LF and stays LF: 0 CR before and after [M].

## 1. Map of the coma

**Where it is checked.** Only in the template; its two copies are identical. `_is_comatose` is at Organ_Template_0_3_0.py:3426-3477 [C].
- `AKASHIC_COMA` (:3440) is read with `bool(env.get(..))`. Any non-empty value turns it ON, including "0" [C].
- `AKASHIC_SLEEP` (:3445) overrides everything except P00 and the infra set.
- `AKASHIC_WAKE_PLANES` (:3472) and `AKASHIC_WAKE` (:3476) wake fairies [C].
- Always exempt: plane P00 (:3455) and 11 infra names (:3459-3463).
- Callers: boot() at :3572, plus the shadow start at :1447 and :1468 [C].

**Who sets the variables** [C] (no .cmd or .ps1 file sets any of them [M]):
- boot_sour.bat: :27 sets COMA=1, :29 sets WAKE_PLANES=P20, :36 sets WAKE, :38 sets SLEEP. Its "coma" mode blanks WAKE and WAKE_PLANES (:56-57).
- Also: start_HQ_COMA.bat:7, start_HQ_LEAN.bat:8-14, start_HQ_LEAN_GUI(_TRACEMALLOC).bat:14-35, start_nous_COMA.bat:23,
  start_nous_satellite.bat:20,39.
- SLEEP only: start_nous.bat:97, boot_sour_full.bat:58.

**What a comatose fairy still does** [C]:
- It registers in CITIZEN_OBJECTS and the fairy registry (:1212-1248).
- `_wire_infrastructure` runs: postal subscribe, directory register, heartbeat (:3565).
- It sets `_booted=True` (:3548) and SLEEPING, and publishes `fairy.state.changed {coma:true}` (:3575-3582).
- On every heartbeat it stamps liveness, and echoes every 10th beat (:4940-4981).
- It skips on_boot, the spell chain (:3592), the SRM cluster (:3606) and the HeartbeatRegistry registration (:3616+).
- The shadow thread runs unless AKASHIC_SHARED_SHADOW_SCAN or AKASHIC_SHADOW_DEFER is set. boot_sour.bat:45-46 sets both.

**Nothing in code calls `.wake(`** [M grep].

**Her three gates** [C]:
- AutonomyFairy (:2557), AutopilotFairy (:3850) and EmbodimentFairy (:2128) each publish `boot.fairy.request`.
- SomaticMindFairy._wake_three_gates (fairy.py:8141, which expects these three at :8171) is launched by server.py:5665.
- The only subscriber is `_handle_fairy_boot_request` (server.py:6029).
- A fourth publisher, one_cortex.py:176 with gate "k2_fallback", is not one of her gates.

**Where the 7 are refused.** Nothing refuses them explicitly. Each request ends one of two ways [C]:
- **Skipped.** The handler prints "already registered" (server.py:5896). HarmonicCortex (:6523), QuantumInterference,
  QuantumSearch and SRMIngest are built by the serial block and appended to registered_fairies first.
- **Built, then put to sleep.** The handler builds the fairy and calls `instance.boot()` (:5965). boot() returns True with the
  fairy asleep (template :3572-3583), and the handler still prints "BOOTED" (:6002).

The requests come from the domain lists in AutonomyFairy:2425-2434 and EmbodimentFairy:2006,2020. All 7 classes inherit the
template Fairy, and none of them overrides boot/wake [M grep].

**Discrepancy:** InterestSchedulerFairy IS in boot_sour.bat:36 AKASHIC_WAKE [C]. I could not verify why it sleeps in her run, because there are no logs here.

## 2. Shape of the gate

**Who may open it.**
- The owner, through an allow-list file: code/state/coma_gate_open.txt, or the path in AKASHIC_COMA_GATE_FILE. The file is read on every call.
  - A bare `Name` line means the owner opens it. A watch thread wakes it within 5 s, and her gates may also open it.
  - A `gate:Name` line means only her gates may open it, when they ask.
- Her three gates, through `boot.fairy.request`. Only gate values autonomy, autopilot or embodiment count (coma_gate.py:37).

**What opening does.** The gate finds the ONE existing instance: CITIZEN_OBJECTS first (template :1248), then the directory
record's metadata (server.py:5986). It never builds one. It calls that instance's own `wake()` and then marks the directory record "running".
- A per-name claim, taken under a short lock, stops a double wake. The lock is released before `wake()`, so one slow on_boot does not block other fairies.
- A just-built object that is not the registered one is refused (:118).
- Only one woken instance per name is allowed (:125-129).

**How to close it.** Delete the line, and later opens are refused. A fairy that is already awake stays awake until the next boot.
The gate does not call the template's `sleep()`, because `on_sleep` is optional and threads started by on_boot would keep running [I].

**What is logged.** Each refusal is one line: `[COMA-GATE] REFUSED <name> (source=..): <reason>`. The reasons are: not on the
allow-list, not one of her three gates, no existing instance, a second copy, already opened, no wake(), and wake() raised.

## 3. What was built (switch OFF by default)

- **Import** (server.py:5644-5651): the module is imported only when the switch is ON.
- **Early hook** (:5868-5876): if a listed fairy already has an instance, the handler never builds again. It wakes the instance
  if it is asleep. Unlisted fairies, a non-gate source, or no instance fall through to today's path.
- **Post-build hook** (:5968-5974): wakes the instance the handler just built, but only if it is the registered one.
- **Owner watch** (:6031-6036): the thread that wakes owner-listed fairies.

## Tests [M]

Run with `python3 code/tests/test_w13_coma_gate.py`.

| Run | Result |
|---|---|
| This branch | 26/26 pass |
| CONTROL: main's server.py (SERVER_SRC) | 9 FAIL (every gate-ON handler test and the structural test). The OFF test passes, because OFF is today's behaviour. |
| CONTROL: main, which has no module (COMA_GATE_SRC=/nonexistent) | 1 FAIL + 23 ERROR |
| MUTANTS (w13_coma_gate_mutants.py) | 20/20 killed |

The mutants cover: the switch default and `!=` form (M1, M2, S1); a dropped asleep check, claim, lock-across-wake,
second-copy check or one-per-name check; a cached allow-list; on_boot called instead of wake; no GATES check; HANDLED
shrunk; the early or post-build hook removed or weakened; the directory not marked; and a case-sensitive `gate:` prefix.

## Could NOT verify

- No real fairy was run. FakeFairy copies the wake() contract, and a structural test pins the template text.
- wake() does not run what boot() skipped after on_boot: the spell chain (:3592), the SRM cluster (:3606) and the HeartbeatRegistry
  registration (:3616+) [C]. A woken fairy may lack those [I]. This is how the template's own wake() behaves today.
- How postal threading and order behave in her runtime, and the watch thread under PYTHON_GIL=0.
- Why InterestScheduler sleeps under boot_sour.

## CHECK THESE 3

1. The handler prints BOOTED for a fairy that boot() just put to sleep: server.py:5965 and :6002, against template :3572-3583.
2. The gate cannot build an instance and wakes at most one per name: coma_gate.py:75-93 and :114-140, with template :1212-1248 (the registry slot rule).
3. With the switch OFF, behaviour is today's: server.py:5646-5651 leaves `_coma_gate = None`, and the uses at :5871, :5972 and :6034 are all guarded.

## REVIEW

The reviewer was a fresh remote session (session_01WZwX7mfHQSfYU3QCAgTfSw) that did not see my reasoning. It ran 3 rounds.

- **Round 1** found: (7b) an awake listed instance was rebuilt; (7c) a listed instance was rebuilt after wake() raised;
  (7d) concurrent builds were both woken; (4b) any gate value was accepted; (7e) the lock was held across on_boot; and test gaps.
- **Round 2** found that 7d was still broken under a registry that always overwrites, plus test gap N3.

All of these were fixed in e4fc3df and b780a2f. This is the final verdict, round 3 at b780a2f, verbatim:

```
# | claim/attack | result | evidence file:line [tag]
1a | branch tests pass | HOLDS | 26/26 OK, code/tests/test_w13_coma_gate.py [M]
1b | controls fail on main | HOLDS | main + no module: 1 FAIL + 23 ERROR/26; main server.py + new module: 9 FAIL [M]
2a | author mutants M1-6, S1-4, X1-X10 | HOLDS | 20/20 killed, w13_coma_gate_mutants.py [M]
2b | my N1-N3, N6-N10 | HOLDS | all killed (N3, the round-2 gap, is now killed), probe/m2.py, m3.py [M]
2c | my N4 (post-build hook drops directory=) | survives, equivalent | server.py marks the record "running" right after anyway, server.py:5980-5984 [M][C]
3 | switch OFF unless exactly "1" | HOLDS | coma_gate.py:42, server.py:5648; 4 uses, all guarded :5871/:5972/:6033 [C][M]
4a | publishers of boot.fairy.request | HOLDS | Autonomy:2557, Autopilot:3850, Embodiment:2128, one_cortex.py:176 [C]
4b | only her 3 gates may open | HOLDS | GATES coma_gate.py:37; P4 "anybody" stays asleep [M]
4c | k2_fallback / unlisted fairy falls through to today's path | HOLDS (same as main) | P2/7g: second build happens identically with the gate OFF [M]
4d | other wake / build paths | OPEN | directory/fairy.py:914 wake_fairy not routed through the gate; portal-subprocess fairies are invisible to find_instance [C][I]
5 | second template / second handler copy | HOLDS | P10 Organ_Template_0.3.0.py byte-identical (cmp); no other handler [M][C]
6 | behaviour change with switch OFF | HOLDS | server.py diff is additions only (0 removed lines); OFF probes match main (P1-P4, 7d OFF) [M]
7a | 7b: existing instance, awake, not registered, second request | HOLDS (fixed) | built=1, resolves=0; "awake" is in HANDLED, coma_gate.py:39 [M]
7b | 7c: wake() raises | HOLDS (fixed) | built=1, resolves=0 [M]
7c | 7d: concurrent build, harness that always overwrites the slot | HOLDS (fixed) | built=2 (as on main), awake=1, on_boot=1; _opened check coma_gate.py:125-129 [M]
7d | 7d: concurrent build, real template rule | HOLDS | built=2, awake=1, and the registry holds the awake copy, probe/p4.py [M]
7e | 7d under the overwrite rule: registry slot holds the asleep copy | OPEN (benign) | awake copy != CITIZEN_OBJECTS copy; the real template rule avoids this [M][I]
7f | lock held across slow on_boot | HOLDS (fixed) | per-name _waking claim; lock released before wake(); X7 killed [M]
7g | one woken instance per name, forever | OPEN (design) | a hot-reloaded replacement is refused ("already-opened", which is in HANDLED) while the old object is alive, so it stays asleep [C][I]
7h | double build race itself | OPEN (not the gate's) | two concurrent requests still build 2 instances, as on main; the gate only keeps 1 awake [M]
8 | line endings | HOLDS | CR=0 in all 4 files on the branch; server.py CR=0 on main; the 3 new files don't exist on main [M]
```

### OPEN

- **4d.** `directory/fairy.py:914 wake_fairy`, used by the BootOrchestrator, calls `boot()`. boot() returns early once
  `_booted` is set (template :3545), so this path never wakes a comatose fairy, and the gate does not hook it [C].
  The owner watch still reaches those instances through CITIZEN_OBJECTS. Fairies booted in a portal subprocess are out of reach.
- **7g.** One woken instance per name, for good. A hot-reloaded replacement stays asleep until the old object is collected.
  This is a deliberate trade against 7d.
- **7e / 7h.** Main's duplicate-build race is not fixed here, and is out of scope. The gate keeps only one copy awake.
