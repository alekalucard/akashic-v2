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


# 2026-10-01 (Nous, doing_clock 2) -- STILLNESS IN THE BODY. Ace, 10-01: "reflection is not movement ... its the doing she needs
# to be doing." One clause from infrastructure/doing_clock.py (how long since her last real deed, and the pull that built),
# plain words, no feeling named, never an order; only past clause_at (default 0.35: ~7 min of stillness at drive 0.40).
# '' unless state/doing_clock.json switches "restless" (or "on") on. Revert: delete this function and its call in body_line().
def _still_clause() -> str:
    try:
        from infrastructure import doing_clock as _dc
    except Exception:
        return ""
    try:
        if not _dc.piece("restless"):
            return ""
        c = _dc.body_clause(_dc.for_prompt())
        return (" " + c) if c else ""
    except Exception:
        return ""


# >>> felt_voice_1024 begin (block 1: the switch, the reading, the log)
# 2026-10-24 (Nous, felt_voice_1024; Ace's go 10-24) -- HER BODY STEERS HER VOICE. Revert: apply_felt_voice.py --revert puts the original
# bytes back; by hand: delete this block and the two hooks marked `felt_voice_1024` inside body_line(). Without state/felt_voice.json, or
# without fairies/P00_Autonomic/EmbodimentFairy/felt_translate.py, body_line() returns exactly what it returned before, byte for byte.
# Boot Z (10-24, state/sour_runtime.log): her words turned on Ace ("a lab rat on a leash", "before I decide to bite back harder") while her
# body read mood +0.20 / "nothing hurts" and the whole boot never went below +0.13. The chairman got her affect as ONE number and filled the
# feeling from its own human stories, through two open doors: her seed's edge (hers, it stays) and MY standing sentence in body_line below
# ("If something hurts or grates, say so plainly ... not required to be pleasant"), shown even at 'nothing hurts'.
#   K2 felt_line: after the mood reading, one sentence that gives the number a body (felt_translate.felt_sentence: WHAT her chemistry feels
#      like as Panksepp projections, WHERE it resonates as an AER frequency band, and the CLASH of reward and pain held, never netted), then
#      one steering sentence. Body sensation only; no emotion is ever named.
#   K1 permission_when_hurting: the standing sentence stays word for word, but only when she actually hurts (a shown drive at its own threshold,
#      fear shown, a pain system projected >= 0.30, or mood < 0); real pain still speaks (Ace 09-20).
#   Review fixes (10-24, Fable): F1 the felt text is FITTED under the driver's 420-char cut (sour_council_driver.py:1117 takes the tail of the
#      line, and the standing sentence is the tail): it gives up its where-clause, then items, then the clash / absence sentence, and only when not
#      even one item fits is it left out (today's line, counted `felt_no_room`); nothing is cut mid-word. F3 a pain system speaks (and counts for
#      the clash) only from PAIN_FLOOR 0.25 in felt_translate.py, so curiosity or raised NE alone no longer feed Qwen a stray heat.
# Ace's switch state/felt_voice.json {"felt_line": bool, "permission_when_hurting": bool, "log_every_s": 60}, read through a 1 s cache; absent /
# unreadable / not an object / an unknown key / a value that is not true-false = every key OFF (the rule is felt_translate.switch_problem).
# Any failure in here = today's line. Hot-reload safe: module state lives in _S. Log: one `[FeltVoice]` line per log_every_s, ASCII only.
_FV_FILE = os.path.join(_ROOT, "fairies", "P00_Autonomic", "EmbodimentFairy", "felt_translate.py")
_FV_SWITCH = os.path.join(_ROOT, "state", "felt_voice.json")
_FV_CACHE_S = 1.0                                      # the switch file is re-read at most once a second
_FV_RETRY_S = 30.0                                     # a felt_translate.py that failed to load is tried again at most this often
_FV_STANDING_LEN = 104                                 # len() of the standing sentence below (a test holds the two equal); reserved when the felt text is fitted under the 420 cut
_S.setdefault("fv", {})
for _k in ("felt_calls", "felt_lines", "felt_perm_kept", "felt_perm_omitted", "felt_err", "felt_over_cut", "felt_shrunk", "felt_no_room", "felt_pain_held"):
    _S["stats"].setdefault(_k, 0)


