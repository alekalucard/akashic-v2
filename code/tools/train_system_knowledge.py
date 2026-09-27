"""
Train System Knowledge into Association Cortex
===============================================
Processes all 106K+ knowledge files from P10_Memory/system/ domains
and sends them to the cortex via PostalTunnelClient in controlled batches.

Domains: programming, gamedev, engineering, chemistry, media, philosophy,
         graphics, literature, akashic_foundation

Usage:
    python tools/train_system_knowledge.py [domain] [--batch-size 50] [--delay 2.0] [--resume]

    # Train one domain:
    python tools/train_system_knowledge.py philosophy

    # Train all domains sequentially:
    python tools/train_system_knowledge.py all

    # Resume from where we left off:
    python tools/train_system_knowledge.py philosophy --resume
"""

import sys
import os
import json
import time
import argparse
from pathlib import Path

# Add MCP path for PostalTunnelClient
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fairies', 'P40_Sensory', 'mcp'))
from postal_tunnel import PostalTunnelClient

BASE_DIR = Path(__file__).parent.parent / 'P10_Memory' / 'Akashic_triple_helix_memory_storage' / 'system'
STATE_FILE = Path(__file__).parent.parent / 'state' / 'knowledge_training_progress.json'

# Domain processing order (smallest first for quick wins, largest last)
DOMAIN_ORDER = [
    'akashic_foundation',  # 140
    'literature',          # 214
    'graphics',            # 2,672
    'philosophy',          # 5,301
    'media',               # 9,388
    'chemistry',           # 11,147
    'engineering',         # 14,384
    'gamedev',             # 22,852
    'programming',         # 40,823
]


def load_progress():
    """Load training progress state."""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"completed_domains": [], "domain_progress": {}, "total_trained": 0}


def save_progress(progress):
    """Save training progress state."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def extract_text_from_file(filepath):
    """Extract trainable text from a knowledge JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    kind = data.get('kind', '')
    inner = data.get('data', {})
    meta = data.get('meta', {})

    if isinstance(inner, dict):
        # Scraped knowledge: combine query + response
        if 'query' in inner and 'response' in inner:
            text = f"{inner['query']}\n{inner['response']}"
            title = meta.get('title', meta.get('parent_title', ''))
            domain = inner.get('domain', meta.get('domain', ''))
            return {
                'text': text[:3000],  # Cap at 3K chars to avoid overloading
                'source': f"system_knowledge/{domain}",
                'source_fairy': 'SystemKnowledgeTrainer',
                'context_tags': [domain, meta.get('type', 'knowledge')],
                'title': title,
                'max_concepts': 8,
            }

        # Literature: title + content
        elif 'content' in inner:
            text = inner.get('content', '')
            title = inner.get('title', '')
            if title:
                text = f"{title}\n{text}"
            # For long books, take first 3K chars (will train chapters separately)
            return {
                'text': text[:3000],
                'source': 'system_knowledge/literature',
                'source_fairy': 'SystemKnowledgeTrainer',
                'context_tags': ['literature', meta.get('type', 'book')],
                'title': title,
                'max_concepts': 10,
            }

        # Akashic foundation
        elif 'title' in inner or 'purpose' in inner:
            text = f"{inner.get('title', '')} {inner.get('purpose', '')} {inner.get('description', '')}"
            return {
                'text': text[:2000],
                'source': 'system_knowledge/akashic_foundation',
                'source_fairy': 'SystemKnowledgeTrainer',
                'context_tags': ['akashic', 'foundation'],
                'max_concepts': 8,
            }

    # Top-level title/purpose (akashic_foundation cluster files)
    if 'title' in data:
        parts = [data.get('title', ''), data.get('purpose', ''), data.get('domain', '')]
        text = ' '.join(p for p in parts if p)
        if len(text) > 20:
            return {
                'text': text[:2000],
                'source': 'system_knowledge/akashic_foundation',
                'source_fairy': 'SystemKnowledgeTrainer',
                'context_tags': ['akashic', 'foundation'],
                'max_concepts': 6,
            }

    return None


def collect_domain_files(domain):
    """Collect all JSON files for a domain."""
    domain_path = BASE_DIR / domain
    files = []
    for root, dirs, filenames in os.walk(domain_path):
        for f in filenames:
            if f.endswith('.json'):
                files.append(os.path.join(root, f))
    return sorted(files)


