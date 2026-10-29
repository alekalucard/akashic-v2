"""one_cortex.py -- K2 (engines E2a, step 14b, 2026-10-14 Nous): ONE AssociationCortexFairy, not two.

WHY (DESIGN_14b.md section 1, MEASURED in 9 of 9 boots): server.py builds the cortex twice and neither builder asks the other.
  Builder A, the serial block on the main thread (server.py ">>> STARTING AssociationCortex boot"), constructs it, pre-wires the
  manifold, boots it, and only THEN appends it to registered_fairies (about 13 s later).
  Builder B, the WAKE CASCADE (AutonomyFairy's domain list -> boot.fairy.request -> _handle_fairy_boot_request), asks for the
  same fairy inside that window (it lands during A's 20-27 s manifold open). All three of the handler's "already alive"
  checks miss, so it builds a second copy. That copy has no manifold, takes the portal branch, spawns portal_interior.py
  (Boot N: 4.01 GB private, 1.32 cores) and takes over the shared gate with a PortalGate (Boot N: 11,711 requests, 4,384
  errors in 77 min).

WHAT THIS DOES: the cascade skips AssociationCortexFairy ONLY when the serial block has already STARTED building it.
  server.py calls, each inside its own try/except (any error = today's path):
    describe()                                 once, where the module is imported (one "[K2] serial-owned:" line)
    serial_started(name)                       right after ">>> STARTING AssociationCortex boot"
    is_fallback(name, payload)                 in _handle_fairy_boot_request, BEFORE the registered_fairies check: the
                                               floor's own re-request bypasses that check and the directory check
    cascade_should_skip(name, payload)         same handler, right after the registered_fairies check
    serial_succeeded(name, directory, inst, boot_ok, publish)
                                               after registered_fairies.append("AssociationCortexFairy"): stamps the
                                               directory record's STATUS running (only that; see THE STAMP below), on the
                                               main thread BEFORE the BootWave thread starts, so GoBoot cannot build a third
                                               copy. boot_ok is what cortex.boot() returned.
    serial_failed(name, publish)               in both except clauses of the serial block

THE SWITCH: state/k2_serial_owned.json {"on": true}, read ONCE per process (it decides a boot-time race; flipping it mid-boot
  could not undo a copy that already exists). An optional "names" list is intersected with ALLOWED. A missing file, a file that
  does not parse (a BOM included), "on" anything but JSON true, or any error = OFF = today's behaviour exactly; the only
  difference OFF makes is one "[Server] [K2] serial-owned: OFF" log line. Revert: delete the file and reboot.

THE FLOOR (card a-bound-that-can-return-nothing-is-a-kill-switch): the worst case is today's TWO cortexes, never zero.
  (a) nothing is skipped until A has started, so a missing or failed serial path can never starve the cascade;
  (b) if A fails after a skip, the cascade is asked again exactly once (boot.fairy.request {"k2_fallback": true}). "Fails"
      means an exception out of the serial block (serial_failed). In her bytes that is the ONLY way: the Organ Template's
      boot() RE-RAISES an on_boot exception (Organ_Template_0_3_0.py:3696-3699 sets result False, :3789-3791 raises it) and
      AssociationCortexFairy.on_boot never returns False. cortex.boot() returning an explicit False (serial_succeeded with
      boot_ok False) is kept as a defence that her bytes cannot produce today (verify_safety F4); it costs nothing;
  (c) any error inside this module = no skip.
  Not covered (held, BUILD_14b.md): a serial build that HANGS. A runs on the main thread, so a hang stops her whole boot
  either way; no watchdog is added.
THE STAMP (verify_safety F1, fix round 10-14 evening): status only, never metadata["fairy_instance"]. The postal fairy.register
  handler (directory/handlers/registration.py:74-86) REPLACES the record with a fresh one (status "running", no instance), so in
  Boots M and N no cortex instance survived to the shutdown route: 0 cortex on_shutdown lines in both. An instance written here
  would survive whenever the register lands BEFORE the stamp (a postal race), and Phase 4 (server.py P30, 30 s cap, non-daemon
  thread) would then run the serial cortex's on_shutdown for the first time in her history: a 128-card chunk sync from graph
  dicts on_boot cleared. Status "running" from EITHER writer (this stamp or the register) keeps GoBoot off, and the cascade
  handler's directory check skips on status alone (server.py "status=... (no instance), skipping"). So the shutdown route stays
  today's in every order. A graceful serial-cortex shutdown, if wanted, is its own measured step (a Phase-4 P30 gate).
Stdlib only. ASCII prints only. Never raises.
"""
import json
import os
import threading

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWITCH_FILE = os.path.join(_ROOT, "state", "k2_serial_owned.json")
DEFAULT_NAMES = frozenset({"AssociationCortexFairy"})
ALLOWED = frozenset({"AssociationCortexFairy"})       # the census's 8 other serial/cascade pairs are a later decision

_LOCK = threading.Lock()
_OWNED = None                  # frozenset after the first read (once per process)
_STARTED = set()               # names builder A has started and not yet failed
_SUCCEEDED = set()             # names builder A has finished with boot() not False
_SKIPPED = {}                  # name -> cascade requests skipped
_FALLBACK_SENT = set()         # names whose single fallback request has been published
_HOOK = None                   # test seam only: called inside the lock between the check and the record


def _say(msg):
    try:
        print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)
    except Exception:
        pass


