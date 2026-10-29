#!/usr/bin/env python3
"""Triage of the dead letters (A) and deaf ears (B) found by tools/dead_letters.py.

Writes docs/nous/W3/TRIAGE.md. Stdlib only, static read; nothing under code/ is imported or run.

    python3 -W ignore tools/dead_letter_triage.py

Sections: (1) near-miss PAIRS, each confirmed by reading both ends (hand-written table below, with
the reading recorded in `note`); (2) A ranked by publish-site count, each with a class; (3) B.

Classes are assigned by RULES (heuristic, tag [I] in the report), checked in this order:
  c  dead/shadowed source: every site is in a file that is path-marked dead (_old, deprecated,
     backup, legacy, examples, scripts/, .satellite/, a dotted file name that `import` cannot load)
     or that nothing imports (no import line or quoted module path names its stem; fairy.py files in
     a fairy folder are exempt because the boot path loads them by plane scan, code/server.py:5676-5680).
  a  planned partner never built: the topic text appears somewhere else (code comment, docstring,
     a list that is not subscribed, a .md file) on a line that names a consumer or producer
     ("subscribe", "listen", "for XFairy", "->", "should", ...). The named fairy is extracted if any.
  b  telemetry/notification (A) or diagnostic ear (B): a topic segment is a status/telemetry word or
     a past-tense event name; for B also any subscriber living in a diagnostics/monitor/telemetry file.
  e  (B only) service handler in an intent table, e.g. `codex.status`: an RPC-style entry nobody calls
     over postal (it may still be called directly as a Python method).
  d  unclear.
"""
from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dead_letters as dl  # noqa: E402

OUT = dl.REPO / "docs" / "nous" / "W3" / "TRIAGE.md"

