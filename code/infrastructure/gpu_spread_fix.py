"""gpu_spread_fix.py -- guards for GPUSpread: ONE graph build, BOUNDED spreads. 2026-10-20 (Nous, nous_builds/gpu_spread_race_1020).

WHY. Boot W built 15 copies of the cortex graph on the GPU (1 + 5 + 9 across two processes) and 97 threads sat inside GPUSpread.spread
for 164+ s without one of them moving (READ.md section 8.1). The lazy build in gpu_spread.py has no lock; nothing bounds how many spreads
run at once. This module holds the guards. gpu_spread.py (the build lock, the slots, the VRAM floor, the shared graph), portal_gate.py and
wmh_tools.py (wm_query_no_spread, the degraded marker) call into it. It does NOT import torch.

OFF BY DEFAULT. Every guard is armed only by state/gpu_spread_fix.json. Absent / unreadable / a BOM / torn / not an object = every guard
OFF = today's code path, byte for byte. The reader is K4's (portal_gate.py _k4_inject_on): strict utf-8, so a BOM fails json and reads OFF.
KEYS (only a JSON true arms a boolean; a number must be a finite JSON number, never a bool):
    build_lock          true     one build per GPUSpread instance (double-checked); also the CPU->GPU migration, the affect refresh and the
                                 sticky-CPU latch
    spread_slots        int>=1   at most N spreads at once PER PROCESS (capped at 16); waits are bounded by timeout_s
    timeout_s           number   how long a caller waits for a slot or a build: clamped to [0.5, 30], default 5. Never None, never infinite
    vram_floor_mb       number   needs build_lock: no new GPU copy while NVML free < copy + floor (clamped [256, 4096]); fails OPEN when
                                 free VRAM cannot be read; after vram_patience_s of continuous refusal ONE build is allowed (a cold build
                                 and a CPU->GPU migration each have their own patience clock)
    vram_patience_s     number   clamped [30, 1800], default 180
    shared_graph        true     needs build_lock: instances that loaded identical CSR bytes with the same manifold share ONE GPU graph
    wm_query_no_spread  true     LocalManifoldGate / PortalGate wm_query(spread=True) skips its per-key spread. Its returned product,
                                 'convergence', is read by nobody (READ.md section 5.2). On the interior path (and the gate's CPU fallback)
                                 the skipped spread is ManifoldMemory.spread_activation, whose tail also TOUCHES (activation + last_access)
                                 up to 15 returned nodes per key: that small reinforcement goes too (review F2, 10-20)
NO GUARD EVER RAISES AND NONE EVER BLOCKS FOREVER. A caller that cannot get a slot or a graph gets a DEGRADED result (status ok, nothing
activated, device 'degraded'), counted and logged, never a CPU fallback. Every guard function wraps its whole body in try/except Exception and
answers today's (unguarded) choice on an internal failure: tested for every internal seam (C9, strict: never a degraded result); a
BaseException escaping a guard is not tested (by construction only).

ONE ANCHOR PER PROCESS. In main, gpu_spread is imported under two module names (portal_gate.py:196 `gpu_spread`, wmh_tools.py:85
`infrastructure.gpu_spread`), so module globals would exist twice. All shared state (the semaphore, the holders, the counters, the switch
cache, the shared-graph registry) lives in ONE object on the sys module: vars(sys).setdefault is atomic under -Xgil=0.
LOCK ORDER: slot permit, then the instance build lock, then a shared-graph key lock, then the leaf locks below. The reader's own lock is
only ever tried without waiting. Every wait has a timeout.
ASCII only (her console is cp1252).
"""
import json
import math
import os
import sys
import threading
import time

NAME = "_akashic_gpu_spread_fix_v1"
SWITCH_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state", "gpu_spread_fix.json")

