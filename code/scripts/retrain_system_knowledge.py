"""
Retrain System Knowledge into Manifold Cortex (v2 Schema).

Re-processes all 116K+ system knowledge cards from ebook_copy with proper
v2 fields: descriptive snippets, node_types, typed edges, domain tags.

The original training (2026-03-18) created bare nodes via cortex.train_batch
postal route. The phonics seed then overwrote their snippets with phoneme
decompositions. This script restores the REAL snippets — what Python IS,
what hydrogen IS, what a game engine DOES — while preserving the phoneme
edges that already exist.

Domains (116K cards):
  programming:        40,823 (600+ languages, frameworks, concepts)
  gamedev:            22,852 (Unity, Unreal, Godot, game design, etc.)
  engineering:        14,384 (electrical, mechanical, software, etc.)
  chemistry:          11,147 (periodic table, reactions, compounds)
  media:               9,388 (skipped — image metadata only)
  philosophy:          5,301 (ethics, epistemology, metaphysics)
  graphics:            2,672 (3D, rendering, shaders, etc.)
  literature:            214 (books, literary concepts)
  akashic_foundation:    140 (core Akashic documents)

Usage:
    python scripts/retrain_system_knowledge.py [--manifold path] [--dry-run]
    python scripts/retrain_system_knowledge.py --domain chemistry
    python scripts/retrain_system_knowledge.py --max-files 5000

2026-03-20, Nous + Ace -- Akashic Foundation
"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import os
import sys
import json
import time
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from infrastructure.manifold_memory import (
    ManifoldMemory,
    NTYPE_CONCEPT,
    REGION_SEMANTIC,
    REL_SEMANTIC, REL_IS_A, REL_PART_OF,
)


# ── Domain → default data paths ──
KNOWLEDGE_BASES = [
    os.path.join("..", "ebook_copy", "P10_Memory",
                 "Akashic_triple_helix_memory_storage", "system"),
    os.path.join("ebook_copy", "P10_Memory",
                 "Akashic_triple_helix_memory_storage", "system"),
    # Fallback to relative from F:\Sandbox\failure_factory
    os.path.join("..", "..", "ebook_copy", "P10_Memory",
                 "Akashic_triple_helix_memory_storage", "system"),
]

DOMAIN_ORDER = [
    'akashic_foundation', 'literature', 'graphics', 'philosophy',
    'chemistry', 'engineering', 'gamedev', 'programming',
]

SKIP_DOMAINS = {'media'}  # Image metadata only, no text content


def find_knowledge_base():
    """Find the system knowledge base directory."""
    for path in KNOWLEDGE_BASES:
        if os.path.isdir(path):
            return path
    return None


def extract_card(filepath: str) -> dict:
    """Extract knowledge from a system knowledge card.

    Returns dict with: key, snippet, domain, tags, or None if not extractable.
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    inner = data.get('data', {})
    meta = data.get('meta', {})

    if not isinstance(inner, dict):
        return None

    # Primary format: scraped knowledge (query + response)
    if 'query' in inner and 'response' in inner:
        query = inner['query'].strip()
        response = inner['response'].strip()
        domain = inner.get('domain', meta.get('domain', ''))
        title = meta.get('title', meta.get('parent_title', ''))
        section = meta.get('section', '')

        if not query or len(query) < 5:
            return None

        # Build key from query (cleaned, lowercase, underscored)
        key = query.lower()
        key = ''.join(c if c.isalnum() or c == ' ' else '' for c in key)
        key = '_'.join(key.split()[:8])  # Max 8 words
        if not key or len(key) < 3:
            return None

        # Build rich snippet
        snippet = f"{query}"
        if response and len(response) > 10:
            # Truncate response to fit in snippet
            max_resp = 400 - len(snippet)
            if max_resp > 30:
                snippet += f" — {response[:max_resp]}"

        tags = [domain] if domain else []
        if title:
            tags.append(title.lower().replace(' ', '_')[:30])

        return {
            "key": key,
            "snippet": snippet[:500],
            "domain": domain,
            "tags": tags,
        }

    # Secondary format: content-based (literature, foundation docs)
    if 'content' in inner:
        content = inner['content'].strip()
        title = inner.get('title', '')
        domain = meta.get('domain', 'unknown')

        if not content or len(content) < 20:
            return None

        key = title.lower() if title else content[:50].lower()
        key = ''.join(c if c.isalnum() or c == ' ' else '' for c in key)
        key = '_'.join(key.split()[:8])

        snippet = f"{title} — {content[:400]}" if title else content[:500]

        return {
            "key": key,
            "snippet": snippet[:500],
            "domain": domain,
            "tags": [domain],
        }

    # Tertiary: title/purpose (akashic_foundation)
    if 'title' in inner or 'purpose' in inner:
        title = inner.get('title', '')
        purpose = inner.get('purpose', '')
        desc = inner.get('description', '')
        text = f"{title} {purpose} {desc}".strip()

        if len(text) < 20:
            return None

        key = (title or purpose)[:50].lower()
        key = ''.join(c if c.isalnum() or c == ' ' else '' for c in key)
        key = '_'.join(key.split()[:8])

        return {
            "key": key,
            "snippet": text[:500],
            "domain": "akashic_foundation",
            "tags": ["akashic", "foundation"],
        }

    return None


