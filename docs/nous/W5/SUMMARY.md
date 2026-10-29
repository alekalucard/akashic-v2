# W5 — four boot fixes (B2, B3, B4, B5)

Branch `nous/w5-boot-fixes`. Tags: [C] read in code, [M] measured here, [I] inference.

## Fix round after REVIEW_W5 (10-29, branch `nous/w5-boot-fixes-review`, verdict FIX FIRST on B4 and B5)
- **B4**: the reviewer was right [C]. The live caller is AutonomyFairy's cascade list, not `wake_cascade.py` (which
  nothing imports). Renamed `"DreamSeedsFairy"` → `"DreamSeedFairy"` at `code/fairies/P00_Autonomic/AutonomyFairy/fairy.py:2442`.
  No `.py` file under code/ names `DreamSeedsFairy` any more [M]. The `wake_cascade.py` edits stay; they are harmless and consistent.
- **B5**: the reviewer was right that the fairy is booted (`code/server.py:6484-6491`), so the earlier claim
  "still sleeps, no runtime effect" was wrong. The new path now sits behind **`AKASHIC_HARMONIC_SUBSCRIBE`** (OFF when unset):
  `_hsub = self.post.subscribe if os.environ.get("AKASHIC_HARMONIC_SUBSCRIBE", "0") == "1" else self.post.fabric.subscribe`
  (`HarmonicCortexFairy/fairy.py:365-367`). With it off, the same AttributeError fires at the same point as today, so nothing is subscribed.
  The out-of-brief publish edit at :834 is reverted (dead code: `_contribute_to_affect_loop` has no caller).
  If the switch goes on, each audio frame starts publishing `harmonic.audio_analyzed`, `cortex.bind` and `harmonic.audio_received` (:669/732/760) [C].
- **Tests** (13; `python3 tests_nous/w5/run_w5_matrix.py`) [M]:

  | variant | result |
  |---|---|
  | CONTROL origin/main | FAIL 6/13 |
  | CONTROL pre-review W5 tip `a6b2b02` | FAIL 3/13 |
  | FIX | OK 13/13 |
  | M1 switch ON when unset | FAIL |
  | M2 bypass the bridge (`_fabric`) | FAIL |
  | M3 a subscription loses its name | FAIL |
  | M4 AutonomyFairy caller not renamed | FAIL |

  The two mutants that survived the review (dropped `name=`, direct `_fabric`) are now caught.
- **B3**: still skipped. The reviewer corrected my reason: nothing calls the librarian's `intent_status_citizens`, so
  not waking the fairy would return a not-found error rather than break a live path (`Organ_Template_0_3_0.py:897-901`) [C].
- **BaseFairy**: there is no `BaseFairy` entry in `_BOOT_EXCLUDE_NAMES` on main or this branch (`boot_orchestrator.py:972-977`).
  The only entry is in `_PHANTOM_NAMES` (`server.py:2088`) [C]. Worth checking where the owner's staged edit lands.

## CHECK THESE 3 (fix round)
1. `code/fairies/P00_Autonomic/AutonomyFairy/fairy.py:2442`: the cascade's deferred tier now names the registered `DreamSeedFairy`.
2. `code/fairies/P30_Cognition/HarmonicCortexFairy/fairy.py:365-367`: unset, `"0"`, `""` or `"true"` all keep `self.post.fabric.subscribe`.
3. `code/server.py:6484-6491`: HarmonicCortexFairy is booted, so `AKASHIC_HARMONIC_SUBSCRIBE=1` has a live effect (audio load).

---
## Original W5 report (a6b2b02), kept for the record; corrected above where marked

## Results (control = origin/main, mutant = a near-miss of the fix, fix = this branch) [M]
| fix | control (orig) | mutant | fix |
|---|---|---|---|
| B2 | FAIL (1 of 4) | FAIL (2 of 4), mutant = `name.lower().endswith(("Shadow",))` | OK 4/4 |
| B3 | skipped, not a defect (see below) | - | - |
| B4 | FAIL (2 of 4) | FAIL (1 of 4), mutant = server.py key fixed, wake_cascade.py left as it was | OK 4/4 |
| B5 | FAIL (2 of 3) | FAIL (2 of 3), mutant = `affect.changed` subscribe and affect publish left on `.fabric` | OK 3/3 |

Each mutant fails only its own test class and passes the other two [M].