DEFAULT_TIMEOUT_S = 5.0
TIMEOUT_MIN, TIMEOUT_MAX = 0.5, 30.0
SLOTS_MAX = 16
FLOOR_MIN, FLOOR_MAX = 256.0, 4096.0
PATIENCE_MIN, PATIENCE_MAX, PATIENCE_DEFAULT = 30.0, 1800.0, 180.0
WEDGE_S = 30.0          # a permit (or a build) held longer than this is a wedge: the breaker stops callers from waiting for it
RECHECK_S = 1.0         # the switch file is stat'ed at most this often ...
REREAD_S = 10.0         # ... and re-read when it changed, or at least this often
SUMMARY_S = 600.0       # the "so far" line
RATE_S = 60.0           # one line per reason per this many seconds
MIGRATE_RETRY_S = 5.0   # a refused / lost CPU->GPU migration is retried at most this often (used by gpu_spread.py)
HIST_EDGES_S = (0.01, 0.1, 1.0)


def _now():
    """The clock every wait / age / rate limit reads. A seam for the tests."""
    return time.monotonic()


# ============================================================================================================================ the switch
class Fx(object):
    """One parsed switch. Never written after construction."""
    __slots__ = ("build_lock", "spread_slots", "timeout_s", "vram_floor_mb", "vram_patience_s", "shared_graph",
                 "wm_query_no_spread", "armed", "spread_armed", "key")

    def __init__(self, build_lock=False, spread_slots=None, timeout_s=DEFAULT_TIMEOUT_S, vram_floor_mb=None,
                 vram_patience_s=PATIENCE_DEFAULT, shared_graph=False, wm_query_no_spread=False):
        self.build_lock = bool(build_lock)
        self.spread_slots = spread_slots
        self.timeout_s = float(timeout_s)
        self.vram_floor_mb = vram_floor_mb
        self.vram_patience_s = float(vram_patience_s)
        self.shared_graph = bool(shared_graph)
        self.wm_query_no_spread = bool(wm_query_no_spread)
        self.spread_armed = bool(self.build_lock or self.spread_slots is not None)    # what gpu_spread.spread acts on
        self.armed = bool(self.spread_armed or self.wm_query_no_spread)                # any guard at all
        self.key = (self.build_lock, self.spread_slots, self.timeout_s, self.vram_floor_mb, self.vram_patience_s,
                    self.shared_graph, self.wm_query_no_spread)

    def describe(self):
        if not self.armed:
            return "OFF (every guard off = today)"
        parts = []
        if self.build_lock:
            parts.append("build_lock")
        if self.spread_slots is not None:
            parts.append("spread_slots=%d" % self.spread_slots)
        if self.build_lock or self.spread_slots is not None:
            parts.append("timeout_s=%g" % self.timeout_s)
        if self.vram_floor_mb is not None:
            parts.append("vram_floor_mb=%g vram_patience_s=%g" % (self.vram_floor_mb, self.vram_patience_s))
        if self.shared_graph:
            parts.append("shared_graph")
        if self.wm_query_no_spread:
            parts.append("wm_query_no_spread")
        return "ARMED: " + " ".join(parts)


OFF = Fx()


