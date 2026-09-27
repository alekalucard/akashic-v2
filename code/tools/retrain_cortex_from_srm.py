"""
Retrain cortex manifold from SRM files.

Phase 0 of cortex rebuild: After nuking the polluted manifold, this script
rehydrates the cortex from SRM session files — the richest source of
semantic content in the system.

Usage:
    python retrain_cortex_from_srm.py [--dry-run] [--max N] [--kinds K1,K2]

Runs OFFLINE — no server, no portal, no fairies needed.
Directly opens the manifold and writes nodes + edges.

2026-03-20 — Nous + Ace
"""

import os
import sys
import re
import json
import time
import glob
import argparse
from pathlib import Path
from collections import defaultdict

# Project root
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from infrastructure.manifold_memory import ManifoldMemory

# ============================================================================
# CONCEPT EXTRACTION (copied from AssociationCortexFairy, post-fix)
# ============================================================================

_STOPWORDS = frozenset({
    # Determiners / pronouns
    'the', 'this', 'that', 'these', 'those', 'their', 'them', 'they',
    'your', 'our', 'you', 'its', 'his', 'her', 'she', 'him', 'who',
    'whom', 'what', 'which', 'where', 'when', 'how', 'why',
    # Be / have / do
    'are', 'was', 'were', 'been', 'being', 'have', 'has', 'had',
    'does', 'did', 'done', 'doing',
    # Modals
    'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
    'shall',
    # Conjunctions / prepositions
    'and', 'but', 'for', 'nor', 'yet', 'with', 'from', 'into', 'onto',
    'over', 'under', 'about', 'between', 'through', 'during', 'before',
    'after', 'above', 'below', 'than', 'then', 'there', 'here',
    # Adverbs / misc filler
    'also', 'just', 'only', 'more', 'some', 'any', 'each', 'all',
    'both', 'few', 'most', 'other', 'very', 'own', 'same', 'such',
    'because', 'really', 'actually', 'still', 'already', 'even',
    'quite', 'well', 'much', 'many', 'like', 'back', 'make', 'made',
    'take', 'took', 'give', 'gave', 'come', 'came', 'going', 'goes',
    'went', 'know', 'knew', 'think', 'thought', 'said', 'says',
    'tell', 'told', 'keep', 'kept', 'want', 'need', 'seem', 'seems',
    'look', 'looks', 'show', 'shows', 'showed', 'call', 'called',
    'work', 'works', 'part', 'good', 'long', 'right', 'used', 'using',
    'true', 'false', 'none', 'null', 'type', 'line', 'file', 'code',
    # System metadata that should NEVER be concepts
    'collision', 'reasoning', 'connection', 'feeling', 'person',
    'source', 'affect', 'fairy', 'postal', 'envelope', 'payload',
    # Common short/filler words the 3-char minimum lets through
    'not', 'one', 'two', 'way', 'get', 'got', 'let', 'put', 'set',
    'try', 'see', 'saw', 'say', 'new', 'old', 'big', 'end', 'now',
    'too', 'use', 'run', 'ran', 'bit', 'lot', 'own', 'yes', 'yet',
    'ask', 'ago', 'add', 'top', 'low', 'key', 'per', 'via', 'due',
    'far', 'off', 'out', 'often', 'something', 'nothing', 'anything',
    'everything', 'sometimes', 'things', 'thing', 'stuff', 'place',
    'people', 'someone', 'always', 'never', 'maybe', 'perhaps',
    'pretty', 'another', 'without', 'within', 'likely', 'simply',
    'rather', 'almost', 'instead', 'however', 'though', 'whether',
    'while', 'since', 'until', 'unless', 'along', 'around',
    # System/template artifacts
    'entry', 'detected', 'detected_text', 'observation', 'usb',
    'encyclopedia', 'akashic_encyclopedia', 'encyclopedia_entry',
    'entry_definition', 'entry_usb',
})


