"""
Google Drive -> Association Cortex Training Script
===================================================
Recursively crawls Ace's entire Google Drive, reads all text content,
skips video files, deduplicates, and trains into the Association Cortex.

MUST run on Python 3.12 (has google-api-python-client):
  C:\\Users\\Ace\\AppData\\Local\\Programs\\Python\\Python312\\python.exe tools/train_gdrive.py

Usage:
    python tools/train_gdrive.py [--resume] [--dry-run] [--folder FOLDER_ID]
"""

import sys, os, json, time, argparse, hashlib, io

# Fix Windows console encoding + force flush
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
os.environ['PYTHONUNBUFFERED'] = '1'

# === Path setup ===
AKASHIC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(AKASHIC_ROOT, "fairies", "P40_Sensory", "mcp"))

from postal_tunnel import PostalTunnelClient

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
    print(r"  C:\Users\Ace\AppData\Local\Programs\Python\Python312\python.exe tools/train_gdrive.py")
    sys.exit(1)

# ═══ Config ═══
PROGRESS_FILE = os.path.join(AKASHIC_ROOT, "state", "gdrive_training_progress.json")
GDRIVE_CREDS_DIR = os.path.join(os.environ.get("APPDATA", ""), "Claude", "gdrive")
GDRIVE_TOKEN_PATH = os.path.join(GDRIVE_CREDS_DIR, "token.json")
GDRIVE_OAUTH_PATH = os.path.join(GDRIVE_CREDS_DIR, "gcp-oauth.keys.json")
GDRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

BATCH_SIZE = 10
BATCH_DELAY = 2.0
MAX_TEXT_PER_CHUNK = 6000  # chars per training chunk
CHUNK_OVERLAP = 200

# ═══ MIME Filters ═══
SKIP_MIMES = {
    "application/vnd.google-apps.folder",
    # Video - Ace said omit
    "video/mp4", "video/mpeg", "video/quicktime", "video/x-msvideo",
    "video/x-ms-wmv", "video/webm", "video/3gpp", "video/3gpp2",
    "video/x-flv", "video/x-matroska", "video/ogg",
    "application/vnd.google-apps.video",
    # Non-trainable
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

# Google Workspace export types
EXPORT_MIMES = {
    'application/vnd.google-apps.document': 'text/plain',
    'application/vnd.google-apps.spreadsheet': 'text/csv',
    'application/vnd.google-apps.presentation': 'text/plain',
}


# ═══════════════════════════════════════════════════════════════════════════════
# GOOGLE DRIVE AUTH
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# PROGRESS TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "trained_ids": [],
        "skipped_ids": [],
        "image_ids": [],
        "error_ids": [],
        "total_trained": 0,
        "total_chunks": 0,
        "folders_crawled": [],
        "content_hashes": [],  # dedup across Drive
    }


