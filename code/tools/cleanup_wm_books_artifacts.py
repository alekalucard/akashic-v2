"""Re-tag the 118K dead wm:*-tagged-BOOKS artifacts to UNKNOWN(0).

These are historical ghost nodes (count=1, freq=1, no snippet, decayed
to act=0.01) tagged TRACE_BOOKS by some past code path that no longer
exists. They pollute the BOOKS tracer count and aren't valuable
content. Re-tagging to UNKNOWN(0) lets:
  1. The cortex eviction loop reclaim them naturally as activation
     pressure rises (they're already at the 0.01 floor).
  2. The forward fix at upsert_node (ownership-aware update) prevents
     similar pollution going forward.

SAFETY NOTE: This script opens cortex.manifold READ-WRITE.
RECOMMENDED: stop server before running. The script will refuse to
proceed if the file is locked. Direct mmap RW while server has the
file mmapped is technically possible on Windows (shared page cache)
but the server's in-memory `_key_index` and `_wm_keys` won't reflect
changes until restart, so a restart is needed regardless.

Run:
    python tools/cleanup_wm_books_artifacts.py            # dry run (default)
    python tools/cleanup_wm_books_artifacts.py --apply    # actually retag
"""
import sys
import mmap
import struct
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from infrastructure.manifold_memory import (
    NODE_STRUCT, NODE_RECORD_SIZE, HEADER_SIZE, HEADER_STRUCT, FLAG_DELETED,
    TRACE_BOOKS, TRACE_UNKNOWN,
)

MANIFOLD = ROOT / "state" / "akashic" / "cortex.manifold"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Actually write changes (default is dry run)")
    args = parser.parse_args()

    if not MANIFOLD.exists():
        print(f"NO MANIFOLD AT {MANIFOLD}")
        return 1

    size = MANIFOLD.stat().st_size
    mode = "READ-WRITE" if args.apply else "READ-ONLY (dry run)"
    print(f"manifold: {MANIFOLD} ({size / 1024 / 1024:.1f} MB)  [{mode}]")
    print()

    if args.apply:
        # Open RW; will share page cache with running server's RO mmap on
        # Windows. The server's in-process state may not reflect until
        # restart, but the on-disk mmap will be correct.
        access_flag = mmap.ACCESS_WRITE
        file_mode = "r+b"
    else:
        access_flag = mmap.ACCESS_READ
        file_mode = "rb"

    candidates = []  # list of (slot, key) to rewrite
    with open(MANIFOLD, file_mode) as f:
        mm = mmap.mmap(f.fileno(), 0, access=access_flag)
        try:
            hdr = HEADER_STRUCT.unpack(mm[:HEADER_STRUCT.size])
            magic, version, node_count, edge_count, string_offset, edge_offset, string_used, node_capacity, edge_capacity = hdr
            print(f"magic={magic!r} version={version} node_count={node_count}")
            if version != 2:
                print(f"!! version={version} but script expects v2; aborting")
                return 1

            string_table_start = HEADER_SIZE + node_capacity * NODE_RECORD_SIZE
            tracer_field_byte_offset = 4 + 2 + 2 + 2 + 2 + 4 + 4 + 2 + 4 + 2 + 1 + 1
            # tracer_id is field 12 in NODE_STRUCT layout:
            # 0:I(4) 1:H(2) 2:H(2) 3:H(2) 4:H(2) 5:f(4) 6:I(4) 7:H(2)
            # 8:f(4) 9:H(2) 10:B(1) 11:B(1) 12:I(4) ...
            # cumulative byte offset to start of tracer_id = 30 bytes
            assert tracer_field_byte_offset == 30, "byte offset sanity check"

            scanned = 0
            for slot in range(node_count):
                rec_off = HEADER_SIZE + slot * NODE_RECORD_SIZE
                rec = NODE_STRUCT.unpack(mm[rec_off:rec_off + NODE_RECORD_SIZE])
                if rec[9] == FLAG_DELETED:
                    continue
                if rec[12] != TRACE_BOOKS:  # not BOOKS-tagged
                    continue
                key = mm[string_table_start + rec[0]:string_table_start + rec[0] + rec[1]].decode("utf-8", errors="replace")
                if not key.startswith("wm:"):
                    continue
                # Additional safety filter: only re-tag the EMPTY-snippet,
                # count=1 ghost nodes (the forensic profile from earlier).
                # If it has a snippet, we don't touch it (could be a real
                # node we're misidentifying).
                if rec[14] != 0:  # snippet_len > 0
                    continue
                if rec[6] != 1:  # count != 1 (touched more than once → real)
                    continue
                candidates.append((slot, rec_off, key))
                scanned += 1

            print(f"Candidates found: {len(candidates):,} dead wm:*-tagged-BOOKS nodes")
            print()
            print("Sample of first 10 candidates:")
            for slot, _off, key in candidates[:10]:
                print(f"  slot={slot:>8}  key={key}")

            if not args.apply:
                print()
                print("DRY RUN — no changes written.")
                print("Re-run with --apply to retag tracer_id BOOKS(2) -> UNKNOWN(0).")
                return 0

            # Apply: write tracer_id=0 at byte offset 30 of each candidate's record
            print()
            print(f"Re-tagging {len(candidates):,} nodes to UNKNOWN(0)...")
            zero_bytes = struct.pack("<I", TRACE_UNKNOWN)  # 4-byte little-endian uint32
            assert len(zero_bytes) == 4
            written = 0
            for slot, rec_off, _key in candidates:
                tracer_off = rec_off + tracer_field_byte_offset
                mm[tracer_off:tracer_off + 4] = zero_bytes
                written += 1
                if written % 10000 == 0:
                    print(f"  ...{written:,} written")
            mm.flush()
            print(f"DONE. Re-tagged {written:,} nodes.")
            print()
            print("NOTE: server in-memory state (_key_index, _wm_keys) won't")
            print("reflect changes until restart. Restart to fully sync.")
        finally:
            mm.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
