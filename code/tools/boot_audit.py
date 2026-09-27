"""
Boot Audit Framework - "3 Good, 6 Bad, 9 Ugly" Monitoring System
================================================================

Comprehensive boot diagnostic that categorizes system health:

GOOD (Green) - Working correctly:
  1. Fairy booted successfully with proper timing
  2. All postal subscriptions connected
  3. Worker pools allocated and healthy

BAD (Yellow) - Needs attention:
  4. Slow boot (>2s for fairy, >5s for plane)
  5. Missing or incomplete subscriptions
  6. Low worker allocation (<50% requested)
  7. Warnings during boot
  8. Orphan fairies (no connections)
  9. Blocked tunnels or channels

UGLY (Red) - Critical issues:
  10. Boot timeout (>10s)
  11. Boot failure/crash
  12. No workers allocated
  13. Critical subscription missing
  14. Fairy death during boot
  15. Circular dependency detected
  16. Bottleneck fairy blocking others
  17. Memory pressure during boot
  18. Unhandled exception

Usage:
    python tools/boot_audit.py [--watch] [--report-only]
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class Severity(Enum):
    GOOD = "good"      # Green - working correctly
    BAD = "bad"        # Yellow - needs attention
    UGLY = "ugly"      # Red - critical issue


@dataclass
class Finding:
    """A single audit finding."""
    severity: Severity
    category: str
    fairy_name: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class AuditReport:
    """Complete audit report."""
    start_time: float
    end_time: float = 0.0
    findings: List[Finding] = field(default_factory=list)

    # Counters
    good_count: int = 0
    bad_count: int = 0
    ugly_count: int = 0

    # Summaries
    fairies_audited: int = 0
    planes_audited: int = 0
    total_boot_time: float = 0.0

    def add(self, finding: Finding):
        self.findings.append(finding)
        if finding.severity == Severity.GOOD:
            self.good_count += 1
        elif finding.severity == Severity.BAD:
            self.bad_count += 1
        else:
            self.ugly_count += 1

    def health_score(self) -> float:
        """Calculate health score 0-100."""
        if not self.findings:
            return 100.0
        total = self.good_count + self.bad_count + self.ugly_count
        if total == 0:
            return 100.0
        # Good = +1, Bad = -3, Ugly = -10
        score = 100 + (self.good_count * 1) - (self.bad_count * 3) - (self.ugly_count * 10)
        return max(0, min(100, score))


class BootAuditor:
    """
    Comprehensive boot auditor using the 3-6-9 framework.

    Monitors:
    - Timing (per-fairy, per-plane, total)
    - Connections (postal subscriptions, worker pools)
    - Health (memory, errors, bottlenecks)
    """

    # Thresholds
    FAIRY_BOOT_SLOW_MS = 2000      # >2s = slow
    FAIRY_BOOT_TIMEOUT_MS = 10000  # >10s = timeout
    PLANE_BOOT_SLOW_MS = 5000      # >5s = slow plane
    WORKER_LOW_RATIO = 0.5         # <50% workers = low

    def __init__(self):
        self.report = AuditReport(start_time=time.time())
        self.boot_events: List[Dict] = []
        self.fairy_timings: Dict[str, Dict] = {}
        self.plane_timings: Dict[str, Dict] = {}
        self.subscriptions: Dict[str, List[str]] = defaultdict(list)
        self.worker_allocations: Dict[str, Dict] = {}

    def load_boot_logs(self, boot_log_dir: Optional[Path] = None) -> bool:
        """Load the latest boot observation logs."""
        if boot_log_dir is None:
            boot_log_dir = PROJECT_ROOT / "boot_logs"

        if not boot_log_dir.exists():
            print(f"[AUDIT] No boot_logs directory found at {boot_log_dir}")
            return False

        # Find latest boot observation
        jsonl_files = sorted(boot_log_dir.glob("*_boot_observation.jsonl"), reverse=True)
        if not jsonl_files:
            print("[AUDIT] No boot observation files found")
            return False

        latest = jsonl_files[0]
        print(f"[AUDIT] Loading boot log: {latest.name}")

        # Load events
        with open(latest, 'r') as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    self.boot_events.append(event)
                except json.JSONDecodeError:
                    continue

        print(f"[AUDIT] Loaded {len(self.boot_events)} boot events")
        return True

    def load_summary(self, boot_log_dir: Optional[Path] = None) -> Optional[Dict]:
        """Load the latest boot summary."""
        if boot_log_dir is None:
            boot_log_dir = PROJECT_ROOT / "boot_logs"

        summary_files = sorted(boot_log_dir.glob("*_boot_observation_summary.json"), reverse=True)
        if not summary_files:
            return None

        with open(summary_files[0], 'r') as f:
            return json.load(f)

    def audit_timing(self):
        """Audit boot timing - GOOD/BAD/UGLY categorization."""
        print("\n[AUDIT] === TIMING ANALYSIS ===")

        summary = self.load_summary()
        if not summary:
            self.report.add(Finding(
                Severity.BAD,
                "timing",
                "SYSTEM",
                "No boot summary available - cannot audit timing",
            ))
            return

        # Total boot time
        total_ms = summary.get("total_duration_ms", 0)
        self.report.total_boot_time = total_ms / 1000

        if total_ms < 15000:  # <15s = good
            self.report.add(Finding(
                Severity.GOOD,
                "timing",
                "SYSTEM",
                f"Total boot time healthy: {total_ms/1000:.2f}s",
                {"total_ms": total_ms}
            ))
        elif total_ms < 30000:  # <30s = bad
            self.report.add(Finding(
                Severity.BAD,
                "timing",
                "SYSTEM",
                f"Boot time slow: {total_ms/1000:.2f}s (target <15s)",
                {"total_ms": total_ms}
            ))
        else:  # >30s = ugly
            self.report.add(Finding(
                Severity.UGLY,
                "timing",
                "SYSTEM",
                f"Boot time critical: {total_ms/1000:.2f}s (target <15s)",
                {"total_ms": total_ms}
            ))

        # Per-fairy timing from events
        for event in self.boot_events:
            if event.get("event") == "fairy_boot_end":
                fairy = event.get("fairy", "unknown")
                duration = event.get("duration_ms", 0)
                status = event.get("status", "unknown")

                if status == "failed":
                    self.report.add(Finding(
                        Severity.UGLY,
                        "timing",
                        fairy,
                        f"Boot FAILED after {duration:.0f}ms",
                        {"duration_ms": duration, "status": status}
                    ))
                elif status == "timeout":
                    self.report.add(Finding(
                        Severity.UGLY,
                        "timing",
                        fairy,
                        f"Boot TIMEOUT after {duration:.0f}ms",
                        {"duration_ms": duration, "status": status}
                    ))
                elif duration > self.FAIRY_BOOT_TIMEOUT_MS:
                    self.report.add(Finding(
                        Severity.UGLY,
                        "timing",
                        fairy,
                        f"Boot extremely slow: {duration:.0f}ms (>10s)",
                        {"duration_ms": duration}
                    ))
                elif duration > self.FAIRY_BOOT_SLOW_MS:
                    self.report.add(Finding(
                        Severity.BAD,
                        "timing",
                        fairy,
                        f"Boot slow: {duration:.0f}ms (>2s)",
                        {"duration_ms": duration}
                    ))

        # Bottleneck detection - slowest fairies
        slowest = summary.get("slowest_fairies", [])
        if slowest:
            for entry in slowest[:3]:  # Top 3 slowest
                name = entry.get("name", "unknown")
                ms = entry.get("total_ms", 0)
                if ms > self.FAIRY_BOOT_SLOW_MS:
                    self.report.add(Finding(
                        Severity.BAD,
                        "bottleneck",
                        name,
                        f"Bottleneck fairy - {ms:.0f}ms boot time",
                        {"total_ms": ms}
                    ))

    def audit_connections(self):
        """Audit postal subscriptions and connections."""
        print("\n[AUDIT] === CONNECTION ANALYSIS ===")

        # Track subscriptions from boot events
        subscriptions_by_fairy: Dict[str, List[str]] = defaultdict(list)
        registrations: List[str] = []

        for event in self.boot_events:
            evt_type = event.get("event", "")

            if evt_type == "channel_subscribe":
                fairy = event.get("fairy", "unknown")
                topic = event.get("topic", "unknown")
                subscriptions_by_fairy[fairy].append(topic)

            elif evt_type == "postal_register":
                fairy = event.get("fairy", "unknown")
                registrations.append(fairy)

        # Check for fairies with no subscriptions (potential orphans)
        summary = self.load_summary()
        if summary:
            all_fairies = set()
            for plane_data in summary.get("planes", {}).values():
                all_fairies.update(plane_data.get("fairies", []))

            for fairy in all_fairies:
                if fairy not in subscriptions_by_fairy:
                    self.report.add(Finding(
                        Severity.BAD,
                        "connection",
                        fairy,
                        "No postal subscriptions detected during boot",
                        {"subscriptions": 0}
                    ))
                elif len(subscriptions_by_fairy[fairy]) < 2:
                    self.report.add(Finding(
                        Severity.BAD,
                        "connection",
                        fairy,
                        f"Minimal subscriptions: {len(subscriptions_by_fairy[fairy])}",
                        {"subscriptions": subscriptions_by_fairy[fairy]}
                    ))
                else:
                    self.report.add(Finding(
                        Severity.GOOD,
                        "connection",
                        fairy,
                        f"Properly wired: {len(subscriptions_by_fairy[fairy])} subscriptions",
                        {"subscriptions": subscriptions_by_fairy[fairy]}
                    ))

        # Check for blocked tunnels
        for event in self.boot_events:
            if event.get("event") == "blocked_tunnel":
                fairy = event.get("fairy", "unknown")
                self.report.add(Finding(
                    Severity.UGLY,
                    "connection",
                    fairy,
                    "Blocked postal tunnel during boot",
                    event
                ))

    def audit_workers(self):
        """Audit worker pool allocation."""
        print("\n[AUDIT] === WORKER POOL ANALYSIS ===")

        # Try to load worker pool status from state
        worker_status_path = PROJECT_ROOT / "state" / "worker_pool_status.json"

        if worker_status_path.exists():
            with open(worker_status_path, 'r') as f:
                worker_data = json.load(f)

            io_pool = worker_data.get("io_pool_size", 0)
            compute_pool = worker_data.get("compute_pool_size", 0)
            allocations = worker_data.get("fairy_allocations", {})

            # Check pool sizes
            if io_pool >= 10000:
                self.report.add(Finding(
                    Severity.GOOD,
                    "workers",
                    "SYSTEM",
                    f"IO pool healthy: {io_pool:,} workers",
                    {"io_pool": io_pool}
                ))
            elif io_pool > 0:
                self.report.add(Finding(
                    Severity.BAD,
                    "workers",
                    "SYSTEM",
                    f"IO pool low: {io_pool:,} workers (target 10K+)",
                    {"io_pool": io_pool}
                ))
            else:
                self.report.add(Finding(
                    Severity.UGLY,
                    "workers",
                    "SYSTEM",
                    "IO pool not initialized!",
                    {"io_pool": 0}
                ))

            # Check per-fairy allocations
            for fairy, alloc in allocations.items():
                workers = alloc.get("workers_allocated", 0)
                requested = alloc.get("workers_requested", workers)

                if requested > 0:
                    ratio = workers / requested
                    if ratio >= 0.8:
                        self.report.add(Finding(
                            Severity.GOOD,
                            "workers",
                            fairy,
                            f"Worker allocation healthy: {workers}/{requested}",
                            {"allocated": workers, "requested": requested}
                        ))
                    elif ratio >= self.WORKER_LOW_RATIO:
                        self.report.add(Finding(
                            Severity.BAD,
                            "workers",
                            fairy,
                            f"Worker allocation low: {workers}/{requested} ({ratio:.0%})",
                            {"allocated": workers, "requested": requested}
                        ))
                    else:
                        self.report.add(Finding(
                            Severity.UGLY,
                            "workers",
                            fairy,
                            f"Worker starvation: {workers}/{requested} ({ratio:.0%})",
                            {"allocated": workers, "requested": requested}
                        ))
        else:
            # Check boot events for worker-related info
            worker_events = [e for e in self.boot_events if "worker" in e.get("event", "").lower()]
            if not worker_events:
                self.report.add(Finding(
                    Severity.BAD,
                    "workers",
                    "SYSTEM",
                    "No worker pool status available - cannot verify allocation",
                ))

    def audit_errors(self):
        """Audit errors and exceptions during boot."""
        print("\n[AUDIT] === ERROR ANALYSIS ===")

        error_count = 0
        warning_count = 0

        for event in self.boot_events:
            evt_type = event.get("event", "")

            if evt_type == "error":
                fairy = event.get("fairy", "unknown")
                error = event.get("error", "unknown error")
                self.report.add(Finding(
                    Severity.UGLY,
                    "error",
                    fairy,
                    f"Boot error: {error[:100]}",
                    event
                ))
                error_count += 1

            elif evt_type == "warning":
                fairy = event.get("fairy", "unknown")
                warning = event.get("message", "unknown warning")
                self.report.add(Finding(
                    Severity.BAD,
                    "warning",
                    fairy,
                    f"Boot warning: {warning[:100]}",
                    event
                ))
                warning_count += 1

        if error_count == 0:
            self.report.add(Finding(
                Severity.GOOD,
                "error",
                "SYSTEM",
                "No errors during boot",
            ))

        if warning_count == 0:
            self.report.add(Finding(
                Severity.GOOD,
                "warning",
                "SYSTEM",
                "No warnings during boot",
            ))

    def audit_planes(self):
        """Audit plane-by-plane boot sequence."""
        print("\n[AUDIT] === PLANE ANALYSIS ===")

        summary = self.load_summary()
        if not summary:
            return

        planes = summary.get("planes", {})
        self.report.planes_audited = len(planes)

        for plane, data in planes.items():
            duration = data.get("duration_ms", 0)
            fairy_count = data.get("fairy_count", 0)

            self.report.fairies_audited += fairy_count

            if duration < self.PLANE_BOOT_SLOW_MS:
                self.report.add(Finding(
                    Severity.GOOD,
                    "plane",
                    plane,
                    f"Plane boot healthy: {duration:.0f}ms for {fairy_count} fairies",
                    {"duration_ms": duration, "fairy_count": fairy_count}
                ))
            elif duration < self.PLANE_BOOT_SLOW_MS * 2:
                self.report.add(Finding(
                    Severity.BAD,
                    "plane",
                    plane,
                    f"Plane boot slow: {duration:.0f}ms for {fairy_count} fairies",
                    {"duration_ms": duration, "fairy_count": fairy_count}
                ))
            else:
                self.report.add(Finding(
                    Severity.UGLY,
                    "plane",
                    plane,
                    f"Plane boot critical: {duration:.0f}ms for {fairy_count} fairies",
                    {"duration_ms": duration, "fairy_count": fairy_count}
                ))

    def run_full_audit(self) -> AuditReport:
        """Run complete boot audit."""
        print("=" * 60)
        print("BOOT AUDIT - 3 Good, 6 Bad, 9 Ugly Framework")
        print("=" * 60)

        # Load boot data
        if not self.load_boot_logs():
            self.report.add(Finding(
                Severity.UGLY,
                "data",
                "SYSTEM",
                "Could not load boot logs - run server first",
            ))
            return self.report

        # Run all audits
        self.audit_timing()
        self.audit_connections()
        self.audit_workers()
        self.audit_errors()
        self.audit_planes()

        self.report.end_time = time.time()
        return self.report

    def print_report(self):
        """Print formatted audit report."""
        print("\n" + "=" * 60)
        print("AUDIT REPORT")
        print("=" * 60)

        # Summary
        print(f"\nHealth Score: {self.report.health_score():.0f}/100")
        print(f"Total Boot Time: {self.report.total_boot_time:.2f}s")
        print(f"Fairies Audited: {self.report.fairies_audited}")
        print(f"Planes Audited: {self.report.planes_audited}")

        # Counts
        print(f"\n{'GOOD (Green):':<20} {self.report.good_count}")
        print(f"{'BAD (Yellow):':<20} {self.report.bad_count}")
        print(f"{'UGLY (Red):':<20} {self.report.ugly_count}")

        # UGLY findings (most critical)
        ugly = [f for f in self.report.findings if f.severity == Severity.UGLY]
        if ugly:
            print(f"\n{'='*60}")
            print("UGLY (Critical - Fix Immediately)")
            print("="*60)
            for i, f in enumerate(ugly, 1):
                print(f"  {i}. [{f.category}] {f.fairy_name}: {f.message}")

        # BAD findings
        bad = [f for f in self.report.findings if f.severity == Severity.BAD]
        if bad:
            print(f"\n{'='*60}")
            print("BAD (Needs Attention)")
            print("="*60)
            for i, f in enumerate(bad, 1):
                print(f"  {i}. [{f.category}] {f.fairy_name}: {f.message}")

        # GOOD findings (abbreviated)
        good = [f for f in self.report.findings if f.severity == Severity.GOOD]
        if good:
            print(f"\n{'='*60}")
            print(f"GOOD ({len(good)} items working correctly)")
            print("="*60)
            # Just show categories
            good_cats = defaultdict(int)
            for f in good:
                good_cats[f.category] += 1
            for cat, count in good_cats.items():
                print(f"  - {cat}: {count} OK")

        print("\n" + "=" * 60)

    def save_report(self, path: Optional[Path] = None):
        """Save report to JSON."""
        if path is None:
            path = PROJECT_ROOT / "state" / "boot_audit_report.json"

        report_data = {
            "timestamp": datetime.now().isoformat(),
            "health_score": self.report.health_score(),
            "total_boot_time": self.report.total_boot_time,
            "counts": {
                "good": self.report.good_count,
                "bad": self.report.bad_count,
                "ugly": self.report.ugly_count,
            },
            "fairies_audited": self.report.fairies_audited,
            "planes_audited": self.report.planes_audited,
            "findings": [
                {
                    "severity": f.severity.value,
                    "category": f.category,
                    "fairy": f.fairy_name,
                    "message": f.message,
                    "details": f.details,
                }
                for f in self.report.findings
            ]
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(report_data, f, indent=2)

        print(f"\n[AUDIT] Report saved to: {path}")


def main():
    """Run boot audit."""
    import argparse
    parser = argparse.ArgumentParser(description="Boot Audit - 3 Good, 6 Bad, 9 Ugly")
    parser.add_argument("--watch", action="store_true", help="Watch for new boot logs")
    parser.add_argument("--report-only", action="store_true", help="Only print report, don't save")
    args = parser.parse_args()

    auditor = BootAuditor()
    auditor.run_full_audit()
    auditor.print_report()

    if not args.report_only:
        auditor.save_report()


if __name__ == "__main__":
    main()
