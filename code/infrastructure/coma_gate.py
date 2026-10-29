"""coma_gate.py -- W13 (2026-10-29 Nous): a gate over the coma, one we can open at will.

WHY: with AKASHIC_COMA=1 every non-exempt fairy boots registered-but-inert (Organ_Template_0_3_0.py _is_comatose / boot()).
  The template already has a reversible wake() that runs the deferred on_boot IN PLACE on the existing instance, but nothing
  calls it. Her three gates (autonomy / autopilot / embodiment) publish boot.fairy.request; server.py's handler either skips
  ("already registered") or builds + boot()s an instance that the coma puts straight back to sleep.

WHAT THIS DOES (only when AKASHIC_COMA_GATE=1; unset or anything else = OFF = nothing here runs):
  * an ALLOW-LIST file, read LIVE on every call (no cache):  AKASHIC_COMA_GATE_FILE, default <code>/state/coma_gate_open.txt
        PainDriveFairy            <- owner opens it: the owner sweep wakes it
        gate:SomaticAvatarFairy   <- her gates may open it: woken only when one of her gates asks (boot.fairy.request)
        # comment, blank lines ignored. An owner-opened name is also open to her gates.
  * open_for(name, source, ...): find the ONE existing instance (CITIZEN_OBJECTS, then the directory record's
        metadata["fairy_instance"]); NEVER constructs one. If it is asleep (_comatose True) call its own wake(). A per-name
        claim taken under a short lock (released before wake, so a slow on_boot never blocks other fairies) means two
        openers cannot wake it twice. After a wake the directory record (if any) is marked "running". Every refusal is
        logged with the fairy name and the reason.
  * on_boot_request(payload, ...): her gates' path (source "gate:<gate>"); only gate in GATES is accepted.
  * sweep(...) / start_owner_watch(...): the owner's path; the watch thread is started only by server.py and only when ON.
  CLOSING: remove the line. Future opens are refused; a fairy already woken stays awake until the next boot (re-sleeping
  through the template's sleep() is NOT done here: on_sleep is optional, so threads started by on_boot would keep running).
"""

from __future__ import annotations

import os
import sys
import threading
import time

SWITCH = "AKASHIC_COMA_GATE"
FILE_ENV = "AKASHIC_COMA_GATE_FILE"
_CODE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_FILE = os.path.join(_CODE_ROOT, "state", "coma_gate_open.txt")

GATES = ("autonomy", "autopilot", "embodiment")   # her three gates (SomaticMindFairy/fairy.py:8171)
# Results that mean "a listed fairy already has its instance": server.py's handler must not build another.
HANDLED = ("woke", "awake", "waking", "refused:no-wake", "refused:wake-error")

_LOCK = threading.Lock()
_waking = set()          # names whose wake() is in progress (claimed under _LOCK)
_watch_thread = None


def enabled() -> bool:
    return os.environ.get(SWITCH, "0") == "1"


def gate_file() -> str:
    return os.environ.get(FILE_ENV) or DEFAULT_FILE


def read_allow_list(path: str = None):
    """Return (owner_open, gate_open) sets, read live. Missing/unreadable file = two empty sets (nothing opens)."""
    owner, gate = set(), set()
    try:
        with open(path or gate_file(), "r", encoding="utf-8-sig") as fh:
            for raw in fh:
                line = raw.split("#", 1)[0].strip()
                if not line:
                    continue
                if line.lower().startswith("gate:"):
                    name = line[5:].strip()
                    if name:
                        gate.add(name)
                else:
                    owner.add(line)
    except Exception:
        return set(), set()
    return owner, gate | owner


def find_instance(name: str, directory=None):
    """The ONE existing instance, or None. Never builds one."""
    # The registry the template already loaded (Organ_Template_0_3_0.py:117). Looked up in sys.modules, never imported:
    # importing fairy_template would import the whole organ template.
    try:
        reg = sys.modules.get("fairy_template.citizen_registry")
        inst = reg.CITIZEN_OBJECTS.get(name) if reg is not None else None
        if inst is not None:
            return inst
    except Exception:
        pass
    try:
        if directory is not None:
            rec = directory.get_fairy(name)
            if rec is not None:
                return (getattr(rec, "metadata", None) or {}).get("fairy_instance")
    except Exception:
        pass
    return None


