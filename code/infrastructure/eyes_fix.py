"""eyes_fix.py -- Ace's EYES switch, state/eyes_fix.json, READ ONLY. 2026-10-09 (Nous, nous_builds/eyes_fix_1009).

DIAGNOSIS vision_focus_1009 section 4; Ace 10-09: "false tellings first". One file, one key per item; this module is the one
reader every eyes_fix site asks (touch_os.eyes_fix_switch, set 1c's fold, reads the SAME file with the SAME rules for its
own keys `toy_names` and `log`; tests/test_eyes_fix.py E01 holds the two readers equal on a battery of files):

    {"log": true, "doubt": true, ...}      a key that is true = that item ON
    absent file, absent key                = that item OFF (today's behaviour)
    not an object, an unknown key, a value that is not true / false, torn JSON
                                           = EVERY key OFF (fail closed), said once per file version in her log

KEYS is the whole planned key set, fixed by set 1c's fold (touch_os.EYES_FIX_KEYS): an unknown key there turns the whole file
OFF in BOTH readers, so a new key needs both re-pinned. Ace writes the file (eyes_fix_switch.cmd / set1c eyes_on.cmd); her
process only reads it, cached on (mtime, size), so a change is seen at the next read. Stdlib only: it is imported in her main
process, by the farm and the visual cortex fairy, and by the visual interior (Python 3.12, PYTHONPATH = her root).
Revert: apply_eyes_fix.py --revert moves this file aside; every site then reads OFF (its import fails closed).
"""
from __future__ import annotations

import json
import os
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
FILE = os.path.join(_ROOT, "state", "eyes_fix.json")
KEYS = frozenset({"toy_names",                                          # set 1c fold: her eyes know the toy names
                  "log", "doubt", "small", "wallpaper", "hand_honest", "same_box", "glance", "fovea",
                  "two_screens", "deeds", "touch_tell", "gaze_size"})    # DIAGNOSIS 10-09 section 4: F0-F10, + F11
_LOCK = threading.Lock()
_CACHE = {"key": None, "data": {}, "why": "absent", "said": None}


def switch() -> dict:
    """{key: True} for the keys that are ON; {} when the file is absent or malformed. Never raises, never writes."""
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
        elif any(not isinstance(v, bool) for v in d.values()):
            why = "a value is not true / false"
        else:
            data = {k: True for k, v in d.items() if v is True}
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
            print("[EyesFix] eyes switch eyes_fix.json: every eyes key OFF (%s)" % why, flush=True)
        except Exception:
            pass
    return dict(data)


def on(key: str) -> bool:
    """One key of Ace's eyes switch; OFF on any doubt."""
    try:
        return switch().get(str(key)) is True
    except Exception:
        return False
