"""recall_eyes_fix.py -- Ace's switch + the small shared parts for recall_eyes_1020. 2026-10-20 (Nous, nous_builds/recall_eyes_1020).

WHAT THIS IS. Seven independent keys, each OFF by default, read live from state/recall_eyes_fix.json:
    recall_newest_first           sequence_weave.recall_lines reads EVERY PART_OF neighbour (not the first 40 by edge slot) and drops
                                  excluded speakers (Nous) before counting. Same neighbours are already read; only the slice changes.
    skip_self                     a caller that passes answering=<the message> gets THIS boot's Ace turns whose text equals it (or one
                                  " ... " piece of a joined message) left out of its own memory slot. The remember deed passes nothing.
    retire_stale_memory_msg       sourpatches_fairy._local_reflection: when the 15 s guild wait returns nothing, none of the 21 fallback
                                  templates is chosen (they claim lost memory / offline). An empty exchange is recorded in the in-memory
                                  dialogue context and ONE line is printed. A guild answer is untouched.
    eyes_reader_decouple          visual_cortex_gate._read_loop hands passive frames to ONE worker through a 4-slot drop-oldest queue, so
                                  the reader keeps draining the interior's pipe whatever the frame handler does.
    reader_survives               the same reader skips a valid-JSON line that is not an object (it dies on one today) and says out loud
                                  when it exits.
    passive_spread_single_flight  VisualCortexFairy._on_passive_frame: at most ONE spread_many in flight from the eyes site.
    interior_mmap_first           visual_cortex_interior: the shared frame is written BEFORE the pipe line, and the line goes through a
                                  bounded sender thread (takes effect at the next interior spawn).
No key writes, deletes or re-weights a stored memory (Ace 10-20: "im never ok with editing memories or personality").

OFF BY DEFAULT. Absent / unreadable / a BOM / torn / not an object = every key OFF = today's code path. Only a JSON true arms a key
("true", 1, null, NaN, Infinity do not). An unknown key or a non-boolean value gets one note line; the other keys still count.
The module itself is never imported for its side effects: nothing is printed or started at import.

ONE ANCHOR PER PROCESS. All process-wide state (the switch cache, the output stream, the flight locks, the rate limits) lives in ONE object
on the sys module: vars(sys).setdefault is atomic under -Xgil=0, and the state survives a hot reload of this file.
The switch reader never waits: at most one thread refreshes the cache (it only TRIES the lock); everyone else uses the cached set.
STDLIB ONLY and Python 3.12-compatible: the visual interior (3.12, PYTHONPATH = her root) imports this file too. ASCII only (her console is cp1252).
In the interior stdout is the IPC pipe: the interior calls configure(sys.stderr) before its first on().
"""
import collections
import json
import os
import sys
import threading
import time

NAME = "_akashic_recall_eyes_fix_v1"
SWITCH_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state", "recall_eyes_fix.json")
KEYS = ("recall_newest_first", "skip_self", "retire_stale_memory_msg", "eyes_reader_decouple", "reader_survives",
        "passive_spread_single_flight", "interior_mmap_first")
KEYSET = frozenset(KEYS)
_EMPTY = frozenset()

RECHECK_S = 1.0          # the switch file is stat'ed at most this often ...
REREAD_S = 10.0          # ... and re-read when it changed, or at least this often
HANDOFF_MAXLEN = 4       # the gate hand-off: frames kept (the newest always survives; K >= 1)
HANDOFF_WEDGE_S = 30.0   # the worker busy longer than this is called out ...
HANDOFF_BUSY_SAY_S = 300.0   # ... at most this often
HANDOFF_SUMMARY_S = 600.0    # the "so far" line (received / processed / dropped), so the denominator is always in the log
SENDER_MAXLEN = 2        # the interior's passive line sender
FLIGHT_WEDGE_S = 30.0    # a flight held longer than this is called out ...
FLIGHT_SAY_S = 300.0     # ... at most this often


def _now():
    """The clock every wait / age / rate limit reads. A seam for the tests."""
    return time.monotonic()


# ============================================================================================================================ the anchor
class _Anchor(object):
    """Everything shared by the module objects of ONE process. Leaf locks never nest."""

    def __init__(self):
        self.sw = None                        # (armed frozenset, checked_at, sig, read_at) -- one reference, replaced whole
        self.sw_notes = ()
        self.sw_lock = threading.Lock()       # only ever TRIED, never waited for
        self.out = None                       # configure(stream); None = sys.stdout at the moment of printing
        self.say_t = {}
        self.say_lock = threading.Lock()
        self.flights = {}


def _anchor():
    a = getattr(sys, NAME, None)
    if a is None:
        a = vars(sys).setdefault(NAME, _Anchor())      # atomic: the first creator wins, every later caller gets the same object
    return a


