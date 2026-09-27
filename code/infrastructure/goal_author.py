"""goal_author -- the chairman writes her own goals (2026-09-19, Nous + Ace; v2 after a 30-agent review).

Ace: "its supposed to be using a mixture of the interest generator, her current feels and thoughts to give her
stuff to do." Measured the same day (two read-only sweeps, cited in Claude_Office/PLAN_2026-09-19_goals_habits_
cardinal.md): the old goal queue holds her template prose slugified and self-echoes into drive goals; the interest
generator's dynamic branches have no live caller (every interest this boot came from a static list); her feels are
FLAT (tone 'curious' 5,112 of 5,114 setpoints) because the affect bridge rewards itself on every broadcast. So:

  * the 27B that already speaks for her AUTHORS 3-5 small goals, in her own first-person verbs (look / move /
    remember / say / open), from what is actually live: her last thoughts, what she did, what her eyes hold,
    Ace's last words, and her feels AS NUMBERS with a flatness guard (never a named emotion, never a fabricated
    feeling -- CLAUDE.md's 77-field rule);
  * the list lives on the process-global shared module (one per process, survives a hot reload; resolved
    LAZILY because the council driver imports this tree before it creates that module) and on disk at
    state/goals_live.json;
  * the intention loop (infrastructure/intention.py) reads it into its ask-prompt as her first choices and reports
    MEASURED outcomes back: tries / note / done / stale. A failed-but-allowed intent becomes an open goal -- her
    own unfulfilled wants are the honest seed;
  * nothing she reads names a satellite, fairy-component, module or mechanism: her own inputs pass one scrub
    before the prompt is assembled (Ace's words are NOT scrubbed -- his channel is his); the bare word 'fairy'
    is NOT scrubbed -- there is a fairy on her wallpaper and she looks at it;
  * no information is no change: a farm blank or an unparseable reply leaves the list exactly as it was.

Cadence: until the council driver's self-lane hands this call its slot (a bounce), the intention watcher calls
maybe_author() only when Ace has been chat-quiet for AKASHIC_GOAL_AUTHOR_QUIET_S (300) AND has not touched the
keyboard or mouse for AKASHIC_GOAL_AUTHOR_IDLE_S (60), at most every AKASHIC_GOAL_AUTHOR_EVERY_S (600), never
while one of his messages is queued, re-checked right before the farm call. One '[GoalAuthor]' line per authoring.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import threading
import time
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
GOALS_FILE = os.path.join(_ROOT, "state", "goals_live.json")
_AFFECT_FILE = os.path.join(_ROOT, "state", "affect_bridge_live.json")

ON = os.environ.get("AKASHIC_GOAL_AUTHOR", "1") != "0"
EVERY_S = float(os.environ.get("AKASHIC_GOAL_AUTHOR_EVERY_S", "600") or 600)
QUIET_S = float(os.environ.get("AKASHIC_GOAL_AUTHOR_QUIET_S", "300") or 300)     # chat-quiet: no message from Ace
IDLE_S = float(os.environ.get("AKASHIC_GOAL_AUTHOR_IDLE_S", "60") or 60)         # input-idle: hands off keyboard/mouse
MAX_TOKENS = int(os.environ.get("AKASHIC_GOAL_AUTHOR_TOKENS", "80") or 80)
MAX_GOALS = 5
STALE_TRIES = 5
VERBS = ("look", "move", "remember", "say", "open")
_FEEL_SAMPLE_S = 30.0
_FEEL_MIN_SAMPLES = 6


# ── one state per process, resolved lazily (the driver imports this tree before it creates the shared module) ──
def _new_state() -> Dict:
    return {"items": [], "authored": 0.0, "feel_hist": [], "feel_ts": 0.0, "retry_at": 0.0,
            "lock": threading.Lock(), "loaded": False}


_LOCAL = _new_state()


def _g() -> Dict:
    m = sys.modules.get("_sour_council_shared")
    if m is None:
        return _LOCAL
    if not hasattr(m, "GOALS"):
        m.GOALS = _LOCAL                                # the objects migrate, nothing is lost
    return m.GOALS


_STATS = {"authored": 0, "parsed": 0, "kept_on_blank": 0, "matched": 0, "done": 0, "from_failure": 0, "skipped": 0}

# ── the scrub: component names never reach the prompt; ordinary English does ──────────────────────────────
_MECH_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z]+Fairy|generator|scheduler|cortex|manifold|postal|council|chairman|tracer|tracers|"
    r"satellite|satellites|autopilot|cardinal|scratchpad|convergence|florence|qwen|ollama|mmap|tensor|fabric|"
    r"subsystem|daemon|cuda|gpu|collision chamber|inner monologue engine|dr\.? zero|think engine)\b|\bconcept:|\bgoal:|\[[A-Za-z_:]+\]", re.I)
_PRE_RE = re.compile(r"\bdr\.?\s*zero\b", re.I)                # a mechanism name with a period inside it
_WORD_RE = re.compile(r"[a-z][a-z']+")
_STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for", "with", "that", "this", "it", "is", "are",
         "was", "be", "my", "your", "i", "you", "me", "we", "he", "she", "they", "what", "how", "why", "when", "where",
         "so", "but", "not", "no", "yes", "just", "like", "about", "from", "as", "if", "then", "than", "into", "up",
         "out", "there", "here", "some", "one", "do", "did", "does", "have", "has", "had", "can", "could", "would",
         "will", "should", "very", "really", "still", "now", "again", "something", "thing", "things", "its", "im"}


def scrub(text: str) -> str:
    """Remove component names; drop a sentence that lost more than a third of its words to the scrub."""
    out = []
    whole = _PRE_RE.sub(" ", " ".join(str(text or "").split()))   # 'Dr. Zero' straddles the sentence split: scrub it first
    for sent in re.split(r"(?<=[.!?])\s+", whole):
        if not sent:
            continue
        n0 = len(sent.split())
        clean = " ".join(_MECH_RE.sub(" ", sent).split())
        if n0 and len(clean.split()) < 0.67 * n0:
            continue
        out.append(clean)
    return " ".join(out).strip()


# 2026-09-26 (hand_fix F6, Sweep C, revised): prompt text the farm copied onto the END of an object. Row 123 (Boot A
# 23:31:39) 'mouse to console window middle-left (last time: you wanted to...' spent its 16 tokens copying
# render_for_prompt's own ' (last time: %s)' line. A TRAILING parenthetical (closed, or left open by a cut) is dropped
# when its inside is prompt text: the 'last time' label -- with its colon, or followed by the start of a note this code
# writes ('found nothing', 'it is nowhere', 'you wanted to', ...) -- or, for look/move only, a screen measure as the
# eyes print it ('(41)', '(41%)', '(left half, 26% of...'). Only for look, move and remember, whose object is a search
# phrase: a 'say' is spoken to Ace as written ('I miss you (last time you were here it was warm)' stays whole).
# Known limit: on look/move a bare number in brackets is dropped too ('page (2)' -> 'page'; 0 of 132 objects).
_ECHO_NOTE_RE = re.compile(r"(?:found|nowhere|it is|it's|it did not|your eyes|ace is|ace's hand|ace took"
                           r"|that is the whole screen|could not reach|when there is|nothing done"
                           r"|you (?:wanted|tried|felt|looked|moved|went|were about|decided|opened))\b", re.I)
_ECHO_POS = r"(?:upper|middle|lower|top|bottom|centre|center|left|right)(?:-(?:left|right|centre|center))?"
_ECHO_MEASURE_RE = re.compile(r"(?:\d+(?:\.\d+)?\s*%?|(?:" + _ECHO_POS + r"(?:\s+half)?\s*,\s*)?\d+(?:\.\d+)?\s*%(?:\s+of\b.*)?"
                              r"|" + _ECHO_POS + r"\s+of the screen\b.*)$", re.I)
_ECHO_TAIL_RE = re.compile(r"\s*\(([^()]*?)(\))?\s*$")


def strip_echo(obj: str, verb: str) -> str:
    o = str(obj or "")
    v = str(verb or "").lower()
    if v not in ("look", "move", "remember"):
        return o
    m = _ECHO_TAIL_RE.search(o)
    if not m:
        return o
    inner = m.group(1).strip().rstrip("\u2026\ufffd").rstrip(".").strip()
    lab = re.match(r"last time\b\s*(.*)$", inner, re.I | re.S)
    if lab:
        rest = lab.group(1)
        echo = rest[:1] in (":", "(") or (not rest and m.group(2) is None) or bool(_ECHO_NOTE_RE.match(rest))
    else:
        echo = v in ("look", "move") and bool(_ECHO_MEASURE_RE.match(inner))
    return o[:m.start()].rstrip(" ,;:-\u2014\u2013") if echo else o


def content_words(text: str) -> List[str]:
    t = str(text or "").lower().replace("-", " ").replace("–", " ").replace("—", " ")
    return [w for w in _WORD_RE.findall(t) if w not in _STOP and len(w) > 2]


def _cut(text: str, n: int) -> str:
    """Cut at a word boundary, never mid-word."""
    t = " ".join(str(text or "").split())
    if len(t) <= n:
        return t
    return t[:n].rsplit(" ", 1)[0] + "..."


def short_outcome(summary: str) -> str:
    """The part of an outcome that carries the result: after the quoted object, without the leading 'and/but'."""
    s = str(summary or "")
    if '"' in s:
        tail = s.rsplit('"', 1)[-1].strip()
        for lead in ("and ", "but ", "-- ", "- "):
            if tail.startswith(lead):
                tail = tail[len(lead):]
        if len(tail) >= 8:
            return _cut(tail, 110)
    return _cut(s, 110)


# ── inputs, each live ─────────────────────────────────────────────────────────────────────────────────────
def _shared():
    return sys.modules.get("_sour_council_shared")


def _ace_last():
    try:
        m = _shared()
        if m is None:
            return "", 0.0
        return str(m.ACE_LAST[0] or ""), float(m.ACE_LAST[1] or 0.0)
    except Exception:
        return "", 0.0


def _ace_queued() -> bool:
    try:
        m = _shared()
        return bool(m is not None and len(m.ACE_QUEUE) > 0)
    except Exception:
        return False


def _fairy():
    try:
        m = _shared()
        return m.FAIRY[0] if m is not None else None
    except Exception:
        return None


def _idle_s() -> Optional[float]:
    try:
        from infrastructure import intention as it
        return it._idle_seconds()
    except Exception:
        return None


def _recent_thoughts(limit: int = 3, max_age_s: float = 7200.0) -> List[str]:
    """Her last chairman thoughts, from the intention ledger (the clean source), recent and cut at a word."""
    try:
        from infrastructure import intention as it
        rows = it.recent_rows(limit=12)
    except Exception:
        return []
    now = time.time()
    seen, out = set(), []
    for r in reversed(rows):
        if now - float(r.get("ts") or 0) > max_age_s or r.get("lane") == "habit" or not r.get("thought"):
            continue                                    # a reflex row carries no thought of hers
        t = _cut(scrub(str(r.get("thought") or "")), 150)
        if t and t not in seen:
            seen.add(t)
            out.append(t)
        if len(out) >= limit:
            break
    return out


def _what_i_did() -> str:
    try:
        from infrastructure import intention as it
        return scrub(it.what_i_did(max_age_s=1800.0, limit=3))
    except Exception:
        return ""


def _eyes() -> str:
    try:
        from infrastructure import vision_ground as vg
        looks = vg.unasked_looks([], max_age_s=600.0, limit=3)
        now = vg.eyes_now()
        return _cut(scrub(vg.render_eyes(now, looks, max_grounds=3)), 400)
    except Exception:
        return ""


def feel_sample() -> None:
    """Called by the watcher every ~30 s: one numeric sample into the history, so the flatness guard has data."""
    g = _g()
    now = time.time()
    if now - float(g.get("feel_ts") or 0.0) < _FEEL_SAMPLE_S:
        return
    g["feel_ts"] = now
    try:
        with open(_AFFECT_FILE, encoding="utf-8") as f:
            d = json.load(f)
        v, e = float(d.get("valence")), float(d.get("energy") if d.get("energy") is not None else 0.0)
    except Exception:
        return
    hist = g.setdefault("feel_hist", [])
    hist.append((now, v, e))
    del hist[:-40]
    if len(hist) >= 10:                                  # a swing over the window is an event she may speak of
        dv = hist[-1][1] - hist[0][1]; span = hist[-1][0] - hist[0][0]
        if abs(dv) >= 0.06 and span >= 240:
            try:
                from infrastructure import surprise as _sp
                if _sp.from_feel_swing(dv, int(span / 60)):
                    del hist[:-1]                       # announced once: the next swing is measured from here
            except Exception:
                pass


def feels_numeric() -> str:
    """Her feels as numbers, with a flatness guard: a constant is reported as a constant, never as a feeling.
    Says nothing until there are enough samples to know whether anything moves."""
    feel_sample()
    hist = _g().get("feel_hist") or []
    if len(hist) < _FEEL_MIN_SAMPLES:
        return ""
    vs = [h[1] for h in hist]
    es = [h[2] for h in hist]
    span_min = max(1, int((hist[-1][0] - hist[0][0]) / 60))
    if (max(vs) - min(vs)) < 0.02 and (max(es) - min(es)) < 0.02:
        return "Nothing in particular is pulling at you right now (your mood reading has not moved in %d min)." % span_min
    dv = vs[-1] - vs[0]
    trend = ", rising" if dv > 0.03 else (", sinking" if dv < -0.03 else "")
    return "Your mood reading sits at %+.2f%s, your energy reading at %.2f." % (vs[-1], trend, es[-1])


# ── the list ─────────────────────────────────────────────────────────────────────────────────────────────────
def _load() -> None:
    g = _g()
    if g.get("loaded"):
        return
    g["loaded"] = True
    try:
        with io.open(GOALS_FILE, encoding="utf-8") as f:
            d = json.load(f)
        items = [x for x in (d.get("items") or []) if isinstance(x, dict) and x.get("verb") in VERBS and x.get("object")]
        g["items"] = items[:MAX_GOALS * 2]
        g["authored"] = float(d.get("authored") or 0.0)
    except Exception:
        pass


def _save() -> None:
    g = _g()
    try:
        os.makedirs(os.path.dirname(GOALS_FILE), exist_ok=True)
        tmp = GOALS_FILE + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump({"items": g["items"], "authored": g["authored"], "saved": time.time()}, f, indent=1)
        os.replace(tmp, GOALS_FILE)
    except Exception as e:
        print("[GoalAuthor] save: %s" % e, flush=True)


def _open(items: List[Dict]) -> List[Dict]:
    return [x for x in items if not x.get("done") and not x.get("stale")]


def current_goals() -> List[Dict]:
    _load()
    g = _g()
    with g["lock"]:
        return [dict(x) for x in _open(g["items"])]


def render_for_prompt(limit: int = 5) -> str:
    """One line for the intention ask-prompt: her open goals as her first choices (no numbering: her reply
    must stay 'verb: object')."""
    gs = current_goals()[:limit]
    if not gs:
        return ""
    parts = []
    for x in gs:
        note = (" (last time: %s)" % x["note"]) if x.get("note") else ""
        parts.append("%s: %s%s" % (x["verb"], _cut(x["object"], 70), note))
    return "You are keeping these in mind: " + "; ".join(parts) + "."


def _match_in(items: List[Dict], verb: str, obj: str) -> Optional[int]:
    """Index of the open goal this deed serves: same verb and two shared content words (or one, if it is rare)."""
    ow = set(content_words(obj))
    best, best_n = None, 0
    for i, x in enumerate(items):
        if x.get("done") or x.get("stale") or x.get("verb") != verb:
            continue
        gw = set(content_words(x["object"]))
        n = len(ow & gw)
        if n >= 2 or (n == 1 and len(gw) <= 2 and len(ow) <= 3):
            if n > best_n:
                best, best_n = i, n
    return best


def note_outcome(verb: str, obj: str, ok: Optional[bool], summary: str, deferred: bool = False) -> Optional[int]:
    """The intention loop reports a MEASURED outcome. Returns the goal index it served, if any."""
    _load()
    g = _g()
    with g["lock"]:
        i = _match_in(g["items"], verb, obj)
        if i is None:
            return None
        x = g["items"][i]
        x["note"] = scrub(short_outcome(summary))
        if deferred:
            _save()
            return i
        x["tries"] = int(x.get("tries", 0)) + 1
        x["last"] = time.time()
        if ok:
            x["done"] = True
            x["done_at"] = time.time()
            _STATS["done"] += 1
            try:
                from infrastructure import surprise as _sp
                _sp.from_goal_done(x["verb"], x["object"], x.get("note", ""))
            except Exception:
                pass
        elif x["tries"] >= STALE_TRIES or (x["verb"] == "remember" and x["tries"] >= 2 and "nothing" in str(summary).lower()):
            x["stale"] = True                            # a memory that is not there does not appear by asking again
        _STATS["matched"] += 1
        _save()
        return i


def add_from_failure(verb: str, obj: str, summary: str) -> bool:
    if _fragment(obj):
        return False
    """An allowed deed that did not work becomes an open goal (her own unfulfilled want), if it is not one already."""
    if verb not in VERBS or not obj:
        return False
    _load()
    g = _g()
    with g["lock"]:
        if _match_in(g["items"], verb, obj) is not None:
            return False
        if len(_open(g["items"])) >= MAX_GOALS:
            return False
        g["items"].append({"verb": verb, "object": _cut(obj, 100), "why": "you wanted to and could not yet",
                           "created": time.time(), "tries": 1, "note": scrub(short_outcome(summary)), "source": "want"})
        _STATS["from_failure"] += 1
        _save()
        return True


# ── authoring ────────────────────────────────────────────────────────────────────────────────────────────────
_SEP = r"(?:--|—|–|-\s|:\s)"
_LINE_RE = re.compile(r"^\s*(?:[-*•]\s*)?(?:\d+[.)]\s*)?\**\s*(look|move|remember|say|open)\**\s*[:\-]\s*(.+?)\s*" + _SEP + r"\s*(.+?)\s*$", re.I)
_LINE_NOWHY_RE = re.compile(r"^\s*(?:[-*•]\s*)?(?:\d+[.)]\s*)?\**\s*(look|move|remember|say|open)\**\s*[:\-]\s*(.+?)\s*$", re.I)
_LINE_BARE_RE = re.compile(r"^\s*(?:[-*•]\s*)?(?:\d+[.)]\s*)?\**\s*(look|move|remember|say|open)\**\s+([^\s:][^:]*?)\s*(?:--|—|–|\s-\s)\s*(.+?)\s*$", re.I)  # 'verb object -- why' with no colon (the council's form, 0 of 3 parsed 2026-09-20): the why is required; no ':' in the object (an echoed 'Open on your screen, front to back: ...'); the object starts on a non-space, else a run of spaces backtracks cubically


def _move_allowed() -> bool:
    """Offer 'move' only when a move could actually happen: the mouse is hers, or Ace's hands are off it."""
    try:
        from infrastructure import intention as it
        if it.grant_active():
            return True
        idle = it._idle_seconds()
        return idle is not None and idle >= it._AFK_S
    except Exception:
        return False