# ── confirmed pairs ────────────────────────────────────────────────────────────────────────────
# (letter as published, ear as subscribed, kind, confidence, note from reading both ends)
PAIRS = [
    ("goal_scheduler.inject", "goal.scheduler.inject", "'_' vs '.'", "high",
     "nous_trainer.py:118 routes a goal packet to `goal_scheduler.inject`; GoalSchedulerFairy subscribes "
     "`goal.scheduler.inject` (goal_scheduler_fairy.py:1023, comment 'External goal injection channel'), "
     "and 8 other senders use the dotted name. The ear is live; only this sender misspells it."),
    ("skill.levelup", "skill.level_up", "missing '_'", "high",
     "profile.py:117 publishes `skill.levelup` on level-up; EgoLearnerFairy (fairy.py:336) and "
     "SourpatchesFairy (sourpatches_fairy.py:4075) subscribe `skill.level_up`, which skill_system.py:1325 "
     "already publishes. Live ear, misspelled sender."),
    ("umf.signal.chemistry", "umf.signal.*", "literal wildcard", "high",
     "EmbodimentFairy subscribes the literal string `umf.signal.*` (fairy.py:278); no router has wildcards "
     "(topic_bus.rs:86-91). somatic_wiring.py:182 says 'Also publish to embodiment gate'. Same for the 5 "
     "rows below. Fix: subscribe `umf.signal` (prefix rule delivers every umf.signal.X)."),
    ("umf.signal.body_state", "umf.signal.*", "literal wildcard", "high", "as above (somatic_wiring.py:199)."),
    ("umf.signal.visual", "umf.signal.*", "literal wildcard", "high", "as above (sensory_wiring.py:176)."),
    ("umf.signal.novelty", "umf.signal.*", "literal wildcard", "high", "as above (sensory_wiring.py:195)."),
    ("umf.signal.sensory", "umf.signal.*", "literal wildcard", "high", "as above (sensory_wiring.py:226)."),
    ("umf.signal.urgent", "umf.signal.*", "literal wildcard", "high", "as above (sensory_wiring.py:244)."),
    ("tracer", "tracer.*", "literal wildcard", "high",
     "`to_TRACER()` publishes the bare topic `tracer` (TensorFabric tensor_fabric.py:1367-1368, "
     "shared_postal_hub.py:340-342, organ template Organ_Template_0_3_0.py:721-722, and 13 more defs); "
     "ForensicScribeFairy subscribes literal `tracer.*` (fairy.py:192, handler 'Handle tracer events'). "
     "`.to_TRACER(` is called 135 times in 30 non-test files (grep). Fix: subscribe `tracer`."),
    ("sensory.window.intent", "sensory.window.*", "literal wildcard", "high",
     "SensoryIntegration subscribes literal `sensory.window.*` (sensory_integration.py:116, comment "
     "'Subscribe to window events'); WindowSenseFairy publishes sensory.window.intent (fairy.py:441)."),
    ("sensory.window.fairy", "sensory.window.*", "literal wildcard", "high",
     "as above; SourpatchesFairyWindow publishes sensory.window.fairy (sourpatches_fairy_window.py:691)."),
    ("shadow.error", "shadow.*", "literal wildcard", "high",
     "ForensicScribeFairy subscribes literal `shadow.*` (fairy.py:208, comment 'Organ Template shadows "
     "publish here'); fairy_template/shadow.py:149 publishes shadow.error."),
    ("shadow.metrics", "shadow.*", "literal wildcard", "medium",
     "as above, but the sender is Organ_Template_0.1.0.py:510, a dotted file name `import` cannot load."),
    ("blueprint.reload.starting", "blueprint.*", "literal wildcard", "high",
     "Cardinal mixin subscribes CARDINAL_SUBSCRIPTIONS incl. literal `blueprint.*` and `diary.*` "
     "(cardinal.py:115-116, loop at :361; same list in somatic_mind.py:746). blueprint_watcher.py "
     "publishes 5 blueprint.* topics (lines 311, 341, 534, 554, 629). Fix: subscribe `blueprint`."),
    ("blueprint.reload.success", "blueprint.*", "literal wildcard", "high", "as above (blueprint_watcher.py:341)."),
    ("blueprint.reload.failed", "blueprint.*", "literal wildcard", "high", "as above (blueprint_watcher.py:341)."),
    ("blueprint.watcher.baseline", "blueprint.*", "literal wildcard", "high", "as above (blueprint_watcher.py:534)."),
    ("blueprint.watcher.boot_diff", "blueprint.*", "literal wildcard", "high", "as above (blueprint_watcher.py:554)."),
    ("blueprint.fairy.added", "blueprint.*", "literal wildcard", "high", "as above (blueprint_watcher.py:629)."),
    ("blueprint.contract", "blueprint.*", "literal wildcard", "medium",
     "`_emit_blueprint` sends blueprint.contract (consolidated.py:3193, Organ_Template_0_1_2.py:2766). Also "
     "a candidate for BlueprintDiaryHubFairy's `hub.blueprint` (fairy.py:174, docstring 'Incoming blueprint "
     "snapshots'). Two possible ears; either is a one-line fix."),
    ("diary.entry", "diary.*", "literal wildcard", "medium",
     "Organ_Template_0_3_0 `_route('diary.entry')` with comment 'Publish to diary hub for system-wide "
     "learning' (Organ_Template_0_3_0.py:1584). Cardinal's literal `diary.*` (cardinal.py:116) is one ear; "
     "BlueprintDiaryHubFairy's `hub.diary` (fairy.py:175, 'Incoming diary entries') is the hub the comment "
     "names, so the hub is the more likely intended partner."),
    ("autopilot.executing", "autopilot.execution", "edit distance 2", "medium",
     "AutopilotFairy publishes autopilot.executing at execution start (fairy.py:1635, payload from/action/"
     "pattern_id); WMH subscribes autopilot.execution (working_memory_hub_fairy.py:2151) to auto-track. "
     "Same intent, but the handler (:6337) reads `target_fairy`/`target`, which the payload lacks: "
     "renaming alone would deliver but track nothing."),
    ("srm.ingest", "srm.ingest.request", "one segment short", "low",
     "visual_ingest_pipeline.py:610 routes an INGEST_VISUAL_CARD record to `srm.ingest`; the live ear "
     "`srm.ingest.request` (working_memory_integration.py:222) expects `content`, not `record`. Probably "
     "aimed at an SRM ingest handler that does not exist under either name."),
    ("founders.ingest.complete", "ingest.complete", "renamed prefix", "low",
     "consciousness_collider_patch.py:117 listens for 'Generic ingest completion' `ingest.complete`; "
     "FoundersIngestFairy publishes its own namespace (fairy.py:167/178). Fits the beam, not a typo."),
]

