"""gpu_reader.py -- ONE shared, in-process GPU reader for her four timed nvidia-smi pollers. 2026-10-16 (Nous, gpu_poll_1016).

WHY. Boot S (tools/xray): abandoned mimalloc segments were 69 % of her private growth, and the one thread group whose deaths tracked
them was subprocess's `_readerthread`: every captured child starts one per pipe, and four of her loops spawn `nvidia-smi` on a timer
(worker_equilibrium every 2 s, cuda_fairy gpu_felt 5 s, server.py GPUMonitor 10 s, resource_equilibrium HealthMonitor 10 s). This module
answers all four from ONE read of the NVIDIA driver's own nvml.dll through ctypes: no thread, no child process, no download, no compiled
code of ours.

HOW A SITE USES IT. A site keeps its own nvidia-smi line, its own parser and its own failure handling, byte for byte. The only change in
her files is three inserted lines after the site's own `import subprocess`: they rebind the local name `subprocess` to bind("<site>"),
a proxy whose `.run(...)` either (a) hands back a CompletedProcess whose stdout is EXACTLY the text nvidia-smi would have printed for that
site's query (same fields, same units, same ", " separators, MiB rounded up as nvidia-smi does), or (b) runs the real `subprocess.run`
with the very same arguments. Every other attribute (`PIPE`, `CREATE_NO_WINDOW`, `TimeoutExpired`, ...) is the real module's. Because the
parsers never change, the values cannot drift; because (b) is the same call, a reader that fails costs nothing but today's behaviour.

WHEN IT ANSWERS (all of these, else it is (b)):
  * state/gpu_poll.json arms the site: `{"on": true}` arms all four, `{"<site>": true}` one; `false` for a site wins over "on". Only a JSON
    true arms; a missing, torn, unreadable or non-object file, a string "true", 1, null = OFF = today. Re-read when it changes and at
    least every 10 s, so on/off needs no restart. Sites: worker_equilibrium, cuda_gpu_felt, gpu_monitor, resource_equilibrium.
  * the call has exactly the shape that site makes today (argv `nvidia-smi --query-gpu=<its fields> --format=csv,noheader,nounits`, only
    capture/text/timeout/creationflags keywords): a later edit of a site's query can never be answered with the wrong columns.
  * the cached reading is at most REFRESH_S (1 s) old, or, when a refresh is not possible at this instant, at most MAX_AGE_S (5 s) old.
  * there is exactly one GPU (several: the sites print/parse several lines today; this reader serves index 0 only, so it steps aside).
REFRESH. Inline, by whichever caller finds the cache older than REFRESH_S: five NVML calls, about 9 microseconds. A caller that cannot take
the lock does not wait: it uses a reading younger than MAX_AGE_S or runs the real call. One failed NVML call anywhere in a read throws the
whole read away (never a partial fill) and puts the reader in back-off for BACKOFF_S (30 s), during which every caller runs today's call.
nvmlShutdown is NEVER called (torch and her own pynvml fallback share the refcount). Never raises into a caller.
2026-10-19 (review fixes, gpu_poll_1016 pass 2):
  * NVML_ERROR_UNINITIALIZED (rc 1) after a good init = someone else's unbalanced nvmlShutdown dropped the shared refcount to 0: the reader
    forgets its init, so the next try (after the back-off) calls nvmlInit_v2 again. Compared as a NUMBER (" rc=1" is a prefix of " rc=13").
  * An NVML call that never returns (a wedged driver) has no timeout in-process. No thread is added to bound it; instead a caller that finds
    the refresh lock held by a refresh older than STUCK_S prints ONE rate-limited line naming the thread that is stuck, and counts it
    (stuck=N in the 10-min line). Everyone else keeps using a <=5 s reading, then nvidia-smi, as before.
  * argtypes/restype are declared once, as nvml.h declares them, before the library is used: a signature mistake fails at the call.
"""
import collections
import ctypes
import json
import os
import subprocess
import sys
import threading
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # infrastructure/gpu_reader.py -> the tree root
SWITCH_FILE = os.path.join(_ROOT, "state", "gpu_poll.json")

