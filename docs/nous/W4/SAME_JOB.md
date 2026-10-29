# W4: fairies that do the same job

Scope: the code-only mirror at `code/`. No server, fairy, boot or launcher was run, no module under `code/` was imported, and no `*.manifold` file was opened. Everything below comes from static reading (grep and `ast` scripts) plus a text-only replay of the boot scanner. **No code under `code/` was changed. Everything below is a proposal.**

Tags: **[C]** read in code, **[M]** measured by a script run here, **[I]** inference. Each claim gives `file:line` relative to the repo root.

Sort order: groups are ranked by **(resources saved x confidence)**, highest first. The ranking is a judgement **[I]**. The measured facts behind each rank are listed in its group.

> `docs/nous/W4/SUMMARY.md` could not be written from this session: the agent harness refuses files named like reports or summaries. Its content is in the next section.

## Summary

**Counts [M]:**

- 201 classes declare `ACTOR_NAME`, with 161 distinct names.
- 34 names are held by 2+ classes (74 copies); 31 of those names are outside test files.
- The scanner sees 149 entries, and the early pass keeps 127.
- The top-level `code/P*` trees are never scanned (`code/server.py:4944,4950`) [C].
- Groups: SAME JOB 7 (G1-G7, plus the templates in G8); OVERLAP 6 pairs (G8, G9); SAME NAME ONLY: channel collisions and the dead template copies.

**Same-plane duplicate winners are decided by directory enumeration order** (`code/server.py:4963-4989`) [M/I]. In 5 wrapper/engine pairs, the old engine wins and the V3 wrapper never boots.

**Fix pattern:** keep one class per name and strip `ACTOR_NAME` from the others. The precedent is `code/fairies/P00_Autonomic/nervous_system/hardware/cuda_fairy.py:209-210`.

**Not verified:**

- Her real NTFS enumeration order.
- The timing of `fairy.register` relative to GoBoot spec building.
- `state/boot_skip_registry` and any other state.
- Whether the top-level P30 modules import cleanly.
- Topics published through helper methods; the topic sets are lower bounds.
- Per-fairy trace-id generation.

**CHECK THESE 3:**

1. **The early pass bypasses `skip_classes`.** It registers every scan winner as sleeping with `needs_instantiation` (`code/server.py:4963-4989`), while the skip list is only applied at `code/server.py:6690-6736`. As a result, `MotorCortexFairy` and `BaseFairy` would be GoBoot-booted (`code/tracer_pool/boot_orchestrator.py:405,415`) [C+I].
2. **PhonemeCortexFairy is registered under class `MyOrganFairy`** (`code/fairies/P30_Cognition/PhonemeCortexFairy/fairy.py:109-110`). That name is the template base on success (`:94-95`), so GoBoot boots the generic template [C+I].
3. **The cognition triad is double-booted.** `code/fairies/P20_Somatic/SomaticMindFairy/fairy.py:140-146,2265-2275` build the stale top-level copies (`code/P30_Cognition/cognition/__init__.py:40-42`), while GoBoot boots `code/fairies/P30_Cognition/cognition/logic_fairy.py:351` and its two siblings [C+I].

---

## 0. How "which copy runs" was decided

### 0.1 Resolution rules used (all [C])

| Mechanism | Where | Effect |
|---|---|---|
| sys.path order | `code/server.py:1525-1527` | `code/` is first, then `code/postal_core/python`, then `code/fairies` (last). |
| Bare `P00_Autonomic.x` import | `code/P00_Autonomic/__init__.py`, `code/P10_Memory/__init__.py`, `code/P20_Somatic/__init__.py`, `code/P30_Cognition/__init__.py`, `code/P60_Executive/__init__.py` | These are regular packages because each has an `__init__.py`. A bare `P30_Cognition.cognition.X` therefore resolves **only** inside `code/P30_Cognition/`, never inside `code/fairies/P30_Cognition/`. `P40_Sensory` and `P50_Persona` have no top-level copy, so a bare import of them falls through to `code/fairies/` and loads a second module object of the same file. |
| `fairies.Pxx...` import | (most code) | Resolves to `code/fairies/Pxx/...`. |
| Boot scanner | `code/directory/migration.py:53-160`; regex at `:117` | Text-reads **only** `ROOT/"fairies"/<plane>` (`code/server.py:4944,4950`; `:6687`). The top-level `code/P*` trees are never scanned. A class line is recognised when it contains `class ` and the word `Fairy` (`migration.py:96`), and `ACTOR_NAME` is attributed to the **last such class line seen above it**. |
| Early first-wins registration | `code/server.py:4963-4989` | Iterates planes P00..P60 in order and keeps the first entry per `actor_name`. Each kept entry's class name is also added to the seen set (`:4972-4973`). The pass registers `status="sleeping"`, `needs_instantiation=True`, `source_file`, `class_name`. **It does not consult `skip_classes`.** |
| Phase 4b registration | `code/directory/migration.py:481-554`, called at `code/server.py:6736` | Same first-wins rule, honours `skip_classes` (`server.py:6690-6707`). Planes come from `as_completed` (`migration.py:178-180`), so cross-plane order is not deterministic. |
| Re-registration merge | `code/directory/fairy.py:705-733` | Later metadata wins key by key. Existing keys are kept. A status of running/booting is never demoted. |
| Registry key | `code/directory/registry.py:138,142-143` | `self._fairies[record.name]` and `_name_to_tracer[record.name]`: **two instances with the same name overwrite each other's record and tracer route.** |
| GoBoot | `code/tracer_pool/boot_orchestrator.py:972-977,1001-1011` | Boots only records with status `sleeping`. Excludes 4 names plus the suffix `Shadow`. Instantiates `getattr(module, metadata["class_name"])` from `source_file` (`:398,405,415`; `:751,758,768`). |
| Self-registration through postal | `code/directory/handlers/registration.py:74` | A `fairy.register` from `boot()` sets `status="running"`, so GoBoot skips that name. |
| Portals | `code/server.py:6108` | `_PORTAL_PLANE_CONFIGS = []`, so every plane boots in-process. |

