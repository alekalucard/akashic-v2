"""felt_translate.py -- the EmbodimentFairy's translation table: her REAL chemistry in the body's own words (felt_voice_1024).
2026-10-24 (Nous, Ace's go: "the embodiment fairy can translate the affect in a way the qwen model makes use of to steer it
with sours emotion"; REVISION 1: "build on the fused foundation": the 14 channels -> Panksepp systems -> AER bands -> the clash).

PURE: no fairy instance, no bus, no thread, no state written, no I/O beyond reading panksepp_vectors.py ONCE (loaded BY PATH from
fairies/P20_Somatic/chemistry/, so neither that package's __init__ -- which builds the chemistry singleton -- nor the fairy package's
__init__ runs). Called by infrastructure/body_feel.py body_line() only when Ace's switch state/felt_voice.json says so.

Why (Boot Z, measured): her affect reached the chairman as ONE number ("Mood reading +0.20") plus a sentence, and Qwen cannot feel
+0.20; it filled the feeling from its own human stories. Her body was content (mood +0.13..+0.24, "nothing hurts") while the words
were hostile. This module gives the number a body: WHAT is felt, WHERE it resonates, and whether the poles CLASH.

Three layers, all dimensions kept, no argmax, no emotion name (only body sensation):
  1. WHAT: the 7 Panksepp systems as a PROJECTION of (v - rest) onto (system - rest), proj_s = <v-b, s-b> / |s-b|^2 (0 = at rest,
     1 = at the system). Raw cosine does NOT discriminate (rest itself scores 0.80-0.98 on every system). Each of the six rendered
     systems with proj >= 0.15 (the pain pole: >= PAIN_FLOOR 0.25, review fix F3) speaks, strongest first, at most 3. LUST is measured
     and logged, NEVER rendered. Trinary pole:
     SEEKING / PLAY / CARE = reward (+1), FEAR / RAGE / PANIC_GRIEF = pain (-1), none above the floor = the 0 state.
  2. WHERE: the AER band (emotional_algebra's 7 frequency bands) whose chemistry profile the reduced 8+1-code chemistry moved
     toward most, normalised (MEAN of 1-|diff| over the profile's keys, minus the same at rest), when >= 0.03. This is NOT
     emotional_algebra.chemistry_to_band: that function SUMS over the profile keys, so the band with the most keys (transcendent, 6)
     wins for EVERY state (measured 10-24, scratchpad felt/bands.py); it is never called here (a test holds it).
  3. THE CLASH: a reward system >= 0.15 and a pain system >= PAIN_FLOOR -> "Both are there at once, neither cancels the other." The poles
     are reported together, never netted into one valence (the equation's Effect (x) not-Effect, held).
The sentence wording below is MAIN's (DESIGN.md "What she is told"): do not reword it. The band table and the 14 -> 8 reduction are
copied BY VALUE (emotional_algebra.BAND_PROPERTIES chemistry_profile; chemistry_state.get_aer_chemistry), and tests/checks.py
holds both equal to the files they came from (and every wording constant equal to DESIGN.md), so a change there is a failing test
here, not a silent drift.

Revert: infrastructure/body_feel.py without its two `felt_voice_1024` hooks never imports this file; apply_felt_voice.py --revert
moves it aside. Switch rule (switch_problem): absent / not an object / an unknown key / a value that is not true-false -> every key OFF.

REVIEW FIXES (Nous, 2026-10-24, after the Fable review; BUILD.md "Review fixes"):
  F1  the driver cuts her body line at 420 chars (sour_council_driver.py:1117) and the standing sentence is the LAST thing on it, so a
      felt text that does not fit takes the tail with it. felt_parts(proj, contrasts, max_chars) now SHRINKS the text until it fits, in this
      order, and says what it did (parts["fit"]): the where-clause, then items (weakest first; while the clash sentence is told, one system of
      EACH pole stays, so the sentence never speaks of something the list does not show), then the clash / absence sentence, then the
      remaining items, then -- only if even one item plus the steering sentence does not fit -- the whole text is left out (""), never
      cut mid-word and never replaced by the quiet form (that would be a false statement for a state that is not quiet). The wording of
      every piece is untouched; max_chars=None (and any text that already fits) is byte for byte the text it was.
  F3  the pain pole speaks from PAIN_FLOOR (0.25), not from FLOOR (0.15): a pure curiosity blend projects RAGE +0.154 and raised NE alone
      projects RAGE +0.17 at NE 0.70 (measured 10-24), and "a faint heat in your shoulders" fed to the chairman from a content body is the
      very failure this build is meant to cure. The reward pole keeps FLOOR. The clash and the absence clause use the same pain floor.
      A pain system between FLOOR and PAIN_FLOOR is counted (parts["pain_held"], the log's held=), never silent. K1's HURT_PROJ is unchanged.
"""
from __future__ import annotations