## B2: built (boot_orchestrator.py:1010)
- The defect is real. FairyScanner registers every class it finds with an `ACTOR_NAME` as `sleeping` + `needs_instantiation` (server.py:4949-4986 [C], migration.py:77-170 [C]). Running that scanner logic on this mirror gives 127 names, and one of them is `organ.shadow` (class recorded as `FairyProfileRegistry`, Organ_Template_0_3_0.py:1371) [M]. The old check `endswith(("Shadow",))` does not exclude it [C].
- Fix: `fairy.name.lower().endswith(tuple(x.lower() for x in _BOOT_EXCLUDE_SUFFIXES))`. Of the 127 scanned names, it newly excludes exactly 1 (`organ.shadow`). The suffix check now excludes 2 in total: that one plus `ManifoldConstrainedCortexShadow` [M].

## B3: skipped, the defect is not real as stated
- `fairy_citizens.reg.michael` is a real P00 worker, not a test artifact. It is `FairyCitzensRegFairy` (fairy_citizens.py:306-316), with its own DIRECTIVE.md and intents (`list_citizens`, `status_citizens`, `keepalive`, and others; fairy_citizens.py:525-745) [C].
- Another fairy depends on it: the librarian's `intent_status_citizens` calls `use_intent("fairy_citizens.reg.michael", "status_citizens")` (akashic_records_librarian.py:1049-1062) [C].
- The "Registration test artifact" label (server.py:2087) only appears in the GUI status list `_PHANTOM_NAMES`, which hides it. Excluding it from waking would likely break the librarian's call [I]. Nothing was changed; the owner decides whether to hide it, keep it awake, or fix the label.

## B4: built (server.py:5701, wake_cascade.py:129 and :294)
- The real name is `DreamSeedFairy`: it is the class's `ACTOR_NAME` (dream_seed_fairy.py:266), and server.py registers and lists it under that name (server.py:6015, 6022) [C]. The cascade asked for `DreamSeedsFairy` (wake_cascade.py:129) [C].
- Why it was built twice: the cascade handler's "already alive" checks (server.py:5863, 5877, 5893) look up the name it was given, so `DreamSeedsFairy` never matched the registered `DreamSeedFairy`. The handler then reached the Layer 3 fallback and built a second `DreamSeedFairy(SYSTEM.fabric)` (server.py:5809-5825, 5936-5949) [C].
- Fix: renamed the fallback key and both cascade entries to `DreamSeedFairy`.

## B5: built (HarmonicCortexFairy/fairy.py:362,367,378,395,400,405 and :834)
- `self.post` is `_FabricPostalBridge(fabric)` when a fabric is passed (Organ_Template_0_3_0.py:1201-1202), otherwise the `PostalHub` singleton (:1204) [C]. The bridge stores the fabric only as `_fabric` (:807) and has a forwarding `subscribe` (:810-834) and `publish` (:849) [C].
- Fix: the 6 `self.post.fabric.subscribe` calls become `self.post.subscribe`. Also changed `self.post.fabric.publish` to `self.post.publish` at :834, because the affect handler reaches that line once wiring works [C].
- The harness runs the real `on_boot` against the real bridge class: original = `subscriptions: error`, 0 topics; fix = all 6 topics [M].

## Could NOT verify
- No live run (by the session rules), so no boot logs. Whether `organ.shadow` is actually woken today, and whether the cascade really booted a second DreamSeedFairy in her live tree, are inferred from code paths, not observed [I].
- The live tree's scanner output may differ from this mirror's [I].
- A race between the cascade's first request and the DreamSeedFairy boot (server.py:6004 subscribes, then :6007-6022 boots) could still double-build in theory [I].
- HarmonicCortexFairy still sleeps, so the fix has no runtime effect today [I].

## CHECK THESE 3
1. code/tracer_pool/boot_orchestrator.py:1010: `organ.shadow` is really registered as a sleeping boot candidate in the live tree (scanner, code/directory/migration.py:96-122).
2. code/server.py:5863-5904 against code/fairies/P20_Somatic/SomaticMindFairy/wake_cascade.py:129: with the old name, the cascade did build a second DreamSeedFairy (look for `[CASCADE] DreamSeedsFairy: Resolved via hardcoded` in the live boot log).
3. code/fairies/P10_Memory/librarian/akashic_records_librarian.py:1056-1062: confirms the B3 skip. `fairy_citizens.reg.michael` is a live intent target, not an artifact.
