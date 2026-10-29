"""_gc_diet.py -- the GC DIET (gc_diet_1015, Nous, 2026-10-15). Lives next to memory_pressure_fairy.py; ASCII only.

WHY (measured, Boot Q): 37-51 stop-the-world collects per 10 min, 137-247 s of frozen world (23-41%), and they free ~nothing.
Every collect in her is an explicit gc.collect() call (gc is disabled). Seven callers; this module gates each one behind ONE key
in state/gc_diet.json and puts ONE shared floor under all of them, so garbage can never grow without bound.

THE SWITCH state/gc_diet.json (absolute path from this file; re-read when it changes and at least every 10 s).
  Absent / unreadable / torn / not an object / a key that is not a JSON true  ==>  she behaves EXACTLY as today.
  gates (JSON true arms one):  monitor_pressure_no_collect  monitor_periodic_no_collect  autosave_no_collect  ladder_no_collect
                               runaway_no_collect  leakhunter_no_spawn  fast_poll_no_collect
  observe (true): install the counter and print [GcDiet] lines, gate nothing.   one_thread_monitor: read by server.py, not here.
  numbers, clamped:  floor_min 45 [15,120] . floor_defer_max_min 10 [0,30] . line_min 10 [5,60]
                     reversal_at_min (absent = none) [20,240] . reversal_len_min 20 [10,30]

HOW. The memory fairy owns gc (gc.disable() in on_boot). While the switch is armed it installs _collect over gc.collect, in HER
process only. server.py (two callers) and tracer_worker_system.py (one) are not edited: the wrapper tells them apart by
(file name, function name, the text of the call line). A caller it does not recognise is NEVER gated: it passes through, is counted,
and is named in the window line. The fairy's own callers are gated where they live (hooks that call skip()).

THE FLOOR. last_real = the end time of the last real collect from any caller. While armed, the fairy's heartbeat tick starts one
collect on thread GcDiet-floor when now - last_real >= floor_min (waiting for a quiet moment at most floor_defer_max_min). If the
tick dies, any gated call collects once last_real is older than floor_min + defer + 5 min (a claim lets exactly one caller through).
No per-boot cap and no off switch while any gate is armed: the only way to zero collects is to disarm, which is today.

REVERSAL. reversal_at_min makes the diet behave exactly as today for reversal_len_min (whole windows): an in-boot control that MUST
bring the stop time back, so a low number in the other windows can be credited to the switch.

SAFE. Every entry point is try/except; a failed decision means COLLECT (today). An exception from the real collect propagates
unchanged, prints one error line and never stamps the floor clock. No lock is held across a real collect. Nothing is written to disk.
Output goes to stderr (the fairy prints there).

SHUTDOWN. Stay-down holds only when the global shutdown flag is set (the HTTP / save-gated route, and M0's route). Ctrl+C and the
reboot route never set it: there on_shutdown removes the wrapper, but a later heartbeat tick reads 'no global shutdown' as a hot reload
and re-arms, so the gates skip again and a floor that is due may start inside the shutdown (about 45 s in 45 min; one collect).
"""
import gc
import json
import linecache
import math
import os
import sys
import threading
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
SWITCH_FILE = os.path.join(_ROOT, "state", "gc_diet.json")

GATE_KEYS = ("monitor_pressure_no_collect", "monitor_periodic_no_collect", "autosave_no_collect", "ladder_no_collect",
             "runaway_no_collect", "leakhunter_no_spawn", "fast_poll_no_collect")
_NUM = {"floor_min": (45.0, 15.0, 120.0), "floor_defer_max_min": (10.0, 0.0, 30.0), "line_min": (10.0, 5.0, 60.0),
        "reversal_at_min": (None, 20.0, 240.0), "reversal_len_min": (20.0, 10.0, 30.0)}
_BACKSTOP_EXTRA_MIN = 5.0     # backstop = floor_min + floor_defer_max_min + this
_CLAIM_S = 120.0              # one backstop claim admits one caller for this long
_RETRY_S = 60.0               # a floor attempt that failed is tried again no sooner than this (never a storm)
_ERR_S = 300.0                # at most one error line per stage per this
_LINE_MAX = 480
_WIN_MAX = 640
_P2_DELAY_S = 2.0             # private memory is read again this long after a floor collect
_SITE_ORDER = ("floor", "backstop", "manual", "ladder", "runaway", "fast_poll", "monitor_pressure", "monitor_periodic",
               "autosave", "leakhunter", "census_g2", "other")
