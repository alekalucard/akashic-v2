"""
Memory Watchdog — Monitors Akashic system memory and kills zombies.

Runs as a lightweight background daemon. Logs memory snapshots to
state/memory_watchdog.jsonl for trend analysis.

Features:
- Periodic RSS sampling of all Akashic-related processes
- Automatic zombie MCP server cleanup (stale instances > 2h)
- Alerts when total RSS exceeds threshold
- JSONL log for time-series analysis

Usage:
    python infrastructure/memory_watchdog.py              # Run foreground
    python infrastructure/memory_watchdog.py --daemon     # Run background
    python infrastructure/memory_watchdog.py --once       # Single snapshot
    python infrastructure/memory_watchdog.py --cleanup    # Kill zombies only
    python infrastructure/memory_watchdog.py --report     # Show recent trends

Author: Nous + Ace (2026-02-16)
"""

import psutil
import time
import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ── Infrastructure Tracer ────────────────────────────────────────────────
def _get_tracer():
    """Lazy import — safe to call even when infra_tracer not yet available."""
    try:
        from infrastructure.infra_tracer import get_infra_tracer
        t = get_infra_tracer()
        t.register_actor("memory_watchdog", role="daemon",
                         description="Monitors RAM, kills zombie processes")
        return t
    except Exception:
        return None

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
STATE_DIR = PROJECT_ROOT / "state"
LOG_FILE = STATE_DIR / "memory_watchdog.jsonl"
PID_FILE = STATE_DIR / "memory_watchdog.pid"

# Thresholds
ZOMBIE_AGE_HOURS = 2.0          # Kill MCP servers older than this
ZOMBIE_RSS_MB = 50              # Only kill if RSS > this (avoid killing fresh ones)
ALERT_TOTAL_RSS_GB = 8.0        # Alert when total Akashic RSS exceeds this
SAMPLE_INTERVAL_SECONDS = 30    # How often to sample
MAX_LOG_LINES = 10000           # Rotate log after this many entries


def classify_process(cmdline: str, name: str) -> Optional[str]:
    """Classify a process by its role in the Akashic system."""
    cmd_lower = cmdline.lower()

    if 'akashic_mcp_server' in cmd_lower or 'mcp_server' in cmd_lower:
        return 'mcp_server'
    if 'server.py' in cmdline and 'mcp' not in cmd_lower:
        return 'main_server'
    if 'portal_interior' in cmd_lower:
        return 'portal'
    if 'v3_boot' in cmd_lower or 'v2_boot' in cmd_lower:
        return 'boot'
    if 'app.exe' in cmd_lower and 'akashic' in cmd_lower:
        return 'dashboard'
    if 'msedgewebview2' in cmd_lower and 'akashic' in cmd_lower:
        return 'dashboard_webview'
    if 'server_stdout.log' in cmdline:
        return 'log_tailer'
    if 'rwkv' in cmd_lower or 'inference' in cmd_lower:
        return 'inference'

    # Generic akashic python process
    if ('akashic' in cmd_lower or 'failure_factory' in cmd_lower) and 'python' in name.lower():
        return 'akashic_python'

    return None