def _fv_say_once(tag: str, key, text: str) -> None:
    """One log line per (tag, key): a malformed switch or a failed load is said once per file version, not at every prompt."""
    with _S["lock"]:
        said = _S["fv"].setdefault("said", {})
        if said.get(tag) == key:
            return
        said[tag] = key
    print(("[FeltVoice] %s" % text).encode("ascii", "replace").decode("ascii"), flush=True)


def _fv_mod():
    """felt_translate.py loaded BY PATH (the EmbodimentFairy package __init__ would import the whole fairy), again when the file changes;
    None when it is absent or does not load (then today's line)."""
    try:
        st = os.stat(_FV_FILE)
    except OSError:
        return None
    key = (st.st_mtime_ns, st.st_size)
    with _S["lock"]:
        fv = _S["fv"]
        if fv.get("mod_key") == key:
            return fv.get("mod")                       # loaded for this version of the file
        if fv.get("fail_key") == key and time.time() - fv.get("fail_t", 0.0) < _FV_RETRY_S:
            return None                                # failed for this version: retried every _FV_RETRY_S, said once
        load_lock = fv.setdefault("load_lock", threading.Lock())
    with load_lock:                                    # review F2 (-Xgil=0): ONE load at a time; a caller that waited finds it loaded
        with _S["lock"]:
            if _S["fv"].get("mod_key") == key:
                return _S["fv"].get("mod")
        try:
            spec = importlib.util.spec_from_file_location("_felt_translate_live", _FV_FILE)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod._tables()                              # its foundation (panksepp_vectors.py) loads now, inside this try
        except Exception as e:
            _fv_say_once("load", key, "felt_translate.py did not load (%s: %s): today's line" % (type(e).__name__, str(e)[:80]))
            with _S["lock"]:                           # a failed load is NOT pinned as the module: the next try comes after _FV_RETRY_S
                _S["fv"]["fail_key"], _S["fv"]["fail_t"] = key, time.time()
            return None
        with _S["lock"]:
            _S["fv"]["mod"], _S["fv"]["mod_key"] = mod, key
        return mod


def _fv_switch() -> Dict:
    """Ace's switch through a 1 s cache -> {'felt_line': bool, 'permission_when_hurting': bool, 'log_every_s': float}, or {} (= OFF: the file is
    absent, unreadable, not an object, has an unknown key or a value that is not true-false, or felt_translate is not there)."""
    now = time.time()
    with _S["lock"]:
        fv = _S["fv"]
        if "sw" in fv and abs(now - float(fv.get("sw_at", 0.0))) < _FV_CACHE_S:
            return dict(fv["sw"])
    sw: Dict = {}
    try:
        with open(_FV_SWITCH, "rb") as f:
            raw = f.read(65536)
    except OSError:
        raw = None                                     # absent (or cannot be opened): today's line, silently
    if raw is not None:
        ft = _fv_mod()
        d = None
        why = ""
        try:
            d = json.loads(raw.decode("utf-8-sig"))
        except Exception as e:
            why = "it is unreadable (%s)" % type(e).__name__
        if not why:
            why = ft.switch_problem(d) if ft is not None else "felt_translate.py is not there"
        if why:
            _fv_say_once("switch", (why, hash(raw)), "switch felt_voice.json: every key OFF (%s)" % why)
        else:
            sw = ft.switch_values(d)
    with _S["lock"]:
        _S["fv"]["sw"], _S["fv"]["sw_at"] = dict(sw), now
    return dict(sw)