def _num(v):
    """A finite JSON number as a float, else None. A bool is not a number; NaN / Infinity (which Python's json accepts) are not numbers."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        f = float(v)
    except (OverflowError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


def _clamp(f, lo, hi):
    return max(lo, min(hi, f))


def parse(data):
    """Pure. The bytes of the switch file (or None) -> (Fx, [notes]). Strict utf-8 (a BOM fails json), JSON object only, and each key is
    judged on its own: a bad value turns THAT key off (a note says so); a file that is not a JSON object turns everything off."""
    notes = []
    if data is None:
        return OFF, notes
    try:
        d = json.loads(bytes(data).decode("utf-8"))
    except Exception as e:
        return OFF, ["the file does not parse (%s): every guard OFF" % type(e).__name__]
    if not isinstance(d, dict):
        return OFF, ["the file is not a JSON object: every guard OFF"]
    build_lock = d.get("build_lock") is True
    if "build_lock" in d and d["build_lock"] is not False and not build_lock:
        notes.append("build_lock is not JSON true: OFF")
    slots = None
    if "spread_slots" in d:
        v = d["spread_slots"]
        if type(v) is int and v >= 1:
            slots = min(v, SLOTS_MAX)
        else:
            notes.append("spread_slots is not an integer >= 1: OFF")
    timeout = DEFAULT_TIMEOUT_S
    if "timeout_s" in d:
        f = _num(d["timeout_s"])
        if f is not None and f > 0:
            timeout = _clamp(f, TIMEOUT_MIN, TIMEOUT_MAX)
        else:
            notes.append("timeout_s is not a finite number > 0: default %g" % DEFAULT_TIMEOUT_S)
    floor = None
    if "vram_floor_mb" in d:
        f = _num(d["vram_floor_mb"])
        if f is None or f <= 0:
            notes.append("vram_floor_mb is not a finite number > 0: OFF")
        elif not build_lock:
            notes.append("vram_floor_mb needs build_lock: ignored")
        else:
            floor = _clamp(f, FLOOR_MIN, FLOOR_MAX)
    patience = PATIENCE_DEFAULT
    if "vram_patience_s" in d:
        f = _num(d["vram_patience_s"])
        if f is not None and f > 0:
            patience = _clamp(f, PATIENCE_MIN, PATIENCE_MAX)
        else:
            notes.append("vram_patience_s is not a finite number > 0: default %g" % PATIENCE_DEFAULT)
    shared = d.get("shared_graph") is True
    if "shared_graph" in d and d["shared_graph"] is not False and not shared:
        notes.append("shared_graph is not JSON true: OFF")
    elif shared and not build_lock:
        notes.append("shared_graph needs build_lock: ignored")
        shared = False
    no_spread = d.get("wm_query_no_spread") is True
    if "wm_query_no_spread" in d and d["wm_query_no_spread"] is not False and not no_spread:
        notes.append("wm_query_no_spread is not JSON true: OFF")
    return Fx(build_lock, slots, timeout, floor, patience, shared, no_spread), notes


# ============================================================================================================================ the anchor
class _Anchor(object):
    """Everything shared by the module objects of ONE process (see the header). Leaf locks never nest."""

    def __init__(self):
        self.lock = threading.Lock()          # counters, rate limits, histogram, summary clock
        self.c = {}
        self.say_t = {}
        self.hist = [0] * (len(HIST_EDGES_S) + 1)
        self.max_wait_ms = 0.0
        self.sum_t = None
        self.sw = None                        # (Fx, checked_at, sig, read_at) -- one reference, replaced whole
        self.sw_notes = ()
        self.sw_lock = threading.Lock()       # only ever tried without waiting
        self.sem = None
        self.sem_n = 0
        self.sem_warned = None
        self.sem_lock = threading.Lock()
        self.hold_lock = threading.Lock()
        self.holders = {}                     # id(slot) -> (thread name, monotonic time its permit was taken)
        self.tls = threading.local()          # .depth: how many slots this thread is inside (re-entry)
        self.reg_lock = threading.Lock()
        self.shared = {}                      # shared-graph key -> (src, dst, w)
        self.klocks = {}
        self.reader_mod = None


def _anchor():
    a = getattr(sys, NAME, None)
    if a is None:
        a = vars(sys).setdefault(NAME, _Anchor())      # atomic: the first creator wins, every later caller gets the same object
    return a


def _emit(line):
    try:
        sys.stderr.write(line.encode("ascii", "replace").decode("ascii") + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def say(key, msg, every=RATE_S):
    """`[GPUSpreadFix] msg`, at most once per `every` seconds per key. -> True when printed. Never raises."""
    try:
        a = _anchor()
        now = _now()
        with a.lock:
            last = a.say_t.get(key)
            if last is not None and now - last < every:
                return False
            a.say_t[key] = now
        _emit("[GPUSpreadFix] " + msg)
        return True
    except Exception:
        return False


def count(name, n=1):
    try:
        a = _anchor()
        with a.lock:
            a.c[name] = a.c.get(name, 0) + n
    except Exception:
        pass


def counts():
    try:
        a = _anchor()
        with a.lock:
            return dict(a.c)
    except Exception:
        return {}


def reset_for_tests():
    """Drops the anchor (a fresh process state). Tests only."""
    try:
        delattr(sys, NAME)
    except AttributeError:
        pass


# ============================================================================================================================ the switch reader
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
    """The current Fx. Never raises. At most once a second it stats the file (one thread does; the others keep using the last value and never
    wait), and re-reads when (mtime_ns, size) changed or every REREAD_S. The FIRST read of the process is the one exception to 'never wait':
    when 16 threads make their first spread at once, 15 of them must not be told OFF (that is the cold-build race this module exists to stop),
    so they wait for the first reader (a stat and a read of a tiny file) for at most 1 s, then read OFF. A change of the armed set prints one line."""
    try:
        a = _anchor()
        cur = a.sw
        now = _now()
        if cur is not None and now - cur[1] < RECHECK_S:
            return cur[0]
        if not (a.sw_lock.acquire(True, 1.0) if cur is None else a.sw_lock.acquire(False)):
            return cur[0] if cur is not None else OFF
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
                fx, notes = OFF, []
            else:
                data = _read_file()
                if data is None:
                    # the file is there but could not be read this time (a rename in flight, a sharing violation): keep the last value and
                    # look again in RECHECK_S -- a transient read error must not switch the guards OFF for REREAD_S
                    keep = cur[0] if cur is not None else OFF
                    a.sw = (keep, now, ("unread",), now)
                    return keep
                fx, notes = parse(data)
            notes = tuple(notes)
            a.sw = (fx, now, sig, now)
            first = cur is None
            changed = (fx.key != OFF.key) if first else (fx.key != cur[0].key)
            if changed or notes != a.sw_notes:
                a.sw_notes = notes
                if changed or notes:
                    _emit("[GPUSpreadFix] switch: " + fx.describe())
                    for n in notes:
                        _emit("[GPUSpreadFix]   note: " + n)
            return fx
        finally:
            a.sw_lock.release()
    except Exception:
        try:
            cur = _anchor().sw
            return cur[0] if cur is not None else OFF           # the last value we trusted, else OFF = today
        except Exception:
            return OFF


def on(key):
    """True only when `key` is a boolean guard that the file arms. Never raises."""
    try:
        return getattr(switch(), key, None) is True
    except Exception:
        return False


# ============================================================================================================================ counters / lines
def note_degraded(why):
    """Counts a degraded result and says so (one line per reason per minute, with the running total). Never raises. It also counts per
    THREAD (thread_degraded), so a caller that makes several spreads in one call can stop after the first degraded one."""
    try:
        try:
            tl = _anchor().tls
            tl.deg = getattr(tl, "deg", 0) + 1
        except Exception:
            pass
        count("degraded")
        count("degraded:" + str(why))
        total = counts().get("degraded:" + str(why), 0)
        say("deg:" + str(why), "degraded result (%s): %d so far; the caller got an empty ok, never the CPU path" % (why, total))
    except Exception:
        pass


def thread_degraded():
    """How many degraded results THIS thread has been handed so far, or None when no spread guard is armed (or on any failure).
    LocalManifoldGate.wm_query reads it before and after each per-key spread: once one spread of a call came back degraded, the
    remaining keys of that call skip theirs (review T6, 10-20: 9 keys x timeout_s = 45 s per call at saturation, now 1 x). Never raises."""
    try:
        if not switch().spread_armed:
            return None
        return getattr(_anchor().tls, "deg", 0)
    except Exception:
        return None


def on_call():
    """Every guarded spread: the denominator, and the 10-minute line."""
    try:
        count("call")
        a = _anchor()
        now = _now()
        fire = False
        with a.lock:
            if a.sum_t is None:
                a.sum_t = now
            elif now - a.sum_t >= SUMMARY_S:
                a.sum_t = now
                fire = True
        if fire:
            _emit(summary_line())
    except Exception:
        pass


def stats():
    """A plain dict (for GPUSpread.get_stats()['fix'] and the summary line)."""
    try:
        a = _anchor()
        with a.lock:
            c = dict(a.c)
            hist = list(a.hist)
            mw = a.max_wait_ms
        with a.hold_lock:
            held = [h for h in a.holders.values()]
            n = a.sem_n
        now = _now()
        oldest = max([now - h[1] for h in held]) if held else 0.0
        return {"switch": switch().describe(), "counters": c, "wait_hist": hist, "wait_hist_edges_s": list(HIST_EDGES_S),
                "max_slot_wait_ms": round(mw, 1), "held_now": len(held), "slots": n, "oldest_holder_s": round(oldest, 1)}
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, str(e)[:80])}


def summary_line():
    s = stats()
    c = s.get("counters", {})
    calls = c.get("call", 0)
    deg = c.get("degraded", 0)
    pct = ("%.2f%%" % (100.0 * deg / calls)) if calls else "n/a"
    return ("[GPUSpreadFix] so far: calls=%d degraded=%d (%s) slot_waits=%d slot_timeouts=%d breaker=%d builds=%d build_waited_ok=%d "
            "build_timeouts=%d build_wedged=%d migrations=%d vram_denied=%d vram_unknown=%d patience_builds=%d patience_migrations=%d "
            "shared_adopts=%d max_slot_wait_ms=%s held=%s/%s"
            % (calls, deg, pct, c.get("slot_wait", 0), c.get("slot_timeout", 0), c.get("breaker", 0), c.get("build", 0),
               c.get("build_wait_ok", 0), c.get("build_timeout", 0), c.get("build_wedged", 0), c.get("migration", 0),
               c.get("vram_denied", 0), c.get("vram_unknown", 0), c.get("patience_build", 0), c.get("patience_migration", 0),
               c.get("shared_adopt", 0), s.get("max_slot_wait_ms", 0), s.get("held_now", 0), s.get("slots", 0)))


def _record_wait(waited_s):
    try:
        a = _anchor()
        i = 0
        while i < len(HIST_EDGES_S) and waited_s >= HIST_EDGES_S[i]:
            i += 1
        with a.lock:
            a.hist[i] += 1
            a.max_wait_ms = max(a.max_wait_ms, waited_s * 1000.0)
    except Exception:
        pass


# ============================================================================================================================ the slots
def _get_sem(a, fx):
    n = max(1, int(fx.spread_slots))
    with a.sem_lock:
        if a.sem is None:
            a.sem = threading.BoundedSemaphore(n)
            a.sem_n = n
        elif n != a.sem_n and a.sem_warned != n:
            a.sem_warned = n
            _emit("[GPUSpreadFix] spread_slots=%d in the file; this process keeps %d until restart" % (n, a.sem_n))
        return a.sem


def _wedged(a):
    """-> (True, oldest (thread, t0)) when EVERY permit is held and every holder has held its permit longer than WEDGE_S: the breaker.
    Engages only then and disengages by itself at the first release (a smaller holders list)."""
    with a.hold_lock:
        hs = list(a.holders.values())
        n = a.sem_n
    if n <= 0 or len(hs) < n:
        return False, None
    now = _now()
    oldest = min(hs, key=lambda h: h[1])
    return all(now - h[1] > WEDGE_S for h in hs), oldest


class _Slot(object):
    """`with slot(fx) as (ok, why):` -- a permit for one spread, or (False, reason). The permit is recorded the moment it is taken and
    released in __exit__ whatever happened. If this class itself fails the caller gets (True, None): today's unbounded path."""
    __slots__ = ("fx", "sem", "held", "reentrant", "tls")

    def __init__(self, fx):
        self.fx = fx
        self.sem = None
        self.held = False
        self.reentrant = False
        self.tls = None

    def __enter__(self):
        try:
            return self._enter()
        except Exception as e:
            say("slot_fail", "the slot guard failed (%s: %s): this spread runs unguarded" % (type(e).__name__, str(e)[:80]))
            return (True, None)

    def _enter(self):
        a = _anchor()
        tls = self.tls = a.tls
        depth = getattr(tls, "depth", 0)
        if depth > 0:                                     # this thread already holds a permit (the latch's retry): no second one
            tls.depth = depth + 1
            self.reentrant = True
            return (True, None)
        fx = self.fx
        sem = _get_sem(a, fx)
        if sem.acquire(False):
            pass
        else:
            count("slot_wait")
            stuck, oldest = _wedged(a)
            if stuck:
                count("breaker")
                say("breaker", "every spread permit has been held more than %d s (oldest: thread %s for %d s): callers get a degraded "
                    "result at once instead of waiting; this is a wedge below Python" % (WEDGE_S, oldest[0], int(_now() - oldest[1])),
                    every=300.0)
                return (False, "slots_wedged")
            t0 = _now()
            got = sem.acquire(True, fx.timeout_s)
            _record_wait(_now() - t0)
            if not got:
                count("slot_timeout")
                return (False, "slot_timeout")
        self.sem = sem
        self.held = True                                  # recorded the moment the permit is ours
        tls.depth = 1
        with a.hold_lock:
            a.holders[id(self)] = (threading.current_thread().name, _now())
        return (True, None)

    def __exit__(self, et, ev, tb):
        try:
            if self.reentrant:
                self.tls.depth = max(0, getattr(self.tls, "depth", 1) - 1)
            elif self.held:
                self.held = False
                try:
                    self.tls.depth = 0
                    a = _anchor()
                    with a.hold_lock:
                        a.holders.pop(id(self), None)
                finally:
                    self.sem.release()
        except Exception:
            pass
        return False


