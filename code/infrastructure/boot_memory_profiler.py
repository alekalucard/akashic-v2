"""
Boot Memory Profiler — Watches system memory during Akashic boot.

START THIS BEFORE BOOTING. It monitors the main server process at high
frequency and correlates memory spikes with boot log events.

Usage:
    1. Open terminal: python infrastructure/boot_memory_profiler.py
    2. Boot the system in another terminal: python server.py
    3. Let it run through boot (it auto-stops after 10 min idle or Ctrl+C)
    4. Read the report: state/boot_memory_profile.json

What it captures every 2 seconds:
    - Server process RSS, VMS, thread count
    - System-wide RAM usage
    - All Akashic child process memory
    - Boot log tail (last new lines since previous sample)
    - Delta analysis (which sample had biggest RSS jump)

Author: Nous + Ace (2026-02-16)
"""

import psutil
import time
import json
import os
import sys
import threading
from pathlib import Path
from datetime import datetime

# ── Infrastructure Tracer (best-effort — may not be available standalone) ──
def _get_tracer():
    try:
        # Add project root to path so infra_tracer can be found
        _root = str(Path(__file__).parent.parent)
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from infrastructure.infra_tracer import get_infra_tracer
        t = get_infra_tracer()
        t.register_actor("boot_memory_profiler", role="monitor",
                         description="Watches system memory during boot, correlates spikes")
        return t
    except Exception:
        return None
from typing import Dict, List, Optional

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
STATE_DIR = PROJECT_ROOT / "state"
PROFILE_FILE = STATE_DIR / "boot_memory_profile.json"
BOOT_LOG = STATE_DIR / "boot_live.log"
SAMPLE_INTERVAL = 2.0  # seconds — fast enough to catch spikes


