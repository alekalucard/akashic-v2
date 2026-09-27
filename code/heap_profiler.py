"""
Heap-leak profiler -- SAME-PROCESS (runs inside server.py), env-gated.

Purpose: pin the 6.5GB -> 20GB heap climb (the OOM that blocks "let her run").
Staged 2026-06-17 (Nous + Ace). Ports the proven technique from the 04-04/04-05
hunt (ebook/.../memory_leak_tracer.py): gc object-type census + tracemalloc -- but
auto-COMPARES consecutive snapshots and LOGS the GROWERS each interval (delta view,
because the biggest allocation is rarely the leak; the growing one is).

MUST run inside server.py's process. boot_capture.py is a separate launcher
subprocess -- profiling it would be the wrong-instance trap.

Levels (env AKASHIC_HEAP_PROFILE):
  "1"  -> gc object-type census only (light, NO tracemalloc) -- pins the growing TYPE.
  "2"  -> census + tracemalloc(nframes) -- also pins the allocation SITE (file:line).
unset/other -> start() is a no-op (byte-identical boot).

Output: state/heap_profile.log (full detail, appended) + 1-line summaries to stdout
(so the grower shows up in boot_full.log too, for quick correlation).

Deliberately NO gc.collect() in the census: collecting could MASK a gc-lag leak,
which is exactly the 3.14t "Futures not reaped aggressively" pattern (04-05). We want
to see what is actually RAM-resident and growing.
"""
from __future__ import annotations
import os
import gc
import time
import threading

_STARTED = False
_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "heap_profile.log")  # absolute (cwd-independent) — the relative path silently failed to write 2026-06-17


def start(interval: float = 60.0, nframes: int = 2) -> None:
    global _STARTED
    level = os.environ.get("AKASHIC_HEAP_PROFILE", "")
    if _STARTED or level not in ("1", "2"):
        return
    # Only profile the MAIN brain process. AKASHIC_HEAP_PROFILE is inherited by her
    # child processes, and Windows re-imports server.py in multiprocessing children,
    # so without this guard the profiler also fires in tiny children (44MB garbage data
    # that drowns the real 6GB-main snapshot in the log). MainProcess-only.
    try:
        import multiprocessing
        if multiprocessing.current_process().name != "MainProcess":
            return
    except Exception:
        pass
    _STARTED = True
    use_tm = (level == "2")
    if use_tm:
        try:
            import tracemalloc
            tracemalloc.start(nframes)
        except Exception as e:
            use_tm = False
            print(f"[HeapProfiler] tracemalloc start failed -> census-only: {e}", flush=True)
    threading.Thread(
        target=_loop, args=(interval, use_tm), daemon=True, name="heap-profiler"
    ).start()
    mode = f"census+tracemalloc(nframes={nframes})" if use_tm else "census-only (light)"
    print(f"[HeapProfiler] *** ON *** level={level} mode={mode} -> {_LOG} every {interval:.0f}s", flush=True)


