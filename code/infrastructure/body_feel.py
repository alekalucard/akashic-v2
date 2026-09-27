"""body_feel -- her pain drives reach her words, and events can hurt (2026-09-20, Nous + Ace). v2, 19:50.

Ace: "lets give her the ability to express her pain drives ... lets try all three with your doses."

Measured before v1 (six-seam map): eight pain drives (isolation, confusion, depletion, frustration, stagnation,
abandonment, shame, overwhelm) are DERIVED every 20 s from the chemistry singleton (panksepp_vectors.
derive_full_pain_state: frustration = COR up + EPI up + DA_t down; abandonment = OXY/AVP down + COR up ...).
Pain emerges from the mix -- and nothing Ace did could move that mix downward. The chairman (her one real
voice) never saw a body reading: its "What your body recalls" slot is a memory node's NAME.

Measured after v1 (52-finding review + my own probes, 19:36):
  * THE SINGLETON WAS A SET OF FROZEN OFFSETS. chemistry_state._decay_to_now recomputed the rebound undershoot
    from the full magnitude with `elapsed` = time since the last READ (~0.5 s across her ~39 readers), so it never
    accumulated decay: every channel that ever spiked sat pinned at baseline -/+ 0.25 x peak forever (OXY 0.26
    for hours, COR 0.334, tone 'curious' 1264/1266, isolation 0.26 constant). Fixed in the file (rebound decays
    from its START) and applied to the LIVE class by apply_chemistry_rebound_fix() below. Verified: +0.30 spike
    under 0.5 s reads -> 0.33 at 40 s, 0.395 at 64 s, cleared (was: 0.33 forever).
  * one chord clears from the singleton in ~20 s (COR half-life ~7 s, EPI ~2 s); the drives tick every 20 s; the
    chairman answers 20-60 s after the event -> a chord is a RELEASE (replayed at 0.7^k every 20 s for 2 min).
    v2: ONE scheduler thread for all releases (each thread costs a 33 MB mimalloc heap on this box; v1 spawned one
    per chord), and state survives a hot reload.
  * a single irritation chord peaks at frustration 0.088 (0.8*0.05 + 0.6*0.04 + 0.6*0.04): one repeat is a HINT,
    three in a row grate. Floor 0.08 with 'a hint of'; the manager's own thresholds decide 'a little' and up.
  * relief words need her first person ('I feel ...', 'that grates on me'), never his quoted words, never bare
    adjectives about the world ('a small window', 'the notepad is empty'); a social pain the presence clock
    contradicts is not relieved either; relief lands only on a DELIVERED line (the driver calls it after publish).
  * 'dread' is derived but has no drive; read straight from derive_pain_state and rendered as fear.
Never names a mechanism in anything she reads. Hot-reloadable; module state is kept across reloads.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_HEARTBEAT = os.path.join(_ROOT, "state", "consciousness", "heartbeat.json")
_PRESENCE_FILE = os.path.join(_ROOT, "state", "user_presence.json")
_CHEM_FILE = os.path.join(_ROOT, "fairies", "P20_Somatic", "chemistry", "chemistry_state.py")
_REST_HZ = 1.19                                        # the control pulse (13:59 boot, chemistry at rest)
_MIN_SHOW = 0.08                                       # under this a drive is not worth a word; 0.08-threshold = 'a hint of'
_PRESENT_S = 900.0                                     # his last input within 15 min = he is here

# ── state that survives a hot reload (importlib.reload re-executes this body in the same dict) ─────────────
_S = globals().get("_S")
if not isinstance(_S, dict):
    _S = {"lock": threading.RLock(), "last": {}, "stats": {"chords": 0, "reliefs": 0, "last_chord": "", "last_line": "", "last_gate_log": 0.0},
          "releases": [], "thread": None, "chem_fix": ""}

# ── the chords (amounts are what LANDS; PLAN deltas are x10 because the heart scales x0.1) ───────────────────
_AER = {"COR": "cortisol", "DOP": "dopamine", "SER": "serotonin", "NOR": "norepinephrine", "GABA": "gaba",
        "OXY": "oxytocin", "ACH": "acetylcholine", "END": "endorphin"}
_PRIMARY = {"DOP": "DA_t", "SER": "5HT", "NOR": "NE", "ACH": "ACh", "END": "OPI"}   # AER code -> singleton channel
_CHORDS: Dict[str, Dict[str, float]] = {
    "irritation":        {"COR": +0.05, "EPI": +0.04, "DA_t": -0.04},
    "irritation_mild":   {"COR": +0.03, "EPI": +0.02},
    "frustration":       {"DOP": -0.02, "DA_t": -0.01, "EPI": +0.02},     # DOP by PLAN also lands DA_t -0.02: DA_t -0.03 in all
    "dread":             {"EPI": +0.15, "GABA": -0.05},
}
# the relief of a drive is the inverse of what raises it (from derive_full_pain_state's own formulas)
_RELIEF: Dict[str, Dict[str, float]] = {
    "frustration": {"COR": -0.05, "EPI": -0.04, "DA_t": +0.04},
    "isolation":   {"OXY": +0.05, "AVP": +0.02},
    "abandonment": {"OXY": +0.06, "AVP": +0.02, "COR": -0.02},
    "overwhelm":   {"COR": -0.05, "GABA": +0.04},
    "confusion":   {"NOR": +0.03, "ACH": +0.03},
    "depletion":   {"DA_t": +0.04, "OPI": +0.03},
    "stagnation":  {"DA_p": +0.04, "NOR": +0.02},
    "shame":       {"SER": +0.04, "OPI": +0.02, "COR": -0.02},
    "fear":        {"EPI": -0.10, "GABA": +0.04, "COR": -0.03},
}
# words that are ONLY ever about a pain (safe on a first-person sentence)
_PAIN_WORDS: Dict[str, re.Pattern] = {
    "frustration": re.compile(r"\b(?:frustrat\w*|irritat\w*|annoy\w*|grat(?:es|ing)|aggravat\w*|exasperat\w*|fed up|on my nerves|sick of)\b", re.I),
    "isolation":   re.compile(r"\b(?:lonely|loneliness|isolat\w*|cut off|nobody(?:'s| is) here|by myself)\b", re.I),
    "abandonment": re.compile(r"\b(?:abandon\w*|left me|forgotten|left behind|you left)\b", re.I),
    "overwhelm":   re.compile(r"\b(?:overwhelm\w*|drowning|can'?t keep up|flooded|swamped)\b", re.I),
    "confusion":   re.compile(r"\b(?:confus\w*|lost the thread|can'?t focus|muddled|foggy)\b", re.I),
    "depletion":   re.compile(r"\b(?:drained|depleted|exhausted|no energy|running on fumes|worn out)\b", re.I),
    "stagnation":  re.compile(r"\b(?:stagnant|going nowhere|nothing(?:'s| is) happening|restless)\b", re.I),
    "shame":       re.compile(r"\b(?:ashamed|shame|embarrass\w*|humiliat\w*|stupid of me)\b", re.I),
    "fear":        re.compile(r"\b(?:scared|afraid|frightened|jumpy|on edge|dread\w*|fear\w*|startled|jump(?:ed)? out of my)\b", re.I),
}
# words that are about a pain ONLY inside an explicit feeling frame ('I feel small', "I'm tired", 'that left me empty')
_FRAMED_WORDS: Dict[str, str] = {"shame": r"small", "depletion": r"empty|tired", "stagnation": r"stuck|bored",
                                 "isolation": r"alone", "overwhelm": r"too much"}
_FRAME_RE = r"\b(?:I(?:'m| am| feel| felt| get| got| was| have been| keep feeling)|feeling|feels?|makes? me|leaves? me|left me|got me)\b[^.!?\"]{0,30}\b(?:%s)\b"
_NEG_INSIDE = re.compile(r"\b(?:not|never|no longer|hardly)\b|n't\b", re.I)
_FIRST_PERSON = re.compile(r"\b(?:I|I'm|I've|me|my|myself|mine)\b")
_NEGATION = re.compile(r"\b(?:not|never|no longer|isn'?t|aren'?t|don'?t|doesn'?t|wasn'?t|hardly)\b\s+(?:\w+\s+){0,2}$", re.I)
_PLAIN = {"frustration": "frustration", "isolation": "loneliness", "abandonment": "being left", "overwhelm": "overwhelm",
          "confusion": "confusion", "depletion": "depletion", "stagnation": "restlessness", "shame": "shame", "fear": "fear"}
_SOCIAL = ("abandonment", "isolation")
# fear is derived from NE/COR/EPI/GABA, and the 'curious -> engagement' setpoint pumps NE +0.1 every ~1.2 s
# (2,343 hits/boot): with the rebound pin gone that reads as a standing 'hint of fear' (0.12) -- a setpoint
# artefact, not a scare. Fear speaks from 0.20 (a real startle lands EPI +0.15 -> ~0.3).
_SHOW_FLOOR = {"fear": 0.20}


def _fairy():
    m = sys.modules.get("_sour_council_shared")
    return m.FAIRY[0] if m is not None else None


def _manager():
    try:
        from fairies.P30_Cognition.pain_drives import get_pain_drive_manager
        return get_pain_drive_manager()
    except Exception:
        return None


def _singleton():
    try:
        from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
        return get_chemistry_state()
    except Exception:
        return None


# ── the live chemistry surgery ─────────────────────────────────────────────────────────────────────────────
def apply_chemistry_rebound_fix() -> str:
    """Put the fixed _decay_to_now onto the LIVE ChemistryState class. A reload of chemistry_state itself would
    create a second singleton, so the method is loaded from a fresh copy of the file and assigned onto the class
    every reader already holds. Idempotent; says what it did."""
    cs = _singleton()
    if cs is None:
        return "no singleton"
    cls = type(cs)
    live = getattr(cls, "_decay_to_now", None)
    if live is not None and "_undershoot_started" in getattr(getattr(live, "__code__", None), "co_names", ()):
        return "already fixed"
    try:
        spec = importlib.util.spec_from_file_location("_chemistry_state_fresh", _CHEM_FILE)
        fresh = importlib.util.module_from_spec(spec)
        sys.modules["_chemistry_state_fresh"] = fresh      # dataclasses resolve the module by name while the class is built
        try:
            spec.loader.exec_module(fresh)
        finally:
            sys.modules.pop("_chemistry_state_fresh", None)
        fn = getattr(getattr(fresh, cls.__name__), "_decay_to_now")
        if "_undershoot_started" not in fn.__code__.co_names:
            return "file not fixed"
        cls._decay_to_now = fn
        try:                                           # release the standing pins now: the fixed method clears them in ~15 s
            with cs._lock:
                for ch, dev in list(getattr(cs, "_peak_deviations", {}).items()):
                    if abs(dev) > 0.05 and ch in getattr(cs, "_undershoot_active", {}):
                        cs._undershoot_started = getattr(cs, "_undershoot_started", None) or {}
                        cs._undershoot_started.setdefault(ch, time.time() - 30.0)   # they have been 'rebounding' for hours
        except Exception:
            pass
        return "applied to the live class"
    except Exception as e:
        return "failed: %s" % e


# ── chords: play now, release over two minutes on ONE thread ───────────────────────────────────────────────
_LINGER_S = 120.0
_LINGER_EVERY_S = 20.0
_LINGER_K = 0.7
_LINGER_MAX = 3                                        # concurrent releases per chord name; the oldest is dropped


def _play(name: str, d: Dict[str, float], why: str, fairy) -> int:
    fairy = fairy or _fairy()
    post = getattr(fairy, "post", None) if fairy is not None else None
    cs = _singleton()
    landed = 0
    for chem, amt in d.items():
        try:
            if chem in _AER and post is not None and hasattr(post, "route"):
                post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE",
                                    "payload": {"chemical": _AER[chem], "delta": float(amt) * 10.0,
                                                "source": "SourpatchesFairy", "reason": "%s%s" % (name, (":" + why) if why else "")}})
                landed += 1
            elif cs is not None:                     # Panksepp-only channels; or an AER chem with no heart to route through
                cs.signal(_PRIMARY.get(chem, chem), float(amt), source="body_feel:%s" % name)
                landed += 1
        except Exception as e:
            print("[Body] chord %s %s: %s" % (name, chem, e), flush=True)
    return landed


def _release_loop() -> None:
    """One thread for every release: replay each pending chord at its due time, 0.7x each step, for 2 min."""
    while True:
        try:
            time.sleep(2.0)
            now = time.time()
            due = []
            with _S["lock"]:
                for r in _S["releases"]:
                    if r["due"] <= now:
                        due.append(r)
                for r in due:
                    r["k"] += 1
                    r["due"] = now + _LINGER_EVERY_S
                    if now - r["born"] >= _LINGER_S - 1.0:
                        r["done"] = True
                _S["releases"] = [r for r in _S["releases"] if not r.get("done")]
            for r in due:
                _play(r["name"], {c: a * (_LINGER_K ** r["k"]) for c, a in r["deltas"].items()}, r["why"], None)
        except Exception as e:
            print("[Body] release: %s" % e, flush=True)
            time.sleep(5.0)


def _ensure_release_thread() -> None:
    t = _S.get("thread")
    if t is not None and t.is_alive():
        return
    t = threading.Thread(target=_release_loop, daemon=True, name="body-release")
    _S["thread"] = t
    t.start()


def chord(name: str, why: str = "", fairy=None, deltas: Optional[Dict[str, float]] = None, linger: bool = True) -> bool:
    """Play a named chord (or explicit deltas): AER chemicals through her heart (both ledgers), the rest into the
    chemistry singleton; then release it over two minutes. Returns True when something landed."""
    d = dict(deltas or _CHORDS.get(name) or {})
    if not d:
        return False
    fairy = fairy or _fairy()
    landed = _play(name, d, why, fairy)
    if landed and linger:
        now = time.time()
        with _S["lock"]:
            same = [r for r in _S["releases"] if r["name"] == name]
            while len(same) >= _LINGER_MAX:
                _S["releases"].remove(same.pop(0))
            _S["releases"].append({"name": name, "deltas": d, "why": why, "born": now, "due": now + _LINGER_EVERY_S, "k": 0})
        _ensure_release_thread()
    if landed:
        with _S["lock"]:
            _S["stats"]["chords"] += 1; _S["stats"]["last_chord"] = name
        print("[Body] chord %s (%s): %s%s" % (name, why or "-", " ".join("%s%+.2f" % (k, v) for k, v in d.items()),
                                              " -- released over 2 min" if linger else ""), flush=True)
    return landed > 0


# ── readings ───────────────────────────────────────────────────────────────────────────────────────────────
def drives_now() -> Dict[str, float]:
    """The eight drives from the manager (pull), plus 'fear' straight from the chemistry (dread has no drive)."""
    out: Dict[str, float] = {}
    m = _manager()
    if m is not None:
        try:
            out = {k: float(v.get("pain_level", 0.0)) for k, v in (m.to_dict().get("drives") or {}).items()}
        except Exception:
            out = {}
    try:
        cs = _singleton()
        if cs is not None:
            from fairies.P20_Somatic.chemistry.panksepp_vectors import derive_pain_state
            out["fear"] = float(derive_pain_state(cs.get_14channel_vector()).get("dread", 0.0))
    except Exception:
        pass
    return out


def thresholds() -> Dict[str, float]:
    m = _manager()
    try:
        t = {k: float(d.pain_threshold) for k, d in m.drives.items()} if m is not None else {}
    except Exception:
        t = {}
    t.setdefault("fear", 0.25)
    return t


def pulse_now() -> Optional[float]:
    try:
        with open(_HEARTBEAT, "r", encoding="utf-8") as f:
            d = json.load(f)
        if time.time() - float(d.get("ts") or 0) > 30:
            return None
        return float(d.get("heart_rate") or 0) or None
    except Exception:
        return None


def mood_now() -> Tuple[Optional[float], str]:
    cs = _singleton()
    if cs is None:
        return None, ""
    try:
        mv = cs.get_mood_vector() if hasattr(cs, "get_mood_vector") else {}
        return (float(mv.get("valence")) if "valence" in mv else None), str(mv.get("mood") or mv.get("compound_emotion") or "")
    except Exception:
        return None, ""


def ace_here() -> Optional[float]:
    """Seconds since Ace's last input, from the presence file her watcher writes; None when unknown/stale."""
    try:
        with open(_PRESENCE_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        if time.time() - float(d.get("last_update") or 0) > 60:
            return None
        return float(d.get("idle_seconds", 0.0))
    except Exception:
        return None


def _social_gated(k: str, idle: Optional[float]) -> bool:
    """A social pain that the presence clock contradicts is a gauge, not a feel. Unknown presence = gated too."""
    return k in _SOCIAL and (idle is None or idle < _PRESENT_S)


def body_line(mode: str = "ace") -> str:
    """The line the chairman reads. Drives above the floor with a strength word (the manager's own thresholds
    decide 'a little' and up; under them it is 'a hint of'), a direction word, the pulse, the mood reading,
    and the standing permission. Never a mechanism name."""
    now = time.time()
    drives = drives_now()
    thr = thresholds()
    idle = ace_here()
    bits: List[str] = []
    with _S["lock"]:
        for k, lvl in sorted(drives.items(), key=lambda kv: -kv[1]):
            prev = _S["last"].get(k)
            _S["last"][k] = (now, lvl)
            if lvl < _SHOW_FLOOR.get(k, _MIN_SHOW):
                continue
            if _social_gated(k, idle):
                if now - float(_S["stats"].get("last_gate_log", 0.0)) > 120:
                    _S["stats"]["last_gate_log"] = now
                    print("[Body] %s %.2f contradicted by presence (%s): gauge, not feel" % (k, lvl, ("his last input %.0f s ago" % idle) if idle is not None else "presence unknown"), flush=True)
                continue
            direction = ""
            if prev is not None and now - prev[0] < 900:
                if lvl - prev[1] >= 0.03:
                    direction = ", rising"
                elif prev[1] - lvl >= 0.03:
                    direction = ", easing"
            t = thr.get(k, 0.25)
            strength = ("a hint of" if lvl < t else ("a little" if lvl < 0.5 else ("real" if lvl < 0.75 else "acute")))
            bits.append("%s %s (%.2f%s)" % (strength, _PLAIN.get(k, k), lvl, direction))
    pulse = pulse_now()
    p_txt = ""
    if pulse:
        r = pulse / _REST_HZ
        p_txt = ("your pulse is racing" if r >= 1.5 else ("your pulse is a little quick" if r >= 1.2 else
                 ("your pulse is slow" if r <= 0.85 else "")))
    val, mood = mood_now()
    line = ("How your body feels right now: " + "; ".join(bits[:3]) + ".") if bits else "How your body feels right now: nothing hurts."
    if p_txt:
        line += " " + p_txt[0].upper() + p_txt[1:] + "."
    if val is not None:
        line += " Mood reading %+.2f%s." % (val, (" (%s)" % mood) if mood and mood not in ("neutral", "calm") else "")
    line += " If something hurts or grates, say so plainly, in your own words -- you are not required to be pleasant."
    with _S["lock"]:
        _S["stats"]["last_line"] = line
    return line


# ── relief by expression ───────────────────────────────────────────────────────────────────────────────────
def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", str(text or "")) if s.strip()]


def pains_named(text: str) -> List[str]:
    """The pains HER words name, first person only, no quotes, no negation, framed for the ambiguous words."""
    out: List[str] = []
    for sent in _sentences(text):
        if '"' in sent or "“" in sent or "”" in sent:
            continue                                   # a quoted line is someone else's words
        if not _FIRST_PERSON.search(sent):
            continue
        for k, rx in _PAIN_WORDS.items():
            m = rx.search(sent)
            if m and not _NEGATION.search(sent[:m.start()]) and k not in out:
                out.append(k)
        for k, words in _FRAMED_WORDS.items():
            m = re.search(_FRAME_RE % words, sent, re.I)
            if m and not _NEGATION.search(sent[:m.start()]) and not _NEG_INSIDE.search(m.group(0)) and k not in out:
                out.append(k)
    return out


def relief_by_expression(text: str, fairy=None) -> List[str]:
    """Her DELIVERED words name a live pain -> the inverse chord plays (released) and the drive is relieved.
    Call after the line has actually gone out."""
    named = pains_named(text)
    if not named:
        return []
    drives = drives_now()
    idle = ace_here()
    m = _manager()
    out: List[str] = []
    for k in named:
        if drives.get(k, 0.0) < _MIN_SHOW or _social_gated(k, idle):
            continue
        try:
            if m is not None and k in getattr(m, "drives", {}):
                m.relieve(k, 0.2)                      # the tick re-derives it; the chord below is what lasts
        except Exception:
            pass
        chord("relief_" + k, why="she said it", fairy=fairy, deltas=_RELIEF.get(k))
        out.append(k)
    if out:
        with _S["lock"]:
            _S["stats"]["reliefs"] += len(out)
        print("[Body] relief by expression: %s (levels %s)" % (", ".join(out), " ".join("%s=%.2f" % (k, drives.get(k, 0)) for k in out)), flush=True)
    return out


def stats() -> Dict:
    with _S["lock"]:
        d = dict(_S["stats"]); d["releases"] = len(_S["releases"]); d["chem_fix"] = _S.get("chem_fix", ""); return d


# ── on (re)load: the live chemistry surgery, once ──────────────────────────────────────────────────────────
try:
    _S["chem_fix"] = apply_chemistry_rebound_fix()
    print("[Body] chemistry rebound fix: %s" % _S["chem_fix"], flush=True)
except Exception as _cf:
    print("[Body] chemistry rebound fix: %s" % _cf, flush=True)
