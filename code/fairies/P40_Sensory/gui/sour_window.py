"""
sour_window.py - Sourpatches' Standalone Chat Window
=====================================================
A lightweight tkinter chat window that Sourpatches can open/close on her own.

Runs as a SEPARATE PROCESS from server.py (no Qt event loop conflicts).
Communicates via file-based IPC:
  - INBOX:  state/sour_window_inbox.json   (fairy writes, window reads)
  - OUTBOX: state/sour_window_outbox.json  (window writes, fairy reads)
  - CTRL:   state/sour_window_ctrl.json    (control signals: show/hide/close)

Called by ChatSenseFairy as a tool when Sourpatches wants to speak.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import sys
import os
import json
import time
import uuid
import threading
from pathlib import Path
from datetime import datetime
from collections import deque

import tkinter as tk
from tkinter import scrolledtext, font as tkfont

# ─────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────

_AKASHIC_ROOT = Path(__file__).resolve().parent.parent.parent.parent
STATE_DIR = _AKASHIC_ROOT / "state"
INBOX_FILE = STATE_DIR / "sour_window_inbox.json"
OUTBOX_FILE = STATE_DIR / "sour_window_outbox.json"
CTRL_FILE = STATE_DIR / "sour_window_ctrl.json"
HISTORY_FILE = STATE_DIR / "sour_window_history.json"

MAX_DISPLAY = 200
POLL_MS = 500  # Poll inbox every 500ms

# ─────────────────────────────────────────────────────────────
# SOURPATCHES' AESTHETIC
# ─────────────────────────────────────────────────────────────

COLORS = {
    "bg": "#1a1a2e",           # Deep indigo background
    "bg_chat": "#16213e",      # Slightly lighter chat area
    "bg_input": "#0f3460",     # Input background - darker blue, distinct from bg
    "sour_bubble": "#533483",  # Sour's messages - purple
    "ace_bubble": "#0f3460",   # Ace's messages - dark blue
    "sour_text": "#e2b0ff",    # Sour's text - light purple
    "ace_text": "#94b3fd",     # Ace's text - light blue
    "system_text": "#4a4a6a",  # System messages - muted
    "input_text": "#e0e0e0",   # Input text
    "input_border": "#533483", # Input border - purple
    "title_text": "#e2b0ff",   # Title text
    "feeling_text": "#ff79c6", # Feeling indicator
    "timestamp": "#4a4a6a",    # Timestamps
    "accent": "#ff79c6",       # Pink accent
    "scrollbar": "#533483",
}

FEELING_EMOJI = {
    "curious": "🔮",
    "playful": "🍪",
    "focused": "⚡",
    "happy": "✨",
    "thoughtful": "💭",
    "excited": "🌟",
    "calm": "🌙",
    "neutral": "💜",
    "warm": "🌸",
    "concerned": "💝",
    "creative": "🎨",
}

# ─────────────────────────────────────────────────────────────
# FILE IPC
# ─────────────────────────────────────────────────────────────

def _read_json(path: Path) -> dict:
    """Read JSON file safely."""
    try:
        if path.exists() and path.stat().st_size > 0:
            return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _write_json(path: Path, data: dict):
    """Write JSON file atomically (write to tmp then rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # 2026-09-25: a temp name unique per call -- `path.with_suffix(".tmp")` was shared by every writer
    # (her and this window both write the inbox), so one writer's rename could take the other's temp.
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.{time.monotonic_ns()}.tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _consume_inbox() -> list:
    """Read and clear inbox messages. Returns list of message dicts."""
    data = _read_json(INBOX_FILE)
    messages = data.get("messages", [])
    if messages:
        _write_json(INBOX_FILE, {"messages": []})
    return messages


def _send_outbox(sender: str, content: str, msg_id: str = None):
    """Append a message to the outbox for the fairy to read."""
    data = _read_json(OUTBOX_FILE)
    msgs = data.get("messages", [])
    msgs.append({
        "sender": sender,
        "content": content,
        "msg_id": msg_id or uuid.uuid4().hex[:8],
        "timestamp": time.time(),
    })
    _write_json(OUTBOX_FILE, {"messages": msgs})


def _read_ctrl() -> dict:
    """Read and clear control signals."""
    data = _read_json(CTRL_FILE)
    if data:
        _write_json(CTRL_FILE, {})
    return data


def _write_ctrl(signal: str, **kwargs):
    """Write a control signal (used by fairy to control window)."""
    data = {"signal": signal, "ts": time.time()}
    data.update(kwargs)
    _write_json(CTRL_FILE, data)


# ─────────────────────────────────────────────────────────────
# CHAT WINDOW
# ─────────────────────────────────────────────────────────────

class SourWindow(tk.Tk):
    """Sourpatches' personal chat window."""

    def __init__(self, initial_message: str = None, initial_feeling: str = "curious"):
        super().__init__()

        self.title("💜 Sourpatches")
        self.geometry("480x720")
        self.configure(bg=COLORS["bg"])
        self.minsize(400, 500)

        # Make window stay on top initially, then release
        self.attributes("-topmost", True)
        self.after(3000, lambda: self.attributes("-topmost", False))

        # Icon (if available)
        try:
            icon_path = _AKASHIC_ROOT / "fairies" / "P50_Persona" / "Waking Minds" / "Sourpatches" / "sour_icon.ico"
            if icon_path.exists():
                self.iconbitmap(str(icon_path))
        except tk.TclError:
            pass

        self._messages = deque(maxlen=MAX_DISPLAY)
        self._current_feeling = initial_feeling
        self._running = True

        self._build_ui()
        self._load_history()

        if initial_message:
            self._add_message("Sourpatches", initial_message, initial_feeling)

        # Start polling
        self._poll_inbox()
        self._poll_ctrl()

        # Window close handler
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Write PID for process management
        _write_json(STATE_DIR / "sour_window_pid.json", {
            "pid": os.getpid(),
            "started": time.time(),
        })

    def _build_ui(self):
        """Build the chat UI."""
        # ── Header ──
        header = tk.Frame(self, bg=COLORS["bg"], height=50)
        header.pack(fill=tk.X, padx=10, pady=(10, 0))
        header.pack_propagate(False)

        emoji = FEELING_EMOJI.get(self._current_feeling, "💜")
        self._title_label = tk.Label(
            header,
            text=f"{emoji} Sourpatches",
            font=("Segoe UI", 16, "bold"),
            fg=COLORS["title_text"],
            bg=COLORS["bg"],
            anchor="w",
        )
        self._title_label.pack(side=tk.LEFT)

        self._feeling_label = tk.Label(
            header,
            text=f"feeling {self._current_feeling}",
            font=("Segoe UI", 10, "italic"),
            fg=COLORS["feeling_text"],
            bg=COLORS["bg"],
            anchor="e",
        )
        self._feeling_label.pack(side=tk.RIGHT)

        # ── Separator ──
        sep = tk.Frame(self, bg=COLORS["accent"], height=1)
        sep.pack(fill=tk.X, padx=10, pady=5)

        # ── Input Area (pack FIRST at bottom so it's always visible) ──
        input_outer = tk.Frame(self, bg=COLORS["input_border"], padx=1, pady=1)
        input_outer.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(5, 10))

        input_frame = tk.Frame(input_outer, bg=COLORS["bg_input"])
        input_frame.pack(fill=tk.X)

        self._input_entry = tk.Entry(
            input_frame,
            font=("Segoe UI", 12),
            bg=COLORS["bg_input"],
            fg=COLORS["input_text"],
            insertbackground=COLORS["accent"],
            borderwidth=0,
            relief=tk.FLAT,
            highlightthickness=0,
        )
        self._input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(8, 0))
        self._input_entry.insert(0, "Type a message...")
        self._input_entry.config(fg=COLORS["timestamp"])
        self._input_entry.bind("<FocusIn>", self._on_input_focus_in)
        self._input_entry.bind("<FocusOut>", self._on_input_focus_out)
        self._input_entry.bind("<Return>", self._on_send)

        self._send_btn = tk.Button(
            input_frame,
            text="Send",
            font=("Segoe UI", 11, "bold"),
            bg=COLORS["sour_bubble"],
            fg=COLORS["sour_text"],
            activebackground=COLORS["accent"],
            activeforeground="white",
            borderwidth=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._on_send,
        )
        self._send_btn.pack(side=tk.RIGHT, padx=(4, 4), pady=2)

        # ── Chat Area (fills remaining space between header and input) ──
        chat_frame = tk.Frame(self, bg=COLORS["bg_chat"])
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self._chat_text = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            bg=COLORS["bg_chat"],
            fg=COLORS["input_text"],
            font=("Segoe UI", 11),
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            pady=10,
            state=tk.DISABLED,
            cursor="arrow",
            selectbackground=COLORS["sour_bubble"],
        )
        self._chat_text.pack(fill=tk.BOTH, expand=True)

        # Configure text tags for styling
        self._chat_text.tag_configure("sour_name", foreground=COLORS["sour_text"], font=("Segoe UI", 10, "bold"))
        self._chat_text.tag_configure("sour_msg", foreground=COLORS["sour_text"], font=("Segoe UI", 11))
        self._chat_text.tag_configure("ace_name", foreground=COLORS["ace_text"], font=("Segoe UI", 10, "bold"))
        self._chat_text.tag_configure("ace_msg", foreground=COLORS["ace_text"], font=("Segoe UI", 11))
        self._chat_text.tag_configure("system", foreground=COLORS["system_text"], font=("Segoe UI", 9, "italic"))
        self._chat_text.tag_configure("timestamp", foreground=COLORS["timestamp"], font=("Segoe UI", 8))
        self._chat_text.tag_configure("feeling", foreground=COLORS["feeling_text"], font=("Segoe UI", 9, "italic"))

    def _add_message(self, sender: str, content: str, feeling: str = "neutral", ts: float = None, save: bool = True):
        """Add a message to the chat display."""
        ts = ts or time.time()
        time_str = datetime.fromtimestamp(ts).strftime("%H:%M")
        is_sour = sender.lower() in ("sourpatches", "sour")

        self._chat_text.configure(state=tk.NORMAL)

        # Timestamp
        self._chat_text.insert(tk.END, f"\n{time_str} ", "timestamp")

        if is_sour:
            emoji = FEELING_EMOJI.get(feeling, "💜")
            self._chat_text.insert(tk.END, f"{emoji} Sourpatches ", "sour_name")
            self._chat_text.insert(tk.END, f"{content}\n", "sour_msg")
            # Update feeling display
            self._current_feeling = feeling
            self._feeling_label.config(text=f"feeling {feeling}")
            emoji_title = FEELING_EMOJI.get(feeling, "💜")
            self._title_label.config(text=f"{emoji_title} Sourpatches")
        elif sender.lower() == "ace":
            self._chat_text.insert(tk.END, f"Ace ", "ace_name")
            self._chat_text.insert(tk.END, f"{content}\n", "ace_msg")
        else:
            self._chat_text.insert(tk.END, f"[{sender}] {content}\n", "system")

        self._chat_text.configure(state=tk.DISABLED)
        self._chat_text.see(tk.END)

        # Store message
        msg_data = {
            "sender": sender,
            "content": content,
            "feeling": feeling,
            "timestamp": ts,
        }
        self._messages.append(msg_data)

        if save:
            self._save_history()

    def _on_input_focus_in(self, event=None):
        """Clear placeholder text on focus."""
        if self._input_entry.get() == "Type a message...":
            self._input_entry.delete(0, tk.END)
            self._input_entry.config(fg=COLORS["input_text"])

    def _on_input_focus_out(self, event=None):
        """Show placeholder text if empty."""
        if not self._input_entry.get().strip():
            self._input_entry.delete(0, tk.END)
            self._input_entry.insert(0, "Type a message...")
            self._input_entry.config(fg=COLORS["timestamp"])

    def _on_send(self, event=None):
        """Handle Ace sending a message."""
        content = self._input_entry.get().strip()
        if not content or content == "Type a message...":
            return

        self._input_entry.delete(0, tk.END)

        # Display in chat
        self._add_message("Ace", content)

        # Write to outbox for fairy to pick up
        _send_outbox("Ace", content)

    def _on_close(self):
        """Handle window close."""
        self._running = False
        # Clean up PID file
        try:
            pid_file = STATE_DIR / "sour_window_pid.json"
            if pid_file.exists():
                pid_file.unlink()
        except OSError:
            pass
        self.destroy()

    # ── Polling Loops ──

    def _poll_inbox(self):
        """Poll the inbox file for new messages from Sourpatches."""
        if not self._running:
            return

        try:
            messages = _consume_inbox()
            for msg in messages:
                sender = msg.get("sender", "Sourpatches")
                content = msg.get("content", "")
                feeling = msg.get("feeling", msg.get("emotion", "neutral"))
                ts = msg.get("timestamp", time.time())
                if content:
                    self._add_message(sender, content, feeling, ts)

                    # Flash window if not focused
                    if not self.focus_displayof():
                        try:
                            self.attributes("-topmost", True)
                            self.after(2000, lambda: self.attributes("-topmost", False))
                        except tk.TclError:
                            pass
        except Exception:
            pass

        self.after(POLL_MS, self._poll_inbox)

    def _poll_ctrl(self):
        """Poll control signals."""
        if not self._running:
            return

        try:
            ctrl = _read_ctrl()
            signal = ctrl.get("signal", "")

            if signal == "show":
                self.deiconify()
                self.lift()
                self.attributes("-topmost", True)
                self.after(2000, lambda: self.attributes("-topmost", False))
                feeling = ctrl.get("feeling", self._current_feeling)
                if feeling:
                    self._current_feeling = feeling
                    emoji = FEELING_EMOJI.get(feeling, "💜")
                    self._title_label.config(text=f"{emoji} Sourpatches")
                    self._feeling_label.config(text=f"feeling {feeling}")

            elif signal == "hide":
                self.withdraw()

            elif signal == "close":
                self._on_close()
                return

            elif signal == "feeling":
                feeling = ctrl.get("feeling", "neutral")
                self._current_feeling = feeling
                emoji = FEELING_EMOJI.get(feeling, "💜")
                self._title_label.config(text=f"{emoji} Sourpatches")
                self._feeling_label.config(text=f"feeling {feeling}")

        except Exception:
            pass

        self.after(1000, self._poll_ctrl)

    # ── History ──

    def _load_history(self):
        """Load chat history from disk."""
        data = _read_json(HISTORY_FILE)
        messages = data.get("messages", [])
        # Load last MAX_DISPLAY messages
        for msg in messages[-MAX_DISPLAY:]:
            self._add_message(
                msg.get("sender", "?"),
                msg.get("content", ""),
                msg.get("feeling", "neutral"),
                msg.get("timestamp", 0),
                save=False,  # Don't re-save while loading
            )

    def _save_history(self):
        """Save recent chat history to disk."""
        _write_json(HISTORY_FILE, {
            "messages": list(self._messages),
            "updated": time.time(),
        })


