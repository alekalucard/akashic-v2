"""
Live Boot Monitor - Real-time 3-6-9 monitoring during server startup.
=====================================================================

Run this BEFORE starting the server to capture boot events in real-time.

Usage:
    # Terminal 1: Start monitor
    python tools/boot_monitor_live.py

    # Terminal 2: Start server
    python server.py

The monitor will:
1. Watch for boot events via file polling
2. Display real-time status with color coding
3. Alert on UGLY issues immediately
4. Generate final audit report
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict
import threading

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


class LiveBootMonitor:
    """Real-time boot monitoring with 3-6-9 categorization."""

    def __init__(self):
        self.boot_log_dir = PROJECT_ROOT / "boot_logs"
        self.state_dir = PROJECT_ROOT / "state"

        self.events: List[Dict] = []
        self.fairy_status: Dict[str, str] = {}
        self.plane_status: Dict[str, str] = {}
        self.worker_counts: Dict[str, int] = {}

        self.good_count = 0
        self.bad_count = 0
        self.ugly_count = 0

        self.start_time = time.time()
        self.running = True

    def log_good(self, msg: str):
        """Log a GOOD finding."""
        self.good_count += 1
        print(f"{GREEN}[GOOD]{RESET} {msg}")

    def log_bad(self, msg: str):
        """Log a BAD finding."""
        self.bad_count += 1
        print(f"{YELLOW}[BAD]{RESET}  {msg}")

    def log_ugly(self, msg: str):
        """Log an UGLY finding."""
        self.ugly_count += 1
        print(f"{RED}{BOLD}[UGLY]{RESET} {msg}")

    def log_info(self, msg: str):
        """Log info message."""
        print(f"{CYAN}[INFO]{RESET} {msg}")

    def process_event(self, event: Dict):
        """Process a single boot event."""
        evt_type = event.get("event", "")
        fairy = event.get("fairy", "unknown")
        ts = event.get("ts", time.time())

        if evt_type == "fairy_boot_start":
            self.fairy_status[fairy] = "booting"
            self.log_info(f"{fairy} starting boot...")

        elif evt_type == "fairy_boot_end":
            duration = event.get("duration_ms", 0)
            status = event.get("status", "unknown")

            if status == "success" or status == "registered":
                self.fairy_status[fairy] = "running"
                if duration < 2000:
                    self.log_good(f"{fairy} booted in {duration:.0f}ms")
                else:
                    self.log_bad(f"{fairy} slow boot: {duration:.0f}ms")
            elif status == "failed":
                self.fairy_status[fairy] = "failed"
                self.log_ugly(f"{fairy} FAILED to boot after {duration:.0f}ms")
            elif status == "timeout":
                self.fairy_status[fairy] = "timeout"
                self.log_ugly(f"{fairy} TIMEOUT after {duration:.0f}ms")

        elif evt_type == "plane_start":
            plane = event.get("plane", "unknown")
            self.plane_status[plane] = "booting"
            print(f"\n{BOLD}=== PLANE {plane} ==={RESET}")

        elif evt_type == "plane_complete":
            plane = event.get("plane", "unknown")
            duration = event.get("duration_ms", 0)
            fairy_count = event.get("fairy_count", 0)
            self.plane_status[plane] = "complete"

            if duration < 5000:
                self.log_good(f"Plane {plane}: {fairy_count} fairies in {duration:.0f}ms")
            else:
                self.log_bad(f"Plane {plane} slow: {fairy_count} fairies in {duration:.0f}ms")

        elif evt_type == "error":
            error = event.get("error", "unknown")[:80]
            self.log_ugly(f"{fairy} ERROR: {error}")

        elif evt_type == "warning":
            msg = event.get("message", "unknown")[:80]
            self.log_bad(f"{fairy} WARNING: {msg}")

        elif evt_type == "channel_subscribe":
            topic = event.get("topic", "unknown")
            # Don't log individual subscriptions, too noisy
            pass

        elif evt_type == "blocked_tunnel":
            self.log_ugly(f"{fairy} has BLOCKED tunnel!")

        elif evt_type == "thread_start":
            thread = event.get("thread_name", "unknown")
            # Track but don't log
            pass

        elif evt_type == "boot_complete":
            duration = event.get("duration_ms", 0)
            fairy_count = event.get("fairy_count", 0)
            print(f"\n{BOLD}{'='*50}{RESET}")
            print(f"{BOLD}BOOT COMPLETE{RESET}")
            print(f"Total time: {duration/1000:.2f}s")
            print(f"Fairies: {fairy_count}")
            print(f"{BOLD}{'='*50}{RESET}")

    def watch_boot_logs(self):
        """Watch boot logs directory for new events."""
        self.boot_log_dir.mkdir(parents=True, exist_ok=True)

        # Find or wait for boot log file
        current_file = None
        file_position = 0

        self.log_info("Waiting for boot to start...")
        self.log_info(f"Watching: {self.boot_log_dir}")

        while self.running:
            # Find latest jsonl file
            jsonl_files = sorted(self.boot_log_dir.glob("*_boot_observation.jsonl"), reverse=True)

            if jsonl_files:
                latest = jsonl_files[0]

                # New file?
                if current_file != latest:
                    current_file = latest
                    file_position = 0
                    self.log_info(f"Monitoring: {latest.name}")

                # Read new lines
                try:
                    with open(current_file, 'r') as f:
                        f.seek(file_position)
                        for line in f:
                            try:
                                event = json.loads(line.strip())
                                self.events.append(event)
                                self.process_event(event)
                            except json.JSONDecodeError:
                                continue
                        file_position = f.tell()
                except Exception as e:
                    pass

            time.sleep(0.1)  # Poll every 100ms

    def watch_worker_pool(self):
        """Watch worker pool status file."""
        worker_file = self.state_dir / "worker_pool_status.json"
        last_mtime = 0

        while self.running:
            if worker_file.exists():
                mtime = worker_file.stat().st_mtime
                if mtime > last_mtime:
                    last_mtime = mtime
                    try:
                        with open(worker_file, 'r') as f:
                            data = json.load(f)

                        io_pool = data.get("io_pool_size", 0)
                        compute_pool = data.get("compute_pool_size", 0)

                        if io_pool > 0:
                            self.log_info(f"Worker pools: IO={io_pool:,} Compute={compute_pool}")
                    except:
                        pass

            time.sleep(1)  # Poll every second

    def print_summary(self):
        """Print final summary."""
        elapsed = time.time() - self.start_time

        print(f"\n{BOLD}{'='*50}{RESET}")
        print(f"{BOLD}MONITOR SUMMARY{RESET}")
        print(f"{'='*50}")
        print(f"Monitor runtime: {elapsed:.1f}s")
        print(f"Events captured: {len(self.events)}")
        print()
        print(f"{GREEN}GOOD:  {self.good_count}{RESET}")
        print(f"{YELLOW}BAD:   {self.bad_count}{RESET}")
        print(f"{RED}UGLY:  {self.ugly_count}{RESET}")

        # Health score
        total = self.good_count + self.bad_count + self.ugly_count
        if total > 0:
            score = 100 + self.good_count - (self.bad_count * 3) - (self.ugly_count * 10)
            score = max(0, min(100, score))

            if score >= 90:
                color = GREEN
            elif score >= 70:
                color = YELLOW
            else:
                color = RED

            print(f"\n{BOLD}Health Score: {color}{score:.0f}/100{RESET}")

        # Fairy status summary
        running = sum(1 for s in self.fairy_status.values() if s == "running")
        failed = sum(1 for s in self.fairy_status.values() if s in ("failed", "timeout"))

        print(f"\nFairies: {running} running, {failed} failed")

        if failed > 0:
            print(f"\n{RED}Failed fairies:{RESET}")
            for fairy, status in self.fairy_status.items():
                if status in ("failed", "timeout"):
                    print(f"  - {fairy}: {status}")

    def run(self):
        """Run the live monitor."""
        print(f"{BOLD}{'='*50}{RESET}")
        print(f"{BOLD}LIVE BOOT MONITOR - 3 Good, 6 Bad, 9 Ugly{RESET}")
        print(f"{'='*50}")
        print("Press Ctrl+C to stop\n")

        # Start watchers in threads
        log_thread = threading.Thread(target=self.watch_boot_logs, daemon=True)
        worker_thread = threading.Thread(target=self.watch_worker_pool, daemon=True)

        log_thread.start()
        worker_thread.start()

        try:
            while self.running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Stopping monitor...{RESET}")
            self.running = False

        self.print_summary()


def main():
    monitor = LiveBootMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
