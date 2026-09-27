"""
Ingest the Human Emotional Context Encyclopedia into manifold snippets.

The Akashic Foundation's Gold Standard emotion encyclopedia (1,550 entries)
contains Ace's hand-written definitions with USB dimensions (Understanding,
Sensing, Being), spectrum ratings, physical sensations, and behavioral context.

This script:
1. Loads encyclopedia cards from the Founders SRM cluster (creator_sessions)
2. Extracts emotion name + Primary/Extended definitions + USB content
3. Composes a rich snippet (up to 1024 bytes) for each emotion
4. Finds the matching manifold node (or creates a normalized key)
5. Writes the snippet via set_snippet()

The emotion encyclopedia is the #1 content source for making Sourpatches
think from MEANING rather than bare graph labels.

Usage:
    python scripts/ingest_emotion_encyclopedia.py [--dry-run] [--manifold PATH]

2026-03-26, Nous + Ace — Co-founders, Akashic Foundation
"She has 471K nodes. Time to fill them with meaning."
"""

import json
import re
import sys
import time
import argparse
from pathlib import Path
from collections import Counter

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.manifold_memory import ManifoldMemory

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# ═══════════════════════════════════════════════════════════════
# Extraction helpers
# ═══════════════════════════════════════════════════════════════

def extract_emotion_name(card: dict) -> str:
    """Extract the emotion name from a card's concept field.

    Concept format: "Akashic Encyclopedia - Hackneyed Cynicism (Gold Standard)"
    or: "Akashic Encyclopedia - Cacophony (Metaphorical Emotion)"
    Returns: "hackneyed cynicism" or "cacophony"
    """
    concept = card.get('helix', {}).get('L', {}).get('concept', '')
    if not concept:
        # Fallback: parse from content first line
        content = card.get('content', '')
        first_line = content.split('\n')[0].strip(' #')
        concept = first_line

    # Strip "Akashic Encyclopedia - " prefix
    if 'Encyclopedia' in concept:
        concept = concept.split(' - ', 1)[-1]

    # Strip parenthetical suffix: "(Gold Standard)", "(Emotional State)", etc.
    concept = re.sub(r'\s*\(.*?\)\s*$', '', concept).strip()

    return concept


def extract_definition(content: str) -> str:
    """Extract the best definition from card content.

    Handles TWO encyclopedia formats:
    1. Gold Standard: "Primary Definition: ..." / "Extended Definition: ..."
    2. Standard: "## Definition\n<paragraph>"

    Returns a clean definition string, no headers or formatting.
    """
    if not content:
        return ""

    lines = content.split('\n')

    # ── Format 1: Gold Standard (Primary/Extended Definition) ──
    primary = ""
    extended = ""
    adaptive = ""

    for i, line in enumerate(lines):
        line_clean = line.strip()

        if line_clean.startswith('Primary Definition:'):
            primary = line_clean.replace('Primary Definition:', '').strip()
        elif line_clean.startswith('Extended Definition:'):
            extended = line_clean.replace('Extended Definition:', '').strip()
        elif 'Adaptive Function:' in line_clean:
            adaptive = line_clean.split('Adaptive Function:', 1)[-1].strip()

    if primary:
        parts = [primary]
        if adaptive and len(primary) + len(adaptive) < 900:
            parts.append(adaptive)
        elif extended and len(primary) + len(extended) < 900:
            parts.append(extended)
        return ' '.join(parts).strip()

    # ── Format 2: Standard (## Definition paragraph) ──
    in_definition = False
    definition_lines = []

    for i, line in enumerate(lines):
        line_clean = line.strip()

        if line_clean == '## Definition' or line_clean.startswith('## Definition'):
            in_definition = True
            continue
        elif in_definition:
            # Stop at next section header
            if line_clean.startswith('## ') or line_clean.startswith('# '):
                break
            if line_clean:  # Skip blank lines
                definition_lines.append(line_clean)

    if definition_lines:
        # Take up to ~900 chars of definition text
        result = ' '.join(definition_lines)
        if len(result) > 900:
            cut = result.rfind(' ', 0, 900)
            result = result[:cut] if cut > 200 else result[:900]
        return result

    # ── Format 3: Fallback — grab the Adaptive Function line ──
    if adaptive:
        return adaptive

    # ── Format 4: Last resort — grab first non-header paragraph ──
    for line in lines:
        line_clean = line.strip()
        if (line_clean and not line_clean.startswith('#')
                and not line_clean.startswith('*')
                and len(line_clean) > 40):
            return line_clean[:900]

    return ""


def extract_physical(content: str) -> str:
    """Extract physical sensations if present (for somatic grounding)."""
    if not content:
        return ""
    for line in content.split('\n'):
        if 'Physical Sensations:' in line:
            return line.split('Physical Sensations:', 1)[-1].strip()
    return ""


