"""
Seed Grapheme-Phoneme Mappings into the Manifold Cortex.

Creates grapheme nodes (spelling patterns) and links them to phoneme nodes.
This bridges visual text (Florence OCR) ←→ sound (Whisper STT).

When Florence reads "ph" in text, it activates phon:F through the grapheme edge.
When Whisper hears /f/, spread activation reaches both "f" and "ph" graphemes.

Usage:
    python scripts/seed_graphemes.py [--manifold path] [--dry-run]

2026-03-20, Nous + Ace -- Akashic Foundation
"""

import os
import sys
import json
import time
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from infrastructure.manifold_memory import (
    ManifoldMemory,
    NTYPE_CONCEPT, REGION_SEMANTIC,
    REL_COMPOSED_OF, REL_SEMANTIC, REL_IS_A,
)


def load_data(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def seed_graphemes(graph, data: dict, stats: dict, dry_run: bool = False):
    """Seed grapheme nodes and phoneme→grapheme edges."""

    for section_name in ["consonant_graphemes", "vowel_graphemes"]:
        section = data.get(section_name, {})
        for phoneme_arpabet, entry in section.items():
            if phoneme_arpabet.startswith("_"):
                continue

            phoneme_key = f"phon:{phoneme_arpabet}"
            graphemes = entry.get("graphemes", [])
            examples = entry.get("examples", [])
            label = entry.get("label", "")

            for i, grapheme in enumerate(graphemes):
                # Create grapheme node
                gkey = f"phon:graph:{grapheme}"
                example = examples[i] if i < len(examples) else ""
                snippet = f"Grapheme '{grapheme}' — spelling pattern for /{phoneme_arpabet}/."
                if label:
                    snippet += f" ({label})."
                if example:
                    snippet += f" Example: '{example}'."

                if dry_run:
                    stats["nodes"] += 1
                    stats["edges"] += 1
                    stats["snippets_bytes"] += len(snippet.encode('utf-8'))
                    continue

                slot = graph.upsert_node(
                    key=gkey,
                    activation=1.5,
                    count=50,
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

                # Link grapheme → phoneme (this grapheme represents this sound)
                ok = graph.link(gkey, phoneme_key, weight=0.7, rel_type=REL_COMPOSED_OF)
                if ok:
                    stats["edges"] += 1
                else:
                    stats["edge_misses"] += 1


def main():
    parser = argparse.ArgumentParser(description="Seed grapheme mappings into cortex")
    parser.add_argument("--manifold", default=None)
    parser.add_argument("--data", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifold_path = args.manifold
    if not manifold_path:
        for c in ["state/akashic/cortex.manifold", "../state/akashic/cortex.manifold"]:
            if os.path.exists(c):
                manifold_path = c
                break

    data_path = args.data
    if not data_path:
        for c in ["state/knowledge_seeds/grapheme_mappings.json",
                   "../state/knowledge_seeds/grapheme_mappings.json"]:
            if os.path.exists(c):
                data_path = c
                break
    if not data_path:
        print("ERROR: Could not find grapheme_mappings.json")
        sys.exit(1)

    print(f"Loading: {data_path}")
    data = load_data(data_path)

    stats = {"nodes": 0, "edges": 0, "failed": 0, "edge_misses": 0, "snippets_bytes": 0}

    if args.dry_run:
        print("\n--- DRY RUN ---")
        seed_graphemes(None, data, stats, dry_run=True)
    else:
        print(f"Opening: {manifold_path}")
        graph = ManifoldMemory(manifold_path)
        before = graph.status()
        print(f"  Before: {before['nodes']:,} nodes, {before['edges']:,} edges")

        seed_graphemes(graph, data, stats)

        graph._write_header()
        after = graph.status()
        print(f"  After:  {after['nodes']:,} nodes, {after['edges']:,} edges")
        graph.close()

    print(f"\n--- Summary ---")
    print(f"  Grapheme nodes: {stats['nodes']}")
    print(f"  Edges:          {stats['edges']}")
    print(f"  Snippet bytes:  {stats['snippets_bytes']:,}")
    print(f"  Failed:         {stats['failed']}")
    print(f"  Missed edges:   {stats['edge_misses']}")

    # Verify
    if not args.dry_run:
        print(f"\n--- Verification ---")
        graph = ManifoldMemory(manifold_path, readonly=True)
        for key in ["phon:graph:ph", "phon:graph:sh", "phon:graph:igh", "phon:graph:oo"]:
            node = graph.get_node(key)
            if node:
                print(f"  {key}: \"{node.get('snippet', '')[:70]}...\"")
            else:
                print(f"  {key}: NOT FOUND")
        graph.close()


if __name__ == "__main__":
    sys.exit(main())
