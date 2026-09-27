"""
Boot server.py with real-time output capture.
Shows everything in terminal AND saves to state/boot_full.log.

FIX 2026-03-03: Added watchdog thread to detect server.py death.
Without this, if server.py segfaults but child processes (portals) keep
the stdout pipe open, readline() hangs forever with no error message.
The watchdog polls proc.poll() and closes the pipe after a grace period.

Run: python boot_capture.py
"""
import subprocess
import sys
import os
import time
import threading

LOG_FILE = os.path.join("state", "boot_full.log")
CRASH_LOG = os.path.join("state", "crash_traceback.log")


def _watchdog(proc, log):
    """Monitor server.py — detect death even when orphan children hold the pipe.

    On Windows, when server.py spawns multiprocessing children (portals),
    those children inherit the stdout pipe handle. If server.py segfaults,
    the children keep the pipe alive → readline() blocks forever.

    This thread polls proc.poll() every second. When server.py exits:
    1. Wait 3s for remaining buffered output to drain
    2. Log the exit code and crash details
    3. Close proc.stdout to break the readline loop
    """
    while proc.poll() is None:
        time.sleep(1.0)

    # ── server.py is dead ──
    code = proc.returncode
    time.sleep(3.0)  # Grace period for remaining output

    # Build diagnostic message
    lines = []
    lines.append("")
    lines.append("=" * 60)
    if code is not None and code < 0:
        lines.append(f"  [boot_capture] SERVER.PY CRASHED — signal {-code}")
        lines.append(f"  This is likely a segfault under Python 3.14t")
    elif code != 0:
        lines.append(f"  [boot_capture] SERVER.PY EXITED — code {code}")
    else:
        lines.append(f"  [boot_capture] SERVER.PY EXITED — code 0 (clean)")

    # Check for crash traceback
    crash_log = os.path.join("state", "crash_traceback.log")
    if os.path.exists(crash_log):
        try:
            with open(crash_log, "r") as f:
                crash_text = f.read().strip()
            if crash_text:
                lines.append("")
                lines.append("  CRASH TRACEBACK (from faulthandler):")
                for cl in crash_text.split("\n"):
                    lines.append(f"    {cl}")
        except Exception:
            pass

    lines.append("=" * 60)
    lines.append("")
    msg = "\n".join(lines)

    try:
        sys.stdout.buffer.write(msg.encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()
    except Exception:
        pass
    try:
        log.write(msg)
        log.flush()
    except Exception:
        pass

    # Break the readline loop by closing the pipe
    try:
        proc.stdout.close()
    except Exception:
        pass


def main():
    print("=" * 60)
    print("  AKASHIC V2 BOOT — with full output capture")
    print(f"  Log file: {LOG_FILE}")
    print("=" * 60)
    print()

    os.makedirs("state", exist_ok=True)

    # Clear previous crash log
    try:
        open(CRASH_LOG, "w").close()
    except Exception:
        pass

    with open(LOG_FILE, "w", encoding="utf-8", errors="replace") as log:
        # -u = unbuffered Python output
        # -Xgil=0 = FORCE GIL off even when non-GIL-safe C extensions load
        # FIX 2026-03-15 Nous: lxml.etree (pulled in by bs4 XML parser) forces
        # the GIL back on, which kills parallelism for all 90+ fairy threads.
        # -Xgil=0 keeps it off. Risk: lxml may crash — but scraping is non-critical
        # and 90-fairy parallelism IS critical.
        env = os.environ.copy()
        env["PYTHON_GIL"] = "0"

        # Use the free-threaded Python 3.14t from the venv.
        # sys.executable may be a standard Python if boot_capture.py is
        # launched from a different interpreter (e.g., Claude Code's Python).
        # -Xgil=0 ONLY works on the free-threaded build (python3.14t).
        # Try common locations for the free-threaded venv
        _sandbox = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        _py314t = os.path.join(_sandbox, "venv314t", "Scripts", "python.exe")
        if not os.path.exists(_py314t):
            _py314t = os.path.join(_sandbox, "venv314t", "Scripts", "python3.14t.exe")
        if not os.path.exists(_py314t):
            _py314t = sys.executable  # Fallback
            print(f"[boot_capture] WARNING: venv314t not found, using {_py314t}")

        # The venv314t python.exe IS the free-threaded build (3.14t).
        # Always use -Xgil=0 when launching from this venv.
        _gil_flags = ["-Xgil=0"] if "venv314t" in _py314t or "314t" in _py314t else []

        # Forward any extra args (e.g. --satellite --primary-ip 192.168.1.6) to
        # server.py. Normal boots pass none -> no change. (Nous+Ace 2026-06-15:
        # lets the .74 satellite node use this same wrapper instead of bypassing it.)
        proc = subprocess.Popen(
            [_py314t] + _gil_flags + ["-u", "server.py"] + sys.argv[1:],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            env=env,
        )

        # Start watchdog — detects server.py death and closes pipe
        wd = threading.Thread(target=_watchdog, args=(proc, log), daemon=True)
        wd.start()

        try:
            for raw_line in iter(proc.stdout.readline, b""):
                # Decode for display and logging
                line = raw_line.decode("utf-8", errors="replace")

                # Write to terminal (raw bytes for speed)
                sys.stdout.buffer.write(raw_line)
                sys.stdout.buffer.flush()

                # Write to log file
                log.write(line)
                log.flush()

        except (KeyboardInterrupt, OSError):
            # OSError: pipe closed by watchdog after server.py crash
            if proc.poll() is None:
                # Still running — user pressed Ctrl+C
                print("\n[boot_capture] Ctrl+C — shutting down...")
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()

        # Wait for watchdog to finish its diagnostics
        wd.join(timeout=5)

        code = proc.poll()
        if code is None:
            proc.wait(timeout=10)
            code = proc.returncode

        print(f"\n[boot_capture] Server exited with code {code}")
        print(f"[boot_capture] Full output saved to: {LOG_FILE}")
        if os.path.exists(CRASH_LOG):
            try:
                with open(CRASH_LOG, "r") as f:
                    if f.read().strip():
                        print(f"[boot_capture] Crash traceback: {CRASH_LOG}")
            except Exception:
                pass


if __name__ == "__main__":
    main()
