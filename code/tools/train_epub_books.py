"""
Train EPUB Books into Association Cortex
=========================================
Extracts text from EPUB files and sends chapter content to the cortex
via PostalTunnelClient. Uses pure stdlib (zipfile + HTMLParser).

Usage:
    python tools/train_epub_books.py "D:\Books"
    python tools/train_epub_books.py "D:\Books" --batch-size 25 --delay 2.0
    python tools/train_epub_books.py "D:\Books" --resume
"""

import sys
import os
import json
import time
import zipfile
import argparse
from pathlib import Path
from html.parser import HTMLParser

# Add MCP path for PostalTunnelClient
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fairies', 'P40_Sensory', 'mcp'))
from postal_tunnel import PostalTunnelClient

STATE_FILE = Path(__file__).parent.parent / 'state' / 'epub_training_progress.json'


class TextExtractor(HTMLParser):
    """Extract plain text from HTML/XHTML content."""
    def __init__(self):
        super().__init__()
        self.text = []
        self._skip = False
        self._skip_tags = {'script', 'style', 'head'}

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip = True

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            d = data.strip()
            if d:
                self.text.append(d)

    def get_text(self):
        return ' '.join(self.text)


def extract_epub_metadata(zf):
    """Try to extract title/author from epub metadata."""
    title = ""
    author = ""
    # Look for content.opf or similar
    for name in zf.namelist():
        if name.endswith('.opf'):
            try:
                content = zf.read(name).decode('utf-8', errors='replace')
                # Quick regex-free parsing
                if '<dc:title' in content:
                    start = content.index('<dc:title')
                    start = content.index('>', start) + 1
                    end = content.index('</dc:title>', start)
                    title = content[start:end].strip()
                if '<dc:creator' in content:
                    start = content.index('<dc:creator')
                    start = content.index('>', start) + 1
                    end = content.index('</dc:creator>', start)
                    author = content[start:end].strip()
            except (KeyError, ValueError):
                pass
            break
    return title, author


def extract_chapters(epub_path):
    """Extract text chapters from an EPUB file."""
    chapters = []
    try:
        with zipfile.ZipFile(epub_path) as zf:
            title, author = extract_epub_metadata(zf)

            # Get all HTML content files
            html_files = sorted([
                fn for fn in zf.namelist()
                if fn.endswith(('.xhtml', '.html', '.htm'))
            ])

            for i, html_file in enumerate(html_files):
                try:
                    content = zf.read(html_file).decode('utf-8', errors='replace')
                    parser = TextExtractor()
                    parser.feed(content)
                    text = parser.get_text()

                    # Skip very short chapters (TOC, copyright, etc.)
                    if len(text) < 100:
                        continue

                    chapters.append({
                        'text': text[:3000],  # Cap at 3K chars per chapter
                        'title': title,
                        'author': author,
                        'chapter_idx': i,
                        'chapter_file': html_file,
                        'full_length': len(text),
                    })
                except Exception:
                    continue

    except (zipfile.BadZipFile, OSError) as e:
        print(f"  ERROR reading {epub_path}: {e}")

    return chapters


def load_progress():
    """Load training progress."""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"completed_books": [], "total_chapters_trained": 0, "total_books": 0}


def save_progress(progress):
    """Save training progress."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def train_books(books_dir, batch_size=25, delay=2.0, resume=False):
    """Train all EPUB books from a directory into the cortex."""
    progress = load_progress()

    # Collect all EPUBs
    epub_files = []
    for root, dirs, files in os.walk(books_dir):
        for f in files:
            if f.lower().endswith('.epub'):
                epub_files.append(os.path.join(root, f))
    epub_files.sort()

    total_books = len(epub_files)
    print(f"Found {total_books} EPUB files in {books_dir}")

    # Connect to postal tunnel
    client = PostalTunnelClient()
    if not client.connect():
        print("ERROR: Could not connect to postal tunnel!")
        return
    if not client.ping():
        print("ERROR: Ping failed!")
        return
    print("Connected to postal tunnel")

    books_trained = 0
    chapters_trained = 0
    books_skipped = 0
    batch = []

    for book_idx, epub_path in enumerate(epub_files):
        book_name = os.path.basename(epub_path)

        # Skip already completed books
        if resume and epub_path in progress.get('completed_books', []):
            books_skipped += 1
            continue

        # Extract chapters
        chapters = extract_chapters(epub_path)
        if not chapters:
            print(f"  [{book_idx+1}/{total_books}] {book_name} — no extractable content")
            progress.setdefault('completed_books', []).append(epub_path)
            save_progress(progress)
            continue

        title = chapters[0].get('title', book_name)
        author = chapters[0].get('author', 'Unknown')
        print(f"  [{book_idx+1}/{total_books}] {title} by {author} — {len(chapters)} chapters")

        # Build training items from chapters
        for ch in chapters:
            # Prefix with book context
            ch_text = ch['text']
            if ch['title']:
                ch_text = f"{ch['title']} by {ch['author']}\n{ch_text}"

            item = {
                'text': ch_text,
                'source': f'epub/{ch.get("author", "unknown")}',
                'source_fairy': 'EpubTrainer',
                'context_tags': ['literature', 'book', 'epub'],
                'max_concepts': 10,
            }
            if ch.get('title'):
                item['context_tags'].append(ch['title'].lower().replace(' ', '_')[:30])

            batch.append(item)

            # Send batch when full
            if len(batch) >= batch_size:
                try:
                    payload = {
                        'items': batch,
                        'source': 'epub_books',
                        'source_fairy': 'EpubTrainer',
                        'trace_id': f'epub_{int(time.time())}',
                    }
                    client.route('cortex.train_batch', payload)
                    chapters_trained += len(batch)
                except Exception as e:
                    print(f"    ERROR sending batch: {e}")
                    try:
                        client.close()
                        time.sleep(2)
                        client = PostalTunnelClient()
                        client.connect()
                    except:
                        pass
                batch = []
                time.sleep(delay)

        # Mark book complete
        books_trained += 1
        progress.setdefault('completed_books', []).append(epub_path)
        progress['total_chapters_trained'] = progress.get('total_chapters_trained', 0) + len(chapters)
        progress['total_books'] = books_trained + books_skipped
        save_progress(progress)

    # Send remaining batch
    if batch:
        try:
            payload = {
                'items': batch,
                'source': 'epub_books',
                'source_fairy': 'EpubTrainer',
                'trace_id': f'epub_{int(time.time())}_final',
            }
            client.route('cortex.train_batch', payload)
            chapters_trained += len(batch)
        except Exception as e:
            print(f"  ERROR on final batch: {e}")

    client.close()

    print(f"\nCOMPLETE — {books_trained} books, {chapters_trained} chapters trained")
    if books_skipped:
        print(f"  ({books_skipped} books skipped — already trained)")


def main():
    parser = argparse.ArgumentParser(description='Train EPUB books into cortex')
    parser.add_argument('books_dir', help='Directory containing EPUB files')
    parser.add_argument('--batch-size', type=int, default=25, help='Items per batch (default: 25)')
    parser.add_argument('--delay', type=float, default=2.0, help='Seconds between batches (default: 2.0)')
    parser.add_argument('--resume', action='store_true', help='Resume from last progress')
    args = parser.parse_args()

    if not os.path.isdir(args.books_dir):
        print(f"ERROR: {args.books_dir} is not a directory")
        return

    train_books(args.books_dir, args.batch_size, args.delay, args.resume)


if __name__ == '__main__':
    main()
