"""Thread diagnostic for server.py — runs OUTSIDE the server process.

Connects to the HTTP tool bridge (port 8766) and injects a thread
enumeration function through the start_memory_monitor tool which
runs a callback inside server.py's process.

Alternative: connects via the `cognitive_ask_oracle` tool path.

If those don't work, we fall back to sampling the thread count
from outside and looking at growth rate.
"""
import urllib.request
import json
import time
import ctypes
import ctypes.wintypes

SERVER_PID = None

def find_server_pid():
    """Find server.py PID from tasklist."""
    import subprocess
    out = subprocess.check_output(
        ['wmic', 'process', 'where', "name='python3.14t.exe'",
         'get', 'ProcessId,CommandLine', '/format:csv'],
        text=True
    )
    for line in out.splitlines():
        if 'server.py' in line and 'mcp' not in line.lower():
            parts = line.strip().split(',')
            for p in parts:
                if p.strip().isdigit() and int(p.strip()) > 100:
                    return int(p.strip())
    return None


def count_threads(pid):
    kernel32 = ctypes.windll.kernel32
    TH32CS_SNAPTHREAD = 0x4
    class TE(ctypes.Structure):
        _fields_ = [
            ('dwSize', ctypes.wintypes.DWORD),
            ('cntUsage', ctypes.wintypes.DWORD),
            ('th32ThreadID', ctypes.wintypes.DWORD),
            ('th32OwnerProcessID', ctypes.wintypes.DWORD),
            ('tpBasePri', ctypes.wintypes.LONG),
            ('tpDeltaPri', ctypes.wintypes.LONG),
            ('dwFlags', ctypes.wintypes.DWORD),
        ]
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    te = TE()
    te.dwSize = ctypes.sizeof(te)
    c = 0
    if kernel32.Thread32First(snap, ctypes.byref(te)):
        while True:
            if te.th32OwnerProcessID == pid:
                c += 1
            if not kernel32.Thread32Next(snap, ctypes.byref(te)):
                break
    kernel32.CloseHandle(snap)
    return c


def get_working_set(pid):
    """Get working set size in MB."""
    import subprocess
    out = subprocess.check_output(
        ['wmic', 'process', 'where', f'ProcessId={pid}',
         'get', 'WorkingSetSize', '/format:csv'],
        text=True
    )
    for line in out.splitlines():
        parts = line.strip().split(',')
        for p in parts:
            if p.strip().isdigit() and int(p.strip()) > 1000:
                return int(p.strip()) / (1024 * 1024)
    return 0


def monitor(pid, samples=12, interval=10):
    """Sample thread count and memory every interval seconds."""
    print(f"Monitoring PID {pid} ({samples} samples, {interval}s interval)")
    print(f"{'Time':>10} {'Threads':>10} {'RAM (MB)':>10} {'d_Threads':>10} {'d_RAM (MB)':>10}")
    print("-" * 55)

    prev_threads = 0
    prev_ram = 0.0

    for i in range(samples):
        t = count_threads(pid)
        ram = get_working_set(pid)
        dt = t - prev_threads if prev_threads else 0
        dr = ram - prev_ram if prev_ram else 0.0
        ts = time.strftime("%H:%M:%S")
        print(f"{ts:>10} {t:>10} {ram:>10.1f} {dt:>+10} {dr:>+10.1f}")
        prev_threads = t
        prev_ram = ram
        if i < samples - 1:
            time.sleep(interval)

    print(f"\nRate: ~{(count_threads(pid) - count_threads(pid)) or dt}/{interval}s threads, "
          f"~{dr:.1f}MB/{interval}s RAM")


if __name__ == "__main__":
    pid = find_server_pid()
    if not pid:
        print("Could not find server.py process!")
        exit(1)
    print(f"Found server.py at PID {pid}")
    monitor(pid, samples=6, interval=10)