### 0.2 Scanner replay [M]

`scanner_replay.py` (kept outside the repo) reproduces `_scan_file` line for line, without importing it, over `code/fairies/P00..P60`:

- **149** scanned entries and **127** early-pass winners [M].
- Traversal used the real `Path.rglob`, with `os.scandir` patched to return names in NTFS order (case-insensitive upcase sort; that ordering is [I], she runs on Windows). Python 3.12.3 and 3.14.6 gave **identical winners** [M]. `code/boot.bat:3,7` says she runs 3.14t [C].
- On a plain Linux directory order, `rglob` traversal differs between 3.12 and 3.14 [M]. **The winner of every same-plane duplicate is therefore chosen by filesystem enumeration order, not by intent** [I].

### 0.3 Census counts [M]

| Measure | Count |
|---|---|
| Classes with a class-body `ACTOR_NAME` in `code/` (AST) | 201 |
| Distinct ACTOR_NAME values | 161 |
| Names held by more than one class | 34 (74 copies). **31** of them are outside test-only files. |
| Status of the 201 actor classes | LIVE-BOOT 93 · LIVE-MANUAL 30 · SHADOWED(first-wins) 22 · IMPORTED-only 19 · DEAD 29 (18 in tests or `_old*`) · EXCLUDED by GoBoot 5 · scan-winner but manual-skip 3 |
| Top-level `code/P00,P10,P20,P30,P60` .py files | 58. Most are shims or stale partial copies of a `code/fairies/` twin (sizes differ; see `twins.py` output). The ones that still hold `ACTOR_NAME` are `GPUPoolFairy`, `SystemWorkerPoolFairy` (no twin), the three cognition fairies, the Organ_Template copies and `AssociationCortexFairyStub`. |
| Bare `Pxx_` imports that resolve to nothing (no file at that top-level path) | 14 module paths. 6 of them exist only under `code/fairies/`, so they are unreachable through the bare form (`bare.py`). |

Status legend:

- **LIVE-BOOT**: early-pass winner, not excluded, so GoBoot imports and boots this class.
- **LIVE-MANUAL**: `server.py` imports the module directly. For stub rows, this means the scanner registered that stub's class name.
- **SHADOWED**: lost first-wins to the same name.
- **IMPORTED**: only reached through imports.
- **DEAD**: no importer and not scanned.

---

## 1. Every duplicate ACTOR_NAME (non-test), with the winner

The winner is the LIVE row. All data is [M] from `census.py`, `scanner_replay.py` and `analyze.py`.