_SKIP_ORDER = ("monitor_pressure", "monitor_periodic", "autosave", "ladder", "runaway", "fast_poll")

# (file name, function name, text of the call line without its comment) -> (site, key). The pinned bytes: server.py :650/:655/:683,
# tracer_worker_system.py :532 (and the fallback copy :531). A text-match survives line shifts made by other builds.
_FOREIGN = {
    ("server.py", "_thread_memory_monitor", "_gc2.collect()"): ("monitor_pressure", "monitor_pressure_no_collect"),
    ("server.py", "_thread_memory_monitor", "_collected = _gc2.collect()"): ("monitor_periodic", "monitor_periodic_no_collect"),
    ("tracer_worker_system.py", "autosave_loop", "gc.collect(generation=0)"): ("autosave", "autosave_no_collect"),
}
_OWN_FILES = ("memory_pressure_fairy.py", "_gc_diet.py")
_OWN_FUNC = {"_on_runaway": "runaway", "_fast_poll": "fast_poll", "run": "leakhunter", "_gz_g2": "census_g2"}

_BUILTIN = getattr(gc.collect, "_gc_diet_orig", None) or gc.collect
_T0 = time.monotonic()
_L = threading.Lock()         # counters only; never held across a real collect or a print
_SWL = threading.Lock()
_TICK = threading.Lock()
_TL = threading.local()
_SW = {"key": None, "data": {}, "read": 0.0}
_CLS = {}


def _neww():
    return {"ran": {}, "wall": {}, "skip": {}, "other": {}}


_W = _neww()                  # the current [GcDiet] window
_C = _neww()                  # cumulative since the process began (status())
_T = {"ran": 0, "wall": 0.0}
_S = {"orig": None, "installed": False, "down": False, "on": False, "armed_at": None, "armed_up": None, "sig": None,
      "last_real": 0.0, "claim_until": 0.0, "try_at": -1e18, "due_since": None, "floor_thread": None, "floor_n": 0,
      "rev": False, "rev_left": 0, "rev_done": False, "win_t0": None, "prev": None, "skip_at": {}, "err_at": {}, "said": set(),
      "proc": None}


# -- clock and system seams (a test replaces these) ---------------------------------------------------------------------------
def _now():
    return time.monotonic()           # every interval here (the floor clock above all) is on the monotonic clock: a stepped wall clock cannot stall it


def _pc():
    return time.perf_counter()


def _sleep(s):
    time.sleep(s)


def _psutil():
    try:
        return sys.modules.get("psutil") or __import__("psutil")
    except Exception:
        return None


def _start_thread(fn, name):
    t = threading.Thread(target=fn, name=name, daemon=True)
    t.start()
    return t


def _shutdown_flag():
    """Has the global shutdown been signalled? Only looks at a module that is already imported (no import side effects)."""
    try:
        for name in ("P00_Autonomic.nervous_system.shared_postal_hub", "fairies.P00_Autonomic.nervous_system.shared_postal_hub"):
            m = sys.modules.get(name)           # the canonical module server.py uses, then the shim that delegates to it
            f = getattr(m, "is_global_shutdown", None) if m is not None else None
            if callable(f):
                return bool(f())
        return False
    except Exception:
        return False                      # cannot tell: the floor proceeds, as today would


# -- output -----------------------------------------------------------------------------------------------------------------
def _say(s, cap=_LINE_MAX):
    try:
        print(str(s).encode("ascii", "replace").decode("ascii").replace("\n", " ")[:cap], file=sys.stderr, flush=True)
    except Exception:
        pass


def _say_once(tag, s):
    if tag not in _S["said"]:
        _S["said"].add(tag)
        _say(s)


def oops(stage, e):
    """One ASCII error line per stage per 300 s. Never raises."""
    try:
        now = _now()
        last = _S["err_at"].get(stage)
        if last is not None and 0.0 <= now - last < _ERR_S:
            return
        _S["err_at"][stage] = now
        _say("[GcDiet] %s error (non-fatal): %s: %s" % (stage, type(e).__name__, str(e)[:120]))
    except Exception:
        pass