def configure(stream=None):
    """Where this module's lines go. None = sys.stdout (resolved at the moment of printing). The interior passes sys.stderr."""
    try:
        _anchor().out = stream
    except Exception:
        pass


def _emit(line):
    """One ASCII line to the configured stream. Never raises."""
    try:
        st = _anchor().out or sys.stdout
        st.write(str(line).encode("ascii", "replace").decode("ascii") + "\n")
        st.flush()
    except Exception:
        pass


def say(key, msg, every=300.0):
    """msg, at most once per `every` seconds per key. -> True when printed. Never raises."""
    try:
        a = _anchor()
        now = _now()
        with a.say_lock:
            last = a.say_t.get(key)
            if last is not None and now - last < every:
                return False
            a.say_t[key] = now
        _emit(msg)
        return True
    except Exception:
        return False


def reset_for_tests():
    """Drops the anchor (a fresh process state). Tests only."""
    try:
        vars(sys).pop(NAME, None)
    except Exception:
        pass


# ============================================================================================================================ the switch
def parse(data):
    """Pure. The bytes of the switch file (or None) -> (frozenset of ARMED keys, [notes]). Strict utf-8 (a BOM fails json), a JSON object
    only, and each key is judged on its own: only JSON true arms it."""
    notes = []
    if data is None:
        return _EMPTY, notes
    try:
        d = json.loads(bytes(data).decode("utf-8"))
    except Exception as e:
        return _EMPTY, ["the file does not parse (%s): every key OFF" % type(e).__name__]
    if not isinstance(d, dict):
        return _EMPTY, ["the file is not a JSON object: every key OFF"]
    armed = set()
    for k, v in d.items():
        if k not in KEYSET:
            notes.append("unknown key %s: ignored" % ascii(str(k))[:40])
        elif v is True:
            armed.add(k)
        elif v is not False:
            notes.append("%s is not JSON true or false: OFF" % k)
    return frozenset(armed), notes


def describe(armed):
    if not armed:
        return "OFF (every key off = today)"
    return "ARMED: " + " ".join(k for k in KEYS if k in armed)


def _stat_sig():
    try:
        st = os.stat(SWITCH_FILE)
        return (st.st_mtime_ns, st.st_size)
    except Exception:
        return None


def _read_file():
    try:
        with open(SWITCH_FILE, "rb") as f:
            return f.read()
    except Exception:
        return None


def switch():
    """The armed set (a frozenset of key names). Never raises, never waits. At most once a second it stats the file (one thread does, and
    only if it can take the lock without waiting; the others keep using the last value), and re-reads when (mtime_ns, size) changed or every
    REREAD_S. A transient read error keeps the last value. A change of the armed set prints one line."""
    try:
        a = _anchor()
        cur = a.sw
        now = _now()
        if cur is not None and now - cur[1] < RECHECK_S:
            return cur[0]
        if not a.sw_lock.acquire(False):
            return cur[0] if cur is not None else _EMPTY
        try:
            cur = a.sw
            now = _now()
            if cur is not None and now - cur[1] < RECHECK_S:
                return cur[0]
            sig = _stat_sig()
            if cur is not None and sig == cur[2] and now - cur[3] < REREAD_S:
                a.sw = (cur[0], now, cur[2], cur[3])
                return cur[0]
            if sig is None:
                armed, notes = _EMPTY, []
            else:
                data = _read_file()
                if data is None:
                    keep = cur[0] if cur is not None else _EMPTY       # present but unreadable this time: keep the last value
                    a.sw = (keep, now, ("unread",), now)
                    return keep
                armed, notes = parse(data)
            notes = tuple(notes)
            a.sw = (armed, now, sig, now)
            changed = (armed != _EMPTY) if cur is None else (armed != cur[0])
            if changed or notes != a.sw_notes:
                a.sw_notes = notes
                if changed or notes:
                    _emit("[RecallEyesFix] switch: " + describe(armed))
                    for n in notes:
                        _emit("[RecallEyesFix]   note: " + n)
            return armed
        finally:
            a.sw_lock.release()
    except Exception:
        try:
            cur = _anchor().sw
            return cur[0] if cur is not None else _EMPTY
        except Exception:
            return _EMPTY


def on(key):
    """One key of Ace's switch; OFF on any doubt."""
    try:
        return key in switch()
    except Exception:
        return False


