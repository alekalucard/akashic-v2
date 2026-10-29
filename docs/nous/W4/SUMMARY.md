# W4 SUMMARY: one job, one fairy (proposal only)

Full report: `docs/nous/W4/SAME_JOB.md`. No code under `code/` was changed. Tags: [C] read in code, [M] measured here, [I] inference.


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

