"""
Memory monitor: watches server.py RSS during boot.
Prints every time RSS grows by >50MB.
Run: python mem_monitor.py  (in a separate terminal while server boots)
Or: python mem_monitor.py --self  (monitors own process, for testing)
"""
import psutil
import time
import sys
import os

def find_server_pid():
    """Find the server.py process."""
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = p.info.get('cmdline') or []
            cmd_str = ' '.join(cmd).lower()
            if 'server.py' in cmd_str and 'python' in (p.info.get('name') or '').lower():
                return p.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

def monitor(pid, interval=0.5):
    proc = psutil.Process(pid)
    last_rss = 0
    start = time.time()
    print(f"Monitoring PID {pid} (RSS every {interval}s, alerts on >50MB jump)")
    print(f"{'Time':>8}  {'RSS_MB':>8}  {'Delta':>8}  Note")
    print("-" * 50)

    while True:
        try:
            rss = proc.memory_info().rss / 1024 / 1024
            delta = rss - last_rss
            elapsed = time.time() - start

            note = ""
            if delta > 50:
                note = f"*** +{delta:.0f}MB JUMP ***"
            elif delta > 10:
                note = f"+{delta:.0f}MB"
            elif delta < -10:
                note = f"{delta:.0f}MB (freed)"

            if abs(delta) > 10 or elapsed < 5 or int(elapsed) % 10 == 0:
                print(f"{elapsed:7.1f}s  {rss:7.0f}  {delta:+7.0f}  {note}")

            last_rss = rss
            time.sleep(interval)
        except psutil.NoSuchProcess:
            print(f"\nProcess {pid} exited")
            break
        except KeyboardInterrupt:
            break

def main():
    if "--self" in sys.argv:
        monitor(os.getpid())
        return

    print("Waiting for server.py process...")
    while True:
        pid = find_server_pid()
        if pid:
            monitor(pid)
            break
        time.sleep(0.5)

if __name__ == "__main__":
    main()
