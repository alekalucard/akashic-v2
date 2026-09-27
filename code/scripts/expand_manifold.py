"""
Expand the cortex manifold to larger capacity.

The 1M-node manifold hit capacity after holographic book ingestion
created ~437K new bigram nodes. Also, the 64MB string table overflowed
by 36MB (159MB used) into the edge region, corrupting edges.

This script:
  1. Opens the old manifold (read-only to avoid more damage)
  2. Creates a new manifold with 2M nodes, 20M edges
  3. Copies all valid nodes with their snippets (skips junk)
  4. Copies all valid edges (skips corrupted region)
  5. Swaps the files

String table sizing: 2M * 128 = 256MB (was 1M * 64 = 64MB)
Total file size: ~736MB. Fine for 32GB RAM.

Usage:
    python scripts/expand_manifold.py [--dry-run] [--prune-bigrams]

Created: 2026-03-27, Nous + Ace
"""

import os
import sys
import time
import struct
import mmap
import argparse
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

OLD_PATH = Path(r"F:\Sandbox\failure_factory\akashic_v2\state\akashic\cortex.manifold")
NEW_PATH = Path(r"F:\Sandbox\failure_factory\akashic_v2\state\akashic\cortex.manifold.expanded")
BACKUP_PATH = Path(r"F:\Sandbox\failure_factory\akashic_v2\state\akashic\cortex.manifold.pre_expand")

# Struct formats (must match manifold_memory.py)
NODE_RECORD_SIZE = 64
NODE_STRUCT = struct.Struct('<IHHHHfIHfHBBIIHII16x')
EDGE_RECORD_SIZE = 24
EDGE_STRUCT = struct.Struct('<IIfBBIf2x')
HEADER_STRUCT = struct.Struct('<4sIIIQQQII')  # 48 bytes
HEADER_SIZE = 4096
FLAG_ACTIVE = 0    # 0 = active, 1 = deleted (inverted from typical usage)
FLAG_DELETED = 1

# New capacities
NEW_NODE_CAPACITY = 2_000_000
NEW_EDGE_CAPACITY = 20_000_000
# Override string table: 128 bytes per node instead of default 64
STRING_BYTES_PER_NODE = 128


