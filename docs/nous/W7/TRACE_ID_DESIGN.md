# W7 -- One trace id system (design only)

Status: design document. No code under `code/` was changed. Nothing was run except grep, an AST walk and
`wc`/counts over the mirror at `origin/main` 189625f.

Tags: **[C]** read in code at the cited line, **[M]** measured here by a command over the mirror,
**[I]** inference (not verified). Paths are relative to `code/` unless they start with `docs/`.
`OT` = `fairies/P00_Autonomic/organ_template/Organ_Template_0_3_0.py`.

Owner's decision being designed for: ONE trace id system. Every creator has a trace id, its workers get
sub-ids. Builders can see what each part IS doing and what it is NOT doing. A wrong address returns to the
sender, and that return is a trace event.

---

## Summary (SUMMARY.md could not be written in this session; its content is here)

* Found: 31 id kinds in 6 incompatible formats. The key `tracer_id` holds a 12-hex string (OT:4446), an int
  (`fairy_tools.py:354`) or `gr_<name>_<ms>` (OT:4591) depending on the writer [C].
* No id links the layers: the fairy instance id (OT:1220) is not on its letters (`postal_core/src/lib.rs:166`),
  its memory nodes (`manifold_memory.py:259`), its spell chain (`fairy_template/spellchain_mixin.py:143`) or
  its heartbeat (`consciousness/heartbeat_registry.py:166`). Its own work tracers carry `fairy_id=""`
  (OT:3949,3979) [C+M].
* Memory `TRACE_*` is a shared source class, not an owner, and node bytes 48-63 are full
  (`manifold_memory.py:1619,1656`) [C]. The directive `trace_id` lookup (OT:2616-2628) is dead [C].
* Absence is erased: no-subscriber publishes count as published (`_python_fallback.py:1059`,
  `topic_bus.rs:249`), and the heart stamps every citizen alive each beat (`heartbeat_registry.py:353-354`) [C].
* The postal lease issuer already has the target shape. The scheme generalises it as L/R/F/W/O/M/E (section 3).
  10 registries are keyed by name (section 4.3). The migration runs M0-M8, and M7 (memory owner bits) is the
  riskiest step.
* Could not verify: the live postal backend or whether the lease is on, the Rust lease code (absent from the
  mirror [M]), whether tracer_pool.dll is present, the directive files, and the tracer_id values in the live
  .mnfl files.
* CHECK THESE 3: (1) `consciousness/heartbeat_registry.py:353-354` (also `:398`, `:404`): liveness is stamped
  regardless of delivery. (2) OT:2619 vs the parser at OT:2645-2665: the directive never yields `trace_id`.
  (3) `directory/handlers/registration.py:79` stores the contract `tracer_id`, but `directory/registry.py:182`
  `get_tracer_id` has 0 callers [M], and `fairies/P00_Autonomic/DirectoryFairy/fairy.py:669` reads a `fairy`
  key the contract lacks.

---

## 0. What exists today in one paragraph

Section 1 lists 31 id kinds. They are minted by many independent expressions in 6 incompatible formats: 12 lowercase hex (`uuid4().hex[:12]`), 36-char UUID strings, 12-char
UUID prefixes containing a hyphen, hash-derived `W-xxxxxxxx`, sequential counters (`py-000001`,
`cns-trace-N`), and small integers 0-12 (memory `TRACE_*`). The key name `tracer_id` carries three different
types depending on who wrote it: a 12-hex string (contract, OT:4446), an int category (FairyTools,
`fairy_tools.py:354`), and a `gr_<name>_<ms>` string (guild, OT:4591) [C]. Almost every registry is keyed by
fairy NAME, not by any id (section 4.3). The one place that already builds a real hierarchy -- the postal lease
issuer (`infrastructure/postal_lease_issuer.py`) -- is the template for the new scheme: namespace -> bus ->
pool -> lease, every id minted by the Organ Template `Tracer` and never reused (`postal_lease_issuer.py:9-29`)
[C].

Two "absences" are invisible by construction today:
* A publish that reaches nobody is counted as published (`postal_core/python/postal_core/_python_fallback.py:1059`;
  `postal_core/src/topic_bus.rs:249`), and the Python API returns `None` either way (`_python_fallback.py:934-939`,
  `postal_core/src/lib.rs:154,177`) [C].
* A fairy whose heartbeat callback never runs is still stamped alive every beat: the heart stamps every citizen
  in `_CITIZEN_OBJECTS` before delivering (`consciousness/heartbeat_registry.py:321-354`) and also stamps on the
  gated-skip and in-flight-skip paths (`:398`, `:404`) [C].

---

## 1. Survey of id kinds

Columns: **Issuer** (who mints), **Readers**, **Persists?**, **Scope** (unique per fairy / per instance /
shared). "Instance" = one Python object of a fairy in one process lifetime.

