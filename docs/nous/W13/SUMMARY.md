# W13 - a gate over the coma (branch nous/w13-coma-gate)

Organ template: NOT edited, so Ace's permission is not needed for this branch. Both copies are untouched and have the same
content (`diff` after stripping CR: empty) [M]. The gate calls the template's existing `wake()` (Organ_Template_0_3_0.py:3487-3509) [C].

Switch: **AKASHIC_COMA_GATE**. It is ON only when the value is exactly "1": `os.environ.get("AKASHIC_COMA_GATE", "0") == "1"`
(server.py:5648, coma_gate.py:39) [C]. When it is unset or any other value, `_coma_gate = None` and every hook is skipped [C][M].

Files: new code/infrastructure/coma_gate.py (166 lines), code/tests/test_w13_coma_gate.py (15 tests),
code/tests/w13_coma_gate_mutants.py. code/server.py: +30 lines, 0 removed. The file stays LF (0 CR before and after) [M].

## 1. Map of the coma

The checks live in one place only: the template, which has two copies with the same content.
`_is_comatose` is at Organ_Template_0_3_0.py:3426-3477 [C].
- `AKASHIC_COMA` :3440 uses `bool(env.get(...))`, so ANY non-empty value, "0" included, turns the coma ON [C].
- `AKASHIC_SLEEP` :3445 overrides everything except P00 and the infra names. `AKASHIC_WAKE_PLANES` :3472. `AKASHIC_WAKE` :3476 [C].
- Always exempt: plane P00 (:3455) and 11 infra names (:3459-3463) [C].
- `_is_comatose` is read by: boot() :3572 (skips on_boot), and shadow start at :1447 (AKASHIC_SHARED_SHADOW_SCAN) and :1468 (AKASHIC_SHADOW_DEFER) [C].

Who sets them [C]:
- boot_sour.bat: :27 COMA=1, :29 WAKE_PLANES=P20, :36 WAKE=<list>, :38 SLEEP=<3 names>. The "coma" mode at :56-57 blanks WAKE and WAKE_PLANES.
- Also: start_HQ_COMA.bat:7, start_HQ_LEAN.bat:8-14, start_HQ_LEAN_GUI.bat and start_HQ_LEAN_GUI_TRACEMALLOC.bat :14-35,
  start_nous_COMA.bat:23, start_nous_satellite.bat:20,39.
- SLEEP only: start_nous.bat:97, boot_sour_full.bat:58.
- No .cmd or .ps1 file sets any of them (grep) [M].

What a comatose fairy still does [C]:
- __init__ registers it in CITIZEN_OBJECTS and in the fairy registry (:1212-1248).
- _wire_infrastructure runs (:3565): postal subscribe, directory register, heartbeat.
- Its state is set to SLEEPING and it publishes `fairy.state.changed {coma:true}` (:3575-3582).
- On every heartbeat it stamps `_tick_count`/`_last_tick`, echoes liveness every 10th beat, then returns (:4940-4981).
- It does NOT run: on_boot, the spell chain (:3592), the SRM cluster (:3606), or the HeartbeatRegistry auto-register (:3616+).
- Shadow: the per-fairy thread starts unless one of the two shadow flags is on. boot_sour.bat:45-46 sets both, so no shadow there.

No code calls `.wake(` anywhere, apart from the template's own definitions (grep) [M].

Her three gates [C]: AutonomyFairy, AutopilotFairy and EmbodimentFairy.
- SomaticMindFairy._wake_three_gates expects {"autonomy","autopilot","embodiment"} (SomaticMindFairy/fairy.py:8171).
  server.py:5665 runs it as SYSTEM.umf.
- Each gate publishes `boot.fairy.request`: AutonomyFairy/fairy.py:2557, AutopilotFairy/fairy.py:3850, EmbodimentFairy/fairy.py:2128.
- The only subscriber is server.py `_handle_fairy_boot_request`, subscribed at :6028 [C][M grep].

Where the 7 gate requests are refused [C]: nothing refuses them outright. One of two things happens:
- (a) The handler skips with "already registered" (server.py:5895). HarmonicCortex (:6523), QuantumInterference, QuantumSearch
  and SRMIngest are built by the serial block and appended to registered_fairies, so they take this path.
- (b) The handler builds the fairy and calls `instance.boot()` (:5964). boot() returns True with the fairy ASLEEP
  (template :3572-3583), and the handler still prints "BOOTED" (:6001). That is the BOOTED-then-sleep line.

