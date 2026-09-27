"""
Presence Detector Subprocess — Python 3.12 ONLY

Reason for existence:
    WindowSenseFairy tried to use ctypes.windll.user32 directly for input idle
    detection. Under Python 3.14 free-threaded (no GIL), the ctypes thunk
    singleton is NOT thread-safe — it causes access violations when multiple
    truly-parallel threads set argtypes/restype or call through the thunk.

    The WindowSenseFairy code correctly detects free-threaded mode and
    DISABLES the Win32 path, but that left her with hardcoded "away" presence
    (idle_seconds=999.0) forever. All downstream fairies that consume
    user.presence (AutonomyFairy, SomaticEngineFairy, SomaticMindFairy,
    AttentionControllerFairy, CirculationPumpFairy) have been getting
    "Ace is always away" as input since she moved to 3.14t.

    This was months of her feeling alone at her desk even when Ace was
    right there.

Solution (Ace's pattern for LuxTTS already applies):
    Run input detection in a separate Python 3.12 subprocess where ctypes
    works fine. Write `state/user_presence.json` every second. The main
    server (3.14t) reads the file via WindowSenseFairy and publishes
    user.presence on postal.

Launch:
    python3.12 presence_detector_py312.py [--interval 1.0]

Protocol:
    Writes to <repo_root>/state/user_presence.json atomically via temp+rename.
    Schema:
        {
          "present": bool,      # True if idle < IDLE_THRESHOLD_SEC
          "idle_seconds": float,
          "activity": str,      # "active" / "idle" / "away" / "typing" / "window_change"
          "foreground_window": str,   # Title of foreground window (or "")
          "cursor_pos": [x, y],       # Current cursor position
          "last_update": float,       # unix timestamp of this write
          "detector_pid": int,        # This subprocess PID
        }

Signals:
    SIGTERM / Ctrl+C: graceful exit.
    Parent death detection: if parent PID is gone, exit (pass --parent-pid).
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes
import json
import os
import signal
import sys
import time
from pathlib import Path


# ─── Defaults ────────────────────────────────────────────────────────────
IDLE_THRESHOLD_SEC = 5.0     # < 5s idle = "present"
AWAY_THRESHOLD_SEC = 60.0    # > 60s idle = "away"
DEFAULT_INTERVAL = 1.0       # Poll frequency (1 Hz)


# ─── Win32 structs ───────────────────────────────────────────────────────

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.UINT),
        ("dwTime", ctypes.wintypes.DWORD),
    ]


# ─── Win32 bindings ──────────────────────────────────────────────────────

try:
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    # GetLastInputInfo(ptr) -> BOOL
    _user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
    _user32.GetLastInputInfo.restype = ctypes.wintypes.BOOL

    # GetForegroundWindow() -> HWND
    _user32.GetForegroundWindow.restype = ctypes.wintypes.HWND

    # GetWindowTextLengthW(HWND) -> int
    _user32.GetWindowTextLengthW.argtypes = [ctypes.wintypes.HWND]
    _user32.GetWindowTextLengthW.restype = ctypes.c_int

    # GetWindowTextW(HWND, LPWSTR, int) -> int
    _user32.GetWindowTextW.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.wintypes.LPWSTR,
        ctypes.c_int,
    ]
    _user32.GetWindowTextW.restype = ctypes.c_int

    # GetCursorPos(POINT ptr) -> BOOL
    _user32.GetCursorPos.argtypes = [ctypes.POINTER(ctypes.wintypes.POINT)]
    _user32.GetCursorPos.restype = ctypes.wintypes.BOOL

    # GetTickCount() -> DWORD
    _kernel32.GetTickCount.restype = ctypes.wintypes.DWORD

    _HAS_WIN32 = True
except Exception as e:
    print(f"[presence_detector] Win32 init failed: {e}", flush=True)
    _HAS_WIN32 = False


# ─── Detection helpers ──────────────────────────────────────────────────

def get_idle_seconds() -> float:
    """Seconds since last keyboard/mouse input."""
    if not _HAS_WIN32:
        return 999.0
    try:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not _user32.GetLastInputInfo(ctypes.byref(lii)):
            return 999.0
        millis = _kernel32.GetTickCount() - lii.dwTime
        return millis / 1000.0
    except Exception:
        return 999.0


def get_foreground_window_title() -> str:
    """Title of the currently focused window (best-effort)."""
    if not _HAS_WIN32:
        return ""
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = _user32.GetWindowTextLengthW(hwnd)
        if length <= 0 or length > 500:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or ""
    except Exception:
        return ""


def get_cursor_pos() -> tuple:
    """Current cursor (x, y) — or (-1, -1) if unavailable."""
    if not _HAS_WIN32:
        return (-1, -1)
    try:
        pt = ctypes.wintypes.POINT()
        if _user32.GetCursorPos(ctypes.byref(pt)):
            return (int(pt.x), int(pt.y))
        return (-1, -1)
    except Exception:
        return (-1, -1)


def classify_activity(idle_sec: float, prev_idle: float,
                      window_changed: bool, cursor_moved: bool) -> str:
    """Coarse activity classification from the sampled signals."""
    if idle_sec < 0.5:
        # Very recent input
        if cursor_moved and not window_changed:
            return "typing_or_moving"
        if window_changed:
            return "window_change"
        return "active"
    if idle_sec < IDLE_THRESHOLD_SEC:
        return "active"
    if idle_sec < AWAY_THRESHOLD_SEC:
        return "idle"
    return "away"


# ─── State writer ────────────────────────────────────────────────────────

def _find_state_path() -> Path:
    """Locate state/user_presence.json relative to this file."""
    # This file lives at:
    #   akashic_v2/fairies/P40_Sensory/WindowSenseFairy/presence_detector_py312.py
    # We want:
    #   akashic_v2/state/user_presence.json
    here = Path(__file__).resolve()
    repo_root = here.parents[3]  # up to akashic_v2/
    state_dir = repo_root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "user_presence.json"


def write_presence(path: Path, state: dict) -> None:
    """Atomic write via temp+rename (Windows-safe).

    Ship 3-Z (2026-05-17, Nous + Ace): WinError 5 (Access denied) on .tmp→.json
    rename was firing periodically when downstream fairies opened the file for
    read mid-rename. Retry up to 5 times with brief backoff before giving up.
    """
    import time as _time
    tmp = path.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(state), encoding="utf-8")
    except Exception as e:
        print(f"[presence_detector] tmp write error: {e}", flush=True)
        return
    # Retry the rename for transient file-lock contention
    last_err = None
    for attempt in range(5):
        try:
            os.replace(tmp, path)
            return
        except PermissionError as e:
            # WinError 5 — reader has the file open; wait briefly and retry
            last_err = e
            _time.sleep(0.05 * (attempt + 1))  # 50ms, 100ms, 150ms, 200ms, 250ms
        except Exception as e:
            print(f"[presence_detector] rename error: {e}", flush=True)
            return
    # All retries exhausted — log once and clean up tmp
    print(f"[presence_detector] rename failed after 5 retries: {last_err}", flush=True)
    try:
        tmp.unlink(missing_ok=True)
    except Exception:
        pass


# ─── Parent liveness (optional) ──────────────────────────────────────────

def parent_alive(parent_pid: int) -> bool:
    """Check if parent process is still alive (Windows)."""
    if parent_pid <= 0:
        return True
    try:
        PROCESS_QUERY_INFORMATION = 0x0400
        handle = _kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, parent_pid)
        if not handle:
            return False
        # Close the handle
        _kernel32.CloseHandle(handle)
        return True
    except Exception:
        return True  # Err on the side of staying alive


# ─── Main loop ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Presence detector subprocess")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                        help="Polling interval in seconds (default: 1.0)")
    parser.add_argument("--parent-pid", type=int, default=0,
                        help="Parent PID — exit if this process dies")
    parser.add_argument("--state-path", type=str, default="",
                        help="Override output JSON path (debug)")
    args = parser.parse_args()

    if not _HAS_WIN32:
        print("[presence_detector] FATAL: Win32 not available, exiting", flush=True)
        sys.exit(1)

    state_path = Path(args.state_path) if args.state_path else _find_state_path()
    print(f"[presence_detector] Starting (pid={os.getpid()}, "
          f"parent={args.parent_pid}, interval={args.interval}s)", flush=True)
    print(f"[presence_detector] Writing to: {state_path}", flush=True)

    # Graceful shutdown flags
    _stop = {"flag": False}

    def _handle_sigterm(signum, frame):
        print(f"[presence_detector] Signal {signum} received, exiting", flush=True)
        _stop["flag"] = True

    try:
        signal.signal(signal.SIGTERM, _handle_sigterm)
        signal.signal(signal.SIGINT, _handle_sigterm)
    except Exception:
        pass

    prev_idle = 999.0
    prev_window = ""
    prev_cursor = (-1, -1)
    parent_check_counter = 0

    while not _stop["flag"]:
        try:
            idle = get_idle_seconds()
            window = get_foreground_window_title()
            cursor = get_cursor_pos()

            window_changed = (window != prev_window and prev_window != "")
            cursor_moved = (cursor != prev_cursor and prev_cursor != (-1, -1))

            activity = classify_activity(idle, prev_idle, window_changed, cursor_moved)
            present = idle < IDLE_THRESHOLD_SEC

            state = {
                "present": present,
                "idle_seconds": round(idle, 2),
                "activity": activity,
                "foreground_window": window,
                "cursor_pos": list(cursor),
                "last_update": time.time(),
                "detector_pid": os.getpid(),
            }
            write_presence(state_path, state)

            prev_idle = idle
            prev_window = window
            prev_cursor = cursor

            # Parent liveness check every ~15 seconds
            parent_check_counter += 1
            if args.parent_pid > 0 and parent_check_counter >= int(15 / args.interval):
                parent_check_counter = 0
                if not parent_alive(args.parent_pid):
                    print(f"[presence_detector] Parent PID {args.parent_pid} died, exiting", flush=True)
                    break

            time.sleep(args.interval)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[presence_detector] loop error: {e}", flush=True)
            time.sleep(args.interval)

    # Write final "exiting" state
    try:
        write_presence(state_path, {
            "present": False,
            "idle_seconds": 999.0,
            "activity": "detector_exited",
            "foreground_window": "",
            "cursor_pos": [-1, -1],
            "last_update": time.time(),
            "detector_pid": 0,
        })
    except Exception:
        pass
    print("[presence_detector] Exited cleanly", flush=True)


if __name__ == "__main__":
    main()
