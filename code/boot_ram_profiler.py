"""Boot RAM profiler — runs alongside server.py to catch the RAM hog.

Usage:
    Terminal 1:  python boot_ram_profiler.py
    Terminal 2:  python server.py

Samples every 2 seconds, shows delta from previous sample.
Highlights any jump > 500 MB.
"""
import psutil, time, os, sys

def get_python_procs():
    """Get all python processes with their RSS."""
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
        try:
            info = p.info
            name = info['name'] or ''
            if 'python' in name.lower():
                rss_mb = info['memory_info'].rss / (1024**2)
                cmd = ''
                if info['cmdline']:
                    cmd = ' '.join(info['cmdline'][:4])
                    # Shorten paths
                    for prefix in [
                        r'C:\Users\Ace\AppData\Local\Programs\Python\Python312' + '\\',
                        r'C:\Users\Ace\AppData\Local\Programs\Python\Python314' + '\\',
                        r'F:\Sandbox\failure_factory\akashic_v2' + '\\',
                    ]:
                        cmd = cmd.replace(prefix, '')
                else:
                    cmd = name
                procs.append((rss_mb, info['pid'], cmd[:80]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(reverse=True)
    return procs

def main():
    print("=" * 70)
    print("BOOT RAM PROFILER — Start server.py in another terminal")
    print("Sampling every 2s. Ctrl+C to stop.")
    print("=" * 70)

    prev_total = 0
    prev_py_total = 0
    prev_procs = {}  # pid -> rss_mb
    sample = 0
    peak_ram = 0

    try:
        while True:
            sample += 1
            mem = psutil.virtual_memory()
            total_used_gb = mem.used / (1024**3)
            total_gb = mem.total / (1024**3)

            procs = get_python_procs()
            py_total = sum(r for r, _, _ in procs)

            delta_total = total_used_gb - prev_total if prev_total > 0 else 0
            delta_py = py_total - prev_py_total if prev_py_total > 0 else 0

            peak_ram = max(peak_ram, total_used_gb)

            # Flag big jumps
            flag = ""
            if abs(delta_total) > 0.5:
                flag = " *** BIG JUMP ***"
            if total_used_gb > total_gb * 0.85:
                flag = " !!! DANGER ZONE !!!"

            print(f"\n[{sample:4d}] {time.strftime('%H:%M:%S')} | "
                  f"RAM: {total_used_gb:.1f}/{total_gb:.1f} GB ({mem.percent}%) | "
                  f"Δ={delta_total:+.1f} GB | "
                  f"Python: {py_total:.0f} MB ({len(procs)} procs, Δ={delta_py:+.0f} MB) | "
                  f"Peak: {peak_ram:.1f} GB{flag}")

            # Show per-process breakdown when there's a jump or every 10 samples
            if abs(delta_total) > 0.3 or sample % 10 == 1:
                for rss, pid, cmd in procs[:8]:
                    prev_rss = prev_procs.get(pid, 0)
                    delta = rss - prev_rss
                    delta_str = f"Δ={delta:+.0f}" if prev_rss > 0 else "NEW"
                    if rss > 50:  # Only show >50 MB
                        print(f"       {rss:7.0f} MB  PID {pid:6d}  {delta_str:>10s}  {cmd}")

            prev_total = total_used_gb
            prev_py_total = py_total
            prev_procs = {pid: rss for rss, pid, _ in procs}

            time.sleep(2)

    except KeyboardInterrupt:
        print(f"\n\nPeak RAM: {peak_ram:.1f} GB")
        print("Done.")

if __name__ == '__main__':
    main()
