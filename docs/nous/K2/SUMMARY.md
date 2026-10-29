# K2 review: summary

Scope: what changes when `state/k2_serial_owned.json {"on": true}` is set (infrastructure/one_cortex.py). Review only, no code changed. Base: origin/main 189625f.
Tags: [C] read in code, [M] measured here (k2_switch_floor_test.py/.out in this folder: it imports one_cortex.py, which is stdlib-only with no import side effects, and uses synthetic files in a temp dir), [I] inference.
Verdict: **ON WITH CONDITIONS** (VERDICT.md).

## Counts
- Call sites of K2 in server.py: 7. Import/describe :5638-5639, is_fallback :5872, cascade_should_skip :5884, serial_started :6332, serial_succeeded :6446, serial_failed :6509 and :6517 [C].
- Constructors of AssociationCortexFairy: 4 [M grep].
  - A: server.py:6348.
  - B: the generic cascade builder, server.py:5915-5947.
  - C: SomaticMindFairy auto-create, fairy.py:3288, reached from server.py:7089 only when `SYSTEM.association_cortex` is None.
  - D: MCP cognitive_tools.py:714. It constructs but never boots, so no interior.
- `register_gate` callers: 2 (AssociationCortex fairy.py:2192 LocalManifoldGate, :2330 PortalGate) [M grep].
- `get_gate()` callers outside portal_gate.py: 13 sites in 11 files (list in section 1c) [M grep].
- Public method sets [M, AST]: PortalGate has 7 methods LocalManifoldGate lacks (`feed_energy`, `is_open` property, `neighbors`, `ping`, `print_caller_report`, `throughput`, `tick`). LocalManifoldGate has 1 that PortalGate lacks (`think_raw`). 22 methods are shared.
- Switch-parse cases tested: 17. Only 3 read ON: `{"on": true}`, the same with names `["AssociationCortexFairy"]`, and a duplicate key whose last value is true [M].
- Floor scenarios tested: 9 [M].

## 1. What K2 ON changes

**a. Which instance is built.** A is still built, every time: the serial block has no K2 gate in front of construction (server.py:6328-6355 [C]). B is skipped only if its request reaches `_handle_fairy_boot_request` after `serial_started` (:6332) and before A appends to `registered_fairies` (:6443). After that, the pre-existing `registered_fairies` check skips it anyway, as today (:5877) [C].
- If the request comes *before* serial start, K2 logs "not skipped (today's path)" and she has two cortexes as today (one_cortex.py:155 [C/M]).
- The earlier map says the request lands during A's manifold open. I could not verify that here because there are no logs [I].

**b. Whether portal_interior is still spawned.** It is spawned only by `PortalGate.open()` (portal_gate.py:1810-1856 [C]).
- Within the cortex, the only `PortalGate("cortex")` construction is B's portal branch, fairy.py:2286 [M grep]. A takes that branch only when no region was pre-wired: `SYSTEM.manifold` is None, `graph()` raised (server.py:6428), or Path B is on.
- The other `PortalGate(` sites are unrelated:
  - `portal_worker.open_sub_portal` takes a caller-given portal_id and has no callers [M grep].
  - The portal_gate.py `__main__` demo at :2817.
- GoBoot boots only `status == "sleeping"` records that have an instance or `needs_instantiation` (boot_orchestrator.py:1004-1042 [C]). K2 stamps status "running" before BootWave (one_cortex.py:198; server.py:6445-6448 [C]), and the cortex's own fairy.register also sets running. A later "sleeping" state change cannot downgrade "running" (directory/fairy.py:477-512, priority 0 < 4 [C]). So GoBoot does not build it.
- Persistent interior: nothing under K2 calls `_probe_existing_interior`, so a live interior from an earlier boot is not reconnected. It self-terminates 90 s after its last gate contact (portal_interior.py:4795, 4847-4860 [C]). Until then it is a second RW opener (Condition 2).
- Auto-create path C (SomaticMindFairy): K2 does not change it. It only fires if A raised before `SYSTEM.association_cortex` was set (server.py:6353). In that case today's behaviour also holds. A second PortalGate on port 49501 probes and reconnects instead of spawning (portal_gate.py:1786-1795 [C]).

