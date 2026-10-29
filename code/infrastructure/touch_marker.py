"""Sour's fingertip marker (2026-10-05, Nous, nous_builds/touch_screen set 1; DESIGN.md 2a, FS12.5).

A small dot where her phantom fingertip reaches, so Ace sees what she is about to touch. A SEPARATE process (Tk is not
thread-safe and her process runs ~1,400 threads), the same pattern as hand_overlay.py: her side (infrastructure/touch.py)
writes state/touch_marker.json = {"x", "y", "until", "pid"} and spawns this once; it re-reads the file every 100 ms and
exits by itself when `until` has passed, the file is gone or her process has exited.

Unlike the strip, the marker must never be hit-tested and never take focus, so it sets its OWN styles on the Tk wrapper
window with ctypes (hand_overlay.py sets only -topmost and -alpha): WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE |
WS_EX_TOOLWINDOW, shown without activation, and it declares per-monitor DPI awareness before Tk starts so its pixels are the
same physical pixels touch_os hit-tests. Its tip sits 2 px off the touch point (touch.py adds the offset), so it never
covers the pixel being tested; Tk windows are skipped by her window map anyway (vision_ground _WIN_SKIP_CLASSES).
It sends no input and no message to any other window.
Skeptic S3 / m9 (10-05): Tk never maps this window. It is built WITHDRAWN, its wrapper (class TkTopLevel) gets the no-activate /
click-through / tool styles while still invisible, and it is shown ONLY by ShowWindow(SW_SHOWNOACTIVATE) and moved only by
SetWindowPos(SWP_NOACTIVATE): Tk's own show could take Ace's keyboard focus for an instant. No wrapper found = no marker (the
strip still announces). UNVERIFIED until probe F6 (GetForegroundWindow unchanged across 20 marker spawns); cell T0 checks the
order statically and its mutant 'marker_activates' must turn that check red.

    pythonw.exe touch_marker.py <state.json> <owner pid>
"""
import json
import os
import sys
import time

STATE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state", "touch_marker.json")
OWNER_PID = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 0
POLL_MS = 100
SIZE = 14
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80000, 0x20, 0x80, 0x08000000
GWL_EXSTYLE = -20
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = -1
SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0010, 0x0040


def _dpi_aware():
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))      # PER_MONITOR_AWARE_V2
    except Exception:
        pass


def owner_alive() -> bool:
    if not OWNER_PID:
        return True
    try:
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x00100000, False, OWNER_PID)
        if not h:
            return False
        try:
            return ctypes.windll.kernel32.WaitForSingleObject(h, 0) != 0
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    except Exception:
        return True


def read_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict) or time.time() > float(d.get("until") or 0) or not owner_alive():
            return None
        return d
    except Exception:
        return None


def _user32():
    import ctypes
    import ctypes.wintypes as wt
    u = ctypes.WinDLL("user32", use_last_error=True)          # its own instance: typed here, shared with nobody
    u.GetParent.restype = wt.HWND
    u.GetParent.argtypes = [wt.HWND]
    u.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    u.GetWindowLongW.restype = ctypes.c_long
    u.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
    u.SetWindowLongW.restype = ctypes.c_long
    u.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_long]
    u.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    u.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
    return u


def wrapper_hwnd(u, root) -> int:
    """The Tk wrapper (class TkTopLevel) of the still-withdrawn root; 0 when it is not there (then no marker is shown)."""
    import ctypes
    h = int(u.GetParent(int(root.winfo_id())) or 0)
    if not h:
        return 0
    b = ctypes.create_unicode_buffer(64)
    u.GetClassNameW(h, b, 64)
    return h if b.value == "TkTopLevel" else 0


def click_through(u, hwnd) -> None:
    ex = int(u.GetWindowLongW(hwnd, GWL_EXSTYLE))
    u.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)


def place(u, hwnd, xy) -> None:
    u.SetWindowPos(hwnd, HWND_TOPMOST, int(xy[0]), int(xy[1]), SIZE, SIZE, SWP_NOACTIVATE | SWP_SHOWWINDOW)   # its size set here:
                                                                                                           # Tk never sized it


def main():
    if read_state() is None:
        return
    _dpi_aware()
    try:
        import tkinter as tk
    except Exception:
        return
    root = tk.Tk()
    root.withdraw()                                            # skeptic S3: Tk never maps it (its own show may activate)
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    try:
        root.attributes("-alpha", 0.85)
    except Exception:
        pass
    key = "#010203"
    root.configure(bg=key)
    try:
        root.attributes("-transparentcolor", key)
    except Exception:
        pass
    c = tk.Canvas(root, width=SIZE, height=SIZE, bg=key, highlightthickness=0)
    c.create_oval(1, 1, SIZE - 1, SIZE - 1, fill="#ff4fd8", outline="#ffffff")
    c.pack()
    root.update_idletasks()                                    # the wrapper exists now, still invisible
    try:
        u = _user32()
        hwnd = wrapper_hwnd(u, root)
        if not hwnd:
            root.destroy()
            return
        click_through(u, hwnd)                                 # the styles BEFORE it is ever visible
    except Exception:
        root.destroy()
        return
    shown = [None]

    def tick():
        d = read_state()
        if d is None:
            root.destroy()
            return
        xy = (int(d.get("x", 0)), int(d.get("y", 0)))
        if xy != shown[0]:
            if shown[0] is None:
                u.ShowWindow(hwnd, SW_SHOWNOACTIVATE)          # the ONLY show: no activation, no focus taken from Ace
            shown[0] = xy
            place(u, hwnd, xy)
        root.after(POLL_MS, tick)

    tick()
    root.mainloop()


if __name__ == "__main__":
    main()