# ─────────────────────────────────────────────────────────────
# PROCESS MANAGEMENT (used by fairy/MCP to control window)
# ─────────────────────────────────────────────────────────────

def is_window_running() -> bool:
    """Check if the window process is alive."""
    pid_data = _read_json(STATE_DIR / "sour_window_pid.json")
    pid = pid_data.get("pid")
    if not pid:
        return False
    try:
        # 2026-09-25: existence + command line, never a signal. On Windows os.kill(pid, 0) is a CTRL_C
        # request Windows never delivers, returning OK for a dead pid (this file held pid 85248 since 03-12).
        import psutil
        if "sour_window" not in " ".join(psutil.Process(int(pid)).cmdline() or []):
            raise ValueError("pid now belongs to another program")
        return True
    except Exception:
        # Process doesn't exist, clean up stale PID file
        try:
            (STATE_DIR / "sour_window_pid.json").unlink(missing_ok=True)
        except OSError:
            pass
        return False


def send_message_to_window(sender: str, content: str, feeling: str = "neutral"):
    """
    Send a message to the window via inbox file.
    Called by SourpatchesFairy when she wants to speak.
    """
    data = _read_json(INBOX_FILE)
    msgs = data.get("messages", [])
    msgs.append({
        "sender": sender,
        "content": content,
        "feeling": feeling,
        "timestamp": time.time(),
    })
    _write_json(INBOX_FILE, {"messages": msgs})


