"""
Backfill Embeddings — Encode all existing cortex nodes with semantic vectors.

One-time (or periodic) tool to give every concept node in the manifold a
384-dim embedding from sentence-transformers. After this, the cortex has
semantic understanding — not just keyword co-occurrence.

Usage:
    python backfill_embeddings.py [--manifold <path>] [--batch-size 32] [--dry-run]

Default manifold: state/portal_cortex.manifold
Companion file created: state/portal_cortex.manifold.embeddings

Expected time: ~83 seconds for 52K nodes (batch of 32, CUDA)

"((Cause + Affect) > Effect > Affect > infinity)"
"""

import os
import sys
import time
import argparse

# Add project root to path
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


def backfill(manifold_path: str, batch_size: int = 32, dry_run: bool = False):
    """Encode all nodes in the manifold with semantic embeddings."""

    from infrastructure.manifold_memory import ManifoldMemory
    from infrastructure.semantic_encoder import get_encoder

    # ── Open manifold ──
    print(f"Opening manifold: {manifold_path}")
    manifold = ManifoldMemory(manifold_path, readonly=dry_run)
    stats = manifold.status()
    print(f"  Nodes: {stats['nodes']:,}")
    print(f"  Edges: {stats['edges']:,}")
    print(f"  Capacity: {stats['node_capacity']:,}")

    # ── Check existing embeddings ──
    emb_stats = manifold.embedding_stats()
    print(f"  Embeddings: {emb_stats['embedded_nodes']:,} / {stats['nodes']:,} "
          f"({emb_stats['coverage']*100:.1f}% coverage)")

    if emb_stats['coverage'] >= 0.99 and not dry_run:
        print("  Already >99% embedded. Use --force to re-encode.")
        if '--force' not in sys.argv:
            manifold.close()
            return

    # ── Load encoder ──
    print("\nLoading semantic encoder...")
    encoder = get_encoder()
    if not encoder.is_loaded:
        print("ERROR: Encoder failed to load")
        manifold.close()
        return
    print(f"  {encoder.status()}")

    # ── Collect all node keys and slots ──
    keys_and_slots = []
    for key, slot in manifold._key_index.items():
        if not dry_run and manifold.has_embedding(slot):
            continue  # Skip already-embedded nodes
        keys_and_slots.append((key, slot))

    total = len(keys_and_slots)
    print(f"\nNodes to encode: {total:,}")

    if dry_run:
        print("(dry run — not writing)")
        # Just encode a sample to show it works
        sample_keys = [k for k, s in keys_and_slots[:5]]
        embs = encoder.encode_batch(sample_keys)
        print(f"Sample encoding ({len(sample_keys)} keys):")
        for i, key in enumerate(sample_keys):
            vec = embs[i]
            norm = vec.norm().item()
            print(f"  '{key}' -> norm={norm:.3f}, first 5 dims: {vec[:5].tolist()}")
        manifold.close()
        return

    if total == 0:
        print("Nothing to encode!")
        manifold.close()
        return

    # ── Batch encode and write ──
    t0 = time.time()
    encoded = 0
    errors = 0

    for batch_start in range(0, total, batch_size):
        batch = keys_and_slots[batch_start:batch_start + batch_size]
        batch_keys = [k for k, s in batch]
        batch_slots = [s for k, s in batch]

        try:
            embeddings = encoder.encode_batch(batch_keys, batch_size=batch_size)
            if embeddings is None:
                errors += len(batch)
                continue

            for i, slot in enumerate(batch_slots):
                ok = manifold.write_embedding(slot, embeddings[i])
                if ok:
                    encoded += 1
                else:
                    errors += 1

        except Exception as e:
            print(f"  Batch error at {batch_start}: {e}")
            errors += len(batch)

        # Progress
        done = batch_start + len(batch)
        if done % (batch_size * 10) == 0 or done == total:
            elapsed = time.time() - t0
            rate = done / max(0.001, elapsed)
            eta = (total - done) / max(0.001, rate)
            print(f"  {done:,}/{total:,} ({done*100/total:.0f}%) "
                  f"— {rate:.0f} nodes/sec, ETA {eta:.0f}s")

    # ── Flush and report ──
    manifold.flush()
    t1 = time.time()

    final_stats = manifold.embedding_stats()
    print(f"\n{'='*50}")
    print(f"DONE in {t1-t0:.1f}s")
    print(f"  Encoded: {encoded:,}")
    print(f"  Errors: {errors:,}")
    print(f"  Coverage: {final_stats['embedded_nodes']:,}/{stats['nodes']:,} "
          f"({final_stats['coverage']*100:.1f}%)")
    print(f"  Embedding file: {final_stats['file_size_mb']}MB")
    print(f"  Rate: {encoded / max(0.001, t1-t0):.0f} nodes/sec")

    manifold.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill cortex node embeddings")
    parser.add_argument("--manifold", default=None,
                        help="Path to .manifold file")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="Re-encode even if already embedded")
    args = parser.parse_args()

    if args.manifold is None:
        args.manifold = os.path.join(_root, "state", "portal_cortex.manifold")

    if not os.path.exists(args.manifold):
        print(f"Manifold not found: {args.manifold}")
        sys.exit(1)

    backfill(args.manifold, batch_size=args.batch_size, dry_run=args.dry_run)
