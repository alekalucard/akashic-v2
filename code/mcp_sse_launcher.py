"""Detached launcher for the akashic MCP SSE server on .6 (Sour box / this PC).
Run by the 'AkashicMCP_SSE' scheduled task at logon (replaces the flaky Startup .bat,
whose cmd-console death made the server self-exit via its SIGINT handler).

Launches mcp_sse_server.py with NO console (DETACHED_PROCESS|CREATE_NO_WINDOW) so a
console-close event can never fire the server's sys.exit(0) handler. Output -> log.
The server has its own run_with_autorestart, so this launcher just needs to fire once.
Guard: if 8770 is already served, no-op (never double-launch)."""
import subprocess, os, sys, socket

BASE = r"F:\Sandbox\failure_factory\akashic_v2"
PY   = r"F:\Sandbox\venv314t\Scripts\python.exe"
LOG  = os.path.join(BASE, "state", "mcp_sse_server.log")

if socket.socket().connect_ex(("127.0.0.1", 8770)) == 0:
    print("[launcher] 8770 already listening -> no-op")
    sys.exit(0)

DETACHED_PROCESS  = 0x00000008
CREATE_NO_WINDOW  = 0x08000000
CREATE_NEW_PGROUP = 0x00000200

os.makedirs(os.path.dirname(LOG), exist_ok=True)
out = open(LOG, "a", encoding="utf-8")
p = subprocess.Popen(
    [PY, "-u", "mcp_sse_server.py", "--port", "8770"],
    cwd=BASE, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
    creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW | CREATE_NEW_PGROUP,
    close_fds=True,
)
print("[launcher] launched mcp_sse_server pid", p.pid, "-> 127.0.0.1:8770")