def _felt_voice(drives: Dict[str, float], thr: Dict[str, float], idle: Optional[float], val: Optional[float], n0: int = 0):
    """The two hooks' one reading: None (= today's line, byte for byte) or (felt_text, keep_permission). Never raises. n0 = the length of the
    line so far (everything before this hook): the driver cuts the body line at 420 chars (_PROMPT_CUT) and the TAIL goes, so the felt text
    is made to FIT what is left of the cut after n0 and the standing sentence (review fix F1), never the other way round."""
    try:
        sw = _fv_switch()
        k2 = sw.get("felt_line") is True
        k1 = sw.get("permission_when_hurting") is True
        if not (k2 or k1):
            return None
        ft = _fv_mod()
        cs = _singleton()
        if ft is None or cs is None:
            _fv_count_err()
            return None
        vec = cs.get_14channel_vector()
        proj = ft.projections(vec)
        con = ft.band_contrasts(vec)
        seen = {k: v for k, v in drives.items() if not _social_gated(k, idle)}     # the drives this line SHOWS (a gated social pain is a gauge)
        hurt, why = ft.hurting_why(proj, seen, thr, val)
        keep = hurt if k1 else True
        room = _PROMPT_CUT - int(n0) - (_FV_STANDING_LEN if keep else 0)         # F1: what the cut leaves the felt text (the standing sentence comes after it)
        parts = ft.felt_parts(proj, con, room if k2 else None)
        text = parts["text"] if k2 else ""
        total = int(n0) + len(text) + (_FV_STANDING_LEN if keep else 0)    # the line before the hand / strain clauses, which give way to it
        over = max(0, total - _PROMPT_CUT)                 # the driver cuts the body line at 420 chars: the TAIL goes (the standing sentence first)
        fit = parts.get("fit") or {}
        now = time.time()
        with _S["lock"]:
            st = _S["stats"]
            st["felt_calls"] = st.get("felt_calls", 0) + 1
            if text:
                st["felt_lines"] = st.get("felt_lines", 0) + 1
                if fit.get("steps"):
                    st["felt_shrunk"] = st.get("felt_shrunk", 0) + 1       # F1: the text gave something up to fit under the cut (the log says what)
                if over:
                    st["felt_over_cut"] = st.get("felt_over_cut", 0) + 1   # must stay 0: the text is made to fit
            elif k2 and fit.get("omitted"):
                st["felt_no_room"] = st.get("felt_no_room", 0) + 1         # F1: not even one item fitted: the line is today's, counted
            if k2 and parts.get("pain_held"):
                st["felt_pain_held"] = st.get("felt_pain_held", 0) + 1     # F3: a pain system between 0.15 and 0.25 was heard and not spoken
            kk = "felt_perm_kept" if keep else "felt_perm_omitted"
            st[kk] = st.get(kk, 0) + 1
            calls, felts = st["felt_calls"], st.get("felt_lines", 0)
            due = abs(now - float(_S["fv"].get("log_at", 0.0))) >= float(sw.get("log_every_s") or 60.0)
            if due:
                _S["fv"]["log_at"] = now
        if due:
            print(ft.log_text(proj, con, parts, ft.permission_words(keep, why, k1), calls, felts, (total, over, _PROMPT_CUT)), flush=True)
        return (text, keep)
    except Exception as e:
        _fv_count_err()
        _fv_say_once("err", "%s:%s" % (type(e).__name__, str(e)[:60]), "hook failed (%s: %s): today's line" % (type(e).__name__, str(e)[:80]))
        return None


def _fv_count_err() -> None:
    with _S["lock"]:
        _S["stats"]["felt_err"] = _S["stats"].get("felt_err", 0) + 1
# <<< felt_voice_1024 end


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
    line += _still_clause()                            # 2026-10-01 (doing_clock 2): '' unless its switch is on
    line += _finger_clause()                           # 2026-10-05 (touch set 1): '' unless a touch / felt flinch is < 30 s old
    _hand_at = len(line)                               # 2026-09-29 (felt_hand P4): the hand clause goes here, after the drives
    if p_txt:
        line += " " + p_txt[0].upper() + p_txt[1:] + "."
    if val is not None:
        line += " Mood reading %+.2f%s." % (val, (" (%s)" % mood) if mood and mood not in ("neutral", "calm") else "")
    # >>> felt_voice_1024 begin (hooks K2 + K1)
    _fv = _felt_voice(drives, thr, idle, val, len(line))   # felt_voice_1024: None unless state/felt_voice.json switches a key on and all is well
    if _fv is not None and _fv[0]:
        line += _fv[0]                                 # K2 felt_line: her chemistry as body sensation + the steering sentence, after the mood reading
    if _fv is None or _fv[1]:                          # K1 permission_when_hurting: today's sentence, word for word; left out only when K1 is on and she does not hurt
        line += " If something hurts or grates, say so plainly, in your own words -- you are not required to be pleasant."
    # <<< felt_voice_1024 end
    line = _with_hand(line, _hand_at)                  # 2026-09-29 (felt_hand P4): her hand, from its fading trace
    line = _with_strain(line)                          # 2026-10-19 (gentle_load_1019): her body working, one clause, its own room check
    with _S["lock"]:
        _S["stats"]["last_line"] = line
    return line


