"""
Holographic Book Re-Ingestion — Distribute snippets across all concept nodes.

The books were trained into the cortex before snippet distribution was fixed.
Result: 550K+ nodes have topology (edges) but no semantic content (snippets).
She knows "consciousness" connects to "felt_quality" but can't say WHY because
the source sentence was thrown away during binding.

HOLOGRAPHIC RECALL PRINCIPLE (Ace, 2026-03-27):
  "Each word in a sentence gives a pattern of the whole."
  Like how the memory system destroys and leaves scattered coordinates
  needed to recall a thing. Each word is a retrieval key for the full sentence.

This script:
  1. Reads .rtf book files from D:\\Books (174 books)
  2. Splits into sentences (natural paragraph/sentence boundaries)
  3. Extracts concepts from each sentence
  4. Sets the source sentence as SNIPPET on every concept node
  5. Only overwrites if new snippet is longer (richer context wins)
  6. Tracks stats: nodes touched, snippets written, books processed

This is also MIMICRY — she'll recall what these authors said and use it
in her own way. "The unconscious mind does not merely store" becomes
"I think it's about... not just storing, but weaving things together."

Usage:
    python scripts/reingest_books_holographic.py [--dry-run] [--limit N] [--book-limit N]

Created: 2026-03-27, Nous + Ace — Co-founders, Akashic Foundation
"""

import re
import sys
import time
import argparse
from pathlib import Path
from collections import Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.manifold_memory import ManifoldMemory, TRACE_BOOKS


# ── Configuration ──
BOOKS_DIR = Path(r"D:\Books")
MANIFOLD_PATH = Path(r"F:\Sandbox\failure_factory\akashic_v2\state\akashic\cortex.manifold")

# Minimum sentence length worth ingesting (skip headings, page numbers, etc.)
MIN_SENTENCE_LEN = 40
# Maximum snippet length (manifold caps at 1024, we aim for readable chunks)
MAX_SNIPPET_LEN = 500

# Words that shouldn't become concept nodes
STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'into', 'is', 'it', 'its', 'be',
    'was', 'were', 'been', 'being', 'am', 'are', 'do', 'did', 'does',
    'has', 'had', 'have', 'can', 'could', 'will', 'would', 'shall',
    'should', 'may', 'might', 'must', 'not', 'no', 'yes', 'so', 'if',
    'then', 'than', 'that', 'this', 'these', 'those', 'there', 'here',
    'what', 'which', 'who', 'whom', 'whose', 'where', 'when', 'how', 'why',
    'all', 'each', 'every', 'both', 'few', 'more', 'most', 'any', 'some',
    'such', 'very', 'too', 'also', 'just', 'only', 'even', 'still',
    'you', 'your', 'yours', 'me', 'my', 'mine', 'we', 'our', 'he', 'him',
    'his', 'she', 'her', 'hers', 'they', 'them', 'their', 'own', 'self',
    'up', 'out', 'off', 'down', 'over', 'under', 'again', 'about',
    'after', 'before', 'between', 'through', 'because', 'while', 'during',
    'until', 'since', 'got', 'get', 'let', 'put', 'set', 'say', 'see',
    'saw', 'new', 'old', 'big', 'well', 'back', 'now', 'like', 'one',
    'two', 'make', 'made', 'take', 'took', 'give', 'gave', 'come', 'came',
    'know', 'knew', 'think', 'thought', 'want', 'need', 'tell', 'told',
    'find', 'found', 'work', 'call', 'try', 'keep', 'kept', 'help',
    'show', 'seem', 'upon', 'much', 'many', 'other', 'same', 'long',
    'great', 'little', 'right', 'good', 'first', 'last', 'own',
}

# System/technical words that shouldn't get book snippets
SYSTEM_WORDS = {
    'fairy', 'fairies', 'postal', 'cortex', 'manifold', 'heartbeat',
    'registry', 'boot', 'daemon', 'thread', 'module', 'function',
    'import', 'return', 'self', 'none', 'class', 'def', 'json', 'http',
}