| ACTOR_NAME | copy (file:ACTOR_NAME line) | class | status | importers (non-test) |
|---|---|---|---|---|
| `actor` | code/P10_Memory/Akashic_Records_Physical/Organ_Templates/Organ_Template_0.3.0.py:1163 | AkashicActorCore | DEAD |  |
|  | code/fairies/P00_Autonomic/organ_template/Organ_Template_0_3_0.py:1163 | AkashicActorCore | LIVE-MANUAL (template base) | core/fairy.py, directory/fairy.py, ... (+4) |
| `AkashicEnvRegisteryFairy` | code/fairies/P30_Cognition/AkashicEnvRegistryFairy/fairy.py:50 | AkashicEnvRegistryFairyV3 | LIVE-BOOT |  |
|  | code/fairies/P30_Cognition/env_registry/akashic_env_registry.py:339 | AkashicEnvRegisteryFairy | SHADOWED | AkashicEnvRegistryFairy/fairy.py |
| `AkashicInferenceFairy` | code/fairies/P30_Cognition/AkashicInferenceFairy/fairy.py:135 | AkashicInferenceFairy | SHADOWED in scan; manual import in server | __init__, QuantumSearchFairy, server.py |
|  | code/fairies/P30_Cognition/AkashicInferenceFairy/fairy.py:52 | `Fairy` (ImportError stub) | **scanner registered this class_name** | same file |
| `AkashicRecordsLibrarianFairy` | code/fairies/P10_Memory/AkashicRecordsLibrarianFairy/fairy.py:50 | ...V3 | LIVE-BOOT |  |
|  | code/fairies/P10_Memory/librarian/akashic_records_librarian.py:383 | AkashicRecordsLibrarianFairy | SHADOWED | wrapper |
| `AutonomyFairy` | code/fairies/P00_Autonomic/AutonomyFairy/fairy.py:297 | AutonomyFairy | LIVE-MANUAL (`server.py:5524-5527`) | 6 |
|  | code/fairies/P30_Cognition/cognition/autonomy_fairy.py:467 | AutonomyFairy | SHADOWED in scan, **but lazily instantiated** (see G3) | 10 modules / 14 call sites |
| `BaseFairy` | code/P10_Memory/Akashic_Records_Physical/Organ_Templates/Organ_Template_0.1.0.py:55 | FairyBase | DEAD |  |
|  | code/fairies/P30_Cognition/cognition/working_memory_hub_fairy.py:272 | `MyOrganFairy` (stub) | **early-pass winner** (see G4) | 28 |
| `BlueprintDiaryHubFairy` | code/fairies/P10_Memory/BlueprintDiaryHubFairy/fairy.py:116 | BlueprintDiaryHubFairy | LIVE-BOOT | __init__ |
|  | code/fairies/P10_Memory/librarian/blueprint_diary_hub.py:323 | BlueprintDiaryHubFairy | SHADOWED |  |
| `CentralNervousFairy` | code/fairies/P00_Autonomic/CentralNervousFairy/fairy.py:87 | ...V3 | LIVE-BOOT |  |
|  | code/fairies/P00_Autonomic/nervous_system/central_nervous_postal_fairy.py:378 | CentralNervousFairy | SHADOWED | wrapper |
| `CochleaFairy` | code/fairies/P40_Sensory/CochleaFairy/fairy.py:91 | CochleaFairyV3 (wrapper) | **SHADOWED** | AudioCortexFairy |
|  | code/fairies/P40_Sensory/audio/cochlea_fairy.py:157 | CochleaFairy (engine) | **LIVE-BOOT** | 5 |
| `DirectoryFairy` | code/directory/fairy.py:170 | DirectoryFairy | LIVE-MANUAL (`server.py:4944`) | 4 |
|  | code/fairies/P00_Autonomic/DirectoryFairy/_old_fractured/fairy_old.py:47 | DirectoryFairy | SHADOWED, old |  |
|  | code/fairies/P00_Autonomic/DirectoryFairy/fairy.py:402 | DirectoryFairy | scan winner; GoBoot skips it (see G6) | 4 |
| `HarmonicCortexFairy` | code/fairies/P30_Cognition/HarmonicCortexFairy/fairy.py:285 | HarmonicCortexFairy | SHADOWED in scan; manual in server | server.py |
|  | code/fairies/P30_Cognition/HarmonicCortexFairy/fairy.py:133 | `MyOrganFairy` (stub) | scanner registered this class_name |  |
| `InnerNarratorFairy` | code/fairies/P30_Cognition/InnerNarratorFairy/fairy.py:515 | InnerNarratorFairy | SHADOWED in scan; manual in server | server.py |
|  | code/fairies/P30_Cognition/InnerNarratorFairy/fairy.py:97 | `Fairy` (stub) | scanner registered this class_name |  |
| `InterestSchedulerFairy` | code/fairies/P30_Cognition/InterestSchedulerFairy/fairy.py:66 | ...V3 (wrapper) | **SHADOWED** | InnerNarrator |
|  | code/fairies/P30_Cognition/cognition/interest_scheduler_fairy.py:526 | InterestSchedulerFairy (engine) | **LIVE-BOOT** | 5 |
| `IrrationalLogicFairy` | code/P30_Cognition/cognition/irrational_logic_fairy.py:65 | IrrationalLogicFairy (top-level, stale) | **instantiated by SomaticMind** (see G1) | cognition/__init__ |
|  | code/fairies/P30_Cognition/cognition/irrational_logic_fairy.py:167 | IrrationalLogicShadow | GoBoot-excluded (suffix) |  |
|  | code/fairies/P30_Cognition/cognition/irrational_logic_fairy.py:356 | IrrationalLogicFairy | LIVE-BOOT | cognition_team |
| `LogicFairy` | code/P30_Cognition/cognition/logic_fairy.py:66 | LogicFairy (top-level, stale) | **instantiated by SomaticMind** | cognition/__init__ |
|  | code/fairies/P30_Cognition/cognition/logic_fairy.py:351 | LogicFairy | LIVE-BOOT | cognition_team |
| `my_organ` | code/P10_Memory/.../Organ_Template_0.3.0.py:2224 | MyOrganFairy | DEAD |  |
|  | code/fairies/P00_Autonomic/organ_template/Organ_Template_0_3_0.py:2224 | MyOrganFairy | EXCLUDED (`boot_orchestrator.py:973`) | 7 |
|  | code/fairies/P10_Memory/config/config_store.py:960 | MyOrganFairy | SHADOWED |  |
| `MyFairy` | code/P10_Memory/.../Organ_Template_0_1_2.py:780 | MyFairy | IMPORTED | 1 |
|  | code/fairy_template/consolidated.py:927 | MyFairy | IMPORTED | 3 |
| `organ.shadow` | code/P10_Memory/.../Organ_Template_0.3.0.py:1371 | MyOrganShadow | DEAD |  |
|  | code/fairies/P00_Autonomic/organ_template/Organ_Template_0_3_0.py:1371 | MyOrganShadow | template base | 7 |
| `ParadoxCognitionFairy` | code/P30_Cognition/cognition/paradox_cognition_fairy.py:65 | (top-level, stale) | **instantiated by SomaticMind** | cognition/__init__ |
|  | code/fairies/P30_Cognition/cognition/paradox_cognition_fairy.py:350 | ParadoxCognitionFairy | LIVE-BOOT | 2 |
| `PerceptualGateFairy` | code/fairies/P40_Sensory/PerceptualGateFairy/fairy.py:70 | ...V3 (wrapper) | **SHADOWED** |  |
|  | code/fairies/P40_Sensory/perceptual_gate_fairy.py:177 | PerceptualGateFairy (engine) | **LIVE-BOOT** | 2 |
| `PhonemeCortexFairy` | code/fairies/P30_Cognition/PhonemeCortexFairy/fairy.py:147 | PhonemeCortexFairy | SHADOWED | __init__ |
|  | code/fairies/P30_Cognition/PhonemeCortexFairy/fairy.py:110 | `MyOrganFairy` (stub) | **LIVE-BOOT with the wrong class** (see G4) |  |
| `ProbabilityOracleFairy` | code/fairies/P30_Cognition/ProbabilityOracleFairy/fairy.py:131 | ProbabilityOracleFairy (893 loc) | SHADOWED in scan, **booted by CognitionTeam** (see G2) | 3 |
|  | code/fairies/P30_Cognition/oracle/akashic_probability_oracle.py:317 | ProbabilityOracleFairy (831 loc) | LIVE-BOOT | 2 |
| `SatelliteBridgeFairy` | code/fairies/P00_Autonomic/SatelliteBridgeFairy/fairy.py:94 | SatelliteBridgeFairy | LIVE-BOOT | __init__ |
|  | code/fairies/P00_Autonomic/nervous_system/hardware/satellite_bridge_fairy.py:89 | SatelliteBridgeFairy | SHADOWED, no importer |  |
| `SomaticAvatarFairy` | code/fairies/P50_Persona/SomaticAvatarFairy/fairy.py:156 | ...V3 | LIVE-BOOT |  |
|  | code/fairies/P50_Persona/avatar/somatic_avatar_fairy.py:94 | SomaticAvatarFairy | IMPORTED (not picked up by the scanner) | 2 |
| `SRMFeatureExtractorFairy` | code/fairies/P10_Memory/SRMFeatureExtractorFairy/fairy.py:44 | ...V3 | LIVE-BOOT |  |
|  | code/fairies/P10_Memory/triple_helix_srm_memory/feature_extractor.py:324 | engine | SHADOWED | wrapper |
| `SRMMemoryLibrarianFairy` | code/fairies/P10_Memory/SRMMemoryLibrarianFairy/fairy.py:62 | ...V3 (wrapper) | **SHADOWED** |  |
|  | code/fairies/P10_Memory/librarian/memory_librarian_fairy.py:326 | engine | **LIVE-BOOT** | wrapper |
| `SRMProjectIndexerFairy` | code/fairies/P10_Memory/SRMProjectIndexerFairy/fairy.py:44 | ...V3 | LIVE-BOOT |  |
|  | code/fairies/P10_Memory/triple_helix_srm_memory/project_indexer.py:378 | engine | SHADOWED | wrapper |
| `SRMProjectSnapshotFairy` | code/fairies/P10_Memory/SRMProjectSnapshotFairy/fairy.py:48 | ...V3 | LIVE-BOOT |  |
|  | code/fairies/P10_Memory/triple_helix_srm_memory/snapshot_fairy.py:319 | engine | SHADOWED | wrapper |
| `SRMReplayFairy` | code/fairies/P10_Memory/SRMReplayFairy/fairy.py:44 | ...V3 | LIVE-BOOT |  |
|  | code/fairies/P10_Memory/triple_helix_srm_memory/replay_adapter.py:319 | engine | SHADOWED | wrapper |
| `TelemetryVisionFairy` | code/fairies/P40_Sensory/TelemetryVisionFairy/fairy.py:99 | ...V3 | LIVE-BOOT |  |
|  | code/fairies/P40_Sensory/telemetry_vision/telemetry_vision_fairy.py:234 | engine | SHADOWED | 6 |
| `TemplateSeedFairy` | code/P10_Memory/.../Organ_Template_0_1_2.py:3024 | TemplateSeedFairy | IMPORTED | 1 |
|  | code/fairy_template/consolidated.py:3462 | TemplateSeedFairy | IMPORTED | 3 |

