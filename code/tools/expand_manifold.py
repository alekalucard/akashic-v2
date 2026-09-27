#!/usr/bin/env python
"""
Expand ManifoldMemory from 100k → 1M node capacity.

The manifold is a fixed-size binary file. You can't just append to it.
This script:
1. Opens the old manifold (100k capacity, 40MB)
2. Reads ALL nodes and edges (including activations, counts, coords)
3. Creates a new manifold with 1M node capacity (~400MB)
4. Copies everything into the new file
5. Backs up the old manifold

Usage:
    python tools/expand_manifold.py

    # Custom capacity:
    python tools/expand_manifold.py --capacity 500000

    # Dry run (just report stats):
    python tools/expand_manifold.py --dry-run

NOTE: Server must be STOPPED before running this. The portal subprocess
has the manifold file mmap'd — writing to it while open will corrupt it.

2026-03-09 (Nous) — Unblock cortex growth past 100k node hard cap.
"""

import os
import sys
import time
import shutil
import argparse

# Add project root to path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from infrastructure.manifold_memory import ManifoldMemory, FLAG_ACTIVE, FLAG_DELETED, FLAG_FROZEN


def expand_manifold(manifold_path: str, new_capacity: int = 1_000_000,
                    edge_ratio: int = 10, dry_run: bool = False):
    """Expand a manifold file to a larger capacity.

    Args:
        manifold_path: Path to existing .manifold file
        new_capacity: New node capacity (default 1M)
        edge_ratio: edges = node_capacity * edge_ratio (default 10 = 10M edges)
        dry_run: If True, just report stats without writing
    """
    print(f"\n{'='*60}")
    print(f"  MANIFOLD EXPANSION TOOL")
    print(f"{'='*60}\n")

    if not os.path.exists(manifold_path):
        print(f"ERROR: Manifold not found at {manifold_path}")
        return False

    # Open the old manifold (read-only)
    print(f"Opening old manifold: {manifold_path}")
    old = ManifoldMemory(manifold_path, readonly=True)
    old_status = old.status()

    print(f"\n  Old Manifold Status:")
    print(f"    Nodes:    {old_status['nodes']:,} / {old_status['node_capacity']:,} "
          f"({old_status['nodes']/old_status['node_capacity']*100:.1f}% full)")
    print(f"    Edges:    {old_status['edges']:,} / {old_status['edge_capacity']:,} "
          f"({old_status['edges']/old_status['edge_capacity']*100:.1f}% full)")
    print(f"    File:     {old_status.get('file_mb', 0):.1f}MB")

    new_edge_cap = new_capacity * edge_ratio
    est_size_mb = (
        48  # header
        + new_capacity * 32  # node table (NODE_RECORD_SIZE)
        + new_capacity * 64  # string table
        + new_edge_cap * 20  # edge table (EDGE_RECORD_SIZE)
    ) / (1024 * 1024)

    print(f"\n  New Manifold Target:")
    print(f"    Nodes:    {new_capacity:,} (was {old_status['node_capacity']:,})")
    print(f"    Edges:    {new_edge_cap:,} (was {old_status['edge_capacity']:,})")
    print(f"    Est size: {est_size_mb:.0f}MB")

    if old_status['node_capacity'] >= new_capacity:
        print(f"\n  WARNING: Old capacity ({old_status['node_capacity']:,}) >= "
              f"new capacity ({new_capacity:,}). Nothing to expand!")
        old.close()
        return False

    if dry_run:
        print(f"\n  DRY RUN — no changes made.")
        # close readonly mmap without flushing
        if old._mm:
            old._mm.close()
            old._mm = None
        if old._file:
            old._file.close()
            old._file = None
        return True

    # ── Phase 1: Extract all nodes ──
    print(f"\n  Phase 1: Extracting {old_status['nodes']:,} nodes...")
    t0 = time.time()

    nodes = []
    slot_to_key = {}
    for key, slot in old._key_index.items():
        record = old._read_node(slot)
        # record: (key_offset, key_len, plane, channel, position,
        #          activation, count, degree, last_access, flags)
        nodes.append({
            'key': key,
            'plane': record[2],
            'channel': record[3],
            'position': record[4],
            'activation': record[5],
            'count': record[6],
            'degree': record[7],
            'last_access': record[8],
            'flags': record[9],
        })
        slot_to_key[slot] = key

    print(f"    Extracted {len(nodes):,} nodes in {(time.time()-t0)*1000:.0f}ms")

    # ── Phase 2: Extract all edges ──
    print(f"\n  Phase 2: Extracting edges...")
    t1 = time.time()

    edges = []
    for slot in range(old._edge_count):
        record = old._read_edge(slot)
        node_a, node_b, weight, rel_type, flags = record
        if flags == FLAG_DELETED:
            continue

        # Map slot IDs to keys
        key_a = slot_to_key.get(node_a)
        key_b = slot_to_key.get(node_b)
        if key_a and key_b:
            edges.append({
                'key_a': key_a,
                'key_b': key_b,
                'weight': weight,
                'rel_type': rel_type,
            })

    print(f"    Extracted {len(edges):,} active edges in {(time.time()-t1)*1000:.0f}ms")

    old.close()

    # ── Phase 3: Backup old manifold ──
    backup_path = manifold_path + f".backup_{int(time.time())}"
    print(f"\n  Phase 3: Backing up old manifold...")
    print(f"    {manifold_path} -> {backup_path}")
    shutil.copy2(manifold_path, backup_path)

    # ── Phase 4: Create new manifold ──
    print(f"\n  Phase 4: Creating new manifold ({new_capacity:,} nodes, {new_edge_cap:,} edges)...")
    t2 = time.time()

    # Remove old file (ManifoldMemory.__init__ needs to create fresh)
    os.remove(manifold_path)

    new = ManifoldMemory(manifold_path, node_capacity=new_capacity,
                         edge_capacity=new_edge_cap)

    print(f"    Created in {(time.time()-t2)*1000:.0f}ms")

    # ── Phase 5: Copy nodes ──
    print(f"\n  Phase 5: Copying {len(nodes):,} nodes...")
    t3 = time.time()

    for i, node in enumerate(nodes):
        coord_str = f"{node['plane']:03d}.{node['channel']:03d}.{node['position']:03d}"
        new.upsert_node(
            key=node['key'],
            activation=node['activation'],
            count=node['count'],
            degree=node['degree'],
            coord_str=coord_str,
        )
        if (i + 1) % 25000 == 0:
            print(f"    ... {i+1:,} / {len(nodes):,} nodes")

    print(f"    Copied {len(nodes):,} nodes in {(time.time()-t3)*1000:.0f}ms")

    # ── Phase 6: Copy edges ──
    print(f"\n  Phase 6: Copying {len(edges):,} edges...")
    t4 = time.time()

    edge_ok = 0
    edge_fail = 0
    for i, edge in enumerate(edges):
        ok = new.link(edge['key_a'], edge['key_b'],
                      weight=edge['weight'], rel_type=edge['rel_type'])
        if ok:
            edge_ok += 1
        else:
            edge_fail += 1

        if (i + 1) % 50000 == 0:
            print(f"    ... {i+1:,} / {len(edges):,} edges")

    print(f"    Copied {edge_ok:,} edges ({edge_fail:,} failed) "
          f"in {(time.time()-t4)*1000:.0f}ms")

    # ── Phase 7: Flush and verify ──
    new.flush()
    new_status = new.status()

    print(f"\n{'='*60}")
    print(f"  EXPANSION COMPLETE")
    print(f"{'='*60}")
    print(f"    Nodes:    {new_status['nodes']:,} / {new_status['node_capacity']:,} "
          f"({new_status['nodes']/new_status['node_capacity']*100:.1f}% full)")
    print(f"    Edges:    {new_status['edges']:,} / {new_status['edge_capacity']:,} "
          f"({new_status['edges']/new_status['edge_capacity']*100:.1f}% full)")
    print(f"    Headroom: {new_status['node_capacity'] - new_status['nodes']:,} node slots free")
    print(f"    File:     {new_status.get('file_mb', 0):.1f}MB")
    print(f"    Backup:   {backup_path}")
    print(f"    Total:    {(time.time()-t0):.1f}s")
    print()

    new.close()
    return True


