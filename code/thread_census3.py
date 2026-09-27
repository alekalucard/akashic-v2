"""Thread census v3 - show ALL postal topic names to understand the base topic distribution."""
import psutil
import ctypes
import ctypes.wintypes
import collections

THREAD_QUERY_LIMITED_INFORMATION = 0x0800
kernel32 = ctypes.windll.kernel32

def get_thread_description(thread_id):
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
    proc = psutil.Process(pid)
    threads = proc.threads()

    print(f"PID {pid}: {proc.memory_info().rss / (1024**2):.0f} MB RAM, {len(threads)} threads")
    print()

    postal_counts = collections.Counter()
    for t in threads:
        name = get_thread_description(t.id)
        if name and name.startswith("postal["):
            topic = name.split("]")[0].replace("postal[", "")
            postal_counts[topic] += 1

    print(f"=== ALL {len(postal_counts)} POSTAL TOPICS (sorted by thread count) ===")
    for topic, count in postal_counts.most_common():
        print(f"  {count:>4}  postal[{topic}]")

    # Group by first word to see actual base topic distribution
    base_counts = collections.Counter()
    for topic in postal_counts:
        base_counts[topic] += postal_counts[topic]

    # Check if any topics still have dots (would mean our fix isn't applied fully)
    dotted = [t for t in postal_counts if '.' in t]
    if dotted:
        print(f"\n=== WARNING: {len(dotted)} topics still have dots (fix may not be applied) ===")
        for t in dotted:
            print(f"  postal[{t}]")


if __name__ == "__main__":
    import sys
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if not pid:
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