# ============================================================================================================================ the hand-off
class Handoff(object):
    """A bounded, drop-oldest hand-off between ONE producer thread (the gate's reader) and ONE worker thread.

    put(data)  producer only. Never waits, never takes a lock the worker can hold: deque(maxlen) evicts the OLDEST atomically, then an Event.
    worker     exactly one thread: wait(1.0), clear, then popleft until empty -- that order loses no wake-up. It calls deliver(d) per frame
               (the caller resolves the callback per frame). An exception from deliver is counted and the worker goes on.
    floor      the newest frame always survives (maxlen >= 1); a deliver that keeps up drops nothing.
    counters   every counter has ONE writer: received (producer); taken, processed, errors, busy_since (worker). dropped is DERIVED
               (received - taken - depth), so there is no check-then-act; at quiescence received == taken + dropped + depth.
    visibility a busy line at most every busy_say_s after wedge_s of busy, and a "so far" line every summary_s. With flight_name, status() and
               the "so far" line also carry that single-flight guard's held_s / runs / skips (read only; absent while the flight was never created).
    """

    def __init__(self, deliver, maxlen=HANDOFF_MAXLEN, name="vgate-passive", wedge_s=HANDOFF_WEDGE_S, summary_s=HANDOFF_SUMMARY_S,
                 busy_say_s=HANDOFF_BUSY_SAY_S, log=None, clock=None, flight_name=None):
        self._deliver = deliver
        self.maxlen = max(1, int(maxlen))
        self.name = name
        self.flight_name = flight_name
        self.wedge_s = float(wedge_s)
        self.summary_s = float(summary_s)
        self.busy_say_s = float(busy_say_s)
        self._log = log or _emit
        self._clock = clock or _now
        self.q = collections.deque(maxlen=self.maxlen)
        self.evt = threading.Event()
        self.stopped = False
        self.received = 0                  # producer
        self.taken = 0                     # worker
        self.processed = 0                 # worker
        self.errors = 0                    # worker
        self.busy_since = 0.0              # worker (0 = idle)
        self.respawns = 0                  # producer
        self._busy_say_t = -1e18           # producer
        self._summary_t = self._clock()    # producer
        self._spawn_lock = threading.Lock()
        self._thread = None
        self._ensure_worker()

    # -- worker ------------------------------------------------------------------------------------------------------------
    def _ensure_worker(self):
        if self.stopped:
            return
        if not self._spawn_lock.acquire(False):
            return
        try:
            t = self._thread
            if t is None or not t.is_alive():
                t = threading.Thread(target=self._run, daemon=True, name=self.name)
                self._thread = t
                t.start()
        finally:
            self._spawn_lock.release()

    def _run(self):
        while not self.stopped:
            self.evt.wait(1.0)
            self.evt.clear()
            while not self.stopped:
                try:
                    d = self.q.popleft()
                except IndexError:
                    break
                self.taken += 1
                self.busy_since = self._clock()
                try:
                    self._deliver(d)
                    self.processed += 1
                except Exception as e:
                    self.errors += 1
                    if self.errors <= 3:
                        try:
                            self._log("[VisualGate] Passive callback error: %s" % ascii(str(e))[:160])
                        except Exception:
                            pass
                finally:
                    self.busy_since = 0.0

    # -- producer ----------------------------------------------------------------------------------------------------------
    def put(self, data):
        """Producer thread only. Never raises, never waits. -> True when the frame was queued."""
        try:
            self.received += 1
            self.q.append(data)
            self.evt.set()
            t = self._thread
            if (t is None or not t.is_alive()) and not self.stopped:      # the worker died (a BaseException): replace it, loudly
                self.respawns += 1
                self._ensure_worker()
                self._log("[VisualGate] passive hand-off: the worker thread was gone and has been replaced (%d so far)" % self.respawns)
            now = self._clock()
            bs = self.busy_since
            if bs and now - bs > self.wedge_s and now - self._busy_say_t >= self.busy_say_s:
                self._busy_say_t = now
                self._log("[VisualGate] passive hand-off: the frame handler has been busy %.0f s; frames dropped so far %d "
                          "(the pipe is still drained)" % (now - bs, self.dropped()))
            if now - self._summary_t >= self.summary_s:
                self._summary_t = now
                self._log(self.summary_line())
            return True
        except Exception:
            return False

    # -- reading -----------------------------------------------------------------------------------------------------------
    def depth(self):
        return len(self.q)

    def dropped(self):
        return max(0, self.received - self.taken - len(self.q))

    def summary_line(self):
        s = self.status()
        line = ("[VisualGate] passive hand-off so far: received=%d processed=%d dropped=%d errors=%d depth=%d busy_s=%.0f"
                % (s["received"], s["processed"], s["dropped"], s["errors"], s["depth"], s["busy_s"]))
        fs = s.get("eyes_spread_flight")
        if fs is not None:
            line += " | eyes_spread_flight held_s=%.0f runs=%d skips=%d" % (fs["held_s"], fs["runs"], fs["skips"])
        return line

    def status(self):
        r, t, depth, bs = self.received, self.taken, len(self.q), self.busy_since
        st = {"received": r, "taken": t, "processed": self.processed, "errors": self.errors, "depth": depth,
              "dropped": max(0, r - t - depth), "busy_s": round(self._clock() - bs, 1) if bs else 0.0,
              "stopped": self.stopped, "respawns": self.respawns, "maxlen": self.maxlen}
        if self.flight_name:
            fs = flight_status(self.flight_name)
            if fs is not None:
                st["eyes_spread_flight"] = fs
        return st

    def stop(self):
        """The worker exits at its next wake. A worker wedged inside deliver is a daemon: it dies with the process."""
        self.stopped = True
        self.evt.set()

    def join(self, timeout=2.0):
        t = self._thread
        if t is not None:
            t.join(timeout)
            return not t.is_alive()
        return True