Domain lists [C]: AutonomyFairy:2425-2434 (InterestScheduler, SRMIngest, QuantumInterference, HarmonicCortex, QuantumSearch)
and EmbodimentFairy:2006,2020 (PainDrive, SomaticAvatar).

Discrepancy: InterestSchedulerFairy IS listed in boot_sour.bat:36 AKASHIC_WAKE, so under boot_sour the env gate does not sleep it [C].
I could not verify why it sleeps in her run (there are no logs here).

## 2. Shape

- **Who opens it:**
  - The owner, by typing a line into an allow-list file: code/state/coma_gate_open.txt by default, or the path in AKASHIC_COMA_GATE_FILE.
    A bare `Name` line means the owner opens it now: the owner watch wakes it within 5 s. It also lets her gates open it.
  - Her gates, through their existing `boot.fairy.request` topic, but only for names the file opens to them with a `gate:Name` line.
- **What opening does:** it finds the ONE existing instance and calls that instance's own `wake()`. It never constructs one.
  - First place it looks: `fairy_template.citizen_registry.CITIZEN_OBJECTS[name]`, the single dict set at template :1248.
  - Fallback: the directory record's `metadata["fairy_instance"]` (server.py sets it, e.g. :5985).
  - One lock covers the check and the wake (coma_gate.py:104).
- **How to close it:** delete the line, and later opens are refused. A fairy that was already woken stays awake until the next boot.
  The gate does not re-sleep it with the template's `sleep()`, because `on_sleep` is optional and threads started by on_boot would keep running [I].
- **What is logged:** each refusal is one line, `[COMA-GATE] REFUSED <name> (source=gate:<gate>|owner): <reason>`. Each open is one `OPENED` line.

## 3. What was built (switch OFF by default)

coma_gate.py provides [C]:
- `enabled`
- `read_allow_list`: reads the file on every call, is BOM-safe, and a missing file means nothing opens.
- `find_instance`: looks in sys.modules and never imports the template.
- `open_for`, `on_boot_request`, `sweep`, `start_owner_watch`.

server.py hooks, each behind `if _coma_gate is not None`:
- Import: :5644-5651.
- Early hook :5868-5875: an existing, asleep, listed instance is woken, then the handler returns and builds nothing.
- Post-build hook :5967-5973: the instance just built is asleep and listed, so it is woken.
- Owner watch: :6030-6035.

## Tests [M]

Run with `python3 code/tests/test_w13_coma_gate.py`.
- This branch: 15/15 pass.
- CONTROL against main's server.py (SERVER_SRC=<main copy>): 4 tests FAIL:
  - a new build wakes exactly once,
  - an existing registered instance wakes in place,
  - an existing unregistered instance is not rebuilt,
  - the structural switch test.
  The OFF test passes on main too, because OFF is today's behaviour.
- CONTROL with no coma_gate.py, as on main (COMA_GATE_SRC=/nonexistent): 11 ERROR + 1 FAIL.
- MUTANTS (code/tests/w13_coma_gate_mutants.py): 9/9 killed.
  - M1 switch default "1"; M2 `!= "0"`; M3 asleep check dropped; M4 owner/gate split ignored; M5 allow-list cached;
    M6 on_boot called instead of wake.
  - S1 server switch default "1"; S2 post-build hook dropped; S3 early hook falls through (builds a 2nd instance).

## Could NOT verify

- Real fairies were not run. The tests use a FakeFairy that copies wake()'s contract, and a structural test pins the template text.
  What a real on_boot does after a wake was not exercised.
- wake() does NOT run the steps boot() skipped after on_boot: the spell chain (:3592), the SRM cluster (:3606) and the
  HeartbeatRegistry register (:3616+) [C]. A woken fairy may therefore lack them [I]. That is how the template's wake() works today.
- In her runtime: the postal delivery order and threading of boot.fairy.request, and how the 5 s watch thread behaves under PYTHON_GIL=0.
- Why InterestSchedulerFairy sleeps under boot_sour (see the discrepancy above).

## CHECK THESE 3

1. The handler prints BOOTED for a fairy that boot() has just put to sleep: server.py:5964 and :6001, against template :3572-3583.
2. CITIZEN_OBJECTS is the ONE instance map, and the gate cannot build an instance: template :1212-1248, coma_gate.py:66-84.
3. With the switch OFF the behaviour is identical to today: server.py:5646-5651 leaves `_coma_gate = None`, and every use
   (:5870, :5971, :6033) sits behind `_coma_gate is not None`.

## REVIEW
(pending)