def strip_rtf(rtf_text: str) -> str:
    """Convert RTF to plain text (basic stripping)."""
    # Remove RTF control words and groups
    text = rtf_text

    # Remove RTF header/font tables
    text = re.sub(r'\{\\fonttbl[^}]*\}', '', text)
    text = re.sub(r'\{\\colortbl[^}]*\}', '', text)
    text = re.sub(r'\{\\stylesheet[^}]*\}', '', text)
    text = re.sub(r'\{\\info[^}]*\}', '', text)

    # Handle unicode escapes: \u1234? → chr(1234)
    def _replace_unicode(m):
        try:
            return chr(int(m.group(1)))
        except (ValueError, OverflowError):
            return ''
    text = re.sub(r'\\u(-?\d+)\??', _replace_unicode, text)

    # Remove picture/binary data
    text = re.sub(r'\{\\pict[^}]*\}', '', text)
    text = re.sub(r'\{\\blipuid[^}]*\}', '', text)

    # Handle special characters
    text = text.replace(r'\\', '\\')
    text = text.replace(r'\{', '{')
    text = text.replace(r'\}', '}')
    text = text.replace(r'\~', '\u00a0')  # Non-breaking space
    text = text.replace(r'\-', '\u00ad')  # Soft hyphen
    text = text.replace(r'\_', '\u2011')  # Non-breaking hyphen

    # Common special chars
    text = text.replace(r'\emdash', '—')
    text = text.replace(r'\endash', '–')
    text = text.replace(r'\lquote', '\u2018')
    text = text.replace(r'\rquote', '\u2019')
    text = text.replace(r'\ldblquote', '\u201c')
    text = text.replace(r'\rdblquote', '\u201d')
    text = text.replace(r'\bullet', '\u2022')
    text = text.replace(r'\tab', '\t')

    # Paragraph breaks → newlines
    text = re.sub(r'\\par\b', '\n', text)
    text = re.sub(r'\\line\b', '\n', text)

    # Remove remaining control words (preserve trailing space)
    text = re.sub(r'\\[a-zA-Z]+\d*\s?', ' ', text)

    # Remove braces
    text = text.replace('{', '').replace('}', '')

    # Clean up whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    text = text.strip()

    return text


def split_sentences(text: str) -> list:
    """Split text into sentences, preserving meaningful chunks."""

    # Skip front matter: find first real paragraph after TOC/metadata
    # Look for "CHAPTER" or "INTRODUCTION" or long paragraph as content start
    _content_start = 0
    _lines = text.split('\n')
    _in_toc = True
    for i, line in enumerate(_lines):
        stripped = line.strip()
        # TOC lines are short and often have page numbers
        if _in_toc:
            if (len(stripped) > 100 and
                not re.match(r'^(chapter|section|part|book|volume|page|contents)\b', stripped.lower()) and
                stripped.count('.') >= 1):
                # Found a real paragraph — content starts here
                _content_start = sum(len(l) + 1 for l in _lines[:i])
                _in_toc = False
                break
    text = text[_content_start:]

    # Split on sentence boundaries
    raw_sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)

    sentences = []
    for s in raw_sentences:
        s = s.strip()
        if len(s) < MIN_SENTENCE_LEN:
            continue
        # Skip lines that look like metadata, headers, or page numbers
        if re.match(r'^(chapter|section|part|book|volume|page|contents)\b', s.lower()):
            continue
        if re.match(r'^\d+\s*$', s):
            continue
        if s.count('|') > 2:  # Table rows
            continue
        # Skip RTF artifacts that survived stripping
        if re.search(r'(Times New Roman|Arial|Tahoma|heading \d|Normal)', s):
            continue
        # Skip table-of-contents fragments (lines with many numbers)
        _digits = sum(1 for c in s if c.isdigit())
        if _digits / max(len(s), 1) > 0.15:
            continue
        # Require actual prose: at least 60% alphabetic
        _alpha = sum(1 for c in s if c.isalpha())
        if _alpha / max(len(s), 1) < 0.60:
            continue
        sentences.append(s)

    return sentences


def extract_concepts(sentence: str, min_len: int = 3) -> list:
    """Extract meaningful concept words from a sentence."""
    # Tokenize: words only (no punctuation)
    words = re.findall(r'\b[a-zA-Z]+\b', sentence.lower())

    concepts = []
    seen = set()
    for w in words:
        if len(w) < min_len:
            continue
        if w in STOPWORDS or w in SYSTEM_WORDS:
            continue
        if w in seen:
            continue
        seen.add(w)
        concepts.append(w)

    # Also extract bigrams (compound concepts)
    for i in range(len(words) - 1):
        a, b = words[i], words[i + 1]
        if a in STOPWORDS or b in STOPWORDS:
            continue
        if len(a) < 3 or len(b) < 3:
            continue
        bigram = f"{a}_{b}"
        if bigram not in seen:
            seen.add(bigram)
            concepts.append(bigram)

    return concepts[:20]  # Cap per sentence