def slot(fx):
    return _Slot(fx)


# ============================================================================================================================ the build lock
def acquire_build(lock, fx, inst):
    """Take the instance build lock for a COLD build (or a latch reset). -> True (the caller holds `lock` and must release it) or False
    (the caller returns a degraded 'build_wait'). Never raises, never waits more than fx.timeout_s, and does not wait at all when the
    builder has been inside its build longer than WEDGE_S (a stuck builder: waiting for it is the wedge)."""
    try:
        if lock.acquire(False):
            return True
        bs = getattr(inst, "_fix_build_started", None)
        if bs is not None and _now() - bs[0] > WEDGE_S:
            count("build_wedged")
            say("build_wedged", "a build by thread %s has been running %d s; callers stop waiting for it (degraded 'build_wait')"
                % (bs[1], int(_now() - bs[0])), every=300.0)
            return False
        t0 = _now()
        if lock.acquire(True, fx.timeout_s):
            count("build_wait_ok")
            _record_wait(_now() - t0)
            return True
        count("build_timeout")
        say("build_timeout", "gave up waiting %g s for another thread's build (degraded 'build_wait')" % fx.timeout_s)
        return False
    except Exception:
        return False                                      # a lock this function cannot vouch for must not be released by the caller


def _f(x):
    try:
        v = float(x)
        return v if (v == v and v not in (float("inf"), float("-inf"))) else None
    except Exception:
        return None