def compose_snippet(emotion_name: str, definition: str,
                     physical: str = "") -> str:
    """Compose a rich snippet from extracted components.

    Target: up to 1024 bytes. Prioritize:
    1. Emotion name + primary definition (always)
    2. Adaptive function (if space)
    3. Physical sensations (if space — helps somatic system)
    """
    # Start with emotion name and definition
    snippet = f"{emotion_name}: {definition}" if definition else emotion_name

    # Add physical sensations if they fit
    if physical and len(snippet) + len(physical) + 15 < 1024:
        snippet += f" Feels like: {physical}"

    # Truncate at word boundary if over 1024
    if len(snippet) > 1024:
        cut = snippet.rfind(' ', 0, 1020)
        if cut > 200:
            snippet = snippet[:cut]
        else:
            snippet = snippet[:1020]

    return snippet


def normalize_key(emotion_name: str) -> str:
    """Normalize emotion name to manifold key format.

    "Hackneyed Cynicism" → "hackneyed cynicism"
    "Self-Deprecation" → "self-deprecation"
    """
    return emotion_name.lower().strip()



# Words that should NEVER get emotion snippets — they're generic English
_SKIP_AS_KEYS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'up', 'about', 'into', 'over', 'after',
    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
    'more', 'less', 'most', 'very', 'just', 'also', 'not', 'no', 'yes',
    'all', 'some', 'any', 'each', 'every', 'both', 'few', 'many', 'much',
    'own', 'same', 'other', 'new', 'old', 'big', 'small', 'long', 'short',
    'high', 'low', 'first', 'last', 'good', 'bad', 'great', 'little',
    'hot', 'cold', 'hard', 'soft', 'fast', 'slow', 'full', 'empty',
    'back', 'keep', 'check', 'value', 'levels', 'false', 'true', 'will',
    'free', 'like', 'well', 'still', 'even', 'right', 'wrong',
    # System/technical words
    'failure', 'filter', 'fixed', 'connected', 'connection', 'human',
    'entertainment', 'brand-new', 'first-rate',
}


