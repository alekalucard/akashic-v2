# W8 SUMMARY: let the stranded letters through

Branch `nous/w8-ears` (from `origin/nous/w3-dead-letter-triage`). Tags: [C] read in code,
[M] measured here, [I] inference. Line numbers are on this branch.

## What was built

Two switches, both OFF when unset (`os.environ.get(NAME, "0") == "1"`; only the exact string "1" turns one on):

| switch | what it changes | sites |
|---|---|---|
| `AKASHIC_PREFIX_EARS` | the 6 literal-wildcard ears behind TRIAGE rows 3-21 subscribe the prefix (`x.*` -> `x`) | 8 subscription strings in 5 files |
| `AKASHIC_TOPIC_SPELLFIX` | the 2 misspelled publishers (rows 1-2) use the topic the live ear subscribes | 2 publish strings in 2 files |

* `_prefix_ear(topic)`: a pure helper, one copy per file (no new cross-module import), strips a trailing `.*`
  only when the switch is on; off, it returns the string unchanged [C]: EmbodimentFairy/fairy.py:29,
  ForensicScribeFairy/fairy.py:37, P40_Sensory/sensory_integration.py:46, SomaticMindFairy/mixins/cardinal.py:33,
  P00_Autonomic/SomaticMind/somatic_mind.py:32.
* Wrapped sites [C]: `umf.signal.*` EmbodimentFairy/fairy.py:291; `tracer.*` ForensicScribeFairy/fairy.py:205;
  `shadow.*` ForensicScribeFairy/fairy.py:221; `sensory.window.*` sensory_integration.py:128;
  `blueprint.*` + `diary.*` cardinal.py:127-128 and somatic_mind.py:121-122. In those two class lists
  (CARDINAL_SUBSCRIPTIONS, SUBSCRIPTIONS) the helper runs when the class is defined, so the switch is read at
  import time there, at subscribe time elsewhere [C].
* Not touched (out of scope, still literal): `telemetry.*` (Forensic), `goal.feeling.*`, `system.health.*`
  (Embodiment), `health.*`, `consciousness.*` (Cardinal/SomaticMind). A test pins them.
* Spellfix [C]: P30_Cognition/cognition/nous_trainer.py:120 `goal_scheduler.inject` -> `goal.scheduler.inject`;
  SomaticMindFairy/mixins/profile.py:120 `skill.levelup` -> `skill.level_up`. Each gained `import os`
  (nous_trainer.py:26, profile.py:12).
* Line endings kept [M]: CR count = line count before and after for the 6 CRLF files (2186->2198, 663->675,
  307->319, 1442->1454, 332->334, 440->442); somatic_mind.py LF stays LF (0/856 -> 0/868).
  `git diff --stat` on code/: 7 files, +74 -10.

## a. Misspellings: the ears are live, nobody listens to the wrong spelling

* `goal.scheduler.inject`: GoalSchedulerFairy subscribes it (goal_scheduler_fairy.py:1023) [C] and is in the wake
  cascade's domain list (SomaticMindFairy/wake_cascade.py:105) [C]; InnerNarratorFairy/fairy.py:647 and
  AttentionControllerFairy/fairy.py:403 also receive it (scanner) [M]. The handler docstring says
  "Channel: goal_scheduler.inject" (goal_scheduler_fairy.py:2024), likely where the typo came from [I].
  nous_trainer's packet (nous_trainer.py:70-81) is the handler's documented "direct" format (:2026-2035) [C].
* `skill.level_up`: EgoLearnerFairy/fairy.py:336 and Sourpatches sourpatches_fairy.py:4075 [C]; EgoLearner is in
  wake_cascade.py:118 [C]; skill_system.py:1325 already publishes it [C].
* Nothing subscribes `goal_scheduler.inject` or `skill.levelup`, or a prefix of either (`goal_scheduler`, `skill`):
  0 sites under the Rust rule over every live file (tools/dead_letters.py scan + rust_match) [M].