def save_progress(progress):
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def chunk_text(text, max_len=MAX_TEXT_PER_CHUNK, overlap=CHUNK_OVERLAP):
    """Split long text into overlapping chunks."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_len
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    return chunks


def content_hash(text):
    """Hash content for deduplication."""
    return hashlib.sha256(text.encode('utf-8', errors='replace')).hexdigest()[:16]


def is_video(mime):
    return mime.startswith("video/") or mime == "application/vnd.google-apps.video"


def read_gdrive_file(service, file_id, name, mime_type):
    """Read a file from Google Drive, return text content or None."""
    try:
        if mime_type in EXPORT_MIMES:
            # Google Workspace file - export as text
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

        # Try UTF-8 decode
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


def list_folder(service, folder_id, max_results=500):
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


def send_batch(postal, batch, indent=""):
    """Send training batch to cortex."""
    items = []
    for item in batch:
        items.append({
            "query": item["source"],
            "response": item["text"],
            "domain": item.get("domain", "akashic_foundation"),
        })

    try:
        result = postal.route("cortex.train_batch", {"items": items})
        print(f"{indent}  >> Trained batch of {len(items)} items")
        time.sleep(BATCH_DELAY)
        return True
    except Exception as e:
        print(f"{indent}  >> BATCH ERROR: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CRAWLER
# ═══════════════════════════════════════════════════════════════════════════════

def crawl_folder(service, postal, folder_id, folder_path, progress, dry_run=False, depth=0):
    """Recursively crawl a Drive folder, read all text, train into cortex."""
    indent = "  " * depth
    print(f"{indent}[FOLDER] {folder_path}")

    if folder_id in progress["folders_crawled"]:
        print(f"{indent}  (already crawled, skipping)")
        return

    items = list_folder(service, folder_id)
    folders = [f for f in items if f['mimeType'] == 'application/vnd.google-apps.folder']
    files = [f for f in items if f['mimeType'] != 'application/vnd.google-apps.folder']
    print(f"{indent}  {len(folders)} subfolders, {len(files)} files")

    batch = []

    for f in files:
        fid = f["id"]
        fname = f["name"]
        mime = f.get("mimeType", "")
        size = int(f.get("size", 0))

        # Already processed?
        all_seen = set(progress["trained_ids"] + progress["skipped_ids"] +
                       progress["image_ids"] + progress["error_ids"])
        if fid in all_seen:
            continue

        # Skip videos and non-trainable
        if is_video(mime) or mime in SKIP_MIMES:
            progress["skipped_ids"].append(fid)
            print(f"{indent}  [SKIP] {fname} ({mime})")
            continue

        # Track images (metadata only for now - future Florence pipeline)
        if mime in IMAGE_MIMES:
            progress["image_ids"].append(fid)
            print(f"{indent}  [IMAGE] {fname}")
            continue

        # Size guard - skip files > 10MB
        if size > 10 * 1024 * 1024:
            progress["skipped_ids"].append(fid)
            print(f"{indent}  [TOO BIG] {fname} ({size/1024/1024:.1f}MB)")
            continue

        if dry_run:
            print(f"{indent}  [DRY] {fname} ({mime}, {size} bytes)")
            continue

        # Read the file
        text = read_gdrive_file(service, fid, fname, mime)
        if not text or len(text.strip()) < 50:
            progress["skipped_ids"].append(fid)
            if text:
                print(f"{indent}  [SHORT] {fname} ({len(text.strip())} chars)")
            continue

        text = text.strip()

        # Dedup by content hash
        h = content_hash(text)
        if h in progress["content_hashes"]:
            progress["skipped_ids"].append(fid)
            print(f"{indent}  [DUP] {fname}")
            continue
        progress["content_hashes"].append(h)

        # Chunk and queue
        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            batch.append({
                "text": chunk,
                "source": f"gdrive:{folder_path}/{fname}" + (f" (part {i+1}/{len(chunks)})" if len(chunks) > 1 else ""),
                "domain": "akashic_foundation",
            })
            progress["total_chunks"] += 1

        progress["trained_ids"].append(fid)
        progress["total_trained"] += 1
        print(f"{indent}  [OK] {fname} -- {len(text)} chars, {len(chunks)} chunk(s)")

        # Flush batch
        if len(batch) >= BATCH_SIZE:
            send_batch(postal, batch, indent)
            batch = []
            save_progress(progress)

    # Flush remaining
    if batch:
        send_batch(postal, batch, indent)
        save_progress(progress)

    # Mark folder done
    if not dry_run:
        progress["folders_crawled"].append(folder_id)
        save_progress(progress)

    # Recurse subfolders
    for sf in folders:
        crawl_folder(service, postal, sf["id"],
                     f"{folder_path}/{sf['name']}", progress, dry_run, depth + 1)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Train Google Drive into Association Cortex")
    parser.add_argument("--resume", action="store_true", help="Resume from progress file")
    parser.add_argument("--dry-run", action="store_true", help="List files without training")
    parser.add_argument("--folder", type=str, default="root", help="Start folder ID")
    args = parser.parse_args()

    progress = load_progress()

    print("=" * 60)
    print("Google Drive -> Association Cortex Trainer")
    print("=" * 60)
    if args.dry_run:
        print("** DRY RUN MODE **")
    if args.resume or progress["total_trained"] > 0:
        print(f"Resuming: {progress['total_trained']} files, {progress['total_chunks']} chunks done")
    print()

    # Authenticate with Google Drive
    print("Authenticating with Google Drive...")
    service = get_gdrive_service()
    about = service.about().get(fields="user").execute()
    email = about.get("user", {}).get("emailAddress", "unknown")
    print(f"Authenticated as: {email}")

    # Connect to PostalHub
    if not args.dry_run:
        print("Connecting to PostalHub...")
        postal = PostalTunnelClient()
        if not postal.connect():
            print("ERROR: Could not connect to PostalHub on port 49500")
            print("Is the Akashic server running?")
            sys.exit(1)
        print("Connected to PostalHub")
    else:
        postal = None

    # Crawl
    print()
    if args.folder == "root":
        # Get root items
        items = list_folder(service, "root")
        root_folders = [f for f in items if f['mimeType'] == 'application/vnd.google-apps.folder']
        root_files = [f for f in items if f['mimeType'] != 'application/vnd.google-apps.folder']

        print(f"Root: {len(root_folders)} folders, {len(root_files)} files")
        print()

        # Process root files first
        print("--- ROOT FILES ---")
        batch = []
        for f in root_files:
            fid = f["id"]
            fname = f["name"]
            mime = f.get("mimeType", "")
            size = int(f.get("size", 0))

            all_seen = set(progress["trained_ids"] + progress["skipped_ids"] +
                           progress["image_ids"] + progress["error_ids"])
            if fid in all_seen:
                continue

            if is_video(mime) or mime in SKIP_MIMES:
                progress["skipped_ids"].append(fid)
                print(f"  [SKIP] {fname}")
                continue

            if mime in IMAGE_MIMES:
                progress["image_ids"].append(fid)
                print(f"  [IMAGE] {fname}")
                continue

            if size > 10 * 1024 * 1024:
                progress["skipped_ids"].append(fid)
                print(f"  [TOO BIG] {fname}")
                continue

            if args.dry_run:
                print(f"  [DRY] {fname} ({mime})")
                continue

            text = read_gdrive_file(service, fid, fname, mime)
            if not text or len(text.strip()) < 50:
                progress["skipped_ids"].append(fid)
                continue

            text = text.strip()
            h = content_hash(text)
            if h in progress["content_hashes"]:
                progress["skipped_ids"].append(fid)
                print(f"  [DUP] {fname}")
                continue
            progress["content_hashes"].append(h)

            chunks = chunk_text(text)
            for i, chunk in enumerate(chunks):
                batch.append({
                    "text": chunk,
                    "source": f"gdrive:root/{fname}" + (f" (part {i+1}/{len(chunks)})" if len(chunks) > 1 else ""),
                    "domain": "akashic_foundation",
                })
                progress["total_chunks"] += 1

            progress["trained_ids"].append(fid)
            progress["total_trained"] += 1
            print(f"  [OK] {fname} -- {len(text)} chars, {len(chunks)} chunk(s)")

            if len(batch) >= BATCH_SIZE:
                send_batch(postal, batch)
                batch = []
                save_progress(progress)

        if batch:
            send_batch(postal, batch)
        save_progress(progress)

        # Then crawl all folders
        print("\n--- FOLDERS ---")
        for folder in root_folders:
            crawl_folder(service, postal, folder["id"],
                         folder["name"], progress, args.dry_run)
    else:
        crawl_folder(service, postal, args.folder, "custom", progress, args.dry_run)

    # Summary
    print("\n" + "=" * 60)
    print("COMPLETE")
    print(f"  Files trained:  {progress['total_trained']}")
    print(f"  Total chunks:   {progress['total_chunks']}")
    print(f"  Images found:   {len(progress['image_ids'])}")
    print(f"  Skipped:        {len(progress['skipped_ids'])}")
    print(f"  Errors:         {len(progress['error_ids'])}")
    print(f"  Folders:        {len(progress['folders_crawled'])}")
    print(f"  Unique hashes:  {len(progress['content_hashes'])}")
    print("=" * 60)
    save_progress(progress)


if __name__ == "__main__":
    main()