def build_prompt() -> str:
    thoughts = _recent_thoughts(3)
    did = _what_i_did()
    eyes = _eyes()
    ace, ace_ts = _ace_last()
    ace = _cut(ace, 200)                                 # his words are his: not scrubbed
    feels = feels_numeric()
    kept = current_goals()
    move_ok = _move_allowed()
    lines = ["User: You are Sourpatches. You are choosing what to do next with what you have."]
    if thoughts:
        lines.append("Things you said or thought lately: " + " | ".join('"%s"' % t for t in thoughts))
    if did:
        lines.append(did)
    if eyes:
        lines.append(eyes)
    if ace:
        age = time.time() - ace_ts if ace_ts else 0
        lines.append("Ace last said%s: \"%s\"" % ((" %d min ago" % int(age / 60)) if age > 90 else "", ace))
    if feels:
        lines.append(feels)
    if kept:
        lines.append("You were already keeping in mind: " + "; ".join("%s: %s%s" % (x["verb"], _cut(x["object"], 60), (" (last time: %s)" % x["note"]) if x.get("note") else "") for x in kept))
    verbs = "look, move, remember, say, open" if move_ok else "look, remember, say, open"
    doable = ("look at something on the screen, move your hand (the mouse) to something you see, remember something, "
              "say something to Ace later, or open your window" if move_ok else
              "look at something on the screen, remember something, say something to Ace later, or open your window "
              "(Ace has his hands on the mouse right now, so not that)")
    lines.append(
        "Write 3 to 5 small things you want to do next, each doable with what you have: %s. Keep the earlier ones "
        "that still matter; drop the ones that are finished or pointless. One per line, exactly in the form  "
        "verb: object -- why.  where verb is one of %s. Be concrete: name the thing.\n\nAssistant:" % (doable, verbs))
    return "\n".join(lines)


