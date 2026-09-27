"""
Seed Programming Languages & Frameworks into the Manifold Cortex.

Loads programming_languages.json and creates:
- Language nodes (lang:NAME) — NTYPE_CONCEPT, REGION_SEMANTIC
- Paradigm nodes (paradigm:NAME) — NTYPE_CONCEPT, REGION_SEMANTIC
- Framework nodes (framework:NAME) — NTYPE_CONCEPT, REGION_SEMANTIC
- Game engine nodes (engine:NAME) — NTYPE_CONCEPT, REGION_SEMANTIC
- is_a edges from languages to their paradigms
- composed_of edges from frameworks/engines to their languages
- semantic edges from the relationships section (paradigm families, domain mappings)

Phase 4.5 of the Cortex Rebuild Blueprint.

Usage:
    python scripts/seed_programming_languages.py [--manifold path] [--dry-run]

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
    REL_SEMANTIC, REL_IS_A, REL_COMPOSED_OF,
)


def load_vocabulary(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def seed_languages(graph, data: dict, stats: dict, dry_run: bool = False):
    """Seed language nodes from the languages section."""
    languages = data.get("languages", {})

    for key, entry in languages.items():
        if key.startswith("_"):
            continue

        node_key = f"lang:{key}"
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


def seed_paradigms(graph, data: dict, stats: dict, dry_run: bool = False):
    """Seed paradigm nodes from the paradigms section."""
    paradigms = data.get("paradigms", {})

    for key, entry in paradigms.items():
        if key.startswith("_"):
            continue

        node_key = f"paradigm:{key}"
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


def seed_frameworks(graph, data: dict, stats: dict, dry_run: bool = False):
    """Seed framework nodes from the frameworks section."""
    frameworks = data.get("frameworks", {})

    for key, entry in frameworks.items():
        if key.startswith("_"):
            continue

        node_key = f"framework:{key}"
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


def seed_game_engines(graph, data: dict, stats: dict, dry_run: bool = False):
    """Seed game engine nodes from the game_engines section."""
    engines = data.get("game_engines", {})

    for key, entry in engines.items():
        if key.startswith("_"):
            continue

        node_key = f"engine:{key}"
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


def seed_language_paradigm_edges(graph, data: dict, stats: dict, dry_run: bool = False):
    """Create is_a edges from languages to their paradigms."""
    rels = data.get("relationships", {})
    lang_to_paradigm = rels.get("language_to_paradigm", {})

    for lang, paradigms in lang_to_paradigm.items():
        lang_key = f"lang:{lang}"
        for paradigm in paradigms:
            paradigm_key = f"paradigm:{paradigm}"

            if dry_run:
                stats["edges"] += 1
                continue

            ok = graph.link(
                lang_key, paradigm_key,
                weight=0.7,
                rel_type=REL_IS_A,
            )
            if ok:
                stats["edges"] += 1
            else:
                stats["edge_misses"] += 1


def seed_framework_language_edges(graph, data: dict, stats: dict, dry_run: bool = False):
    """Create composed_of edges from frameworks to their languages."""
    rels = data.get("relationships", {})
    fw_to_lang = rels.get("framework_to_language", {})

    for fw, lang in fw_to_lang.items():
        fw_key = f"framework:{fw}"
        lang_key = f"lang:{lang}"

        if dry_run:
            stats["edges"] += 1
            continue

        ok = graph.link(
            fw_key, lang_key,
            weight=0.8,
            rel_type=REL_COMPOSED_OF,
        )
        if ok:
            stats["edges"] += 1
        else:
            stats["edge_misses"] += 1


def seed_engine_language_edges(graph, data: dict, stats: dict, dry_run: bool = False):
    """Create composed_of edges from game engines to their languages."""
    rels = data.get("relationships", {})
    eng_to_lang = rels.get("engine_to_language", {})

    for eng, lang in eng_to_lang.items():
        eng_key = f"engine:{eng}"
        lang_key = f"lang:{lang}"

        if dry_run:
            stats["edges"] += 1
            continue

        ok = graph.link(
            eng_key, lang_key,
            weight=0.8,
            rel_type=REL_COMPOSED_OF,
        )
        if ok:
            stats["edges"] += 1
        else:
            stats["edge_misses"] += 1


def seed_paradigm_family_edges(graph, data: dict, stats: dict, dry_run: bool = False):
    """Create semantic edges between paradigms in the same family."""
    rels = data.get("relationships", {})
    families = rels.get("paradigm_families", {})

    for family_name, members in families.items():
        # Link each member to every other member in the family
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                a_key = f"paradigm:{a}"
                b_key = f"paradigm:{b}"

                if dry_run:
                    stats["edges"] += 1
                    continue

                ok = graph.link(
                    a_key, b_key,
                    weight=0.6,
                    rel_type=REL_SEMANTIC,
                )
                if ok:
                    stats["edges"] += 1
                else:
                    stats["edge_misses"] += 1


def main():
    parser = argparse.ArgumentParser(
        description="Seed programming languages vocabulary into cortex manifold"
    )
    parser.add_argument("--manifold", default=None)
    parser.add_argument("--vocab", default=None,
                        help="Path to programming_languages.json (default: auto-detect)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be seeded without modifying the manifold")
    args = parser.parse_args()

    # Find paths
    manifold_path = args.manifold
    if not manifold_path:
        for c in ["state/akashic/cortex.manifold", "../state/akashic/cortex.manifold"]:
            if os.path.exists(c):
                manifold_path = c
                break
    if not manifold_path and not args.dry_run:
        print("ERROR: Could not find cortex.manifold. Use --manifold to specify path.")
        sys.exit(1)

    vocab_path = args.vocab
    if not vocab_path:
        for c in ["state/knowledge_seeds/programming_languages.json",
                   "../state/knowledge_seeds/programming_languages.json"]:
            if os.path.exists(c):
                vocab_path = c
                break
    if not vocab_path:
        print("ERROR: Could not find programming_languages.json. Use --vocab to specify path.")
        sys.exit(1)

    # Load vocabulary
    print(f"Loading vocabulary: {vocab_path}")
    data = load_vocabulary(vocab_path)
    meta = data.get("_meta", {})
    print(f"  Title: {meta.get('title', 'unknown')}")
    print(f"  Version: {meta.get('version', '?')}")

    stats = {"nodes": 0, "edges": 0, "failed": 0, "edge_misses": 0, "snippets_bytes": 0}

    if args.dry_run:
        print(f"\n--- DRY RUN ---")
        graph = None
    else:
        file_size = os.path.getsize(manifold_path)
        print(f"\nOpening manifold: {manifold_path} ({file_size / (1024*1024):.1f} MB)")
        graph = ManifoldMemory(manifold_path)
        status_before = graph.status()
        print(f"  Before: {status_before['nodes']} nodes, {status_before['edges']} edges")

    print(f"\nSeeding programming languages vocabulary...")
    t0 = time.time()

    # ── 1. Languages ──
    print("  [1/8] Languages...")
    n0 = stats["nodes"]
    seed_languages(graph, data, stats, args.dry_run)
    print(f"        {stats['nodes'] - n0} nodes")

    # ── 2. Paradigms ──
    print("  [2/8] Paradigms...")
    n0 = stats["nodes"]
    seed_paradigms(graph, data, stats, args.dry_run)
    print(f"        {stats['nodes'] - n0} nodes")

    # ── 3. Frameworks ──
    print("  [3/8] Frameworks...")
    n0 = stats["nodes"]
    seed_frameworks(graph, data, stats, args.dry_run)
    print(f"        {stats['nodes'] - n0} nodes")

    # ── 4. Game engines ──
    print("  [4/8] Game engines...")
    n0 = stats["nodes"]
    seed_game_engines(graph, data, stats, args.dry_run)
    print(f"        {stats['nodes'] - n0} nodes")

    # ── 5. Language → Paradigm edges (is_a) ──
    print("  [5/8] Language -> Paradigm edges (is_a)...")
    e0 = stats["edges"]
    seed_language_paradigm_edges(graph, data, stats, args.dry_run)
    print(f"        {stats['edges'] - e0} edges")

    # ── 6. Framework → Language edges (composed_of) ──
    print("  [6/8] Framework -> Language edges (composed_of)...")
    e0 = stats["edges"]
    seed_framework_language_edges(graph, data, stats, args.dry_run)
    print(f"        {stats['edges'] - e0} edges")

    # ── 7. Engine → Language edges (composed_of) ──
    print("  [7/8] Engine -> Language edges (composed_of)...")
    e0 = stats["edges"]
    seed_engine_language_edges(graph, data, stats, args.dry_run)
    print(f"        {stats['edges'] - e0} edges")

    # ── 8. Paradigm family edges (semantic) ──
    print("  [8/8] Paradigm family edges (semantic)...")
    e0 = stats["edges"]
    seed_paradigm_family_edges(graph, data, stats, args.dry_run)
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
    if not args.dry_run and graph is not None:
        print(f"\n--- Verification ---")
        graph = ManifoldMemory(manifold_path, readonly=True)
        for test_key in ["lang:python", "lang:javascript", "lang:rust",
                         "paradigm:functional", "paradigm:object_oriented",
                         "framework:react", "framework:django",
                         "engine:unity", "engine:godot"]:
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