### 1A. Fairy identity (Organ Template)

| # | Id | Issuer (mint) | Readers | Persists? | Scope |
|---|----|---------------|---------|-----------|-------|
| 1 | `FairyProfile.fairy_id` | `uuid.uuid4().hex[:12]` at OT:1220, registered into `FairyProfileRegistry` keyed by **name** (OT:602-612) [C] | `tracer_id` property OT:3919-3921; contract OT:4446; mini chamber OT:1236; `spawn_tracer` (AkashicActorCore) OT:1333; postal lease issuer `_fairy_of`/`_lookup` `postal_lease_issuer.py:223-235,282-291` [C] | No (RAM only) [C for no write in OT; I for none elsewhere] | Per instance. A second `register()` under the same name overwrites `fairy_id` on the SAME profile object via `setattr` (OT:604-609) [C]; the earlier contract already published the old value [I]. |
| 2 | contract `tracer_id` | `getattr(self,'_tracer_id','') or profile.fairy_id` OT:4446, published on `fairy.register` OT:4449 [C] | live directory `directory/handlers/registration.py:79` -> `FairyRecord.tracer_id` `directory/registry.py:34` and `_name_to_tracer` `:133,142-143` [C]. `FairyRegistry.get_tracer_id` (`registry.py:182`) has **0 callers** [M: grep `get_tracer_id(`]. The other DirectoryFairy (`fairies/P00_Autonomic/DirectoryFairy/fairy.py:667-671`) reads `payload.get("fairy")`, a key the contract does not have [C]; `server.py:4712,4944` boot the `directory` package one [C]. | No | Per instance, except one override: `intent_to_goal_fairy.py:96` sets `_tracer_id = "tracer-<name>-<8hex>"` [C] (the only `self._tracer_id =` in code [M]). |
| 3 | `MyOrganFairy.tracer_id` property | alias of #1 OT:3919-3921 [C] | many fairies (`tracer_id` appears 1432 times in .py [M]) | No | Per instance |
| 4 | `MiniCollisionChamber.tracer_id` | #2 expression at OT:1236 [C] | broadcast on `consciousness.collision.mini` OT:1030-1036 [C] | No | Per instance |
| 5 | `mail_id` `MAIL::<plane>::<name>::v<maj.min>` | OT:1269-1273 [C] | contract `mail` OT:1293-1297; directory `registration.py:82` [C] | No, but deterministic from name+version, so stable across boots [C] | Per fairy (name), shared by all instances |
| 6 | `_mail_session` (12 hex) + `_mail_epoch` (ms) | OT:1189-1190 [C] | contract OT:1296; reused as a `boot_id` by `fairies/P10_Memory/triple_helix_srm_memory/snapshot_fairy.py:606` [C] | No | Per instance |
| 7 | `GATE_ID`, `GUILD_ID`, `GUILD_ROLE` | class constants, OT:1300-1303 [C] | contract; guild leader subscribe OT:4494-4509 [C] | In source | Per fairy class |

### 1B. Work tracers

| # | Id | Issuer | Readers | Persists? | Scope |
|---|----|--------|---------|-----------|-------|
| 8 | `Tracer.id` (12 hex) + `parent_id` | `Tracer` dataclass OT:389,395 [C]. `MyOrganFairy._init_tracer_worker` makes a root tracer OT:3947-3955 and `spawn_tracer` parents to it OT:3974-3976 [C] | `TracerRegistry` OT:447-480; `submit_work` path; `root_tracer_id` in stats OT:4092 [C] | No | Per work item. **Bug-shaped:** root and child tracers set `fairy_id=getattr(self,'fairy_id','')` (OT:3949,3979) but the template never sets `self.fairy_id` [C: grep shows only the two getattr sites]; and no file under `fairies/` assigns `self.fairy_id` [M: grep `self\.fairy_id\s*=` = 0 hits], so template work tracers carry `fairy_id=""` [C+M; a dynamic setattr was not ruled out]. The base-class `spawn_tracer` (OT:1327-1341, uses `self._profile.fairy_id`) is overridden by the `MyOrganFairy` one (OT:3959) [C: AST, AkashicActorCore 1151-1359 vs MyOrganFairy 2211-6401]. |
| 9 | `TracerRegistry` (organ template) | singleton via `__new__` OT:452-458; `get_tracer_registry` OT:483-490; `_init_tracer_worker` calls `TracerRegistry()` which returns the same singleton OT:3946 [C] | `get`, `get_by_fairy` (filters by **name**) OT:473-480 [C] | No; prunes oldest 1000 above 10000 OT:463-470 [C] | Process-wide |
| 10 | Two more `TracerRegistry` + `UniversalTracer.id` | `fairies/P00_Autonomic/tracer_worker_system.py:115,243,549` and a copy at `P00_Autonomic/tracer_worker_system.py:242` [C] | e.g. `working_memory_hub_fairy.py:126` imports the first [C] | No | Separate singletons from #9 [I: different classes, so different `_instance`] |
| 11 | Go `tracer_pool` tracer id | `uuid.New().String()[:12]` `tracer_pool/internal/tracer/types.go:178` -> 8 hex + `-` + 3 hex [C]. Python fallbacks: `str(uuid.uuid4())[:12]` `tracer_pool/tracer_pool.py:258` (same hyphen shape) and `_NullLib` counter `py-%06d` `tracer_pool.py:114-116` (restarts at 1 every process) [C] | Go registry indexes `byFairyName`, `byCluster`, `identities[FunctionName]` `tracer_pool/internal/registry/registry.go:140-151,311` [C]; `directory/migration.py:363-366` `_boot_tracer_id` [C] | No | Per item; the hyphen form fails the lease issuer's `_valid_tid` (12 hex only, `postal_lease_issuer.py:116-117`) [C+I] |
| 12 | `tracer_pool` Identity | `register_identity(function_name, ...)` `tracer_pool.py:354-370`, called from directory `registration.py:95-99` [C] | `resolve_identity(name)` `tracer_pool.py:373` [C] | No | Keyed by **name** |
| 13 | `InfraEvent.trace_id` (12 hex), `InfraActor` by name | `infrastructure/infra_tracer.py:69,97-100` [C] | ring buffer + `telemetry.infra.*` topics `infra_tracer.py:35-39` [C] | No | Per event; actors per name |