# site -> the exact --query-gpu field list that site asks nvidia-smi for today
SITES = {
    "worker_equilibrium": ("utilization.gpu", "memory.used", "memory.total"),
    "cuda_gpu_felt": ("utilization.gpu", "memory.used", "memory.total", "temperature.gpu"),
    "gpu_monitor": ("utilization.gpu",),
    "resource_equilibrium": ("name", "memory.total", "memory.free", "memory.used", "compute_cap"),
}
_FORMAT = "--format=csv,noheader,nounits"
_QUERY = "--query-gpu="
_KW_OK = frozenset(("capture_output", "stdout", "stderr", "text", "timeout", "creationflags"))
REFRESH_S = 1.0               # the cache is refreshed no more often than this (her fastest consumer polls every 2 s)
MAX_AGE_S = 5.0               # a reading older than this is never served
BACKOFF_S = 30.0              # after a failed open/read nobody asks NVML again for this long
STUCK_S = 10.0                # a refresh still inside NVML after this long is reported (never waited on)
_SWITCH_RECHECK_S = 10.0
_REPORT_S = 600.0             # one [GpuPoll] summary line per this while armed
_ERR_S = 300.0                # at most one failure/error line per kind per this
_MIB = 1024 * 1024
_NVML_UNINITIALIZED = 1       # NVML_ERROR_UNINITIALIZED

Snap = collections.namedtuple("Snap", "t name util used_mib free_mib total_mib temp_c cc")

_L = threading.Lock()         # one refresh at a time; a caller that cannot take it never waits
_SWL = threading.Lock()
_CL = threading.Lock()        # counters only
_SW = {"key": None, "data": {}, "read": 0.0}
_S = {"snap": None, "lib": None, "inited": False, "h": None, "name": "", "cc": "", "retry_at": -1e18, "why": "", "busy_since": None, "busy_on": ""}
_C = {}                       # (site or "nvml", what) -> n
_R = {"t": None, "err_at": {}}


class _Fail(Exception):
    pass