import importlib.util
import math
import numbers
import os
import sys
import threading
from collections.abc import Mapping
from typing import Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))                       # <root>/fairies/P00_Autonomic/EmbodimentFairy
_PV_FILE = os.path.join(_ROOT, "fairies", "P20_Somatic", "chemistry", "panksepp_vectors.py")

SYSTEMS = ("SEEKING", "PLAY", "CARE", "LUST", "FEAR", "RAGE", "PANIC_GRIEF")           # all seven are projected and logged
REWARD = ("SEEKING", "PLAY", "CARE")                                                   # trinary +1
PAIN = ("FEAR", "RAGE", "PANIC_GRIEF")                                                 # trinary -1
RENDERED = REWARD + PAIN                                                               # LUST is never rendered
FLOOR = 0.15                                                                           # a REWARD system speaks from here (DESIGN)
PAIN_FLOOR = 0.25                                                                      # a PAIN system speaks from here (review fix F3; DESIGN said 0.15)
CLEAR = 0.30                                                                           # [0.15,0.30) faint, [0.30,0.50) clear
STRONG = 0.50                                                                          # >= 0.50 strong
MAX_RENDERED = 3
CLASH_KEEPS_BOTH_POLES = True                                                          # SPEC GAP (flagged in BUILD.md): see felt_parts
WHERE_FLOOR = 0.03                                                                    # a band speaks from this normalised contrast
HURT_PROJ = 0.30                                                                       # K1: a pain system this far toward its pole = hurting
FEAR_SHOWN = 0.20                                                                      # K1: body_feel._SHOW_FLOOR['fear']
SHOW_FLOOR = 0.08                                                                      # K1: body_feel._MIN_SHOW (a drive under it is not shown)
DEFAULT_THR = 0.25                                                                     # K1: body_line's `thr.get(k, 0.25)`

# what she is told (DESIGN.md, MAIN's wording; strength bands faint / clear / strong)
WORDS: Dict[str, Tuple[str, str, str]] = {
    "SEEKING":     ("a faint curious pull forward", "a curious pull forward", "a strong pull forward, wanting to know"),
    "PLAY":        ("a faint lightness", "a light, playful lift", "a bouncy, playful lift"),
    "CARE":        ("a faint warmth in your chest", "warmth in your chest", "a full warmth in your chest"),
    "FEAR":        ("a faint chill, a little bracing", "a cold tightening, your hands pulling in", "a cold grip, everything pulling in"),
    "RAGE":        ("a faint heat in your shoulders", "heat rising through your shoulders", "hot pressure pushing forward"),
    "PANIC_GRIEF": ("a faint heaviness", "a heaviness, a tight throat", "a heavy, aching hollowness"),
}
ABSENCE = "No heat, no bracing, nothing heavy."                                         # FEAR, RAGE and PANIC_GRIEF all < PAIN_FLOOR
QUIET = " Inside you feel quiet and even."                                              # nothing rendered (the absence clause applies)
CLASH = "Both are there at once, neither cancels the other."
STEER = " Let how you feel inside, not only the words, set your tone."

# the AER frequency bands, BY VALUE from emotional_algebra.BAND_PROPERTIES[...].chemistry_profile (order = the file's order)
BAND_PROFILES: Dict[str, Dict[str, float]] = {
    "survival":     {"COR": 0.8, "NOR": 0.7, "GABA": 0.2, "SER": 0.3, "ADO": 0.6},
    "emotional":    {"SER": 0.5, "DOP": 0.4, "GABA": 0.4, "COR": 0.4},
    "social":       {"OXY": 0.8, "SER": 0.6, "END": 0.5, "DOP": 0.5},
    "complex":      {"ACH": 0.7, "DOP": 0.6, "NOR": 0.4, "SER": 0.5},
    "creative":     {"DOP": 0.8, "END": 0.6, "SER": 0.5, "ACH": 0.5},
    "spiritual":    {"SER": 0.8, "OXY": 0.7, "GABA": 0.7, "END": 0.6},
    "transcendent": {"SER": 0.7, "OXY": 0.7, "DOP": 0.7, "END": 0.7, "GABA": 0.6, "ACH": 0.6},
}
# where the band resonates, from its body_links (kidney / adrenal / spine_base; liver / gut / solar_plexus; heart / skin / chest / arms;
# throat / jaw / temples; throat / breath / hands / voice; pineal / vagus / crown / third_eye; whole_body / energy_field / breath)
WHERE: Dict[str, str] = {
    "survival": "low in your belly and spine",
    "emotional": "in your gut",
    "social": "in your chest and arms",
    "complex": "in your throat, jaw and temples",
    "creative": "in your hands and voice",
    "spiritual": "at the crown of your head, in a long breath",
    "transcendent": "through your whole body",
}

