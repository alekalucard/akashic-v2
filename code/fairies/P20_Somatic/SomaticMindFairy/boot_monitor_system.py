"""
Boot Monitor System - UMF spawns 33 agents to monitor system health.

When the UMF boots, it checks for boot_monitoring_directive.json.
If active, it spawns 33 monitoring agents that track postal traffic
for 10 minutes, then compile a report to Claude_Office.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import json
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict

ROOT = Path(__file__).parent.parent


@dataclass
class MonitorAgent:
    """A single monitoring agent tracking a postal topic."""
    id: int
    name: str
    watch_topic: str
    track_key: str

    # Tracking state
    events: List[Dict[str, Any]] = field(default_factory=list)
    count: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0
    errors: List[str] = field(default_factory=list)

    def record(self, event: Dict[str, Any]) -> None:
        """Record an event."""
        now = time.time()
        if self.count == 0:
            self.first_seen = now
        self.last_seen = now
        self.count += 1

        # Keep last 100 events
        if len(self.events) < 100:
            self.events.append({
                "time": now,
                "data": str(event)[:200]  # Truncate large events
            })

    def record_error(self, error: str) -> None:
        """Record an error."""
        self.errors.append(f"{time.time()}: {error}")

    def summary(self) -> Dict[str, Any]:
        """Get agent summary."""
        return {
            "id": self.id,
            "name": self.name,
            "topic": self.watch_topic,
            "count": self.count,
            "errors": len(self.errors),
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
        }


class BootMonitorSystem:
    """
    Spawns and manages 33 monitoring agents for UMF.

    Called by UMF on boot if directive is active.
    Runs for specified duration, then generates report.
    """

    def __init__(self, fabric=None):
        self.fabric = fabric
        self.agents: Dict[int, MonitorAgent] = {}
        self.active = False
        self.start_time = 0.0
        self.duration_minutes = 10
        self.report_location = "Claude_Office/boot_monitoring_report.md"
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def load_directive(self) -> bool:
        """Load the monitoring directive if it exists and is active."""
        directive_path = ROOT / "state" / "boot_monitoring_directive.json"

        if not directive_path.exists():
            return False

        try:
            with open(directive_path) as f:
                directive = json.load(f)

            if not directive.get("active", False):
                return False

            self.duration_minutes = directive.get("duration_minutes", 10)
            self.report_location = directive.get("report_location", self.report_location)

            # Create agents from directive
            for monitor in directive.get("monitors", []):
                agent = MonitorAgent(
                    id=monitor["id"],
                    name=monitor["name"],
                    watch_topic=monitor["watch"],
                    track_key=monitor["track"],
                )
                self.agents[agent.id] = agent

            print(f"[BootMonitor] Loaded directive: {len(self.agents)} agents, {self.duration_minutes} minutes")
            return True

        except Exception as e:
            print(f"[BootMonitor] Failed to load directive: {e}")
            return False

    def start(self) -> bool:
        """Start the monitoring system."""
        if not self.agents:
            if not self.load_directive():
                return False

        if not self.fabric:
            print("[BootMonitor] No fabric - cannot subscribe to topics")
            return False

        self.active = True
        self.start_time = time.time()

        # Subscribe each agent to its topic
        for agent in self.agents.values():
            self._subscribe_agent(agent)

        # Start timer thread to generate report after duration
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="BootMonitor"
        )
        self._monitor_thread.start()

        print(f"[BootMonitor] Started {len(self.agents)} agents, will report in {self.duration_minutes} minutes")
        return True

    def _subscribe_agent(self, agent: MonitorAgent) -> None:
        """Subscribe an agent to its watch topic."""
        topic = agent.watch_topic

        def handler(message):
            try:
                if hasattr(message, 'payload'):
                    data = message.payload
                elif isinstance(message, dict):
                    data = message
                else:
                    data = {"raw": str(message)[:100]}

                agent.record(data)

                # Check for errors in the event
                data_str = str(data).lower()
                if any(err in data_str for err in ["error", "exception", "fail", "traceback"]):
                    agent.record_error(str(data)[:200])

            except Exception as e:
                agent.record_error(f"Handler error: {e}")

        try:
            # Handle wildcard topics
            if topic == "*":
                # Can't subscribe to all - skip or use a different approach
                pass
            elif "*" in topic:
                # Pattern subscription - fabric may not support this
                # Subscribe to the base topic
                base = topic.replace("*", "").rstrip(".")
                if base:
                    self.fabric.subscribe(base, handler, f"BootMonitor-{agent.id}")
            else:
                self.fabric.subscribe(topic, handler, f"BootMonitor-{agent.id}")

        except Exception as e:
            print(f"[BootMonitor] Failed to subscribe agent {agent.name} to {topic}: {e}")

    def _monitor_loop(self) -> None:
        """Background thread that waits for duration then generates report."""
        duration_sec = self.duration_minutes * 60

        # Wait for duration or stop signal
        self._stop_event.wait(timeout=duration_sec)

        if self.active:
            self.generate_report()
            self.active = False

    def stop(self) -> None:
        """Stop monitoring and generate report."""
        self._stop_event.set()
        self.active = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)

    def generate_report(self) -> str:
        """Generate the monitoring report."""
        duration = time.time() - self.start_time

        report = []
        report.append("# Boot Monitoring Report")
        report.append(f"\n**Generated:** {datetime.now().isoformat()}")
        report.append(f"**Duration:** {duration/60:.1f} minutes")
        report.append(f"**Agents:** {len(self.agents)}")

        # Summary stats
        total_events = sum(a.count for a in self.agents.values())
        total_errors = sum(len(a.errors) for a in self.agents.values())

        report.append(f"\n## Summary")
        report.append(f"- **Total Events:** {total_events}")
        report.append(f"- **Total Errors:** {total_errors}")

        # The Good - what's working
        report.append(f"\n## The Good")
        active_agents = [a for a in self.agents.values() if a.count > 0]
        if active_agents:
            report.append(f"- {len(active_agents)}/{len(self.agents)} agents saw activity")
            top_5 = sorted(active_agents, key=lambda a: a.count, reverse=True)[:5]
            for a in top_5:
                report.append(f"  - **{a.name}**: {a.count} events")
        else:
            report.append("- No activity detected (is the system running?)")

        # The Bad - errors found
        report.append(f"\n## The Bad")
        agents_with_errors = [a for a in self.agents.values() if a.errors]
        if agents_with_errors:
            report.append(f"- {len(agents_with_errors)} agents detected errors")
            for a in agents_with_errors:
                report.append(f"\n### {a.name} ({len(a.errors)} errors)")
                for err in a.errors[:5]:  # First 5 errors
                    report.append(f"- {err[:150]}")
        else:
            report.append("- No errors detected!")

        # The Ugly - silent agents (expected activity but got none)
        report.append(f"\n## The Ugly")
        critical_topics = ["fairy.booted", "heartbeat", "consciousness.collision", "cognition.think"]
        silent_critical = [
            a for a in self.agents.values()
            if a.count == 0 and any(t in a.watch_topic for t in critical_topics)
        ]
        if silent_critical:
            report.append("- **Silent critical monitors** (expected activity, got none):")
            for a in silent_critical:
                report.append(f"  - {a.name} ({a.watch_topic})")
        else:
            report.append("- All critical systems showing activity")

        # Agent details
        report.append(f"\n## Agent Details")
        report.append("| ID | Agent | Topic | Events | Errors |")
        report.append("|---|---|---|---|---|")
        for a in sorted(self.agents.values(), key=lambda x: x.id):
            status = "✓" if a.count > 0 else "✗"
            report.append(f"| {a.id} | {a.name} | {a.watch_topic} | {a.count} | {len(a.errors)} |")

        report_text = "\n".join(report)

        # Save report
        report_path = ROOT / self.report_location
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text)

        print(f"[BootMonitor] Report saved to {report_path}")

        # Also deactivate the directive so it doesn't run again
        directive_path = ROOT / "state" / "boot_monitoring_directive.json"
        try:
            with open(directive_path) as f:
                directive = json.load(f)
            directive["active"] = False
            directive["last_run"] = datetime.now().isoformat()
            with open(directive_path, "w") as f:
                json.dump(directive, f, indent=2)
        except:
            pass

        return report_text

    def status(self) -> Dict[str, Any]:
        """Get current monitoring status."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        remaining = max(0, (self.duration_minutes * 60) - elapsed)

        return {
            "active": self.active,
            "agents": len(self.agents),
            "elapsed_minutes": elapsed / 60,
            "remaining_minutes": remaining / 60,
            "total_events": sum(a.count for a in self.agents.values()),
            "total_errors": sum(len(a.errors) for a in self.agents.values()),
        }


# Singleton
_boot_monitor: Optional[BootMonitorSystem] = None


def get_boot_monitor() -> BootMonitorSystem:
    """Get or create the boot monitor singleton."""
    global _boot_monitor
    if _boot_monitor is None:
        _boot_monitor = BootMonitorSystem()
    return _boot_monitor


def start_boot_monitoring(fabric) -> bool:
    """Start boot monitoring if directive is active."""
    monitor = get_boot_monitor()
    monitor.fabric = fabric
    return monitor.start()