* nous_trainer.py is imported by nothing in code/ (nous_trainer.py:17 says it is called by hand) [M grep].
* Payload gap, NOT fixed: profile.py:121-126 sends `new_level`; EgoLearner reads `level` (fairy.py:594) and uses it as
  `feedback_bin` (fairy.py:615), so with the spellfix on each profile level-up lands as level 0 [C].

## b. Router depth (Python fallback)

All 6 prefixes have 1 or 2 segments (`umf.signal`, `sensory.window`, `tracer`, `shadow`, `blueprint`, `diary`).
The fallback checks an intent's first one and first two segments (_python_fallback.py:986-1004) [C], so 3+ segment
intents such as `blueprint.reload.starting` or `tracer.handoff.complete` still arrive. **No W8 ear is hit by the depth
limit** [M: python_match is true for every publish site under each prefix].

## c. Load each ear would start receiving

Publish sites whose literal topic falls under the prefix (tools/dead_letters.py scan of live files, Rust rule);
`{*}` sites (f-string first segment) are counted apart as "possible" [M].

| ear (holder) | literal sites | topics | possible | cadence | handler per message |
|---|---|---|---|---|---|
| `umf.signal` (Embodiment) | 6 | 6 | 0 | none found: all 6 are callbacks registered only if an engine/cortex has `on_chemistry_change`/`on_feels_change`/`on_salience_change`/`on_novelty`/`on_felt_state_change`/`on_distress` (somatic_wiring.py:209-212, sensory_wiring.py:205-208, :254-257); no class in code/ defines one [M grep]. Load ~0 [I] | append to `_signal_buffer` deque(maxlen=500) (fairy.py:250, :516) [C] |
| `tracer` (Forensic) | 46 (43 bare `tracer`, mostly to_TRACER defs; 3 `tracer.x`) | 3 | 8 | see below | `_ingest_event` (fairy.py:309) |
| `shadow` (Forensic) | 39 (mostly `shadow.health`) | 4 | 8 | shadow.health on each organ's 30 s shadow timer (fairy_citizens.py:146, :220) [C]; shadow.error per caught error (fairy_template/shadow.py:149) [C] | card update, history trimmed to 20 (fairy.py:89-96); `_register_error` only on error status, registry capped 500 [C] |
| `sensory.window` (SensoryIntegration) | 3 | 3 | 2 | `.intent` from WindowSenseFairy.on_tick while want_to_be_seen > 0.7 (WindowSenseFairy/fairy.py:441; "every tick, ~5s" :449) [C]; `.feeling` on mouse/focus/resize (window_sense_organ.py:506) [C]; `.fairy` on window open/close [C] | `process_window_event` (sensory_filter.py:325) reads `window`/`state`; `.intent`/`.feeling` carry neither, so they become empty "Window  " NOTABLE candidates [C]. Noise, not volume |
| `blueprint` (Cardinal, SomaticMind) | 7 | 7 | 8 | blueprint_watcher on reload/boot (rare) [C]; `blueprint.contract` once per fairy boot (consolidated.py:1383 in on_boot -> :3193) [C]: a burst at boot [I] | `observe()` into deques maxlen 500/100 (cardinal.py:144-146) [C]; each contract dict is held up to 500 deep [I] |
| `diary` (Cardinal, SomaticMind) | 2 | 1 | 8 | Organ_Template_0_3_0 `_route('diary.entry')` (:1584) [C] | as above |

