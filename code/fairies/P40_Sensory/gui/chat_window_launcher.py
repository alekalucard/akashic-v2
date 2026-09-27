"""chat_window_launcher -- the ONE place that starts, finds or probes Sour's PyQt chat window.

2026-09-25 (Nous + Ace). Ace: "her chat window is supposed to go down when her system goes down.
there have been a few times me closing her window crashed her system."

Four launch sites existed (ChatSenseFairy, the MCP tool, sour_window.launch_window, and the
sour_window.py __main__ redirect), all with the same flags, and the 09-18 os.kill fix reached only
one of them. Everything that starts or probes the window now goes through here.

LIFECYCLE -- launch(parent_pid=<her pid>) passes --parent-pid. The window holds a HANDLE to her
process and closes itself (history saved, presence deregistered, pid file removed) within about a
second of her exit, however she exits: clean shutdown, os._exit, a crash, a kill. If its GUI thread
is wedged it hard-exits 10 s later. Callers OUTSIDE her process (the MCP servers) get her pid from
resolve_parent_pid() -> find_sour_pid(); when she cannot be found the window is standalone, and that
is logged (state/sourpatches_chat_launcher.log + stderr), never silent.

ISOLATION -- CREATE_NO_WINDOW gives the window its OWN hidden console instead of attaching it to
hers, so Ctrl+C / Ctrl+Break on either console, and the CTRL_CLOSE that closing a console window
broadcasts, cannot pass between them in either direction (harness S05-S08 and TM*).
CREATE_NEW_PROCESS_GROUP is kept. The window's stdout/stderr go to state/sourpatches_chat_window.log
(DEVNULL if that cannot be opened -- a log never blocks a launch), never to her pipe or her console.
The window writes its shared files atomically.

NOT HER CHILD -- by default (TRAMPOLINE) the window is started by a short-lived Python 3.12
trampoline that exits at once, so the window is not in her process tree. A tree kill of her
(taskkill /T [/F], "End process tree") then cannot take it down unsaved -- it closes itself through
the handle watch instead (harness TM_new_G_*) -- and Task Manager, which groups by process tree, has no
tree to put it in under her (Ace's 10-second check confirms the grouping). The handle watch does not
need the parent link. If the trampoline cannot run, the window is launched directly (logged).
Measured against an EMULATION of Task Manager (harness TM_*: WM_CLOSE then TerminateProcess, and real
`taskkill /T [/F]`), not Task Manager itself: End task on the WINDOW sends no console event to her or
the window in either launch shape; closing HER hidden console window (Windows reports it as owned by
her pid) -- taskkill without /F, or an End task that posts WM_CLOSE to it -- sends CTRL_CLOSE to every
process on her console and ends her even with a handler that returns TRUE. Only the old shape put the
window there.

LIVENESS -- psutil existence + command line. NEVER os.kill(pid, 0): on Windows CPython turns signal 0
into GenerateConsoleCtrlEvent(CTRL_C_EVENT, pid), and Windows never delivers CTRL_C to a process-group
id, so NOTHING is delivered and the call returns OK -- for a dead pid too (measured 09-25). It is a
probe that always says "alive".

stdlib only (psutil optional), so it imports cheaply inside her process and inside the MCP servers.
"""
import itertools
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

_GUI_DIR = Path(__file__).resolve().parent
AKASHIC_ROOT = _GUI_DIR.parents[2]                      # gui -> P40_Sensory -> fairies -> akashic_v2
STATE_DIR = AKASHIC_ROOT / "state"
SCRIPT = _GUI_DIR / "sourpatches_chat_window.py"
PID_FILE = STATE_DIR / "sourpatches_chat_window_pid.json"
LOG_FILE = STATE_DIR / "sourpatches_chat_window.log"        # the WINDOW's stdout/stderr
LAUNCHER_LOG = STATE_DIR / "sourpatches_chat_launcher.log"  # this module's own notes (separate file: the
#                                                             window holds LOG_FILE open with its own offset)
PY312 = r"C:\Users\Ace\AppData\Local\Programs\Python\Python312\python.exe"

# Her server, for callers outside her process. She runs `pythonw3.14t -Xgil=0 -u server.py` with
# cwd = AKASHIC_ROOT (Sour_HQ_LEAN_v2.bat:7,143). 5758 = her internal HTTP server, 8081 = her
# PostalHTTPBridge. NOT 5757: that is the status proxy, a different process.
SERVER_SCRIPT = AKASHIC_ROOT / "server.py"
SOUR_PORTS = (5758, 8081)