def main():
    parser = argparse.ArgumentParser(description="Expand ManifoldMemory capacity")
    parser.add_argument("--capacity", type=int, default=1_000_000,
                        help="New node capacity (default: 1,000,000)")
    parser.add_argument("--edge-ratio", type=int, default=10,
                        help="Edges per node capacity (default: 10)")
    parser.add_argument("--manifold", type=str, default="",
                        help="Path to manifold file (auto-detected if omitted)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report stats without modifying anything")
    args = parser.parse_args()

    # Auto-detect manifold path
    manifold_path = args.manifold
    if not manifold_path:
        candidates = [
            os.path.join(ROOT, "state", "portal_cortex.manifold"),
            os.path.join(ROOT, "P10_Memory", "Akashic_triple_helix_memory_storage",
                         "relational_clusters", "AssociationCortexFairy",
                         "helix_cards", "portal_cortex.manifold"),
        ]
        for c in candidates:
            if os.path.exists(c):
                manifold_path = c
                break

    if not manifold_path:
        print("ERROR: Could not find portal_cortex.manifold. Use --manifold <path>")
        sys.exit(1)

    # Also expand the P10 copy if it exists
    p10_manifold = os.path.join(
        ROOT, "P10_Memory", "Akashic_triple_helix_memory_storage",
        "relational_clusters", "AssociationCortexFairy",
        "helix_cards", "portal_cortex.manifold")

    ok = expand_manifold(manifold_path, args.capacity, args.edge_ratio, args.dry_run)

    if ok and not args.dry_run and os.path.exists(p10_manifold) and p10_manifold != manifold_path:
        print(f"\n  Syncing expanded manifold to P10 location...")
        shutil.copy2(manifold_path, p10_manifold)
        print(f"    Copied to: {p10_manifold}")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
