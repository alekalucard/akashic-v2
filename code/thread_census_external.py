"""External thread census using ctypes to enumerate thread names from outside the process."""
import psutil
import ctypes
import ctypes.wintypes
import collections

# Windows API for thread names
THREAD_QUERY_LIMITED_INFORMATION = 0x0800

class UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ("Length", ctypes.wintypes.USHORT),
        ("MaximumLength", ctypes.wintypes.USHORT),
        ("Buffer", ctypes.c_wchar_p),
    ]

# Try to use NtQueryInformationThread to get thread names
ntdll = ctypes.windll.ntdll
kernel32 = ctypes.windll.kernel32

# ThreadNameInformation = 38
ThreadNameInformation = 38

def get_thread_description(thread_id):
    """Get thread name using GetThreadDescription (Win10 1607+)."""
    try:
        handle = kernel32.OpenThread(THREAD_QUERY_LIMITED_INFORMATION, False, thread_id)
        if not handle:
            return None

        desc = ctypes.c_wchar_p()
        hr = ctypes.windll.kernel32.GetThreadDescription(handle, ctypes.byref(desc))
        kernel32.CloseHandle(handle)

        if hr >= 0 and desc.value:
            return desc.value
        return None
    except Exception:
        return None


def census(pid):
    """Enumerate all threads of a process and group by name prefix."""
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print(f"Process {pid} not found")
        return

    print(f"=== Thread Census for PID {pid} ===")
    print(f"Process: {proc.name()}")
    print(f"RAM: {proc.memory_info().rss / (1024*1024):.0f} MB")

    threads = proc.threads()
    print(f"Total threads: {len(threads)}")
    print()

    # Try to get thread names
    named = 0
    unnamed = 0
    prefix_counts = collections.Counter()
    name_samples = {}

    for t in threads:
        tid = t.id
        name = get_thread_description(tid)

        if name:
            named += 1
            # Extract prefix (ThreadPoolExecutor uses "{prefix}_{n}")
            parts = name.rsplit("_", 1)
            if len(parts) == 2 and parts[1].isdigit():
                prefix = parts[0]
            else:
                prefix = name
            prefix_counts[prefix] += 1
            if prefix not in name_samples:
                name_samples[prefix] = name
        else:
            unnamed += 1

    print(f"Named threads: {named}")
    print(f"Unnamed threads: {unnamed}")
    print()

    if prefix_counts:
        print("=== THREAD GROUPS BY PREFIX (sorted by count) ===")
        for prefix, count in prefix_counts.most_common(80):
            sample = name_samples.get(prefix, "")
            print(f"  {count:>6}  {prefix:55s}  sample={sample}")
    else:
        print("Could not read thread names (need Win10 1607+ or admin)")
        print("Falling back to thread state analysis...")
        print()

        # Fallback: analyze thread states
        state_counts = collections.Counter()
        for t in threads:
            # user_time and system_time can hint at active vs idle
            if t.user_time == 0 and t.system_time == 0:
                state_counts["zero_cpu"] += 1
            elif t.user_time < 0.1 and t.system_time < 0.1:
                state_counts["very_low_cpu"] += 1
            else:
                state_counts["active_cpu"] += 1

        print("=== THREAD STATES ===")
        for state, count in state_counts.most_common():
            print(f"  {count:>6}  {state}")

    # Thread creation rate
    print()
    print("=== THREAD CPU TIME DISTRIBUTION ===")
    cpu_times = []
    for t in threads:
        total = t.user_time + t.system_time
        cpu_times.append(total)

    cpu_times.sort(reverse=True)
    print(f"  Total threads: {len(cpu_times)}")
    print(f"  Threads with 0 CPU time: {sum(1 for c in cpu_times if c == 0)}")
    print(f"  Threads with <0.1s CPU: {sum(1 for c in cpu_times if c < 0.1)}")
    print(f"  Threads with <1s CPU: {sum(1 for c in cpu_times if c < 1.0)}")
    print(f"  Threads with >1s CPU: {sum(1 for c in cpu_times if c >= 1.0)}")
    print(f"  Threads with >10s CPU: {sum(1 for c in cpu_times if c >= 10.0)}")
    print(f"  Top 10 CPU consumers:")
    for i, ct in enumerate(cpu_times[:10]):
        tid = threads[i].id if i < len(threads) else "?"
        name = get_thread_description(threads[i].id) if i < len(threads) else "?"
        print(f"    {ct:>10.2f}s  tid={tid}  name={name}")


if __name__ == "__main__":
    import sys
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else None

    if not pid:
        # Find the biggest python process (likely the server)
        biggest = None
        biggest_rss = 0
        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            if "python" in p.info["name"].lower():
                rss = p.info["memory_info"].rss
                if rss > biggest_rss:
                    biggest_rss = rss
                    biggest = p.info["pid"]
        pid = biggest

    if pid:
        census(pid)
    else:
        print("No python process found")