class _Util(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class _Mem2(ctypes.Structure):                       # nvmlMemory_v2_t: the only one whose `used` equals nvidia-smi's memory.used
    _fields_ = [("version", ctypes.c_uint), ("total", ctypes.c_ulonglong), ("reserved", ctypes.c_ulonglong),
                ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]


_MEM2_VERSION = ctypes.sizeof(_Mem2) | (2 << 24)
_P = ctypes.POINTER
# nvml.h, the eight functions this reader calls (nvmlShutdown is never called): (name, argtypes); every one returns nvmlReturn_t (int)
_SIGS = (("nvmlInit_v2", []),
         ("nvmlDeviceGetCount_v2", [_P(ctypes.c_uint)]),
         ("nvmlDeviceGetHandleByIndex_v2", [ctypes.c_uint, _P(ctypes.c_void_p)]),
         ("nvmlDeviceGetName", [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint]),
         ("nvmlDeviceGetCudaComputeCapability", [ctypes.c_void_p, _P(ctypes.c_int), _P(ctypes.c_int)]),
         ("nvmlDeviceGetUtilizationRates", [ctypes.c_void_p, _P(_Util)]),
         ("nvmlDeviceGetMemoryInfo_v2", [ctypes.c_void_p, _P(_Mem2)]),
         ("nvmlDeviceGetTemperature", [ctypes.c_void_p, ctypes.c_int, _P(ctypes.c_uint)]))


# -- seams (a test replaces these) ----------------------------------------------------------------------------------------------
def _now():
    return time.monotonic()


def _load_lib():
    """The driver's own nvml.dll: System32 first (as pynvml does), then the old NVSMI folder. None when none loads. Windows only."""
    if sys.platform != "win32":
        return None
    win = os.environ.get("WINDIR") or os.environ.get("SystemRoot") or r"C:\Windows"
    pf = os.environ.get("ProgramFiles") or r"C:\Program Files"
    for p in (os.path.join(win, "System32", "nvml.dll"), os.path.join(pf, "NVIDIA Corporation", "NVSMI", "nvml.dll")):
        try:
            if os.path.isfile(p):
                return ctypes.CDLL(p)
        except OSError:
            continue
    return None


# -- output ---------------------------------------------------------------------------------------------------------------------
def _say(s):
    try:
        print(str(s).encode("ascii", "replace").decode("ascii").replace("\n", " ")[:480], file=sys.stderr, flush=True)
    except Exception:
        pass


def _say_rl(kind, s):
    """At most one line per kind per _ERR_S. Never raises."""
    try:
        now = _now()
        last = _R["err_at"].get(kind)
        if last is not None and 0.0 <= now - last < _ERR_S:
            return
        _R["err_at"][kind] = now
        _say(s)
    except Exception:
        pass


def _oops(stage, e):
    _say_rl("err:" + stage, "[GpuPoll] %s error (non-fatal, callers run nvidia-smi as before): %s: %s" % (stage, type(e).__name__, str(e)[:120]))


# -- counters and the periodic line ---------------------------------------------------------------------------------------------
def _count(key, what):
    """+1 under the counter lock. -> the new count (1 = the first one ever, decided atomically)."""
    now = _now()
    with _CL:
        n = _C[(key, what)] = _C.get((key, what), 0) + 1
        first = _R["t"] is None
        due = (not first) and now - _R["t"] >= _REPORT_S
        if first or due:
            _R["t"] = now
        line = _report_line() if due else None
    if line:
        _say(line)
    return n


def _report_line():
    parts = []
    for site in SITES:
        served = _C.get((site, "served"), 0)
        fb = sum(n for (k, w), n in _C.items() if k == site and w.startswith("fallback"))
        if served or fb:
            parts.append("%s served=%d fallback=%d" % (site, served, fb))
    stuck = _C.get(("nvml", "stuck"), 0)
    parts.append("nvml reads=%d failed=%d%s" % (_C.get(("nvml", "read"), 0), _C.get(("nvml", "fail"), 0), (" stuck=%d" % stuck) if stuck else ""))
    return "[GpuPoll] so far: " + " | ".join(parts)


def stats():
    """A copy of the counters: {(site or 'nvml', what): n}."""
    with _CL:
        return dict(_C)


# -- the switch -----------------------------------------------------------------------------------------------------------------
def switch():
    """state/gpu_poll.json as a dict; {} (= today) when absent, unreadable, torn or not an object."""
    try:
        st = os.stat(SWITCH_FILE)
    except OSError:
        with _SWL:
            _SW["key"], _SW["data"], _SW["read"] = None, {}, 0.0
        return {}
    key = (st.st_mtime_ns, st.st_size)
    now = _now()
    with _SWL:
        if key != _SW["key"] or not (0.0 <= now - float(_SW["read"]) <= _SWITCH_RECHECK_S):
            try:
                with open(SWITCH_FILE, "rb") as f:
                    d = json.loads(f.read().decode("utf-8-sig"))          # a hand-edited file may carry a BOM
                _SW["data"], _SW["key"], _SW["read"] = (d if isinstance(d, dict) else {}), key, now
            except Exception:
                _SW["data"], _SW["key"], _SW["read"] = {}, None, 0.0       # torn or bad: today, read again next time
        return dict(_SW["data"])


def site_on(d, site):
    """Only a JSON true arms. A site's own false wins over the master "on"."""
    return d.get(site) is True or (d.get("on") is True and d.get(site) is not False)


# -- NVML -----------------------------------------------------------------------------------------------------------------------
def _ceil_mib(b):
    return -(-int(b) // _MIB)                # nvidia-smi prints MiB rounded UP (67 of 67 pairs measured on this box)


def _declare(lib):
    """argtypes/restype once, as nvml.h declares them, before the library is used. A symbol the dll lacks raises AttributeError here: the
    read fails, the reader backs off and callers run nvidia-smi; the library is kept only once this has succeeded."""
    for name, args in _SIGS:
        fn = getattr(lib, name)
        fn.argtypes, fn.restype = args, ctypes.c_int


def _rc_fail(what, rc):
    """The reason for a non-zero NVML return. NVML_ERROR_UNINITIALIZED after a good init means the shared refcount fell to 0 under us:
    forget our init so the next try calls nvmlInit_v2 again. Any other code keeps it (no extra references on a refcount we share)."""
    if rc == _NVML_UNINITIALIZED:
        _S["inited"] = False
    return "%s rc=%d" % (what, rc)


def _open():
    """Load, init, check there is exactly one GPU, fetch handle/name/compute capability. -> None on success, else a short reason."""
    lib = _S["lib"]
    if lib is None:
        lib = _load_lib()
        if lib is None:
            return "no nvml.dll"
        _declare(lib)
        _S["lib"] = lib
    if not _S["inited"]:
        rc = lib.nvmlInit_v2()
        if rc != 0:
            return "nvmlInit_v2 rc=%d" % rc
        _S["inited"] = True                                  # refcounted; never shut down from here
    n = ctypes.c_uint()
    rc = lib.nvmlDeviceGetCount_v2(ctypes.byref(n))
    if rc != 0:
        return _rc_fail("nvmlDeviceGetCount_v2", rc)
    if n.value != 1:
        return "%d GPUs (this reader serves exactly one)" % n.value
    h = ctypes.c_void_p()
    rc = lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(h))
    if rc != 0:
        return _rc_fail("nvmlDeviceGetHandleByIndex_v2", rc)
    buf = ctypes.create_string_buffer(96)
    rc = lib.nvmlDeviceGetName(h, buf, 96)
    if rc != 0:
        return _rc_fail("nvmlDeviceGetName", rc)
    maj, mnr = ctypes.c_int(), ctypes.c_int()
    rc = lib.nvmlDeviceGetCudaComputeCapability(h, ctypes.byref(maj), ctypes.byref(mnr))
    if rc != 0:
        return _rc_fail("nvmlDeviceGetCudaComputeCapability", rc)
    name = buf.value.decode("utf-8", "replace").strip()
    if not name or "\n" in name or "\r" in name:
        return "unusable GPU name"
    _S["h"], _S["name"], _S["cc"] = h, name, "%d.%d" % (maj.value, mnr.value)
    return None


def _read_once(now):
    """One full read. A non-zero return from ANY call throws the whole read away (never a partial fill)."""
    lib, h = _S["lib"], _S["h"]
    u, m, t = _Util(), _Mem2(), ctypes.c_uint()
    m.version = _MEM2_VERSION
    rcs = (("util", lib.nvmlDeviceGetUtilizationRates(h, ctypes.byref(u))),
           ("mem", lib.nvmlDeviceGetMemoryInfo_v2(h, ctypes.byref(m))),
           ("temp", lib.nvmlDeviceGetTemperature(h, 0, ctypes.byref(t))))
    for what, rc in rcs:
        if rc != 0:
            raise _Fail(_rc_fail(what, rc))
    s = Snap(now, _S["name"], int(u.gpu), _ceil_mib(m.used), _ceil_mib(m.free), _ceil_mib(m.total), int(t.value), _S["cc"])
    if not (0 <= s.util <= 100 and s.total_mib > 0 and 0 <= s.used_mib <= s.total_mib and 0 <= s.free_mib <= s.total_mib
            and 0 <= s.temp_c <= 200):
        raise _Fail("values out of range %r" % (s[2:7],))
    return s


def _refresh(now):
    """-> (Snap, None) or (None, reason). Called under _L. Marks itself busy (when, which thread) for _stuck_tell, and clears the mark."""
    _S["busy_on"], _S["busy_since"] = threading.current_thread().name, now
    try:
        if _S["h"] is None:
            why = _open()
            if why:
                _count("nvml", "fail")
                return None, why
        s = _read_once(now)
        _count("nvml", "read")
        return s, None
    except _Fail as e:
        _S["h"] = None                                       # fetch the handle again next time
        _count("nvml", "fail")
        return None, str(e)
    except Exception as e:
        _S["h"] = None
        _count("nvml", "fail")
        return None, "%s: %s" % (type(e).__name__, str(e)[:80])
    finally:
        _S["busy_since"] = None


def _stuck_tell(now):
    """No thread, no wait: the refresh lock is held; when a refresh has been inside it for more than STUCK_S, count it and say which thread
    (one line per _ERR_S). The caller still gets a <=5 s reading or today's call."""
    t0 = _S["busy_since"]
    if t0 is not None and now - t0 > STUCK_S:
        _count("nvml", "stuck")
        _say_rl("stuck", "[GpuPoll] NVML refresh stuck for %d s on thread %s (a call into the driver has not returned; other callers use a "
                         "reading up to 5 s old, then nvidia-smi)" % (int(now - t0), _S["busy_on"] or "?"))


def _usable(s, now):
    return s if (s is not None and 0.0 <= now - s.t <= MAX_AGE_S) else None


def snapshot():
    """The shared reading, or None. A Snap is at most REFRESH_S old, or (when a refresh is not possible right now) at most MAX_AGE_S old.
    None = run today's nvidia-smi call. Never raises, never waits on another thread."""
    try:
        now = _now()
        s = _S["snap"]
        if s is not None and 0.0 <= now - s.t < REFRESH_S:
            return s
        if not _L.acquire(blocking=False):
            _stuck_tell(now)
            return _usable(s, now)
        try:
            now = _now()
            s = _S["snap"]
            if s is not None and 0.0 <= now - s.t < REFRESH_S:
                return s
            if now < _S["retry_at"]:
                return _usable(s, now)
            new, why = _refresh(now)
            if new is None:
                _S["retry_at"] = now + BACKOFF_S
                _S["why"] = why
                _say_rl("nvml", "[GpuPoll] NVML read failed (%s): callers run nvidia-smi as before; next try in %d s" % (why, int(BACKOFF_S)))
                return _usable(s, now)
            _S["snap"], _S["why"] = new, ""
            return new
        finally:
            _L.release()
    except Exception as e:
        _oops("snapshot", e)
        return None


def read(site):
    """The shared reading for `site`, or None when the site is not armed or no reading is available. Never raises."""
    try:
        if site in SITES and site_on(switch(), site):
            return snapshot()
    except Exception as e:
        _oops("read", e)
    return None


# -- the nvidia-smi look-alike --------------------------------------------------------------------------------------------------
_FIELD = {
    "name": lambda s: s.name,
    "utilization.gpu": lambda s: str(s.util),
    "memory.used": lambda s: str(s.used_mib),
    "memory.total": lambda s: str(s.total_mib),
    "memory.free": lambda s: str(s.free_mib),
    "temperature.gpu": lambda s: str(s.temp_c),
    "compute_cap": lambda s: s.cc,
}


def render(site, s):
    """The one line nvidia-smi prints for this site's query: ", "-joined, newline-terminated."""
    return ", ".join(_FIELD[f](s) for f in SITES[site]) + "\n"


def _shaped(site, args, kw):
    """True only for exactly the call `site` makes today."""
    if len(args) != 1:
        return False
    argv = args[0]
    if not isinstance(argv, (list, tuple)) or len(argv) != 3:
        return False
    q = argv[1]
    if argv[0] != "nvidia-smi" or argv[2] != _FORMAT or not isinstance(q, str) or not q.startswith(_QUERY):
        return False
    if tuple(q[len(_QUERY):].split(",")) != SITES[site]:
        return False
    if any(k not in _KW_OK for k in kw):
        return False
    cap = bool(kw.get("capture_output"))
    if cap and ("stdout" in kw or "stderr" in kw):
        return False                                         # the real call raises ValueError here: let it
    if not cap and kw.get("stdout") != subprocess.PIPE:
        return False
    if not cap and kw.get("stderr", subprocess.PIPE) != subprocess.PIPE:
        return False
    return True


def _serve(site, args, kw):
    if site not in SITES or not site_on(switch(), site):
        return None
    if not _shaped(site, args, kw):
        _count(site, "fallback_shape")
        return None
    s = snapshot()
    if s is None:
        _count(site, "fallback_nodata")
        return None
    text = render(site, s)
    as_text = bool(kw.get("text"))
    cap_err = bool(kw.get("capture_output")) or kw.get("stderr") == subprocess.PIPE
    out = text if as_text else text.encode("utf-8")
    err = ("" if as_text else b"") if cap_err else None
    cp = subprocess.CompletedProcess(args[0], 0, out, err)
    if _count(site, "served") == 1:                          # decided under the counter lock: printed once even when two threads race
        _say("[GpuPoll] %s: now answered from NVML (state/gpu_poll.json armed it); no nvidia-smi child, no reader threads" % site)
    return cp


def _run(site, args, kw):
    cp = None
    try:
        cp = _serve(site, args, kw)
    except Exception as e:
        _oops("serve", e)
    if cp is not None:
        return cp
    return subprocess.run(*args, **kw)           # today's call, today's arguments, raising whatever it raises


class _Bound(object):
    """What the name `subprocess` means inside a gated site: .run is gated, every other attribute is the real module's."""
    __slots__ = ("_site",)

    def __init__(self, site):
        self._site = site

    def run(self, *args, **kw):
        return _run(self._site, args, kw)

    def __getattr__(self, name):
        return getattr(subprocess, name)


def bind(site):
    """Called by the three lines inserted in her files. Cheap, never raises, decides nothing: the switch is read on every run()."""
    return _Bound(site)