### 1C. Memory ownership

| # | Id | Issuer | Readers | Persists? | Scope |
|---|----|--------|---------|-----------|-------|
| 14 | Memory `TRACE_*` ints 0-12 | constants `infrastructure/manifold_memory.py:175-205`; priority table `:209-226` [C]. Passed as literals at 46 call sites in 11 files (SYSTEM 12, SEEDED 9, PERSONAL 9, INFERENCE 6, ACE 5, VISUAL 2, MOTOR 2, BOOKS 1) [M: grep `tracer_id=TRACE_`] | node field 12 / edge field 5 `manifold_memory.py:259,281`; ownership guard `:2243-2248`, `set_snippet` `:2474-2491`; filters `:2811,2956,3283`; census `:3536`; node dict `:2387`; edge dicts `:2892,2909` [C]. Outside: `infrastructure/portal_interior.py:1713,2320,2398`, `cortex_reasoner.py:2377`, `thought_chain_engine.py:296`, `wmh_tools.py:395` read `node['tracer_id']` [C] | **Yes** -- 4 bytes (`I`) in every 64-byte node and 24-byte edge in the `.mnfl` file `:246,275` [C] | **Shared category**, not an owner. Every fairy of the same class writes the same int [C]. Node bytes 48-63 (the `_reserved` region) are already used: fairy_state + affect_coupling[56-59] + paradox_residue[60-63] `:1619,1656-1657` [C]; edges have 2 spare bytes `:283` [C]. |
| 15 | Directive `trace_id` -> `FairyTools.trace_id` | OT:2615-2628 looks up `self._directive["trace_id"]` [C]. `_load_directive` (OT:2636-2669) only sets `raw`, `loaded`, `sections`, and `activation/nature/essence/core_values/foundation` [C]; no code anywhere assigns `_directive["trace_id"]` [M: grep]. So every template fairy's tools get `TRACE_SYSTEM` (5) [C+I] | `FairyTools.publish_thought` sends it as **`"tracer_id"`** (int) on `consciousness.working_memory.store` `fairy_tools.py:349-355` [C] | No | Shared (all = 5) [I] |

### 1D. Batteries, spells, chains

| # | Id | Issuer | Readers | Persists? | Scope |
|---|----|--------|---------|-----------|-------|
| 16 | `B-`, `W-`, `C-`, `CT-`, `CR-`, `CP-` + 8 hex | `_derive_trace_id(portal_id, component)` = sha256(`portal_id:component`)[:8] `infrastructure/dimension_battery.py:50-67`, wired at `:469-481` [C] | OT `_spell_trace_ids` OT:3887-3905 (also `portal_id`) [C]; battery save/load `dimension_battery.py:135,151,242,253,389-423` [C] | Yes, inside battery save data (`save()`/`load()` doc `:444-445`) [C], and deterministic anyway | **Shared per portal**: the fairy takes `system.batteries[ACTOR_NAME]`, else `[ACTOR_PLANE]`, else `["System"]` OT:3841-3845 [C], so all fairies on a plane/System battery report the same `B-`/`W-` [I] |
| 17 | spell `trace_id` = `<battery W/B id>-<last 8 of spell.id>` | `dimension_battery.py:650-651` [C] | battery executor | No | Per spell |
| 18 | `Spell.id` `spell_<12hex>` | `spellchain/spell.py:62` [C] | pool/chain | in chain save data `spell.py:259` [C] | Per spell |
| 19 | `SpellChain.fairy_id` `<ACTOR_NAME>_<id(obj)>` and `SpellChain.id` `chain_<fairy_id>_<8hex>` | `fairy_template/spellchain_mixin.py:143`; `spellchain/chain.py:95-96` [C]. The template constructs a throwaway `SpellChainMixin()` (OT:3852) so `id(self)` there is the mixin's address, not the fairy's [C+I] | `chain_id` in OT:3888 [C]; battery `_spell_chains` keyed by fairy_id `dimension_battery.py:487` [C] | No | Per instance, but unrelated to #1 |