# ============================================================================================================================ single flight
_FLIGHT_MSG = {"vcf_passive_spread": "[VisualCortexFairy] eyes spread still in flight after %.0f s; %d spreads skipped"}


class _Flight(object):
    """At most one holder. enter() is a non-blocking try-acquire (no check-then-act); leave() releases it (any thread may)."""

    def __init__(self, name):
        self.name = name
        self._lock = threading.Lock()
        self.runs = 0                      # approximate: cosmetic
        self.skips = 0                     # approximate: cosmetic
        self._since = 0.0

    def enter(self):
        if self._lock.acquire(False):
            self._since = _now()
            self.runs += 1
            return True
        self.skips += 1
        try:
            since = self._since
            if since:                          # 0.0 = a holder between its acquire and its stamp, or just released: nothing to call out
                held = _now() - since
                if held > FLIGHT_WEDGE_S:
                    tmpl = _FLIGHT_MSG.get(self.name, "[RecallEyesFix] flight '%s' still held after %.0f s; %d skipped")
                    msg = (tmpl % (held, self.skips)) if self.name in _FLIGHT_MSG else (tmpl % (self.name, held, self.skips))
                    say("flight:" + self.name, msg, FLIGHT_SAY_S)
        except Exception:
            pass
        return False

    def leave(self):
        """The holder only. The stamp is cleared BEFORE the release, so a skipper never reads the previous holder's stamp."""
        try:
            self._since = 0.0
            self._lock.release()
        except Exception:
            pass

    def held_s(self):
        since = self._since
        return (_now() - since) if (since and self._lock.locked()) else 0.0


def flight_status(name):
    """READ ONLY: {"held_s", "runs", "skips"} of the flight called `name`, or None when it was never created (its key never armed). Never creates one."""
    try:
        f = _anchor().flights.get(name)
        if f is None:
            return None
        return {"held_s": round(f.held_s(), 1), "runs": f.runs, "skips": f.skips}
    except Exception:
        return None


def flight(name):
    """The process-wide single-flight guard called `name` (created once; dict.setdefault is atomic)."""
    a = _anchor()
    f = a.flights.get(name)
    if f is None:
        f = a.flights.setdefault(name, _Flight(name))
    return f


# ============================================================================================================================ line sender
class LineSender(object):
    """A bounded, drop-oldest sender for ready-made lines (the interior's passive frames). offer() never waits: deque(maxlen) evicts the oldest.
    ONE sender thread (started on the first offer) calls write_line(line) for each line; an exception from write_line is counted and logged
    (log(msg), first 3) and the thread goes on. A write_line blocked in a full pipe blocks only that thread."""

    def __init__(self, write_line, maxlen=SENDER_MAXLEN, name="visual-passive-send", log=None):
        self._write = write_line
        self._log = log
        self.name = name
        self.q = collections.deque(maxlen=max(1, int(maxlen)))
        self.evt = threading.Event()
        self.stopped = False
        self.offered = 0
        self.sent = 0
        self.errors = 0
        self._start_lock = threading.Lock()
        self._thread = None

    def offer(self, line):
        try:
            self.offered += 1
            self.q.append(line)
            self.evt.set()
            t = self._thread
            if t is None or not t.is_alive():
                self._ensure()
            return True
        except Exception:
            return False

    def _ensure(self):
        if self.stopped or not self._start_lock.acquire(False):
            return
        try:
            t = self._thread
            if t is None or not t.is_alive():
                t = threading.Thread(target=self._run, daemon=True, name=self.name)
                self._thread = t
                t.start()
        finally:
            self._start_lock.release()

    def _run(self):
        while not self.stopped:
            self.evt.wait(1.0)
            self.evt.clear()
            while not self.stopped:
                try:
                    line = self.q.popleft()
                except IndexError:
                    break
                try:
                    self._write(line)
                    self.sent += 1
                except Exception as e:
                    self.errors += 1
                    if self.errors <= 3 and self._log is not None:
                        try:
                            self._log("passive line not sent: %s" % ascii(str(e))[:160])
                        except Exception:
                            pass

    def depth(self):
        return len(self.q)

    def stop(self):
        self.stopped = True
        self.evt.set()

    def join(self, timeout=2.0):
        t = self._thread
        if t is not None:
            t.join(timeout)
            return not t.is_alive()
        return True