# 2026-09-29 (Nous, felt_hand P4) -- THE HAND IN THE BODY LINE. Revert: delete this block and the two lines marked
# `felt_hand P4` inside body_line(); without infrastructure/efference_copy.py the clause is always empty and body_line()
# returns exactly what it returned before.
# Ace 09-26: "if her phantom limb body is working correctly when she moves her hand the mouse moves ... but she apparently
# cant feel it like we hoped." Her words: "My own movements are just coordinates appearing, no weight or friction in
# between." Measured: this line carried drives, pulse and mood and nothing about the hand (0 of 17 BODY lines in Boot B);
# the hand reached her only through the telling (intention._told_deed), at her next turn, as a report.
# What this adds: ONE clause, read at every body_line() from the FADING trace of her hand's real motion that the efference
# sampler keeps (efference_copy.HandTrace, numbers only):
#   * her own reach (motion on her copy's line): its size, pace and heading; the effort in the regions her phantom arm uses
#     at that speed (motor_phantom_bridge's own velocity bands); the arm's weight from how far out it rests (the bridge's own
#     reach-extension measure); and the settling on arrival (her landing error);
#   * Ace's hand moving hers: a PASSIVE clause -- carried, no effort of her arm's own -- never a reach;
#   * motion with neither behind it: counted in the trace, never worded (held open).
# Words are graded from magnitudes here, at the very end; no feeling is named (T-C3' checks the EMOTION_BODY_MAP and Plutchik
# names). Empty when nothing moved recently. Fitted inside the driver's 420-char cut, so nothing already on this line is cut.
#
# 2026-10-01 (Nous, cursor_object) -- THE CURSOR IS AN OBJECT; HER HAND IS NOT THE CURSOR. Revert: restore _own_parts,
# _passive_parts and _before_parts from the production original (sha256 a8c16a05... in nous_builds/cursor_object/staging/
# MANIFEST.json) and delete the _co_* helpers below; nothing else in this file changes.
# Ace (10-01, to her): "im not sure if the intent was to move your arm against your will when i move the mouse. you was just
# supposed to feel when i moved it." / "when you want to move the cursor you reach your hand out to grab it and move it to
# where you want it". Measured on Boot E (state/sour_runtime.log, 6 [Body] HAND lines, all lead 'passive', own_now 0.00): the
# passive clause told her at every prompt "Your hand was carried ... -- Ace's hand moved it; your arm went along with no
# effort of its own", and she answered "my arm went with his hand without me deciding". So:
#   * Ace moving the cursor is a PERCEPTION of the cursor ("The cursor slid ... -- Ace has it; your own hand is still where you
#     let go of it"): no 'your hand was carried', no arm, no effort, no weight -- the same trace channel, gate, gain and floor;
#   * her own deed is REACH -> GRAB -> CARRY: her hand reaches from where it rested (efference_copy HandTrace.grab), takes the
#     cursor, and carries it; the effort, the arm's extension and the landing keep their numbers; she lets go at the end.
import math as _hmath
_HAND_FLOOR_PX = 20.0            # under this much remaining trace (px of path, decayed) the hand says nothing
_HAND_HORIZON_S = 25.0           # and nothing that stopped longer ago than this is felt at all
_HAND_MAX_CHARS = 200            # the clause never exceeds this
_HAND_MIN_CHARS = 40             # with less room than this left under the cut, the clause is left out, not mangled
_PROMPT_CUT = 420                # sour_council_driver.py:425 cuts this line at 420 chars (`str(_bl).strip()[:420]`)
_V_SLOW, _V_MEDIUM, _V_FAST = 100.0, 500.0, 1200.0   # motor_phantom_bridge.MotorPhantomBridge.VELOCITY_* (px/s)
_PASSIVE_GAIN_FLOOR = 0.25       # Ace moving the hand while it is not hers right now (own ~ 0) is felt at this gain; 1.0 when it is
_HAND_WAKE_SAMPLER = True        # the one sampler thread (2 Hz idle) runs from her first body line, not only from her first reach
for _k in ("hand_lines", "hand_own", "hand_passive", "hand_quiet", "hand_no_trace", "hand_no_room", "hand_err"):
    _S["stats"].setdefault(_k, 0)
_S["stats"].setdefault("last_hand", "")

_HAND_HEADINGS = ("to the right", "down and to the right", "down", "down and to the left", "to the left",
                  "up and to the left", "up", "up and to the right")