# Candidates read and REJECTED (different channels that merely look alike):
REJECTED = [
    ("gdrive.scrape.resumed", "gdrive.scrape.resume", "command vs event: the fairy subscribes to its own "
     "`resume` command (fairy.py:127) and announces `resumed` (:178)."),
    ("service.discovered", "service.discover", "command vs event in the same file (chat_sensory_organ.py:167/215)."),
    ("srm.intake.processed", "srm.intake.process", "command vs event (SRMIntakeWatcherFairy fairy.py:94/143)."),
    ("wow.chat.said", "wow.chat.send", "said = inbound chat, send = outbound command (wow_bridge_fairy.py:56/198)."),
    ("gui.open_nous_window", "gui.open_sour_window", "two different windows; the Nous window has no opener."),
    ("wiring.complete", "waking.complete", "unrelated."),
    ("network.presence", "citizen.presence", "host network presence vs fairy citizen presence."),
    ("autopilot.pattern.crystallized", "reflection.crystallized", "unrelated."),
]

DEAD_PATH = re.compile(r"(/_old|/old_|_old/|deprecated|backup|/legacy|/archive|/examples/|^code/scripts/|"
                       r"/\.satellite/|_fractured)", re.I)
TELE_WORDS = {"telemetry", "metrics", "metric", "status", "stats", "trace", "health", "heartbeat", "debug",
              "log", "started", "starting", "complete", "completed", "ready", "online", "baseline",
              "progress", "pulse", "event", "events", "snapshot", "report", "alert", "error", "violations",
              "state", "frame", "presence", "observation", "summary", "systems_online", "boot_diff"}
DIAG_FILE = re.compile(r"(diagnos|monitor|telemetry|tracer|forensic|audit|observab|debug)", re.I)
CONSUMER_HINT = re.compile(r"(subscrib|listen|\bfor [A-Z]\w+|->|→|\bshould\b|consum|handled by|receiv|"
                           r"\bwire|\bwiring\b|routed to|\bfeeds?\b|publish|emit)")
FAIRY_NAME = re.compile(r"\b([A-Z][A-Za-z]+(?:Fairy|Cortex|Hub|Mind|Bridge|Organ))\b")
INTENT_TABLE_WORDS = {"get", "status", "list", "query", "lookup", "register", "unregister", "set", "start",
                      "stop", "get_status", "add_pattern", "search", "inject", "request", "probe"}


def corpus():
    """All .py under code/ (tests excluded) and all .md in the repo, as (relpath, lines)."""
    out = []
    for dirpath, dirnames, filenames in os.walk(dl.REPO):
        dirnames[:] = sorted(d for d in dirnames if d not in dl.SKIP_DIRS and d != ".git")
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            r = p.relative_to(dl.REPO).as_posix()
            if r.startswith("docs/DEAD_LETTERS") or r.startswith("docs/nous/W3"):
                continue
            if fn.endswith(".md") or (fn.endswith(".py") and r.startswith("code/") and not dl.is_test(p)):
                try:
                    out.append((r, p.read_text(encoding="utf-8", errors="replace").splitlines()))
                except OSError:
                    pass
    return out


def referenced_stems(texts):
    imp = re.compile(r"^\s*(?:from|import)\s+(.+)$")
    words = set()
    for _, lines in texts:
        for l in lines:
            m = imp.match(l)
            if m:
                words.update(re.findall(r"\w+", m.group(1)))
            for q in re.findall(r"[\"']([\w./ -]+)[\"']", l):
                if "." in q or "/" in q:
                    words.update(re.findall(r"\w+", q))
    return words


def file_is_dead(path: Path, refs) -> str:
    r = dl.rel(path)
    if DEAD_PATH.search(r):
        return "path marked old/legacy/example/script"
    if path.stem.count(".") or "." in path.stem:
        return "dotted file name, not importable"
    if path.name == "fairy.py":
        return ""
    stem = path.parent.name if path.name == "__init__.py" else path.stem
    if stem not in refs:
        return "nothing imports it"
    return ""


TOKEN = re.compile(r"(?<![\w.])[A-Za-z_][\w]*(?:\.[\w*]+)*")
_INDEX: dict = {}