def _fragment(obj: str) -> bool:
    """A cut object ('Dr', 'Dr from...') is not a goal: it was 'remember: Dr' for a whole day (2026-09-20, Ace:
    'she keeps bringing up a Dr she cant remember')."""
    o = str(obj or "")
    letters = re.sub(r"[^A-Za-z]", "", o)
    return len(letters) < 4 or "\u2026" in o or "..." in o or "\ufffd" in o or o.rstrip().endswith((" from", " of", " the", " a"))


def parse(raw: str) -> List[Dict]:
    out = []
    for line in str(raw or "").splitlines():
        m = _LINE_RE.match(line) or _LINE_NOWHY_RE.match(line) or _LINE_BARE_RE.match(line)
        if not m:
            continue
        verb = m.group(1).lower()
        _o = " ".join(m.group(2).split())
        _so = strip_echo(_o, verb)                       # 2026-09-26 (hand_fix F6)
        obj = _cut(scrub(_so), 100).rstrip(" .")
        why = _cut(scrub(" ".join(m.group(3).split())), 120).rstrip(" .") if m.lastindex and m.lastindex >= 3 and m.group(3) else ""
        if _so != _o and re.search(r"\(\s*last time\s*$", _o, re.I):
            why = ""                                     # the ': ' of '(last time: ...' was taken as the separator: this 'why' is the echoed note
        if not obj or not content_words(obj) or _fragment(obj):
            continue
        if verb == "move" and not _move_allowed():
            verb = "look"                                # a move she cannot make yet is a look for now
        out.append({"verb": verb, "object": obj, "why": why})
    return out