def process_domain(graph, base_path: str, domain: str, stats: dict,
                   dry_run: bool = False, max_files: int = 0):
    """Process all cards in a knowledge domain."""
    domain_path = os.path.join(base_path, domain)
    if not os.path.isdir(domain_path):
        print(f"  SKIP: {domain} (not found)")
        return

    # Collect all JSON files
    files = []
    for dirpath, dirs, filenames in os.walk(domain_path):
        for fn in filenames:
            if fn.endswith('.json'):
                files.append(os.path.join(dirpath, fn))
                if max_files and len(files) >= max_files:
                    break
        if max_files and len(files) >= max_files:
            break

    domain_key = f"domain:{domain}"
    if not dry_run:
        graph.upsert_node(
            key=domain_key,
            activation=3.0,
            count=200,
            snippet=f"Knowledge domain: {domain} — {len(files)} cards",
            node_type=NTYPE_CONCEPT,
            region=REGION_SEMANTIC,
        )
        stats["nodes"] += 1

    processed = 0
    for i, fpath in enumerate(files):
        card = extract_card(fpath)
        if card is None:
            stats["skipped"] += 1
            continue

        key = card["key"]
        snippet = card["snippet"]

        if dry_run:
            stats["nodes"] += 1
            stats["edges"] += 1 + len(card["tags"])
            stats["snippets_bytes"] += len(snippet.encode('utf-8'))
            processed += 1
            continue

        # Upsert the concept node with real snippet
        slot = graph.upsert_node(
            key=key,
            activation=1.0,
            count=1,
            snippet=snippet,
            node_type=NTYPE_CONCEPT,
            region=REGION_SEMANTIC,
        )
        if slot < 0:
            stats["failed"] += 1
            continue

        stats["nodes"] += 1
        stats["snippets_bytes"] += len(snippet.encode('utf-8'))

        # Link to domain
        if graph.link(key, domain_key, weight=0.5, rel_type=REL_IS_A):
            stats["edges"] += 1

        # Link to tags
        for tag in card["tags"][:5]:
            tag_key = f"tag:{tag}"
            if graph.link(key, tag_key, weight=0.4, rel_type=REL_SEMANTIC):
                stats["edges"] += 1

        processed += 1

        # Progress every 5000
        if processed % 5000 == 0:
            graph._write_header()
            print(f"    [{domain}] {processed}/{len(files)} — "
                  f"{stats['nodes']} nodes, {stats['edges']} edges")

    return processed


def main():
    parser = argparse.ArgumentParser(
        description="Retrain system knowledge into cortex (v2 schema)"
    )
    parser.add_argument("--manifold", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--domain", default=None,
                        help="Train single domain (e.g. chemistry)")
    parser.add_argument("--max-files", type=int, default=0,
                        help="Max files per domain (0=all)")
    parser.add_argument("--batch-save", type=int, default=10000,
                        help="Save header every N nodes")
    args = parser.parse_args()

    # Find manifold
    manifold_path = args.manifold
    if not manifold_path:
        for c in ["state/akashic/cortex.manifold",
                   "../state/akashic/cortex.manifold"]:
            if os.path.exists(c):
                manifold_path = c
                break
    if not manifold_path and not args.dry_run:
        print("ERROR: Could not find cortex.manifold")
        sys.exit(1)

    # Find knowledge base
    base_path = find_knowledge_base()
    if not base_path:
        print("ERROR: Could not find system knowledge base")
        print("Expected at: ebook_copy/P10_Memory/Akashic_triple_helix_memory_storage/system/")
        sys.exit(1)
    print(f"Knowledge base: {base_path}")

    # Determine domains to process
    if args.domain:
        domains = [args.domain]
    else:
        domains = [d for d in DOMAIN_ORDER if d not in SKIP_DOMAINS]

    stats = {
        "nodes": 0, "edges": 0, "failed": 0, "skipped": 0,
        "snippets_bytes": 0,
    }

    if args.dry_run:
        print("\n--- DRY RUN ---")
        graph = None
    else:
        file_size = os.path.getsize(manifold_path)
        print(f"\nOpening manifold: {manifold_path} ({file_size / (1024*1024):.1f} MB)")
        graph = ManifoldMemory(manifold_path)
        before = graph.status()
        print(f"  Before: {before['nodes']:,} nodes, {before['edges']:,} edges")

    print(f"\nRetraining system knowledge ({len(domains)} domains)...")
    t0 = time.time()

    for domain in domains:
        d0 = time.time()
        n0, e0 = stats["nodes"], stats["edges"]
        print(f"\n  [{domain}] Processing...")
        process_domain(graph, base_path, domain, stats,
                       dry_run=args.dry_run, max_files=args.max_files)
        dn, de = stats["nodes"] - n0, stats["edges"] - e0
        dt = time.time() - d0
        print(f"  [{domain}] Done: {dn} nodes, {de} edges in {dt:.1f}s")

        if graph and not args.dry_run:
            graph._write_header()

    elapsed = time.time() - t0

    if graph and not args.dry_run:
        graph._write_header()
        after = graph.status()
        print(f"\n  After: {after['nodes']:,} nodes, {after['edges']:,} edges")
        graph.close()

    print(f"\nRetraining complete in {elapsed:.1f}s")
    print(f"\n--- Summary ---")
    print(f"  Nodes created/updated: {stats['nodes']}")
    print(f"  Edges created:         {stats['edges']}")
    print(f"  Snippet bytes:         {stats['snippets_bytes']:,}")
    print(f"  Failed nodes:          {stats['failed']}")
    print(f"  Skipped (no text):     {stats['skipped']}")

    # Verification
    if not args.dry_run and manifold_path:
        print(f"\n--- Verification ---")
        graph = ManifoldMemory(manifold_path, readonly=True)
        test_keys = [
            "domain:programming", "domain:chemistry", "domain:gamedev",
            "python", "javascript", "hydrogen", "oxygen",
            "algorithm", "unity_engine",
        ]
        for key in test_keys:
            node = graph.get_node(key)
            if node:
                snippet = node.get("snippet", "")[:80]
                print(f"  {key}: \"{snippet}...\"")
            else:
                print(f"  {key}: NOT FOUND")
        graph.close()

    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