def extract_concepts(text: str, max_concepts: int = 30) -> list:
    """Extract meaningful concepts from text.

    Post-fix version: 3-char minimum, no metadata injection.
    """
    if not text or len(text) < 20:
        return []

    # Clean
    cleaned = re.sub(r'[#*_\[\](){}|`"\'\\]', ' ', text)
    cleaned = re.sub(r'https?://\S+', '', cleaned)
    cleaned = re.sub(r'\b\d+\b', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    if len(cleaned) < 20:
        return []

    # Phase 1: CamelCase
    camel_concepts = []
    for match in re.finditer(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', cleaned):
        parts = re.findall(r'[A-Z][a-z]+', match.group())
        if len(parts) >= 2:
            joined = '_'.join(p.lower() for p in parts)
            camel_concepts.append(joined)

    # Phase 2: Bigrams
    lower = cleaned.lower()
    words_raw = re.findall(r'\b[a-zA-Z]{3,}\b', lower)
    words_filtered = [w for w in words_raw if w not in _STOPWORDS and len(w) >= 3]

    bigrams = []
    for i in range(len(words_filtered) - 1):
        a, b = words_filtered[i], words_filtered[i + 1]
        if len(a) >= 3 and len(b) >= 3:
            bigrams.append(f"{a}_{b}")

    # Phase 3: Singles with frequency
    singles = [w for w in words_filtered if len(w) >= 3]
    freq = {}
    for w in singles:
        freq[w] = freq.get(w, 0) + 1

    # Phase 4: Score and rank
    scored = {}
    for c in camel_concepts:
        scored[c] = scored.get(c, 0) + 5.0
    for b in bigrams:
        scored[b] = scored.get(b, 0) + 2.0
    for w, count in freq.items():
        scored[w] = scored.get(w, 0) + min(count, 5)

    ranked = sorted(scored.keys(), key=lambda k: scored[k], reverse=True)
    return ranked[:max_concepts]


# ============================================================================
# SRM FILE PROCESSING
# ============================================================================

# Priority ordering for retraining — richest content first
KIND_PRIORITY = {
    'encyclopedia': 10,                   # Gold Standard emotional context encyclopedia!
    'memory.personal_ai_interview': 10,  # Sour's identity interviews
    'reflection': 9,                      # Sour's reflections — her actual thoughts!
    'sour_mind': 9,                       # Sour's own thoughts
    'sour_fresh': 9,                      # Sour's fresh memories
    'session.claude_code': 8,             # Nous + Ace engineering sessions
    'session.claude_ai': 8,              # AI collaboration sessions
    'session.ace_mythos': 8,             # Ace's stories/worldbuilding
    'document.ace_foundation': 8,        # Ace foundation docs
    'ace_mythos': 8,                      # Ace's stories/worldbuilding
    'session.notes': 7,                   # Manual notes
    'notes': 7,                           # Manual notes
    'nous_trace': 5,                      # Reasoning traces
    'ace_ingest': 7,                      # Ace ingested content
    'visual': 3,                          # Visual observations (lower priority)
    'visual.perception': 3,              # Visual observations
}

# Weight by kind — how strongly to bind concepts
KIND_WEIGHT = {
    'encyclopedia': 0.9,                  # Core emotional knowledge — high binding
    'memory.personal_ai_interview': 0.7,
    'reflection': 0.7,
    'sour_mind': 0.8,
    'sour_fresh': 0.7,
    'session.claude_code': 0.4,
    'session.claude_ai': 0.5,
    'session.ace_mythos': 0.6,
    'document.ace_foundation': 0.6,
    'ace_mythos': 0.6,
    'session.notes': 0.5,
    'notes': 0.5,
    'nous_trace': 0.3,
    'ace_ingest': 0.5,
    'visual': 0.3,
    'visual.perception': 0.3,
}


def load_srm_file(path: str) -> dict:
    """Load and parse an SRM JSON file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def get_text_from_srm(data: dict) -> str:
    """Extract all meaningful text from an SRM record."""
    parts = []

    # Primary content
    content = data.get('content', '')
    if isinstance(content, str) and content:
        parts.append(content)

    # Helix L-strand concept (title/summary)
    helix = data.get('helix', {})
    if helix:
        l_strand = helix.get('L', {})
        if isinstance(l_strand, dict):
            concept = l_strand.get('concept', '')
            if isinstance(concept, str) and concept:
                parts.append(concept)

    # Tags as context
    tags = data.get('tags', [])
    if tags and isinstance(tags, list):
        tag_text = ' '.join(str(t) for t in tags if isinstance(t, str) and len(t) > 2)
        if tag_text:
            parts.append(tag_text)

    return ' '.join(parts)


def infer_kind(data: dict, filename: str) -> str:
    """Infer the kind of SRM record.

    FIX 2026-03-20 (Nous): Check tags for 'encyclopedia' FIRST.
    Encyclopedia entries are filed as 'session.notes' but are actually
    the Gold Standard emotional context encyclopedia — Ace's core dataset.
    They need highest priority and weight for manifold mass.
    """
    # Check tags for encyclopedia marker (overrides kind field)
    tags = data.get('tags', [])
    if isinstance(tags, list) and 'encyclopedia' in tags:
        return 'encyclopedia'

    kind = data.get('kind', '')
    if kind:
        return kind

    # Infer from filename
    name = os.path.basename(filename).lower()
    if name.startswith('sour_mind'):
        return 'sour_mind'
    elif name.startswith('sour_fresh'):
        return 'sour_fresh'
    elif name.startswith('claude_code'):
        return 'session.claude_code'
    elif name.startswith('nous_trace'):
        return 'nous_trace'
    elif name.startswith('visual'):
        return 'visual'
    elif name.startswith('notes'):
        return 'notes'
    elif name.startswith('ace_'):
        return 'ace_mythos'
    elif name.startswith('sourpatchesfairy.reflection'):
        return 'sour_mind'
    return 'unknown'


# ============================================================================
# MAIN RETRAINING LOOP
# ============================================================================

def retrain(manifold_path: str, srm_dir: str,
            dry_run: bool = False, max_files: int = 0,
            kinds_filter: list = None, skip_visual: bool = True):
    """Retrain the cortex manifold from SRM files.

    Args:
        manifold_path: Path to the .manifold file (created fresh if missing)
        srm_dir: Path to SRM_Intake directory
        dry_run: If True, only analyze — don't write to manifold
        max_files: Max files to process (0 = all)
        kinds_filter: Only process these kinds (None = all)
        skip_visual: Skip visual observation files (low semantic value)
    """
    print(f"{'=' * 60}")
    print(f"CORTEX RETRAINING FROM SRM")
    print(f"{'=' * 60}")
    print(f"Manifold: {manifold_path}")
    print(f"SRM dir:  {srm_dir}")
    print(f"Dry run:  {dry_run}")
    print(f"Max files: {max_files or 'ALL'}")
    print(f"Skip visual: {skip_visual}")
    print()

    # Collect all SRM files
    t0 = time.time()
    all_files = []
    for root, dirs, files in os.walk(srm_dir):
        for f in files:
            if f.endswith('.json'):
                all_files.append(os.path.join(root, f))

    print(f"Found {len(all_files)} SRM files")

    # Quick scan to categorize
    categorized = defaultdict(list)
    for fpath in all_files:
        data = load_srm_file(fpath)
        if not data:
            continue
        kind = infer_kind(data, fpath)
        if skip_visual and kind == 'visual':
            continue
        if kinds_filter and kind not in kinds_filter:
            continue
        text = get_text_from_srm(data)
        if not text or len(text) < 30:
            continue
        priority = KIND_PRIORITY.get(kind, 1)
        categorized[kind].append((fpath, data, text, priority))

    total_usable = sum(len(v) for v in categorized.values())
    print(f"\nUsable files by kind:")
    for kind in sorted(categorized.keys(), key=lambda k: KIND_PRIORITY.get(k, 0), reverse=True):
        print(f"  {kind}: {len(categorized[kind])} files (priority {KIND_PRIORITY.get(kind, 0)}, weight {KIND_WEIGHT.get(kind, 0.3)})")
    print(f"  TOTAL: {total_usable}")

    if dry_run:
        # Show sample extraction
        print(f"\n{'=' * 40}")
        print("DRY RUN — Sample extractions:")
        print(f"{'=' * 40}")
        count = 0
        for kind in sorted(categorized.keys(), key=lambda k: KIND_PRIORITY.get(k, 0), reverse=True):
            if count >= 5:
                break
            items = categorized[kind]
            if items:
                fpath, data, text, _ = items[0]
                concepts = extract_concepts(text)
                print(f"\n[{kind}] {os.path.basename(fpath)}")
                print(f"  Text (first 200): {text[:200]}...")
                print(f"  Concepts ({len(concepts)}): {concepts[:15]}")
                count += 1
        return

    # Open or create manifold
    if os.path.exists(manifold_path):
        manifold = ManifoldMemory(manifold_path)
        print(f"\nOpened existing manifold: {manifold.node_count} nodes, {manifold.edge_count} edges")
    else:
        os.makedirs(os.path.dirname(manifold_path) or '.', exist_ok=True)
        manifold = ManifoldMemory(manifold_path, node_capacity=1_000_000, edge_capacity=10_000_000)
        print(f"\nCreated fresh manifold: 1M nodes, 10M edges capacity")

    # Process files in priority order
    total_processed = 0
    total_concepts = 0
    total_edges = 0
    files_processed = 0

    # Flatten and sort by priority
    all_items = []
    for kind, items in categorized.items():
        for fpath, data, text, priority in items:
            all_items.append((priority, kind, fpath, data, text))
    all_items.sort(key=lambda x: x[0], reverse=True)

    if max_files:
        all_items = all_items[:max_files]

    print(f"\nProcessing {len(all_items)} files...")
    batch_start = time.time()

    for idx, (priority, kind, fpath, data, text) in enumerate(all_items):
        # Encyclopedia entries are dense, structured docs — extract more concepts
        _max_c = 30 if kind == 'encyclopedia' else 20
        concepts = extract_concepts(text, max_concepts=_max_c)
        if len(concepts) < 2:
            continue

        weight = KIND_WEIGHT.get(kind, 0.3)

        # Upsert all concept nodes
        for c in concepts:
            manifold.upsert_node(c, activation=weight)

        # Bind top N concepts (not all-pairs — that was the old problem)
        # Use a sliding window instead: connect adjacent concepts + a few cross-links
        n = min(len(concepts), 15)
        edges_this = 0

        # Adjacent pairs (strong — these co-occur in extraction order = importance order)
        for i in range(n - 1):
            if manifold.link(concepts[i], concepts[i + 1], weight=weight):
                edges_this += 1

        # Skip-1 pairs (medium — concepts 2 apart are still related)
        for i in range(n - 2):
            if manifold.link(concepts[i], concepts[i + 2], weight=weight * 0.7):
                edges_this += 1

        # Top concept connects to all others (star pattern — most important concept is hub)
        for i in range(1, min(n, 8)):
            if manifold.link(concepts[0], concepts[i], weight=weight * 0.9):
                edges_this += 1

        # If identity content, anchor to owner
        owner = data.get('owner_mind', '')
        if owner:
            owner_key = owner.lower().replace(' ', '_')
            manifold.upsert_node(owner_key, activation=1.0)
            for c in concepts[:5]:
                if c != owner_key:
                    manifold.link(owner_key, c, weight=weight * 1.2)
                    edges_this += 1

        total_concepts += len(concepts)
        total_edges += edges_this
        files_processed += 1

        # Progress
        if files_processed % 500 == 0:
            elapsed = time.time() - batch_start
            rate = files_processed / elapsed if elapsed > 0 else 0
            print(f"  [{files_processed}/{len(all_items)}] "
                  f"{manifold.node_count} nodes, {manifold.edge_count} edges "
                  f"({rate:.0f} files/sec)")

    # Flush
    manifold.flush()
    elapsed = time.time() - t0

    print(f"\n{'=' * 60}")
    print(f"RETRAINING COMPLETE")
    print(f"{'=' * 60}")
    print(f"Files processed: {files_processed}")
    print(f"Concepts extracted: {total_concepts}")
    print(f"Edges created: {total_edges}")
    print(f"Final manifold: {manifold.node_count} nodes, {manifold.edge_count} edges")
    print(f"File size: {manifold.status()['file_size_mb']:.1f}MB")
    print(f"Time: {elapsed:.1f}s")

    # Show top nodes by degree
    print(f"\nTop 20 nodes by degree:")
    node_degrees = []
    for key in manifold._key_index:
        slot = manifold._key_index[key]
        neighbors = manifold._adjacency.get(slot, set())
        node_degrees.append((key, len(neighbors)))
    node_degrees.sort(key=lambda x: x[1], reverse=True)
    for key, deg in node_degrees[:20]:
        print(f"  {key}: {deg} edges")

    manifold.close()


# ============================================================================
# CLI
# ============================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Retrain cortex from SRM files')
    parser.add_argument('--dry-run', action='store_true', help='Analyze only, no writes')
    parser.add_argument('--max', type=int, default=0, help='Max files to process (0=all)')
    parser.add_argument('--kinds', type=str, default='', help='Comma-separated kinds to include')
    parser.add_argument('--include-visual', action='store_true', help='Include visual observation files')
    parser.add_argument('--manifold', type=str, default='', help='Path to manifold file')
    parser.add_argument('--srm', type=str, default='', help='Path to SRM_Intake directory')

    args = parser.parse_args()

    # Defaults
    project_root = Path(__file__).parent.parent
    manifold_path = args.manifold or str(
        project_root / 'P10_Memory' / 'Akashic_triple_helix_memory_storage' /
        'relational_clusters' / 'AssociationCortexFairy' / 'helix_cards' /
        'portal_cortex.manifold'
    )
    srm_dir = args.srm or str(project_root / 'SRM_Intake')

    kinds_filter = [k.strip() for k in args.kinds.split(',') if k.strip()] or None

    retrain(
        manifold_path=manifold_path,
        srm_dir=srm_dir,
        dry_run=args.dry_run,
        max_files=args.max,
        kinds_filter=kinds_filter,
        skip_visual=not args.include_visual,
    )