### 1E. Postal

| # | Id | Issuer | Readers | Persists? | Scope |
|---|----|--------|---------|-----------|-------|
| 20 | Rust `Envelope.trace_id` (UUID string), `source`, `reply_to`, `correlation_id` | `Envelope::new` sets `trace_id = Uuid::new_v4()`, `source = ""`, `reply_to/correlation_id = None` `postal_core/src/envelope.rs:61-73` [C]. The Python binding `publish(intent,payload,priority,pool)` has no source/trace/correlation argument `lib.rs:153-167` [C] | getters `lib.rs:74-80` [C]; no caller-supplied value can reach them [C] | No | Per letter, but disconnected from any sender id |
| 21 | Python fallback `Envelope` (same fields) | `_python_fallback.py:27-39`; `publish` builds it with only intent/payload/priority `:961-965` [C] | -- | No | Per letter |
| 22 | `TensorEnvelope.trace_id` | default `""` `tensor_fabric.py:126` [C]; `TensorFabric.publish(..., source="")` copies `source` into **payload** only `:1275-1277`, then calls `self._postal.publish(intent, payload, priority)` `:1306` [C] | handlers | No | Empty |
| 23 | Postal lease: `NS` (ns root), `bus_tid`, `pool_tid`, `lease_tid`, subscription target tag, address `postal/<bus>/<topic>/w<n>` | all minted by the template `Tracer` (`_mint` `postal_lease_issuer.py:120-134`), never reused (`_ISSUED` `:46,137-146`); ns `:160-173`; bus `:354-370`; pool `:176-187`; lease `:389-415`; tag = target fairy_id or `?<name>` `:313-350,373-386` [C] | Rust (asks `issue_*`), `census()` joins lineage `ns/bus/pool/lease` `:419-463`; written to `state/postal_lease_census.json` `:480-498` [C] | Census file only (snapshot, every 300 s by default `:54`) [C] | ns per process; bus per PostalCore; pool per (bus, topic); lease per worker thread; tag per subscription. **Off unless** `state/postal_lease.json` exists and the Rust core is in use (`tensor_fabric.py:969-998`) [C]. The Rust side (`set_lease_issuer`, `worker_mode`, `lease_census`) is **not in this mirror's** `postal_core/src` [M: grep returns nothing]. |
| 24 | AKP message `id` + optional `trace_id` | `postal_core/python/postal_core/akp_protocol.py:324-333` [C] | AKP bridge/server | No | Per request |

### 1F. Request/response, boot and other ad-hoc ids

| # | Id | Issuer | Readers | Persists? | Scope |
|---|----|--------|---------|-----------|-------|
| 25 | Guild request `tracer_id` `gr_<ACTOR_NAME>_<ms % 100000>` | OT:4591 [C] | class-level `_guild_pending` / `_guild_events` (shared by ALL fairies) OT:4563-4565,4609-4611; matcher OT:4718-4727 [C] | No | Per request; wraps every 100 s and two requests by one fairy in the same ms collide [I]. A reply whose tracer is not pending (late, after timeout OT:4666-4671) is dropped with no record (OT:4724 has no else) [C]. |
| 26 | Perspective `trace_id` = `ACTOR_NAME` | OT:4833 [C] | interest_generator route-back (OT:4805-4821 doc) [C] | No | Per fairy name |
| 27 | CNS `cns-trace-<N>` | `fairies/P00_Autonomic/CentralNervousFairy/fairy.py:598-599` [C] | `cns.trace` subscribers | No | Counter, restarts per process |
| 28 | Boot ids (5 shapes): `cascade_<8hex>` `SomaticMindFairy/fairy.py:8164`; `uuid hex12` `BlueprintDiaryHubFairy/fairy.py:150`; `_mail_session` reuse `snapshot_fairy.py:606`; `orch_<unix>_<plane>` `unconscious_mind_fairy.py:945`; literal `"k2_fallback"` `infrastructure/one_cortex.py:176` [C] | Embodiment/Autopilot cascade `EmbodimentFairy/fairy.py:2029,2103`, `AutopilotFairy/fairy.py:3751` [C] | some written into logs/snapshots [I] | Per cascade, unrelated to each other |
| 29 | Misc: `ace_<unix>_<6hex>` `working_memory_hub_fairy.py:2611`; stub `stub_<type>_<time>` `fairy_template/consolidated.py:177`; `CLUSTER_TRACER_ID` `AssociationCortexFairy/fairy.py:2700`; `owner_trace_id` `thinking_directive.py:63` [C] | local | -- | -- |