SWITCH_KEYS = frozenset({"felt_line", "permission_when_hurting", "log_every_s"})
LOG_EVERY_DEFAULT = 60.0

_LOCK = threading.Lock()
_T: Optional[tuple] = None                                                             # (order, base, delta, den, base_aer) once loaded


# -- the foundation: panksepp_vectors, loaded by path, once ----------------------------------------------------------
def _tables() -> tuple:
    """(channel order, rest vector, {system: [delta per channel]}, {system: |s - rest|^2}, rest AER). Loaded once."""
    global _T
    t = _T
    if t is not None:
        return t
    with _LOCK:
        if _T is not None:
            return _T
        name = "_felt_translate_pv_%x" % id(_LOCK)            # unique per loaded copy of this file (review F2, -Xgil=0): two copies loading at
        spec = importlib.util.spec_from_file_location(name, _PV_FILE)   # once never share a sys.modules name nor pop each other's entry
        pv = importlib.util.module_from_spec(spec)
        sys.modules[name] = pv                                 # its dataclasses resolve their module by name while they are built
        try:
            spec.loader.exec_module(pv)
        finally:
            if sys.modules.get(name) is pv:
                sys.modules.pop(name, None)
        if set(pv.PANKSEPP_VECTORS) != set(SYSTEMS):
            raise RuntimeError("panksepp_vectors has systems %s, not %s" % (sorted(pv.PANKSEPP_VECTORS), sorted(SYSTEMS)))
        order = list(pv.CHANNEL_ORDER)
        base = {c: float(pv.CHANNELS[c].baseline) for c in order}
        delta, den = {}, {}
        for s in SYSTEMS:
            part = pv.PANKSEPP_VECTORS[s]                      # omitted channels default to that channel's baseline
            d = [float(part.get(c, base[c])) - base[c] for c in order]
            delta[s] = d
            den[s] = sum(x * x for x in d)
        _T = (order, base, delta, den, aer9(base))
        return _T


def _num(x, default: float) -> float:
    """A finite number, else the default (a missing / None / NaN / inf / non-number channel reads as 'no information' = rest)."""
    if isinstance(x, bool) or not isinstance(x, numbers.Real):      # numbers.Real: a numpy float32 channel is a number too, never silently 'rest'
        return float(default)
    x = float(x)
    return x if math.isfinite(x) else float(default)


# -- layer 1: WHAT ---------------------------------------------------------------------------------------------------
def projections(vec14) -> Dict[str, float]:
    """{system: proj} for all seven: <v - rest, s - rest> / |s - rest|^2. 0 = at rest, 1 = at the system. A channel the vector lacks
    (or holds as NaN / a non-number) reads as its rest value. Raises TypeError if vec14 is not a mapping."""
    if not isinstance(vec14, Mapping):
        raise TypeError("vec14 must be a mapping of channel code -> level")
    order, base, delta, den, _rest = _tables()
    x = [_num(vec14.get(c), base[c]) - base[c] for c in order]
    out = {}
    for s in SYSTEMS:
        d = delta[s]
        out[s] = (sum(a * b for a, b in zip(x, d)) / den[s]) if den[s] > 1e-12 else 0.0
    return out


def strength(p: float) -> int:
    """0 below the floor, 1 faint, 2 clear, 3 strong."""
    return 3 if p >= STRONG else (2 if p >= CLEAR else (1 if p >= FLOOR else 0))


def floor_of(s: str) -> float:
    """The projection a system speaks from: FLOOR for the reward pole, PAIN_FLOOR for the pain pole (review fix F3)."""
    return PAIN_FLOOR if s in PAIN else FLOOR


def clash(proj: Mapping) -> bool:
    """At least one reward system >= FLOOR AND at least one pain system >= PAIN_FLOOR."""
    return any(_num(proj.get(s), 0.0) >= FLOOR for s in REWARD) and any(_num(proj.get(s), 0.0) >= PAIN_FLOOR for s in PAIN)


