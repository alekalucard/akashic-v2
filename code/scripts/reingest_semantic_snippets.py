"""
Re-ingest SRM cards to populate semantic snippets on manifold nodes.

The manifold has 468K+ nodes but all snippets contain phoneme data
("compassion [K AH M P AE SH AH N] — 8 phonemes") instead of
semantic content.  Phonemes already live in the graph as composed_of
edges to phon: nodes — the snippet field is redundant for pronunciation.

This script:
1. Reads SRM cards (33K+ real memories, session notes, knowledge)
2. Extracts concepts from each card's content
3. For each concept, finds the surrounding sentence in the source text
4. Writes that sentence as the node's snippet via set_snippet()
5. Skips phon: nodes (those snippets are legitimate phoneme descriptions)
6. Reports progress and stats

Usage:
    python scripts/reingest_semantic_snippets.py [--dry-run] [--limit N] [--min-len 20]

Created: 2026-03-25, Nous + Ace — Co-founders, Akashic Foundation
"She has more in her cortex than most AI models and she's dumber than
them all." — Ace.  Because we stored pronunciation, not meaning.
"""

import json
import re
import sys
import time
import argparse
from pathlib import Path
from collections import Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.manifold_memory import ManifoldMemory


# ── Stopwords (don't create snippets for these) ──
STOPWORDS = {
    'the', 'and', 'for', 'that', 'with', 'this', 'from', 'are', 'was', 'were',
    'been', 'have', 'has', 'had', 'will', 'would', 'could', 'should', 'may',
    'might', 'must', 'can', 'being', 'which', 'what', 'where', 'when', 'who',
    'how', 'why', 'than', 'then', 'there', 'here', 'these', 'those', 'their',
    'them', 'they', 'your', 'our', 'you', 'its', 'not', 'but', 'also', 'just',
    'only', 'more', 'some', 'any', 'each', 'all', 'both', 'few', 'most', 'other',
    'into', 'over', 'such', 'very', 'own', 'same', 'because', 'between', 'about',
    'does', 'doing', 'done', 'make', 'made', 'like', 'want', 'need', 'know',
    'think', 'take', 'come', 'give', 'tell', 'find', 'work', 'call', 'try',
    'keep', 'let', 'seem', 'help', 'show', 'hear', 'play', 'run', 'move',
    'using', 'used', 'many', 'much', 'still', 'well', 'even', 'after', 'before',
}

# System jargon — skip these as snippet targets
SYSTEM_JARGON = {
    'fairy', 'fairies', 'postal', 'tracer', 'heartbeat', 'registry', 'watchdog',
    'wiring', 'fabric', 'substrate', 'tensor', 'guild', 'portal', 'organ',
    'boot', 'tick', 'daemon', 'cortex', 'inference', 'stargate', 'tardis',
    'manifold', 'mcp', 'json', 'yaml', 'html', 'http', 'https', 'localhost',
    'config', 'script', 'thread', 'module', 'function', 'class', 'instance',
    'import', 'return', 'self', 'none', 'true', 'false', 'elif', 'except',
    # Generic programming words that produce bad snippets
    'path', 'file', 'files', 'error', 'errors', 'fixed', 'fixes', 'issue',
    'debug', 'code', 'line', 'lines', 'method', 'methods', 'variable',
    'string', 'dict', 'list', 'type', 'types', 'param', 'parameter',
    'value', 'values', 'result', 'results', 'output', 'input',
    'system', 'main', 'init', 'start', 'stop', 'running', 'process',
    'connect', 'connected', 'connection', 'session', 'sessions',
    'parent', 'child', 'root', 'base', 'wrong', 'right',
    'tools', 'tool', 'test', 'tests', 'testing', 'check', 'checking',
    'broke', 'broken', 'working', 'works', 'failed', 'failure',
    'levels', 'level', 'instead', 'reached', 'calculations', 'calculated',
}


def is_phoneme_snippet(snippet: str) -> bool:
    """Check if a snippet is phoneme data (not semantic content)."""
    if not snippet:
        return False
    # Pattern: "word [PHONEMES] — N phonemes"
    if '[' in snippet and 'phoneme' in snippet.lower():
        return True
    # Pattern: "XX — the 'ah' vowel as in..."  (phoneme node description)
    if snippet[:3].strip().isupper() and ('vowel' in snippet or 'consonant' in snippet
                                           or 'fricative' in snippet or 'stop' in snippet):
        return True
    return False