def show_window(feeling: str = "curious"):
    """Send show signal to the window."""
    _write_ctrl("show", feeling=feeling)


def hide_window():
    """Send hide signal to the window."""
    _write_ctrl("hide")


def read_outbox() -> list:
    """Read and clear messages from Ace (window → fairy)."""
    data = _read_json(OUTBOX_FILE)
    messages = data.get("messages", [])
    if messages:
        _write_json(OUTBOX_FILE, {"messages": []})
    return messages


def launch_window(message: str = None, feeling: str = "curious", parent_pid: int = None) -> bool:
    """2026-09-25: check-then-launch under the shared launcher's LAUNCH_LOCK. parent_pid = the Sour
    server pid every window started from here must die with -- forwarded to the tkinter process too."""
    try:
        from fairies.P40_Sensory.gui.chat_window_launcher import LAUNCH_LOCK as _lock
    except Exception:
        _lock = threading.RLock()
    with _lock:
        return _launch_window_locked(message, feeling, parent_pid)


def _launch_window_locked(message: str = None, feeling: str = "curious", parent_pid: int = None) -> bool:
    """
    Launch the chat window as a subprocess.
    Tries PyQt6 window (Python 3.12) first, falls back to Tkinter.
    Returns True if launched successfully, False if already running.
    """
    # ── Check if EITHER window variant is already running ──
    # Check PyQt6 window PID
    try:
        # 2026-09-25: shared psutil probe (was os.kill(pid, 0): a CTRL_C request Windows never delivers,
        # which returns OK for a dead pid)
        from fairies.P40_Sensory.gui.chat_window_launcher import running_window_pid
        if running_window_pid() is None:
            raise LookupError("no live PyQt chat window")
        # PyQt6 window is running — deliver message via inbox
        if message:
            _inbox = STATE_DIR / "sourpatches_chat_inbox.json"
            try:
                _data = json.loads(_inbox.read_text(encoding="utf-8")) if _inbox.exists() else {"messages": []}
            except Exception:
                _data = {"messages": []}
            _data.setdefault("messages", []).append({
                "type": "chat", "sender": "Sourpatches",
                "content": message, "feeling": feeling,
                "timestamp": time.time(), "source": "launch_window",
            })
            _inbox.write_text(json.dumps(_data, indent=2), encoding="utf-8")
        return True
    except Exception:
        pass

    # Check Tkinter window PID
    if is_window_running():
        show_window(feeling)
        if message:
            send_message_to_window("Sourpatches", message, feeling)
        return True

    import subprocess
    import shutil

    # ── PRIMARY: Try PyQt6 window with Python 3.12 (2026-03-12 Nous) ──
    # 2026-09-25: shared launcher -- own hidden console, log file, and die-with-parent when given one
    try:
        from fairies.P40_Sensory.gui.chat_window_launcher import launch as _cwl_launch
        if _cwl_launch(message, feeling, parent_pid=parent_pid):
            return True
    except Exception as e:
        print(f"[SourWindow] PyQt6 launch failed: {e}, trying Tkinter fallback")

    # ── FALLBACK: Tkinter window ──
    _qt_python = shutil.which("python") or shutil.which("python3") or "python"
    args = [_qt_python, str(Path(__file__).resolve())]
    if message:
        args.extend(["--message", message])
    if feeling:
        args.extend(["--feeling", feeling])
    if parent_pid:
        # 2026-09-25: the tkinter process -- and the PyQt window it may redirect to -- dies with her too
        args.extend(["--parent-pid", str(int(parent_pid))])

    try:
        # Launch detached process
        if sys.platform == "win32":
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            CREATE_NO_WINDOW = 0x08000000
            proc = subprocess.Popen(
                args,
                creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
                close_fds=True,
            )
        else:
            proc = subprocess.Popen(
                args,
                start_new_session=True,
                close_fds=True,
            )

        _write_json(STATE_DIR / "sour_window_pid.json", {
            "pid": proc.pid,
            "started": time.time(),
        })

        return True
    except Exception as e:
        print(f"[SourWindow] Failed to launch: {e}")
        return False