# -- the switch -------------------------------------------------------------------------------------------------------------
def switch():
    """state/gc_diet.json as a dict; {} (= today) when absent, unreadable, torn or not an object."""
    try:
        st = os.stat(SWITCH_FILE)
    except OSError:
        with _SWL:
            _SW["key"], _SW["data"], _SW["read"] = None, {}, 0.0
        return {}
    key = (st.st_mtime_ns, st.st_size)
    now = _now()
    with _SWL:
        if key != _SW["key"] or not (0.0 <= now - float(_SW["read"]) <= 10.0):
            try:
                with open(SWITCH_FILE, "rb") as f:
                    d = json.loads(f.read().decode("utf-8-sig"))          # a hand-edited file may carry a BOM
                _SW["data"], _SW["key"], _SW["read"] = (d if isinstance(d, dict) else {}), key, now
            except Exception:
                _SW["data"], _SW["key"], _SW["read"] = {}, None, 0.0       # torn or bad: today, read again next time
        return dict(_SW["data"])


def reset_cache():
    with _SWL:
        _SW["key"], _SW["data"], _SW["read"] = None, {}, 0.0


def _num(sw, k):
    dflt, lo, hi = _NUM[k]
    v = sw.get(k, dflt)
    try:
        if isinstance(v, (bool, str)) or v is None:
            raise ValueError(v)
        x = float(v)
        if x != x:
            raise ValueError(v)
    except Exception:
        if dflt is None:
            return None
        x = float(dflt)
    return min(max(x, lo), hi)


def cfg_of(sw):
    return {k: _num(sw, k) for k in _NUM}


def armed_keys(sw):
    return tuple(k for k in GATE_KEYS if sw.get(k) is True)


def _her():
    m = sys.modules.get("__main__")
    return m is not None and getattr(m, "SYSTEM", None) is not None and callable(getattr(m, "shutdown_system", None))


# -- counters ---------------------------------------------------------------------------------------------------------------
def _bump(d, k, n=1):
    d[k] = d.get(k, 0) + n


def _record(site, dt):
    """A real collect finished (any caller). Stamps the floor clock."""
    with _L:
        _bump(_W["ran"], site)
        _bump(_C["ran"], site)
        _W["wall"][site] = _W["wall"].get(site, 0.0) + dt
        _T["ran"] += 1
        _T["wall"] += dt
        _S["last_real"] = _now()


def _note_other(name):
    with _L:
        if name in _W["other"] or len(_W["other"]) < 32:
            _bump(_W["other"], name)
        if name in _C["other"] or len(_C["other"]) < 64:
            _bump(_C["other"], name)


# -- the decision ----------------------------------------------------------------------------------------------------------
def _decide(key, site, gap=0.0):
    """'skip' | 'pass' | 'backstop'. 'pass' and 'backstop' mean: collect. Never raises (a failure is 'pass' = today)."""
    try:
        if _S["down"] or not _her():
            return "pass"
        sw = switch()
        if sw.get(key) is not True or _S["rev"]:
            return "pass"
        cfg = cfg_of(sw)
        now = _now()
        if _S["last_real"] <= 0.0:
            _S["last_real"] = now                        # first sight of an armed switch: the floor clock starts now
        if site != "leakhunter":                         # a spawn is not a collect: it takes no part in the backstop
            late = (cfg["floor_min"] + cfg["floor_defer_max_min"] + _BACKSTOP_EXTRA_MIN) * 60.0
            if now - _S["last_real"] >= late:
                with _L:
                    ok = now >= _S["claim_until"]
                    if ok:
                        _S["claim_until"] = now + _CLAIM_S
                if ok:
                    _TL.bs = now
                    return "backstop"
        with _L:
            last = _S["skip_at"].get(site)
            if gap <= 0.0 or last is None or now - last >= gap:
                _S["skip_at"][site] = now
                _bump(_W["skip"], site)
                _bump(_C["skip"], site)
        return "skip"
    except Exception:
        return "pass"


def skip(key, site, min_gap_s=0.0):
    """True = skip this collect / spawn. The in-file hooks of the fairy call this. Never raises."""
    try:
        return _decide(key, site, float(min_gap_s)) == "skip"
    except Exception:
        return False