TRAMPOLINE = True                       # False = launch the window as a direct child of the caller

CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
_LOG_MAX_BYTES = 5 * 1024 * 1024
_NOTE_MAX_BYTES = 1 * 1024 * 1024

# Check-then-launch must be one step inside a free-threaded process: two postal workers could both
# see "no window" before either wrote the pid file. RLock: launch() and ensure_window() nest.
LAUNCH_LOCK = threading.RLock()
_TMP_SEQ = itertools.count(1)


def _unlink_quiet(p: Path) -> None:
    try:
        p.unlink(missing_ok=True)
    except OSError:
        pass


def _atomic_write_text(path: Path, text: str) -> None:
    """temp file + os.replace, so a reader never sees a torn file; retry while a reader holds it.

    The temp name is unique PER CALL (pid, thread, counter). With one name per process, two threads
    writing the same file raced: one thread's os.replace consumed the other's temp and the second
    raised FileNotFoundError (Fable review, measured 09-25).
    """
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.{next(_TMP_SEQ)}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
    except BaseException:
        _unlink_quiet(tmp)
        raise
    for attempt in range(6):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:              # a reader has the target open (Windows); it lets go in ms
            time.sleep(0.05 * (attempt + 1))
        except BaseException:
            _unlink_quiet(tmp)
            raise
    try:
        path.write_text(text, encoding="utf-8")
    finally:
        _unlink_quiet(tmp)


