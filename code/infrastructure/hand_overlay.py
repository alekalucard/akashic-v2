"""Sour's hand indicator (2026-09-19, Ace: "an alert or something that she is holding the mouse so I don't take
it away from her while she practices").

A small always-on-top strip at the top-centre of the screen while she is holding the mouse. It is a SEPARATE
process: Tk is not thread-safe and her process runs ~1,400 threads. Her side (infrastructure/intention.py)
writes state/hand_overlay.json = {"text": str, "until": epoch_s} and spawns this once; the strip re-reads the
file every 300 ms, shows the latest text, and exits by itself when `until` has passed, the text is empty, or
the file is gone. Nothing to kill, nothing to leak.

    pythonw.exe hand_overlay.py <state.json>
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


def main():
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


if __name__ == "__main__":
    main()