def _classify(f):
    """-> (kind, site, key). kind: 'gate' (a foreign caller with a key), 'own' (this fairy), 'other' (unrecognised: never gated)."""
    co = f.f_code
    fn, name, ln = co.co_filename, co.co_name, f.f_lineno
    ck = (fn, name, ln)
    hit = _CLS.get(ck)
    if hit is not None:
        return hit
    base = os.path.basename(fn).lower()
    if base in _OWN_FILES:
        if name == "_do_gc":                             # not cached: ladder or manual depends on who called _do_gc
            up = f.f_back
            return ("own", "ladder" if (up is not None and up.f_code.co_name == "_monitor_tick") else "manual", None)
        site = _OWN_FUNC.get(name)
        r = ("own", site, None) if site else ("other", "%s:%s:%d" % (base, name, ln), None)
    else:
        txt = ""
        try:
            txt = (linecache.getline(fn, ln) or "").split("#", 1)[0].strip()
        except Exception:
            pass
        rule = _FOREIGN.get((base, name, txt))
        r = ("gate", rule[0], rule[1]) if rule else ("other", "%s:%s:%d" % (base, name, ln), None)
    if len(_CLS) < 256:
        _CLS[ck] = r
    return r


def _collect(*a, **kw):
    """Replaces gc.collect while armed or observing, in her process only. Fail-open: any trouble in here means 'collect'.
    Only a real collect that RETURNED stamps the floor clock (a raising one never satisfies the floor). A call that re-enters this
    wrapper from inside one of our own real collects on the same thread (a foreign wrapper adopted over us, a finalizer) goes straight
    to the collector: never a cycle."""
    if getattr(_TL, "inside", False):
        return _BUILTIN(*a, **kw)
    orig = _S["orig"] or _BUILTIN
    label = None
    try:
        kind, site, key = _classify(sys._getframe(1))
        label = site
        if kind == "gate":
            if _decide(key, site, 0.0) == "skip":
                return 0                                 # what a collect that found nothing returns (H2 tests > 1000)
        elif kind == "other":
            label = "other"
            _note_other(site)
        bs = getattr(_TL, "bs", None)
        if bs is not None:
            _TL.bs = None
            if 0.0 <= _now() - bs <= 30.0:
                label = "backstop"
    except Exception:
        label = label or "other"
    t0 = _pc()
    ok = False
    _TL.inside = True
    try:
        r = orig(*a, **kw)
        ok = True
        return r
    except Exception as e:
        oops("collect", e)                               # visible; the exception reaches the caller unchanged
        raise
    finally:
        _TL.inside = False
        if ok:
            try:
                _record(label or "other", _pc() - t0)
            except Exception:
                pass


_collect._gc_diet_orig = None


def install():
    """Idempotent: never stacks a wrapper on a wrapper of ours."""
    try:
        cur = gc.collect
        if cur is not _collect:
            inner = getattr(cur, "_gc_diet_orig", None)
            _S["orig"] = inner if inner is not None else cur
            _collect._gc_diet_orig = _S["orig"]
            gc.collect = _collect
        elif _S["orig"] is None:
            _S["orig"] = _BUILTIN
        _S["installed"] = gc.collect is _collect
        return _S["installed"]
    except Exception as e:
        oops("install", e)
        return False


def uninstall():
    try:
        if gc.collect is _collect:
            gc.collect = _S["orig"] or _BUILTIN
        _S["installed"] = gc.collect is _collect
    except Exception as e:
        oops("uninstall", e)


def shutdown():
    """The fairy is going down: the gc.collect wrapper is removed. It stays down only while the global shutdown flag is set (see SHUTDOWN)."""
    _S["down"] = True
    uninstall()


# -- measuring --------------------------------------------------------------------------------------------------------------
def _mem():
    try:
        ps = _psutil()
        if ps is None:
            return None
        p = _S["proc"]
        if p is None:
            p = _S["proc"] = ps.Process()
        mi = p.memory_info()
        d = {"private": float(getattr(mi, "private", None) or getattr(mi, "vms", 0) or 0), "wset": float(getattr(mi, "rss", 0) or 0),
             "faults": int(getattr(mi, "num_page_faults", 0) or 0), "handles": -1}
        try:
            d["handles"] = int(p.num_handles())
        except Exception:
            pass
        return d
    except Exception:
        return None


def _gb(m, k):
    return (m[k] / 1073741824.0) if m else float("nan")


def _counts(d, order):
    items = [(k, d[k]) for k in order if d.get(k)] + [(k, d[k]) for k in sorted(d) if k not in order and d.get(k)]
    return " ".join("%s %d" % kv for kv in items) or "-"


def _leakhunter_alive(fairy):
    try:
        for a in list(getattr(fairy, "_active_agents", ())):
            th = getattr(a, "_thread", None)
            if type(a).__name__ == "LeakHunterAgent" and th is not None and th.is_alive():
                return True
    except Exception:
        pass
    return False


