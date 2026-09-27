"""
Seed Periodic Table into the Manifold Cortex.

Loads periodic_table.json and creates:
- 118 element nodes (chem:element:SYMBOL) with snippets
- 10 element group nodes (chem:group:NAME)
- is_a edges from elements to their groups
- semantic edges between elements in the same period

Phase 4.5 of the Cortex Rebuild Blueprint.

Usage:
    python scripts/seed_periodic_table.py [--manifold path] [--dry-run]

2026-03-20, Nous + Ace -- Akashic Foundation
"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import os
import sys
import json
import time
import argparse
from collections import defaultdict

# Add project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from infrastructure.manifold_memory import (
    ManifoldMemory,
    NTYPE_CONCEPT,
    REGION_SEMANTIC,
    REL_SEMANTIC, REL_IS_A,
)


def load_vocabulary(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def seed_elements(graph, data: dict, stats: dict, dry_run: bool = False):
    """Seed element nodes (chem:element:SYMBOL)."""
    elements = data.get("elements", {})

    for symbol, entry in elements.items():
        if symbol.startswith("_"):
            continue

        node_key = f"chem:element:{symbol}"
        snippet = entry.get("snippet", "")

        if dry_run:
            stats["nodes"] += 1
            stats["snippets_bytes"] += len(snippet.encode('utf-8'))
            continue

        slot = graph.upsert_node(
            key=node_key,
            activation=2.0,
            count=100,
            snippet=snippet,
            node_type=NTYPE_CONCEPT,
            region=REGION_SEMANTIC,
        )
        if slot >= 0:
            stats["nodes"] += 1
            stats["snippets_bytes"] += len(snippet.encode('utf-8'))
        else:
            stats["failed"] += 1
            print(f"  FAILED to seed: {node_key}")


def seed_groups(graph, data: dict, stats: dict, dry_run: bool = False):
    """Seed element group nodes (chem:group:NAME) and is_a edges from elements."""
    groups = data.get("element_groups", {})

    for group_name, group_data in groups.items():
        if group_name.startswith("_"):
            continue

        node_key = f"chem:group:{group_name}"
        snippet = group_data.get("snippet", "")
        members = group_data.get("members", [])

        if dry_run:
            stats["nodes"] += 1
            stats["snippets_bytes"] += len(snippet.encode('utf-8'))
            stats["edges"] += len(members)
            continue

        slot = graph.upsert_node(
            key=node_key,
            activation=2.0,
            count=100,
            snippet=snippet,
            node_type=NTYPE_CONCEPT,
            region=REGION_SEMANTIC,
        )
        if slot >= 0:
            stats["nodes"] += 1
            stats["snippets_bytes"] += len(snippet.encode('utf-8'))
        else:
            stats["failed"] += 1
            continue

        # is_a edges: element -> group
        for member in members:
            ok = graph.link(
                f"chem:element:{member}", node_key,
                weight=0.7,
                rel_type=REL_IS_A,
            )
            if ok:
                stats["edges"] += 1
            else:
                stats["edge_misses"] += 1


def seed_period_edges(graph, data: dict, stats: dict, dry_run: bool = False):
    """Create semantic edges between elements in the same period."""
    elements = data.get("elements", {})

    # Group elements by period
    periods = defaultdict(list)
    for symbol, entry in elements.items():
        if symbol.startswith("_"):
            continue
        period = entry.get("period")
        if period is not None:
            periods[period].append(symbol)

    # Sort each period by atomic number for neighbor linking
    for period_num in sorted(periods.keys()):
        members = periods[period_num]
        # Sort by atomic number
        members.sort(key=lambda s: elements[s].get("atomic_number", 0))

        # Link consecutive elements in the period
        for i in range(len(members) - 1):
            a = f"chem:element:{members[i]}"
            b = f"chem:element:{members[i + 1]}"

            if dry_run:
                stats["edges"] += 1
                continue

            ok = graph.link(a, b, weight=0.5, rel_type=REL_SEMANTIC)
            if ok:
                stats["edges"] += 1
            else:
                stats["edge_misses"] += 1


def main():
    parser = argparse.ArgumentParser(description="Seed periodic table into cortex manifold")
    parser.add_argument("--manifold", default=None,
                        help="Path to cortex.manifold (default: auto-detect)")
    parser.add_argument("--vocab", default=None,
                        help="Path to periodic_table.json (default: auto-detect)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be seeded without modifying the manifold")
    args = parser.parse_args()

    # Find manifold
    manifold_path = args.manifold
    if not manifold_path:
        for c in ["state/akashic/cortex.manifold", "../state/akashic/cortex.manifold"]:
            if os.path.exists(c):
                manifold_path = c
                break
    if not manifold_path and not args.dry_run:
        print("ERROR: Could not find cortex.manifold. Use --manifold to specify path.")
        sys.exit(1)

    # Find vocabulary JSON
    vocab_path = args.vocab
    if not vocab_path:
        for c in ["state/knowledge_seeds/periodic_table.json",
                   "../state/knowledge_seeds/periodic_table.json"]:
            if os.path.exists(c):
                vocab_path = c
                break
    if not vocab_path:
        print("ERROR: Could not find periodic_table.json. Use --vocab to specify path.")
        sys.exit(1)

    # Load vocabulary
    print(f"Loading vocabulary: {vocab_path}")
    data = load_vocabulary(vocab_path)
    meta = data.get("_meta", {})
    print(f"  Title: {meta.get('title', 'unknown')}")
    print(f"  Version: {meta.get('version', '?')}")
    print(f"  Elements: {meta.get('element_count', '?')}")

    stats = {"nodes": 0, "edges": 0, "failed": 0, "edge_misses": 0, "snippets_bytes": 0}

    if args.dry_run:
        print(f"\n--- DRY RUN (no manifold changes) ---")
        graph = None
    else:
        file_size = os.path.getsize(manifold_path)
        print(f"\nOpening manifold: {manifold_path} ({file_size / (1024*1024):.1f} MB)")
        graph = ManifoldMemory(manifold_path)
        status_before = graph.status()
        print(f"  Before: {status_before['nodes']} nodes, {status_before['edges']} edges")

    print(f"\nSeeding periodic table...")
    t0 = time.time()

    # ── 1. Element nodes ──
    print("  [1/3] Element nodes (118 elements)...")
    n0 = stats["nodes"]
    seed_elements(graph, data, stats, args.dry_run)
    print(f"        {stats['nodes'] - n0} nodes")

    # ── 2. Group nodes + is_a edges ──
    print("  [2/3] Element groups + is_a edges...")
    n0, e0 = stats["nodes"], stats["edges"]
    seed_groups(graph, data, stats, args.dry_run)
    print(f"        {stats['nodes'] - n0} nodes, {stats['edges'] - e0} edges")

    # ── 3. Period neighbor edges ──
    print("  [3/3] Period neighbor edges (semantic)...")
    e0 = stats["edges"]
    seed_period_edges(graph, data, stats, args.dry_run)
    print(f"        {stats['edges'] - e0} edges")

    elapsed = time.time() - t0

    if graph and not args.dry_run:
        graph._write_header()
        status_after = graph.status()
        print(f"\n  After: {status_after['nodes']} nodes, {status_after['edges']} edges")
        graph.close()

    print(f"\nSeeding complete in {elapsed:.1f}s")
    print(f"\n--- Summary ---")
    print(f"  Nodes created:  {stats['nodes']}")
    print(f"  Edges created:  {stats['edges']}")
    print(f"  Snippet bytes:  {stats['snippets_bytes']:,}")
    print(f"  Failed nodes:   {stats['failed']}")
    print(f"  Missed edges:   {stats['edge_misses']}")

    # Verification
    if not args.dry_run and manifold_path:
        print(f"\n--- Verification ---")
        graph = ManifoldMemory(manifold_path, readonly=True)
        for test_key in ["chem:element:H", "chem:element:Fe", "chem:element:Au",
                         "chem:group:noble_gas", "chem:group:halogen",
                         "chem:group:transition_metal"]:
            node = graph.get_node(test_key)
            if node:
                snippet = node.get("snippet", "")[:60]
                ntype = node.get("node_type_name", "?")
                print(f"  {test_key}: type={ntype}, snippet=\"{snippet}...\"")
            else:
                print(f"  {test_key}: NOT FOUND")
        graph.close()

    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