### 1G. Heartbeat

| # | Id | Issuer | Readers | Persists? | Scope |
|---|----|--------|---------|-----------|-------|
| 30 | HeartbeatRegistry entries | `register(name, callback, plane)` keyed by **name** `consciousness/heartbeat_registry.py:166-201`; same-name re-register replaces the callback and only prints `OVERWRITE` `:196-200` [C] | `_last_delivered_ts[name]` read by `directory/handlers/heartbeat.py:333-358,515-516,682` [C] | No | Per name. No id at all. |
| 31 | Directory heartbeat `_sender` | read `fairies/P00_Autonomic/DirectoryFairy/fairy.py:679-683` [C] | `Directory.touch(name)` | No | Per name |

Counts [M]: 1169 `.py` files in `code/`; identifier `tracer_id` 1432 occurrences, `trace_id` 217, `parent_tracer_id`
74 (grep `-o` over `*.py`); `tracer_id` appears in 119 files outside the archived templates; 45 files under
`fairies/` mention `MyOrganFairy`, 37 declare a class that subclasses it.

---

## 2. Findings that shape the design

F1. **No id ties the layers together.** The fairy instance id (#1) is not on the letters it sends (#20-22), not
on the memory nodes it writes (#14), not on its spell chain (#19), not on its heartbeat (#30), and its own
work tracers carry `fairy_id=""` (#8) [C+I].

F2. **The memory "trace id" is a source CLASS, not an identity** (#14). It must stay (the priority guard at
`manifold_memory.py:2243-2248` depends on it) but it is a different thing from a trace id; the design names it
`trace_class` and adds an owner beside it.

F3. **The directive path is dead** (#15): the parser never produces `trace_id`, so the lookup at OT:2619 is
always empty [C].

F4. **The lease issuer already is the target shape** (#23): one mint, parent links, never-reuse set, census with
a `lineage` string (`postal_lease_issuer.py:459`). The design generalises it rather than inventing a new one.

F5. **Absence is erased twice**: unsubscribed publishes count as published, and heartbeat liveness is stamped
for every citizen whether or not its callback ran (section 0) [C].

F6. **Name is the primary key almost everywhere** (section 4.3), and same-name replacement is silent or
print-only (OT:604-609; `heartbeat_registry.py:196-200`; `_CITIZEN_OBJECTS[name] = self` OT:1248) [C].

---

## 3. The scheme

### 3.1 One id, one mint, one ledger

* **Format.** A trace id (`tid`) is 12 lowercase hex, exactly what `Tracer.id` mints today (OT:389) and what
  the lease issuer validates (`postal_lease_issuer.py:116-117`). No new format.
* **One mint.** `mint(kind, parent_tid, owner_name, op, payload) -> tid`, implemented once (a lift of
  `postal_lease_issuer._mint/_commit/_issue`, `:120-157`), with the never-reuse set. Every other expression in
  section 1 either calls it or is retired.
* **One ledger.** Every mint appends `{tid, parent, kind, owner_name, channel, op, ts}` to an in-RAM index plus an
  append-only JSONL under `state/` (rotated). Lineage is resolved from the ledger by walking `parent`; letters
  carry only `tid` and `parent`, not the full path. This replaces the three `TracerRegistry` singletons and the
  Go registry as the place to look things up (they become views, then are retired, section 4).
* **Hierarchy (lineage string = tids joined by `/`, as the census does at `postal_lease_issuer.py:459`):**

```
life      L   one per (ACTOR_NAME, ACTOR_CHANNEL); persisted in the ledger; survives boots ("id for life",
              postal_lease_issuer.py:5)
boot      R   the galaxy/root of one process = today's lease NS (postal_lease_issuer.py:160-173), minted on
              first use; payload {pid, main, prev_boot}
creator   F   an INSTANCE: a fairy object, an infra actor, a battery/portal, a PostalCore bus.
              parent = R. Payload names its life id L (the "who" across boots).
worker    W   a sub-id of a creator: work-tracer root, spell chain, postal pool/lease, executor thread.
              parent = F (or another W)
op        O   one unit of work: a Tracer, a spell cast, a guild request, a boot cascade. parent = W or F
letter    M   one envelope. parent = the O (or F) that sent it
event     E   a trace event about something that did NOT happen: return, absence, overwrite.
              parent = the M or F it is about
```

A fairy's identity triple is `(ACTOR_NAME, ACTOR_CHANNEL, F)` with `L` as the cross-boot handle. `mail_id`
(#5) stays as the human-readable stable ADDRESS; it is not an id and is derivable from the name.

### 3.2 Mapping every existing kind

| # | Existing | New role | Action |
|---|----------|----------|--------|
| 1 | `FairyProfile.fairy_id` | **F** (creator instance) | mint through ledger with parent R; keep field name |
| 2 | contract `tracer_id` | F, plus new `life_id` = L, `boot` = R | keep key; retire the `_tracer_id` override at `intent_to_goal_fairy.py:96` |
| 3 | `.tracer_id` property | alias of F | keep |
| 4 | mini chamber `tracer_id` | F | keep |
| 5 | `mail_id` | address (not an id) | keep |
| 6 | `_mail_session`/`_mail_epoch` | redundant with F / R | retire after readers (`snapshot_fairy.py:606`) move to R |
| 7 | `GATE_ID`/`GUILD_ID` | static labels | keep as labels |
| 8 | `Tracer.id` | **O**; root tracer = **W** "tracer-root" under F | mint via ledger; set `fairy_id=F` (fixes the `""` at OT:3949,3979) |
| 9,10 | three `TracerRegistry` | views over the ledger | retire two copies; keep OT one as a facade |
| 11,12 | Go `tracer_pool` ids, `py-N`, identities | O (ids come from the ledger, Go stores them) | stop minting in Go/NullLib; identity keyed by L not name |
| 13 | `InfraEvent.trace_id`, `InfraActor` | infra actor = F; event = O | mint via ledger |
| 14 | memory `TRACE_*` | **trace_class** (unchanged ints) + **owner** = index of L | see 3.4 |
| 15 | directive `trace_id` / FairyTools int | trace_class declared on the class (e.g. `TRACE_CLASS = "SYSTEM"`) | fix or delete the dead directive lookup; rename the `"tracer_id"` key in `fairy_tools.py:354` to `trace_class` and add `owner_tid` |
| 16 | `B-`/`W-`/`C-`/`CT-`/`CR-`/`CP-` | battery/portal = F (infra creator); components = W; derived strings kept as **display labels** | mint F once per portal per boot; L = portal_id |
| 17,18 | spell trace / `Spell.id` | O under the fairy's chain W | -- |
| 19 | `SpellChain.fairy_id`, `chain_id` | W under the fairy's F | pass F into the chain instead of `<name>_<id(mixin)>` |
| 20-22 | `Envelope.trace_id`, `source`, `correlation_id` | `trace_id` = **M**, `source` = sender F (or O), `correlation_id` = the M being answered | add optional args to the binding and fallback; TensorFabric stops stuffing source into payload only |
| 23 | lease NS/bus/pool/lease/tag | NS = **R**, bus = F (infra), pool = W, lease = W, tag = target F or `?<name>` | keep; already conformant |
| 24 | AKP `trace_id` | carries M across the bridge | keep |
| 25 | guild `gr_...` | O under F; `reply_topic` unchanged; late reply = E(return, `late_reply`) | -- |
| 26 | perspective `trace_id=ACTOR_NAME` | F | -- |
| 27 | `cns-trace-N` | O under CNS F | -- |
| 28 | boot ids (5 shapes) | cascade = O under R; the process boot itself = R | -- |
| 29 | misc | O | -- |
| 30,31 | heartbeat by name | registration carries F; absence = E | see 3.6 |

### 3.3 Fairy identity

* At `AkashicActorCore.__init__` (OT:1218-1226): F = `mint("creator", R, ACTOR_NAME, "fairy.instance",
  {channel, plane, class, L})`; L = ledger lookup of `(ACTOR_NAME, ACTOR_CHANNEL)` or mint once.
* Same-name re-registration (OT:604-609, OT:1212-1215) emits `E(overwrite, parent=old F, new=F')` instead of
  silently replacing the id.
* The engine-borrows-wrapper case (OT:1227-1229) gets W under the wrapper's F, so inner engines become workers
  of their wrapper, which is what they are.

### 3.4 Memory owner of a written node

The node record has no free bytes (bytes 48-63 are in use, `manifold_memory.py:1619,1656-1657`) [C], so the owner
cannot be a new field without a file-format migration. Proposal: split the existing 4-byte `tracer_id`
(`:259`, `:281`):

```
bits  0-7   trace_class   (today's TRACE_* value, 0-12)          -- unchanged meaning
bits  8-31  owner index   (24 bits = 16.7 M lives) -> ledger row -> L -> (name, channel)
```

* Existing files read correctly as `owner=0` ("unknown/legacy"), because all stored values are <= 12 [I: true
  for every constant at `:175-205`; not verified on her live `.mnfl` files].
* Owner is the **life** id L (stable across boots), not F, so "who wrote this" survives restarts; F of the
  writing instance can go to the ledger as an O ("memory.write") when finer detail is wanted.
* **Edges** carry the same split in their `tracer_id` field (`:281`).
* Precondition (see migration M7): every reader must compare `v & 0xFF`, not `v`.

### 3.5 Postal envelopes and returned letters

* **Letter id.** M = `Envelope.trace_id`. Today a fresh UUID per envelope with no link (`envelope.rs:69`,
  `_python_fallback.py:35`) [C]. New: minted as a 12-hex child of the sending O/F; `source` = sender F.
* **Return to sender.** A publish whose matched-subscriber count is 0 is a **return**, not a publish. Concretely:
  * Python fallback: `subs` is already computed (`_python_fallback.py:991-1005`); when it is empty, count
    `messages_returned` instead of (not in addition to) `messages_published` at `:1059`, and append
    `E(return, reason="no_subscriber", letter=M, sender=source, intent)`.
  * Same treatment for the other silent outcomes in the same function: `target_pool is None` (`:1083-1088`,
    reason `no_pool`), `enqueue_no_signal` false (`:1090-1094`, reason `queue_full`), not running (`:948-949`,
    reason `bus_stopped`).
  * Rust `publish_routed` (`topic_bus.rs:217-251`): count the subscribers that pass `wants()` (`:240`); if 0,
    `metrics.inc_returned()` instead of `inc_published()` (`:249`) and push a small record into a bounded ring
    that Python drains, the same pull pattern as `lease_census()` (`postal_lease_issuer.py:421-428`). Also the
    early returns at `:218-220` (stopped) and `:223-225` (empty intent) become returns.
  * In-process `PostalHub.route` already returns the delivered count (OT:683-697) [C]; `_FabricPostalBridge.route`
    returns `1` whenever no exception is raised (OT:842-847) [C], which hides the return. It should return the
    bus's matched count once the bus reports it.
  * **Delivery of the return.** The return record goes to the ledger (never back through postal, to avoid
    a return-of-a-return loop). The sender sees it by asking the ledger for `E` children of its F, and an
    optional per-fairy counter `returned` on `FairyProfile` next to `messages_sent` (OT:559).
  * Guild late reply (OT:4724) and unresolved subscription tags `?<name>` (`postal_lease_issuer.py:313-316,345`)
    are also `E(return)`.
* **Replies.** `correlation_id` = the M being answered; the guild's `tracer_id` in payload becomes redundant.

### 3.6 Heartbeats: silence is an event

* Registration: `HeartbeatRegistry.register(name, cb, plane)` (`heartbeat_registry.py:166`) gains `tid=F`.
* Keep the two meanings apart (the comment at `:307-317` already says liveness and work are separate):
  * `attested[F]` = the heart saw the citizen exist (today's `_last_delivered_ts`, keep it -- the directory
    watchdog depends on it, `directory/handlers/heartbeat.py:358,516,682`).
  * `served[F]` = beat number of the last callback that RETURNED (stats worker already observes completion,
    `:459-527`).
* Absence: when `beat - served[F] > k * divisor(plane)` (divisor `:388-395`), emit `E(absence, parent=F,
  last_served_beat, reason in {never_served, gated, in_flight, error, slow})` once per transition, and
  `E(present)` when it resumes. Gated and in-flight skips (`:396-406`) are recorded as their reason, not as
  service.
* A citizen in `_CITIZEN_OBJECTS` with no heartbeat registration at all (the Cochlea case, `:313-316`) is an
  `E(absence, reason=never_registered)`.

---

## 4. Migration, smallest first

Each step is separately revertible and changes no behaviour of her mind, only what is recorded.

| Step | Change | Size | What can break |
|------|--------|------|----------------|
| M0 | Lift the lease issuer's mint/commit/never-reuse into one `trace_ledger` module (RAM index + JSONL). Nothing calls it yet. | 1 new file | nothing |
| M1 | Counters only: `messages_returned` in the Python fallback (`_python_fallback.py:1059`) and `returned` in Rust metrics (`topic_bus.rs:249`). No records yet. | ~10 lines + Rust rebuild | any dashboard that sums `messages_published` sees a drop equal to the old silent losses [I]; Rust ABI rebuild must be done from her live tree because the mirror lacks the lease Rust code [M] |
| M2 | Mint F through the ledger at OT:1220 (same 12-hex shape), record R. Fix work tracers to use F (OT:3949,3979). | ~10 lines in OT | nothing reads `Tracer.fairy_id` for equality [I, not exhaustively checked] |
| M3 | Envelope `source` and `trace_id` args: Python fallback `publish` and the Rust binding (`lib.rs:153-167`); TensorFabric passes `source` through (`tensor_fabric.py:1306`) | small API change | callers passing positional args to `publish` [I]; the compiled extension must be rebuilt |
| M4 | Return records (`E(return)`) for the reasons in 3.5, drained into the ledger | medium | ring overflow under storms: must be bounded and counted |
| M5 | Heartbeat `served[F]` + absence events. **Do not** change `_last_delivered_ts`. | medium | the 2026-04-17 / 2026-05-10 false-death bugs (`heartbeat_registry.py:307-345`) return if anyone wires absence into the watchdog's kill path; keep it observation-only |
| M6 | Guild, perspective, CNS, boot cascade, infra events mint O under F/R; guild late reply = E(return) | many small edits | guild matcher keyed by the payload `tracer_id` string (OT:4718-4727): keep the payload key, change only its value |
| M7 | Memory owner: first replace every `record[12]` / `node['tracer_id']` comparison with `trace_class(v)` (`manifold_memory.py:2245-2248,2474-2491,2811,2956,3283,3536`; `portal_interior.py:1713,2320,2398`; `cortex_reasoner.py:2377`; `thought_chain_engine.py:296`; `wmh_tools.py:395`), THEN start writing owner bits | the riskiest | any equality test missed turns owned nodes invisible to filters, e.g. motor-region check at `portal_interior.py:1713`; `TRACE_PRIORITY.get(v)` (`:2245-2246`) returns 0 for a combined value. 12 `record[12]` sites [M] plus the 6 external readers above; there may be more readers of `.mnfl` files outside `code/` [I] |
| M8 | Retire: two extra `TracerRegistry` copies, Go/NullLib minting, `consolidated.py:177` stub, `_mail_session` as boot id, `intent_to_goal_fairy.py:96` override, dead directive lookup | deletions | importers of the retired modules (`working_memory_hub_fairy.py:126` etc.) |

### 4.3 Registries keyed by NAME today

All of these key by fairy name. The recommendation is NOT to re-key routing (name is the address), but each
must (a) store F as the value, (b) keep a reverse index F -> name, and (c) emit `E(overwrite)` on same-name
replacement instead of silently replacing:

* `FairyProfileRegistry._profiles[name]` OT:598,604-612 [C]
* `_CITIZEN_OBJECTS[name]` `fairy_template/citizen_registry.py:33`, written OT:1248 [C]; read by
  `PostalHub.use_intent` OT:761 and `_FabricPostalBridge.use_intent` OT:898 [C], and by the heart
  `heartbeat_registry.py:323-354` [C]
* `HeartbeatRegistry._callbacks/_fairy_planes/_slow_counts/_error_counts/_last_delivered_ts` `:67-102` [C]
* Directory `FairyRegistry._fairies/_name_to_tracer/_topic_to_fairies/_fairy_to_topics` `directory/registry.py:120-133` [C]
* Fallback `Directory._fairies/_capabilities/_last_seen` `fairies/P00_Autonomic/DirectoryFairy/fairy.py:82-90` [C]
* Go `identities[FunctionName]`, `byFairyName` `tracer_pool/internal/registry/registry.go:141,311` [C]
* `system.batteries[ACTOR_NAME | ACTOR_PLANE | "System"]` OT:3841-3845 [C]
* `TracerRegistry.get_by_fairy(fairy_name)` OT:477-480 [C]
* Lease issuer name resolution `_lookup/_by_name` `postal_lease_issuer.py:282-310` (already records disagreement
  between frame, bridge and name, `:319-350`) [C]
* `InfraActor` by name `infra_tracer.py:97-100` [C]

---

## 5. What could not be verified here

* Which postal backend runs live (Rust vs `_python_fallback`) and whether `state/postal_lease.json` exists
  (lease on/off) -- no state in the mirror.
* The Rust lease code itself: `set_lease_issuer`, `worker_mode`, `lease_census` are absent from
  `postal_core/src` in this mirror [M], so the Rust half of #23 is described only from the Python side.
* Whether `tracer_pool.dll/.so` is present live (`tracer_pool.py:21-23`); if absent, ids are `py-N` (#11).
* Directive files (`<root>/directives/*.directive`, OT:2553) are not in the mirror; moot for #15 because the
  parser never reads `trace_id` anyway.
* The value distribution of `tracer_id` in her live `.mnfl` files (needed before M7).
* Whether any fairy sets `fairy_id` dynamically (setattr/property); a plain `self.fairy_id =` has 0 hits under `fairies/` [M].
* Live fairy count and how many share a plane/System battery (#16).
