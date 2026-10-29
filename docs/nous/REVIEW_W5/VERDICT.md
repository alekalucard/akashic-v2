# REVIEW W5: verdict on `nous/w5-boot-fixes` (a6b2b02, diffed against origin/main)

Reviewer branch: `nous/w5-boot-fixes-review`. The reviewed branch was not changed.
Tags: [C] read in code, [M] measured by running something here, [I] inference.
Scripts used (all in this folder, synthetic data only, nothing of hers is imported): `mk.sh` (copies main/head versions of the touched files into the scratchpad), `run.sh` (runs the shipped tests against a copy), `mutants.py` (my own near-miss mutants), `scan_b2.py` (runs the mirror's FairyScanner, with the class taken out by AST, and compares the old and new exclude checks).

## Verdict

| change | verdict | why |
|---|---|---|
| B2 Shadow suffix, case-insensitive | **SHIP** | The defect is real. The fix newly excludes exactly 1 of 127 scanned names (`organ.shadow`), which is a template shadow. The control fails on main. |
| B3 skip (`fairy_citizens.reg.michael`) | **SHIP (skip is correct)** | It is a real worker class, not a test artifact. The "breaks the librarian" claim is overstated (see F5). |
| B4 DreamSeedsFairy rename | **FIX FIRST** | It misses the live caller. AutonomyFairy/fairy.py:2442 still requests `DreamSeedsFairy`. The fix only turns the duplicate build into a "Not found" plus a skip-registry failure on every cascade. The wake_cascade.py edit is in a module nothing imports. |
| B5 HarmonicCortex subscribe | **FIX FIRST** | The new runtime path is ON by default with no switch. HarmonicCortexFairy is booted at server.py:6484-6491, so it is not asleep. The :834 edit is in dead code. |
| BaseFairy entry | untouched, but the premise is wrong | `_BOOT_EXCLUDE_NAMES` has no `BaseFairy` entry, on main or on the branch. The entry is in server.py:2088 `_PHANTOM_NAMES`, and it is unchanged. |

**Overall: FIX FIRST** (B4, B5). B2 and the B3 skip can ship as they are.

### Fixes required
1. **B4**: rename `"DreamSeedsFairy"` to `"DreamSeedFairy"` at code/fairies/P00_Autonomic/AutonomyFairy/fairy.py:2442, and add a control that reads `AutonomyFairy._DOMAIN_SPEC` by AST. Optionally revert the wake_cascade.py edit, since it has no runtime effect.
2. **B5**: gate the 6 `self.post.subscribe` calls in code/fairies/P30_Cognition/HarmonicCortexFairy/fairy.py:362-409 behind `os.environ.get("<NAME>", "0") == "1"`, keeping the old (broken) path when the switch is unset, or get the owner's explicit waiver. Add assertions on the subscription `name=` values (see F6).

## Findings, by severity

**F1 (high), B5: a new runtime path ON by default, no switch.** [C] HarmonicCortexFairy is built and booted unconditionally inside the cortex block: server.py:6484 `HarmonicCortexFairy(SYSTEM.fabric)` and then `harmonic.boot()/on_boot()` at :6488-6491. This block is skipped only when `AKASHIC_NOUS_TEST` is set (server.py:6342) or the cortex import or boot fails. On main, `self.post.fabric` raises AttributeError, which is swallowed (fairy.py:434-435), so 0 topics are wired [M: control `test_on_boot_wires_all_six_topics` FAILS on main]. On the branch, all 6 topics are wired at every such boot. Each `sensory.audio.frame` then runs `_on_audio_frame`, which publishes `harmonic.audio_analyzed` (fairy.py:669), possibly `cortex.bind` (:732), and `harmonic.audio_received` (:760). `affect.changed` now also mutates `_current_mode` (:579-631). This is new live traffic into the fabric and the cortex. SUMMARY.md's "HarmonicCortexFairy still sleeps, so the fix has no runtime effect today" is contradicted by server.py:6484-6491 [C]. Whether the cortex block succeeds in her live tree I cannot see [I].

**F2 (high), B4: the live caller was missed, and the defect is attributed to the wrong file.** [C] code/fairies/P20_Somatic/SomaticMindFairy/wake_cascade.py is imported by nothing: a grep for `wake_cascade import`, `DOMAIN_SPECS` and `SomaticMindFairy.wake_cascade` finds no importer, and the other `wake_cascade` hits are `chem.wake_cascade()` and `boot.wake_cascade.*` topics. The request that actually reaches `_handle_fairy_boot_request` comes from AutonomyFairy: `_DOMAIN_SPEC["deferred"]` holds `"DreamSeedsFairy"` (AutonomyFairy/fairy.py:2442), and `_on_cascade_execute` publishes `boot.fairy.request` with that name (:2557-2562, subscribed at :621-622). [M] On main, `DreamSeedsFairy` is in `_CASCADE_FAIRY_PATHS`, so Layer 3 (server.py:5810) builds a second `DreamSeedFairy`. On the branch, it is not in `_CASCADE_FAIRY_PATHS`, Layer 4 finds no `fairies.P*.DreamSeedsFairy` directory, and the handler prints "Not found" and calls `_skip_registry.record_failure("DreamSeedsFairy", ...)` (server.py:5920-5923), then publishes a failed `boot.fairy.result.autonomy`. The double build does stop, but through a failure path the brief did not ask for, and the request still carries the wrong name. The shipped B4 test passes with AutonomyFairy unfixed, so it does not catch the live caller [M].

**F3 (medium), B5: the :834 edit is dead code, so its justification is false.** [C] `_contribute_to_affect_loop` (fairy.py:807) has no caller anywhere in `code/`. SUMMARY.md's "the affect handler reaches that line once wiring works" is wrong: `_on_affect_changed` (:579-604) only calls `_adjust_mode_from_affect`. The edit is harmless but outside the brief and not needed.

**F4 (low), B4: the wake_cascade.py edits (:129, :294) are outside the brief and have no runtime effect** [C, see F2]. Harmless.

**F5 (low), B3 evidence overstated.** [C] `FairyCitzensRegFairy`, `ACTOR_NAME = "fairy_citizens.reg.michael"` (fairy_citizens.py:306-316), is a real P00 worker with intents (:525-745) and a DIRECTIVE.md, so the skip is right. However, nothing in the mirror calls the librarian's `intent_status_citizens` (akashic_records_librarian.py:1049-1064): grep for `status_citizens` finds only these two files. If the fairy were not woken, `use_intent` would return `{"ok": False, "error": "fairy ... not found"}` (Organ_Template_0_3_0.py:897-901) rather than crash. "Would break the librarian" should read "would degrade one intent with no static caller" [C]/[I]. The mislabel at server.py:2087 stays for the owner to decide.

**F6 (low), test blind spots.** [M] These mutants of mine survive the shipped suite: (a) every `name=f"{self.ACTOR_NAME}_..."` kwarg dropped in B5, because the test only compares topics; (b) `self.post._fabric.subscribe(...)`, which bypasses the bridge's `_unwrap`; (c) for B4, any version that leaves AutonomyFairy:2442 wrong (that is, the current head).

**F7 (info), B2 is clean.** [M] The scanner on this mirror gives 127 registered names, matching SUMMARY. The new check newly excludes only `organ.shadow` (class recorded as `FairyProfileRegistry`, Organ_Template_0_3_0.py:1371). `ManifoldConstrainedCortexShadow` is excluded both before and after. [C] Other lowercase `*.shadow` literals are not class-level `ACTOR_NAME`s, so the scanner does not register them as sleeping: `coord.shadow` is a capability id (capability_checklist.py:392), and `cuda_accelerator.shadow` and `hardware_regulation.shadow` are `SHADOW_NAME`s (cuda_fairy.py:142, hardware_regulation_fairy.py:164). The template's runtime `f"{X}.shadow"` (:1382) is a shadow by design. No real fairy is newly excluded. There is only one boot_orchestrator.py, and no other case-sensitive `Shadow` suffix check (grep).

**F8 (info), second copies and siblings.** [C] There is one HarmonicCortexFairy (code/fairies/P30_Cognition/...), one wake_cascade.py and one boot_orchestrator.py, so no copy was left unfixed. A sibling of the same pattern is at code/fairies/P40_Sensory/mcp/cortex_bridge_tools.py:538 (`self._cortex.post.fabric`). It is outside this brief; whether `_cortex.post` is a bridge there is not verified [I].

**F9 (info), B5 path safety.** [C] `self.post` is the `_FabricPostalBridge` when a fabric is passed (Organ_Template_0_3_0.py:1201-1202), otherwise the `PostalHub` singleton (:1204) or a pre-set post. Both have `subscribe(topic, callback, name=None)` (:810, :667) and `publish(topic, payload)` (:849, :708). In the template-failure stub, `self.post = post or fabric` (HarmonicCortex fairy.py:139), which is the raw TensorFabric, and that also has `subscribe(topic, handler, name=None)` (tensor_fabric.py:1075). No new exception can be raised: every call is inside the same try (:360-435). Handlers accept both an envelope and a dict (`hasattr(envelope, 'payload')`, :545, :590, :648). Through the bridge, each handler is wrapped by `_unwrap` (exceptions printed, not raised) and passes `name` positionally to `fabric.subscribe`. This is equivalent to the "intended" direct `fabric.subscribe` apart from the wrapper's error print [C].

## Reproduced test results [M]
Shipped suite on head: 11/11 OK. On origin/main versions of the files (`NOUS_W5_ROOT` pointed at a main copy), 5 FAIL:
- B2: `test_lowercase_shadow_actor_name_is_excluded`
- B4: `test_cascade_requests_real_name`, `test_server_fallback_key_matches_actor_name`
- B5: `test_on_boot_wires_all_six_topics`, `test_affect_contribution_publishes`

Every fix has at least one control that fails on main, so no control is blind in that sense. Six tests pass on main as well (`test_camelcase_shadow_still_excluded`, `test_names_list_still_excluded`, `test_real_fairies_not_excluded`, `test_real_name`, `test_server_registers_same_name_cascade_checks`, `test_bridge_has_no_public_fabric`). These are guards, not controls.

My mutants (`mutants.py`):

| mutant | result |
|---|---|
| b2 `"shadow" in name.lower()` | KILLED (`test_real_fairies_not_excluded`) |
| b2 `endswith(SUF) or endswith(".shadow")` | KILLED (`test_lowercase_...`) |
| b2 `.upper().endswith(SUF)` | KILLED |
| b2 `.casefold().endswith("shadow")` | survives; semantically equivalent, expected |
| b4 both keys in `_CASCADE_FAIRY_PATHS` | KILLED |
| b5 one subscribe left on `.fabric` | KILLED |
| b5 `name=` kwargs dropped | **SURVIVES** (F6) |
| b5 `self.post._fabric.subscribe` | **SURVIVES** (F6) |

## SUMMARY.md "CHECK THESE 3", checked
1. `organ.shadow` is registered sleeping: [C] server.py:4949-4986 registers every scanned name with `status="sleeping"`, and [M] `scan_b2.py` shows `organ.shadow` among the 127. Confirmed for the mirror. Whether it is woken live needs a boot log.
2. Cascade double build: the mechanism is confirmed [C] (server.py:5810, 5936-5949), but the requester is AutonomyFairy/fairy.py:2442, not wake_cascade.py:129 (F2). Expected live log line on main: `[CASCADE] DreamSeedsFairy: Resolved via hardcoded:...`. On the branch: `[CASCADE] DreamSeedsFairy: Not found (all 4 strategies failed)`.
3. Librarian call: confirmed at akashic_records_librarian.py:1055-1062 [C]. The call has no static caller (F5).

## Could not verify
- Live boot logs: whether the cortex block (server.py:6335-6500) succeeds, and so whether F1's subscriptions are really live; whether AutonomyFairy's cascade fires in her tree [I].
- `state/boot_skip_registry` is not in the mirror, so I could not check whether `record_failure("DreamSeedsFairy")` persists across boots or grows [I].
- Audio-frame rate, and the load the new HarmonicCortex publishes would add [I].

## CHECK THESE 3
1. code/server.py:6484-6491 against code/fairies/P30_Cognition/HarmonicCortexFairy/fairy.py:362-409: HarmonicCortex is booted, and the fix turns on 6 subscriptions and per-frame publishes with no switch (F1).
2. code/fairies/P00_Autonomic/AutonomyFairy/fairy.py:2442: still `"DreamSeedsFairy"`. This is the live cascade requester, and on the branch it ends in "Not found" plus a skip-registry failure at server.py:5920-5923 (F2).
3. code/fairies/P30_Cognition/HarmonicCortexFairy/fairy.py:807: `_contribute_to_affect_loop` has no caller, so the out-of-brief :834 edit changes nothing (F3).