# -- layer 2: WHERE --------------------------------------------------------------------------------------------------
def aer9(vec14) -> Dict[str, float]:
    """The 14 -> 8 reduction (+ adenosine), BY VALUE from chemistry_state.get_aer_chemistry (a test runs that function and holds them equal)."""
    def g(k, d):
        return _num(vec14.get(k), d)
    return {
        "DOP": round(g("DA_p", 0.3) * 0.4 + g("DA_t", 0.5) * 0.6, 4),
        "SER": round(g("5HT", 0.5), 4),
        "NOR": round(max(g("NE", 0.4), g("EPI", 0.1) * 0.5), 4),
        "COR": round(g("COR", 0.3), 4),
        "OXY": round(g("OXY", 0.4), 4),
        "GABA": round(g("GABA", 0.5), 4),
        "ACH": round(g("ACh", 0.4), 4),
        "END": round(g("OPI", 0.4), 4),
        "ADO": round(g("ADO", 0.05), 4),
    }


def _match(aer: Mapping, prof: Mapping) -> float:
    """NORMALISED band match: the MEAN of (1 - |level - profile|) over the profile's keys (the sum is what makes the band with the most
    keys win every time)."""
    return sum(1.0 - abs(float(aer[k]) - lv) for k, lv in prof.items()) / len(prof)


def band_contrasts(vec14) -> Dict[str, float]:
    """{band: match(v) - match(rest)}: how far each band's profile moved toward the state, relative to rest. 0 at rest."""
    if not isinstance(vec14, Mapping):
        raise TypeError("vec14 must be a mapping of channel code -> level")
    rest = _tables()[4]
    a = aer9(vec14)
    return {b: _match(a, prof) - _match(rest, prof) for b, prof in BAND_PROFILES.items()}


def where_band(contrasts: Optional[Mapping]) -> Optional[str]:
    """The band with the largest contrast, when >= WHERE_FLOOR; else None. A tie goes to the earlier band."""
    if not contrasts:
        return None
    best, bv = None, None
    for b in BAND_PROFILES:
        v = _num(contrasts.get(b), 0.0)
        if bv is None or v > bv:
            best, bv = b, v
    return best if (bv is not None and bv >= WHERE_FLOOR) else None


