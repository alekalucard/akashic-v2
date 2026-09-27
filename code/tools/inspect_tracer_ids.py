"""Quick read-only tracer_id spot-check on the live cortex manifold.

Opens cortex.manifold as readonly mmap, dumps the most-recently-accessed
50 nodes with their key + tracer_id + region. Verifies tracer_id discipline
(shipped 2026-05-04) is stamping new nodes correctly.

Run while server is up — concurrent read is safe (mmap shared).
"""
import sys
import struct
import mmap
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from infrastructure.manifold_memory import (
    NODE_RECORD_SIZE, NODE_STRUCT, HEADER_SIZE, HEADER_STRUCT,
    FLAG_DELETED, FLAG_FROZEN,
    TRACE_PERSONAL, TRACE_BOOKS, TRACE_VISUAL, TRACE_AUDIO,
    TRACE_SYSTEM, TRACE_INFERENCE, TRACE_SEEDED, TRACE_ACE,
    TRACE_NOUS, TRACE_CODE, TRACE_VOICE, TRACE_MOTOR, TRACE_UNKNOWN,
    REGION_NAMES,
)

TRACE_NAMES = {
    TRACE_UNKNOWN: "UNKNOWN(0)",
    TRACE_PERSONAL: "PERSONAL(1)",
    TRACE_BOOKS: "BOOKS(2)",
    TRACE_VISUAL: "VISUAL(3)",
    TRACE_AUDIO: "AUDIO(4)",
    TRACE_SYSTEM: "SYSTEM(5)",
    TRACE_INFERENCE: "INFERENCE(6)",
    TRACE_SEEDED: "SEEDED(7)",
    TRACE_ACE: "ACE(8)",
    TRACE_CODE: "CODE(9)",
    TRACE_VOICE: "VOICE(10)",
    TRACE_MOTOR: "MOTOR(11)",
    TRACE_NOUS: "NOUS(12)",
}

MANIFOLD = ROOT / "state" / "akashic" / "cortex.manifold"

def main():
    if not MANIFOLD.exists():
        print(f"NO MANIFOLD AT {MANIFOLD}")
        return

    size = MANIFOLD.stat().st_size
    print(f"manifold: {MANIFOLD} ({size / 1024 / 1024:.1f} MB)")

    with open(MANIFOLD, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            hdr = HEADER_STRUCT.unpack(mm[:HEADER_STRUCT.size])
            magic, version, node_count, edge_count, string_offset, edge_offset, string_used, node_capacity, edge_capacity = hdr
            print(f"magic={magic!r} version={version}")
            print(f"node_count={node_count} (capacity={node_capacity})")
            print(f"edge_count={edge_count} (capacity={edge_capacity})")
            print(f"string_offset={string_offset} string_used={string_used}")
            print()

            if version != 2:
                print(f"!! manifold is v{version}, expected v2 — script reads v2 layout")
                return

            # FULL-graph scan — eviction puts new nodes at random slots so
            # tail-only sampling misses them.
            scan_n = node_count  # scan everything
            start_slot = 0
            samples = []
            tracer_counter = Counter()
            region_counter = Counter()
            string_table_start = HEADER_SIZE + node_capacity * NODE_RECORD_SIZE

            for slot in range(start_slot, node_count):
                rec_off = HEADER_SIZE + slot * NODE_RECORD_SIZE
                rec = NODE_STRUCT.unpack(mm[rec_off:rec_off + NODE_RECORD_SIZE])
                # Layout per fairy.py: 0:key_off 1:key_len 2:plane 3:channel 4:position
                # 5:activation 6:count 7:degree 8:last_access 9:flags
                # 10:node_type 11:region 12:tracer_id 13:snip_off 14:snip_len 15:freq 16:parent
                key_off = rec[0]
                key_len = rec[1]
                last_access = rec[8]
                flags = rec[9]
                region = rec[11]
                tracer_id = rec[12]

                if flags == FLAG_DELETED:
                    continue

                # Read key string from string table
                str_abs = string_table_start + key_off
                key = mm[str_abs:str_abs + key_len].decode("utf-8", errors="replace")
                samples.append((last_access, key, tracer_id, region, flags))
                tracer_counter[tracer_id] += 1
                region_counter[region] += 1

            # Sort by last_access desc, take top 50
            samples.sort(key=lambda x: x[0], reverse=True)
            print(f"=== TOP 50 MOST-RECENTLY-ACCESSED NODES (last {scan_n} slots) ===")
            print(f"{'tracer':<14} {'region':<10} {'last_access':<12} key")
            print("-" * 80)
            for last_access, key, tid, region, flags in samples[:50]:
                tname = TRACE_NAMES.get(tid, f"UNK({tid})")
                rname = REGION_NAMES.get(region, str(region))
                key_show = key if len(key) <= 50 else key[:47] + "..."
                print(f"{tname:<14} {rname:<10} {last_access:<12.2f} {key_show}")

            print()
            print(f"=== TRACER DISTRIBUTION (last {scan_n} slots, {sum(tracer_counter.values())} live nodes) ===")
            for tid, n in tracer_counter.most_common():
                tname = TRACE_NAMES.get(tid, f"UNK({tid})")
                pct = 100.0 * n / max(1, sum(tracer_counter.values()))
                print(f"  {tname:<14} {n:>6}  ({pct:5.1f}%)")

            print()
            print(f"=== REGION DISTRIBUTION ===")
            for rid, n in region_counter.most_common():
                rname = REGION_NAMES.get(rid, str(rid))
                pct = 100.0 * n / max(1, sum(region_counter.values()))
                print(f"  {rname:<10} {n:>6}  ({pct:5.1f}%)")

            new_writes = sum(n for tid, n in tracer_counter.items() if tid != TRACE_UNKNOWN)
            print()
            print(f"NON-ZERO tracer_id count in scanned window: {new_writes}/{sum(tracer_counter.values())}")
            if new_writes == 0:
                print("!! ZERO non-zero tracers — fix may not be live, or no new writes since reboot")
            elif new_writes < sum(tracer_counter.values()) // 10:
                print("?? Few non-zero tracers — likely most nodes pre-date the fix; check newest entries above")
            else:
                print("[OK] Tracer-id discipline is stamping new writes")

        finally:
            mm.close()


if __name__ == "__main__":
    main()