def _log(log, msg):
    try:
        (log or print)("[COMA-GATE] " + msg)
    except Exception:
        pass


def open_for(name: str, source: str, directory=None, instance=None, log=None, owner_only: bool = False) -> str:
    """Try to open the gate for one fairy. Returns one of:
    off | refused:not-listed | refused:no-instance | refused:not-the-one | refused:no-wake | awake | waking | woke |
    refused:wake-error.  `instance` (a just-built object) is woken only if it IS the one the registry holds."""
    if not enabled() or not name:
        return "off"
    owner_open, gate_open = read_allow_list()
    allowed = owner_open if owner_only else gate_open
    if name not in allowed:
        _log(log, "REFUSED %s (source=%s): not on the allow-list %s" % (name, source, gate_file()))
        return "refused:not-listed"
    with _LOCK:
        the_one = find_instance(name, directory)
        if instance is not None and the_one is not None and the_one is not instance:
            _log(log, "REFUSED %s (source=%s): this object is a second copy, not the registered instance" % (name, source))
            return "refused:not-the-one"
        inst = instance if instance is not None else the_one
        if inst is None:
            _log(log, "REFUSED %s (source=%s): no existing instance (the gate never builds one)" % (name, source))
            return "refused:no-instance"
        if name in _waking:
            return "waking"
        if not getattr(inst, "_comatose", False):
            return "awake"
        wake = getattr(inst, "wake", None)
        if not callable(wake):
            _log(log, "REFUSED %s (source=%s): instance has no wake()" % (name, source))
            return "refused:no-wake"
        _waking.add(name)
    try:
        wake(reason="coma_gate:%s" % source)
    except Exception as e:
        _log(log, "REFUSED %s (source=%s): wake() raised %s" % (name, source, type(e).__name__))
        return "refused:wake-error"
    finally:
        with _LOCK:
            _waking.discard(name)
    try:
        rec = directory.get_fairy(name) if directory is not None else None
        if rec is not None:
            rec.status = "running"
    except Exception:
        pass
    _log(log, "OPENED %s (source=%s): woke the existing instance in place" % (name, source))
    return "woke"


def on_boot_request(payload, directory=None, instance=None, log=None) -> str:
    """Her gates' path: a boot.fairy.request payload {"fairy_name", "gate", ...}."""
    if not enabled():
        return "off"
    try:
        if isinstance(payload, dict) and isinstance(payload.get("payload"), dict):
            payload = payload["payload"]
        name = payload.get("fairy_name")
        gate = payload.get("gate", "unknown")
    except Exception:
        return "off"
    if gate not in GATES:
        _log(log, "REFUSED %s (source=gate:%s): not one of her three gates %s" % (name, gate, "/".join(GATES)))
        return "refused:not-a-gate"
    return open_for(name, "gate:%s" % gate, directory=directory, instance=instance, log=log)


def sweep(directory=None, log=None) -> dict:
    """The owner's path: open every owner-listed name (quiet for ones already awake)."""
    if not enabled():
        return {}
    owner_open, _ = read_allow_list()
    return {n: open_for(n, "owner", directory=directory, log=log, owner_only=True) for n in sorted(owner_open)}


def start_owner_watch(directory=None, interval_s: float = 5.0, log=None):
    """Start ONE daemon thread that re-reads the file every interval_s and sweeps. No-op when OFF or already started."""
    global _watch_thread
    if not enabled():
        return None
    with _LOCK:
        if _watch_thread is not None and _watch_thread.is_alive():
            return _watch_thread

        def _loop():
            while True:
                try:
                    sweep(directory=directory, log=log)
                except Exception:
                    pass
                time.sleep(interval_s)

        _watch_thread = threading.Thread(target=_loop, daemon=True, name="coma_gate_owner_watch")
        _watch_thread.start()
    _log(log, "owner watch ON (file %s, every %ss)" % (gate_file(), interval_s))
    return _watch_thread