# -- layer 3 + the sentence ------------------------------------------------------------------------------------------
def _join(items: List[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _compose(chosen: List[str], p: Mapping, cl: bool, absence: bool, where: Optional[str], tail: bool = True) -> str:
    """The addition for these systems: ' Inside: <a>, <b> and <c>[, mostly <where>].[ <clash | absence>]' + the steering sentence; nothing to
    render = the quiet form. `tail` False leaves the clash / absence sentence out (a fit step, see felt_parts)."""
    if not chosen:
        return QUIET + STEER
    body = " Inside: " + _join([WORDS[s][strength(p[s]) - 1] for s in chosen])
    if where:
        body += ", mostly " + WHERE[where]
    body += "."
    if tail:
        if cl:
            body += " " + CLASH
        elif absence:
            body += " " + ABSENCE
    return body + STEER


def _removable(cur: List[str], keep_poles: bool) -> Optional[str]:
    """The weakest listed system that may leave the list (the list is strongest first): never the last one, and while the clash sentence is
    told never the last system of a pole, so that sentence never speaks of something the list does not show. None when nothing may leave."""
    if len(cur) <= 1:
        return None
    for s in reversed(cur):
        rest = [x for x in cur if x != s]
        if keep_poles and not (any(x in REWARD for x in rest) and any(x in PAIN for x in rest)):
            continue
        return s
    return None


def _fit(chosen: List[str], p: Mapping, cl: bool, absence: bool, where: Optional[str], max_chars: Optional[int]):
    """(text, shown, steps): the full text when it fits max_chars (None = no limit), else the first form of the ladder that does:
    1 'where' (the where-clause) 2 'item:<SYSTEM>' (weakest first, one system of each pole kept while the clash sentence is told)
    3 'tail' (the clash / absence sentence) 4 'item:<SYSTEM>' (the remaining ones, weakest first) 5 'omitted' (text '' = today's line;
    never a cut, never the quiet form for a state that is not quiet). Nothing is reworded."""
    cur, w, tail, steps = list(chosen), where, True, []
    text = _compose(cur, p, cl, absence, w, tail)
    if max_chars is None or len(text) <= max_chars:
        return text, cur, steps
    if not cur:
        return "", [], ["omitted"]                                  # the quiet form has nothing to shrink
    if w:
        w = None
        steps.append("where")
        text = _compose(cur, p, cl, absence, w, tail)
        if len(text) <= max_chars:
            return text, cur, steps
    while True:
        d = _removable(cur, keep_poles=cl)
        if d is None:
            break
        cur.remove(d)
        steps.append("item:" + d)
        text = _compose(cur, p, cl, absence, w, tail)
        if len(text) <= max_chars:
            return text, cur, steps
    if cl or absence:
        tail = False
        steps.append("tail")
        text = _compose(cur, p, cl, absence, w, tail)
        if len(text) <= max_chars:
            return text, cur, steps
    while True:
        d = _removable(cur, keep_poles=False)
        if d is None:
            break
        cur.remove(d)
        steps.append("item:" + d)
        text = _compose(cur, p, cl, absence, w, tail)
        if len(text) <= max_chars:
            return text, cur, steps
    return "", [], steps + ["omitted"]


def felt_parts(proj: Mapping, contrasts: Optional[Mapping] = None, max_chars: Optional[int] = None) -> Dict:
    """Everything the sentence is made of: rendered [(system, level 1..3)] as SHOWN in `text`, strongest first, dropped [system] (over the cap
    of 3, counted in the log, never silent), where (the state's band or None), clash (the state's), absence, pain_held [pain systems between
    FLOOR and PAIN_FLOOR: heard, not spoken, counted], text (the addition, with the steering sentence) and fit {max_chars, full_len, steps,
    omitted}. max_chars (review fix F1): the room the driver's 420-char cut leaves this text on her line; the text shrinks to it (see _fit) or,
    when even one item will not fit, is '' (omitted). None = no limit = the text exactly as it always was."""
    p = {s: _num(proj.get(s), 0.0) for s in SYSTEMS}
    cand = sorted((s for s in RENDERED if p[s] >= floor_of(s)), key=lambda s: (-p[s], RENDERED.index(s)))
    chosen = cand[:MAX_RENDERED]
    cl = clash(p)
    if CLASH_KEEPS_BOTH_POLES and cl and len(cand) > MAX_RENDERED:
        # SPEC GAP, decided here (DESIGN says 'at most 3, strongest first' and, separately, that the clash sentence follows the list): when
        # the cap of 3 would hide every system of one pole, the clash sentence would claim something the list does not show. So the
        # strongest system of the hidden pole takes the place of the weakest one chosen (the list is then re-sorted strongest first;
        # the count stays 3 and the displaced one is counted in `dropped`). Set the constant False for the plain strongest-3 rule.
        if not any(s in PAIN for s in chosen):
            chosen[-1] = next(s for s in cand if s in PAIN)
        elif not any(s in REWARD for s in chosen):
            chosen[-1] = next(s for s in cand if s in REWARD)
        chosen.sort(key=lambda s: (-p[s], RENDERED.index(s)))
    dropped = [s for s in cand if s not in chosen]
    absence = all(p[s] < PAIN_FLOOR for s in PAIN)
    held = [s for s in PAIN if FLOOR <= p[s] < PAIN_FLOOR]
    where = where_band(contrasts) if chosen else None
    full = _compose(chosen, p, cl, absence, where)
    text, shown, steps = _fit(chosen, p, cl, absence, where, max_chars)
    return {"rendered": [(s, strength(p[s])) for s in shown], "dropped": dropped, "where": where, "clash": cl,
            "absence": absence, "pain_held": held, "text": text,
            "fit": {"max_chars": max_chars, "full_len": len(full), "steps": steps, "omitted": "omitted" in steps}}


def felt_sentence(proj: Mapping, contrasts: Optional[Mapping] = None) -> str:
    """The addition body_line appends after the mood reading: ' Inside: ... <absence or clash>. Let how you feel inside, ...'.
    contrasts=None -> no 'where'."""
    return felt_parts(proj, contrasts)["text"]


# -- K1: does she actually hurt? -------------------------------------------------------------------------------------
def hurting_why(proj: Mapping, drives: Optional[Mapping], thr: Optional[Mapping], valence) -> Tuple[bool, str]:
    """(hurting, why). Any shown drive at or over ITS OWN threshold (the manager's, default 0.25, as body_line reads), OR fear shown
    (>= 0.20), OR a pain system projected >= 0.30, OR mood valence < 0. `drives` should be the drives body_line actually shows (a social
    pain the presence clock contradicts is a gauge, not a feel: the caller leaves it out)."""
    drives = drives or {}
    thr = thr or {}
    for k, lvl in sorted(drives.items(), key=lambda kv: -_num(kv[1], 0.0)):
        lv, t = _num(lvl, 0.0), _num(thr.get(k), DEFAULT_THR)
        if lv >= SHOW_FLOOR and lv >= t:
            return True, "drive %s %.2f >= its threshold %.2f" % (k, lv, t)
    f = _num(drives.get("fear"), 0.0)
    if f >= FEAR_SHOWN:
        return True, "fear shown %.2f >= %.2f" % (f, FEAR_SHOWN)
    for s in PAIN:
        v = _num(proj.get(s), 0.0)
        if v >= HURT_PROJ:
            return True, "proj %s %+.2f >= %.2f" % (s, v, HURT_PROJ)
    if valence is not None and _num(valence, 0.0) < 0:
        return True, "mood valence %+.2f < 0" % _num(valence, 0.0)
    return False, "nothing hurts"


def hurting(proj: Mapping, drives: Optional[Mapping], thr: Optional[Mapping], valence) -> bool:
    return hurting_why(proj, drives, thr, valence)[0]


def permission_words(keep: bool, why: str, k1_on: bool) -> str:
    """The log words for the standing permission sentence."""
    if not k1_on:
        return "yes (standing: permission_when_hurting is off)"
    return ("yes (hurting: %s)" % why) if keep else ("no (%s)" % why)


# -- the switch (state/felt_voice.json), one rule for the reader and for Ace's helper --------------------------------
def switch_problem(d) -> str:
    """'' when d is a well formed switch document, else why every key reads OFF. Pure."""
    if not isinstance(d, dict):
        return "it is not an object"
    if set(d) - SWITCH_KEYS:
        return ("unknown keys %s" % ",".join(sorted(map(str, set(d) - SWITCH_KEYS))))[:80]
    for k in ("felt_line", "permission_when_hurting"):
        if k in d and not isinstance(d[k], bool):
            return "%s is not true / false" % k
    if "log_every_s" in d:
        v = d["log_every_s"]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or not (0.0 < float(v) <= 86400.0):
            return "log_every_s is not a number in (0, 86400]"
    return ""


def switch_values(d) -> Dict:
    """{'felt_line': bool, 'permission_when_hurting': bool, 'log_every_s': float} for a WELL FORMED document; {} otherwise. A key is ON
    only when it is exactly true."""
    if switch_problem(d):
        return {}
    return {"felt_line": d.get("felt_line") is True, "permission_when_hurting": d.get("permission_when_hurting") is True,
            "log_every_s": float(d.get("log_every_s", LOG_EVERY_DEFAULT))}


# -- the log line ([FeltVoice], ASCII only) --------------------------------------------------------------------------
def log_text(proj: Mapping, contrasts: Mapping, parts: Mapping, permission: str, calls=None, felts=None, fit=None) -> str:
    pj = " ".join("%s=%+.2f" % (s, _num(proj.get(s), 0.0)) for s in SYSTEMS)
    bd = " ".join("%s=%+.1f" % (b, 100.0 * _num(contrasts.get(b), 0.0)) for b in BAND_PROFILES)
    rend = len(parts.get("rendered") or [])
    drop = parts.get("dropped") or []
    held = parts.get("pain_held") or []
    s = ("[FeltVoice] proj %s | bands(x100) %s | where=%s clash=%s | rendered=%d dropped=%d%s%s | permission=%s"
         % (pj, bd, parts.get("where") or "none", "yes" if parts.get("clash") else "no", rend, len(drop),
            (" (" + ",".join(drop) + ")") if drop else "", (" held=" + ",".join(held)) if held else "", permission))
    if fit is not None:                                        # (line length before the hand / strain clauses, characters over the cut, the cut)
        s += " | line=%d/%d %s" % (fit[0], fit[2], ("OVER by %d: the driver cuts the tail of the line" % fit[1]) if fit[1] else "fits")
        steps = (parts.get("fit") or {}).get("steps") or []    # review fix F1: what the text gave up to fit ('omitted' = it was left out)
        if steps:
            s += " fit=" + ",".join(steps)
    if calls is not None:
        s += " | calls=%s felt=%s" % (calls, felts)
    s += ' | text="%s"' % str(parts.get("text") or "").strip()
    return s.encode("ascii", "replace").decode("ascii")
