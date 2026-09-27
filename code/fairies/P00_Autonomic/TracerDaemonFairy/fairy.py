"""
TracerDaemonFairy — Tracer Daemon (V3 Wrapper)

Part of P00 Autonomic plane.

The tracer daemon — monitors fairy health via tracer flows,
detects stuck/dead fairies, and maintains system-wide health visibility.
"""

import os
import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState


class TracerDaemonShadow:
    """Shadow for TracerDaemonFairy."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "TracerDaemonShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        engine = getattr(self.actor, '_engine', None)
        if engine:
            tests.append(("engine_connected", True))
            tests.append(("running", getattr(engine, '_running', False)))
        else:
            tests.append(("engine_connected", False))
        return tests


class TracerDaemonFairyV3(Fairy):
    """Tracer daemon — system-wide health monitoring via tracer flows."""

    ACTOR_NAME = "TracerDaemonFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autonomic.tracer"

    PURPOSE = "Monitor fairy health via tracer flows, detect stuck/dead fairies"
    MANTRA = "If a fairy stops breathing, I notice"
    LORE = "The watchman in the dark — always watching, always counting heartbeats"

    SHADOW_CLASS = TracerDaemonShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 1
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._engine = None

    def on_boot(self) -> bool:
        """Boot with deferred engine init."""
        super().on_boot()

        # RETRY 2026-08-27 (Nous + Ace). This is the ONLY fairy that imports its engine
        # from a BACKGROUND THREAD 1.5 s into boot. With __pycache__ cold, every module
        # compiles from source at once, and on the free-threaded (no-GIL) build that
        # concurrent read can tear -> "SyntaxError: source code string cannot contain null
        # bytes". It was swallowed below, so the fairy-health watchdog died SILENTLY for a
        # whole session -- twice in two months (08-27, 07-01), while 15 other engines booted
        # fine in the same run and the entire import chain NUL-checks clean afterwards.
        # A transient deserves a retry; a REAL corruption still fails all attempts and is
        # still reported, so this cannot hide a genuine fault.
        _ENGINE_IMPORT_ATTEMPTS = 3

        def _deferred_init():
            time.sleep(1.5)
            last_err = None
            for _attempt in range(1, _ENGINE_IMPORT_ATTEMPTS + 1):
                try:
                    from fairies.P00_Autonomic.nervous_system.health.tracer_daemon_core import (
                        TracerDaemonFairy as DaemonEngine,
                    )
                    self._engine = DaemonEngine.__new__(DaemonEngine)
                    self._engine.post = self.post
                    # TracerDaemonFairy __init__ takes akashic_root
                    self._engine.__init__(akashic_root=str(ROOT))
                    if hasattr(self._engine, 'on_boot'):
                        self._engine.on_boot()
                    if _attempt > 1:
                        print(f"[{self.ACTOR_NAME}] engine import recovered on attempt "
                              f"{_attempt} (transient: {type(last_err).__name__})", flush=True)
                    print(f"[{self.ACTOR_NAME}] Tracer daemon engine ONLINE")
                    return
                except SyntaxError as e:
                    # Measured 2026-08-27: all 3 attempts fail identically, so this is NOT
                    # transient and the old message saying so was wrong. Retry kept (it is
                    # cheap and harmless if the shape ever does turn out to be transient),
                    # but it no longer asserts a cause it cannot know.
                    last_err = e
                    _mod = "fairies.P00_Autonomic.nervous_system.health.tracer_daemon_core"
                    sys.modules.pop(_mod, None)
                    print(f"[{self.ACTOR_NAME}] engine import attempt {_attempt}/"
                          f"{_ENGINE_IMPORT_ATTEMPTS} failed: {e}", flush=True)
                    # _NUL_CAPTURE -- name the source instead of inferring it a sixth time.
                    # e.filename/lineno/offset/text are ALL None for this error class BY
                    # CONSTRUCTION (CPython checks for NUL before attaching a filename --
                    # verified with a real path argument), so they are a checksum, not a
                    # clue. The traceback and the frame locals are the entire signal:
                    # importlib strips its own frames, so the deepest surviving frame is
                    # whatever executed the failing `import`, and its source line names it.
                    if _attempt == 1:
                        try:
                            import linecache as _lc
                            import traceback as _tb
                            _L = ["TRACER DAEMON NUL CAPTURE",
                                  "  attempt  : %d" % _attempt,
                                  "  msg      : %r" % getattr(e, "msg", None),
                                  "  (filename/lineno/offset/text are None by construction",
                                  "   for this error class -- not a clue, just a checksum:",
                                  "   %r %r %r %r)" % (getattr(e, "filename", None),
                                                       getattr(e, "lineno", None),
                                                       getattr(e, "offset", None),
                                                       getattr(e, "text", None)),
                                  "", "  TRACEBACK (deepest frame = the failing import)"]
                            for _ln in _tb.format_exc().splitlines()[-80:]:
                                _L.append("    " + _ln[:220])
                            _L.append("")
                            _L.append("  FRAMES + LOCALS")
                            _tbo = sys.exc_info()[2]
                            _n = 0
                            while _tbo is not None and _n < 80:
                                _f = _tbo.tb_frame
                                _fn = _f.f_code.co_filename
                                _L.append("    %s:%d in %s"
                                          % (_fn, _tbo.tb_lineno, _f.f_code.co_name))
                                _srcln = _lc.getline(_fn, _tbo.tb_lineno).strip()
                                if _srcln:
                                    _L.append("        source> %s" % _srcln[:200])
                                for _k, _v in list(_f.f_locals.items())[:30]:
                                    if isinstance(_v, str) and 0 < len(_v) <= 300:
                                        _L.append("        %-14s = %r" % (_k, _v[:200]))
                                    elif isinstance(_v, (int, float, bool, type(None))):
                                        _L.append("        %-14s = %r" % (_k, _v))
                                    else:
                                        # a loader object carries the path it is reading --
                                        # the most direct namer available
                                        _lp = getattr(_v, "path", None)
                                        _lnm = getattr(_v, "name", None)
                                        if isinstance(_lp, str):
                                            _L.append("        %-14s .path=%r .name=%r"
                                                      % (_k, _lp[:200], _lnm))
                                _tbo = _tbo.tb_next
                                _n += 1
                            # ---- v2 forensics: name the module, and test transience ----
                            # v1 proved this is a COMPILE-time failure (single-frame
                            # traceback). These four levels are the only things compiled
                            # before tracer_daemon_core. Walking them names the culprit.
                            _L.append("")
                            _L.append("  SYS.PATH AT FAILURE (first 14) -- her real one")
                            for _pp in sys.path[:14]:
                                _L.append("    %r" % _pp)
                            try:
                                _L.append("")
                                _L.append("  dont_write_bytecode=%s  threads=%d"
                                          % (sys.dont_write_bytecode,
                                             len(sys._current_frames())))
                                _L.append("  cwd=%s" % os.getcwd())
                            except BaseException as _e1:
                                _L.append("  <env probe failed: %s>" % _e1)
                            _chain = ["fairies",
                                      "fairies.P00_Autonomic",
                                      "fairies.P00_Autonomic.nervous_system",
                                      "fairies.P00_Autonomic.nervous_system.health"]
                            _L.append("")
                            _L.append("  CHAIN WALK -- the level that raises IS the answer")
                            for _nm in _chain:
                                try:
                                    _m = __import__(_nm, fromlist=["x"])
                                    _L.append("    OK   %-46s %s"
                                              % (_nm, getattr(_m, "__file__", "<ns>")))
                                except BaseException as _ie:
                                    _L.append("    FAIL %-46s %s: %s"
                                              % (_nm, type(_ie).__name__, str(_ie)[:130]))
                                    break
                            _L.append("")
                            _L.append("  FORENSICS AT FAILURE TIME (+ LIVE RE-COMPILE)")
                            _L.append("  a file that recompiles OK here was TRANSIENTLY bad")
                            try:
                                import importlib.util as _iu
                                _files = []
                                for _nm in _chain + [_mod]:
                                    try:
                                        _sp = _iu.find_spec(_nm)
                                        if _sp is not None and _sp.origin:
                                            _files.append(_sp.origin)
                                        else:
                                            _L.append("    %-50s <no origin>" % _nm)
                                    except BaseException as _se:
                                        _L.append("    find_spec(%s) -> %s: %s"
                                                  % (_nm, type(_se).__name__, str(_se)[:90]))
                                for _fp in _files:
                                    try:
                                        with open(_fp, "rb") as _bf:
                                            _b = _bf.read()
                                        try:
                                            compile(_b, _fp, "exec")
                                            _cr = "recompile OK"
                                        except SyntaxError as _c2:
                                            _cr = "recompile FAIL: %s" % _c2.msg
                                        _L.append("    %-58s %7d B NUL=%-5d %s"
                                                  % (_fp[-58:], len(_b),
                                                     _b.count(b"\x00"), _cr))
                                        _L.append("        head=%r" % _b[:44])
                                    except BaseException as _fe:
                                        _L.append("    %-58s <read failed: %s>"
                                                  % (_fp[-58:], _fe))
                                _L.append("")
                                _L.append("  __pycache__ STATE (absent dir = never compiled)")
                                _seen_d = []
                                for _fp in _files:
                                    _pd = os.path.join(os.path.dirname(_fp), "__pycache__")
                                    if _pd in _seen_d:
                                        continue
                                    _seen_d.append(_pd)
                                    try:
                                        if os.path.isdir(_pd):
                                            _L.append("    %-54s %d entries"
                                                      % (_pd[-54:], len(os.listdir(_pd))))
                                        else:
                                            _L.append("    %-54s <ABSENT>" % _pd[-54:])
                                    except BaseException as _pe:
                                        _L.append("    %-54s <%s>" % (_pd[-54:], _pe))
                            except BaseException as _fx:
                                _L.append("  <forensics failed: %s: %s>"
                                          % (type(_fx).__name__, str(_fx)[:120]))
                            # ---- v3 DISCRIMINATOR ----------------------------------
                            # A literal b"" and the file's bytes, compiled at the same
                            # instant. Literal fails too => the compiler is broken here.
                            # Literal passes => open() lied about what it returned.
                            _L.append("")
                            _L.append("  DISCRIMINATOR")
                            try:
                                import builtins as _bi
                                _L.append("    compile is builtins.compile : %s"
                                          % (compile is _bi.compile))
                                _L.append("    compile repr                : %r" % (compile,))
                                _L.append("    open    is builtins.open    : %s"
                                          % (open is _bi.open))
                                try:
                                    compile(b"", "literal_probe.py", "exec")
                                    _L.append("    LITERAL b'' via compile     : OK")
                                except BaseException as _l1:
                                    _L.append("    LITERAL b'' via compile     : %s: %s"
                                              % (type(_l1).__name__, _l1))
                                try:
                                    _bi.compile(b"", "literal_probe.py", "exec")
                                    _L.append("    LITERAL b'' via builtins    : OK")
                                except BaseException as _l2:
                                    _L.append("    LITERAL b'' via builtins    : %s: %s"
                                              % (type(_l2).__name__, _l2))
                                # re-read one failing file through a SECOND, independent
                                # path -- os.open/os.read bypasses the io layer entirely.
                                _probe = None
                                for _cand in _files:
                                    if _cand.endswith("__init__.py"):
                                        try:
                                            if os.path.getsize(_cand) == 0:
                                                _probe = _cand
                                                break
                                        except BaseException:
                                            pass
                                if _probe:
                                    _L.append("    probe file: %s" % _probe[-70:])
                                    try:
                                        _fd = os.open(_probe, os.O_RDONLY | getattr(os, "O_BINARY", 0))
                                        try:
                                            _rb = os.read(_fd, 4096)
                                        finally:
                                            os.close(_fd)
                                        _L.append("      os.read  -> %d bytes, type=%s, repr=%r"
                                                  % (len(_rb), type(_rb).__name__, _rb[:32]))
                                        try:
                                            compile(_rb, _probe, "exec")
                                            _L.append("      compile(os.read bytes)  : OK")
                                        except BaseException as _l3:
                                            _L.append("      compile(os.read bytes)  : %s: %s"
                                                      % (type(_l3).__name__, _l3))
                                    except BaseException as _l4:
                                        _L.append("      os.read failed: %s" % _l4)
                                    try:
                                        with open(_probe, "rb") as _pf:
                                            _pb = _pf.read()
                                        _L.append("      open().read -> %d bytes, type=%s, repr=%r"
                                                  % (len(_pb), type(_pb).__name__, _pb[:32]))
                                        _L.append("      is b'' : %s   == b'' : %s"
                                                  % (_pb is b"", _pb == b""))
                                        try:
                                            compile(_pb, _probe, "exec")
                                            _L.append("      compile(open bytes)     : OK")
                                        except BaseException as _l5:
                                            _L.append("      compile(open bytes)     : %s: %s"
                                                      % (type(_l5).__name__, _l5))
                                    except BaseException as _l6:
                                        _L.append("      open() failed: %s" % _l6)
                                _L.append("    sys.meta_path:")
                                for _mp in sys.meta_path:
                                    _L.append("      %r  find_spec=%s"
                                              % (_mp, hasattr(_mp, "find_spec")))
                            except BaseException as _dx:
                                _L.append("  <discriminator failed: %s: %s>"
                                          % (type(_dx).__name__, str(_dx)[:140]))
                            _txt = "\n".join(_L) + "\n"
                            _txt.encode("utf-8")   # prove encodable BEFORE opening anything
                            _out = os.path.join(str(ROOT), "state", "tracer_nul_capture.txt")
                            os.makedirs(os.path.dirname(_out), exist_ok=True)
                            _tmp = _out + ".tmp"
                            with open(_tmp, "w", encoding="utf-8", newline="") as _fh:
                                _fh.write(_txt)
                                _fh.flush()
                                os.fsync(_fh.fileno())
                            os.replace(_tmp, _out)   # atomic: a torn diagnostic is worse than none
                            print(f"[{self.ACTOR_NAME}] NUL capture -> {_out}", flush=True)
                        except Exception as _ce:
                            print(f"[{self.ACTOR_NAME}] NUL capture failed: {_ce}", flush=True)
                    time.sleep(2.0 * _attempt)
                except Exception as e:
                    # Not the transient shape -- fail loudly and immediately, as before.
                    print(f"[{self.ACTOR_NAME}] Engine init error: {e}")
                    import traceback
                    traceback.print_exc()
                    return
            print(f"[{self.ACTOR_NAME}] Engine init FAILED after "
                  f"{_ENGINE_IMPORT_ATTEMPTS} attempts: {last_err}", flush=True)
            import traceback
            # Verified 2026-08-27: sys.exc_info() is (None, None, None) here because the
            # except block has already exited, so the print_exc() I put here with the retry
            # printed literally "NoneType: None". Use the exception's own __traceback__.
            if last_err is not None:
                traceback.print_exception(last_err)
            else:
                traceback.print_exc()

        # ---- _NUL_PROBE 2026-08-27 (Nous + Ace) -------------------------------
        # A/B-proven: an EMPTY __init__.py kills this daemon because a literal b""
        # fails to compile inside this process. The capture only fires ON FAILURE,
        # and the 13-file sweep should stop the failure -- so without this we would
        # never learn WHEN the corruption lands or WHETHER it is the b"" singleton.
        # bytearray() is a FRESH object; b"" is shared process-wide. If b"" breaks
        # while bytearray() still compiles, singleton corruption is confirmed.
        def _nul_probe():
            try:
                _t0 = time.time()
                _log = os.path.join(str(ROOT), "state", "nul_probe.log")
                try:
                    os.makedirs(os.path.dirname(_log), exist_ok=True)
                except Exception:
                    pass

                def _try(_src):
                    try:
                        compile(_src, "nul_probe.py", "exec")
                        return "OK"
                    except SyntaxError as _e:
                        return "FAIL(%s)" % str(_e.msg)[:44]
                    except BaseException as _e:
                        return "ERR(%s)" % type(_e).__name__

                def _emit(_tag, _st, _n):
                    try:
                        _line = ("%s  t=%7.1fs  threads=%-5s  %s\n"
                                 % (_tag, time.time() - _t0, _n,
                                    "  ".join("%s=%s" % (k, v) for k, v in _st)))
                        with open(_log, "a", encoding="utf-8", newline="") as _f:
                            _f.write(_line)
                            _f.flush()
                    except Exception:
                        pass

                _prev = None
                _i = 0
                while _i < 900:                      # ~30 min then stop
                    _i += 1
                    try:
                        _n = threading.active_count()
                    except Exception:
                        _n = "?"
                    _st = [("bytes_empty", _try(b"")),
                           ("str_empty", _try("")),
                           ("bytearray", _try(bytearray())),
                           ("control", _try(b"# control\nx = 1\n"))]
                    _key = tuple(v for _, v in _st)
                    if _prev is None:
                        _emit("START ", _st, _n)
                    elif _key != _prev:
                        _emit("CHANGE", _st, _n)
                        if _prev[0] == "OK" and _st[0][1] != "OK":
                            _emit("^^^^^^ b'' BROKE HERE -- bytearray tells you if it is the "
                                  "singleton", _st, _n)
                            try:
                                print("[%s] NUL PROBE: compile(b'') broke at t=%.1fs "
                                      "(threads=%s) -> %s"
                                      % (self.ACTOR_NAME, time.time() - _t0, _n, _log),
                                      flush=True)
                            except Exception:
                                pass
                    elif _i % 150 == 0:              # heartbeat every ~5 min
                        _emit("alive ", _st, _n)
                    _prev = _key
                    time.sleep(2.0)
            except BaseException:
                pass                                  # never raise into the fairy

        try:
            threading.Thread(target=_nul_probe, daemon=True, name="nul-probe").start()
        except Exception:
            pass
        # ---- end _NUL_PROBE ---------------------------------------------------

        threading.Thread(target=_deferred_init, daemon=True, name="defer-TracerDaemonFairy").start()

        print(f"[{self.ACTOR_NAME}] {self.MANTRA} (booting engine...)")
        return True

    def _handle_heartbeat(self, packet):
        if not self._engine:
            return


    def on_die(self):
        if self._engine and hasattr(self._engine, '_running'):
            self._engine._running = False
        super().on_die()


ACTOR_NAME = "TracerDaemonFairy"
FAIRY_CLASS = TracerDaemonFairyV3