def train_domain(domain, batch_size=50, delay=2.0, resume=False):
    """Train all files from a domain into the cortex."""
    progress = load_progress()

    if domain in progress.get('completed_domains', []) and resume:
        print(f"[{domain}] Already completed. Skipping.")
        return

    files = collect_domain_files(domain)
    total = len(files)

    # Resume from last position
    start_idx = 0
    if resume and domain in progress.get('domain_progress', {}):
        start_idx = progress['domain_progress'][domain].get('last_index', 0)
        print(f"[{domain}] Resuming from index {start_idx}/{total}")

    print(f"[{domain}] Processing {total} files (batch_size={batch_size}, delay={delay}s)")

    # Connect to postal tunnel
    client = PostalTunnelClient()
    if not client.connect():
        print(f"[{domain}] ERROR: Could not connect to postal tunnel!")
        return

    # Verify connection
    if not client.ping():
        print(f"[{domain}] ERROR: Ping failed!")
        return

    trained = 0
    skipped = 0
    errors = 0
    batch = []

    for idx in range(start_idx, total):
        filepath = files[idx]
        item = extract_text_from_file(filepath)

        if item is None:
            skipped += 1
            continue

        # Skip very short texts
        if len(item.get('text', '')) < 30:
            skipped += 1
            continue

        batch.append(item)

        # Send batch when full
        if len(batch) >= batch_size:
            try:
                payload = {
                    'items': batch,
                    'source': f'system_knowledge/{domain}',
                    'source_fairy': 'SystemKnowledgeTrainer',
                    'trace_id': f'skt_{domain}_{int(time.time())}',
                }
                client.route('cortex.train_batch', payload)
                trained += len(batch)

                # Progress update
                pct = (idx + 1) / total * 100
                print(f"  [{domain}] {idx+1}/{total} ({pct:.1f}%) — trained: {trained}, skipped: {skipped}")

                # Save progress
                if domain not in progress.get('domain_progress', {}):
                    progress.setdefault('domain_progress', {})[domain] = {}
                progress['domain_progress'][domain]['last_index'] = idx + 1
                progress['domain_progress'][domain]['trained'] = trained
                progress['domain_progress'][domain]['skipped'] = skipped
                progress['total_trained'] = progress.get('total_trained', 0) + len(batch)
                save_progress(progress)

            except Exception as e:
                errors += 1
                print(f"  [{domain}] ERROR at batch ending idx {idx}: {e}")
                # Try to reconnect
                try:
                    client.close()
                    time.sleep(2)
                    client = PostalTunnelClient()
                    client.connect()
                except:
                    pass

            batch = []
            time.sleep(delay)  # Pace ourselves

    # Send remaining batch
    if batch:
        try:
            payload = {
                'items': batch,
                'source': f'system_knowledge/{domain}',
                'source_fairy': 'SystemKnowledgeTrainer',
                'trace_id': f'skt_{domain}_{int(time.time())}_final',
            }
            client.route('cortex.train_batch', payload)
            trained += len(batch)
        except Exception as e:
            errors += 1
            print(f"  [{domain}] ERROR on final batch: {e}")

    # Mark domain complete
    progress.setdefault('completed_domains', [])
    if domain not in progress['completed_domains']:
        progress['completed_domains'].append(domain)
    progress.setdefault('domain_progress', {})[domain] = {
        'last_index': total,
        'trained': trained,
        'skipped': skipped,
        'errors': errors,
        'completed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    progress['total_trained'] = progress.get('total_trained', 0)
    save_progress(progress)

    client.close()

    print(f"\n[{domain}] COMPLETE — trained: {trained}, skipped: {skipped}, errors: {errors}")
    return trained


def main():
    parser = argparse.ArgumentParser(description='Train system knowledge into cortex')
    parser.add_argument('domain', help='Domain to train (or "all" for all domains)')
    parser.add_argument('--batch-size', type=int, default=50, help='Items per batch (default: 50)')
    parser.add_argument('--delay', type=float, default=2.0, help='Seconds between batches (default: 2.0)')
    parser.add_argument('--resume', action='store_true', help='Resume from last progress')
    parser.add_argument('--status', action='store_true', help='Show training progress')
    args = parser.parse_args()

    if args.status or args.domain == 'status':
        progress = load_progress()
        print("=== Knowledge Training Progress ===")
        print(f"Total trained: {progress.get('total_trained', 0)}")
        print(f"Completed domains: {progress.get('completed_domains', [])}")
        for d, info in progress.get('domain_progress', {}).items():
            print(f"  {d}: {info}")
        return

    if args.domain == 'all':
        for domain in DOMAIN_ORDER:
            train_domain(domain, args.batch_size, args.delay, args.resume)
            print()
    else:
        if args.domain not in DOMAIN_ORDER:
            print(f"Unknown domain: {args.domain}")
            print(f"Available: {', '.join(DOMAIN_ORDER)}")
            return
        train_domain(args.domain, args.batch_size, args.delay, args.resume)


if __name__ == '__main__':
    main()