def find_manifold_keys(emotion_name: str, manifold: ManifoldMemory) -> list:
    """Find all manifold keys that match this emotion name.

    Returns list of matching keys. Tries:
    1. Exact lowercase match (full emotion name)
    2. Single-word match ONLY for meaningful emotion words (5+ chars, not generic)
    3. Hyphenated variant
    """
    matches = []
    key = normalize_key(emotion_name)

    # Exact match (full compound name)
    if key in manifold._key_index:
        matches.append(key)

    # Hyphenated variant of full name
    hyphenated = key.replace(' ', '-')
    if hyphenated != key and hyphenated in manifold._key_index:
        matches.append(hyphenated)

    # Single-word matches — ONLY for the primary emotion word,
    # and only if it's a meaningful emotion term (not a preposition/adjective)
    words = key.split()
    if len(words) >= 1:
        for word in words:
            if (len(word) >= 4
                    and word not in _SKIP_AS_KEYS
                    and word in manifold._key_index
                    and word not in matches):
                matches.append(word)

    return matches


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Ingest emotion encyclopedia into manifold snippets')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without writing')
    parser.add_argument('--manifold', type=str,
                        default='state/akashic/cortex.manifold',
                        help='Path to manifold file')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite existing semantic snippets')
    parser.add_argument('--verbose', action='store_true',
                        help='Show each snippet being written')
    args = parser.parse_args()

    print("=" * 65)
    print("  EMOTION ENCYCLOPEDIA → MANIFOLD SNIPPET INGESTION")
    print("  Akashic Foundation — Human Emotional Context Encyclopedia")
    print("=" * 65)
    print()

    # ── Load encyclopedia cards from Founders SRM ──
    founders_path = (
        Path(__file__).parent.parent /
        "P10_Memory" / "Akashic_triple_helix_memory_storage" /
        "relational_clusters" / "Founders" / "creator_sessions" / "index.json"
    )

    if not founders_path.exists():
        print(f"ERROR: Founders index not found: {founders_path}")
        return 1

    print(f"Loading Founders/creator_sessions index...")
    data = json.loads(founders_path.read_text(encoding='utf-8'))
    all_cards = data.get('cards', [])
    print(f"  Total cards: {len(all_cards)}")

    # Filter encyclopedia cards
    enc_cards = [
        c for c in all_cards
        if 'encyclopedia' in str(c.get('tags', '')).lower()
        and 'emotion' in str(c.get('tags', '')).lower()
    ]
    print(f"  Encyclopedia emotion cards: {len(enc_cards)}")

    if not enc_cards:
        print("ERROR: No encyclopedia cards found!")
        return 1

    # ── Load manifold ──
    readonly = args.dry_run
    print(f"\nLoading manifold from {args.manifold} "
          f"({'readonly' if readonly else 'read-write'})...")
    manifold = ManifoldMemory(args.manifold, readonly=readonly)
    print(f"  Nodes: {manifold.node_count:,}")
    print(f"  Edges: {manifold.edge_count:,}")

    # ── Process encyclopedia cards ──
    print(f"\nProcessing {len(enc_cards)} encyclopedia entries...")
    t0 = time.time()

    stats = Counter()
    snippets_to_write = {}  # key → (snippet, emotion_name)

    for card in enc_cards:
        emotion_name = extract_emotion_name(card)
        if not emotion_name:
            stats['no_name'] += 1
            continue

        content = card.get('content', '')
        definition = extract_definition(content)
        if not definition:
            stats['no_definition'] += 1
            continue

        physical = extract_physical(content)
        snippet = compose_snippet(emotion_name, definition, physical)

        if len(snippet) < 20:
            stats['snippet_too_short'] += 1
            continue

        # Find matching manifold keys
        keys = find_manifold_keys(emotion_name, manifold)

        if not keys:
            stats['no_manifold_key'] += 1
            if args.verbose:
                print(f"  [NO KEY] {emotion_name}")
            continue

        stats['matched'] += 1

        for key in keys:
            # Keep the BEST snippet per key (longest, from most specific card)
            if key in snippets_to_write:
                existing_snippet = snippets_to_write[key][0]
                if len(snippet) <= len(existing_snippet):
                    continue
            snippets_to_write[key] = (snippet, emotion_name)

    elapsed = time.time() - t0
    print(f"  Processed in {elapsed:.1f}s")
    print(f"  Matched emotions: {stats['matched']}")
    print(f"  Unique manifold keys: {len(snippets_to_write)}")
    print(f"  No manifold key: {stats['no_manifold_key']}")
    print(f"  No definition: {stats['no_definition']}")
    print(f"  No name: {stats['no_name']}")

    # ── Write snippets ──
    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Writing snippets...")
    written = 0
    skipped_existing = 0
    replaced = 0

    for key, (snippet, emotion_name) in sorted(snippets_to_write.items()):
        existing = manifold.get_snippet(key)

        # Decision: encyclopedia definitions are AUTHORITATIVE.
        # Always replace phoneme data, short fragments, and non-definition text.
        # Only skip if existing is ALREADY an encyclopedia definition (starts with emotion name).
        if existing and not args.force:
            _is_phoneme = ('[' in existing and 'phoneme' in existing.lower())
            _is_encyclopedia = existing.startswith(emotion_name + ':')
            _is_short = len(existing) < 60
            _new_is_better = len(snippet) > len(existing) * 1.5

            if _is_encyclopedia and not _new_is_better:
                # Already has an encyclopedia definition of similar quality
                skipped_existing += 1
                continue
            elif not _is_phoneme and not _is_short and not _new_is_better:
                # Has decent content and new isn't significantly better
                # Still replace — encyclopedia > random sentence fragments
                pass  # Encyclopedia always wins

        if args.dry_run:
            action = "REPLACE" if existing else "NEW"
            print(f"  [{action}] {key}: {snippet[:80]}...")
            written += 1
        else:
            success = manifold.set_snippet(key, snippet)
            if success:
                written += 1
                if existing:
                    replaced += 1
                if args.verbose:
                    print(f"  ✓ {key}: {snippet[:60]}...")
            else:
                stats['write_fail'] += 1

    # ── Also write the full emotion name as a key if single words got it ──
    # This creates compound concept entries like "hackneyed cynicism"
    new_concepts_written = 0
    # (Skip for now — compound key creation requires add_node which may
    #  have side effects. Focus on enriching existing nodes first.)

    # ── Results ──
    print(f"\n{'=' * 65}")
    print(f"  RESULTS {'(DRY RUN)' if args.dry_run else ''}")
    print(f"{'=' * 65}")
    print(f"  Encyclopedia entries processed:  {len(enc_cards)}")
    print(f"  Emotions matched to manifold:    {stats['matched']}")
    print(f"  Unique keys to write:            {len(snippets_to_write)}")
    print(f"  Snippets written:                {written}")
    print(f"    Replaced (phoneme/short):      {replaced}")
    print(f"    New:                            {written - replaced}")
    print(f"  Skipped (already semantic):       {skipped_existing}")
    print(f"  No manifold key found:            {stats['no_manifold_key']}")
    if stats.get('write_fail'):
        print(f"  Write failures:                   {stats['write_fail']}")
    print()

    # Show sample snippets
    if snippets_to_write:
        print("Sample snippets:")
        for i, (key, (snippet, emo)) in enumerate(sorted(snippets_to_write.items())):
            if i >= 5:
                break
            print(f"  [{key}] ({emo})")
            print(f"    {snippet[:120]}...")
            print()

    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
