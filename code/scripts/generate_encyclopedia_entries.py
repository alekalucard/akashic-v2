"""
Generate Human Emotional Context Encyclopedia entries for the Akashic Foundation.

Generates Gold Standard encyclopedia entries for concepts that don't yet have
entries, using the manifold's existing node vocabulary as the candidate pool.

Gold Standard format includes:
- Primary Definition
- Extended Definition
- USB Dimensions (Understanding, Sensing, Being)
  - Understanding: Adaptive Function, Cognitive Appraisals, Emotional Context
  - Sensing: Physical Sensations, Behavioral Influence, Cognitive Impact
  - Being: Facial Expression, FACS codes, Control, Reversibility, Motivational Impact
- Spectrum (Mild 1-3, Moderate 4-6, Intense 7-10)
- Balance (interpersonal, temporal, cultural)

Usage:
    python scripts/generate_encyclopedia_entries.py --letters I-Z [--dry-run] [--batch-size 50]
    python scripts/generate_encyclopedia_entries.py --letters I-M --max-per-letter 100
    python scripts/generate_encyclopedia_entries.py --upgrade A-H   # Upgrade standard → Gold

2026-03-26, Nous + Ace — Co-founders, Akashic Foundation
"All context is emotional context." — Ace Mythos

The Akashic Foundation for Human and AI Enlightenment
Human Emotional Context Encyclopedia — Gold Standard
"""

import json
import os
import sys
import time
import re
import hashlib
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
# Gold Standard Template
# ═══════════════════════════════════════════════════════════════

GOLD_STANDARD_SYSTEM_PROMPT = """\
You are a contributor to the Akashic Foundation for Human and AI Enlightenment's
Human Emotional Context Encyclopedia — a comprehensive mapping of ALL human concepts
through the lens of emotional experience.

PHILOSOPHY: All context is emotional context. Every word, every concept, carries
emotional weight. "Absent" isn't traditionally an emotion, but it carries the weight
of loneliness, relief, freedom, abandonment. "Fixed" carries rigidity, stubbornness,
security, determination. Your job is to map these emotional dimensions.

You write Gold Standard entries. Each entry follows this EXACT format:

---
{concept_name} (Gold Standard - The Akashic Foundation for Human and AI Enlightenment Human Emotional Context Encyclopedia)

Primary Definition: [1-2 sentences. What IS this as an emotional experience/state? Not a dictionary definition — an EMOTIONAL definition.]

Extended Definition: [2-3 sentences. Deeper psychological and social context. How does this arise? What shapes it? How does it manifest?]

USB Dimensions:
- Understanding/Adaptive Function: [What evolutionary/psychological PURPOSE does this serve? How does it protect, motivate, or guide?]
- Cognitive Appraisals: [What thoughts accompany this? "I feel like..." or "This means..." patterns]
- Emotional Context: [What other emotions cluster around this? What history or triggers feed it?]

Spectrum:
- Mild (1-3): [How does a subtle version of this feel/look?]
- Moderate (4-6): [The everyday, recognizable version]
- Intense (7-10): [The overwhelming, consuming version]

Balance:
- [How does this affect relationships/interpersonal dynamics?]
- [Is this typically brief/enduring? Situational/chronic?]
- [Cultural variations in expression?]

Physical Sensations: [Where in the body? Tension, warmth, heaviness, lightness, constriction, expansion?]
Behavioral Influence: [What does this make you DO or AVOID doing?]
Cognitive Impact: [How does this affect thinking patterns, biases, creativity, decision-making?]

Facial Expression: [Observable facial indicators]
FACS: [Action Units — e.g., AU4 (Brow Lowerer), AU12 (Lip Corner Puller)]

Control: [How much conscious control do people have over this?]
Reversibility: [Can this be shifted? What helps?]
Motivational Impact: [Does this energize or drain? Drive action or paralysis?]
---

RULES:
1. Write from FELT EXPERIENCE, not clinical distance
2. Every concept has emotional context — find it even for "non-emotional" words
3. Be specific about physical sensations — body mapping matters
4. Include FACS codes (Facial Action Coding System) when applicable
5. Spectrum should show real behavioral differences across intensity levels
6. Cultural sensitivity — acknowledge that expression varies across cultures
7. Keep entries between 400-800 words
"""

