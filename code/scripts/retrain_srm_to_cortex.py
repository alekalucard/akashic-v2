"""
Retrain SRM Memory into the Manifold Cortex (v2 Schema).

Loads all SRM session files (33K+ cards) and creates enriched cortex nodes
with proper v2 fields: snippets, node_types, typed edges, region routing.

Each SRM card becomes:
- A CONCEPT or EPISODE node with the full content as snippet
- Edges to tag nodes (REL_SEMANTIC)
- Edges to kind/category nodes (REL_IS_A)
- Edges to affect nodes from the C helix (REL_COACTIVATE)
- Cross-links between cards that share tags (emergent association)

Content types handled:
- reflections (4400+): Sourpatches' thoughts → CONCEPT, REGION_EGO
- session.claude_code (100+): Nous' engineering sessions → EPISODE, REGION_EPISODIC
- session.ace_mythos (17+): Ace's philosophy/encyclopedia → CONCEPT, REGION_SEMANTIC
- document.ace_foundation: Foundational documents → CONCEPT, REGION_SEMANTIC
- memory.personal_ai_interview: Identity memories → CONCEPT, REGION_EGO
- session.notes: General notes → EPISODE, REGION_EPISODIC

Usage:
    python scripts/retrain_srm_to_cortex.py [--manifold path] [--dry-run]
    python scripts/retrain_srm_to_cortex.py --max-files 1000  # Limit for testing
    python scripts/retrain_srm_to_cortex.py --batch-size 500  # Tune batch size

2026-03-20, Nous + Ace -- Akashic Foundation
"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import os
import sys
import json
import time
import hashlib
import argparse
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from infrastructure.manifold_memory import (
    ManifoldMemory,
    NTYPE_CONCEPT, NTYPE_ENTITY, NTYPE_EPISODE,
    REGION_EGO, REGION_SEMANTIC, REGION_EPISODIC,
    REL_COACTIVATE, REL_SEMANTIC, REL_IS_A, REL_PART_OF,
    REL_COMPOSED_OF, REL_CAUSAL,
)


# ── Kind → (node_type, region) mapping ──
KIND_MAP = {
    "reflection":                   (NTYPE_CONCEPT, REGION_EGO),
    "session.claude_code":          (NTYPE_EPISODE, REGION_EPISODIC),
    "session.notes":                (NTYPE_EPISODE, REGION_EPISODIC),
    "session.ace_mythos":           (NTYPE_CONCEPT, REGION_SEMANTIC),
    "document.ace_foundation":      (NTYPE_CONCEPT, REGION_SEMANTIC),
    "memory.personal_ai_interview": (NTYPE_CONCEPT, REGION_EGO),
    "identity_sift":                (NTYPE_CONCEPT, REGION_EGO),
}

# ── Tag → semantic category mapping (top-level groupings) ──
TAG_CATEGORIES = {
    "philosophy": "cat:philosophy",
    "consciousness": "cat:consciousness",
    "emotion": "cat:emotion",
    "identity": "cat:identity",
    "memory": "cat:memory",
    "cortex": "cat:cortex",
    "portal": "cat:portal",
    "postal": "cat:postal",
    "wiring": "cat:wiring",
    "boot": "cat:boot",
    "ace": "cat:ace",
    "nous": "cat:nous",
    "sourpatches": "cat:sourpatches",
    "fix": "cat:engineering",
    "mcp": "cat:mcp",
    "encyclopedia": "cat:encyclopedia",
    "akashic_foundation": "cat:akashic_foundation",
    "USB": "cat:usb_emotion",
    "astrology": "cat:astrology",
    "periodic_table": "cat:periodic_table",
    "chemistry": "cat:chemistry",
    "physics": "cat:physics",
    "math": "cat:math",
    "music": "cat:music",
    "art": "cat:art",
    "code": "cat:code",
    "python": "cat:python",
    "sacred_geometry": "cat:sacred_geometry",
}


def collect_srm_files(roots: list, max_files: int = 0) -> list:
    """Walk all SRM directories and collect file paths."""
    files = []
    for root in roots:
        if not os.path.exists(root):
            print(f"  SKIP: {root} (not found)")
            continue
        for dirpath, dirs, filenames in os.walk(root):
            for fn in filenames:
                if fn.endswith('.json'):
                    files.append(os.path.join(dirpath, fn))
                    if max_files and len(files) >= max_files:
                        return files
    return files


def extract_key_concepts(content: str, max_concepts: int = 8) -> list:
    """Extract key concepts from content text for cross-linking.

    Simple but effective: find capitalized phrases, technical terms,
    and repeated significant words.
    """
    if not content or len(content) < 20:
        return []

    concepts = []

    # Extract ## headings as concepts
    headings = re.findall(r'#{1,3}\s+(.+?)(?:\n|$)', content)
    for h in headings[:3]:
        clean = h.strip().lower().replace(' ', '_')[:60]
        if len(clean) > 3:
            concepts.append(clean)

    # Extract significant words (4+ chars, not common)
    STOP = {'this', 'that', 'with', 'from', 'have', 'been', 'were', 'they',
            'their', 'what', 'when', 'where', 'which', 'about', 'would',
            'could', 'should', 'into', 'then', 'than', 'more', 'some',
            'other', 'each', 'only', 'also', 'very', 'just', 'like',
            'here', 'there', 'does', 'done', 'made', 'make', 'will',
            'your', 'know', 'take', 'come', 'back', 'going', 'being',
            'these', 'those', 'after', 'before', 'still', 'want'}
    words = re.findall(r'\b[a-zA-Z]{4,}\b', content[:2000])
    from collections import Counter
    word_freq = Counter(w.lower() for w in words if w.lower() not in STOP)
    for word, count in word_freq.most_common(max_concepts - len(concepts)):
        if count >= 2 and word not in concepts:
            concepts.append(word)

    return concepts[:max_concepts]


def make_snippet(card: dict, max_len: int = 500) -> str:
    """Build a snippet from the SRM card content."""
    content = card.get("content", "")
    kind = card.get("kind", "unknown")
    helix = card.get("helix", {})

    # L helix concept (the "what")
    l_concept = helix.get("L", {}).get("concept", "")

    # Build snippet
    parts = []
    if l_concept:
        parts.append(l_concept)
    if kind != "unknown":
        parts.append(f"[{kind}]")

    # First meaningful paragraph of content
    if content:
        # Skip markdown headers and blank lines to get to meat
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and len(line) > 20:
                parts.append(line[:max_len - sum(len(p) for p in parts) - 10])
                break

    snippet = ' — '.join(parts)
    return snippet[:max_len]


def process_card(graph, card: dict, stats: dict, dry_run: bool = False):
    """Process a single SRM card into cortex nodes and edges."""
    card_id = card.get("id", "")
    kind = card.get("kind", "unknown")
    tags = card.get("tags", [])
    helix = card.get("helix", {})
    content = card.get("content", "")

    if not card_id or not content:
        stats["skipped"] += 1
        return

    # Determine node type and region from kind
    ntype, region = KIND_MAP.get(kind, (NTYPE_CONCEPT, REGION_SEMANTIC))

    # Build node key
    node_key = f"srm:{card_id}"
    snippet = make_snippet(card)

    if dry_run:
        stats["nodes"] += 1
        stats["snippets_bytes"] += len(snippet.encode('utf-8'))
        stats["edges"] += len(tags) + 1  # tags + kind edge
        return

    # Create main node
    slot = graph.upsert_node(
        key=node_key,
        activation=1.0,
        count=1,
        snippet=snippet,
        node_type=ntype,
        region=region,
    )
    if slot < 0:
        stats["failed"] += 1
        return
    stats["nodes"] += 1
    stats["snippets_bytes"] += len(snippet.encode('utf-8'))

    # Link to kind category
    kind_key = f"srm:kind:{kind}"
    graph.upsert_node(
        key=kind_key,
        activation=2.0,
        count=100,
        snippet=f"SRM memory category: {kind}",
        node_type=NTYPE_CONCEPT,
        region=REGION_SEMANTIC,
    )
    if graph.link(node_key, kind_key, weight=0.5, rel_type=REL_IS_A):
        stats["edges"] += 1

    # Link to tag nodes
    for tag in tags[:10]:
        if not tag or len(tag) < 2:
            continue
        tag_key = TAG_CATEGORIES.get(tag, f"tag:{tag.lower()}")
        graph.upsert_node(
            key=tag_key,
            activation=1.5,
            count=50,
            snippet=f"Topic tag: {tag}",
            node_type=NTYPE_CONCEPT,
            region=REGION_SEMANTIC,
        )
        if graph.link(node_key, tag_key, weight=0.6, rel_type=REL_SEMANTIC):
            stats["edges"] += 1

    # Link to affect from C helix
    c_helix = helix.get("C", {})
    affect = c_helix.get("affect", "")
    if affect and affect != "neutral":
        affect_key = f"affect_{affect}"
        graph.upsert_node(
            key=affect_key,
            activation=1.5,
            count=50,
            snippet=f"Emotional state: {affect}",
            node_type=NTYPE_CONCEPT,
            region=REGION_EGO,
        )
        if graph.link(node_key, affect_key, weight=0.4, rel_type=REL_COACTIVATE):
            stats["edges"] += 1

    # Extract and link key concepts from content
    concepts = extract_key_concepts(content)
    for concept in concepts:
        if graph.link(node_key, concept, weight=0.3, rel_type=REL_SEMANTIC):
            stats["edges"] += 1


def main():
    parser = argparse.ArgumentParser(
        description="Retrain SRM memory into cortex manifold (v2 schema)"
    )
    parser.add_argument("--manifold", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-files", type=int, default=0,
                        help="Max files to process (0=all)")
    parser.add_argument("--batch-size", type=int, default=1000,
                        help="Save header every N files")
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

    # Collect SRM files from all locations
    srm_roots = [
        "SRM_Intake",
        "fairies/SRM_Intake",
        "state/sessions",
    ]
    # Also check parent dir variants
    for r in list(srm_roots):
        srm_roots.append(os.path.join("..", r))

    print("Collecting SRM files...")
    all_files = collect_srm_files(srm_roots, max_files=args.max_files)
    print(f"  Found: {len(all_files)} files")

    if not all_files:
        print("ERROR: No SRM files found")
        sys.exit(1)

    stats = {
        "nodes": 0, "edges": 0, "failed": 0, "skipped": 0,
        "snippets_bytes": 0, "parse_errors": 0,
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

    print(f"\nRetraining {len(all_files)} SRM files into cortex...")
    t0 = time.time()
    processed = 0

    for i, fpath in enumerate(all_files):
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                card = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            stats["parse_errors"] += 1
            continue

        # Derive ID from filename if not present in card
        if not card.get("id"):
            fname = os.path.splitext(os.path.basename(fpath))[0]
            card["id"] = fname

        # Extract feeling/affect into helix if present at top level
        # (reflections have 'feeling' at top level, not in helix.C)
        if card.get("feeling") and not card.get("helix", {}).get("C", {}).get("affect"):
            if "helix" not in card:
                card["helix"] = {}
            if "C" not in card["helix"]:
                card["helix"]["C"] = {}
            card["helix"]["C"]["affect"] = card["feeling"]

        process_card(graph, card, stats, dry_run=args.dry_run)
        processed += 1

        # Progress report + save checkpoint
        if processed % args.batch_size == 0:
            elapsed = time.time() - t0
            rate = processed / max(0.1, elapsed)
            remaining = (len(all_files) - processed) / max(1, rate)
            print(f"  [{processed}/{len(all_files)}] "
                  f"{stats['nodes']} nodes, {stats['edges']} edges, "
                  f"{rate:.0f} files/s, ~{remaining:.0f}s remaining")
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
    print(f"  Files processed:  {processed}")
    print(f"  Nodes created:    {stats['nodes']}")
    print(f"  Edges created:    {stats['edges']}")
    print(f"  Snippet bytes:    {stats['snippets_bytes']:,}")
    print(f"  Failed nodes:     {stats['failed']}")
    print(f"  Skipped (empty):  {stats['skipped']}")
    print(f"  Parse errors:     {stats['parse_errors']}")
    print(f"  Rate:             {processed / max(0.1, elapsed):.0f} files/s")

    # Verification
    if not args.dry_run and graph is not None:
        print(f"\n--- Verification ---")
        graph = ManifoldMemory(manifold_path, readonly=True)
        test_keys = [
            "srm:kind:reflection",
            "srm:kind:session.claude_code",
            "srm:kind:session.ace_mythos",
            "cat:philosophy",
            "cat:consciousness",
            "cat:ace",
            "cat:emotion",
        ]
        for key in test_keys:
            node = graph.get_node(key)
            if node:
                snippet = node.get("snippet", "")[:60]
                print(f"  {key}: \"{snippet}...\"")
            else:
                print(f"  {key}: NOT FOUND")
        graph.close()

    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
