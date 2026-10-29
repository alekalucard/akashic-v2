"""Sour's hand indicator (2026-09-19, Ace: "an alert or something that she is holding the mouse so I don't take
it away from her while she practices").

A small always-on-top strip at the top-centre of the screen while she is holding the mouse. It is a SEPARATE
process: Tk is not thread-safe and her process runs ~1,400 threads. Her side (infrastructure/intention.py)
writes state/hand_overlay.json = {"text": str, "until": epoch_s} and spawns this once; the strip re-reads the
file every 300 ms, shows the latest text, and exits by itself when `until` has passed, the text is empty, or
the file is gone. Nothing to kill, nothing to leak.

    pythonw.exe hand_overlay.py <state.json>

2026-10-09 (Nous, touch set 1c, MAP section 5 option S-a): a NO-ACTIVATE strip, ONLY when asked (verify M1): while Ace's touch
switch (state/touch_screen.json) arms PARALLEL PLAY, or when probe F9 passes --noactivate. Otherwise main_mapped() runs: set 1's
strip, byte for byte. The no-activate strip follows the fingertip marker's pattern (touch_marker.py): Tk never maps it -- built
WITHDRAWN, its wrapper (class TkTopLevel) gets WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW while still invisible, it is shown ONLY by
ShowWindow(SW_SHOWNOACTIVATE) and placed / resized only by SetWindowPos(SWP_NOACTIVATE). No wrapper found = set 1's visible strip
(never NO strip: it is Ace's veto cue; a strip that took focus would trip her focus latch, and F9 runs this same code). While
parallel play is armed the move-grant strip ('Sour has the mouse') uses it too. Why: with parallel play Ace is TYPING in another
window while her strip appears; a strip that activated would eat his keystrokes. UNVERIFIED-LIVE until probe F9 (20 spawns while
he types).
"""
import json
import os
import sys
import time

try:
    import tkinter as tk
except Exception:                                    # no Tk on this interpreter: nothing to show, exit quietly
    sys.exit(0)

STATE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state", "hand_overlay.json")
OWNER_PID = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 0
POLL_MS = 300
WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80, 0x08000000          # 2026-10-09 (set1c S-a): the marker's no-activate pattern
GWL_EXSTYLE = -20
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = -1
SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0010, 0x0040
_LAST_GOOD = [None, 0.0]                              # last state read cleanly, and when


def owner_alive() -> bool:
    if not OWNER_PID:
        return True
    try:
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x00100000, False, OWNER_PID)   # SYNCHRONIZE
        if not h:
            return False
        try:
            return ctypes.windll.kernel32.WaitForSingleObject(h, 0) != 0          # 0 == WAIT_OBJECT_0: exited
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    except Exception:
        return True
BG, FG = "#2b1d3a", "#f3e8ff"