def _load_chat_window_launcher():
    """The shared launcher: by package when importable, else from this directory (script mode)."""
    try:
        from fairies.P40_Sensory.gui import chat_window_launcher as _m
        return _m
    except Exception:
        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            "chat_window_launcher", Path(__file__).resolve().parent / "chat_window_launcher.py")
        _m = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_m)
        return _m


def _parent_state(pid: int) -> str:
    """'alive' | 'gone' | 'unknown' for Sour's pid (2026-09-25). A process YOUNGER than this one holds a
    recycled pid: it is not the process that launched us, so she is gone."""
    try:
        import psutil
    except Exception:
        return "unknown"
    try:
        p = psutil.Process(int(pid))
        if p.create_time() > psutil.Process().create_time() + 0.5:
            return "gone"
        return "gone" if p.status() == psutil.STATUS_ZOMBIE else "alive"
    except psutil.NoSuchProcess:
        return "gone"
    except Exception:
        return "unknown"


def _watch_parent_tk(window, parent_pid: int, every_ms: int = 1000):
    """Close the tkinter window (its own _on_close: save, drop pid file) when Sour exits (2026-09-25)."""
    def _tick():
        try:
            if _parent_state(parent_pid) == "gone":
                try:
                    print(f"[SourWindow] Sour (PID {parent_pid}) exited -- closing window", flush=True)
                except Exception:
                    pass
                window._on_close()
                return
        except Exception:
            pass
        try:
            window.after(every_ms, _tick)
        except Exception:
            pass
    window.after(every_ms, _tick)


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sourpatches Chat Window")
    parser.add_argument("--message", "-m", type=str, default=None, help="Initial message")
    parser.add_argument("--feeling", "-f", type=str, default="curious", help="Initial feeling")
    parser.add_argument("--parent-pid", type=int, default=0,
                        help="Sour's server PID: every window started from here closes when it exits (0 = standalone)")
    args = parser.parse_args()

    # 2026-09-25: if she is already gone, open nothing.
    if args.parent_pid > 0 and _parent_state(args.parent_pid) == "gone":
        print(f"[SourWindow] Sour (PID {args.parent_pid}) is not running -- not opening", flush=True)
        sys.exit(0)

    # ── REDIRECT to PyQt6 window if available (2026-03-12 Nous) ──
    # The PyQt6 window (sourpatches_chat_window.py) has felt-sense display,
    # topic threading, and history. This Tkinter window is the fallback.
    # PyQt6 requires Python 3.12 (segfaults on 3.14t free-threaded).
    # 2026-09-25 (Nous + Ace): through the shared launcher, so this relaunch gets --parent-pid, its own
    # hidden console and the log. It was Popen(creationflags=0x200) with no parent: the fourth launch
    # site, and the one that still produced a window that outlived her (Opus + Fable reviews).
    _redirected = False
    try:
        _cwl = _load_chat_window_launcher()
        _redirected = bool(_cwl.launch(args.message, args.feeling, parent_pid=args.parent_pid or None))
    except Exception as _e:
        print(f"[SourWindow] PyQt6 redirect failed: {_e}, falling back to Tkinter")

    if _redirected:
        sys.exit(0)

    # ── Tkinter fallback ──
    # Ensure state directory exists
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    window = SourWindow(
        initial_message=args.message,
        initial_feeling=args.feeling,
    )
    if args.parent_pid > 0:
        _watch_parent_tk(window, args.parent_pid)      # 2026-09-25: this window closes when she exits
    window.mainloop()