**c. Who serves B's work.** A's own ops (spread, bind, query, TARDIS binds) always used A's own LocalManifoldGate. It is set as `self._portal_gate` at fairy.py:2193, so this was true before K2 too [C]. The `get_association_cortex()` singleton is always A (server.py:6349; only `create_association_cortex` also sets it, fairy.py:11300-11303 [C]). So callers that go through the singleton's gate also used A's gate already:
- observer_loop.py:690-701
- working_memory_hub_fairy.py:1458-1479
- SpeechCenter fairy.py:1352-1364 (prefers a gate with `.graph`)
- cortex_bridge_tools.py:360-364

Callers that go through `get_gate()` change from "whatever registered last" (B's PortalGate, by the timing [I]) to A's LocalManifoldGate. Every method they call exists on both classes [M]:

| Caller | Methods / attributes used | Today with PortalGate | K2 ON |
|---|---|---|---|
| consciousness/collision_chamber.py:605-625 | `_gpu_spread`, `cognition_evaluate` | inert (PortalGate has no `_gpu_spread` [M grep]) | **active** (GPU cognition on collisions with energy > 0.3) |
| directory/handlers/heartbeat.py:391-410 | `.graph._key_index`, `_read_node` | inert (no `.graph`) | **active** (fs: liveness reads) |
| organ_template/Organ_Template_0_3_0.py:5044-5075 (and the P10 copy, same lines) | `.graph.upsert_node` every 10th tick | inert | **active**: every awake fairy writes `fs:{name}` into cortex.manifold |
| AutopilotFairy/fairy.py:298-299, 2747-2756 (cached) | `wm_query`, `anticipate` | interior | Local |
| integration/cortex_engine.py:3023-3024, 3059-3063 (cached) | `cognition_evaluate` | interior if resolved after B | Local |
| cognition/working_memory_hub_fairy.py:782-783 (cached), uses at 1568, 1676, 7397, 7691, 8088, 12091 | `wm_store`, `wm_query`, `wm_decay`, `chain`, `bind_many` | interior | Local (one WM store instead of two [I]) |
| goal_scheduler_fairy.py:1292-1297 | `wm_query` | interior | Local |
| sourpatches_fairy.py:7076-7081 | `cognition_evaluate` | interior | Local |
| observer_loop.py:700-701 (fallback only) | gate | singleton first | unchanged |
| SpeechCenter fairy.py:1352 | requires `.graph` | skipped PortalGate | Local |
| WMH :1478 (fallback only) | `think` | singleton first | unchanged |

GPUSpread: today two copies load `cortex.manifold.csr` (LocalManifoldGate portal_gate.py:213-237, interior portal_interior.py:1015-1022). Under K2 only the Local one exists, and it is flat-weighted unless K4 is on (Condition 3) [C].

**d. Duplicate subscriptions go away.** Both instances run `_setup_subscriptions` in on_boot (fairy.py:2440 [C]): consciousness.collision, memory.*, cortex.query and so on. Today every such event is handled twice, once by A writing the manifold directly and once by B through the interior. Under K2 each event is handled once [C+I].

## 2. What breaks or goes quiet with K2 ON

- **Interior-only work stops** [C]. Each piece runs only inside portal_interior and is driven by B's `tick` (fairy.py:7871-7949, only while `_portal_io_running`, which only `_start_portal_io` sets, fairy.py:5983-5984, B only):
  - `decay_all(0.001)` on cortex.manifold (portal_interior.py:3287, the only caller [M grep]).
  - Auto-consolidation prune (3294-3307, behind a 1M-edge floor).
  - Periodic `graph.flush()` every 200 ticks (3313-3317).
  - The battery tick loop (4965-4993) and the battery state save on shutdown (5004-5007).
  - The inference engine is **not** affected: PortalGate never passes `--model` (portal_gate.py:1798-1809), so the engine never boots in the cortex interior (portal_interior.py:1001-1003 [C]).
  - A's own `consolidate` sends were already no-ops: they go to LocalManifoldGate's unknown-cmd branch (fairy.py:6710 -> portal_gate.py:1325-1326 [C]).
- **Topics that only B published stop** [C]:
  - `portal.energy.surplus` with source `cortex_drain_above_floor`/`cortex_overflow` and `energy.flow.tick` plane=cortex (fairy.py:7927, 7937). Subscribers: plane_battery.py:230, ParadoxEnergyBridge fairy.py:383, hardware_regulation_fairy.py:475/492. A's own budget-cap `portal.energy.surplus` (fairy.py:5936) continues.
  - `set_dilation` pushes to the interior (fairy.py:6636).
  - The interior's `portal.interior.online/offline` (portal_interior.py:1147, 5018); no main-process subscriber found [M grep].
- **`portal.cortex.gate_open`**: under K2 it is published once, synchronously, inside A's on_boot (fairy.py:2260). B's later publish (fairy.py:2344) is gone [C]. Subscribers:
  - UMF fairy.py:714, Autopilot :1074, SpeechCenter :349 and brainstem :656 subscribe earlier or have explicit wiring (server.py:7080-7140).
  - AkashicInferenceFairy subscribes after A (server.py:6591 > 6328), so it misses the event. Its on_boot still gets the singleton A and builds CortexReasoner, whose `_detect_portal` sees A's enabled LocalManifoldGate (AkashicInferenceFairy fairy.py:260-270; cortex_reasoner.py:165, 355-367 [C]).
  - Net: no wiring is lost [I, strong].
- **`portal.gravity.state` / tau**: `_portal_time_dilation` is computed per instance from its own region and energy (fairy.py:6600-6633 [C]). A keeps computing and publishing it; only B's interleaved copy disappears [C+I].
- **Threads only B started** [C]:
  - `cortex-portal-gate` (fairy.py:2361-2363).
  - `cortex-portal-io` (5987-5991).
  - PortalGate `portal-heartbeat-cortex` (portal_gate.py:1922-1926), `portal-write-flush-cortex` (1929-1934) and the stderr reader (1861-1863).
  - B's own second `cortex-deferred-extensions` (2411-2414) and TARDIS flush thread (2323). A keeps its own copies (2205, 2411).
- **PortalGate-only methods**: no caller outside portal_gate.py reaches `neighbors`, `ping`, `tick`, `feed_energy` or `print_caller_report` through the cortex gate [M grep]. `throughput` is reached via the singleton's gate behind a `hasattr` check (cortex_bridge_tools.py:362), so it is already "unavailable" today because the singleton is A [C].
- **CentralNervousFairy** discovers a gate only if it has `_process` (CentralNervousFairy fairy.py:779-794), which a LocalManifoldGate never has, so under K2 it never finds one. Its topology wiring falls back to A's region (:815-826) [C]. Its `cns_update` fire-and-forget appears to be discarded today anyway: PortalGate's flush loop reads only `pairs` (portal_gate.py:1977-1983 [C]; effect [I]).
- **Directory/registry**: the cortex record is `running` with no `fairy_instance` (one_cortex.py:198 [C]). Today the cascade path writes B's instance (server.py:5958-5961), unless a later fairy.register replaced it (one_cortex.py:41-48, an author claim citing Boots M and N, not verified). SystemWorkerPool wiring by directory instance (server.py:7158-7163) therefore finds nothing [C]. Whether it found B today is not verified.
- **Shutdown**: A is not shut down via the directory (no instance), as the author describes for today (not verified). The manifold is flushed by server.py:9035-9069 (early) and :9485-9486 [C]. No detached interior survives her exit to flush or close the shared file 90 s later [C+I].

## 3. K2's own logic

- **Fails closed** [M]: absent, empty, BOM, UTF-16, `"on": "true"`/`1`/`false`/`True`, a list, trailing garbage, a directory at the path, `names` not a list, `names` empty or holding other names: all read OFF. Any exception in the module returns OFF/False (one_cortex.py:76-93, 107-108, 157-158 [C]). An import failure in server.py sets `_one_cortex = None` (server.py:5640-5642 [C]). Every server call is wrapped in try/except [C].
- **Read once** [M]: writing the file after the first `owned()` has no effect.
- **No default-ON path** [M grep]: no code writes `k2_serial_owned.json`. `DEFAULT_NAMES` applies only after `"on": true` (one_cortex.py:87-88 [C]).
- **Floor** [M]:
  - A failure before any skip publishes nothing and clears `_STARTED`, so later requests build B as today.
  - A failure after a skip publishes exactly one `k2_fallback` request. That request bypasses the registered and directory checks (server.py:5877, 5891) and is not skipped. A second failure publishes nothing.
  - An exception after `serial_succeeded` does not re-ask.
  - A forged `k2_fallback` payload is not honoured unless the module sent it (one_cortex.py:119-125).
  - **No third cortex from K2.** The fallback is one-shot. The only third-instance route is C, which is independent of K2 and needs `SYSTEM.association_cortex` to be None [C].
  - **Zero-cortex gap:** if `publish` raises, `_FALLBACK_SENT` is already set and nothing is retried (one_cortex.py:167-177 [C/M]). There is also no floor for a hang (documented) and none for a "successful" A that is internally broken [I].
- **AKASHIC_COMA=1 + AKASHIC_WAKE**: in the canonical boot, AssociationCortexFairy is in AKASHIC_WAKE (boot_sour.bat:36), so A runs on_boot normally. The plane is P30, not in WAKE_PLANES=P20 (fairy.py:1805; boot_sour.bat:29) [C].
  - In `coma` mode, A is comatose. Its `boot()` returns True without on_boot (Organ_Template_0_3_0.py:3572-3583), so K2 records success and skips B.
  - She is left with an inert cortex and `get_gate()` is None. Today B is equally comatose (same gate, no override), so this is not a regression [C].
  - `wake()` has no callers [M grep].
- **Cascade skip does not stall anything**: gates publish requests fire-and-forget and report "requested" themselves (AutonomyFairy fairy.py:2557-2575 [C]).

## Could NOT verify

- Timing: whether B's request actually lands after `serial_started` on her machine, and whether B's `register_gate` is in fact the last writer. There are no logs here; it depends on postal dispatch (sync or async), which I did not trace.
- Whether, today, fairy.register really replaces B's directory instance (one_cortex.py:41-48 cites Boots M/N).
- Behavioural impact of losing interior `decay_all` and consolidation (activation saturation?) and the cortex energy feed to plane batteries.
- Windows mmap durability without the interior's periodic flush. My view is that the OS lazy writer covers process death but not power loss [I].
- Load from newly active `fs:{name}` writes by every awake fairy into cortex.manifold, concurrent with A's writes in the same process.
- K4's live state, and whether other processes (MCP, tools/scripts) hold RW handles on cortex.manifold. The MCP server opens it readonly (akashic_mcp_server.py:5710).
- The `verify_safety` F1/F4 and Boot M/N/DESIGN_14b documents that one_cortex.py cites are not in this mirror.

## CHECK THESE 3

1. **The zero-cortex gap in the floor.** `_FALLBACK_SENT.add(name)` runs before `publish(...)`, and the exception is swallowed, so a raising publish leaves no cortex and no retry: one_cortex.py:167-177 and 214-227 (measured in k2_switch_floor_test.out, "publish raises").
2. **K2 turns ON three paths that were inert under B's PortalGate**, because they need `.graph` / `_gpu_spread`, which only LocalManifoldGate has:
   - Organ_Template_0_3_0.py:5044-5075: every awake fairy writes `fs:` nodes into cortex.manifold every 10 ticks.
   - directory/handlers/heartbeat.py:391-410.
   - consciousness/collision_chamber.py:605-625.
3. **Interior-only maintenance stops**: `decay_all` is called only at portal_interior.py:3287, driven by B's `tick` at fairy.py:7946-7949. The energy-feedback publishes at fairy.py:7927/7937 also stop. Confirm the owner accepts both, or that something else covers them.