def snapshot() -> Dict:
    """Take a memory snapshot of all Akashic processes."""
    processes = []
    total_rss = 0
    total_vms = 0

    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info',
                                       'create_time', 'num_threads']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            role = classify_process(cmdline, proc.info['name'] or '')
            if role is None:
                continue

            mi = proc.info['memory_info']
            rss_mb = mi.rss / (1024 * 1024)
            vms_mb = mi.vms / (1024 * 1024)
            age_h = (time.time() - proc.info['create_time']) / 3600

            total_rss += rss_mb
            total_vms += vms_mb

            processes.append({
                'pid': proc.info['pid'],
                'role': role,
                'rss_mb': round(rss_mb, 1),
                'vms_mb': round(vms_mb, 0),
                'threads': proc.info['num_threads'],
                'age_hours': round(age_h, 2),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # System memory
    vm = psutil.virtual_memory()

    return {
        'timestamp': time.time(),
        'iso_time': datetime.now().isoformat(timespec='seconds'),
        'total_rss_mb': round(total_rss, 1),
        'total_vms_mb': round(total_vms, 0),
        'system_ram_used_pct': vm.percent,
        'system_ram_available_gb': round(vm.available / (1024**3), 2),
        'process_count': len(processes),
        'processes': processes,
    }


def find_zombies(snap: Dict) -> List[Dict]:
    """Find zombie processes that should be killed."""
    zombies = []
    for p in snap['processes']:
        # Zombie MCP servers: old + fat
        if p['role'] == 'mcp_server' and p['age_hours'] > ZOMBIE_AGE_HOURS and p['rss_mb'] > ZOMBIE_RSS_MB:
            zombies.append({**p, 'reason': f"Stale MCP server ({p['rss_mb']:.0f}MB, {p['age_hours']:.1f}h)"})

        # Ancient log tailers
        if p['role'] == 'log_tailer' and p['age_hours'] > 24:
            zombies.append({**p, 'reason': f"Ancient log tailer ({p['age_hours']:.0f}h)"})

    return zombies


def kill_zombies(zombies: List[Dict]) -> List[Dict]:
    """Kill zombie processes. Returns list of killed processes."""
    killed = []
    tracer = _get_tracer()
    for z in zombies:
        try:
            proc = psutil.Process(z['pid'])
            proc.kill()
            killed.append(z)
            # ── Emit trace for every process kill ──
            if tracer:
                tracer.process_killed(
                    "memory_watchdog", z['pid'], z.get('reason', 'zombie'),
                    freed_mb=z.get('rss_mb', 0), role=z.get('role', 'unknown'),
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            z['kill_error'] = str(e)
    return killed


def log_snapshot(snap: Dict, zombies_killed: List[Dict] = None):
    """Append snapshot to JSONL log file."""
    STATE_DIR.mkdir(exist_ok=True)

    entry = {
        'ts': snap['timestamp'],
        't': snap['iso_time'],
        'rss_mb': snap['total_rss_mb'],
        'sys_pct': snap['system_ram_used_pct'],
        'procs': snap['process_count'],
        # Per-role summary
        'by_role': {},
    }

    for p in snap['processes']:
        role = p['role']
        if role not in entry['by_role']:
            entry['by_role'][role] = {'count': 0, 'rss_mb': 0}
        entry['by_role'][role]['count'] += 1
        entry['by_role'][role]['rss_mb'] += p['rss_mb']

    # Round role RSS
    for role_data in entry['by_role'].values():
        role_data['rss_mb'] = round(role_data['rss_mb'], 1)

    if zombies_killed:
        entry['zombies_killed'] = len(zombies_killed)
        entry['freed_mb'] = round(sum(z['rss_mb'] for z in zombies_killed), 1)

    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry) + '\n')

    # Rotate if too large
    _rotate_log_if_needed()


def _rotate_log_if_needed():
    """Keep log file at reasonable size."""
    if not LOG_FILE.exists():
        return
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if len(lines) > MAX_LOG_LINES:
            # Keep last half
            keep = lines[len(lines) // 2:]
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.writelines(keep)
    except Exception:
        pass


def print_snapshot(snap: Dict):
    """Pretty-print a snapshot."""
    print(f"\n{'='*60}")
    print(f"  Memory Watchdog Snapshot — {snap['iso_time']}")
    print(f"{'='*60}")
    print(f"  Total Akashic RSS:  {snap['total_rss_mb']:,.0f} MB")
    print(f"  System RAM:         {snap['system_ram_used_pct']}% used, "
          f"{snap['system_ram_available_gb']:.1f} GB available")
    print(f"  Akashic processes:  {snap['process_count']}")
    print()

    # Group by role
    by_role = {}
    for p in snap['processes']:
        role = p['role']
        if role not in by_role:
            by_role[role] = []
        by_role[role].append(p)

    for role in sorted(by_role.keys()):
        procs = by_role[role]
        total_rss = sum(p['rss_mb'] for p in procs)
        print(f"  [{role}] {len(procs)} process(es), {total_rss:.0f} MB total")
        for p in sorted(procs, key=lambda x: -x['rss_mb']):
            flag = " !! ZOMBIE" if (p['role'] == 'mcp_server' and
                                     p['age_hours'] > ZOMBIE_AGE_HOURS and
                                     p['rss_mb'] > ZOMBIE_RSS_MB) else ""
            print(f"    PID {p['pid']:6d}: {p['rss_mb']:7.1f} MB | "
                  f"{p['threads']:3d} threads | {p['age_hours']:.1f}h{flag}")

    print()


def report(n: int = 20):
    """Show recent trend from log file."""
    if not LOG_FILE.exists():
        print("No watchdog log found. Run --once first.")
        return

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    if not lines:
        print("Log file is empty.")
        return

    entries = []
    for line in lines[-n:]:
        try:
            entries.append(json.loads(line.strip()))
        except json.JSONDecodeError:
            continue

    print(f"\n{'='*60}")
    print(f"  Memory Trend (last {len(entries)} samples)")
    print(f"{'='*60}")
    print(f"  {'Time':>19s}  {'RSS MB':>8s}  {'Sys%':>5s}  {'Procs':>5s}  {'Zombies':>7s}")
    print(f"  {'-'*19}  {'-'*8}  {'-'*5}  {'-'*5}  {'-'*7}")

    for e in entries:
        zombies = e.get('zombies_killed', '-')
        print(f"  {e.get('t', '?'):>19s}  {e['rss_mb']:>8.0f}  {e['sys_pct']:>5.1f}  {e['procs']:>5d}  {zombies:>7s}")

    # Growth analysis
    if len(entries) >= 2:
        first = entries[0]
        last = entries[-1]
        dt_h = (last['ts'] - first['ts']) / 3600
        d_rss = last['rss_mb'] - first['rss_mb']
        if dt_h > 0:
            rate = d_rss / dt_h
            print(f"\n  Growth rate: {rate:+.1f} MB/hour over {dt_h:.1f} hours")
            if rate > 50:
                print(f"  !! WARNING: Significant memory growth detected!")
            elif rate > 0:
                print(f"  Moderate growth — monitor over longer period")
            else:
                print(f"  Stable or shrinking — healthy")

    print()


def run_daemon(auto_kill: bool = True, interval: int = SAMPLE_INTERVAL_SECONDS):
    """Run as continuous monitoring daemon."""
    print(f"[MemoryWatchdog] Starting daemon (interval={interval}s)")
    print(f"[MemoryWatchdog] Log: {LOG_FILE}")
    print(f"[MemoryWatchdog] Auto-kill zombies: {auto_kill}")

    # Write PID file
    STATE_DIR.mkdir(exist_ok=True)
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

    try:
        while True:
            try:
                snap = snapshot()

                zombies = find_zombies(snap)
                killed = []
                if auto_kill and zombies:
                    killed = kill_zombies(zombies)
                    if killed:
                        freed = sum(z['rss_mb'] for z in killed)
                        print(f"[MemoryWatchdog] Killed {len(killed)} zombies, freed {freed:.0f} MB")

                log_snapshot(snap, killed)

                # Alert on high memory
                if snap['total_rss_mb'] > ALERT_TOTAL_RSS_GB * 1024:
                    print(f"[MemoryWatchdog] ALERT: Total RSS {snap['total_rss_mb']:.0f} MB "
                          f"exceeds {ALERT_TOTAL_RSS_GB} GB threshold!")
                    _t = _get_tracer()
                    if _t:
                        _t.health_alert(
                            "memory_watchdog", "total_rss_mb",
                            snap['total_rss_mb'], ALERT_TOTAL_RSS_GB * 1024,
                            severity="error",
                        )

            except Exception as e:
                print(f"[MemoryWatchdog] Error: {e}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n[MemoryWatchdog] Stopped")
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description='Akashic Memory Watchdog')
    parser.add_argument('--daemon', action='store_true', help='Run as background daemon')
    parser.add_argument('--once', action='store_true', help='Take single snapshot and exit')
    parser.add_argument('--cleanup', action='store_true', help='Kill zombies only')
    parser.add_argument('--report', action='store_true', help='Show recent trends')
    parser.add_argument('--no-kill', action='store_true', help='Disable auto-kill in daemon mode')
    parser.add_argument('--interval', type=int, default=SAMPLE_INTERVAL_SECONDS, help='Sample interval (seconds)')
    args = parser.parse_args()

    if args.interval != SAMPLE_INTERVAL_SECONDS:
        # Override module-level constant via run_daemon parameter
        pass

    if args.report:
        report()
    elif args.cleanup:
        snap = snapshot()
        zombies = find_zombies(snap)
        if zombies:
            print(f"Found {len(zombies)} zombies:")
            for z in zombies:
                print(f"  PID {z['pid']}: {z['reason']}")
            killed = kill_zombies(zombies)
            freed = sum(z['rss_mb'] for z in killed)
            print(f"Killed {len(killed)}, freed {freed:.0f} MB")
        else:
            print("No zombies found.")
    elif args.once:
        snap = snapshot()
        print_snapshot(snap)
        log_snapshot(snap)
    elif args.daemon:
        run_daemon(auto_kill=not args.no_kill, interval=args.interval)
    else:
        # Default: snapshot + cleanup
        snap = snapshot()
        print_snapshot(snap)

        zombies = find_zombies(snap)
        if zombies:
            print(f"Found {len(zombies)} zombie(s):")
            for z in zombies:
                print(f"  PID {z['pid']}: {z['reason']}")
            killed = kill_zombies(zombies)
            freed = sum(z['rss_mb'] for z in killed)
            print(f"Killed {len(killed)}, freed {freed:.0f} MB")

        log_snapshot(snap, killed if zombies else None)


if __name__ == '__main__':
    main()
