#!/usr/bin/env python3
"""
Live System Monitor - Watches for Ace to start the server and monitors for 10 minutes.

This is designed to catch the bugs that only appear when YOU run it vs when I test it.

Usage:
    1. Run this script: python tools/monitor_live_system.py
    2. Start the server in another terminal: python server.py
    3. Wait 10 minutes while it monitors
    4. Review the report

"The user sees bugs I never will - different environments, different thinking."
"""

import sys
import time
import json
import socket
import threading
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

# Monitoring state
@dataclass
class MonitorState:
    """Tracks all observations during monitoring."""
    start_time: float = 0.0
    server_detected_time: float = 0.0

    # Error tracking
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)

    # Fairy tracking
    fairy_boots: List[Dict[str, Any]] = field(default_factory=list)
    fairy_deaths: List[Dict[str, Any]] = field(default_factory=list)
    fairy_errors: List[Dict[str, Any]] = field(default_factory=list)

    # Activity tracking
    postal_messages: int = 0
    thought_count: int = 0
    goal_changes: int = 0
    collision_events: int = 0

    # Bridge/Cognition tracking
    bridge_attempts: int = 0
    bridge_successes: int = 0
    bridge_failures: int = 0
    ollama_calls: int = 0

    # Periodic snapshots
    snapshots: List[Dict[str, Any]] = field(default_factory=list)


