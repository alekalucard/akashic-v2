# W7 SUMMARY: one trace id system (design only)

Full design: `docs/nous/W7/TRACE_ID_DESIGN.md`. No code under `code/` was changed. Tags: [C] read in code, [M] measured here, [I] inference.


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