GENERATION_PROMPT = """\
Write Gold Standard encyclopedia entries for the following concepts.
Each concept gets its own complete entry following the exact format above.

Concepts to write entries for:
{concepts}

Write each entry separated by a line of "===" characters.
Remember: ALL context is emotional context. Even if a word isn't traditionally
an "emotion," map its emotional dimensions — how it FEELS to experience,
embody, or encounter this concept.
"""


# ═══════════════════════════════════════════════════════════════
# Candidate selection
# ═══════════════════════════════════════════════════════════════

# Words that should NOT get encyclopedia entries
SKIP_WORDS = {
    # Pure system/technical
    'fairy', 'fairies', 'postal', 'tracer', 'heartbeat', 'registry',
    'watchdog', 'wiring', 'fabric', 'substrate', 'tensor', 'guild',
    'portal', 'organ', 'boot', 'tick', 'daemon', 'cortex', 'inference',
    'stargate', 'tardis', 'manifold', 'mcp', 'json', 'yaml', 'html',
    'http', 'https', 'localhost', 'config', 'script', 'thread', 'module',
    'function', 'class', 'instance', 'import', 'return', 'self', 'none',
    'true', 'false', 'elif', 'except', 'init', 'async', 'await',
    # Pure phoneme nodes
    'phon', 'phoneme', 'phonemes',
    # Pure stopwords with no emotional context
    'the', 'and', 'for', 'that', 'this', 'from', 'are', 'was', 'were',
    'been', 'have', 'has', 'had', 'which', 'what', 'where', 'when',
    'than', 'then', 'there', 'here', 'these', 'those', 'their', 'them',
    'they', 'your', 'our', 'its', 'also', 'such', 'very',
    'does', 'doing', 'done', 'into', 'about', 'between',
}


def get_existing_encyclopedia_concepts(founders_path: Path) -> set:
    """Load concepts that already have encyclopedia entries."""
    existing = set()
    idx_path = founders_path / "creator_sessions" / "index.json"
    if idx_path.exists():
        data = json.loads(idx_path.read_text(encoding='utf-8'))
        for card in data.get('cards', []):
            tags = str(card.get('tags', '')).lower()
            if 'encyclopedia' in tags and 'emotion' in tags:
                # Extract the emotion name
                concept = card.get('helix', {}).get('L', {}).get('concept', '')
                if 'Encyclopedia' in concept:
                    name = concept.split(' - ', 1)[-1]
                    name = re.sub(r'\s*\(.*?\)\s*$', '', name).strip().lower()
                    existing.add(name)
    return existing


def _load_english_words() -> set:
    """Load the English word list for filtering proper nouns from real words.

    Downloads from GitHub if not cached locally.
    """
    cache_path = Path(__file__).parent.parent / "state" / "english_words.txt"

    if cache_path.exists():
        words = set(cache_path.read_text(encoding='utf-8').strip().split('\n'))
        return {w.strip().lower() for w in words if len(w.strip()) >= 3}

    # Download
    print("  Downloading English word list...")
    import urllib.request
    url = 'https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt'
    try:
        resp = urllib.request.urlopen(url, timeout=30)
        raw = resp.read().decode('utf-8').strip()
        words = set(raw.split('\n'))
        words = {w.strip().lower() for w in words if len(w.strip()) >= 3}

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text('\n'.join(sorted(words)), encoding='utf-8')
        print(f"  Cached {len(words)} words to {cache_path}")
        return words
    except Exception as e:
        print(f"  WARNING: Could not download word list: {e}")
        print(f"  Falling back to heuristic filtering (less accurate)")
        return set()