def _floor_run(why, up, since_last_min, floor_min):
    """The floor collect, on its own thread. Calls the saved original directly (it does not depend on the wrapper)."""
    try:
        m0 = _mem()
        orig = _S["orig"] or _BUILTIN
        t0 = _pc()
        _TL.inside = True                                # an adopted foreign wrapper that calls back into us goes straight to the collector
        try:
            found = orig()
        finally:
            _TL.inside = False
        dt = _pc() - t0
        m1 = _mem()
        _record("floor", dt)
        _S["floor_n"] += 1
        n = _S["floor_n"]
        _sleep(_P2_DELAY_S)
        m2 = _mem()
        fl = (m1["faults"] - m0["faults"]) if (m0 and m1) else 0
        _say("[GcDiet] floor collect #%d why=%s up=%.1fmin since-last=%.1fmin found=%s pause=%.0fms faults=%+d (%d/s during) | "
             "private %.2f->%.2fGB (+2s %.2f) wset %.2f->%.2fGB handles %s->%s | next due in %.1fmin"
             % (n, why, up, since_last_min, found, dt * 1e3, fl, int(fl / dt) if dt > 0 else 0, _gb(m0, "private"), _gb(m1, "private"),
                _gb(m2, "private"), _gb(m0, "wset"), _gb(m1, "wset"), m0["handles"] if m0 else "?", m1["handles"] if m1 else "?",
                floor_min))
    except Exception as e:
        oops("floor", e)


def _floor_step(fairy, now, up, cfg, census_busy):
    if _S["rev"] or now - _S["last_real"] < cfg["floor_min"] * 60.0:
        _S["due_since"] = None                           # in the reversal, or not due yet
        return
    if _shutdown_flag() or getattr(fairy, "_cg_fired", False) or getattr(fairy, "_cg_inflight", False):
        _S["due_since"] = None                           # a hard condition (shutdown, the commit guard): no floor and no deferral clock either
        return
    th = _S["floor_thread"]
    if th is not None and th.is_alive():
        return
    if now - _S["try_at"] < _RETRY_S:
        return
    if _S["due_since"] is None:
        _S["due_since"] = now
    if not census_busy and not _leakhunter_alive(fairy):
        why = "due"
    elif now - _S["due_since"] >= cfg["floor_defer_max_min"] * 60.0:
        why = "deferred"                                 # waiting for a quiet moment is bounded
    else:
        return
    since = (now - _S["last_real"]) / 60.0
    _S["try_at"], _S["due_since"] = now, None
    fm = cfg["floor_min"]
    try:
        _S["floor_thread"] = _start_thread(lambda: _floor_run(why, up, since, fm), "GcDiet-floor")
    except Exception as e:
        oops("floor-start", e)


