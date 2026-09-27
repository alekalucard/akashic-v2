"""Thread census v2 - better grouping to find the explosion."""
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

    # Collect all thread names
    names = []
    unnamed = 0
    for t in threads:
        name = get_thread_description(t.id)
        if name:
            names.append(name)
        else:
            unnamed += 1

    # Group into categories
    categories = collections.Counter()
    fairy_worker_counts = collections.Counter()
    postal_counts = collections.Counter()
    hb_deliver_counts = 0
    spell_chain_counts = 0
    other_named = collections.Counter()

    for name in names:
        if name.startswith("postal["):
            # Extract the topic: postal[topic]#N -> topic
            topic = name.split("]")[0].replace("postal[", "")
            postal_counts[topic] += 1
            categories["postal_subscriber"] += 1
        elif "_worker_" in name:
            # FairyName_worker_N
            prefix = name.rsplit("_worker_", 1)[0]
            fairy_worker_counts[prefix] += 1
            categories["fairy_worker"] += 1
        elif name.startswith("hb-deliver"):
            hb_deliver_counts += 1
            categories["hb-deliver"] += 1
        elif "spell" in name.lower() or "chain" in name.lower():
            spell_chain_counts += 1
            categories["spell_chain"] += 1
        elif name.startswith("Thread-"):
            categories["generic_Thread"] += 1
        elif name.startswith("ThreadPoolExecutor"):
            categories["TPE_generic"] += 1
        else:
            other_named[name] += 1
            categories["other_named"] += 1

    # Summary
    print("=== CATEGORY SUMMARY ===")
    for cat, count in categories.most_common():
        print(f"  {count:>6}  {cat}")
    print(f"  {unnamed:>6}  unnamed")
    print(f"  {len(threads):>6}  TOTAL")
    print()

    # Postal topics with multiple threads (should be 1 per topic)
    multi_postal = {t: c for t, c in postal_counts.items() if c > 1}
    if multi_postal:
        print("=== POSTAL TOPICS WITH >1 THREAD (leak!) ===")
        for topic, count in sorted(multi_postal.items(), key=lambda x: -x[1]):
            print(f"  {count:>6}  postal[{topic}]")
        print()

    # Postal topics: total unique
    print(f"=== POSTAL: {len(postal_counts)} unique topics, {sum(postal_counts.values())} total threads ===")
    print()

    # Fairy workers with many threads (should be max 2 per fairy)
    multi_worker = {f: c for f, c in fairy_worker_counts.items() if c > 2}
    if multi_worker:
        print("=== FAIRY WORKERS WITH >2 THREADS (leak!) ===")
        for fairy, count in sorted(multi_worker.items(), key=lambda x: -x[1]):
            print(f"  {count:>6}  {fairy}")
        print()

    # All fairy workers
    print(f"=== FAIRY WORKERS: {len(fairy_worker_counts)} fairies, {sum(fairy_worker_counts.values())} total threads ===")
    for fairy, count in sorted(fairy_worker_counts.items(), key=lambda x: -x[1])[:30]:
        marker = " <-- LEAK" if count > 2 else ""
        print(f"  {count:>4}  {fairy}{marker}")
    print()

    # Heartbeat delivery
    print(f"=== HEARTBEAT DELIVERY: {hb_deliver_counts} threads ===")
    print()

    # Other named
    if other_named:
        print("=== OTHER NAMED THREADS ===")
        for name, count in other_named.most_common(40):
            print(f"  {count:>4}  {name}")
        print()

    # Unnamed thread CPU analysis
    print(f"=== UNNAMED THREADS: {unnamed} ===")
    unnamed_cpu = []
    for t in threads:
        name = get_thread_description(t.id)
        if not name:
            unnamed_cpu.append((t.user_time + t.system_time, t.id))
    unnamed_cpu.sort(reverse=True)
    print(f"  With >0 CPU: {sum(1 for c,_ in unnamed_cpu if c > 0)}")
    print(f"  With 0 CPU:  {sum(1 for c,_ in unnamed_cpu if c == 0)}")
    print(f"  Top 5 CPU:")
    for cpu, tid in unnamed_cpu[:5]:
        print(f"    {cpu:>10.2f}s  tid={tid}")


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