def _reader():
    """The shared NVML reading (an object with .free_mib) or None. Never raises. A seam for the tests."""
    try:
        a = _anchor()
        m = a.reader_mod
        if m is None:
            m = sys.modules.get("infrastructure.gpu_reader") or sys.modules.get("gpu_reader")
            if m is None:
                try:
                    if __package__:
                        from . import gpu_reader as m
                    else:
                        import gpu_reader as m
                except Exception:
                    m = None
            if m is None:
                say("reader", "gpu_reader is not importable: free VRAM is unknown (the floor fails open)")
                return None
            a.reader_mod = m
        return m.snapshot()
    except Exception:
        return None


def vram_ok(copy_mib, fx, inst, cold):
    """For a cuda build or migration, under the instance build lock. -> (ok, free_mib or None).
    Reads free VRAM from gpu_reader.snapshot() (cached, never waits). No torch.cuda.memory_* call (those take the allocator mutex).
    The floor: free < copy + floor refuses. It FAILS OPEN when free VRAM is unreadable, and after vram_patience_s of continuous refusal ONE
    build is allowed -- for a COLD build (no copy at all) and, on its own clock, for a CPU->GPU MIGRATION (review F1, 10-20): a refused
    migration keeps the instance on its CPU copy, and a CPU-resident 23M-entry scatter is the 16.78-core storm of 09-11, so the floor may
    delay a migration but never forbid it for the whole boot."""
    try:
        snap = _reader()
        free = None if snap is None else _f(getattr(snap, "free_mib", None))
        if fx.vram_floor_mb is None:
            return True, free
        if free is None:
            count("vram_unknown")
            say("vram_unknown", "free VRAM is unreadable: the floor fails open and the build goes ahead")
            return True, None
        need = float(copy_mib) + float(fx.vram_floor_mb)
        attr = "_fix_denied_since" if cold else "_fix_mig_denied_since"
        if free >= need:
            setattr(inst, attr, None)
            return True, free
        now = _now()
        t0 = getattr(inst, attr, None)
        if t0 is None:
            t0 = now
            setattr(inst, attr, t0)
        if now - t0 >= fx.vram_patience_s:
            setattr(inst, attr, None)
            count("patience_build" if cold else "patience_migration")
            _emit("[GPUSpreadFix] VRAM PATIENCE: a %s refused for %d s; allowing ONE (free %d MiB, needed %d)"
                  % ("cold build (no copy in this instance)" if cold else "CPU->GPU migration (this instance spreads on the CPU meanwhile)",
                     int(now - t0), int(free), int(need)))
            return True, free
        count("vram_denied")
        say("vram_denied", "no new GPU copy: NVML free %d MiB < copy %d + floor %d MiB (%s); kept waiting (at most vram_patience_s %d s)"
            % (int(free), int(copy_mib), int(fx.vram_floor_mb), "cold build" if cold else "migration: the CPU copy keeps working",
               int(fx.vram_patience_s)))
        return False, free
    except Exception:
        return True, None


def note_build(inst, device, kind, free_mib):
    """Counts a guarded build (kind 'cold' or 'migrate') and prints the ONE observation line per build. Never raises."""
    try:
        count("build" if kind == "cold" else "migration")
        _emit("[GPUSpreadFix] build: device=%s kind=%s nvml_free_mib=%s thread=%s"
              % (device, kind, "?" if free_mib is None else "%d" % int(free_mib), threading.current_thread().name))
    except Exception:
        pass


# ============================================================================================================================ the shared graph
def key_lock(key):
    """The lock that makes one build per shared-graph key. None on any failure (the caller then builds its own, unshared)."""
    try:
        a = _anchor()
        with a.reg_lock:
            lk = a.klocks.get(key)
            if lk is None:
                lk = a.klocks[key] = threading.Lock()
            return lk
    except Exception:
        return None


def shared_get(key):
    try:
        return _anchor().shared.get(key)
    except Exception:
        return None


def shared_put(key, ma):
    """Registers (src, dst, w) of a good CUDA build. The affect vector stays per instance."""
    try:
        _anchor().shared[key] = (ma[0], ma[1], ma[2])
    except Exception:
        pass


def shared_drop(key):
    try:
        _anchor().shared.pop(key, None)
    except Exception:
        pass