def _window_line(now, up, cfg, rev_during):
    with _L:
        w = dict(_W)
        _W.update(_neww())
    ran = sum(w["ran"].values())
    wall = sum(w["wall"].values())
    nsk = sum(w["skip"].values())
    m = _mem()
    prev = _S["prev"]
    fps = 0
    if m and prev and now > prev[0]:
        fps = int(max(0, m["faults"] - prev[1]) / (now - prev[0]))
    if m:
        _S["prev"] = (now, m["faults"])
    oth = sorted(w["other"].items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    until = ("%.1fmin" % max(0.0, cfg["floor_min"] - (now - _S["last_real"]) / 60.0)) if _S["armed_at"] is not None else "-"
    _say("[GcDiet] up=%.1fmin last %.1fmin: ran=%d wall=%.2fs wrapper=%s reversal=%s | by site: %s | skipped=%d (%s) | "
         "no-spawn leakhunter %d | other callers: %s | private=%.2fGB wset=%.2fGB faults=%d/s handles=%s | "
         "floor: last %.1fmin ago, next in %s"
         % (up, cfg["line_min"], ran, wall, "on" if _S["installed"] else "OFF", "yes" if rev_during else "no",
            _counts(w["ran"], _SITE_ORDER), nsk - w["skip"].get("leakhunter", 0), _counts(
                {k: v for k, v in w["skip"].items() if k != "leakhunter"}, _SKIP_ORDER),
            w["skip"].get("leakhunter", 0), " ".join("%s x%d" % kv for kv in oth) or "-", _gb(m, "private"), _gb(m, "wset"), fps,
            m["handles"] if m else "?", max(0.0, (now - _S["last_real"]) / 60.0), until), cap=_WIN_MAX)


def _reversal_step(up, cfg, armed):
    """At a window boundary, after the line was printed."""
    if _S["rev"]:
        _S["rev_left"] -= 1
        if _S["rev_left"] <= 0:
            _S["rev"], _S["rev_done"] = False, True
            _say("[GcDiet] REVERSAL off at up=%.1fmin: the diet is back on" % up)
        return
    at = cfg["reversal_at_min"]
    if (armed and at is not None and not _S["rev_done"] and up >= at and _S["armed_up"] is not None and _S["armed_up"] <= at):
        _S["rev"] = True
        _S["rev_left"] = max(1, int(math.ceil(cfg["reversal_len_min"] / cfg["line_min"] - 1e-9)))
        _say("[GcDiet] REVERSAL on at up=%.1fmin for %d windows: every site collects as today, the floor is idle" % (up, _S["rev_left"]))


# -- the heartbeat entry ----------------------------------------------------------------------------------------------------
def tick(fairy, now, her=None, census_busy=False, up_min=None):
    """Once per heartbeat (the fairy's on_tick). Never raises."""
    if not _TICK.acquire(False):
        return                                           # another heartbeat thread is in here this very moment
    try:
        _tick(fairy, _now(), census_busy, up_min)         # `now` from the caller is the wall clock; the diet keeps its own monotonic time
    except Exception as e:
        oops("tick", e)
    finally:
        _TICK.release()


def _tick(fairy, now, census_busy, up_min):
    if _S["down"]:
        if _shutdown_flag():
            return                                       # she is going down for good: stay down
        _S["down"] = False                               # on_shutdown without a global shutdown = a hot reload of the fairy: the diet comes back
    if not _her():
        if _S["installed"]:
            uninstall()
        return
    sw = switch()
    keys = armed_keys(sw)
    armed = bool(keys)
    if not (armed or sw.get("observe") is True):
        if _S["on"]:
            _S["on"], _S["armed_at"], _S["rev"], _S["sig"] = False, None, False, None
            uninstall()
            _say("[GcDiet] DISARMED: the switch is off; every site collects as today")
        return
    cfg = cfg_of(sw)
    up = ((now - _T0) / 60.0) if up_min is None else float(up_min)
    if not _S["on"]:
        _S["on"], _S["win_t0"] = True, now
        _S["prev"] = None
    ok = install()
    if armed and _S["armed_at"] is None:
        _S["armed_at"], _S["armed_up"], _S["last_real"] = now, up, now
    elif not armed:
        _S["armed_at"] = None
    sig = (keys, bool(ok), cfg["floor_min"], cfg["floor_defer_max_min"], cfg["line_min"], cfg["reversal_at_min"], cfg["reversal_len_min"])
    if sig != _S["sig"]:
        _S["sig"] = sig
        _say("[GcDiet] ARMED: gates=%s floor=%.0fmin defer<=%.0fmin backstop=%.0fmin line=%.0fmin reversal=%s wrapper=%s%s"
             % (",".join(k.replace("_no_collect", "").replace("_no_spawn", "") for k in keys) or "none (observe only)", cfg["floor_min"],
                cfg["floor_defer_max_min"], cfg["floor_min"] + cfg["floor_defer_max_min"] + _BACKSTOP_EXTRA_MIN, cfg["line_min"],
                ("at %.0fmin for %.0fmin" % (cfg["reversal_at_min"], cfg["reversal_len_min"])) if cfg["reversal_at_min"] is not None
                else "none", "on" if ok else "NOT INSTALLED", "" if ok else " (the foreign sites are not gated)"))
    if armed and gc.isenabled():
        _say_once("gc_enabled", "[GcDiet] NOTE: gc.isenabled() is True while armed: automatic collects would bypass the counter")
    if now - float(_S["win_t0"]) >= cfg["line_min"] * 60.0:
        _S["win_t0"] = now
        _window_line(now, up, cfg, _S["rev"])
        _reversal_step(up, cfg, armed)
    if armed:
        _floor_step(fairy, now, up, cfg, census_busy)


def status():
    """A copy of the counters (tests, debugging)."""
    with _L:
        return {"ran": dict(_C["ran"]), "skip": dict(_C["skip"]), "other": dict(_C["other"]), "total_ran": _T["ran"],
                "last_real": _S["last_real"], "installed": _S["installed"], "armed_at": _S["armed_at"], "rev": _S["rev"],
                "floor_n": _S["floor_n"], "on": _S["on"]}
