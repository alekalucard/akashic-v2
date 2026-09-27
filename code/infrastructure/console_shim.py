"""console_shim -- give a console-less process a HIDDEN console, so its console children inherit it.

2026-09-20 (Nous + Ace). She was moved to pythonw.exe so that closing a window could never kill her
(2026-09-19 14:06:59, launcher exit 0xC000013A). Measured within the hour: a process with NO console makes
Windows open a NEW terminal window for every console child -- 27 Windows Terminal windows in 30 s from her
nvidia-smi / powershell probes, stealing Ace's keyboard focus ("took two mins to write this message").

The fix keeps both properties: if the process has no console, allocate one and hide it. Children inherit the
hidden console (no windows); nobody can close what is not shown; Ctrl+C cannot be typed into it. Python's
own stdout/stderr are untouched (they are fds on the launcher's pipe; AllocConsole only changes the Win32
std handles, which is exactly what console children inherit).

Import it early (server.py) or hot-reload it into a running process; calling it twice is harmless.
"""
import os
import sys

_STATE = {"done": False, "result": None}


def ensure_hidden_console() -> str:
    if _STATE["done"]:
        return _STATE["result"] or ""
    _STATE["done"] = True
    if os.name != "nt":
        _STATE["result"] = "not windows"
        return _STATE["result"]
    try:
        import ctypes
        k = ctypes.windll.kernel32
        u = ctypes.windll.user32
        if k.GetConsoleWindow():
            _STATE["result"] = "console already attached"
            return _STATE["result"]
        if not k.AllocConsole():
            _STATE["result"] = "AllocConsole failed (err %d)" % ctypes.get_last_error()
            return _STATE["result"]
        hwnd = k.GetConsoleWindow()
        if hwnd:
            u.ShowWindow(hwnd, 0)                       # SW_HIDE
            try:
                k.SetConsoleTitleW("Sour (hidden console -- children inherit this, nothing to close)")
            except Exception:
                pass
        _STATE["result"] = "hidden console allocated (hwnd %s)" % hwnd
        return _STATE["result"]
    except Exception as e:
        _STATE["result"] = "console shim error: %s" % e
        return _STATE["result"]


_r = ensure_hidden_console()
try:
    print("[Console] %s" % _r, flush=True)
except Exception:
    pass