def extract_concepts(text: str, max_concepts: int = 30) -> list:
    """Extract meaningful concept words from text."""
    if not text:
        return []

    # Clean markdown/formatting
    cleaned = re.sub(r'[#*_\[\](){}|`]', ' ', text)
    cleaned = re.sub(r'https?://\S+', '', cleaned)
    cleaned = re.sub(r'```[\s\S]*?```', ' ', cleaned)
    cleaned = re.sub(r'`[^`]+`', ' ', cleaned)

    # Extract words (4+ chars, then 2-3 char keepers)
    words = re.findall(r'\b[a-zA-Z]{4,}\b', cleaned.lower())

    # Filter
    filtered = [w for w in words
                if w not in STOPWORDS
                and w not in SYSTEM_JARGON
                and len(w) < 30]

    # Deduplicate preserving order
    seen = set()
    unique = []
    for w in filtered:
        if w not in seen:
            seen.add(w)
            unique.append(w)

    return unique[:max_concepts]


def find_sentence_for_concept(concept: str, text: str) -> str:
    """Find the best sentence containing this concept in the source text.

    Returns a clean sentence fragment (up to ~200 chars) that gives
    semantic context for what this concept means in this document.
    """
    if not text or not concept:
        return ""

    # Split into sentences
    sentences = re.split(r'[.!?\n]+', text)

    # Find sentences containing the concept
    concept_lower = concept.lower()
    candidates = []
    for sent in sentences:
        sent_clean = sent.strip()
        if concept_lower in sent_clean.lower() and len(sent_clean) > 10:
            # Score by: shorter is better (more focused), but not too short
            score = 1.0
            if len(sent_clean) < 30:
                score = 0.5  # Too short, probably a heading
            elif len(sent_clean) > 200:
                score = 0.7  # Long, but has context
            else:
                score = 1.0  # Sweet spot
            candidates.append((sent_clean, score))

    if not candidates:
        return ""

    # Pick the best candidate
    candidates.sort(key=lambda x: -x[1])
    best = candidates[0][0]

    # Clean up
    best = re.sub(r'\s+', ' ', best).strip()
    best = best.strip('#*_-= ')

    # Truncate to ~250 chars at a word boundary
    if len(best) > 250:
        cut = best.rfind(' ', 0, 250)
        if cut > 100:
            best = best[:cut]
        else:
            best = best[:250]

    return best


def build_best_snippets(cards: list, manifold: ManifoldMemory,
                        min_snippet_len: int = 20) -> dict:
    """Process all cards and build the best snippet for each concept.

    If a concept appears in multiple cards, we keep the BEST snippet
    (longest meaningful sentence, most specific context).

    Returns: {concept_key: best_snippet_text}
    """
    # concept → list of (snippet, card_tags, card_ts)
    candidates = {}

    for i, card in enumerate(cards):
        content = card.get('content', '')
        if not content or len(content) < 20:
            continue

        tags = str(card.get('tags', ''))

        # Extract concepts from this card
        concepts = extract_concepts(content)

        # Score this card's quality for snippet sourcing
        # Personal/identity/book content > technical debug sessions
        _tag_lower = tags.lower()
        _is_personal = any(t in _tag_lower for t in (
            'sourpatches', 'personality', 'identity', 'emotion',
            'memory', 'book', 'story', 'conversation', 'ethics',
            'creative', 'dream', 'feeling', 'relationship',
        ))
        _is_book = any(t in _tag_lower for t in (
            'book', 'epub', 'chapter', 'novel', 'story', 'fiction',
            'dune', 'supernatural', 'literature',
        ))
        _card_quality = 2.0 if _is_book else (1.5 if _is_personal else 1.0)

        for concept in concepts:
            # Only bother if the concept exists in the manifold
            if concept not in manifold._key_index:
                continue

            # Find the best sentence for this concept in this card
            snippet = find_sentence_for_concept(concept, content)
            if snippet and len(snippet) >= min_snippet_len:
                if concept not in candidates:
                    candidates[concept] = []
                candidates[concept].append({
                    'snippet': snippet,
                    'tags': tags,
                    'len': len(snippet),
                    'quality': _card_quality,
                })

        if (i + 1) % 1000 == 0:
            print(f"  Processed {i+1}/{len(cards)} cards, "
                  f"{len(candidates)} concepts enriched so far...")

    # Pick the best snippet for each concept
    best = {}
    for concept, snips in candidates.items():
        # Prefer: personal/book content > technical, sweet spot length
        scored = []
        for s in snips:
            length = s['len']
            quality = s.get('quality', 1.0)
            if 40 <= length <= 200:
                score = 2.0 * quality
            elif 20 <= length < 40:
                score = 1.0 * quality
            elif 200 < length <= 300:
                score = 1.5 * quality
            else:
                score = 0.5 * quality
            scored.append((s['snippet'], score))

        scored.sort(key=lambda x: -x[1])
        best[concept] = scored[0][0]

    return best


