# W3 SUMMARY: dead-letter triage

Tags: [C] read in code, [M] measured here, [I] inference. Nothing under code/ was changed, imported or run;
so there is **no switch** (the switch rule applies to code/ only). All changes are in tools/ and docs/.

## 1. VERIFY (seed 1029, 30 A rows + 30 B rows, checked by hand with grep and reading)

Error rate of the base-branch tool: **A 5/30 (17%), B 11/30 (37%), all 16/60 (27%)** [M]. Above 10%, so the tool was fixed.

Wrong A rows (a subscriber exists):
* `somatic.weather`, `council.peer_review`, `habit.responded`: subscribed in code/fairies/P30_Cognition/cognition/working_memory_hub_fairy.py:1995/:2055/:2010, a file the tool excluded as "shadowed" [C].
* `directory.lookup`: base catch-all `self.post.receive("directory", ...)` at code/fairy_template/consolidated.py:3527 [C].
* `cns.submit_work`: `self.post.receive("cns.submit_work", ...)` at code/fairies/P00_Autonomic/nervous_system/central_nervous_postal_fairy.py:660 [C].

Wrong B rows (a publisher exists):
* via `.route(`: `srm.ingest.packet` (memory_flow_tracer.py:178), `claudefairy.nudge` (interest_scheduler_fairy.py:1443), `claudefairy.tool_result` (code/postal_core/mcp.py:437), `motor.response` (motor_cortex_fairy.py:1468), `claudefairy.input` (code/postal_core/mcp.py:3505), `sensory.visual.observation` (akashic_mcp_server.py:813 with `modality="visual"` at :2001; my first hand check missed it, and the fixed tool found it) [C].
* in the "shadowed" copies: `working_memory.tracer_promoted` (working_memory_hub_fairy.py:7944), `working_memory.tracer_added` (:7738 route), `autonomy.drive_state` (code/fairies/P30_Cognition/cognition/autonomy_fairy.py:873 route), `skill.level_up` (skill_system.py:1325 through the wrapper `_emit_skill_event`), `cognition.unconscious.task` (autonomy_fairy.py:3241 dict value, routed at :3277) [C].

Causes and fixes in tools/dead_letters.py:
1. `.route(` / `.receive(` / `.request(` were not scanned. They are aliases of publish/subscribe/publish: code/P00_Autonomic/nervous_system/shared_postal_hub.py:257-267 and code/postal_core/python/postal_core/tensor_fabric.py:1332-1345, 1411-1460 [C]. 685 such sites are now counted [M].
2. Wrong shadow rule: a code/fairies/P*/X copy is loaded whenever it is imported as `fairies.X`, which most callers do. The "winner" code/P30_Cognition/cognition/working_memory_hub_fairy.py:27 is just a re-export of the copy, and code/P30_Cognition/cognition/autonomy_fairy.py is a 23-line stub [C]. New rule: a copy is excluded only if no non-test file imports it by its `fairies.` name. Result: 40 of 41 copies are now live and 1 is still excluded [M].
3. Wrappers: a def whose topic parameter reaches publish/subscribe now turns its callers into sites (same module, imported name, or self-method on the class or a same-named base, up to 3 levels). This adds 81 sites [M].

**New counts: A = 293 (was 202), B = 353 (was 448), C = 231 (was 161)** [M]. A rose because about 570 `.route` publishes now count as letters. Ablation, with each fix off in turn [M]: without the aliases A=215/B=464, without the twin rule 292/346, without wrappers 275/359.
Re-check: on the same 60 rows the fixed tool is still wrong on 3/60 (5%) [M]. `cognition.unconscious.task` is still in B because its topic is a dict value. `fairy.idle` and `fairy.reflection` left B only because an f-string `fairy.{x}.pong` counts as "maybe". A fresh sample (seed 1030, 15 A + 15 B) gave 0/30 wrong [M, by hand].

## 2-4. PAIRS and CLASSES (docs/nous/W3/TRIAGE.md)

* **24 pairs confirmed by reading both ends**: 18 high, 4 medium, 2 low, plus 8 candidates read and rejected [C].
  * 2 misspellings with a live ear: `goal_scheduler.inject` should be `goal.scheduler.inject` (nous_trainer.py:118), and `skill.levelup` should be `skill.level_up` (profile.py:117).
  * 19 rows come from **literal-wildcard ears** (`umf.signal.*`, `blueprint.*`, `tracer.*`, `shadow.*`, `sensory.window.*`, `diary.*`). No router expands `*` (topic_bus.rs:86-91). The fix is one line per ear: subscribe the prefix. `tracer.*` alone strands all 135 `.to_TRACER(` calls in 30 files [M grep].
* Classes by rule [I]. A (269 after pairs): a=39 planned ear, b=78 telemetry, c=19 dead source, d=133 unclear. B (345 after pairs): a=35, b=46, c=12, d=158, e=78 intent-table handlers, w=16 literal wildcards.
* Tools: tools/dead_letter_pairs.py (candidates), tools/dead_letter_triage.py (writes TRIAGE.md).

## Tests (tools/tests/, synthetic tree in a temp dir) [M]

`python3 tools/tests/run_control_and_mutants.py`:
* FIXED: 7/7 pass.
* CONTROL (base-branch tool from `git show`): FAIL (4 failures).
* Mutants, all FAIL: M1 no receive alias (1 failure), M2 reached twins not scanned (1), M3 method arg index not shifted (2), M4 twin rule also counts bare imports (1).

## Could NOT verify

* Which copy really runs at boot. Static imports only: no runtime, no logs, no FairyScanner registry.
* Whether `fairy.py` files are all booted. I assumed they are, per the plane scan at code/server.py:5676-5680.
* Topics built at runtime (C = 231 sites).
* Delivery through other buses: AKP websocket and sqlite channel.
* The class rules for section 2/3 of TRIAGE.md were not hand-checked row by row. Only the top rows and samples were.

## CHECK THESE 3

1. `.route`/`.receive` are plain aliases of publish/subscribe on the objects fairies hold as `self.post`: code/P00_Autonomic/nervous_system/shared_postal_hub.py:257-267 and code/postal_core/python/postal_core/tensor_fabric.py:1332-1345.
2. The code/fairies/ WMH copy is the one that runs, so its subscriptions count: code/P30_Cognition/cognition/working_memory_hub_fairy.py:27 re-exports `fairies.P30_Cognition.cognition.working_memory_hub_fairy`, and code/fairies/P30_Cognition/cognition/working_memory_boot_patch.py:24 boots the `fairies.` copy.
3. Literal `tracer.*` means the `tracer` stream reaches nobody: code/fairies/P10_Memory/ForensicScribeFairy/fairy.py:192 against code/postal_core/python/postal_core/tensor_fabric.py:1367-1368. Also check that no unresolved (section C) subscriber takes `tracer`.