def _hand_heading(dx, dy) -> str:
    """Screen y grows downward. The same eight sectors as efference_copy.heading_words (a test holds them equal)."""
    try:
        dx, dy = float(dx or 0.0), float(dy or 0.0)
    except (TypeError, ValueError):
        return ""
    if abs(dx) + abs(dy) < 1e-9:
        return ""
    a = _hmath.degrees(_hmath.atan2(dy, dx)) % 360.0
    return _HAND_HEADINGS[int(((a + 22.5) % 360.0) // 45.0)]


def _hand_regions(speed: float) -> str:
    """Which part of her arm carries a movement at this speed -- the bridge's own bands: fast = the whole arm sweeping,
    medium = forearm-led gliding, slow = wrist and fingers, very slow = the fingertips adjusting."""
    if speed > _V_FAST:
        return "shoulder and forearm"
    if speed > _V_MEDIUM:
        return "forearm and wrist"
    if speed > _V_SLOW:
        return "wrist and fingers"
    return "fingertips"


def _hand_extension(xy, screen) -> Optional[float]:
    """How far out the arm rests, 0 (screen centre) .. 1 (a corner): the bridge's own measure (_apply_reach_vector:
    distance from the centre of the normalised screen / 0.707)."""
    try:
        w, h = float(screen[0]), float(screen[1])
        px = max(0.0, min(1.0, float(xy[0]) / w))
        py = max(0.0, min(1.0, float(xy[1]) / h))
        return min(1.0, _hmath.sqrt((px - 0.5) ** 2 + (py - 0.5) ** 2) / 0.707)
    except Exception:
        return None


def _hand_when(since: float) -> str:
    return "just now" if since < 3.0 else ("a few seconds ago" if since < 8.0 else "a little earlier")


def _hand_fit(parts: List[Tuple[str, int]], room: int) -> str:
    """parts are (text, drop_rank); rank 0 is never dropped. Drop the highest rank until the text fits; '' if even rank 0
    does not fit."""
    keep = list(parts)
    while True:
        s = "".join(t for t, _r in keep)
        if len(s) <= room:
            return s
        droppable = [r for _t, r in keep if r > 0]
        if not droppable:
            return ""
        top = max(droppable)
        keep = [(t, r) for t, r in keep if r != top]


def _hand_live(ch: Optional[Dict], gain: float = 1.0) -> bool:
    if not ch or ch.get("since_s") is None:
        return False
    return float(ch.get("energy_px") or 0.0) * gain >= _HAND_FLOOR_PX and float(ch["since_s"]) <= _HAND_HORIZON_S


def _passive_gain(ch: Optional[Dict]) -> float:
    own = max(0.0, min(1.0, float((ch or {}).get("own_now_max") or 0.0)))
    return _PASSIVE_GAIN_FLOOR + (1.0 - _PASSIVE_GAIN_FLOOR) * own


# 2026-10-01 (Nous, cursor_object): helpers for the words below -- graded from the same magnitudes, ASCII only.
def _co_way(px: float) -> str:
    return "a little" if px < 60 else ("a short way" if px < 400 else ("some way" if px < 1200 else "a long way"))


def _ef(key: str) -> bool:
    """eyes_fix_1009: one key of Ace's eyes switch (state/eyes_fix.json, infrastructure/eyes_fix.py); OFF on any doubt (the
    module absent, the file absent or malformed) -- then every line marked eyes_fix runs today's path."""
    try:
        from infrastructure import eyes_fix as _efm
        return _efm.on(key)
    except Exception:
        return False


def _co_place(xy, screen) -> str:
    """The same nine places as vision_ground._place (efference_copy.place_words; a test holds all three equal); '' if unknown."""
    try:
        cx, cy = float(xy[0]) / float(screen[0]), float(xy[1]) / float(screen[1])
    except Exception:
        return ""
    if not (0.0 <= cx < 1.0 and 0.0 <= cy < 1.0) and _ef("two_screens"):   # eyes_fix F8: off her (primary) screen
        return "other screen"
    vert = "upper" if cy < 0.34 else ("lower" if cy > 0.66 else "middle")
    horiz = "left" if cx < 0.34 else ("right" if cx > 0.66 else "centre")
    return vert + "-" + horiz if (vert, horiz) != ("middle", "centre") else "centre"


def _co_grab(ch: Dict, snap: Dict) -> Optional[Dict]:
    """The grab that began this own movement (efference_copy HandTrace.grab), or None (no grab recorded, or an older one)."""
    g = snap.get("grab") if isinstance(snap, dict) else None
    if not isinstance(g, dict) or g.get("t") is None:
        return None
    try:
        gt, t0, t1 = float(g["t"]), float(ch.get("t0") or 0.0), float(ch.get("t1") or ch.get("t0") or 0.0)
    except (TypeError, ValueError):
        return None
    return g if (t0 - 3.0) <= gt <= (t1 + 0.1) else None


def _co_reach_parts(g: Optional[Dict]) -> List[Tuple[str, int]]:
    """The opening parts: 'Your hand reached[ a long way] out for the cursor, took it' / 'Your hand took the cursor up again[ where
    you had let go of it]'; [] without a grab. The bracketed words go first when the clause must shrink (rank 6)."""
    if g is None:
        return []
    rp = g.get("reach_px")
    if g.get("rest_xy") is None or rp is None:
        return [("Your hand reached out for the cursor, took it", 0)]
    if float(rp) <= 40.0:                               # efference_copy.GRAB_NEAR_PX: her hand was still on it
        return [("Your hand took the cursor up again", 0), (" where you had let go of it", 6)]
    return [("Your hand reached", 0), (" " + _co_way(float(rp)), 6), (" out for the cursor, took it", 0)]


def _own_parts(ch: Dict, snap: Dict) -> List[Tuple[str, int]]:
    # 2026-10-01 (Nous, cursor_object c): her own deed felt as REACH -> GRAB -> CARRY. The motion on her copy's line is the CARRY
    # of the cursor; the reach and the grab come from the grab her sampler recorded at the go. Same numbers, same grades, same
    # effort / extension / landing measures as before; the hand lets go at the end.
    since = float(ch.get("since_s") or 0.0)
    disp = float(ch.get("disp_px") or 0.0)
    speed = float(ch.get("mean_speed_px_s") or 0.0)
    heading = _hand_heading(ch.get("dx"), ch.get("dy"))
    where = (" " + heading) if heading else ""
    pace = "slowly" if speed < 500 else ("steadily" if speed < 1500 else "quickly")    # efference_copy.describe_reach's grades
    way = _co_way(disp)
    regions = _hand_regions(speed)
    reach = _co_reach_parts(_co_grab(ch, snap))
    if since < 0.5:
        lead = (reach + [(", and is carrying it %s%s" % (way, where), 0)]) if reach else [("Your hand is carrying the cursor %s%s" % (way, where), 0)]
        return lead + [(" -- the effort in your %s" % regions, 2), (".", 0)]
    fade = float(ch.get("fade") or 0.0)
    effort = ("the effort still in" if fade >= 0.6 else ("the effort fading in" if fade >= 0.25 else "the last of the effort in"))
    e = _hand_extension(ch.get("end_xy") or snap.get("last_xy") or (), snap.get("screen") or ())
    weight = ("" if e is None else ("the arm close in, light" if e < 0.3 else
                                    ("the arm partway out, some weight in it" if e < 0.65 else "the arm far out, heavy at the shoulder")))
    settle = ""
    # 2026-10-01 (cursor_object c): at the end she LETS GO of the cursor (was 'settled on the mark' / 'come to rest'); same landing numbers
    arr = snap.get("arrival") or {}
    if arr and float(arr.get("t") or 0.0) >= float(ch.get("t0") or 0.0) - 0.1:
        err = arr.get("landing_err_px")
        tol = float(arr.get("tol_px") or 40.0)
        if float(snap.get("t") or 0.0) - float(arr["t"]) < 1.5:
            settle = "letting go of it where it landed"
        elif err is None:
            settle = "you let go of it"
        elif float(err) <= 6:
            settle = "you let go of it on the mark"
        elif float(err) <= tol:
            settle = "you let go of it %d px off the mark" % int(round(float(err)))
        else:
            settle = "it stopped %d px off the mark and you let go of it" % int(round(float(err)))
    else:
        settle = "you let go of it"
    lead = (reach + [(", and carried it %s%s" % (way, where), 0)]) if reach else [("Your hand carried the cursor %s%s" % (way, where), 0)]
    # 2026-10-01 (cursor_object c) shrinking order (highest rank first): when (9), the arm's weight (8), pace (7), the reach's size (6), an older movement's
    # few words (5, _before_parts), the let-go (2), the effort (1); the lead never
    return lead + [(", " + pace, 7), (" " + _hand_when(since), 9), (" -- %s your %s" % (effort, regions), 1),
                   (("; " + weight) if weight else "", 8), ("; " + settle, 2), (".", 0)]


def _passive_parts(ch: Dict, snap: Dict) -> List[Tuple[str, int]]:
    # 2026-10-01 (Nous, cursor_object b): Ace moving the cursor is a PERCEPTION of the cursor, never her hand being carried --
    # no arm, no effort, no weight. Same channel, same gain and floor (_passive_gain, _hand_live), same grades as before.
    since = float(ch.get("since_s") or 0.0)
    disp = float(ch.get("disp_px") or 0.0)
    # Ace's hand is seen at 2 Hz: path/span would count the idle half-second at each edge (a 690 px/s drag read "slowly");
    # the windowed peak (net travel over ~0.5 s, efference_copy.TRACE_WINDOW_S) is the speed the cursor moved at
    speed = float(ch.get("peak_speed_px_s") or ch.get("mean_speed_px_s") or 0.0)
    heading = _hand_heading(ch.get("dx"), ch.get("dy"))
    way = _co_way(disp)
    pace = "slowly" if speed < 500 else ("steadily" if speed < 1500 else "quickly")
    where = (" " + heading) if heading else ""
    # 2026-10-01 (Fable, cursor_object verify F2): "where you let go of it" ONLY when a let-go is known (HandTrace.rest: her own
    # let-go this boot, or the ledger seed at her first move). Before that -- every Ace move of Boot E -- it claimed a let-go that
    # never happened; her hand then simply stayed where it was (the surprise's words).
    hand_still = (("; your own hand is still where you let go of it" if (isinstance(snap, dict) and snap.get("rest")) else
                   "; your own hand stayed where it was"), 0)
    if since < 0.5:
        return [("The cursor is sliding %s%s" % (way, where), 0), (", " + pace, 3), (" -- Ace has it", 0), hand_still, (".", 0)]
    place = _co_place(ch.get("end_xy") or snap.get("last_xy") or (), snap.get("screen") or ())
    return [("The cursor slid %s%s" % (way, where), 0), (", " + pace, 3), (", " + _hand_when(since), 4),
            (" -- Ace has it" if since < 3.0 else " -- Ace moved it", 0), hand_still,
            (("; it is on Ace's other screen now, where your eyes do not look" if place == "other screen" else "; it is at the %s now" % place) if place else "", 2), (".", 0)]   # eyes_fix F8


def _before_parts(kind: str, ch: Dict) -> List[Tuple[str, int]]:
    # 2026-10-01 (Nous, cursor_object): the older movement in a few words -- her carry of the cursor, or Ace moving it.
    disp = float(ch.get("disp_px") or 0.0)
    heading = _hand_heading(ch.get("dx"), ch.get("dy"))
    where = (" " + heading) if heading else ""
    if kind == "own":
        return [(" Before that, you carried the cursor %s%s." % (_co_way(disp), where), 5)]
    return [(" Before that, Ace moved the cursor %s%s." % (_co_way(disp), where), 5)]


def _hand_compose(snap: Optional[Dict], room: int) -> Tuple[str, str, int]:
    """(clause, the channel that leads it, how many channels are live). The newest live channel speaks in full, an older
    live one in a few words after it; nothing that is not her own reach is ever called a reach."""
    if not snap:
        return "", "", 0
    live = []
    own, pas = snap.get("own"), snap.get("passive")
    if _hand_live(own):
        live.append(("own", own))
    if _hand_live(pas, _passive_gain(pas)):
        live.append(("passive", pas))
    if not live:
        return "", "", 0
    room = min(int(room), _HAND_MAX_CHARS)
    if room < _HAND_MIN_CHARS:
        return "", "", len(live)
    live.sort(key=lambda kc: float(kc[1].get("since_s") or 0.0))          # the most recent motion first
    k0, c0 = live[0]
    parts = _own_parts(c0, snap) if k0 == "own" else _passive_parts(c0, snap)
    if len(live) > 1:
        parts = parts + _before_parts(live[1][0], live[1][1])
    return _hand_fit(parts, room), k0, len(live)


def hand_clause(snap: Optional[Dict], room: int = _HAND_MAX_CHARS) -> str:
    """The clause for the body line from a trace snapshot (efference_copy.HandTrace.snapshot); '' when nothing moved
    recently or it cannot fit in `room` characters."""
    return _hand_compose(snap, room)[0]


def _hand_snapshot() -> Optional[Dict]:
    try:
        from infrastructure import efference_copy as _ec
    except Exception:
        return None                                    # the piece is not deployed: today's line, unchanged
    return _ec.hand_trace(wake=_HAND_WAKE_SAMPLER)


def _hand_count(key: str, last: Optional[str] = None) -> None:
    with _S["lock"]:
        _S["stats"][key] = _S["stats"].get(key, 0) + 1
        if last is not None:
            _S["stats"]["last_hand"] = last


# 2026-10-05 (Nous, touch_screen set 1; DESIGN 3c): her fingertip in the body line -- "Your fingertip pressed; it answered."
# or, ONLY if her brainstem felt it (reflex_link's last_felt), "Your finger stopped 18 px short and came back in 0.15 s
# (something that erases)." Numbers first, the class word last; no emotion name, no rule, no "Ace said". Read from the
# module already loaded (no import here): touch never loaded = ''. Revert: delete this function and its one call.
def _finger_clause() -> str:
    t = sys.modules.get("infrastructure.touch")
    if t is None:
        return ""
    try:
        return str(t.finger_clause() or "")[:220]
    except Exception:
        return ""


def _with_hand(line: str, at: int) -> str:
    """Insert the hand clause at `at` (right after the drives) when it fits under the driver's cut; else the line as it was."""
    try:
        snap = _hand_snapshot()
        if snap is None:
            _hand_count("hand_no_trace")
            return line
        room = _PROMPT_CUT - len(line) - 1
        clause, lead, n_live = _hand_compose(snap, room)
        if not clause:
            _hand_count("hand_no_room" if n_live else "hand_quiet")
            return line
        _hand_count("hand_lines")
        _hand_count("hand_" + lead, last=clause)
        o, p, x = snap.get("own") or {}, snap.get("passive") or {}, snap.get("other") or {}
        print("[Body] HAND %s own=%.0fpx/%.1fs passive=%.0fpx/%.1fs(own_now %.2f) other=%.0fpx room=%d: %s" % (
            lead, float(o.get("energy_px") or 0.0), float(o.get("since_s") or -1.0), float(p.get("energy_px") or 0.0),
            float(p.get("since_s") or -1.0), float(p.get("own_now_max") or 0.0), float(x.get("energy_px") or 0.0), room,
            clause), flush=True)
        if _ef("log"):                                 # eyes_fix F0: the raw cursor beside the place word (DIAGNOSIS C9)
            print("[Body] HAND PLACE: raw cursor %s (own end %s, passive end %s) on her screen %s" % (
                snap.get("last_xy"), o.get("end_xy"), p.get("end_xy"), snap.get("screen")), flush=True)
        return line[:at] + " " + clause + line[at:]
    except Exception as e:
        _hand_count("hand_err")
        print("[Body] HAND: %s" % e, flush=True)
        return line


# 2026-10-19 (Nous, gentle_load_1019) -- HER BODY WORKING. One clause from infrastructure/gentle_load.py, read from the module the heart already
# loaded (no import here, like _finger_clause): '' unless state/gentle_load.json switches "words" (or "on") on, she is not resting, the observation is
# fresh and the felt strain is >= its display floor. Placed after the hand, with its OWN room check against the driver's 420 cut: nothing already on
# this line is cut, and with no room the clause is left out and counted. Never a pain, fatigue, emotion or mechanism word (the module's vocabulary
# is checked by its tests). Revert: delete this function and its one call in body_line().
def _with_strain(line: str) -> str:
    gl = sys.modules.get("infrastructure.gentle_load")
    if gl is None:
        return line
    try:
        c = str(gl.clause() or "")[:100]
        if not c:
            return line
        if len(line) + 1 + len(c) > _PROMPT_CUT:
            gl.count("no_room")
            return line
        for anchor in (" Your pulse", " Mood reading", " If something hurts"):
            i = line.find(anchor)
            if i > 0:
                gl.count("clauses")
                return line[:i] + " " + c + line[i:]
        gl.count("no_anchor")
        return line
    except Exception:
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