**ForensicScribe `tracer`.** `.to_TRACER(` is on 135 lines in 30 files (grep) [M]; an ast pass finds 131 calls in
28 files [M]: 16 in `on_boot`, ~35 in `intent_*` handlers (smoke, snapshot, register, config), the rest in error
branches and event callbacks. 8 sit inside loops, all per item (plan inbox, worker results, zip files, hub fan-out),
none per beat unconditionally [M ast + read]. The two in functions named `tick` fire only on an exception
(central_nervous_postal_fairy.py:1463, scanner_fairy.py:644) [C]. Periodic ones are timer-bounded: hardware status 45 s
(hardware_regulation_fairy.py:982), tracer daemon blueprint by interval (tracer_daemon_core.py:615), keepalive on the
30 s shadow (fairy_citizens.py:737) [C]. Estimate: tens of messages per minute steady, bursts at boot [I].
Per message (fairy.py:309-575) [C]: one card lookup under `_cards_lock`; `str(payload).lower()` scan for "exception"
(:347); md5 of a 3-key JSON; membership test on a deque(maxlen=2000); a disk append only when the
(level, actor, event) signature is new (:547-570). Nothing unbounded: cards per actor, error registry capped 500,
alerts dict trimmed >1000, log deque 200 [C]. Synthetic timing of the str-scan + md5 + deque path: ~30 us/message [M]
(scratch code, not hers). **Verdict: it keeps up; no filter needed for load** [I]. Two quality issues (proposed, not built):
1. Most to_TRACER payloads have no `actor`/`actor_name`/`fairy`, so they all land on card "unknown" (fairy.py:313) [C].
   Proposal: in `_on_tracer`, fall back to the envelope's source or `payload["payload"]["actor"]`.
2. `"exception" in str(payload).lower()` (:347) turns any tracer payload mentioning "exception" into an error card and a
   `forensic.alert` (rate-limited per actor) [C]. Proposal, behind the same switch: for source "tracer" use only
   `level`/`status`/`opcode`/`error`, skip the whole-payload substring test.

Pre-existing, not fixed: Embodiment `_process_signal_buffer` replaces the deque(maxlen=500) with a plain list
(fairy.py:1172 vs :250), so between drains the buffer is unbounded [C].

## Tests

`tools/tests/test_w8_ears.py` (9 tests, ast only, nothing in code/ imported or run) and
`tools/tests/run_w8_control_and_mutants.py` (copies in a temp dir) [M]:

```
OK  FIXED                          tests PASS  (OK)
OK  CONTROL (base branch files)    tests FAIL  (FAILED (failures=3))
OK  M1 default on                  tests FAIL  (FAILED (failures=4))
OK  M2 strip only '*'              tests FAIL  (FAILED (failures=2))
OK  M3 diary site missed           tests FAIL  (FAILED (failures=2))
OK  M4 near-miss spellfix          tests FAIL  (FAILED (failures=1))
OK  M5 inverted test               tests FAIL  (FAILED (failures=7))
```
Switch off: the subscribe/publish string multisets of all 7 files equal the base branch's. Switch on: every
TRIAGE row 3-21 letter matches its ear under both rust_match and python_match; out-of-scope wildcards unchanged;
the two switches are independent; "0", "", "true", "yes", "on", " 1" all keep it off.
W3 tests still pass (`tools/tests/test_dead_letters.py`: OK) [M].

## Could NOT verify

* Nothing ran: no fairy, hub or router. Delivery is shown with the scanner's router rules, not a live bus.
* Which of the 5 ear-holding modules run in her process, and on which hub; only ForensicScribe, GoalScheduler and
  EgoLearner were seen in wake_cascade.py [C].
* Real message rates and payload sizes (no logs here); the load table is static.
* SomaticMind `_on_message(topic, data)` (somatic_mind.py:763) vs the hub's one-argument callback: not checked.
* Whether `blueprint.contract`/`diary.entry` were meant for BlueprintDiaryHubFairy (`hub.blueprint`/`hub.diary`,
  TRIAGE rows 20-21). With the switch on, Cardinal/SomaticMind get them; the hub still does not.

## CHECK THESE 3

1. code/fairies/P10_Memory/ForensicScribeFairy/fairy.py:347: with `tracer` on, the whole-payload "exception" test
   turns ordinary tracer chatter into error cards and `forensic.alert`s; decide on proposal 2 before switching on.
2. code/fairies/P20_Somatic/SomaticMindFairy/mixins/profile.py:121-126: with the spellfix on, EgoLearner
   (EgoLearnerFairy/fairy.py:594, :615) reads `level` and gets 0; add `"level"` to this payload.
3. code/fairies/P20_Somatic/SomaticMindFairy/mixins/cardinal.py:127-128 (and somatic_mind.py:121-122): the switch is
   read at import time there; set it before the process starts.