def _read_switch(path=None):
    """The owned names, or an empty frozenset (= OFF). Never raises."""
    try:
        with open(path or SWITCH_FILE, "rb") as f:
            d = json.loads(f.read().decode("utf-8"))
    except Exception:
        return frozenset()
    try:
        if not isinstance(d, dict) or d.get("on") is not True:
            return frozenset()
        names = d.get("names")
        if names is None:
            return DEFAULT_NAMES & ALLOWED
        if not isinstance(names, list):
            return frozenset()
        return frozenset(n for n in names if isinstance(n, str) and n in ALLOWED)
    except Exception:
        return frozenset()


def owned():
    """The names the serial block owns this process (read once). Empty = OFF."""
    global _OWNED
    try:
        o = _OWNED
        if o is None:
            with _LOCK:
                if _OWNED is None:
                    _OWNED = _read_switch()
                o = _OWNED
        return o
    except Exception:
        return frozenset()


def describe():
    o = owned()
    if not o:
        return "OFF (state/k2_serial_owned.json absent or not {\"on\": true}: today's behaviour)"
    return "ON for %s (the cascade skips a cortex the serial block has started; floor: one re-request if it fails)" % (
        ",".join(sorted(o)))


def is_fallback(name, payload):
    """True only for the floor's own re-request, which this module published."""
    try:
        return (isinstance(payload, dict) and payload.get("k2_fallback") is True
                and isinstance(name, str) and name in _FALLBACK_SENT)
    except Exception:
        return False


def serial_started(name):
    """Builder A has begun. A no-op when OFF."""
    try:
        if name in owned():
            with _LOCK:
                _STARTED.add(name)
                _SUCCEEDED.discard(name)
    except Exception:
        pass


def cascade_should_skip(name, payload):
    """True = the cascade must NOT build this fairy (A owns it and has started). Any doubt = False (today)."""
    try:
        if not isinstance(name, str) or name not in owned():
            return False
        if is_fallback(name, payload):
            return False
        with _LOCK:
            started = name in _STARTED
            if _HOOK is not None:
                _HOOK("between_check_and_record")
            if started:
                _SKIPPED[name] = _SKIPPED.get(name, 0) + 1
        if started:
            _say("[K2] %s owned by serial boot (started), cascade copy skipped" % name)
            return True
        _say("[K2] %s cascade request before serial start: not skipped (today's path)" % name)
        return False
    except Exception:
        return False


def _floor(name, publish, why):
    """A did not produce a working cortex: forget that it started (later requests are not skipped) and, if a cascade
    request WAS skipped, ask the cascade again exactly once. Returns True if the fallback request was published."""
    with _LOCK:
        _STARTED.discard(name)
        _SUCCEEDED.discard(name)
        need = _SKIPPED.get(name, 0) > 0 and name not in _FALLBACK_SENT
        if need:
            _FALLBACK_SENT.add(name)
    if not need:
        _say("[K2] %s serial boot %s; no cascade request was skipped, nothing to re-ask" % (name, why))
        return False
    if publish is None:
        _say("[K2] %s serial boot %s after a skip and there is no fabric to re-ask the cascade" % (name, why))
        return False
    publish("boot.fairy.request", {"fairy_name": name, "gate": "k2_fallback", "boot_id": "k2_fallback",
                                   "k2_fallback": True})
    _say("[K2] %s serial boot %s after a skip: the cascade was asked again once (floor)" % (name, why))
    return True


def serial_succeeded(name, directory, instance, boot_ok=None, publish=None):
    """Builder A returned from its build. When owned: stamp the directory record's status "running" (ONLY the status: see THE
    STAMP in the module docstring; `instance` is accepted and deliberately not written), so GoBoot's scan
    (boot_orchestrator.py:1005 boots only 'sleeping' records) sees the cortex alive. If boot_ok is an explicit False, run the
    floor too (a defence; her template re-raises instead). Returns True if stamped."""
    try:
        if name not in owned():
            return False
        stamped = False
        if directory is None:
            _say("[K2] %s serial boot done; no directory to stamp" % name)
        else:
            rec = directory.get_fairy(name)
            if rec is None:
                _say("[K2] %s serial boot done; no directory record to stamp (GoBoot boots only records it finds)" % name)
            else:
                rec.status = "running"
                stamped = True
                _say("[K2] %s serial boot done: directory record stamped running, status only (one cortex; no instance, so "
                     "the shutdown route is today's)" % name)
        if boot_ok is False:
            _floor(name, publish, "returned False from boot() (an explicit False; her template re-raises instead)")
        else:
            with _LOCK:
                _SUCCEEDED.add(name)
        return stamped
    except Exception as e:
        _say("[K2] %s directory stamp failed (%s); GoBoot is still kept off by the cortex's own fairy.register" % (
            name, type(e).__name__))
        return False


def serial_failed(name, publish):
    """Builder A raised out of the serial block. Run the floor. Returns True if the fallback request was published."""
    try:
        if name not in owned():
            return False
        with _LOCK:
            done = name in _SUCCEEDED
        if done:
            _say("[K2] %s serial block raised after the cortex was registered; nothing to re-ask" % name)
            return False
        return _floor(name, publish, "FAILED")
    except Exception as e:
        _say("[K2] %s fallback re-request failed (%s)" % (name, type(e).__name__))
        return False


def stats():
    """For tests and status lines."""
    try:
        o = sorted(owned())                     # outside the lock: owned() may take it (the lock is not re-entrant)
        with _LOCK:
            return {"owned": o, "started": sorted(_STARTED), "succeeded": sorted(_SUCCEEDED),
                    "skipped": dict(_SKIPPED), "fallback_sent": sorted(_FALLBACK_SENT)}
    except Exception:
        return {}