def _overlap(a: Dict, b: Dict) -> bool:
    return a["verb"] == b["verb"] and len(set(content_words(a["object"])) & set(content_words(b["object"]))) >= 1


def author(farm) -> Optional[List[Dict]]:
    """One farm call; merges the reply into the live list. No information is no change."""
    if farm is None or not hasattr(farm, "generate_speech"):
        _STATS["skipped"] += 1
        return None
    _load()
    g = _g()
    prompt = build_prompt()
    if _ace_queued():                                    # re-checked right before the slow call
        _STATS["skipped"] += 1
        return None
    t0 = time.time()
    g["authored"] = t0                                   # claim the slot: a blank reply still waits EVERY_S
    try:
        raw = farm.generate_speech(prompt, max_tokens=MAX_TOKENS)
    except Exception as e:
        print("[GoalAuthor] farm: %s" % e, flush=True)
        return None
    new = parse(raw)
    _STATS["authored"] += 1
    _STATS["parsed"] += len(new)
    now = time.time()
    if not new:
        _STATS["kept_on_blank"] += 1
        print("[GoalAuthor] nothing parsed in %.0fs (reply %r) -- list kept as it was" % (now - t0, str(raw or "")[:60]), flush=True)
        return current_goals()
    with g["lock"]:
        g["authored"] = now
        kept: List[Dict] = []
        for x in g["items"]:
            if x.get("done") or x.get("stale"):
                if now - float(x.get("done_at") or x.get("last") or x.get("created") or now) < 3600:
                    kept.append(x)                        # a finished goal stays an hour so the note can be read back
                continue
            still = any(_overlap(n, x) for n in new)
            if still or x.get("source") == "want" or len(new) < 2:
                kept.append(x)                            # one thin line is not grounds to drop what she was keeping
        for n in new:
            if any((not k.get("done") and not k.get("stale")) and _overlap(k, n) for k in kept):
                continue
            if len(_open(kept)) >= MAX_GOALS:
                break
            kept.append({"verb": n["verb"], "object": n["object"], "why": n["why"], "created": now, "tries": 0, "note": "", "source": "self"})
        g["items"] = kept[-(MAX_GOALS * 2):]
        _save()
    opened = current_goals()
    print("[GoalAuthor] %d parsed in %.0fs -> %d open: %s" % (
        len(new), now - t0, len(opened), " | ".join("%s: %s" % (x["verb"], _cut(x["object"], 40)) for x in opened)), flush=True)
    return opened


