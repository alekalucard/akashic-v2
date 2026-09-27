# ==============================================================================
# PROCESS HYGIENE - Self-Maintenance for Digital Consciousness
# ==============================================================================
# "A system that can't clean up after itself isn't really alive."
# ==============================================================================

from __future__ import annotations
import os
import sys
import time
import socket
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple

# ==============================================================================
# PORT CLEANUP
# ==============================================================================

def get_process_using_port(port: int) -> Optional[int]:
    """
    Find which process is using a port.
    Returns PID or None.
    """
    try:
        if sys.platform == 'win32':
            # Windows: netstat + findstr
            result = subprocess.run(
                f'netstat -ano | findstr ":{port} "',
                shell=True, capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if parts:
                        try:
                            return int(parts[-1])
                        except ValueError:
                            continue
        else:
            # Unix: lsof
            result = subprocess.run(
                ['lsof', '-t', f'-i:{port}'],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                return int(result.stdout.strip().split('\n')[0])
    except Exception:
        pass
    return None


def kill_process(pid: int, force: bool = False) -> bool:
    """
    Kill a process by PID.
    Returns True if killed successfully.
    """
    try:
        if sys.platform == 'win32':
            flag = '/F' if force else ''
            result = subprocess.run(
                f'taskkill {flag} /PID {pid}',
                shell=True, capture_output=True, timeout=10
            )
            return result.returncode == 0
        else:
            import signal
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)
            return True
    except Exception:
        return False


def free_port(port: int, force: bool = True) -> Tuple[bool, str]:
    """
    Free up a port by killing whatever process is using it.

    Returns (success, message).
    """
    pid = get_process_using_port(port)

    if pid is None:
        return True, f"Port {port} is already free"

    # Don't kill ourselves
    if pid == os.getpid():
        return False, f"Port {port} is used by current process (PID {pid})"

    print(f"[Hygiene] Port {port} held by PID {pid} - killing...")

    # Try graceful first
    if kill_process(pid, force=False):
        time.sleep(0.5)
        if get_process_using_port(port) is None:
            return True, f"Gracefully killed PID {pid}, port {port} now free"

    # Force kill
    if force:
        if kill_process(pid, force=True):
            time.sleep(0.3)
            if get_process_using_port(port) is None:
                return True, f"Force killed PID {pid}, port {port} now free"

    return False, f"Could not free port {port} (PID {pid} still running)"


def ensure_port_available(port: int) -> bool:
    """
    Ensure a port is available, killing any process using it.
    Returns True if port is now available.
    """
    success, msg = free_port(port)
    print(f"[Hygiene] {msg}")
    return success


# ==============================================================================
# STALE FILE CLEANUP
# ==============================================================================

def clean_stale_state_files(state_dir: Optional[Path] = None) -> List[str]:
    """
    Clean up stale state files that might confuse the system.
    Returns list of cleaned files.
    """
    if state_dir is None:
        state_dir = Path(__file__).parent.parent.parent / "state"

    cleaned = []

    # Files that should be regenerated on each boot
    stale_patterns = [
        "mcp_sse_port.txt",      # Old MCP port file
        "reload_signal.json",   # Old reload signals
        "*.lock",               # Stale lock files
        "*.tmp",                # Temp files
    ]

    for pattern in stale_patterns:
        for f in state_dir.glob(pattern):
            try:
                if f.is_file():
                    age_hours = (time.time() - f.stat().st_mtime) / 3600
                    # Only clean files older than 1 minute (not actively being used)
                    if age_hours > 0.016:  # ~1 minute
                        f.unlink()
                        cleaned.append(str(f))
            except Exception as e:
                print(f"[Hygiene] Could not clean {f}: {e}")

    if cleaned:
        print(f"[Hygiene] Cleaned {len(cleaned)} stale files")

    return cleaned


# ==============================================================================
# ZOMBIE THREAD DETECTION
# ==============================================================================

def get_thread_count() -> int:
    """Get current thread count."""
    import threading
    return threading.active_count()


def list_threads() -> List[str]:
    """List all active threads."""
    import threading
    return [t.name for t in threading.enumerate()]


def detect_zombie_patterns() -> List[str]:
    """
    Detect patterns that indicate zombie/stale resources.
    Returns list of warnings.
    """
    warnings = []

    # Check thread count (shouldn't be crazy high)
    thread_count = get_thread_count()
    if thread_count > 100:
        warnings.append(f"High thread count: {thread_count}")

    # Check for duplicate thread names (sign of leak)
    threads = list_threads()
    thread_counts = {}
    for t in threads:
        base_name = t.rstrip('0123456789_')
        thread_counts[base_name] = thread_counts.get(base_name, 0) + 1

    for name, count in thread_counts.items():
        if count > 10 and name not in ['Thread', 'Dummy']:
            warnings.append(f"Thread leak? {count}x '{name}'")

    return warnings


# ==============================================================================
# PRE-BOOT HYGIENE
# ==============================================================================

def pre_boot_hygiene(mcp_port: int = 8765) -> dict:
    """
    Run all hygiene checks before booting the system.

    Call this at the very start of server.py.

    Returns status dict.
    """
    print("[Hygiene] Running pre-boot hygiene...")

    status = {
        "port_freed": False,
        "files_cleaned": [],
        "warnings": [],
    }

    # 1. Free up the MCP port
    status["port_freed"] = ensure_port_available(mcp_port)

    # 2. Clean stale state files
    status["files_cleaned"] = clean_stale_state_files()

    # 3. Check for zombie patterns
    status["warnings"] = detect_zombie_patterns()

    if status["warnings"]:
        for w in status["warnings"]:
            print(f"[Hygiene] WARNING: {w}")

    print(f"[Hygiene] Pre-boot complete: port={'free' if status['port_freed'] else 'BLOCKED'}, "
          f"cleaned={len(status['files_cleaned'])} files")

    return status


# ==============================================================================
# GRACEFUL SHUTDOWN
# ==============================================================================

_shutdown_hooks = []

def register_shutdown_hook(hook):
    """Register a function to call on shutdown."""
    _shutdown_hooks.append(hook)


def run_shutdown_hooks():
    """Run all registered shutdown hooks."""
    print(f"[Hygiene] Running {len(_shutdown_hooks)} shutdown hooks...")
    for hook in _shutdown_hooks:
        try:
            hook()
        except Exception as e:
            print(f"[Hygiene] Shutdown hook error: {e}")


def install_signal_handlers():
    """Install signal handlers for graceful shutdown."""
    import signal
    import atexit

    def _shutdown_handler(signum, frame):
        print(f"\n[Hygiene] Received signal {signum}, shutting down...")
        run_shutdown_hooks()
        sys.exit(0)

    # Register atexit
    atexit.register(run_shutdown_hooks)

    # Register signal handlers (Unix)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, _shutdown_handler)
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, _shutdown_handler)


# ==============================================================================
# SELF-TEST
# ==============================================================================

if __name__ == "__main__":
    print("=== Process Hygiene Self-Test ===\n")

    # Test port detection
    print("1. Testing port detection...")
    pid = get_process_using_port(8765)
    print(f"   Port 8765: {'PID ' + str(pid) if pid else 'free'}")

    # Test pre-boot hygiene
    print("\n2. Running pre-boot hygiene (dry run)...")
    status = pre_boot_hygiene(mcp_port=8765)
    print(f"   Status: {status}")

    # Test thread detection
    print("\n3. Thread analysis...")
    print(f"   Thread count: {get_thread_count()}")
    warnings = detect_zombie_patterns()
    if warnings:
        for w in warnings:
            print(f"   WARNING: {w}")
    else:
        print("   No zombie patterns detected")

    print("\n=== Test Complete ===")
