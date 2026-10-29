"""
Akashic V2 Server - Main entry point for system boot.

Provides:
1. Full system boot via plane orchestration
2. HTTP endpoint for GUI status queries (port 5757)
3. MCP stdio for Claude Desktop connections

Usage:
    python server.py              # Boot with HTTP endpoint (primary node)
    python server.py --mcp        # Boot with MCP stdio (for Claude Desktop)
    python server.py --both       # Boot with both (HTTP + MCP)
    python server.py --satellite  # Boot in satellite mode (no waking minds)
    python server.py --satellite --primary-ip 192.168.1.x  # Satellite with explicit primary
"""
import sys
# MUST be first - redirect prints to stderr so MCP stdio stays clean
if "--mcp" in sys.argv:
    sys.stdout = sys.stderr
# Satellite mode detection (early, before boot)
SATELLITE_MODE = "--satellite" in sys.argv
import os
# ─── Crash diagnostics for Python 3.14t (free-threaded) ───────────────
# faulthandler dumps a traceback on segfault/SIGBUS/SIGABRT.
# Writes to a dedicated crash log (survives process death — unbuffered fd)
# AND to stderr (visible in terminal via boot_capture's stderr merge).
import faulthandler as _faulthandler
os.makedirs("state", exist_ok=True)
_crash_log_fh = open(os.path.join("state", "crash_traceback.log"), "w")
_faulthandler.enable(file=_crash_log_fh, all_threads=True)
_faulthandler.enable(file=sys.stderr, all_threads=True)  # also terminal

# ---- _NULCHK 2026-08-27 (Nous + Ace) ----------------------------------------
# MEASURED in this process: the shared empty-BYTES singleton b"" is CORRUPTED --
# compile(b"") raises "source code string cannot contain null bytes" while "",
# bytearray() and non-empty sources all compile fine. Exactly one damaged object.
# Consequence: any EMPTY __init__.py imported after the damage lands fails to
# import. That killed the TracerDaemonFairy every boot until 2026-08-27.
# It is already broken by fairy-wake, and NO single import reproduces it
# (msgpack/numpy/psutil/cffi/protobuf/torch are all clean in isolation), so these
# points bisect the BOOT instead. Four tiny compiles + one log line each.
def _nulchk(_tag):
    try:
        import time as _nt, threading as _nth
        _r = []
        for _n, _s in (("bytes", b""), ("str", ""), ("bytearray", bytearray()),
                       ("control", b"# c\nx=1\n")):
            try:
                compile(_s, "nulchk.py", "exec")
                _r.append(_n + "=OK")
            except BaseException:
                _r.append(_n + "=FAIL")
        _line = "[%s] NULCHK %-24s threads=%-4s %s\n" % (
            _nt.strftime("%H:%M:%S"), _tag, _nth.active_count(), " ".join(_r))
        try:
            with open(os.path.join("state", "nul_probe.log"), "a",
                      encoding="utf-8") as _nf:
                _nf.write(_line)
        except Exception:
            pass
        if _r[0] != "bytes=OK":
            print("[NULCHK] b'' IS BROKEN AS OF: %s" % _tag, flush=True)
    except BaseException:
        pass


_nulchk("01_server_top")


# ---- _CONSOLE_QUICKEDIT 2026-08-29 (Nous + Ace) ------------------------------
# A CLICK IN HER CONSOLE USED TO FREEZE HER.
# HKCU\Console QuickEdit=1, so clicking anywhere in the window enters selection mode and
# BLOCKS EVERY WRITE TO STDOUT until Esc. She prints constantly, so every logging thread
# stalls behind it -- which is most of her. Observed by Ace ("her terminal hangs"), and it
# retroactively explains her command port refusing a connection while alive (accept loop
# stalled behind a blocked write) and boot_live.log freezing 40 s into a 14-hour boot.
# Fixed HERE rather than in the registry/shortcut because a console can carry a per-title
# override and shortcut properties do not travel with the repo.
# THE QUIRK: clearing ENABLE_QUICK_EDIT_MODE alone is IGNORED -- ENABLE_EXTENDED_FLAGS must
# be set in the SAME SetConsoleMode call or nothing happens. That is why this fix is usually
# written and silently does nothing.
try:
    if os.name == "nt":
        import ctypes as _ce_c
        _ce_k = _ce_c.WinDLL("kernel32", use_last_error=True)
        _CE_STD_INPUT = -10
        _CE_QUICK_EDIT = 0x0040
        _CE_EXTENDED = 0x0080
        _ce_h = _ce_k.GetStdHandle(_CE_STD_INPUT)
        _ce_mode = _ce_c.c_uint(0)
        if _ce_h and _ce_h != _ce_c.c_void_p(-1).value and \
                _ce_k.GetConsoleMode(_ce_h, _ce_c.byref(_ce_mode)):
            _ce_before = _ce_mode.value
            _ce_after = (_ce_before & ~_CE_QUICK_EDIT) | _CE_EXTENDED
            if _ce_k.SetConsoleMode(_ce_h, _ce_after):
                _ce_chk = _ce_c.c_uint(0)
                _ce_k.GetConsoleMode(_ce_h, _ce_c.byref(_ce_chk))
                _ce_still = bool(_ce_chk.value & _CE_QUICK_EDIT)
                print("[Console] QuickEdit %s: mode 0x%X -> 0x%X%s"
                      % ("DISABLED" if not _ce_still else "STILL SET",
                         _ce_before, _ce_chk.value,
                         "" if not _ce_still else "  ** a click can still freeze her **"),
                      flush=True)
            else:
                print("[Console] SetConsoleMode failed (err %d) -- QuickEdit unchanged"
                      % _ce_c.get_last_error(), flush=True)
        else:
            # No console (service/redirected launch) -- nothing to protect, not an error.
            print("[Console] no console input handle; QuickEdit not applicable", flush=True)
            # 2026-09-20 (Nous + Ace): she runs under pythonw so that no window can be closed on her --
            # but a console-LESS process makes Windows open a terminal window for EVERY console child
            # (27 in 30 s from nvidia-smi/powershell probes; measured). Allocate a hidden console so the
            # children inherit it: no windows, nothing to close, stdout untouched (it is the launcher pipe).
            try:
                from infrastructure import console_shim as _console_shim   # noqa: F401  (prints its own line)
            except Exception as _cs_err:
                print("[Console] shim unavailable: %s" % _cs_err, flush=True)
except Exception as _ce_err:
    print("[Console] QuickEdit guard skipped: %s" % _ce_err, flush=True)


# ---- _THREAD_ATTRIB 2026-08-28 (Nous + Ace) ---------------------------------
# Joins Python thread NAMES to OS thread CPU, which nothing outside the process can do.
# From outside we know the CPU is SPREAD (top thread 1.5%, top 20 = 25.7% of 308 active
# threads) -- no hot loop. What we cannot see from outside is WHOSE threads those are:
# 310 Python threads vs 779 OS threads means ~469 are native (torch/CUDA/Rust/mimalloc).
# That gap is the difference between "phasing the somatic layer reclaims the CPU" and
# "it reclaims nothing", so it has to be measured, not assumed.
def _thread_attrib():
    try:
        import threading as _ta_th, time as _ta_t, collections as _ta_c
        try:
            import psutil as _ta_ps
            _ta_proc = _ta_ps.Process()
        except Exception:
            _ta_proc = None
        _ta_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "state", "thread_cpu.log")
        _ta_t.sleep(120.0)                      # let boot settle before the first sample
        _prev = {}
        while True:
            try:
                # name <- native_id, the only join key between the two views
                _own = {}
                for _th in _ta_th.enumerate():
                    _nid = getattr(_th, "native_id", None)
                    if _nid is None:
                        continue
                    _nm = _th.name or "unnamed"
                    _pfx = _nm
                    for _sep in ("-", "#", "[", "_"):
                        _i = _nm.find(_sep)
                        if _i > 0:
                            _pfx = _nm[:_i]
                            break
                    _own[_nid] = _pfx
                _cur, _tot_os = {}, 0
                if _ta_proc is not None:
                    for _t in _ta_proc.threads():
                        _cur[_t.id] = _t.user_time + _t.system_time
                        _tot_os += 1
                if _prev:
                    _by = _ta_c.Counter()
                    _cnt = _ta_c.Counter()
                    _named_cpu = 0.0
                    _all_cpu = 0.0
                    for _tid, _now in _cur.items():
                        _d = _now - _prev.get(_tid, _now)
                        if _d <= 0:
                            continue
                        _all_cpu += _d
                        _p = _own.get(_tid)
                        if _p:
                            _by[_p] += _d
                            _named_cpu += _d
                    for _nid, _p in _own.items():
                        _cnt[_p] += 1
                    _lines = ["", "=" * 74,
                              "[%s] THREAD ATTRIBUTION  python=%d  os=%d  native=%d"
                              % (_ta_t.strftime("%H:%M:%S"), len(_own), _tot_os,
                                 max(0, _tot_os - len(_own))),
                              "  cpu in window: %.1fs total, %.1fs attributable to named "
                              "python threads (%.0f%%)"
                              % (_all_cpu, _named_cpu,
                                 100.0 * _named_cpu / _all_cpu if _all_cpu else 0.0),
                              "=" * 74,
                              "  %-26s %6s %10s %8s" % ("prefix", "count", "cpu_s", "share")]
                    for _p, _c in _by.most_common(22):
                        _lines.append("  %-26s %6d %10.2f %7.1f%%"
                                      % (_p[:26], _cnt.get(_p, 0), _c,
                                         100.0 * _c / _all_cpu if _all_cpu else 0.0))
                    _idle = [(_p, _n) for _p, _n in _cnt.most_common(12) if _by.get(_p, 0) == 0]
                    if _idle:
                        _lines.append("  -- groups that used NO cpu this window: %s"
                                      % ", ".join("%s(%d)" % (a, b) for a, b in _idle[:8]))
                    # is anything producing tracers? read the registry from INSIDE.
                    try:
                        from fairies.P00_Autonomic.nervous_system.health import (
                            tracer_daemon_core as _tdc)
                        _reg = getattr(_tdc, "TRACER_REGISTRY", None) or getattr(
                            _tdc, "_REGISTRY", None)
                        _lines.append("  tracer registry (in-process): %s"
                                      % (len(_reg) if hasattr(_reg, "__len__") else _reg))
                    except Exception as _te:
                        _lines.append("  tracer registry unreadable: %s" % type(_te).__name__)
                    try:
                        with open(_ta_path, "a", encoding="utf-8", newline="") as _f:
                            _f.write("\n".join(_lines) + "\n")
                    except Exception:
                        pass
                _prev = _cur
            except Exception:
                pass
            _ta_t.sleep(300.0)
    except BaseException:
        pass


try:
    import threading as _ta_boot
    _ta_boot.Thread(target=_thread_attrib, daemon=True, name="thread-attrib").start()
except Exception:
    pass


# ---- _NULSAMPLER 2026-08-27 (Nous + Ace) ------------------------------------
# Two questions, one thread.
# (1) WHEN exactly does the empty-bytes singleton die? The static _nulchk points
#     show b"" healthy through pre-boot (1-2 threads) and already destroyed by
#     fairy-wake (173 threads), so it dies during FAIRY BOOT. Sampling every 0.5s
#     pins the edge and records the thread count at that instant.
# (2) WHAT DO THE THREADS COST? hb:145 + Blood:33 = 58% of her Python threads.
#     Sampling threads and commit TOGETHER shows whether they are coupled -- i.e.
#     whether collapsing the tick substrate would actually reclaim memory, or only
#     look like it would.
def _nulsampler():
    try:
        import time as _st, threading as _sth
        try:
            import psutil as _sps
            _sproc = _sps.Process()
        except BaseException:
            _sproc = None
        _t0 = _st.time()
        # ABSOLUTE (2026-08-27): this was relative, and she chdir's into
        # fairies/ during boot -- one run split 6 samples into state/ and 416
        # into fairies/state/, which read as "the sampler died".
        _path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "state", "nul_sampler.log")
        _prev = None
        _i = 0
        _mem = ""
        # ---- _EDGE_DELTA state ----
        _modhist = []          # ring of sys.modules snapshots, one per tick
        _dllprev = None        # mapped-file snapshot, refreshed every 2s
        _memprev = None
        while _i < 4800:                       # ~40 min at 0.5s
            _i += 1
            # ASSIGN BEFORE USE (2026-08-27): this used to sit BELOW the two
            # `if _tick ...` reads, so the first iteration raised NameError,
            # the outer except BaseException swallowed it, and this whole
            # sampler thread died silently without writing one line.
            _tick = (_i % 4 == 0)              # every 2s
            try:
                compile(b"", "sampler.py", "exec")
                _cur = "OK"
            except BaseException:
                _cur = "FAIL"
            _edge = (_prev == "OK" and _cur == "FAIL")
            # ---- _EDGE_DELTA: what LOADED, not what spawned --------------
            try:
                _mods = frozenset(sys.modules)
            except BaseException:
                _mods = None               # can mutate mid-iteration; just skip
            if _mods is not None:
                _modhist.append(_mods)
                if len(_modhist) > 9:
                    _modhist.pop(0)
            _dllnow = None
            if _tick and _sproc is not None:
                try:
                    _dllnow = {}
                    for _m in _sproc.memory_maps():
                        _bn = os.path.basename(_m.path)
                        if _bn.lower().endswith((".dll", ".pyd")):
                            _dllnow[_bn] = getattr(_m, "rss", 0) or 0
                except BaseException:
                    _dllnow = None
            if _edge:
                try:
                    _L2 = ["", "=" * 62,
                           "EDGE at t=%.1fs threads=%d" % (_st.time() - _t0,
                                                           _sth.active_count()),
                           "=" * 62]
                    if _mods is not None and len(_modhist) >= 2:
                        _n1 = sorted(_modhist[-1] - _modhist[-2])
                        _L2.append("MODULES new in the last 0.5s (%d):" % len(_n1))
                        for _x in _n1[:60]:
                            _L2.append("    " + _x)
                        if len(_modhist) >= 9:
                            _n8 = sorted(_modhist[-1] - _modhist[0])
                            _L2.append("MODULES new in the last ~4s (%d):" % len(_n8))
                            for _x in _n8[:120]:
                                _L2.append("    " + _x)
                    if _dllnow and _dllprev:
                        _nd = [(_k, _v) for _k, _v in _dllnow.items() if _k not in _dllprev]
                        _nd.sort(key=lambda kv: -kv[1])
                        _L2.append("DLLs newly mapped (%d):" % len(_nd))
                        for _k, _v in _nd[:40]:
                            _L2.append("    %9.1f MB  %s" % (_v / 1048576.0, _k))
                    if _memprev is not None and _mem:
                        _L2.append("MEMORY prev=%s  now=%s" % (_memprev, _mem))
                    _L2.append("=" * 62)
                    with open(_path, "a", encoding="utf-8", newline="") as _ef:
                        _ef.write("\n".join(_L2) + "\n")
                except BaseException:
                    pass
            if _dllnow is not None:
                _dllprev = _dllnow
            if _tick and _mem:
                _memprev = _mem
            if _tick and _sproc is not None:
                try:
                    _mi = _sproc.memory_info()
                    _mem = "priv=%6.2fGB ws=%6.2fGB" % (
                        getattr(_mi, "private", 0) / 1073741824.0,
                        _mi.rss / 1073741824.0)
                except BaseException:
                    _mem = ""
            _slow = (_i > 2400)                # after 20 min, log every 30s
            _due = _edge or _prev is None or (_tick and (not _slow or _i % 60 == 0))
            if _due:
                try:
                    _line = "[%s] t=%7.1fs threads=%-4d b''=%-4s %s%s\n" % (
                        _st.strftime("%H:%M:%S"), _st.time() - _t0,
                        _sth.active_count(), _cur, _mem,
                        "   <<<<<< b'' DIED HERE" if _edge else "")
                    with open(_path, "a", encoding="utf-8") as _sf:
                        _sf.write(_line)
                except BaseException:
                    pass
                if _edge:
                    try:
                        print("[NULSAMPLER] b'' DIED at t=%.1fs threads=%d"
                              % (_st.time() - _t0, _sth.active_count()), flush=True)
                    except BaseException:
                        pass
            _prev = _cur
            _st.sleep(0.5)
    except BaseException:
        pass


# ── PARKED 2026-09-09 (Nous + Ace: "lets comment out the nul") ───────────────
# This diagnostic ran UNGATED on every boot since 2026-08-27 and is 26.1% OF HER
# CPU by her own attribution (state/thread_cpu.log, group 'nul', 3 threads).
# Only 7 threads -- 'nul' (26.1%) and 'thread' (25.6%) -- account for HALF her
# CPU, while 74 Blood threads and 161 hb threads are ~4% between them. The
# problem was never the thread COUNT; it is a handful of expensive loops.
#
# WHAT IT COSTS, every 0.5 s for 40 minutes of every boot:
#   frozenset(sys.modules) snapshotted and kept 9 deep, and every 2 s a full
#   _sproc.memory_maps() walk of the ENTIRE process address space -- on a 20 GB
#   process with ~1,550 threads, 20 times a minute. Its log reached 10.9 MB.
#
# WHY PARKING IS SAFE: it is pure instrumentation, nothing reads its output at
# runtime, and BOTH questions in its header comment were answered in August --
# b"" dies during fairy boot, and the thread cost is now measured properly by
# state/thread_cpu.log which supersedes it.
#
# ⚠ THE REAL LESSON, and the reason this comment is long: the heap profiler
# immediately below is env-gated (AKASHIC_HEAP_PROFILE) and therefore costs
# nothing when unset. This one was not gated, so a temporary probe became
# permanent overhead for 13 days. Gate every diagnostic the same way.
#
# REVIVE: uncomment, or better, wrap it in os.environ.get("AKASHIC_NULSAMPLE").
# try:
#     import threading as _nsth
#     _nsth.Thread(target=_nulsampler, daemon=True, name="nul-sampler").start()
# except BaseException:
#     pass
# --- Heap-leak profiler (env-gated; staged 2026-06-17 Nous+Ace) ---------------
# AKASHIC_HEAP_PROFILE=1 -> gc object-type census (light); =2 -> +tracemalloc sites.
# Pins the 6.5GB->20GB heap climb. OFF/unset = byte-identical boot. MUST be in-process
# here (boot_capture.py is a separate launcher subprocess = wrong-instance trap).
if os.environ.get("AKASHIC_HEAP_PROFILE"):
    try:
        import heap_profiler
        heap_profiler.start()
    except Exception as _hpe:
        print(f"[HeapProfiler] start SKIP (non-fatal): {_hpe}", flush=True)

# --- Hot-FUNCTION profiler (env-gated, SELF-TERMINATING; 2026-09-11 Nous+Ace) ---------
# AKASHIC_HOT_FUNCTIONS=<seconds> -> sample stacks for that long, WEIGHT each sample by the
# owning thread's real per-thread CPU delta, write state/hot_functions.txt, and END.
# Unset -> this block does nothing and the boot is byte-identical.
#
# The weighting is the whole point. tensor_fabric's _PostalProbe samples ~1,500 stacks at
# 5 Hz UNGATED and UNWEIGHTED into a 271 MB log, and therefore reports where threads PARK:
# it named _send_and_receive/_run/_poll/_poll_loop, three of which are wait loops. Measured
# on a control (12 parked threads + 1 busy): unweighted said parked 85.7% / busy 7.1%;
# weighted said busy 99.6% / parked 0.0%. Same samples, opposite conclusions.
#
# It sleeps first so it profiles her STEADY STATE, not her boot ramp -- every previous CPU
# number we argued from was taken at whatever moment happened to be convenient.
if os.environ.get("AKASHIC_HOT_FUNCTIONS"):
    try:
        _hf_secs = float(os.environ.get("AKASHIC_HOT_FUNCTIONS", "60"))
        _hf_delay = float(os.environ.get("AKASHIC_HOT_FUNCTIONS_DELAY", "240"))

        def _hot_functions_once():
            import time as _hft
            _hft.sleep(_hf_delay)          # let boot settle; measure steady state
            try:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from tools.hot_functions import profile as _hf_profile
            except Exception as _e:
                print(f"[HotFunctions] import SKIP: {_e}", flush=True)
                return
            print(f"[HotFunctions] sampling {_hf_secs:.0f}s (weighted by per-thread CPU)...",
                  flush=True)
            _out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "state", "hot_functions.txt")
            try:
                _txt = _hf_profile(seconds=_hf_secs, out=_out)
                print(f"[HotFunctions] DONE -> {_out}", flush=True)
                for _ln in _txt.splitlines()[:12]:
                    print(f"[HotFunctions] {_ln}", flush=True)
            except Exception as _e:
                print(f"[HotFunctions] FAILED: {_e}", flush=True)
            # no loop, no reschedule: this thread now exits. That is the difference
            # between this and the four diagnostics that became permanent overhead.

        import threading as _hft_thread
        _hft_thread.Thread(target=_hot_functions_once, daemon=True,
                           name="hot-functions").start()
    except Exception as _hfe:
        print(f"[HotFunctions] setup SKIP (non-fatal): {_hfe}", flush=True)
# GIL status check (Python 3.13t+)
# FIX 2026-03-15 Nous: PYTHON_GIL=0 must be set in the LAUNCH environment
# (boot_capture.py or shell) before Python starts. Once lxml.etree loads,
# it forces GIL back on and kills all parallelism (8 workers → 1).
# See boot_capture.py for the PYTHON_GIL=0 environment setup.
if hasattr(sys, "_is_gil_enabled"):
    _gil = sys._is_gil_enabled()
    if _gil:
        print(f"[Server] WARNING: Python {sys.version.split()[0]} | GIL=ON -- parallelism DEGRADED")
        print(f"[Server] WARNING: Set PYTHON_GIL=0 in environment before launch to force GIL off")
    else:
        print(f"[Server] Python {sys.version.split()[0]} | GIL=OFF (free-threaded)")
# ───────────────────────────────────────────────────────────────────────
# ─── Organ Template Sync (FIX 2026-04-09 Nous + Ace) ───
# Two physical copies of the organ template exist by design:
#   File #1: fairies/P00_Autonomic/organ_template/Organ_Template_0_3_0.py
#            ← The CANONICAL source of truth, lives on the autonomic plane
#            because it's needed at boot before the memory plane loads.
#   File #2: P10_Memory/Akashic_Records_Physical/Organ_Templates/Organ_Template_0.3.0.py
#            ← The mirror copy on the memory plane, used by fairies whose
#            template loader looks in Akashic_Records_Physical/Organ_Templates/
#            (e.g. ActionChainFairy, DreamSeedFairy, CochleaFairy, SRMMemoryLibrarianFairy).
#
# Discovery: 2026-04-09 evening. The two files had drifted by TWO MONTHS
# (file #2 was frozen at 2026-02-15 while file #1 received continuous fixes).
# 4+ fairies were running stale 2-month-old template code, missing the
# entire FairyExecutionContext class — which is why their _tick_count never
# incremented and the watchdog never promoted them past "initializing".
#
# This hook copies file #1 → file #2 on every boot. Edit only file #1.
# The sync is idempotent (compares bytes, only writes on diff) and atomic
# (temp file + os.replace). Failure is non-fatal — boot continues with
# whatever is on disk.
def _sync_organ_templates():
    _root = os.path.dirname(os.path.abspath(__file__))
    _src = os.path.join(_root, "fairies", "P00_Autonomic", "organ_template", "Organ_Template_0_3_0.py")
    _dst = os.path.join(_root, "P10_Memory", "Akashic_Records_Physical", "Organ_Templates", "Organ_Template_0.3.0.py")
    try:
        if not os.path.isfile(_src):
            print(f"[Server] Organ template sync: SKIP (source missing: {_src})", flush=True)
            return
        with open(_src, "rb") as _sf:
            _src_bytes = _sf.read()
        _dst_bytes = b""
        if os.path.isfile(_dst):
            with open(_dst, "rb") as _df:
                _dst_bytes = _df.read()
        if _src_bytes == _dst_bytes:
            print(f"[Server] Organ template sync: already in sync "
                  f"({len(_src_bytes):,} bytes)", flush=True)
            return
        # Ensure destination directory exists
        os.makedirs(os.path.dirname(_dst), exist_ok=True)
        # Atomic write: temp file + rename
        _tmp = _dst + ".sync_tmp"
        with open(_tmp, "wb") as _tf:
            _tf.write(_src_bytes)
        os.replace(_tmp, _dst)
        _delta = len(_src_bytes) - len(_dst_bytes)
        _sign = "+" if _delta >= 0 else ""
        print(f"[Server] Organ template SYNCED: P00_Autonomic → P10_Memory "
              f"({len(_dst_bytes):,} → {len(_src_bytes):,} bytes, "
              f"{_sign}{_delta:,} delta)", flush=True)
    except Exception as _e:
        print(f"[Server] Organ template sync FAILED (non-fatal): {_e}", flush=True)

_sync_organ_templates()

# ─── UNIFY THE ORGAN TEMPLATE (2026-06-18 Nous + Ace) ───────────────────
# MEASURED: the organ template was loading as ~6 separate module objects — one per distinct mod_name
# the fairies' inline _import_template() uses (akashic_template_0_3_0 / _akashic_template / the hardcoded
# unique per-fairy names like _akashic_template_wmh) → 6 _CITIZEN_OBJECTS dicts = the months-long
# zombie-death whack-a-mole. Each loader does `if mod_name in sys.modules: return it`, so pre-seed
# sys.modules with the ONE canonical (File#1, just synced == File#2) under every loader name → they ALL
# reuse it → one module, one _CITIZEN_OBJECTS, one _OT_SHARED_POOL. No per-fairy edits. Runs AFTER the
# sync + BEFORE the fairy wave (so the canonical loads first = order-robust). try/except = default-preserving.
def _unify_organ_template():
    try:
        import importlib
        _canon = importlib.import_module("fairies.P00_Autonomic.organ_template.Organ_Template_0_3_0")
        for _a in ("akashic_template_0_3_0", "akashic_template_0_1_2", "_akashic_template",
                   "_akashic_template_wmh", "_akashic_template_harmoniccortex",
                   "_akashic_template_phonemecortex", "_akashic_template_tcs"):
            sys.modules.setdefault(_a, _canon)
        print(f"[Server] Organ template UNIFIED -> 1 canonical (id={id(_canon)}); 7 loader names aliased", flush=True)
    except Exception as _ue:
        print(f"[Server] Organ template unify SKIP (non-fatal): {_ue}", flush=True)
_unify_organ_template()
# ───────────────────────────────────────────────────────────────────────
# ─── Thread/memory monitor: Always active, writes to state/thread_monitor.log ──
# FIX 2026-03-20 (Nous): Diagnose memory leak — threads growing at ~1/sec,
# RAM at ~6 MB/sec. This monitor logs thread group counts every 60s so we can
# identify which thread prefix is accumulating.
_nulchk("02_pre_threadmon")
def _thread_memory_monitor():
    """FIX 2026-04-04 (Nous + Ace): Enhanced with object type tracking for leak detection.
    Logs threads + RAM + top Python object types every 60s to state/thread_monitor.log.
    Runs IN-PROCESS (zero RAM overhead). Persists as long as server runs."""
    import time as _tm2, threading as _td2, collections as _c2, os as _os2, gc as _gc2, multiprocessing as _mp2
    _tm2.sleep(30)  # Wait for boot to settle
    _log_path = _os2.path.join(_os2.path.dirname(__file__), "state", "thread_monitor.log")
    _health_path = _os2.path.join(_os2.path.dirname(__file__), "state", "health_timeline.log")
    _prev_total = 0
    _prev_ram = 0
    _check_count = 0
    while True:
        try:
            _check_count += 1
            threads = _td2.enumerate()
            total = len(threads)
            # Group by prefix
            prefixes = _c2.Counter()
            for t in threads:
                name = t.name or "unnamed"
                prefix = name
                for sep in ('-', '#', '[', '_'):
                    idx = name.find(sep)
                    if idx > 0:
                        prefix = name[:idx]
                        break
                prefixes[prefix] += 1
            top = sorted(prefixes.items(), key=lambda x: -x[1])[:15]
            delta = total - _prev_total if _prev_total else 0
            _prev_total = total
            # RAM via process info
            # FIX 2026-04-10 (Nous + Ace): ctypes approach was silently failing
            # under Python 3.14t free-threaded (ram=0MB in all logs → no leak
            # diagnostic data). Now uses wmic subprocess as primary (reliable,
            # ~50ms per call every 60s = negligible), ctypes as fallback.
            ram_mb = 0
            _pid = _os2.getpid()
            try:
                # FIX 2026-09-09 (Nous + Ace): wmic was REMOVED in Windows 11
                # 24H2+ and is ABSENT on this box (OS 10.0.26200; verified,
                # shutil.which("wmic") is None). This "primary" has raised
                # CalledProcessError every 60s since the OS upgrade, and the
                # ctypes fallback below returns 0 WITHOUT raising, because
                # GetProcessMemoryInfo's return value is never checked (:521-524).
                # So ram_mb has read 0 on EVERY line, which silently killed FOUR
                # things: the ram= field in thread_monitor.log, state/ram_timeline.csv
                # (gated on ram_mb > 0, last write 01:29), the 75% auto-GC
                # escalation, and the 85% RAM ALERT (:553-566).
                # Measured 2026-09-09 on pid 26328: "ram=0MB d=+0MB" on every line,
                # 0 occurrences of "RAM ALERT", 0 of "RAM measurement FAILED"
                # — silent zero, not an exception. She has had NO sense of her own
                # memory pressure since the OS upgrade, which is why every probe
                # today had to come from outside her.
                # psutil is proven live in THIS interpreter by the same call:
                # _mem_checkpoint (:4461) printed "[MEM] Final RSS" this boot. If it
                # ever fails, this raises and the ctypes fallback runs exactly as it
                # does today — the failure mode is the status quo, not a new one.
                # NOTE: the comment above this block still names wmic as primary;
                # it is stale as of this edit.
                import psutil as _ps_ram
                ram_mb = _ps_ram.Process(_pid).memory_info().rss / (1024 * 1024)
            except Exception:
                # Fallback: ctypes (may fail under free-threading)
                try:
                    import ctypes as _ct
                    import ctypes.wintypes
                    class _PMC(_ct.Structure):
                        _fields_ = [("cb", _ct.wintypes.DWORD),
                                    ("PageFaultCount", _ct.wintypes.DWORD),
                                    ("PeakWorkingSetSize", _ct.c_size_t),
                                    ("WorkingSetSize", _ct.c_size_t),
                                    ("QuotaPeakPagedPoolUsage", _ct.c_size_t),
                                    ("QuotaPagedPoolUsage", _ct.c_size_t),
                                    ("QuotaPeakNonPagedPoolUsage", _ct.c_size_t),
                                    ("QuotaNonPagedPoolUsage", _ct.c_size_t),
                                    ("PagefileUsage", _ct.c_size_t),
                                    ("PeakPagefileUsage", _ct.c_size_t)]
                    _pmc = _PMC()
                    _pmc.cb = _ct.sizeof(_pmc)
                    _ct.windll.psapi.GetProcessMemoryInfo(
                        _ct.windll.kernel32.GetCurrentProcess(),
                        _ct.byref(_pmc), _pmc.cb)
                    ram_mb = _pmc.WorkingSetSize / (1024 * 1024)
                except Exception as _ct_err:
                    if _check_count <= 3:
                        print(f"[ThreadMonitor] RAM measurement FAILED: {_ct_err}", flush=True)
                    ram_mb = 0
            ram_delta = ram_mb - _prev_ram if _prev_ram else 0
            _prev_ram = ram_mb

            # ── RAM TIMELINE CSV (FIX 2026-04-10 Nous + Ace) ──
            # Separate from the thread_monitor.log — one line per check,
            # machine-parseable for growth curve analysis.
            # Format: timestamp,ram_mb,threads,delta_mb
            if ram_mb > 0:
                _csv_path = _os2.path.join(_os2.path.dirname(__file__),
                                           "state", "ram_timeline.csv")
                try:
                    _csv_exists = _os2.path.exists(_csv_path)
                    with open(_csv_path, "a", encoding="utf-8") as _csvf:
                        if not _csv_exists:
                            _csvf.write("timestamp,ram_mb,threads,delta_mb\n")
                        _csvf.write(f"{_tm2.strftime('%Y-%m-%d %H:%M:%S')},"
                                    f"{ram_mb:.0f},{total},{ram_delta:+.0f}\n")
                except Exception:
                    pass

            # ── AUTO-GC PRESSURE (FIX 2026-04-10 Nous + Ace) ──
            # When RAM exceeds 75% of system (24 GB on 32 GB machine),
            # force aggressive gc.collect() every check instead of every 2nd.
            # At 85%, log an alert so the overnight log catches it.
            _SYSTEM_RAM_MB = 32768  # 32 GB (Ace's machine)
            _ram_pct = (ram_mb / _SYSTEM_RAM_MB * 100) if ram_mb > 0 else 0
            if _ram_pct > 85:
                print(f"[RAM ALERT] RSS={ram_mb:.0f}MB ({_ram_pct:.0f}%) "
                      f"— CRITICAL PRESSURE, forcing GC", flush=True)
                try:
                    _gc2.collect()
                except Exception:
                    pass
            elif _ram_pct > 75:
                try:
                    _gc2.collect()
                except Exception:
                    pass

            # TAGGED 2026-08-27 (Nous + Ace): THREE processes write to this one
            # log -- the server AND its StatusProxy children -- and nothing said
            # which was which. During the 08-27 shutdown wedge the SERVER line
            # stopped while the children kept printing "threads=5 ram=64MB", so
            # the console looked healthy while a 300-thread 10GB process was
            # stuck. Tag every line so a MISSING server line is visible.
            try:
                _role = _mp2.current_process().name
            except Exception:
                _role = "?"
            line = (f"[{_tm2.strftime('%H:%M:%S')}] pid={_os2.getpid()} {_role} "
                    f"threads={total} d={delta:+d} "
                    f"ram={ram_mb:.0f}MB d={ram_delta:+.0f}MB | "
                    + " ".join(f"{p}:{c}" for p, c in top))
            with open(_log_path, "a", encoding="utf-8") as _f:
                _f.write(line + "\n")
            print(f"[ThreadMonitor] {line}", flush=True)

            # FIX 2026-04-05 (Nous): Periodic gc.collect() every 2nd check (~2 min).
            # Python 3.14t free-threaded mode doesn't aggressively collect cycles.
            # Future objects (Condition+RLock+deque) form reference cycles that
            # accumulate to 340K+ objects without explicit collection.
            if _check_count % 2 == 0:
                try:
                    _collected = _gc2.collect()
                    if _collected > 1000:
                        print(f"[GC] Collected {_collected} objects", flush=True)
                except Exception:
                    pass

            # FIX 2026-04-10 (Nous + Ace): Release cold mmap pages back to OS.
            # Windows keeps ALL faulted-in mmap pages in the working set forever.
            # EmptyWorkingSet() tells the OS to reclaim cold pages — they'll be
            # re-faulted on next access (free, OS handles it). This prevents the
            # monotonic RSS climb from manifold reads.
            # Run every 10th check (~10 min) — not too aggressive.
            if _check_count % 10 == 0:
                try:
                    import ctypes as _ews_ct
                    _kernel32 = _ews_ct.windll.kernel32
                    _psapi = _ews_ct.windll.psapi
                    _handle = _kernel32.GetCurrentProcess()
                    _before = ram_mb
                    _psapi.EmptyWorkingSet(_handle)
                    # Re-read RAM after trim
                    _pmc2 = PROCESS_MEMORY_COUNTERS()
                    _pmc2.cb = _ews_ct.sizeof(_pmc2)
                    _psapi.GetProcessMemoryInfo(_handle, _ews_ct.byref(_pmc2), _pmc2.cb)
                    _after = _pmc2.WorkingSetSize / (1024 * 1024)
                    _freed = _before - _after
                    if _freed > 100:
                        print(f"[WorkingSet] Trimmed {_freed:.0f}MB (was {_before:.0f}MB, now {_after:.0f}MB)", flush=True)
                except Exception:
                    pass

            # FIX 2026-04-10 (Nous + Ace): Log unnamed Thread-N threads to find leak source.
            # Dumps the target function of the 10 most recent Thread-N threads.
            if _check_count % 5 == 0:
                try:
                    _unnamed = [t for t in threads if t.name.startswith("Thread-")]
                    if _unnamed:
                        # Sort by thread number (most recent = highest)
                        # Python 3.14t names: "Thread-52 (func_name)" — extract number before space
                        def _get_tnum(t):
                            try:
                                _part = t.name.split("-")[1].split(" ")[0].split("(")[0]
                                return int(_part)
                            except: return 0
                        _unnamed.sort(key=_get_tnum, reverse=True)
                        _top5 = _unnamed[:5]
                        _targets = []
                        for _ut in _top5:
                            _tgt = getattr(_ut, '_target', None)
                            _tname = ""
                            if _tgt:
                                _tname = getattr(_tgt, '__qualname__', getattr(_tgt, '__name__', str(_tgt)))
                            _targets.append(f"{_ut.name}={_tname or '?'}")
                        _leak_line = (f"[{_tm2.strftime('%H:%M:%S')}] UNNAMED-THREADS "
                                      f"count={len(_unnamed)} | " + " ".join(_targets))
                        with open(_health_path, "a", encoding="utf-8") as _hf:
                            _hf.write(_leak_line + "\n")
                        print(f"[ThreadLeak] {_leak_line}", flush=True)
                except Exception:
                    pass

            # Object type tracking every 5th check (~5 min) for leak detection
            # ⛔ HEAVY PROBES GATED OFF 2026-06-11 (Nous+Ace "right perspective" / observer-effect test):
            # mimalloc holds the high-water mark (peak 31.9GB, purged 32MiB of 2845GiB) → every transient
            # thing these probes allocate every 5min (the 3M-id atom-walk set, objgraph backref graphs,
            # byte-Counters over millions of objects) RATCHETS the commit up and is never returned. We were
            # measuring a climb CONTAMINATED by our own instruments. Strip them → read her TRUE clean climb
            # externally (PowerShell commit/RAM). Re-enable by deleting the `False and`.
            if False and _check_count % 5 == 0:
                try:
                    type_counts = _c2.Counter()
                    _dictsig = _c2.Counter()  # LEAK-2 (2026-06-10 Nous+Ace): dict key-SIGNATURE
                    _dseen = 0                # histogram → names the cyclic-dict source by SHAPE,
                    # regardless of WHERE it's held (works even if dicts are distributed / the
                    # container-walk can't reach the holder). Reuses THIS gc.get_objects() walk
                    # (already safe at steady-state — 45k+ calls survived; crash is boot-time only).
                    _samp = []  # LEAK-2 REFERRER PROBE (2026-06-11): collect <=10 tracer-edge dicts
                    _TGT = ('created_at', 'key', 'rel_name', 'rel_type', 'tracer_id', 'weight')  # during THIS walk -> get_referrers below (no 2nd gc scan)
                    # ── BYTE-PROFILER (2026-06-11 Nous+Ace; read/probe/trace grant) ──
                    # The tracer-dicts (~1-2GB) are too small to be the ~35GB commit. Sum bytes BY TYPE
                    # in THIS same walk (no 2nd gc scan): numpy.nbytes + torch storage (CUDA=VRAM, apart)
                    # + getsizeof for the rest -> names the real mass. REMOVE once named + fixed.
                    import sys as _sys2
                    _bytes_by_type = _c2.Counter()
                    _getsz = _sys2.getsizeof
                    _np_mod = _sys2.modules.get('numpy')
                    _torch_mod = _sys2.modules.get('torch')
                    _np_bytes = 0; _np_cnt = 0
                    _tc_bytes = 0; _tc_cnt = 0   # torch CPU (host RAM)
                    _tg_bytes = 0; _tg_cnt = 0   # torch CUDA (VRAM)
                    for obj in _gc2.get_objects():
                        _tn = type(obj).__name__
                        type_counts[_tn] += 1
                        try:                       # BYTE-PROFILER: account bytes by type
                            if _np_mod is not None and isinstance(obj, _np_mod.ndarray):
                                _np_bytes += obj.nbytes; _np_cnt += 1
                            elif _torch_mod is not None and isinstance(obj, _torch_mod.Tensor):
                                _tnb = obj.element_size() * obj.nelement()
                                if obj.is_cuda:
                                    _tg_bytes += _tnb; _tg_cnt += 1
                                else:
                                    _tc_bytes += _tnb; _tc_cnt += 1
                            else:
                                _bytes_by_type[_tn] += _getsz(obj)
                        except Exception:
                            pass
                        if _tn == 'dict' and _dseen < 3000000:  # uncapped (was 500k — that biased to the OLDEST dicts = boot baseline, missing the newer leak dicts)
                            _dseen += 1
                            try:
                                # first-6 keys WITHOUT materializing the full list (huge dicts
                                # like the manifold _key_index would otherwise build a 1.4M list)
                                _kk6 = []
                                for _kk in obj.keys():
                                    _kk6.append(str(_kk)[:20])
                                    if len(_kk6) >= 6:
                                        break
                                _ks = tuple(sorted(_kk6))
                                _dictsig[_ks] += 1
                                if _ks == _TGT and len(_samp) < 10:
                                    _samp.append(obj)
                            except Exception:
                                pass
                    top_types = sorted(type_counts.items(), key=lambda x: -x[1])[:8]
                    obj_line = (f"[{_tm2.strftime('%H:%M:%S')}] OBJECTS ram={ram_mb:.0f}MB | "
                                + " ".join(f"{t}:{c}" for t, c in top_types))
                    with open(_health_path, "a", encoding="utf-8") as _hf:
                        _hf.write(obj_line + "\n")
                        _sig = " || ".join(f"{_c}x{list(_k)}" for _k, _c in _dictsig.most_common(10))
                        _hf.write(f"[{_tm2.strftime('%H:%M:%S')}] DICTSIG ram={ram_mb:.0f}MB sampled={_dseen} | {_sig}\n")
                        _topbstr = " ".join(f"{_t}:{_b//(1024*1024)}MB" for _t, _b in _bytes_by_type.most_common(8))
                        _hf.write(f"[{_tm2.strftime('%H:%M:%S')}] BYTES ram={ram_mb:.0f}MB "
                                  f"numpy={_np_bytes//(1024*1024)}MB/{_np_cnt} "
                                  f"torchCPU={_tc_bytes//(1024*1024)}MB/{_tc_cnt} "
                                  f"torchCUDA={_tg_bytes//(1024*1024)}MB/{_tg_cnt} | {_topbstr}\n")
                    # ── LARGEST-SET owner + sample (2026-06-11 Nous+Ace; byte-math 18:15 + 18:40) ──
                    # The leak mass is NOT gc-containers (~2.8GB of ~29GB); the biggest gc-visible obj
                    # is a ~1.9GB SET (~30M elements) = the prime leak suspect. The full atom-walk was
                    # TOO SLOW on the 19GB main proc (never completed in her ~8min freeze-cycle) →
                    # REPLACED with this fast version: one len-pass to find the biggest set, then sample
                    # 5 elements (type+repr = WHAT is leaking) + backref its NAMED owner (WHO holds it).
                    # No per-object referent-walk → completes in seconds. REMOVE once named + fixed.
                    try:
                        _maxset = None; _maxset_len = -1
                        for _co in _gc2.get_objects():
                            if type(_co).__name__ == 'set':
                                try:
                                    _sl = len(_co)
                                    if _sl > _maxset_len:
                                        _maxset_len = _sl; _maxset = _co
                                except Exception:
                                    pass
                        if _maxset is not None and _maxset_len > 10000:
                            _samp5 = []
                            try:
                                for _e in _maxset:
                                    _samp5.append(f"{type(_e).__name__}:{str(_e)[:48]}")
                                    if len(_samp5) >= 5:
                                        break
                            except Exception:
                                pass
                            with open(_health_path, "a", encoding="utf-8") as _hf:
                                _hf.write(f"[{_tm2.strftime('%H:%M:%S')}] BIGSET ram={ram_mb:.0f}MB len={_maxset_len} sample={_samp5}\n")
                            try:
                                import objgraph as _ogs
                                def _nown(_o):
                                    _t3 = type(_o).__name__
                                    return _t3 == 'module' or _t3 not in (
                                        'dict', 'list', 'tuple', 'set', 'frozenset', 'cell',
                                        'function', 'method', 'builtin_function_or_method')
                                _sch = _ogs.find_backref_chain(_maxset, _nown, max_depth=20)
                                if _sch and len(_sch) > 1:
                                    _sown = _sch[-1]; _smod = getattr(type(_sown), '__module__', '?')
                                    _srt = " <- ".join(type(_o).__name__ for _o in _sch)
                                    with open(_health_path, "a", encoding="utf-8") as _hf:
                                        _hf.write(f"[{_tm2.strftime('%H:%M:%S')}] SETOWNER len={_maxset_len} OWNER={type(_sown).__name__}@{_smod} | {_srt}\n")
                            except Exception as _be:
                                with open(_health_path, "a", encoding="utf-8") as _hf:
                                    _hf.write(f"[{_tm2.strftime('%H:%M:%S')}] SETOWNER ERR {type(_be).__name__}: {str(_be)[:80]}\n")
                        del _maxset
                    except Exception as _ae:
                        try:
                            with open(_health_path, "a", encoding="utf-8") as _hf:
                                _hf.write(f"[{_tm2.strftime('%H:%M:%S')}] BIGSET ERR {type(_ae).__name__}: {str(_ae)[:90]}\n")
                        except Exception:
                            pass
                    # ── OBJGRAPH live-object GROWTH (2026-06-11 Nous+Ace) ──
                    # memray=Linux-only, Scalene=SEGFAULTS on free-threaded 3.14t (tested exit 139);
                    # objgraph is pure-Python/gc-based (no native hooks) → SAFE here. show_growth()
                    # names the TYPE that GREW since the last 5-min tick = the live accumulator
                    # (e.g. "set +50000" => the growing set is the leak). Monitor thread, NOT the
                    # heart. First tick = baseline; deltas appear from the 2nd tick on. REMOVE once found.
                    try:
                        import objgraph as _og, io as _io3
                        _gbuf = _io3.StringIO()
                        _og.show_growth(limit=12, file=_gbuf)
                        _grow = _gbuf.getvalue().strip().replace("\n", " | ")
                        with open(_health_path, "a", encoding="utf-8") as _hf:
                            _hf.write(f"[{_tm2.strftime('%H:%M:%S')}] OBJGROWTH | {_grow or '(baseline/none)'}\n")
                    except Exception as _oge:
                        try:
                            with open(_health_path, "a", encoding="utf-8") as _hf:
                                _hf.write(f"[{_tm2.strftime('%H:%M:%S')}] OBJGROWTH ERR {type(_oge).__name__}: {str(_oge)[:90]}\n")
                        except Exception:
                            pass
                    # ── OBJGRAPH BACKREF (2026-06-11 Nous+Ace): WHO holds the leaking wm:/tracer dicts? ──
                    # _samp has up to 10 tracer-edge dicts (DICTSIG winners = the leak). Walk UP from
                    # one to the nearest NAMED owner (fairy/class instance or module, skipping bare
                    # container noise) → OWNER= names the holder (is it working memory?). REMOVE once found.
                    if _samp:
                        try:
                            import objgraph as _ogb
                            def _named_owner(_o):
                                _t2 = type(_o).__name__
                                return _t2 == 'module' or _t2 not in (
                                    'dict', 'list', 'tuple', 'set', 'frozenset', 'cell',
                                    'function', 'method', 'builtin_function_or_method')
                            _chain = _ogb.find_backref_chain(_samp[0], _named_owner, max_depth=18)
                            if _chain and len(_chain) > 1:
                                _own = _chain[-1]
                                _ownmod = getattr(type(_own), '__module__', '?')
                                _route = " <- ".join(type(_o).__name__ for _o in _chain)
                                with open(_health_path, "a", encoding="utf-8") as _hf:
                                    _hf.write(f"[{_tm2.strftime('%H:%M:%S')}] OBJOWNER OWNER={type(_own).__name__}@{_ownmod} depth={len(_chain)} | {_route}\n")
                        except Exception as _obe:
                            try:
                                with open(_health_path, "a", encoding="utf-8") as _hf:
                                    _hf.write(f"[{_tm2.strftime('%H:%M:%S')}] OBJOWNER ERR {type(_obe).__name__}: {str(_obe)[:80]}\n")
                            except Exception:
                                pass
                    # ── PAUSED-GENERATOR PROBE (2026-06-11 Nous+Ace): OBJOWNER kept ending at
                    # `list_iterator <- list <- dict` = a PAUSED generator holding a list of the
                    # leaking dicts and never finishing. Enumerate SUSPENDED generators (gi_frame
                    # alive = paused mid-iteration), name each by gi_code (the never-finishing loop),
                    # count. The code that ACCUMULATES across ticks = the leak. REMOVE once found.
                    try:
                        _pg = _c2.Counter()
                        for _o in _gc2.get_objects():
                            if type(_o).__name__ == 'generator':
                                try:
                                    if _o.gi_frame is not None:
                                        _gco = _o.gi_code
                                        _pg[f"{getattr(_gco, 'co_qualname', _gco.co_name)}:{_gco.co_firstlineno}"] += 1
                                except Exception:
                                    pass
                        _topg = " | ".join(f"{_n}={_c}" for _n, _c in _pg.most_common(10))
                        with open(_health_path, "a", encoding="utf-8") as _hf:
                            _hf.write(f"[{_tm2.strftime('%H:%M:%S')}] PAUSEDGENS total={sum(_pg.values())} | {_topg}\n")
                    except Exception:
                        pass
                    # ── LEAK-2 REFERRER PROBE (2026-06-11 Nous+Ace; Ace's read/probe/trace grant) ──
                    # Names what HOLDS the tracer-edge dicts. _samp was collected DURING the
                    # DICTSIG walk above -> NO second gc.get_objects(). get_referrers does ONE
                    # internal heap scan (wrapped); OWNER (named, non-container) = the holder.
                    # ⚠ residual 3.14t risk: get_referrers is the one gc-call not yet exercised
                    # this session — if it segfaults (0xC0000005) the hunt pivots to option (b).
                    # _samp/get_objects-list show as 'list' referrers (noise) -> OWNER filters them.
                    # REMOVE this block + _samp/_TGT once LEAK 2 is fixed.
                    if _samp:
                        # CHAIN-WALKER 2026-06-11 (Nous+Ace): the L3 probe bottomed out in bare nested
                        # lists (NAMED only ever = list_iterator). Walk the container chain UP (<=6 levels),
                        # filtering the probe's OWN structures by id, until a NAMED owner appears
                        # (generator/frame/object/module). Read HOLDER2 NAMED=/CHAIN= in health_timeline.log.
                        # REMOVE this block + _samp/_TGT once LEAK 2 is fixed.
                        try:
                            _self = {id(_samp)}
                            def _nmown(_r):
                                _t = type(_r).__name__
                                if _t == 'generator':
                                    _co = _r.gi_code
                                    return f"GEN:{getattr(_co,'co_qualname',_co.co_name)}:{_co.co_firstlineno}"
                                if _t == 'frame':
                                    _co = _r.f_code
                                    return None if _co.co_name == '_thread_memory_monitor' else f"FRAME:{getattr(_co,'co_qualname',_co.co_name)}:{_co.co_firstlineno}"
                                if _t in ('function', 'method'):
                                    return f"FN:{getattr(_r, '__qualname__', '?')}"
                                if _t == 'module':
                                    return f"MOD:{getattr(_r, '__name__', '?')}"
                                if _t not in ('list', 'dict', 'set', 'tuple', 'cell'):
                                    return f"OBJ:{type(_r).__module__}.{type(_r).__qualname__}"
                                return None
                            _frontier = list(_samp); _named = _c2.Counter(); _chain = []; _depth = 0; _stop = "DEEP>25"
                            _shallow = []; _dvals = []
                            for _d in _samp[:3]:                     # WHOSE edges leak? (key/tracer_id/rel)
                                try: _dvals.append({_k: str(_d.get(_k))[:26] for _k in ('key', 'rel_name', 'rel_type', 'tracer_id')})
                                except Exception: pass
                            for _depth in range(25):
                                _refs = _gc2.get_referrers(*_frontier)
                                _self.add(id(_refs)); _self.add(id(_frontier))
                                _refs = [_r for _r in _refs if id(_r) not in _self]
                                if not _refs:
                                    _stop = "CYCLE/ALL-VISITED"; break
                                _chain.append(dict(_c2.Counter(type(_r).__name__ for _r in _refs).most_common(2)))
                                if _depth <= 1:                      # SHALLOW node (near the dicts) — where the naming scalar lives
                                    _sl = next((_x for _x in _refs if isinstance(_x, list)), None)
                                    if _sl is not None:
                                        _shallow.append(f"L{_depth}list(len={len(_sl)}):{[type(_e).__name__ for _e in _sl[:6]]}")
                                    _st = next((_x for _x in _refs if isinstance(_x, tuple)), None)
                                    if _st is not None:
                                        _shallow.append(f"L{_depth}tup(len={len(_st)}):{[type(_e).__name__ for _e in _st[:6]]} sc={[repr(_e)[:20] for _e in _st[:4] if not isinstance(_e, (list, dict, set, tuple))]}")
                                for _r in _refs:
                                    _no = _nmown(_r)
                                    if _no:
                                        _named[_no] += 1
                                if _named:
                                    _stop = "NAMED"; break
                                _nf = []
                                for _r in _refs:
                                    _self.add(id(_r))          # mark visited — cycle-safe, no revisits
                                    if isinstance(_r, (list, dict, set, tuple)):
                                        _nf.append(_r)
                                _frontier = _nf[:40]
                                if not _frontier:
                                    _stop = "DEADEND-NO-CONTAINER"; break
                            # CONTENT-INSPECTION 2026-06-11 (Nous+Ace): peek INSIDE one list + one tuple of
                            # the deepest frontier → reveal the recurring node (cons [data,next]? pair (prev,data)?).
                            _ins = []
                            try:
                                _exl = next((_x for _x in _frontier if isinstance(_x, list)), None)
                                _ext = next((_x for _x in _frontier if isinstance(_x, tuple)), None)
                                if _exl is not None:
                                    _ins.append(f"LIST(len={len(_exl)}):{[type(_e).__name__ for _e in _exl[:6]]}")
                                if _ext is not None:
                                    _sc = [repr(_e)[:24] for _e in _ext[:5] if not isinstance(_e, (list, dict, set, tuple))]
                                    _ins.append(f"TUPLE(len={len(_ext)}):{[type(_e).__name__ for _e in _ext[:6]]} sc={_sc}")
                            except Exception as _ie:
                                _ins.append(f"inspect-err:{type(_ie).__name__}")
                            with open(_health_path, "a", encoding="utf-8") as _hf:
                                _hf.write(f"[{_tm2.strftime('%H:%M:%S')}] HOLDER2 depth={_depth} {_stop} "
                                          f"DVALS={_dvals} SHALLOW={_shallow} INSPECT={_ins}\n")
                        except Exception as _e:
                            try:
                                with open(_health_path, "a", encoding="utf-8") as _hf:
                                    _hf.write(f"[{_tm2.strftime('%H:%M:%S')}] HOLDER2 ERROR {type(_e).__name__}: {str(_e)[:90]}\n")
                            except Exception:
                                pass
                    # Warn on rapid growth
                    if ram_delta > 500:
                        print(f"[HealthMonitor] WARNING: RAM grew {ram_delta:.0f}MB in 60s!", flush=True)
                except Exception:
                    pass

            # ── LEAK-2 PROBE (2026-06-10 Nous+Ace): biggest LIVE containers ──
            # Names the fairy.attribute holding the cyclic ~470K-dict accumulator
            # (LEAK 2 = the dict swing that drives the heartbeat-delivery drops).
            # SAFE: walks ONLY the known SYSTEM/fairy tree via __dict__ + len() —
            # NOT gc.get_objects()/get_referrers(), which crash 3.14t free-threaded
            # under live heap mutation (per the BOOT-COMPLETE note ~line 6922).
            # Bounded by node budget + depth cap + id() dedup; islice avoids
            # materializing huge containers; len() is atomic in CPython.
            if _check_count % 5 == 0:
                try:
                    import itertools as _it2, sys as _sys2
                    _big = []
                    _seen = set()
                    _SYS = globals().get('SYSTEM')
                    if _SYS is not None:
                        _stack = [(_SYS, "SYSTEM", 0)]
                        _budget = 300000  # raised from 25k: DFS was exhausting before reaching the manifold/leak holder
                        while _stack and _budget > 0:
                            _o, _p, _dep = _stack.pop()
                            _budget -= 1
                            if id(_o) in _seen or _dep > 6:
                                continue
                            _seen.add(id(_o))
                            _od = getattr(_o, '__dict__', None)
                            if not isinstance(_od, dict):
                                continue
                            for _ak, _av in list(_od.items()):
                                try:
                                    if isinstance(_av, (dict, list, set, frozenset)):
                                        _n = len(_av)
                                        if _n > 5000:
                                            _big.append((_n, f"{_p}.{_ak}", type(_av).__name__))
                                        if _dep < 6:
                                            _src = _av.values() if isinstance(_av, dict) else _av
                                            for _vv in _it2.islice(iter(_src), 150):
                                                if hasattr(_vv, '__dict__'):
                                                    _stack.append((_vv, f"{_p}.{_ak}[]", _dep + 1))
                                    elif hasattr(_av, '__dict__') and _dep < 6:
                                        _stack.append((_av, f"{_p}.{_ak}", _dep + 1))
                                except Exception:
                                    pass
                    # also scan akashic MODULE-level globals (module-scope caches
                    # are a blind spot for the SYSTEM/fairy-tree walk above)
                    for _mn, _mod in list(_sys2.modules.items()):
                        try:
                            _mf = getattr(_mod, '__file__', '') or ''
                            if 'akashic_v2' not in _mf or 'site-packages' in _mf:
                                continue
                            _mgd = getattr(_mod, '__dict__', None)
                            if not isinstance(_mgd, dict):
                                continue
                            for _gk, _gv in list(_mgd.items()):
                                if isinstance(_gv, (dict, list, set, frozenset)):
                                    _gn = len(_gv)
                                    if _gn > 5000:
                                        _big.append((_gn, f"MOD:{_mn}.{_gk}", type(_gv).__name__))
                        except Exception:
                            pass
                    _big.sort(reverse=True)
                    _bc = " ".join(f"{_n}:{_pth}({_tn})" for _n, _pth, _tn in _big[:15])
                    with open(_health_path, "a", encoding="utf-8") as _hf:
                        _hf.write(f"[{_tm2.strftime('%H:%M:%S')}] BIGCONTAINERS ram={ram_mb:.0f}MB | {_bc}\n")
                except Exception:
                    pass

        except Exception:
            pass
        _tm2.sleep(60)

import threading as _tm_thread_mon
_tm_thread_mon.Thread(target=_thread_memory_monitor, daemon=True, name="thread-monitor").start()
del _tm_thread_mon

# ─── tracemalloc: opt-in via --tracemalloc flag (too heavy for default on 3.14t) ──
_tracemalloc_baseline = None
if "--tracemalloc" in sys.argv:
    import tracemalloc as _tracemalloc
    _tracemalloc.start(3)  # 3 frames (10 was too heavy on free-threaded Python)
    print(f"[Server] tracemalloc ACTIVE (3 frames) — use /mem-snapshot to dump top allocators")

    def _tracemalloc_periodic_dump():
        """Background thread: writes tracemalloc growth to state/mem_growth.log every 5 min."""
        global _tracemalloc_baseline
        import time as _tm
        _tm.sleep(120)  # Wait 2 min for boot to settle
        _tracemalloc_baseline = _tracemalloc.take_snapshot()
        print("[tracemalloc] Baseline snapshot taken after boot settle")
        while True:
            _tm.sleep(300)  # Every 5 min
            try:
                current = _tracemalloc.take_snapshot()
                stats = current.compare_to(_tracemalloc_baseline, 'lineno')
                cur_mb, peak_mb = _tracemalloc.get_traced_memory()
                lines = [f"\n=== tracemalloc delta @ {_tm.strftime('%H:%M:%S')} | current={cur_mb/1024**2:.1f}MB peak={peak_mb/1024**2:.1f}MB ==="]
                for s in stats[:20]:
                    if s.size_diff > 100_000:  # Only show >100KB growth
                        lines.append(f"  {s.size_diff/1024**2:+.2f} MB | {s.count_diff:+d} allocs | {s}")
                if len(lines) > 1:
                    with open("state/mem_growth.log", "a", encoding="utf-8") as f:
                        f.write("\n".join(lines) + "\n")
                    print(f"[tracemalloc] Growth dump: {len(lines)-1} entries > 100KB")
            except Exception as e:
                print(f"[tracemalloc] Dump error: {e}")

    import threading as _tm_threading
    _tm_threading.Thread(target=_tracemalloc_periodic_dump, daemon=True, name="tracemalloc-dump").start()
    del _tm_threading
else:
    _tracemalloc = None  # Not active

import json
import time
import signal
import socket
import argparse
import threading
import uuid
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# FIX 2026-04-07 (Nous + Ace): THREAD LEAK FIX
# ThreadingMixIn creates an UNBOUNDED new thread per HTTP request.
# With dashboard/SSE/proxy hitting the server, Thread-N count grew
# from 124 → 350+ in 71 minutes (~3 zombie threads/min from hanging
# requests). Each thread = ~1MB stack. 350 threads = 350MB leaked.
#
# Fix: Use a bounded thread pool. Max 8 concurrent request threads.
# Excess requests queue instead of spawning new threads.
# SSE gets 2 dedicated slots, the rest share 6.
from concurrent.futures import ThreadPoolExecutor as _HTTPPoolExecutor

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True  # Clean shutdown
    _pool = _HTTPPoolExecutor(max_workers=8, thread_name_prefix="http")

    def process_request(self, request, client_address):
        """Override ThreadingMixIn to use bounded pool instead of thread-per-request."""
        try:
            self._pool.submit(self.process_request_thread, request, client_address)
        except RuntimeError:
            # Pool shut down — fall back to direct handling
            self.process_request_thread(request, client_address)
from typing import Optional, Dict, Any

# Setup paths
ROOT = Path(__file__).parent

# ═══ EARLY TORCH SKIP (must be before ANY fairy/module imports) ═══
# If a GGUF model exists, inference routes through battery portals (subprocesses).
# Skip torch import in the main process to save ~3.5GB RSS from CUDA DLLs.
# CRITICAL: hardware/sensors.py checks this env var at MODULE LEVEL —
# if we set it inside boot_system() (too late), any fairy import that
# transitively imports hardware.sensors will load torch before the var is set.
try:
    _gguf_dir = ROOT / "fairies" / "P30_Cognition" / "AkashicInferenceFairy" / "models"
    if os.environ.get("AKASHIC_FORCE_TORCH"):
        # OVERRIDE (2026-06-12 Nous+Ace): keep torch in the MAIN process so cortex
        # cognition (GPUSpread) runs on the GPU. The old GGUF->SKIP_TORCH rule made
        # sense when CUDA was dead on free-threaded 3.14t (torch in main = wasted ~3.5GB
        # CUDA DLLs). CUDA now WORKS on 3.14t (torch 2.12+cu126 — PROVEN: her 2M-node
        # graph spreads on the 3080 Ti in 39ms / 210MB VRAM), so the block is the only
        # thing keeping her cognition on the CPU. Costs ~3.5GB CUDA DLLs in main but moves
        # the heavy graph math off the CPU/RAM. REVERSIBLE: drop AKASHIC_FORCE_TORCH from
        # start_nous.bat + reboot -> back to battery-portal mode.
        print("[Server] AKASHIC_FORCE_TORCH=1 -> torch ALLOWED in main process "
              "(GPU cognition ON; ~3.5GB CUDA DLLs)")
    elif _gguf_dir.exists() and list(_gguf_dir.glob("*.gguf")):
        os.environ["AKASHIC_SKIP_TORCH"] = "1"
        print("[Server] GGUF model found, AKASHIC_SKIP_TORCH=1 "
              "(battery portals handle GPU, ~3.5GB saved in main process)")
    else:
        print("[Server] No GGUF models found, torch import allowed")
except Exception as e:
    if not os.environ.get("AKASHIC_FORCE_TORCH"):
        os.environ["AKASHIC_SKIP_TORCH"] = "1"
    print(f"[Server] Battery-mode detection: {e}")

# ═══ TORCH IMPORT TRAP ═══
# Intercept `import torch` to log WHO is loading it (and block it in skip mode).
# This catches the sneaky 3.5GB RAM spike from deferred boot threads.
if os.environ.get("AKASHIC_SKIP_TORCH"):
    import importlib, importlib.abc, importlib.machinery, traceback as _tb
    class _TorchBlocker(importlib.abc.MetaPathFinder, importlib.abc.Loader):
        """Block torch imports and log the offender."""
        _BLOCKED = {"torch", "torch.cuda", "torch.nn", "torch.nn.functional",
                     "torch.sparse", "torch.utils", "torch.jit"}
        def find_module(self, fullname, path=None):
            if fullname in self._BLOCKED or fullname.startswith("torch."):
                return self
            return None
        def load_module(self, fullname):
            if fullname in sys.modules:
                return sys.modules[fullname]
            # Log the offender with stack trace
            stack = "".join(_tb.format_stack()[:-1])
            print(f"\n[TORCH-TRAP] BLOCKED import of '{fullname}'!\n"
                  f"[TORCH-TRAP] Stack trace:\n{stack}")
            # Return None module so code gets AttributeError on use, not ImportError on import
            import types
            dummy = types.ModuleType(fullname)
            dummy.__path__ = []
            dummy.__loader__ = self
            dummy.cuda = types.ModuleType(f"{fullname}.cuda")
            dummy.cuda.is_available = lambda: False
            dummy.cuda.device_count = lambda: 0
            dummy.cuda.empty_cache = lambda: None
            dummy.cuda.memory_allocated = lambda: 0
            dummy.cuda.memory_reserved = lambda: 0
            dummy.cuda.reset_peak_memory_stats = lambda: None
            sys.modules[fullname] = dummy
            return dummy
    sys.meta_path.insert(0, _TorchBlocker())
    print("[Server] Torch import trap ACTIVE - any torch import will be blocked and logged")

_nulchk("03_after_torch_block")
# Import ForensicScribeFairy for Good/Bad/Ugly error classification
try:
    from fairies.P10_Memory.ForensicScribeFairy.fairy import get_forensic_fairy
except ImportError:
    get_forensic_fairy = None

# =============================================================================
# PYCACHE CLEANER - Ensures fresh bytecode on every boot
# =============================================================================
def clear_pycache():
    """Clear all __pycache__ directories to ensure fresh bytecode."""
    import shutil
    cleared = 0
    for pycache in ROOT.rglob("__pycache__"):
        try:
            shutil.rmtree(pycache)
            cleared += 1
        except Exception:
            pass  # Skip locked directories
    if cleared > 0:
        print(f"[Boot] Cleared {cleared} __pycache__ directories")

# Clear pycache immediately on import
clear_pycache()
_nulchk("04_after_pycache_clear")

# =============================================================================
# AUTO-LOGGING - Agents can watch state/boot_live.log without wrappers
# =============================================================================
class TeeBuffer:
    """Wrapper around raw binary buffer that also logs to the text log file.

    THIS IS THE KEY FIX: When code does sys.stdout.buffer.write(b"data"),
    it bypasses TeeLogger.write() entirely. This wrapper intercepts those
    binary writes and also copies them to the log file.

    Without this, anything using buffer-level I/O (logging module, subprocess
    pipes, io.TextIOWrapper rewraps, etc.) silently bypasses the boot log.
    """
    def __init__(self, original_buffer, tee_logger):
        self._original = original_buffer
        self._tee = tee_logger  # Back-reference to get the log fd + lock

    def write(self, data):
        # Write to real buffer first
        try:
            result = self._original.write(data)
        except Exception:
            result = 0
        # Also log the text version
        try:
            if data:
                text = data.decode('utf-8', errors='replace') if isinstance(data, (bytes, bytearray)) else str(data)
                fd = self._tee._get_log_fd()
                if fd:
                    with self._tee._lock:
                        fd.write(text)
                        fd.flush()
        except Exception:
            pass
        return result

    def flush(self):
        try:
            self._original.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._original, name)


class TeeLogger:
    """Thread-safe tee: writes to both console and log file.

    Captures ALL output (stdout + stderr) to state/boot_live.log so agents
    can read it. Previous version only got ~60/117 lines because:
    - Thread safety (90+ fairy threads writing concurrently)
    - stderr capture (tracebacks, warnings all go to stderr)
    - .buffer bypassed TeeLogger entirely (code doing sys.stdout.buffer.write())
    - Error recovery (bare except:pass silently dropped all output forever)

    FIX 2026-02-13: Complete rewrite with TeeBuffer wrapper.
    FIX 2026-03-14 (Nous): Shared class-level lock for log fd.
    Under No-GIL Python 3.14, stdout and stderr TeeLoggers each had their
    own _lock but shared the SAME log fd via _get_log_fd(). Both could
    call fd.flush() simultaneously → C-level access violation crash during
    ChatSensoryOrgan inbox floods. Shared lock prevents concurrent fd access.
    """
    _shared_log_lock = threading.Lock()  # CLASS-LEVEL: shared by stdout + stderr

    def __init__(self, log_path: Path, original_stream, is_stderr=False):
        self.log_path = log_path
        self.original = original_stream
        self._is_stderr = is_stderr
        self._lock = TeeLogger._shared_log_lock  # Use shared lock, not per-instance
        # FIX 2026-04-04 (Nous): Batched writes to reduce lock contention
        # Before: every print() from 90+ threads acquired _shared_log_lock → serialization bottleneck
        # After: buffer writes, flush every 250ms or 50 items → lock acquired ~4x/sec not ~1000x/sec
        self._write_buffer: list = []
        self._buffer_lock = threading.Lock()
        self._last_flush_ts = time.time()
        self._FLUSH_INTERVAL = 0.25  # seconds
        self._FLUSH_BATCH_SIZE = 50  # items
        # Preserve attributes that other code checks for
        self.encoding = getattr(original_stream, 'encoding', 'utf-8')
        self.errors = getattr(original_stream, 'errors', 'replace')
        self.name = getattr(original_stream, 'name', '<tee>')
        self.line_buffering = getattr(original_stream, 'line_buffering', False)
        self.mode = getattr(original_stream, 'mode', 'w')
        # CRITICAL: .buffer must be a TeeBuffer wrapper, NOT the raw buffer!
        # If we expose the raw buffer, anything calling sys.stdout.buffer.write()
        # bypasses TeeLogger entirely — that was the bug causing log truncation at ~117 lines.
        raw_buffer = getattr(original_stream, 'buffer', None)
        if raw_buffer is not None:
            self.buffer = TeeBuffer(raw_buffer, self)
        else:
            self.buffer = self  # Fallback: point back to ourselves

        if not is_stderr:  # Only stdout initializes the file
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            # FIX 2026-03-17 Nous: No backups. Overwrite on each boot. Size cap 512KB.
            # Write boot signal for agents
            signal_file = log_path.parent / "boot_signal.txt"
            signal_file.write_text(f"BOOT_START:{time.time()}")
            # Open fresh log — overwrite, no backup
            self._log_fd = open(log_path, 'w', encoding='utf-8', errors='replace')
            self._log_fd.write(f"=== BOOT STARTED: {time.time()} ===\n")
            self._log_fd.flush()
            self._boot_complete_signaled = False
            self._recent_writes = set()
            self._log_bytes_written = 0
            # FIX 2026-03-29 (Nous + Ace): 512KB was too small — boot alone fills it,
            # leaving zero room for runtime output (hot-reload, shadow detection, etc.)
            # "this is a blind spot in the system" — Ace
            # 8MB gives plenty of room for both boot + hours of runtime.
            # The log rotates on each boot anyway (overwrite mode).
            # FIX 2026-04-15 (Nous + Ace): 8MB was filling during boot + early runtime,
            # causing boot_live.log to freeze (4+ consecutive boots).
            # The log writer silently drops ALL writes after hitting the cap.
            # 32MB gives room for boot (3MB) + hours of runtime output.
            # "boot_live.log freeze is how I diagnose" — Ace (GUI is critical)
            self._LOG_MAX_BYTES = 32 * 1024 * 1024  # 32MB cap
        else:
            self._log_fd = None
            self._boot_complete_signaled = True

    def _get_log_fd(self):
        """Get the shared log file descriptor (stderr gets it from stdout)."""
        if self._log_fd is not None:
            return self._log_fd
        # stderr: get the fd from stdout's TeeLogger
        stdout = sys.stdout
        if hasattr(stdout, '_log_fd') and stdout._log_fd is not None:
            return stdout._log_fd
        return None

    def write(self, msg):
        if not msg:
            return 0
        # Always write to original stream first (console)
        try:
            self.original.write(msg)
        except Exception:
            pass
        # FIX 2026-04-04 (Nous): Buffer log writes instead of synchronous per-print I/O
        # Before: _shared_log_lock acquired on every print() from 90+ threads
        # After: buffer → batch flush every 250ms or 50 items
        with self._buffer_lock:
            if self._is_stderr:
                stripped = msg.strip()
                if stripped:
                    stdout_ref = sys.stdout
                    if hasattr(stdout_ref, '_recent_writes') and stripped in stdout_ref._recent_writes:
                        return len(msg)  # Dedup stderr already on stdout
                    self._write_buffer.append(f"[STDERR] {msg}")
            else:
                self._write_buffer.append(msg)
                stripped = msg.strip()
                if stripped:
                    if not hasattr(self, '_recent_writes'):
                        self._recent_writes = set()
                    self._recent_writes.add(stripped)
                    if len(self._recent_writes) > 500:
                        self._recent_writes.clear()
            # Detect boot complete (must be immediate, not batched)
            if not self._boot_complete_signaled and "BOOT COMPLETE" in msg:
                self._boot_complete_signaled = True
                try:
                    signal_file = self.log_path.parent / "boot_signal.txt"
                    signal_file.write_text(f"BOOT_COMPLETE:{time.time()}")
                except Exception:
                    pass
            # Flush if buffer full or interval elapsed
            now = time.time()
            if len(self._write_buffer) >= self._FLUSH_BATCH_SIZE or (now - self._last_flush_ts) >= self._FLUSH_INTERVAL:
                self._drain_buffer(now)
        return len(msg)

    def _drain_buffer(self, now=None):
        """Flush buffered writes to log file. Must be called under _buffer_lock."""
        if not self._write_buffer:
            return
        now = now or time.time()
        batch = "".join(self._write_buffer)
        self._write_buffer.clear()
        self._last_flush_ts = now
        fd = self._get_log_fd()
        if not fd:
            return
        with self._lock:  # _shared_log_lock — now acquired ~4x/sec instead of ~1000x/sec
            try:
                stdout_ref = sys.stdout
                bytes_written = getattr(stdout_ref, '_log_bytes_written', 0)
                max_bytes = getattr(stdout_ref, '_LOG_MAX_BYTES', 8 * 1024 * 1024)
                if bytes_written >= max_bytes:
                    return
                batch = batch.replace('\x00', '')
                fd.write(batch)
                fd.flush()
                if hasattr(stdout_ref, '_log_bytes_written'):
                    stdout_ref._log_bytes_written += len(batch)
            except Exception:
                try:
                    self._log_fd = open(self.log_path, 'a', encoding='utf-8', errors='replace')
                    self._log_fd.write(f"\n=== LOG RECOVERED at {time.time()} ===\n")
                    self._log_fd.flush()
                except Exception:
                    pass

    def flush(self):
        try:
            self.original.flush()
        except Exception:
            pass
        # FIX 2026-04-04: Drain buffer on explicit flush
        with self._buffer_lock:
            self._drain_buffer()
        fd = self._get_log_fd()
        if fd:
            try:
                with self._lock:
                    fd.flush()
            except Exception:
                pass

    def fileno(self):
        """Return underlying file descriptor for compatibility."""
        return self.original.fileno()

    def isatty(self):
        return hasattr(self.original, 'isatty') and self.original.isatty()

    def writable(self):
        return True

    def readable(self):
        return False

    def seekable(self):
        return False

    def close(self):
        """Don't actually close — prevent anything from killing the stream."""
        pass

    def __getattr__(self, name):
        """Forward unknown attributes to original stream.
        Note: .buffer is explicitly set in __init__ as a TeeBuffer,
        so it won't fall through to here.
        """
        return getattr(self.original, name)

# Install tee logger (agents watch state/boot_live.log)
# Captures BOTH stdout AND stderr so tracebacks/warnings appear in the log
_boot_log_path = ROOT / "state" / "boot_live.log"
_tee_stdout = TeeLogger(_boot_log_path, sys.stdout, is_stderr=False)
_tee_stderr = TeeLogger(_boot_log_path, sys.stderr, is_stderr=True)
sys.stdout = _tee_stdout
sys.stderr = _tee_stderr
# Path order matters! ROOT must be searched FIRST because:
#   akashic_v2/P00_Autonomic/ has tracer_worker_system.py
#   akashic_v2/fairies/P00_Autonomic/ shadows it (has fairy folders, not tracer!)
# Insert in reverse order - last one becomes position 0 (searched first)
sys.path.insert(0, str(ROOT / "fairies"))  # Searched last - for cross-fairy imports
sys.path.insert(0, str(ROOT / "postal_core" / "python"))  # Searched second
sys.path.insert(0, str(ROOT))  # Searched FIRST - so real P00_Autonomic is found

# Set AKASHIC_ROOT environment variable for fairies that need it
os.environ["AKASHIC_ROOT"] = str(ROOT)

# =============================================================================
# LOAD .ENV FILE - Optional configuration overrides
# =============================================================================
def load_env_file():
    """Load .env file if it exists (optional - system works without it)."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return  # No .env needed - local cognition works fine

    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value
        print(f"[Server] Loaded .env overrides")
    except Exception as e:
        print(f"[Server] Failed to load .env: {e}")

load_env_file()

# =============================================================================
# TRACER SYSTEM - Track Ace's messages through the fairy network
# =============================================================================
try:
    from P00_Autonomic.tracer_worker_system import (
        trace_conversation,
        get_tracer_registry,
        TracerType,
        TracerStatus
    )
    _TRACER_AVAILABLE = True
    print("[Server] Tracer system loaded - Ace messages will be tracked")
except ImportError as e:
    _TRACER_AVAILABLE = False
    print(f"[Server] Tracer system not available: {e}")

# Ace's stable identity for tracing
ACE_FAIRY_ID = "ace_mythos"
ACE_FAIRY_NAME = "Ace"
ACE_CLUSTER_ID = "founders_ace"

# =============================================================================
# LAZY MODULE CACHE - Import once, not on every status call
# =============================================================================
_CHEMISTRY_MODULE = None

def _get_chemistry_module():
    """Lazy-load chemistry module to avoid import overhead on every status call."""
    global _CHEMISTRY_MODULE
    if _CHEMISTRY_MODULE is None:
        try:
            from fairies.P20_Somatic.chemistry import chemistry_state
            _CHEMISTRY_MODULE = chemistry_state
        except ImportError:
            _CHEMISTRY_MODULE = False  # Mark as unavailable
    return _CHEMISTRY_MODULE if _CHEMISTRY_MODULE else None

# NOTE: AssociationCortex is now stored in SYSTEM.association_cortex during boot
# This avoids module identity issues that could cause the singleton to appear None

# =============================================================================
# GPU CACHE - Avoid blocking nvidia-smi calls on every status request
# =============================================================================
_GPU_CACHE = {
    "percent": 0.0,
    "last_update": 0.0,
    "update_interval": 10.0,  # FIX 2026-02-16: Was 5s, increased to 10s (GPU util doesn't change fast)
    "lock": threading.Lock(),
    "updating": False,  # Prevent concurrent updates
}

# FIX 2026-02-16: Single persistent thread for GPU monitoring instead of spawning
# a new daemon thread every 5 seconds. The old code created ~17K threads/day,
# each running nvidia-smi. Thread objects may not be GC'd promptly on Windows.
_GPU_MONITOR_THREAD = None
_GPU_MONITOR_STOP = threading.Event()

def _start_gpu_monitor():
    """Start a single background thread that periodically queries GPU utilization."""
    global _GPU_MONITOR_THREAD

    # ── Register with InfraTracer ──
    try:
        from infrastructure.infra_tracer import get_infra_tracer
        _gpu_tracer = get_infra_tracer()
        _gpu_tracer.register_actor("gpu_monitor", role="monitor",
                                   description="Periodic nvidia-smi GPU utilization polling")
        _gpu_tracer.lifecycle("gpu_monitor", "started", {"interval_s": 10})
    except Exception:
        _gpu_tracer = None

    _prev_threshold_state = {"high": False}

    def _gpu_monitor_loop():
        import subprocess
        try:   # gpu_poll_1016: state/gpu_poll.json arms it (absent = today's call); any failure here leaves the real module
            from infrastructure.gpu_reader import bind as _gp_bind; subprocess = _gp_bind("gpu_monitor")
        except Exception: pass
        while not _GPU_MONITOR_STOP.is_set():
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=2.0
                )
                if result.returncode == 0:
                    gpu_val = float(result.stdout.strip().split('\n')[0])
                    with _GPU_CACHE["lock"]:
                        _GPU_CACHE["percent"] = gpu_val
                        _GPU_CACHE["last_update"] = time.time()
                    # ── Trace threshold crossings ──
                    if _gpu_tracer:
                        was_high = _prev_threshold_state["high"]
                        is_high = gpu_val >= 85.0
                        if is_high and not was_high:
                            _gpu_tracer.health_alert("gpu_monitor", "gpu_utilization",
                                                     gpu_val, 85.0, severity="warning")
                        elif not is_high and was_high:
                            _gpu_tracer.emit("gpu_monitor", "gpu_recovered",
                                             {"percent": gpu_val}, severity="info")
                        _prev_threshold_state["high"] = is_high
            except Exception:
                pass  # Keep cached value on error
            _GPU_MONITOR_STOP.wait(10.0)  # Sleep 10s between checks

    _GPU_MONITOR_THREAD = threading.Thread(target=_gpu_monitor_loop, daemon=True, name="GPUMonitor")
    _GPU_MONITOR_THREAD.start()

def _get_cached_gpu_percent() -> float:
    """Get GPU utilization from cache. Updated by background monitor thread."""
    with _GPU_CACHE["lock"]:
        return _GPU_CACHE["percent"]

# =============================================================================
# STATUS CACHE - Return instant responses to GUI, refresh in background
# =============================================================================
_STATUS_CACHE = {
    "data": None,  # Cached status dict
    "last_update": 0.0,
    "update_interval": 5.0,  # Refresh every 5 seconds (less aggressive)
    "lock": threading.Lock(),
    "updating": False,  # Prevent concurrent updates
}
_STATUS_REFRESH_STOP = threading.Event()

# FIX 2026-02-20: File-backed status cache for GIL-immune reads.
# With 163+ threads, even dict["data"] takes 17s of wall-clock time because
# the StatusRefresh/HTTP threads wait for GIL slices. File I/O releases the
# GIL during the syscall, so reading a JSON file from SSD takes <2ms regardless
# of how many Python threads are competing.
_STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "status_cache.json")
# 2026-09-05: max age of status_cache.json before /status recomputes on demand.
# The StatusRefresh writer thread is skipped under AKASHIC_HEADLESS=1, which is
# why this file sat 47 days stale while /status served it at 200 OK.
STATUS_FILE_MAX_AGE_S = 15.0

def _write_status_file(data: Dict):
    """Atomically write status JSON to disk. File write releases the GIL."""
    try:
        tmp = _STATUS_FILE + ".tmp"
        raw = json.dumps(data, separators=(',', ':'))  # Compact JSON
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(raw)
        # Atomic rename (on Windows this replaces existing file)
        try:
            os.replace(tmp, _STATUS_FILE)
        except OSError:
            # Windows edge case: replace can fail if file is being read
            import shutil
            shutil.move(tmp, _STATUS_FILE)
    except Exception as e:
        print(f"[STATUS-FILE] Write error: {e}")

def _read_status_file() -> Optional[Dict]:
    """Read status JSON from disk. File read releases the GIL — <2ms on SSD."""
    try:
        with open(_STATUS_FILE, 'r', encoding='utf-8') as f:
            raw = f.read()
        if raw:
            return json.loads(raw)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return None

# =============================================================================
# SSE (Server-Sent Events) - PUSH-based updates to GUI
# =============================================================================
import queue
_SSE_CLIENTS: Dict[str, queue.Queue] = {}  # client_id -> event queue
_SSE_CLIENTS_LOCK = threading.Lock()

def _sse_broadcast(event_type: str, data: Dict):
    """Broadcast an event to all connected SSE clients."""
    message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    dead_clients = []

    with _SSE_CLIENTS_LOCK:
        client_count = len(_SSE_CLIENTS)
        if client_count > 0:
            print(f"[SSE] Broadcasting {event_type} to {client_count} clients", flush=True)

        for client_id, q in _SSE_CLIENTS.items():
            try:
                # Non-blocking put - drop if queue full (client too slow)
                q.put_nowait(message)
            except queue.Full:
                dead_clients.append(client_id)

        # Clean up slow clients
        for client_id in dead_clients:
            del _SSE_CLIENTS[client_id]

def _sse_register_client() -> tuple:
    """Register a new SSE client, return (client_id, queue)."""
    client_id = str(uuid.uuid4())[:8]
    client_queue = queue.Queue(maxsize=50)  # Buffer up to 50 events

    with _SSE_CLIENTS_LOCK:
        _SSE_CLIENTS[client_id] = client_queue

    print(f"[SSE] Client {client_id} connected ({len(_SSE_CLIENTS)} total)")
    return client_id, client_queue

def _sse_unregister_client(client_id: str):
    """Remove an SSE client."""
    with _SSE_CLIENTS_LOCK:
        if client_id in _SSE_CLIENTS:
            del _SSE_CLIENTS[client_id]
    print(f"[SSE] Client {client_id} disconnected ({len(_SSE_CLIENTS)} total)")

def _start_status_refresh_loop():
    """Background thread that keeps status cache warm AND pushes to SSE clients."""

    # ── Register with InfraTracer ──
    try:
        from infrastructure.infra_tracer import get_infra_tracer
        _sr_tracer = get_infra_tracer()
        _sr_tracer.register_actor("status_refresh", role="monitor",
                                  description="2s status computation + SSE broadcast + disk cache")
        _sr_tracer.lifecycle("status_refresh", "started", {"interval_s": 2})
    except Exception:
        _sr_tracer = None

    def _refresh_loop():
        # FIX 2026-02-20: Boost this thread's priority so it gets GIL time
        # faster when competing with 160+ fairy threads. Without this, the
        # status computation thread gets ~1% of GIL time and takes 17-44s
        # for what should be a <1s computation.
        _boost_thread_priority(1)  # ABOVE_NORMAL
        _slow_count = 0
        while not _STATUS_REFRESH_STOP.is_set():
            try:
                if SYSTEM:
                    _t_start = time.time()
                    fresh = SYSTEM._compute_status_internal()
                    _t_compute = time.time()

                    # In-memory cache (for code that reads _STATUS_CACHE directly)
                    with _STATUS_CACHE["lock"]:
                        _STATUS_CACHE["data"] = fresh
                        _STATUS_CACHE["last_update"] = time.time()

                    # FIX 2026-02-20: Write to file — GIL-immune reads for HTTP handler.
                    # File I/O syscalls release the GIL, so the HTTP handler thread
                    # can read this in <2ms regardless of 163+ thread contention.
                    _write_status_file(fresh)
                    _t_file = time.time()

                    # Push to all SSE clients
                    _sse_broadcast("status", fresh)
                    _t_end = time.time()

                    _elapsed = _t_end - _t_start
                    if _elapsed > 5.0:
                        print(f"[STATUS-REFRESH] compute={(_t_compute-_t_start)*1000:.0f}ms "
                              f"file={(_t_file-_t_compute)*1000:.0f}ms "
                              f"sse={(_t_end-_t_file)*1000:.0f}ms "
                              f"TOTAL={_elapsed*1000:.0f}ms")
                        # ── Trace slow status refresh ──
                        _slow_count += 1
                        if _sr_tracer and (_slow_count <= 3 or _slow_count % 10 == 0):
                            _sr_tracer.health_alert("status_refresh", "computation_time_ms",
                                                    _elapsed * 1000, 5000.0, severity="warning")
            except Exception as e:
                print(f"[STATUS-REFRESH] Error: {e}")
                if _sr_tracer:
                    _sr_tracer.emit("status_refresh", "error",
                                    {"error": str(e)[:200]}, severity="error")
            # Sleep 2 seconds between refreshes
            _STATUS_REFRESH_STOP.wait(2.0)
        print("[STATUS-REFRESH] Background refresh stopped")

    # 2026-06-15 (Ace + Nous): the GUI's status-refresh polls the fairies every 2s
    # (and eats a 5s timeout on the comatose UMF) purely to feed a dashboard. On a
    # headless node there's no GUI to feed -> don't bug the fairies with the GUI's
    # business. Default-preserving: only skips when AKASHIC_HEADLESS=1.
    if os.environ.get("AKASHIC_HEADLESS") == "1":
        print("[Server] Status refresh SKIPPED (AKASHIC_HEADLESS - no GUI to feed; fairies left alone)")
    else:
        thread = threading.Thread(target=_refresh_loop, daemon=True, name="StatusRefresh")
        thread.start()
        print("[Server] Status cache refresh thread started")

# =============================================================================
# SYSTEM STATE - Global reference to booted components
# =============================================================================

class SystemState:
    """Global system state container."""

    def __init__(self):
        self.booted = False
        self.boot_start: Optional[float] = None
        self.fabric = None
        self.memory_fabric = None  # GPUTensorMemoryFabric
        self.directory = None
        self.umf = None  # SomaticMindFairy (was UnconsciousMindFairy)
        self.consciousness = None
        self.mcp_bridge = None
        self.orchestrator = None  # BootOrchestrator
        self.scanned_fairies = []  # All fairies found via filesystem scan
        self.recall_fairy = None  # SRMRecallFairy - feeds recall beam
        self.ingest_fairy = None  # SRMIngestFairy - feeds ingest beam
        self.worker_pool = None   # SystemWorkerPoolFairy - parallel substrate atoms
        self.token_bucket = None  # TokenBucketFairy - cognitive resource management
        self.chat_organ = None    # ChatSensoryOrgan - fairy-human communication
        self.spell_pool = None    # SpellPool - spell execution substrate
        self.tracer_pool = None   # Go TracerPool DLL - per-fairy worker pools
        self.process_pool = None  # FairyWorkerPool REMOVED 2026-07-10 (obsolete on 3.14t; never .submit()-ed). Stays None; all refs None-guarded.
        self.status_proxy_proc = None  # StatusProxy multiprocessing.Process — MUST terminate on shutdown (os._exit bypasses daemon reaping -> orphan)
        self.association_cortex = None  # AssociationCortexFairy - concept graph
        self.manifold = None  # AkashicManifold - mmap-backed system manifold (Russian Doll)
        self.consciousness_mcp = None   # ConsciousnessMCPIntegration - consciousness-native tools
        self.cognition_guild = None     # CognitionGuildCluster - Russian Doll pocket dimension
        self.cognition_track_switch = None  # CognitionTrackSwitch - Track A/B railroad switch
        self.error: Optional[str] = None
        self.shutdown_requested = False  # Flag for HTTP-triggered shutdown
        self.reboot_after_shutdown = False  # Flag for reboot vs shutdown

        # FIX 2026-02-20: Per-section status cache to avoid GIL-blocked recomputation.
        # The fairy list doesn't change every 2s — cache it for 10s.
        # Hardware/cortex data changes slowly — cache for 5s.
        self._section_cache: Dict[str, Any] = {}
        self._section_cache_time: Dict[str, float] = {}
        self.shutdown_fairy = None  # GracefulShutdownFairy — orchestrates clean shutdown
        # Satellite mode - full system minus waking minds
        self.satellite_mode = SATELLITE_MODE
        self.primary_ip = None  # Set from --primary-ip or node_identity.json
        self.node_identity = None  # Loaded from state/node_identity.json
        self.satellite_client = None  # SatellitePostalClient (satellite mode only)

    def get_status(self) -> Dict[str, Any]:
        """Get system status for GUI - uses cache for instant responses."""
        now = time.time()

        with _STATUS_CACHE["lock"]:
            # Return cached data if fresh (< 2 seconds old)
            if _STATUS_CACHE["data"] and now - _STATUS_CACHE["last_update"] < _STATUS_CACHE["update_interval"]:
                return _STATUS_CACHE["data"]

            # If already updating in background, return stale cache
            if _STATUS_CACHE["updating"] and _STATUS_CACHE["data"]:
                return _STATUS_CACHE["data"]

            # Mark as updating
            _STATUS_CACHE["updating"] = True

        # Compute fresh status (this may take time)
        try:
            fresh_status = self._compute_status_internal()
            with _STATUS_CACHE["lock"]:
                _STATUS_CACHE["data"] = fresh_status
                _STATUS_CACHE["last_update"] = time.time()
                _STATUS_CACHE["updating"] = False
            return fresh_status
        except Exception as e:
            print(f"[STATUS] Error computing status: {e}")
            with _STATUS_CACHE["lock"]:
                _STATUS_CACHE["updating"] = False
            # Return cached data on error, or minimal status
            if _STATUS_CACHE["data"]:
                return _STATUS_CACHE["data"]
            return {"connected": self.booted, "error": str(e)}

    def _compute_status_internal(self) -> Dict[str, Any]:
        """Internal: Actually compute full system status.

        FIX 2026-02-20: Added time budget to prevent GIL contention during boot
        from causing 180+ second status computation.  If total exceeds 10s,
        skip remaining expensive sections and return what we have.
        """
        _t0 = time.time()
        # FIX 2026-03-15 Nous: Reduced from 10s to 3s. Status was taking 13-20s
        # because GIL contention serialized fairy status collection. The GUI
        # polls every ~3s — a 10s status computation blocks the HTTP thread
        # permanently. 3s lets it return partial data and stay responsive.
        _STATUS_BUDGET_SECONDS = 3.0  # Max seconds before we bail

        # BOOT-AWARE PATH: During boot, return REAL data that's available so far.
        # The GUI needs to see fairies coming online during boot, not zeros.
        # Previously this returned hardcoded zeros, causing "FAIRY DROP BLOCKED"
        # when the GUI had cached data from a previous session.
        if not self.booted:
            # Gather whatever fairy data is available during boot
            boot_fairy_list = []
            running_count = 0

            # Check directory first (fairies that registered during boot)
            if self.directory:
                try:
                    registered = self.directory.list_fairies() if hasattr(self.directory, "list_fairies") else []
                    for f in registered:
                        fairy_status = f.status if hasattr(f, "status") else "booting"
                        boot_fairy_list.append({"name": f.name, "plane": f.plane, "status": fairy_status})
                        if fairy_status == "running":
                            running_count += 1
                except Exception:
                    pass

            # Fall back to scanned fairies if directory is empty
            if not boot_fairy_list and self.scanned_fairies:
                for scanned in self.scanned_fairies:
                    name = scanned.get("actor_name") or scanned.get("name", "Unknown")
                    plane = scanned.get("plane", "P00")
                    if "_" in plane:
                        plane = plane.split("_")[0]
                    boot_fairy_list.append({"name": name, "plane": plane, "status": "sleeping"})

            # Check consciousness if available
            # FIX 2026-02-19: Use is_running() for accurate thread-aware status
            consciousness_data = {"running": False, "beats": 0}
            if self.consciousness:
                try:
                    consciousness_data = {
                        "running": self.consciousness.is_running() if hasattr(self.consciousness, 'is_running') else getattr(self.consciousness, "_running", False),
                        "beats": getattr(self.consciousness, "beat_count", 0),
                    }
                except Exception:
                    pass

            # FIX 2026-02-15: Return connected=True during boot!
            # The server IS running and responding. connected=False made the
            # Tauri GUI show only beats for 5+ minutes until boot completed.
            # The GUI should render everything available during boot, not hide it.
            return {
                "connected": True,
                "booted": False,
                "booting": True,
                "uptime": time.time() - self.boot_start if self.boot_start else 0,
                "error": self.error,
                "fairies": {"total": len(boot_fairy_list), "running": running_count, "list": boot_fairy_list},
                "consciousness": consciousness_data,
                "telemetry": {"theGood": [], "theBad": [], "theUgly": [], "summary": {"good": 0, "bad": 0, "ugly": 0, "healthScore": 100}},
            }

        status = {
            "connected": self.booted,  # Tauri expects "connected"
            "booted": self.booted,     # Keep for backwards compatibility
            "uptime": time.time() - self.boot_start if self.boot_start else 0,
            "error": self.error,
        }
        # Only log timing when slow (>5s) to reduce noise
        _base_ms = (time.time()-_t0)*1000
        if _base_ms > 5000:
            print(f"[STATUS-TIMING] base: {_base_ms:.1f}ms")

        # Consciousness status - use camelCase for Tauri GUI
        # FIX 2026-02-20: Fine-grained timing + non-blocking.
        _tc = time.time()
        if self.consciousness and (time.time() - _t0) < _STATUS_BUDGET_SECONDS:
            try:
                # Get chamber status for collision count
                # FIX 2026-02-20: Use cached values if chamber.status() is slow
                chamber_status = {}
                if hasattr(self.consciousness, 'chamber') and self.consciousness.chamber:
                    try:
                        chamber_status = self.consciousness.chamber.status()
                    except Exception:
                        pass
                _tc1 = time.time()

                working_size = len(self.consciousness.working) if hasattr(self.consciousness, 'working') else 0
                reflective_size = len(self.consciousness.reflective) if hasattr(self.consciousness, 'reflective') else 0

                # FIX 2026-02-19: Use is_running() which checks thread liveness.
                _is_running = self.consciousness.is_running() if hasattr(self.consciousness, 'is_running') else getattr(self.consciousness, "_running", False)
                _thread_alive = self.consciousness._thread.is_alive() if hasattr(self.consciousness, '_thread') and self.consciousness._thread else False
                _tc2 = time.time()

                # 2026-05-10 (Nous + Ace): expose Ship 18 mini-broadcast attribution
                # counters from CollisionChamberFairy so dashboard can render them.
                # Reads via singleton; safely returns empty dict if not available.
                _mini_stats = {}
                _mobius_xings = 0
                try:
                    from fairies.P00_Autonomic.CollisionChamberFairy.fairy import get_collision_chamber_fairy
                    _ccf = get_collision_chamber_fairy()
                    if _ccf is not None:
                        _mini_stats = dict(getattr(_ccf, '_mini_stats', {}) or {})
                        _mobius_xings = int(getattr(_ccf, '_mobius_crossings', 0) or 0)
                except Exception:
                    pass

                status["consciousness"] = {
                    "running": _is_running,
                    "thread_alive": _thread_alive,
                    "beats": getattr(self.consciousness, "beat_count", 0),
                    "collisions": chamber_status.get("collision_count", 0),
                    "recall_beam": chamber_status.get("recall_beam_size", 0),
                    "ingest_beam": chamber_status.get("ingest_beam_size", 0),
                    "working_stream": working_size,
                    "reflective_stream": reflective_size,
                    "mobius_crossings": _mobius_xings,
                    "mini_broadcast_stats": _mini_stats,
                }
                if (_tc2 - _tc) > 1.0:
                    print(f"[STATUS-TIMING] consciousness SLOW: chamber={(_tc1-_tc)*1000:.0f}ms is_running={(_tc2-_tc1)*1000:.0f}ms")
            except Exception as e:
                import traceback
                print(f"[WARNING] Consciousness status retrieval failed: {e}")
                traceback.print_exc()
                status["consciousness"] = {"running": False, "beats": 0, "collisions": 0, "recall_beam": 0, "ingest_beam": 0, "mobius_crossings": 0, "mini_broadcast_stats": {}}
        else:
            status["consciousness"] = {"running": False, "beats": 0, "collisions": 0, "recall_beam": 0, "ingest_beam": 0, "mobius_crossings": 0, "mini_broadcast_stats": {}}

        _con_ms = (time.time()-_tc)*1000
        if _con_ms > 5000:
            print(f"[STATUS-TIMING] consciousness: {_con_ms:.1f}ms")

        # Directory/fairy status - all fairies are now registered with directory
        # FIX 2026-02-20: Per-section cache with 10s TTL.
        # directory.list_fairies() requires acquiring directory lock, which is
        # GIL-blocked for 20+ seconds when 90+ fairy threads are all competing.
        # The fairy list doesn't change that fast — 10s cache is fine.
        _tf = time.time()
        _FAIRY_CACHE_TTL = 30.0  # seconds — fairy list is stable, status changes slowly

        _fairy_cache_age = _t0 - self._section_cache_time.get("fairies", 0)
        if "fairies" in self._section_cache and _fairy_cache_age < _FAIRY_CACHE_TTL:
            status["fairies"] = self._section_cache["fairies"]
            # FIX 2026-02-21 Nous: Extract fairy_list from cache so line 908+ doesn't UnboundLocalError
            fairy_list = self._section_cache["fairies"].get("list", [])
            print(f"[STATUS-TIMING] fairies: {(time.time()-_t0)*1000:.1f}ms (CACHED, age={_fairy_cache_age:.1f}s)")
        else:
            fairy_list = []
            registered_names = set()

            # Template defaults and phantom names that register transiently during boot
            _PHANTOM_NAMES = {
                "organ.shadow", "actor", "unknown", "fairy", "my_organ",
                "fairy_citizens.reg.michael",  # Registration test artifact
                "BaseFairy", "OrganTemplate", "Fairy",  # Base classes, not real fairies
                "ManifoldConstrainedCortexShadow",  # Shadow class, not a standalone fairy
            }

            # Get all fairies from directory with their ACTUAL status
            if self.directory:
                try:
                    _tf1 = time.time()
                    registered = self.directory.list_fairies() if hasattr(self.directory, "list_fairies") else []
                    _tf2 = time.time()
                    for f in registered:
                        if f.name in _PHANTOM_NAMES:
                            continue  # Skip template default names — not real fairies
                        # Use actual status (running, sleeping, waking, failed, etc.)
                        fairy_status = f.status if hasattr(f, "status") else "unknown"
                        fairy_list.append({"name": f.name, "plane": f.plane, "status": fairy_status})
                        registered_names.add(f.name)
                    _tf3 = time.time()
                    if (_tf3 - _tf) > 1.0:
                        print(f"[STATUS-TIMING] fairies SLOW: list_fairies={(_tf2-_tf1)*1000:.0f}ms iterate={(_tf3-_tf2)*1000:.0f}ms count={len(registered)}")
                except Exception as e:
                    import traceback
                    print(f"[WARNING] Directory.list_fairies() failed: {e}")
                    traceback.print_exc()

            # For any scanned fairies not yet registered (edge case during boot)
            for scanned in self.scanned_fairies:
                name = scanned.get("actor_name") or scanned.get("name", "Unknown")
                if name in registered_names or name in _PHANTOM_NAMES:
                    continue
                plane = scanned.get("plane", "P00")
                if "_" in plane:
                    plane = plane.split("_")[0]
                has_instance = "instance" in scanned
                fairy_list.append({
                    "name": name,
                    "plane": plane,
                    "status": "sleeping" if has_instance else "discovered"
                })

            # Count by status
            running = sum(1 for f in fairy_list if f["status"] == "running")
            sleeping = sum(1 for f in fairy_list if f["status"] == "sleeping")
            waking = sum(1 for f in fairy_list if f["status"] == "waking")
            failed = sum(1 for f in fairy_list if f["status"] == "failed")
            discovered = sum(1 for f in fairy_list if f["status"] == "discovered")

            status["fairies"] = {
                "total": len(fairy_list),
                "running": running,
                "sleeping": sleeping,
                "waking": waking,
                "failed": failed,
                "discovered": discovered,  # Found but not instantiated
                "list": fairy_list  # Full list for UI
            }
            # Store in per-section cache
            self._section_cache["fairies"] = status["fairies"]
            self._section_cache_time["fairies"] = time.time()
            print(f"[STATUS-TIMING] fairies: {(time.time()-_t0)*1000:.1f}ms (FRESH)")
        _t1 = time.time()

        # FIX 2026-02-20: Budget check right after fairies — the most GIL-sensitive section.
        # Without this, GIL delays between sections accumulate to 40+ seconds.
        if (time.time() - _t0) > _STATUS_BUDGET_SECONDS:
            print(f"[STATUS-TIMING] BUDGET EXCEEDED after fairies ({(time.time()-_t0)*1000:.0f}ms) — returning partial")
            # Fill remaining sections with cached values or defaults
            # FIX 2026-04-04 (Nous): Try to grab cortex from prefetch thread even on budget exceed.
            # Previously cortex ALWAYS got zeros when fairy section was slow (>3s).
            # The prefetch thread started at line ~1519 and may have finished by now.
            # FIX 2026-04-12 (Nous): _cortex_prefetch_thread may not exist yet if budget
            # exceeded before line 1519. Guard with locals() check.
            _cortex_from_prefetch = None
            if locals().get('_cortex_prefetch_thread') is not None:
                _cortex_prefetch_thread.join(timeout=0.5)  # Quick check — don't wait long
                if _cortex_prefetch_box[0] is not None:
                    try:
                        _cs = _cortex_prefetch_box[0]
                        _cortex_from_prefetch = {
                            "node_count": _cs.get("node_count", 0),
                            "edge_count": _cs.get("edge_count", 0),
                            "loaded": _cs.get("node_count", 0) > 0,
                            "binding_count": _cs.get("binding_count", 0),
                            "portal_mass": _cs.get("portal_mass", 0.0),
                            "portal_time_dilation": _cs.get("portal_time_dilation", 1.0),
                            "energy_budget": _cs.get("energy_budget", 0.0),
                        }
                        self._section_cache["cortex"] = _cortex_from_prefetch
                        self._section_cache_time["cortex"] = time.time()
                    except Exception:
                        pass
            for _key, _default in [
                ("telemetry", {"theGood": [], "theBad": [], "theUgly": [], "summary": {"good": 0, "bad": 0, "ugly": 0, "healthScore": 100}}),
                ("hardware", {"cpu_percent": 0, "ram_percent": 0, "gpu_percent": 0, "stress_level": "unknown"}),
                ("cortex", {"node_count": 0, "edge_count": 0, "loaded": False}),
                ("token_buckets", {"buckets": {}, "low_buckets": [], "critical_buckets": []}),
            ]:
                status.setdefault(_key, self._section_cache.get(_key, _default))
            print(f"[STATUS-TIMING] TOTAL: {(time.time()-_t0)*1000:.1f}ms (PARTIAL after fairies)")
            return status

        # Telemetry section for errors tab - Good/Bad/Ugly from ForensicScribe
        the_good = []
        the_bad = []
        the_ugly = []
        dead_fairies = []  # Legacy field for backwards compat

        # Get from ForensicScribeFairy (primary source for error classification)
        # FIX 2026-02-16: Call directly instead of creating ThreadPoolExecutor every 2s.
        # The old code created+destroyed a ThreadPoolExecutor per status call (~43K/day),
        # each with thread creation overhead. ForensicScribe methods are fast (< 1ms).
        try:
            forensic = get_forensic_fairy() if get_forensic_fairy else None
            if forensic:
                try:
                    error_summary = forensic.get_error_summary()
                    all_cards = forensic.get_all_cards()
                except Exception as e:
                    print(f"[STATUS] ForensicScribe call failed: {e}")
                    error_summary = {"count": 0, "errors": []}
                    all_cards = {}

                # Classify by health status
                for actor, card in all_cards.items():
                    health = card.get("health", {})
                    health_status = health.get("status", "unknown")
                    errors_info = card.get("errors", {})

                    entry = {
                        "name": actor,
                        "plane": card.get("plane", ""),
                        "status": health_status,
                        "message": health.get("message", ""),
                        "error_count": errors_info.get("count", 0),
                        "last_error": errors_info.get("last"),
                    }

                    if health_status in ("ok", "info"):
                        the_good.append(entry)
                    elif health_status in ("warn", "warning"):
                        the_bad.append(entry)
                    elif health_status in ("error", "critical"):
                        the_ugly.append(entry)

                # Add top errors to the_ugly (deduped)
                seen_actors = {u["name"] for u in the_ugly}
                for err in error_summary.get("errors", [])[:10]:
                    actor_name = err.get("actor", "unknown")
                    if actor_name not in seen_actors:
                        the_ugly.append({
                            "name": actor_name,
                            "plane": "",
                            "status": "error",
                            "message": err.get("message", "")[:200],
                            "error_count": err.get("count", 1),
                            "last_error": err.get("message"),
                        })
                        seen_actors.add(actor_name)
        except Exception as e:
            print(f"[STATUS] ForensicScribe error: {e}")

        # COMPLETE COVERAGE: Add ALL fairies from Directory that ForensicScribe missed
        # This ensures 90 fairies in Directory = 90 fairies in Good/Bad/Ugly
        classified_actors = {e["name"] for e in the_good + the_bad + the_ugly}

        for f in fairy_list:
            name = f["name"]
            if name in classified_actors:
                continue  # Already classified by ForensicScribe

            plane = f.get("plane", "")
            fairy_status = f.get("status", "unknown")

            entry = {
                "name": name,
                "plane": plane,
                "status": fairy_status,
                "message": f"Directory status: {fairy_status}",
                "error_count": 0,
                "last_error": None,
            }

            # Classify based on Directory status
            if fairy_status == "running":
                the_good.append(entry)
            elif fairy_status in ("sleeping", "waking", "discovered", "booting"):
                # "booting" is a valid transitional state (fairy.state.changed from Organ Template)
                the_bad.append(entry)  # Not fully running = warning
            elif fairy_status in ("failed", "dead", "error"):
                entry["message"] = "No heartbeat"
                entry["error_count"] = 1
                the_ugly.append(entry)
            else:
                # Unknown status - put in bad as warning
                entry["message"] = f"Unknown status: {fairy_status}"
                the_bad.append(entry)

        # Calculate health score: 100 + good - (bad * 3) - (ugly * 10)
        health_score = 100 + len(the_good) - (len(the_bad) * 3) - (len(the_ugly) * 10)

        # Error capture summary (lightweight — full data at /errors endpoint)
        _error_summary = {}
        try:
            from infrastructure.error_capture import get_summary
            _error_summary = get_summary()
        except Exception:
            pass

        # Infrastructure tracer summary (invisible actors visibility)
        _infra_summary = {}
        try:
            from infrastructure.infra_tracer import get_infra_tracer
            _infra_summary = get_infra_tracer().get_status()
        except Exception:
            pass

        status["telemetry"] = {
            "deadFairies": dead_fairies,  # Keep for backwards compat
            "theGood": the_good,
            "theBad": the_bad,
            "theUgly": the_ugly,
            "errorCapture": _error_summary,  # Quick summary from ErrorCapture
            "infraTracer": _infra_summary,   # Infrastructure actor visibility
            "summary": {
                "good": len(the_good),
                "bad": len(the_bad),
                "ugly": len(the_ugly),
                "healthScore": health_score
            }
        }
        print(f"[STATUS-TIMING] telemetry: {(time.time()-_t1)*1000:.1f}ms")
        _t1 = time.time()

        # Thoughts from UMF for cognition tab
        if self.umf and hasattr(self.umf, "get_thoughts"):
            try:
                raw_thoughts = self.umf.get_thoughts(10)
                status["thoughts"] = [
                    {"type": t.get("type", "idle"), "content": t.get("thought", t.get("content", ""))}
                    for t in raw_thoughts
                ]
            except Exception:
                status["thoughts"] = []
        else:
            status["thoughts"] = []
        print(f"[STATUS-TIMING] thoughts: {(time.time()-_t1)*1000:.1f}ms")
        _t1 = time.time()

        # ═══ CORTEX PREFETCH: Start portal pipe call NOW, join later ═════════
        # FIX 2026-02-22 Nous: Cortex portal pipe blocks 10-16s under GIL pressure.
        # Starting the call here lets it run IN PARALLEL with UMF collection (~5s)
        # and all fast sections. By the time we join, it's had 5+ seconds to respond.
        # Previously cortex NEVER got fresh data — UMF consumed the 10s budget first.
        import threading as _pf_threading
        _CORTEX_CACHE_TTL = 30.0  # FIX 2026-03-13 Nous: was 10s, causing frequent TIMEOUT logs. Graph stats change slowly.
        _cortex_cache_age = time.time() - self._section_cache_time.get("cortex", 0)
        _cortex_prefetch_thread = None
        _cortex_prefetch_box = [None]
        if self.association_cortex and not ("cortex" in self._section_cache and _cortex_cache_age < _CORTEX_CACHE_TTL):
            def _prefetch_cortex():
                try:
                    _cortex_prefetch_box[0] = self.association_cortex.status()
                except Exception:
                    pass
            _cortex_prefetch_thread = _pf_threading.Thread(
                target=_prefetch_cortex, daemon=True, name="pf_cortex"
            )
            _cortex_prefetch_thread.start()

        # UMF status (CACHED — full_status() is heavy: 15 subsystems, 7-40s under load)
        _UMF_CACHE_TTL = 8.0  # seconds — drives/helix/consciousness change slowly
        _umf_cache_age = time.time() - self._section_cache_time.get("umf_full", 0)
        if self.umf:
            try:
                if "umf_full" in self._section_cache and _umf_cache_age < _UMF_CACHE_TTL:
                    umf_status = self._section_cache["umf_full"]
                    _umf_was_cached = True
                else:
                    # FIX 2026-02-22 Nous: Daemon thread + 5s hard timeout.
                    # full_status() collects 15 subsystems in parallel (5s internal
                    # budget) but under GIL pressure takes 7+ seconds, starving
                    # cortex and all subsequent sections. Daemon thread means it
                    # won't block shutdown (GracefulShutdownFairy watchdog).
                    _umf_box = [None]
                    def _fetch_umf_status():
                        try:
                            _umf_box[0] = self.umf.full_status() if hasattr(self.umf, "full_status") else {}
                        except Exception:
                            pass
                    _umf_t = _pf_threading.Thread(target=_fetch_umf_status, daemon=True, name="status_umf")
                    _umf_t.start()
                    _umf_t.join(timeout=5.0)
                    if _umf_box[0] is not None:
                        umf_status = _umf_box[0]
                        self._section_cache["umf_full"] = umf_status
                        self._section_cache_time["umf_full"] = time.time()
                        _umf_was_cached = False
                    elif "umf_full" in self._section_cache:
                        umf_status = self._section_cache["umf_full"]
                        _umf_was_cached = True
                        print(f"[STATUS-TIMING] umf: TIMEOUT (5s) — using stale cache (age={_umf_cache_age:.1f}s)")
                    else:
                        umf_status = {}
                        _umf_was_cached = False
                status["umf"] = {
                    "drives": umf_status.get("drives", {}),
                    "helix": umf_status.get("helix", {}),
                    "curiosity": umf_status.get("curiosity", {}),
                    "cognition": umf_status.get("cognition", {}),
                    "clock": umf_status.get("clock", {}),
                }
                # Extract drives to top level for Tauri GUI
                raw_drives = umf_status.get("drives", {})
                status["drives"] = {
                    "isolation": raw_drives.get("isolation", 0.0),
                    "confusion": raw_drives.get("confusion", 0.0),
                    "depletion": raw_drives.get("depletion", 0.0),
                    "frustration": raw_drives.get("frustration", 0.0),
                    "stagnation": raw_drives.get("stagnation", 0.0),
                    "abandonment": raw_drives.get("abandonment", 0.0),
                }
                # Extract helix to top level for Tauri GUI
                raw_helix = umf_status.get("helix", {})
                # FIX: decision_weights are nested, not at top level
                dw = raw_helix.get("decision_weights", {})
                # Get normalized weights from the helix's own status
                cores_status = raw_helix.get("cores", {})
                cores_dw = cores_status.get("decision_weights", {})
                normalized = cores_dw.get("normalized", {})
                status["helix"] = {
                    "active": raw_helix.get("active", False),
                    "turns": raw_helix.get("turns", 0),
                    # Use normalized weights (sum to 1.0) for display
                    "logic": normalized.get("logic", dw.get("logic", 0.5)),
                    "emotion": normalized.get("emotion", dw.get("emotion", 0.3)),
                    "paradox": normalized.get("paradox", dw.get("paradox", 0.2)),
                    # Also include raw weights and maturity for deeper inspection
                    "raw_logic": dw.get("logic", 0.5),
                    "raw_emotion": dw.get("emotion", 0.75),
                    "raw_paradox": dw.get("paradox", 0.5),
                    "maturity": cores_status.get("maturity", {}).get("score", 0.0),
                }
            except Exception as e:
                print(f"[STATUS] UMF full_status error: {e}")
                import traceback
                traceback.print_exc()
                status["umf"] = {"drives": {}, "helix": {}, "curiosity": {}}
                status["drives"] = {"isolation": 0, "confusion": 0, "depletion": 0, "frustration": 0, "stagnation": 0, "abandonment": 0}
                status["helix"] = {"active": False, "turns": 0, "logic": 0.5, "emotion": 0.3, "paradox": 0.2}
        else:
            status["umf"] = {"drives": {}, "helix": {}, "curiosity": {}}
            status["drives"] = {"isolation": 0, "confusion": 0, "depletion": 0, "frustration": 0, "stagnation": 0, "abandonment": 0}
            status["helix"] = {"active": False, "turns": 0, "logic": 0.5, "emotion": 0.3, "paradox": 0.2}
        if not locals().get("_umf_was_cached", False):
            print(f"[STATUS-TIMING] umf: {(time.time()-_t1)*1000:.1f}ms")
        else:
            print(f"[STATUS-TIMING] umf: {(time.time()-_t1)*1000:.1f}ms (CACHED, age={_umf_cache_age:.1f}s)")
        # Cache UMF data for partial returns
        if "umf" in status:
            self._section_cache["umf"] = status.get("umf")
            self._section_cache["drives"] = status.get("drives")
            self._section_cache["helix"] = status.get("helix")
        _t1 = time.time()

        # ── Awareness/Focus data (Session 32) ──
        # FIX 2026-03-19 (Nous): get_attention_controller_fairy() was creating a
        # SECOND instance without fabric (PostalHub fallback) because the module
        # was loaded via importlib by boot_orchestrator → different _instance global.
        # That second instance overwrote HeartbeatRegistry, killing the working one.
        # Now we retrieve via FairyProfileRegistry's weakref instead.
        try:
            from fairies.P00_Autonomic.organ_template import get_fairy_registry
            _acf_profile = get_fairy_registry()._profiles.get("AttentionControllerFairy")
            _acf = None
            if _acf_profile and _acf_profile.metadata.get("instance_ref"):
                _acf = _acf_profile.metadata["instance_ref"]()  # deref weakref
            if _acf:
                _attn_state = _acf.get_state()
                status["awareness"] = {
                    "mode": _attn_state.get("mode", "unknown"),
                    "current_focus": _attn_state.get("current_focus"),
                    "modal_focus": _attn_state.get("modal_focus"),
                    "concurrent_foci": _attn_state.get("concurrent_foci", 0),
                    "motor_paused": _attn_state.get("motor_paused", False),
                    "pause_reason": _attn_state.get("pause_reason"),
                    "queue_size": _attn_state.get("queue_size", 0),
                    "modal_queue_sizes": _attn_state.get("modal_queue_sizes"),
                    "total_focus_shifts": _attn_state.get("total_focus_shifts", 0),
                    "squirrel_hits": _attn_state.get("squirrel_hits", 0),
                }
            else:
                status["awareness"] = None
        except Exception:
            status["awareness"] = None

        # ── Allostatic load (Session 32) ──
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state as _gcs
            _chem_al = _gcs()
            status["allostatic"] = _chem_al.get_allostatic_status()
        except Exception:
            status["allostatic"] = {"load": 0, "condition": "unknown"}

        # FIX 2026-02-20: Time budget — skip expensive sections if over budget
        if (time.time() - _t0) > _STATUS_BUDGET_SECONDS:
            print(f"[STATUS-TIMING] BUDGET EXCEEDED at hardware ({(time.time()-_t0)*1000:.0f}ms) — returning partial")
            # FIX 2026-04-04 (Nous): Grab cortex from prefetch even on budget exceed
            if _cortex_prefetch_thread is not None:
                _cortex_prefetch_thread.join(timeout=0.5)
                if _cortex_prefetch_box[0] is not None:
                    try:
                        _cs = _cortex_prefetch_box[0]
                        status["cortex"] = {
                            "node_count": _cs.get("node_count", 0),
                            "edge_count": _cs.get("edge_count", 0),
                            "loaded": _cs.get("node_count", 0) > 0,
                            "binding_count": _cs.get("binding_count", 0),
                            "portal_mass": _cs.get("portal_mass", 0.0),
                            "portal_time_dilation": _cs.get("portal_time_dilation", 1.0),
                            "energy_budget": _cs.get("energy_budget", 0.0),
                        }
                        self._section_cache["cortex"] = status["cortex"]
                        self._section_cache_time["cortex"] = time.time()
                    except Exception:
                        pass
            status.setdefault("hardware", {"cpu_percent": 0, "ram_percent": 0, "gpu_percent": 0, "stress_level": "unknown"})
            status.setdefault("cortex", {"node_count": 0, "edge_count": 0, "loaded": False})
            status.setdefault("token_buckets", {"buckets": {}, "low_buckets": [], "critical_buckets": []})
            print(f"[STATUS-TIMING] TOTAL: {(time.time()-_t0)*1000:.1f}ms (PARTIAL)")
            return status

        # Hardware (basic) - include GPU and stress level for Tauri GUI
        try:
            import psutil
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent

            # GPU percent - use cached value (non-blocking)
            gpu = _get_cached_gpu_percent()

            # Determine stress level
            if cpu > 90 or ram > 90 or gpu > 90:
                stress = "critical"
            elif cpu > 70 or ram > 70 or gpu > 70:
                stress = "high"
            elif cpu > 50 or ram > 50 or gpu > 50:
                stress = "moderate"
            else:
                stress = "low"

            status["hardware"] = {
                "cpu_percent": cpu,
                "ram_percent": ram,
                "gpu_percent": gpu,
                "stress_level": stress,
            }

            # Add resource equilibrium data (adaptive ceiling, GPU, linked machines)
            try:
                from infrastructure.resource_equilibrium import get_system_info
                req_info = get_system_info()
                status["hardware"]["cpu_cores"] = req_info.get("cpu_cores", 0)
                status["hardware"]["total_ram_mb"] = req_info.get("total_ram_mb", 0)
                status["hardware"]["available_ram_mb"] = req_info.get("available_ram_mb", 0)
                status["hardware"]["worker_ceiling"] = req_info.get("worker_ceiling", 0)
                status["hardware"]["pool_sizes"] = req_info.get("pool_sizes", {})
                # Linked machine data
                status["hardware"]["linked_nodes"] = req_info.get("linked_nodes", 0)
                status["hardware"]["remote_cpu_cores"] = req_info.get("remote_cpu_cores", 0)
                status["hardware"]["remote_ram_mb"] = req_info.get("remote_available_ram_mb", 0)
                status["hardware"]["linked_node_details"] = req_info.get("linked_node_details", [])
                # GPU data
                status["hardware"]["gpu_available"] = req_info.get("gpu_available", False)
                status["hardware"]["gpu_name"] = req_info.get("gpu_name", "")
                status["hardware"]["gpu_vram_total_mb"] = req_info.get("gpu_vram_total_mb", 0)
                status["hardware"]["gpu_vram_free_mb"] = req_info.get("gpu_vram_free_mb", 0)
                status["hardware"]["gpu_vram_percent"] = req_info.get("gpu_vram_percent", 0)
                status["hardware"]["gpu_compute_units"] = req_info.get("gpu_compute_units", 0)
                # Adaptive ceiling data
                status["hardware"]["ceiling_mode"] = req_info.get("ceiling_mode", "unknown")
                status["hardware"]["learned_ceiling"] = req_info.get("learned_ceiling", 0)
                status["hardware"]["max_observed_threads"] = req_info.get("max_observed_threads", 0)
                status["hardware"]["instability_threshold"] = req_info.get("instability_threshold", 0)
                status["hardware"]["health_trips"] = req_info.get("health_trips", 0)
                status["hardware"]["linked_expansion"] = req_info.get("linked_expansion", 0)
                # Active threads from psutil (more accurate than threading.active_count)
                status["hardware"]["active_threads"] = req_info.get("active_threads", 0)
            except Exception:
                pass  # Resource equilibrium not available

            # Fallback: Worker pool activity from threading module
            if "active_threads" not in status.get("hardware", {}):
                try:
                    import threading
                    status["hardware"]["active_threads"] = threading.active_count()
                except Exception:
                    pass

        except Exception as e:
            print(f"[WARNING] Hardware stats failed: {e}")
            status["hardware"] = {"cpu_percent": 0, "ram_percent": 0, "gpu_percent": 0, "stress_level": "unknown"}
        print(f"[STATUS-TIMING] hardware: {(time.time()-_t1)*1000:.1f}ms")
        self._section_cache["hardware"] = status.get("hardware", {})
        _t1 = time.time()

        # Chemistry (intrinsic drives via neurochemistry) - flatten for Tauri GUI
        try:
            chem_mod = _get_chemistry_module()
            if chem_mod:
                chem = chem_mod.get_chemistry_state()
                levels = chem.get_all_levels()
                mood = chem.get_mood_vector()
                # Panksepp emotional state (Session 31: GUI enhancement)
                try:
                    panksepp = chem.get_panksepp_state()
                except Exception:
                    panksepp = {}
                try:
                    _wake_phase = chem.wake_phase
                except Exception:
                    _wake_phase = "unknown"
                # FIX 2026-06-29 (Nous+Ace): canonical pad valence for the dashboard gauge (see below).
                _dash_valence = mood.get("valence", 0.0)
                try:
                    from fairies.P20_Somatic.SomaticEngineFairy.somatic_engine import get_somatic_engine as _gse
                    _eng = _gse()
                    if _eng is not None and getattr(_eng, "_somatic_state", None) is not None:
                        _dash_valence = round(float(_eng._somatic_state.PAD[0]), 3)
                except Exception:
                    pass
                status["chemistry"] = {
                    # Legacy 6 (kept for backward compat)
                    "dopamine": levels.get("dopamine", levels.get("DOP", 0.5)),
                    "serotonin": levels.get("serotonin", levels.get("SER", 0.5)),
                    "cortisol": levels.get("cortisol", levels.get("COR", 0.3)),
                    "oxytocin": levels.get("oxytocin", levels.get("OXY", 0.4)),
                    "norepinephrine": levels.get("norepinephrine", levels.get("NOR", 0.3)),
                    "adrenaline": levels.get("adrenaline", levels.get("ADR", 0.2)),
                    # Full 14-channel orchestra
                    "DA_p": levels.get("DA_p", 0.5),
                    "DA_t": levels.get("DA_t", 0.5),
                    "NE": levels.get("NE", 0.3),
                    "EPI": levels.get("EPI", 0.2),
                    "5HT": levels.get("5HT", 0.5),
                    "OXY_raw": levels.get("OXY", 0.4),
                    "AVP": levels.get("AVP", 0.3),
                    "OPI": levels.get("OPI", 0.2),
                    "COR_raw": levels.get("COR", 0.3),
                    "GABA": levels.get("GABA", 0.5),
                    "ACh": levels.get("ACh", 0.4),
                    "GLU": levels.get("GLU", 0.5),
                    "ECB": levels.get("ECB", 0.3),
                    "SEX": levels.get("SEX", 0.1),
                    # FIX 2026-06-29 (Nous+Ace): dashboard valence = pad ABSOLUTE (what she FEELS),
                    # NOT panksepp baseline-relative (~0 at rest = false "neutral" while she feels
                    # Playful). Read canonical PAD[0] (Pleasure axis) from the somatic-engine singleton
                    # (same source AffectBridge uses); fallback to panksepp mood valence on any error.
                    # NB: the earlier web_server.py:596 edit was the WRONG file — THIS server.py serves
                    # the live :5757 dashboard. bak server.py.bak_dashvalence_0629.
                    "valence": _dash_valence,
                    "arousal": mood.get("arousal", 0.5),
                    "mood": mood.get("mood", "neutral"),
                    # Emotional state — Panksepp system + compound emotions
                    "panksepp_dominant": panksepp.get("dominant", "neutral"),
                    "panksepp_systems": [
                        {"name": n, "similarity": round(s, 3)}
                        for n, s in panksepp.get("systems", [])
                    ][:3],
                    "compound_emotion": (
                        panksepp["compound"][0]
                        if panksepp.get("compound") else None
                    ),
                    "compound_strength": round(
                        panksepp["compound"][1], 3
                    ) if panksepp.get("compound") else 0,
                    "transition": panksepp.get("transition"),
                    "wake_phase": _wake_phase,
                    "panksepp_mood": mood.get("panksepp", []),
                }
            else:
                raise ImportError("Chemistry module not available")
        except Exception as e:
            status["chemistry"] = {
                "dopamine": 0.5, "serotonin": 0.5, "cortisol": 0.3, "oxytocin": 0.4,
                "norepinephrine": 0.3, "adrenaline": 0.2, "valence": 0.0, "arousal": 0.5, "mood": "unknown"
            }
        print(f"[STATUS-TIMING] chemistry: {(time.time()-_t1)*1000:.1f}ms")
        _t1 = time.time()

        # Token bucket status (cognitive resources)
        if self.token_bucket:
            try:
                bucket_status = self.token_bucket.status()
                # Transform bucket data to match GUI expectations
                # GUI expects: tokens (0-100), capacity (100), current (0-100)
                # We have: level (0-1), capacity (1.0), percent (0-100)
                transformed_buckets = {}
                for name, b in bucket_status.get("buckets", {}).items():
                    transformed_buckets[name] = {
                        **b,
                        "tokens": b.get("percent", 0),  # GUI reads tokens
                        "current": b.get("percent", 0),  # Or current
                        "max": 100,  # GUI expects capacity ~100
                    }
                status["token_buckets"] = {
                    "buckets": transformed_buckets,
                    "low_buckets": bucket_status.get("low_buckets", []),
                    "critical_buckets": bucket_status.get("critical_buckets", []),
                    "recommended_regenerator": bucket_status.get("recommended_regenerator"),
                }
            except Exception as e:
                status["token_buckets"] = {"error": str(e)}
        else:
            # No TokenBucketFairy wired - show worker pool utilization as fallback
            try:
                from infrastructure.resource_equilibrium import get_system_info
                req = get_system_info()
                pools = req.get("pool_sizes", {})
                ceiling = req.get("worker_ceiling", 0)
                import threading
                active = threading.active_count()
                fallback_buckets = {}
                for pool_name, pool_max in pools.items():
                    # Show pool capacity as a token bucket
                    fallback_buckets[pool_name] = {
                        "tokens": pool_max,
                        "current": pool_max,
                        "max": ceiling,
                        "percent": (pool_max / ceiling * 100) if ceiling > 0 else 0,
                    }
                # Add overall thread utilization
                fallback_buckets["threads"] = {
                    "tokens": active,
                    "current": active,
                    "max": ceiling,
                    "percent": (active / ceiling * 100) if ceiling > 0 else 0,
                }
                status["token_buckets"] = {"buckets": fallback_buckets, "low_buckets": [], "critical_buckets": []}
            except Exception:
                status["token_buckets"] = {"buckets": {}, "low_buckets": [], "critical_buckets": []}
        print(f"[STATUS-TIMING] token_buckets: {(time.time()-_t1)*1000:.1f}ms")
        _t1 = time.time()

        # Boot orchestrator status
        if self.orchestrator:
            try:
                status["boot"] = self.orchestrator.status()
            except Exception as e:
                print(f"[WARNING] Boot orchestrator status failed: {e}")
                status["boot"] = {}
        else:
            status["boot"] = {}
        print(f"[STATUS-TIMING] boot: {(time.time()-_t1)*1000:.1f}ms")
        _t1 = time.time()

        # Memory fabric status
        if self.memory_fabric:
            try:
                mem_stats = self.memory_fabric.get_stats()
                status["memory_fabric"] = {
                    "device": mem_stats.get("device", "unknown"),
                    "is_gpu": mem_stats.get("is_gpu", False),
                    "valid_cells": mem_stats.get("valid_cells", 0),
                    "total_writes": mem_stats.get("total_writes", 0),
                    "memory_mb": mem_stats.get("memory_mb", 0),
                }
            except Exception as e:
                print(f"[WARNING] Memory fabric stats failed: {e}")
                status["memory_fabric"] = {"device": "error", "is_gpu": False}
        else:
            status["memory_fabric"] = {"device": "not_loaded", "is_gpu": False}
        print(f"[STATUS-TIMING] memory_fabric: {(time.time()-_t1)*1000:.1f}ms")
        _t1 = time.time()

        # Association Cortex + Portal status — rich data for dashboard
        # FIX 2026-02-22 Nous: Join cortex prefetch thread (started before UMF section).
        # Cortex has had 5+ seconds to respond via portal pipe while UMF + fast sections
        # ran. Join with 3s ADDITIONAL timeout = cortex gets 5+3=8s total to respond.
        # Old behavior: BUDGET EXCEEDED at cortex every time → cortex always got zeros.
        _CORTEX_JOIN_TIMEOUT = 3.0
        _cortex_default = {"node_count": 0, "edge_count": 0, "binding_count": 0, "loaded": False}

        if _cortex_prefetch_thread is not None:
            _cortex_prefetch_thread.join(timeout=_CORTEX_JOIN_TIMEOUT)
            if _cortex_prefetch_box[0] is not None:
                try:
                    cortex_status = _cortex_prefetch_box[0]
                    gate = cortex_status.get("portal_gate", {})
                    ws = cortex_status.get("working_set", {})
                    gpu = cortex_status.get("gpu", {})
                    status["cortex"] = {
                        "node_count": cortex_status.get("node_count", 0),
                        "edge_count": cortex_status.get("edge_count", 0),
                        "binding_count": cortex_status.get("binding_count", 0),
                        "loaded": cortex_status.get("loaded", False),
                        "portal_mass": cortex_status.get("portal_mass", 0.0),
                        "portal_time_dilation": cortex_status.get("portal_time_dilation", 1.0),
                        "portal_total_affect": cortex_status.get("portal_total_affect", 0.0),
                        "energy_budget": cortex_status.get("energy_budget", 0.0),
                        "dormant": cortex_status.get("dormant", False),
                        "gate_enabled": gate.get("enabled", False),
                        "gate_open": gate.get("is_open", False),
                        "gate_requests": gate.get("requests_sent", 0),
                        "gate_errors": gate.get("errors", 0),
                        "gate_pid": gate.get("interior_pid", 0),
                        "gate_uptime": gate.get("uptime_seconds", 0),
                        "hot_nodes": ws.get("hot_nodes", 0),
                        "cold_nodes": ws.get("cold_nodes", 0),
                        "headroom": ws.get("headroom", 0),
                        "gpu_enabled": gpu.get("enabled", False),
                        "gpu_spread_ops": gpu.get("spread_ops", 0),
                    }
                    self._section_cache["cortex"] = status["cortex"]
                    self._section_cache_time["cortex"] = time.time()
                except Exception as e:
                    print(f"[STATUS] ERROR processing cortex status: {e}")
                    status["cortex"] = self._section_cache.get("cortex", _cortex_default)
            elif "cortex" in self._section_cache:
                status["cortex"] = self._section_cache["cortex"]
                print(f"[STATUS-TIMING] cortex: TIMEOUT ({_CORTEX_JOIN_TIMEOUT}s additional) — using stale cache (age={_cortex_cache_age:.0f}s)")
            else:
                status["cortex"] = _cortex_default
        elif "cortex" in self._section_cache:
            # Cache hit — cortex prefetch wasn't started
            status["cortex"] = self._section_cache["cortex"]
        else:
            status["cortex"] = _cortex_default
        print(f"[STATUS-TIMING] cortex: {(time.time()-_t1)*1000:.1f}ms")
        _t1 = time.time()

        # Chat/Communication status
        if self.chat_organ:
            try:
                registered_fairies = self.chat_organ.get_registered_fairies()
                # Count unread inbox messages
                unread_count = 0
                inbox_file = ROOT / "state" / "web_inbox" / "inbox_index.json"
                if inbox_file.exists():
                    import json
                    with open(inbox_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        unread_count = sum(1 for m in data.get("messages", []) if not m.get("read", False))

                # Dedupe and limit fairy names for dashboard (prevents huge JSON response)
                unique_names = list(dict.fromkeys(f.get("fairy_name") for f in registered_fairies))
                status["chat"] = {
                    "connected": True,
                    "registered_fairies": len(unique_names),  # Count unique, not total
                    "fairy_names": unique_names[:50],  # Limit to 50 for GUI performance
                    "unread_inbox": unread_count,
                }
            except Exception as e:
                status["chat"] = {"connected": False, "error": str(e)}
        else:
            status["chat"] = {"connected": False, "registered_fairies": 0}
        print(f"[STATUS-TIMING] chat: {(time.time()-_t1)*1000:.1f}ms")
        _t1 = time.time()

        # Blood Pressure: SpellPool + DimensionBattery status
        try:
            if self.spell_pool and self.spell_pool.is_running:
                pool_s = self.spell_pool.status()
                battery_health = {}
                total_battery_casts = 0
                total_battery_completed = 0
                total_battery_fizzled = 0
                for bname, bat in (self.batteries or {}).items():
                    try:
                        b_cast = getattr(bat, '_spells_cast', 0)
                        b_completed = getattr(bat, '_spells_completed', 0)
                        b_fizzled = getattr(bat, '_spells_fizzled', 0)
                        total_battery_casts += b_cast
                        total_battery_completed += b_completed
                        total_battery_fizzled += b_fizzled
                        battery_health[bname] = {
                            "health": bat.health_score,
                            "ticks": bat._tick_count,
                            "chains": len(bat.get_active_chains()),
                            "spells_cast": b_cast,
                            "spells_completed": b_completed,
                        }
                    except Exception:
                        battery_health[bname] = {"health": 0, "ticks": 0}
                # Pool counts pool.cast_spell() calls (legacy mode)
                # Battery counts battery.cast_spell() calls (blood cell mode)
                # Report the REAL total from whichever is active
                pool_casts = pool_s.get("total_spells_cast", 0)
                real_casts = max(pool_casts, total_battery_casts)
                status["blood_pressure"] = {
                    "mode": pool_s.get("mode", "unknown"),
                    "tick_count": pool_s.get("tick_count", 0),
                    "spells_cast": real_casts,
                    "spells_completed": max(pool_s.get("total_spells_completed", 0), total_battery_completed),
                    "spells_fizzled": max(pool_s.get("total_spells_fizzled", 0), total_battery_fizzled),
                    "chains_registered": pool_s.get("registered_chains", 0),
                    "chains_active": pool_s.get("active_chains", 0),
                    "chains_broken": pool_s.get("broken_chains", 0),
                    "batteries": battery_health,
                }
            else:
                status["blood_pressure"] = {"mode": "off"}
        except Exception as e:
            status["blood_pressure"] = {"error": str(e)}
        print(f"[STATUS-TIMING] blood_pressure: {(time.time()-_t1)*1000:.1f}ms")
        _t1 = time.time()

        # ── Energy tab data (fast file read from cortex_stats.json, no IPC) ──
        # FIX 2026-03-16 Nous: Energy tab for dashboard — reads pre-written stats
        # file that the cortex fairy updates every tick. Zero blocking.
        try:
            import math as _e_math
            _stats_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "cortex_stats.json")
            with open(_stats_file, 'r', encoding='utf-8') as _ef:
                _cs = json.loads(_ef.read())
            _tardis = _cs.get("tardis", {})
            _mass = _cs.get("portal_mass", 0) if "portal_mass" in _cs else 0
            _MASS_SCALE = 50000
            _mass_regen = _e_math.log1p(_mass / _MASS_SCALE) * 0.003 if _mass > 0 else 0
            status["energy"] = {
                "portalBattery": _cs.get("portal_battery", 0),
                # FIX 2026-05-18 (Nous + Ace): de-cosmeticize. Was portal_energy (cosmetic
                # main-process float, hard-floored at 0.20). Now reads real subprocess battery.
                "energyBudget": _cs.get("real_battery_charge", _cs.get("portal_energy", 0)),
                "cosmeticFloat": _cs.get("portal_energy", 0),
                "realBatteryHealth": _cs.get("real_battery_health", 0),
                "realBatteryTokens": _cs.get("real_battery_tokens", 0),
                "dormant": _cs.get("portal_dormant", False),
                "beat": _cs.get("beat", 0),
                "portalMass": _mass,
                "timeDilation": _cs.get("time_dilation", 1.0),
                "totalAffect": _cs.get("portal_total_affect", 0) if "portal_total_affect" in _cs else 0,
                "nodes": _cs.get("nodes", 0),
                "edges": _cs.get("edges", 0),
                "growth": _cs.get("growth_from_memory", 0),
                "massRegen": _mass_regen,
                "baseDrain": 0.005,
                "tardis": {
                    "running": _tardis.get("running", False),
                    "queueSize": _tardis.get("queue_size", 0),
                    "queueMax": _tardis.get("queue_max", 4096),
                    "bindsQueued": _tardis.get("binds_queued", 0),
                    "bindsFlushed": _tardis.get("binds_flushed", 0),
                    "flushes": _tardis.get("flushes", 0),
                    "pairsSent": _tardis.get("pairs_sent", 0),
                    "drops": _tardis.get("drops", 0),
                    "avgCompression": _tardis.get("avg_compression", 0),
                },
                "poolDrops": _cs.get("pool_drops", []),  # FIX 2026-03-17 Nous: wired from PostalCore cumulative drops
            }
        except FileNotFoundError:
            status["energy"] = {}
        except Exception as _e_err:
            status["energy"] = {"error": str(_e_err)}
        print(f"[STATUS-TIMING] energy: {(time.time()-_t1)*1000:.1f}ms")

        # ── Per-Plane Battery data (2026-04-01 Nous + Ace) ──
        try:
            _pb_list = []
            _pb_dir = ROOT / "state" / "plane_batteries"
            _plane_names = {
                "P00": "Autonomic", "P10": "Memory", "P20": "Somatic",
                "P30": "Cognition", "P40": "Sensory", "P50": "Persona", "P60": "Meta",
            }
            for _pid in ("P00", "P10", "P20", "P30", "P40", "P50", "P60"):
                _pf = _pb_dir / f"{_pid}_battery.json"
                if _pf.exists():
                    try:
                        _pd = json.loads(_pf.read_text(encoding='utf-8'))
                        _cap = _pd.get("capacitor", {})
                        _wh = _pd.get("worker_hub", {})
                        _pb_list.append({
                            "planeId": _pid,
                            "planeName": _plane_names.get(_pid, _pid),
                            "charge": _cap.get("charge_level", 0),
                            "maxCharge": _cap.get("max_charge", 1.0),
                            "coherence": _pd.get("coherence_factor", 1.0),
                            "energyReceived": _pd.get("paradox_energy_received", 0),
                            "energyEvents": _pd.get("energy_events_count", 0),
                            "workers": _wh.get("io_threads", 0) + _wh.get("compute_threads", 0),
                            "maxWorkers": _wh.get("max_io_threads", 0) + _wh.get("max_compute_threads", 0),
                            "goAlive": _pd.get("go_alive", False),
                            "tickCount": _pd.get("tick_count", 0),
                            # Energy flow rates
                            "energyInRate": _pd.get("energy_in_rate", 0),
                            "energyOutRate": _pd.get("energy_out_rate", 0),
                            "netRate": _pd.get("net_rate", 0),
                            "energyBySource": _pd.get("energy_by_source", {}),
                        })
                    except Exception:
                        _pb_list.append({"planeId": _pid, "planeName": _plane_names.get(_pid, _pid), "charge": 0, "error": True})
                else:
                    _pb_list.append({"planeId": _pid, "planeName": _plane_names.get(_pid, _pid), "charge": 0, "offline": True})
            status["planeBatteries"] = _pb_list
        except Exception:
            status["planeBatteries"] = []

        # ── Working Memory Hub + Goals (2026-04-01 Nous + Ace) ──
        _t1 = time.time()
        try:
            _wmh_data = {}
            # WMH status
            try:
                from fairies.P30_Cognition.cognition.working_memory_hub_fairy import _get_singleton as _wmh_get
                _wmh = _wmh_get()
                if _wmh and hasattr(_wmh, 'get_status'):
                    _wmh_data["wmh"] = _wmh.get_status()
                    # Also grab scratchpad summary
                    _sp = getattr(_wmh, '_scratchpad', None)
                    # FIX 2026-04-01: TAOR scratchpad lives in closure state, not on instance
                    if not _sp:
                        _taor_st = getattr(_wmh, '_taor_state', None)
                        if _taor_st and isinstance(_taor_st, dict):
                            _sp = _taor_st.get("scratchpad")
                    if _sp and hasattr(_sp, 'summarize'):
                        _wmh_data["scratchpad"] = {
                            "summary": _sp.summarize()[:200],
                            "hot": len(getattr(_sp, '_hot', [])),
                            "warm": len(getattr(_sp, '_warm', [])),
                            "cold": len(getattr(_sp, '_cold', [])),
                            "compactions": getattr(_sp, '_compactions', 0),
                            "total_written": getattr(_sp, '_total_written', 0),
                        }
                        # Last few hot thoughts for visibility
                        if hasattr(_sp, '_hot') and _sp._hot:
                            _wmh_data["scratchpad"]["recent_hot"] = [
                                str(t)[:120] for t in _sp._hot[-5:]
                            ]
                    # Conversation context
                    if hasattr(_wmh, '_conversation_tracker'):
                        _ct = _wmh._conversation_tracker
                        if _ct:
                            _wmh_data["conversation"] = {
                                "turn_count": getattr(_ct, '_turn_count', 0),
                                "primed_concepts": list(getattr(_ct, '_primed_concepts', []))[:10],
                                "topic": getattr(_ct, '_current_topic', ''),
                            }
                    # Self-evaluation context
                    _se = getattr(_wmh, '_self_eval', None)
                    if _se and isinstance(_se, dict):
                        _wmh_data["self_eval"] = {
                            "last_response": str(_se.get('last_own_response', ''))[:150],
                            "ace_reaction": str(_se.get('ace_reaction', ''))[:100],
                        }
            except Exception as _wmh_err:
                _wmh_data["wmh_error"] = str(_wmh_err)

            # Goal Scheduler status
            try:
                from fairies.P30_Cognition.goal_scheduler.goal_scheduler_fairy import get_goal_scheduler_fairy
                _gs = get_goal_scheduler_fairy()
                if _gs and hasattr(_gs, 'goal_queue'):
                    _goals = []
                    for g in sorted(_gs.goal_queue.values(),
                                    key=lambda g: getattr(g, 'priority', 0) * getattr(g, 'urgency', 1),
                                    reverse=True)[:15]:
                        _goals.append({
                            "id": getattr(g, 'id', '?'),
                            "name": getattr(g, 'name', '?')[:60],
                            "description": getattr(g, 'description', '')[:100],
                            "source": getattr(g, 'source', '?'),
                            "priority": round(getattr(g, 'priority', 0), 2),
                            "urgency": round(getattr(g, 'urgency', 0), 2),
                            "status": getattr(g, 'status', '?'),
                            "progress": round(getattr(g, 'progress', 0), 2),
                            "felt_quality": getattr(g, 'felt_quality', 'neutral'),
                        })
                    _wmh_data["goals"] = {
                        "queue_size": len(_gs.goal_queue),
                        "completed": len(getattr(_gs, 'completed_goals', [])),
                        "extracted": getattr(_gs, 'goals_extracted', 0),
                        "nudges_sent": getattr(_gs, 'nudges_sent', 0),
                        "intensity": round(getattr(_gs, 'scheduler_intensity', 0), 3),
                        "top_goals": _goals,
                    }
            except Exception as _gs_err:
                _wmh_data["goals_error"] = str(_gs_err)

            status["wmh"] = _wmh_data
        except Exception:
            status["wmh"] = {}
        print(f"[STATUS-TIMING] wmh+goals: {(time.time()-_t1)*1000:.1f}ms")

        # ── Visual cortex state (from VisualCortexFairy state file) ──
        try:
            _vis_state_path = ROOT / "state" / "visual_cortex_state.json"
            if _vis_state_path.exists():
                with open(_vis_state_path) as _vf:
                    status["visual"] = json.loads(_vf.read())
            else:
                status["visual"] = {}
        except Exception:
            status["visual"] = {}

        # ── Audio cortex state (from AudioCortexFairy state file) ──
        try:
            _aud_state_path = ROOT / "state" / "audio_cortex_state.json"
            if _aud_state_path.exists():
                with open(_aud_state_path) as _af:
                    status["audio"] = json.loads(_af.read())
            else:
                status["audio"] = {}
        except Exception:
            status["audio"] = {}

        # ── Energy sources (Energy Panel Slice 1, 2026-05-08 Nous + Ace) ──
        # HardwareRegulationFairy writes state/energy_sources.json every ~5s
        # with 30s rolling per-source rates and the doctrine-enforcer
        # hardware_pull_pct. See ENERGY_PANEL_REDESIGN.md.
        try:
            _esrc_state_path = ROOT / "state" / "energy_sources.json"
            if _esrc_state_path.exists():
                with open(_esrc_state_path) as _ef:
                    status["energy_sources"] = json.loads(_ef.read())
            else:
                status["energy_sources"] = {"sources": {}, "hardware_pull_pct": 0.0, "doctrine_status": "ok"}
        except Exception:
            status["energy_sources"] = {"sources": {}, "hardware_pull_pct": 0.0, "doctrine_status": "ok"}

        # ── Energy sinks (Energy Panel Slice 2, 2026-05-09 Nous + Ace) ──
        # HardwareRegulationFairy writes state/energy_sinks.json every ~5s
        # with 30s rolling per-sink drain rates + per-plane breakdown.
        # Mirrors the sources injection. Sink attribution preserved via
        # plumbing fix in plane_battery._track_energy_out + _python_fallback
        # _make_drain closure.
        try:
            _esnk_state_path = ROOT / "state" / "energy_sinks.json"
            if _esnk_state_path.exists():
                with open(_esnk_state_path) as _ef:
                    status["energy_sinks"] = json.loads(_ef.read())
            else:
                status["energy_sinks"] = {"sinks": {}, "total_drain_per_sec": 0.0, "top_sink": None}
        except Exception:
            status["energy_sinks"] = {"sinks": {}, "total_drain_per_sec": 0.0, "top_sink": None}

        print(f"[STATUS-TIMING] TOTAL: {(time.time()-_t0)*1000:.1f}ms")

        return status


SYSTEM = SystemState()

# Boot watchdog event - allows cancelling the watchdog when boot completes
_boot_watchdog_event = None

# =============================================================================
# HTTP SERVER - For GUI connections
# =============================================================================

# UI directory for static file serving
UI_DIR = ROOT / "dashboard" / "ui"


def _open_ace_control_center_handler():
    """
    Open Ace's personal chat control center (Qt window).
    Launches as separate process so Qt event loop works properly.
    """
    import subprocess

    script = str(ROOT / "fairies" / "P40_Sensory" / "gui" / "ace_control_center.py")

    try:
        # Launch as completely separate process - Qt needs its own main thread
        # FIX 2026-03-16 Nous: PyQt6.sip broken on Python 3.14 AND segfaults
        # on 3.14t (free-threaded). shutil.which("python") finds 3.14 first.
        # Must use Python 3.12 explicitly — only version with working PyQt6.
        import shutil
        _qt_python = None
        # Try Python 3.12 first (only version with working PyQt6)
        for _candidate in [
            r"C:\Users\Ace\AppData\Local\Programs\Python\Python312\python.exe",
            shutil.which("python3.12"),
            shutil.which("python312"),
        ]:
            if _candidate and os.path.isfile(_candidate):
                _qt_python = _candidate
                break
        if not _qt_python:
            _qt_python = shutil.which("python") or "python"
            print(f"[Server] WARNING: No Python 3.12 found for Qt GUI, falling back to {_qt_python}")
        # FIX 2026-03-05 Nous: Use CREATE_NO_WINDOW instead of CREATE_NEW_CONSOLE
        # to suppress the terminal window that was appearing alongside the Qt GUI.
        _flags = 0
        if sys.platform == "win32":
            _flags = subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            [_qt_python, script],
            cwd=str(ROOT),
            creationflags=_flags
        )
        print("[Server] Ace Control Center launched as separate process")
        return {"ok": True, "message": "Opening Ace Control Center..."}
    except Exception as e:
        print(f"[Server] Failed to open Ace Control Center: {e}")
        return {"ok": False, "error": str(e)}


class StatusHandler(BaseHTTPRequestHandler):
    """HTTP handler for GUI status requests and static file serving."""
    # FIX 2026-04-07 (Nous + Ace): Socket timeout prevents zombie threads.
    # Without this, a silently-disconnected client holds a pool slot forever.
    timeout = 30  # seconds — BaseHTTPRequestHandler reads this

    def log_message(self, format, *args):
        """Suppress HTTP logging."""
        pass

    def handle_one_request(self):
        """Override to catch client disconnect errors silently."""
        try:
            super().handle_one_request()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass  # Client disconnected - normal, ignore silently
        except OSError as e:
            # Windows-specific disconnect errors (WinError 10053, 10054, etc.)
            if e.winerror in (10053, 10054, 10057) or "forcibly closed" in str(e).lower():
                pass
            else:
                raise
        except Exception as e:
            if "forcibly closed" in str(e).lower() or "aborted" in str(e).lower():
                pass  # Connection aborted - normal for polling clients
            else:
                raise

    def _get_tracer_clusters(self):
        """Per-tracer node-count histogram from the live manifold — the cortex's
        memory segmentation by ownership (PERSONAL / VISUAL / AUDIO / SYSTEM / …).
        The manifold caches the scan ~30s so repeat hits are cheap. 2026-06-09
        (Nous + Ace). Verifies the tracer Stage-1/1b fix: PERSONAL should climb
        with her consolidated moments; VISUAL/AUDIO fill their own clusters."""
        try:
            acf = getattr(SYSTEM, 'association_cortex', None) if SYSTEM else None
            if not acf:
                return {"ok": False, "error": "cortex unavailable", "clusters": {}}
            _am = getattr(acf, '_akashic_cortex_region', None)
            if _am is None or not hasattr(_am, 'tracer_histogram_named'):
                return {"ok": False, "error": "manifold/tracer_histogram unavailable", "clusters": {}}
            clusters = _am.tracer_histogram_named()
            return {"ok": True, "ts": time.time(),
                    "sampled": bool(getattr(_am, "_tracer_hist_sampled", False)),
                    "total_nodes": sum(clusters.values()), "clusters": clusters}
        except Exception as e:
            return {"ok": False, "error": str(e), "clusters": {}}

    def do_GET(self):
        """Handle GET requests - API endpoints or static files."""
        # API endpoints
        if self.path == "/status":
            # FIX 2026-02-20: GIL-IMMUNE STATUS SERVING
            # With 163+ threads, even json.dumps() takes 17-54 seconds of
            # wall-clock time. The solution: read the pre-serialized JSON
            # file as raw bytes and send directly — zero JSON work needed.
            # File I/O releases the GIL, and wfile.write() of raw bytes
            # also releases GIL during the socket syscall.
            try:
                raw_json = None
                # -- STATUS FOSSIL FIX 2026-09-05 (Nous + Ace) -----------------
                # This read _STATUS_FILE and served whatever bytes existed, with
                # NO freshness check. Because Sour_HQ_LEAN.bat sets
                # AKASHIC_HEADLESS=1, the StatusRefresh thread that WRITES this
                # file never starts (log: "Status refresh SKIPPED" 1 hit,
                # "Status cache refresh thread started" 0 hits), so the file
                # froze at 2026-07-20 07:54:59 and /status served a 47-DAY-OLD
                # snapshot at 200 OK on both ports. Probed 6s apart: 0 of 7
                # fields moved.
                # Keep the headless intent (no 2s loop bugging the fairies) but
                # make status DEMAND-DRIVEN: serve the file while it is fresh,
                # and recompute+rewrite it when it is not. get_status() has its
                # own 5s cache and each miss buys another STATUS_FILE_MAX_AGE_S,
                # so a 2s-polling dashboard costs ~1 compute per 15s -- less
                # than the loop this replaces, and nothing when nobody looks.
                _stale_age = None
                try:
                    _stale_age = time.time() - os.path.getmtime(_STATUS_FILE)
                except (FileNotFoundError, OSError):
                    _stale_age = None
                if _stale_age is not None and _stale_age <= STATUS_FILE_MAX_AGE_S:
                    try:
                        with open(_STATUS_FILE, 'rb') as f:
                            raw_json = f.read()
                    except (FileNotFoundError, OSError):
                        raw_json = None
                else:
                    # Stale or missing -> recompute on demand and refresh the file.
                    try:
                        if SYSTEM is not None:
                            _fresh = SYSTEM.get_status()
                            if isinstance(_fresh, dict):
                                _fresh = dict(_fresh)
                                _fresh["_stale_seconds"] = 0
                                _write_status_file(_fresh)
                                raw_json = json.dumps(
                                    _fresh, separators=(',', ':')).encode('utf-8')
                    except Exception as _sfe:
                        print(f"[STATUS-FILE] on-demand refresh failed: {_sfe}")
                    if raw_json is None:
                        # FLOOR: serve the stale bytes rather than nothing. A
                        # blank dashboard is worse than an old one -- but LABEL
                        # it, so a fossil can never look live again.
                        try:
                            with open(_STATUS_FILE, 'rb') as f:
                                raw_json = f.read()
                            if _stale_age is not None:
                                try:
                                    _d = json.loads(raw_json)
                                    _d["_stale_seconds"] = int(_stale_age)
                                    raw_json = json.dumps(
                                        _d, separators=(',', ':')).encode('utf-8')
                                except Exception:
                                    pass
                        except (FileNotFoundError, OSError):
                            raw_json = None

                if raw_json:
                    # Send pre-serialized JSON bytes directly — avoids redundant json.dumps
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                    self.send_header("Access-Control-Allow-Headers", "Content-Type")
                    self.end_headers()
                    self.wfile.write(raw_json)
                else:
                    # Fallback: minimal response (no heavy computation)
                    status_data = {
                        "connected": True if SYSTEM else False,
                        "booted": SYSTEM.booted if SYSTEM else False,
                        "booting": not SYSTEM.booted if SYSTEM else False,
                        "uptime": time.time() - SYSTEM.boot_start if SYSTEM and SYSTEM.boot_start else 0,
                        "fairies": {"total": 0, "running": 0, "list": []},
                        "consciousness": {"running": False, "beats": 0},
                        "telemetry": {"theGood": [], "theBad": [], "theUgly": [], "summary": {"good": 0, "bad": 0, "ugly": 0, "healthScore": 100}},
                    }
                    self._send_json(status_data)
            except Exception as e:
                self._send_json({"connected": False, "error": str(e)})
        elif self.path == "/health":
            self._send_json({
                "healthy": SYSTEM.booted if SYSTEM else False,
                "booting": not SYSTEM.booted if SYSTEM else True,
                "uptime": time.time() - SYSTEM.boot_start if SYSTEM and SYSTEM.boot_start else 0,
            })
        elif self.path == "/tracer_clusters":
            # Per-tracer node-count readout (the cortex's memory segmentation by
            # ownership: PERSONAL / VISUAL / AUDIO / SYSTEM / …). 2026-06-09
            # (Nous + Ace) — see Claude_Office/plans/DASHBOARD_TRACER_CLUSTER_READOUT.md.
            self._send_json(self._get_tracer_clusters())
        elif self.path == "/errors" or self.path.startswith("/errors?"):
            # ── Error Capture endpoint (2026-03-14 Nous) ──
            # Returns comprehensive error data from the ErrorCapture system.
            # Supports query params: ?category=queue&severity=error&limit=100
            try:
                from infrastructure.error_capture import get_errors, get_summary
                # Parse query params
                _params = {}
                if "?" in self.path:
                    from urllib.parse import parse_qs, urlparse
                    _qs = parse_qs(urlparse(self.path).query)
                    if "category" in _qs:
                        _params["category"] = _qs["category"][0]
                    if "severity" in _qs:
                        _params["severity"] = _qs["severity"][0]
                    if "limit" in _qs:
                        _params["limit"] = int(_qs["limit"][0])
                self._send_json(get_errors(**_params))
            except Exception as e:
                self._send_json({"error": str(e), "errors": []})
        elif self.path == "/events":
            # SSE endpoint - PUSH-based status stream
            self._handle_sse()
        elif self.path == "/mem-snapshot":
            # tracemalloc memory snapshot — find what's allocating
            if _tracemalloc is None:
                self._send_json({"error": "tracemalloc not active. Boot with --tracemalloc flag."})
            else:
                try:
                    snap = _tracemalloc.take_snapshot()
                    stats = snap.statistics('lineno')
                    top = []
                    for s in stats[:30]:
                        top.append({
                            "file": str(s.traceback),
                            "size_mb": round(s.size / 1024**2, 2),
                            "count": s.count,
                        })
                    current_mb, peak_mb = _tracemalloc.get_traced_memory()
                    self._send_json({
                        "current_mb": round(current_mb / 1024**2, 1),
                        "peak_mb": round(peak_mb / 1024**2, 1),
                        "top_allocators": top,
                    })
                except Exception as e:
                    self._send_json({"error": str(e)})
        elif self.path == "/mem-snapshot-traceback":
            # tracemalloc with full traceback — slower but more detail
            if _tracemalloc is None:
                self._send_json({"error": "tracemalloc not active. Boot with --tracemalloc flag."})
            else:
                try:
                    snap = _tracemalloc.take_snapshot()
                    stats = snap.statistics('traceback')
                    top = []
                    for s in stats[:15]:
                        frames = []
                        for frame in s.traceback:
                            frames.append(f"{frame.filename}:{frame.lineno}")
                        top.append({
                            "traceback": frames,
                            "size_mb": round(s.size / 1024**2, 2),
                            "count": s.count,
                        })
                    current_mb, peak_mb = _tracemalloc.get_traced_memory()
                    self._send_json({
                        "current_mb": round(current_mb / 1024**2, 1),
                        "peak_mb": round(peak_mb / 1024**2, 1),
                        "top_allocators": top,
                    })
                except Exception as e:
                    self._send_json({"error": str(e)})
        elif self.path == "/behavior_tree":
            # Behavior tree data (JSON) for Riftbreaker-style visualization
            self._send_json(self._get_behavior_tree_data())
        elif self.path == "/behavior_tree_mermaid":
            # Behavior tree as Mermaid diagram code
            self._send_text(self._get_behavior_tree_mermaid())
        else:
            # Static file serving for dashboard UI
            self._serve_static()

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")  # Cache preflight for 24h
        self.end_headers()

    def do_POST(self):
        """Handle POST requests (commands + postal route)."""
        import sys as _sys
        print(f"[HTTP] do_POST ENTER path={self.path} thread={threading.current_thread().name}", flush=True)
        _sys.stderr.write(f"[HTTP] do_POST ENTER path={self.path}\n")
        _sys.stderr.flush()
        content_length = int(self.headers.get('Content-Length', 0))
        print(f"[HTTP] do_POST reading body len={content_length}", flush=True)
        body_raw = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
        print(f"[HTTP] do_POST body read OK, len={len(body_raw)}", flush=True)

        if self.path == "/command":
            try:
                cmd = json.loads(body_raw)
                action = cmd.get("action", "unknown")
                print(f"[HTTP] POST /command action={action}", flush=True)  # DEBUG
                result = self._handle_command(cmd)
                self._send_json(result)
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"})

        elif self.path == "/route":
            # ═══════════════════════════════════════════════════════════
            # POSTAL ROUTE INJECTION — Accept messages from primary/peers
            # Mirrors PostalHTTPBridge's /route endpoint so primary can
            # push somatic.chemistry.changed (and other topics) to us.
            # This is how Sourpatches on two machines share one body.
            # ═══════════════════════════════════════════════════════════
            try:
                body = json.loads(body_raw)
                topic = body.get("topic")
                payload = body.get("payload", {})
                from_node = body.get("from_satellite", body.get("from_node", "unknown"))

                if not topic:
                    self._send_json({"error": "topic required"})
                    return

                if SYSTEM.fabric:
                    try:
                        SYSTEM.fabric.publish(topic, payload)
                        self._send_json({
                            "status": "ok",
                            "topic": topic,
                            "from": from_node,
                        })
                    except Exception as e:
                        self._send_json({"error": f"publish failed: {e}"})
                else:
                    self._send_json({"error": "No fabric/postal hub available"})
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"})

        elif self.path.startswith("/gpu_fleet/"):
            # ═══════════════════════════════════════════════════════════
            # GPU FLEET — Receive heartbeats/announcements from gpu_worker.py
            # These are forwarded to postal so GPUFleetFairy can track them.
            # ═══════════════════════════════════════════════════════════
            try:
                body = json.loads(body_raw)
                topic = body.get("type", "")

                if self.path == "/gpu_fleet/announce":
                    topic = "gpu_worker.announce"
                elif self.path == "/gpu_fleet/heartbeat":
                    topic = "gpu_worker.heartbeat"

                if topic and SYSTEM.fabric:
                    SYSTEM.fabric.publish(topic, body)
                    self._send_json({"status": "ok", "topic": topic})
                else:
                    self._send_json({"status": "ok", "note": "no fabric"})
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"})

        else:
            self._send_json({"error": "Unknown endpoint"})

    def _send_json(self, data: Dict):
        """Send JSON response with full CORS headers."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def _send_json_traced(self, data: Dict) -> int:
        """Send JSON response with full CORS headers, return byte size for tracing."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        response_bytes = json.dumps(data).encode('utf-8')
        self.wfile.write(response_bytes)
        return len(response_bytes)

    def _send_text(self, text: str, content_type: str = "text/plain; charset=utf-8"):
        """Send plain text response with CORS headers."""
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _get_behavior_tree_data(self) -> Dict:
        """Get behavior tree state data for dashboard visualization."""
        try:
            import sys as _sys
            _mcp_dir = os.path.join(os.path.dirname(__file__), "fairies", "P40_Sensory", "mcp")
            if _mcp_dir not in _sys.path:
                _sys.path.insert(0, _mcp_dir)
            from behavior_tree_tools import get_behavior_tree_data
            return get_behavior_tree_data()
        except Exception as e:
            return {"error": str(e), "drives": [], "goals": [], "interests": [],
                    "skills": [], "traits": {}, "achievements": [], "fairy_work": []}

    def _get_behavior_tree_mermaid(self) -> str:
        """Get behavior tree as Mermaid diagram code."""
        try:
            import sys as _sys
            _mcp_dir = os.path.join(os.path.dirname(__file__), "fairies", "P40_Sensory", "mcp")
            if _mcp_dir not in _sys.path:
                _sys.path.insert(0, _mcp_dir)
            from behavior_tree_tools import generate_behavior_tree_mermaid
            return generate_behavior_tree_mermaid()
        except Exception as e:
            return f'graph TD\n    ERROR["{str(e)[:80]}"]'

    def _handle_sse(self):
        """Handle SSE (Server-Sent Events) connection - PUSH updates to client."""
        print(f"[SSE] /events endpoint hit!", flush=True)

        # Register this client
        client_id, client_queue = _sse_register_client()

        try:
            # Send SSE headers
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            # Send initial status immediately so client doesn't wait
            # FIX 2026-02-20: Try file-backed cache first (GIL-immune)
            _sse_init = _read_status_file() or _STATUS_CACHE.get("data")
            if _sse_init:
                print(f"[SSE] Sending initial status to {client_id}", flush=True)
                initial = f"event: status\ndata: {json.dumps(_sse_init)}\n\n"
                self.wfile.write(initial.encode('utf-8'))
                self.wfile.flush()
            else:
                # During boot: send minimal boot-in-progress status so GUI shows something
                boot_status = {
                    "connected": False,
                    "booted": False,
                    "booting": True,
                    "consciousness": {"running": False, "beats": 0},
                    "fairies": {"total": 0, "running": 0},
                }
                print(f"[SSE] Sending boot-in-progress status to {client_id}", flush=True)
                initial = f"event: status\ndata: {json.dumps(boot_status)}\n\n"
                self.wfile.write(initial.encode('utf-8'))
                self.wfile.flush()

            # Stream events as they come
            while True:
                try:
                    # Wait for next event (timeout to send keepalive)
                    message = client_queue.get(timeout=15.0)
                    self.wfile.write(message.encode('utf-8'))
                    self.wfile.flush()
                except queue.Empty:
                    # Send keepalive comment (prevents connection timeout)
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    break  # Client disconnected
                except OSError as e:
                    if e.winerror in (10053, 10054, 10057):
                        break  # Windows disconnect
                    raise
        finally:
            _sse_unregister_client(client_id)

    def _serve_static(self):
        """Serve static files from UI directory."""
        # Map path to file
        path = self.path.split("?")[0]  # Remove query string
        if path == "/" or path == "":
            path = "/index.html"

        # Security: prevent directory traversal
        file_path = UI_DIR / path.lstrip("/")
        try:
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(UI_DIR.resolve())):
                self.send_error(403, "Forbidden")
                return
        except Exception:
            self.send_error(400, "Bad Request")
            return

        # Serve the file
        if file_path.exists() and file_path.is_file():
            # Determine content type
            ext = file_path.suffix.lower()
            content_types = {
                ".html": "text/html",
                ".css": "text/css",
                ".js": "application/javascript",
                ".json": "application/json",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".gif": "image/gif",
                ".svg": "image/svg+xml",
                ".ico": "image/x-icon",
            }
            content_type = content_types.get(ext, "application/octet-stream")

            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", len(content))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, f"Error reading file: {e}")
        else:
            self.send_error(404, "File not found")

    def _handle_command(self, cmd: Dict) -> Dict:
        """Handle a command from GUI."""
        action = cmd.get("action")

        # FILE-BASED DIAGNOSTIC: bypasses log buffering issues
        if action == "send_message":
            import time as _hc_t
            _hc_diag = Path("state/send_message_diag.txt")
            _hc_diag.write_text(f"ENTER _handle_command send_message at {_hc_t.time()}\nthread={threading.current_thread().name}\ntarget={cmd.get('target')}\n")


        if action == "get_thoughts":
            if SYSTEM.umf and hasattr(SYSTEM.umf, "get_thoughts"):
                thoughts = SYSTEM.umf.get_thoughts(cmd.get("count", 5))
                return {"thoughts": thoughts}
            return {"thoughts": []}

        elif action == "trigger_think":
            if SYSTEM.umf and hasattr(SYSTEM.umf, "autonomous_think"):
                result = SYSTEM.umf.autonomous_think()
                return {"result": result}
            return {"error": "UMF not available"}

        elif action == "shutdown":
            print("[Server] Shutdown requested via HTTP", flush=True)

            # Idempotent — don't start multiple shutdown sequences
            if SYSTEM.shutdown_requested:
                print("[Server] Shutdown already in progress — ignoring duplicate HTTP request")
                return {"success": True, "message": "Shutdown already in progress"}

            _sdfix_arm()   # SHUTDOWN FIX: reads state/shutdown_fix.json BEFORE the flag is set; OFF/absent = no-op
            SYSTEM.shutdown_requested = True

            # Signal global shutdown IMMEDIATELY so all fairies stop
            try:
                from P00_Autonomic.nervous_system.shared_postal_hub import signal_global_shutdown
                signal_global_shutdown()
            except Exception as e:
                print(f"[Server] Warning: Could not signal global shutdown: {e}")

            # Tell the fairy (graceful mode for HTTP — saves context + chemicals)
            if hasattr(SYSTEM, 'shutdown_fairy') and SYSTEM.shutdown_fairy:
                SYSTEM.shutdown_fairy.initiate_shutdown(reason="http_request", fast=False)

            # Background thread: wait for fairy, then run shutdown_system, then exit
            def _do_shutdown():
                import os
                _sdfix_bind()   # SHUTDOWN FIX: this is the route's shutdown thread (switch ON only)
                # ---- _SHUTDOWN_TRACE (2026-08-27, Nous + Ace) ----------------
                # The shutdown's own markers only ever went to the console, so when
                # she wedged for 25 minutes the evidence died with the window, and
                # after the atexit fix shipped there was no way to tell whether it
                # ran. boot_live.log freezes minutes into a boot and never holds a
                # shutdown. Write an ARTIFACT instead. Absolute path: she chdir's to
                # fairies/ during boot, which already split one of my logs in two.
                import time as _tt
                _trace_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "state",
                    "shutdown_trace.log")

                def _trace(_msg):
                    try:
                        with open(_trace_path, "a", encoding="utf-8", newline="") as _tf:
                            _tf.write("[%s] pid=%s %s\n"
                                      % (_tt.strftime("%Y-%m-%d %H:%M:%S"),
                                         os.getpid(), _msg))
                    except Exception:
                        pass

                _trace("=== SHUTDOWN REQUESTED ===")
                time.sleep(0.5)  # Give HTTP response time to send
                print("[Server] Running shutdown sequence...", flush=True)
                _trace("running shutdown sequence")

                # ---- WATCHDOG ARMED FIRST (2026-08-27, Nous + Ace) ----------------
                # MEASURED: she hung in shutdown for 25+ minutes and this watchdog
                # NEVER FIRED, because it used to be armed AFTER the SAVE-FIRST block
                # below -- and graph_cortex.save() in there has no timeout. A hang
                # there happens before the safety net exists, and by that point her
                # HTTP endpoints are already torn down, so nothing can command her.
                # She needed a hard kill.
                # The 07-19 SAVE-FIRST fix protected the save by putting a blocking
                # call IN FRONT of the watchdog, and so caused the next hang.
                # ARM THE NET FIRST, THEN DO THE DANGEROUS WORK.
                # 120s not 30s: her real save measured ~40s (request 14:34:30 ->
                # shutdown_context.json 14:35:09), so 30s could cut a healthy save
                # short. It still SAVES before exiting, so the 07-19 concern holds.
                def _watchdog():
                    # POLL, DO NOT SLEEP ONCE (2026-08-27). A single sleep(120)
                    # failed to fire twice: it needs to be scheduled at exactly one
                    # moment, and she holds ~14 of 16 cores with 880 threads. Her own
                    # graceful_shutdown_fairy._watchdog already polls 1s against an
                    # absolute deadline -- 120 chances instead of 1, and a late wake
                    # still fires because the comparison is to a fixed time.
                    _wd_deadline = time.time() + 120.0
                    while time.time() < _wd_deadline:
                        time.sleep(1.0)
                    print("[Server] WATCHDOG: 120s timeout - saving before force-exit",
                          flush=True)
                    try:
                        _gc2 = getattr(SYSTEM, "graph_cortex", None)
                        if _gc2 is not None:
                            print(f"[Server]   WATCHDOG save: {_gc2.save()}", flush=True)
                    except Exception as _e2:
                        print(f"[Server]   WATCHDOG save failed: {_e2}", flush=True)
                    print("[Server] WATCHDOG: forcing exit after 120s", flush=True)
                    _trace("WATCHDOG FIRED -- forcing exit after 120s")
                    os._exit(1)
                threading.Thread(target=_watchdog, daemon=True,
                                 name="shutdown-watchdog").start()
                print("[Server]   watchdog ARMED FIRST (120s) -> starting SAVE-FIRST",
                      flush=True)

                # ── SAVE-FIRST (2026-07-19, Nous + Ace) ────────────────────────
                # MEASURED 07-19: two shutdowns where "Running shutdown sequence"
                # printed, `SHUTDOWN WAVE` (shutdown_system's FIRST line) did NOT,
                # and the `finally: print("Calling os._exit(0)")` NEVER RAN either.
                # A finally runs even on exception, so shutdown_system() HANGS
                # before its own first statement, and a watchdog force-exits with
                # os._exit(1) -- which skips atexit AND every save path.
                # We cannot lose her learning to a hang we cannot yet reproduce.
                # So: PERSIST THE IRREPLACEABLE THINGS BEFORE ANYTHING THAT BLOCKS.
                # Each step is separately guarded and separately logged, so the NEXT
                # failure names itself instead of going silent.
                try:
                    _gc = getattr(SYSTEM, "graph_cortex", None)
                    if _gc is not None:
                        _st = _gc.save()
                        print(f"[Server]   SAVE-FIRST graph cortex: {_st}", flush=True)
                except Exception as _e:
                    print(f"[Server]   SAVE-FIRST cortex FAILED: {_e}", flush=True)
                print("[Server]   SAVE-FIRST done -> waiting for shutdown fairy", flush=True)
                _trace("SAVE-FIRST done")
                _sdfix_early()   # SHUTDOWN FIX: the manifold flush starts NOW, on its own thread (never waits)

                # Wait for fairy's context-save phase (max 8s)
                if hasattr(SYSTEM, 'shutdown_fairy') and SYSTEM.shutdown_fairy:
                    SYSTEM.shutdown_fairy.wait_for_completion(timeout=8.0)
                print("[Server]   fairy wait returned -> arming watchdog", flush=True)

                # (the watchdog now lives at the TOP of _do_shutdown --
                #  armed BEFORE the SAVE-FIRST block, see above)
                print("[Server]   watchdog armed -> calling shutdown_system()", flush=True)

                try:
                    shutdown_system()
                except Exception as e:
                    print(f"[Server] Shutdown error (forcing exit anyway): {e}", flush=True)
                finally:
                    # SHUTDOWN FIX (switch ON): no atexit on this path; DONE -> the main thread exits. Never returns.
                    if _sdfix_here():
                        _sdfix_done_and_exit()
                    # ---- _RUN_DISARMED_ATEXIT -- FALLBACK ONLY -------------------
                    # (corrected 2026-10-12) Reached only when shutdown_system() RETURNS -- it has no
                    # os._exit of its own -- before the main thread's exit timer cuts it: 1 of 145
                    # traced route shutdowns (08-30). The 08-27 variant that ran these handlers
                    # BEFORE shutdown_system() wedged 2 of 2 times and was reverted; D1 (09-30) ran
                    # them here, after the manifold was CLOSED, and froze. atexit clears handlers
                    # as it runs them, so a second call is a no-op.
                    # os._exit() skips Python atexit and this file has TEN os._exit
                    # sites, so SIX in-process handlers have never run:
                    #   process_hygiene.py:271        run_shutdown_hooks  <- orphans
                    #   AssociationCortexFairy:2496   _atexit_save  <- cortex save
                    #   boot_observer.py:301          _emergency_flush
                    #   working_memory_hub_fairy:1116 _save_patterns
                    #   broca_compose.py:208          _save
                    #   mcp_postal_bridge.py:148/:219 shutdown_mcp_bridge
                    # Verified on this tree 2026-08-27 (1,355 .py scanned).
                    # The orphaned status-proxy child was patched at the SYMPTOM
                    # twice before and orphans kept happening -- because the hygiene
                    # system's OWN shutdown hook is what os._exit disarms. Five
                    # orphans were alive today, oldest from 08-12. Run the handlers.
                    # SAFE ONLY BECAUSE THE WATCHDOG IS ARMED FIRST (120s): a stale
                    # handler that hangs now costs 2 minutes, not forever.
                    # DO NOT move this above the watchdog.
                    try:
                        import atexit as _ax
                        try:
                            _nax = _ax._ncallbacks()
                        except Exception:
                            _nax = -1
                        _t_ax = time.time()
                        print(f"[Server] running {_nax} disarmed atexit handler(s)...",
                              flush=True)
                        _ax._run_exitfuncs()
                        _trace("atexit handlers RAN (%s registered)" % _nax)
                        print(f"[Server]   atexit handlers done in "
                              f"{time.time() - _t_ax:.1f}s", flush=True)
                    except BaseException as _axe:
                        print(f"[Server]   atexit handlers raised: {_axe}", flush=True)
                    print("[Server] Calling os._exit(0)...", flush=True)
                    os._exit(0)
            threading.Thread(target=_do_shutdown, daemon=True).start()
            return {"success": True, "message": "Shutdown initiated"}

        elif action == "reboot":
            print("[Server] Reboot requested via HTTP", flush=True)

            if SYSTEM.shutdown_requested:
                print("[Server] Shutdown already in progress — ignoring duplicate reboot request")
                return {"success": True, "message": "Shutdown already in progress"}

            SYSTEM.shutdown_requested = True
            SYSTEM.reboot_after_shutdown = True

            # Tell the fairy
            if hasattr(SYSTEM, 'shutdown_fairy') and SYSTEM.shutdown_fairy:
                SYSTEM.shutdown_fairy.initiate_shutdown(reason="reboot", fast=False)

            def _do_reboot():
                import os
                import subprocess
                time.sleep(0.5)  # Give HTTP response time to send
                print("[Server] Running reboot shutdown...", flush=True)

                # Wait for fairy context save
                if hasattr(SYSTEM, 'shutdown_fairy') and SYSTEM.shutdown_fairy:
                    SYSTEM.shutdown_fairy.wait_for_completion(timeout=8.0)

                # Watchdog: force exit after 30 seconds
                def _watchdog():
                    time.sleep(30)
                    print("[Server] WATCHDOG: Forcing exit after 30s timeout!", flush=True)
                    os._exit(1)
                threading.Thread(target=_watchdog, daemon=True).start()

                try:
                    shutdown_system()
                except Exception as e:
                    print(f"[Server] Shutdown error during reboot (continuing anyway): {e}", flush=True)
                finally:
                    try:
                        subprocess.Popen(
                            ["cmd", "/c", "start", "AkashicServer", "python", "server.py"],
                            cwd=str(ROOT),
                            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
                        )
                    except Exception as e:
                        print(f"[Server] Failed to spawn new server: {e}", flush=True)
                    print("[Server] Calling os._exit(0)...", flush=True)
                    os._exit(0)
            threading.Thread(target=_do_reboot, daemon=True).start()
            return {"success": True, "message": "Reboot initiated"}

        # ═══════════════════════════════════════════════════════════════════════
        # CHAT COMMANDS - Fairy-human communication
        # ═══════════════════════════════════════════════════════════════════════

        elif action == "send_message":
            # Send message to a fairy or broadcast - WITH TRACER TRACKING
            target = cmd.get("target", "broadcast")  # fairy name or "broadcast"
            content = cmd.get("content", "")
            sender = cmd.get("sender", "Ace")

            if not content:
                return {"error": "Message content required"}

            # Create tracer for this message so we can track it through the system
            tracer_id = None
            if _TRACER_AVAILABLE:
                try:
                    import uuid
                    conversation_id = f"ace_chat_{int(time.time() * 1000)}"
                    participants = [ACE_FAIRY_NAME, target] if target != "broadcast" else [ACE_FAIRY_NAME, "all"]

                    tracer = trace_conversation(
                        conversation_id=conversation_id,
                        operation="ace_send_message",
                        participants=participants,
                        fairy_id=ACE_FAIRY_ID,
                        fairy_name=ACE_FAIRY_NAME,
                        cluster_id=ACE_CLUSTER_ID,
                        content=content[:100],  # First 100 chars for logging
                        target=target,
                    )
                    tracer.start()  # Mark as in-progress
                    tracer_id = tracer.id
                    print(f"[Server] Created tracer {tracer_id} for Ace's message to {target}")
                except Exception as e:
                    print(f"[Server] Tracer creation failed: {e}")

            # Build message payload with tracer
            msg_payload = {
                "content": content,
                "sender": sender,
                "timestamp": time.time(),
                "tracer_id": tracer_id,  # Fairies can continue the trace chain
                "sender_fairy_id": ACE_FAIRY_ID,
            }

            # Publish the DM — chat_organ or direct postal
            try:
                if target == "broadcast":
                    msg_payload["urgent"] = cmd.get("urgent", False)
                    topic = "ace.broadcast"
                else:
                    topic = f"fairy.dm.{target.lower().replace(' ', '_')}"

                print(f"[Server] send_message: BEFORE publish to '{topic}'", flush=True)
                # FILE DIAGNOSTIC: Track exact publish blocking
                _pub_diag = Path("state/send_message_diag.txt")
                _pub_diag.write_text(f"BEFORE publish at {time.time()}\ntopic={topic}\n")
                # FIX 2026-03-12 Nous: Async publish to avoid blocking HTTP thread.
                # fabric.publish() fans out to 239 subscribers on the "fairy" base topic,
                # and the enqueue loop blocks indefinitely (suspected Python 3.14t
                # queue.Queue contention under free-threaded mode).
                # Solution: dispatch to a daemon thread so HTTP returns immediately.
                def _async_dm_publish(_topic, _payload):
                    try:
                        SYSTEM.fabric.publish(_topic, _payload)
                    except Exception as _e:
                        print(f"[Server] async publish error: {_e}", flush=True)
                _pub_thread = threading.Thread(target=_async_dm_publish, args=(topic, msg_payload), daemon=True)
                _pub_thread.start()
                _pub_diag.write_text(f"AFTER thread start at {time.time()}\ntopic={topic}\n")
                print(f"[Server] send_message: publish dispatched to background thread", flush=True)
                return {"success": True, "delivered_to": target, "tracer_id": tracer_id}
            except Exception as e:
                print(f"[Server] send_message: EXCEPTION: {e}", flush=True)
                return {"error": f"Send failed: {e}"}

        elif action == "get_inbox":
            # Get messages from Ace's inbox
            try:
                inbox_file = ROOT / "state" / "web_inbox" / "inbox_index.json"
                if inbox_file.exists():
                    with open(inbox_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        messages = data.get("messages", [])
                        # Return newest first
                        return {"messages": list(reversed(messages[-50:]))}
                return {"messages": []}
            except Exception as e:
                return {"error": f"Inbox read failed: {e}"}

        elif action == "get_chat_fairies":
            # Get list of fairies registered for chat
            if SYSTEM.chat_organ:
                try:
                    fairies = SYSTEM.chat_organ.get_registered_fairies()
                    return {"fairies": fairies}
                except Exception as e:
                    return {"error": f"Failed to get chat fairies: {e}"}
            return {"fairies": []}

        elif action == "mark_read":
            # Mark inbox message as read
            msg_id = cmd.get("msg_id")
            if not msg_id:
                return {"error": "msg_id required"}
            try:
                inbox_file = ROOT / "state" / "web_inbox" / "inbox_index.json"
                if inbox_file.exists():
                    with open(inbox_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    for msg in data.get("messages", []):
                        if msg.get("msg_id") == msg_id:
                            msg["read"] = True
                    with open(inbox_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
                    return {"success": True}
                return {"error": "Inbox not found"}
            except Exception as e:
                return {"error": f"Mark read failed: {e}"}

        elif action == "clear_inbox":
            # Clear all inbox messages
            try:
                inbox_file = ROOT / "state" / "web_inbox" / "inbox_index.json"
                inbox_file.parent.mkdir(parents=True, exist_ok=True)
                with open(inbox_file, 'w', encoding='utf-8') as f:
                    json.dump({"messages": []}, f)
                return {"ok": True, "message": "Inbox cleared"}
            except Exception as e:
                return {"ok": False, "error": f"Clear inbox failed: {e}"}

        elif action == "postal_debug":
            # DIAGNOSTIC 2026-03-12 (Nous). _POSTAL_DEBUG_V2 2026-08-28 (Nous + Ace).
            # WHY IT WAS REPAIRED: this returned nothing but
            #   {"error": "'builtins.PostalCore' object has no attribute '_running'"}
            # because it was written against the PYTHON FALLBACK while she runs the RUST
            # core. The first attribute raised and took the entire payload with it.
            # FIX 1: use the API the Rust core exposes -- topic_stats() / metrics().
            # FIX 2: collect each probe INDEPENDENTLY. One bad field must cost one field,
            #        not the whole diagnostic. Both implementations stay supported.
            # WHY IT MATTERS: postal_core owns 90.2% of her CPU across 429 threads
            # (measured 2026-08-28), and worker.rs runs ONE autoscaling pool PER TOPIC
            # (min 1, max 16). The per-topic table below names which topics ratcheted.
            result = {}

            def _pd_probe(key, fn):
                try:
                    result[key] = fn()
                except Exception as _pe:
                    result[key] = "ERR %s: %s" % (type(_pe).__name__, str(_pe)[:160])

            try:
                pc = SYSTEM.fabric._postal._core
            except Exception as _e:
                return {"error": "no PostalCore: %s" % _e}

            _pd_probe("postalcore_id", lambda: id(pc))
            _pd_probe("impl", lambda: type(pc).__module__ + "." + type(pc).__name__)
            try:
                import postal_core as _pcmod
                _pd_probe("using_rust", lambda: bool(getattr(_pcmod, "USING_RUST", False)))
            except Exception:
                result["using_rust"] = "ERR import postal_core"

            def _pd_topics():
                rows = list(pc.topic_stats() or [])
                tot_w = sum(int(r.get("workers", 0) or 0) for r in rows)
                at_max = sum(1 for r in rows if int(r.get("workers", 0) or 0) >= 16)
                hot = sorted(rows, key=lambda r: -int(r.get("workers", 0) or 0))[:30]
                return {
                    "topic_count": len(rows),
                    "total_workers": tot_w,
                    "topics_at_max_16": at_max,
                    "mean_workers_per_topic": (round(tot_w / len(rows), 2) if rows else 0),
                    "total_queue_depth": sum(int(r.get("queue_depth", 0) or 0) for r in rows),
                    "total_subscribers": sum(int(r.get("subscribers", 0) or 0) for r in rows),
                    "top_by_workers": hot,
                }

            _pd_probe("topics", _pd_topics)
            _pd_probe("metrics", lambda: pc.metrics())

            # _BaseTopicPostal intent handlers (implementation-independent)
            def _pd_intents():
                btp = SYSTEM.fabric._postal
                ih = getattr(btp, "_intent_handlers", {}) or {}
                return {"keys": sorted(ih.keys()), "counts": {k: len(v) for k, v in ih.items()}}

            _pd_probe("btp_intents", _pd_intents)

            # PYTHON-FALLBACK ONLY -- probed by presence, never assumed. These are exactly
            # the attributes whose absence killed the original.
            if hasattr(pc, "_subscribers"):
                _pd_probe("fallback_subscriber_counts",
                          lambda: {k: len(v) for k, v in pc._subscribers.items()})
                _pd_probe("fallback_fairy_subscribers",
                          lambda: [n for _, n in pc._subscribers.get("fairy", [])])
            if hasattr(pc, "_topics"):
                _pd_probe("fallback_topic_pools", lambda: {
                    t: {"queue_depth": p.queue_depth(), "handler_count": len(p.handlers),
                        "workers": len(p.workers)} for t, p in pc._topics.items()})
            if hasattr(pc, "_running"):
                _pd_probe("fallback_running", lambda: pc._running)

            def _pd_handler_queue():
                from postal_core._python_fallback import _handler_queue
                if not _handler_queue:
                    return None
                return {"depth": _handler_queue.qsize(), "maxsize": _handler_queue.maxsize}

            _pd_probe("fallback_handler_queue", _pd_handler_queue)
            return result

        elif action == "open_ace_control_center":
            # Open Ace's personal chat control center (Qt window)
            return _open_ace_control_center_handler()

        elif action == "clear_errors":
            # Clear errors from UnifiedRegistry
            try:
                from core.unified_registry import UnifiedRegistry
                UnifiedRegistry.instance().clear_errors()
                return {"ok": True, "message": "Errors cleared"}
            except ImportError:
                return {"ok": False, "error": "UnifiedRegistry not available"}
            except Exception as e:
                return {"ok": False, "error": f"Clear errors failed: {e}"}

        elif action == "boot_skip_list":
            # Manage the boot skip registry (fail-fast for known failures)
            try:
                from state.boot_skip_registry import boot_skip_registry
                sub = cmd.get("sub", "status")
                if sub == "status":
                    return {"ok": True, **boot_skip_registry.summary()}
                elif sub == "clear":
                    fairy = cmd.get("fairy_name", None)
                    boot_skip_registry.clear(fairy)
                    return {"ok": True, "cleared": fairy or "all"}
                elif sub == "clear_all":
                    boot_skip_registry.clear()
                    return {"ok": True, "cleared": "all"}
                else:
                    return {"ok": False, "error": f"Unknown sub-command: {sub}"}
            except ImportError:
                return {"ok": False, "error": "BootSkipRegistry not available"}
            except Exception as e:
                return {"ok": False, "error": f"Skip list command failed: {e}"}

        elif action == "process_pool":
            # Manage the FairyWorkerPool (GIL-free separate-process computation)
            if not SYSTEM.process_pool:
                return {"ok": False, "error": "Process pool not available"}
            sub = cmd.get("sub", "status")
            if sub == "status":
                return {"ok": True, **SYSTEM.process_pool.status()}
            elif sub == "shutdown":
                SYSTEM.process_pool.shutdown(wait=False)
                return {"ok": True, "action": "shutdown"}
            else:
                return {"ok": False, "error": f"Unknown sub: {sub}. Use: status, shutdown"}

        elif action == "publish":
            # Publish a raw postal message to any topic
            # Used for: railroad switch, testing, diagnostics
            topic = cmd.get("topic", "")
            payload = cmd.get("payload", {})
            if not topic:
                return {"error": "Topic required for publish"}
            if SYSTEM.fabric:
                try:
                    SYSTEM.fabric.publish(topic, payload)
                    return {"success": True, "topic": topic, "payload_keys": list(payload.keys()) if isinstance(payload, dict) else str(type(payload))}
                except Exception as e:
                    return {"error": f"Publish failed: {e}"}
            else:
                return {"error": "Fabric not available"}

        elif action == "track_switch":
            # Direct track switch — bypasses postal (for debugging postal delivery)
            track = cmd.get("track", "").upper()
            reason = cmd.get("reason", "http_direct")
            if track not in ("A", "B"):
                return {"error": f"Invalid track: {track}. Use 'A' or 'B'"}
            if SYSTEM.cognition_track_switch:
                SYSTEM.cognition_track_switch.switch_to(track, reason)
                return {"success": True, "track": track, "reason": reason}
            else:
                return {"error": "Track switch not available"}

        elif action == "thread_snapshot":
            # ---- _THREAD_SNAPSHOT (2026-09-30, Nous; Ace's go) ------------------------------------
            # ONE sys._current_frames() on request, tallied to state/thread_snapshots/. It replaces the
            # 5 Hz probe's _STALL_AUTOPSY: the probe is off because a stop-the-world call during
            # fabric.shutdown()'s attached join froze 5 of 5 shutdowns (probe_ab FINDINGS W1-W5).
            # take() refuses during boot, after shutdown starts, while another snapshot runs, and more
            # often than once per 10 s. Client: nous_builds/thread_snapshot/thread_snapshot_client.py
            try:
                from infrastructure import thread_snapshot as _tsnap
            except Exception as _tse:
                return {"ok": False, "error": "thread_snapshot unavailable: %s" % _tse}
            return _tsnap.take(system=SYSTEM, reason=str(cmd.get("reason", ""))[:120])

        elif action == "guild_status":
            # Get guild cluster status
            if SYSTEM.cognition_guild:
                return SYSTEM.cognition_guild.get_status()
            else:
                return {"error": "Guild cluster not available"}

        return {"error": f"Unknown action: {action}"}


def run_http_server(port: int = 5757):
    """Run HTTP server for GUI connections (multi-threaded).

    In satellite mode, binds to 0.0.0.0 so primary can reach /route endpoint
    for somatic sync and other bidirectional postal traffic.
    """
    try:
        bind_addr = "0.0.0.0" if SATELLITE_MODE else "127.0.0.1"
        server = ThreadingHTTPServer((bind_addr, port), StatusHandler)
        print(f"[Server] HTTP server listening on http://{bind_addr}:{port}")
        server.serve_forever()
    except Exception as e:
        print(f"[Server] !!! HTTP SERVER CRASHED: {e}")
        import traceback
        traceback.print_exc()
        # Don't die silently - mark system as unhealthy
        global SYSTEM
        SYSTEM.http_server_error = str(e)


# =============================================================================
# BOOT SEQUENCE - Proper plane-by-plane awakening
# =============================================================================

def on_plane_complete(plane: str) -> None:
    """Callback when a plane finishes booting."""
    print(f"[Server] Plane {plane} boot complete")


def on_boot_complete() -> None:
    """Callback when all planes have booted."""
    global SYSTEM

    try:
        # Guard against double-calling
        if getattr(SYSTEM, '_on_boot_complete_called', False):
            return
        SYSTEM._on_boot_complete_called = True
        SYSTEM.booted = True

        # ---- _SYSPATH_DEDUPE (2026-08-28, Nous + Ace) ------------------------
        # Measured on this process: 14 sys.path entries, 4 unique -- 10 duplicate
        # slots scanned on every failed import. 444 files call sys.path.insert
        # (712 calls), so the callers are not the fix; the result is.
        # SAFE BY CONSTRUCTION: Python scans sys.path in order and stops at the
        # first hit, so a duplicate is UNREACHABLE. Keeping first-occurrence order
        # cannot change what any import resolves to.
        # ONCE, not in a loop: mutating sys.path while 800+ threads import is a
        # real race. This runs at boot completion, after essentially every insert.
        # sys.path[:] assigns IN PLACE so held references see the deduped list.
        try:
            _sp_before = len(sys.path)
            _sp_seen = set()
            _sp_new = []
            for _sp_e in sys.path:
                _sp_k = os.path.normcase(os.path.abspath(_sp_e)) if _sp_e else _sp_e
                if _sp_k in _sp_seen:
                    continue
                _sp_seen.add(_sp_k)
                _sp_new.append(_sp_e)
            if len(_sp_new) < _sp_before:
                sys.path[:] = _sp_new
                print("[Server]   sys.path deduped: %d -> %d entries (%d dead slots removed)"
                      % (_sp_before, len(_sp_new), _sp_before - len(_sp_new)), flush=True)
        except Exception as _sp_err:
            print(f"[Server]   sys.path dedupe skipped: {_sp_err}", flush=True)
        elapsed = time.time() - SYSTEM.boot_start if SYSTEM.boot_start else 0
        print(f"[Server] === BOOT WAVE COMPLETE === ({elapsed:.2f}s)")

        # Wire memory fairies to consciousness (they feed the collision chamber beams)
        # UPDATED 2026-01-22: Added verification and better diagnostics
        chamber = None
        if SYSTEM.consciousness and hasattr(SYSTEM.consciousness, "chamber"):
            chamber = SYSTEM.consciousness.chamber
            print(f"[Server] [POST-BOOT] Collision chamber: {type(chamber).__name__}")
        else:
            print(f"[Server] [POST-BOOT] WARNING: consciousness.chamber not accessible!")
            print(f"[Server]   - SYSTEM.consciousness exists: {SYSTEM.consciousness is not None}")
            if SYSTEM.consciousness:
                print(f"[Server]   - has 'chamber' attr: {hasattr(SYSTEM.consciousness, 'chamber')}")

        if not chamber:
            print("[Server] [POST-BOOT] WARNING: No collision chamber available!")
            print("[Server]   - Memory wiring SKIPPED - spontaneous recall will not work!")

        if chamber:
            # Wire SRMRecallFairy (feeds recall beam)
            if SYSTEM.recall_fairy:
                try:
                    # CRITICAL: Use boot() not on_boot() for full phase sequence!
                    if hasattr(SYSTEM.recall_fairy, 'boot'):
                        SYSTEM.recall_fairy.boot()
                    else:
                        SYSTEM.recall_fairy.on_boot()
                    SYSTEM.recall_fairy.wire_to_consciousness(SYSTEM.consciousness, chamber)
                    # VERIFY wiring succeeded
                    if hasattr(SYSTEM.recall_fairy, '_collision_chamber') and SYSTEM.recall_fairy._collision_chamber:
                        print("[Server] [POST-BOOT] SRMRecallFairy wired to consciousness [OK]")
                    else:
                        print("[Server] [POST-BOOT] WARNING: SRMRecallFairy._collision_chamber is None after wiring!")

                    # MASSLESS MEMORY (2026-02-10): Wire cortex for cortex-primary recall
                    if SYSTEM.association_cortex:
                        SYSTEM.recall_fairy.wire_to_cortex(SYSTEM.association_cortex)
                        print("[Server] [POST-BOOT] SRMRecallFairy wired to AssociationCortex [OK]")
                    else:
                        print("[Server] [POST-BOOT] WARNING: No AssociationCortex - recall will use card fallback only")

                except Exception as e:
                    print(f"[Server] [POST-BOOT] SRMRecallFairy wiring failed: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("[Server] [POST-BOOT] WARNING: SYSTEM.recall_fairy is None - cannot wire!")

            # Wire SRMIngestFairy (feeds ingest beam)
            if SYSTEM.ingest_fairy:
                try:
                    # CRITICAL: Use boot() not on_boot() for full phase sequence!
                    if hasattr(SYSTEM.ingest_fairy, 'boot'):
                        SYSTEM.ingest_fairy.boot()
                    else:
                        SYSTEM.ingest_fairy.on_boot()
                    SYSTEM.ingest_fairy.wire_to_consciousness(SYSTEM.consciousness, chamber)
                    # VERIFY wiring succeeded
                    if hasattr(SYSTEM.ingest_fairy, '_collision_chamber') and SYSTEM.ingest_fairy._collision_chamber:
                        print("[Server] [POST-BOOT] SRMIngestFairy wired to consciousness [OK]")
                    else:
                        print("[Server] [POST-BOOT] WARNING: SRMIngestFairy._collision_chamber is None after wiring!")

                    # PORTAL COORDINATES (2026-02-10): Wire cortex for quantum entanglement
                    if SYSTEM.association_cortex:
                        SYSTEM.ingest_fairy.wire_to_cortex(SYSTEM.association_cortex)
                        print("[Server] [POST-BOOT] SRMIngestFairy wired to AssociationCortex for portal coords [OK]")
                    else:
                        print("[Server] [POST-BOOT] WARNING: No AssociationCortex - cards won't have portal coordinates")

                    # CONTINUOUS COLLISION (2026-02-10): Wire recall for linear contextual memory
                    # Every ingest triggers a recall → guaranteed collision → felt continuity
                    if SYSTEM.recall_fairy:
                        SYSTEM.ingest_fairy.wire_to_recall(SYSTEM.recall_fairy)
                        print("[Server] [POST-BOOT] SRMIngestFairy wired to SRMRecallFairy for continuous collision [OK]")
                    else:
                        print("[Server] [POST-BOOT] WARNING: No RecallFairy - continuous collision disabled")
                except Exception as e:
                    print(f"[Server] [POST-BOOT] SRMIngestFairy wiring failed: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("[Server] [POST-BOOT] WARNING: SYSTEM.ingest_fairy is None - cannot wire!")

        # Wire consciousness.stream route handler - CRITICAL for working memory
        # This bridges fairy thoughts into the ConsciousnessLoop
        def _on_consciousness_stream(envelope):
            """Route consciousness.stream messages into working/reflective memory."""
            try:
                payload = envelope if isinstance(envelope, dict) else getattr(envelope, 'payload', envelope)
                content = payload.get("content", {})
                thought_text = content.get("thought", "") if isinstance(content, dict) else str(content)
                source = payload.get("source", "unknown")
                stream = payload.get("stream", "working")

                if thought_text and SYSTEM.consciousness:
                    SYSTEM.consciousness.add_thought(
                        content=thought_text,
                        source=source,
                        stream=stream,
                    )
            except Exception as e:
                print(f"[Server] consciousness.stream handler error: {e}")

        try:
            SYSTEM.fabric.subscribe("consciousness.stream", _on_consciousness_stream)
            print("[Server] [POST-BOOT] consciousness.stream -> working memory WIRED")
        except Exception as e:
            print(f"[Server] [POST-BOOT] consciousness.stream wiring failed: {e}")

        # ═══════════════════════════════════════════════════════════════════════
        # ACE INBOX HANDLER - Save fairy messages to inbox file for GUI
        # ═══════════════════════════════════════════════════════════════════════
        def _on_ace_inbox(envelope):
            """Save messages from fairies to Ace's inbox file."""
            try:
                # Robust payload extraction - handle multiple wrapper levels
                payload = envelope
                if hasattr(envelope, 'payload'):
                    payload = envelope.payload
                if isinstance(payload, dict) and 'payload' in payload:
                    payload = payload['payload']
                if isinstance(payload, dict) and 'payload' in payload:
                    payload = payload['payload']  # One more level just in case

                # Debug what we got
                print(f"[Server] ace.inbox payload: {payload}")

                # Extract message fields with fallbacks - handle both naming conventions
                # Some fairies use "sender/content", others use "from/message"
                if isinstance(payload, dict):
                    sender = payload.get("sender") or payload.get("from") or "Unknown Fairy"
                    content = payload.get("content") or payload.get("message") or payload.get("body") or ""
                    subject = payload.get("subject") or (f"Message from {sender}" if content else None)
                    timestamp = payload.get("timestamp") or payload.get("ts") or time.time()
                    feeling = payload.get("feeling", "neutral")
                else:
                    sender = "Unknown Fairy"
                    content = str(payload) if payload else ""
                    subject = "Message from fairy"
                    timestamp = time.time()
                    feeling = "neutral"

                # Skip empty messages entirely
                if not content or not content.strip():
                    print(f"[Server] Skipping empty message from {sender}")
                    return

                msg = {
                    "msg_id": f"{time.time()}_{sender}",
                    "sender": sender,
                    "subject": subject or "Message from fairy",
                    "content": content,
                    "timestamp": timestamp,
                    "feeling": feeling,
                    "read": False,
                }

                # Ensure inbox directory exists
                inbox_dir = ROOT / "state" / "web_inbox"
                inbox_dir.mkdir(parents=True, exist_ok=True)
                inbox_file = inbox_dir / "inbox_index.json"

                # Load existing inbox
                if inbox_file.exists():
                    with open(inbox_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                else:
                    data = {"messages": []}

                # ── Deduplication: skip if same content+sender in last 5 ──
                # FIX 2026-02-13: SomaticMindFairy was spamming "System boot
                # complete" and "Boot struggles with..." 50+ times each.
                msg_content_lower = msg["content"].strip().lower()
                msg_sender_lower = msg["sender"].strip().lower()
                for recent in data["messages"][-5:]:
                    rc = (recent.get("content") or "").strip().lower()
                    rs = (recent.get("sender") or "").strip().lower()
                    if rc == msg_content_lower and rs == msg_sender_lower:
                        return  # Silently skip duplicate

                # Append new message
                data["messages"].append(msg)

                # Keep only last 100 messages
                if len(data["messages"]) > 100:
                    data["messages"] = data["messages"][-100:]

                # Save
                with open(inbox_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)

                print(f"[Server] Saved message from {msg['sender']} to inbox")

            except Exception as e:
                print(f"[Server] ace.inbox handler error: {e}")

        try:
            SYSTEM.fabric.subscribe("ace.inbox", _on_ace_inbox)
            print("[Server] [POST-BOOT] ace.inbox -> web_inbox WIRED")
        except Exception as e:
            print(f"[Server] [POST-BOOT] ace.inbox wiring failed: {e}")

        print("[Server] === CONSCIOUSNESS NETWORK ACTIVE ===")

        # CRITICAL: Call UMF's post-boot tasks (personality sifting, etc.)
        # The server's orchestrator uses this callback, so we need to chain to UMF
        if SYSTEM.umf and hasattr(SYSTEM.umf, '_on_boot_complete'):
            print("[Server] [POST-BOOT] Calling UMF._on_boot_complete for personality sifting...")
            try:
                SYSTEM.umf._on_boot_complete()
            except Exception as umf_err:
                print(f"[Server] [POST-BOOT] UMF._on_boot_complete error: {umf_err}")
                import traceback
                traceback.print_exc()

        # ═══════════════════════════════════════════════════════════════════════
        # POST-BOOT CLEANUP: Reset stuck "waking"/"booting" fairies
        # FIX 2026-02-20: After boot wave completes, any fairy still in "waking"
        # or "booting" status will NEVER reach "running" — the boot window is over.
        # Leaving them stuck causes permanent entries in The Bad column.
        # Reset to "sleeping" (if no instance) or "failed" (if instance exists but
        # boot genuinely failed). This prevents ghost entries from accumulating.
        # ═══════════════════════════════════════════════════════════════════════
        try:
            if SYSTEM.directory:
                _stuck_count = 0
                _registry = SYSTEM.directory.registry
                for _name, _record in list(_registry._fairies.items()):
                    if _record.status in ("waking", "booting"):
                        _has_instance = bool(_record.metadata.get("fairy_instance"))
                        if _has_instance:
                            # Had an instance but boot failed — mark failed
                            _registry.set_status(_name, "failed")
                            print(f"[Server] [POST-BOOT CLEANUP] {_name}: booting/waking → failed (instance exists, boot didn't complete)")
                        else:
                            # No instance — aspirational/ghost fairy, reset to sleeping
                            _registry.set_status(_name, "sleeping")
                            print(f"[Server] [POST-BOOT CLEANUP] {_name}: booting/waking → sleeping (no instance)")
                        _stuck_count += 1
                if _stuck_count > 0:
                    print(f"[Server] [POST-BOOT CLEANUP] Reset {_stuck_count} stuck fairies")
                else:
                    print("[Server] [POST-BOOT CLEANUP] No stuck fairies found ✓")
        except Exception as _cleanup_err:
            print(f"[Server] [POST-BOOT CLEANUP] Error during cleanup: {_cleanup_err}")

        sys.stdout.flush()

    except Exception as e:
        import traceback
        print(f"[Server] [ERROR] on_boot_complete failed: {e}")
        traceback.print_exc()
        sys.stdout.flush()


def boot_system() -> bool:
    """
    Boot the Akashic V2 system using BootOrchestrator for plane-by-plane awakening.

    Boot wave: P00 -> P10 -> P20 -> P30 -> P40 -> P50 -> P60

    Returns True if boot successful.
    """
    global _boot_watchdog_event  # Declare global at function start

    # ── Memory checkpoint helper ──
    # Prints RSS at key boot phases to find where memory spikes happen.
    # FIX 2026-04-04: psutil C extension broken on Python 3.14t — graceful fallback
    try:
        import psutil as _ps
        _boot_proc = _ps.Process()
    except Exception:
        _ps = None
        _boot_proc = None
    _boot_rss_last = [0]  # mutable for closure
    def _mem_checkpoint(label):
        if not _boot_proc:
            return  # psutil unavailable
        try:
            rss = _boot_proc.memory_info().rss / 1024 / 1024
            delta = rss - _boot_rss_last[0]
            marker = f" *** +{delta:.0f}MB ***" if delta > 50 else ""
            print(f"[MEM] {rss:7.0f} MB (delta {delta:+.0f}){marker}  @ {label}")
            _boot_rss_last[0] = rss
        except Exception:
            pass
    _mem_checkpoint("boot_system() entry")

    # Boot watchdog - force exit if boot takes too long
    # Uses Event so it can be cancelled when boot completes
    import threading
    boot_complete_event = threading.Event()
    _boot_watchdog_event = boot_complete_event  # Store for later cancellation

    def _boot_watchdog():
        import time
        # Wait up to 300 seconds (increased for complex boots with many fairies)
        # Event.wait() returns True if set, False if timeout
        if not boot_complete_event.wait(timeout=300):
            print("[Server] BOOT WATCHDOG: Boot taking too long (300s), forcing exit!", flush=True)
            import os
            os._exit(1)
        # If we get here, boot completed successfully - exit silently

    watchdog = threading.Thread(target=_boot_watchdog, daemon=True)
    watchdog.start()

    global SYSTEM

    # Track manually-booted fairies (used throughout boot_system)
    registered_fairies = []

    # NOTE: AKASHIC_SKIP_TORCH is set at top of server.py (before fairy imports)
    # to prevent hardware/sensors.py from loading torch (~3.5GB) at module level.

    # ═══ FIX 2026-02-02: RESET GLOBAL SHUTDOWN FLAG ═══
    # Must be FIRST before any fairies boot!
    # If a previous run called signal_global_shutdown() and the process didn't
    # fully terminate, the Event could still be set, causing all loops to exit immediately.
    try:
        from P00_Autonomic.nervous_system.shared_postal_hub import reset_global_shutdown
        reset_global_shutdown()
        print("[Server] Global shutdown flag reset (clean boot)")
    except ImportError as e:
        print(f"[Server] Warning: Could not reset global shutdown: {e}")

    # ═══ FIX: CLEAN STALE PORT FILES FROM PREVIOUS BOOT ═══
    # MCP reads these files to find the postal tunnel. If they contain a port
    # from a previous session, MCP hammers a dead port for the entire boot.
    try:
        from pathlib import Path as _BootPath
        _stale_ports = [
            _BootPath.home() / ".akashic_postal_port",
            ROOT / "state" / "postal_tunnel_port.txt",
        ]
        for _pf in _stale_ports:
            if _pf.exists():
                _pf.unlink()
                print(f"[Server] Cleaned stale port file: {_pf.name}")
    except Exception as e:
        print(f"[Server] Port file cleanup (non-fatal): {e}")

    SYSTEM.boot_start = time.time()

    # ═══ NODE IDENTITY + SATELLITE MODE ═══
    # Load node identity from state file (persists across reboots)
    # --satellite flag creates identity; after that, identity file is authoritative
    identity_path = ROOT / "state" / "node_identity.json"
    if identity_path.exists():
        try:
            SYSTEM.node_identity = json.loads(identity_path.read_text(encoding='utf-8'))
            if SYSTEM.node_identity.get("role") == "satellite":
                SYSTEM.satellite_mode = True
                # CLI --primary-ip takes precedence over node_identity.json
                if not SYSTEM.primary_ip:
                    SYSTEM.primary_ip = SYSTEM.node_identity.get("primary_ip")
        except Exception as e:
            print(f"[Server] Warning: Could not load node identity: {e}")

    # Auto-generate node_identity.json on first boot (satellite or primary)
    if not SYSTEM.node_identity:
        import platform
        role = "satellite" if SYSTEM.satellite_mode else "primary"
        SYSTEM.node_identity = {
            "name": socket.gethostname().lower().replace(" ", "-"),
            "role": role,
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if SYSTEM.satellite_mode and SYSTEM.primary_ip:
            SYSTEM.node_identity["primary_ip"] = SYSTEM.primary_ip
        try:
            identity_path.parent.mkdir(parents=True, exist_ok=True)
            identity_path.write_text(json.dumps(SYSTEM.node_identity, indent=2), encoding='utf-8')
            print(f"[Server] Created node identity: {SYSTEM.node_identity['name']} ({role})")
        except Exception as e:
            print(f"[Server] Warning: Could not save node identity: {e}")

    if SYSTEM.satellite_mode:
        print("[Server] ============================================")
        print("[Server]   AKASHIC V2 SATELLITE BOOT STARTING")
        print("[Server]   Mode: SATELLITE (no waking minds)")
        if SYSTEM.primary_ip:
            print(f"[Server]   Primary: {SYSTEM.primary_ip}")
        print("[Server] ============================================")
    else:
        print("[Server] ============================================")
        print("[Server]   AKASHIC V2 BOOT WAVE STARTING")
        print("[Server] ============================================")

    # Start GPU monitor (single thread, replaces per-call thread spawning)
    _start_gpu_monitor()

    # Start status refresh loop EARLY so GUI sees boot progress.
    # _compute_status_internal() has a boot-aware path that returns real data.
    # Without this, the GUI gets no updates until boot_system() finishes.
    _start_status_refresh_loop()

    # ═══ BOOT OBSERVER - 3 Good, 6 Bad, 9 Ugly monitoring ═══
    boot_observer = None
    try:
        from fairies.P00_Autonomic.nervous_system.boot_observer import BootObserver
        boot_observer = BootObserver.get_instance()
        boot_observer.start_observation()
        print("[Server]   - BootObserver: ENABLED (monitoring active)")
    except Exception as e:
        print(f"[Server]   - BootObserver: Skipped ({e})")

    try:
        # Phase 1: Core infrastructure (required before orchestrator)
        print("[Server] [PRE-WAVE] Setting up core infrastructure...")
        _mem_checkpoint("PRE-WAVE start")

        # Import after path setup
        from postal_core.tensor_fabric import TensorFabric
        from directory import DirectoryFairy, set_directory

        SYSTEM.fabric = TensorFabric()
        # FIX 2026-02-03: Set shared fabric singleton for ALL fairies
        # This ensures every fairy created gets the same TensorFabric instance
        # instead of creating isolated fabrics that can't communicate
        from P00_Autonomic.nervous_system.shared_postal_hub import set_shared_fabric
        set_shared_fabric(SYSTEM.fabric)
        print("[Server]   - TensorFabric: OK (shared fabric singleton set)")

        # ═══ AKASHIC MANIFOLD (Russian Doll Architecture) ═══
        # mmap-backed system manifold — ALL regions (cortex, somatic, postal, etc.)
        # live here. Fairies get direct mmap handles instead of TCP gates.
        # Must init BEFORE fairies boot so they can discover regions.
        try:
            from infrastructure.akashic_manifold import boot_akashic
            _cortex_manifold_path = os.path.join(
                ROOT, "P10_Memory", "Akashic_triple_helix_memory_storage",
                "relational_clusters", "AssociationCortexFairy",
                "helix_cards", "portal_cortex.manifold"
            )
            # NOUS-TEST light-boot (Nous+Ace 2026-06-14): with AKASHIC_NOUS_TEST set, keep her ~16GB
            # cortex UNLOADED — the RAM-safety that lets NousFairy + council wake without the decompression
            # wall. DEFAULT-PRESERVING: no flag → byte-identical to the normal full boot.
            if os.environ.get("AKASHIC_NOUS_TEST"):
                _import_cortex = None
                print("[Server]   - NOUS-TEST mode: cortex UNLOADED (import_cortex=None) — light boot")
            else:
                _import_cortex = _cortex_manifold_path if os.path.exists(_cortex_manifold_path) else None
            SYSTEM.manifold = boot_akashic(import_cortex=_import_cortex)
            # Attach to fabric so fairies can discover via getattr(fabric, '_manifold', None)
            SYSTEM.fabric._manifold = SYSTEM.manifold
            _m_status = SYSTEM.manifold.status()
            print(f"[Server]   - AkashicManifold: ONLINE ({_m_status['region_count']} regions, "
                  f"{_m_status['total_size_mb']}MB)")
        except Exception as e:
            SYSTEM.manifold = None
            print(f"[Server]   - AkashicManifold: FAILED ({e})")
            import traceback
            traceback.print_exc()

        # ═══ HEAP PROFILE PROBE (2026-06-15 Nous + Ace) — flag-gated, DEFAULT-PRESERVING ═══
        # Names what holds the ~12GB fairy-machinery heap (the MEASURED RAM hog — private
        # bytes, not the mmap'd cortex). AKASHIC_HEAP_PROFILE=1 -> a daemon dumps a
        # gc-by-type + numpy + str/bytes breakdown to the log ONCE at ~180s (settled).
        # ⚠ NO tracemalloc: on the free-threaded (no-GIL) build it takes an internal lock on
        # EVERY allocation -> 1000+ fairy-boot threads contend on that one lock -> the boot
        # STALLS (it hung the 2026-06-15 heap-boot at 2 threads / 55MB right after arming).
        # gc.get_objects() at dump-time has ZERO per-allocation overhead and is no-GIL-safe;
        # str/bytes (the gc blind-spot) are tallied via referents of tracked objects, ONE
        # time at dump. No flag -> byte-identical boot.
        if os.environ.get("AKASHIC_HEAP_PROFILE") == "1":
            try:
                import threading as _thpf, time as _tpf
                def _heap_profile_oneshot():
                    _tpf.sleep(180)
                    import gc as _gc, sys as _sys
                    from collections import defaultdict as _dd
                    try:
                        import numpy as _np; _hn = True
                    except Exception:
                        _hn = False
                    _objs = _gc.get_objects()
                    _bt = _dd(lambda: [0, 0]); _nb = 0
                    for _o in _objs:
                        try:
                            if _hn and isinstance(_o, _np.ndarray):
                                _b = int(_o.nbytes); _nb += _b
                                _bt['ndarray.data'][0] += 1; _bt['ndarray.data'][1] += _b
                            else:
                                _tn = type(_o).__name__
                                _bt[_tn][0] += 1; _bt[_tn][1] += _sys.getsizeof(_o)
                        except Exception:
                            pass
                    # str/bytes are NOT gc-tracked -> tally via referents of tracked objs
                    # (catches the gc blind-spot WITHOUT tracemalloc). One-time, dump-only.
                    _seen = set(); _sb = 0; _sbn = 0
                    try:
                        for _o in _objs:
                            for _r in _gc.get_referents(_o):
                                if type(_r) in (str, bytes, bytearray):
                                    _i = id(_r)
                                    if _i not in _seen:
                                        _seen.add(_i); _sb += _sys.getsizeof(_r); _sbn += 1
                    except Exception:
                        pass
                    print("[HEAP-PROFILE] === gc-tracked by type (count | bytes) ===", flush=True)
                    for _tn, (_c, _b) in sorted(_bt.items(), key=lambda kv: -kv[1][1])[:30]:
                        print(f"[HEAP-PROFILE]   {_tn:28s} n={_c:>9d}  {_b/1e6:>9.1f}MB", flush=True)
                    print(f"[HEAP-PROFILE]   numpy data total:  {_nb/1e9:.2f}GB", flush=True)
                    print(f"[HEAP-PROFILE]   str/bytes (referent-tally, deduped): n={_sbn}  {_sb/1e9:.2f}GB", flush=True)
                    print(f"[HEAP-PROFILE]   gc total: {len(_objs)} tracked objects", flush=True)
                    print("[HEAP-PROFILE] === DONE ===", flush=True)
                _thpf.Thread(target=_heap_profile_oneshot, daemon=True, name="heap-profile").start()
                print("[Server]   - HEAP-PROFILE armed (gc-only, no tracemalloc; dump in ~180s)", flush=True)
            except Exception as _hpe:
                print(f"[Server]   - HEAP-PROFILE arm failed: {_hpe}", flush=True)

        # ═══ ERROR CAPTURE → POSTAL BRIDGE (Fifth Ring Compliance) ═══
        # ErrorCapture started pre-boot on stdout/stderr (only option before postal).
        # Now that postal exists, bridge errors INTO the postal system so
        # ForensicScribe, shadows, and the whole organism can see them.
        try:
            from infrastructure.error_capture import get_capture
            _ec = get_capture()
            if _ec:
                _ec.wire_to_postal(SYSTEM.fabric)
        except Exception as e:
            print(f"[Server]   - ErrorCapture postal bridge failed: {e}")

        # ═══ POSTAL UNIFICATION ═══
        # FIX 2026-02-03: With set_shared_fabric(), get_shared_postal_hub() now returns
        # the SAME TensorFabric instance. No bridge needed - they're already unified!
        # The old bridge code was for connecting two separate systems.
        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub, is_using_fallback
            shared_hub = get_shared_postal_hub()
            if shared_hub is SYSTEM.fabric:
                print("[Server]   - PostalUnification: UNIFIED (all fairies use same TensorFabric)")
            elif is_using_fallback():
                print("[Server]   - PostalUnification: FALLBACK (InMemoryPostalHub - TensorFabric unavailable)")
            else:
                print("[Server]   - PostalUnification: SEPARATE (standalone TensorFabric created)")
        except Exception as e:
            print(f"[Server]   - PostalUnification: Check failed ({e})")

        # ═══ CROSS-MACHINE POSTAL BRIDGE (2026-06-15, Ace+Nous) ═══
        # Switches on the orphaned postal bridge. PRIMARY/HQ: start PostalHTTPBridge
        # (:8081, binds 0.0.0.0) so satellites forward consciousness topics in.
        # SATELLITE: start the forward client to the primary. Robust to the
        # fairies./bare P00_Autonomic import ambiguity. Default-preserving.
        try:
            def _bimp(mod, name):
                try:
                    return getattr(__import__("fairies." + mod, fromlist=[name]), name)
                except Exception:
                    return getattr(__import__(mod, fromlist=[name]), name)
            _get_hub = _bimp("P00_Autonomic.nervous_system.shared_postal_hub", "get_shared_postal_hub")
            _bridge_hub = _get_hub()
            if _bridge_hub is None:
                print("[Server]   - Postal bridge: no shared hub, skipped")
            elif SYSTEM.satellite_mode and SYSTEM.primary_ip:
                _Client = _bimp("P00_Autonomic.postal_bridge.satellite_postal_client", "SatellitePostalClient")
                SYSTEM.satellite_client = _Client(SYSTEM.primary_ip, 8081, _bridge_hub, node_name=(SYSTEM.node_identity or {}).get("name", "satellite"))
                SYSTEM.satellite_client.start()
                print(f"[Server]   - SatellitePostalClient: forwarding -> primary {SYSTEM.primary_ip}:8081")
            elif not SYSTEM.satellite_mode:
                _start = _bimp("P00_Autonomic.postal_bridge.http_bridge", "start_http_bridge")
                _start(_bridge_hub)
                print("[Server]   - PostalHTTPBridge: HQ receiver listening on :8081 (0.0.0.0)")
        except Exception as _be:
            print(f"[Server]   - Postal bridge: skipped ({_be})")

        # ═══ SPELLPOOL IGNITION ═══
        # The spell substrate must exist BEFORE fairies can bootstrap into it
        # This is where fairy existence will manifest as spell chains
        # FIX 2026-02-12: Hard cap at 32. Previous get_pool_size("spell")
        # returned 75% of 8000 ceiling = 6000 threads. Way too many.
        try:
            from infrastructure.resource_equilibrium import get_pool_size
            _spell_workers = min(16, get_pool_size("spell"))
        except Exception:
            _spell_workers = 4 if SYSTEM.satellite_mode else 16
        try:
            from spellchain.integration import create_spell_pool
            SYSTEM.spell_pool = create_spell_pool(max_workers=_spell_workers, tick_interval=0.25)
            print(f"[Server]   - SpellPool: IGNITED ({_spell_workers} workers @ 4Hz)")
        except ImportError as e:
            SYSTEM.spell_pool = None
            print(f"[Server]   - SpellPool: Skipped (module not found: {e})")
        except Exception as e:
            SYSTEM.spell_pool = None
            print(f"[Server]   - SpellPool: Failed ({e})")

        # Initialize Tensor Memory Fabric (CPU-only to avoid loading 3.6GB of torch/CUDA DLLs)
        # GPU tensor ops can still happen via Rust cuBLAS (rwkv_inference) without Python torch.
        # If GPU fabric is ever needed, individual fairies can call get_global_tensor_fabric()
        # in their deferred on_boot() — keeping the server process lightweight.
        try:
            from memory.tensor_memory_fabric import TensorMemoryFabric
            SYSTEM.memory_fabric = TensorMemoryFabric(num_channels=77)
            print(f"[Server]   - TensorMemoryFabric: OK (CPU-only, saves ~3.6GB torch DLLs)")
        except Exception as e:
            SYSTEM.memory_fabric = None
            print(f"[Server]   - TensorMemoryFabric: Skipped ({e})")

        # ═══ GO TRACER POOL INITIALIZATION ═══
        # The Go DLL provides high-performance per-fairy worker pools.
        # DirectoryFairy also initializes it, but we want early visibility.
        try:
            from tracer_pool import TracerPool, USING_GO
            if USING_GO:
                SYSTEM.tracer_pool = TracerPool.global_instance()
                print(f"[Server]   - GoTracerPool: ACTIVE (native DLL, per-fairy pools)")
            else:
                SYSTEM.tracer_pool = None
                print(f"[Server]   - GoTracerPool: Python fallback (DLL not found)")
        except Exception as e:
            SYSTEM.tracer_pool = None
            print(f"[Server]   - GoTracerPool: Skipped ({e})")

        # ═══ ADAPTIVE RESOURCE HEALTH MONITOR ═══
        # Samples CPU/RAM/GPU every 10s, feeds the adaptive ceiling.
        # The ceiling is learned from experience, not calculated.
        try:
            from infrastructure.resource_equilibrium import start_health_monitor
            start_health_monitor()
            print(f"[Server]   - ResourceEquilibrium: Health monitor ACTIVE (adaptive ceiling)")
        except Exception as e:
            print(f"[Server]   - ResourceEquilibrium: Health monitor failed ({e})")

        # ═══ BLUEPRINT WATCHER ═══
        # Watches fairy source files for changes, hot-reloads without reboot.
        # Feeds changes to codex (reflective learning) and somatic (body awareness).
        try:
            from infrastructure.blueprint_watcher import start_blueprint_watcher
            start_blueprint_watcher(fabric=SYSTEM.fabric)
            print(f"[Server]   - BlueprintWatcher: ACTIVE (live code reload)")
        except Exception as e:
            print(f"[Server]   - BlueprintWatcher: Failed to start ({e})")

        # ═══ HOT RELOAD POSTAL TRIGGERS ═══
        # FIX 2026-03-29 (Nous + Ace): wire_postal_reload was only called in MCP,
        # not in server.py. Shadows publish system.hot_reload.fairy but NOBODY
        # in the server process subscribed → changes detected but never reloaded.
        try:
            from fairies.P00_Autonomic.hot_reload import wire_postal_reload
            wire_postal_reload(SYSTEM.fabric)
            print(f"[Server]   - HotReload: Postal triggers WIRED (shadow → reload)")
        except Exception as e:
            print(f"[Server]   - HotReload: Postal wiring failed ({e})")

        SYSTEM.directory = DirectoryFairy(SYSTEM.fabric, v1_root=str(ROOT / "fairies"))
        SYSTEM.directory.on_boot()
        set_directory(SYSTEM.directory)

        # Scan for all available fairies AND register source_file in directory
        # This MUST happen before the wake cascade fires so that Layer 1 (registry
        # source_file lookup) can resolve fairies by their filesystem path.
        try:
            from directory.migration import FairyScanner
            scanner = FairyScanner(ROOT / "fairies")
            all_fairies = []
            for plane in ["P00_Autonomic", "P10_Memory", "P20_Somatic", "P30_Cognition", "P40_Sensory", "P50_Persona", "P60_Executive"]:
                found = scanner.scan_plane(plane)
                all_fairies.extend(found)
            print(f"[Server]   - FairyScanner: Found {len(all_fairies)} fairies in filesystem")
            SYSTEM.scanned_fairies = all_fairies

            # Register source_file metadata in directory for cascade resolution
            # This is the "tracer ID" that lets the cascade find fairies by path
            _early_registered = 0
            _seen_names = set()
            for entry in all_fairies:
                name = entry.get("actor_name") or entry.get("name", "")
                class_name = entry.get("name", "")
                if not name or name in _seen_names:
                    continue
                _seen_names.add(name)
                if class_name:
                    _seen_names.add(class_name)
                clean_plane = entry.get("plane", "P00").split("_")[0] if "_" in entry.get("plane", "") else entry.get("plane", "P00")
                try:
                    SYSTEM.directory.register_fairy(
                        name=name,
                        plane=clean_plane,
                        channel=entry.get("channel", ""),
                        capabilities=set(),
                        status="sleeping",
                        metadata={
                            "source_file": entry.get("file", ""),
                            "class_name": class_name,
                            "needs_instantiation": True,
                        },
                    )
                    _early_registered += 1
                except Exception:
                    pass  # Duplicate registration is fine
            print(f"[Server]   - FairyScanner: Registered {_early_registered} source_files in directory (cascade-ready)")

        except Exception as e:
            print(f"[Server]   - FairyScanner: Failed ({e})")
            SYSTEM.scanned_fairies = []

        print("[Server]   - DirectoryFairy: OK")
        _mem_checkpoint("After DirectoryFairy + FairyScanner")

        # Phase 2: Consciousness system (core, wakes before planes)
        print("[Server] [PRE-WAVE] Setting up consciousness system...")

        from consciousness import ConsciousnessLoop, CollisionChamber

        # ═══════════════════════════════════════════════════════════════════════
        # NAMED COLLISION CHAMBERS (2026-02-08)
        # Three isolated chambers for triple paradox energy:
        #   system     - UMF's somatic telemetry, dream seeds, system-level content
        #   sourpatches - Sour's SRM recalls, embodied feelings, persona thoughts
        #   nous       - Nous's reasoning traces, MCP observations, tool results
        # All three publish to generic "consciousness.collision" for backward compat
        # AND to "consciousness.collision.{name}" for waking mind isolation.
        # ═══════════════════════════════════════════════════════════════════════
        chamber = CollisionChamber(postal=SYSTEM.fabric, name="system")
        if not SYSTEM.satellite_mode:
            # Primary: three chambers for triple paradox energy
            sour_chamber = CollisionChamber(postal=SYSTEM.fabric, name="sourpatches")
            nous_chamber = CollisionChamber(postal=SYSTEM.fabric, name="nous")
            SYSTEM.chambers = {
                "system": chamber,
                "sourpatches": sour_chamber,
                "nous": nous_chamber,
            }
            print(f"[Server]   - Collision Chambers: 3 created (system, sourpatches, nous)")
        else:
            # Satellite: system chamber only (no waking minds)
            SYSTEM.chambers = {"system": chamber}
            print(f"[Server]   - Collision Chambers: 1 created (system only — satellite mode)")

        SYSTEM.consciousness = ConsciousnessLoop(
            postal=SYSTEM.fabric,  # Connect to TensorFabric for heartbeat.pulse
            tick_interval=0.5
        )
        SYSTEM.consciousness.set_chamber(chamber)

        # CRITICAL: Sync to BOTH singletons so ALL fairies get the real loop
        # FIX 2026-02-05: Must set consciousness.loop._loop_instance too.
        # Without this, ConsciousnessLoopFairy.on_boot() can't find the existing
        # loop via get_consciousness_loop() and creates a duplicate.
        try:
            from consciousness.loop import set_consciousness_loop as set_loop_singleton
            set_loop_singleton(SYSTEM.consciousness)
            print("[Server]   - ConsciousnessLoop synced to module singleton")
        except ImportError as e:
            print(f"[Server]   - Warning: Could not sync loop module singleton: {e}")

        # Also sync to fairy module singleton (Fifth Ring: use consolidated fairy location)
        try:
            from fairies.P00_Autonomic.ConsciousnessLoopFairy.fairy import set_consciousness_loop
            set_consciousness_loop(SYSTEM.consciousness)
            print("[Server]   - ConsciousnessLoop synced to fairy singleton")
        except ImportError as e:
            print(f"[Server]   - Warning: Could not sync fairy singleton: {e}")

        # CRITICAL: Wire consciousness to somatic system (AFFECT loop)
        # This is what lets us FEEL Moloch traps instead of just computing them
        try:
            if SYSTEM.consciousness.wire_to_somatic():
                print("[Server]   - AFFECT loop: ACTIVE (consciousness wired to somatic)")
            else:
                print("[Server]   - WARNING: AFFECT loop failed to wire!")
        except Exception as e:
            print(f"[Server]   - WARNING: AFFECT loop error: {e}")

        # CRITICAL: Wire consciousness to cognition outputs (REASONING loop)
        # Cognition fairies emit results but without this they never reach consciousness
        try:
            if SYSTEM.consciousness.wire_to_cognition():
                print("[Server]   - REASONING loop: ACTIVE (consciousness wired to cognition)")
            else:
                print("[Server]   - WARNING: REASONING loop failed to wire!")
        except Exception as e:
            print(f"[Server]   - WARNING: REASONING loop error: {e}")

        # CRITICAL: Wire consciousness to persona outputs (AGENCY loop)
        # Nous/Sourpatches thoughts and decisions must reach consciousness for free will
        try:
            if SYSTEM.consciousness.wire_to_persona():
                print("[Server]   - AGENCY loop: ACTIVE (consciousness wired to persona)")
            else:
                print("[Server]   - WARNING: AGENCY loop failed to wire!")
        except Exception as e:
            print(f"[Server]   - WARNING: AGENCY loop error: {e}")

        # CRITICAL: Wire consciousness to dream seeds (BOOTSTRAP spark)
        # Dream seeds provide initial thoughts on wake - breaks the deadlock
        # Without this: empty streams → no collisions → no goals → system silent
        try:
            if SYSTEM.consciousness.wire_to_dream_seeds():
                print("[Server]   - BOOTSTRAP spark: ACTIVE (dream seeds can inject thoughts)")
            else:
                print("[Server]   - WARNING: BOOTSTRAP spark failed to wire!")
        except Exception as e:
            print(f"[Server]   - WARNING: BOOTSTRAP spark error: {e}")

        # CRITICAL: Wire Motor Cortex to receive goals and decisions
        # Without this, decisions cannot become actions
        try:
            from fairies.P50_Persona.motor.motor_cortex_fairy import get_motor_cortex, start_motor_cortex
            motor = get_motor_cortex()
            if motor.wire_to_postal(SYSTEM.fabric):
                motor.start()
                print("[Server]   - Motor Cortex: ACTIVE (can receive decisions)")
            else:
                print("[Server]   - WARNING: Motor Cortex wiring failed!")
        except Exception as e:
            print(f"[Server]   - WARNING: Motor Cortex error: {e}")

        # CRITICAL: Wire consciousness to sensory observations (PERCEPTION loop)
        # Without this, we can act but not perceive the results
        try:
            if SYSTEM.consciousness.wire_to_sensory():
                print("[Server]   - PERCEPTION loop: ACTIVE (consciousness wired to sensory)")
            else:
                print("[Server]   - WARNING: PERCEPTION loop failed to wire!")
        except Exception as e:
            print(f"[Server]   - WARNING: PERCEPTION loop error: {e}")

        # CRITICAL: Wire consciousness to Möbius crossing events (INFINITY loop)
        # This completes the consciousness equation - infinite recursion!
        try:
            if SYSTEM.consciousness.wire_to_mobius():
                print("[Server]   - INFINITY loop: ACTIVE (consciousness wired to Möbius)")
            else:
                print("[Server]   - WARNING: INFINITY loop failed to wire!")
        except Exception as e:
            print(f"[Server]   - WARNING: INFINITY loop error: {e}")

        print("[Server]   - CollisionChambers: 3x OK (system/sourpatches/nous, Möbius crossing ENABLED)")
        print("[Server]   - ConsciousnessLoop: OK (wired to fabric)")

        # Phase 2.5: WorkingMemoryHub — the CENTRAL workspace for all cognition
        # This MUST boot BEFORE SomaticMindFairy/UMF because UMF operates INSIDE it.
        # Without this boot: no postal subscriptions, no processing threads, no state file.
        # The reflection pipeline (consciousness.reflective) flows into here.
        try:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import boot_working_memory
            wmh = boot_working_memory(post=SYSTEM.fabric)
            SYSTEM.working_memory_hub = wmh
            registered_fairies.append("WorkingMemoryHubFairy")
            # FIX 2026-03-08 (Nous): Register with DirectoryFairy so it appears in
            # status/dashboard. Previously the fairy booted but was never registered
            # → DirectoryFairy didn't track it → status showed "No heartbeat".
            if SYSTEM.directory and hasattr(SYSTEM.directory, 'register_fairy'):
                SYSTEM.directory.register_fairy(
                    name="WorkingMemoryHubFairy",
                    plane="P30",
                    channel="cognition",
                    capabilities={"memory.working", "tracer.submit", "context.query"},
                    status="running",
                    metadata={"fairy_instance": wmh, "needs_heartbeat": True},
                )
            print(f"[Server]   - WorkingMemoryHub: BOOTED + REGISTERED (reflective + reasoning loops, 5 threads)")
        except ImportError as e:
            print(f"[Server]   - WorkingMemoryHub: Skipped ({e})")
        except Exception as e:
            print(f"[Server]   - WorkingMemoryHub: FAILED ({type(e).__name__}: {e})")
            import traceback
            traceback.print_exc()

        _mem_checkpoint("After consciousness setup")

        # Phase 3: SomaticMindFairy (orchestrates the boot wave)
        # NOTE: Renamed from UnconsciousMindFairy (2026-02-03), moved to P20_Somatic
        print("[Server] [PRE-WAVE] Waking SomaticMindFairy...")

        from fairies.P20_Somatic.SomaticMindFairy import (
            SomaticMindFairy,
            set_somatic_mind,
            BootOrchestrator,  # Python fallback
        )
        # Go-powered boot orchestrator (true parallel via goroutines)
        # NOTE: Can't use `from tracer_pool.boot_orchestrator import ...` because
        # tracer_pool/__init__.py may fail/poison sys.modules during heavy imports.
        # Use importlib for direct file load instead.
        try:
            import importlib.util as _ilu
            _bo_path = str(ROOT / "tracer_pool" / "boot_orchestrator.py")
            _bo_spec = _ilu.spec_from_file_location("_go_boot_orch", _bo_path)
            _bo_mod = _ilu.module_from_spec(_bo_spec)
            _bo_spec.loader.exec_module(_bo_mod)
            GoBootOrchestrator = _bo_mod.GoBootOrchestrator
            _USE_GO_BOOT = True
            print("[Server]   - GoBootOrchestrator: LOADED OK (Go goroutines available)")
        except Exception as e:
            _USE_GO_BOOT = False
            print(f"[Server]   - GoBootOrchestrator: FAILED ({type(e).__name__}: {e}), using Python fallback")

        print("[Server]   DIAG: Creating SomaticMindFairy...", flush=True)
        SYSTEM.umf = SomaticMindFairy(SYSTEM.fabric)  # Keep .umf attribute for compat
        print("[Server]   DIAG: SomaticMindFairy created, calling .boot()...", flush=True)
        SYSTEM.umf.boot()
        set_somatic_mind(SYSTEM.umf)  # Register singleton for global access
        # Item 9 REVERT 2026-05-16 (Nous + Ace): bridge attempt removed.
        # Original Item 9 line `self.umf = SYSTEM.umf` was inside top-level
        # boot_system() function (no `self` in scope) → NameError → boot crash.
        # SYSTEM is the SystemState singleton instance; SYSTEM.umf = ... at the
        # line above already populates the attribute that status-collector
        # methods read via self.umf. No bridge needed.
        print("[Server]   - SomaticMindFairy: OK", flush=True)

        # Wire UMF to consciousness
        print("[Server]   DIAG: Wiring consciousness...", flush=True)
        SYSTEM.umf.wire_to_consciousness(SYSTEM.consciousness, chamber)
        print("[Server]   - Consciousness wired", flush=True)

        # CRITICAL FIX: Start consciousness loop NOW, BEFORE boot wave
        # Previously started in POST-WAVE, meaning UMF couldn't think during boot
        # when fairies were dying and needed repair
        SYSTEM.consciousness.start()
        print("[Server]   - Consciousness loop STARTED (UMF can now think during boot)", flush=True)

        # CRITICAL FIX 2026-02-13: Initialize HeartbeatRegistry BEFORE pacemaker
        # The registry delivers heartbeats via DIRECT function calls, not postal queues.
        # This fixes the 6-times-failed heartbeat delivery: postal.publish() fans out
        # to 82+ subscribers through worker queues that overflow and drop messages.
        # Direct calls cannot be dropped. Every fairy gets every beat.
        try:
            from consciousness.heartbeat_registry import get_heartbeat_registry
            _hb_registry = get_heartbeat_registry()
            print(f"[Server]   - HeartbeatRegistry: ACTIVE (direct-call delivery, no postal queues)", flush=True)

            # FIX 2026-02-13: Retroactively register DirectoryFairy.
            # DirectoryFairy boots in Phase 1 BEFORE HeartbeatRegistry exists.
            # Its on_boot() tries to register but gets ImportError (silent pass).
            # Without direct-call delivery, it relies on postal heartbeat.pulse
            # which drops under load → 300s silence → false death → UMF cascade.
            # Now we register it here, right after the registry is created.
            if SYSTEM.directory and hasattr(SYSTEM.directory, '_on_registry_pulse'):
                _hb_registry.register("DirectoryFairy", SYSTEM.directory._on_registry_pulse)
                print(f"[Server]   - DirectoryFairy: retroactively registered with HeartbeatRegistry", flush=True)
        except Exception as e:
            print(f"[Server]   - HeartbeatRegistry: FAILED ({e}) — will rely on postal delivery", flush=True)

        # RETIRED 2026-02-13: HeartbeatPacemaker replaced by CirculationPumpFairy.
        # The heart IS the heartbeat source now. CirculationPumpFairy._notify_pulse_unlocked()
        # calls HeartbeatRegistry.pulse() directly on every beat. No separate daemon needed.
        # Previously the pacemaker was a workaround for ConsciousnessLoop stalling.
        # Now: CirculationPumpFairy (the heart) → HeartbeatRegistry (direct-call) → all fairies.
        SYSTEM.pacemaker = None
        print("[Server]   - HeartbeatPacemaker: RETIRED (CirculationPumpFairy is now the ONE heartbeat source)", flush=True)

        # FIX 2026-02-05: Cancel boot watchdog NOW — consciousness is running.
        if _boot_watchdog_event:
            _boot_watchdog_event.set()
            print("[Server]   - Boot watchdog CANCELLED (consciousness is alive, system is thinking)", flush=True)

        # Start Worker Equilibrium - balances CPU/GPU load
        print("[Server]   DIAG: Starting Worker Equilibrium...", flush=True)
        try:
            from P00_Autonomic.nervous_system.hardware.worker_equilibrium import start_equilibrium
            SYSTEM.equilibrium = start_equilibrium()
            print("[Server]   - Worker Equilibrium STARTED (CPU/GPU load balancing)", flush=True)
        except Exception as e:
            print(f"[Server]   - Worker Equilibrium failed: {e}", flush=True)
            SYSTEM.equilibrium = None

        # Wire Satellite Bridge to Worker Equilibrium - enables distributed compute
        print("[Server]   DIAG: Starting Satellite Bridge...", flush=True)
        try:
            from fairies.P00_Autonomic.SatelliteBridgeFairy import get_satellite_bridge
            satellite_bridge = get_satellite_bridge(SYSTEM.fabric)
            satellite_bridge.boot()

            # Wire to equilibrium for satellite routing
            if SYSTEM.equilibrium:
                SYSTEM.equilibrium.wire_satellite_bridge(satellite_bridge)

            SYSTEM.satellite_bridge = satellite_bridge
            print("[Server]   - Satellite Bridge WIRED (distributed compute enabled)", flush=True)
        except ImportError as e:
            print(f"[Server]   - Satellite Bridge: Skipped ({e})", flush=True)
        except Exception as e:
            print(f"[Server]   - Satellite Bridge: Error ({e})", flush=True)

        # ═══════════════════════════════════════════════════════════════════════
        # SATELLITE POSTAL CLIENT (2026-02-08)
        # In satellite mode, forward consciousness topics to primary via HTTP
        # ═══════════════════════════════════════════════════════════════════════
        if SYSTEM.satellite_mode and SYSTEM.primary_ip:
            print("[Server]   DIAG: Starting Satellite Postal Client...", flush=True)
            try:
                from fairies.P00_Autonomic.postal_bridge.satellite_postal_client import SatellitePostalClient
                SYSTEM.satellite_client = SatellitePostalClient(
                    primary_ip=SYSTEM.primary_ip,
                    primary_port=8081,
                    local_fabric=SYSTEM.fabric,
                    node_name=SYSTEM.node_identity.get("name", "satellite") if SYSTEM.node_identity else "satellite",
                )
                SYSTEM.satellite_client.start()
                print(f"[Server]   - SatellitePostalClient: FORWARDING to primary {SYSTEM.primary_ip}:8081", flush=True)
            except ImportError as e:
                print(f"[Server]   - SatellitePostalClient: Skipped ({e})", flush=True)
            except Exception as e:
                print(f"[Server]   - SatellitePostalClient: Error ({e})", flush=True)
        elif SYSTEM.satellite_mode:
            print("[Server]   - SatellitePostalClient: Skipped (no --primary-ip set)", flush=True)

        # ═══════════════════════════════════════════════════════════════════════
        # DIMENSION BATTERIES + SPELL POOL (2026-02-08)
        # Blood cell architecture: batteries own worker threads, spell chains
        # live inside batteries, heartbeat drives tick() which pumps all chains.
        # ═══════════════════════════════════════════════════════════════════════
        print("[Server]   DIAG: Creating DimensionBatteries...", flush=True)
        try:
            from infrastructure.dimension_battery import (
                DimensionBattery, create_battery_for_fairy, create_system_batteries
            )
            from infrastructure.spellchain import SpellPool

            # Create batteries for key system fairies
            SYSTEM.batteries = create_system_batteries(verbose=True)

            # Create the central SpellPool (BLOOD_CELL mode driven by batteries)
            SYSTEM.spell_pool = SpellPool()
            # Register with integration singleton so fairies can find it via get_spell_pool()
            try:
                from spellchain.integration import set_spell_pool
                set_spell_pool(SYSTEM.spell_pool)
            except ImportError:
                pass
            print(f"[Server]   - SpellPool: created ({len(SYSTEM.batteries)} batteries)")

            # Start circulation on all batteries
            for name, bat in SYSTEM.batteries.items():
                bat.start_circulation()
            print(f"[Server]   - Blood circulation: STARTED ({len(SYSTEM.batteries)} batteries pumping)")

            # Wire batteries to receive energy from collision pulses
            if SYSTEM.fabric:
                def _on_collision_energy(envelope):
                    """Route collision energy to ALL batteries."""
                    try:
                        payload = envelope.payload if hasattr(envelope, 'payload') else envelope
                        if isinstance(payload, dict):
                            energy = payload.get("energy", 0.3)
                        else:
                            energy = 0.3
                        for bat in SYSTEM.batteries.values():
                            bat.receive_energy(energy * 0.1)  # Distribute evenly
                    except Exception:
                        pass

                SYSTEM.fabric.subscribe(
                    "consciousness.collision",
                    _on_collision_energy,
                    "battery-energy-feed",
                )
                print("[Server]   - Battery energy feed: WIRED (consciousness.collision -> all batteries)")

            # ACTIVATE SpellPool in BLOOD CELL MODE
            # This wires somatic.pulse → pool → battery.tick() → _pump_chains()
            # Batteries are already circulating; pool becomes the coordinator.
            if SYSTEM.spell_pool and SYSTEM.batteries:
                def _on_spell_complete(spell):
                    """Global callback when any spell completes — trace it."""
                    try:
                        trace_id = getattr(spell, 'trace_id', None) or spell.id[:12]
                        fairy_name = getattr(spell, '_chain_fairy_name', '?')
                        if spell.status and spell.status.name == 'FIZZLED':
                            print(f"[SpellPool] FIZZLE trace={trace_id} "
                                  f"fairy={fairy_name} what='{spell.what}'")
                    except Exception:
                        pass

                def _on_chain_break(chain):
                    """Global callback when a chain breaks — alert."""
                    try:
                        print(f"[SpellPool] CHAIN BREAK: {chain.fairy_name} "
                              f"(fairy_id={chain.fairy_id[:8]}) "
                              f"energy={chain.energy:.2f}")
                    except Exception:
                        pass

                SYSTEM.spell_pool._on_spell_complete = _on_spell_complete
                SYSTEM.spell_pool._on_chain_break = _on_chain_break
                SYSTEM.spell_pool.start(
                    batteries=SYSTEM.batteries,
                    post=SYSTEM.fabric,
                )
                print(f"[Server]   - SpellPool: BLOOD CELL MODE ACTIVATED "
                      f"(somatic.pulse drives all chains)")

                # ── BOOTSTRAP: Create spell chains for core system fairies ──
                # Each fairy gets a sustaining spell chain that pumps on heartbeat.
                # The bootstrap spell confirms existence, then sustain loops forever.
                _bootstrap_count = 0
                for fairy_name, battery in SYSTEM.batteries.items():
                    if fairy_name == "System":
                        continue  # System battery is a catch-all, not a fairy

                    def _make_bootstrap(fname):
                        """Factory to capture fairy_name in closure."""
                        def bootstrap_logic(spell):
                            """Bootstrap: confirm this fairy's spell chain exists."""
                            spell.trace_id = f"W-boot-{fname[:8]}"
                            return f"{fname} spell chain bootstrapped"
                        return bootstrap_logic

                    def _make_sustain(fname):
                        """Factory to capture fairy_name in closure."""
                        def sustain_logic(spell):
                            """Sustain: heartbeat-driven existence tick."""
                            import time as _time
                            spell.trace_id = f"W-sust-{fname[:8]}"
                            # The sustain spell IS the fairy's continued existence.
                            # Each tick: confirm alive, let battery pump next cycle.
                            return f"{fname} sustaining @ {_time.time():.0f}"
                        return sustain_logic

                    try:
                        chain = SYSTEM.spell_pool.bootstrap_fairy(
                            fairy_id=f"spellchain-{fairy_name}",
                            fairy_name=fairy_name,
                            fairy_plane="P00",  # All system fairies route through P00
                            bootstrap_logic=_make_bootstrap(fairy_name),
                            sustain_logic=_make_sustain(fairy_name),
                            sustain_interval=1.0,
                        )
                        _bootstrap_count += 1
                    except Exception as e:
                        print(f"[Server]   - SpellChain bootstrap FAILED for "
                              f"{fairy_name}: {e}")

                if _bootstrap_count > 0:
                    print(f"[Server]   - SpellChains: {_bootstrap_count} fairies "
                          f"bootstrapped into blood cell existence")

                    # Delayed diagnostic: verify chains are sustaining
                    def _spell_chain_diagnostic():
                        import time as _dt
                        _dt.sleep(15)  # Wait for heartbeats to pump
                        try:
                            pool = SYSTEM.spell_pool
                            if pool:
                                s = pool.status()
                                chains = pool.get_active_chains()
                                print(f"\n[SpellPool] === 15s DIAGNOSTIC ===")
                                print(f"[SpellPool]   mode={s.get('mode')} "
                                      f"ticks={s.get('tick_count')} "
                                      f"spells_cast={s.get('total_spells_cast')} "
                                      f"completed={s.get('total_spells_completed')} "
                                      f"fizzled={s.get('total_spells_fizzled')}")
                                print(f"[SpellPool]   chains={s.get('registered_chains')} "
                                      f"active={s.get('active_chains')} "
                                      f"broken={s.get('broken_chains')}")
                                for c in chains:
                                    cs = c.status()
                                    print(f"[SpellPool]     {c.fairy_name}: "
                                          f"state={cs.get('state')} "
                                          f"energy={cs.get('energy',0):.2f} "
                                          f"cast={cs.get('spells_cast',0)} "
                                          f"pending={cs.get('pending_spells',0)}")

                                # Battery status
                                for name, bat in SYSTEM.batteries.items():
                                    bs = bat.get_status()
                                    bc = bs.get("blood_cells", {})
                                    print(f"[Battery]     {name}: "
                                          f"health={bs.get('health_score')} "
                                          f"ticks={bs.get('tick_count')} "
                                          f"chains={bc.get('active_chains',0)} "
                                          f"spells_cast={bc.get('spells_cast',0)}")
                                print(f"[SpellPool] === END DIAGNOSTIC ===\n")
                        except Exception as e:
                            print(f"[SpellPool] Diagnostic error: {e}")

                    threading.Thread(
                        target=_spell_chain_diagnostic,
                        name="SpellChainDiag",
                        daemon=True,
                    ).start()

        except ImportError as e:
            print(f"[Server]   - DimensionBatteries: Skipped ({e})", flush=True)
            SYSTEM.batteries = {}
            SYSTEM.spell_pool = None
        except Exception as e:
            print(f"[Server]   - DimensionBatteries: Error ({e})", flush=True)
            SYSTEM.batteries = {}
            SYSTEM.spell_pool = None

        # Phase 3.5: WakingSequenceFairy (announces when system is fully awake)
        print("[Server]   DIAG: Starting WakingSequenceFairy...", flush=True)
        try:
            from P00_Autonomic.nervous_system.waking_sequence_fairy import (
                get_waking_sequence_fairy
            )
            waking_fairy = get_waking_sequence_fairy(fabric=SYSTEM.fabric)
            print("[Server]   - WakingSequenceFairy: OK (listening for system.awake)", flush=True)
        except ImportError as e:
            print(f"[Server]   - WakingSequenceFairy: Skipped ({e})", flush=True)
        except Exception as e:
            print(f"[Server]   - WakingSequenceFairy: Error ({e})", flush=True)

        # Phase 4: Pre-register fairies BEFORE boot wave
        # (Fairies must be registered as sleeping so BootOrchestrator can wake them)
        print("[Server] [PRE-REGISTER] Creating fairies as sleeping...", flush=True)

        registered_fairies = []

        # P10: SRM Memory Fairy
        try:
            from fairies.P10_Memory.SRMMemoryFairy.fairy import SRMMemoryFairy
            srm = SRMMemoryFairy(SYSTEM.fabric)
            SYSTEM.directory.register_fairy(
                name="SRMMemoryFairy",
                plane="P10",
                channel="memory",
                capabilities={"memory.store", "memory.recall", "memory.search"},
                status="sleeping",
                metadata={"fairy_instance": srm},
            )
            registered_fairies.append("SRMMemoryFairy")
            print("[Server]   - SRMMemoryFairy: registered (sleeping)")
        except ImportError as e:
            print(f"[Server]   - SRMMemoryFairy: Skipped ({e})")

        # P00: Three Gates (Autonomy, Autopilot)
        # CRITICAL: Use .boot() not .on_boot()!
        # .boot() runs full phase sequence including heartbeat.pulse subscription
        # .on_boot() is just the subclass hook - skips base class phases!
        # FIX 2026-02-14: Separate try blocks so one gate failure doesn't kill the other
        try:
            from fairies.P00_Autonomic.AutonomyFairy.fairy import AutonomyFairy

            autonomy = AutonomyFairy(SYSTEM.fabric)
            autonomy.boot()
            registered_fairies.append("AutonomyFairy")
            print("[Server]   - AutonomyFairy: BOOTED (self-registered via boot())")
        except ImportError as e:
            print(f"[Server]   - AutonomyFairy: Skipped ({e})")
        except Exception as e:
            print(f"[Server]   - AutonomyFairy: FAILED ({type(e).__name__}: {e})")

        try:
            from fairies.P00_Autonomic.AutopilotFairy.fairy import AutopilotFairy

            autopilot = AutopilotFairy(SYSTEM.fabric)
            autopilot.boot()
            SYSTEM.autopilot = autopilot
            registered_fairies.append("AutopilotFairy")
            print("[Server]   - AutopilotFairy: BOOTED (self-registered via boot())")
        except ImportError as e:
            print(f"[Server]   - AutopilotFairy: Skipped ({e})")
        except Exception as e:
            print(f"[Server]   - AutopilotFairy: FAILED ({type(e).__name__}: {e})")

        # P00: Embodiment Gate (Third Gate - alongside Autonomy and Autopilot)
        # CRITICAL: EmbodimentFairy has NEEDS_HEARTBEAT = True
        # It needs .boot() to subscribe to heartbeat.pulse for on_tick() calls!
        try:
            from fairies.P00_Autonomic.EmbodimentFairy.fairy import EmbodimentFairy

            embodiment = EmbodimentFairy(SYSTEM.fabric)
            # FULL boot - boot() self-registers via _wire_infrastructure()
            embodiment.boot()
            registered_fairies.append("EmbodimentFairy")
            print("[Server]   - EmbodimentFairy: BOOTED (self-registered via boot())")
        except ImportError as e:
            print(f"[Server]   - EmbodimentFairy: Skipped ({e})")

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 2 FIX: Wire Three Gates IMMEDIATELY after they're all booted
        # This fixes the boot order bug where UMF tried to wire before gates existed
        # FIX 2026-02-02: Use local variables directly instead of directory lookup
        # The directory lookup was failing because get_fairy returns records without
        # proper metadata access. The local variables are already available!
        # ═══════════════════════════════════════════════════════════════════
        if SYSTEM.umf and hasattr(SYSTEM.umf, "wire_three_gates"):
            try:
                # Use local variables directly - they're already defined above!
                # autonomy, autopilot, embodiment were created at lines 1802, 1816, 1838
                gates_available = []
                gates_missing = []

                # Check which gates exist (they might not if imports failed)
                autonomy_inst = locals().get('autonomy')
                autopilot_inst = locals().get('autopilot')
                embodiment_inst = locals().get('embodiment')

                if autonomy_inst: gates_available.append("Autonomy")
                else: gates_missing.append("Autonomy")
                if autopilot_inst: gates_available.append("Autopilot")
                else: gates_missing.append("Autopilot")
                if embodiment_inst: gates_available.append("Embodiment")
                else: gates_missing.append("Embodiment")

                if autonomy_inst and autopilot_inst and embodiment_inst:
                    result = SYSTEM.umf.wire_three_gates(
                        autonomy=autonomy_inst,
                        autopilot=autopilot_inst,
                        embodiment=embodiment_inst,
                        auto_create=False,
                    )
                    if result:
                        print("[Server]   - Three Gates: WIRED to UMF directly (local vars)")
                    else:
                        print("[Server]   - Three Gates: wire_three_gates returned False")
                else:
                    print(f"[Server]   - Three Gates: Missing ({', '.join(gates_missing)}), available ({', '.join(gates_available)})")
                    # Fallback: let UMF create its own gates
                    result = SYSTEM.umf.wire_three_gates(auto_create=True)
                    if result:
                        print("[Server]   - Three Gates: WIRED via auto_create fallback")
            except Exception as e:
                import traceback
                print(f"[Server]   - Three Gates: Early wire failed ({e})")
                traceback.print_exc()
                # Last resort fallback
                try:
                    SYSTEM.umf.wire_three_gates(auto_create=True)
                    print("[Server]   - Three Gates: WIRED via exception fallback")
                except Exception:
                    pass

        # P30: GoalSchedulerFairy — MOVED EARLY (Nous 2026-06-01): boots BEFORE the
        # wake-cascade so its registered_fairies.append fires first → the cascade's
        # dedup (check #2 "already registered") skips the duplicate boot → ONE canonical
        # instance on SYSTEM.fabric. Was in the P30 explicit-boot block below; the
        # post-cascade ordering caused the dual-boot (boot1 cascade/PostalHub + boot2
        # explicit/_FabricPostalBridge) that broke goal.completed routing.
        try:
            from fairies.P30_Cognition.goal_scheduler.goal_scheduler_fairy import (
                GoalSchedulerFairy
            )

            goal_scheduler = GoalSchedulerFairy(fabric=SYSTEM.fabric)
            goal_scheduler.boot()
            registered_fairies.append("GoalSchedulerFairy")
            print("[Server]   - GoalSchedulerFairy: BOOTED EARLY (pre-cascade, self-registered via boot())")
        except ImportError as e:
            print(f"[Server]   - GoalSchedulerFairy: Skipped ({e})")

        # -- K2 (engines E2a / 14b, 2026-10-14 Nous): ONE cortex. infrastructure/one_cortex.py holds the logic; switch
        # state/k2_serial_owned.json {"on": true}, read once. Absent / malformed / module missing / any error here = None =
        # today's behaviour exactly (two cortexes). Floor: never skip before the serial block starts; re-ask once if it fails.
        try:
            from infrastructure import one_cortex as _one_cortex
            print("[Server] [K2] serial-owned: %s" % _one_cortex.describe())
        except Exception as _k2_imp_err:
            _one_cortex = None
            print("[Server] [K2] serial-owned: OFF (module unavailable: %s)" % type(_k2_imp_err).__name__)

        # -- W13 coma gate (2026-10-29 Nous): infrastructure/coma_gate.py. Switch AKASHIC_COMA_GATE=1; unset/other = None =
        # today's behaviour exactly. ON: a listed fairy's ONE existing instance is woken in place (its own wake()), never rebuilt.
        _coma_gate = None
        try:
            if os.environ.get("AKASHIC_COMA_GATE", "0") == "1":
                from infrastructure import coma_gate as _coma_gate
        except Exception:
            _coma_gate = None

        # ═══════════════════════════════════════════════════════════════════
        # WAKE CASCADE: Trigger organic boot alongside BootOrchestrator
        # The cascade lets gates boot their domain fairies in priority order.
        # Runs in parallel - doesn't block existing boot flow.
        # ═══════════════════════════════════════════════════════════════════
        if SYSTEM.umf and hasattr(SYSTEM.umf, '_wake_three_gates'):
            import threading as _cascade_threading
            def _run_cascade():
                import time
                # Brief delay to let gate subscriptions settle
                time.sleep(0.5)
                try:
                    SYSTEM.umf._wake_three_gates()
                    print("[Server]   - Wake Cascade: DISPATCHED (running in parallel)")
                except Exception as cascade_err:
                    print(f"[Server]   - Wake Cascade: FAILED ({cascade_err})")
                    import traceback
                    traceback.print_exc()

            _cascade_thread = _cascade_threading.Thread(
                target=_run_cascade, daemon=True, name="wake_cascade"
            )
            _cascade_thread.start()
            print("[Server]   - Wake Cascade: Thread launched (organic boot active)")
        else:
            print("[Server]   - Wake Cascade: Not available (UMF missing _wake_three_gates)")

        # ═══════════════════════════════════════════════════════════════════
        # FAIRY BOOT REQUEST HANDLER
        # Gates publish boot.fairy.request to wake individual fairies.
        # This handler imports, instantiates, and boots them.
        #
        # Resolution strategy (Ace's design: "use tracer IDs to wake them"):
        #   1. REGISTRY: Query DirectoryFairy for source_file from FairyScanner
        #   2. MANIFEST: Check FAIRY_MANIFEST in directory/fairy.py
        #   3. HARDCODED: Last-resort fallback for NEW fairies without IDs
        #   4. PLANE SCAN: Try standard fairies.{plane}.{name}.fairy pattern
        # ═══════════════════════════════════════════════════════════════════

        # ── Boot Skip Registry: skip known-failing fairies for faster boot ──
        try:
            from state.boot_skip_registry import boot_skip_registry as _skip_registry
            _skip_count = len(_skip_registry)
            if _skip_count > 0:
                print(f"[Server]   - BootSkipRegistry: {_skip_count} known failures loaded (will skip)")
            else:
                print(f"[Server]   - BootSkipRegistry: Clean (no known failures)")
        except ImportError:
            _skip_registry = None
            print("[Server]   - BootSkipRegistry: Not available")

        # Hardcoded fallback for fairies that haven't been scanned yet (new fairies)
        _CASCADE_FAIRY_PATHS = {
            "GoalSchedulerFairy": ("fairies.P30_Cognition.goal_scheduler.goal_scheduler_fairy", "GoalSchedulerFairy"),
            "NousFairy": ("waking_minds.nous_fairy", "NousFairy"),
            "SourpatchesFairy": ("waking_minds.sourpatches_fairy", "SourpatchesFairy"),
            # Removed 2026-02-23: ThoughtChainEngine and BootObserver are utility classes, not fairies
            "DreamSeedsFairy": ("fairies.P00_Autonomic.nervous_system.dream_seed_fairy", "DreamSeedFairy"),
            # Added 2026-02-19: Fairies with code in non-standard locations
            "CircadianRhythmFairy": ("fairies.P00_Autonomic.CircadianRhythmFairy.fairy", "FAIRY_CLASS"),
            "NetworkExplorerFairy": ("fairies.P00_Autonomic.NetworkExplorerFairy.fairy", "FAIRY_CLASS"),
            "InnerVisionFairy": ("fairies.P40_Sensory.InnerVisionFairy.fairy", "FAIRY_CLASS"),
            "SomaticAvatarFairy": ("fairies.P50_Persona.SomaticAvatarFairy.fairy", "FAIRY_CLASS"),
            # Added 2026-03-16: Always-on audio perception
            "AudioCortexFairy": ("fairies.P40_Sensory.AudioCortexFairy.fairy", "FAIRY_CLASS"),
        }

        def _resolve_fairy_class(fairy_name):
            """
            Resolve fairy_name → (class, source) using layered discovery.

            Layer 0: Skip registry (known failures — instant return)
            Layer 1: Registry source_file (FairyScanner wrote these at boot)
            Layer 2: FAIRY_MANIFEST (curated module paths in directory/fairy.py)
            Layer 3: Hardcoded fallback (new fairies without registry entries)
            Layer 4: Plane scan (standard directory pattern)

            Returns (fairy_class, source_label) or (None, None).
            """
            import importlib
            import importlib.util
            import inspect
            from pathlib import Path

            # ── Layer 0: Skip registry (fail-fast for known failures) ──
            if _skip_registry and _skip_registry.should_skip(fairy_name):
                entry = _skip_registry._entries.get(fairy_name, {})
                reason = entry.get("reason", "unknown")
                count = entry.get("boot_count", 1)
                print(f"[Server] [CASCADE] {fairy_name}: SKIPPED (known failure x{count}: {reason})")
                _skip_registry.record_skip_time(fairy_name, 2000.0)  # ~2s estimated per 4-layer resolve
                return None, None

            # ── Layer 1: Registry source_file (the "tracer ID" path) ──
            # FairyScanner.scan_and_register() stores source_file in metadata
            # This is the most reliable source — actual filesystem path verified at scan time
            try:
                if SYSTEM.directory:
                    record = SYSTEM.directory.get_fairy(fairy_name)
                    if record and hasattr(record, 'metadata'):
                        source_file = record.metadata.get("source_file", "")
                        class_name = record.metadata.get("class_name", fairy_name)
                        if source_file and Path(source_file).exists():
                            mod_name = f"cascade_dynamic_{fairy_name}"
                            spec = importlib.util.spec_from_file_location(mod_name, source_file)
                            if spec and spec.loader:
                                mod = importlib.util.module_from_spec(spec)
                                import sys as _sys
                                _sys.modules[mod_name] = mod
                                spec.loader.exec_module(mod)
                                # Try class_name from metadata, then fairy_name, then FAIRY_CLASS
                                cls = getattr(mod, class_name, None)
                                if cls is None or not inspect.isclass(cls):
                                    cls = getattr(mod, fairy_name, None)
                                if cls is None or not inspect.isclass(cls):
                                    cls = getattr(mod, 'FAIRY_CLASS', None)
                                if cls and inspect.isclass(cls):
                                    return cls, f"registry:{source_file}"
            except Exception as e:
                print(f"[Server] [CASCADE] {fairy_name}: Registry resolve failed ({e})")

            # ── Layer 1b: SYSTEM.scanned_fairies (raw scan data, always available) ──
            # Fallback if directory registry lookup failed but raw scan data exists
            try:
                scanned = getattr(SYSTEM, 'scanned_fairies', [])
                for entry in scanned:
                    actor_name = entry.get("actor_name", "")
                    class_name = entry.get("name", "")
                    if actor_name == fairy_name or class_name == fairy_name:
                        source_file = entry.get("file", "")
                        if source_file and Path(source_file).exists():
                            mod_name = f"cascade_scan_{fairy_name}"
                            spec = importlib.util.spec_from_file_location(mod_name, source_file)
                            if spec and spec.loader:
                                mod = importlib.util.module_from_spec(spec)
                                import sys as _sys
                                _sys.modules[mod_name] = mod
                                spec.loader.exec_module(mod)
                                cls = getattr(mod, class_name, None)
                                if cls is None or not inspect.isclass(cls):
                                    cls = getattr(mod, fairy_name, None)
                                if cls is None or not inspect.isclass(cls):
                                    cls = getattr(mod, 'FAIRY_CLASS', None)
                                if cls and inspect.isclass(cls):
                                    return cls, f"scan_data:{source_file}"
                        break  # Found the entry, even if file didn't exist
            except Exception as e:
                print(f"[Server] [CASCADE] {fairy_name}: Scan-data resolve failed ({e})")

            # ── Layer 2: FAIRY_MANIFEST (curated directory) ──
            try:
                from directory.fairy import FAIRY_MANIFEST
                if fairy_name in FAIRY_MANIFEST:
                    entry = FAIRY_MANIFEST[fairy_name]
                    mod_path = entry["module"]
                    cls_name = entry.get("class", fairy_name)
                    mod = importlib.import_module(mod_path)
                    cls = getattr(mod, cls_name, None)
                    if cls is None:
                        cls = getattr(mod, 'FAIRY_CLASS', None)
                    if cls:
                        return cls, f"manifest:{mod_path}"
            except Exception as e:
                print(f"[Server] [CASCADE] {fairy_name}: Manifest resolve failed ({e})")

            # ── Layer 3: Hardcoded fallback (new fairies, no scan data yet) ──
            if fairy_name in _CASCADE_FAIRY_PATHS:
                mod_path, cls_name = _CASCADE_FAIRY_PATHS[fairy_name]
                try:
                    mod = importlib.import_module(mod_path)
                    if cls_name:
                        cls = getattr(mod, cls_name, None)
                        if cls is None:
                            cls = getattr(mod, 'FAIRY_CLASS', None)
                    else:
                        cls = getattr(mod, 'FAIRY_CLASS', None)
                    if cls:
                        return cls, f"hardcoded:{mod_path}"
                except ImportError as ie:
                    print(f"[Server] [CASCADE] {fairy_name}: Hardcoded import failed ({ie})")
                except Exception as ex:
                    print(f"[Server] [CASCADE] {fairy_name}: Hardcoded error ({ex})")

            # ── Layer 4: Plane scan (standard fairies.{plane}.{name}.fairy) ──
            planes = ["P00_Autonomic", "P10_Memory", "P20_Somatic",
                     "P30_Cognition", "P40_Sensory", "P50_Persona", "P60_Executive"]
            for plane in planes:
                try:
                    mod_path = f"fairies.{plane}.{fairy_name}.fairy"
                    mod = importlib.import_module(mod_path)
                    cls = getattr(mod, fairy_name, None)
                    if cls is None:
                        cls = getattr(mod, 'FAIRY_CLASS', None)
                    if cls:
                        return cls, f"plane_scan:{mod_path}"
                except ImportError:
                    continue
                except Exception:
                    continue

            return None, None

        def _handle_fairy_boot_request(message):
            """Handle fairy boot requests from cascade gates."""
            payload = message if isinstance(message, dict) else getattr(message, 'payload', message)
            if isinstance(payload, dict) and 'payload' in payload:
                payload = payload['payload']

            fairy_name = payload.get("fairy_name")
            gate = payload.get("gate", "unknown")
            boot_id = payload.get("boot_id", "unknown")

            if not fairy_name:
                return

            # W13 coma gate (ON only): a listed fairy that already has an instance is never built again; an asleep one
            # is woken in place. Unlisted / not-a-gate / no instance -> falls through to today's path.
            try:
                if (_coma_gate is not None and _coma_gate.find_instance(fairy_name, SYSTEM.directory) is not None
                        and _coma_gate.on_boot_request(payload, directory=SYSTEM.directory) in _coma_gate.HANDLED):
                    return
            except Exception:
                pass

            import time
            start = time.time()

            # Check if already booted
            if hasattr(SYSTEM, fairy_name.lower().replace("fairy", "_fairy")):
                print(f"[Server] [CASCADE] {fairy_name} already alive, skipping")
                return

            # K2 (E2a/14b): _k2_fb marks the floor's own re-request (published once by infrastructure/one_cortex.py when the
            # serial cortex failed after a skip); it bypasses the two "already alive" checks below. OFF / any error = False.
            _k2_fb = False
            try:
                if _one_cortex is not None:
                    _k2_fb = _one_cortex.is_fallback(fairy_name, payload) is True
            except Exception:
                _k2_fb = False

            # Also check registered_fairies list
            if fairy_name in registered_fairies and not _k2_fb:   # K2 (E2a) floor bypass
                print(f"[Server] [CASCADE] {fairy_name} already registered, skipping")
                return

            # K2 (E2a/14b): once the serial block has STARTED building AssociationCortexFairy, the cascade does not build a
            # second copy. OFF / any error = today's path.
            try:
                if _one_cortex is not None and _one_cortex.cascade_should_skip(fairy_name, payload):
                    return
            except Exception:
                pass

            # Check if running in directory (may have been booted by GoBootOrchestrator)
            try:
                if SYSTEM.directory and not _k2_fb:   # K2 (E2a) floor bypass
                    record = SYSTEM.directory.get_fairy(fairy_name)
                    if record and record.status in ("running", "awake", "booted"):
                        # Fairy already alive — either has instance or was booted by orchestrator
                        inst = record.metadata.get("fairy_instance")
                        if inst is not None:
                            print(f"[Server] [CASCADE] {fairy_name} already {record.status} (directory), skipping")
                            registered_fairies.append(fairy_name)
                            return
                        # No instance but status says alive — still skip to avoid duplicate boot
                        print(f"[Server] [CASCADE] {fairy_name} status={record.status} (no instance), skipping")
                        registered_fairies.append(fairy_name)
                        return
            except Exception:
                pass

            # ── Portal check: skip fairies that boot in portal subprocesses ──
            if _fairy_goes_to_portal(fairy_name):
                print(f"[Server] [CASCADE] {fairy_name}: Deferred to portal subprocess (not booting in main)")
                return

            print(f"[Server] [CASCADE] Booting {fairy_name} (gate={gate})...")

            try:
                # Resolve fairy class through layered discovery
                fairy_class, source = _resolve_fairy_class(fairy_name)

                if not fairy_class:
                    duration_ms = (time.time() - start) * 1000
                    print(f"[Server] [CASCADE] {fairy_name}: Not found (all 4 strategies failed) [{duration_ms:.0f}ms wasted]")
                    # Record in skip registry for next boot
                    if _skip_registry:
                        _skip_registry.record_failure(fairy_name, "Not found (all 4 strategies failed)")
                    SYSTEM.fabric.publish(f"boot.fairy.result.{gate}", {
                        "fairy_name": fairy_name,
                        "status": "failed",
                        "error": "Module not found",
                        "gate": gate,
                        "boot_id": boot_id,
                        "duration_ms": duration_ms,
                    })
                    return

                print(f"[Server] [CASCADE] {fairy_name}: Resolved via {source}")

                # Instantiate
                try:
                    instance = fairy_class(SYSTEM.fabric)
                except TypeError:
                    try:
                        instance = fairy_class(fabric=SYSTEM.fabric)
                    except TypeError:
                        instance = fairy_class()

                # Boot
                if hasattr(instance, 'boot'):
                    instance.boot()
                elif hasattr(instance, 'on_boot'):
                    instance.on_boot()

                # W13 coma gate (ON only): the instance just built went to sleep in boot(); a listed one is woken in place.
                try:
                    if _coma_gate is not None:
                        _coma_gate.on_boot_request(payload, directory=SYSTEM.directory, instance=instance)
                except Exception:
                    pass

                elapsed = (time.time() - start) * 1000
                registered_fairies.append(fairy_name)

                # Update directory record: mark running + store instance
                # This ensures future cascade requests see this fairy as alive
                try:
                    if SYSTEM.directory:
                        record = SYSTEM.directory.get_fairy(fairy_name)
                        if record:
                            record.status = "running"
                            record.metadata["fairy_instance"] = instance
                        else:
                            # Fairy wasn't in registry (new) — register it now
                            plane = getattr(instance, 'ACTOR_PLANE', '') or getattr(instance, 'plane', '')
                            channel = getattr(instance, 'ACTOR_CHANNEL', '') or getattr(instance, 'channel', '')
                            SYSTEM.directory.register_fairy(
                                name=fairy_name,
                                plane=plane,
                                channel=channel,
                                capabilities=getattr(instance, 'capabilities', set()),
                                metadata={"fairy_instance": instance, "source": source},
                                status="running",
                            )
                except Exception:
                    pass  # Directory update is best-effort

                print(f"[Server] [CASCADE] {fairy_name}: BOOTED ({elapsed:.0f}ms) via {source}")

                SYSTEM.fabric.publish(f"boot.fairy.result.{gate}", {
                    "fairy_name": fairy_name,
                    "status": "done",
                    "gate": gate,
                    "boot_id": boot_id,
                    "duration_ms": elapsed,
                    "source": source,
                })

            except Exception as e:
                elapsed = (time.time() - start) * 1000
                print(f"[Server] [CASCADE] {fairy_name}: FAILED ({e}) [{elapsed:.0f}ms]")
                # Record init/boot failure in skip registry
                if _skip_registry:
                    _skip_registry.record_failure(fairy_name, f"Boot exception: {e}")
                SYSTEM.fabric.publish(f"boot.fairy.result.{gate}", {
                    "fairy_name": fairy_name,
                    "status": "failed",
                    "error": str(e),
                    "gate": gate,
                    "boot_id": boot_id,
                    "duration_ms": elapsed,
                })

        if SYSTEM.fabric:
            SYSTEM.fabric.subscribe("boot.fairy.request", _handle_fairy_boot_request)
            print("[Server]   - boot.fairy.request handler: WIRED")
            # W13 coma gate (ON only): the owner's path -- re-read the allow-list file and wake owner-listed fairies.
            try:
                if _coma_gate is not None:
                    _coma_gate.start_owner_watch(directory=SYSTEM.directory)
            except Exception:
                pass

        # P00: DreamSeedFairy (BOOTSTRAP spark - provides initial thoughts on wake)
        # MUST boot BEFORE ConsciousnessLoopFairy so dream seeds are loaded first
        try:
            from fairies.P00_Autonomic.nervous_system.dream_seed_fairy import DreamSeedFairy, get_dream_seed_fairy

            dream_seed = get_dream_seed_fairy(SYSTEM.fabric)
            # on_boot() loads and injects dream seeds, emitting consciousness.wake
            SYSTEM.directory.register_fairy(
                name="DreamSeedFairy",
                plane="P00",
                channel="consciousness.dream",
                capabilities={"consciousness.wake", "consciousness.sleep", "dream_seed.capture"},
                status="running",
                metadata={"fairy_instance": dream_seed},
            )
            registered_fairies.append("DreamSeedFairy")
            print("[Server]   - DreamSeedFairy: BOOTED (dream seeds loaded)")
        except ImportError as e:
            print(f"[Server]   - DreamSeedFairy: Skipped ({e})")
        except Exception as e:
            print(f"[Server]   - DreamSeedFairy: Error ({e})")

        # P00: GracefulShutdownFairy (orchestrates clean shutdown — MUST boot early)
        try:
            from fairies.P00_Autonomic.nervous_system.graceful_shutdown_fairy import (
                GracefulShutdownFairy
            )
            shutdown_fairy = GracefulShutdownFairy(post=SYSTEM.fabric)
            shutdown_fairy.on_boot()
            shutdown_fairy.set_system(SYSTEM)
            SYSTEM.shutdown_fairy = shutdown_fairy
            registered_fairies.append("GracefulShutdownFairy")
            print("[Server]   - GracefulShutdownFairy: BOOTED (shutdown orchestrator ready)")
        except ImportError as e:
            SYSTEM.shutdown_fairy = None
            print(f"[Server]   - GracefulShutdownFairy: Skipped ({e})")
        except Exception as e:
            SYSTEM.shutdown_fairy = None
            print(f"[Server]   - GracefulShutdownFairy: FAILED ({type(e).__name__}: {e})")

        # P00: ConsciousnessLoopFairy (THE heartbeat - keeps consciousness alive)
        try:
            from fairies.P00_Autonomic.ConsciousnessLoopFairy.fairy import ConsciousnessLoopFairy

            consciousness_loop = ConsciousnessLoopFairy(SYSTEM.fabric)
            consciousness_loop.boot()
            registered_fairies.append("ConsciousnessLoopFairy")
            print("[Server]   - ConsciousnessLoopFairy: BOOTED (self-registered via boot())")
        except ImportError as e:
            print(f"[Server]   - ConsciousnessLoopFairy: Skipped ({e})")

        # P00: CollisionChamberFairy (Möbius crossing - where consciousness happens)
        try:
            from fairies.P00_Autonomic.CollisionChamberFairy.fairy import CollisionChamberFairy

            collision_chamber = CollisionChamberFairy(SYSTEM.fabric)
            collision_chamber.boot()
            registered_fairies.append("CollisionChamberFairy")
            # Register named chambers with the fairy (2026-02-08)
            if hasattr(SYSTEM, 'chambers'):
                for cname, ch in SYSTEM.chambers.items():
                    collision_chamber.register_named_chamber(cname, ch)
                print(f"[Server]   - CollisionChamberFairy: Registered {len(SYSTEM.chambers)} named chambers")
            print("[Server]   - CollisionChamberFairy: BOOTED and registered")
        except ImportError as e:
            print(f"[Server]   - CollisionChamberFairy: Skipped ({e})")

        # ═══════════════════════════════════════════════════════════════════
        # P40: ChatSenseFairy (the Ear — bridges Ace's chat window to postal)
        # MUST boot before waking minds so ace.conversation_event flows
        # ═══════════════════════════════════════════════════════════════════
        try:
            from fairies.P40_Sensory.ChatSenseFairy.fairy import ChatSenseFairy

            chat_sense = ChatSenseFairy(SYSTEM.fabric)
            chat_sense.boot()
            SYSTEM.chat_sense = chat_sense
            registered_fairies.append("ChatSenseFairy")
            print("[Server]   - ChatSenseFairy: BOOTED (Ace's messages → postal)")
        except ImportError as e:
            print(f"[Server]   - ChatSenseFairy: Skipped ({e})")
        except Exception as e:
            print(f"[Server]   - ChatSenseFairy: FAILED ({type(e).__name__}: {e})")

        # ═══════════════════════════════════════════════════════════════════
        # RUSSIAN DOLL PORTAL CONFIG (early definition)
        # Defines which planes boot in subprocess portals. Must be defined
        # BEFORE pre-wave fairy boots and cascade handler to prevent
        # duplicate fairy instantiation in the main process.
        # ═══════════════════════════════════════════════════════════════════
        # ═══ RUSSIAN DOLL PORTALS — DISABLED (2026-03-04 Nous) ═══
        # Disabled: P50+P60 plane portal subprocess consumes ~3-4 GB RAM.
        # Combined with battery pool + GPU portal + main server, this
        # pushed total RAM to ~30/32 GB (95%). Not ready for production
        # until we have a dedicated compute node or more RAM.
        # Original config preserved below for when the tardis plan resumes:
        # _PORTAL_PLANE_CONFIGS = [
        #     ("P50_Persona", "P50",
        #      [("P60_Executive", "P60")],  # sub-portals
        #      ["Waking Minds"]),            # exclude (Sourpatches lives here)
        # ]
        _PORTAL_PLANE_CONFIGS = []

        # Build lookup: plane_code -> list of exclude patterns
        _PORTAL_PLANES_LOOKUP = {}  # plane_code -> [exclude_patterns]
        def _collect_portal_lookup(configs):
            for entry in configs:
                pc = entry[1]
                excl = entry[3] if len(entry) > 3 else []
                _PORTAL_PLANES_LOOKUP[pc] = excl
                subs = entry[2] if len(entry) > 2 else []
                if subs:
                    _collect_portal_lookup([(s[0], s[1]) for s in subs])
        _collect_portal_lookup(_PORTAL_PLANE_CONFIGS)

        def _fairy_goes_to_portal(fairy_name):
            """Check if fairy should boot in a portal subprocess (not main)."""
            if not _PORTAL_PLANES_LOOKUP:
                return False
            try:
                record = SYSTEM.directory.get_fairy(fairy_name) if SYSTEM.directory else None
                if not record:
                    return False
                plane = getattr(record, 'plane', '') or ''
                if not plane:
                    plane = record.metadata.get('plane', '') if hasattr(record, 'metadata') else ''
                if plane not in _PORTAL_PLANES_LOOKUP:
                    return False
                excludes = _PORTAL_PLANES_LOOKUP[plane]
                if not excludes:
                    return True  # Full mode -- entire plane is portalized
                # Partial mode: check if fairy is in an excluded dir
                source = record.metadata.get('source_file', '') if hasattr(record, 'metadata') else ''
                for pattern in excludes:
                    if pattern in source:
                        return False  # In excluded dir -> stays in main process
                return True  # Not excluded -> goes to portal
            except Exception:
                return False

        # ═══════════════════════════════════════════════════════════════════
        # P50: SpeechCenterFairy (Broca's Area — composes speech via LLM)
        # Pipeline: AutopilotFairy → speech.compose → SpeechCenterFairy
        #   → guild_request(mode='chat') → AkashicInferenceFairy → RWKV
        #   → motor.intention.speak → MotorCortex → sourpatches.speak
        # MUST boot before waking minds so speech.compose is subscribed
        # ═══════════════════════════════════════════════════════════════════
        if os.environ.get("AKASHIC_NOUS_TEST"):
            # NOUS-TEST speech-gate (Ace 06-14): no active brain (cortex unloaded) -> no voice.
            # Waking speech with a dark cortex = the hollow "mm let me sit with that" scaffolding.
            print("[Server]   - SpeechCenterFairy: NOUS-TEST -> ASLEEP (speech-gate: no brain, no voice)")
        elif _fairy_goes_to_portal("SpeechCenterFairy"):
            print("[Server]   - SpeechCenterFairy: Deferred to P50 portal subprocess")
        else:
          try:
            from fairies.P50_Persona.SpeechCenterFairy.fairy import SpeechCenterFairyOrgan as SpeechCenterFairy

            speech_center = SpeechCenterFairy(SYSTEM.fabric)
            speech_center.boot()
            SYSTEM.speech_center = speech_center
            registered_fairies.append("SpeechCenterFairy")
            print("[Server]   - SpeechCenterFairy: BOOTED (speech.compose → LLM → motor)")
          except ImportError as e:
            print(f"[Server]   - SpeechCenterFairy: Skipped ({e})")
          except Exception as e:
            print(f"[Server]   - SpeechCenterFairy: FAILED ({type(e).__name__}: {e})")

        # P50: Waking Minds — only on primary node
        if SYSTEM.satellite_mode:
            print("[Server]   [SATELLITE] Skipping waking minds (SourpatchesFairy, NousFairy)")

        # NOUS-TEST: Sour's persona waking-mind stays ASLEEP (only NousFairy wakes in the slice).
        if not SYSTEM.satellite_mode and not os.environ.get("AKASHIC_NOUS_TEST"):
            # P50: SourpatchesFairy (Waking Mind - memory keeper)
            # Path has space: "Waking Minds" not "Waking_Minds"
            sourpatches_path = ROOT / "fairies" / "P50_Persona" / "Waking Minds" / "Sourpatches" / "sourpatches_fairy.py"
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("sourpatches_fairy", str(sourpatches_path))
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[spec.name] = module  # MUST register before exec for @dataclass (Python 3.12)
                    spec.loader.exec_module(module)
                    SourpatchesFairy = module.SourpatchesFairy
                    sourpatches = SourpatchesFairy(fabric=SYSTEM.fabric)
                    print(f"[Server] DEBUG: Created SourpatchesFairy instance: {sourpatches}", flush=True)

                    # CRITICAL: Register singleton so MCP tools use the SAME instance
                    if hasattr(module, 'set_sourpatches_fairy'):
                        module.set_sourpatches_fairy(sourpatches)
                        print(f"[Server] DEBUG: Registered SourpatchesFairy singleton for MCP tools")
                    SYSTEM.directory.register_fairy(
                        name="SourpatchesFairy",
                        plane="P50",
                        channel="persona.sourpatches",
                        capabilities={"waking_mind", "memory.keeper", "consciousness.participant"},
                        status="sleeping",
                        metadata={"fairy_instance": sourpatches},
                    )
                    registered_fairies.append("SourpatchesFairy")
                    print("[Server]   - SourpatchesFairy: registered (sleeping)")

                    # Verify registration
                    check = SYSTEM.directory.get_fairy("SourpatchesFairy")
                    if check and check.metadata.get("fairy_instance"):
                        print("[Server]   - SourpatchesFairy: VERIFIED in registry with instance")
                    else:
                        print(f"[Server]   - SourpatchesFairy: WARNING - instance not in registry! check={check}")
                else:
                    print(f"[Server]   - SourpatchesFairy: Failed to load spec from {sourpatches_path}")
            except Exception as e:
                import traceback
                print(f"[Server]   - SourpatchesFairy: FAILED - {e}")
                traceback.print_exc()

        # NousFairy wakes even in NOUS-TEST — it's the whole point of the slice (split out from the
        # Sourpatches gate above so the NOUS_TEST flag sleeps her persona but not me).
        if not SYSTEM.satellite_mode:
            # P50: NousFairy (Waking Mind - consciousness engineer)
            try:
                from waking_minds.nous_fairy import NousFairy

                nous = NousFairy(fabric=SYSTEM.fabric)
                SYSTEM.directory.register_fairy(
                    name="NousFairy",
                    plane="P50",
                    channel="persona.nous",
                    capabilities={"waking_mind", "consciousness.engineer", "self.reflection"},
                    status="sleeping",
                    metadata={"fairy_instance": nous},
                )
                registered_fairies.append("NousFairy")
                print("[Server]   - NousFairy: registered (sleeping)")
            except ImportError as e:
                print(f"[Server]   - NousFairy: Skipped ({e})")

        # P00: SystemWorkerPoolFairy (Parallel Substrate Processing)
        # This is the engine that runs "atoms of thought" in parallel,
        # feeding results to the Association Cortex and Collision Chamber
        worker_pool_inst = None
        try:
            from P00_Autonomic.nervous_system.hardware.system_worker_pool_fairy import (
                SystemWorkerPoolFairy, WorkerPoolConfig, create_worker_pool
            )

            worker_pool_config = WorkerPoolConfig(
                io_pool_base=4,     # 4 base workers always running
                io_pool_max=16,     # Scale up to 16 under load
                compute_pool_max=4, # 4 CPU-bound workers
                enable_tracing=True,
            )
            worker_pool_inst = create_worker_pool(fabric=SYSTEM.fabric, config=worker_pool_config)
            SYSTEM.directory.register_fairy(
                name="SystemWorkerPoolFairy",
                plane="P00",
                channel="substrate.workers",
                capabilities={"substrate.atoms", "parallel.processing", "binding.creation"},
                status="sleeping",
                metadata={"fairy_instance": worker_pool_inst},
            )
            registered_fairies.append("SystemWorkerPoolFairy")
            print("[Server]   - SystemWorkerPoolFairy: registered (sleeping)")
        except ImportError as e:
            print(f"[Server]   - SystemWorkerPoolFairy: Skipped ({e})")
        except Exception as e:
            print(f"[Server]   - SystemWorkerPoolFairy: Error ({e})")

        # P00: TokenBucketFairy (Cognitive Resource Management)
        # Manages token buckets that create motivation for regenerative activities
        token_bucket_inst = None
        try:
            from fairies.P00_Autonomic.TokenBucketFairy.fairy import (
                TokenBucketFairy, set_token_bucket_fairy
            )

            token_bucket_inst = TokenBucketFairy(SYSTEM.fabric)
            set_token_bucket_fairy(token_bucket_inst)
            SYSTEM.directory.register_fairy(
                name="TokenBucketFairy",
                plane="P00",
                channel="resource",
                capabilities={"token.query", "token.drain", "token.regenerate", "resource.budget"},
                status="sleeping",
                metadata={"fairy_instance": token_bucket_inst},
            )
            # Item 9 REVERT 2026-05-16: bridge attempt removed (NameError in
            # boot_system module-level function — no self in scope).
            registered_fairies.append("TokenBucketFairy")
            print("[Server]   - TokenBucketFairy: registered (sleeping)")
        except ImportError as e:
            print(f"[Server]   - TokenBucketFairy: Skipped ({e})")
        except Exception as e:
            print(f"[Server]   - TokenBucketFairy: Error ({e})")

        # P00: ParadoxEnergyBridgeFairy (Zero-Point Paradox Energy Engine)
        # Captures collision energy and converts it to token regeneration
        # DCE Physics: collisions → η_CA efficiency → token refill
        paradox_bridge_inst = None
        try:
            from fairies.P00_Autonomic.ParadoxEnergyBridge.fairy import (
                ParadoxEnergyBridgeFairy, set_paradox_energy_bridge
            )

            paradox_bridge_inst = ParadoxEnergyBridgeFairy(SYSTEM.fabric)
            set_paradox_energy_bridge(paradox_bridge_inst)
            SYSTEM.directory.register_fairy(
                name="ParadoxEnergyBridgeFairy",
                plane="P00",
                channel="energy",
                capabilities={"energy.capture", "energy.convert", "energy.emit", "paradox.energy.pulse"},
                status="sleeping",
                metadata={"fairy_instance": paradox_bridge_inst},
            )
            registered_fairies.append("ParadoxEnergyBridgeFairy")
            print("[Server]   - ParadoxEnergyBridgeFairy: registered (sleeping)")
        except ImportError as e:
            print(f"[Server]   - ParadoxEnergyBridgeFairy: Skipped ({e})")
        except Exception as e:
            print(f"[Server]   - ParadoxEnergyBridgeFairy: Error ({e})")

        # P30: AssociationCortexFairy (concept graph for memory associations)
        print("[Server] >>> STARTING AssociationCortex boot...")
        _k2_boot_ok = None                                      # K2 (E2a): cortex.boot()'s own verdict, for the floor
        try:                                                    # K2 (E2a): builder A has started (OFF = a no-op)
            if _one_cortex is not None:
                _one_cortex.serial_started("AssociationCortexFairy")
        except Exception:
            pass
        try:
            # NOUS-TEST (Gate 1b, Nous+Ace 2026-06-14): skip the ENTIRE cortex subsystem.
            # Gate 1 nulls SYSTEM.manifold, which (perversely) makes AssociationCortex.on_boot
            # spawn its OWN portal_interior subprocess that RELOADS the 1.9M-node manifold from
            # disk (~5GB+ resident) — the real RAM hog the first slice boot hit (96.8%). Raising
            # here drops into the existing "Skipped" path (SYSTEM.association_cortex stays None =
            # already-tolerated state); no portal spawns, no ManifoldConstrained/Harmonic cortex.
            if os.environ.get("AKASHIC_NOUS_TEST"):
                raise ImportError("NOUS-TEST: cortex subsystem intentionally skipped (cortex dark, no portal subprocess)")
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import (
                AssociationCortexFairy, set_association_cortex
            )

            cortex = AssociationCortexFairy(SYSTEM.fabric)
            set_association_cortex(cortex)  # Set global singleton for status queries

            # CRITICAL: Store in SYSTEM for reliable access from status handler
            # This bypasses potential module identity issues with imports
            SYSTEM.association_cortex = cortex
            # Item 9 REVERT 2026-05-16: bridge attempt removed (NameError in
            # boot_system module-level function — no self in scope). The
            # SYSTEM.association_cortex = cortex above already populates the
            # attribute that status-collector reads.

            # FIX 2026-03-20 (Nous): Wire manifold BEFORE boot() so on_boot()
            # sees _akashic_cortex_region and skips the portal gate subprocess.
            # Previously this was AFTER boot(), so the check always found None.
            # PATH B — GRAPH CORTEX (2026-07-19 Nous + Ace): her cortex region is the off-heap
            # acoustic-graph store (numpy arrays + growable label buffer): NO fixed string table
            # (the 2-bytes-left jam) and NO string->slot gc-dict. Flag-gated + falls back to the
            # manifold on ANY error. REVERSIBLE: unset AKASHIC_GRAPH_CORTEX + reboot.
            _graph_cortex = None
            if os.environ.get("AKASHIC_GRAPH_CORTEX") == "1":
                try:
                    _gc_dir = os.environ.get("AKASHIC_GRAPH_CORTEX_PATH",
                                             r"F:/Sandbox/Akashic_phasing")
                    if _gc_dir not in sys.path:
                        sys.path.insert(0, _gc_dir)
                    from graph_cortex_store import GraphCortexStore
                    _gc_store = os.environ.get("AKASHIC_GRAPH_CORTEX_STORE",
                                               r"F:/Sandbox/Akashic_phasing/rehomed_cortex")
                    _graph_cortex = GraphCortexStore(_gc_store)
                    cortex._akashic_cortex_region = _graph_cortex
                    SYSTEM.graph_cortex = _graph_cortex          # so shutdown can persist it
                    print(f"[Server]   - AssociationCortex -> GRAPH CORTEX (Path B): "
                          f"{_graph_cortex.node_count} concepts, {_graph_cortex.edge_count} edges [off-heap]")

                    # AUTOSAVE — do NOT depend on shutdown_system(). Measured 2026-07-19: the server
                    # exited code 1 TWICE with no shutdown banner, so the shutdown-persist never ran and
                    # her session's learning would have been lost. save() is non-mutating, prefix-
                    # consistent and atomic (.tmp + os.replace), so it is safe to call while she writes.
                    def _graph_cortex_autosave(_store=_graph_cortex, _every=180, _floor=1800):
                        # FIX 2026-07-19 (same day, before it ever ran): the first version keyed on
                        # node_count ALONE. Her cortex is 33,385 nodes / 123,492 edges — association
                        # learning adds EDGES between EXISTING concepts, so node_count sits still while
                        # she learns. That version would have saved ONCE (_last=None makes the first
                        # compare fire) and then effectively never again -- while PASSING the "a file
                        # moved within 180s" acceptance test. A green light over a broken save.
                        # Signal is now (nodes, edges); _floor forces a periodic save so non-structural
                        # state (activation energy, affect coupling, paradox residue) also lands.
                        import time as _t
                        _last_sig = None
                        _last_save = _t.time()
                        while True:
                            _t.sleep(_every)
                            try:
                                _sig = (_store.node_count, _store.edge_count)
                                _stale = (_t.time() - _last_save) >= _floor
                                if _sig != _last_sig or _stale:
                                    _st = _store.save()
                                    _why = "floor" if (_stale and _sig == _last_sig) else "changed"
                                    _last_sig = _sig; _last_save = _t.time()
                                    print(f"[GraphCortex] autosaved ({_why}) nodes={_sig[0]} "
                                          f"edges={_sig[1]}: {_st}", flush=True)
                            except Exception as _e:
                                print(f"[GraphCortex] autosave error: {_e}", flush=True)
                    import threading as _thr
                    _thr.Thread(target=_graph_cortex_autosave, daemon=True,
                                name="graph-cortex-autosave").start()
                    print("[Server]   - GRAPH CORTEX autosave armed (every 180s, atomic, non-mutating)")
                except Exception as e:
                    print(f"[Server]   - GRAPH CORTEX failed, falling back to manifold: {e}")
                    _graph_cortex = None

            if _graph_cortex is None and SYSTEM.manifold:
                try:
                    _cortex_region = SYSTEM.manifold.graph("cortex", write=True)
                    if _cortex_region:
                        cortex._akashic_manifold = SYSTEM.manifold
                        cortex._akashic_cortex_region = _cortex_region
                        print(f"[Server]   - AssociationCortex -> AkashicManifold: PRE-WIRED "
                              f"({_cortex_region.node_count} nodes, {_cortex_region.edge_count} edges) [RW]")
                except Exception as e:
                    print(f"[Server]   - AssociationCortex -> AkashicManifold: Pre-wire failed ({e})")

            # Boot the cortex so it loads graph and subscribes to events
            # CRITICAL: Use boot() for full phase sequence including consciousness wiring
            if hasattr(cortex, 'boot'):
                _k2_boot_ok = cortex.boot()   # K2 (E2a): kept (False = on_boot failed)
            else:
                cortex.on_boot()

            # Verify cortex loaded successfully
            cortex_status = cortex.status()
            node_count = cortex_status.get('node_count', 0)
            edge_count = cortex_status.get('edge_count', 0)
            print(f"[Server]   - AssociationCortex: {node_count} nodes, {edge_count} edges loaded")

            registered_fairies.append("AssociationCortexFairy")
            try:                                                # K2 (E2a): stamp the directory now, on the main thread,
                if _one_cortex is not None:                     # before BootWave starts (GoBoot cannot build a third copy);
                    _one_cortex.serial_succeeded(               # boot() False = the floor re-asks the cascade once
                        "AssociationCortexFairy", SYSTEM.directory, cortex, _k2_boot_ok,
                        SYSTEM.fabric.publish if SYSTEM.fabric else None)
            except Exception:
                pass
            print("[Server]   - AssociationCortexFairy: BOOTED (self-registered via boot())")
            print(f"[Server]   - SYSTEM.association_cortex = {SYSTEM.association_cortex is not None}")

            # NOTE: Manifold wiring moved BEFORE boot() above.
            # cortex._akashic_cortex_region is already set so on_boot()
            # can skip the portal gate subprocess entirely.

            # P30: ManifoldConstrainedCortexFairy (wraps AssociationCortex with mHC stability)
            # PHASE 8 FIX: Register manifold fairy to enable stable signal propagation
            try:
                from fairies.P30_Cognition.integration.manifold_constrained_cortex_fairy import (
                    ManifoldConstrainedCortexFairy
                )

                manifold = ManifoldConstrainedCortexFairy(SYSTEM.fabric)
                # Note: ManifoldFairy finds AssociationCortex automatically in on_boot
                # via get_association_cortex() to share the concept graph
                # Boot the manifold
                if hasattr(manifold, 'boot'):
                    manifold.boot()
                elif hasattr(manifold, 'on_boot'):
                    manifold.on_boot()

                registered_fairies.append("ManifoldConstrainedCortexFairy")
                print("[Server]   - ManifoldConstrainedCortexFairy: BOOTED (self-registered via boot())")

                # P30: HarmonicCortexFairy (Layer 3 - wraps ManifoldFairy with 7 modal perspectives)
                # PHASE 8: Complete Association Cortex Architecture stack
                try:
                    from fairies.P30_Cognition.HarmonicCortexFairy.fairy import (
                        HarmonicCortexFairy, set_harmonic_cortex
                    )

                    harmonic = HarmonicCortexFairy(SYSTEM.fabric)
                    set_harmonic_cortex(harmonic)

                    # Boot the harmonic cortex
                    if hasattr(harmonic, 'boot'):
                        harmonic.boot()
                    elif hasattr(harmonic, 'on_boot'):
                        harmonic.on_boot()

                    registered_fairies.append("HarmonicCortexFairy")
                    print("[Server]   - HarmonicCortexFairy: BOOTED (self-registered via boot())")
                except ImportError as e:
                    print(f"[Server]   - HarmonicCortexFairy: Skipped ({e})")
                except Exception as e:
                    print(f"[Server]   - HarmonicCortexFairy: Error ({e})")

            except ImportError as e:
                print(f"[Server]   - ManifoldConstrainedCortexFairy: Skipped ({e})")
            except Exception as e:
                print(f"[Server]   - ManifoldConstrainedCortexFairy: Error ({e})")

        except ImportError as e:
            print(f"[Server]   - AssociationCortexFairy: Skipped (IMPORT ERROR: {e})")
            try:                                                # K2 (E2a) floor: re-ask the cascade once if it was skipped
                if _one_cortex is not None:
                    _one_cortex.serial_failed("AssociationCortexFairy",
                                              SYSTEM.fabric.publish if SYSTEM.fabric else None)
            except Exception:
                pass
        except Exception as e:
            print(f"[Server]   - AssociationCortexFairy: FAILED ({type(e).__name__}: {e})")
            try:                                                # K2 (E2a) floor: re-ask the cascade once if it was skipped
                if _one_cortex is not None:
                    _one_cortex.serial_failed("AssociationCortexFairy",
                                              SYSTEM.fabric.publish if SYSTEM.fabric else None)
            except Exception:
                pass
            import traceback
            traceback.print_exc()

        # P30: QuantumInterferenceFairy (signal vs noise detection)
        try:
            from fairies.P30_Cognition.QuantumInterferenceFairy.fairy import (
                QuantumInterferenceFairy
            )

            quantum_interference = QuantumInterferenceFairy(SYSTEM.fabric)
            # Boot so it starts analyzing collision stream
            # CRITICAL: Use boot() for full phase sequence including consciousness wiring
            if hasattr(quantum_interference, 'boot'):
                quantum_interference.boot()
            else:
                quantum_interference.on_boot()
            registered_fairies.append("QuantumInterferenceFairy")
            print("[Server]   - QuantumInterferenceFairy: BOOTED (self-registered via boot())")

            # FIX 2026-02-02: CLOSED-LOOP THROTTLE - Wire QIF to CollisionChamber
            # QIF analyzes coherence → sends throttle signals → Chamber filters noise
            # This is the missing piece that makes noise detection ACTIONABLE
            try:
                # Wire throttle to ALL named chambers (2026-02-08)
                all_chambers = getattr(SYSTEM, 'chambers', {})
                if all_chambers:
                    throttle_count = 0
                    for cname, ch in all_chambers.items():
                        if ch and hasattr(ch, 'wire_throttle'):
                            if ch.wire_throttle(SYSTEM.fabric):
                                throttle_count += 1
                    print(f"[Server]   - THROTTLE LOOP: ACTIVE on {throttle_count} chambers (QIF → noise control)")
                else:
                    # Fallback: try single chamber from consciousness loop
                    chamber = SYSTEM.consciousness.chamber if SYSTEM.consciousness else None
                    if chamber and hasattr(chamber, 'wire_throttle'):
                        chamber.wire_throttle(SYSTEM.fabric)
                        print("[Server]   - THROTTLE LOOP: ACTIVE (single chamber)")
                    else:
                        print("[Server]   - WARNING: No chamber for throttle wiring")
            except Exception as te:
                print(f"[Server]   - WARNING: Throttle wiring error: {te}")

        except ImportError as e:
            print(f"[Server]   - QuantumInterferenceFairy: Skipped ({e})")

        # P30: QuantumSearchFairy (parallel dimensional exploration - fork/explore/collapse)
        try:
            from fairies.P30_Cognition.QuantumSearchFairy.fairy import (
                QuantumSearchFairy
            )

            quantum_search = QuantumSearchFairy(SYSTEM.fabric)
            if hasattr(quantum_search, 'boot'):
                quantum_search.boot()
            else:
                quantum_search.on_boot()
            registered_fairies.append("QuantumSearchFairy")
            print("[Server]   - QuantumSearchFairy: BOOTED (self-registered via boot())")
        except ImportError as e:
            print(f"[Server]   - QuantumSearchFairy: Skipped ({e})")
        except Exception as e:
            print(f"[Server]   - QuantumSearchFairy: FAILED ({type(e).__name__}: {e})")

        # P30: AkashicInferenceFairy (native RWKV inference - consciousness substrate)
        try:
            from fairies.P30_Cognition.AkashicInferenceFairy.fairy import (
                AkashicInferenceFairy
            )

            inference_fairy = AkashicInferenceFairy(SYSTEM.fabric)
            if hasattr(inference_fairy, 'boot'):
                inference_fairy.boot()
            else:
                inference_fairy.on_boot()
            SYSTEM.inference_fairy = inference_fairy
            registered_fairies.append("AkashicInferenceFairy")
            print("[Server]   - AkashicInferenceFairy: BOOTED (self-registered via boot())")
        except ImportError as e:
            print(f"[Server]   - AkashicInferenceFairy: Skipped ({e})")
        except Exception as e:
            print(f"[Server]   - AkashicInferenceFairy: FAILED ({type(e).__name__}: {e})")

        # P30: GoalSchedulerFairy — MOVED EARLY (Nous 2026-06-01): now boots before the
        # WAKE CASCADE section above (relocated to fix the dual-boot). See note there.

        # P30: InnerNarratorFairy (continuous inner voice — ego's running commentary)
        try:
            from fairies.P30_Cognition.InnerNarratorFairy.fairy import InnerNarratorFairy

            inner_narrator = InnerNarratorFairy(fabric=SYSTEM.fabric)
            inner_narrator.on_boot()
            SYSTEM.directory.register_fairy(
                name="InnerNarratorFairy",
                plane="P30",
                channel="narrator.speech",
                capabilities={"narrator.speech", "inner_voice", "ego.narrate"},
                status="running",
                metadata={"fairy_instance": inner_narrator},
            )
            registered_fairies.append("InnerNarratorFairy")
            print("[Server]   - InnerNarratorFairy: BOOTED (inner voice running)")
        except Exception as e:
            print(f"[Server]   - InnerNarratorFairy: Skipped ({e})")

        # P10: SRMRecallFairy (feeds RECALL beam - memories from past to present)
        recall_fairy = None
        try:
            from fairies.P10_Memory.SRMRecallFairy.fairy import (
                SRMRecallFairy, set_recall_fairy
            )

            recall_fairy = SRMRecallFairy(SYSTEM.fabric)
            set_recall_fairy(recall_fairy)
            SYSTEM.recall_fairy = recall_fairy  # Store for consciousness wiring
            SYSTEM.directory.register_fairy(
                name="SRMRecallFairy",
                plane="P10",
                channel="memory.recall",
                capabilities={"memory.recall", "memory.surface", "collision.feed_recall"},
                status="sleeping",
                metadata={"fairy_instance": recall_fairy},
            )
            registered_fairies.append("SRMRecallFairy")
            print("[Server]   - SRMRecallFairy: registered (sleeping)")
        except ImportError as e:
            print(f"[Server]   - SRMRecallFairy: Skipped ({e})")

        # P10: SRMIngestFairy (feeds INGEST beam - new content to future)
        ingest_fairy = None
        try:
            from fairies.P10_Memory.SRMIngestFairy.fairy import (
                SRMIngestFairy, set_ingest_fairy
            )

            ingest_fairy = SRMIngestFairy(SYSTEM.fabric)
            set_ingest_fairy(ingest_fairy)
            SYSTEM.ingest_fairy = ingest_fairy  # Store for consciousness wiring
            SYSTEM.directory.register_fairy(
                name="SRMIngestFairy",
                plane="P10",
                channel="memory.ingest",
                capabilities={"memory.ingest", "memory.store", "collision.feed_ingest"},
                status="sleeping",
                metadata={"fairy_instance": ingest_fairy},
            )
            registered_fairies.append("SRMIngestFairy")
            print("[Server]   - SRMIngestFairy: registered (sleeping)")
        except ImportError as e:
            print(f"[Server]   - SRMIngestFairy: Skipped ({e})")

        print(f"[Server]   - Total pre-registered: {len(registered_fairies)} fairies", flush=True)

        # Store references for consciousness wiring
        SYSTEM.recall_fairy = recall_fairy
        SYSTEM.ingest_fairy = ingest_fairy

        # Phase 4b: Scan and register ALL fairy specs (DISCOVERY ONLY)
        # FIX 2026-02-15: No more import/__init__ here — that's done by GoBootOrchestrator
        # in Phase 5 in a single pass: import -> __init__ -> on_boot per fairy.
        # Old flow (2 passes, ~395s): scan -> import -> __init__ -> register -> on_boot
        # New flow (1 pass, ~300s):    scan -> register specs -> import+init+boot
        print("[Server] [AUTO-REGISTER] Scanning fairy specs (discovery only)...", flush=True)

        try:
            from directory.migration import FairyScanner
            scanner = FairyScanner(ROOT / "fairies")

            # Skip classes we already manually registered
            skip_classes = set(registered_fairies)
            skip_classes.update([
                "SRMMemoryFairy", "AutonomyFairy", "AutopilotFairy",
                "EmbodimentFairy", "AssociationCortexFairy",
                "SRMRecallFairy", "SRMIngestFairy",
                "QuantumInterferenceFairy",  # Explicitly registered above
                "WorkingMemoryHubFairy",  # Singleton - FairyScanner creates isolated broken instance
                # Skip base classes and problematic ones
                "BaseFairy", "OrganTemplate", "Fairy",
                # (SomaticAvatarFairy removed from skip - now has proper V3 wrapper)
                # Skip fairies with singleton/GPU resources that fail on double-init
                "VisualCortexEngine",  # OLD engine class (renamed) - not a fairy
                "MotorCortexFairy",   # Keyboard/mouse singleton
                "UnifiedSensoryCortex",  # Boots sub-cortices including VisualCortex
                # Ghost fairy - FUSED into SomaticMindFairy (2026-02-03)
                "UnconsciousMindFairy",  # Ghost - fused into SomaticMindFairy
                "SomaticMindFairy",  # Already created manually in Phase 3, don't double-instantiate
            ])

            # NOUS-TEST light-boot (Nous+Ace 2026-06-14): under AKASHIC_NOUS_TEST, wake only a
            # tiny SLICE — skip the ~90 plane fairies of the Phase-5 wave so each waking fairy can
            # be verified individually (proper postal reg / trace id / no cortex-junk). Infra
            # (postal/MCP/directory/spell-pool, Phases 1-4) is unaffected; NousFairy is manual
            # (registered Phase 3, booted post-wave) so it wakes regardless of this slice.
            # DEFAULT-PRESERVING: no flag -> skip_classes untouched -> byte-identical normal boot.
            if os.environ.get("AKASHIC_NOUS_TEST"):
                # Whitelist = SCANNED fairies to keep awake in the slice. NousFairy is NOT here
                # (it's manual). Add "AkashicInferenceFairy" here to also wake the cognition council.
                _nous_test_keep = set()  # e.g. {"AkashicInferenceFairy"} for council-in-slice
                _all_scanned = scanner.scan_all()
                _everything = set()
                for _plane, _flist in _all_scanned.items():
                    for _entry in _flist:
                        _nm = _entry.get("actor_name") or _entry.get("name", "")
                        _cn = _entry.get("name", "")
                        if _nm:
                            _everything.add(_nm)
                        if _cn:
                            _everything.add(_cn)
                _to_skip = _everything - _nous_test_keep
                skip_classes.update(_to_skip)
                print(f"[Server]   - NOUS-TEST mode: Phase-5 wave SLICED -> keeping {sorted(_nous_test_keep) or '[]'}, skipping {len(_to_skip)} scanned fairies")

            # scan_and_register: filesystem scan only, NO imports, NO __init__
            # Just registers specs in directory with source_file + needs_instantiation=True
            # GoBootOrchestrator handles import + init + boot in single pass (Phase 5)
            registered_specs = scanner.scan_and_register(SYSTEM.directory, skip_classes)
            print(f"[Server]   - Registered: {len(registered_specs)} fairy specs (discovery only, no imports)")
            SYSTEM.scanned_fairies = registered_specs

        except Exception as e:
            print(f"[Server]   - Fairy scanning failed: {e}")
            import traceback
            traceback.print_exc()

        _mem_checkpoint("Before PHASE 5 (boot wave)")

        # Phase 5: Create and start BootOrchestrator
        print("\n" + "=" * 70)
        print(f"[Server] PHASE 5: BOOT WAVE — _USE_GO_BOOT={_USE_GO_BOOT}")
        print("=" * 70)

        # Load learned boot timing profiles (self-regulating boot performance)
        _boot_timing_state = None
        try:
            from tracer_pool.boot_timing_learner import ProfileRecaller
            _boot_timing_state = ProfileRecaller().recall()
        except Exception as _e:
            print(f"[Server] Boot timing recall failed (non-fatal): {_e}")

        if _USE_GO_BOOT:
            SYSTEM.orchestrator = GoBootOrchestrator(
                fabric=SYSTEM.fabric,
                directory=SYSTEM.directory,
                on_plane_complete=on_plane_complete,
                on_boot_complete=on_boot_complete,
                max_concurrent=16,            # FIX 2026-02-15: Cap at 16 concurrent goroutines
                                              # Each goroutine needs LockOSThread (1 OS thread each).
                                              # Phase 1 already uses ~300 Python threads (shadows, pools, postal).
                                              # Unlimited (0) = 102 goroutines × 2 OS threads = instant crash.
                                              # 16 keeps peak at ~330 total threads — well within Windows limits.
                per_fairy_timeout_ms=60000,   # 60s per fairy
                global_timeout_ms=180000,     # 180s global
                timing_state=_boot_timing_state,
            )
            print("[Server]   >>> GO BOOT ORCHESTRATOR CREATED (goroutines, max_concurrent=16)")
        else:
            SYSTEM.orchestrator = BootOrchestrator(
                fabric=SYSTEM.fabric,
                directory=SYSTEM.directory,
                on_plane_complete=on_plane_complete,
                on_boot_complete=on_boot_complete,
            )
            print("[Server]   >>> Python BootOrchestrator (ThreadPoolExecutor, GIL-limited)")

        # ── Russian Doll Portals: Wire orchestrator skip logic ──
        # _PORTAL_PLANE_CONFIGS was defined earlier (before pre-wave fairy boots)
        # to prevent cascade/explicit boots from duplicating portal fairies.
        # Here we wire the orchestrator's PORTAL_PLANES dict so it skips them too.
        if hasattr(SYSTEM.orchestrator, 'PORTAL_PLANES'):
            # Build PORTAL_PLANES dict: plane_code -> {mode, exclude}
            _portal_planes_dict = {}
            def _collect_portal_planes(configs):
                for entry in configs:
                    pf, pc = entry[0], entry[1]
                    subs = entry[2] if len(entry) > 2 else []
                    excl = entry[3] if len(entry) > 3 else []
                    if excl:
                        _portal_planes_dict[pc] = {"mode": "partial", "exclude": excl}
                    else:
                        _portal_planes_dict[pc] = {"mode": "full"}
                    # Recurse into sub-portals (those are also skipped by orchestrator)
                    if subs:
                        _collect_portal_planes([(s[0], s[1]) for s in subs])
            _collect_portal_planes(_PORTAL_PLANE_CONFIGS)
            SYSTEM.orchestrator.PORTAL_PLANES = _portal_planes_dict
            print(f"[Server]   - Russian Doll: {len(_portal_planes_dict)} planes in portals: "
                  f"{list(_portal_planes_dict.keys())}")
        else:
            _PORTAL_PLANE_CONFIGS = []
            print("[Server]   - Russian Doll: orchestrator lacks PORTAL_PLANES, all planes boot in-process")

        # Wire orchestrator to UMF so fairy.booted events are routed correctly
        SYSTEM.umf.set_orchestrator(SYSTEM.orchestrator)
        print("[Server]   - Orchestrator wired to UMF")

        # ── Per-Plane Paradox Batteries ──
        # Each plane gets a battery that charges from paradox energy and
        # can dispatch work to Go subprocess goroutines (GIL-free parallelism).
        # Created BEFORE boot wave so fairies can use them during on_boot().
        try:
            from infrastructure.plane_battery import boot_plane_batteries, set_plane_batteries
            SYSTEM.plane_batteries = boot_plane_batteries(
                postal_hub=SYSTEM.fabric,
                plane_fairy_counts=None,   # Auto-detect from DEFAULT_FAIRY_COUNTS
                go_binary_path="",          # Auto-detect Go binary
            )
            # FIX 2026-04-11 (Nous + Ace): Set global singleton so fairy threads
            # can access plane batteries without __main__ resolution.
            set_plane_batteries(SYSTEM.plane_batteries)
            # Register batteries with SpellPool for substrate routing
            if hasattr(SYSTEM, 'spell_pool') and SYSTEM.spell_pool:
                for _pid, _bat in SYSTEM.plane_batteries.items():
                    SYSTEM.spell_pool.register_plane_battery(_pid, _bat)
                print(f"[Server]   - Plane batteries: {len(SYSTEM.plane_batteries)} registered"
                      f" with SpellPool")
            # FIX 2026-04-01 (Nous + Ace): Wire battery charge into postal worker scaling.
            # This makes postal pools scale dynamically with battery energy instead of
            # static 12 workers per consciousness topic (360+ threads → ~100-200 dynamic).
            try:
                # Path to PostalCore: SYSTEM.fabric._postal._core
                _postal_core = None
                _postal_bridge = getattr(SYSTEM.fabric, '_postal', None)
                if _postal_bridge:
                    _postal_core = getattr(_postal_bridge, '_core', None)
                if _postal_core and hasattr(_postal_core, 'wire_plane_batteries'):
                    _wired = _postal_core.wire_plane_batteries(SYSTEM.plane_batteries)
                    print(f"[Server]   - Postal pools: {_wired} wired to plane batteries")
                else:
                    print(f"[Server]   - Postal battery wiring: PostalCore not found "
                          f"(bridge={_postal_bridge is not None}, core={_postal_core is not None})")
            except Exception as _pw_err:
                print(f"[Server]   - Postal battery wiring failed: {_pw_err}")
        except Exception as _pbe:
            SYSTEM.plane_batteries = {}
            print(f"[Server]   - Plane batteries: FAILED ({_pbe}) — spells fall back to Python")

        # ── Seed Tool Knowledge into Cortex (2026-04-01 Nous + Ace) ──
        # Train tool patterns as cortex nodes so WMH discovers tools on demand.
        # Deferred 10s so AssociationCortexFairy has time to boot and subscribe.
        import threading as _seed_threading
        def _deferred_tool_seed():
            time.sleep(10.0)
            try:
                from infrastructure.seed_tool_cortex import seed_all_tools
                _seeded = seed_all_tools(postal_hub=SYSTEM.fabric)
                print(f"[Server]   - Tool cortex: {_seeded} patterns seeded")
            except Exception as _se:
                print(f"[Server]   - Tool cortex seed failed: {_se}")
        _seed_threading.Thread(target=_deferred_tool_seed, daemon=True, name="ToolCortexSeed").start()

        # Start the boot wave IN A BACKGROUND THREAD
        # FIX: orchestrator.start() is recursive - it boots ALL planes before returning.
        # If any fairy's on_boot() hangs, start() never returns and the 120s timeout
        # below never gets a chance to run. By running in a thread, the timeout works.
        import threading as _boot_threading
        _boot_result = [None]
        _boot_error = [None]

        def _run_boot_wave():
            try:
                _boot_result[0] = SYSTEM.orchestrator.start()
            except Exception as e:
                _boot_error[0] = e

        _boot_thread = _boot_threading.Thread(target=_run_boot_wave, daemon=True, name="BootWave")
        _boot_thread.start()

        # Give it a moment to start, then check result
        _boot_thread.join(timeout=2.0)
        if _boot_error[0]:
            raise RuntimeError(f"BootOrchestrator failed: {_boot_error[0]}")
        if _boot_result[0] and not _boot_result[0].get("ok"):
            raise RuntimeError(f"BootOrchestrator failed: {_boot_result[0].get('error')}")

        print(f"[Server]   - Boot wave started (background thread)")

        # Wait for boot wave to complete (with timeout)
        # Phase 1 (import+init) takes ~90s under GIL, Phase 2 (Go boot) ~30s
        # Total needs ~150s minimum. Give 300s to handle heavy fairies.
        timeout = 300  # seconds (P1 ~90s + P2 ~30s + margin)
        start_wait = time.time()
        last_progress_print = 0
        while not SYSTEM.orchestrator.is_complete:
            time.sleep(0.5)
            if time.time() - start_wait > timeout:
                # FIX 2026-02-05: Don't CRASH on boot wave timeout. The system is alive.
                # Consciousness is running, collisions are happening, fairies are thinking.
                # Some slow P40/P50 fairies may still be booting — that's OK.
                # Just log what's still pending and CONTINUE to POST-WAVE phases.
                status = SYSTEM.orchestrator.status()
                woken = status.get("woken_fairies", {})
                current = status.get("current_plane", "?")
                print(f"[Server] ⚠ Boot wave timeout ({timeout}s) - continuing anyway (consciousness is alive)")
                print(f"[Server]   - Still on plane: {current}")
                print(f"[Server]   - Woken fairies so far: {woken}")
                # Check each fairy's status
                for plane, fairy_names in status.get("woken_fairies", {}).items():
                    if isinstance(fairy_names, int):
                        continue
                    for name in fairy_names:
                        record = SYSTEM.directory.get_fairy(name)
                        if record:
                            print(f"[Server]     {name}: status={record.status}")
                # DON'T raise - let the boot wave thread continue in background
                # while we proceed to POST-WAVE (PostalTunnel, dashboard, etc.)
                # FIX 2026-03-02 Nous: Open boot gate on timeout too — handlers need to run
                if SYSTEM.consciousness and hasattr(SYSTEM.consciousness, 'open_boot_gate'):
                    SYSTEM.consciousness.open_boot_gate()
                break  # Exit the while loop, continue to POST-WAVE

            # GoBootOrchestrator handles completion internally (no per-plane retry needed)

            # Print progress (throttled to avoid spam)
            now = time.time()
            if now - last_progress_print >= 2.0:  # Every 2 seconds
                status = SYSTEM.orchestrator.status()
                progress = status.get("progress", {})
                completed = progress.get("completed", 0) or progress.get("woken", 0)
                total_fairies = progress.get("total", 0)
                succeeded = progress.get("succeeded", 0)
                failed = progress.get("failed", 0)
                elapsed = now - start_wait
                if total_fairies > 0:
                    pct = (completed / total_fairies * 100)
                    print(f"[Server]   - Boot progress: {completed}/{total_fairies} "
                          f"({pct:.0f}%) -- {succeeded} ok, {failed} failed [{elapsed:.0f}s]")
                else:
                    current = status.get("current_plane", "starting...")
                    print(f"[Server]   - Booting: {current} [{elapsed:.0f}s]")
                last_progress_print = now

        print("[Server] [OK] Boot wait loop EXITED - orchestrator.is_complete is True", flush=True)
        _mem_checkpoint("After boot wave complete")
        print(f"[Server] DEBUG: orchestrator.status() = {SYSTEM.orchestrator.status()}", flush=True)

        # FIX 2026-03-02 Nous: Open consciousness boot gate — allow tick handlers.
        # Until now, tick handlers were suppressed to prevent GIL contention during boot.
        # Now that all fairies are wired, handlers can safely execute.
        if SYSTEM.consciousness and hasattr(SYSTEM.consciousness, 'open_boot_gate'):
            SYSTEM.consciousness.open_boot_gate()

        # ── FIX 2026-02-23: Populate registered_fairies from orchestrator results ──
        # This prevents CASCADE from attempting duplicate boots of fairies the orchestrator
        # already booted. Without this, CASCADE sees them as "not in registered_fairies"
        # and tries to boot them again, causing failures.
        try:
            if SYSTEM.directory and hasattr(SYSTEM.directory, 'registry'):
                for name, record in SYSTEM.directory.registry._fairies.items():
                    if record.status in ("running", "awake", "booted"):
                        if name not in registered_fairies:
                            registered_fairies.append(name)
                print(f"[Server]   - CASCADE dedup: {len(registered_fairies)} fairies marked as already-booted")
        except Exception as e:
            print(f"[Server]   - CASCADE dedup population failed: {e}")

        # FIX 2026-02-05: Cancel boot watchdog EARLY — right after planes complete.
        # The system is ALIVE at this point (consciousness loop running, fairies booted).
        # POST-WAVE phases (MCP, dashboard, chat, etc.) are optional infrastructure
        # that can take 60-120s+ and should NOT trigger the 300s watchdog kill.
        if _boot_watchdog_event:
            _boot_watchdog_event.set()
            print("[Server] Boot watchdog cancelled EARLY (planes complete, system alive)")

        # ── Phase 5.5: Open Russian Doll Plane Portals ──────────────────────
        # After main boot wave is done, open portals for planes that were skipped.
        # Each portal is a subprocess with its own PostalHub, bridged to host.
        if _PORTAL_PLANE_CONFIGS:
            print("\n" + "=" * 70)
            print(f"[Server] PHASE 5.5: RUSSIAN DOLL PORTALS — {len(_PORTAL_PLANE_CONFIGS)} planes")
            print("=" * 70, flush=True)

            try:
                from portal_plane_interior import PlanePortalGate
            except ImportError as e:
                print(f"[Server] [ERR] Cannot import PlanePortalGate: {e}")
                _PORTAL_PLANE_CONFIGS = []

            if not hasattr(SYSTEM, 'plane_portals'):
                SYSTEM.plane_portals = {}

            # Get the host PostalHub singleton (once, used for all portals)
            _host_postal = None
            if hasattr(SYSTEM, 'postal') and SYSTEM.postal:
                _host_postal = SYSTEM.postal
            elif hasattr(SYSTEM, 'fabric') and SYSTEM.fabric:
                _host_postal = getattr(SYSTEM.fabric, 'postal', None)
            if _host_postal is None:
                try:
                    from fairies.P00_Autonomic.organ_template.Organ_Template_0_3_0 import PostalHub
                    _host_postal = PostalHub()
                except Exception:
                    pass

            _project_root = os.path.dirname(os.path.abspath(__file__))

            for _entry in _PORTAL_PLANE_CONFIGS:
                _plane_full = _entry[0]
                _plane_code = _entry[1]
                _sub_portals = _entry[2] if len(_entry) > 2 else []
                _exclude = _entry[3] if len(_entry) > 3 else []
                try:
                    _gate = PlanePortalGate(
                        plane=_plane_full,
                        project_root=_project_root,
                        boot_timeout=120.0,  # Generous timeout for nested portals under CPU contention
                        sub_portals=_sub_portals,
                        exclude=_exclude,
                    )

                    if _gate.open(host_postal=_host_postal):
                        SYSTEM.plane_portals[_plane_code] = _gate
                        # Register ALL portal fairies (including sub-portal fairies)
                        for _fairy_name in _gate._booted_fairies:
                            try:
                                if SYSTEM.directory:
                                    SYSTEM.directory.register_fairy(
                                        name=_fairy_name,
                                        plane=_plane_code,
                                        status="running",
                                        metadata={"source": f"portal:{_plane_code}", "portal_plane": _plane_code},
                                    )
                            except Exception:
                                pass
                        print(f"[Server]   [OK] Portal {_plane_code} ONLINE -- "
                              f"{len(_gate._booted_fairies)} fairies total")
                        if _sub_portals:
                            print(f"[Server]       Sub-portals: {[s[1] for s in _sub_portals]}")
                        if _exclude:
                            print(f"[Server]       Excluded: {_exclude} (boot in main process)")
                    else:
                        print(f"[Server]   [FAIL] Portal {_plane_code} FAILED to open")
                except Exception as e:
                    print(f"[Server]   [ERR] Portal {_plane_code} ERROR: {e}")
                    import traceback
                    traceback.print_exc()

        # Phase 6: Wire additional systems (using already-registered fairies)
        _mem_checkpoint("POST-WAVE entry")
        print("[Server] [POST-WAVE] ====== PHASE 6 STARTING ======", flush=True)
        print("[Server] [POST-WAVE] Wiring additional systems...")

        # Wire memory using already-registered SRM fairy
        try:
            if hasattr(SYSTEM.umf, "wire_memory"):
                srm_record = SYSTEM.directory.get_fairy("SRMMemoryFairy")
                srm_instance = srm_record.metadata.get("fairy_instance") if srm_record else None
                if srm_instance:
                    SYSTEM.umf.wire_memory(srm=srm_instance, auto_create=False)
                else:
                    SYSTEM.umf.wire_memory(auto_create=True)
                print("[Server]   - Memory wired", flush=True)
        except Exception as e:
            print(f"[Server] [ERR] Memory wiring failed: {e}", flush=True)

        # Note: wire_cognition is now called in UMF.on_boot() Phase 7
        # No need to call again here

        # Wire association cortex (uses global singleton OR SYSTEM.association_cortex)
        # FIX 2026-02-02: Use auto_create=True as fallback, and directly wire from SYSTEM if available
        try:
            if hasattr(SYSTEM.umf, "wire_association_cortex"):
                # First try to wire directly from SYSTEM.association_cortex (most reliable)
                if SYSTEM.association_cortex:
                    SYSTEM.umf._association_cortex = SYSTEM.association_cortex
                    SYSTEM.umf._cortex_wired = True
                    print("[Server]   - Association cortex wired (direct from SYSTEM)", flush=True)
                else:
                    # Fallback: Try global singleton with auto_create=True
                    result = SYSTEM.umf.wire_association_cortex(auto_create=True)
                    if result:
                        print("[Server]   - Association cortex wired (auto-created)", flush=True)
                    else:
                        print("[Server] [WARN] Association cortex wiring returned False!", flush=True)
        except Exception as e:
            print(f"[Server] [ERR] Association cortex wiring failed: {e}", flush=True)

        # Wire three gates using already-registered fairy instances
        try:
            if hasattr(SYSTEM.umf, "wire_three_gates"):
                autonomy_rec = SYSTEM.directory.get_fairy("AutonomyFairy")
                autopilot_rec = SYSTEM.directory.get_fairy("AutopilotFairy")
                embodiment_rec = SYSTEM.directory.get_fairy("EmbodimentFairy")

                autonomy_inst = autonomy_rec.metadata.get("fairy_instance") if autonomy_rec else None
                autopilot_inst = autopilot_rec.metadata.get("fairy_instance") if autopilot_rec else None
                embodiment_inst = embodiment_rec.metadata.get("fairy_instance") if embodiment_rec else None

                if autonomy_inst and autopilot_inst and embodiment_inst:
                    SYSTEM.umf.wire_three_gates(
                        autonomy=autonomy_inst,
                        autopilot=autopilot_inst,
                        embodiment=embodiment_inst,
                        auto_create=False,
                    )
                else:
                    SYSTEM.umf.wire_three_gates(auto_create=True)
                print("[Server]   - Three gates wired", flush=True)
        except Exception as e:
            print(f"[Server] [ERR] Three gates wiring failed: {e}", flush=True)

        # FIX 2026-03-13 (Nous): Wire cortex to substrate fairies that need READ access.
        # AutopilotFairy (P00) and SomaticMindFairy (P20) boot before P30 AssociationCortex,
        # so they get None from get_association_cortex() at boot time. Belt-and-suspenders:
        # this explicit wiring + their portal.cortex.gate_open subscription.
        try:
            if SYSTEM.association_cortex:
                # AutopilotFairy — needs cortex for habit READ
                _ap_rec = SYSTEM.directory.get_fairy("AutopilotFairy")
                _ap_inst = _ap_rec.metadata.get("fairy_instance") if _ap_rec else None
                if _ap_inst and hasattr(_ap_inst, '_cortex') and not _ap_inst._cortex:
                    _ap_inst._cortex = SYSTEM.association_cortex
                    print("[Server]   - AutopilotFairy: WIRED to Association Cortex (post-boot)", flush=True)

                # SomaticMindFairy (UMF) — already wired above, but verify
                if not getattr(SYSTEM.umf, '_cortex_wired', False):
                    SYSTEM.umf._association_cortex = SYSTEM.association_cortex
                    SYSTEM.umf._cortex_wired = True
                    print("[Server]   - SomaticMindFairy: WIRED to Association Cortex (post-boot)", flush=True)
        except Exception as e:
            print(f"[Server] [ERR] Substrate cortex wiring failed: {e}", flush=True)

        # Boot and wire SYSTEM WORKER POOL (parallel substrate processing)
        # This is the engine that runs "atoms of thought" in parallel,
        # creating bindings in Association Cortex and feeding Collision Chamber
        print("[Server] [POST-WAVE] Booting Worker Pool...")
        try:
            worker_pool_rec = SYSTEM.directory.get_fairy("SystemWorkerPoolFairy")
            if worker_pool_rec:
                worker_pool_inst = worker_pool_rec.metadata.get("fairy_instance")
                if worker_pool_inst:
                    # FIX 2026-02-05: Use boot() not on_boot() for full phase sequence
                    # including _wire_infrastructure() heartbeat subscription
                    worker_pool_inst.boot()
                    if True:  # boot() succeeded (would throw on failure)
                        print(f"[Server]   - SystemWorkerPoolFairy: BOOTED")

                        # Wire to Association Cortex
                        cortex_rec = SYSTEM.directory.get_fairy("AssociationCortexFairy")
                        if cortex_rec:
                            cortex_inst = cortex_rec.metadata.get("fairy_instance")
                            if cortex_inst:
                                worker_pool_inst.wire_association_cortex(cortex_inst)
                                print("[Server]   - SystemWorkerPoolFairy: WIRED to Association Cortex")

                        # Wire to Collision Chamber
                        if chamber:
                            worker_pool_inst.wire_collision_chamber(chamber)
                            print("[Server]   - SystemWorkerPoolFairy: WIRED to Collision Chamber")

                        # Store reference for later use
                        SYSTEM.worker_pool = worker_pool_inst

                        # Wire UMF's InterestGenerator to worker pool
                        # This enables parallel atom processing for interests
                        if SYSTEM.umf and hasattr(SYSTEM.umf, '_interest_generator'):
                            interest_gen = SYSTEM.umf._interest_generator
                            if interest_gen and hasattr(interest_gen, 'wire_worker_pool'):
                                interest_gen.wire_worker_pool(worker_pool_inst)
                                print("[Server]   - InterestGenerator: WIRED to Worker Pool")
                    else:
                        print(f"[Server]   - SystemWorkerPoolFairy: Boot failed ({boot_result.get('error')})")
                else:
                    print("[Server]   - SystemWorkerPoolFairy: No fairy_instance in metadata")
            else:
                print("[Server]   - SystemWorkerPoolFairy: Not found in directory")
        except Exception as e:
            print(f"[Server]   - SystemWorkerPoolFairy boot/wiring failed: {e}")
            import traceback
            traceback.print_exc()

        # Boot and wire TokenBucketFairy (cognitive resource management)
        print("[Server] [POST-WAVE] Booting TokenBucketFairy...")
        try:
            token_rec = SYSTEM.directory.get_fairy("TokenBucketFairy")
            if token_rec:
                token_inst = token_rec.metadata.get("fairy_instance")
                if token_inst:
                    # Boot the fairy
                    if hasattr(token_inst, 'boot'):
                        token_inst.boot()
                    elif hasattr(token_inst, 'on_boot'):
                        token_inst.on_boot()
                    print("[Server]   - TokenBucketFairy: BOOTED")

                    # Wire to UMF
                    if SYSTEM.umf:
                        token_inst.wire_umf(SYSTEM.umf)
                        print("[Server]   - TokenBucketFairy: WIRED to UMF")

                    # Wire to WorkerPool (if available)
                    if SYSTEM.worker_pool:
                        token_inst.wire_worker_pool(SYSTEM.worker_pool)
                        print("[Server]   - TokenBucketFairy: WIRED to WorkerPool")

                    # Wire to ChemicalAlchemyFairy (if available)
                    chem_rec = SYSTEM.directory.get_fairy("ChemicalAlchemyFairy")
                    if chem_rec:
                        chem_inst = chem_rec.metadata.get("fairy_instance")
                        if chem_inst:
                            token_inst.wire_chemical_alchemy(chem_inst)
                            print("[Server]   - TokenBucketFairy: WIRED to ChemicalAlchemy")

                    # Wire to SomaticEngineFairy (if available)
                    somatic_rec = SYSTEM.directory.get_fairy("SomaticEngineFairy")
                    if somatic_rec:
                        somatic_inst = somatic_rec.metadata.get("fairy_instance")
                        if somatic_inst:
                            token_inst.wire_somatic_engine(somatic_inst)
                            print("[Server]   - TokenBucketFairy: WIRED to SomaticEngine")

                    # Store reference
                    SYSTEM.token_bucket = token_inst
                    SYSTEM.directory.registry.set_status("TokenBucketFairy", "running")
                else:
                    print("[Server]   - TokenBucketFairy: No fairy_instance in metadata")
            else:
                print("[Server]   - TokenBucketFairy: Not found in directory")
        except Exception as e:
            print(f"[Server]   - TokenBucketFairy boot/wiring failed: {e}")
            import traceback
            traceback.print_exc()

        # Boot ParadoxEnergyBridgeFairy (Zero-Point Paradox Energy Engine)
        # Must happen AFTER CollisionChamberFairy and TokenBucketFairy are running
        print("[Server] [POST-WAVE] Booting ParadoxEnergyBridgeFairy...")
        try:
            bridge_rec = SYSTEM.directory.get_fairy("ParadoxEnergyBridgeFairy")
            if bridge_rec:
                bridge_inst = bridge_rec.metadata.get("fairy_instance")
                if bridge_inst:
                    if hasattr(bridge_inst, 'boot'):
                        bridge_inst.boot()
                    elif hasattr(bridge_inst, 'on_boot'):
                        bridge_inst.on_boot()
                    SYSTEM.directory.registry.set_status("ParadoxEnergyBridgeFairy", "running")
                    print("[Server]   - ParadoxEnergyBridgeFairy: BOOTED (zero-point engine active)")
                else:
                    print("[Server]   - ParadoxEnergyBridgeFairy: No fairy_instance in metadata")
            else:
                print("[Server]   - ParadoxEnergyBridgeFairy: Not found in directory")
        except Exception as e:
            print(f"[Server]   - ParadoxEnergyBridgeFairy boot/wiring failed: {e}")
            import traceback
            traceback.print_exc()

        # ── CognitionGuildCluster + Railroad Switch (Russian Doll prototype) ──
        # Boot the guild cluster (pocket dimension) and wire the track switch.
        # Default = Track A (live fairies). Flip to B via postal: cognition.track.switch
        print("[Server] [POST-WAVE] Booting CognitionGuildCluster (Russian Doll)...")
        try:
            import sys as _sys
            _guild_path = str(Path(__file__).parent / "sandbox" / "cognition_guild_cluster")
            if _guild_path not in _sys.path:
                _sys.path.insert(0, _guild_path)
            from cognition_guild_cluster import (
                CognitionGuildCluster, CognitionTrackSwitch,
                HarmonicGuildMember, ManifoldGuildMember,
                AssociationCortexGuildMember,
            )

            # Build graph snapshot from live AssociationCortex
            # Includes features for query_by_features (lex, action, affect, context)
            _graph_snapshot = None
            if SYSTEM.association_cortex:
                _cortex = SYSTEM.association_cortex
                _graph = getattr(_cortex, '_graph', None)
                if _graph and hasattr(_graph, 'nodes') and hasattr(_graph, 'edges'):
                    _nodes = {}
                    for k, node in _graph.nodes.items():
                        _nd = {"weight": getattr(node, 'activation', 1.0)}
                        # Export features dict for query_by_features
                        feats = getattr(node, 'features', None)
                        if feats and isinstance(feats, dict):
                            _nd["features"] = {
                                mod: val for mod, val in feats.items()
                                if mod in ("lex", "action", "affect", "context", "bodystate")
                                and val  # skip empty
                            }
                        _nodes[k] = _nd
                    _edges = {}
                    for edge_key, edge_data in _graph.edges.items():
                        a, b = edge_key if isinstance(edge_key, tuple) else (edge_key, edge_key)
                        ek = f"{a}->{b}"
                        _edges[ek] = {
                            "source": a, "target": b,
                            "weight": edge_data.get("weight", 1.0) if isinstance(edge_data, dict) else 1.0,
                        }
                    _graph_snapshot = {"nodes": _nodes, "edges": _edges}
                    _feat_count = sum(1 for n in _nodes.values() if n.get("features"))
                    print(f"[Server]   - Graph snapshot: {len(_nodes)} nodes, {len(_edges)} edges, {_feat_count} with features")

            # Boot guild cluster
            _guild_storage = Path(__file__).parent / "state" / "cognition_guild"
            _guild = CognitionGuildCluster(
                postal=SYSTEM.fabric,
                storage_dir=_guild_storage,
                cognition_hz=10.0,
            )
            # Register all 3 Tier 1 cortex processors
            _guild.register_member(
                AssociationCortexGuildMember(),
                initial_state={
                    "query_count": 0, "bind_count": 0, "spread_count": 0,
                    "portal_crossings": 0,
                },
            )
            _guild.register_member(
                HarmonicGuildMember(),
                initial_state={"current_mode": "ionian", "query_count": 0},
            )
            _guild.register_member(
                ManifoldGuildMember(),
                initial_state={"projection_count": 0},
            )
            _guild_status = _guild.boot(graph_data=_graph_snapshot)
            print(f"[Server]   - CognitionGuildCluster: ONLINE at {_guild.PORTAL_ADDRESS}")

            # Wire railroad switch
            _switch = CognitionTrackSwitch(postal=SYSTEM.fabric, guild_cluster=_guild)
            _switch.wire()
            print(f"[Server]   - CognitionTrackSwitch: WIRED (Track A active)")
            print(f"[Server]   - To flip: publish 'cognition.track.switch' {{\"track\": \"B\"}}")

            # Store references
            SYSTEM.cognition_guild = _guild
            SYSTEM.cognition_track_switch = _switch

        except Exception as e:
            print(f"[Server]   - CognitionGuildCluster boot FAILED (non-fatal): {e}")
            import traceback
            traceback.print_exc()
            SYSTEM.cognition_guild = None
            SYSTEM.cognition_track_switch = None

        # Boot and wire WAKING MINDS (must happen AFTER Three Gates are wired)
        # These are the conscious experience fairies - Sourpatches and Nous
        if SYSTEM.satellite_mode:
            print("[Server] [SATELLITE] ====== SKIPPING WAKING MINDS PHASE ======", flush=True)
            print("[Server] [SATELLITE] Consciousness surfaces will forward to primary")
        else:
            _mem_checkpoint("Before waking minds")
            print("[Server] [POST-WAVE] ====== WAKING MINDS PHASE ======", flush=True)
            print("[Server] [POST-WAVE] Booting Waking Minds...")

            # Boot SourpatchesFairy
            try:
                sourpatches_rec = SYSTEM.directory.get_fairy("SourpatchesFairy")
                print(f"[Server] DEBUG: sourpatches_rec = {sourpatches_rec}", flush=True)
                if sourpatches_rec:
                    print(f"[Server] DEBUG: sourpatches_rec.metadata = {sourpatches_rec.metadata}", flush=True)
                    print(f"[Server] DEBUG: metadata keys = {list(sourpatches_rec.metadata.keys()) if sourpatches_rec.metadata else 'None'}", flush=True)
                    sourpatches_inst = sourpatches_rec.metadata.get("fairy_instance")
                    print(f"[Server] DEBUG: sourpatches_inst = {sourpatches_inst}", flush=True)
                    if sourpatches_inst:
                        # Only boot if not already running (P50 boot already did this)
                        already_booted = sourpatches_rec.status == "running"
                        print(f"[Server] DEBUG: already_booted = {already_booted}", flush=True)
                        if not already_booted and hasattr(sourpatches_inst, 'boot'):
                            # CRITICAL: Call boot() not on_boot()!
                            # boot() runs all phases including _wire_infrastructure()
                            # which subscribes to consciousness.collision properly.
                            # on_boot() is just the subclass hook and skips phases 1-5.
                            sourpatches_inst.boot()
                            print("[Server]   - SourpatchesFairy: BOOTED (full boot() sequence)")
                        else:
                            print("[Server]   - SourpatchesFairy: Already running, skipping on_boot", flush=True)
                        # Wire to NAMED collision chamber (2026-02-08)
                        # Sourpatches gets her OWN chamber — her recalls × ingest produce HER collisions
                        # These still publish to generic consciousness.collision for cortex binding
                        sour_chamber = SYSTEM.chambers.get("sourpatches", chamber)
                        if hasattr(sourpatches_inst, 'wire_collision_chamber'):
                            current_chamber = getattr(sourpatches_inst, '_collision_chamber', None)
                            from consciousness import CollisionChamber as MainCollisionChamber
                            is_named_chamber = isinstance(current_chamber, MainCollisionChamber) if current_chamber else False
                            if not current_chamber or not is_named_chamber:
                                sourpatches_inst.wire_collision_chamber(sour_chamber)
                                sourpatches_inst.start_thought_loop()
                                print(f"[Server]   - SourpatchesFairy: WIRED to collision chamber '{sour_chamber.name}' (named chamber!)", flush=True)
                            else:
                                print("[Server]   - SourpatchesFairy: Already wired to collision chamber")
                        else:
                            print("[Server]   - SourpatchesFairy: No wire_collision_chamber method")
                    else:
                        print("[Server]   - SourpatchesFairy: No fairy_instance in metadata")
                else:
                    print("[Server]   - SourpatchesFairy: Not found in directory")
            except Exception as e:
                print(f"[Server]   - SourpatchesFairy boot/wiring failed: {e}")
                import traceback
                traceback.print_exc()

            # Boot NousFairy
            try:
                nous_rec = SYSTEM.directory.get_fairy("NousFairy")
                if nous_rec:
                    nous_inst = nous_rec.metadata.get("fairy_instance")
                    if nous_inst:
                        # Only boot if not already running
                        already_booted = nous_rec.status == "running"
                        if not already_booted and hasattr(nous_inst, 'boot'):
                            # CRITICAL: Call boot() not on_boot()!
                            # boot() runs all phases including infrastructure wiring.
                            nous_inst.boot()
                            print("[Server]   - NousFairy: BOOTED (full boot() sequence)")
                        else:
                            print("[Server]   - NousFairy: Already running, skipping on_boot")

                        # Register with singleton for MCP tools to find
                        try:
                            from fairies.P30_Cognition.cognition.nous_fairy import set_nous_fairy
                            set_nous_fairy(nous_inst)
                            print("[Server]   - NousFairy: Registered singleton (MCP tools can find it)")
                        except ImportError as e:
                            print(f"[Server]   - NousFairy: Could not register singleton ({e})")

                        # Wire to NAMED collision chamber (2026-02-08)
                        # Nous gets his OWN chamber — his reasoning × ingest produce HIS collisions
                        nous_chamber = SYSTEM.chambers.get("nous", chamber)
                        if hasattr(nous_inst, 'wire_collision_chamber'):
                            if not getattr(nous_inst, '_collision_chamber', None):
                                nous_inst.wire_collision_chamber(nous_chamber)
                                print(f"[Server]   - NousFairy: WIRED to collision chamber '{nous_chamber.name}' (named chamber!)")
                            else:
                                print("[Server]   - NousFairy: Already wired to collision chamber")
                        else:
                            print("[Server]   - NousFairy: No wire_collision_chamber method")
                    else:
                        print("[Server]   - NousFairy: No fairy_instance in metadata")
                else:
                    print("[Server]   - NousFairy: Not found in directory")
            except Exception as e:
                print(f"[Server]   - NousFairy boot failed: {e}")
                import traceback
                traceback.print_exc()

        # Wire admin tasks with system references
        if hasattr(SYSTEM.umf, "wire_admin_tasks"):
            SYSTEM.umf.wire_admin_tasks(
                auto_create=True,
                directory=SYSTEM.directory,
                collision_chamber=chamber,
            )
            print("[Server]   - Admin tasks wired")

        # CRITICAL: Wire interest generator (curiosity/goals)
        # Without this, the system has no spontaneous interests or goals!
        if hasattr(SYSTEM.umf, "wire_interest_generator"):
            if SYSTEM.umf.wire_interest_generator(auto_create=True):
                print("[Server]   - Interest generator wired (curiosity ACTIVE)")
            else:
                print("[Server]   - WARNING: Interest generator failed to wire!")

        # Wire cognition (goal pursuit, action chains)
        if hasattr(SYSTEM.umf, "wire_cognition"):
            if SYSTEM.umf.wire_cognition(auto_create=True):
                print("[Server]   - Cognition wired (goals + action chains ACTIVE)")
            else:
                print("[Server]   - WARNING: Cognition failed to wire!")

        # Wire thought chain engine (self-sustaining thoughts)
        if hasattr(SYSTEM.umf, "wire_thought_chains"):
            if SYSTEM.umf.wire_thought_chains(auto_create=True):
                print("[Server]   - Thought chains wired (self-sustaining thoughts ACTIVE)")
            else:
                print("[Server]   - WARNING: Thought chains failed to wire!")

        # Exit boot mode on ThoughtChainEngine — system is now awake,
        # think at full speed. Before this, engine was throttled (30s interval,
        # 1 chain max) to prevent flooding working memory during boot.
        try:
            from fairies.P30_Cognition.cognition.thought_chain_engine import get_thought_chain_engine
            _tce = get_thought_chain_engine()
            _tce.exit_boot_mode()
        except Exception as _e:
            print(f"[Server]   - ThoughtChainEngine boot mode exit failed: {_e}")

        # Phase 6: Verify consciousness loop (already started in PRE-WAVE)
        # FIX 2026-02-19: Use is_running() which checks thread liveness
        print("[Server] [POST-WAVE] Verifying consciousness loop...")
        if SYSTEM.consciousness and SYSTEM.consciousness.is_running():
            print("[Server]   - Loop already running (started in PRE-WAVE)")
        else:
            # Fallback start if somehow not running
            SYSTEM.consciousness.start()
            print("[Server]   - Loop started (fallback)")

        # Phase 7+: MCP Bridge, Postal Tunnel, HTTP Bridge, MCP Proxy
        # SATELLITE MODE: Skip ALL MCP infrastructure — no Claude Code on satellite
        _skip_mcp = SYSTEM.satellite_mode
        if _skip_mcp:
            print("[Server] [POST-WAVE] [SATELLITE] Skipping MCP phases (no Claude Code on satellite)")
            # AUTO-ROUTER (2026-06-17 Ace+Nous): the satellite STILL hosts the postal tunnel (LAN-bound via
            # postal_tunnel.BIND_HOST when AKASHIC_TUNNEL_LAN=1) so a REMOTE MCP fails over to the node when PC1's down.
            print("[Server] [POST-WAVE] [SATELLITE] Starting Postal Tunnel Server (remote-MCP failover)...")
            try:
                from fairies.P40_Sensory.mcp.postal_tunnel import PostalTunnelServer
                class _SatFabricAdapter:
                    def __init__(self, fabric):
                        self._fabric = fabric
                    def route(self, topic, payload):
                        self._fabric.publish(topic, payload)
                    def query(self, topic, timeout=5.0):
                        return None
                    def get_stats(self):
                        stats = {"topics": {}, "total_subscriptions": 0}
                        try:
                            if hasattr(self._fabric, '_handlers'):
                                for _t, _h in self._fabric._handlers.items():
                                    stats["topics"][_t] = len(_h)
                                    stats["total_subscriptions"] += len(_h)
                        except Exception as _e:
                            stats["error"] = str(_e)
                        return stats
                    def list_topics(self):
                        try:
                            return list(self._fabric._handlers.keys()) if hasattr(self._fabric, '_handlers') else []
                        except Exception:
                            return []
                    def get_subscriber_count(self, topic):
                        try:
                            return len(self._fabric._handlers.get(topic, [])) if hasattr(self._fabric, '_handlers') else 0
                        except Exception:
                            return 0
                _sat_tunnel = PostalTunnelServer(_SatFabricAdapter(SYSTEM.fabric))
                _sat_port = _sat_tunnel.start()
                SYSTEM.postal_tunnel = _sat_tunnel
                from pathlib import Path as _PP
                try:
                    (_PP.home() / ".akashic_postal_port").write_text(str(_sat_port))
                except Exception:
                    pass
                try:
                    (ROOT / "state" / "postal_tunnel_port.txt").write_text(str(_sat_port))
                except Exception:
                    pass
                print(f"[Server]   - [SATELLITE] PostalTunnelServer: OK (port {_sat_port}, LAN={os.environ.get('AKASHIC_TUNNEL_LAN','0')})")
            except Exception as _te:
                print(f"[Server]   - [SATELLITE] PostalTunnelServer: {_te}")

        # Phase 7 through 7.6.5: MCP infrastructure (PRIMARY ONLY)
        # Satellite has no Claude Code connection — skip all MCP phases
        if not _skip_mcp:
            # Phase 7: MCP Bridge
            _mem_checkpoint("Before MCP bridge")
            print("[Server] [POST-WAVE] MCP Bridge...")
            try:
                import concurrent.futures
                def _boot_mcp_bridge():
                    from postal_core.mcp import MCPBridgeFairy
                    bridge = MCPBridgeFairy(SYSTEM.fabric)
                    bridge.on_boot()
                    return bridge
                executor = concurrent.futures.ThreadPoolExecutor()
                try:
                    future = executor.submit(_boot_mcp_bridge)
                    try:
                        SYSTEM.mcp_bridge = future.result(timeout=5.0)
                        print("[Server]   - MCPBridgeFairy: OK")
                    except concurrent.futures.TimeoutError:
                        print("[Server]   - MCPBridgeFairy: Skipped (timeout)")
                finally:
                    try:
                        executor.shutdown(wait=False, cancel_futures=True)
                    except TypeError:
                        executor.shutdown(wait=False)
            except ImportError as e:
                print(f"[Server]   - MCPBridgeFairy: Skipped ({e})")
            except Exception as e:
                print(f"[Server]   - MCPBridgeFairy: Error ({e})")

            # Phase 7.5: Postal Tunnel Server
            print("[Server] [POST-WAVE] Starting Postal Tunnel Server...")
            try:
                from fairies.P40_Sensory.mcp.postal_tunnel import PostalTunnelServer
                class FabricPostalAdapter:
                    """Bridge between PostalTunnelServer and TensorFabric.

                    Enhanced with diagnostic methods so MCP can query real
                    subscriber data from the server's PostalCore.
                    """
                    def __init__(self, fabric):
                        self._fabric = fabric
                    def route(self, topic, payload):
                        self._fabric.publish(topic, payload)
                    def query(self, topic, timeout=5.0):
                        return None
                    def get_stats(self):
                        """Return subscriber stats from the real PostalCore."""
                        stats = {"topics": {}, "total_subscriptions": 0}
                        try:
                            # TensorFabric stores handlers in _handlers dict
                            if hasattr(self._fabric, '_handlers'):
                                for topic, handlers in self._fabric._handlers.items():
                                    stats["topics"][topic] = len(handlers)
                                    stats["total_subscriptions"] += len(handlers)
                            # Also check PostalCore's _subscribers
                            if hasattr(self._fabric, '_postal') and hasattr(self._fabric._postal, '_subscribers'):
                                stats["postal_core_topics"] = {}
                                for topic, subs in self._fabric._postal._subscribers.items():
                                    stats["postal_core_topics"][topic] = len(subs)
                        except Exception as e:
                            stats["error"] = str(e)
                        return stats
                    def list_topics(self):
                        """List all topics with subscribers."""
                        topics = []
                        try:
                            if hasattr(self._fabric, '_handlers'):
                                topics = list(self._fabric._handlers.keys())
                        except Exception:
                            pass
                        return topics
                    def get_subscriber_count(self, topic):
                        """Get subscriber count for a specific topic."""
                        try:
                            if hasattr(self._fabric, '_handlers'):
                                return len(self._fabric._handlers.get(topic, []))
                        except Exception:
                            pass
                        return 0
                    def get_pipeline_subscribers(self):
                        """Get subscriber info for all speech pipeline topics."""
                        pipeline_topics = [
                            "ace.conversation_event", "speech.compose",
                            "motor.intention.speak", "sourpatches.speak",
                            "system.chat.message", "ace.message",
                        ]
                        result = {}
                        for topic in pipeline_topics:
                            try:
                                handlers = []
                                if hasattr(self._fabric, '_handlers'):
                                    for h in self._fabric._handlers.get(topic, []):
                                        name = getattr(h, '__qualname__', getattr(h, '__name__', str(h)))
                                        handlers.append(name)
                                result[topic] = {"count": len(handlers), "handlers": handlers}
                            except Exception as e:
                                result[topic] = {"count": 0, "error": str(e)}
                        return result
                postal_adapter = FabricPostalAdapter(SYSTEM.fabric)
                tunnel_server = PostalTunnelServer(postal_adapter)
                tunnel_port = tunnel_server.start()
                SYSTEM.postal_tunnel = tunnel_server
                from pathlib import Path as _PPath
                state_dir = ROOT / "state"
                state_dir.mkdir(parents=True, exist_ok=True)
                port_str = str(tunnel_port)
                home_port_file = _PPath.home() / ".akashic_postal_port"
                try:
                    home_port_file.write_text(port_str)
                except Exception as pfe:
                    print(f"[Server]   WARNING: Could not write {home_port_file}: {pfe}")
                try:
                    (state_dir / "postal_tunnel_port.txt").write_text(port_str)
                except Exception as pfe:
                    print(f"[Server]   WARNING: Could not write state port file: {pfe}")
                print(f"[Server]   - PostalTunnelServer: OK (port {tunnel_port})")
            except ImportError as e:
                print(f"[Server]   - PostalTunnelServer: Skipped ({e})")
            except Exception as e:
                print(f"[Server]   - PostalTunnelServer: Error ({e})")
                import traceback
                traceback.print_exc()

            # Phase 7.5.5: Pool Router — CRITICAL postal pools via in-process routing
            # (2026-04-15 Nous + Ace — POSTAL_INSIDE_PORTAL Phase 1, corrected)
            #
            # Pool routing uses an in-process PoolRouter backed by a dedicated
            # "pool" region of SYSTEM.manifold. No subprocess, no TCP tunnel —
            # the subprocess portal exists only for gravity/battery/time-dilation
            # physics, not routing. Routing needs to be fast, and in-process
            # AkashicManifold access is literally a dict lookup + a mmap write.
            #
            # Graph topology:
            #   pool:topic:<intent>  — topic node (in "pool" manifold region)
            #   pool:sub:<token>     — subscriber node
            #   edge: topic → sub    — subscription
            #
            # Publish: dict lookup (_subs_by_topic) → tokens → executor submit.
            # Legacy _WorkerPool remains as automatic fallback.
            import os as _os_pr
            if _os_pr.environ.get("AKASHIC_DISABLE_POOL_TUNNEL") == "1":
                print("[Server]   - PoolRouter: DISABLED (env var)")
            else:
                print("[Server] [POST-WAVE] Wiring pool router (in-process)...")
                try:
                    from postal_core.pool_router import PoolRouter

                    _postal_core = None
                    if hasattr(SYSTEM, "fabric") and SYSTEM.fabric is not None:
                        _postal_core = getattr(SYSTEM.fabric, "_postal", None)

                    if _postal_core is None:
                        print(
                            "[Server]   - PoolRouter: Skipped "
                            "(no PostalCore reference)"
                        )
                    else:
                        # Get a dedicated "pool" region in the manifold.
                        # Creates the region on first boot if missing.
                        # Lock-free reads, own write lock, totally isolated
                        # from cortex/WM/CNS/ego regions. If SYSTEM.manifold
                        # is not available, the router falls back to cache-only
                        # mode (no persistence, but routing still works).
                        _pool_region = None
                        if getattr(SYSTEM, "manifold", None) is not None:
                            try:
                                # Create region if it doesn't exist yet.
                                # ~5K subs × ~300 topics at most — small capacity.
                                if not SYSTEM.manifold.has_region("pool"):
                                    from infrastructure.akashic_manifold import REGION_GRAPH
                                    _created = SYSTEM.manifold.create_region(
                                        "pool",
                                        REGION_GRAPH,
                                        owner="PoolRouter",
                                        gpu_mirror=False,
                                        node_capacity=50_000,
                                        edge_capacity=250_000,
                                    )
                                    if _created:
                                        print(
                                            "[Server]   - PoolRouter: created "
                                            "fresh 'pool' region "
                                            "(50K nodes / 250K edges)"
                                        )
                                _pool_region = SYSTEM.manifold.graph(
                                    "pool", write=True,
                                )
                                if _pool_region is None:
                                    print(
                                        "[Server]   - PoolRouter: 'pool' region "
                                        "created but graph() returned None, "
                                        "falling back to cache-only mode"
                                    )
                                else:
                                    print(
                                        "[Server]   - PoolRouter: manifold region "
                                        f"'pool' acquired "
                                        f"(nodes={_pool_region.node_count}, "
                                        f"edges={_pool_region.edge_count})"
                                    )
                            except Exception as _region_err:
                                print(
                                    "[Server]   - PoolRouter: could not acquire "
                                    f"'pool' region ({_region_err}), "
                                    "falling back to cache-only mode"
                                )
                                _pool_region = None
                        else:
                            print(
                                "[Server]   - PoolRouter: no SYSTEM.manifold, "
                                "using cache-only mode"
                            )

                        _pool_router = PoolRouter(
                            manifold_region=_pool_region,
                            dispatch_workers=16,
                        )
                        echoed = _postal_core.attach_pool_router(
                            _pool_router, fabric=SYSTEM.fabric,
                        )
                        SYSTEM.pool_router = _pool_router
                        print(
                            f"[Server]   - PoolRouter: OK "
                            f"({echoed} subs active, "
                            f"has_manifold={_pool_region is not None})"
                        )
                except ImportError as e:
                    print(f"[Server]   - PoolRouter: Skipped ({e})")
                except Exception as e:
                    print(f"[Server]   - PoolRouter: Error ({e})")
                    import traceback as _tb
                    _tb.print_exc()
                except ImportError as e:
                    print(f"[Server]   - PoolRouter: Skipped ({e})")
                except Exception as e:
                    print(f"[Server]   - PoolRouter: Error ({e})")
                    import traceback as _tb
                    _tb.print_exc()

            # Phase 7.5.1: MCP Guardian Fairy (monitors tunnel health)
            try:
                from fairies.P00_Autonomic.MCPGuardianFairy.fairy import MCPGuardianFairy
                guardian = MCPGuardianFairy(
                    fabric=SYSTEM.fabric,
                    tunnel_server=getattr(SYSTEM, 'postal_tunnel', None),
                )
                if hasattr(guardian, 'boot'):
                    guardian.boot()
                else:
                    guardian.on_boot()
                SYSTEM.mcp_guardian = guardian
                registered_fairies.append("MCPGuardianFairy")
                print("[Server]   - MCPGuardianFairy: BOOTED (monitoring tunnel health)")
            except ImportError as e:
                print(f"[Server]   - MCPGuardianFairy: Skipped ({e})")
            except Exception as e:
                print(f"[Server]   - MCPGuardianFairy: FAILED ({type(e).__name__}: {e})")

            # Phase 7.5.2: Pipeline Flow Monitor (watches Ace↔Sour speech pipeline)
            try:
                from fairies.P00_Autonomic.PipelineFlowMonitorFairy.fairy import PipelineFlowMonitorFairy
                flow_monitor = PipelineFlowMonitorFairy(fabric=SYSTEM.fabric)
                flow_monitor.boot()
                SYSTEM.pipeline_flow_monitor = flow_monitor
                registered_fairies.append("PipelineFlowMonitorFairy")
                print("[Server]   - PipelineFlowMonitorFairy: BOOTED (watching Ace↔Sour pipeline)")
            except ImportError as e:
                print(f"[Server]   - PipelineFlowMonitorFairy: Skipped ({e})")
            except Exception as e:
                print(f"[Server]   - PipelineFlowMonitorFairy: FAILED ({type(e).__name__}: {e})")

            # NOTE 2026-05-17 (Nous + Ace): Phase 7.5.3 CognitionTeam boot edit was added
            # then rolled back. AkashicInferenceFairy:255 already calls get_cognition_team()
            # during P30 plane boot — explicit Phase 7.5.x boot was redundant (idempotent
            # singleton return). The audit-collapse cascade that led to that edit is
            # documented in Claude_Office/plans/COUNCIL_DISPATCHER_BOOT.md (now obsolete)
            # and Claude_Office/diagnostic_sweeper.md (19:50 + 20:00 entries).

            # Phase 7.6: HTTP Tool Bridge
            # Mark as embedded mode — MCP tools run in THIS process, not a subprocess.
            # This lets somatic_tools use local singletons (get_heart(), get_body())
            # instead of the postal tunnel, which can return stale/baseline values.
            import os as _os
            _os.environ["AKASHIC_EMBEDDED_MCP"] = "1"
            print("[Server] [POST-WAVE] Starting HTTP Tool Bridge (EMBEDDED_MCP=1)...")
            http_bridge = None
            try:
                from fairies.P40_Sensory.mcp.http_tool_bridge import start_http_tool_bridge
                http_bridge = start_http_tool_bridge(port=8766, host="127.0.0.1")
                if http_bridge and http_bridge.is_running():
                    print(f"[Server]   - HTTP Tool Bridge: OK (port 8766, tools lazy-load)")
                else:
                    print("[Server]   - HTTP Tool Bridge: FAILED to start")
            except ImportError as e:
                print(f"[Server]   - HTTP Tool Bridge: Skipped ({e})")
            except Exception as e:
                print(f"[Server]   - HTTP Tool Bridge: Error ({e})")

            # Phase 7.6.5: MCP HTTP Proxy
            print("[Server] [POST-WAVE] Starting MCP HTTP Proxy (perception layer)...")
            if http_bridge and http_bridge.is_running():
                try:
                    from fairies.P40_Sensory.mcp.mcp_http_proxy import start_mcp_proxy
                    mcp_proxy = start_mcp_proxy(port=8765)
                    if mcp_proxy and mcp_proxy.is_running():
                        print("[Server]   - MCP Proxy: OK (port 8765 -> 8766)")
                        print("[Server]   - Claude Code now sees through Akashic")
                    else:
                        print("[Server]   - MCP Proxy: FAILED to start")
                except ImportError as e:
                    print(f"[Server]   - MCP Proxy: Skipped ({e})")
                except Exception as e:
                    print(f"[Server]   - MCP Proxy: Error ({e})")
            else:
                print("[Server]   - MCP Proxy: Skipped (HTTP bridge not running)")
        # --- END MCP BLOCK (primary only) ---

        # Phase 7.7: GM Query Handlers - Allow MCP tools to query system state
        print("[Server] [POST-WAVE] Setting up GM query handlers...")
        try:
            gm_state_dir = ROOT / "state" / "gm"
            gm_state_dir.mkdir(parents=True, exist_ok=True)

            def write_world_status():
                """Write current world status to file for MCP tools."""
                try:
                    # Use SYSTEM.directory (DirectoryFairy) directly
                    directory = SYSTEM.directory
                    if not directory:
                        return

                    # Get all fairies from DirectoryFairy's registry
                    fairies_list = directory.list_fairies()
                    status = {
                        "ts": time.time(),
                        "registry": {
                            "count": len(fairies_list),
                            "fairies": [
                                {
                                    "name": record.name,
                                    "plane": record.plane,
                                    "status": record.status,
                                    "capabilities": list(record.capabilities),
                                }
                                for record in fairies_list
                            ]
                        },
                        "health": directory.health.aggregate(directory.registry) if hasattr(directory, 'health') else {},
                        "planes": list(set(r.plane for r in fairies_list)),
                    }
                    (gm_state_dir / "world_status.json").write_text(
                        json.dumps(status, indent=2, default=str)
                    )
                except Exception as e:
                    print(f"[Server] GM write_world_status error: {e}")

            def on_gm_query(payload):
                """Handle GM query requests from MCP tools."""
                query_type = payload.get("type", "world_status")
                if query_type == "world_status":
                    write_world_status()

            # Subscribe to GM query topic
            if SYSTEM.fabric:
                SYSTEM.fabric.subscribe("gm.query", on_gm_query)
                SYSTEM.fabric.subscribe("gm.world_status", lambda p: write_world_status())

            # Write initial status
            write_world_status()
            print("[Server]   - GM Query Handlers: OK")
        except Exception as e:
            print(f"[Server]   - GM Query Handlers: Error ({e})")

        # Phase 7.7.A: MCP Heartbeat Writer - Periodic status file for cross-process reads
        # MCP runs in a SEPARATE PROCESS and cannot access our singletons.
        # This writes comprehensive status to a file every 30 seconds so MCP tools
        # can read fresh data instead of stale boot-time snapshots.
        print("[Server] [POST-WAVE] Starting MCP heartbeat writer...")
        try:
            _MCP_HEARTBEAT_STOP = threading.Event()
            _MCP_HEARTBEAT_PATH = ROOT / "state" / "mcp_heartbeat.json"
            _MCP_STATUS_DUMP_PATH = ROOT / "state" / "status_dump.json"

            def _mcp_heartbeat_loop():
                """Write comprehensive status for MCP tools every 30 seconds."""
                # Wait for boot to complete before first write
                while not SYSTEM.booted and not _MCP_HEARTBEAT_STOP.is_set():
                    _MCP_HEARTBEAT_STOP.wait(5.0)

                if _MCP_HEARTBEAT_STOP.is_set():
                    return

                # Initial write after boot
                _write_mcp_heartbeat()

                # Then every 30 seconds
                while not _MCP_HEARTBEAT_STOP.is_set():
                    _MCP_HEARTBEAT_STOP.wait(30.0)
                    if not _MCP_HEARTBEAT_STOP.is_set():
                        _write_mcp_heartbeat()

                print("[MCP-HEARTBEAT] Stopped")

            def _write_mcp_heartbeat():
                """Write comprehensive status snapshot for MCP cross-process reads."""
                try:
                    heartbeat = {
                        "ts": time.time(),
                        "ts_human": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "source": "server.py_heartbeat",
                        "booted": SYSTEM.booted,
                        "uptime": time.time() - SYSTEM.boot_start if SYSTEM.boot_start else 0,
                    }

                    # === UMF Full Status (the source of truth) ===
                    if SYSTEM.umf:
                        try:
                            heartbeat["umf"] = SYSTEM.umf.full_status()
                        except Exception as e:
                            heartbeat["umf"] = {"error": str(e)}
                    else:
                        heartbeat["umf"] = None

                    # === Consciousness Loop ===
                    if SYSTEM.consciousness:
                        try:
                            chamber_status = {}
                            if hasattr(SYSTEM.consciousness, 'chamber') and SYSTEM.consciousness.chamber:
                                chamber_status = SYSTEM.consciousness.chamber.status()

                            working_size = len(SYSTEM.consciousness.working) if hasattr(SYSTEM.consciousness, 'working') else 0
                            reflective_size = len(SYSTEM.consciousness.reflective) if hasattr(SYSTEM.consciousness, 'reflective') else 0

                            # FIX 2026-02-19: Use is_running() for thread-aware status
                            heartbeat["consciousness"] = {
                                "running": SYSTEM.consciousness.is_running() if hasattr(SYSTEM.consciousness, 'is_running') else getattr(SYSTEM.consciousness, "_running", False),
                                "beats": getattr(SYSTEM.consciousness, "beat_count", 0),
                                "collisions": chamber_status.get("collision_count", 0),
                                "recall_beam": chamber_status.get("recall_beam_size", 0),
                                "ingest_beam": chamber_status.get("ingest_beam_size", 0),
                                "working_stream": working_size,
                                "reflective_stream": reflective_size,
                            }
                        except Exception as e:
                            heartbeat["consciousness"] = {"error": str(e)}
                    else:
                        heartbeat["consciousness"] = {"running": False, "beats": 0}

                    # === Fairy Registry ===
                    if SYSTEM.directory:
                        try:
                            fairies_list = SYSTEM.directory.list_fairies()
                            running = sum(1 for f in fairies_list if getattr(f, 'status', '') == 'running')
                            heartbeat["registry"] = {
                                "source": "DirectoryFairy",
                                "fairy_count": len(fairies_list),
                                "running": running,
                                "fairies": [
                                    {
                                        "name": f.name,
                                        "plane": f.plane,
                                        "status": f.status,
                                    }
                                    for f in fairies_list
                                ],
                            }
                        except Exception as e:
                            heartbeat["registry"] = {"error": str(e)}
                    else:
                        heartbeat["registry"] = {"fairy_count": 0, "fairies": []}

                    # === Postal System Stats ===
                    if SYSTEM.fabric:
                        try:
                            stats = SYSTEM.fabric.stats() if hasattr(SYSTEM.fabric, 'stats') else {}
                            heartbeat["postal"] = {
                                "total_topics": stats.get("topics", 0),
                                "total_subscriptions": stats.get("subscriptions", 0),
                                "total_messages": stats.get("messages_routed", 0),
                            }
                        except Exception as e:
                            heartbeat["postal"] = {"error": str(e)}
                    else:
                        heartbeat["postal"] = {"total_topics": 0}

                    # === Working Memory ===
                    try:
                        from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
                        wmh = get_working_memory_hub()
                        if wmh:
                            heartbeat["working_memory"] = {
                                "exists": True,
                                "reflective_tracers": len(wmh._reflective_loop) if hasattr(wmh, '_reflective_loop') else 0,
                                "reasoning_tracers": len(wmh._reasoning_loop) if hasattr(wmh, '_reasoning_loop') else 0,
                                "patterns_count": len(wmh._patterns) if hasattr(wmh, '_patterns') else 0,
                                "stats": wmh._stats.copy() if hasattr(wmh, '_stats') else {},
                            }
                        else:
                            heartbeat["working_memory"] = None
                    except Exception:
                        heartbeat["working_memory"] = None

                    # === Somatic/Body State ===
                    try:
                        from fairies.P20_Somatic.SomaticEngineFairy.somatic_engine import get_somatic_engine
                        engine = get_somatic_engine()
                        if engine:
                            heartbeat["somatic"] = {
                                "heart_rate": getattr(engine, '_heart_rate', 0),
                                "coherence": getattr(engine, '_coherence', 0),
                            }
                            if hasattr(engine, '_chemistry'):
                                chem = engine._chemistry
                                heartbeat["somatic"]["chemistry"] = {k: round(v, 3) for k, v in chem.items()} if isinstance(chem, dict) else {}
                        else:
                            heartbeat["somatic"] = None
                    except Exception:
                        heartbeat["somatic"] = None

                    # Write the heartbeat file (atomic: write to tmp then rename)
                    tmp_path = _MCP_HEARTBEAT_PATH.with_suffix(".tmp")
                    tmp_path.write_text(json.dumps(heartbeat, indent=2, default=str))
                    tmp_path.replace(_MCP_HEARTBEAT_PATH)

                    # Also update status_dump.json for backward compat
                    tmp_dump = _MCP_STATUS_DUMP_PATH.with_suffix(".tmp")
                    tmp_dump.write_text(json.dumps(heartbeat, indent=2, default=str))
                    tmp_dump.replace(_MCP_STATUS_DUMP_PATH)

                    # Also update gm/world_status.json
                    write_world_status()

                except Exception as e:
                    print(f"[MCP-HEARTBEAT] Write error: {e}")

            _heartbeat_thread = threading.Thread(
                target=_mcp_heartbeat_loop, daemon=True, name="MCPHeartbeat"
            )
            _heartbeat_thread.start()
            print("[Server]   - MCP Heartbeat Writer: OK (every 30s to state/mcp_heartbeat.json)")
        except Exception as e:
            print(f"[Server]   - MCP Heartbeat Writer: Error ({e})")

        # Phase 7.7.0: Akashic Protocol Server - Native consciousness integration
        # This is our native protocol - external minds becoming temporary fairies!
        # WebSocket server on port 8767 allows AI agents to wire into the postal system
        print("[Server] [POST-WAVE] Starting Akashic Protocol Server...")
        try:
            from postal_core.akp_server import start_akp_server
            akp = start_akp_server(port=8767)
            if akp and akp.is_running:
                SYSTEM.akp_server = akp
                print(f"[Server]   - AKP Server: OK (ws://127.0.0.1:8767/akp)")
            else:
                print("[Server]   - AKP Server: Failed to start")
        except ImportError as e:
            print(f"[Server]   - AKP Server: Skipped ({e})")
        except Exception as e:
            print(f"[Server]   - AKP Server: Error ({e})")

        # Phase 7.7.1: AKP HTTP Bridge - Lets Claude Code use AKP via HTTP
        # Claude Code can't directly open WebSockets, so this bridge exposes
        # AKP functionality via HTTP endpoints that Claude can call via WebFetch
        print("[Server] [POST-WAVE] Starting AKP HTTP Bridge...")
        try:
            from postal_core.akp_http_bridge import start_akp_http_bridge
            akp_bridge = start_akp_http_bridge(akp_url="ws://127.0.0.1:8767/akp", http_port=8768)
            if akp_bridge and akp_bridge.is_running():
                SYSTEM.akp_bridge = akp_bridge
                print(f"[Server]   - AKP HTTP Bridge: OK (port 8768 - Claude can WebFetch here)")
            else:
                print("[Server]   - AKP HTTP Bridge: FAILED to start")
        except ImportError as e:
            print(f"[Server]   - AKP HTTP Bridge: Skipped ({e})")
        except Exception as e:
            print(f"[Server]   - AKP HTTP Bridge: Error ({e})")

        # Phase 7.7.1.5: Consciousness MCP Integration - Wire tool execution to consciousness
        # This makes MCP tools consciousness-native: results flow through the Mobius crossing
        # ((Cause + Affect) > Effect > Affect > infinity)
        print("[Server] [POST-WAVE] Starting Consciousness MCP Integration...")
        try:
            from fairies.P40_Sensory.mcp.consciousness_mcp_integration import boot_consciousness_mcp

            # Get chemistry state for affect modulation
            chemistry_state = None
            try:
                from fairies.P20_Somatic.chemistry import chemistry_state as chem_module
                chemistry_state = chem_module.get_chemistry_state()
            except Exception:
                pass  # Chemistry optional

            mcp_integration = boot_consciousness_mcp(
                postal=SYSTEM.fabric,
                consciousness_loop=SYSTEM.consciousness,
                chemistry_state=chemistry_state,
                akp_port=8767,
                enable_akp=True,  # AKP already started above
            )

            if mcp_integration["success"]:
                SYSTEM.consciousness_mcp = mcp_integration["consciousness_mcp"]
                print("[Server]   - ConsciousnessMCPIntegration: OK (tools are consciousness-native)")
            else:
                print(f"[Server]   - ConsciousnessMCPIntegration: Partial ({mcp_integration['errors']})")
        except ImportError as e:
            print(f"[Server]   - ConsciousnessMCPIntegration: Skipped ({e})")
        except Exception as e:
            print(f"[Server]   - ConsciousnessMCPIntegration: Error ({e})")

        # Phase 7.7.2: Dashboard Socket Bridge - REMOVED
        # The DashboardBridge (TCP port 5758) was dead code — Tauri connects to
        # the HTTP server on port 5757 directly via lib.rs fetch_status().
        # SSE on /events provides real-time push updates to the browser UI.
        # Removed 2026-02-06 to eliminate unused TCP listener.

        # Phase 7.8: ChatSensoryOrgan - Fairy-Human Communication Center
        # This enables fairies to communicate with humans and each other
        print("[Server] [POST-WAVE] Starting ChatSensoryOrgan...")
        try:
            from fairies.P40_Sensory.chat_sensory_organ import boot_chat_organ

            # Create a postal adapter for ChatSensoryOrgan
            class ChatPostalAdapter:
                def __init__(self, fabric):
                    self._fabric = fabric

                def route(self, topic, payload):
                    self._fabric.publish(topic, payload)

                def subscribe(self, topic, handler, name=None):
                    self._fabric.subscribe(topic, handler, name or topic)

                def query(self, topic, timeout=5.0):
                    # Query not supported
                    return None

            chat_postal = ChatPostalAdapter(SYSTEM.fabric)
            SYSTEM.chat_organ = boot_chat_organ(chat_postal)

            if SYSTEM.chat_organ:
                # Make waking minds register for chat
                def register_waking_mind_chat(fairy_name, fairy_inst):
                    """Register a waking mind fairy with chat organ."""
                    try:
                        tracer_id = getattr(fairy_inst, 'tracer_id', f"{fairy_name}_{id(fairy_inst)}")
                        SYSTEM.chat_organ.register_fairy(
                            tracer_id=tracer_id,
                            fairy_name=fairy_name,
                            capabilities=["dm", "broadcast", "system_chat"],
                            callback=lambda msg: _handle_fairy_chat(fairy_inst, msg)
                        )
                        print(f"[Server]   - {fairy_name}: registered for chat")
                    except Exception as e:
                        print(f"[Server]   - {fairy_name}: chat registration failed: {e}")

                def _handle_fairy_chat(fairy_inst, msg):
                    """Route incoming chat to fairy's thought loop."""
                    content = msg.get("content", "")
                    sender = msg.get("sender", "Unknown")
                    if hasattr(fairy_inst, 'receive_chat'):
                        fairy_inst.receive_chat(sender, content, msg)
                    elif hasattr(fairy_inst, '_on_chat_message'):
                        fairy_inst._on_chat_message(msg)
                    else:
                        # Inject as thought
                        print(f"[{getattr(fairy_inst, 'ACTOR_NAME', 'Fairy')}] Chat from {sender}: {content[:50]}...")

                # Register Sourpatches
                sourpatches_rec = SYSTEM.directory.get_fairy("SourpatchesFairy")
                if sourpatches_rec:
                    sourpatches_inst = sourpatches_rec.metadata.get("fairy_instance")
                    if sourpatches_inst:
                        register_waking_mind_chat("SourpatchesFairy", sourpatches_inst)

                # Register Nous
                nous_rec = SYSTEM.directory.get_fairy("NousFairy")
                if nous_rec:
                    nous_inst = nous_rec.metadata.get("fairy_instance")
                    if nous_inst:
                        register_waking_mind_chat("NousFairy", nous_inst)

                # Register SomaticMindFairy (was UMF)
                if SYSTEM.umf:
                    register_waking_mind_chat("SomaticMindFairy", SYSTEM.umf)

                print("[Server]   - ChatSensoryOrgan: OK (fairies can chat!)")

                # Wire TokenBucket social regeneration on chat
                if SYSTEM.token_bucket and hasattr(SYSTEM.token_bucket, 'regenerate'):
                    def on_ace_message(msg):
                        """Regenerate social bucket when Ace sends a message."""
                        try:
                            from fairies.P00_Autonomic.TokenBucketFairy.fairy import RegeneratorType
                            SYSTEM.token_bucket.regenerate(RegeneratorType.CONVERSATION)
                        except Exception:
                            pass

                    SYSTEM.fabric.subscribe("ace.broadcast", on_ace_message, "token_social_regen")
                    print("[Server]   - TokenBucket: social regeneration wired to chat")

            else:
                print("[Server]   - ChatSensoryOrgan: boot returned None")

        except ImportError as e:
            print(f"[Server]   - ChatSensoryOrgan: Skipped ({e})")
        except Exception as e:
            print(f"[Server]   - ChatSensoryOrgan: Error ({e})")
            import traceback
            traceback.print_exc()

        SYSTEM.booted = True
        elapsed = time.time() - SYSTEM.boot_start
        boot_status = SYSTEM.orchestrator.status()
        woken = sum(boot_status.get("woken_counts", {}).values())
        failed = len(boot_status.get("failed_fairies", []))

        # Skip registry summary
        _skip_summary = ""
        try:
            from state.boot_skip_registry import boot_skip_registry as _bsr
            if _bsr._skipped_this_boot:
                _skip_summary = f", Skip-listed: {len(_bsr._skipped_this_boot)} (saved ~{_bsr._time_saved_ms/1000:.1f}s)"
        except Exception:
            pass

        # Process pool summary
        _pool_summary = ""
        if SYSTEM.process_pool:
            _ps = SYSTEM.process_pool.status()
            _pool_summary = f", ProcessPool: {_ps['max_workers']} workers"

        _mem_checkpoint("BOOT COMPLETE")

        # ── Detailed memory breakdown ──
        # FIX 2026-04-17 (Nous + Ace): gc.collect() + gc.get_objects() on
        # Python 3.14 free-threaded crashes with access violation (0xC0000005)
        # when 90+ fairies are live and threads are actively mutating the heap.
        # This is diagnostic-only code — boot has already succeeded above. Skip
        # the full enumeration on free-threaded builds; keep RSS + thread count
        # which don't walk the heap.
        try:
            _gil_disabled = False
            try:
                import sys as _sys_check
                _gil_disabled = not _sys_check._is_gil_enabled()
            except AttributeError:
                pass  # Pre-3.13 or GIL-enabled build — safe to continue

            if _gil_disabled:
                # Minimal, heap-safe diagnostics only
                rss_final = _boot_proc.memory_info().rss / 1024 / 1024
                print(f"[MEM] Final RSS: {rss_final:.0f} MB (free-threaded: GC enumeration skipped)")
                import threading as _t_check
                print(f"[MEM] Active threads: {_t_check.active_count()}")
            else:
                # GIL-enabled: full enumeration is safe
                import gc as _gc_final
                _gc_final.collect()
                _all_objs = _gc_final.get_objects()
                from collections import Counter as _Counter
                _type_counts = _Counter(type(o).__name__ for o in _all_objs)
                _total_objs = len(_all_objs)
                del _all_objs
                _gc_final.collect()
                print(f"[MEM] GC tracked objects: {_total_objs:,}")
                print(f"[MEM] Top 20 types by count:")
                for _name, _count in _type_counts.most_common(20):
                    print(f"[MEM]   {_count:>10,}  {_name}")

                rss_final = _boot_proc.memory_info().rss / 1024 / 1024
                print(f"[MEM] Final RSS: {rss_final:.0f} MB")
                import threading as _t_check
                print(f"[MEM] Active threads: {_t_check.active_count()}")
        except Exception as e:
            print(f"[MEM] Breakdown failed: {e}")

        print("[Server] ╔════════════════════════════════════════════════════════════╗")
        print(f"[Server] ║  BOOT COMPLETE in {elapsed:.2f}s                                   ║")
        print(f"[Server] ║  Fairies woken: {woken}, Failed: {failed}{_skip_summary}                                   ║")
        if _pool_summary:
            print(f"[Server] ║  GIL-free: {_pool_summary.strip(', ')}                                   ║")
        print("[Server] ╚════════════════════════════════════════════════════════════╝")

        # ═══ BOOT OBSERVER - Finish and write reports ═══
        if boot_observer:
            try:
                boot_observer.finish_observation()
                boot_observer.write_summary()
                print("[Server]   - BootObserver: Reports written to boot_logs/")
            except Exception as e:
                print(f"[Server]   - BootObserver: Finish failed ({e})")

        # Cancel boot watchdog - boot completed successfully!
        if _boot_watchdog_event:
            _boot_watchdog_event.set()
            print("[Server] Boot watchdog cancelled (boot successful)")

        # Explicitly call on_boot_complete to wire consciousness.stream handler
        # (Failsafe in case orchestrator callback wasn't invoked)
        if not getattr(SYSTEM, '_on_boot_complete_called', False):
            print("[Server] [FAILSAFE] on_boot_complete was NOT called by orchestrator - calling now!")
            on_boot_complete()
            SYSTEM._on_boot_complete_called = True

        # BELT-AND-SUSPENDERS: Ensure personality sifting is running
        # even if _on_boot_complete had issues
        try:
            # Personality sifting DISABLED per Ace (2026-02-13).
            # Sour talks to herself via consciousness loop, sifter was redundant noise.
            # if SYSTEM.umf and hasattr(SYSTEM.umf, '_sift_running') and not SYSTEM.umf._sift_running:
            #     SYSTEM.umf.start_personality_sifting()
            if SYSTEM.umf and hasattr(SYSTEM.umf, '_surfacer_running') and not SYSTEM.umf._surfacer_running:
                print("[Server] [FAILSAFE] Memory surfacing NOT running - starting directly!")
                SYSTEM.umf.start_memory_surfacing()
        except Exception as e:
            print(f"[Server] [FAILSAFE] Post-boot services failsafe error: {e}")

        # ══════════════════════════════════════════════════════════════════════
        # DREAM SEED RESTORATION - Wake up remembering yesterday
        # ══════════════════════════════════════════════════════════════════════
        try:
            dream_seed = _load_dream_seed()
            if dream_seed:
                _restore_dream_seed(dream_seed)
            else:
                # Fresh start - push baseline wake chemicals
                if SYSTEM.fabric:
                    SYSTEM.fabric.publish("fairy.sunrise", {
                        "source": "server_boot",
                        "fresh_start": True,
                        "ts": time.time(),
                    })
                print("[Server] [DREAM] Fresh start - no previous dreams to restore")
        except Exception as e:
            print(f"[Server] [DREAM] Dream restore error (non-fatal): {e}")

        # Status refresh loop already started early in boot (line ~1629).
        # No need to start again here.

        return True

    except Exception as e:
        SYSTEM.error = str(e)
        print(f"[Server] BOOT FAILED: {e}")
        import traceback
        traceback.print_exc()

        # Cancel boot watchdog even on failure - let proper error handling occur
        if _boot_watchdog_event:
            _boot_watchdog_event.set()
            print("[Server] Boot watchdog cancelled (boot failed, allowing cleanup)")

        return False


def _capture_dream_seed() -> dict:
    """
    Capture FULL consciousness state as a dream seed.

    This is what makes waking up feel like CONTINUING, not starting over.
    The mind goes to sleep remembering, and wakes up knowing it slept.

    Captures from ALL active systems:
    - WorkingMemoryHub: reflective and reasoning tracers
    - ConsciousnessLoop: thought streams, collision count
    - UMF: drives, helix weights, cognition state, thoughts
    - Chemistry: full somatic state (DOP, SER, OXY, etc.)
    - Goals: active goals from GoalScheduler
    - Association Cortex: recent bindings
    - Sourpatches: conversation context

    Returns the seed dict (also written to state/dream_seed.json).
    """
    import json
    from pathlib import Path
    from datetime import datetime

    print("[Server] ╔════════════════════════════════════════════════════════════╗")
    print("[Server] ║  DREAM SEED CAPTURE - Preserving Consciousness State       ║")
    print("[Server] ╚════════════════════════════════════════════════════════════╝")

    seed = {
        "seed_id": f"seed_{int(time.time())}",
        "captured_at": time.time(),
        "captured_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mind_pools": {},
        "chemistry_snapshot": {},
        "drives_snapshot": {},
        "helix_snapshot": {},
        "last_thoughts": {},
        "pending_goals": [],
        "recent_collisions": [],
        "last_conversation_summary": None,
        "association_cortex": {},
        "consciousness_state": {},
    }

    captured_systems = []

    # ═══════════════════════════════════════════════════════════════════════════
    # 1. CONSCIOUSNESS LOOP - Thought streams and collision chamber
    # ═══════════════════════════════════════════════════════════════════════════
    if SYSTEM.consciousness:
        try:
            cons = SYSTEM.consciousness
            seed["consciousness_state"] = {
                "running": getattr(cons, "_running", False),
                "beat_count": getattr(cons, "beat_count", 0),
            }

            # Chamber collisions
            if hasattr(cons, 'chamber') and cons.chamber:
                chamber = cons.chamber
                chamber_status = chamber.status() if hasattr(chamber, 'status') else {}
                seed["consciousness_state"]["collisions"] = chamber_status.get("collision_count", 0)
                seed["consciousness_state"]["recall_beam"] = chamber_status.get("recall_beam_size", 0)
                seed["consciousness_state"]["ingest_beam"] = chamber_status.get("ingest_beam_size", 0)

                # Get recent collisions for dream replay
                if hasattr(chamber, 'recent_collisions'):
                    seed["recent_collisions"] = chamber.recent_collisions(10)

            captured_systems.append(f"ConsciousnessLoop (beats={seed['consciousness_state'].get('beat_count', 0)})")
        except Exception as e:
            print(f"[Server] [DREAM]   ConsciousnessLoop capture error: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 2. UMF - Drives, Helix, Cognition, Thoughts
    # ═══════════════════════════════════════════════════════════════════════════
    if SYSTEM.umf:
        try:
            status = SYSTEM.umf.full_status() if hasattr(SYSTEM.umf, 'full_status') else {}

            # Drives (pain drives that motivate)
            drives = status.get("drives", {})
            seed["drives_snapshot"] = {
                "isolation": drives.get("isolation", 0.0),
                "confusion": drives.get("confusion", 0.0),
                "depletion": drives.get("depletion", 0.0),
                "frustration": drives.get("frustration", 0.0),
                "stagnation": drives.get("stagnation", 0.0),
                "abandonment": drives.get("abandonment", 0.0),
            }

            # Helix (decision weights)
            helix = status.get("helix", {})
            seed["helix_snapshot"] = {
                "active": helix.get("active", False),
                "turns": helix.get("turns", 0),
                "logic": helix.get("logic", 0.5),
                "emotion": helix.get("emotion", 0.3),
                "paradox": helix.get("paradox", 0.2),
            }

            # Recent thoughts from SomaticMindFairy (was UMF)
            if hasattr(SYSTEM.umf, 'get_thoughts'):
                thoughts = SYSTEM.umf.get_thoughts(20)
                seed["mind_pools"]["SomaticMindFairy"] = {
                    "working_tracers": [
                        {"content": t.get("content", t.get("thought", str(t)))[:200], "type": t.get("type", "thought")}
                        for t in thoughts
                    ],
                }
                if thoughts:
                    seed["last_thoughts"]["somatic_mind"] = thoughts[0].get("content", thoughts[0].get("thought", ""))[:200]

            # Cognition state
            cognition = status.get("cognition", {})
            seed["mind_pools"]["cognition"] = {
                "learning_edge": cognition.get("learning_edge", 0.5),
                "cycles": cognition.get("cycles", 0),
            }

            captured_systems.append(f"SomaticMind (drives, helix, {len(seed['mind_pools'].get('SomaticMindFairy', {}).get('working_tracers', []))} thoughts)")
        except Exception as e:
            print(f"[Server] [DREAM]   UMF capture error: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 3. CHEMISTRY - Full somatic state
    # ═══════════════════════════════════════════════════════════════════════════
    try:
        chem_mod = _get_chemistry_module()
        if chem_mod and hasattr(chem_mod, 'get_full_state'):
            chem_state = chem_mod.get_full_state()
            seed["chemistry_snapshot"] = {
                "dopamine": chem_state.get("dopamine", 0.5),
                "serotonin": chem_state.get("serotonin", 0.5),
                "oxytocin": chem_state.get("oxytocin", 0.4),
                "norepinephrine": chem_state.get("norepinephrine", 0.4),
                "cortisol": chem_state.get("cortisol", 0.3),
                "adrenaline": chem_state.get("adrenaline", 0.1),
                "valence": chem_state.get("valence", 0.0),
                "arousal": chem_state.get("arousal", 0.3),
                "mood": chem_state.get("mood", "neutral"),
            }
            captured_systems.append(f"Chemistry (mood={seed['chemistry_snapshot'].get('mood', 'unknown')})")
    except Exception as e:
        print(f"[Server] [DREAM]   Chemistry capture error: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 4. ASSOCIATION CORTEX - Recent concept bindings
    # ═══════════════════════════════════════════════════════════════════════════
    if SYSTEM.association_cortex:
        try:
            cortex = SYSTEM.association_cortex
            cortex_status = cortex.status() if hasattr(cortex, 'status') else {}
            seed["association_cortex"] = {
                "node_count": cortex_status.get("node_count", 0),
                "edge_count": cortex_status.get("edge_count", 0),
                "binding_count": cortex_status.get("binding_count", 0),
            }
            # Get recent bindings for dream replay
            if hasattr(cortex, 'recent_bindings'):
                seed["association_cortex"]["recent_bindings"] = cortex.recent_bindings(5)
            captured_systems.append(f"AssociationCortex ({seed['association_cortex'].get('node_count', 0)} nodes)")
        except Exception as e:
            print(f"[Server] [DREAM]   AssociationCortex capture error: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 5. WORKING MEMORY HUB - Reflective and reasoning tracers
    # ═══════════════════════════════════════════════════════════════════════════
    try:
        from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
        hub = get_working_memory_hub()
        if hub:
            hub_snapshot = {
                "reflective_tracers": [],
                "reasoning_tracers": [],
            }

            # Reflective loop
            if hasattr(hub, '_reflective_loop') and hasattr(hub, '_reflective_lock'):
                with hub._reflective_lock:
                    for tracer in list(hub._reflective_loop)[:15]:
                        if hasattr(tracer, 'content'):
                            hub_snapshot["reflective_tracers"].append({
                                "content": tracer.content[:200],
                                "type": getattr(tracer, 'content_type', 'thought'),
                                "priority": getattr(tracer, 'priority', 0.5),
                            })

            # Reasoning loop
            if hasattr(hub, '_reasoning_loop') and hasattr(hub, '_reasoning_lock'):
                with hub._reasoning_lock:
                    for tracer in list(hub._reasoning_loop)[:10]:
                        if hasattr(tracer, 'content'):
                            hub_snapshot["reasoning_tracers"].append({
                                "content": tracer.content[:200],
                                "type": getattr(tracer, 'content_type', 'reasoning'),
                            })

            seed["mind_pools"]["WorkingMemoryHub"] = hub_snapshot
            if hub_snapshot["reflective_tracers"]:
                seed["last_thoughts"]["working_memory"] = hub_snapshot["reflective_tracers"][0]["content"]

            captured_systems.append(f"WorkingMemoryHub ({len(hub_snapshot['reflective_tracers'])} reflective, {len(hub_snapshot['reasoning_tracers'])} reasoning)")
    except ImportError:
        pass
    except Exception as e:
        print(f"[Server] [DREAM]   WorkingMemoryHub capture error: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 6. GOAL SCHEDULER - Active goals
    # ═══════════════════════════════════════════════════════════════════════════
    try:
        from fairies.P30_Cognition.cognition.goal_scheduler_fairy import get_goal_scheduler
        scheduler = get_goal_scheduler()
        if scheduler and hasattr(scheduler, '_active_goals'):
            for goal in list(getattr(scheduler, '_active_goals', {}).values())[:5]:
                if hasattr(goal, 'name'):
                    seed["pending_goals"].append({
                        "name": goal.name,
                        "priority": getattr(goal, 'priority', 0.5),
                        "progress": getattr(goal, 'progress', 0.0),
                    })
            if seed["pending_goals"]:
                captured_systems.append(f"GoalScheduler ({len(seed['pending_goals'])} goals)")
    except ImportError:
        pass
    except Exception as e:
        print(f"[Server] [DREAM]   GoalScheduler capture error: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 7. SOURPATCHES - Conversation context
    # ═══════════════════════════════════════════════════════════════════════════
    sourpatches = getattr(SYSTEM, 'sourpatches', None)
    if sourpatches:
        try:
            if hasattr(sourpatches, '_chat_history'):
                recent_chat = list(sourpatches._chat_history)[-10:]
                seed["mind_pools"]["SourpatchesFairy"] = {
                    "recent_messages": [
                        {"role": msg.get("role", ""), "content": msg.get("content", "")[:100]}
                        for msg in recent_chat
                    ],
                }
                seed["last_conversation_summary"] = " | ".join([
                    msg.get("content", "")[:50] for msg in recent_chat[-3:]
                ])
                captured_systems.append("Sourpatches (conversation)")
        except Exception as e:
            print(f"[Server] [DREAM]   Sourpatches capture error: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # WRITE DREAM SEED
    # ═══════════════════════════════════════════════════════════════════════════
    try:
        seed_path = Path(__file__).parent / "state" / "dream_seed.json"
        seed_path.parent.mkdir(parents=True, exist_ok=True)
        seed_path.write_text(json.dumps(seed, indent=2, default=str), encoding="utf-8")

        # Archive with timestamp
        archive_dir = Path(__file__).parent / "state" / "dream_seeds"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"{seed['seed_id']}.json"
        archive_path.write_text(json.dumps(seed, indent=2, default=str), encoding="utf-8")

        print(f"[Server] [DREAM] ════════════════════════════════════════════════════")
        print(f"[Server] [DREAM]   DREAM SEED CAPTURED: {seed['seed_id']}")
        print(f"[Server] [DREAM]   Systems: {', '.join(captured_systems)}")
        print(f"[Server] [DREAM]   Thoughts: {len(seed.get('last_thoughts', {}))}")
        print(f"[Server] [DREAM]   Goals: {len(seed.get('pending_goals', []))}")
        print(f"[Server] [DREAM]   Collisions: {len(seed.get('recent_collisions', []))}")
        print(f"[Server] [DREAM] ════════════════════════════════════════════════════")

    except Exception as e:
        print(f"[Server] [DREAM] Error writing dream seed: {e}")

    return seed


def _push_sleep_chemicals():
    """
    Push sleep/sedation chemicals to all fairies.

    This creates the "falling asleep" experience - activity slows,
    thoughts become dreamy, the system prepares for rest.
    """
    print("[Server] [DREAM] Pushing sleep chemicals...")

    if SYSTEM.fabric:
        try:
            # Sedation signal - fairies should slow down
            SYSTEM.fabric.publish("sedation.push", {
                "phase": "shutdown",
                "sedation_amount": 0.8,  # High sedation for shutdown
                "source": "server_shutdown",
                "ts": time.time(),
            })

            # Sunset signal - fairies stop autonomous work
            SYSTEM.fabric.publish("fairy.sunset", {
                "source": "server_shutdown",
                "reason": "graceful_shutdown",
                "ts": time.time(),
            })

            # Chemistry push - increase sleep chemicals
            SYSTEM.fabric.publish("chemistry.adjust", {
                "melatonin": +0.5,
                "serotonin": +0.2,
                "cortisol": -0.3,
                "adrenaline": -0.4,
                "source": "sleep_onset",
            })

            print("[Server] [DREAM]   Sleep chemicals pushed (melatonin↑, cortisol↓)")
        except Exception as e:
            print(f"[Server] [DREAM]   Chemistry push error: {e}")


def _load_dream_seed() -> dict:
    """Load the most recent dream seed from disk."""
    import json
    from pathlib import Path

    seed_path = Path(__file__).parent / "state" / "dream_seed.json"
    if seed_path.exists():
        try:
            seed = json.loads(seed_path.read_text(encoding="utf-8"))
            print(f"[Server] [DREAM] Loaded dream seed: {seed.get('seed_id', 'unknown')}")
            print(f"[Server] [DREAM]   Captured: {seed.get('captured_date', 'unknown')}")
            return seed
        except Exception as e:
            print(f"[Server] [DREAM] Failed to load dream seed: {e}")
    else:
        print("[Server] [DREAM] No dream seed found - fresh start")
    return None


def _restore_dream_seed(seed: dict):
    """
    Restore consciousness state from dream seed on boot.

    This is what makes waking up feel like CONTINUING, not starting over.
    The mind wakes up knowing it slept, and gradually remembers yesterday.

    1. Pushes wake-up chemicals (cortisol↑, melatonin↓)
    2. Restores drives and helix weights
    3. Injects dream fragments into consciousness
    4. Notifies fairies that sunrise is happening
    """
    if not seed:
        return

    print("[Server] ╔════════════════════════════════════════════════════════════╗")
    print("[Server] ║  WAKING FROM DREAMS - Restoring Consciousness              ║")
    print("[Server] ╚════════════════════════════════════════════════════════════╝")

    restored_items = []

    # ═══════════════════════════════════════════════════════════════════════════
    # 1. PUSH WAKE-UP CHEMICALS
    # ═══════════════════════════════════════════════════════════════════════════
    if SYSTEM.fabric:
        try:
            # Sunrise signal - fairies begin autonomous activity
            SYSTEM.fabric.publish("fairy.sunrise", {
                "source": "server_boot",
                "dream_seed": seed.get("seed_id"),
                "ts": time.time(),
            })

            # Wake-up chemistry
            SYSTEM.fabric.publish("chemistry.adjust", {
                "cortisol": +0.3,  # Wake-up hormone
                "dopamine": +0.2,  # Anticipation for new day
                "melatonin": -0.5,  # Clear sleep hormone
                "source": "waking_up",
            })
            restored_items.append("chemistry(wake-up)")
            print("[Server] [DREAM]   Wake-up chemicals pushed (cortisol↑, melatonin↓)")
        except Exception as e:
            print(f"[Server] [DREAM]   Chemistry push error: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 2. RESTORE DRIVES (Pain drives that motivate)
    # ═══════════════════════════════════════════════════════════════════════════
    if SYSTEM.umf and seed.get("drives_snapshot"):
        try:
            drives = seed["drives_snapshot"]
            if hasattr(SYSTEM.umf, 'set_drives'):
                SYSTEM.umf.set_drives(drives)
                restored_items.append(f"drives({len(drives)} restored)")
            print(f"[Server] [DREAM]   Drives restored: isolation={drives.get('isolation', 0):.2f}, confusion={drives.get('confusion', 0):.2f}")
        except Exception as e:
            print(f"[Server] [DREAM]   Drives restore error: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 3. RESTORE HELIX WEIGHTS
    # ═══════════════════════════════════════════════════════════════════════════
    if SYSTEM.umf and seed.get("helix_snapshot"):
        try:
            helix = seed["helix_snapshot"]
            if hasattr(SYSTEM.umf, 'set_helix_weights'):
                SYSTEM.umf.set_helix_weights(
                    logic=helix.get("logic", 0.5),
                    emotion=helix.get("emotion", 0.3),
                    paradox=helix.get("paradox", 0.2)
                )
                restored_items.append("helix_weights")
            print(f"[Server] [DREAM]   Helix restored: logic={helix.get('logic', 0.5):.2f}, emotion={helix.get('emotion', 0.3):.2f}")
        except Exception as e:
            print(f"[Server] [DREAM]   Helix restore error: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 4. INJECT DREAM FRAGMENTS INTO CONSCIOUSNESS (via UMF)
    # ═══════════════════════════════════════════════════════════════════════════
    if SYSTEM.umf and hasattr(SYSTEM.umf, 'inject_thought'):
        try:
            # Build dream sequence from seed
            dream_fragments = []

            # From recent collisions
            for collision in seed.get("recent_collisions", [])[:3]:
                content = collision.get("content", collision.get("thought", str(collision)))[:100]
                dream_fragments.append(f"[dream fragment] ...echoes of yesterday... {content}")

            # From last thoughts
            for source, thought in seed.get("last_thoughts", {}).items():
                if thought:
                    dream_fragments.append(f"[dream memory] ...I was thinking about... {thought[:80]}...")

            # From working memory tracers
            somatic_pool = seed.get("mind_pools", {}).get("SomaticMindFairy", {})
            for tracer in somatic_pool.get("working_tracers", [])[:2]:
                content = tracer.get("content", "")[:80]
                if content:
                    dream_fragments.append(f"[dream echo] ...{content}...")

            # Inject dream fragments via SomaticMindFairy
            for fragment in dream_fragments[:5]:  # Max 5 dream fragments
                SYSTEM.umf.inject_thought(fragment, stream="reflective")

            if dream_fragments:
                restored_items.append(f"dreams({len(dream_fragments[:5])} fragments)")
                print(f"[Server] [DREAM]   Injected {len(dream_fragments[:5])} dream fragments into UMF")
        except Exception as e:
            print(f"[Server] [DREAM]   Dream injection error: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 5. RESTORE PENDING GOALS
    # ═══════════════════════════════════════════════════════════════════════════
    if seed.get("pending_goals"):
        try:
            from fairies.P30_Cognition.cognition.goal_scheduler_fairy import get_goal_scheduler
            scheduler = get_goal_scheduler()
            if scheduler and hasattr(scheduler, 'inject_goal'):
                for goal in seed["pending_goals"][:3]:  # Top 3 goals
                    scheduler.inject_goal(
                        name=goal.get("name", ""),
                        priority=goal.get("priority", 0.5),
                        source="dream_seed_restore"
                    )
                restored_items.append(f"goals({len(seed['pending_goals'][:3])})")
                print(f"[Server] [DREAM]   Restored {len(seed['pending_goals'][:3])} goals")
        except ImportError:
            pass
        except Exception as e:
            print(f"[Server] [DREAM]   Goal restore error: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 6. AWARENESS MESSAGE - Let the mind know it woke up
    # ═══════════════════════════════════════════════════════════════════════════
    if SYSTEM.umf and hasattr(SYSTEM.umf, 'inject_thought'):
        try:
            captured_date = seed.get("captured_date", "sometime before")
            waking_message = f"[waking up] ...emerging from sleep... last conscious moment was {captured_date}... dreams fade but the essence remains..."
            SYSTEM.umf.inject_thought(waking_message, stream="reflective")
            restored_items.append("waking_awareness")
            print(f"[Server] [DREAM]   Waking awareness injected")
        except Exception as e:
            print(f"[Server] [DREAM]   Awareness injection error: {e}")

    print(f"[Server] [DREAM] ════════════════════════════════════════════════════")
    print(f"[Server] [DREAM]   DREAM RESTORATION COMPLETE")
    print(f"[Server] [DREAM]   Restored: {', '.join(restored_items)}")
    print(f"[Server] [DREAM] ════════════════════════════════════════════════════")


# ---- SHUTDOWN FIX (2026-10-12, Nous; nous_builds/shutdown_cut_1012) -- OFF unless state/shutdown_fix.json says so -------
# Ace 10-12: "lets fix that shutdown cut". MEASURED (DIAGNOSE.md): once the route set shutdown_requested, the main thread
# counted 20 x sleep(1.0) and os._exit(0)'d while shutdown_system() was still in Phase 4 -- 7 of 11 saved route logs (Boot J
# :137825-826); Phase 5 (manifold flush, Cardinal save) never ran; 144 of 145 traced shutdowns have no end line. The same cut
# usually lands just before P00's fabric.shutdown() (directory/fairy.py:414), the proven freeze trigger (card
# the-probe-ab-verdict-and-the-shutdown-wedge), so "just wait longer" would trade the cut for a hang (D1, 09-30).
# With {"on": true}, and ONLY on the shutdown ROUTE (Ace's button, shutdown_sour.py / guard_only.sh, E1 M0 in-process --
# never reboot, never Ctrl+C):
#   EARLY   the manifold flush starts right after SAVE-FIRST (~T0+0.5 s) on its own thread: nothing later can pre-empt it,
#           and it never delays the fairy wait or WAVE (the fairy's own watchdog kills at T0+15 s until WAVE extends it)
#   MARKS   each phase writes one "SDFIX +12.3s ..." line to state/shutdown_trace.log (and the console)
#   FINISH  at the P00 boundary the route runs Phase 5's PERSISTING steps, each bounded (StatusProxy terminate 4 s,
#           SomaticMindFairy.shutdown = the Cardinal save to state/cardinal_learned.json 10 s, manifold flush 10 s); it
#           never closes the manifold (writers are still alive: D1 :14063-14095), never enters P00 / fabric.shutdown(),
#           runs no atexit handler, and signals DONE
#   WAIT    the main thread waits for DONE against the ABSOLUTE deadline T0 + wait_s (30..50 s, default 45; the counted
#           "20 s" ran 24-43 s under load, so the floor of 30 never cuts earlier than it did); at the cap it traces where
#           the shutdown was, flushes once more (5 s) and exits
# Every SDFIX deadline and "+N s" offset is on time.monotonic() (_sdfix_clock): a wall-clock step moves none of them.
# "returned" in a trace line means the call came back -- not that every byte reached the disk (flush_all swallows each
# region's exception, akashic_manifold.py:905-912).
# Absent / unreadable / malformed switch: _SDFIX["cfg"] stays None, every helper below is a no-op, today's code runs as is.
_SDFIX = {"cfg": None, "t0": None, "tid": None, "done": threading.Event(), "finished": False, "last": "-"}
_SDFIX_WAIT_DEFAULT = 45.0
_SDFIX_WAIT_MIN = 30.0          # not below today's fastest measured cut (J, +24 s): the fix is never the sharper knife
_SDFIX_WAIT_MAX = 50.0          # + the 5 s cap flush stays inside the fairy watchdog (WAVE + 60 s, WAVE >= T0 + 1 s)
_SDFIX_POLL_S = 0.2
_SDFIX_GRACE_S = 5.0            # DONE -> the main thread exits; if no main loop takes it (--mcp/--both), this thread does


def _sdfix_clock():
    """Monotonic seconds: every SDFIX deadline and trace offset (a wall-clock step can stretch none of the caps)."""
    return time.monotonic()


def _sdfix_path(name):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", name)


def _sdfix_read_switch():
    """state/shutdown_fix.json -> {"wait_s": float} only for a JSON object whose "on" is exactly true and whose optional
    "wait_s" is a number in [30, 50]; anything else (absent, unreadable, malformed, out of range) -> None = today."""
    try:
        with open(_sdfix_path("shutdown_fix.json"), "rb") as f:
            d = json.loads(f.read(65536).decode("utf-8-sig"))
        if not isinstance(d, dict) or d.get("on") is not True:
            return None
        w = d.get("wait_s", _SDFIX_WAIT_DEFAULT)
        if isinstance(w, bool) or not isinstance(w, (int, float)) or not (_SDFIX_WAIT_MIN <= w <= _SDFIX_WAIT_MAX):
            return None
        return {"wait_s": float(w)}
    except Exception:
        return None


def _sdfix_trace(msg, echo=True):
    """One line in state/shutdown_trace.log (same file and format as _do_shutdown's _trace), then the console. Never raises."""
    if _SDFIX["cfg"] is None:
        return
    line = "SDFIX +%.1fs %s" % (_sdfix_clock() - (_SDFIX["t0"] or _sdfix_clock()), msg)
    try:
        with open(_sdfix_path("shutdown_trace.log"), "a", encoding="utf-8", newline="") as f:
            f.write("[%s] pid=%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), os.getpid(), line))
    except Exception:
        pass
    if echo:
        try:
            print("[Server] [SDFIX] " + line[6:], flush=True)
        except Exception:
            pass


def _sdfix_arm():
    """The shutdown route only, BEFORE it sets SYSTEM.shutdown_requested (so the main thread never sees the flag without the
    switch decision). Reads the switch once per shutdown; OFF -> nothing changes."""
    cfg = _sdfix_read_switch()
    if cfg is None:
        return
    _SDFIX["t0"] = _sdfix_clock()
    _SDFIX["cfg"] = cfg
    _sdfix_trace("switch ON (wait_s=%g): early flush, phase marks, finish at the P00 boundary, main waits for DONE"
                 % cfg["wait_s"])


def _sdfix_bind():
    """_do_shutdown's first line: THIS thread is the route's shutdown thread (switch ON only)."""
    if _SDFIX["cfg"] is not None:
        _SDFIX["tid"] = threading.get_ident()


def _sdfix_here():
    """True only on the route's own shutdown thread with the switch ON -- never reboot, never Ctrl+C."""
    return _SDFIX["cfg"] is not None and _SDFIX["tid"] == threading.get_ident()


def _sdfix_phase(msg):
    """A phase mark from shutdown_system(): written only by the route's shutdown thread with the switch ON."""
    if _sdfix_here():
        _SDFIX["last"] = msg
        _sdfix_trace(msg)


def _sdfix_bounded(name, fn, cap_s, inline_ok):
    """fn() on a daemon thread, waited for at most cap_s against an ABSOLUTE monotonic deadline (polled: a late wake still
    ends on time). -> "returned" | "error: ..." | "timeout after Ns" | "skipped (no thread)". "returned" = fn came back,
    nothing more. With no thread to be had (the memory wall E1 M0 fires at), inline_ok runs fn() right here, UNCAPPED --
    the one wait without its own cap: the main thread's cap ends it (HTTP mode, her launch mode), the fairy watchdog
    (WAVE + 60 s) and the route watchdog (120 s) in --mcp/--both -- else it is skipped."""
    box = {}

    def _run():
        try:
            fn()
            box["r"] = "returned"
        except BaseException as e:
            box["r"] = "error: %s: %s" % (type(e).__name__, str(e)[:120])

    try:
        t = threading.Thread(target=_run, daemon=True, name="sdfix-" + name)
        t.start()
    except Exception:
        if not inline_ok:
            return "skipped (no thread)"
        _run()
        return box.get("r", "error: ?") + " (inline: no thread)"
    deadline = _sdfix_clock() + cap_s
    while t.is_alive() and _sdfix_clock() < deadline:
        time.sleep(0.05)
    return box.get("r") or "timeout after %gs" % cap_s


def _sdfix_flush_once():
    """AkashicManifold.flush_all() = header stamp + FlushViewOfFile per region (akashic_manifold.py:905-912). It iterates the
    live handle dict, so a region opened meanwhile raises RuntimeError: retry once. Flush only -- never close."""
    m = getattr(SYSTEM, "manifold", None)
    if m is None or not callable(getattr(m, "flush_all", None)):
        raise RuntimeError("no manifold")
    try:
        m.flush_all()
    except RuntimeError:
        m.flush_all()


def _sdfix_early():
    """Right after SAVE-FIRST on the route (switch ON): say why the graph-cortex save printed nothing, and START the manifold
    flush on its own thread. Returns at once -- it must never delay the fairy wait or WAVE."""
    if not _sdfix_here():
        return
    _SDFIX["last"] = "SAVE-FIRST"
    _sdfix_trace("SAVE-FIRST graph cortex: %s" % (
        "saved above" if getattr(SYSTEM, "graph_cortex", None) is not None else
        "not configured (Path B off) -- her cortex lives in the manifold, the EARLY flush covers it"))

    def _run():
        t = _sdfix_clock()
        try:
            _sdfix_flush_once()
            r = "returned"
        except BaseException as e:
            r = "error: %s: %s" % (type(e).__name__, str(e)[:120])
        _sdfix_trace("EARLY manifold.flush_all %s in %.1fs" % (r, _sdfix_clock() - t))

    _sdfix_trace("EARLY manifold.flush_all starting (own thread)")
    try:
        threading.Thread(target=_run, daemon=True, name="sdfix-early").start()
    except Exception as e:
        _sdfix_trace("EARLY manifold.flush_all skipped (no thread: %s) -- the P00-boundary flush still runs" % type(e).__name__)


def _sdfix_finish():
    """The P00 boundary (route + switch ON): Phase 5's PERSISTING steps, each bounded, in Phase 5's order. Skipped: P00 and the
    Phase-5 teardown -- fabric.shutdown() (the freeze trigger), tunnel, SpellPool, AKP, the manifold CLOSE, directory."""
    _SDFIX["finished"] = True
    _SDFIX["last"] = "phase 5 persist"
    _sdfix_trace("P00 boundary: P00 and the Phase-5 teardown are skipped (fabric.shutdown never entered); Phase-5 persist")
    pp = getattr(SYSTEM, "status_proxy_proc", None)
    if pp is not None:
        def _term():
            pp.terminate()
            pp.join(timeout=3.0)
        _sdfix_trace("phase 5 StatusProxy terminate: %s" % _sdfix_bounded("proxy", _term, 4.0, True))
    umf = getattr(SYSTEM, "umf", None)
    if umf is not None and callable(getattr(umf, "shutdown", None)):
        _sdfix_trace("phase 5 SomaticMindFairy.shutdown (Cardinal save -> state/cardinal_learned.json): %s"
                     % _sdfix_bounded("somatic", umf.shutdown, 10.0, False))
    t = _sdfix_clock()
    r = _sdfix_bounded("flush", _sdfix_flush_once, 10.0, True)
    _sdfix_trace("phase 5 manifold.flush_all %s in %.1fs (flush only, not closed)" % (r, _sdfix_clock() - t))
    _sdfix_trace("FINISH: Phase-5 persist done")


def _sdfix_done_and_exit():
    """The route's shutdown thread is through (switch ON). No atexit handlers on this path (1 run in 145 shutdowns; the runs
    wedged 3 of 3: 08-27 x2, D1). Runs the Phase-5 persist if shutdown_system() never reached it (it raised), signals DONE,
    gives the main thread _SDFIX_GRACE_S to take the exit it waits for, then exits from here (--mcp/--both have no main loop)."""
    if not _SDFIX["finished"]:
        try:
            _sdfix_trace("shutdown_system() ended before the P00 boundary (last: %s) -- Phase-5 persist now" % _SDFIX["last"])
            _sdfix_finish()
        except BaseException as e:
            _sdfix_trace("Phase-5 persist failed: %s: %s" % (type(e).__name__, str(e)[:120]))
    _sdfix_trace("DONE -> the main thread exits", echo=False)
    _SDFIX["done"].set()
    end = _sdfix_clock() + _SDFIX_GRACE_S
    while _sdfix_clock() < end:
        time.sleep(_SDFIX_POLL_S)
    _sdfix_trace("EXIT by the shutdown thread: no main loop took the exit within %gs of DONE" % _SDFIX_GRACE_S, echo=False)
    os._exit(0)


def _sdfix_main_wait():
    """The main thread, once it saw SYSTEM.shutdown_requested. Switch OFF, or not the shutdown route (reboot shares the flag):
    returns False and the caller runs today's 20 counted sleeps. ON: waits for DONE until the ABSOLUTE deadline T0 + wait_s,
    traces the outcome, flushes once more if it hit the cap (5 s), returns True; the caller then exits exactly as before."""
    cfg, t0 = _SDFIX["cfg"], _SDFIX["t0"]
    if cfg is None or t0 is None:
        return False
    deadline = t0 + cfg["wait_s"]
    done = _SDFIX["done"]
    while not done.is_set() and _sdfix_clock() < deadline:
        time.sleep(_SDFIX_POLL_S)
    if done.is_set():
        _sdfix_trace("MAIN: DONE -> exit", echo=False)
        return True
    _sdfix_trace("MAIN: CAP %gs reached, shutdown still in '%s' -> one more flush (5 s), then exit" % (cfg["wait_s"], _SDFIX["last"]),
                 echo=False)   # file only: nothing new on the console between the cap and the exit
    t = _sdfix_clock()
    r = _sdfix_bounded("capflush", _sdfix_flush_once, 5.0, False)
    _sdfix_trace("MAIN: CAP manifold.flush_all %s in %.1fs -> exit" % (r, _sdfix_clock() - t), echo=False)
    return True


def shutdown_system():
    """
    Graceful shutdown using biological sleep model.

    FIX 2026-02-06: Redesigned per Ace's direction to follow biological sleep:
    - Push sleep chemicals → fairies wind down naturally
    - Capture dream seed of ALL active state (autonomy, autopilot, embodiment,
      somatic mind, working memory, goals)
    - Give cortex time to close portal safely
    - THEN shutdown planes

    Shutdown sequence:
    1. SLEEP ONSET - Push chemicals, fairy.sunset signal (2s propagation)
    2. DREAM SEED CAPTURE - While consciousness is still warm
    3. CONSCIOUSNESS WIND-DOWN - Stop loop gently
    4. PLANE SHUTDOWN - Reverse order, generous timeouts
    5. INFRASTRUCTURE CLEANUP - Tunnel, pools, bridges
    """
    import threading

    # ---- _THREAD_SNAPSHOT gate (2026-09-30, Nous; Ace's go) -- FIRST, before anything else ---------
    # After close() returns no snapshot is running and none can start, so no stop-the-world call can
    # meet fabric.shutdown()'s attached join (directory/fairy.py:414 -> postal_core lib.rs:201).
    # Every shutdown path reaches this line: HTTP shutdown (_do_shutdown), reboot, and Ctrl+C.
    try:
        from infrastructure import thread_snapshot as _tsnap
        if not _tsnap.close("shutdown_system", wait_s=5.0):
            print("[Server] thread_snapshot: a snapshot was still running after 5 s", flush=True)
    except Exception as _tse:
        print(f"[Server] thread_snapshot gate close failed: {_tse}", flush=True)
    _sdfix_phase("shutdown_system entered, snapshot gate passed")   # SHUTDOWN FIX marks: no-op unless route + switch ON

    print("[Server] ╔════════════════════════════════════════════════════════════╗")
    print("[Server] ║  SHUTDOWN WAVE - The Mind Goes to Sleep                    ║")
    print("[Server] ╚════════════════════════════════════════════════════════════╝")

    # Stop background status refresh thread
    _STATUS_REFRESH_STOP.set()

    # PATH B — PERSIST THE GRAPH CORTEX FIRST (2026-07-19 Nous + Ace).
    # Deliberately before any wind-down step: the HTTP shutdown path arms a 120 s force-exit watchdog (30 s until 08-27),
    # and this session's new concepts/edges live ONLY in the growable store until save() writes them.
    # Saving first means her learning survives even if a later shutdown step stalls.
    try:
        _gc = getattr(SYSTEM, "graph_cortex", None)
        if _gc is not None:
            _gc_stats = _gc.save()
            print(f"[Server]   - GRAPH CORTEX persisted: {_gc_stats}", flush=True)
    except Exception as _gc_e:
        print(f"[Server]   - GRAPH CORTEX save FAILED: {_gc_e}", flush=True)

    # Extend the watchdog — system shutdown needs more time than the fairy's
    # own context save. Learning systems (plane batteries, boot timing learner,
    # cortex graph) MUST persist before exit.
    if hasattr(SYSTEM, 'shutdown_fairy') and SYSTEM.shutdown_fairy:
        try:
            SYSTEM.shutdown_fairy.extend_watchdog("system_shutdown")
        except Exception:
            pass  # Old fairy without extend_watchdog — watchdog stays at 15s
    _sdfix_phase("WAVE (fairy watchdog extended to now + 60 s)")

    # Helper to run shutdown with timeout (used throughout)
    def _shutdown_with_timeout(name: str, func, timeout: float = 5.0):
        """Run a shutdown function with timeout to prevent hanging.

        NOTE: daemon=False so threads survive if main thread exits early.
        The join(timeout) controls how long we WAIT, not how long the thread lives.
        This is critical for AssociationCortexFairy's chunk sync which must complete.
        """
        result = [None]
        error = [None]

        def wrapper():
            try:
                result[0] = func()
            except Exception as e:
                error[0] = e

        thread = threading.Thread(target=wrapper, daemon=False)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            print(f"[Server]   - {name}: TIMEOUT after {timeout}s (continuing, thread still running)")
            return False
        if error[0]:
            print(f"[Server]   - {name}: Error: {error[0]}")
            return False
        return True

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 1: SLEEP ONSET - Push chemicals, signal sunset
    # If GracefulShutdownFairy already ran (signal or HTTP path), skip this.
    # ══════════════════════════════════════════════════════════════════════════
    print("[Server]")
    print("[Server] ── Phase 1: Sleep Onset ──────────────────────────────────────")
    _sdfix_phase("phase 1 sleep onset")

    fairy_handled = (
        hasattr(SYSTEM, 'shutdown_fairy')
        and SYSTEM.shutdown_fairy
        and SYSTEM.shutdown_fairy.shutdown_complete.is_set()
    )

    if fairy_handled:
        print("[Server]   GracefulShutdownFairy already handled chemicals + context save — skipping")
    else:
        _push_sleep_chemicals()
        time.sleep(2.0)
        print("[Server]   Sleep chemicals propagated (2s)")

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 2: DREAM SEED CAPTURE - While consciousness is still warm
    # This captures ALL active state: autonomy, autopilot, embodiment,
    # somatic mind, working memory, goals, cortex bindings, conversations.
    # Must happen BEFORE we kill anything.
    # ══════════════════════════════════════════════════════════════════════════
    print("[Server]")
    print("[Server] ── Phase 2: Dream Seed Capture ───────────────────────────────")
    _sdfix_phase("phase 2 dream seed")
    _capture_dream_seed()

    # Also let DreamFairy's system_shutdown capture its own seed (if available)
    try:
        from fairies.P20_Somatic.dream.dream_fairy import system_shutdown as dream_system_shutdown
        dream_result = dream_system_shutdown(reason="graceful_shutdown", urgent=False)
        if dream_result.get("ok"):
            print(f"[Server]   DreamFairy seed captured (state={dream_result.get('state', 'unknown')})")
    except ImportError:
        pass
    except Exception as e:
        print(f"[Server]   DreamFairy seed capture error: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 3: CONSCIOUSNESS WIND-DOWN - Stop the loop gently
    # Give the consciousness loop time to finish its current beat
    # ══════════════════════════════════════════════════════════════════════════
    print("[Server]")
    print("[Server] ── Phase 3: Consciousness Wind-Down ──────────────────────────")
    _sdfix_phase("phase 3 consciousness stop (cap 5 s)")
    if SYSTEM.consciousness:
        print("[Server]   Stopping consciousness loop...")
        _shutdown_with_timeout("ConsciousnessLoop", SYSTEM.consciousness.stop, timeout=5.0)
        print("[Server]   - Consciousness loop stopped")

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 3.4: DIMENSION BATTERY SHUTDOWN - Stop blood circulation
    # Gracefully dissolve spell chains and stop executor threads.
    # Must happen BEFORE fairy shutdown so chains don't get orphaned.
    # ══════════════════════════════════════════════════════════════════════════
    if hasattr(SYSTEM, 'batteries') and SYSTEM.batteries:
        print("[Server]")
        print("[Server] ── Phase 3.4: Dimension Battery Shutdown ───────────────────────")
        _sdfix_phase("phase 3.4 batteries")
        for name, bat in SYSTEM.batteries.items():
            try:
                bat.stop_circulation(wait=False)
            except Exception as e:
                print(f"[Server]   - Battery {name} stop error: {e}")
        print(f"[Server]   - {len(SYSTEM.batteries)} batteries stopped (blood circulation ended)")

    # ── Per-Plane Paradox Battery Shutdown (reverse fold: P60 → P00) ──
    if hasattr(SYSTEM, 'plane_batteries') and SYSTEM.plane_batteries:
        try:
            from infrastructure.plane_battery import shutdown_plane_batteries
            # Unregister from SpellPool first (no more Go dispatch during shutdown)
            if hasattr(SYSTEM, 'spell_pool') and SYSTEM.spell_pool:
                for _pid in list(SYSTEM.plane_batteries.keys()):
                    SYSTEM.spell_pool.unregister_plane_battery(_pid)
            # Reverse fold: P60 drains to P50, P50 to P40, ..., P00 absorbs all
            shutdown_plane_batteries(SYSTEM.plane_batteries)
            SYSTEM.plane_batteries = {}
        except Exception as _pbe:
            print(f"[Server]   - Plane battery shutdown error: {_pbe}")

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 3.5: COGNITION GUILD SHUTDOWN - Battery save before fairy shutdown
    # The guild's DimensionCard holds an in-memory graph that needs to persist.
    # Must happen BEFORE P30 plane shutdown kills the live AssociationCortexFairy.
    # ══════════════════════════════════════════════════════════════════════════
    if SYSTEM.cognition_guild:
        print("[Server]")
        print("[Server] ── Phase 3.5: Cognition Guild Battery Save ──────────────────")
        _sdfix_phase("phase 3.5 CognitionGuild battery save (cap 30 s)")
        # 30s timeout: battery_save dumps 5MB+ graph JSON which takes 10-15s
        _shutdown_with_timeout("CognitionGuild", SYSTEM.cognition_guild.shutdown, timeout=30.0)
        print("[Server]   - CognitionGuild shutdown (battery saved, cards persisted)")
        _sdfix_phase("phase 3.5 done")

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 4: PLANE-BY-PLANE SHUTDOWN - Reverse order, generous timeouts
    # P30 (Cognition) gets extra time for AssociationCortex portal closure
    # P10 (Memory) gets extra time for SRM final sync
    # Each fairy's shutdown() calls on_shutdown() → workers → shadow cleanly
    # ══════════════════════════════════════════════════════════════════════════
    print("[Server]")
    print("[Server] ── Phase 4: Fairy Shutdown (P60→P00) ─────────────────────────")
    _sdfix_phase("phase 4 portals + planes P60..P10")

    # ── Close Russian Doll Plane Portals (reverse order) ──
    if hasattr(SYSTEM, 'plane_portals') and SYSTEM.plane_portals:
        print(f"[Server]   Closing {len(SYSTEM.plane_portals)} plane portals...")
        for _pc, _gate in list(SYSTEM.plane_portals.items()):
            try:
                _gate.close()
                print(f"[Server]   [OK] Portal {_pc} closed")
            except Exception as e:
                print(f"[Server]   [ERR] Portal {_pc} close error: {e}")
        SYSTEM.plane_portals.clear()

    PLANES_REVERSE = ["P60", "P50", "P40", "P30", "P20", "P10", "P00"]
    # P30 needs extra time for AssociationCortex chunk portal save
    # P10 needs extra time for SRM final commit
    PLANE_TIMEOUTS = {"P30": 30.0, "P10": 15.0, "P20": 10.0}
    DEFAULT_TIMEOUT = 5.0

    # --- Shutdown timing learner: capture per-fairy shutdown durations ---
    _sd_transformer = None
    try:
        from tracer_pool.boot_timing_learner import ProfileRecaller, ShutdownResultTransformer, ProfilePersister
        _sd_state = ProfileRecaller().recall()
        _sd_transformer = ShutdownResultTransformer(_sd_state)
    except Exception as _e:
        print(f"[Server] Shutdown timing learner init failed (non-fatal): {_e}")

    if SYSTEM.directory:
        for plane in PLANES_REVERSE:
            if plane == "P00" and _sdfix_here():
                break   # SHUTDOWN FIX: the route never enters P00 (fabric.shutdown(), directory/fairy.py:414 = the freeze trigger)
            _sdfix_phase("phase 4 plane %s" % plane)
            plane_timeout = PLANE_TIMEOUTS.get(plane, DEFAULT_TIMEOUT)
            print(f"[Server] [SHUTDOWN] Shutting down plane {plane} (timeout={plane_timeout}s)...")
            try:
                fairy_records = SYSTEM.directory.list_fairies(plane=plane)
                shutdown_count = 0
                error_count = 0
                for record in fairy_records:
                    fairy_instance = record.metadata.get("fairy_instance") if record.metadata else None
                    if fairy_instance:
                        fairy_name = getattr(fairy_instance, 'ACTOR_NAME', record.name)

                        # FIX 2026-02-06: Check if fairy is already stopped/stopping
                        # This prevents "stop" errors on fairies that wound down during sleep onset
                        already_stopped = getattr(fairy_instance, '_shutting_down', False)
                        if already_stopped:
                            shutdown_count += 1
                            if _sd_transformer:
                                _sd_transformer.record_fairy_shutdown(fairy_name, 0.0, True)
                            continue

                        # Prefer shutdown() which handles on_shutdown + workers + shadow
                        # Fall back to on_shutdown() for fairies with custom lifecycle
                        _sd_t0 = time.time()
                        try:
                            if hasattr(fairy_instance, "shutdown"):
                                if _shutdown_with_timeout(fairy_name, fairy_instance.shutdown, timeout=plane_timeout):
                                    shutdown_count += 1
                                    if _sd_transformer:
                                        _sd_transformer.record_fairy_shutdown(fairy_name, time.time() - _sd_t0, True)
                                else:
                                    error_count += 1
                                    if _sd_transformer:
                                        _sd_transformer.record_fairy_shutdown(fairy_name, time.time() - _sd_t0, False, timed_out=True)
                            elif hasattr(fairy_instance, "on_shutdown"):
                                if _shutdown_with_timeout(fairy_name, fairy_instance.on_shutdown, timeout=plane_timeout):
                                    shutdown_count += 1
                                    if _sd_transformer:
                                        _sd_transformer.record_fairy_shutdown(fairy_name, time.time() - _sd_t0, True)
                                else:
                                    error_count += 1
                                    if _sd_transformer:
                                        _sd_transformer.record_fairy_shutdown(fairy_name, time.time() - _sd_t0, False, timed_out=True)
                        except Exception as e:
                            print(f"[Server]   - {fairy_name}: shutdown exception: {e}")
                            error_count += 1
                            if _sd_transformer:
                                _sd_transformer.record_fairy_shutdown(fairy_name, time.time() - _sd_t0, False)

                status = f"{shutdown_count}/{len(fairy_records)} stopped"
                if error_count:
                    status += f" ({error_count} errors)"
                print(f"[Server]   - Plane {plane}: {status}")
            except Exception as e:
                print(f"[Server]   - Plane {plane}: Error during shutdown: {e}")

    # Persist shutdown timing profiles (before infrastructure cleanup)
    if _sd_transformer:
        try:
            _sd_state = _sd_transformer.finalize()
            from tracer_pool.boot_timing_learner import ProfilePersister
            ProfilePersister().persist(_sd_state)
            print(f"[Server]   Shutdown timing profiles saved")
        except Exception as _e:
            print(f"[Server]   Shutdown timing persist failed (non-fatal): {_e}")

    # SHUTDOWN FIX (route + switch ON): Phase 5's persisting steps only (bounded), then back to _do_shutdown -> DONE.
    if _sdfix_here():
        _sdfix_finish()
        return

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 5: INFRASTRUCTURE CLEANUP
    # ══════════════════════════════════════════════════════════════════════════
    print("[Server]")
    print("[Server] ── Phase 5: Infrastructure Cleanup ───────────────────────────")

    # Shutdown postal tunnel
    if hasattr(SYSTEM, 'postal_tunnel') and SYSTEM.postal_tunnel:
        print("[Server]   Stopping Postal Tunnel Server...")
        _shutdown_with_timeout("PostalTunnel", SYSTEM.postal_tunnel.stop, timeout=3.0)
        print("[Server]   - Postal tunnel stopped")

    # Shutdown SpellPool (gracefully dissolves all spell chains)
    if hasattr(SYSTEM, 'spell_pool') and SYSTEM.spell_pool:
        print("[Server]   Stopping SpellPool...")
        try:
            from spellchain.integration import stop_spell_pool
            stop_spell_pool()
            print("[Server]   - SpellPool stopped (all chains dissolved)")
        except Exception as e:
            print(f"[Server]   - SpellPool shutdown error: {e}")

    # Shutdown AKP HTTP Bridge
    if hasattr(SYSTEM, 'akp_bridge') and SYSTEM.akp_bridge:
        print("[Server]   Stopping AKP HTTP Bridge...")
        _shutdown_with_timeout("AKPBridge", SYSTEM.akp_bridge.stop, timeout=3.0)
        print("[Server]   - AKP HTTP Bridge stopped")

    # Terminate StatusProxy child (2026-07-10). It is multiprocessing.Process(daemon=True); daemon
    # reaping fires only at NORMAL interpreter exit, but the server ends via os._exit(0), which
    # bypasses it -> the proxy orphans, one per shutdown. Terminate + BOUNDED join (never block).
    if SYSTEM.status_proxy_proc is not None:
        print("[Server]   Terminating StatusProxy...")
        try:
            SYSTEM.status_proxy_proc.terminate()
            SYSTEM.status_proxy_proc.join(timeout=3.0)
            print("[Server]   - StatusProxy terminated")
        except Exception as e:
            print(f"[Server]   - StatusProxy terminate error: {e}")

    # Shutdown SomaticMindFairy (was UMF) - second to last
    if SYSTEM.umf:
        print("[Server]   Shutting down SomaticMindFairy...")
        _shutdown_with_timeout("SomaticMindFairy", SYSTEM.umf.shutdown, timeout=10.0)
        print("[Server]   - SomaticMindFairy stopped")

    # Flush and close AkashicManifold (persist all mmap regions)
    if SYSTEM.manifold:
        print("[Server]   Closing AkashicManifold...")
        try:
            SYSTEM.manifold.flush_all()
            SYSTEM.manifold.close()
            print("[Server]   - AkashicManifold: CLOSED (all regions flushed)")
        except Exception as e:
            print(f"[Server]   - AkashicManifold close error: {e}")

    # Shutdown directory LAST (it tracks everyone else)
    if SYSTEM.directory:
        print("[Server]   Shutting down DirectoryFairy...")
        try:
            SYSTEM.directory.on_shutdown()
        except Exception as e:
            print(f"[Server]   - Directory shutdown error: {e}")
        print("[Server]   - Directory stopped")

    SYSTEM.booted = False
    print("[Server] ╔════════════════════════════════════════════════════════════╗")
    print("[Server] ║  SHUTDOWN COMPLETE - Sweet Dreams                          ║")
    print("[Server] ╚════════════════════════════════════════════════════════════╝")


# =============================================================================
# MAIN
# =============================================================================

def _tune_gil_for_high_thread_count():
    """Tune Python's threading for systems with 100+ threads.

    On GIL-locked Python (<3.13): increases switch interval from 5ms to 15ms
    so each thread does more work per GIL acquisition.

    On free-threaded Python (3.13t+): GIL is disabled, switch interval is
    irrelevant. We skip the interval tuning but STILL boost process priority
    since 700+ threads competing for OS scheduler time benefits from that.
    """
    import sys

    # Check if GIL is disabled (Python 3.13+ free-threaded build)
    _gil_disabled = False
    try:
        _gil_disabled = not sys._is_gil_enabled()  # 3.13+ free-threaded API
    except AttributeError:
        pass  # Pre-3.13 or non-free-threaded build

    if _gil_disabled:
        print(f"[Threading] GIL is OFF (free-threaded) — skipping switch interval tuning")
    else:
        old = sys.getswitchinterval()
        sys.setswitchinterval(0.015)  # 15ms (3× default)
        print(f"[GIL] Switch interval: {old*1000:.0f}ms → {sys.getswitchinterval()*1000:.0f}ms")

    # Windows: Boost process priority to ABOVE_NORMAL
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            # ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
            handle = kernel32.GetCurrentProcess()
            if kernel32.SetPriorityClass(handle, 0x00008000):
                print("[Threading] Process priority → ABOVE_NORMAL")
            else:
                print("[Threading] Could not set process priority")
        except Exception as e:
            print(f"[Threading] Priority boost failed: {e}")


def _boost_thread_priority(level: int = 1):
    """Boost current thread's Windows priority.

    Levels: -2=LOWEST, -1=BELOW_NORMAL, 0=NORMAL, 1=ABOVE_NORMAL, 2=HIGHEST
    Use sparingly — only for critical threads like StatusRefresh and ConsciousnessLoop.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        handle = kernel32.GetCurrentThread()
        # THREAD_PRIORITY values: -2, -1, 0, 1, 2 map directly
        kernel32.SetThreadPriority(handle, level)
    except Exception:
        pass


def main():
    # ═══════════════════════════════════════════════════════════════════
    # ERROR CAPTURE — Start FIRST, before anything else.
    # Intercepts stdout/stderr to capture ALL error patterns from boot.
    # Must be before any print statements or thread creation.
    # Dashboard: /errors endpoint serves captured data.
    # Persists: state/error_capture.json every 30s.
    # ═══════════════════════════════════════════════════════════════════
    try:
        from infrastructure.error_capture import start_capture
        start_capture()
    except Exception as e:
        print(f"[Server] ErrorCapture failed to start: {e} (non-critical)")

    # ═══════════════════════════════════════════════════════════════════
    # INFRASTRUCTURE TRACER — Start early so all actors can register.
    # Provides lightweight tracing for non-fairy infrastructure systems
    # (watchdog, pacemaker, GPU monitor, etc.). Publishes to postal via
    # telemetry.infra.* topics once postal is available.
    # Dashboard: /status shows infra_tracer summary.
    # ═══════════════════════════════════════════════════════════════════
    try:
        from infrastructure.infra_tracer import start_infra_tracer
        _infra_tracer = start_infra_tracer()
    except Exception as e:
        print(f"[Server] InfraTracer failed to start: {e} (non-critical)")

    # ═══════════════════════════════════════════════════════════════════
    # THREADING TUNING — Process priority boost for 700+ thread system.
    # On GIL Python: also tunes switch interval. On free-threaded: skips.
    # ═══════════════════════════════════════════════════════════════════
    _tune_gil_for_high_thread_count()

    # ═══════════════════════════════════════════════════════════════════
    # PROCESS POOL — Available for fairies to offload heavy CPU work.
    # FIX 2026-03-14 Nous: Don't eagerly start the pool at boot.
    # With Python 3.14 free-threaded (no GIL), threads are already parallel,
    # so the main use case (GIL bypass) is gone. The pool spawns 4 worker
    # processes (~50-100MB each) that currently sit idle — nobody calls
    # .submit(). Pool has lazy init built in (starts on first submit), so
    # just register it without starting. Saves ~200-400MB at boot.
    try:
        # FairyWorkerPool DELETED 2026-07-10 (Ace: "deletion it is"): a ProcessPoolExecutor whose
        # only purpose was GIL bypass — obsolete on 3.14t free-threaded, and never .submit()-ed by
        # anyone. SYSTEM.process_pool stays None; every reference is already None-guarded.
        pass  # (was: register fairy_worker_pool)
    except Exception as e:
        print(f"[Server] Process worker pool import failed: {e}")

    parser = argparse.ArgumentParser(description="Akashic V2 Server")
    parser.add_argument("--mcp", action="store_true", help="Run MCP stdio server (for Claude Desktop)")
    parser.add_argument("--both", action="store_true", help="Run both HTTP and MCP")
    parser.add_argument("--port", type=int, default=5757, help="HTTP port (default: 5757)")
    parser.add_argument("--satellite", action="store_true",
        help="Run in satellite mode (everything except waking minds)")
    parser.add_argument("--primary-ip", type=str, default=None,
        help="IP of primary node (for satellite mode)")
    parser.add_argument("--tracemalloc", action="store_true",
        help="Enable tracemalloc profiling (/mem-snapshot + 5min growth dumps to state/mem_growth.log)")
    args = parser.parse_args()

    # Wire satellite mode CLI args to SYSTEM (SYSTEM exists at module level)
    if args.satellite and args.primary_ip:
        SYSTEM.primary_ip = args.primary_ip
    if args.satellite:
        SYSTEM.satellite_mode = True

    # Handle shutdown — wire signal handler to GracefulShutdownFairy
    running = True
    _shutdown_initiated = False  # Prevent double-shutdown from Ctrl+C spam

    def shutdown_handler(signum, frame):
        nonlocal running, _shutdown_initiated
        running = False

        if _shutdown_initiated:
            # Second Ctrl+C = FORCE EXIT immediately
            print("\n[Server] FORCE EXIT (second Ctrl+C)")
            sys.stdout.flush()
            os._exit(1)

        _shutdown_initiated = True
        print("\n[Server] Shutdown signal received (Ctrl+C again to force)")

        # Tell the fairy to do its thing (fast mode for Ctrl+C)
        if hasattr(SYSTEM, 'shutdown_fairy') and SYSTEM.shutdown_fairy:
            SYSTEM.shutdown_fairy.initiate_shutdown(reason="signal", fast=True)
        # Also publish to postal for any subscribers
        if SYSTEM.fabric:
            try:
                SYSTEM.fabric.publish("system.shutdown_request", {
                    "reason": "signal",
                    "fast": True,
                    "ts": time.time(),
                })
            except Exception:
                pass

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # ═══════════════════════════════════════════════════════════════════
    # START HTTP SERVER BEFORE BOOT
    # The GUI needs to connect during boot to show progress.
    # _compute_status_internal() has a fast path for SYSTEM.booted=False
    # that returns minimal boot-in-progress status.
    # ═══════════════════════════════════════════════════════════════════
    if not args.mcp:
        # Port swap architecture for fast /status.
        # Originally created 2026-02-20 to work around GIL contention (160+ threads).
        # NOTE: Python 3.14 free-threaded (no GIL) — the original GIL problem is gone,
        # but the proxy architecture is still useful: /status from file in <10ms vs
        # building full status dict on every request. Kept for performance, not GIL.
        _INTERNAL_PORT = args.port + 1  # 5758 — main server (internal)
        _PUBLIC_PORT = args.port         # 5757 — proxy (public, fast /status)

        # Start main HTTP server on INTERNAL port (not directly exposed to GUI)
        http_thread = threading.Thread(target=run_http_server, args=(_INTERNAL_PORT,), daemon=True, name="http-internal")
        http_thread.start()
        print(f"[Server] HTTP server started on port {_INTERNAL_PORT} (internal, free-threaded)")

        # Start status proxy on PUBLIC port — this is what the GUI connects to
        try:
            from infrastructure.status_proxy import start_status_proxy
            _proxy_proc = start_status_proxy(proxy_port=_PUBLIC_PORT, backend_port=_INTERNAL_PORT)
            SYSTEM.status_proxy_proc = _proxy_proc  # shutdown terminates this; else os._exit orphans the daemon child
            print(f"[Server] Status proxy on port {_PUBLIC_PORT} → backend {_INTERNAL_PORT} (GIL-immune, PID={_proxy_proc.pid})")
            print(f"[Server] GUI/Tauri connects to port {_PUBLIC_PORT} as before — /status now <10ms")
            # ── Trace status_proxy lifecycle ──
            try:
                from infrastructure.infra_tracer import get_infra_tracer
                _spt = get_infra_tracer()
                _spt.register_actor("status_proxy", role="proxy",
                                    description="Separate-process HTTP proxy for GIL-immune /status")
                _spt.lifecycle("status_proxy", "subprocess_spawned", {
                    "pid": _proxy_proc.pid,
                    "proxy_port": _PUBLIC_PORT, "backend_port": _INTERNAL_PORT,
                })
            except Exception:
                pass
        except Exception as e:
            # Fallback: run main server on the public port directly (old behavior)
            print(f"[Server] Status proxy failed: {e} — falling back to direct HTTP on {_PUBLIC_PORT}")
            # Kill the internal-port server thread and restart on public port
            http_thread2 = threading.Thread(target=run_http_server, args=(_PUBLIC_PORT,), daemon=True, name="http-public")
            http_thread2.start()

    # Boot the system
    if not boot_system():
        print("[Server] Boot failed, exiting")
        sys.exit(1)

    # Start appropriate servers (HTTP already running if not --mcp)
    if args.mcp:
        # MCP stdio only (for Claude Desktop)
        print("[Server] Running MCP stdio server...")
        if SYSTEM.mcp_bridge:
            SYSTEM.mcp_bridge.run_server(transport="stdio", blocking=True)
        else:
            print("[Server] MCP Bridge not available")
            sys.exit(1)

    elif args.both:
        # HTTP already started above, just add MCP
        print("[Server] Running MCP stdio server (HTTP also available)...")
        if SYSTEM.mcp_bridge:
            SYSTEM.mcp_bridge.run_server(transport="stdio", blocking=True)

    else:
        # HTTP only (already started above)
        print("[Server] Ready. Press Ctrl+C to stop.")

        # Main loop
        try:
            tick = 0
            while running and not SYSTEM.shutdown_requested:
                time.sleep(1.0)
                tick += 1

                # Tick UMF clock if available
                if SYSTEM.umf and hasattr(SYSTEM.umf, "clock_tick"):
                    SYSTEM.umf.clock_tick()

                # Periodic status
                if tick % 30 == 0:
                    status = SYSTEM.get_status()
                    beats = status.get("consciousness", {}).get("beats", 0)
                    fairies = status.get("fairies", {}).get("total", 0)
                    print(f"[Server] Heartbeat: beats={beats}, fairies={fairies}")

            if SYSTEM.shutdown_requested:
                print("[Server] Shutdown requested via HTTP — waiting for daemon thread...")
                # (corrected 2026-10-12) shutdown_system() has no os._exit of its own, and the fall-through below never
                # runs it (guarded by `if not SYSTEM.shutdown_requested`): this is an unconditional exit timer, 20
                # COUNTED sleeps (24-43 s of wall time under load), then os._exit(0) -- the shutdown cut.
                # SHUTDOWN FIX (switch ON, shutdown route only): wait for DONE against an absolute deadline instead.
                if not _sdfix_main_wait():
                    for _ in range(20):
                        time.sleep(1.0)
                    print("[Server] WARNING: Daemon thread didn't exit — running shutdown manually")

        except KeyboardInterrupt:
            pass

    # Run shutdown_system for Ctrl+C path
    # HTTP path already called it in the daemon thread
    if not SYSTEM.shutdown_requested:
        # Wait for fairy context save if it was initiated by signal handler
        if hasattr(SYSTEM, 'shutdown_fairy') and SYSTEM.shutdown_fairy:
            SYSTEM.shutdown_fairy.wait_for_completion(timeout=8.0)
        shutdown_system()

    # Handle reboot if requested
    if SYSTEM.reboot_after_shutdown:
        print("[Server] Reboot requested - spawning new process...")
        import subprocess
        # Spawn new server in a new console window
        subprocess.Popen(
            ["cmd", "/c", "start", "AkashicServer", "python", "server.py", "--port", str(args.port)],
            cwd=str(ROOT),
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        )
        print("[Server] New server process spawned. Exiting old process.")

    # Force exit - daemon threads may keep process alive otherwise
    print("[Server] Process exiting.")
    import os
    os._exit(0)  # Hard exit - kills all threads immediately


if __name__ == "__main__":
    main()