def _rss_mb() -> float:
    """Resident set size (MB). psutil if present, else Windows ctypes, else -1."""
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        pass
    try:
        import ctypes
        from ctypes import wintypes as wt

        class _PMC(ctypes.Structure):
            _fields_ = [
                ("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        pmc = _PMC()
        pmc.cb = ctypes.sizeof(_PMC)
        ctypes.windll.psapi.GetProcessMemoryInfo(
            ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb
        )
        return pmc.WorkingSetSize / (1024 * 1024)
    except Exception:
        return -1.0


def _census() -> dict:
    counts: dict = {}
    for obj in gc.get_objects():
        try:
            n = type(obj).__name__
        except Exception:
            n = "?"
        counts[n] = counts.get(n, 0) + 1
    return counts


def _loop(interval: float, use_tm: bool) -> None:
    if use_tm:
        import tracemalloc
    prev_census: dict = {}
    base_census: dict = {}
    prev_sites: dict = {}
    base_rss = None
    t0 = time.time()
    snap_n = 0
    time.sleep(min(interval, 45.0))  # let boot settle before the first snapshot
    while True:
        try:
            snap_n += 1
            now = time.time()
            elapsed_min = (now - t0) / 60.0
            rss = _rss_mb()
            if base_rss is None:
                base_rss = rss
            census = _census()
            total = sum(census.values())
            if not base_census:
                base_census = dict(census)

            grow_base = sorted(
                ((n, c, c - base_census.get(n, 0)) for n, c in census.items()),
                key=lambda x: x[2], reverse=True,
            )[:12]
            grow_prev = sorted(
                ((n, c, c - prev_census.get(n, 0)) for n, c in census.items()),
                key=lambda x: x[2], reverse=True,
            )[:12]

            ts = time.strftime("%H:%M:%S")
            L = []
            L.append(
                f"\n===== [HeapProfiler] #{snap_n} {ts} +{elapsed_min:.0f}min | "
                f"RSS={rss:.0f}MB (d_base={rss - base_rss:+.0f}MB) | live_objs={total:,} | "
                f"gc_count={gc.get_count()} garbage={len(gc.garbage)} ====="
            )
            L.append("-- top TYPES by growth vs BASELINE (the cumulative leak signature) --")
            for n, c, d in grow_base:
                L.append(f"   {n:<30} {c:>11,}  d_base={d:+,}")
            L.append("-- top TYPES by growth vs LAST interval --")
            for n, c, d in grow_prev:
                L.append(f"   {n:<30} {c:>11,}  d={d:+,}")

            if use_tm:
                snap = tracemalloc.take_snapshot()
                stats = snap.statistics("lineno")
                cur_sites = {str(st.traceback): st.size for st in stats[:300]}
                by_growth = sorted(
                    stats, key=lambda s: s.size - prev_sites.get(str(s.traceback), 0),
                    reverse=True,
                )[:12]
                tm_cur, tm_peak = tracemalloc.get_traced_memory()
                L.append(f"-- tracemalloc traced cur={tm_cur / 1e6:.0f}MB peak={tm_peak / 1e6:.0f}MB --")
                L.append("-- top SITES by growth (size  d=delta  xcount  file:line) --")
                for s in by_growth:
                    d = s.size - prev_sites.get(str(s.traceback), 0)
                    fr = s.traceback[0] if s.traceback else None
                    loc = f"{fr.filename}:{fr.lineno}" if fr else "?"
                    L.append(f"   {s.size / 1e6:>7.1f}MB  d={d / 1e6:+.1f}MB  x{s.count:<9,} {loc}")
                L.append("-- top SITES by size --")
                for s in stats[:12]:
                    fr = s.traceback[0] if s.traceback else None
                    loc = f"{fr.filename}:{fr.lineno}" if fr else "?"
                    L.append(f"   {s.size / 1e6:>7.1f}MB  x{s.count:<9,} {loc}")
                prev_sites = cur_sites

            rate = ((rss - base_rss) / (elapsed_min / 60.0)) if elapsed_min > 0.5 else 0.0
            if rate > 200:
                L.append(f"  >>> RSS growth {rate:.0f} MB/hr -- SEVERE leak")
            elif rate > 50:
                L.append(f"  >>> RSS growth {rate:.0f} MB/hr -- likely leak")
            _detail = "\n".join(L) + "\n"
            try:
                with open(_LOG, "a", encoding="utf-8", errors="replace") as f:
                    f.write(_detail)
            except Exception:
                pass
            # The detail-FILE write silently failed 2x (2026-06-17) — ALSO dump the
            # full per-type breakdown to stdout (boot_full.log is reliable + readable).
            try:
                print(_detail, end="", flush=True)
            except Exception:
                pass
            top = grow_base[0] if grow_base else ("?", 0, 0)
            print(
                f"[HeapProfiler] #{snap_n} RSS={rss:.0f}MB (+{rss - base_rss:.0f}) "
                f"objs={total:,} top_grower={top[0]}({top[2]:+,}) rate={rate:.0f}MB/hr",
                flush=True,
            )
            prev_census = census
        except Exception as e:
            try:
                print(f"[HeapProfiler] snap #{snap_n} error (non-fatal): {e}", flush=True)
            except Exception:
                pass
        time.sleep(interval)