def find_server_pid() -> Optional[int]:
    """Find the main Akashic server.py process."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if 'server.py' in cmdline and 'mcp' not in cmdline.lower() and 'memory' not in cmdline.lower() and 'boot_memory' not in cmdline.lower():
                return proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def get_all_akashic_processes() -> List[Dict]:
    """Get memory info for all Akashic-related processes."""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info', 'num_threads']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            cmd_lower = cmdline.lower()

            # Classify
            role = None
            if 'server.py' in cmdline and 'mcp' not in cmd_lower and 'memory' not in cmd_lower and 'boot_memory' not in cmd_lower:
                role = 'server'
            elif 'akashic_mcp_server' in cmd_lower or 'mcp_server' in cmd_lower:
                role = 'mcp'
            elif 'portal_interior' in cmd_lower:
                role = 'portal'
            elif 'app.exe' in cmd_lower and 'akashic' in cmd_lower:
                role = 'dashboard'
            elif 'msedgewebview2' in cmd_lower and 'akashic' in cmd_lower:
                role = 'webview'
            elif ('akashic' in cmd_lower or 'failure_factory' in cmd_lower) and 'python' in (proc.info['name'] or '').lower():
                role = 'other_python'

            if role is None:
                continue

            mi = proc.info['memory_info']
            processes.append({
                'pid': proc.info['pid'],
                'role': role,
                'rss_mb': round(mi.rss / (1024 * 1024), 1),
                'vms_mb': round(mi.vms / (1024 * 1024), 0),
                'threads': proc.info['num_threads'],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return processes


def read_boot_log_tail(last_pos: int) -> tuple:
    """Read new lines from boot log since last position.
    Returns (new_lines_text, new_position).
    """
    if not BOOT_LOG.exists():
        return "", last_pos
    try:
        with open(BOOT_LOG, 'r', encoding='utf-8', errors='replace') as f:
            f.seek(last_pos)
            new_text = f.read()
            new_pos = f.tell()
        return new_text, new_pos
    except Exception:
        return "", last_pos


def take_sample(server_pid: Optional[int], boot_log_pos: int) -> tuple:
    """Take a single profiling sample. Returns (sample_dict, new_log_pos)."""
    now = time.time()
    vm = psutil.virtual_memory()

    sample = {
        'ts': now,
        'elapsed_s': 0,  # filled in later
        'system_ram_pct': vm.percent,
        'system_ram_avail_gb': round(vm.available / (1024**3), 2),
    }

    # Server process details
    if server_pid:
        try:
            proc = psutil.Process(server_pid)
            mi = proc.memory_info()
            sample['server_rss_mb'] = round(mi.rss / (1024 * 1024), 1)
            sample['server_vms_mb'] = round(mi.vms / (1024 * 1024), 0)
            sample['server_threads'] = proc.num_threads()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            sample['server_rss_mb'] = 0
            sample['server_threads'] = 0
    else:
        sample['server_rss_mb'] = 0
        sample['server_threads'] = 0

    # All Akashic processes
    all_procs = get_all_akashic_processes()
    sample['total_akashic_rss_mb'] = round(sum(p['rss_mb'] for p in all_procs), 1)
    sample['total_akashic_threads'] = sum(p['threads'] for p in all_procs)
    sample['process_count'] = len(all_procs)

    # Per-role breakdown
    by_role = {}
    for p in all_procs:
        r = p['role']
        if r not in by_role:
            by_role[r] = {'count': 0, 'rss_mb': 0, 'threads': 0}
        by_role[r]['count'] += 1
        by_role[r]['rss_mb'] += p['rss_mb']
        by_role[r]['threads'] += p['threads']
    for rd in by_role.values():
        rd['rss_mb'] = round(rd['rss_mb'], 1)
    sample['by_role'] = by_role

    # Boot log context
    new_log, new_pos = read_boot_log_tail(boot_log_pos)
    if new_log.strip():
        # Extract key boot events from new log lines
        events = []
        for line in new_log.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            # Look for fairy boot events, phase markers, errors
            if any(kw in line for kw in ['Phase', 'BOOT', 'fairy', 'Fairy', 'ERROR', 'WARN',
                                          'consciousness', 'portal', 'Portal', 'Thread',
                                          'memory', 'Memory', 'started', 'complete',
                                          'Online', 'ONLINE', 'beat', 'Beat',
                                          'wiring', 'cascade', 'wave']):
                # Truncate long lines
                if len(line) > 200:
                    line = line[:200] + '...'
                events.append(line)
        sample['boot_events'] = events[-10:]  # Keep last 10 relevant events per sample
    else:
        sample['boot_events'] = []

    return sample, new_pos


def print_sample(sample: Dict, prev_rss: float):
    """Print a live sample line."""
    delta = sample['server_rss_mb'] - prev_rss
    delta_str = f"+{delta:.0f}" if delta >= 0 else f"{delta:.0f}"

    # Color-code the delta
    flag = ""
    if delta > 100:
        flag = " !! SPIKE"
    elif delta > 50:
        flag = " ! JUMP"

    elapsed = sample['elapsed_s']
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)

    print(f"  {mins:02d}:{secs:02d}  | "
          f"Server: {sample['server_rss_mb']:>7.0f} MB ({delta_str:>5s}) | "
          f"Threads: {sample['server_threads']:>4d} | "
          f"Total: {sample['total_akashic_rss_mb']:>7.0f} MB | "
          f"Sys: {sample['system_ram_pct']:>5.1f}%{flag}")

    # Print notable boot events
    for evt in sample.get('boot_events', [])[-3:]:
        print(f"         | LOG: {evt[:100]}")


def analyze_profile(samples: List[Dict]) -> Dict:
    """Analyze the collected profile for spikes and patterns."""
    if not samples:
        return {"error": "No samples collected"}

    analysis = {
        'total_samples': len(samples),
        'duration_s': samples[-1]['elapsed_s'] if samples else 0,
        'peak_server_rss_mb': max(s['server_rss_mb'] for s in samples),
        'peak_total_rss_mb': max(s['total_akashic_rss_mb'] for s in samples),
        'peak_threads': max(s['server_threads'] for s in samples),
        'peak_system_ram_pct': max(s['system_ram_pct'] for s in samples),
        'final_server_rss_mb': samples[-1]['server_rss_mb'],
        'final_total_rss_mb': samples[-1]['total_akashic_rss_mb'],
    }

    # Find top 5 biggest RSS jumps
    spikes = []
    for i in range(1, len(samples)):
        delta = samples[i]['server_rss_mb'] - samples[i-1]['server_rss_mb']
        if delta > 10:  # Only care about jumps > 10 MB
            spikes.append({
                'sample_index': i,
                'elapsed_s': round(samples[i]['elapsed_s'], 1),
                'delta_mb': round(delta, 1),
                'rss_before': samples[i-1]['server_rss_mb'],
                'rss_after': samples[i]['server_rss_mb'],
                'threads_before': samples[i-1]['server_threads'],
                'threads_after': samples[i]['server_threads'],
                'boot_events': samples[i].get('boot_events', []),
            })

    spikes.sort(key=lambda s: -s['delta_mb'])
    analysis['top_spikes'] = spikes[:10]

    # Find top 5 biggest thread jumps
    thread_spikes = []
    for i in range(1, len(samples)):
        delta = samples[i]['server_threads'] - samples[i-1]['server_threads']
        if delta > 10:
            thread_spikes.append({
                'sample_index': i,
                'elapsed_s': round(samples[i]['elapsed_s'], 1),
                'delta_threads': delta,
                'threads_before': samples[i-1]['server_threads'],
                'threads_after': samples[i]['server_threads'],
                'rss_delta_mb': round(samples[i]['server_rss_mb'] - samples[i-1]['server_rss_mb'], 1),
                'boot_events': samples[i].get('boot_events', []),
            })

    thread_spikes.sort(key=lambda s: -s['delta_threads'])
    analysis['top_thread_spikes'] = thread_spikes[:10]

    # Memory growth phases
    # Split into 30-second windows and compute growth rate
    phases = []
    window = 30  # seconds
    i = 0
    while i < len(samples):
        window_start = samples[i]['elapsed_s']
        window_end = window_start + window
        window_samples = [s for s in samples if window_start <= s['elapsed_s'] < window_end]
        if len(window_samples) >= 2:
            rss_start = window_samples[0]['server_rss_mb']
            rss_end = window_samples[-1]['server_rss_mb']
            delta = rss_end - rss_start
            phases.append({
                'window_start_s': round(window_start, 0),
                'window_end_s': round(window_samples[-1]['elapsed_s'], 0),
                'rss_start_mb': rss_start,
                'rss_end_mb': rss_end,
                'delta_mb': round(delta, 1),
                'growth_rate_mb_per_min': round(delta / (window / 60), 1),
            })
        # Advance past this window
        while i < len(samples) and samples[i]['elapsed_s'] < window_end:
            i += 1

    phases.sort(key=lambda p: -abs(p['delta_mb']))
    analysis['growth_phases'] = phases[:10]

    return analysis


def print_report(analysis: Dict):
    """Print the final analysis report."""
    print(f"\n{'='*70}")
    print(f"  BOOT MEMORY PROFILE REPORT")
    print(f"{'='*70}")
    print(f"  Duration:          {analysis['duration_s']:.0f}s ({analysis['duration_s']/60:.1f} min)")
    print(f"  Samples:           {analysis['total_samples']}")
    print(f"  Peak server RSS:   {analysis['peak_server_rss_mb']:.0f} MB")
    print(f"  Peak total RSS:    {analysis['peak_total_rss_mb']:.0f} MB")
    print(f"  Peak threads:      {analysis['peak_threads']}")
    print(f"  Peak system RAM:   {analysis['peak_system_ram_pct']:.1f}%")
    print(f"  Final server RSS:  {analysis['final_server_rss_mb']:.0f} MB")
    print(f"  Final total RSS:   {analysis['final_total_rss_mb']:.0f} MB")

    print(f"\n  TOP MEMORY SPIKES (biggest RSS jumps):")
    print(f"  {'Time':>8s}  {'Delta':>8s}  {'Before':>8s}  {'After':>8s}  {'Threads':>10s}  Boot Events")
    print(f"  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*10}  {'-'*30}")
    for s in analysis.get('top_spikes', [])[:5]:
        mins = int(s['elapsed_s'] // 60)
        secs = int(s['elapsed_s'] % 60)
        t_delta = s['threads_after'] - s['threads_before']
        t_str = f"{s['threads_before']}->{s['threads_after']}" if t_delta else f"{s['threads_after']}"
        events = '; '.join(s.get('boot_events', [])[:2])[:60]
        print(f"  {mins:02d}:{secs:02d}    {s['delta_mb']:>+7.0f}  {s['rss_before']:>7.0f}  {s['rss_after']:>7.0f}  {t_str:>10s}  {events}")

    print(f"\n  TOP THREAD SPIKES:")
    print(f"  {'Time':>8s}  {'Delta':>8s}  {'Before':>8s}  {'After':>8s}  {'RSS +':>8s}  Boot Events")
    print(f"  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*30}")
    for s in analysis.get('top_thread_spikes', [])[:5]:
        mins = int(s['elapsed_s'] // 60)
        secs = int(s['elapsed_s'] % 60)
        events = '; '.join(s.get('boot_events', [])[:2])[:60]
        print(f"  {mins:02d}:{secs:02d}    {s['delta_threads']:>+7d}  {s['threads_before']:>7d}  {s['threads_after']:>7d}  {s['rss_delta_mb']:>+7.0f}  {events}")

    print(f"\n  GROWTH PHASES (30s windows, sorted by |delta|):")
    print(f"  {'Window':>12s}  {'Start MB':>9s}  {'End MB':>8s}  {'Delta':>8s}  {'Rate MB/min':>12s}")
    print(f"  {'-'*12}  {'-'*9}  {'-'*8}  {'-'*8}  {'-'*12}")
    for p in analysis.get('growth_phases', [])[:5]:
        s1 = int(p['window_start_s'])
        s2 = int(p['window_end_s'])
        m1, sec1 = divmod(s1, 60)
        m2, sec2 = divmod(s2, 60)
        print(f"  {m1:02d}:{sec1:02d}-{m2:02d}:{sec2:02d}  {p['rss_start_mb']:>8.0f}  {p['rss_end_mb']:>7.0f}  {p['delta_mb']:>+7.0f}  {p['growth_rate_mb_per_min']:>+11.0f}")

    print()


def main():
    print(f"\n{'='*70}")
    print(f"  AKASHIC BOOT MEMORY PROFILER")
    print(f"  Sampling every {SAMPLE_INTERVAL}s — start the server now")
    print(f"  Press Ctrl+C to stop and generate report")
    print(f"{'='*70}")
    print(f"  {'Time':>6s}  | {'Server RSS':>14s}{'Delta':>8s} | "
          f"{'Threads':>8s} | {'Total Akashic':>14s} | {'System':>7s}")
    print(f"  {'-'*6}  | {'-'*14}{'-'*8} | {'-'*8} | {'-'*14} | {'-'*7}")

    STATE_DIR.mkdir(exist_ok=True)

    # ── Trace lifecycle ──
    _t = _get_tracer()
    if _t:
        _t.lifecycle("boot_memory_profiler", "started", {"interval_s": SAMPLE_INTERVAL})

    samples = []
    start_time = time.time()
    boot_log_pos = 0
    prev_server_rss = 0
    server_pid = None
    idle_count = 0
    max_idle = 300  # Stop after 5 min of no server process

    # Check if boot log exists and get current size (skip pre-existing content)
    if BOOT_LOG.exists():
        boot_log_pos = BOOT_LOG.stat().st_size

    try:
        while True:
            # Try to find server if not yet found
            if server_pid is None:
                server_pid = find_server_pid()
                if server_pid:
                    print(f"\n  >> Server detected! PID={server_pid}")
                    idle_count = 0
                    # Reset boot log position to catch boot output
                    if BOOT_LOG.exists():
                        # Go back a bit to catch early boot messages
                        size = BOOT_LOG.stat().st_size
                        boot_log_pos = max(0, size - 4096)
            else:
                # Verify server is still running
                try:
                    psutil.Process(server_pid)
                except psutil.NoSuchProcess:
                    print(f"\n  >> Server process {server_pid} exited!")
                    server_pid = None

            # Take sample
            sample, boot_log_pos = take_sample(server_pid, boot_log_pos)
            sample['elapsed_s'] = round(time.time() - start_time, 1)
            samples.append(sample)

            # Print live
            print_sample(sample, prev_server_rss)
            prev_server_rss = sample['server_rss_mb']

            # Track idle (no server) time
            if server_pid is None:
                idle_count += 1
                if idle_count > max_idle / SAMPLE_INTERVAL:
                    print(f"\n  >> No server detected for {max_idle}s — stopping")
                    break
            else:
                idle_count = 0

            time.sleep(SAMPLE_INTERVAL)

    except KeyboardInterrupt:
        print(f"\n\n  >> Profiling stopped (Ctrl+C)")

    if not samples:
        print("  No samples collected.")
        return

    # Analyze
    analysis = analyze_profile(samples)

    # Save full profile
    profile = {
        'start_time': datetime.fromtimestamp(start_time).isoformat(timespec='seconds'),
        'end_time': datetime.now().isoformat(timespec='seconds'),
        'sample_count': len(samples),
        'analysis': analysis,
        'samples': samples,
    }

    with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
        json.dump(profile, f, indent=2, default=str)

    print(f"\n  Full profile saved to: {PROFILE_FILE}")

    # Print report
    print_report(analysis)


if __name__ == '__main__':
    main()