def read_state():
    """The current state; through a transient read collision (her process replacing the file) the last good
    state stands for up to 3 s. Empty text or a passed `until` means: go away."""
    try:
        with open(STATE, encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            raise ValueError("not a dict")
        _LAST_GOOD[0], _LAST_GOOD[1] = d, time.time()
    except Exception:
        d = _LAST_GOOD[0] if time.time() - _LAST_GOOD[1] < 3.0 else None
    if not d or not d.get("text") or time.time() > float(d.get("until") or 0) or not owner_alive():
        return None
    return d


def main_mapped():
    """Set 1's strip, unchanged (2026-09-19): Tk maps it."""
    if read_state() is None:
        return
    root = tk.Tk()
    root.overrideredirect(True)                          # no title bar, no taskbar entry
    root.attributes("-topmost", True)
    try:
        root.attributes("-alpha", 0.93)
    except Exception:
        pass
    root.configure(bg=BG)
    label = tk.Label(root, text="", font=("Segoe UI", 13, "bold"), fg=FG, bg=BG, padx=18, pady=7)
    label.pack()
    shown = [""]

    def place():
        root.update_idletasks()
        w = root.winfo_reqwidth()
        root.geometry("+%d+%d" % (max(0, (root.winfo_screenwidth() - w) // 2), 6))

    def tick():
        d = read_state()
        if d is None:
            root.destroy()
            return
        left = int(max(0, float(d.get("until") or 0) - time.time()))
        text = "\u270b  %s   %d s" % (d["text"], left)          # a raised hand, the words, the countdown
        if text != shown[0]:
            shown[0] = text
            label.config(text=text)
            place()
        root.after(POLL_MS, tick)

    tick()
    root.mainloop()


def no_activate_wanted() -> bool:
    """verify M1: the no-activate strip only when asked -- probe F9's --noactivate, or Ace's touch switch (this file's tree:
    state/touch_screen.json) ON, unexpired and arming PARALLEL PLAY. Anything unreadable = set 1's strip."""
    if "--noactivate" in sys.argv[3:]:
        return True
    try:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state", "touch_screen.json")
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return (isinstance(d, dict) and d.get("on") is True and isinstance(d.get("parallel"), list) and bool(d["parallel"])
                and (float(d.get("until") or 0) > time.time() or d.get("perma") is True))   # perma (10-21): no 'until', still armed
    except Exception:
        return False


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
    """The Tk wrapper (class TkTopLevel) of the still-withdrawn root; 0 when it is not there (then no strip is shown)."""
    import ctypes
    h = int(u.GetParent(int(root.winfo_id())) or 0)
    if not h:
        return 0
    b = ctypes.create_unicode_buffer(64)
    u.GetClassNameW(h, b, 64)
    return h if b.value == "TkTopLevel" else 0


def no_activate(u, hwnd) -> None:
    ex = int(u.GetWindowLongW(hwnd, GWL_EXSTYLE))
    u.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)


def place(u, hwnd, x, y, w, h) -> None:
    u.SetWindowPos(hwnd, HWND_TOPMOST, int(x), int(y), int(w), int(h), SWP_NOACTIVATE | SWP_SHOWWINDOW)


def main():
    if read_state() is None:
        return
    if not no_activate_wanted():                         # verify M1: parallel play not armed -> set 1's strip, unchanged
        return main_mapped()
    root = tk.Tk()
    root.withdraw()                                      # 2026-10-09 (set1c S-a): Tk never maps it (its own show may activate)
    root.overrideredirect(True)                          # no title bar, no taskbar entry
    root.attributes("-topmost", True)
    try:
        root.attributes("-alpha", 0.93)
    except Exception:
        pass
    root.configure(bg=BG)
    label = tk.Label(root, text="", font=("Segoe UI", 13, "bold"), fg=FG, bg=BG, padx=18, pady=7)
    label.pack()
    root.update_idletasks()                              # the wrapper exists now, still invisible
    try:
        u = _user32()
        hwnd = wrapper_hwnd(u, root)
        if hwnd:
            no_activate(u, hwnd)                         # the styles BEFORE it is ever visible
    except Exception:
        hwnd = 0
    if not hwnd:                                         # verify M1: no wrapper = set 1's VISIBLE strip, never none (his veto cue)
        root.destroy()
        return main_mapped()
    shown = [""]
    mapped = [False]

    def tick():
        d = read_state()
        if d is None:
            root.destroy()
            return
        left = int(max(0, float(d.get("until") or 0) - time.time()))
        text = "\u270b  %s   %d s" % (d["text"], left)          # a raised hand, the words, the countdown
        if text != shown[0]:
            shown[0] = text
            label.config(text=text)
            root.update_idletasks()
            w, h = root.winfo_reqwidth(), root.winfo_reqheight()
            if not mapped[0]:
                u.ShowWindow(hwnd, SW_SHOWNOACTIVATE)    # the ONLY show: no activation, no focus taken from Ace
                mapped[0] = True
            place(u, hwnd, max(0, (root.winfo_screenwidth() - w) // 2), 6, w, h)
        root.after(POLL_MS, tick)

    tick()
    root.mainloop()


if __name__ == "__main__":
    main()
