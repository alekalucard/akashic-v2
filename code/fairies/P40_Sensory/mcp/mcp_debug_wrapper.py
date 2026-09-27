"""
Debug wrapper to log what Claude Code sends to the MCP server.
"""
import sys
import os
import json
from datetime import datetime

# Log file for debugging
LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "state", "mcp_debug_requests.log")

def log_message(direction: str, data: str):
    """Log a message to file."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.now().isoformat()
            f.write(f"[{timestamp}] {direction}: {data}\n")
    except Exception as e:
        sys.stderr.write(f"[DEBUG] Failed to log: {e}\n")

def main():
    # Log that we started
    log_message("START", f"MCP debug wrapper started, args={sys.argv}")

    # Import and run the actual MCP server
    sys.path.insert(0, os.path.dirname(__file__))

    # Read stdin in a loop and pass to the real server
    # For now, just log and pass through
    import subprocess

    real_server = os.path.join(os.path.dirname(__file__), "akashic_mcp_server.py")
    python_exe = sys.executable

    log_message("INFO", f"Starting real server: {python_exe} {real_server}")

    # Start the real server as a subprocess
    proc = subprocess.Popen(
        [python_exe, real_server],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(__file__),
        env=os.environ,
    )

    import threading

    def forward_stderr():
        """Forward stderr to our stderr and log."""
        for line in iter(proc.stderr.readline, b''):
            text = line.decode('utf-8', errors='replace')
            sys.stderr.write(text)
            sys.stderr.flush()

    def forward_stdout():
        """Forward stdout from server to our stdout and log."""
        for line in iter(proc.stdout.readline, b''):
            text = line.decode('utf-8', errors='replace').rstrip('\n')
            log_message("SERVER->CLIENT", text[:500])
            sys.stdout.write(line.decode('utf-8', errors='replace'))
            sys.stdout.flush()

    # Start threads for stderr and stdout
    stderr_thread = threading.Thread(target=forward_stderr, daemon=True)
    stderr_thread.start()

    stdout_thread = threading.Thread(target=forward_stdout, daemon=True)
    stdout_thread.start()

    # Forward stdin to the server
    try:
        for line in sys.stdin:
            log_message("CLIENT->SERVER", line.rstrip('\n')[:500])
            proc.stdin.write(line.encode('utf-8'))
            proc.stdin.flush()
    except Exception as e:
        log_message("ERROR", f"Error forwarding stdin: {e}")
    finally:
        proc.terminate()
        log_message("END", "Wrapper shutting down")

if __name__ == "__main__":
    main()