def index(texts):
    """token -> [(relpath, line)], tokens being dotted words; built once."""
    if not _INDEX:
        for k, (r, lines) in enumerate(texts):
            for i, l in enumerate(lines, 1):
                for t in set(TOKEN.findall(l)):
                    _INDEX.setdefault(t, []).append((k, i))
    return _INDEX


def mention(topic, texts, exclude, site_files=(), consumer=True):
    """First line elsewhere that mentions the topic near a consumer/producer hint. Skipped: the site
    lines themselves, and quoted mentions inside a file that holds a site of this topic (those are the
    tables the site loops over, not independent evidence)."""
    first = None
    quoted = re.compile(r"[\"']" + re.escape(topic) + r"[\"']")
    for k, i in index(texts).get(topic, []):
        r, lines = texts[k]
        l = lines[i - 1]
        if True:
            if (r, i) in exclude or (r in site_files and quoted.search(l)):
                continue
            ctx = " ".join(lines[max(0, i - 2):i + 1])
            hit = (r, i, l.strip()[:120], FAIRY_NAME.findall(ctx))
            if not consumer or CONSUMER_HINT.search(ctx):
                return hit
            first = first or hit
    return None if consumer else first


def classify(topic, sites, refs, texts, exclude, side):
    if side == "B" and "*" in topic:
        return "w", "literal wildcard; no router expands `*` (see the wildcard table in section 1)"
    deads = [file_is_dead(s.file, refs) for s in sites]
    if sites and all(deads):
        return "c", f"{deads[0]} ({sites[0].loc})"
    # a one-word topic ("GUI", "somatic") occurs everywhere as a plain word; no mention search
    m = mention(topic, texts, exclude, {dl.rel(s.file) for s in sites}) if "." in topic else None
    if m:
        r, i, line, names = m
        who = f" names {names[0]}" if names else ""
        return "a", f"{r}:{i}{who}: `{line.replace('|', '/').replace('`', '')}`"
    segs = topic.split(".")
    if side == "B" and segs[-1] in INTENT_TABLE_WORDS | {"get_feeling", "get_registered", "send_alert"} \
            or (side == "B" and segs[-1].startswith(("get_", "set_", "list_", "add_", "do_"))):
        return "e", f"intent-style handler `{segs[-1]}`"
    if any(s in TELE_WORDS or (len(s) > 4 and s.endswith("ed")) for s in segs):
        return "b", "status/event-style name"
    if side == "B" and all(DIAG_FILE.search(dl.rel(s.file)) for s in sites):
        return "b", "subscriber is a diagnostic/monitor file"
    return "d", ""


