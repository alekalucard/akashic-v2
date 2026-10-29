"""tardis_fix.py -- Ace's TARDIS-fix switch, state/tardis_fix.json, READ ONLY. 2026-10-15 (Nous, nous_builds/tardis_fix_1015).

One file, one key per layer; this module is the one reader every tardis_fix site asks (fairy.py hooks, manifold_memory.py A1,
tardis_timing.py, tardis_backlog.py):

    {"l0_timing": true, "a1_fastlink": true, "b_persist": true}      a key that is exactly true = that layer ON
    absent file, absent key                                         = that layer OFF (today's behaviour, exactly)
    not an object, an unknown key, a value that is not true/false,
    torn JSON, unreadable                                           = EVERY key OFF (fail closed), said ONCE per file version

Same house pattern as infrastructure/eyes_fix.py (cached on (mtime_ns, size), never raises, never writes), with two differences:
  * on(key) re-stats the file at most every TTL_S seconds (default 2.0; floor 0.5, ceiling 10) because A1 asks on EVERY link()
    call and an os.stat per call is not free;
  * the one-line complaint goes to STDERR, never stdout: manifold_memory.py is imported by the Python 3.12 portal interior whose
    stdout is a JSON RPC pipe, and one stray print there corrupts the wire (mm.py:_mlog says the same).
Ace writes the file (tardis_fix.cmd); her process only reads it. The installer never writes it. Stdlib only.
Revert: apply_tardis_fix.py --revert moves this module aside; every site then reads OFF (each import fails closed).
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
FILE = os.path.join(_ROOT, "state", "tardis_fix.json")
KEYS = frozenset({"l0_timing", "a1_fastlink", "b_persist"})
TTL_S = 2.0            # switch re-read at most this often by on(); floor 0.5, ceiling 10 (clamped in _ttl())
_TTL_FLOOR, _TTL_CEIL = 0.5, 10.0
_LOCK = threading.Lock()
_CACHE = {"key": None, "data": {}, "why": "absent", "said": None, "t": -1e9}


def _ttl() -> float:
    try:
        return min(_TTL_CEIL, max(_TTL_FLOOR, float(TTL_S)))
    except Exception:
        return 2.0


def _say(msg: str) -> None:
    try:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def switch() -> dict:
    """{key: True} for the keys that are ON; {} when the file is absent or malformed. Never raises, never writes."""
    try:
        stt = os.stat(FILE)
    except OSError:
        with _LOCK:
            _CACHE.update(key=None, data={}, why="absent", t=time.monotonic())
        return {}
    except Exception:
        return {}
    key = (stt.st_mtime_ns, stt.st_size)
    with _LOCK:
        if key == _CACHE["key"]:
            _CACHE["t"] = time.monotonic()
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
        _CACHE.update(key=key, data=dict(data), why=why or "ok", t=time.monotonic())
        say = bool(why) and _CACHE.get("said") != (why, stt.st_mtime_ns)
        if say:
            _CACHE["said"] = (why, stt.st_mtime_ns)
    if say:
        _say("[TardisFix] tardis_fix.json: every key OFF (%s)" % why)
    return dict(data)


# W11 (2026-10-29, Nous; nous/w11-bind-carryover): two ENVIRONMENT switches that turn a layer ON without the file. Each is ON
# only when its variable is exactly "1"; unset / anything else = the file decides, exactly as before. They can only add ON,
# never turn a layer OFF that the file turned ON. a1_fastlink has no environment switch.
ENV_ALIAS = {"b_persist": "AKASHIC_BIND_CARRYOVER", "l0_timing": "AKASHIC_BIND_TIMING"}


def env_on(key: str) -> bool:
    """The W11 environment switch for this key; False when unset or on any doubt. Never raises."""
    try:
        name = ENV_ALIAS.get(str(key))
        return bool(name) and os.environ.get(name, "0") == "1"
    except Exception:
        return False


def on(key: str, fresh: bool = False) -> bool:
    """One key of Ace's TARDIS-fix switch; OFF on any doubt. fresh=True skips the TTL (still cached on mtime/size)."""
    try:
        if env_on(key):
            return True
        if not fresh:
            with _LOCK:
                if time.monotonic() - _CACHE["t"] < _ttl():
                    return _CACHE["data"].get(str(key)) is True
        return switch().get(str(key)) is True
    except Exception:
        return False


def reset_cache() -> None:
    """Test hook: forget the cache (the next read re-stats the file)."""
    with _LOCK:
        _CACHE.update(key=None, data={}, why="absent", said=None, t=-1e9)