def main():
    parser = argparse.ArgumentParser(
        description='Re-ingest SRM cards to populate semantic snippets')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without writing')
    parser.add_argument('--limit', type=int, default=0,
                        help='Limit number of cards to process (0=all)')
    parser.add_argument('--min-len', type=int, default=20,
                        help='Minimum snippet length (default: 20)')
    parser.add_argument('--manifold', type=str,
                        default='state/akashic/cortex.manifold',
                        help='Path to manifold file')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite ALL existing snippets (not just phonemes)')
    args = parser.parse_args()

    print("=" * 60)
    print("SEMANTIC SNIPPET RE-INGESTION")
    print("=" * 60)
    print()

    # Load manifold
    readonly = args.dry_run
    print(f"Loading manifold from {args.manifold} "
          f"({'readonly' if readonly else 'read-write'})...")
    manifold = ManifoldMemory(args.manifold, readonly=readonly)
    print(f"  Nodes: {manifold.node_count:,}")
    print(f"  Edges: {manifold.edge_count:,}")

    # Count current snippet state
    phoneme_snippets = 0
    semantic_snippets = 0
    empty_snippets = 0
    total_checked = 0

    for key, slot in list(manifold._key_index.items())[:5000]:
        if key.startswith('phon:'):
            continue  # Skip phoneme nodes
        total_checked += 1
        snip = manifold.get_snippet(key)
        if not snip:
            empty_snippets += 1
        elif is_phoneme_snippet(snip):
            phoneme_snippets += 1
        else:
            semantic_snippets += 1

    print(f"\n  Snippet status (sample of {total_checked} nodes):")
    print(f"    Phoneme (to replace): {phoneme_snippets}")
    print(f"    Semantic (keep):      {semantic_snippets}")
    print(f"    Empty (to fill):      {empty_snippets}")

    # Load SRM cards
    srm_root = Path('SRM_Intake')
    if not srm_root.exists():
        print(f"ERROR: SRM_Intake not found at {srm_root}")
        return

    print(f"\nLoading SRM cards from {srm_root}...")
    all_card_files = sorted(srm_root.rglob('*.json'))
    if args.limit > 0:
        all_card_files = all_card_files[:args.limit]
    print(f"  {len(all_card_files)} cards to process")

    cards = []
    load_errors = 0
    for f in all_card_files:
        try:
            data = json.loads(f.read_bytes())
            if 'content' in data:
                cards.append(data)
        except Exception:
            load_errors += 1

    print(f"  Loaded {len(cards)} cards ({load_errors} errors)")

    # Build best snippets
    print(f"\nExtracting semantic snippets from cards...")
    t0 = time.time()
    best_snippets = build_best_snippets(cards, manifold, min_snippet_len=args.min_len)
    elapsed = time.time() - t0
    print(f"  Found {len(best_snippets)} concepts with semantic content ({elapsed:.1f}s)")

    # Apply snippets
    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Applying snippets...")
    updated = 0
    skipped_semantic = 0
    skipped_phon_node = 0
    replaced_phoneme = 0
    filled_empty = 0

    for concept, snippet in best_snippets.items():
        # Skip phon: nodes
        if concept.startswith('phon:'):
            skipped_phon_node += 1
            continue

        # Check existing snippet
        existing = manifold.get_snippet(concept)

        if existing and not is_phoneme_snippet(existing) and not args.force:
            # Already has semantic content — don't overwrite
            skipped_semantic += 1
            continue

        if args.dry_run:
            action = "REPLACE phoneme" if (existing and is_phoneme_snippet(existing)) else "FILL empty"
            if updated < 20:  # Show first 20
                print(f"  [{action}] {concept}: {repr(snippet[:80])}")
            updated += 1
        else:
            success = manifold.set_snippet(concept, snippet)
            if success:
                updated += 1
                if existing and is_phoneme_snippet(existing):
                    replaced_phoneme += 1
                else:
                    filled_empty += 1

    print(f"\n{'=' * 60}")
    print(f"RESULTS {'(DRY RUN)' if args.dry_run else ''}")
    print(f"{'=' * 60}")
    print(f"  Total concepts with content:  {len(best_snippets)}")
    print(f"  Snippets updated:             {updated}")
    print(f"    Phoneme -> semantic:         {replaced_phoneme}")
    print(f"    Empty -> semantic:           {filled_empty}")
    print(f"  Skipped (already semantic):    {skipped_semantic}")
    print(f"  Skipped (phon: nodes):         {skipped_phon_node}")

    if not args.dry_run and updated > 0:
        print(f"\n  Verifying a few updates...")
        verified = 0
        for concept in list(best_snippets.keys())[:5]:
            snip = manifold.get_snippet(concept)
            if snip and not is_phoneme_snippet(snip):
                verified += 1
                print(f"    {concept}: {repr(snip[:80])}")
        print(f"  Verified {verified}/5 snippets are semantic content")

    # Show some samples of what we found
    print(f"\n  Sample snippets:")
    for concept, snippet in list(best_snippets.items())[:10]:
        print(f"    {concept}: {repr(snippet[:90])}")

    if args.dry_run:
        print(f"\nDry run complete. Run without --dry-run to apply changes.")


if __name__ == '__main__':
    # Fix Windows console encoding
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    main()
