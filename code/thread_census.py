"""Thread census - enumerate all threads by name prefix to find the explosion source."""
import threading
import collections

def census():
    results = []
    all_threads = threading.enumerate()
    results.append(f"Total alive threads: {len(all_threads)}")
    results.append(f"Active count: {threading.active_count()}")

    # Group by name prefix (thread_name_prefix from ThreadPoolExecutor)
    prefix_counts = collections.Counter()
    prefix_samples = {}
    daemon_count = 0
    alive_count = 0

    for t in all_threads:
        name = t.name or "unnamed"
        if t.daemon:
            daemon_count += 1
        if t.is_alive():
            alive_count += 1

        # Extract prefix: "FairyName_worker_0" -> "FairyName_worker"
        # ThreadPoolExecutor format: "{prefix}_{n}"
        parts = name.rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            prefix = parts[0]
        else:
            prefix = name

        prefix_counts[prefix] += 1
        if prefix not in prefix_samples:
            prefix_samples[prefix] = name

    results.append(f"Daemon threads: {daemon_count}")
    results.append(f"Alive threads: {alive_count}")
    results.append("")
    results.append("=== THREAD GROUPS BY PREFIX (sorted by count) ===")

    for prefix, count in prefix_counts.most_common(60):
        sample = prefix_samples.get(prefix, "")
        results.append(f"  {count:>6}  {prefix:50s}  sample={sample}")

    # Also check ThreadPoolExecutor instances
    results.append("")
    results.append("=== THREAD POOL DETAILS ===")

    import gc
    tpe_count = 0
    for obj in gc.get_objects():
        if type(obj).__name__ == 'ThreadPoolExecutor':
            tpe_count += 1
            try:
                prefix = getattr(obj, '_thread_name_prefix', 'unknown')
                max_w = getattr(obj, '_max_workers', '?')
                threads = len(getattr(obj, '_threads', set()))
                shutdown = getattr(obj, '_shutdown', False)
                results.append(f"  TPE: prefix={prefix!r}, max_workers={max_w}, "
                             f"live_threads={threads}, shutdown={shutdown}")
            except:
                results.append(f"  TPE: (could not inspect)")

    results.append(f"\nTotal ThreadPoolExecutors: {tpe_count}")

    return "\n".join(results)

if __name__ == "__main__":
    print(census())