def main():
    live, tests, shadowed, reached = dl.census()
    sites = dl.scan(live)
    pub, sub = defaultdict(list), defaultdict(list)
    for s in sites:
        for t in s.topics:
            if s.kind == "pub":
                pub[t].append(s)
            elif s.kind == "sub":
                sub[t].append(s)
    dead, deaf = dl.dead_and_deaf(sites)
    texts = corpus()
    refs = referenced_stems(texts)
    exclude = {(dl.rel(s.file), s.line) for s in sites if s.topics}

    L = []
    w = L.append
    w("# W3 TRIAGE: dead letters and deaf ears")
    w("")
    w("Generated by `python3 -W ignore tools/dead_letter_triage.py` from the same scan as")
    w(f"docs/DEAD_LETTERS.md. Now: **A = {len(dead)} dead-letter topics, B = {len(deaf)} deaf-ear topics.**")
    w("Tags: [C] read in code, [I] inference. Pairs were confirmed by reading both ends [C]; the A/B classes")
    w("below the pairs are assigned by rules (see the script docstring) and are [I] unless a row says otherwise.")
    w("")
    w("## 1. Near-miss pairs (cheapest real fixes)")
    w("")
    w("Candidates came from `tools/dead_letter_pairs.py` (A x B, and A x live ears). Each listed pair was read")
    w("at both ends. 'still' column: whether the scan still lists the letter in A and the ear in B / live.")
    w("")
    w("| # | letter (published) | publish file:line | ear (subscribed) | subscribe file:line | kind | conf. | reading [C] |")
    w("|---|---|---|---|---|---|---|---|")
    paired_a, paired_b = set(), set()
    for i, (a, b, kind, conf, note) in enumerate(PAIRS, 1):
        pa = ", ".join(s.loc for s in pub.get(a, [])[:3]) or "(not found by scan)"
        sb = ", ".join(s.loc for s in sub.get(b, [])[:3]) or "(not found by scan)"
        state = ("A" if a in dead else "not A") + "/" + ("B" if b in deaf else "live ear" if b in sub else "?")
        paired_a.add(a)
        paired_b.add(b)
        w(f"| {i} | `{a}` | {pa} | `{b}` | {sb} | {kind} ({state}) | {conf} | {note} |")
    w("")
    w("Read and rejected (look alike, different channels):")
    w("")
    for a, b, why in REJECTED:
        w(f"* `{a}` / `{b}`: {why}")
    w("")
    w("### Literal-wildcard ears (the pattern behind most pairs)")
    w("")
    w("Every B row containing `*` is a subscriber that waits on a literal string. What each would receive")
    w("if it subscribed the prefix instead (publish topics under that prefix in this scan):")
    w("")
    w("| ear | subscribe file:line | topics published under the prefix | of which in A |")
    w("|---|---|---|---|")
    for b in sorted(t for t in deaf if "*" in t):
        pre = b.rstrip("*").rstrip(".")
        if not pre or dl.WILD in pre:
            continue
        hits = [p for p in pub if p == pre or p.startswith(pre + ".")]
        w(f"| `{dl.show(b)}` | {', '.join(s.loc for s in sub[b][:2])} | {len(hits)} | "
          f"{sum(1 for p in hits if p in dead)} |")
    w("")

    counts = {"A": defaultdict(int), "B": defaultdict(int)}
    rows_a = []
    for t in dead:
        if t in paired_a:
            continue
        cls, ev = classify(t, pub[t], refs, texts, exclude, "A")
        counts["A"][cls] += 1
        rows_a.append((len(pub[t]), t, cls, ev))
    rows_a.sort(key=lambda x: (-x[0], x[1]))
    rows_b = []
    for t in deaf:
        if t in paired_b:
            continue
        cls, ev = classify(t, sub[t], refs, texts, exclude, "B")
        counts["B"][cls] += 1
        rows_b.append((len(sub[t]), t, cls, ev))
    rows_b.sort(key=lambda x: (x[2], -x[0], x[1]))

    names = {"a": "planned partner never built", "b": "telemetry / notification", "c": "dead or shadowed source",
             "d": "unclear", "e": "intent-table handler nobody calls over postal",
             "w": "literal-wildcard ear (B only; a wiring bug, not a missing voice)"}
    w("## 2. Class counts [I]")
    w("")
    w("| class | A (letters, excl. pairs) | B (ears, excl. pairs) |")
    w("|---|---|---|")
    for k in "abcdew":
        w(f"| {k}: {names[k]} | {counts['A'][k]} | {counts['B'][k]} |")
    w(f"| total | {sum(counts['A'].values())} | {sum(counts['B'].values())} |")
    w("")
    w("## 3. A: dead letters, ranked by publish sites")
    w("")
    w("| topic | publish sites | first sites | class [I] | evidence |")
    w("|---|---|---|---|---|")
    for n, t, cls, ev in rows_a:
        locs = ", ".join(s.loc for s in pub[t][:3]) + (" ..." if n > 3 else "")
        w(f"| `{dl.md_escape(dl.show(t))}` | {n} | {locs} | {cls} | {dl.md_escape(ev)} |")
    w("")
    w("## 4. B: deaf ears, by class")
    w("")
    w("| topic | subscribe sites | first sites | class [I] | evidence |")
    w("|---|---|---|---|---|")
    for n, t, cls, ev in rows_b:
        locs = ", ".join(s.loc for s in sub[t][:3]) + (" ..." if n > 3 else "")
        w(f"| `{dl.md_escape(dl.show(t))}` | {n} | {locs} | {cls} | {dl.md_escape(ev)} |")
    w("")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {dl.rel(OUT)}  A={len(dead)} B={len(deaf)} pairs={len(PAIRS)} "
          f"A-classes={dict(counts['A'])} B-classes={dict(counts['B'])}")


if __name__ == "__main__":
    main()