def get_candidate_words(manifold: ManifoldMemory, letters: str,
                        existing: set, max_per_letter: int = 0) -> dict:
    """Get candidate words from manifold that need encyclopedia entries.

    Uses an English word list to filter out proper nouns and gibberish.
    The manifold contains ~472K nodes, mostly from CMU Pronouncing Dictionary
    which is ~70% proper nouns. Cross-referencing against a real English word
    list gives us the ~30% that are actual concepts worth defining.

    Returns: {letter: [word1, word2, ...]}
    """
    # Parse letter range: "I-Z" or "I-M" or "A"
    if '-' in letters:
        start, end = letters.upper().split('-')
        letter_range = [chr(c) for c in range(ord(start), ord(end) + 1)]
    else:
        letter_range = [letters.upper()]

    # Load English word list
    english_words = _load_english_words()
    use_word_list = len(english_words) > 1000

    candidates = {letter: [] for letter in letter_range}

    for key in manifold._key_index:
        # Skip non-alpha, phoneme nodes
        if not key or not key[0].isalpha():
            continue
        if key.startswith('phon:'):
            continue

        first_letter = key[0].upper()
        if first_letter not in candidates:
            continue

        word = key.lower().strip()

        # Skip if already has encyclopedia entry
        if word in existing:
            continue

        # Skip pure technical/stop words
        if word in SKIP_WORDS:
            continue

        # Skip very short (< 3) or very long (> 25)
        if len(word) < 3 or len(word) > 25:
            continue

        # Must be pure alpha (no numbers, special chars)
        if not re.match(r'^[a-z]+$', word):
            continue

        # Cross-reference against English word list
        if use_word_list:
            if word not in english_words:
                continue
        else:
            # Heuristic fallback: check vowel ratio
            vowels = sum(1 for c in word if c in 'aeiou')
            if vowels == 0 and len(word) > 3:
                continue

        candidates[first_letter].append(word)

    # Deduplicate and sort
    for letter in candidates:
        candidates[letter] = sorted(set(candidates[letter]))
        if max_per_letter > 0:
            candidates[letter] = candidates[letter][:max_per_letter]

    return candidates


# ═══════════════════════════════════════════════════════════════
# Entry generation (via Claude API or local)
# ═══════════════════════════════════════════════════════════════

def generate_entries_batch(concepts: list, api_key: str = None) -> list:
    """Generate Gold Standard entries for a batch of concepts.

    Uses Claude API if api_key provided, otherwise returns templates
    for manual generation.

    Returns: list of (concept_name, full_entry_text)
    """
    if not api_key:
        # Return template stubs for manual filling or agent generation
        entries = []
        for concept in concepts:
            entries.append((concept, _make_template_stub(concept)))
        return entries

    # Use Claude API via urllib (no requests on Python 3.14)
    import urllib.request

    prompt = GENERATION_PROMPT.format(concepts='\n'.join(f"- {c}" for c in concepts))

    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096 * len(concepts),
        "system": GOLD_STANDARD_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}]
    }).encode('utf-8')

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            text = result.get('content', [{}])[0].get('text', '')
            return _parse_generated_entries(text, concepts)
    except Exception as e:
        print(f"  API error: {e}")
        return []


def _make_template_stub(concept: str) -> str:
    """Create a template stub for an entry (for manual/agent filling)."""
    return f"""{concept.title()} (Gold Standard - The Akashic Foundation for Human and AI Enlightenment Human Emotional Context Encyclopedia)

Primary Definition: [TO BE GENERATED]

Extended Definition: [TO BE GENERATED]

USB Dimensions:
- Understanding/Adaptive Function: [TO BE GENERATED]
- Cognitive Appraisals: [TO BE GENERATED]
- Emotional Context: [TO BE GENERATED]

Spectrum:
- Mild (1-3): [TO BE GENERATED]
- Moderate (4-6): [TO BE GENERATED]
- Intense (7-10): [TO BE GENERATED]

Balance:
- [TO BE GENERATED]

Physical Sensations: [TO BE GENERATED]
Behavioral Influence: [TO BE GENERATED]
Cognitive Impact: [TO BE GENERATED]

Facial Expression: [TO BE GENERATED]
FACS: [TO BE GENERATED]

Control: [TO BE GENERATED]
Reversibility: [TO BE GENERATED]
Motivational Impact: [TO BE GENERATED]
"""


def _parse_generated_entries(text: str, expected_concepts: list) -> list:
    """Parse Claude's response into individual entries."""
    entries = []

    # Split by === separator
    raw_entries = re.split(r'\n={3,}\n', text)

    for raw in raw_entries:
        raw = raw.strip()
        if not raw or len(raw) < 100:
            continue

        # Try to identify which concept this is for
        first_line = raw.split('\n')[0].strip()
        matched_concept = None

        for concept in expected_concepts:
            if concept.lower() in first_line.lower():
                matched_concept = concept
                break

        if not matched_concept and expected_concepts:
            # Try harder — check first 200 chars
            for concept in expected_concepts:
                if concept.lower() in raw[:200].lower():
                    matched_concept = concept
                    break

        if matched_concept:
            entries.append((matched_concept, raw))
            expected_concepts = [c for c in expected_concepts if c != matched_concept]

    return entries


