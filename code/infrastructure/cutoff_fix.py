"""cutoff_fix.py -- Ace's CUT-OFF switch, state/cutoff_fix.json, READ ONLY. 2026-10-19 (Nous, nous_builds/cutoff_fix_1019).

Ace 10-19, after two cut lines in Boot T (10:42 / 10:43): "were these thoughts cut off?" then "aye lets go with your lean". One file, one
key per item; this module is the one reader every cutoff_fix site asks (infrastructure/intention.py, the council driver):

    {"say_capped": "compose", "strip_say_quotes": true, "budget_hint": true, "trim_leadin": true}

    say_capped        "compose" | "drop" | "off"   a say-plan that hit its token cap is never spoken as written: compose hands its
                                                   opening to the voluntary chairman at a quiet moment, drop lets it go
    strip_say_quotes  true | false                 wrapping quotes come off every say object
    budget_hint       true | false                 the length sentence in the chairman / voluntary prompt
    trim_leadin       true | false                 a dangling lead-in at the end of a reply that provably hit its cap is dropped

    absent file, absent key, "off"         = that item OFF (today's behaviour)
    not an object, an unknown key, a say_capped outside the three words, a bool key that is not exactly true / false, torn or
    empty JSON                             = EVERY key OFF (fail closed), said once per file version in her log

Ace writes the file (cutoff_fix.cmd); her process only reads it, cached on (mtime, size), so a change is seen at the next read.
Stdlib only. Revert: apply_cutoff_fix.py --revert moves this file aside; every site then reads OFF (its import fails closed).
"""
from __future__ import annotations

import json
import os
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
FILE = os.path.join(_ROOT, "state", "cutoff_fix.json")
BOOL_KEYS = frozenset({"strip_say_quotes", "budget_hint", "trim_leadin"})
SAY_VALUES = ("compose", "drop", "off")
KEYS = BOOL_KEYS | {"say_capped"}
_LOCK = threading.Lock()
_CACHE = {"key": None, "data": {}, "why": "absent", "said": None}
_META = {}                                              # farm class -> does its generate_speech take meta=


def switch() -> dict:
    """{key: True} for the bool keys that are ON, plus {"say_capped": "compose" | "drop"} when it is set; {} when the file is absent
    or malformed. Never raises, never writes."""
    try:
        stt = os.stat(FILE)
    except OSError:
        with _LOCK:
            _CACHE.update(key=None, data={}, why="absent")
        return {}
    key = (stt.st_mtime_ns, stt.st_size)
    with _LOCK:
        if key == _CACHE["key"]:
            return dict(_CACHE["data"])
    data, why = {}, ""
    try:
        with open(FILE, "rb") as f:
            d = json.loads(f.read().decode("utf-8-sig"))
        if not isinstance(d, dict):
            why = "it is not an object"
        elif set(d) - KEYS:
            why = ("unknown keys %s" % ",".join(sorted(map(str, set(d) - KEYS))))[:80]
        elif "say_capped" in d and not (isinstance(d["say_capped"], str) and d["say_capped"] in SAY_VALUES):
            why = "say_capped is not compose / drop / off"
        elif any(not isinstance(v, bool) for k, v in d.items() if k in BOOL_KEYS):
            why = "a value is not true / false"
        else:
            data = {k: True for k, v in d.items() if k in BOOL_KEYS and v is True}
            if d.get("say_capped") in ("compose", "drop"):
                data["say_capped"] = d["say_capped"]
    except OSError as e:
        why, key = "it could not be opened (%s)" % type(e).__name__, None
    except Exception as e:
        why = "it is unreadable (%s)" % type(e).__name__
    with _LOCK:
        _CACHE.update(key=key, data=dict(data), why=why or "ok")
        say = bool(why) and _CACHE.get("said") != (why, stt.st_mtime_ns)
        if say:
            _CACHE["said"] = (why, stt.st_mtime_ns)
    if say:
        try:
            print("[CutoffFix] cutoff_fix.json: every key OFF (%s)" % why, flush=True)
        except Exception:
            pass
    return dict(data)


def say_capped():
    """'compose' | 'drop' | None. None = a capped say-plan is handled exactly as today. OFF on any doubt."""
    try:
        v = switch().get("say_capped")
        return v if v in ("compose", "drop") else None
    except Exception:
        return None


def on(key: str) -> bool:
    """One bool key of Ace's cut-off switch (strip_say_quotes, budget_hint, trim_leadin); OFF on any doubt."""
    try:
        k = str(key)
        return k in BOOL_KEYS and switch().get(k) is True
    except Exception:
        return False


def takes_meta(farm) -> bool:
    """True when the farm's generate_speech takes meta= (the farm's own cap signal). Read once per farm class, by signature. Asked
    only while a key that needs it is ON, so a farm without it (a wrapper, a proxy, *args) says so ONCE per class: a key that is
    on and does nothing must not be silent (the same precedent as intention._takes_deed)."""
    try:
        k = type(farm)
        if k not in _META:
            import inspect
            try:
                _META[k] = "meta" in inspect.signature(farm.generate_speech).parameters
            except Exception:
                _META[k] = False
            if not _META[k]:
                print("[CutoffFix] the farm's generate_speech (%s) takes no meta=, so the cap signal is unavailable -- "
                      "say_capped and trim_leadin stay inactive" % ascii(getattr(k, "__name__", "?")), flush=True)
        return bool(_META[k])
    except Exception:
        return False