def check_port(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False


def wait_for_server(ports: List[int] = [5757, 8765, 8080, 5000], timeout: int = 300) -> Optional[int]:
    """Wait for the server to start on one of the expected ports."""
    print("\n" + "=" * 70)
    print(" LIVE SYSTEM MONITOR")
    print(" Waiting for you to start the server...")
    print("=" * 70)
    print(f"\n  Watching ports: {ports}")
    print(f"  Timeout: {timeout}s")
    print("\n  Start your server now: python server.py")
    print("  (Press Ctrl+C to cancel)\n")

    start = time.time()
    last_dot = 0

    while time.time() - start < timeout:
        for port in ports:
            if check_port(port):
                print(f"\n\n  [✓] Server detected on port {port}!")
                return port

        # Progress indicator
        elapsed = int(time.time() - start)
        if elapsed > last_dot:
            print(".", end="", flush=True)
            last_dot = elapsed

        time.sleep(1)

    print(f"\n\n  [✗] Timeout after {timeout}s - no server detected")
    return None


def connect_to_fabric(port: int) -> Optional[Any]:
    """Try to connect to the system's tensor fabric."""
    try:
        # Try HTTP API first
        import urllib.request
        url = f"http://127.0.0.1:{port}/api/status"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            print(f"  [✓] Connected to system API - {data.get('fairies_running', '?')} fairies running")
            return {"type": "http", "port": port, "data": data}
    except Exception as e:
        print(f"  [!] HTTP API not available: {e}")

    # Try WebSocket
    try:
        # Check if ws port file exists
        ws_port_file = ROOT / "state" / "mcp_sse_port.txt"
        if ws_port_file.exists():
            ws_port = int(ws_port_file.read_text().strip())
            print(f"  [✓] Found WebSocket port: {ws_port}")
            return {"type": "ws", "port": ws_port}
    except:
        pass

    return {"type": "poll", "port": port}


def poll_system_state(connection: Dict, state: MonitorState) -> Dict[str, Any]:
    """Poll the system for current state."""
    snapshot = {
        "timestamp": time.time(),
        "elapsed": time.time() - state.start_time,
    }

    try:
        import urllib.request

        # Get main status (port 5757)
        try:
            url = f"http://127.0.0.1:{connection['port']}/status"
            with urllib.request.urlopen(url, timeout=5) as resp:
                status = json.loads(resp.read().decode())
                snapshot["status"] = status
                snapshot["connected"] = status.get("connected", False)
                snapshot["booted"] = status.get("booted", False)

                # Extract fairy info
                fairies = status.get("fairies", {})
                if isinstance(fairies, list):
                    snapshot["fairy_count"] = len(fairies)
                    snapshot["fairies"] = fairies
                elif isinstance(fairies, dict):
                    snapshot["fairy_count"] = fairies.get("total", fairies.get("running", 0))
                    snapshot["fairies"] = fairies
        except Exception as e:
            snapshot["status_error"] = str(e)

        # Get health check
        try:
            url = f"http://127.0.0.1:{connection['port']}/health"
            with urllib.request.urlopen(url, timeout=5) as resp:
                health = json.loads(resp.read().decode())
                snapshot["health"] = health
                snapshot["healthy"] = health.get("healthy", False)
                snapshot["uptime"] = health.get("uptime", 0)
        except Exception as e:
            snapshot["health_error"] = str(e)

        # Check boot log for recent errors
        try:
            boot_log = ROOT / "state" / "boot_live.log"
            if boot_log.exists():
                content = boot_log.read_text(errors='ignore')
                # Count errors and warnings in log
                error_count = content.lower().count("error")
                warning_count = content.lower().count("warning")
                exception_count = content.lower().count("exception")
                traceback_count = content.lower().count("traceback")

                snapshot["log_errors"] = error_count
                snapshot["log_warnings"] = warning_count
                snapshot["log_exceptions"] = exception_count + traceback_count

                # Check for specific issues
                if "Bridge error" in content:
                    state.bridge_failures += 1
                if "Bridged thinking..." in content:
                    state.bridge_attempts += 1
                if "Bridged:" in content:
                    state.bridge_successes += 1
        except:
            pass

    except Exception as e:
        snapshot["error"] = str(e)

    return snapshot


def check_log_files(state: MonitorState) -> None:
    """Check log files for errors."""
    log_patterns = [
        ROOT / "state" / "fairy_deaths.jsonl",
        ROOT / "fairies" / "boot_logs",
    ]

    # Check fairy deaths
    death_file = ROOT / "state" / "fairy_deaths.jsonl"
    if death_file.exists():
        try:
            with open(death_file) as f:
                for line in f:
                    try:
                        death = json.loads(line.strip())
                        ts = death.get("timestamp", 0)
                        if ts > state.start_time:
                            state.fairy_deaths.append(death)
                    except:
                        pass
        except:
            pass


def tail_log_for_errors(state: MonitorState, stop_event: threading.Event) -> None:
    """Background thread to watch boot log for errors."""
    boot_log = ROOT / "state" / "boot_live.log"
    last_size = 0
    error_patterns = [
        "Error:", "ERROR", "Exception:", "Traceback",
        "FAIL", "failed:", "ImportError", "AttributeError",
        "TypeError", "KeyError", "ValueError", "RuntimeError"
    ]
    warning_patterns = [
        "WARNING", "Warning:", "WARN"
    ]

    while not stop_event.is_set():
        try:
            if boot_log.exists():
                current_size = boot_log.stat().st_size
                if current_size > last_size:
                    with open(boot_log, 'r', errors='ignore') as f:
                        f.seek(last_size)
                        new_content = f.read()

                        for line in new_content.splitlines():
                            line_lower = line.lower()

                            # Check for errors
                            for pattern in error_patterns:
                                if pattern.lower() in line_lower:
                                    state.errors.append({
                                        "time": time.time(),
                                        "line": line[:200],
                                        "pattern": pattern
                                    })
                                    print(f"\n    [!]  {line[:100]}...")
                                    break

                            # Check for warnings
                            for pattern in warning_patterns:
                                if pattern.lower() in line_lower:
                                    state.warnings.append({
                                        "time": time.time(),
                                        "line": line[:200]
                                    })
                                    break

                    last_size = current_size
        except:
            pass

        stop_event.wait(1)  # Check every second


def monitor_loop(connection: Dict, state: MonitorState, duration_minutes: int = 10) -> None:
    """Main monitoring loop."""
    print("\n" + "=" * 70)
    print(f" MONITORING FOR {duration_minutes} MINUTES")
    print(" (Watching for errors in real-time...)")
    print("=" * 70)

    duration_sec = duration_minutes * 60
    interval_sec = 30  # Snapshot every 30 seconds

    # Start log watcher thread
    stop_event = threading.Event()
    log_thread = threading.Thread(target=tail_log_for_errors, args=(state, stop_event), daemon=True)
    log_thread.start()

    start = time.time()
    last_snapshot = 0
    last_progress = -1

    try:
        while time.time() - start < duration_sec:
            elapsed = time.time() - start
            progress = int((elapsed / duration_sec) * 100)

            # Progress update every 10%
            if progress // 10 > last_progress // 10:
                remaining = int((duration_sec - elapsed) / 60)
                err_count = len(state.errors)
                warn_count = len(state.warnings)
                status = f"Errors: {err_count} | Warnings: {warn_count}" if (err_count + warn_count) > 0 else "No issues"
                print(f"\n  [{progress:3d}%] {remaining} minutes remaining... ({status})")
                last_progress = progress

            # Periodic snapshot
            if elapsed - last_snapshot >= interval_sec:
                snapshot = poll_system_state(connection, state)
                state.snapshots.append(snapshot)
                last_snapshot = elapsed

                # Check for issues
                check_log_files(state)

                # Print activity summary
                parts = []
                if "fairy_count" in snapshot:
                    parts.append(f"Fairies: {snapshot['fairy_count']}")
                if "healthy" in snapshot:
                    parts.append(f"Healthy: {'✓' if snapshot['healthy'] else '✗'}")
                if "uptime" in snapshot:
                    parts.append(f"Uptime: {snapshot['uptime']:.0f}s")

                if parts:
                    print(f"    {' | '.join(parts)}")

            time.sleep(5)

    finally:
        stop_event.set()
        log_thread.join(timeout=2)

    print(f"\n  [✓] Monitoring complete!")


def generate_report(state: MonitorState) -> str:
    """Generate the final monitoring report."""
    report = []
    report.append("\n" + "=" * 70)
    report.append(" LIVE MONITORING REPORT")
    report.append("=" * 70)

    duration = time.time() - state.start_time
    report.append(f"\nDuration: {duration/60:.1f} minutes")
    report.append(f"Snapshots: {len(state.snapshots)}")

    # Fairy status
    report.append("\n--- FAIRY STATUS ---")
    if state.snapshots:
        last = state.snapshots[-1]
        if "fairy_count" in last:
            report.append(f"Final fairy count: {last['fairy_count']}")

    if state.fairy_deaths:
        report.append(f"\n[!]  FAIRY DEATHS: {len(state.fairy_deaths)}")
        for death in state.fairy_deaths[:5]:
            report.append(f"  - {death.get('fairy', 'Unknown')}: {death.get('reason', 'Unknown')}")
    else:
        report.append("✓ No fairy deaths detected")

    # Errors
    report.append("\n--- ERRORS ---")
    if state.errors:
        report.append(f"[!]  ERRORS: {len(state.errors)}")
        for err in state.errors[:10]:
            report.append(f"  - {err}")
    else:
        report.append("✓ No errors detected")

    # Warnings
    if state.warnings:
        report.append(f"\n--- WARNINGS ({len(state.warnings)}) ---")
        for warn in state.warnings[:10]:
            report.append(f"  - {warn}")

    # Activity summary
    report.append("\n--- ACTIVITY ---")
    if state.snapshots:
        first = state.snapshots[0]
        last = state.snapshots[-1]

        if "umf" in first and "umf" in last:
            first_thoughts = first["umf"].get("thought_count", 0)
            last_thoughts = last["umf"].get("thought_count", 0)
            report.append(f"Thoughts produced: {last_thoughts - first_thoughts}")

    report.append(f"Bridge attempts: {state.bridge_attempts}")
    report.append(f"Bridge successes: {state.bridge_successes}")
    report.append(f"Bridge failures: {state.bridge_failures}")

    # Recommendations
    report.append("\n--- RECOMMENDATIONS ---")
    if state.fairy_deaths:
        report.append("[!]  Investigate fairy deaths - check fairy_deaths.jsonl")
    if state.bridge_failures > state.bridge_successes:
        report.append("[!]  Bridge failure rate high - check HybridCognitionFairy wiring")
    if not state.snapshots or all("error" in s for s in state.snapshots):
        report.append("[!]  Could not connect to system API - check server endpoints")

    report.append("\n" + "=" * 70)

    return "\n".join(report)


def main():
    """Main entry point."""
    print("\n" + "=" * 70)
    print(" LIVE SYSTEM MONITOR - 33 Agent Audit System")
    print(" \"Watching for the bugs that only appear when YOU run it\"")
    print("=" * 70)

    # Initialize state
    state = MonitorState()
    state.start_time = time.time()

    # Wait for server to start (5757 is the default HTTP port)
    port = wait_for_server(ports=[5757, 8765, 8080, 5000], timeout=300)
    if not port:
        print("\nNo server detected. Please start the server and try again.")
        return 1

    state.server_detected_time = time.time()

    # Connect to system
    print("\n  Connecting to system...")
    connection = connect_to_fabric(port)

    # Initial snapshot
    print("  Taking initial snapshot...")
    initial = poll_system_state(connection, state)
    state.snapshots.append(initial)

    # Monitor for 10 minutes
    try:
        monitor_loop(connection, state, duration_minutes=10)
    except KeyboardInterrupt:
        print("\n\n  [!] Monitoring interrupted by user")

    # Generate report
    report = generate_report(state)
    print(report)

    # Save report
    report_path = ROOT / "state" / "live_monitor_report.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)
    print(f"\nReport saved to: {report_path}")

    # Also save raw data
    data_path = ROOT / "state" / "live_monitor_data.json"
    data = {
        "start_time": state.start_time,
        "end_time": time.time(),
        "snapshots": state.snapshots,
        "fairy_deaths": state.fairy_deaths,
        "errors": state.errors,
        "warnings": state.warnings,
    }
    with open(data_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Raw data saved to: {data_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