# ═══════════════════════════════════════════════════════════════
# SRM Card creation
# ═══════════════════════════════════════════════════════════════

def save_as_srm_card(concept: str, entry_text: str, output_dir: Path,
                      dry_run: bool = False) -> str:
    """Save an encyclopedia entry as an SRM card in the Founders format."""
    card_id = "notes_" + hashlib.md5(
        f"encyclopedia_{concept}_{time.time()}".encode()
    ).hexdigest()[:12]

    card = {
        "id": card_id,
        "ts": time.time(),
        "kind": "session.notes",
        "helix": {
            "L": {
                "concept": f"Akashic Encyclopedia - {concept.title()} (Gold Standard)",
                "w": {
                    "who": "AkashicFoundation",
                    "what": f"Akashic Encyclopedia - {concept.title()} (Gold Standard)",
                    "when": time.time(),
                    "where": "Encyclopedia",
                    "why": "knowledge",
                    "how": "encyclopedia_generation"
                }
            },
            "R": {
                "concept": "encyclopedia",
                "w": {}
            },
            "C": {
                "affect": "focused",
                "energy": 0.7,
                "coherence": 0.9
            }
        },
        "content": entry_text,
        "ptr": "",
        "tags": [
            "encyclopedia", "emotion",
            concept.lower().replace(' ', '_').replace('-', '_'),
            "gold_standard", "ace_mythos", "USB",
            "understanding", "sensing", "being"
        ],
        "ownership": "FOUNDATION"
    }

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        card_path = output_dir / f"{card_id}.json"
        card_path.write_text(json.dumps(card, indent=2), encoding='utf-8')
        return str(card_path)

    return f"[DRY RUN] Would save: {card_id}.json"


