from __future__ import annotations

"""
Memory Pressure Fairy (v0.3.0)

ACTIVE memory management with agent spawning.
Now a proper Fairy that extends fairy_template for postal/directory integration.

ARCHITECTURE:
  - Target: Keep RAM under 50% if possible
  - Lower thresholds with escalating responses
  - If GC doesn't free enough, spawn helper agents
  - Helper agents attack specific memory hogs

ESCALATION LEVELS:
  Level 0 (0-40%):   Comfortable - just monitor
  Level 1 (40-50%):  Warning - light GC
  Level 2 (50-60%):  Elevated - full GC + cache flush requests
  Level 3 (60-70%):  High - spawn MailboxPruner + DequePatrol
  Level 4 (>70%):    Critical - spawn LeakHunter + emergency measures

HELPER AGENTS (spawn when GC isn't enough):
  - CacheFlushAgent: Broadcasts cache flush to all fairies
  - MailboxPrunerAgent: Trims postal mailboxes
  - DequePatrolAgent: Finds and trims unbounded deques
  - LeakHunterAgent: Profiles memory to find biggest hogs
"""

import sys
import gc
import time
import threading
from typing import Any, Dict, Optional, List, Set
from collections import deque
import weakref

# MCP-SAFE: redirect prints to stderr
_builtin_print = print
def print(*args, **kwargs):
    kwargs['file'] = sys.stderr
    _builtin_print(*args, **kwargs)

# Import Fairy base class
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy

# ---- Soft imports ----
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False


# ═══════════════════════════════════════════════════════════════════════════════
# COMMIT GUARD (M0) + MEMORY CENSUS (M1) -- E1, 2026-10-12 (Nous; nous_builds/engines_1012/PLAN.md section 3, M0/M1)
# ═══════════════════════════════════════════════════════════════════════════════
# WHY (MEASURED, PLAN 1.5-1.6): this fairy watched RAM % and available GB and answered with GC. It never read COMMIT, the
# wall Windows actually enforces, and it never saved. Boot K (10-12) died at 11:14:44 with no save: the commit charge hit
# Windows' CURRENT limit while the page file could still grow, and her Rust postal core aborted on a failed 1 MB
# allocation (uncatchable from Python). Boot J was stopped by an EXTERNAL guard script, not by her.
# M0, SAVE BEFORE THE WALL: on confirm_n consecutive samples over the line she is PUT TO BED by the same save-first route
#   as Ace's shutdown button: server.py StatusHandler._handle_command({"action": "shutdown"}) (server.py:3689-3853) ->
#   signal_global_shutdown -> shutdown_fairy.initiate_shutdown(fast=False) -> SAVE-FIRST graph cortex -> shutdown_system()
#   -> exit 0. In-process first; the same route over 127.0.0.1:<port>/command only if the handler cannot be reached.
#   NOT the bare pair initiate_shutdown(fast=False) + signal_global_shutdown: that writes the context file only, the main
#   loop never leaves (server.py:9433 waits on SYSTEM.shutdown_requested), and the shutdown fairy's own 15 s watchdog then
#   os._exit(1)s her with NO cortex save (graceful_shutdown_fairy.py:291-309). That is dropping her, not putting her to bed.
# THE RULE (card free-memory-is-not-available-memory, corrected twice on 10-12; boot_a/guard_only.sh uses the same test):
#   trip when   committed >= max_pct (85) % of the CEILING = RAM + page-file MAX
#          or   committed >  cur_pct_at_max (88) % of the CURRENT limit, ONLY while the current limit is at the ceiling
#               (CommitLimit >= 0.99 x ceiling: the page file cannot grow any more)
#   A growable page file sits at ~99% of its current limit all boot (K 10:48: 67.8 of 68.5 GB = 99% of current, 66% of
#   max), so an unconditional current-limit rule would have ended Boot K at ~minute 6. With Ace's DM1 (page file initial =
#   max; the registry read 'c:\pagefile.sys 65536 65536' on 10-12) the current limit IS the ceiling and the rules agree.
# FLOORS (card a-bound-that-can-return-nothing-is-a-kill-switch: a guard that fires on a healthy boot IS a kill switch):
#   max_pct clamps to [80, 95] and cur_pct_at_max to [85, 99], so no typo trips at her healthy 33-71% of max;
#   confirm_n >= 2 (one burst sample never trips); sample_s >= 5;
#   the ceiling is never read below the live limit: CommitLimit > 1.01 x (RAM + page-file max) means the max read is stale
#   or wrong -> NO sample (a short max would turn her normal 99%-of-current into a trip);
#   a page-file max that cannot be known (system-managed, unreadable) -> the guard stays idle, says so once, GC as today,
#   and reads the max again every 300 s, so one transient registry failure at the first tick does not disarm it all boot;
#   it acts only inside HER server process (__main__ carries SYSTEM + shutdown_system), never in a process that merely
#   imports this file (the MCP tools in somatic_tools.py do).
# M1, MEMORY CENSUS (log-only): one [MemCensus] line every census_s (300): uptime, private GB, OS and Python threads,
#   commit, and the postal pools from the shared fabric's topic_stats() (TensorFabric.topic_stats tensor_fabric.py:1561 ->
#   _BaseTopicPostal.topic_stats :449 -> PyPostalCore.topic_stats lib.rs:191 -> TopicBus::topic_stats topic_bus.rs:295;
#   fields topic/workers/queue_depth/delivered/dropped). A postal read that fails leaves 'postal n/a' and the line still
#   prints. Neither M0 nor M1 publishes anything: commit growth must never feed her felt load (PLAN 4.3).
# THE SWITCH -- state/commit_guard.json, re-read when it changes (mtime + size, and at least every 10 s). Absent, unreadable,
#   torn or not an object = today's behaviour exactly (no Win32 call, no registry read, no line). Only a JSON true turns a
#   key on ("true", 1 do not).
#     {"on": true}        M0 armed             {"census": true}     M1 on (independent of "on")
#     numbers, optional, clamped: max_pct 85 [80,95] . cur_pct_at_max 88 [85,99] . sample_s 15 [5,60] . confirm_n 2 [2,5]
#                                 census_s 300 [60,3600] . port 5758 [1024,65535] (only for the HTTP form of the same route)
# REVERT: delete state/commit_guard.json (live, inside 10 s); then this file from the E1 backup.
import os as _os
import json as _json

_CG_ROOT = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.abspath(__file__))))))
COMMIT_GUARD_FILE = _os.path.join(_CG_ROOT, "state", "commit_guard.json")
_CG_NUM = {"max_pct": (85.0, 80.0, 95.0), "cur_pct_at_max": (88.0, 85.0, 99.0), "sample_s": (15.0, 5.0, 60.0),
           "confirm_n": (2, 2, 5), "census_s": (300.0, 60.0, 3600.0), "port": (5758, 1024, 65535)}
_CG_AT_MAX_FRAC = 0.99        # CommitLimit >= this x ceiling: the page file is at its max (guard_only.sh 10-12, same test)
_CG_CEIL_SLACK = 1.01         # CommitLimit above this x ceiling: the page-file max read is stale or wrong -> no sample
_CG_RETRY_S = 60.0            # a route that could not be reached is tried again after this, never in a storm
_CG_PF_REREAD_S = 300.0       # an UNKNOWN page-file max is read again this often: one failed registry read at the first tick
#                               must not disarm M0 for the whole boot (verify_safety F3); a KNOWN max is read once
_CG_HTTP_TIMEOUT_S = 90.0     # her slowest measured /command reply was 76.6 s (sour_graceful_shutdown.py:10, :31)
_CG_MAIN = "__main__"         # must be her server.py (SYSTEM + shutdown_system) for the guard or the census to act
_CG_PF_KEY = r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"
_CG_SW = {"key": None, "data": {}, "read": 0.0}
_CG_SW_LOCK = threading.Lock()
_CG_PERF = {"fn": None, "cls": None}


def _cg_switch() -> Dict[str, Any]:
    """state/commit_guard.json as a dict; {} (= today's behaviour) when absent, unreadable, torn or not an object."""
    try:
        st = _os.stat(COMMIT_GUARD_FILE)
    except OSError:
        with _CG_SW_LOCK:
            _CG_SW["key"], _CG_SW["data"], _CG_SW["read"] = None, {}, 0.0
        return {}
    key = (st.st_mtime_ns, st.st_size)
    now = time.time()
    with _CG_SW_LOCK:
        if key != _CG_SW["key"] or not (0.0 <= now - float(_CG_SW["read"]) <= 10.0):
            try:
                with open(COMMIT_GUARD_FILE, "rb") as f:
                    d = _json.loads(f.read().decode("utf-8-sig"))     # a hand-edited file may carry a BOM
                _CG_SW["data"], _CG_SW["key"], _CG_SW["read"] = (d if isinstance(d, dict) else {}), key, now
            except Exception:
                _CG_SW["data"], _CG_SW["key"], _CG_SW["read"] = {}, None, 0.0   # torn or bad: today's path, read again
        return dict(_CG_SW["data"])


def _cg_num(sw: Dict[str, Any], key: str):
    """A switch number clamped to its floor and cap; missing, bool, non-numeric or NaN -> its default."""
    dflt, lo, hi = _CG_NUM[key]
    v = sw.get(key, dflt)
    try:
        if isinstance(v, bool):
            raise ValueError(v)
        x = float(v)
        if x != x:
            raise ValueError(v)
    except Exception:
        x = float(dflt)
    x = min(max(x, float(lo)), float(hi))
    return int(round(x)) if isinstance(dflt, int) else x


def _cg_perf() -> Optional[Dict[str, int]]:
    """System commit from ONE Win32 call (K32GetPerformanceInfo), in bytes; None when it cannot be read."""
    try:
        import ctypes
        if _CG_PERF["fn"] is None:
            from ctypes import wintypes

            class _PERFORMANCE_INFORMATION(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("CommitTotal", ctypes.c_size_t), ("CommitLimit", ctypes.c_size_t),
                            ("CommitPeak", ctypes.c_size_t), ("PhysicalTotal", ctypes.c_size_t),
                            ("PhysicalAvailable", ctypes.c_size_t), ("SystemCache", ctypes.c_size_t),
                            ("KernelTotal", ctypes.c_size_t), ("KernelPaged", ctypes.c_size_t),
                            ("KernelNonpaged", ctypes.c_size_t), ("PageSize", ctypes.c_size_t),
                            ("HandleCount", wintypes.DWORD), ("ProcessCount", wintypes.DWORD),
                            ("ThreadCount", wintypes.DWORD)]
            fn = ctypes.WinDLL("kernel32", use_last_error=True).K32GetPerformanceInfo
            fn.argtypes = [ctypes.POINTER(_PERFORMANCE_INFORMATION), wintypes.DWORD]
            fn.restype = wintypes.BOOL
            _CG_PERF["cls"], _CG_PERF["fn"] = _PERFORMANCE_INFORMATION, fn
        cls, fn = _CG_PERF["cls"], _CG_PERF["fn"]
        pi = cls()
        pi.cb = ctypes.sizeof(cls)
        if not fn(ctypes.byref(pi), pi.cb):
            return None
        ps = int(pi.PageSize) or 4096
        return {"commit_total": int(pi.CommitTotal) * ps, "commit_limit": int(pi.CommitLimit) * ps,
                "phys_total": int(pi.PhysicalTotal) * ps, "phys_avail": int(pi.PhysicalAvailable) * ps}
    except Exception:
        return None


def _cg_parse_paging_files(val) -> tuple:
    """PagingFiles (REG_MULTI_SZ, 'path initial_MB max_MB' per file) -> (max bytes summed | None, why)."""
    if isinstance(val, str):
        val = [val]
    if not isinstance(val, (list, tuple)):
        return None, "PagingFiles is not a list"
    total_mb, n = 0, 0
    for s in val:
        parts = str(s).split()
        if not parts:
            continue
        if parts[0].startswith("?") or len(parts) < 3:
            return None, "system-managed page file"
        try:
            max_mb = int(parts[-1])
        except ValueError:
            return None, "unparsed PagingFiles entry"
        if max_mb <= 0:
            return None, "system-managed page file"
        total_mb += max_mb
        n += 1
    return total_mb * 1048576, "%d page file(s), max %d MB" % (n, total_mb)


