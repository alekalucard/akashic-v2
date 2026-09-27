"""
Seed Phonics Vocabulary into the Manifold Cortex.

Loads phonics_vocabulary.json and creates:
- 39 ARPABET phoneme nodes (node_type=SHAPE) — the atoms of English speech
- Phoneme category nodes (vowel, consonant, stop, fricative, etc.)
- 26 letter-sound mapping nodes (ABCs)
- Typed edges: is_a (phoneme→category), composed_of (letter→phonemes),
  contrasts (voiced pairs), semantic (place neighbors)

Optionally trains word→phoneme mappings from CMUdict (135K words).

Phase 4.5 of the Cortex Rebuild Blueprint.

Usage:
    python scripts/seed_phonics_vocabulary.py [--manifold path] [--dry-run]
    python scripts/seed_phonics_vocabulary.py --train-words [--max-words N]

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
    NTYPE_CONCEPT, NTYPE_SHAPE,
    REGION_SEMANTIC,
    REL_COACTIVATE, REL_SEMANTIC, REL_IS_A, REL_PART_OF,
    REL_COMPOSED_OF, REL_CONTRASTS,
)


def load_vocabulary(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def seed_phoneme_primitives(graph, data: dict, stats: dict, dry_run: bool = False):
    """Seed the 39 ARPABET phoneme nodes."""
    primitives = data.get("phoneme_primitives", {})

    for section_name in ["vowels", "consonants"]:
        section = primitives.get(section_name, {})
        if isinstance(section, dict) and "_doc" in section:
            # Vowels are flat: {"AA": {...}, "AE": {...}}
            # Consonants are nested: {"stops": {"B": {...}}, "fricatives": {...}}
            for key, value in section.items():
                if key.startswith("_"):
                    continue
                if isinstance(value, dict) and "snippet" in value:
                    # Direct phoneme entry
                    _seed_phoneme(graph, key, value, stats, dry_run)
                elif isinstance(value, dict):
                    # Subcategory (stops, fricatives, etc.)
                    for pkey, pvalue in value.items():
                        if pkey.startswith("_"):
                            continue
                        if isinstance(pvalue, dict) and "snippet" in pvalue:
                            _seed_phoneme(graph, pkey, pvalue, stats, dry_run)


def _seed_phoneme(graph, arpabet: str, entry: dict, stats: dict, dry_run: bool):
    """Seed a single phoneme node."""
    node_key = f"phon:{arpabet}"
    snippet = entry.get("snippet", "")

    if dry_run:
        stats["nodes"] += 1
        stats["snippets_bytes"] += len(snippet.encode('utf-8'))
        return

    slot = graph.upsert_node(
        key=node_key,
        activation=2.0,
        count=100,
        snippet=snippet,
        node_type=NTYPE_SHAPE,
        region=REGION_SEMANTIC,
    )
    if slot >= 0:
        stats["nodes"] += 1
        stats["snippets_bytes"] += len(snippet.encode('utf-8'))
    else:
        stats["failed"] += 1


def seed_categories(graph, data: dict, stats: dict, dry_run: bool = False):
    """Seed phoneme category nodes and is_a edges."""
    categories = data.get("phoneme_categories", {})

    for cat_name, cat_data in categories.items():
        if cat_name.startswith("_"):
            continue

        node_key = f"phon:cat:{cat_name}"
        snippet = cat_data.get("snippet", "")
        members = cat_data.get("members", [])

        if dry_run:
            stats["nodes"] += 1
            stats["snippets_bytes"] += len(snippet.encode('utf-8'))
            stats["edges"] += len(members)
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
            continue

        # Link members to category
        for member in members:
            ok = graph.link(f"phon:{member}", node_key, weight=0.7, rel_type=REL_IS_A)
            if ok:
                stats["edges"] += 1
            else:
                stats["edge_misses"] += 1


def seed_letter_mappings(graph, data: dict, stats: dict, dry_run: bool = False):
    """Seed the 26 letter→phoneme nodes and edges."""
    letters = data.get("letter_sound_mappings", {})

    for letter, entry in letters.items():
        if letter.startswith("_"):
            continue

        node_key = f"phon:letter:{letter.upper()}"
        snippet = entry.get("snippet", "")
        phonemes = entry.get("phonemes", [])

        if dry_run:
            stats["nodes"] += 1
            stats["snippets_bytes"] += len(snippet.encode('utf-8'))
            stats["edges"] += len(phonemes)
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
            continue

        # Link letter → phonemes (composed_of: letter uses these sounds)
        for phon in phonemes:
            ok = graph.link(node_key, f"phon:{phon}", weight=0.8, rel_type=REL_COMPOSED_OF)
            if ok:
                stats["edges"] += 1
            else:
                stats["edge_misses"] += 1


def seed_relationships(graph, data: dict, stats: dict, dry_run: bool = False):
    """Seed voiced pairs and place neighbors."""
    rels = data.get("phonetic_relationships", {})

    # Voiced pairs (contrasts)
    for pair in rels.get("voiced_pairs", []):
        vl = f"phon:{pair['voiceless']}"
        vd = f"phon:{pair['voiced']}"

        if dry_run:
            stats["edges"] += 1
            continue

        ok = graph.link(vl, vd, weight=0.8, rel_type=REL_CONTRASTS)
        if ok:
            stats["edges"] += 1
        else:
            stats["edge_misses"] += 1

    # Place neighbors (semantic proximity)
    for neighbor in rels.get("place_neighbors", []):
        a = f"phon:{neighbor['from']}"
        b = f"phon:{neighbor['to']}"

        if dry_run:
            stats["edges"] += 1
            continue

        ok = graph.link(a, b, weight=0.6, rel_type=REL_SEMANTIC)
        if ok:
            stats["edges"] += 1
        else:
            stats["edge_misses"] += 1


def seed_word_phoneme_mappings(graph, cmudict_path: str, max_words: int = 0,
                                stats: dict = None, dry_run: bool = False):
    """Train word → phoneme edges from CMUdict.

    Each word becomes a CONCEPT node linked to its phonemes via composed_of edges.
    This creates the bridge between text (semantic) and sound (phonetic).
    """
    if stats is None:
        stats = {"nodes": 0, "edges": 0, "failed": 0, "edge_misses": 0, "snippets_bytes": 0}

    words_processed = 0
    with open(cmudict_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(';') or line.startswith('#'):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            word_raw = parts[0]
            # Skip variant pronunciations like "a(2)"
            if '(' in word_raw:
                continue

            # Clean word
            word = word_raw.lower().strip("'.")
            if len(word) < 2:
                continue

            # Extract phonemes (strip stress markers)
            phonemes = []
            for p in parts[1:]:
                if p.startswith('#'):
                    break
                phonemes.append(p.rstrip('012'))

            if not phonemes:
                continue

            # Build pronunciation string for snippet
            pron_str = ' '.join(phonemes)
            snippet = f"{word} [{pron_str}] — {len(phonemes)} phonemes"

            if dry_run:
                stats["nodes"] += 1
                stats["edges"] += len(phonemes)
                words_processed += 1
                if max_words and words_processed >= max_words:
                    break
                continue

            # Create/update word node
            # Use the word itself as key (no prefix) so it connects to existing concept nodes
            slot = graph.upsert_node(
                key=word,
                activation=0.5,
                count=1,
                snippet=snippet,
                node_type=NTYPE_CONCEPT,
                region=REGION_SEMANTIC,
            )

            if slot >= 0:
                stats["nodes"] += 1
            else:
                stats["failed"] += 1
                continue

            # Link word → phonemes
            for phon in phonemes:
                ok = graph.link(word, f"phon:{phon}", weight=0.3, rel_type=REL_COMPOSED_OF)
                if ok:
                    stats["edges"] += 1

            words_processed += 1
            if max_words and words_processed >= max_words:
                break

            if words_processed % 10000 == 0:
                print(f"    {words_processed} words processed...")

    return words_processed


def main():
    parser = argparse.ArgumentParser(description="Seed phonics vocabulary into cortex manifold")
    parser.add_argument("--manifold", default=None)
    parser.add_argument("--vocab", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--train-words", action="store_true",
                        help="Also train word->phoneme mappings from CMUdict")
    parser.add_argument("--max-words", type=int, default=0,
                        help="Max words to train (0=all 135K)")
    parser.add_argument("--cmudict", default=None,
                        help="Path to cmudict.dict")
    args = parser.parse_args()

    # Find paths
    manifold_path = args.manifold
    if not manifold_path:
        for c in ["state/akashic/cortex.manifold", "../state/akashic/cortex.manifold"]:
            if os.path.exists(c):
                manifold_path = c
                break
    if not manifold_path and not args.dry_run:
        print("ERROR: Could not find cortex.manifold")
        sys.exit(1)

    vocab_path = args.vocab
    if not vocab_path:
        for c in ["state/knowledge_seeds/phonics_vocabulary.json",
                   "../state/knowledge_seeds/phonics_vocabulary.json"]:
            if os.path.exists(c):
                vocab_path = c
                break
    if not vocab_path:
        print("ERROR: Could not find phonics_vocabulary.json")
        sys.exit(1)

    cmudict_path = args.cmudict
    if not cmudict_path and args.train_words:
        for c in ["state/knowledge_seeds/phonics/cmudict.dict",
                   "../state/knowledge_seeds/phonics/cmudict.dict"]:
            if os.path.exists(c):
                cmudict_path = c
                break
        if not cmudict_path:
            print("ERROR: Could not find cmudict.dict for --train-words")
            sys.exit(1)

    # Load vocabulary
    print(f"Loading vocabulary: {vocab_path}")
    data = load_vocabulary(vocab_path)
    meta = data.get("_meta", {})
    print(f"  Title: {meta.get('title', 'unknown')}")

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

    print(f"\nSeeding phonics vocabulary...")
    t0 = time.time()

    print("  [1/4] Phoneme primitives (39 ARPABET phones)...")
    n0 = stats["nodes"]
    seed_phoneme_primitives(graph, data, stats, args.dry_run)
    print(f"        {stats['nodes'] - n0} nodes")

    print("  [2/4] Phoneme categories...")
    n0, e0 = stats["nodes"], stats["edges"]
    seed_categories(graph, data, stats, args.dry_run)
    print(f"        {stats['nodes'] - n0} nodes, {stats['edges'] - e0} edges")

    print("  [3/4] Letter-sound mappings (ABCs)...")
    n0, e0 = stats["nodes"], stats["edges"]
    seed_letter_mappings(graph, data, stats, args.dry_run)
    print(f"        {stats['nodes'] - n0} nodes, {stats['edges'] - e0} edges")

    print("  [4/4] Phonetic relationships...")
    e0 = stats["edges"]
    seed_relationships(graph, data, stats, args.dry_run)
    print(f"        {stats['edges'] - e0} edges")

    if args.train_words and cmudict_path:
        print(f"\n  [EXTRA] Training word->phoneme mappings from CMUdict...")
        n0, e0 = stats["nodes"], stats["edges"]
        word_count = seed_word_phoneme_mappings(
            graph, cmudict_path, args.max_words, stats, args.dry_run
        )
        print(f"        {word_count} words -> {stats['nodes'] - n0} nodes, "
              f"{stats['edges'] - e0} edges")

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

    if not args.dry_run and graph is None:
        return 0

    # Verification
    if not args.dry_run:
        print(f"\n--- Verification ---")
        graph = ManifoldMemory(manifold_path, readonly=True)
        for test_key in ["phon:AA", "phon:S", "phon:M", "phon:cat:vowel",
                         "phon:letter:A", "phon:cat:sibilant"]:
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