The test-only names (`NamedFairy`, `TestCardinal`, `TestFairy`) are omitted.

**Channel collisions among live classes [M]:**

- `cognition` is used by LogicFairy, IrrationalLogicFairy, ParadoxCognitionFairy, NousFairy, ProbabilityOracleFairy (engine) and WorkingMemoryHubFairy.
- `memory.ingest` is used by SRMIngestFairy (`code/fairies/P10_Memory/SRMIngestFairy/fairy.py:178`) and FoundersIngestFairy (`code/fairies/P10_Memory/FoundersIngestFairy/fairy.py:92`).
- `memory` is used by MemoryConsolidatorFairy and SRMMemoryLibrarianFairy (engine).
- `autonomic` is used by HabitConsultant, TemporalDispatcher and TimeSense.

These are SAME NAME ONLY at the channel level: the jobs differ.

---

## 2. Groups ranked by (resources saved x confidence)

### G1. Cognition triad booted twice: SAME JOB. Saving: 3 subscribed fairies. Confidence: high

| | copy A (GoBoot) | copy B (SomaticMind) | copy C (CognitionTeam) |
|---|---|---|---|
| Source | `code/fairies/P30_Cognition/cognition/{logic,irrational_logic,paradox_cognition}_fairy.py` (LIVE-BOOT [M]) | `code/P30_Cognition/cognition/{logic,irrational_logic,paradox_cognition}_fairy.py`: top-level, stale, 953/706/720 lines vs 1636/1230/1069 [M] | `code/fairies/...` same classes as A |
| How it is created | GoBoot spec | `from P30_Cognition.cognition import LogicFairy, IrrationalLogicFairy, ParadoxCognitionFairy` (`code/fairies/P20_Somatic/SomaticMindFairy/fairy.py:140-146`) [C]. This resolves to the top-level package [C, §0.1]. `code/P30_Cognition/cognition/__init__.py:29` star-imports the fairies copy, but `:40-42` then rebind the three names to the **local** copies [C]. Instantiated plus `.boot()` in `SomaticMindFairy.wire_cognition_fairies` (`fairy.py:2246-2300`), called from `on_boot` (`:800-801,820`) [C]. | `CognitionTeam._load_fairies` (`code/fairies/P30_Cognition/integration/cognition_team.py:513-537`, called at `:432`), reached from AkashicInferenceFairy (`code/fairies/P30_Cognition/AkashicInferenceFairy/fairy.py:255`) [C]. Constructed **without** `boot()` [C]. |
| Consumes | A: `consciousness.collision`, `cognition.irrational`, `cognition.paradox`, `mcp.tool_result`, `memory.recall.result`, `somatic.pulse` (logic; subscribed in `on_boot` at `fairies/.../logic_fairy.py:515-529`) [C] | B: `cognition.irrational`, `cognition.paradox`, `consciousness.collision`, `memory.recall.result` (`code/P30_Cognition/cognition/logic_fairy.py:223-244`) [C] | none (A's subscriptions live in `on_boot`) [I] |
| Produces | `cognition.logic` / `.irrational` / `.paradox`, `cognition.output`, `consciousness.stream` (B, measured) [M]. A publishes through helpers that the AST scan did not catch [M]. | same | (direct calls) |
| Tick | irrational `_feel_interval=45.0`, paradox `_paradox_interval=50.0`, plus `on_tick` (both copies) [M] | same | none |

Both A and B subscribe to `consciousness.collision` and to each other's outputs. **Every collision is therefore handled twice per kind, and each copy's outputs feed the other copy's handlers** [I]. Both copies register the same name (`registry.py:138` overwrites).

**Proposal:**

1. Survivor: copy A (GoBoot).
2. Change SomaticMind to fetch the running instances (directory `get_fairy_instance`, `code/directory/fairy.py:743`) instead of constructing them. Alternatively, import `fairies.P30_Cognition.cognition` and drop `wire_cognition_fairies`' construction.
3. Delete the top-level copies, or reduce them to a pure re-export by removing `code/P30_Cognition/cognition/__init__.py:40-42`.
4. Change CognitionTeam to reuse A as well.

**What breaks:**

- `SomaticMindFairy.cognition_fairies_status()` (`:2308-2317`) expects `.status()` on its private instances.
- The private 45 s and 50 s feeling loops of B stop.
- Anything that relied on B's older behaviour (953-line LogicFairy) changes to A's.

**Risk: 2.**

### G2. ProbabilityOracleFairy, two implementations, both booted: SAME JOB. Saving: 1 fairy and its loop. Confidence: high

| | A | B |
|---|---|---|
| File | `code/fairies/P30_Cognition/oracle/akashic_probability_oracle.py:311` (831 loc) | `code/fairies/P30_Cognition/ProbabilityOracleFairy/fairy.py:118` (893 loc) |
| Boot path | GoBoot winner [M] | `get_probability_oracle_fairy` constructs and `.boot()`s it (`ProbabilityOracleFairy/fairy.py:1019-1025`) [C], called by CognitionTeam (`cognition_team.py:541-542`) [C] |
| Channel | `cognition` | `oracle` |
| Importers | predictive_autonomy_mixin, working_memory_hub_fairy [M] | QuantumSearchFairy, cognition_team, __init__ [M] |

Both register `ProbabilityOracleFairy`, so the directory record and tracer route flip to whichever registers last (`registry.py:138,143`) [C/I].

**Proposal:**

1. Survivor: B, the `ProbabilityOracleFairy/` folder. It is the canonical folder and has the larger set of importers.
2. Move any A-only methods that are used by `predictive_autonomy_mixin.py` and `working_memory_hub_fairy.py` into B.
3. Make A a re-export, or remove its `ACTOR_NAME` (precedent: `code/fairies/P00_Autonomic/nervous_system/hardware/cuda_fairy.py:209-210`, "ACTOR_NAME stripped — wrapped by ...").

**What breaks:**

- Callers of A's module-level API.
- The channel changes from `cognition` to `oracle` for whoever filters on it [I].

**Risk: 3.**

### G3. AutonomyFairy, two engines: SAME JOB. Saving: 1 large engine (2847 loc, 0.5 s tick when booted). Confidence: medium

| | A (live) | B |
|---|---|---|
| File | `code/fairies/P00_Autonomic/AutonomyFairy/fairy.py:282` (2491 loc) | `code/fairies/P30_Cognition/cognition/autonomy_fairy.py:446` (2847 loc) |
| Boot | `server.py:5524-5527` (`.boot()`) [C] | Lazy singleton `get_autonomy_fairy()` builds `AutonomyFairy()` (`autonomy_fairy.py:3345-3355`) [C], from 14 call sites, for example `code/fairies/P00_Autonomic/consciousness_heartbeat_wiring.py:230-233` and `code/fairies/P00_Autonomic/nervous_system/dream_seed_fairy.py:76` [M] |
| Consumes | 14 topics, e.g. `drives`, `pain.relief`, `consciousness.thought` [M] | 25 topics, e.g. `claudefairy.*`, `cognition.logic`, `goal.*` [M] |
| Produces | `autonomy.*`, `goal.completed`, ... (22) [M] | `autonomy.goal`, `goal.completed`, `somatic.chemistry`, ... (6) [M] |
| State | `autonomy_state.json`, `speech_wanting_signal.json` [M] | `active_goals.json`; module constant `_AUTONOMY_STATE_FILE = state/autonomy_state.json` (`autonomy_fairy.py:22`) [C]. **Same state file name as A** [I: path equality not proven]. |
| Tick | `_cot_heartbeat_loop`, sleep 30 [M] | `_tick_interval=0.5` loop, started in `on_boot` (`:1063`) or on ignition (`:1080`) [C] |

Callers of `get_autonomy_fairy()` read drive or goal state from B, while A is the live engine (`dream_seed_fairy.py:83-84` already notes that "AutonomyFairy's get_active_goals was returning empty") [C].

**Proposal:**

1. Survivor: A.
2. Point `get_autonomy_fairy()` at the directory instance of A.
3. Port the B-only intents that the 14 callers use into A.
4. Retire B.

**What breaks:**

- The 14 call sites if A lacks the methods they call.
- The `autonomy_state.json` format if A and B share the file.

**Risk: 4.** Not verified: whether B's tick loop actually starts when no one calls `boot()`.

### G4. Scanner registers the wrong class, or a skipped class: identity bug (not a fusion), wasted instances. Confidence: high (code), medium (runtime)

- **4a, stub class captured.** The text scanner attributes `ACTOR_NAME` to the most recent `class ...Fairy` line (`migration.py:96-120`). Seven scan winners are registered with a stub or base class name [M]:
  - PhonemeCortexFairy → `MyOrganFairy` (`code/fairies/P30_Cognition/PhonemeCortexFairy/fairy.py:109-110`)
  - InnerNarratorFairy → `Fairy` (`:97`)
  - HarmonicCortexFairy → `MyOrganFairy` (`:131-133`)
  - AkashicInferenceFairy → `Fairy` (`:50-52`)
  - BaseFairy → `MyOrganFairy` (`working_memory_hub_fairy.py:272`)
  - MockRecallFairy → `MockFairy`
  - organ.shadow → `FairyProfileRegistry`

  GoBoot instantiates `getattr(module, class_name)` (`boot_orchestrator.py:398,415`) [C]. For PhonemeCortexFairy, when the template import succeeds, `MyOrganFairy = _organ_template.MyFairy` (`PhonemeCortexFairy/fairy.py:94-95`) [C]. **GoBoot would therefore boot the generic template class, not PhonemeCortexFairy** [I].

  HarmonicCortex, InnerNarrator and AkashicInference are rescued because `server.py` builds them by hand and registers `fairy_instance`.
- **4b, skip list bypassed.** The early pass (`server.py:4963-4989`) ignores `skip_classes`. Names that `server.py:6690-6707` means to skip, and that nothing else registers, therefore stay `sleeping` with `needs_instantiation=True`. That includes `MotorCortexFairy` (comment: "Keyboard/mouse singleton", `:6702`) and `BaseFairy` [C]. GoBoot then boots them [I].

  For `BaseFairy`, this re-executes all 12,374 lines of `working_memory_hub_fairy.py` under `fairy_dynamic_MyOrganFairy` (`boot_orchestrator.py:405`). That is a second module copy with its own module-level singletons [I]. The same mechanism voids the AKASHIC_NOUS_TEST slice (`server.py:6714-6730`) [I].

**Proposal:**

1. Remove `ACTOR_NAME` from the 7 stub classes. Leave a comment, as in `cuda_fairy.py:209-210`.
2. Pass the same skip set to the early pass, or have Phase 4b mark skipped names `status="skip"`.

**What breaks:** nothing should. Stubs still work standalone; they only lose scanner visibility.

**Risk: 1 (4a), 2 (4b).**

### G5. WorkingMemoryFairy and WorkingMemoryTrackerFairy: SAME JOB. Saving: 1 fairy plus a duplicated state file. Confidence: high

| | WorkingMemoryFairy | WorkingMemoryTrackerFairy |
|---|---|---|
| File | `code/fairies/P10_Memory/WorkingMemoryFairy/fairy.py:144` (940 loc, LIVE-BOOT [M]) | `code/fairies/P10_Memory/WorkingMemoryTrackerFairy/fairy.py:115` (318 loc, LIVE-BOOT [M]) |
| Docstring | "Tracks memory lifecycle with ID tracers" (`:1-19`) | same text, same lifecycle diagram (`:1-26`) [C] |
| Consumes | `consciousness.collision`, `consciousness.thought`, `memory.ingest`, `memory.recall` **plus** `consciousness.reflective`, `working_memory.query`, CNS backpressure/throttle/relief (`:246-284`) [C] | `consciousness.collision`, `memory.recall`, `memory.ingest`, `consciousness.thought` (`:177-180`) [C] |
| Produces | `working_memory.promoted`, `.consolidated`, `consciousness.thought`, `cns.component.pressure` [M] | none caught [M] |
| State | `SRM_Intake/working_memory/tracker_state.json` (`:52,811,824`) [C] | `state/working_memory_tracker/tracker_state.json` (`:169,409,422`) [C]. Same schema keys: `longterm_count`, `decayed_count`, `stats` [C]. |
| Tick | `NEEDS_HEARTBEAT=False`, event-driven (`:166`) | `NEEDS_HEARTBEAT=True` (`:138`) |

Each `memory.ingest` or `memory.recall` creates two tracers and is written twice [I].

**Proposal:**

1. Survivor: WorkingMemoryFairy, which is the superset and is referenced by name in `MemoryEngineFairy`, `TensorFabricFairy`, `SpeechCenterFairy` and `P10_Memory/__init__.py:100-106` [M].
2. Port anything the tracker does in `on_tick` (heartbeat-driven decay) into WorkingMemoryFairy's handler.
3. Retire the tracker. Merge its `stats` into WorkingMemoryFairy's state file once.

**What breaks:**

- The `cartographer_fairy.py:85` expected-fairy list, which names `WorkingMemoryTrackerFairy`.
- Anything reading `state/working_memory_tracker/`.

**Risk: 2.**

### G6. DirectoryFairy, two implementations: SAME JOB. Saving: one module, and the name stops being ambiguous. Confidence: medium

- A: `code/directory/fairy.py:155` is `SYSTEM.directory` (`server.py:4944`). It self-registers with `status="running"` (`code/directory/fairy.py:289-296`) [C]. It subscribes to `fairy.register`, `fairy.unregister`, `fairy.heartbeat`, `heartbeat.pulse`, ... [M].
- B: `code/fairies/P00_Autonomic/DirectoryFairy/fairy.py:393` is the scan winner [M]. Because A already holds the name as `running`, the scan re-registration cannot demote it (`directory/fairy.py:719-720`), so GoBoot skips B [I]. B is still imported by `fairies/P00_Autonomic/directory_fairy.py` and the organ template [M]. It subscribes to `directory.*`, `fairy.register`, `fairy.unregister`, `fairy.heartbeat`, `system.health_check` [M].
- Shared consumed topics: `fairy.register`, `fairy.unregister`, `fairy.heartbeat`. If B is ever instantiated and booted, both handle registrations [I].

**Proposal:**

1. Survivor: A.
2. Move B's `system.health_check` and `directory.*` intents into A.
3. Turn B and `_old_fractured/` into re-exports, or delete them.

**What breaks:** importers of `fairies.P00_Autonomic.DirectoryFairy` that use B-only methods.

**Risk: 3.**

### G7. Wrapper/engine twins that share one ACTOR_NAME: SAME JOB by design. Saving: no CPU, but restores intended identity. Confidence: high

There are 16 pairs. In each, a `<Name>Fairy/fairy.py` "V3" organ-template wrapper wraps an older engine module, and **both** declare the same `ACTOR_NAME` (§1).

The winner is decided by NTFS enumeration order [M, I]. In 5 pairs the **engine wins and the wrapper is never booted by GoBoot**: CochleaFairy, InterestSchedulerFairy, PerceptualGateFairy, SRMMemoryLibrarianFairy and ProbabilityOracleFairy (G2) [M].

As a result, wrapper-only behaviour does not run [I]. Example: CochleaFairyV3 Phase-B cortex-habit binding, `code/fairies/P40_Sensory/CochleaFairy/fairy.py:103,113,207-221`.

**Proposal:**

1. Strip `ACTOR_NAME` from every engine class, following the precedent at `code/fairies/P00_Autonomic/nervous_system/hardware/cuda_fairy.py:209-210`. The wrapper is the single identity.
2. Engines that are imported elsewhere (for example `telemetry_vision_fairy.py`, 6 importers) keep their classes; they just stop being scan candidates.

**What breaks:**

- For the 5 engine-wins pairs, the booted class changes from engine to wrapper. Postal subscriptions done by the engine's own `on_boot` move under the wrapper's lifecycle [I].
- The channel changes, e.g. PerceptualGate `perception.unified` → `sensory.perception`, CochleaFairy `None` → `sensory.audio` [M].

**Risk: 2.**

### G8. Stale top-level and template copies: SAME NAME ONLY or dead. Saving: disk and confusion only. Confidence: high

- `code/P10_Memory/Akashic_Records_Physical/Organ_Templates/Organ_Template_0.3.0.py` duplicates `actor`, `organ.shadow` and `my_organ` from `code/fairies/P00_Autonomic/organ_template/Organ_Template_0_3_0.py` at the same line numbers (1163/1371/2224). It has 0 importers [M]. The dotted file name cannot be imported as a module [I].
- `MyFairy` and `TemplateSeedFairy` exist in both `code/fairy_template/consolidated.py:927,3462` and `code/P10_Memory/.../Organ_Template_0_1_2.py:780,3024`. Both are imported [M]. **SAME JOB (template).** Survivor: `fairy_template/consolidated.py`. **Risk: 2.**
- `GPUPoolFairy` lives only in top-level `code/P00_Autonomic/nervous_system/hardware/cuda_fairy.py:209`. It is reached only through the top-level `hardware/__init__.py` [M]. Its `code/fairies/` twin is a different class (`CudaFairy`, ACTOR_NAME stripped) [C]. **OVERLAP** with `GPUFleetFairy` (`code/fairies/P00_Autonomic/nervous_system/hardware/gpu_fleet_fairy.py:131`): both route GPU work across workers and satellites (`gpu.task.submit` vs `fleet.generate`) [M]. Not proposed for fusion without runtime evidence.
- `code/fairies/P10_Memory/media/media_ingest_fairy.py:164` (no ACTOR_NAME, 0 importers, same docstring as `MediaIngestFairy/fairy.py:172`) is DEAD [M].
- `code/fairies/P10_Memory/config/config_store.py:960` `MyOrganFairy` with `my_organ` is SAME NAME ONLY (a template copy) [M].

### G9. OVERLAP, not fused (different jobs; evidence too thin)

| Pair | Why not SAME JOB |
|---|---|
| MemoryConsolidationFairy (`code/fairies/P10_Memory/MemoryConsolidationFairy/fairy.py:97`) vs MemoryConsolidatorFairy (`code/fairies/P10_Memory/consolidation/memory_consolidator_fairy.py:777`) | The first moves scattered memory files (`memory.consolidate` → `memory.consolidated`). The second orchestrates pattern consolidation (`patterns.json`). No shared topics [M]. |
| SomaticMind (`code/fairies/P00_Autonomic/SomaticMind/somatic_mind.py:89`) vs SomaticMindFairy | SomaticMind is a pre-boot sysadmin with its own 1 s tick. Its only importer is `demo.py` [M]. Likely dead [I]. |
| EmbodimentIntegratorFairy vs `_embodiment_integrator.py` EmbodimentIntegrator | Wrapper plus engine with distinct names. Fine as is. |
| AkashicLibrarianFairy (`code/fairies/P10_Memory/AkashicLibrarianFairy/fairy.py:147`, actor registry and status hub) vs AkashicRecordsLibrarianFairy vs SRMMemoryLibrarianFairy | Different jobs. Note that AkashicLibrarianFairy (`directory.register`, `fairy.status`, `fairy.card`) overlaps the Directory (G6) [I]. |
| AutonomyFairy vs AutopilotFairy vs EmbodimentFairy | They share `boot.wake_cascade.*` and `gate.habit.dispatched` by design: the "three gates" [M]. |
| SRMIngestFairy vs FoundersIngestFairy | Same channel `memory.ingest`, different topics [M]. Rename the channel only. |

---

## 3. Not verified

- Actual runtime directory enumeration order on her Windows disk. I assumed NTFS upcase order. If the order differs, the winners in §1 for same-plane pairs can flip [I].
- Whether the `fairy.register` publish from `boot()` lands synchronously before GoBoot builds specs. This decides whether G4b, G6 and SomaticMindFairy are really skipped or double-booted.
- The contents of `state/boot_skip_registry` (`boot_orchestrator.py:262`) and any other runtime state. Not in the mirror.
- Whether the top-level P30 cognition modules import cleanly at runtime (G1 copy B). I did not import them.
- Whether B in G3 ever starts its 0.5 s loop.
- Publish topics sent through helper methods (`self._emit*`, `send`). The AST scan catches only literal `.publish/.emit/.subscribe` calls, so the topic sets are lower bounds [M].
- Trace-id uniqueness. The registry routes by name (`registry.py:142-143`). I did not trace the tracer-id generation for every fairy.
