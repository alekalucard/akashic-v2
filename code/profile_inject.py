"""Run inside the main server process to profile RAM."""
import sys, gc, os

def profile():
    gc.collect()

    results = []

    # Count by type
    type_counts = {}
    type_sizes = {}
    for obj in gc.get_objects():
        t = type(obj).__name__
        type_counts[t] = type_counts.get(t, 0) + 1
        try:
            type_sizes[t] = type_sizes.get(t, 0) + sys.getsizeof(obj)
        except:
            pass

    results.append("TOP TYPES BY SIZE:")
    for t, s in sorted(type_sizes.items(), key=lambda x: -x[1])[:20]:
        c = type_counts.get(t, 0)
        results.append(f"  {t:30s}  {s/(1024*1024):>8.1f} MB  count={c:,}")

    # ConceptNode/ConceptGraph check
    cn_count = type_counts.get('ConceptNode', 0)
    cg_count = type_counts.get('ConceptGraph', 0)
    results.append(f"\nConceptNode count: {cn_count}")
    results.append(f"ConceptGraph count: {cg_count}")

    # Find ConceptGraph details
    for obj in gc.get_objects():
        if type(obj).__name__ == 'ConceptGraph':
            n = len(getattr(obj, 'nodes', {}))
            e = len(getattr(obj, 'edges', {}))
            ro = getattr(obj, '_read_only', 'N/A')
            results.append(f"  Graph: nodes={n}, edges={e}, _read_only={ro}")

    # Large dicts
    big_dicts = []
    for obj in gc.get_objects():
        if isinstance(obj, dict) and len(obj) > 1000:
            try:
                size = sys.getsizeof(obj)
                keys = list(obj.keys())[:3]
                sample = str(keys)[:60]
                big_dicts.append((len(obj), size, sample))
            except:
                pass

    results.append(f"\nLarge dicts (>1000): {len(big_dicts)}")
    for length, size, sample in sorted(big_dicts, key=lambda x: -x[0])[:15]:
        results.append(f"  len={length:>10,}  {size/(1024*1024):>6.1f} MB  keys={sample}")

    # Large lists
    big_lists = []
    for obj in gc.get_objects():
        if isinstance(obj, list) and len(obj) > 1000:
            try:
                size = sys.getsizeof(obj)
                sample = type(obj[0]).__name__ if obj else "empty"
                big_lists.append((len(obj), size, sample))
            except:
                pass

    results.append(f"\nLarge lists (>1000): {len(big_lists)}")
    for length, size, sample in sorted(big_lists, key=lambda x: -x[0])[:10]:
        results.append(f"  len={length:>10,}  {size/(1024*1024):>6.1f} MB  type={sample}")

    # Large strings
    big_strings = []
    for obj in gc.get_objects():
        if isinstance(obj, str) and len(obj) > 100000:
            big_strings.append((len(obj), obj[:50]))

    results.append(f"\nLarge strings (>100K chars): {len(big_strings)}")
    for length, preview in sorted(big_strings, key=lambda x: -x[0])[:5]:
        results.append(f"  len={length:>10,}  preview={preview!r}")

    # Large bytes
    big_bytes = []
    for obj in gc.get_objects():
        if isinstance(obj, bytes) and len(obj) > 100000:
            big_bytes.append(len(obj))

    results.append(f"\nLarge bytes (>100K): {len(big_bytes)}")
    total_big_bytes = sum(big_bytes)
    results.append(f"  Total: {total_big_bytes/(1024*1024):.1f} MB")
    for size in sorted(big_bytes, reverse=True)[:5]:
        results.append(f"  {size/(1024*1024):.1f} MB")

    total = sum(type_sizes.values())
    results.append(f"\nTOTAL TRACKED BY GC: {total/(1024*1024*1024):.2f} GB")

    # Process RSS
    try:
        import psutil
        p = psutil.Process(os.getpid())
        rss = p.memory_info().rss
        results.append(f"PROCESS RSS: {rss/(1024*1024*1024):.2f} GB")
    except:
        results.append("(psutil not available)")

    return "\n".join(results)

if __name__ == "__main__":
    print(profile())