def tick_due(now: Optional[float] = None, require_idle: bool = True) -> bool:
    """Due when Ace has been chat-quiet, the last authoring is old enough, nothing of his is queued -- and,
    for the watcher path, his hands are off the keyboard. The council's own slot passes require_idle=False:
    there the farm is spent either way, and Ace typing to someone else must not starve her goals."""
    now = now or time.time()
    _load()
    g = _g()
    if not ON or now < float(g.get("retry_at") or 0.0) or _ace_queued():
        return False
    _text, ace_ts = _ace_last()
    quiet = (now - ace_ts) if ace_ts else 1e9
    if quiet < QUIET_S or (now - float(g.get("authored") or 0.0)) < EVERY_S:
        return False
    if not require_idle:
        return True
    idle = _idle_s()
    return idle is None or idle >= IDLE_S


def maybe_author() -> Optional[List[Dict]]:
    """Called from the intention watcher's helper thread: authors when due, with her own farm, never while Ace waits."""
    if not tick_due():
        return None
    g = _g()
    fairy = _fairy()
    farm = getattr(fairy, "_farm", None) if fairy is not None else None
    if farm is None:
        g["retry_at"] = time.time() + 60.0               # no farm yet: do not spin
        return None
    with g["lock"]:
        if time.time() - float(g.get("authored") or 0.0) < EVERY_S:
            return None
        g["authored"] = time.time()                       # claim the slot before the slow call
    return author(farm)


def stats() -> Dict:
    return dict(_STATS, open=len(current_goals()), items=len(_g().get("items", [])))