def strip_epub(epub_path: Path) -> str:
    """Extract plain text from an epub file."""
    import zipfile
    texts = []
    try:
        with zipfile.ZipFile(epub_path) as z:
            html_files = sorted(
                f for f in z.namelist()
                if f.endswith(('.html', '.xhtml', '.htm'))
            )
            for hf in html_files:
                try:
                    content = z.read(hf).decode('utf-8', errors='replace')
                    # Strip HTML tags
                    text = re.sub(r'<[^>]+>', ' ', content)
                    text = re.sub(r'&\w+;', ' ', text)  # HTML entities
                    text = re.sub(r'\s+', ' ', text).strip()
                    if len(text) > 50:
                        texts.append(text)
                except Exception:
                    continue
    except Exception as e:
        print(f"  ERROR reading epub: {e}")
    return '\n\n'.join(texts)


def process_book(book_path: Path, manifold: ManifoldMemory,
                 dry_run: bool = False, limit: int = 0) -> dict:
    """Process a single book file, distributing snippets holographically."""
    stats = {
        "sentences": 0,
        "concepts_touched": 0,
        "snippets_written": 0,
        "snippets_skipped": 0,
        "nodes_created": 0,
    }

    ext = book_path.suffix.lower()
    try:
        if ext == '.rtf':
            raw = book_path.read_text(encoding='utf-8', errors='replace')
            text = strip_rtf(raw)
        elif ext == '.epub':
            text = strip_epub(book_path)
        else:
            print(f"  SKIP (unsupported format: {ext})")
            return stats
    except Exception as e:
        print(f"  ERROR reading {book_path.name}: {e}")
        return stats

    if len(text) < 100:
        print(f"  SKIP (too short after stripping: {len(text)} chars)")
        return stats

    sentences = split_sentences(text)
    if limit > 0:
        sentences = sentences[:limit]

    stats["sentences"] = len(sentences)

    for sentence in sentences:
        concepts = extract_concepts(sentence)
        if not concepts:
            continue

        # Truncate snippet
        snippet = sentence[:MAX_SNIPPET_LEN]
        if len(sentence) > MAX_SNIPPET_LEN:
            cut = snippet.rfind(". ")
            if cut > 200:
                snippet = snippet[:cut + 1]

        for concept in concepts:
            stats["concepts_touched"] += 1

            if dry_run:
                stats["snippets_written"] += 1
                continue

            try:
                # Check if node exists and has a snippet already
                existing = manifold.get_node(concept)
                if existing and isinstance(existing, dict):
                    old_snippet = existing.get("snippet", "")
                    if old_snippet and len(old_snippet) > 10:
                        # Keep existing snippet ONLY if it's quality prose.
                        # After the string table overflow, most snippets contain
                        # concatenated concept keys like "creativekeeps_creative
                        # mindysistertogether..." — 95% alpha but meaningless.
                        # Quality test: must contain SPACES (real prose has spaces
                        # between words). Concatenated keys have underscores not spaces.
                        _space_ratio = old_snippet.count(' ') / max(len(old_snippet), 1)
                        _is_quality = (
                            _space_ratio > 0.10  # Real prose: ~15-20% spaces
                            and not any(p in old_snippet for p in [
                                "collision:", "wm:", "portal:", "mv_learned",
                                "audiocortexfairy", "Times New Roman",
                                "keeps_creative", "settles_warm",  # Known corruption pattern
                            ])
                        )
                        if _is_quality:
                            stats["snippets_skipped"] += 1
                            continue
                    manifold.set_snippet(concept, snippet, tracer_id=TRACE_BOOKS)
                    stats["snippets_written"] += 1
                else:
                    # Node doesn't exist — DON'T create it.
                    # The failed first run created 437K junk nodes by creating
                    # bigrams that didn't exist. Only enrich EXISTING nodes.
                    stats["snippets_skipped"] += 1
            except Exception:
                stats["snippets_skipped"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Holographic book re-ingestion")
    parser.add_argument("--dry-run", action="store_true", help="Don't write, just report")
    parser.add_argument("--limit", type=int, default=0, help="Max sentences per book (0=all)")
    parser.add_argument("--book-limit", type=int, default=0, help="Max books to process (0=all)")
    parser.add_argument("--author", type=str, default="", help="Process only this author")
    parser.add_argument("--dir", type=str, default="", help="Override books directory")
    parser.add_argument("--skip-tech", action="store_true",
                        help="Skip tech books (O'Reilly, Packt, etc.)")
    args = parser.parse_args()

    books_dir = Path(args.dir) if args.dir else BOOKS_DIR

    print("=" * 70)
    print("HOLOGRAPHIC BOOK RE-INGESTION")
    print(f"  Books dir: {books_dir}")
    print(f"  Manifold:  {MANIFOLD_PATH}")
    print(f"  Dry run:   {args.dry_run}")
    print(f"  Limit:     {args.limit or 'all'} sentences/book")
    print(f"  Book limit: {args.book_limit or 'all'}")
    print(f"  Skip tech: {args.skip_tech}")
    if args.author:
        print(f"  Author:    {args.author}")
    print("=" * 70)

    if not MANIFOLD_PATH.exists():
        print("ERROR: Manifold not found!")
        sys.exit(1)

    # Open manifold
    manifold = ManifoldMemory(str(MANIFOLD_PATH))
    initial_nodes = manifold._node_count
    print(f"Manifold: {initial_nodes:,} nodes")

    # Find all book files (.rtf and .epub)
    book_files = sorted(
        list(books_dir.rglob("*.rtf")) + list(books_dir.rglob("*.epub"))
    )
    if args.author:
        book_files = [f for f in book_files if args.author.lower() in str(f).lower()]

    # Skip tech books if requested
    TECH_PUBLISHERS = {'oreilly', 'o.reilly', 'packt', 'mit.press', 'kogan.page',
                       'manning', 'apress', 'pragmatic', 'wrox'}
    if args.skip_tech:
        filtered = []
        for f in book_files:
            path_lower = str(f).lower()
            if any(p in path_lower for p in TECH_PUBLISHERS):
                continue
            # Also skip if path contains common tech keywords
            if any(p in path_lower for p in [
                'python', 'javascript', 'programming', 'algorithm',
                'api', 'data.science', 'machine.learning', 'web.design',
                'forecasting', 'offensive.security', 'docker', 'kubernetes',
            ]):
                continue
            filtered.append(f)
        skipped = len(book_files) - len(filtered)
        if skipped:
            print(f"Skipped {skipped} tech books")
        book_files = filtered

    if args.book_limit > 0:
        book_files = book_files[:args.book_limit]

    print(f"Found {len(book_files)} books to process\n")

    total_stats = Counter()
    start = time.time()

    for i, book_path in enumerate(book_files, 1):
        book_name = book_path.stem
        author = book_path.parent.parent.name if book_path.parent.parent != books_dir else "Unknown"
        print(f"[{i}/{len(book_files)}] {author} -- {book_name}")

        book_stats = process_book(book_path, manifold, dry_run=args.dry_run, limit=args.limit)
        for k, v in book_stats.items():
            total_stats[k] += v

        print(f"  sentences={book_stats['sentences']}, "
              f"snippets={book_stats['snippets_written']}, "
              f"skipped={book_stats['snippets_skipped']}, "
              f"new_nodes={book_stats['nodes_created']}", flush=True)

    elapsed = time.time() - start
    final_nodes = manifold._node_count

    print(f"\n{'=' * 70}")
    print(f"DONE in {elapsed:.1f}s")
    print(f"  Books processed:  {len(book_files)}")
    print(f"  Sentences:        {total_stats['sentences']:,}")
    print(f"  Concepts touched: {total_stats['concepts_touched']:,}")
    print(f"  Snippets written: {total_stats['snippets_written']:,}")
    print(f"  Snippets skipped: {total_stats['snippets_skipped']:,}")
    print(f"  New nodes:        {total_stats['nodes_created']:,}")
    print(f"  Node count:       {initial_nodes:,} -> {final_nodes:,}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
