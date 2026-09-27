"""Attach to running Akashic server and profile RAM usage."""
import sys, os, gc, json

# Add project to path
sys.path.insert(0, r"F:\Sandbox\failure_factory\akashic_v2")

def profile_objects():
    """Count objects by type and find the biggest."""
    gc.collect()

    type_counts = {}
    type_sizes = {}

    for obj in gc.get_objects():
        t = type(obj).__name__
        type_counts[t] = type_counts.get(t, 0) + 1
        try:
            s = sys.getsizeof(obj)
            type_sizes[t] = type_sizes.get(t, 0) + s
        except:
            pass

    print("=== TOP TYPES BY COUNT ===")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1])[:20]:
        size_mb = type_sizes.get(t, 0) / (1024*1024)
        print(f"  {t:30s}  count={c:>10,}  size={size_mb:>8.1f} MB")

    print("\n=== TOP TYPES BY SIZE ===")
    for t, s in sorted(type_sizes.items(), key=lambda x: -x[1])[:20]:
        c = type_counts.get(t, 0)
        print(f"  {t:30s}  size={s/(1024*1024):>8.1f} MB  count={c:>10,}")

    # Check specific suspects
    print("\n=== SPECIFIC CHECKS ===")

    # Find ConceptNode instances
    concept_nodes = [o for o in gc.get_objects() if type(o).__name__ == 'ConceptNode']
    print(f"  ConceptNode instances: {len(concept_nodes)}")

    # Find ConceptGraph instances
    graphs = [o for o in gc.get_objects() if type(o).__name__ == 'ConceptGraph']
    print(f"  ConceptGraph instances: {len(graphs)}")
    for i, g in enumerate(graphs):
        nodes = len(getattr(g, 'nodes', {}))
        edges = len(getattr(g, 'edges', {}))
        ro = getattr(g, '_read_only', 'NOT SET')
        print(f"    Graph #{i}: nodes={nodes}, edges={edges}, _read_only={ro}")

    # Find large dicts
    big_dicts = []
    for obj in gc.get_objects():
        if isinstance(obj, dict) and len(obj) > 5000:
            try:
                size = sys.getsizeof(obj)
                # Get a sample key for identification
                sample = str(list(obj.keys())[:3])[:80]
                big_dicts.append((len(obj), size, sample))
            except:
                pass

    print(f"\n  Large dicts (>5000 entries): {len(big_dicts)}")
    for length, size, sample in sorted(big_dicts, key=lambda x: -x[0])[:15]:
        print(f"    len={length:>10,}  size={size/(1024*1024):>6.1f} MB  keys={sample}")

    # Find large lists
    big_lists = []
    for obj in gc.get_objects():
        if isinstance(obj, list) and len(obj) > 5000:
            try:
                size = sys.getsizeof(obj)
                sample = str(type(obj[0]).__name__) if obj else "empty"
                big_lists.append((len(obj), size, sample))
            except:
                pass

    print(f"\n  Large lists (>5000 entries): {len(big_lists)}")
    for length, size, sample in sorted(big_lists, key=lambda x: -x[0])[:10]:
        print(f"    len={length:>10,}  size={size/(1024*1024):>6.1f} MB  item_type={sample}")

    # Total tracked
    total = sum(type_sizes.values())
    print(f"\n=== TOTAL TRACKED: {total/(1024*1024*1024):.2f} GB ===")

if __name__ == "__main__":
    profile_objects()