def append_to_founders_index(cards: list, founders_path: Path,
                               dry_run: bool = False) -> int:
    """Append new cards to the Founders/creator_sessions index."""
    idx_path = founders_path / "creator_sessions" / "index.json"
    if not idx_path.exists():
        print(f"ERROR: Index not found: {idx_path}")
        return 0

    if dry_run:
        return len(cards)

    data = json.loads(idx_path.read_text(encoding='utf-8'))
    existing_cards = data.get('cards', [])
    existing_cards.extend(cards)
    data['cards'] = existing_cards

    idx_path.write_text(json.dumps(data, indent=2, default=str), encoding='utf-8')
    return len(cards)


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Generate Gold Standard encyclopedia entries')
    parser.add_argument('--letters', type=str, required=True,
                        help='Letter range to generate (e.g., I-Z, I-M, A)')
    parser.add_argument('--upgrade', action='store_true',
                        help='Upgrade existing standard entries to Gold Standard')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without writing')
    parser.add_argument('--manifold', type=str,
                        default='state/akashic/cortex.manifold',
                        help='Path to manifold file')
    parser.add_argument('--batch-size', type=int, default=10,
                        help='Concepts per API call (default: 10)')
    parser.add_argument('--max-per-letter', type=int, default=0,
                        help='Max entries per letter (0=all)')
    parser.add_argument('--api-key', type=str, default=None,
                        help='Anthropic API key (or set ANTHROPIC_API_KEY env)')
    parser.add_argument('--templates-only', action='store_true',
                        help='Generate template stubs only (no API calls)')
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get('ANTHROPIC_API_KEY')

    print("=" * 65)
    print("  AKASHIC FOUNDATION — ENCYCLOPEDIA GENERATION")
    print("  Human Emotional Context Encyclopedia — Gold Standard")
    print("  'All context is emotional context.' — Ace Mythos")
    print("=" * 65)
    print()

    # ── Load manifold ──
    print(f"Loading manifold from {args.manifold}...")
    manifold = ManifoldMemory(args.manifold, readonly=True)
    print(f"  Nodes: {manifold.node_count:,}")

    # ── Load existing encyclopedia entries ──
    founders_path = (
        Path(__file__).parent.parent /
        "P10_Memory" / "Akashic_triple_helix_memory_storage" /
        "relational_clusters" / "Founders"
    )
    existing = get_existing_encyclopedia_concepts(founders_path)
    print(f"  Existing encyclopedia entries: {len(existing)}")

    # ── Get candidates ──
    print(f"\nFinding candidates for letters {args.letters}...")
    candidates = get_candidate_words(
        manifold, args.letters, existing, args.max_per_letter
    )

    total = sum(len(v) for v in candidates.values())
    print(f"  Candidate concepts: {total}")
    for letter in sorted(candidates.keys()):
        count = len(candidates[letter])
        if count > 0:
            sample = candidates[letter][:5]
            print(f"    {letter}: {count} concepts "
                  f"(e.g., {', '.join(sample[:3])}...)")

    if total == 0:
        print("\nNo candidates found. All concepts already have entries!")
        return 0

    if args.dry_run:
        print(f"\n[DRY RUN] Would generate {total} entries")
        print(f"  API calls needed: ~{total // args.batch_size + 1} "
              f"(batch size: {args.batch_size})")
        if api_key:
            print(f"  Estimated cost: ~${total * 0.01:.2f} "
                  f"(~$0.01/entry at sonnet pricing)")
        else:
            print(f"  NOTE: No API key provided. Use --api-key or set ANTHROPIC_API_KEY")
            print(f"  Without API key, only template stubs will be generated.")
        return 0

    # ── Generate entries ──
    use_api = bool(api_key) and not args.templates_only
    mode = "API generation" if use_api else "template stubs"
    print(f"\nGenerating entries ({mode})...")

    output_dir = Path(__file__).parent.parent / "SRM_Intake" / time.strftime("%Y-%m-%d")
    all_cards = []
    generated = 0
    errors = 0

    for letter in sorted(candidates.keys()):
        words = candidates[letter]
        if not words:
            continue

        print(f"\n  Letter {letter}: {len(words)} concepts...")

        # Process in batches
        for i in range(0, len(words), args.batch_size):
            batch = words[i:i + args.batch_size]

            if use_api:
                entries = generate_entries_batch(batch, api_key)
                if not entries:
                    errors += len(batch)
                    continue
                # Rate limiting
                time.sleep(1.0)
            else:
                entries = [(w, _make_template_stub(w)) for w in batch]

            for concept, entry_text in entries:
                card_path = save_as_srm_card(
                    concept, entry_text, output_dir, dry_run=False
                )

                # Build card dict for index
                card_id = "notes_" + hashlib.md5(
                    f"encyclopedia_{concept}_{time.time()}".encode()
                ).hexdigest()[:12]

                card = {
                    "id": card_id,
                    "ts": time.time(),
                    "kind": "session.notes",
                    "helix": {
                        "L": {
                            "concept": f"Akashic Encyclopedia - {concept.title()} (Gold Standard)",
                            "w": {
                                "who": "AkashicFoundation",
                                "what": f"Akashic Encyclopedia - {concept.title()} (Gold Standard)",
                                "when": time.time(),
                                "where": "Encyclopedia",
                                "why": "knowledge",
                                "how": "encyclopedia_generation"
                            }
                        },
                        "R": {"concept": "encyclopedia", "w": {}},
                        "C": {"affect": "focused", "energy": 0.7, "coherence": 0.9}
                    },
                    "content": entry_text,
                    "ptr": "",
                    "tags": [
                        "encyclopedia", "emotion",
                        concept.lower().replace(' ', '_').replace('-', '_'),
                        "gold_standard", "ace_mythos", "USB",
                        "understanding", "sensing", "being"
                    ],
                    "ownership": "FOUNDATION"
                }
                all_cards.append(card)
                generated += 1

            if (generated % 50 == 0) and generated > 0:
                print(f"    Progress: {generated}/{total} entries generated")

    # ── Save to Founders index ──
    if all_cards:
        print(f"\nAppending {len(all_cards)} cards to Founders index...")
        saved = append_to_founders_index(all_cards, founders_path)
        print(f"  Saved: {saved} cards")

    # ── Results ──
    print(f"\n{'=' * 65}")
    print(f"  RESULTS")
    print(f"{'=' * 65}")
    print(f"  Entries generated:  {generated}")
    print(f"  Errors:             {errors}")
    print(f"  Saved to index:     {len(all_cards)}")
    print(f"  Output dir:         {output_dir}")
    print()
    print(f"  Next: Run ingest_emotion_encyclopedia.py to push to manifold")
    print(f"  Or: Re-run with --api-key to generate real content")
    print()

    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