def _cg_pagefile_max() -> tuple:
    """The page files' configured MAXIMUM, read-only from the registry (the values CIM Win32_PageFileSetting reports)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _CG_PF_KEY, 0, winreg.KEY_READ) as k:
            val, _typ = winreg.QueryValueEx(k, "PagingFiles")
    except Exception as e:
        return None, "registry unreadable (%s)" % type(e).__name__
    return _cg_parse_paging_files(val)


def _cg_eval(perf, pf_max, max_pct: float, cur_pct_at_max: float) -> Dict[str, Any]:
    """One sample judged. valid=False means NO sample: the streak is held, never advanced."""
    ev = {"valid": False, "why": "", "pct_max": None, "pct_cur": None, "at_max": None, "over": False, "rule": ""}
    if not perf:
        ev["why"] = "commit counters unreadable"
        return ev
    try:
        total = float(perf["commit_total"])
        limit = float(perf["commit_limit"])
        phys = float(perf["phys_total"])
    except Exception:
        ev["why"] = "commit counters malformed"
        return ev
    if not (total > 0.0 and limit > 0.0 and phys > 0.0):
        ev["why"] = "commit counters not positive"
        return ev
    if pf_max is None:
        ev["why"] = "page-file max unknown"
        return ev
    ceiling = phys + float(pf_max)
    if limit > ceiling * _CG_CEIL_SLACK:
        ev["why"] = "current limit above RAM + page-file max (max read stale or wrong)"
        return ev
    pct_max = 100.0 * total / ceiling
    pct_cur = 100.0 * total / limit
    at_max = limit >= _CG_AT_MAX_FRAC * ceiling
    over_max = pct_max >= max_pct
    over_cur = at_max and pct_cur > cur_pct_at_max
    ev.update(valid=True, pct_max=pct_max, pct_cur=pct_cur, at_max=at_max, ceiling=ceiling,
              over=bool(over_max or over_cur), rule=("max" if over_max else ("current@max" if over_cur else "")))
    return ev


def _cg_http_post(port: int, body: Dict[str, Any], timeout: float) -> tuple:
    """POST JSON to her own /command on 127.0.0.1 (http.client: no proxy setting can reroute it) -> (status, text)."""
    import http.client
    conn = http.client.HTTPConnection("127.0.0.1", int(port), timeout=timeout)
    try:
        conn.request("POST", "/command", body=_json.dumps(body).encode("utf-8"),
                     headers={"Content-Type": "application/json"})
        r = conn.getresponse()
        return r.status, r.read(512).decode("utf-8", "replace")
    finally:
        conn.close()


def _cg_ascii(v, n: int = 160) -> str:
    """ASCII only: her console is cp1252, and a diagnostic must never be the failure."""
    return str(v)[:n].encode("ascii", "replace").decode("ascii")


def _mc_int(v) -> int:
    try:
        return int(v) if not isinstance(v, bool) else 0
    except Exception:
        return 0


def _mc_topic_stats():
    """The pinned postal accessor: the shared TensorFabric (set at server.py:4704-4709) -> topic_stats()."""
    from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_fabric
    fab = get_shared_fabric()
    if fab is None:
        raise RuntimeError("no shared fabric")
    return fab.topic_stats()


def _mc_postal_summary(rows) -> str:
    """'postal pools=N workers=W q_total=Q dropped=D top5=topic:workers/queue/delivered,...' from topic_stats() rows."""
    if not isinstance(rows, (list, tuple)):
        raise TypeError("topic_stats is not a list")
    pools = workers = q_total = dropped = 0
    have_drop = False
    tops = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        w = _mc_int(r.get("workers"))
        q = _mc_int(r.get("queue_depth"))
        d = r.get("dropped", r.get("total_drops"))       # the Python fallback core names it total_drops
        pools += 1
        workers += w
        q_total += q
        if d is not None:
            have_drop = True
            dropped += _mc_int(d)
        dl = r.get("delivered")
        name = "".join("_" if (c.isspace() or c in ",/:") else c for c in _cg_ascii(r.get("topic"), 48))
        tops.append((w, q, name, "-" if dl is None else str(_mc_int(dl))))
    tops.sort(key=lambda t: (-t[0], -t[1], t[2]))
    top5 = ",".join("%s:%d/%d/%s" % (t[2], t[0], t[1], t[3]) for t in tops[:5])
    return ("postal pools=%d workers=%d q_total=%d dropped=%s top5=%s"
            % (pools, workers, q_total, str(dropped) if have_drop else "-", top5 or "-"))


# ----------------------------------------------------------------------------------------------------------------------------
# GARBAGE CENSUS (G1-G4) -- garbage_census_1014 (Nous, 2026-10-15). Design: nous_builds/garbage_census_1014/DESIGN.md, plain words: BUILD.md
# ----------------------------------------------------------------------------------------------------------------------------
# WHY (Ace 10-14): "whatever is doing the leaking does not have a trace id, which is why it is hard to find". LeakHunterAgent below
# counts objects by TYPE ("set 4.4 M") and never says WHOSE they are, and nothing says what its own gc.collect() frees or how long it
# freezes her. This block adds four readings INSIDE LeakHunter's existing pass (no new scan):
#   G1  what the collect frees (objects, private bytes before/after) and how long it stops the world; G1b times EVERY collect in the
#       process with a gc.callbacks watcher and prints one [GcWatch] line per 10 minutes.
#   G2  the garbage itself, by type (DEBUG_SAVEALL around ONE extra collect; gc.garbage is cleared in a finally, the flags restored).
#   G3  who holds a sample of the anonymous sets / dicts / lists (ONE gc.get_referrers pass + budgeted owner hops) and what they hold.
#   G4  how many of those holders are, or belong to, an Organ Template fairy that carries the template's trace identity
#       (self._profile.fairy_id, Organ_Template_0_3_0.py:1218-1228; the tracer_id property reads it), versus modules / singletons / ...
# THE SWITCH -- state/garbage_census.json, re-read when it changes (mtime + size, and at least every 10 s). Absent, unreadable, torn,
#   empty or not an object = TODAY'S behaviour exactly: no watcher, no line, LeakHunter's output byte for byte what it was.
#   Only a JSON true arms it ({"on": true}); "true" and 1 do not. Under an armed switch "g2", "g3" and "watch_all" are on and a JSON
#   false turns one off. Numbers are clamped to [floor, cap] (see _GZ_NUM); bool, str, NaN fall back to the default.
# EVERY pause has a budget set BEFORE it runs (every new stop-the-world call: <= stw_cap_ms, <= run_stw_budget_ms in all) and is SKIPPED,
#   never stretched, when over it, with the numbers printed. Every limiter has a floor. Nothing here raises into her: every path is
#   try/except and prints one ASCII line. No file is written. No allocation tracer is ever started (the stdlib one deadlock-stalls free-threaded 3.14t).
# REVERT: delete state/garbage_census.json (live inside 10 s: the watcher is removed, no census starts); then this file from the
#   installer backup. memory_pressure_fairy.py is ALSO E1's (M0/M1): revert THIS first, then E1 (E1's installer expects 2bc1b5ba).
import random as _random
import math as _math
import heapq as _heapq
import itertools as _itertools
import types as _types

# ---- GC DIET (gc_diet_1015): OFF unless state/gc_diet.json arms a key (absent / torn / not true = today, exactly). ----------------
#   All logic lives in _gc_diet.py next to this file; these are the hooks. One key per collect site: monitor_pressure_no_collect,
#   monitor_periodic_no_collect, autosave_no_collect (server.py and tracer_worker_system.py are NOT edited: a wrapper over gc.collect,
#   installed only while armed and only in her process, tells their callers apart), ladder_no_collect (_do_gc), runaway_no_collect
#   (_on_runaway), leakhunter_no_spawn (_monitor_tick), fast_poll_no_collect (_fast_poll). One shared floor collect (floor_min 45)
#   keeps garbage from growing without bound. REVERT: delete state/gc_diet.json (live, inside 10 s), then this file from the backup.
try:
    from fairies.P00_Autonomic.nervous_system.hardware import _gc_diet as _GD
except Exception:                       # missing or broken module = today's behaviour: every hook below is a no-op
    _GD = None
_GD_LADDER = ("critical", "high", "elevated", "warning")      # the four reasons _monitor_tick passes to _do_gc; "manual" is never gated


def _gd_skip(key, site, min_gap_s=0.0):
    """True = skip this collect / spawn (key on, not in the reversal, the floor not overdue). Never raises: a failure = collect."""
    try:
        return bool(_GD is not None and _GD.skip(key, site, min_gap_s))
    except Exception:
        return False


def _gd_oops(stage, e):
    try:
        if _GD is not None:
            _GD.oops(stage, e)
    except Exception:
        pass


GARBAGE_CENSUS_FILE = _os.path.join(_CG_ROOT, "state", "garbage_census.json")
# key -> (default, floor, cap). An int default gives an int result, a float default a float.
_GZ_NUM = {
    "cap_per_boot": (4, 1, 12), "min_gap_min": (15.0, 5.0, 120.0), "min_uptime_min": (10.0, 3.0, 60.0),
    "force_at_min": (45.0, 15.0, 240.0), "force_window_min": (30.0, 5.0, 120.0), "force_repeat_min": (0.0, 0.0, 240.0),
    "quiet_commit_pct": (78.0, 50.0, 80.0), "census_max_commit_pct": (80.0, 60.0, 84.0),
    "sample_per_type": (200, 10, 500), "biggest_n": (8, 0, 16), "stw_cap_ms": (1500.0, 500.0, 3000.0),
    "run_stw_budget_ms": (4000.0, 1000.0, 8000.0), "cpu_budget_ms": (8000.0, 1000.0, 30000.0),
    "g2_max_objects": (2000000, 10000, 5000000), "owner_hops": (3, 0, 4), "hop_targets": (32, 4, 64),
    "top_n": (15, 5, 30), "watch_line_min": (10.0, 5.0, 60.0), "seed": (0, 0, 2147483647),
}
_GZ_MAX_LINES = 25            # census lines per run (the last one says how many were dropped)
_GZ_LINE_CHARS = 480
_GZ_P2_DELAY_S = 2.0          # G1: private memory is read again this long after the collect (PURGE_DELAY=0 returns pages with a lag)
_GZ_BIG_LEN = 10000           # the 09-05 "oversized container" line (LeakHunter :616-626)
_GZ_MODEL = {"safety": 1.3}   # T(k) = safety * rho * m * T_go * (1.10 + 0.021 k); fitted on the 10-15 probe (DESIGN 5.3)
_GZ_OVERRUN_MIN_MS = 25.0     # an OVERRUN needs actual > 1.5 x predicted AND at least this many ms more (noise on a small heap is not one)
_GZ_MIN_TARGETS = 30          # the floor of G3: even this many targets must fit the limit, else G3 is SKIPPED with the numbers
_GZ_MAX_HOLDERS_PER_NODE = 8
_GZ_MAX_KEEP = 4096           # strong references to holders held during one run
_GZ_VARS_BUDGET = 96          # instances whose __dict__ may be materialised per run (the 09-05 code does this for <= 12)
_GZ_KEEP_FULL = -1            # sentinel holder id: a holder dropped at _GZ_MAX_KEEP still marks its target, as BUDGET (review F5)
_GZ_QUIET_WINDOW_S = 3600.0   # the forced reading needs a MEASURED collect this recent, under stw_cap_ms (review F2)
_GZ_BUSY_STALE_S = 120.0      # a watcher 'busy' flag older than this is stale (its stop never came), not a collect in progress
_GZ_SW = {"key": None, "data": {}, "read": 0.0}
_GZ_SW_LOCK = threading.Lock()
_GZ_RUN_LOCK = threading.Lock()        # one census at a time (a duplicate LeakHunter does today's path only)
_GZ_TICK_LOCK = threading.Lock()
_GZ_T0 = time.time()
_GZ = {"runs_total": 0, "runs_attached": 0, "forced_n": 0, "last_census": 0.0, "force_pending": False, "next_force": None,
       "m": 1.0, "pf": None, "pf_at": 0.0, "create": None, "armed_cfg": None, "w_at": 0.0, "said": set(), "err_at": {},
       "quiet_why": "", "force_tries": 0, "force_thread": None, "force_t": 0.0}


def _gz_switch() -> Dict[str, Any]:
    """state/garbage_census.json as a dict; {} (= today's behaviour) when absent, unreadable, torn or not an object."""
    try:
        st = _os.stat(GARBAGE_CENSUS_FILE)
    except OSError:
        with _GZ_SW_LOCK:
            _GZ_SW["key"], _GZ_SW["data"], _GZ_SW["read"] = None, {}, 0.0
        return {}
    key = (st.st_mtime_ns, st.st_size)
    now = time.time()
    with _GZ_SW_LOCK:
        if key != _GZ_SW["key"] or not (0.0 <= now - float(_GZ_SW["read"]) <= 10.0):
            try:
                with open(GARBAGE_CENSUS_FILE, "rb") as f:
                    d = _json.loads(f.read().decode("utf-8-sig"))      # a hand-edited file may carry a BOM
                _GZ_SW["data"], _GZ_SW["key"], _GZ_SW["read"] = (d if isinstance(d, dict) else {}), key, now
            except Exception:
                _GZ_SW["data"], _GZ_SW["key"], _GZ_SW["read"] = {}, None, 0.0   # torn or bad: today's path, read again
        return dict(_GZ_SW["data"])


def _gz_num(sw: Dict[str, Any], key: str):
    """A switch number clamped to its floor and cap; missing, bool, str, non-numeric or NaN -> its default."""
    dflt, lo, hi = _GZ_NUM[key]
    v = sw.get(key, dflt)
    try:
        if isinstance(v, (bool, str)):
            raise ValueError(v)
        x = float(v)
        if x != x:
            raise ValueError(v)
    except Exception:
        x = float(dflt)
    x = min(max(x, float(lo)), float(hi))
    return int(round(x)) if isinstance(dflt, int) else x


def _gz_cfg(sw: Dict[str, Any]) -> Dict[str, Any]:
    """Every setting of an ARMED switch, clamped. 'on' itself is judged by the caller (only a JSON true arms)."""
    c = {k: _gz_num(sw, k) for k in _GZ_NUM}
    if c["force_repeat_min"] > 0.0:
        c["force_repeat_min"] = max(30.0, c["force_repeat_min"])          # 1..29 become 30; 0 stays 0 (off)
    for k in ("g2", "g3", "watch_all"):
        c[k] = sw.get(k) is not False                                      # on under an armed switch; only a JSON false turns it off
    return c


def _gz_her_main():
    """Her server module (__main__ = server.py, carrying SYSTEM + shutdown_system), or None in any other process."""
    m = sys.modules.get(_CG_MAIN)
    if m is not None and getattr(m, "SYSTEM", None) is not None and callable(getattr(m, "shutdown_system", None)):
        return m
    return None


def _gz_pc() -> float:
    return time.perf_counter()


def _gz_now() -> float:
    return time.time()


def _gz_uptime_min(now=None) -> float:
    """Process uptime in minutes (psutil create_time, as M1 does); this module's import time when that cannot be read."""
    try:
        if _GZ["create"] is None:
            _GZ["create"] = float(psutil.Process().create_time())
        base = _GZ["create"]
    except Exception:
        base = _GZ_T0
    return ((_gz_now() if now is None else now) - base) / 60.0


def _gz_private():
    """Private bytes of this process (psutil memory_info().private, as M1 reads it); None when it cannot be read."""
    try:
        mi = psutil.Process().memory_info()
        return float(getattr(mi, "private", mi.vms))
    except Exception:
        return None


def _gz_commit():
    """-> (commit % of RAM + page-file max or None, available RAM in GB or None). Never raises."""
    pct, avail = None, None
    try:
        perf = _cg_perf()
        if perf:
            avail = float(perf["phys_avail"]) / 2 ** 30
            now = _gz_now()
            pf = _GZ["pf"]
            if pf is None or (pf[0] is None and not (0.0 <= now - float(_GZ["pf_at"]) < _CG_PF_REREAD_S)):
                pf = _GZ["pf"] = _cg_pagefile_max()
                _GZ["pf_at"] = now
            if pf[0] is not None:
                ceiling = float(perf["phys_total"]) + float(pf[0])
                if ceiling > 0.0 and float(perf["commit_limit"]) <= ceiling * _CG_CEIL_SLACK:
                    pct = 100.0 * float(perf["commit_total"]) / ceiling
    except Exception:
        pass
    return pct, avail


def _gz_say_once(tag: str, line: str) -> None:
    try:
        if tag in _GZ["said"]:
            return
        _GZ["said"].add(tag)
        print(_cg_ascii(line, _GZ_LINE_CHARS), flush=True)
    except Exception:
        pass


def _gz_line(ctx: Dict[str, Any], text: str) -> None:
    """One census line, ASCII, <= 480 chars, <= _GZ_MAX_LINES per run (extras are counted, not printed)."""
    try:
        if len(ctx["lines"]) >= _GZ_MAX_LINES - 2:          # room is kept for the G1 line and the "dropped" note
            ctx["dropped"] += 1
            return
        ctx["lines"].append(_cg_ascii(text, _GZ_LINE_CHARS))
    except Exception:
        pass


def _gz_oops(ctx, stage: str, exc: BaseException) -> None:
    """An error is ONE ASCII line per stage (per run, or per 300 s outside a run). It is never raised on."""
    try:
        line = _cg_ascii("[GcCensus] %s error (non-fatal): %s: %s" % (stage, type(exc).__name__, _cg_ascii(exc, 120)), _GZ_LINE_CHARS)  # GZ-ASCII
        if ctx is not None:
            if stage in ctx["errs"]:
                return
            ctx["errs"].add(stage)
            ctx["errlines"].append(line)
            return
        now = _gz_now()
        last = _GZ["err_at"].get(stage)
        if last is not None and 0.0 <= now - last < 300.0:
            return
        _GZ["err_at"][stage] = now
        print(line, flush=True)
    except Exception:
        pass


def _gz_sz(nbytes) -> str:
    try:
        return "%.2fMB" % (float(nbytes) / 1048576.0) if abs(nbytes) < 2 ** 30 else "%.2fGB" % (float(nbytes) / 2 ** 30)
    except Exception:
        return "?"


def _gz_top(pairs, limit_chars: int = 380) -> str:
    """'label count; label count' until the text would pass limit_chars."""
    out, used = [], 0
    for lab, n in pairs:
        s = "%s %s" % (lab, n)
        if used + len(s) + 2 > limit_chars and out:
            out.append("...")
            break
        out.append(s)
        used += len(s) + 2
    return "; ".join(out)


# ---- G1b: the watcher. Every collect in the process, from any thread. Registered ONLY while the switch is armed. ----------------
def _gz_win() -> Dict[str, Any]:
    return {"n": 0, "found": 0, "fmax": 0, "sum": 0.0, "max": 0.0, "dts": [], "thr": {}}


_GZW = {"busy": False, "t0": 0.0, "thr": "", "n": 0, "ring": deque(maxlen=64), "w": _gz_win(), "s": _gz_win()}


def _gz_watch_cb(phase, info) -> None:
    """gc.callbacks hook. Tiny, allocation-bounded, never raises, no print, no lock. It NEVER calls threading.current_thread() (on a
    foreign thread that would create a permanent _DummyThread): the thread name comes from threading._active.get(get_ident())."""
    try:
        g = _GZW
        if phase == "start":
            g["t0"] = time.perf_counter()
            g["busy"] = True
            th = threading._active.get(threading.get_ident())
            g["thr"] = str(th.name)[:32] if th is not None else "foreign"
        elif phase == "stop":
            dt = (time.perf_counter() - g["t0"]) if g["t0"] else 0.0
            g["busy"] = False
            f = 0
            if isinstance(info, dict):
                c = info.get("collected", 0)
                if isinstance(c, int) and not isinstance(c, bool):
                    f = c
            name = g["thr"]
            g["n"] += 1
            g["ring"].append((_gz_now(), dt, f, name))
            for w in (g["w"], g["s"]):
                w["n"] += 1
                w["found"] += f
                w["sum"] += dt
                if f > w["fmax"]:
                    w["fmax"] = f
                if dt > w["max"]:
                    w["max"] = dt
                thr = w["thr"]
                if name in thr or len(thr) < 32:
                    thr[name] = thr.get(name, 0) + 1
                else:
                    thr["other"] = thr.get("other", 0) + 1
            if len(g["w"]["dts"]) < 512:
                g["w"]["dts"].append(dt)
    except Exception:
        pass


def _gz_watch_present() -> bool:
    try:
        return any(cb is _gz_watch_cb for cb in list(gc.callbacks))
    except Exception:
        return False


def _gz_watch_busy() -> bool:
    """A collect is in progress (the watcher saw its start and not yet its stop). A flag older than _GZ_BUSY_STALE_S is stale."""
    try:
        return bool(_GZW["busy"]) and (time.perf_counter() - float(_GZW["t0"])) < _GZ_BUSY_STALE_S
    except Exception:
        return False


def _gz_watch_set(on: bool) -> bool:
    """Register the watcher once (identity check), or remove every copy of it. Touches nothing else in gc.callbacks.
    Never while a collect is in progress (review F6): on the free-threaded build a collecting thread walks gc.callbacks by index
    without the list's lock, so the list op is simply left to the next heartbeat. No wait, no lock. -> True when the state is as asked."""
    try:
        present = _gz_watch_present()
        if bool(on) == present:
            return True
        if _gz_watch_busy():                                  # GZ-BUSY
            return False
        if on:
            gc.callbacks.append(_gz_watch_cb)
        else:
            for _i in range(8):
                if not _gz_watch_present():
                    break
                try:
                    gc.callbacks.remove(_gz_watch_cb)
                except ValueError:
                    break
        return _gz_watch_present() == bool(on)
    except Exception:
        return False


def _gz_watch_max_ms(window_s: float = 600.0):
    """The longest collect wall seen in HER process in the last window_s seconds, in ms; None when none was measured."""
    try:
        now = _gz_now()
        best = None
        for t, dt, _f, _thr in list(_GZW["ring"]):
            if 0.0 <= now - t <= window_s and (best is None or dt > best):
                best = dt
        return None if best is None else best * 1e3
    except Exception:
        return None


def _gz_watch_line(now: float) -> str:
    """The [GcWatch] line for the window since the last one; resets the window."""
    w = _GZW["w"]
    _GZW["w"] = _gz_win()
    dts = sorted(w["dts"])
    med = dts[len(dts) // 2] if dts else 0.0
    thr = sorted(w["thr"].items(), key=lambda kv: (-kv[1], kv[0]))
    try:
        dbg = gc.get_debug()
        garb = len(gc.garbage)
    except Exception:
        dbg, garb = "?", "?"
    return ("[GcWatch] up=%.1fmin last %.1fmin: collects=%d found=%d (max %d) wall sum=%.2fs max=%.0fms med=%.0fms | by thread: %s "
            "| gc.garbage=%s debug=%s" % (_gz_uptime_min(now), max(0.0, (now - float(_GZ["w_at"])) / 60.0), w["n"], w["found"],
                                          w["fmax"], w["sum"], w["max"] * 1e3, med * 1e3,
                                          _gz_top([(k, v) for k, v in thr[:6]], 160) or "-", garb, dbg))


# ---- type and size helpers: only type-level attributes and exact builtin types are touched, so no user code ever runs ----------
_TY_MOD = type.__dict__["__module__"]
_TY_QN = type.__dict__["__qualname__"]
_TY_NM = type.__dict__["__name__"]
_TY_MRO = type.__dict__["__mro__"]
_GZ_FT = _types.FunctionType
_GZ_MT = _types.MethodType
_GZ_BT = _types.BuiltinFunctionType
_GZ_GEN = _types.GeneratorType
_GZ_COR = _types.CoroutineType
_GZ_AGEN = _types.AsyncGeneratorType
_GZ_FRAME = _types.FrameType
_GZ_CELL = _types.CellType
# ids, not the types: a set lookup hashes the probed type, and a metaclass may define __hash__ / __eq__ (no user code, review F4)
_GZ_EXACT_T = (int, float, complex, str, bytes, bytearray, tuple, list, dict, set, frozenset, bool, range, slice, type,
               type(None), _GZ_FT, _GZ_MT, _GZ_BT, _GZ_GEN, _GZ_COR, _GZ_AGEN, _GZ_FRAME, _GZ_CELL, _types.CodeType,
               _types.ModuleType, deque)
_GZ_EXACT = frozenset(id(_t) for _t in _GZ_EXACT_T)


def _gz_in(t, mro) -> bool:
    """t is one of the classes in mro, by identity (a tuple 'in' would call a metaclass __eq__)."""
    for c in mro:
        if c is t:
            return True
    return False


def _gz_tname(t) -> str:
    """'module.qualname' of a type, read from the type itself (never getattr on an instance, never a metaclass property)."""
    try:
        m = _TY_MOD.__get__(t)
        q = _TY_QN.__get__(t)
    except Exception:
        return "?"
    return "%s.%s" % (m if type(m) is str else "?", q if type(q) is str else "?")


def _gz_tmod(t) -> str:
    try:
        m = _TY_MOD.__get__(t)
        return m if type(m) is str else ""
    except Exception:
        return ""


def _gz_tbare(t) -> str:
    try:
        n = _TY_NM.__get__(t)
        return n if type(n) is str else "?"
    except Exception:
        return "?"


def _gz_mro(t):
    try:
        return _TY_MRO.__get__(t)
    except Exception:
        return ()


# ---- instance attributes without user code (review F4) ---------------------------------------------------------------------------
# object.__getattribute__ skips a class's __getattribute__ / __getattr__, but it still runs a DESCRIPTOR it finds on the type: a user
# property named _profile (or __dict__, _tracer_id, fairy_id, _name, __name__) would run. So the type's MRO is read first (type-level
# dicts only) and the attribute is read only when no class defines that name, or defines it as a C slot (getset / member descriptor,
# e.g. the standard __dict__) or as a plain value whose type has no __get__ (a str / None default). Otherwise it is skipped and counted.
_TY_DICT = type.__dict__["__dict__"]
_GZ_NOATTR = object()


def _gz_attr_safe(ctx, t, name: str) -> bool:
    cache = ctx.get("asafe") if ctx is not None else None
    key = (id(t), name)
    if cache is not None:
        ent = cache.get(key)
        if ent is not None:
            return ent[1]
    ok = True
    try:
        for c in _gz_mro(t):
            d = _TY_DICT.__get__(c)
            if name in d:
                td = type(d[name])
                if not (td is _types.GetSetDescriptorType or td is _types.MemberDescriptorType):
                    for cc in _gz_mro(td):
                        if "__get__" in _TY_DICT.__get__(cc):
                            ok = False
                            break
                break
    except Exception:
        ok = False
    if cache is not None:
        try:
            cache[key] = (t, ok)                       # the type is kept with its id, so the id cannot be reused within the run
        except Exception:
            pass
    return ok


def _gz_getattr(ctx, r, name: str):
    """object.__getattribute__(r, name) when that can run no user code; _GZ_NOATTR when it could, or when r has no such attribute."""
    try:
        if not _gz_attr_safe(ctx, type(r), name):            # GZ-DESC
            if ctx is not None:
                ctx["desc_skip"] = ctx.get("desc_skip", 0) + 1
            return _GZ_NOATTR
        return object.__getattribute__(r, name)
    except Exception:
        return _GZ_NOATTR


def _gz_size(o, t) -> int:
    """Shallow size: sys.getsizeof for exact builtin types only, otherwise object.__sizeof__ (a user __sizeof__ never runs)."""
    try:
        return sys.getsizeof(o) if id(t) in _GZ_EXACT else object.__sizeof__(o)
    except Exception:
        return 0


def _gz_strattr(v) -> str:
    return _cg_ascii(v, 60) if type(v) is str else "?"          # type(v) is str: isinstance could look up a user __class__


def _gz_code_name(o, t):
    """A short name for a function-like or generator-like object of an EXACT builtin type; None for anything else."""
    try:
        if t is _GZ_FT:
            return "function:%s.%s" % (_gz_strattr(o.__module__), _gz_strattr(o.__qualname__))
        if t is _GZ_MT:
            f = o.__func__
            if type(f) is _GZ_FT:
                return "method:%s.%s" % (_gz_strattr(f.__module__), _gz_strattr(f.__qualname__))
            return "method:?"
        if t is _GZ_BT:
            return "builtin:%s.%s" % (_gz_strattr(o.__module__), _gz_strattr(o.__qualname__))
        if t is _GZ_GEN:
            return "code:" + _gz_strattr(o.gi_code.co_qualname)
        if t is _GZ_COR:
            return "code:" + _gz_strattr(o.cr_code.co_qualname)
        if t is _GZ_AGEN:
            return "code:" + _gz_strattr(o.ag_code.co_qualname)
        if t is _GZ_FRAME:
            return "code:" + _gz_strattr(o.f_code.co_qualname)
    except Exception:
        return "?"
    return None


# ---- G2: the garbage by type ----------------------------------------------------------------------------------------------------
def _gz_g2_count(pre: int, max_obj: int, cpu_ms: float) -> Dict[str, Any]:
    """Count gc.garbage[pre:] by type: {key: [count, shallow bytes]}. Runs with the world RUNNING. The FLOOR counts iterations (not
    produced rows): 10,000 objects are always counted; past that the cpu budget or max_obj ends it as PARTIAL, never stretched."""
    garbage = gc.garbage
    total = max(0, len(garbage) - pre)
    stop = min(len(garbage), pre + max_obj)
    rows: Dict[str, list] = {}
    t0 = _gz_pc()
    i = pre
    partial = False
    o = None
    while i < stop:
        try:
            o = garbage[i]
        except IndexError:
            break
        t = type(o)
        key = _gz_code_name(o, t) or _gz_tname(t)
        r = rows.get(key)
        if r is None:
            r = rows[key] = [0, 0]
        r[0] += 1
        r[1] += _gz_size(o, t)
        i += 1
        n = i - pre
        if n >= 10000 and (n & 255) == 0 and (_gz_pc() - t0) * 1e3 > cpu_ms:
            partial = True
            break
    o = None
    n = i - pre
    return {"rows": rows, "n": n, "total": total, "partial": partial or (stop - pre < total)}


def _gz_g2(ctx: Dict[str, Any]) -> None:
    """ONE extra stop-the-world collect with DEBUG_SAVEALL, a census of what it saved, then gc.garbage CLEARED and the flags restored
    (the flags BEFORE the census, so the window in which another thread's collect could save into gc.garbage is as short as it can
    be). The collect that LeakHunter makes next (B2) is what really frees the garbage."""
    cfg = ctx["cfg"]
    if not cfg["g2"]:
        _gz_line(ctx, "[GcCensus] G2 skipped: g2=false in the switch")
        return
    pre = len(gc.garbage)
    if pre != 0:
        _gz_line(ctx, "[GcCensus] G2 skipped: gc.garbage already holds %d objects that are not ours" % pre)
        return
    if _GZW["busy"]:
        t_end = _gz_pc() + 2.0
        while _GZW["busy"] and _gz_pc() < t_end:
            time.sleep(0.05)
        if _GZW["busy"]:
            _gz_line(ctx, "[GcCensus] G2 skipped: another collect was still running after 2 s")
            return
    pred = _gz_watch_max_ms()
    remaining = cfg["run_stw_budget_ms"] - ctx["stw_ms"]
    if pred is None:
        _gz_line(ctx, "[GcCensus] G2 skipped: no measured pause yet (the watcher saw no collect in the last 10 min)")
        return
    if pred > cfg["stw_cap_ms"] or pred > remaining:
        _gz_line(ctx, "[GcCensus] G2 skipped: the longest collect in the last 10 min took %.0fms > limit %.0fms (cap %.0f, run "
                      "budget left %.0f)" % (pred, min(cfg["stw_cap_ms"], remaining), cfg["stw_cap_ms"], remaining))
        return
    ring = list(_GZW["ring"])
    since = ""
    if ring:
        since = " (since last collect %.1fs by %s)" % (max(0.0, _gz_now() - ring[-1][0]), _cg_ascii(ring[-1][3], 32))
    old = gc.get_debug()
    found = 0
    pause_ms = 0.0
    t0 = _gz_pc()
    try:
        try:
            gc.set_debug(old | gc.DEBUG_SAVEALL)         # GZ-SAVEALL
            found = gc.collect()
        finally:
            gc.set_debug(old)                            # GZ-RESTORE
            pause_ms = (_gz_pc() - t0) * 1e3
            ctx["stw_ms"] += pause_ms
        if gc.get_debug() != old:                        # restored before the census; make sure, and say so loudly
            gc.set_debug(old)
            _gz_line(ctx, "[GcCensus] G2 WARNING: gc debug flags were not restored by the first try; set again to %s" % old)
        t_c = _gz_pc()
        res = _gz_g2_count(pre, cfg["g2_max_objects"], cfg["cpu_budget_ms"] - ctx["cpu_ms"])
        census_ms = (_gz_pc() - t_c) * 1e3
        ctx["cpu_ms"] += census_ms
        rows = res["rows"]
        nbytes = sum(v[1] for v in rows.values())
        ctx["g2"] = {"found": found, "pause_ms": pause_ms, "garbage": res["n"], "bytes": nbytes, "rows": len(rows)}
        by_count = sorted(rows.items(), key=lambda kv: (-kv[1][0], -kv[1][1], kv[0]))
        by_bytes = sorted(rows.items(), key=lambda kv: (-kv[1][1], -kv[1][0], kv[0]))
        top = cfg["top_n"]
        part = " PARTIAL %d/%d" % (res["n"], res["total"]) if res["partial"] else ""
        _gz_line(ctx, "[GcCensus] G2 garbage=%d objs %s%s%s census=%.0fms | by count: %s" % (
            res["n"], _gz_sz(nbytes), part, since, census_ms,
            _gz_top([(k, "%d %s" % (v[0], _gz_sz(v[1]))) for k, v in by_count[:top]]) or "(none)"))
        if [k for k, _v in by_bytes[:5]] != [k for k, _v in by_count[:5]]:
            _gz_line(ctx, "[GcCensus] G2 by bytes: %s" % _gz_top([(k, "%s %d" % (_gz_sz(v[1]), v[0])) for k, v in by_bytes[:top]]))
    finally:
        try:
            del gc.garbage[pre:]                         # GZ-CLEAR: the census must never be why garbage stays alive
        except Exception:
            pass


# ---- G3 / G4: who holds the anonymous containers, and do they carry a trace id ---------------------------------------------------
class _GzRes(object):
    """One Algorithm-L reservoir (Li 1994): k slots, about k*(1+ln(N/k)) random draws for N objects, not one per object."""
    __slots__ = ("n", "nxt", "w", "items")

    def __init__(self):
        self.n = 0
        self.nxt = 0
        self.w = 1.0
        self.items = []


class _GzSampler(object):
    """Samples set / dict / list objects DURING the scan LeakHunter already makes (no second walk) and keeps the few biggest
    ones as their own stratum (a uniform sample by count misses the giants that hold the bytes). Never raises: on an error it
    records it and stops sampling. It holds strong references until _gz_drop()."""
    __slots__ = ("k", "nbig", "rnd", "res", "heap", "ctr", "err", "seed")

    def __init__(self, k: int, nbig: int, seed: int):
        self.k = int(k)
        self.nbig = int(nbig)
        self.seed = int(seed)
        self.rnd = _random.Random(self.seed)
        self.res = {set: _GzRes(), dict: _GzRes(), list: _GzRes()}
        self.heap = []
        self.ctr = 0
        self.err = None

    def _advance(self, r) -> None:
        rnd = self.rnd.random
        r.w *= _math.exp(_math.log(1.0 - rnd()) / self.k)
        lw = _math.log(max(1.0 - r.w, 1e-300))
        step = _math.log(1.0 - rnd()) / lw if lw != 0.0 else 1.0
        r.nxt = r.n + int(min(step, 1e15)) + 1

    def feed(self, t, obj) -> None:
        try:
            r = self.res[t]
            n = r.n = r.n + 1
            if n <= self.k:
                r.items.append(obj)
                if n == self.k:
                    self._advance(r)
            elif n == r.nxt:
                r.items[self.rnd.randrange(self.k)] = obj
                self._advance(r)
            if self.nbig:
                ln = len(obj)
                if ln > _GZ_BIG_LEN:
                    h = self.heap
                    self.ctr += 1
                    if len(h) < self.nbig:
                        _heapq.heappush(h, (ln, self.ctr, obj))
                    elif ln > h[0][0]:
                        _heapq.heapreplace(h, (ln, self.ctr, obj))
        except Exception as e:
            self.err = "%s: %s" % (type(e).__name__, _cg_ascii(e, 80))


def _gz_sampler(ctx: Dict[str, Any]):
    """The sampler of this run (created before the scan; None when G3 is off)."""
    cfg = ctx["cfg"]
    if not cfg["g3"]:
        return None
    seed = cfg["seed"] or int.from_bytes(_os.urandom(4), "little")
    ctx["seed"] = seed
    ctx["samp"] = _GzSampler(cfg["sample_per_type"], cfg["biggest_n"], seed)
    return ctx["samp"]


def _gz_price_ms(ctx: Dict[str, Any], k: int) -> float:
    """Predicted stop-the-world time of ONE gc.get_referrers(*k targets), in ms: safety * rho * m * T_go * (1.10 + 0.021 k)."""
    return _GZ_MODEL["safety"] * ctx["rho"] * _GZ["m"] * ctx["t_go_ms"] * (1.10 + 0.021 * k)


def _gz_k_for(ctx: Dict[str, Any], limit_ms: float) -> int:
    """The largest k whose predicted time fits limit_ms (can be < 0)."""
    base = _GZ_MODEL["safety"] * ctx["rho"] * _GZ["m"] * ctx["t_go_ms"]
    if base <= 0.0:
        return 10 ** 6
    return int((limit_ms / base - 1.10) / 0.021)


def _gz_codes():
    """Code objects of the census itself: a frame running one of them is never reported as a holder."""
    out = set()
    try:
        for name, fn in list(globals().items()):
            if name.startswith("_gz_") and type(fn) is _GZ_FT:
                out.add(fn.__code__)
        out.add(LeakHunterAgent.run.__code__)
    except Exception:
        pass
    return out


def _gz_ref_ok(ctx: Dict[str, Any], r, nodes) -> bool:
    """False for the census's own containers: get_referrers reports the call's args tuple and the caller's lists (probe)."""
    if id(r) in ctx["own"]:                              # GZ-OWN
        ctx["self_excl"] += 1
        return False
    tr = type(r)
    if tr is tuple and len(r) == len(nodes):
        same = True
        for a, b in zip(r, nodes):
            if a is not b:
                same = False
                break
        if same:
            ctx["self_excl"] += 1
            return False
    if tr is _GZ_FRAME:
        try:
            if r.f_code in ctx["codes"]:
                ctx["self_excl"] += 1
                return False
        except Exception:
            pass
    return True


def _gz_map_ref(ctx: Dict[str, Any], r, nids, kind: str = "instance") -> list:
    """The edges from referrer r to a node in nids: [(node id, key or None)]. Reads builtin containers directly; for an instance it
    may materialise its __dict__ (at most _GZ_VARS_BUDGET per run) through object.__getattribute__, else uses gc.get_referents.
    Stops at the cpu deadline only after the first 10 referrers (the floor counts referrers mapped, not edges found)."""
    out = []
    tr = type(r)
    mro = _gz_mro(tr)
    ctx["mapped"] += 1
    try:
        if _gz_in(dict, mro):
            n = 0
            for k, v in dict.items(r):
                iv = id(v)
                if iv in nids:
                    out.append((iv, k if type(k) is str else None))
                n += 1
                if (n & 8191) == 0 and ctx["mapped"] > 10 and _gz_pc() > ctx["deadline"]:
                    ctx["partial_map"] = True
                    break
            return out
        seq = None
        for base in (list, tuple, deque, set, frozenset):
            if _gz_in(base, mro):
                seq = base.__iter__(r)
                break
        if seq is not None:
            n = 0
            for v in seq:
                iv = id(v)
                if iv in nids:
                    out.append((iv, None))
                n += 1
                if (n & 8191) == 0 and ctx["mapped"] > 10 and _gz_pc() > ctx["deadline"]:
                    ctx["partial_map"] = True
                    break
            return out
        d = None
        if kind == "instance" and ctx["vars_left"] > 0:         # only a user instance may have its __dict__ materialised
            ctx["vars_left"] -= 1
            d = _gz_getattr(ctx, r, "__dict__")                 # a user property named __dict__ is never run (review F4)
        if type(d) is dict:
            for k, v in dict.items(d):
                iv = id(v)
                if iv in nids:
                    out.append((iv, k if type(k) is str else None))
        if not out:
            for v in gc.get_referents(r):
                iv = id(v)
                if iv in nids:
                    out.append((iv, None))
    except RuntimeError:
        ctx["mutating"] += 1                      # a container changed size under us: keep what was found
    except Exception:
        pass
    return out


def _gz_fid_ot(ctx, r) -> bool:
    """Does this Organ Template fairy carry its trace identity? self._profile.fairy_id (Organ_Template_0_3_0.py:1218-1228), else a
    non-empty self._tracer_id (:1236). Read through _gz_getattr: the tracer_id PROPERTY (:3919) is never called, and neither is a
    user property that a fairy class might define under one of these names (review F4)."""
    try:
        p = _gz_getattr(ctx, r, "_profile")
        if p is not _GZ_NOATTR and _gz_tbare(type(p)) == "FairyProfile":
            v = _gz_getattr(ctx, p, "fairy_id")
            if type(v) is str and v:
                return True
    except Exception:
        pass
    try:
        v = _gz_getattr(ctx, r, "_tracer_id")
        if type(v) is str and v:
            return True
    except Exception:
        pass
    return False


def _gz_fid_legacy(ctx, r) -> bool:
    try:
        v = _gz_getattr(ctx, r, "fairy_id")                  # fairy_template/consolidated.py:1054
        return type(v) is str and bool(v)
    except Exception:
        return False


def _gz_instance(ctx: Dict[str, Any], r, tr, mro):
    tc = ctx["tcache"]
    ent = tc.get(id(tr))                                     # keyed by id: hashing the type could run a metaclass __hash__
    if ent is not None and ent[4] is not tr:
        ent = None
    if ent is None:
        ot = legacy = False
        for c in mro:
            nm, md = _gz_tbare(c), _gz_tmod(c)
            if nm == "AkashicActorCore" and md.endswith("Organ_Template_0_3_0"):
                ot = True                                    # suffix match: a duplicate module object still counts (server.py:515-525)
            elif nm == "MyFairy" and "fairy_template" in md and md.endswith("consolidated"):
                legacy = True
        infra = (not ot) and _gz_tmod(tr).endswith("Organ_Template_0_3_0")
        ent = tc[id(tr)] = (ot, legacy, infra, _gz_tname(tr), tr)
    ot, legacy, infra, name, _tr = ent
    fid = _gz_fid_ot(ctx, r) if ot else (_gz_fid_legacy(ctx, r) if legacy else False)
    return ("instance", name, bool(ot or legacy or infra), {"ot": ot, "legacy": legacy, "infra": infra, "fid": fid})


def _gz_classify(ctx: Dict[str, Any], r):
    """(kind, label, term, info) of one holder. term=True stops the climb. Types are read from the type; instance attributes only
    through _gz_getattr (no __getattribute__ / __getattr__ override and no user descriptor runs); MRO tests are by identity."""
    tr = type(r)
    try:
        if tr is dict:
            if "__name__" in r and "__spec__" in r:
                return ("module", _gz_strattr(r.get("__name__")), True, None)
            if "__module__" in r and ("__dict__" in r or "__weakref__" in r or "__qualname__" in r or "__init__" in r
                                      or "__static_attributes__" in r or "__firstlineno__" in r):
                return ("classdict", "", False, None)
            return ("anon", "dict", False, None)
        if tr is list or tr is tuple or tr is set or tr is frozenset or tr is deque:
            return ("anon", _gz_tbare(tr), False, None)
        if tr is _GZ_CELL:
            return ("anon", "cell", False, None)
        cn = _gz_code_name(r, tr)
        if cn is not None:
            return ("code" if cn.startswith("code:") else "function", cn, True, None)
        mro = _gz_mro(tr)
        if _gz_in(type, mro):
            return ("class", _gz_tname(r), True, None)
        if _gz_in(threading.Thread, mro):
            return ("thread", "thread " + _gz_strattr(_gz_getattr(ctx, r, "_name")), True, None)
        if _gz_in(_types.ModuleType, mro):
            return ("module", _gz_strattr(_gz_getattr(ctx, r, "__name__")), True, None)
        if _gz_tmod(tr) in ("builtins", "collections"):
            for base in (dict, list, tuple, set, frozenset, deque):
                if _gz_in(base, mro):
                    return ("anon", _gz_tbare(tr), False, None)
        return _gz_instance(ctx, r, tr, mro)
    except Exception:
        return ("anon", "?", False, None)


_GZ_RANK = {"thread": 1, "code": 1, "function": 1, "class": 2, "classdict": 3, "anon": 5, "module": 6}
_GZ_BUCKETS = ("TRACED-direct", "TRACED-via", "FAIRY-NO-ID", "LEGACY-ID", "TEMPLATE-INFRA", "MODULE-GLOBAL", "SINGLETON",
               "CLASS-ATTR", "INSTANCE", "THREAD/CODE", "UNREACHED")
_GZ_BSHORT = {"TRACED-direct": "direct", "TRACED-via": "via", "FAIRY-NO-ID": "no-id", "LEGACY-ID": "legacy",
              "TEMPLATE-INFRA": "infra", "MODULE-GLOBAL": "module", "SINGLETON": "singleton", "CLASS-ATTR": "class-attr",
              "INSTANCE": "instance", "THREAD/CODE": "code", "UNREACHED": "unreached"}


def _gz_rank(ctx: Dict[str, Any], hid: int) -> int:
    kind, _label, term, _info = ctx["cls"][hid]
    if kind == "instance":
        return 0 if term else 4
    return _GZ_RANK.get(kind, 7)


def _gz_resolve(ctx: Dict[str, Any], tid: int, final: bool = False):
    """Walk up from target id tid through the holders found so far.
    -> (bucket, owner label, path of anonymous containers, stop node id or None, fairy class or None).
    bucket BUDGET with a stop node = the holders of that node were never asked for (outside the denominator of G4)."""
    holders, cls, keep, queried = ctx["holders"], ctx["cls"], ctx["keep"], ctx["queried"]
    node = tid
    path: list = []
    owner = None
    plain = False
    last_key = None
    cdkey = None
    seen = {tid}
    for _depth in range(ctx["cfg"]["owner_hops"] + 2):
        hs = holders.get(node)
        if not hs:
            if node in queried:
                return ("INSTANCE" if plain else "UNREACHED", owner, path, None, None)
            return ("BUDGET", owner, path, node, None)
        hid, key = min(hs, key=lambda h: (_gz_rank(ctx, h[0]), h[0]))
        if hid in seen:
            return ("UNREACHED", owner, path, None, None)
        seen.add(hid)
        kind, label, term, info = cls[hid]
        if kind == "budget":                                 # its holder was dropped at _GZ_MAX_KEEP: not asked, not counted
            return ("BUDGET", owner, path, None, None)
        if kind == "anon":
            path.append(label)
            last_key = key
            node = hid
            continue
        if kind == "classdict":
            cdkey = key
            if not holders.get(hid):
                if final or hid in queried:
                    try:
                        mod = _gz_strattr(keep[hid].get("__module__"))
                    except Exception:
                        mod = "?"
                    return ("CLASS-ATTR", "class-attr %s.?.%s" % (mod, _gz_strattr(key)), path, None, None)
                return ("BUDGET", owner, path, hid, None)
            node = hid
            continue
        if kind == "class":
            if cdkey is not None:
                return ("CLASS-ATTR", "class-attr %s.%s" % (label, _gz_strattr(cdkey)), path, None, None)
            return ("CLASS-ATTR", "class " + label, path, None, None)
        if kind in ("thread", "code", "function"):
            return ("THREAD/CODE", owner or label, path, None, None)
        if kind == "module":
            return ("SINGLETON" if plain else "MODULE-GLOBAL", owner or ("module %s:%s" % (label, _gz_strattr(key))), path, None, None)
        if kind == "instance":
            alias = False
            if key is None and path and path[-1] == "dict":
                try:
                    alias = _gz_getattr(ctx, keep[hid], "__dict__") is keep.get(node)
                except Exception:
                    alias = False
            if alias:
                path.pop()                                       # the instance's own materialised __dict__ is the instance
                attr = last_key
            else:
                attr = key
            if owner is None:
                owner = label + ("." + attr if isinstance(attr, str) else "")
            if term:
                if info["ot"]:
                    if info["fid"]:
                        return ("TRACED-direct" if (not path and not plain) else "TRACED-via", owner, path, None, label)
                    return ("FAIRY-NO-ID", owner, path, None, label)
                if info["legacy"]:
                    return ("LEGACY-ID" if info["fid"] else "FAIRY-NO-ID", owner, path, None, label)
                return ("TEMPLATE-INFRA", owner, path, None, label)
            plain = True
            last_key = None
            node = hid
            continue
        return ("UNREACHED", owner, path, None, None)
    return ("BUDGET", owner, path, node, None)


def _gz_lenb(n: int) -> str:
    if n == 0:
        return "0"
    if n == 1:
        return "1"
    if n <= 4:
        return "2-4"
    if n <= 16:
        return "5-16"
    if n <= 256:
        return "17-256"
    if n <= 4096:
        return "257-4K"
    if n <= 65536:
        return "4K-64K"
    return ">64K"


_GZ_LENORDER = ("0", "1", "2-4", "5-16", "17-256", "257-4K", "4K-64K", ">64K")


def _gz_signature(ctx: Dict[str, Any], objs, t) -> str:
    """What the sampled containers HOLD (a set of node ids and a set of strings point at different code): the size histogram, the
    element type mix (top 4), the mean builtin element size; for dicts also key/value mix, key SHAPE (sorted first-6 str keys, the
    June LEAK-2 method) and how many carry a tracer_id / trace_id / fairy_id key. <= 64 elements per container are looked at."""
    lens: Dict[str, int] = {}
    et: Dict[str, int] = {}
    vt: Dict[str, int] = {}
    shapes: Dict[tuple, int] = {}
    nel = 0
    nbytes = 0
    selft = 0
    mutating = 0
    nobj = 0
    for o in objs:
        if nobj >= 10 and _gz_pc() > ctx["deadline"]:
            break
        nobj += 1
        try:
            ln = len(o)
            b = _gz_lenb(ln)
            lens[b] = lens.get(b, 0) + 1
            if t is dict:
                ks = []
                for k, v in _itertools.islice(dict.items(o), 64):
                    tn = _gz_tbare(type(k))
                    et[tn] = et.get(tn, 0) + 1
                    vn = _gz_tbare(type(v))
                    vt[vn] = vt.get(vn, 0) + 1
                    nel += 1
                    if type(k) is str and len(ks) < 16:
                        ks.append(k)
                shapes_key = tuple(sorted(ks)[:6])
                shapes[shapes_key] = shapes.get(shapes_key, 0) + 1
                if "tracer_id" in o or "trace_id" in o or "fairy_id" in o:
                    selft += 1
            else:
                it = list.__iter__(o) if t is list else set.__iter__(o)
                for e in _itertools.islice(it, 64):
                    te = type(e)
                    tn = _gz_tbare(te)
                    et[tn] = et.get(tn, 0) + 1
                    nel += 1
                    if id(te) in _GZ_EXACT and te is not list and te is not dict and te is not set:
                        nbytes += _gz_size(e, te)
        except RuntimeError:
            mutating += 1
        except Exception:
            pass

    def mix(d):
        tot = sum(d.values()) or 1
        return " ".join("%s %d%%" % (k, round(100.0 * v / tot)) for k, v in sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:4]) or "-"

    ltot = sum(lens.values()) or 1
    lh = " ".join("%s:%d%%" % (k, round(100.0 * lens[k] / ltot)) for k in _GZ_LENORDER if k in lens) or "-"
    s = "len %s | %s %s" % (lh, "keys" if t is dict else "elems", mix(et))
    if t is dict:
        s += " | vals %s" % mix(vt)
        top = sorted(shapes.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        s += " | shapes %s | self-traced %d%%" % (
            "; ".join("(%s) %d%%" % (",".join(_cg_ascii(x, 20) for x in k), round(100.0 * v / ltot)) for k, v in top) or "-",
            round(100.0 * selft / ltot))
    elif nel and nbytes:
        s += " ~%dB" % (nbytes // max(1, nel))
    if mutating:
        s += " | mutating %d" % mutating
    return s


def _gz_weight(o, t) -> float:
    """Shallow bytes of a sampled container plus its first-16 atomic elements scaled to its length (an ESTIMATE, labelled so)."""
    try:
        sz = float(_gz_size(o, t))
        n = len(o)
        if n:
            tot, m = 0, 0
            if t is dict:
                it = _itertools.islice(dict.values(o), 16)
            else:
                it = _itertools.islice(list.__iter__(o) if t is list else set.__iter__(o), 16)
            for e in it:
                te = type(e)
                if id(te) in _GZ_EXACT and te is not list and te is not dict and te is not set:
                    tot += _gz_size(e, te)
                m += 1
            if m:
                sz += float(tot) * n / m
        return sz
    except Exception:
        return 0.0


def _gz_g3(ctx: Dict[str, Any], type_counts: Dict[str, int], type_sizes: Dict[str, int], scan_count: int, t_go, t_r,
           k_big: int) -> None:
    """G3 + G4 (see the block comment). t_go/t_r are the first-iteration times of LeakHunter's own get_objects and get_referrers."""
    try:
        ctx["tracked"] = int(scan_count)
        ctx["shallow"] = float(sum(type_sizes.values()))
        ctx["t_go"], ctx["t_r"], ctx["k_big"] = t_go, t_r, k_big
    except Exception as e:
        _gz_oops(ctx, "G1", e)
    t_stage = _gz_pc()
    stw0 = ctx["stw_ms"]
    ctx["deadline"] = t_stage + max(0.0, ctx["cfg"]["cpu_budget_ms"] - ctx["cpu_ms"]) / 1e3
    try:
        _gz_g3_run(ctx, type_counts, type_sizes, t_go, t_r, k_big)
    finally:
        ctx["cpu_ms"] += max(0.0, (_gz_pc() - t_stage) * 1e3 - (ctx["stw_ms"] - stw0))


def _gz_g3_run(ctx: Dict[str, Any], type_counts, type_sizes, t_go, t_r, k_big: int) -> None:
    cfg = ctx["cfg"]
    samp = ctx.get("samp")
    if not cfg["g3"]:
        _gz_line(ctx, "[GcCensus] G3 skipped: g3=false in the switch")
        return
    if samp is None:
        _gz_line(ctx, "[GcCensus] G3 skipped: no sampler")
        return
    if samp.err:
        _gz_line(ctx, "[GcCensus] G3 skipped: the sampler failed (%s)" % samp.err)
        return
    if t_go is None:
        _gz_line(ctx, "[GcCensus] G3 skipped: the get_objects time was not measured (no predicted pause without it)")
        return
    ctx["t_go_ms"] = max(float(t_go) * 1e3, 0.001)
    ctx["rho"] = 1.0
    if t_r is not None and k_big > 0:
        ctx["rho"] = max(1.0, float(t_r) * 1e3 / (ctx["t_go_ms"] * (1.10 + 0.021 * k_big)))
    ctx["codes"] = _gz_codes()
    types3 = (set, dict, list)
    own = ctx["own"]
    for t in types3:
        own.add(id(samp.res[t].items))
    own.add(id(samp.heap))
    for e in samp.heap:
        own.add(id(e))
    avail = {t: len([o for o in samp.res[t].items if id(o) not in own]) for t in types3}
    bigs = sorted(samp.heap, key=lambda e: (-e[0], e[1]))
    nb_all = len(bigs)
    want = nb_all + sum(avail.values())
    if want < 1:
        _gz_line(ctx, "[GcCensus] G3 skipped: no set, dict or list was sampled")
        return
    remaining = cfg["run_stw_budget_ms"] - ctx["stw_ms"]
    reserve = cfg["owner_hops"] * _gz_price_ms(ctx, cfg["hop_targets"]) if cfg["owner_hops"] > 0 else 0.0
    hard = min(cfg["stw_cap_ms"], remaining)                       # the pause cap and what is left of the run budget: never crossed
    limit = min(hard, remaining - reserve)               # the hop reserve is a PREFERENCE (room for the optional owner hops) ...
    kmax = _gz_k_for(ctx, limit)                         # GZ-CLAMP
    pred_floor = _gz_price_ms(ctx, _GZ_MIN_TARGETS)
    if kmax < _GZ_MIN_TARGETS and pred_floor <= hard:      # GZ-RESERVE-FLOOR
        kmax = _GZ_MIN_TARGETS                           # ... never a kill switch (review F1): the 30-target floor runs inside the
        ctx["reserve_cut"] = reserve                     #     hard limit, and each hop is gated on what is left (hop gate below)
    if kmax < _GZ_MIN_TARGETS:
        m_was = _GZ["m"]
        _GZ["m"] = max(1.0, m_was * 0.7)                 # GZ-DECAY: one slow call must not switch G3 off for the whole boot
        _gz_line(ctx, "[GcCensus] G3 skipped: predicted %.0fms for the %d-target floor > limit %.0fms (cap %.0f, run budget left "
                      "%.0f; T_go=%.0fms rho=%.2f m=%.2f, m decays to %.2f for the next run)" % (
                          pred_floor, _GZ_MIN_TARGETS, max(0.0, hard), cfg["stw_cap_ms"], remaining, ctx["t_go_ms"],
                          ctx["rho"], m_was, _GZ["m"]))
        return
    nb = max(0, min(nb_all, kmax - _GZ_MIN_TARGETS))
    uni_budget = min(sum(avail.values()), kmax - nb)
    per = max(10, uni_budget // 3)
    take = {t: min(avail[t], per) for t in types3}
    while sum(take.values()) + nb > kmax and any(v > 0 for v in take.values()):
        tmax = max(types3, key=lambda t: take[t])
        take[tmax] -= 1
    targets: list = []
    meta: list = []
    seen_ids: set = set()
    own.add(id(targets))
    for ln, _c, o in bigs[:nb]:
        if id(o) not in seen_ids and id(o) not in own:
            seen_ids.add(id(o))
            targets.append(o)
            meta.append((_gz_tbare(type(o)), "b"))
    for t in types3:
        got = 0
        for o in samp.res[t].items:
            if got >= take[t]:
                break
            if id(o) in own or id(o) in seen_ids:
                continue
            seen_ids.add(id(o))
            targets.append(o)
            meta.append((_gz_tbare(t), "u"))
            got += 1
    k = len(targets)
    if k < 1:
        _gz_line(ctx, "[GcCensus] G3 skipped: no target left after the census's own containers were excluded")
        return
    ctx["targets"] = targets
    ctx["keep"] = {}
    own.add(id(ctx["keep"]))
    ctx["holders"] = {}
    ctx["cls"] = {_GZ_KEEP_FULL: ("budget", "keep-full", True, None)}
    ctx["queried"] = set()
    ctx["tcache"] = {}
    tids = {id(o): i for i, o in enumerate(targets)}
    pred = _gz_price_ms(ctx, k)
    t0 = _gz_pc()
    refs = gc.get_referrers(*targets)
    act = (_gz_pc() - t0) * 1e3
    ctx["stw_ms"] += act
    ctx["queried"].update(tids)
    over = ""
    if act > 1.5 * pred and act - pred > _GZ_OVERRUN_MIN_MS:         # GZ-OVERRUN
        ratio = act / max(pred, 1e-9)
        _GZ["m"] = max(1.0, _GZ["m"] * ratio)
        over = " OVERRUN x%.1f (m now %.2f)" % (ratio, _GZ["m"])
    hop_log = []
    _gz_ingest(ctx, refs, targets, tids)
    refs = None
    for rd in range(1, cfg["owner_hops"] + 1):
        results = [_gz_resolve(ctx, id(o)) for o in targets]
        stops: Dict[int, int] = {}
        for rr in results:
            if rr[0] == "BUDGET" and rr[3] is not None:
                stops[rr[3]] = stops.get(rr[3], 0) + 1
        if not stops:
            break
        order = sorted(stops, key=lambda s: (-stops[s], s))
        pick = [s for s in order[:cfg["hop_targets"]] if s in ctx["keep"]]
        if not pick:
            break
        remaining = cfg["run_stw_budget_ms"] - ctx["stw_ms"]
        hp = _gz_price_ms(ctx, len(pick))
        if hp > min(cfg["stw_cap_ms"], remaining):
            _gz_line(ctx, "[GcCensus] G3 hop %d skipped: predicted %.0fms for %d parents > limit %.0fms" % (
                rd, hp, len(pick), max(0.0, min(cfg["stw_cap_ms"], remaining))))
            break
        nodes = [ctx["keep"][s] for s in pick]
        own.add(id(nodes))
        t0 = _gz_pc()
        refs = gc.get_referrers(*nodes)
        ha = (_gz_pc() - t0) * 1e3
        ctx["stw_ms"] += ha
        ctx["queried"].update(pick)
        hop_log.append((len(pick), ha))
        if ha > 1.5 * hp and ha - hp > _GZ_OVERRUN_MIN_MS:
            _GZ["m"] = max(1.0, _GZ["m"] * (ha / max(hp, 1e-9)))
            over += " hop%d OVERRUN" % rd
        _gz_ingest(ctx, refs, nodes, {s: True for s in stops})
        refs = None
        nodes = None
    results = [_gz_resolve(ctx, id(o), True) for o in targets]
    cpu_left = max(0.0, (ctx["deadline"] - _gz_pc()) * 1e3)
    head = "[GcCensus] G3 k=%d (%s%s) pred=%.0fms actual=%.0fms%s | hops %s | self-excluded %d | seed=%s%s" % (
        k, " ".join("%s %d/%d" % (_gz_tbare(t), take[t], type_counts.get(_gz_tbare(t), 0)) for t in types3),
        " +%d biggest" % nb if nb else "", pred, act, over,
        ("%s = %s" % ("/".join(str(h[0]) for h in hop_log), "/".join("%.0f" % h[1] for h in hop_log) + "ms") if hop_log
         else ("none" if cfg["owner_hops"] == 0 else "none needed")),
        ctx["self_excl"], ctx.get("seed"), " PARTIAL (cpu budget)" if ctx.get("partial_map") else "")
    if ctx.get("reserve_cut") is not None:
        head += " | hop reserve %.0fms cut to run the %d-target floor" % (ctx["reserve_cut"], _GZ_MIN_TARGETS)
    if ctx.get("keep_dropped"):
        head += " | keep-full %d (those edges read BUDGET)" % ctx["keep_dropped"]
    if ctx.get("desc_skip"):
        head += " | user-descriptor reads skipped %d" % ctx["desc_skip"]
    _gz_line(ctx, head)
    ctx["g3"] = {"k": k, "pred": pred, "act": act, "hops": hop_log}
    # ---- reports: owners per type, content, biggest, then G4 ----
    for t in types3:
        tn = _gz_tbare(t)
        idx = [i for i, m in enumerate(meta) if m[0] == tn and m[1] == "u"]
        if not idx:
            continue
        hist: Dict[str, int] = {}
        nbud = 0
        for i in idx:
            b, owner, path, _stop, _f = results[i]
            if b == "BUDGET":
                nbud += 1
                continue
            lab = owner or ("(unreached)" if b == "UNREACHED" else "(" + b + ")")
            if path:
                lab += " via " + ">".join(path)
            hist[lab] = hist.get(lab, 0) + 1
        top = sorted(hist.items(), key=lambda kv: (-kv[1], kv[0]))[:cfg["top_n"]]
        _gz_line(ctx, "[GcCensus] G3 %s holders (resolved %d/%d, budget %d): %s" % (
            tn, len(idx) - nbud, len(idx), nbud, _gz_top(top) or "(none)"))
    for t in types3:
        tn = _gz_tbare(t)
        objs = [targets[i] for i, m in enumerate(meta) if m[0] == tn and m[1] == "u"]
        if objs:
            _gz_line(ctx, "[GcCensus] G3 %s content (%d sampled): %s" % (tn, len(objs), _gz_signature(ctx, objs, t)))
    bi = [i for i, m in enumerate(meta) if m[1] == "b"]
    if bi:
        parts = []
        for i in bi[:5]:
            o = targets[i]
            try:
                parts.append("%s(%d) %s <- %s [%s]" % (_gz_tbare(type(o)), len(o), _gz_sz(_gz_size(o, type(o))),
                                                      results[i][1] or "?", results[i][0]))
            except Exception:
                pass
        _gz_line(ctx, "[GcCensus] G3 biggest %d: %s" % (len(bi), "; ".join(parts)))
    _gz_g4(ctx, targets, meta, results, type_counts, type_sizes)


def _gz_ingest(ctx: Dict[str, Any], refs, nodes, nids) -> None:
    """Map one get_referrers result back to the nodes it holds; classify each new holder once; keep it (strong, bounded)."""
    keep, holders, cls = ctx["keep"], ctx["holders"], ctx["cls"]
    for r in refs:
        if not _gz_ref_ok(ctx, r, nodes):
            continue
        hid = id(r)
        c = cls.get(hid)
        if c is None:
            c = _gz_classify(ctx, r)
        edges = _gz_map_ref(ctx, r, nids, c[0])
        if not edges:
            continue
        if hid not in keep:
            if len(keep) >= _GZ_MAX_KEEP:
                ctx["keep_dropped"] += 1
                hid = _GZ_KEEP_FULL                      # GZ-KEEP: the edge stays, as BUDGET (outside G4's denominator; review F5)
            else:
                keep[hid] = r
                cls[hid] = c
        for nid, key in edges:
            lst = holders.setdefault(nid, [])
            if len(lst) < _GZ_MAX_HOLDERS_PER_NODE and all(h[0] != hid for h in lst):
                lst.append((hid, key))


def _gz_g4(ctx: Dict[str, Any], targets, meta, results, type_counts, type_sizes) -> None:
    """G4: of the holders of the UNIFORM sample, how many are (or belong to) a traced Organ Template fairy. Per type: resolved/sampled,
    the bucket shares, a 95% margin; then the population and byte estimates (labelled estimates). The denominator is the RESOLVED
    count and must be > 0: BUDGET chains are outside it and reported (a ratio over silence reads 100%)."""
    cfg = ctx["cfg"]
    tot_w = tr_w = 0.0
    pop_all = pop_tr = 0.0
    untraced: Dict[str, float] = {}
    for t in (set, dict, list):
        tn = _gz_tbare(t)
        idx = [i for i, m in enumerate(meta) if m[0] == tn and m[1] == "u"]
        if not idx:
            continue
        cnt: Dict[str, int] = {}
        for i in idx:
            cnt[results[i][0]] = cnt.get(results[i][0], 0) + 1
        n_res = sum(v for b, v in cnt.items() if b != "BUDGET")      # GZ-M8B
        nbud = cnt.get("BUDGET", 0)
        if n_res <= 0:
            _gz_line(ctx, "[GcCensus] G4 %s n/a: 0 of %d resolved (%d budget)" % (tn, len(idx), nbud))
            continue
        traced = cnt.get("TRACED-direct", 0) + cnt.get("TRACED-via", 0)  # GZ-M8
        p = traced / float(n_res)
        marg = 196.0 * ((p * (1.0 - p) / n_res) ** 0.5)
        shares = " ".join("%s %d%%" % (_GZ_BSHORT[b], round(100.0 * cnt.get(b, 0) / n_res)) for b in _GZ_BUCKETS[2:] if cnt.get(b, 0))
        _gz_line(ctx, "[GcCensus] G4 trace-id %s (resolved/sampled %d/%d): traced %d%% (direct %d%% via %d%%) %s +-%d%% budget %d" % (
            tn, n_res, len(idx), round(100.0 * p), round(100.0 * cnt.get("TRACED-direct", 0) / n_res),
            round(100.0 * cnt.get("TRACED-via", 0) / n_res), shares or "-", round(marg), nbud))
        n_t = float(type_counts.get(tn, 0))
        pop_all += n_t
        pop_tr += p * n_t
        scale = n_t / float(len(idx)) if idx else 0.0
        for i in idx:
            b, owner, path, _s, _f = results[i]
            if b == "BUDGET":
                continue
            w = _gz_weight(targets[i], t) * scale
            tot_w += w
            if b in ("TRACED-direct", "TRACED-via"):
                tr_w += w
            else:
                lab = (owner or "(unreached)") + ((" via " + ">".join(path)) if path else "")
                untraced["%s: %s" % (tn, lab)] = untraced.get("%s: %s" % (tn, lab), 0.0) + scale
    if pop_all > 0.0:
        top = sorted(untraced.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        _gz_line(ctx, "[GcCensus] G4 all (estimates): by population traced ~%.2fM of %.2fM (%d%%), by bytes ~%d%% (uniform sample only; "
                      "the biggest-%d are on the G3 biggest line) | top untraced: %s" % (                                    # GZ-T10
            pop_tr / 1e6, pop_all / 1e6, round(100.0 * pop_tr / pop_all), round(100.0 * tr_w / tot_w) if tot_w > 0.0 else 0,
            cfg["biggest_n"], "; ".join("%s ~%.2fM" % (k, v / 1e6) for k, v in top) or "-"))
    else:
        _gz_line(ctx, "[GcCensus] G4 all: n/a (no type had a resolved holder)")
    ctx["g4"] = True


# ---- the run: eligibility (B1), G1 around the existing collect (B2), the lines (B6), the end (finally) -------------------------
def _gz_begin(parent):
    """-> the census context of THIS LeakHunter run, or None (= today's run, exactly). Never raises.
    Eligible only when: the switch is armed (a JSON true) AND this is her server process AND the census lock is free AND (a) it is the
    forced run, or (b) attached runs < cap_per_boot, uptime >= min_uptime_min, >= min_gap_min since the last census, commit <=
    census_max_commit_pct of RAM + page-file max (available RAM >= 1 GB when the max is unknown) -- and M0 has not fired."""
    try:
        sw = _gz_switch()
        if sw.get("on") is not True:
            return None
        cfg = _gz_cfg(sw)
        if _gz_her_main() is None:
            _gz_say_once("not_her", "[GcCensus] idle: not her server process")
            return None
        now = _gz_now()
        forced = bool(_GZ["force_pending"])
        _GZ["force_pending"] = False
        _GZ["force_thread"] = None
        if not _GZ_RUN_LOCK.acquire(blocking=False):
            _gz_say_once("lock", "[GcCensus] not this run (another census holds the census lock): today's LeakHunter run only")
            return None
        ok = False
        try:
            why = tag = None
            up = _gz_uptime_min(now)
            if getattr(parent, "_cg_fired", False) or getattr(parent, "_cg_inflight", False):
                why, tag = "the commit guard (M0) has fired or is in flight", "m0"
            elif not forced:
                last = float(_GZ["last_census"])
                if _GZ["runs_attached"] >= cfg["cap_per_boot"]:
                    why, tag = "per-boot cap %d reached" % cfg["cap_per_boot"], "cap"
                elif up < cfg["min_uptime_min"]:
                    why, tag = "uptime %.1f min < %.0f min" % (up, cfg["min_uptime_min"]), "uptime"
                elif last > 0.0 and 0.0 <= now - last < cfg["min_gap_min"] * 60.0:
                    why, tag = "the last census was %.1f min ago (< %.0f)" % ((now - last) / 60.0, cfg["min_gap_min"]), "gap"
                else:
                    pct, avail = _gz_commit()
                    if pct is not None:
                        if pct > cfg["census_max_commit_pct"]:
                            why, tag = "commit %.0f%% > %.0f%% of max" % (pct, cfg["census_max_commit_pct"]), "commit"
                    elif avail is not None:
                        if avail < 1.0:
                            why, tag = "available RAM %.1f GB < 1 GB (page-file max unknown)" % avail, "commit"
                    else:
                        why, tag = "commit and available RAM unreadable", "commit"
            if why is not None:
                _gz_say_once("skip:" + tag, "[GcCensus] not this run (%s): today's LeakHunter run only" % why)
                return None
            _GZ["runs_total"] += 1
            if forced:
                _GZ["forced_n"] += 1
                _GZ["force_tries"] = 0
                _GZ["next_force"] = (up + cfg["force_repeat_min"]) if cfg["force_repeat_min"] > 0.0 else False
                if _GZ["forced_n"] > 1:
                    _GZ["runs_attached"] += 1               # a forced REPEAT counts toward the cap; the first forced run is the +1
            else:
                _GZ["runs_attached"] += 1
            ctx = {"cfg": cfg, "lines": [], "errlines": [], "errs": set(), "dropped": 0, "stw_ms": 0.0, "cpu_ms": 0.0,
                   "run": _GZ["runs_total"], "why": "forced" if forced else "leakhunter", "up": up, "own": set(),
                   "vars_left": _GZ_VARS_BUDGET, "mapped": 0, "mutating": 0, "partial_map": False, "self_excl": 0, "flushed": False,
                   "released": False, "pre": len(gc.garbage), "p0": None, "p1": None, "p2": None, "t0": 0.0, "pause_ms": None,
                   "found": None, "g2": None, "samp": None, "targets": None, "keep": None, "holders": None, "cls": None,
                   "queried": None, "tcache": None, "deadline": 0.0, "t_go": None, "t_r": None, "k_big": 0, "tracked": None,
                   "shallow": None, "seed": None, "rho": 1.0, "t_go_ms": 0.0, "codes": None, "keep_dropped": 0, "asafe": {},
                   "desc_skip": 0, "reserve_cut": None,
                   # her collects since the last census, taken BEFORE this run's own two collects (review F8)
                   "s": _gz_snap(_GZW["s"])}
            ok = True
        finally:
            if not ok:
                _GZ_RUN_LOCK.release()
        try:
            _gz_g2(ctx)
        except Exception as e:
            _gz_oops(ctx, "G2", e)
        try:
            _gz_sampler(ctx)
        except Exception as e:
            _gz_oops(ctx, "G3 sampler", e)
        return ctx
    except Exception as e:
        _gz_oops(None, "begin", e)
        return None


def _gz_snap(w) -> Dict[str, Any]:
    """A copy of a watcher window's totals (n, found, sum, max)."""
    try:
        return {"n": int(w["n"]), "found": int(w["found"]), "sum": float(w["sum"]), "max": float(w["max"])}
    except Exception:
        return {"n": 0, "found": 0, "sum": 0.0, "max": 0.0}


def _gz_pre_collect(ctx: Dict[str, Any]) -> None:
    """G1a, before LeakHunter's own gc.collect(): private bytes, then the clock."""
    try:
        ctx["p0"] = _gz_private()
        ctx["t0"] = _gz_pc()
    except Exception as e:
        _gz_oops(ctx, "G1", e)


def _gz_post_collect(ctx: Dict[str, Any], found) -> None:
    """G1a, right after the collect: its wall time (= the stop-the-world pause on this build), what it freed, private bytes now and
    _GZ_P2_DELAY_S later (this agent thread sleeps; she does not)."""
    try:
        ctx["pause_ms"] = (_gz_pc() - ctx["t0"]) * 1e3
        ctx["found"] = found
        ctx["p1"] = _gz_private()
        if _GZ_P2_DELAY_S > 0.0:
            time.sleep(_GZ_P2_DELAY_S)
        ctx["p2"] = _gz_private()
    except Exception as e:
        _gz_oops(ctx, "G1", e)


def _gz_fmt_gb(v) -> str:
    return "?" if v is None else "%.2f" % (float(v) / 2 ** 30)


def _gz_g1_line(ctx: Dict[str, Any]) -> str:
    cfg = ctx["cfg"]
    g2 = ctx.get("g2")
    s = ctx.get("s") or _gz_snap(_GZW["s"])  # GZ-SNAP
    parts =["[GcCensus] G1 run=%d/%d why=%s up=%.1fmin" % (ctx["run"], cfg["cap_per_boot"] + 1, ctx["why"], ctx["up"])]
    if g2:
        parts.append("saveall-collect found=%s pause=%.0fms" % (g2["found"], g2["pause_ms"]))
    if ctx["pause_ms"] is not None:
        parts.append("collect found=%s pause=%.0fms" % (ctx["found"], ctx["pause_ms"]))
    else:
        parts.append("collect not timed")
    parts.append("private %s->%sGB (+%.0fs %s)" % (_gz_fmt_gb(ctx["p0"]), _gz_fmt_gb(ctx["p1"]), _GZ_P2_DELAY_S, _gz_fmt_gb(ctx["p2"])))
    if ctx["tracked"] is not None:
        parts.append("tracked=%d shallow=%sGB" % (ctx["tracked"], _gz_fmt_gb(ctx["shallow"])))
    go = ("get_objects=%.0fms" % (ctx["t_go"] * 1e3)) if ctx["t_go"] is not None else "get_objects=?"
    rf = ("refs(%d)=%.0fms" % (ctx["k_big"], ctx["t_r"] * 1e3)) if ctx["t_r"] is not None else "refs=n/a"
    parts.append(go + " " + rf)
    if s["n"] or _gz_watch_present():
        parts.append("since last census: collects=%d found=%d wall sum=%.1fs max=%.0fms" % (s["n"], s["found"], s["sum"], s["max"] * 1e3))
    else:
        parts.append("watcher off")
    parts.append("new stop-the-world %.0fms cpu %.0fms" % (ctx["stw_ms"], ctx["cpu_ms"]))
    return " | ".join(parts)


def _gz_flush(ctx: Dict[str, Any], report=None) -> None:
    """Print this run's lines (G1 first), then any error lines. Once."""
    try:
        if ctx.get("flushed"):
            return
        ctx["flushed"] = True
        out = []
        try:
            out.append(_cg_ascii(_gz_g1_line(ctx), _GZ_LINE_CHARS))
        except Exception as e:
            _gz_oops(ctx, "G1 line", e)
        out.extend(ctx["lines"])
        if ctx["dropped"]:
            out.append("[GcCensus] (+%d more lines dropped: the limit is %d lines per run)" % (ctx["dropped"], _GZ_MAX_LINES))
        out.extend(ctx["errlines"])
        for line in out:
            print(line, flush=True)
    except Exception:
        pass


def _gz_drop(ctx: Dict[str, Any]) -> None:
    """Release every strong reference the census holds (a leak hunter must not become a leak)."""
    try:
        samp = ctx.get("samp")
        if samp is not None:
            for r in list(samp.res.values()):
                r.items = []
            samp.heap = []
        for k in ("keep", "holders", "cls", "tcache", "asafe"):
            d = ctx.get(k)
            if isinstance(d, dict):
                d.clear()
            ctx[k] = None
        q = ctx.get("queried")
        if isinstance(q, set):
            q.clear()
        ctx["queried"] = None
        t = ctx.get("targets")
        if isinstance(t, list):
            del t[:]
        ctx["targets"] = None
        ctx["samp"] = None
        ctx["codes"] = None
        ctx["own"] = set()
    except Exception:
        pass


def _gz_end(ctx: Dict[str, Any]) -> None:
    """The finally of LeakHunter's try: flush what is left, the gc.garbage INVARIANT (back to what it was when the run began, or a
    loud line), reset the since-last-census window, drop every reference, release the census lock. Never raises."""
    try:
        if ctx.get("released"):
            return
        ctx["released"] = True
        try:
            _gz_flush(ctx, None)
            pre = ctx["pre"]
            try:
                n = len(gc.garbage) - pre
                if n > 0:
                    del gc.garbage[pre:]                  # GZ-INVARIANT
                    print("[GcCensus] G2 cleanup: %d stray entries cleared from gc.garbage" % n, flush=True)
            except Exception:
                pass
            _GZW["s"] = _gz_win()
            _GZ["last_census"] = _gz_now()
            _gz_drop(ctx)
        finally:
            try:
                _GZ_RUN_LOCK.release()
            except RuntimeError:
                pass
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER AGENTS - These get spawned to attack specific memory problems
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryAgent:
    """Base class for memory relief agents."""

    def __init__(self, parent: 'MemoryPressureFairy'):
        self.parent = weakref.ref(parent)
        self.spawn_time = time.time()
        self.actions_taken = 0
        self.bytes_freed = 0

    def run(self) -> Dict[str, Any]:
        """Execute the agent's task. Override in subclass."""
        raise NotImplementedError

    def report(self) -> Dict[str, Any]:
        return {
            "agent": self.__class__.__name__,
            "spawn_time": self.spawn_time,
            "actions": self.actions_taken,
            "bytes_freed": self.bytes_freed,
            "age_sec": time.time() - self.spawn_time,
        }


class CacheFlushAgent(MemoryAgent):
    """
    Broadcasts cache flush requests to all fairies.
    Many fairies keep caches that can be cleared under pressure.
    """

    def run(self) -> Dict[str, Any]:
        parent = self.parent()
        if not parent or not parent.fabric:
            return {"success": False, "reason": "no_fabric"}

        # Broadcast flush request to multiple channels
        request = {
            "opcode": "FLUSH_CACHES_URGENT",
            "payload": {
                "reason": "memory_pressure",
                "level": parent._last_level,
                "ram_pct": parent._get_memory_percent(),
                "ts": time.time(),
            }
        }

        channels = [
            "memory.stream",
            "telemetry",
            "system.command",
            "fairy.command",
        ]

        sent = 0
        for ch in channels:
            try:
                parent.fabric.publish(ch, request)
                sent += 1
            except Exception:
                pass

        self.actions_taken = sent
        print(f"[CacheFlushAgent] Broadcast flush request to {sent} channels")
        return {"success": True, "channels_notified": sent}


class MailboxPrunerAgent(MemoryAgent):
    """
    Trims postal mailboxes that may have accumulated old messages.
    Postal mailboxes can grow unbounded if nobody consumes them.
    """

    MAX_MAILBOX_SIZE = 100  # Keep only latest N messages per topic

    def run(self) -> Dict[str, Any]:
        parent = self.parent()
        if not parent:
            return {"success": False, "reason": "no_parent"}

        pruned_count = 0
        bytes_before = self._estimate_postal_size()

        try:
            # Try to access the shared postal hub directly
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal = get_shared_postal_hub()

            if postal and hasattr(postal, '_mailboxes'):
                mailboxes = postal._mailboxes
                for topic, box in mailboxes.items():
                    if hasattr(box, '__len__') and len(box) > self.MAX_MAILBOX_SIZE:
                        old_len = len(box)
                        # If it's a deque, we can truncate by reassigning
                        if isinstance(box, deque):
                            # Keep only the latest messages
                            while len(box) > self.MAX_MAILBOX_SIZE:
                                box.popleft()
                                pruned_count += 1
                        # If it's a list
                        elif isinstance(box, list):
                            del box[:-self.MAX_MAILBOX_SIZE]
                            pruned_count += old_len - len(box)

            # Also check subscriber lists
            if postal and hasattr(postal, '_subscribers'):
                # Can't prune subscribers but can report
                sub_count = sum(len(subs) for subs in postal._subscribers.values())
                print(f"[MailboxPrunerAgent] {sub_count} active subscribers")

        except Exception as e:
            print(f"[MailboxPrunerAgent] Error pruning: {e}")

        bytes_after = self._estimate_postal_size()
        self.bytes_freed = bytes_before - bytes_after
        self.actions_taken = pruned_count

        if pruned_count > 0:
            print(f"[MailboxPrunerAgent] Pruned {pruned_count} old messages")

        return {
            "success": True,
            "messages_pruned": pruned_count,
            "bytes_freed_est": self.bytes_freed,
        }

    def _estimate_postal_size(self) -> int:
        """Rough estimate of postal memory usage."""
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal = get_shared_postal_hub()
            if postal and hasattr(postal, '_mailboxes'):
                # Very rough estimate: 1KB per message average
                total_msgs = sum(
                    len(box) for box in postal._mailboxes.values()
                    if hasattr(box, '__len__')
                )
                return total_msgs * 1024
        except Exception:
            pass
        return 0


class DequePatrolAgent(MemoryAgent):
    """
    Finds and reports unbounded deques across the system.
    Unbounded deques (maxlen=None) can grow forever and leak memory.
    """

    def run(self) -> Dict[str, Any]:
        parent = self.parent()
        if not parent:
            return {"success": False, "reason": "no_parent"}

        findings = []
        trimmed = 0

        # Scan imported modules for deque attributes
        for name, module in list(sys.modules.items()):
            if module is None:
                continue
            if not name.startswith(('P00_', 'P10_', 'P20_', 'P30_', 'P40_', 'P50_', 'P60_')):
                continue

            try:
                for attr_name in dir(module):
                    try:
                        attr = getattr(module, attr_name, None)
                        if isinstance(attr, deque):
                            # Check if unbounded and large
                            if attr.maxlen is None and len(attr) > 1000:
                                findings.append({
                                    "module": name,
                                    "attr": attr_name,
                                    "size": len(attr),
                                    "maxlen": attr.maxlen,
                                })
                                # Trim to 1000 items
                                while len(attr) > 1000:
                                    attr.popleft()
                                    trimmed += 1
                    except Exception:
                        pass
            except Exception:
                pass

        self.actions_taken = len(findings)

        if findings:
            print(f"[DequePatrolAgent] Found {len(findings)} large unbounded deques:")
            for f in findings[:5]:  # Show first 5
                print(f"  - {f['module']}.{f['attr']}: {f['size']} items")
            if trimmed > 0:
                print(f"[DequePatrolAgent] Trimmed {trimmed} items total")

        return {
            "success": True,
            "unbounded_deques": len(findings),
            "items_trimmed": trimmed,
            "findings": findings[:10],  # First 10
        }


class LeakHunterAgent(MemoryAgent):
    """
    Profiles memory to identify the biggest consumers.
    This is the heavy artillery - only spawn when really needed.

    Uses MemoryLeakTracer for detailed tracemalloc-based diagnostics
    to identify WHERE allocations are coming from.
    """

    def run(self) -> Dict[str, Any]:
        parent = self.parent()
        if not parent:
            return {"success": False, "reason": "no_parent"}

        report = {
            "success": True,
            "timestamp": time.time(),
            "findings": [],
        }

        # Use MemoryLeakTracer for detailed diagnostics
        try:
            from fairies.P00_Autonomic.utils.memory_leak_tracer import get_memory_tracer
            tracer = get_memory_tracer()

            # Take a snapshot if tracer is running
            if hasattr(tracer, '_running') and tracer._running:
                snap_name = f"leak_hunt_{int(time.time())}"
                tracer.snapshot(snap_name)

                # Get top memory consumers with source locations
                top_consumers = tracer.get_top_consumers(10)
                report["tracemalloc_top_consumers"] = top_consumers

                # Get comparison from start if available
                if "start" in getattr(tracer, '_snapshots', {}):
                    comparison = tracer.compare("start", snap_name)
                    report["growth_since_start"] = {
                        "memory_growth_mb": comparison.get("memory_growth_mb", 0),
                        "growth_rate_mb_per_hour": comparison.get("memory_growth_rate_mb_per_hour", 0),
                        "top_growing_types": dict(list(comparison.get("top_growing_types", {}).items())[:5]),
                    }
                    print(f"[LeakHunterAgent] Growth rate: {comparison.get('memory_growth_rate_mb_per_hour', 0):.1f} MB/hour")
        except Exception as e:
            print(f"[LeakHunterAgent] MemoryLeakTracer not available: {e}")

        # Get process memory breakdown
        # GARBAGE CENSUS (G1-G4), garbage_census_1014: _gz stays None (= today's run) unless state/garbage_census.json arms it.
        _gz = None
        _gz_on = False
        _gz_samp = None
        _gz_t_go = None
        _gz_t_go0 = 0.0
        _gz_t_r = None
        _gz_t_ref0 = 0.0
        _gz_k_big = 0
        _gz_found = 0
        if HAS_PSUTIL:
            try:
                proc = psutil.Process()
                mem_info = proc.memory_info()
                report["process"] = {
                    "rss_mb": mem_info.rss / (1024**2),
                    "vms_mb": mem_info.vms / (1024**2),
                }

                # GARBAGE CENSUS B1 (garbage_census_1014): eligibility, then G2 (one SAVEALL collect, census, gc.garbage cleared).
                try:
                    _gz = _gz_begin(parent)
                except Exception as _gze:
                    _gz = None
                    _gz_oops(None, "begin", _gze)
                _gz_on = _gz is not None

                # FIX 2026-03-03 (Nous): SINGLE-PASS gc scan.
                # OLD: 3 separate gc.get_objects() passes (count, then lists, then dicts).
                # Each pass iterates EVERY Python object (~millions), holding the GIL
                # the entire time. With multiple LeakHunterAgents, this consumed 200%+ CPU
                # and caused stop-and-go terminal output.
                # NEW: One pass collects all metrics. Yields GIL every 50K objects.
                if _gz_on:
                    _gz_pre_collect(_gz)
                _gz_found = gc.collect()
                if _gz_on:
                    _gz_post_collect(_gz, _gz_found)

                type_counts = {}
                type_sizes = {}
                large_lists = 0
                large_dicts = 0
                scan_count = 0
                # -- REFERRER ANALYSIS 2026-09-05 (Nous + Ace) ------------------
                # This agent reported WHAT was accumulating and never WHO held it.
                # Measured: 1,622,793 sets / 786,451 dicts / 523,761 lists and
                # "51 lists with >10K items", against 13.78 GB of ANONYMOUS heap
                # vs a 3.46 GB mmap cortex that can no longer stay resident
                # (248,650 page faults/sec; edge throughput fell 105x in one boot).
                # Ownership is the one missing fact. Collect the oversized
                # containers HERE -- the scan already identifies them, so this
                # costs nothing extra -- then resolve holders in ONE pass below.
                _big = []
                _TRACK_MAX = 12
                _REF_BUDGET_S = 20.0
                if _gz_on:
                    _gz_samp = _gz.get("samp")
                    _gz_t_go0 = time.perf_counter()

                for obj in gc.get_objects():
                    scan_count += 1

                    # Yield GIL every 50K objects to prevent starvation
                    if scan_count % 50000 == 0:
                        time.sleep(0)  # GIL yield point

                    try:
                        t = type(obj).__name__
                        type_counts[t] = type_counts.get(t, 0) + 1
                        type_sizes[t] = type_sizes.get(t, 0) + sys.getsizeof(obj)

                        # Pattern detection in same pass
                        if isinstance(obj, list) and len(obj) > 10000:
                            large_lists += 1
                            if len(_big) < _TRACK_MAX:
                                _big.append(obj)
                        elif isinstance(obj, dict) and len(obj) > 10000:
                            large_dicts += 1
                            if len(_big) < _TRACK_MAX:
                                _big.append(obj)
                        elif isinstance(obj, set) and len(obj) > 10000:
                            if len(_big) < _TRACK_MAX:
                                _big.append(obj)
                        if _gz_on:
                            # GARBAGE CENSUS B3: time to the first object = get_objects' stop-the-world; reservoir + biggest-n sampling.
                            _gz_ty = type(obj)
                            if _gz_t_go is None:
                                _gz_t_go = time.perf_counter() - _gz_t_go0
                            if _gz_samp is not None and (_gz_ty is set or _gz_ty is dict or _gz_ty is list):
                                _gz_samp.feed(_gz_ty, obj)
                    except Exception:
                        pass

                # Top 10 by count
                top_count = sorted(type_counts.items(), key=lambda x: -x[1])[:10]
                report["top_by_count"] = top_count

                # Top 10 by size
                top_size = sorted(type_sizes.items(), key=lambda x: -x[1])[:10]
                report["top_by_size"] = [
                    (t, s / (1024**2)) for t, s in top_size
                ]

                # Patterns from single pass
                patterns = []
                if large_lists > 0:
                    patterns.append(f"Found {large_lists} lists with >10K items")
                if large_dicts > 0:
                    patterns.append(f"Found {large_dicts} dicts with >10K items")
                report["patterns"] = patterns

                # -- REFERRER ANALYSIS 2026-09-05 (Nous + Ace) ------------------
                # ONE gc.get_referrers() call over ALL tracked containers.
                # get_referrers walks the WHOLE heap per call, so calling it per
                # object would be ~12 full passes over 3.6M objects inside a mind
                # already thrashing. One call, hard time budget, GIL yields.
                # A diagnostic must never become the outage it is diagnosing.
                _owners = []
                try:
                    if _big:
                        _t_ref = time.time()
                        _ids = {id(o): i for i, o in enumerate(_big)}
                        _seen = 0
                        if _gz_on:
                            _gz_k_big = len(_big)
                            _gz_t_ref0 = time.perf_counter()
                        for _r in gc.get_referrers(*_big):
                            _seen += 1
                            if _gz_on and _gz_t_r is None:
                                _gz_t_r = time.perf_counter() - _gz_t_ref0
                            if _seen % 50000 == 0:
                                time.sleep(0)  # GIL yield, same as the scan above
                            if time.time() - _t_ref > _REF_BUDGET_S:
                                _owners.append("(referrer scan hit %.0fs budget)"
                                               % _REF_BUDGET_S)
                                break
                            try:
                                _rt = type(_r).__name__
                                # ★ On Python 3.11+ (and 3.14t here) instances use
                                # MANAGED DICTS: get_referrers returns the OBJECT,
                                # not its __dict__. Verified on this interpreter --
                                # the naive "scan the referrer as a dict" approach
                                # finds NOTHING and would have reported "no owners".
                                # So read vars() to name the attribute directly.
                                _rd = getattr(_r, "__dict__", None)
                                if isinstance(_rd, dict):
                                    for _k, _v in list(_rd.items())[:4000]:
                                        if id(_v) in _ids and isinstance(_k, str):
                                            _t = _big[_ids[id(_v)]]
                                            _owners.append("%s.%s -> %s(%d)"
                                                           % (_rt[:40], _k[:40],
                                                              type(_t).__name__, len(_t)))
                                elif isinstance(_r, dict):
                                    # module globals / a plain cache dict
                                    for _k, _v in list(_r.items())[:4000]:
                                        if id(_v) in _ids and isinstance(_k, str):
                                            _t = _big[_ids[id(_v)]]
                                            _owners.append("dict['%s'] -> %s(%d)"
                                                           % (_k[:40], type(_t).__name__,
                                                              len(_t)))
                                elif _rt not in ("list", "tuple", "frame"):
                                    _owners.append("%s holds a big container" % _rt[:48])
                            except Exception:
                                pass
                        if _gz_on and _gz_t_r is None:
                            _gz_t_r = time.perf_counter() - _gz_t_ref0
                        # de-dup, keep it short enough for a cp1252 console
                        _uniq = []
                        for _o in _owners:
                            if _o not in _uniq:
                                _uniq.append(_o)
                        _owners = _uniq[:12]
                        report["big_container_owners"] = _owners
                except Exception as _re:
                    print("[LeakHunterAgent] referrer analysis failed: %s" % str(_re)[:120])
                finally:
                    # Drop the strong refs immediately -- a leak hunter must not
                    # become a leak.
                    try:
                        _big = []
                        del _ids
                    except Exception:
                        pass

                # GARBAGE CENSUS B5 (garbage_census_1014): G3 (who holds a sample of the anonymous containers) + G4 (trace id?).
                if _gz_on:
                    # the loops above leave objects in their locals (the last scanned object, the last referrer -- which is the _big
                    # list itself or the call's args tuple -- the last __dict__ and target): drop them, or they read as holders
                    obj = _r = _rd = _v = _t = None
                    try:
                        _gz_g3(_gz, type_counts, type_sizes, scan_count, _gz_t_go, _gz_t_r, _gz_k_big)
                    except Exception as _gze:
                        _gz_oops(_gz, "G3/G4", _gze)
                    finally:
                        _gz_drop(_gz)

                self.actions_taken = 1

                print(f"[LeakHunterAgent] Memory analysis complete ({scan_count:,} objects scanned):")
                print(f"  Process RSS: {report['process']['rss_mb']:.1f} MB")
                print(f"  Top types: {report['top_by_count'][:5]}")
                if patterns:
                    for p in patterns:
                        print(f"  [WARN] {p}")
                if report.get("big_container_owners"):
                    print("  [OWNERS] who holds the oversized containers:")
                    for _o in report["big_container_owners"]:
                        print(f"    {_o}")

                # GARBAGE CENSUS B6 (garbage_census_1014): the [GcCensus] lines, after every line this agent printed before.
                if _gz is not None:
                    _gz_flush(_gz, report)

            except Exception as e:
                report["error"] = str(e)
                print(f"[LeakHunterAgent] Analysis error: {e}")
            finally:
                try:
                    if _gz is not None:
                        _gz_end(_gz)                 # gc.garbage invariant, drop every reference, release the census lock
                except Exception:
                    pass
        else:
            report["error"] = "psutil not available"

        return report


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryPressureFairy(Fairy):
    """
    Active memory pressure manager with agent spawning.

    Now a proper Fairy that integrates with the postal system and Directory.

    THRESHOLDS (target: keep under 50%):
      - Level 0 (0-40%):   Comfortable - just monitor
      - Level 1 (40-50%):  Warning - light GC
      - Level 2 (50-60%):  Elevated - full GC + cache flush
      - Level 3 (60-70%):  High - spawn pruning agents
      - Level 4 (>70%):    Critical - spawn leak hunter + emergency
    """

    # ═══════════════════════════════════════════════════════════════════════════
    # FAIRY IDENTITY
    # ═══════════════════════════════════════════════════════════════════════════

    ACTOR_NAME = "MemoryPressureFairy"
    ACTOR_VERSION = "0.3.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "hardware.memory"

    # ═══════════════════════════════════════════════════════════════════════════
    # FAIRY CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════════════

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 1  # Check every heartbeat (we manage our own cadence)

    # Disable infrastructure we don't need (lightweight fairy)
    NEEDS_CIRCADIAN = False
    NEEDS_BODY = False
    NEEDS_AFFECT = False
    NEEDS_MEMORY = False
    NEEDS_GOALS = False
    NEEDS_CONSCIOUSNESS = False
    NEEDS_CORTEX = False
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_LEARNING = False

    # ═══════════════════════════════════════════════════════════════════════════
    # THRESHOLDS AND CADENCE
    # ═══════════════════════════════════════════════════════════════════════════

    # Lower thresholds - target is to stay under 50%
    THRESHOLD_WARNING = 40.0     # Start paying attention
    THRESHOLD_ELEVATED = 50.0    # Target ceiling
    THRESHOLD_HIGH = 60.0        # Getting concerning
    THRESHOLD_CRITICAL = 70.0    # Need aggressive action

    # FREE-RAM FLOOR (2026-06-25, Nous): system-% is only a PROXY for "running low" — the real
    # signal is ABSOLUTE free RAM. A large-but-LIVE footprint (e.g. a ~12GB mmap cortex on a 32GB
    # box → ~70% system RAM with ~9GB free) is NOT an emergency, and gc.collect() can't shrink it
    # anyway. Without this floor the % ladder pins such a system in permanent "critical" → endless
    # CRIT alerts + futile agent spawns (incl the heavy LeakHunter, since GC can never look
    # "effective" against a live mmap). So escalation past "comfortable" now requires free RAM to
    # be genuinely low. Tune to taste (Ace's dial); 3GB suits the 32GB box.
    MIN_FREE_GB = 3.0            # >= this much AVAILABLE RAM ⇒ no pressure, just monitor

    # Cadence (seconds between checks at each level)
    CADENCE_COMFORTABLE = 30.0
    CADENCE_WARNING = 20.0
    CADENCE_ELEVATED = 15.0     # was 10 — too aggressive for 9GB process
    CADENCE_HIGH = 10.0         # was 5  — GC alone takes several seconds
    CADENCE_CRITICAL = 5.0      # was 3  — need breathing room between GCs

    # FIX 2026-03-03 (Nous): Minimum seconds between GC runs.
    # gc.collect(2) on a 9GB process holds the GIL for seconds, blocking ALL
    # other threads (print, consciousness, speech). Running it every 5s caused
    # permanent stop-and-go. Now we enforce at least 60s between full GCs.
    MIN_GC_INTERVAL = 60.0

    # GC effectiveness threshold - if we free less than this %, escalate
    GC_EFFECTIVENESS_THRESHOLD = 2.0  # If GC frees <2%, it's not helping

    # ═══════════════════════════════════════════════════════════════════════════
    # GC-CONTROLLER + GROWTH-RATE GUARD (2026-07-16 Nous + Ace)
    # ═══════════════════════════════════════════════════════════════════════════
    # WHY: two failure modes, one root (millions of gc-tracked objects):
    #  1) FREEZE (07-13) — a full gc.collect(2) is STOP-THE-WORLD: it froze EVERY
    #     thread for seconds. The "SLOW: X callback took 111s" lines were 2-LINE
    #     liveness callbacks frozen mid-run, not slow fairies. Sandbox: thread-freeze
    #     2213ms default -> 12ms with gc.disable() (~180x). gen0=146ms vs gen2=836ms.
    #  2) CRASH (07-13 OOM) — _get_level's FREE-RAM FLOOR keeps us "comfortable"
    #     (cadence 30s, NO action) until ~29GB, so an 11->32GB runaway in <30s
    #     balloons BETWEEN checks and we NEVER react. We reacted AT 100% = too late.
    # SO: this fairy now OWNS gc (automatic collection disabled at boot) and does
    # cheap gen-0 OFTEN on a level-INDEPENDENT fast poll, full gen-2 RARELY in a
    # window. gen-0 must ride the FAST poll (not the level ladder) — gc.disable()
    # plus sparse ladder-collection would let RAM climb unchecked to the floor and
    # CAUSE the very OOM we're fixing.
    POLL_FAST_SEC = 5.0             # cheap RSS poll + gen-0 (level-INDEPENDENT)
    RATE_LIMIT_MB_PER_MIN = 4096.0  # >4GB/min climb = runaway -> EMERGENCY (bypasses free-RAM floor)
    EMERGENCY_COOLDOWN_SEC = 60.0
    FULL_GC_WINDOW_SEC = 300.0      # deep gen-2 reclaim, off the hot path
    # FIX 2026-07-16b (caught by the LIVE loop, not the sim): BOOT legitimately
    # allocates ~0->10GB in the first minute (manifold/cortex load) = ~16GB/min,
    # which tripped the rate guard on the very first boot ("RUNAWAY rss=9021MB
    # climbing 16.5GB/min") and spuriously fired a full gen-2 + cache flush.
    # A runaway only MATTERS if it's heading for the 32GB wall, so require BOTH
    # a high rate AND an already-high RSS, plus a grace window past boot.
    # (The 07-13 runaway went 11GB->32GB, so it crosses 16GB early and still gets
    #  ~16GB / ~30s of headroom — vs the old logic's "never fires".)
    RUNAWAY_MIN_RSS_MB = 16384.0    # don't alarm below ~half the box (boot's ~10GB is normal)
    BOOT_GRACE_SEC = 180.0          # don't arm the rate guard until the load settles

    # ── ZERO-COLLECT TEST (2026-07-16, Ace's call — the LIVE arbiter) ──
    # The gc-controller did NOT collapse the SLOW callbacks (10 before, 10 after;
    # worst 47.7s). Sandbox says the worst GC pause reproducible is ~0.9-2.2s, i.e.
    # 20-50x too small to BE her 47s freeze — but the sandbox measures the MECHANISM,
    # only her loop measures the SYSTEM. So: run with gc.disable() and ZERO scheduled
    # collects for one boot and read the SLOW list.
    #   SLOW vanishes  -> GC IS the freeze after all -> collect far less / only in sleep.
    #   SLOW persists  -> GC is NOT the cause -> hunt elsewhere (status-gather lock is
    #                     the prime suspect: fairies: 132,123ms, 0.1ms at beat 40).
    # SAFETY: the level ladder (_monitor_tick) still collects under real pressure, and
    # the runaway guard still emergency-collects >16GB. RAM WILL grow this run — expected.
    # REVERT: set back to True (or restore .bak_gcctl_0716).
    SCHEDULED_COLLECTS_ENABLED = False

    # ═══════════════════════════════════════════════════════════════════════════
    # INITIALIZATION
    # ═══════════════════════════════════════════════════════════════════════════

    def __init__(self, fabric=None):
        """Initialize the Memory Pressure Fairy."""
        super().__init__(fabric)

        self._last_gc_time = 0.0
        self._gc_count = 0
        self._last_level = "comfortable"
        self._pressure_history: deque = deque(maxlen=120)
        self._last_alert_time = 0.0
        self._alert_cooldown = 30.0

        # GC effectiveness tracking
        self._gc_results: deque = deque(maxlen=10)
        self._ineffective_gc_streak = 0

        # Agent tracking
        self._active_agents: List[MemoryAgent] = []
        self._agent_cooldowns: Dict[str, float] = {}  # agent_class -> last_spawn_time
        # FIX 2026-03-03 (Nous): 60s was far too short — LeakHunterAgent takes
        # minutes to scan millions of objects, so new agents piled up every 60s.
        self._agent_cooldown_sec = 300.0  # 5 min between same agent type

        # Cadence management (track last check time for dynamic cadence)
        self._last_check_time = 0.0
        self._monitor_tick_count = 0

        # GC-CONTROLLER + GROWTH-RATE GUARD state (2026-07-16)
        self._last_rss_mb = 0.0
        self._last_rss_time = 0.0
        self._last_fast_poll = 0.0
        self._emergency_fired_at = 0.0
        self._last_full_gc = 0.0
        self._boot_time = 0.0  # set in on_boot; gates the rate guard past boot load

        # COMMIT GUARD (M0) + MEMORY CENSUS (M1) state, E1 2026-10-12. Idle unless state/commit_guard.json turns them on.
        self._cg_lock = threading.Lock()   # heartbeat threads may call on_tick together: one sampler at a time
        self._cg_last_sample = 0.0
        self._cg_streak = 0                # consecutive VALID samples over the line
        self._cg_fired = False             # latched once the save-first route took the request: one trip per boot
        self._cg_inflight = False
        self._cg_retry_at = 0.0
        self._cg_thread = None
        self._cg_pf = None                 # (page-file max bytes | None, why): read once when known, every 300 s while not
        self._cg_pf_at = 0.0               # when the page-file max was last read
        self._cg_armed = None
        self._cg_last = {}
        self._cg_said = set()              # one-time lines already printed
        self._cg_err_at = 0.0
        self._mc_last = 0.0
        self._mc_create = None

    # ═══════════════════════════════════════════════════════════════════════════
    # FAIRY LIFECYCLE HOOKS
    # ═══════════════════════════════════════════════════════════════════════════

    def get_capabilities(self) -> Set[str]:
        """Return capabilities for Directory registration."""
        return {
            "hardware.memory.monitor",
            "hardware.memory.gc",
            "hardware.memory.pressure",
        }

    def on_boot(self) -> bool:
        """Called when fairy boots. Initialize monitoring state."""
        self._last_check_time = time.time()
        self._boot_time = time.time()  # rate guard arms only after BOOT_GRACE_SEC
        # GC-CONTROLLER (2026-07-16): disable AUTOMATIC stop-the-world collection.
        # A collect over ~millions of gc-tracked objects freezes EVERY thread for
        # seconds (the 07-13 "121s SLOW callback" freeze). We schedule it ourselves:
        # cheap gen-0 on the fast poll, full gen-2 only in a window / under pressure.
        # Reversible: gc.enable() restores stock behaviour.
        try:
            gc.disable()
            if self.SCHEDULED_COLLECTS_ENABLED:
                print(f"[{self.ACTOR_NAME}] GC-CONTROLLER: automatic gc DISABLED "
                      f"(gen0 every {self.POLL_FAST_SEC:.0f}s, full gen2 every {self.FULL_GC_WINDOW_SEC:.0f}s/pressure)")
            else:
                print(f"[{self.ACTOR_NAME}] *** ZERO-COLLECT TEST *** automatic gc DISABLED + NO scheduled "
                      f"collects (ladder/runaway-guard only). RAM will grow — reading the SLOW list to "
                      f"decide: is GC the freeze, or not?")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] gc.disable failed (non-fatal, stock gc stays on): {e}")
        print(f"[{self.ACTOR_NAME}] [OK] Started v{self.ACTOR_VERSION} (target: <{self.THRESHOLD_ELEVATED}% RAM)")
        return True

    def on_shutdown(self) -> bool:
        """Called during shutdown. Clean up agents."""
        self._active_agents.clear()
        try:
            _gz_watch_set(False)                 # garbage_census_1014: the gc.callbacks watcher goes with her
        except Exception:
            pass
        try:
            if _GD is not None:
                _GD.shutdown()                   # gc_diet_1015: the gc.collect wrapper goes with her
        except Exception:
            pass
        print(f"[{self.ACTOR_NAME}] Stopped")
        return True

    def on_tick(self, beat: int) -> None:
        """
        Called on each heartbeat. Check if it's time to monitor based on cadence.

        The cadence is dynamic based on pressure level - we check more frequently
        under higher pressure. The heartbeat provides the clock, but we only
        act when enough time has passed based on current cadence.
        """
        now = time.time()

        # ── COMMIT GUARD (M0) + MEMORY CENSUS (M1), E1 2026-10-12: OFF unless state/commit_guard.json turns them on.
        # First in the tick, so the ladder's cadence can never starve it; it never raises into the tick.
        try:
            self._cg_tick(now)
        except Exception as e:
            if not (0.0 <= now - self._cg_err_at < 300.0):
                self._cg_err_at = now
                print(f"[MemoryPressure] commit guard error (non-fatal): {type(e).__name__}: {_cg_ascii(e, 120)}")

        # ---- GARBAGE CENSUS (G1-G4), garbage_census_1014: OFF unless state/garbage_census.json arms it. Never raises into the tick.
        try:
            self._gz_tick(now)
        except Exception as e:
            _gz_oops(None, "tick", e)

        # ---- GC DIET (gc_diet_1015): OFF unless state/gc_diet.json arms it. One call; never raises into the tick.
        try:
            if _GD is not None:
                _GD.tick(self, now, her=_gz_her_main() is not None, census_busy=_GZ_RUN_LOCK.locked(), up_min=_gz_uptime_min(now))
        except Exception as e:
            _gd_oops("tick", e)

        # ── FAST PATH (2026-07-16): level-INDEPENDENT, every POLL_FAST_SEC ──
        # A bare psutil rss read is microseconds. The free-RAM floor keeps us
        # "comfortable" to ~29GB, so the level ladder below is BLIND to a fast
        # runaway (the 07-13 OOM) — this poll is what actually catches it. It also
        # does the cheap gen-0 that keeps garbage from aging into the costly gen-2.
        if now - self._last_fast_poll >= self.POLL_FAST_SEC:
            self._last_fast_poll = now
            try:
                self._fast_poll(now)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] fast_poll error (non-fatal): {e}")

        cadence = self._get_cadence(self._last_level)

        # Only check if enough time has passed (respects dynamic cadence)
        if now - self._last_check_time < cadence:
            return

        self._last_check_time = now
        self._monitor_tick()

    # ═══════════════════════════════════════════════════════════════════════════
    # GC-CONTROLLER + GROWTH-RATE GUARD (2026-07-16 Nous + Ace)
    # ═══════════════════════════════════════════════════════════════════════════

    def _fast_poll(self, now: float) -> None:
        """Cheap + level-independent: growth-rate guard, then young-gen collect."""
        rss = self._get_python_memory_mb()

        # ── GROWTH-RATE GUARD: escalate on dRSS/dt, BYPASSING the free-RAM floor.
        # The floor assumes gradual change; a runaway is not gradual.
        # Gated by RUNAWAY_MIN_RSS_MB + BOOT_GRACE_SEC so boot's own legitimate
        # manifold load (~16GB/min to ~10GB) doesn't trip it (fix 2026-07-16b).
        armed = (rss > self.RUNAWAY_MIN_RSS_MB and
                 self._boot_time > 0.0 and
                 now - self._boot_time > self.BOOT_GRACE_SEC)
        if armed and self._last_rss_time and rss > 0 and self._last_rss_mb > 0:
            dt = now - self._last_rss_time
            if dt > 0:
                rate = (rss - self._last_rss_mb) / dt * 60.0  # MB/min
                if (rate > self.RATE_LIMIT_MB_PER_MIN and
                        now - self._emergency_fired_at > self.EMERGENCY_COOLDOWN_SEC):
                    self._emergency_fired_at = now
                    self._on_runaway(rss, rate)
        self._last_rss_mb = rss
        self._last_rss_time = now

        # ── ZERO-COLLECT TEST gate: when False we do NO scheduled collection at all
        # (gc is disabled at boot), so the SLOW list answers "is GC the freeze?".
        if not self.SCHEDULED_COLLECTS_ENABLED:
            return
        # gc_diet_1015: fast_poll_no_collect (insurance for the landmine above: flipping SCHEDULED_COLLECTS_ENABLED back to True)
        if _gd_skip("fast_poll_no_collect", "fast_poll"):
            return

        # ── cheap gen-0: young cyclic garbage only (~146ms@1M .. ~277ms@5M, sub-linear).
        # Frequent gen-0 keeps garbage from aging, so the rare gen-2 has less to do.
        gc.collect(0)

        # ── deep gen-2 ONLY in a maintenance window, off the hot path.
        if now - self._last_full_gc > self.FULL_GC_WINDOW_SEC:
            self._last_full_gc = now
            gc.collect(2)

    def _on_runaway(self, rss_mb: float, rate_mb_min: float) -> None:
        """A runaway allocation is climbing fast. React NOW — the level ladder won't."""
        print(f"[{self.ACTOR_NAME}] *** RUNAWAY ALLOCATION *** rss={rss_mb:.0f}MB climbing "
              f"{rate_mb_min / 1024.0:.1f}GB/min -- emergency response", flush=True)
        # 1) Name the site if tracemalloc is live (heap_profiler level=2, deferred start).
        try:
            import tracemalloc
            if tracemalloc.is_tracing():
                snap = tracemalloc.take_snapshot()
                for s in snap.statistics("traceback")[:3]:
                    where = " | ".join(str(f) for f in s.traceback[:3])
                    print(f"[{self.ACTOR_NAME}] [RUNAWAY-SITE] {s.size / 1e6:.0f}MB @ {where}", flush=True)
        except Exception:
            pass  # never let diagnostics break the emergency path
        # 2) Shed: full reclaim + cache flush.
        try:
            if not _gd_skip("runaway_no_collect", "runaway"): gc.collect(2)   # gc_diet_1015: the alert and the cache flush stay
        except Exception:
            pass
        try:
            self._spawn_agent(CacheFlushAgent)
        except Exception:
            pass
        try:
            self._emit_alert("critical", 100.0 * rss_mb / (32.0 * 1024.0),
                             "RUNAWAY allocation - emergency shed")
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # COMMIT GUARD (M0) + MEMORY CENSUS (M1) -- E1 2026-10-12, see the module block at the top
    # ═══════════════════════════════════════════════════════════════════════════

    def _cg_say_once(self, tag: str, line: str) -> None:
        if tag in self._cg_said:
            return
        self._cg_said.add(tag)
        print(line, flush=True)

    def _cg_her_main(self):
        """Her server module (__main__ = server.py, carrying SYSTEM + shutdown_system), or None in any other process."""
        m = sys.modules.get(_CG_MAIN)
        if m is not None and getattr(m, "SYSTEM", None) is not None and callable(getattr(m, "shutdown_system", None)):
            return m
        return None

    def _cg_tick(self, now: float) -> None:
        sw = _cg_switch()
        if not sw:
            return                         # no switch file: today's behaviour exactly
        guard_on = sw.get("on") is True
        census_on = sw.get("census") is True
        if not (guard_on or census_on):
            return
        if not self._cg_lock.acquire(blocking=False):
            return                         # another heartbeat thread is sampling this very moment
        try:
            if self._cg_her_main() is None:
                self._cg_say_once("not_her", "[MemoryPressure] commit guard / census idle: not her server process")
                return
            if self._cg_pf is None or (self._cg_pf[0] is None and not (0.0 <= now - self._cg_pf_at < _CG_PF_REREAD_S)):
                self._cg_pf = _cg_pagefile_max()
                self._cg_pf_at = now
            if guard_on:
                self._cg_guard(now, sw)
            if census_on:
                self._mc_tick(now, sw)
        finally:
            self._cg_lock.release()

    def _cg_guard(self, now: float, sw: Dict[str, Any]) -> None:
        sample_s = _cg_num(sw, "sample_s")
        if self._cg_last_sample > 0.0 and 0.0 <= now - self._cg_last_sample < sample_s:
            return
        self._cg_last_sample = now
        if self._cg_fired or self._cg_inflight:
            return                         # one trip per boot; a request in flight is never repeated
        max_pct = _cg_num(sw, "max_pct")
        cur_pct = _cg_num(sw, "cur_pct_at_max")
        need = _cg_num(sw, "confirm_n")
        pf_max, pf_why = self._cg_pf
        if pf_max is None:
            self._cg_say_once("idle:" + pf_why, "[MemoryPressure] commit guard IDLE: page-file max unknown (%s) -- "
                              "GC ladder only, as before" % _cg_ascii(pf_why))
            return
        armed = (max_pct, cur_pct, need, sample_s, pf_max)
        if armed != self._cg_armed:
            self._cg_armed = armed
            print("[MemoryPressure] commit guard ARMED: trip at >= %.0f%% of RAM + page-file max, or > %.0f%% of the "
                  "current limit while the page file is at its max; %d consecutive %.0f s samples (%s)"
                  % (max_pct, cur_pct, need, sample_s, _cg_ascii(pf_why)), flush=True)
        ev = _cg_eval(_cg_perf(), pf_max, max_pct, cur_pct)
        self._cg_last = ev
        if not ev["valid"]:
            self._cg_say_once("invalid:" + ev["why"], "[MemoryPressure] commit guard: no sample (%s), streak held at %d"
                              % (_cg_ascii(ev["why"]), self._cg_streak))
            return
        self._cg_streak = self._cg_streak + 1 if ev["over"] else 0
        if self._cg_streak >= need and now >= self._cg_retry_at:
            self._cg_fire(now, ev)

    def _cg_fire(self, now: float, ev: Dict[str, Any]) -> None:
        self._cg_retry_at = now + _CG_RETRY_S
        self._cg_inflight = True
        print("[MemoryPressure] COMMIT %.0f%% of max, %.0f%% of current (page file at max: %s; rule %s; %d samples) "
              "-> save-first shutdown" % (ev["pct_max"], ev["pct_cur"], "yes" if ev["at_max"] else "no", ev["rule"],
                                          self._cg_streak), flush=True)
        t = threading.Thread(target=self._cg_route, daemon=True, name="CommitGuard-save-first")
        self._cg_thread = t
        try:
            t.start()
        except Exception:
            self._cg_thread = None
            self._cg_route()               # no thread to be had at the wall: the in-process route is quick, run it here

    def _cg_route(self) -> None:
        """Ace's shutdown button, pressed from inside: the route's own handler in-process, else the same route over HTTP."""
        errs = []
        try:
            try:
                m = self._cg_her_main()
                h = getattr(getattr(m, "StatusHandler", None), "_handle_command", None) if m is not None else None
                if callable(h):
                    res = h(None, {"action": "shutdown"})      # the route never reads self (server.py:3666-3853)
                    self._cg_fired = True
                    print("[MemoryPressure] save-first shutdown requested in-process: %s" % _cg_ascii(res), flush=True)
                    return
                errs.append("in-process: no StatusHandler._handle_command")
            except Exception as e:
                errs.append("in-process: %s: %s" % (type(e).__name__, _cg_ascii(e, 80)))
            port = _cg_num(_cg_switch(), "port")
            try:
                status, text = _cg_http_post(port, {"action": "shutdown"}, _CG_HTTP_TIMEOUT_S)
                if 200 <= int(status) < 300:
                    self._cg_fired = True
                    print("[MemoryPressure] save-first shutdown requested over 127.0.0.1:%d/command: %s"
                          % (port, _cg_ascii(text)), flush=True)
                    return
                errs.append("http %d: status %s" % (port, status))
            except Exception as e:
                errs.append("http %d: %s: %s" % (port, type(e).__name__, _cg_ascii(e, 80)))
            print("[MemoryPressure] save-first route UNREACHABLE (%s) -- retry in %.0f s; she is NOT stopped without a "
                  "save" % ("; ".join(errs), _CG_RETRY_S), flush=True)
        finally:
            self._cg_inflight = False

    def _mc_tick(self, now: float, sw: Dict[str, Any]) -> None:
        every = _cg_num(sw, "census_s")
        if self._mc_last > 0.0 and 0.0 <= now - self._mc_last < every:
            return
        self._mc_last = now
        print(self._mc_line(now), flush=True)

    def _mc_line(self, now: float) -> str:
        """One census line; every part is read on its own, so a part that fails is '?' and the line still prints."""
        parts = []
        try:
            if self._mc_create is None:
                self._mc_create = float(psutil.Process().create_time())
            parts.append("up=%.1fmin" % ((now - self._mc_create) / 60.0))
        except Exception:
            parts.append("up=?")
        try:
            p = psutil.Process()
            mi = p.memory_info()
            parts.append("private=%.2fGB" % (float(getattr(mi, "private", mi.vms)) / 2 ** 30))
            parts.append("os_threads=%d" % p.num_threads())
        except Exception:
            parts.append("private=? os_threads=?")
        try:
            parts.append("py_threads=%d" % threading.active_count())
        except Exception:
            parts.append("py_threads=?")
        try:
            perf = _cg_perf()
            total, limit, phys = float(perf["commit_total"]), float(perf["commit_limit"]), float(perf["phys_total"])
            pf_max = self._cg_pf[0] if self._cg_pf else None
            ceiling = (phys + float(pf_max)) if pf_max is not None else 0.0
            pm = "%.0f" % (100.0 * total / ceiling) if (ceiling > 0.0 and limit <= ceiling * _CG_CEIL_SLACK) else "?"
            parts.append("commit=%s%% max / %.0f%% current" % (pm, 100.0 * total / limit))
        except Exception:
            parts.append("commit=?")
        line = "[MemCensus] " + " ".join(parts)
        try:
            line += " | " + _mc_postal_summary(_mc_topic_stats())
        except Exception as e:
            line += " | postal n/a (%s)" % type(e).__name__
        return line


    # ---------------------------------------------------------------------------
    # GARBAGE CENSUS (G1-G4) -- garbage_census_1014: the per-heartbeat part (see the module block above _gz_begin)
    # ---------------------------------------------------------------------------

    def _gz_quiet(self, now: float, cfg: Dict[str, Any]):
        """Is the box quiet enough for the ONE forced reading? -> (ok, why)."""
        if getattr(self, "_cg_fired", False) or getattr(self, "_cg_inflight", False):
            return False, "the commit guard (M0) is active"
        for a in list(self._active_agents):
            th = getattr(a, "_thread", None)
            if type(a).__name__ == "LeakHunterAgent" and th is not None and th.is_alive():
                return False, "a LeakHunter is running"
        if _GZ_RUN_LOCK.locked():
            return False, "a census is running"
        last = float(_GZ["last_census"])
        if last > 0.0 and 0.0 <= now - last < cfg["min_gap_min"] * 60.0:
            return False, "a census ran %.1f min ago" % ((now - last) / 60.0)
        # review F2: the forced run makes LeakHunter's OWN collect + get_objects + get_referrers happen in a boot that would not have
        # had them. Its budget is the watcher's measured collects: each of those three pauses is about one collect or less (probe at
        # 3.84 M objects: collect 238 ms, get_objects 90 ms, get_referrers(12) 150 ms). No measurement = no forced run.
        pred = _gz_watch_max_ms(_GZ_QUIET_WINDOW_S)         # GZ-QUIETPAUSE
        if pred is None:
            return False, "not quiet (no collect measured in the last %.0f min, so the forced run's own pauses have no budget)" % (
                _GZ_QUIET_WINDOW_S / 60.0)
        if pred > cfg["stw_cap_ms"]:
            return False, "not quiet (the longest collect in the last %.0f min took %.0f ms > cap %.0f ms)" % (
                _GZ_QUIET_WINDOW_S / 60.0, pred, cfg["stw_cap_ms"])
        pct, avail = _gz_commit()
        if pct is not None:
            if pct > cfg["quiet_commit_pct"]:
                return False, "not quiet (commit %.0f%% > %.0f%%)" % (pct, cfg["quiet_commit_pct"])
        elif avail is not None:
            if avail < 3.0:
                return False, "not quiet (available RAM %.1f GB < 3 GB)" % avail
        else:
            return False, "commit and available RAM unreadable"
        return True, "quiet"

    def _gz_force(self, now: float, cfg: Dict[str, Any]) -> None:
        """The forced reading: at uptime >= force_at_min, once the box is quiet, a LeakHunter is spawned through _spawn_agent (so the
        5-minute cooldown and the duplicate guard still apply). If it is not quiet for force_window_min: one line, and it is given up."""
        nf = _GZ["next_force"]
        if nf is False:
            return
        if _GZ["force_pending"]:
            # review F3: the spawned LeakHunter may end WITHOUT reaching _gz_begin (its parent weakref died, or memory_info() raised
            # before B1). Then nothing clears force_pending. Its thread ended = stale; with no thread to watch, a window's wait = stale.
            # The try was counted at the spawn, so the 2-try give-up below still applies.
            stale = None
            th = _GZ["force_thread"]
            if th is not None:
                try:
                    if not th.is_alive():
                        stale = "the spawned LeakHunter ended before it reached the census"
                except Exception:
                    stale = "the spawned LeakHunter's thread cannot be read"
            elif not (0.0 <= now - float(_GZ["force_t"]) <= cfg["force_window_min"] * 60.0):
                stale = "no census %.0f min after the spawn" % (max(0.0, now - float(_GZ["force_t"])) / 60.0)
            if stale is not None:                       # GZ-STALE
                _GZ["force_pending"] = False
                _GZ["force_thread"] = None
                _gz_say_once("force_stale_%d" % _GZ["force_tries"], "[GcCensus] forced reading: %s (try %d of 2)" % (
                    stale, _GZ["force_tries"]))
            return
        target = cfg["force_at_min"] if nf is None else float(nf)
        up = _gz_uptime_min(now)
        if up < target:
            return
        if up > target + cfg["force_window_min"]:
            _gz_say_once("force_skip_%.0f" % target, "[GcCensus] forced reading skipped: %s" % (_GZ["quiet_why"] or "not quiet"))
            rep = cfg["force_repeat_min"]
            _GZ["next_force"] = (up + rep) if (rep > 0.0 and _GZ["runs_attached"] < cfg["cap_per_boot"]) else False
            return
        if _GZ["forced_n"] >= 1 and _GZ["runs_attached"] >= cfg["cap_per_boot"]:
            _GZ["next_force"] = False
            return
        ok, why = self._gz_quiet(now, cfg)
        _GZ["quiet_why"] = why
        if not ok:
            return
        if _GZ["force_tries"] >= 2:                 # two spawned LeakHunters never reached a census (M0, lock...): stop paying for them
            _GZ["next_force"] = False
            _gz_say_once("force_giveup", "[GcCensus] forced reading given up: 2 spawned LeakHunters did not reach a census")
            return
        _GZ["force_tries"] += 1
        _GZ["force_pending"] = True
        _GZ["force_t"] = now
        _GZ["force_thread"] = None
        agent = self._spawn_agent(LeakHunterAgent)
        if agent is None:
            _GZ["force_pending"] = False        # on cooldown or one is running: try again next tick, inside the window
            _GZ["force_tries"] -= 1             # nothing was spawned, nothing was spent
        elif _GZ["force_pending"]:
            _GZ["force_thread"] = getattr(agent, "_thread", None)    # _spawn_agent sets it before it returns (base :1458)

    def _gz_tick(self, now: float) -> None:
        """Per heartbeat. Switch absent / not armed: the watcher is removed (if it was ours) and nothing else happens. Armed: register
        the watcher once, one [GcWatch] line per watch_line_min, and the forced-reading decision. Never raises into the tick."""
        sw = _gz_switch()
        if sw.get("on") is not True:
            if _gz_watch_present():
                _gz_watch_set(False)
            _GZ["armed_cfg"] = None
            return
        if not _GZ_TICK_LOCK.acquire(blocking=False):
            return                               # another heartbeat thread is in here this very moment
        try:
            if _gz_her_main() is None:
                _gz_say_once("not_her", "[GcCensus] idle: not her server process")
                return
            cfg = _gz_cfg(sw)
            sig = tuple(sorted(cfg.items()))
            if sig != _GZ["armed_cfg"]:
                if _GZ["armed_cfg"] is None:
                    _GZ["w_at"] = now
                _GZ["armed_cfg"] = sig
                print("[GcCensus] ARMED: up to %d runs with a LeakHunter (after %.0f min up, >= %.0f min apart, commit <= %.0f%%) "
                      "+ 1 forced reading from +%.0f min when quiet (commit <= %.0f%%); g2=%s g3=%s watch=%s; every new pause <= %.0f ms, "
                      "<= %.0f ms per run; sample %d/type, biggest %d, hops %d x %d"
                      % (cfg["cap_per_boot"], cfg["min_uptime_min"], cfg["min_gap_min"], cfg["census_max_commit_pct"],
                         cfg["force_at_min"], cfg["quiet_commit_pct"], cfg["g2"], cfg["g3"], cfg["watch_all"],
                         cfg["stw_cap_ms"], cfg["run_stw_budget_ms"], cfg["sample_per_type"], cfg["biggest_n"],
                         cfg["owner_hops"], cfg["hop_targets"]), flush=True)
            _gz_watch_set(bool(cfg["watch_all"]))
            if cfg["watch_all"] and now - float(_GZ["w_at"]) >= cfg["watch_line_min"] * 60.0:
                line = _gz_watch_line(now)
                _GZ["w_at"] = now
                print(_cg_ascii(line, _GZ_LINE_CHARS), flush=True)
            self._gz_force(now, cfg)
        finally:
            _GZ_TICK_LOCK.release()

    # ═══════════════════════════════════════════════════════════════════════════
    # MONITORING LOGIC
    # ═══════════════════════════════════════════════════════════════════════════

    def _monitor_tick(self) -> None:
        """
        Perform one monitoring tick. Called from on_tick when cadence allows.
        This replaces the old _monitor_loop - no while/sleep, just one check.
        """
        try:
            pct = self._get_memory_percent()
            python_mb = self._get_python_memory_mb()
            level = self._get_level(pct)
            self._pressure_history.append((time.time(), pct, level, python_mb))
            self._monitor_tick_count += 1

            # Periodic status log
            if self._monitor_tick_count % 10 == 0:
                print(f"[{self.ACTOR_NAME}] tick #{self._monitor_tick_count} | RAM: {pct:.1f}% | Python: {python_mb:.0f}MB | level: {level}")

            # Level transition
            if level != self._last_level:
                print(f"[{self.ACTOR_NAME}] Level change: {self._last_level} -> {level} ({pct:.1f}%)")
                self._last_level = level

            # Actions based on level
            if level == "critical":
                # LEVEL 4: Everything
                self._do_gc("critical", generations=2)
                self._emit_alert(level, pct, "RAM critical - aggressive measures")

                # Spawn all agents
                self._spawn_agent(CacheFlushAgent)
                self._spawn_agent(MailboxPrunerAgent)
                self._spawn_agent(DequePatrolAgent)

                # Only spawn leak hunter if GC isn't working
                if self._ineffective_gc_streak >= 2 and not _gd_skip("leakhunter_no_spawn", "leakhunter", self._agent_cooldown_sec):   # gc_diet_1015
                    self._spawn_agent(LeakHunterAgent)

            elif level == "high":
                # LEVEL 3: GC + pruning agents
                # 2026-07-16: gen2->gen1 on the hot ladder (gen2 = 836ms STW freeze;
                # the deep full collect now runs in _fast_poll's window / at critical).
                self._do_gc("high", generations=1)
                self._emit_alert(level, pct, "RAM high - spawning cleanup agents")

                self._spawn_agent(CacheFlushAgent)
                self._spawn_agent(MailboxPrunerAgent)

                # Spawn deque patrol if GC not working
                if self._ineffective_gc_streak >= 2:
                    self._spawn_agent(DequePatrolAgent)

            elif level == "elevated":
                # LEVEL 2: light GC + cache flush
                # 2026-07-16: gen2->gen0 (young-gen is ~5.7x less freezing).
                self._do_gc("elevated", generations=0)

                if self._ineffective_gc_streak >= 2:
                    self._spawn_agent(CacheFlushAgent)
                    self._emit_alert(level, pct, "GC ineffective - requesting cache flush")

            elif level == "warning":
                # LEVEL 1: Light GC (2026-07-16: gen1->gen0)
                self._do_gc("warning", generations=0)

            # else: Comfortable - just monitor

            # Clean up finished agents - ALWAYS do this regardless of level!
            old_count = len(self._active_agents)
            self._active_agents = [a for a in self._active_agents
                                   if (time.time() - a.spawn_time) < 300]  # 5 min max
            if old_count != len(self._active_agents):
                print(f"[{self.ACTOR_NAME}] [CLEANUP] Purged {old_count - len(self._active_agents)} expired agents")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [X] Monitor error: {e}")
            import traceback
            traceback.print_exc()

    def _get_memory_percent(self) -> float:
        if not HAS_PSUTIL:
            return 0.0
        try:
            return psutil.virtual_memory().percent
        except Exception:
            return 0.0

    def _get_python_memory_mb(self) -> float:
        """Get current Python process memory in MB."""
        if not HAS_PSUTIL:
            return 0.0
        try:
            return psutil.Process().memory_info().rss / (1024**2)
        except Exception:
            return 0.0

    def _get_free_gb(self) -> float:
        """Absolute AVAILABLE system RAM in GB (free + reclaimable — what a process can realistically get).
        The honest 'are we actually running low?' signal vs the % proxy. No psutil ⇒ 999 (never false-escalate)."""
        if not HAS_PSUTIL:
            return 999.0
        try:
            return psutil.virtual_memory().available / (1024**3)
        except Exception:
            return 999.0

    def _get_level(self, pct: float, free_gb: float = None) -> str:
        # FREE-RAM FLOOR (2026-06-25): when ample RAM is actually free, there's no pressure to act
        # on — regardless of how high the % looks. A big-but-live footprint isn't an emergency and
        # gc can't shrink it. Only once free RAM is genuinely low does the % ladder escalate (so a
        # real leak / sudden alloc that drives free RAM down is still caught + handled aggressively).
        if free_gb is None:
            free_gb = self._get_free_gb()
        if free_gb >= self.MIN_FREE_GB:
            return "comfortable"
        if pct >= self.THRESHOLD_CRITICAL:
            return "critical"
        elif pct >= self.THRESHOLD_HIGH:
            return "high"
        elif pct >= self.THRESHOLD_ELEVATED:
            return "elevated"
        elif pct >= self.THRESHOLD_WARNING:
            return "warning"
        return "comfortable"

    def _get_cadence(self, level: str) -> float:
        return {
            "comfortable": self.CADENCE_COMFORTABLE,
            "warning": self.CADENCE_WARNING,
            "elevated": self.CADENCE_ELEVATED,
            "high": self.CADENCE_HIGH,
            "critical": self.CADENCE_CRITICAL,
        }.get(level, self.CADENCE_COMFORTABLE)

    def _do_gc(self, reason: str, generations: int = 2) -> Optional[Dict[str, Any]]:
        # FIX 2026-03-03 (Nous): Enforce minimum interval between GC runs.
        # gc.collect(2) on a 9GB process holds the GIL for SECONDS, freezing
        # every thread (print, consciousness, speech). The old code ran it
        # every 5-10s → permanent stop-and-go terminal output.
        now = time.time()
        if (now - self._last_gc_time) < self.MIN_GC_INTERVAL:
            return None  # Too soon — skip this GC
        # gc_diet_1015: ladder_no_collect. The four ladder reasons skip; "manual" (force_gc, the MCP tool) and anything else collect as today.
        # _last_gc_time / _gc_count / _ineffective_gc_streak are NOT touched by a skip; the skip is counted at most once per MIN_GC_INTERVAL.
        if reason in _GD_LADDER and _gd_skip("ladder_no_collect", "ladder", self.MIN_GC_INTERVAL):
            return None

        before = self._get_memory_percent()

        # FIX: gc.collect(N) collects generation N AND all younger ones.
        # So gc.collect(2) already does gen 0 + gen 1 + gen 2.
        # The old for-loop calling gc.collect(0), gc.collect(1), gc.collect(2)
        # did 3x the GIL-holding work for zero additional benefit.
        collected = gc.collect(generations)
        time.sleep(0)  # Explicit GIL yield after GC

        after = self._get_memory_percent()
        self._gc_count += 1
        self._last_gc_time = time.time()
        freed_pct = before - after

        result = {
            "reason": reason,
            "generations": generations,
            "objects_collected": collected,
            "before_pct": before,
            "after_pct": after,
            "freed_pct": freed_pct,
            "gc_count": self._gc_count,
            "ts": self._last_gc_time,
            "effective": freed_pct >= self.GC_EFFECTIVENESS_THRESHOLD,
        }

        self._gc_results.append(result)

        # Track effectiveness
        if result["effective"]:
            self._ineffective_gc_streak = 0
            print(f"[{self.ACTOR_NAME}] [OK] GC freed {freed_pct:.1f}% ({reason})")
        else:
            self._ineffective_gc_streak += 1
            if self._ineffective_gc_streak >= 3:
                print(f"[{self.ACTOR_NAME}] [WARN] GC ineffective {self._ineffective_gc_streak}x - need agents!")

        return result

    def _can_spawn_agent(self, agent_class: type) -> bool:
        """Check if we can spawn this agent type (cooldown + no duplicate)."""
        name = agent_class.__name__
        last_spawn = self._agent_cooldowns.get(name, 0)
        if (time.time() - last_spawn) <= self._agent_cooldown_sec:
            return False

        # FIX 2026-03-03 (Nous): Prevent duplicate agents.
        # Old code only checked cooldown, not whether the agent was still running.
        # LeakHunterAgent scans gc.get_objects() (millions of objects) under GIL —
        # with 6-8 concurrent instances this consumed 200%+ CPU and caused
        # stop-and-go terminal output by starving all other threads of GIL time.
        for existing in self._active_agents:
            if (type(existing).__name__ == name
                    and hasattr(existing, '_thread')
                    and existing._thread is not None
                    and existing._thread.is_alive()):
                return False

        return True

    def _spawn_agent(self, agent_class: type) -> Optional[MemoryAgent]:
        """Spawn a helper agent if not on cooldown and not already running."""
        if not self._can_spawn_agent(agent_class):
            return None

        # Clean up dead agents first
        self._active_agents = [
            a for a in self._active_agents
            if hasattr(a, '_thread') and a._thread is not None and a._thread.is_alive()
        ]

        agent = agent_class(self)
        self._active_agents.append(agent)
        self._agent_cooldowns[agent_class.__name__] = time.time()

        print(f"[{self.ACTOR_NAME}] [GO] Spawned {agent_class.__name__} "
              f"(active agents: {len(self._active_agents)})")

        # Run agent in thread to not block monitor
        def run_agent():
            try:
                result = agent.run()
                print(f"[{self.ACTOR_NAME}] Agent {agent_class.__name__} complete: {result.get('success')}")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Agent {agent_class.__name__} error: {e}")

        t = threading.Thread(target=run_agent, daemon=True, name=f"Agent-{agent_class.__name__}")
        agent._thread = t  # Track thread for duplicate detection
        t.start()

        return agent

    def _emit_alert(self, level: str, pct: float, message: str) -> None:
        now = time.time()
        if now - self._last_alert_time < self._alert_cooldown:
            return
        self._last_alert_time = now

        python_mb = self._get_python_memory_mb()

        alert = {
            "opcode": "MEMORY_PRESSURE_ALERT",
            "payload": {
                "level": level,
                "ram_percent": pct,
                "python_mb": python_mb,
                "message": message,
                "actor": self.ACTOR_NAME,
                "ineffective_gc_streak": self._ineffective_gc_streak,
                "agents_spawned": len(self._active_agents),
                "ts": now,
            }
        }

        level_icons = {"critical": "[CRIT]", "high": "[HIGH]", "elevated": "[WARN]", "warning": "[INFO]"}
        icon = level_icons.get(level, "")
        print(f"[{self.ACTOR_NAME}] {icon} {level.upper()}: {pct:.1f}% RAM, Python {python_mb:.0f}MB - {message}")

        # Publish via fabric (Fairy base provides self.post)
        try:
            self.post.publish("telemetry", alert)
            self.post.publish("tracer", alert)
            if level == "critical":
                self.post.publish("executive", alert)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════════

    def force_gc(self, reason: str = "manual") -> Dict[str, Any]:
        # Bypass MIN_GC_INTERVAL for explicit manual requests
        self._last_gc_time = 0.0
        result = self._do_gc(reason, generations=2)
        return result or {"skipped": True, "reason": "unexpected"}

    def get_status(self) -> Dict[str, Any]:
        pct = self._get_memory_percent()
        python_mb = self._get_python_memory_mb()
        return {
            "running": self.is_running,
            "ram_percent": pct,
            "python_mb": python_mb,
            "level": self._get_level(pct),
            "gc_count": self._gc_count,
            "ineffective_gc_streak": self._ineffective_gc_streak,
            "active_agents": len(self._active_agents),
            "agent_names": [type(a).__name__ for a in self._active_agents],
            "last_gc_time": self._last_gc_time,
            "history_len": len(self._pressure_history),
        }

    def get_trend(self) -> Dict[str, Any]:
        if len(self._pressure_history) < 5:
            return {"trend": "insufficient_data"}

        recent = list(self._pressure_history)[-20:]
        values = [p[1] for p in recent]
        avg = sum(values) / len(values)

        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        if second_avg > first_avg + 3:
            trend = "rising"
        elif second_avg < first_avg - 3:
            trend = "falling"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "current": values[-1] if values else 0,
            "average": avg,
            "min": min(values),
            "max": max(values),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON + BOOT
# ═══════════════════════════════════════════════════════════════════════════════

_instance: Optional[MemoryPressureFairy] = None


def get_memory_pressure_fairy(fabric=None) -> MemoryPressureFairy:
    """Get or create the singleton MemoryPressureFairy instance."""
    global _instance
    if _instance is None:
        _instance = MemoryPressureFairy(fabric=fabric)
    return _instance


def start_memory_pressure_monitor(fabric=None) -> MemoryPressureFairy:
    """Get the fairy and boot it."""
    fairy = get_memory_pressure_fairy(fabric)
    if not fairy.is_running:
        fairy.boot()
    return fairy


def force_gc(reason: str = "manual") -> Dict[str, Any]:
    """Force a garbage collection via the fairy."""
    fairy = get_memory_pressure_fairy()
    return fairy.force_gc(reason)


def on_boot(fabric=None) -> MemoryPressureFairy:
    """Boot function for orchestrator compatibility."""
    return start_memory_pressure_monitor(fabric)


if __name__ == "__main__":
    print("Testing MemoryPressureFairy v0.3.0...")
    fairy = MemoryPressureFairy()
    fairy.boot()
    print(f"Status: {fairy.get_status()}")
    result = fairy.force_gc("test")
    print(f"GC result: {result}")

    # Test agent spawning
    agent = CacheFlushAgent(fairy)
    print(f"Agent report: {agent.report()}")

    fairy.shutdown()