def note(msg: str) -> None:
    """One timestamped line in state/sourpatches_chat_launcher.log. Never raises, never prints to stdout
    (in a stdio MCP server stdout IS the JSON-RPC wire)."""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            if LAUNCHER_LOG.exists() and LAUNCHER_LOG.stat().st_size > _NOTE_MAX_BYTES:
                os.replace(LAUNCHER_LOG, LAUNCHER_LOG.with_name(LAUNCHER_LOG.name + ".prev"))
        except OSError:
            pass
        with open(LAUNCHER_LOG, "a", encoding="utf-8", errors="backslashreplace") as f:
            f.write("%s [pid %d] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), os.getpid(), msg))
    except Exception:
        pass


def find_python312():
    """Same search order the old launch sites used. PyQt6 needs a GIL build (3.12)."""
    import shutil
    for p in (PY312, shutil.which("python3.12"), shutil.which("python3"), shutil.which("python")):
        if p and Path(p).exists():
            return str(p)
    return None


# ─────────────────────────────── the window ───────────────────────────────

def running_window_info():
    """The pid-file record of the LIVE chat window ({'pid', 'parent_pid', ...}), else None.
    Existence + command line (psutil); never a signal."""
    try:
        data = json.loads(PID_FILE.read_text(encoding="utf-8"))
        pid = int(data.get("pid") or 0)
    except Exception:
        return None
    if pid <= 0:
        return None
    try:
        import psutil
        cmdline = " ".join(psutil.Process(pid).cmdline() or [])
    except Exception:
        return None
    if "sourpatches_chat_window" not in cmdline:
        return None
    data["pid"] = pid
    return data


def running_window_pid():
    """PID of the live chat window named in the pid file, else None."""
    info = running_window_info()
    return info["pid"] if info else None


# ─────────────────────────────── her ───────────────────────────────

_PY_OPTS_WITH_VALUE = ("-X", "-W", "-Q", "--check-hash-based-pycs")


def _script_arg(cmdline):
    """The script a python command line runs: the first non-option argument after the interpreter's own
    options -- None for `-c` / `-m`. ONLY that position counts: a process that merely mentions server.py
    in its arguments (an editor, a tail, `--server-script server.py`) is not running it. (The first
    version matched any argument, and the harness caught the MCP stand-in resolving to ITSELF.)"""
    args = list(cmdline or [])[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-c", "-m"):
            return None
        if a in _PY_OPTS_WITH_VALUE:
            i += 2
            continue
        if a.startswith("-") and a != "-":
            i += 1
            continue
        return a
    return None


def _runs_server_script(p, script=None) -> bool:
    """True when psutil Process `p` is a python whose SCRIPT (see _script_arg) is `script` (default
    SERVER_SCRIPT), a relative script path being resolved against that process's cwd."""
    script = Path(script or SERVER_SCRIPT)
    want = os.path.normcase(os.path.abspath(script))
    try:
        if "python" not in (p.name() or "").lower():
            return False
        a = _script_arg(p.cmdline())
        if not a or Path(a).name.lower() != script.name.lower():
            return False
        cand = Path(a)
        if not cand.is_absolute():
            cand = Path(p.cwd()) / cand
        return os.path.normcase(os.path.abspath(cand)) == want
    except Exception:
        return False


def _find_sour():
    """(pid, how). how = 'port:<n>' | 'cmdline' | 'cmdline-ambiguous:<n>' | 'no psutil' | 'unresolved'."""
    try:
        import psutil
    except Exception:
        return None, "no psutil"
    # 1. whoever LISTENS on her ports -- and is running her script (a stranger on the port is not her)
    try:
        for c in psutil.net_connections(kind="tcp"):
            if c.status != psutil.CONN_LISTEN or not c.pid or not c.laddr or c.laddr.port not in SOUR_PORTS:
                continue
            try:
                if _runs_server_script(psutil.Process(c.pid)):
                    return int(c.pid), "port:%d" % c.laddr.port
            except psutil.Error:
                pass
    except Exception:
        pass
    # 2. early boot / shutdown: not listening yet. Match the command line. The venv stub
    #    (Scripts\pythonw.exe) re-launches the real pythonw3.14t.exe with the SAME command line, so
    #    both match; she is the leaf -- the match whose children are not matches.
    try:
        cands = {}
        for p in psutil.process_iter(["name"]):
            if "python" in (p.info.get("name") or "").lower() and _runs_server_script(p):
                cands[p.pid] = p
        leaves = []
        for p in cands.values():
            try:
                kids = p.children()
            except psutil.Error:
                kids = []
            if not any(k.pid in cands for k in kids):
                leaves.append(p)
        if len(leaves) == 1:
            return int(leaves[0].pid), "cmdline"
        if leaves:
            newest = max(leaves, key=lambda q: q.create_time())
            return int(newest.pid), "cmdline-ambiguous:%d" % len(leaves)
    except Exception:
        pass
    return None, "unresolved"


def find_sour_pid():
    """Her server's pid, or None: the process listening on SOUR_PORTS that runs SERVER_SCRIPT, else the
    python running SERVER_SCRIPT (leaf of the venv-stub pair)."""
    return _find_sour()[0]


def resolve_parent_pid(embedded: bool, caller: str = "?"):
    """(pid, how) of the Sour process a window launched from this process must die with.

    embedded=True means this code runs INSIDE her (AKASHIC_EMBEDDED_MCP=1): that is os.getpid().
    Otherwise look her up. Unresolved is LOGGED: that window will be standalone and will outlive her.
    """
    if embedded:
        return os.getpid(), "embedded"
    pid, how = _find_sour()
    if pid is None or how.startswith("cmdline-ambiguous"):
        msg = ("%s: Sour's server pid %s (%s; ports %s, script %s)%s" % (
            caller, "UNRESOLVED" if pid is None else "AMBIGUOUS, using %d" % pid, how, SOUR_PORTS,
            SERVER_SCRIPT, " -- the window will be STANDALONE and will not close with her" if pid is None else ""))
        note(msg)
        try:
            print("[chat_window_launcher] " + msg, file=sys.stderr, flush=True)
        except Exception:
            pass
    return pid, how


# ─────────────────────────────── launching ───────────────────────────────

def _rotate_log() -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > _LOG_MAX_BYTES:
            os.replace(LOG_FILE, LOG_FILE.with_name(LOG_FILE.name + ".prev"))
    except OSError:
        pass


def _banner(parent_pid, via) -> bytes:
    return ("\n=== %s launch parent_pid=%s via=%s ===\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), parent_pid, via)).encode()


def _spawn_direct(args, env, parent_pid):
    """The window as a direct child of this process. Raises if the process cannot be created."""
    try:
        log = open(LOG_FILE, "ab")
    except Exception as e:                       # a log must never block a launch (Opus review R1)
        note("window log %s could not be opened (%r) -- window output goes to DEVNULL" % (LOG_FILE, e))
        log = None
    try:
        if log is not None:
            try:
                log.write(_banner(parent_pid, "direct"))
                log.flush()
            except OSError:
                pass
        out = log if log is not None else subprocess.DEVNULL
        if sys.platform == "win32":
            proc = subprocess.Popen(
                args, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW, close_fds=True, env=env,
            )
        else:
            proc = subprocess.Popen(
                args, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                start_new_session=True, close_fds=True, env=env,
            )
    finally:
        if log is not None:
            log.close()          # the child holds its own handle; ours must not pin the file
    return proc.pid


# Runs under `python3.12 -I -S -c`: stdlib only, reads its spec from stdin (no command-line length
# issue for long messages), starts the window on its OWN new hidden console, reports the pid, exits.
_TRAMPOLINE_SRC = r'''
import json, subprocess, sys, time
spec = json.loads(sys.stdin.buffer.read().decode("utf-8"))
out, log_state = subprocess.DEVNULL, "none"
if spec["log"]:
    try:
        out = open(spec["log"], "ab")
        out.write(("\n=== %s launch parent_pid=%s via=trampoline ===\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), spec["parent_pid"])).encode())
        out.flush()
        log_state = "ok"
    except Exception as e:
        out, log_state = subprocess.DEVNULL, "devnull: %r" % (e,)
p = subprocess.Popen(spec["args"], stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                     creationflags=spec["flags"], close_fds=True)
sys.stdout.write(json.dumps({"pid": p.pid, "log": log_state}) + "\n")
sys.stdout.flush()
'''


def _spawn_via_trampoline(python, args, env, parent_pid):
    """The window as a child of a trampoline that exits at once: NOT in the caller's process tree."""
    spec = {"args": args, "flags": CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
            "log": str(LOG_FILE), "parent_pid": parent_pid}
    t = subprocess.Popen(
        [python, "-I", "-S", "-c", _TRAMPOLINE_SRC],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW, close_fds=True, env=env,
    )
    try:
        out, err = t.communicate(json.dumps(spec, ensure_ascii=False).encode("utf-8"), timeout=30)
    except subprocess.TimeoutExpired:
        t.kill()
        t.communicate()
        raise RuntimeError("trampoline did not report within 30 s")
    if t.returncode != 0:
        raise RuntimeError("trampoline rc=%s: %s" % (t.returncode, err.decode("utf-8", "replace")[-400:]))
    rep = json.loads(out.decode("utf-8").strip().splitlines()[-1])
    if rep.get("log") != "ok":
        note("window log %s: %s -- window output goes to DEVNULL" % (LOG_FILE, rep.get("log")))
    return int(rep["pid"])


def launch(message=None, feeling="curious", parent_pid=None):
    """Start the window and return its pid, or None if there is no Python 3.12 or no window script.
    Raises if the process cannot be created (callers catch).

    Callers check running_window_pid() first -- or call ensure_window(), which does both under the
    lock. parent_pid = the Sour server pid the window must die with; None only for a deliberately
    standalone window.
    """
    python = find_python312()
    if not python or not SCRIPT.exists():
        note("launch refused: python312=%r script=%s exists=%s" % (python, SCRIPT, SCRIPT.exists()))
        return None
    args = [python, "-u", str(SCRIPT)]
    if message:
        args += ["--message", message]
    if feeling:
        args += ["--feeling", feeling]
    if parent_pid:
        args += ["--parent-pid", str(int(parent_pid))]
    # stdout is a FILE, and Python gives a file the locale codec (cp1252) with errors='strict': one
    # emoji in a print outside a try (e.g. "Skipping duplicate message") raised inside a Qt slot and
    # aborted the window (measured 09-25, D3). Only the std streams change.
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8:backslashreplace"
    with LAUNCH_LOCK:
        _rotate_log()
        pid, via = None, None
        if TRAMPOLINE and sys.platform == "win32":
            try:
                pid, via = _spawn_via_trampoline(python, args, env, parent_pid), "trampoline"
            except Exception as e:
                note("trampoline failed (%r) -- launching the window directly (it will be this process's child)" % (e,))
        if pid is None:
            pid, via = _spawn_direct(args, env, parent_pid), "direct"
        # Provisional pid file NOW, so an open request in the next second sees this window instead of
        # launching a second one (07-19: two windows 2 s apart). The window rewrites it once it is up.
        try:
            _atomic_write_text(PID_FILE, json.dumps({
                "pid": pid, "started": time.time(), "parent_pid": parent_pid, "provisional": True, "via": via,
            }))
        except Exception as e:
            note("provisional pid file not written: %r" % (e,))
        note("launched window pid=%s parent_pid=%s via=%s" % (pid, parent_pid, via))
    return pid


def ensure_window(message=None, feeling="curious", parent_pid=None):
    """Check-then-launch as ONE step (LAUNCH_LOCK). Returns (pid, launched): (existing pid, False) when a
    window is already up, (new pid, True) when one was started, (None, False) when none could be."""
    with LAUNCH_LOCK:
        pid = running_window_pid()
        if pid:
            return pid, False
        pid = launch(message, feeling, parent_pid=parent_pid)
        return pid, bool(pid)
