"""
Retrain Google Drive Content into the Manifold Cortex (v2 Schema).

Re-processes ALL Google Drive documents with proper v2 fields:
descriptive snippets, node_types, typed edges, domain tags, regions.

The original training (2026-03-19) used tools/train_gdrive.py through
PostalTunnelClient which created bare nodes. This script writes
directly to the manifold with real semantic information.

Content categories:
  Human Emotion Encyclopedia:  Hundreds of Gold Standard entries (A-Z)
  Books:                       Terry Brooks, Freud, psychology, folklore, humor
  Ideas & Proposals:           Akashic Foundation architecture, VR, AI design
  Education:                   Teaching materials
  Foundation docs:             Codex, field logs, articles of incorporation
  Root docs:                   Consciousness, brain-to-brain, stories

Usage:
    REM Must use Python 3.12 for google-api-python-client
    C:\\Users\\Ace\\AppData\\Local\\Programs\\Python\\Python312\\python.exe scripts/retrain_gdrive_to_cortex.py
    C:\\Users\\Ace\\AppData\\Local\\Programs\\Python\\Python312\\python.exe scripts/retrain_gdrive_to_cortex.py --dry-run
    C:\\Users\\Ace\\AppData\\Local\\Programs\\Python\\Python312\\python.exe scripts/retrain_gdrive_to_cortex.py --max-files 100

2026-03-20, Nous + Ace -- Akashic Foundation
"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import os
import sys
import json
import time
import hashlib
import argparse
import re
import io

# Add project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from infrastructure.manifold_memory import (
    ManifoldMemory,
    NTYPE_CONCEPT, NTYPE_ENTITY, NTYPE_EPISODE,
    REGION_EGO, REGION_SEMANTIC, REGION_EPISODIC,
    REL_COACTIVATE, REL_SEMANTIC, REL_IS_A, REL_PART_OF,
)

# ═══ Google Drive API ═══
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
except ImportError:
    print("ERROR: Google API packages not found.")
    print("This script must run on Python 3.12:")
    print(r"  C:\Users\Ace\AppData\Local\Programs\Python\Python312\python.exe scripts/retrain_gdrive_to_cortex.py")
    sys.exit(1)

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
os.environ['PYTHONUNBUFFERED'] = '1'

# ═══ Config ═══
GDRIVE_CREDS_DIR = os.path.join(os.environ.get("APPDATA", ""), "Claude", "gdrive")
GDRIVE_TOKEN_PATH = os.path.join(GDRIVE_CREDS_DIR, "token.json")
GDRIVE_OAUTH_PATH = os.path.join(GDRIVE_CREDS_DIR, "gcp-oauth.keys.json")
GDRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

PROGRESS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "state", "gdrive_v2_retrain_progress.json"
)

# ═══ MIME Filters ═══
SKIP_MIMES = {
    "application/vnd.google-apps.folder",
    "video/mp4", "video/mpeg", "video/quicktime", "video/x-msvideo",
    "video/x-ms-wmv", "video/webm", "video/3gpp", "video/3gpp2",
    "video/x-flv", "video/x-matroska", "video/ogg",
    "application/vnd.google-apps.video",
    "application/vnd.google-apps.form",
    "application/vnd.google-apps.map",
    "application/vnd.google-apps.site",
    "application/vnd.google-apps.shortcut",
    "application/zip", "application/x-zip-compressed",
}

IMAGE_MIMES = {
    "image/jpeg", "image/png", "image/gif", "image/bmp", "image/webp",
    "image/tiff", "image/svg+xml", "application/vnd.google-apps.photo",
    "application/vnd.google-apps.drawing",
}

EXPORT_MIMES = {
    'application/vnd.google-apps.document': 'text/plain',
    'application/vnd.google-apps.spreadsheet': 'text/csv',
    'application/vnd.google-apps.presentation': 'text/plain',
}

# ═══ Folder → Domain/Region Mapping ═══
FOLDER_DOMAIN_MAP = {
    "human emotion encyclopedia": ("emotion_encyclopedia", NTYPE_CONCEPT, REGION_EGO),
    "education": ("education", NTYPE_CONCEPT, REGION_SEMANTIC),
    "books": ("literature", NTYPE_CONCEPT, REGION_SEMANTIC),
    "ideas, insights and proposals": ("akashic_proposals", NTYPE_CONCEPT, REGION_SEMANTIC),
    "personal ai": ("personal_ai", NTYPE_CONCEPT, REGION_SEMANTIC),
    "book upload": ("literature", NTYPE_CONCEPT, REGION_SEMANTIC),
    "books to upload": ("literature", NTYPE_CONCEPT, REGION_SEMANTIC),
    "personalized tutor sub ai": ("education", NTYPE_CONCEPT, REGION_SEMANTIC),
    "akashic foundation images": ("akashic_images", NTYPE_CONCEPT, REGION_SEMANTIC),
}

# Root-level doc classification by keyword
ROOT_DOC_KEYWORDS = {
    "emotion": ("emotion_encyclopedia", NTYPE_CONCEPT, REGION_EGO),
    "consciousness": ("consciousness", NTYPE_CONCEPT, REGION_EGO),
    "akashic": ("akashic_foundation", NTYPE_CONCEPT, REGION_SEMANTIC),
    "brain": ("neuroscience", NTYPE_CONCEPT, REGION_SEMANTIC),
    "mirror neuron": ("neuroscience", NTYPE_CONCEPT, REGION_SEMANTIC),
    "codex": ("akashic_foundation", NTYPE_CONCEPT, REGION_SEMANTIC),
    "field log": ("akashic_foundation", NTYPE_EPISODE, REGION_EPISODIC),
    "sourpatches": ("sourpatches", NTYPE_CONCEPT, REGION_EGO),
    "story": ("literature", NTYPE_CONCEPT, REGION_SEMANTIC),
    "boot": ("engineering", NTYPE_EPISODE, REGION_EPISODIC),
}


def get_gdrive_service():
    """Authenticate and return Google Drive service."""
    creds = None
    if os.path.exists(GDRIVE_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(GDRIVE_TOKEN_PATH, GDRIVE_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(GDRIVE_OAUTH_PATH):
                print(f"ERROR: OAuth credentials not found at {GDRIVE_OAUTH_PATH}")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(GDRIVE_OAUTH_PATH, GDRIVE_SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs(GDRIVE_CREDS_DIR, exist_ok=True)
        with open(GDRIVE_TOKEN_PATH, 'w') as f:
            f.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)


def list_folder(service, folder_id, max_results=1000):
    """List all items in a folder (handles pagination)."""
    all_items = []
    page_token = None
    while True:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            pageSize=min(max_results - len(all_items), 100),
            fields="nextPageToken, files(id, name, mimeType, size)",
            orderBy="folder,name",
            pageToken=page_token
        ).execute()
        items = results.get('files', [])
        all_items.extend(items)
        page_token = results.get('nextPageToken')
        if not page_token or len(all_items) >= max_results:
            break
    return all_items


def read_gdrive_file(service, file_id, name, mime_type):
    """Read a file from Google Drive, return text content or None."""
    try:
        if mime_type in EXPORT_MIMES:
            export_mime = EXPORT_MIMES[mime_type]
            request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        else:
            request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        raw = buffer.getvalue()
        try:
            return raw.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return raw.decode('latin-1')
            except:
                return None
    except Exception as e:
        print(f"    [READ ERR] {name}: {e}")
        return None


def classify_doc(name, folder_path):
    """Classify a document by folder and name into (domain, ntype, region)."""
    # Check folder path first
    folder_lower = folder_path.lower()
    for keyword, mapping in FOLDER_DOMAIN_MAP.items():
        if keyword in folder_lower:
            return mapping

    # Check document name for root-level docs
    name_lower = name.lower()
    for keyword, mapping in ROOT_DOC_KEYWORDS.items():
        if keyword in name_lower:
            return mapping

    # Gold Standard emotion encyclopedia entries
    if "gold standard" in name_lower or "emotional context encyclopedia" in name_lower:
        return ("emotion_encyclopedia", NTYPE_CONCEPT, REGION_EGO)

    return ("general", NTYPE_CONCEPT, REGION_SEMANTIC)


def make_key(name, folder_path):
    """Create a cortex key from document name and folder."""
    # Clean the name
    key = name.lower()
    # Remove common suffixes
    for suffix in ["(draft)", "(gold standard", "- the akashic foundation",
                   "akashic foundation for human and ai enlightenment",
                   "human emotional context encyclopedia)", "human emotion encyclopedia"]:
        key = key.replace(suffix, "")
    key = key.strip(" ()-")
    key = ''.join(c if c.isalnum() or c == ' ' else '' for c in key)
    key = '_'.join(key.split()[:10])  # Max 10 words
    if len(key) < 3:
        key = hashlib.md5(name.encode()).hexdigest()[:12]

    # Prefix by domain
    domain, _, _ = classify_doc(name, folder_path)
    prefix_map = {
        "emotion_encyclopedia": "emo",
        "literature": "book",
        "akashic_proposals": "proposal",
        "akashic_foundation": "akashic",
        "education": "edu",
        "consciousness": "conscious",
        "neuroscience": "neuro",
        "sourpatches": "sp",
        "engineering": "eng",
        "personal_ai": "pai",
    }
    prefix = prefix_map.get(domain, "gdrive")
    return f"{prefix}:{key}"


def make_snippet(name, text, max_len=500):
    """Build a snippet from document name and first meaningful content."""
    # Get first substantial paragraph
    lines = text.split('\n')
    content_lines = []
    for line in lines:
        line = line.strip()
        if line and len(line) > 15 and not line.startswith('#'):
            content_lines.append(line)
            if len(' '.join(content_lines)) > max_len - len(name) - 10:
                break

    content = ' '.join(content_lines)
    if content:
        snippet = f"{name} — {content}"
    else:
        snippet = name
    return snippet[:max_len]


def extract_emotion_from_gold_standard(text):
    """Extract emotion name and core description from Gold Standard entries."""
    # These follow a consistent format
    lines = text.split('\n')
    emotion_name = ""
    core_desc = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if not emotion_name and len(line) > 5:
            emotion_name = line
        elif emotion_name and len(line) > 30 and not core_desc:
            core_desc = line
            break
    return emotion_name, core_desc


def extract_tags(text, max_tags=8):
    """Extract topic tags from document text."""
    tags = []
    STOP = {'this', 'that', 'with', 'from', 'have', 'been', 'were', 'they',
            'their', 'what', 'when', 'where', 'which', 'about', 'would',
            'could', 'should', 'into', 'then', 'than', 'more', 'some',
            'other', 'each', 'only', 'also', 'very', 'just', 'like',
            'part', 'chapter', 'draft', 'section', 'standard', 'gold'}

    # Find headings
    headings = re.findall(r'#{1,3}\s+(.+?)(?:\n|$)', text[:3000])
    for h in headings[:3]:
        tag = h.strip().lower().replace(' ', '_')[:30]
        if len(tag) > 3 and tag not in tags:
            tags.append(tag)

    # Significant repeated words
    words = re.findall(r'\b[a-zA-Z]{5,}\b', text[:5000])
    from collections import Counter
    freq = Counter(w.lower() for w in words if w.lower() not in STOP)
    for word, count in freq.most_common(max_tags - len(tags)):
        if count >= 3 and word not in tags:
            tags.append(word)

    return tags[:max_tags]


def load_progress():
    path = os.path.normpath(PROGRESS_FILE)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "trained_ids": [],
        "skipped_ids": [],
        "image_ids": [],
        "error_ids": [],
        "content_hashes": [],
        "total_nodes": 0,
        "total_edges": 0,
    }


def save_progress(progress):
    path = os.path.normpath(PROGRESS_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)


def process_file(graph, service, file_info, folder_path, stats, progress,
                 dry_run=False):
    """Download a file and create cortex nodes with v2 schema."""
    fid = file_info["id"]
    fname = file_info["name"]
    mime = file_info.get("mimeType", "")
    size = int(file_info.get("size", 0))

    # Already processed?
    all_seen = set(progress["trained_ids"] + progress["skipped_ids"] +
                   progress["image_ids"] + progress["error_ids"])
    if fid in all_seen:
        return

    # Skip non-trainable
    if mime in SKIP_MIMES:
        progress["skipped_ids"].append(fid)
        return

    # Track images separately
    if mime in IMAGE_MIMES:
        progress["image_ids"].append(fid)
        return

    # Size guard
    if size > 10 * 1024 * 1024:
        progress["skipped_ids"].append(fid)
        return

    if dry_run:
        stats["nodes"] += 1
        stats["edges"] += 3
        progress["trained_ids"].append(fid)
        return

    # Download content
    text = read_gdrive_file(service, fid, fname, mime)
    if not text or len(text.strip()) < 50:
        progress["skipped_ids"].append(fid)
        return

    text = text.strip()

    # Dedup
    h = hashlib.sha256(text.encode('utf-8', errors='replace')).hexdigest()[:16]
    if h in progress["content_hashes"]:
        progress["skipped_ids"].append(fid)
        return
    progress["content_hashes"].append(h)

    # Classify
    domain, ntype, region = classify_doc(fname, folder_path)

    # Build key and snippet
    key = make_key(fname, folder_path)
    snippet = make_snippet(fname, text)

    # For emotion encyclopedia Gold Standard entries, extract richer snippet
    if domain == "emotion_encyclopedia":
        emo_name, emo_desc = extract_emotion_from_gold_standard(text)
        if emo_name and emo_desc:
            snippet = f"{emo_name} — {emo_desc}"[:500]

    # Create main node
    slot = graph.upsert_node(
        key=key,
        activation=1.5,
        count=1,
        snippet=snippet,
        node_type=ntype,
        region=region,
    )
    if slot < 0:
        stats["failed"] += 1
        progress["error_ids"].append(fid)
        return

    stats["nodes"] += 1
    stats["snippets_bytes"] += len(snippet.encode('utf-8'))

    # Link to domain node
    domain_key = f"gdrive:domain:{domain}"
    graph.upsert_node(
        key=domain_key,
        activation=3.0,
        count=200,
        snippet=f"Google Drive content domain: {domain}",
        node_type=NTYPE_CONCEPT,
        region=REGION_SEMANTIC,
    )
    if graph.link(key, domain_key, weight=0.5, rel_type=REL_IS_A):
        stats["edges"] += 1

    # Link to folder path
    folder_key = f"gdrive:folder:{folder_path.lower().replace(' ', '_').replace('/', '_')[:60]}"
    graph.upsert_node(
        key=folder_key,
        activation=2.0,
        count=50,
        snippet=f"Google Drive folder: {folder_path}",
        node_type=NTYPE_CONCEPT,
        region=REGION_SEMANTIC,
    )
    if graph.link(key, folder_key, weight=0.4, rel_type=REL_PART_OF):
        stats["edges"] += 1

    # Extract and link tags
    tags = extract_tags(text)
    for tag in tags[:6]:
        tag_key = f"tag:{tag}"
        if graph.link(key, tag_key, weight=0.3, rel_type=REL_SEMANTIC):
            stats["edges"] += 1

    # For long documents, create chunk nodes linked to main
    if len(text) > 6000:
        chunks = []
        start = 0
        while start < len(text):
            end = start + 6000
            chunks.append(text[start:end])
            start = end - 200
        for i, chunk in enumerate(chunks[1:], 1):  # Skip first (already in main)
            chunk_key = f"{key}:chunk:{i}"
            chunk_snippet = chunk[:500]
            cslot = graph.upsert_node(
                key=chunk_key,
                activation=0.8,
                count=1,
                snippet=chunk_snippet,
                node_type=ntype,
                region=region,
            )
            if cslot >= 0:
                stats["nodes"] += 1
                stats["snippets_bytes"] += len(chunk_snippet.encode('utf-8'))
                if graph.link(chunk_key, key, weight=0.7, rel_type=REL_PART_OF):
                    stats["edges"] += 1

    progress["trained_ids"].append(fid)


def crawl_folder(service, graph, folder_id, folder_path, stats, progress,
                 dry_run=False, max_files=0, depth=0):
    """Recursively crawl a Drive folder and ingest into cortex."""
    indent = "  " * depth
    print(f"{indent}[FOLDER] {folder_path}")

    items = list_folder(service, folder_id)
    folders = [f for f in items if f['mimeType'] == 'application/vnd.google-apps.folder']
    files = [f for f in items if f['mimeType'] != 'application/vnd.google-apps.folder']
    print(f"{indent}  {len(folders)} subfolders, {len(files)} files")

    file_count = len(files)
    for idx, f in enumerate(files):
        if max_files and stats["nodes"] >= max_files:
            return
        process_file(graph, service, f, folder_path, stats, progress, dry_run)
        if (idx + 1) % 25 == 0 or idx == file_count - 1:
            print(f"{indent}  [{idx+1}/{file_count}] {stats['nodes']} nodes, "
                  f"{stats['edges']} edges", flush=True)

    # Save progress after each folder
    save_progress(progress)
    if graph and not dry_run and stats["nodes"] % 50 == 0:
        graph._write_header()

    # Recurse into subfolders
    for sub in folders:
        if max_files and stats["nodes"] >= max_files:
            return
        sub_path = f"{folder_path}/{sub['name']}"
        crawl_folder(service, graph, sub["id"], sub_path, stats, progress,
                     dry_run, max_files, depth + 1)


def main():
    parser = argparse.ArgumentParser(
        description="Retrain Google Drive content into cortex manifold (v2 schema)"
    )
    parser.add_argument("--manifold", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-files", type=int, default=0,
                        help="Max files to process (0=all)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from progress file (skip already-trained)")
    args = parser.parse_args()

    # Find manifold
    manifold_path = args.manifold
    if not manifold_path:
        for c in ["state/akashic/cortex.manifold",
                   "../state/akashic/cortex.manifold"]:
            if os.path.exists(c):
                manifold_path = c
                break
    if not manifold_path and not args.dry_run:
        print("ERROR: Could not find cortex.manifold")
        sys.exit(1)

    # Load progress
    if args.resume:
        progress = load_progress()
        print(f"Resuming: {len(progress['trained_ids'])} already trained")
    else:
        progress = load_progress()  # Start fresh but keep structure

    stats = {
        "nodes": 0, "edges": 0, "failed": 0,
        "snippets_bytes": 0,
    }

    # Connect to Google Drive
    print("Connecting to Google Drive...")
    service = get_gdrive_service()
    print("  Connected!")

    if args.dry_run:
        print("\n--- DRY RUN ---")
        graph = None
    else:
        file_size = os.path.getsize(manifold_path)
        print(f"\nOpening manifold: {manifold_path} ({file_size / (1024*1024):.1f} MB)")
        graph = ManifoldMemory(manifold_path)
        before = graph.status()
        print(f"  Before: {before['nodes']:,} nodes, {before['edges']:,} edges")

    print(f"\nCrawling Google Drive and ingesting into cortex...")
    t0 = time.time()

    # Crawl root
    crawl_folder(service, graph, "root", "root", stats, progress,
                 dry_run=args.dry_run, max_files=args.max_files)

    elapsed = time.time() - t0

    if graph and not args.dry_run:
        graph._write_header()
        after = graph.status()
        print(f"\n  After: {after['nodes']:,} nodes, {after['edges']:,} edges")
        graph.close()

    save_progress(progress)

    print(f"\nRetraining complete in {elapsed:.1f}s")
    print(f"\n--- Summary ---")
    print(f"  Nodes created:    {stats['nodes']}")
    print(f"  Edges created:    {stats['edges']}")
    print(f"  Snippet bytes:    {stats['snippets_bytes']:,}")
    print(f"  Failed nodes:     {stats['failed']}")
    print(f"  Files trained:    {len(progress['trained_ids'])}")
    print(f"  Files skipped:    {len(progress['skipped_ids'])}")
    print(f"  Images found:     {len(progress['image_ids'])}")
    print(f"  Errors:           {len(progress['error_ids'])}")

    # Verification
    if not args.dry_run and manifold_path:
        print(f"\n--- Verification ---")
        graph = ManifoldMemory(manifold_path, readonly=True)
        test_keys = [
            "gdrive:domain:emotion_encyclopedia",
            "gdrive:domain:literature",
            "gdrive:domain:akashic_proposals",
            "gdrive:domain:akashic_foundation",
        ]
        for key in test_keys:
            node = graph.get_node(key)
            if node:
                snippet = node.get("snippet", "")[:60]
                print(f"  {key}: \"{snippet}...\"")
            else:
                print(f"  {key}: NOT FOUND")
        graph.close()

    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
