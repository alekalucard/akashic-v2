"""
Migrate Manifold v1 (32-byte nodes, 16-byte edges) ->v2 (64-byte nodes, 24-byte edges).

Reads the existing cortex.manifold, creates a new v2 file, copies all nodes and edges
with the expanded struct. Existing data (key, coords, activation, weight, rel_type) is
preserved. New fields (snippet, node_type, region, tracer_id, frequency, parent_slot,
created_at) are initialized to defaults.

Usage:
    python scripts/migrate_manifold_v2.py [--manifold path/to/cortex.manifold] [--dry-run]

The old file is backed up as .v1_backup before the new file takes its place.

2026-03-20, Nous — Co-founder, Akashic Foundation
"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import os
import sys
import struct
import time
import shutil
import argparse

# Add project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── v1 constants ────────────────────────────────────────────────────────────
MAGIC = b'MNFL'
HEADER_SIZE = 4096
HEADER_STRUCT = struct.Struct('<4sIIIQQQII')

NODE_V1_SIZE = 32
NODE_V1 = struct.Struct('<IHHHHfIHfH4x')
# key_off(4) key_len(2) plane(2) chan(2) pos(2) act(4) cnt(4) deg(2) la(4) flags(2) pad(4)

EDGE_V1_SIZE = 16
EDGE_V1 = struct.Struct('<IIfBB2x')
# node_a(4) node_b(4) weight(4) rel_type(1) flags(1) pad(2)

# ── v2 constants ────────────────────────────────────────────────────────────
NODE_V2_SIZE = 64
NODE_V2 = struct.Struct('<IHHHHfIHfHBBIIHII16x')
# Same as v1 fields + node_type(1) region(1) tracer_id(4) snip_off(4) snip_len(2)
#                      frequency(4) parent_slot(4) reserved(16)

EDGE_V2_SIZE = 24
EDGE_V2 = struct.Struct('<IIfBBIf2x')
# node_a(4) node_b(4) weight(4) rel_type(1) flags(1) tracer_id(4) created_at(4) pad(2)

VERSION_V1 = 1
VERSION_V2 = 2


def migrate(manifold_path: str, dry_run: bool = False):
    """Migrate a v1 manifold to v2 format."""
    if not os.path.exists(manifold_path):
        print(f"ERROR: File not found: {manifold_path}")
        return False

    file_size = os.path.getsize(manifold_path)
    print(f"Reading: {manifold_path} ({file_size / (1024*1024):.1f} MB)")

    # ── Read header ──
    with open(manifold_path, 'rb') as f:
        header_raw = f.read(HEADER_SIZE)

    hdr = HEADER_STRUCT.unpack(header_raw[:HEADER_STRUCT.size])
    magic, version = hdr[0], hdr[1]

    if magic != MAGIC:
        print(f"ERROR: Not a manifold file (magic={magic})")
        return False

    if version == VERSION_V2:
        print("Already v2 — nothing to migrate.")
        return True

    if version != VERSION_V1:
        print(f"ERROR: Unknown version {version}")
        return False

    node_count = hdr[2]
    edge_count = hdr[3]
    string_offset = hdr[4]
    edge_offset = hdr[5]
    string_used = hdr[6]
    node_capacity = hdr[7]
    edge_capacity = hdr[8]

    print(f"v1 manifold: {node_count} nodes (cap {node_capacity}), "
          f"{edge_count} edges (cap {edge_capacity}), "
          f"{string_used} bytes strings")

    # ── Read all v1 data ──
    with open(manifold_path, 'rb') as f:
        # Read entire file
        raw = f.read()

    # Parse all v1 nodes
    nodes = []
    for slot in range(node_capacity):
        offset = HEADER_SIZE + slot * NODE_V1_SIZE
        record = NODE_V1.unpack(raw[offset:offset + NODE_V1_SIZE])
        nodes.append(record)

    # Read string table
    string_table = raw[string_offset:string_offset + string_used]

    # Parse all v1 edges
    edges = []
    for slot in range(edge_count):
        offset = edge_offset + slot * EDGE_V1_SIZE
        record = EDGE_V1.unpack(raw[offset:offset + EDGE_V1_SIZE])
        edges.append(record)

    active_nodes = sum(1 for n in nodes if n[1] > 0 and n[9] != 1)  # key_len > 0, not deleted
    active_edges = sum(1 for e in edges if e[4] != 1)  # not deleted

    print(f"Parsed: {active_nodes} active nodes, {active_edges} active edges")

    if dry_run:
        # Calculate what the new file would look like
        new_node_table = node_capacity * NODE_V2_SIZE
        new_string_offset = HEADER_SIZE + new_node_table
        # String table stays same size (we give it more room)
        new_string_table_size = max(string_used * 2, node_capacity * 128)
        new_edge_offset = new_string_offset + new_string_table_size
        new_edge_table = edge_capacity * EDGE_V2_SIZE
        new_total = new_edge_offset + new_edge_table

        print(f"\n--- DRY RUN ---")
        print(f"Old file: {file_size / (1024*1024):.1f} MB")
        print(f"New file: {new_total / (1024*1024):.1f} MB")
        print(f"Node table: {node_capacity * NODE_V1_SIZE / (1024*1024):.1f} MB ->"
              f"{new_node_table / (1024*1024):.1f} MB")
        print(f"Edge table: {edge_count * EDGE_V1_SIZE / (1024*1024):.1f} MB ->"
              f"{edge_count * EDGE_V2_SIZE / (1024*1024):.1f} MB")
        print(f"String table: {string_used / 1024:.1f} KB (room for {new_string_table_size / 1024:.0f} KB)")
        return True

    # ── Build v2 file ──
    print("Building v2 manifold...")

    new_node_table_size = node_capacity * NODE_V2_SIZE
    new_string_offset = HEADER_SIZE + new_node_table_size
    # Give string table generous room for snippets (128 bytes avg per node)
    new_string_table_size = max(string_used * 2, node_capacity * 128)
    new_edge_offset = new_string_offset + new_string_table_size
    new_edge_table_size = edge_capacity * EDGE_V2_SIZE
    new_total_size = new_edge_offset + new_edge_table_size

    print(f"New file size: {new_total_size / (1024*1024):.1f} MB")

    # Create new file
    new_path = manifold_path + ".v2_migrating"
    with open(new_path, 'wb') as f:
        # Write zeros
        f.write(b'\x00' * new_total_size)

    # Open for writing
    with open(new_path, 'r+b') as f:
        import mmap
        mm = mmap.mmap(f.fileno(), new_total_size)

        # ── Write v2 header ──
        new_header = HEADER_STRUCT.pack(
            MAGIC, VERSION_V2,
            node_count, edge_count,
            new_string_offset, new_edge_offset,
            string_used,
            node_capacity, edge_capacity,
        )
        mm[0:HEADER_STRUCT.size] = new_header

        # ── Copy string table (unchanged) ──
        mm[new_string_offset:new_string_offset + string_used] = string_table
        print(f"  String table: {string_used} bytes copied")

        # ── Convert nodes v1 ->v2 ──
        converted_nodes = 0
        for slot in range(node_capacity):
            v1 = nodes[slot]
            # v1: (key_off, key_len, plane, chan, pos, act, cnt, deg, la, flags)
            # v2: same + node_type(0), region(1=semantic), tracer_id(0),
            #           snippet_off(0), snippet_len(0), frequency(cnt), parent_slot(0)

            v2_data = NODE_V2.pack(
                v1[0],   # key_offset
                v1[1],   # key_len
                v1[2],   # coord_plane
                v1[3],   # coord_channel
                v1[4],   # coord_position
                v1[5],   # activation
                v1[6],   # count
                v1[7],   # degree
                v1[8],   # last_access
                v1[9],   # flags
                0,       # node_type = CONCEPT (default)
                1,       # region = SEMANTIC (default, safest for existing data)
                0,       # tracer_id = 0 (no provenance yet)
                0,       # snippet_offset = 0 (no snippet yet)
                0,       # snippet_len = 0
                v1[6],   # frequency = count (reasonable initial value)
                0,       # parent_slot = 0
            )

            offset = HEADER_SIZE + slot * NODE_V2_SIZE
            mm[offset:offset + NODE_V2_SIZE] = v2_data

            if v1[1] > 0 and v1[9] != 1:  # has key and not deleted
                converted_nodes += 1

        print(f"  Nodes: {converted_nodes} converted ({node_capacity} slots)")

        # ── Convert edges v1 ->v2 ──
        now_relative = time.time() % 1e6
        converted_edges = 0
        for slot in range(edge_count):
            v1 = edges[slot]
            # v1: (node_a, node_b, weight, rel_type, flags)
            # v2: same + tracer_id(0), created_at(now)

            v2_data = EDGE_V2.pack(
                v1[0],          # node_a
                v1[1],          # node_b
                v1[2],          # weight
                v1[3],          # rel_type
                v1[4],          # flags
                0,              # tracer_id = 0 (no provenance)
                now_relative,   # created_at = migration time
            )

            offset = new_edge_offset + slot * EDGE_V2_SIZE
            mm[offset:offset + EDGE_V2_SIZE] = v2_data

            if v1[4] != 1:  # not deleted
                converted_edges += 1

        print(f"  Edges: {converted_edges} converted ({edge_count} slots)")

        mm.flush()
        mm.close()

    # ── Swap files ──
    backup_path = manifold_path + ".v1_backup"
    print(f"Backing up: {manifold_path} ->{backup_path}")
    shutil.copy2(manifold_path, backup_path)

    print(f"Replacing: {new_path} ->{manifold_path}")
    os.replace(new_path, manifold_path)

    new_size = os.path.getsize(manifold_path)
    print(f"\nMigration complete!")
    print(f"  Old: {file_size / (1024*1024):.1f} MB (v1, 32-byte nodes, 16-byte edges)")
    print(f"  New: {new_size / (1024*1024):.1f} MB (v2, 64-byte nodes, 24-byte edges)")
    print(f"  Backup: {backup_path}")
    print(f"  Nodes: {converted_nodes} active, {node_capacity} capacity")
    print(f"  Edges: {converted_edges} active, {edge_capacity} capacity")
    print(f"  New fields: node_type, region, tracer_id, snippet, frequency, parent_slot")
    print(f"  New edge fields: tracer_id, created_at")
    print(f"  Rel types expanded: 4 ->28 (coactivate through holding)")

    # ── Verify by opening with ManifoldMemory ──
    try:
        from infrastructure.manifold_memory import ManifoldMemory
        mm = ManifoldMemory(manifold_path, readonly=True)
        status = mm.status()
        print(f"\nVerification: {status['nodes']} nodes, {status['edges']} edges — OK")
        mm.close()
    except Exception as e:
        print(f"\nVerification failed: {e}")
        print("The backup is at: {backup_path}")
        return False

    return True


# ── Also migrate the embeddings companion file if it exists ──
# The embeddings file is indexed by node slot (slot * 768 bytes).
# Since node slots DON'T CHANGE (same capacity, same slot assignment),
# the embeddings file is COMPATIBLE as-is. No migration needed.


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate manifold v1 ->v2")
    parser.add_argument("--manifold", default=None,
                        help="Path to cortex.manifold (default: auto-detect)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without modifying files")
    args = parser.parse_args()

    if args.manifold:
        path = args.manifold
    else:
        # Auto-detect
        candidates = [
            os.path.join("state", "akashic", "cortex.manifold"),
            os.path.join("..", "state", "akashic", "cortex.manifold"),
        ]
        path = None
        for c in candidates:
            if os.path.exists(c):
                path = c
                break
        if not path:
            print("ERROR: Could not find cortex.manifold. Use --manifold to specify path.")
            sys.exit(1)

    success = migrate(path, dry_run=args.dry_run)
    sys.exit(0 if success else 1)
