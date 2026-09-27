"""Watch system RAM and top Python processes during boot."""
import psutil, time, os

def snapshot():
    mem = psutil.virtual_memory()
    used_gb = mem.used / (1024**3)
    total_gb = mem.total / (1024**3)
    free_gb = mem.available / (1024**3)
    print(f"\n{'='*60}")
    print(f"RAM: {used_gb:.1f} / {total_gb:.1f} GB used  ({free_gb:.1f} GB free, {mem.percent}%)")
    print(f"{'='*60}")

    # Get all python processes
    py_procs = []
    for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
        try:
            info = p.info
            name = info['name'] or ''
            if 'python' in name.lower():
                rss_mb = info['memory_info'].rss / (1024**2)
                cmd = ' '.join(info['cmdline'][:3]) if info['cmdline'] else name
                # Trim long paths
                cmd = cmd.replace('C:\\Users\\Ace\\AppData\\Local\\Programs\\Python\\Python312\\', '')
                cmd = cmd.replace('F:\\Sandbox\\failure_factory\\akashic_v2\\', '')
                py_procs.append((rss_mb, info['pid'], cmd[:80]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    py_procs.sort(reverse=True)
    total_py = sum(r for r, _, _ in py_procs)
    print(f"\nPython processes: {len(py_procs)} ({total_py:.0f} MB total)")
    for rss, pid, cmd in py_procs[:15]:
        print(f"  {rss:7.0f} MB  PID {pid:6d}  {cmd}")

    # Top non-python RAM consumers
    others = []
    for p in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            info = p.info
            name = info['name'] or ''
            if 'python' not in name.lower():
                rss_mb = info['memory_info'].rss / (1024**2)
                if rss_mb > 200:
                    others.append((rss_mb, info['pid'], name))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    others.sort(reverse=True)
    if others:
        print(f"\nOther big processes (>200 MB):")
        for rss, pid, name in others[:10]:
            print(f"  {rss:7.0f} MB  PID {pid:6d}  {name}")

if __name__ == '__main__':
    print("RAM watcher — snapshots every 15s. Ctrl+C to stop.")
    try:
        while True:
            snapshot()
            time.sleep(15)
    except KeyboardInterrupt:
        print("\nDone.")