def main():
    parser = argparse.ArgumentParser(description="Expand cortex manifold")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--prune-bigrams", action="store_true",
                        help="Skip bigram nodes with low activity (junk from failed ingestion)")
    args = parser.parse_args()

    new_string_table = NEW_NODE_CAPACITY * STRING_BYTES_PER_NODE
    new_node_table = NEW_NODE_CAPACITY * NODE_RECORD_SIZE
    new_edge_table = NEW_EDGE_CAPACITY * EDGE_RECORD_SIZE
    new_string_offset = HEADER_SIZE + new_node_table
    new_edge_offset = new_string_offset + new_string_table
    new_total = new_edge_offset + new_edge_table

    print("=" * 70)
    print("MANIFOLD EXPANSION")
    print(f"  Old: {OLD_PATH} ({OLD_PATH.stat().st_size / (1024**2):.0f}MB)")
    print(f"  New capacity: {NEW_NODE_CAPACITY:,} nodes, {NEW_EDGE_CAPACITY:,} edges")
    print(f"  String table: {new_string_table / (1024**2):.0f}MB")
    print(f"  Total size:   {new_total / (1024**2):.0f}MB")
    print(f"  Prune bigrams: {args.prune_bigrams}")
    print(f"  Dry run: {args.dry_run}")
    print("=" * 70)

    # Open old manifold raw (not through ManifoldMemory to avoid index rebuild overhead)
    print("\nReading old manifold header...")
    old_file = open(str(OLD_PATH), 'rb')
    old_mm = mmap.mmap(old_file.fileno(), 0, access=mmap.ACCESS_READ)
    old_header = HEADER_STRUCT.unpack(old_mm[:HEADER_STRUCT.size])
    old_magic = old_header[0]
    old_version = old_header[1]
    old_node_count = old_header[2]
    old_edge_count = old_header[3]
    old_string_offset = old_header[4]
    old_edge_offset = old_header[5]
    old_string_used = old_header[6]
    old_node_capacity = old_header[7]
    old_edge_capacity = old_header[8]

    old_string_table_alloc = old_node_capacity * 64  # Original allocation
    overflow = max(0, old_string_used - old_string_table_alloc)

    print(f"  Magic: {old_magic}")
    print(f"  Version: {old_version}")
    print(f"  Nodes: {old_node_count:,} / {old_node_capacity:,}")
    print(f"  Edges: {old_edge_count:,} / {old_edge_capacity:,}")
    print(f"  String table: {old_string_used:,} bytes used "
          f"({old_string_table_alloc:,} allocated)")
    print(f"  Overflow into edges: {overflow:,} bytes "
          f"(~{overflow // EDGE_RECORD_SIZE:,} edge slots corrupted)")

    if args.dry_run:
        print("\n[DRY RUN] Would create expanded manifold. Exiting.")
        old_mm.close()
        old_file.close()
        return

    # Create new file
    print(f"\nCreating new manifold file ({new_total / (1024**2):.0f}MB)...")
    t0 = time.time()

    if NEW_PATH.exists():
        NEW_PATH.unlink()

    with open(str(NEW_PATH), 'wb') as f:
        chunk = b'\x00' * (4 * 1024 * 1024)
        written = 0
        while written < new_total:
            size = min(len(chunk), new_total - written)
            f.write(chunk[:size])
            written += size
        f.flush()
    print(f"  Created in {time.time() - t0:.1f}s")

    new_file = open(str(NEW_PATH), 'r+b')
    new_mm = mmap.mmap(new_file.fileno(), new_total)

    # ── COPY NODES ──
    print("\nCopying nodes...")
    t1 = time.time()
    nodes_copied = 0
    nodes_pruned = 0
    new_string_used = 0
    slot_map = {}  # old_slot -> new_slot

    for old_slot in range(old_node_capacity):
        old_offset = HEADER_SIZE + old_slot * NODE_RECORD_SIZE
        raw = old_mm[old_offset:old_offset + NODE_RECORD_SIZE]
        if len(raw) < NODE_RECORD_SIZE:
            break

        try:
            fields = list(NODE_STRUCT.unpack(raw))
        except struct.error:
            continue

        flags = fields[9]
        if flags == FLAG_DELETED:
            continue

        # Read key
        key_off, key_len = fields[0], fields[1]
        if key_len == 0 or key_len > 5000:
            continue

        key_start = old_string_offset + key_off
        if key_start + key_len > len(old_mm):
            continue
        key_bytes = bytes(old_mm[key_start:key_start + key_len])

        try:
            key_str = key_bytes.decode('utf-8', errors='replace')
        except Exception:
            continue

        # Optional pruning of junk bigrams
        if args.prune_bigrams:
            activation = fields[5]
            count = fields[6]
            # Bigrams created by failed ingestion: low activation, low count,
            # contain underscore (bigram format)
            if '_' in key_str and count <= 2 and activation < 1.0:
                nodes_pruned += 1
                continue

        # Read snippet
        snip_off, snip_len = fields[12], fields[13]
        snippet_bytes = b''
        if snip_len > 0 and snip_len < 5000:
            snip_start = old_string_offset + snip_off
            if snip_start + snip_len <= len(old_mm):
                snippet_bytes = bytes(old_mm[snip_start:snip_start + snip_len])

        # Write key to new string table
        new_key_off = new_string_used
        dest = new_string_offset + new_key_off
        new_mm[dest:dest + key_len] = key_bytes
        new_string_used += key_len

        # Write snippet to new string table
        new_snip_off = 0
        new_snip_len = 0
        if snippet_bytes:
            new_snip_off = new_string_used
            new_snip_len = len(snippet_bytes)
            dest = new_string_offset + new_snip_off
            new_mm[dest:dest + new_snip_len] = snippet_bytes
            new_string_used += new_snip_len

        # Update node record with new string offsets
        fields[0] = new_key_off
        fields[1] = key_len
        fields[12] = new_snip_off
        fields[13] = new_snip_len

        # Write to new node table
        new_slot = nodes_copied
        slot_map[old_slot] = new_slot
        new_node_off = HEADER_SIZE + new_slot * NODE_RECORD_SIZE
        new_mm[new_node_off:new_node_off + NODE_RECORD_SIZE] = NODE_STRUCT.pack(*fields)

        nodes_copied += 1
        if nodes_copied % 200000 == 0:
            print(f"  {nodes_copied:,} nodes, "
                  f"{new_string_used / (1024**2):.1f}MB strings...", flush=True)

    print(f"  Nodes copied: {nodes_copied:,}")
    if args.prune_bigrams:
        print(f"  Nodes pruned: {nodes_pruned:,}")
    print(f"  Strings used: {new_string_used:,} bytes ({new_string_used / (1024**2):.1f}MB)")
    print(f"  Time: {time.time() - t1:.1f}s")

    # ── COPY EDGES ──
    print("\nCopying edges...")
    t2 = time.time()
    edges_copied = 0
    edges_corrupted = 0
    edges_orphaned = 0

    for old_edge_slot in range(old_edge_capacity):
        old_edge_start = old_edge_offset + old_edge_slot * EDGE_RECORD_SIZE
        if old_edge_start + EDGE_RECORD_SIZE > len(old_mm):
            break

        raw = old_mm[old_edge_start:old_edge_start + EDGE_RECORD_SIZE]
        try:
            e_fields = list(EDGE_STRUCT.unpack(raw))
        except struct.error:
            edges_corrupted += 1
            continue

        src, dst, weight = e_fields[0], e_fields[1], e_fields[2]
        e_flags = e_fields[4]

        # Skip inactive edges
        if e_flags == FLAG_DELETED:
            continue

        # Validate
        if src >= old_node_capacity or dst >= old_node_capacity:
            edges_corrupted += 1
            continue
        if weight <= 0 or weight > 100:
            edges_corrupted += 1
            continue

        # Remap slot IDs
        new_src = slot_map.get(src)
        new_dst = slot_map.get(dst)
        if new_src is None or new_dst is None:
            edges_orphaned += 1
            continue

        # Write to new edge table
        e_fields[0] = new_src
        e_fields[1] = new_dst

        new_edge_start = new_edge_offset + edges_copied * EDGE_RECORD_SIZE
        new_mm[new_edge_start:new_edge_start + EDGE_RECORD_SIZE] = EDGE_STRUCT.pack(*e_fields)
        edges_copied += 1

        if edges_copied % 1000000 == 0:
            print(f"  {edges_copied:,} edges...", flush=True)

    print(f"  Edges copied:    {edges_copied:,}")
    print(f"  Edges corrupted: {edges_corrupted:,}")
    print(f"  Edges orphaned:  {edges_orphaned:,}")
    print(f"  Time: {time.time() - t2:.1f}s")

    # ── WRITE HEADER ──
    header_data = HEADER_STRUCT.pack(
        b'MNFL',
        2,
        nodes_copied,
        edges_copied,
        new_string_offset,
        new_edge_offset,
        new_string_used,
        NEW_NODE_CAPACITY,
        NEW_EDGE_CAPACITY,
    )
    new_mm[:HEADER_STRUCT.size] = header_data

    new_mm.flush()
    new_mm.close()
    new_file.close()
    old_mm.close()
    old_file.close()

    elapsed = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"EXPANSION COMPLETE in {elapsed:.1f}s")
    print(f"  Nodes: {old_node_count:,} -> {nodes_copied:,}")
    print(f"  Edges: {old_edge_count:,} -> {edges_copied:,}")
    print(f"  Strings: {old_string_used / (1024**2):.1f}MB -> "
          f"{new_string_used / (1024**2):.1f}MB")
    print(f"  File: {NEW_PATH.stat().st_size / (1024**2):.0f}MB")
    print()

    # Swap files
    print("Swapping files...")
    os.rename(str(OLD_PATH), str(BACKUP_PATH))
    os.rename(str(NEW_PATH), str(OLD_PATH))
    print(f"  Old -> {BACKUP_PATH.name} (backup)")
    print(f"  Expanded -> cortex.manifold (live)")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
