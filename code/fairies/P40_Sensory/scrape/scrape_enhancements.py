# ScrapeFairy Enhancements - Container Support, Deduplication, Version Tracking
# Adds support for: EPUB, ZIP, RAR, PDF, image extraction, content deduplication
#
# Usage: 
#   from scrape_enhancements import EnhancedScrapeFairy
#   fairy = EnhancedScrapeFairy()
#   fairy.ingest_ebook("path/to/book.epub")

from __future__ import annotations

import os
import io
import re
import json
import time
import hashlib
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlparse
import shutil

# Container libraries - install if missing
try:
    import ebooklib
    from ebooklib import epub
    HAS_EBOOKLIB = True
except ImportError:
    HAS_EBOOKLIB = False
    print("[ScrapeFairy] [WARN] ebooklib not installed - EPUB support disabled")
    print("  Install with: pip install ebooklib --break-system-packages")

try:
    import zipfile
    HAS_ZIPFILE = True
except ImportError:
    HAS_ZIPFILE = False

try:
    import rarfile
    HAS_RARFILE = True
except ImportError:
    HAS_RARFILE = False
    print("[ScrapeFairy] [WARN] rarfile not installed - RAR support disabled")
    print("  Install with: pip install rarfile --break-system-packages")

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    print("[ScrapeFairy] [WARN] PyMuPDF not installed - PDF support disabled")
    print("  Install with: pip install pymupdf --break-system-packages")

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("[ScrapeFairy] [WARN] Pillow not installed - Image processing disabled")
    print("  Install with: pip install Pillow --break-system-packages")

from bs4 import BeautifulSoup


# ══════════════════════════════════════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════════════════════════════════════

def _get_project_root() -> Path:
    """Find project root."""
    current = Path(__file__).parent
    while current.parent != current:
        if (current / "SRM_Intake").exists():
            return current
        current = current.parent
    return Path.cwd()

PROJECT_ROOT = _get_project_root()
SRM_INTAKE = PROJECT_ROOT / "SRM_Intake"
CONTENT_HASHES_FILE = PROJECT_ROOT / "P40_Sensory" / "scrape" / "content_hashes.json"
BOOK_REGISTRY_FILE = PROJECT_ROOT / "P40_Sensory" / "scrape" / "book_registry.json"
IMAGES_DIR = PROJECT_ROOT / "P10_Memory" / "Akashic_Records_Physical" / "Images" / "scraped"

# Ensure directories exist
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# CONTENT DEDUPLICATION
# ══════════════════════════════════════════════════════════════════════════════

class ContentDeduplicator:
    """
    Prevents ingesting the same content twice using content hashing.
    
    Tracks:
    - Content hash (SHA256 of normalized text)
    - Source info (URL, file path, etc.)
    - First seen timestamp
    - Version info if available
    """
    
    def __init__(self, hashes_file: Path = CONTENT_HASHES_FILE):
        self.hashes_file = hashes_file
        self._hashes: Dict[str, Dict[str, Any]] = {}
        self._load()
    
    def _load(self):
        """Load existing hashes from disk."""
        if self.hashes_file.exists():
            try:
                with open(self.hashes_file, 'r') as f:
                    self._hashes = json.load(f)
                print(f"[Dedup] Loaded {len(self._hashes)} content hashes")
            except Exception as e:
                print(f"[Dedup] [WARN] Failed to load hashes: {e}")
                self._hashes = {}
    
    def _save(self):
        """Save hashes to disk."""
        try:
            self.hashes_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.hashes_file, 'w') as f:
                json.dump(self._hashes, f, indent=2)
        except Exception as e:
            print(f"[Dedup] [WARN] Failed to save hashes: {e}")
    
    def compute_hash(self, content: str) -> str:
        """
        Compute content hash from normalized text.
        
        Normalization:
        - Lowercase
        - Remove extra whitespace
        - Remove punctuation variations
        - Take first 50KB for speed (enough to identify)
        """
        # Normalize
        normalized = content.lower()
        normalized = re.sub(r'\s+', ' ', normalized)  # Collapse whitespace
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
        normalized = normalized[:50000]  # First 50KB
        
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    
    def is_duplicate(self, content: str) -> Tuple[bool, Optional[Dict]]:
        """
        Check if content is a duplicate.
        
        Returns:
            (is_duplicate, existing_record or None)
        """
        content_hash = self.compute_hash(content)
        
        if content_hash in self._hashes:
            return True, self._hashes[content_hash]
        
        return False, None
    
    def register(self, content: str, source: str, title: str = "", 
                 version: str = "", metadata: Dict = None) -> str:
        """
        Register new content.
        
        Returns:
            Content hash
        """
        content_hash = self.compute_hash(content)
        
        self._hashes[content_hash] = {
            "hash": content_hash,
            "source": source,
            "title": title,
            "version": version,
            "first_seen": time.time(),
            "first_seen_iso": datetime.now().isoformat(),
            "word_count": len(content.split()),
            "metadata": metadata or {},
        }
        
        self._save()
        return content_hash
    
    def is_different_version(self, content: str, title: str) -> Tuple[bool, Optional[str]]:
        """
        Check if this is a different version of existing content.
        
        Matches by title similarity, then checks if content hash differs.
        
        Returns:
            (is_different_version, existing_version or None)
        """
        content_hash = self.compute_hash(content)
        title_lower = title.lower()
        
        # Find existing entries with similar title
        for existing_hash, record in self._hashes.items():
            existing_title = record.get("title", "").lower()
            
            # Simple title similarity check
            if self._titles_match(title_lower, existing_title):
                if content_hash != existing_hash:
                    # Same title, different content = different version
                    return True, record.get("version", "unknown")
                else:
                    # Same title, same content = duplicate
                    return False, None
        
        # No matching title found - this is new
        return False, None
    
    def _titles_match(self, title1: str, title2: str) -> bool:
        """Check if two titles refer to the same work."""
        # Normalize
        t1 = re.sub(r'[^\w\s]', '', title1).strip()
        t2 = re.sub(r'[^\w\s]', '', title2).strip()
        
        # Exact match
        if t1 == t2:
            return True
        
        # One contains the other (handles subtitles)
        if t1 in t2 or t2 in t1:
            return True
        
        # Word overlap > 80%
        words1 = set(t1.split())
        words2 = set(t2.split())
        if words1 and words2:
            overlap = len(words1 & words2) / max(len(words1), len(words2))
            if overlap > 0.8:
                return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get deduplication statistics."""
        return {
            "total_registered": len(self._hashes),
            "total_words": sum(r.get("word_count", 0) for r in self._hashes.values()),
        }


# ══════════════════════════════════════════════════════════════════════════════
# BOOK REGISTRY - Track books with version info
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BookRecord:
    """A registered book with version tracking."""
    
    book_id: str                    # Unique ID (e.g., gutenberg_1234)
    title: str
    author: str = ""
    version: str = "1.0"            # Edition/version string
    source: str = ""                # Where it came from
    source_url: str = ""
    content_hash: str = ""
    file_format: str = ""           # epub, pdf, txt, html
    word_count: int = 0
    has_images: bool = False
    image_count: int = 0
    first_ingested: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "version": self.version,
            "source": self.source,
            "source_url": self.source_url,
            "content_hash": self.content_hash,
            "file_format": self.file_format,
            "word_count": self.word_count,
            "has_images": self.has_images,
            "image_count": self.image_count,
            "first_ingested": self.first_ingested,
            "last_updated": self.last_updated,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BookRecord":
        return cls(**data)


class BookRegistry:
    """
    Registry of all ingested books with version tracking.
    
    Prevents re-ingesting the same book unless:
    - It's a different version/edition
    - Content has changed (different hash)
    """
    
    def __init__(self, registry_file: Path = BOOK_REGISTRY_FILE):
        self.registry_file = registry_file
        self._books: Dict[str, BookRecord] = {}  # book_id -> record
        self._title_index: Dict[str, List[str]] = {}  # normalized_title -> [book_ids]
        self._load()
    
    def _load(self):
        """Load registry from disk."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, 'r') as f:
                    data = json.load(f)
                
                for book_id, book_data in data.get("books", {}).items():
                    record = BookRecord.from_dict(book_data)
                    self._books[book_id] = record
                    self._index_title(record)
                
                print(f"[BookRegistry] Loaded {len(self._books)} books")
            except Exception as e:
                print(f"[BookRegistry] [WARN] Failed to load: {e}")
    
    def _save(self):
        """Save registry to disk."""
        try:
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "books": {bid: b.to_dict() for bid, b in self._books.items()},
                "updated_at": datetime.now().isoformat(),
            }
            with open(self.registry_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[BookRegistry] [WARN] Failed to save: {e}")
    
    def _index_title(self, record: BookRecord):
        """Add book to title index."""
        normalized = self._normalize_title(record.title)
        if normalized not in self._title_index:
            self._title_index[normalized] = []
        if record.book_id not in self._title_index[normalized]:
            self._title_index[normalized].append(record.book_id)
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for matching."""
        return re.sub(r'[^\w\s]', '', title.lower()).strip()
    
    def find_by_title(self, title: str) -> List[BookRecord]:
        """Find all versions of a book by title."""
        normalized = self._normalize_title(title)
        book_ids = self._title_index.get(normalized, [])
        return [self._books[bid] for bid in book_ids if bid in self._books]
    
    def find_by_id(self, book_id: str) -> Optional[BookRecord]:
        """Find book by ID."""
        return self._books.get(book_id)
    
    def should_ingest(self, title: str, author: str, content_hash: str, 
                      version: str = "") -> Tuple[bool, str, Optional[BookRecord]]:
        """
        Determine if a book should be ingested.
        
        Returns:
            (should_ingest, reason, existing_record)
            
        Reasons:
        - "new": Never seen this book
        - "new_version": Different version of existing book
        - "updated": Same version but content changed
        - "duplicate": Already have this exact content
        """
        existing = self.find_by_title(title)
        
        if not existing:
            return True, "new", None
        
        # Check for exact hash match
        for record in existing:
            if record.content_hash == content_hash:
                return False, "duplicate", record
        
        # Check for same version
        for record in existing:
            if record.version == version and version:
                # Same version, different content = updated
                return True, "updated", record
        
        # Different version
        return True, "new_version", existing[0] if existing else None
    
    def register(self, record: BookRecord) -> str:
        """Register a new book or update existing."""
        self._books[record.book_id] = record
        self._index_title(record)
        self._save()
        return record.book_id
    
    def generate_book_id(self, source: str, title: str, identifier: str = "") -> str:
        """Generate a unique book ID."""
        # Clean source
        source_clean = re.sub(r'[^\w]', '_', source.lower())[:20]
        
        # Use identifier if available (e.g., Gutenberg ID)
        if identifier:
            return f"{source_clean}_{identifier}"
        
        # Otherwise hash title
        title_hash = hashlib.md5(title.lower().encode()).hexdigest()[:8]
        return f"{source_clean}_{title_hash}"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        formats = {}
        for b in self._books.values():
            fmt = b.file_format or "unknown"
            formats[fmt] = formats.get(fmt, 0) + 1
        
        return {
            "total_books": len(self._books),
            "unique_titles": len(self._title_index),
            "total_words": sum(b.word_count for b in self._books.values()),
            "books_with_images": sum(1 for b in self._books.values() if b.has_images),
            "total_images": sum(b.image_count for b in self._books.values()),
            "by_format": formats,
        }


# ══════════════════════════════════════════════════════════════════════════════
# CONTAINER EXTRACTORS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ExtractedBook:
    """Result of extracting a book from any format."""
    
    title: str
    author: str = ""
    content: str = ""                          # Full text content
    chapters: List[Dict[str, str]] = field(default_factory=list)  # [{title, content}]
    images: List[Dict[str, Any]] = field(default_factory=list)    # [{name, data, mime}]
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_format: str = ""
    version: str = ""
    identifier: str = ""                       # e.g., Gutenberg ID
    
    @property
    def word_count(self) -> int:
        return len(self.content.split())
    
    @property
    def has_images(self) -> bool:
        return len(self.images) > 0


class EPUBExtractor:
    """Extract content and images from EPUB files."""
    
    def extract(self, file_path: Path) -> Optional[ExtractedBook]:
        """Extract book from EPUB file."""
        if not HAS_EBOOKLIB:
            print("[EPUB] ebooklib not available")
            return None
        
        try:
            book = epub.read_epub(str(file_path))
            
            # Get metadata
            title = self._get_metadata(book, 'title') or file_path.stem
            author = self._get_metadata(book, 'creator') or ""
            identifier = self._get_metadata(book, 'identifier') or ""
            version = self._get_metadata(book, 'version') or "1.0"
            
            # Extract chapters
            chapters = []
            full_content = []
            
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    soup = BeautifulSoup(item.get_content(), 'html.parser')
                    
                    # Get chapter title
                    chapter_title = ""
                    for tag in ['h1', 'h2', 'h3', 'title']:
                        elem = soup.find(tag)
                        if elem:
                            chapter_title = elem.get_text(strip=True)
                            break
                    
                    if not chapter_title:
                        chapter_title = item.get_name()
                    
                    # Get text
                    text = soup.get_text(separator=' ', strip=True)
                    text = re.sub(r'\s+', ' ', text)
                    
                    if len(text) > 100:
                        chapters.append({
                            "title": chapter_title,
                            "content": text,
                        })
                        full_content.append(text)
            
            # Extract images
            images = []
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_IMAGE:
                    images.append({
                        "name": item.get_name(),
                        "data": item.get_content(),
                        "mime": item.media_type,
                    })
            
            return ExtractedBook(
                title=title,
                author=author,
                content="\n\n".join(full_content),
                chapters=chapters,
                images=images,
                metadata={
                    "language": self._get_metadata(book, 'language'),
                    "publisher": self._get_metadata(book, 'publisher'),
                    "date": self._get_metadata(book, 'date'),
                },
                source_format="epub",
                version=version,
                identifier=identifier,
            )
            
        except Exception as e:
            print(f"[EPUB] Extraction error: {e}")
            return None
    
    def _get_metadata(self, book, field: str) -> str:
        """Get metadata field from EPUB."""
        try:
            values = book.get_metadata('DC', field)
            if values:
                return str(values[0][0])
        except Exception:
            pass
        return ""


class PDFExtractor:
    """Extract content and images from PDF files."""
    
    def extract(self, file_path: Path) -> Optional[ExtractedBook]:
        """Extract book from PDF file."""
        if not HAS_PYMUPDF:
            print("[PDF] PyMuPDF not available")
            return None
        
        try:
            doc = fitz.open(str(file_path))
            
            # Get metadata
            metadata = doc.metadata or {}
            title = metadata.get('title', '') or file_path.stem
            author = metadata.get('author', '')
            
            # Extract pages
            chapters = []
            full_content = []
            images = []
            
            for page_num, page in enumerate(doc):
                # Extract text
                text = page.get_text()
                if text.strip():
                    chapters.append({
                        "title": f"Page {page_num + 1}",
                        "content": text,
                    })
                    full_content.append(text)
                
                # Extract images
                for img_index, img in enumerate(page.get_images(full=True)):
                    try:
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        images.append({
                            "name": f"page{page_num + 1}_img{img_index}.{base_image['ext']}",
                            "data": base_image["image"],
                            "mime": f"image/{base_image['ext']}",
                        })
                    except Exception:
                        pass
            
            doc.close()
            
            return ExtractedBook(
                title=title,
                author=author,
                content="\n\n".join(full_content),
                chapters=chapters,
                images=images,
                metadata=metadata,
                source_format="pdf",
            )
            
        except Exception as e:
            print(f"[PDF] Extraction error: {e}")
            return None


class ZIPExtractor:
    """Extract books from ZIP archives."""
    
    SUPPORTED_FORMATS = {'.txt', '.html', '.htm', '.epub', '.pdf'}
    IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    
    def __init__(self):
        self._epub_extractor = EPUBExtractor()
        self._pdf_extractor = PDFExtractor()
    
    def extract(self, file_path: Path) -> List[ExtractedBook]:
        """Extract all books from ZIP archive."""
        if not HAS_ZIPFILE:
            print("[ZIP] zipfile not available")
            return []
        
        books = []
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                # Find all extractable files
                for name in zf.namelist():
                    ext = Path(name).suffix.lower()
                    
                    if ext in self.SUPPORTED_FORMATS:
                        # Extract to temp and process
                        with tempfile.TemporaryDirectory() as tmp:
                            extracted_path = Path(tmp) / Path(name).name
                            
                            with zf.open(name) as src, open(extracted_path, 'wb') as dst:
                                dst.write(src.read())
                            
                            book = self._extract_file(extracted_path, ext)
                            if book:
                                books.append(book)
                
                # Also collect standalone images
                images = []
                for name in zf.namelist():
                    ext = Path(name).suffix.lower()
                    if ext in self.IMAGE_FORMATS:
                        images.append({
                            "name": Path(name).name,
                            "data": zf.read(name),
                            "mime": f"image/{ext[1:]}",
                        })
                
                # Attach images to first book if any
                if books and images:
                    books[0].images.extend(images)
        
        except Exception as e:
            print(f"[ZIP] Extraction error: {e}")
        
        return books
    
    def _extract_file(self, path: Path, ext: str) -> Optional[ExtractedBook]:
        """Extract a single file based on format."""
        if ext == '.epub':
            return self._epub_extractor.extract(path)
        elif ext == '.pdf':
            return self._pdf_extractor.extract(path)
        elif ext in {'.txt', '.html', '.htm'}:
            return self._extract_text(path, ext)
        return None
    
    def _extract_text(self, path: Path, ext: str) -> Optional[ExtractedBook]:
        """Extract plain text or HTML file."""
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if ext in {'.html', '.htm'}:
                soup = BeautifulSoup(content, 'html.parser')
                title = soup.find('title')
                title = title.get_text(strip=True) if title else path.stem
                content = soup.get_text(separator=' ', strip=True)
            else:
                title = path.stem
            
            return ExtractedBook(
                title=title,
                content=content,
                source_format=ext[1:],
            )
            
        except Exception as e:
            print(f"[TEXT] Extraction error: {e}")
            return None


class RARExtractor:
    """Extract books from RAR archives."""
    
    SUPPORTED_FORMATS = {'.txt', '.html', '.htm', '.epub', '.pdf'}
    IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    
    def __init__(self):
        self._epub_extractor = EPUBExtractor()
        self._pdf_extractor = PDFExtractor()
    
    def extract(self, file_path: Path) -> List[ExtractedBook]:
        """Extract all books from RAR archive."""
        if not HAS_RARFILE:
            print("[RAR] rarfile not available")
            return []
        
        books = []
        
        try:
            with rarfile.RarFile(str(file_path), 'r') as rf:
                # Find all extractable files
                for name in rf.namelist():
                    ext = Path(name).suffix.lower()
                    
                    if ext in self.SUPPORTED_FORMATS:
                        # Extract to temp and process
                        with tempfile.TemporaryDirectory() as tmp:
                            extracted_path = Path(tmp) / Path(name).name
                            rf.extract(name, tmp)
                            
                            book = self._extract_file(Path(tmp) / name, ext)
                            if book:
                                books.append(book)
                
                # Also collect standalone images
                images = []
                for name in rf.namelist():
                    ext = Path(name).suffix.lower()
                    if ext in self.IMAGE_FORMATS:
                        images.append({
                            "name": Path(name).name,
                            "data": rf.read(name),
                            "mime": f"image/{ext[1:]}",
                        })
                
                # Attach images to first book if any
                if books and images:
                    books[0].images.extend(images)
        
        except Exception as e:
            print(f"[RAR] Extraction error: {e}")
        
        return books
    
    def _extract_file(self, path: Path, ext: str) -> Optional[ExtractedBook]:
        """Extract a single file based on format."""
        if ext == '.epub':
            return self._epub_extractor.extract(path)
        elif ext == '.pdf':
            return self._pdf_extractor.extract(path)
        elif ext in {'.txt', '.html', '.htm'}:
            return self._extract_text(path, ext)
        return None
    
    def _extract_text(self, path: Path, ext: str) -> Optional[ExtractedBook]:
        """Extract plain text or HTML file."""
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if ext in {'.html', '.htm'}:
                soup = BeautifulSoup(content, 'html.parser')
                title = soup.find('title')
                title = title.get_text(strip=True) if title else path.stem
                content = soup.get_text(separator=' ', strip=True)
            else:
                title = path.stem
            
            return ExtractedBook(
                title=title,
                content=content,
                source_format=ext[1:],
            )
            
        except Exception as e:
            print(f"[TEXT] Extraction error: {e}")
            return None


# ══════════════════════════════════════════════════════════════════════════════
# ENHANCED SCRAPE FAIRY
# ══════════════════════════════════════════════════════════════════════════════

class EnhancedScrapeFairy:
    """
    Enhanced ScrapeFairy with:
    - EPUB, PDF, ZIP, RAR support
    - Image extraction from books
    - Content deduplication
    - Version tracking
    """
    
    VERSION = "2.0.0"
    
    def __init__(self, srm_intake: Path = SRM_INTAKE, images_dir: Path = IMAGES_DIR):
        self.srm_intake = srm_intake
        self.images_dir = images_dir
        
        # Sub-components
        self.deduplicator = ContentDeduplicator()
        self.registry = BookRegistry()
        
        # Extractors
        self._epub = EPUBExtractor()
        self._pdf = PDFExtractor()
        self._zip = ZIPExtractor()
        self._rar = RARExtractor()
        
        # Stats
        self.stats = {
            "books_processed": 0,
            "books_ingested": 0,
            "books_skipped_duplicate": 0,
            "images_extracted": 0,
            "images_saved": 0,
            "errors": 0,
        }
        
        print(f"[EnhancedScrapeFairy] v{self.VERSION} initialized")
        print(f"  EPUB: {'[OK]' if HAS_EBOOKLIB else '[X]'}")
        print(f"  PDF:  {'[OK]' if HAS_PYMUPDF else '[X]'}")
        print(f"  ZIP:  {'[OK]' if HAS_ZIPFILE else '[X]'}")
        print(f"  RAR:  {'[OK]' if HAS_RARFILE else '[X]'}")
        print(f"  PIL:  {'[OK]' if HAS_PIL else '[X]'}")
    
    def ingest_file(self, file_path: Path, source: str = "local") -> Dict[str, Any]:
        """
        Ingest a book file (EPUB, PDF, ZIP, RAR).
        
        Returns:
            Result dict with status and details
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return {"ok": False, "error": "File not found"}
        
        ext = file_path.suffix.lower()
        self.stats["books_processed"] += 1
        
        # Extract based on format
        books = []
        
        if ext == '.epub':
            book = self._epub.extract(file_path)
            if book:
                books = [book]
        elif ext == '.pdf':
            book = self._pdf.extract(file_path)
            if book:
                books = [book]
        elif ext == '.zip':
            books = self._zip.extract(file_path)
        elif ext == '.rar':
            books = self._rar.extract(file_path)
        else:
            return {"ok": False, "error": f"Unsupported format: {ext}"}
        
        if not books:
            self.stats["errors"] += 1
            return {"ok": False, "error": "Extraction failed"}
        
        results = []
        
        for book in books:
            result = self._ingest_book(book, source, str(file_path))
            results.append(result)
        
        return {
            "ok": True,
            "books_found": len(books),
            "results": results,
        }
    
    def ingest_folder(self, folder_path: Path, recursive: bool = True) -> Dict[str, Any]:
        """Ingest all supported books from a folder."""
        folder_path = Path(folder_path)
        
        if not folder_path.is_dir():
            return {"ok": False, "error": "Not a directory"}
        
        supported = {'.epub', '.pdf', '.zip', '.rar'}
        
        if recursive:
            files = [f for f in folder_path.rglob('*') if f.suffix.lower() in supported]
        else:
            files = [f for f in folder_path.iterdir() if f.suffix.lower() in supported]
        
        print(f"[EnhancedScrapeFairy] Found {len(files)} supported files")
        
        results = []
        for file in files:
            result = self.ingest_file(file, source="folder")
            results.append({"file": str(file), **result})
        
        return {
            "ok": True,
            "files_processed": len(files),
            "results": results,
            "stats": self.stats,
        }
    
    def _ingest_book(self, book: ExtractedBook, source: str, source_path: str) -> Dict[str, Any]:
        """Ingest a single extracted book."""
        
        # Compute content hash
        content_hash = self.deduplicator.compute_hash(book.content)
        
        # Check if should ingest
        should_ingest, reason, existing = self.registry.should_ingest(
            title=book.title,
            author=book.author,
            content_hash=content_hash,
            version=book.version,
        )
        
        if not should_ingest:
            self.stats["books_skipped_duplicate"] += 1
            print(f"[EnhancedScrapeFairy]  Skipped (duplicate): {book.title}")
            return {
                "ok": False,
                "reason": reason,
                "title": book.title,
                "existing_version": existing.version if existing else None,
            }
        
        # Register content
        self.deduplicator.register(
            content=book.content,
            source=source,
            title=book.title,
            version=book.version,
        )
        
        # Generate book ID
        book_id = self.registry.generate_book_id(
            source=source,
            title=book.title,
            identifier=book.identifier,
        )
        
        # Save images
        saved_images = self._save_images(book.images, book_id)
        self.stats["images_extracted"] += len(book.images)
        self.stats["images_saved"] += len(saved_images)
        
        # Create book record
        record = BookRecord(
            book_id=book_id,
            title=book.title,
            author=book.author,
            version=book.version,
            source=source,
            source_url=source_path,
            content_hash=content_hash,
            file_format=book.source_format,
            word_count=book.word_count,
            has_images=book.has_images,
            image_count=len(book.images),
            metadata=book.metadata,
        )
        
        self.registry.register(record)
        
        # Ingest to SRM
        self._ingest_to_srm(book, record, saved_images)
        
        self.stats["books_ingested"] += 1
        print(f"[EnhancedScrapeFairy] [OK] Ingested ({reason}): {book.title} "
              f"({book.word_count} words, {len(book.images)} images)")
        
        return {
            "ok": True,
            "reason": reason,
            "book_id": book_id,
            "title": book.title,
            "word_count": book.word_count,
            "images": len(book.images),
            "version": book.version,
        }
    
    def _save_images(self, images: List[Dict], book_id: str) -> List[Path]:
        """Save extracted images to disk."""
        saved = []
        
        book_images_dir = self.images_dir / book_id
        book_images_dir.mkdir(parents=True, exist_ok=True)
        
        for img in images:
            try:
                img_path = book_images_dir / img["name"]
                with open(img_path, 'wb') as f:
                    f.write(img["data"])
                saved.append(img_path)
            except Exception as e:
                print(f"[EnhancedScrapeFairy] [WARN] Failed to save image: {e}")
        
        return saved
    
    def _ingest_to_srm(self, book: ExtractedBook, record: BookRecord, 
                       image_paths: List[Path]):
        """Ingest book content to SRM_Intake."""
        
        date_dir = self.srm_intake / datetime.now().strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        
        # Main book record
        main_record = {
            "kind": f"book.{book.source_format}",
            "domain": "literature",
            "book_id": record.book_id,
            "title": book.title,
            "author": book.author,
            "version": book.version,
            "content": book.content[:10000],  # First 10K chars for main record
            "word_count": book.word_count,
            "chapter_count": len(book.chapters),
            "has_images": book.has_images,
            "image_count": len(image_paths),
            "image_paths": [str(p) for p in image_paths[:10]],  # First 10 refs
            "metadata": book.metadata,
            "ts": time.time(),
            "source_format": book.source_format,
        }
        
        filename = f"book.{book.source_format}-{record.book_id[:8]}.json"
        with open(date_dir / filename, 'w', encoding='utf-8') as f:
            json.dump(main_record, f, indent=2, ensure_ascii=False)
        
        # Chapter records (for granular recall)
        for i, chapter in enumerate(book.chapters[:50]):  # Max 50 chapters
            chapter_record = {
                "kind": f"book.chapter",
                "domain": "literature",
                "book_id": record.book_id,
                "book_title": book.title,
                "chapter_title": chapter["title"],
                "chapter_index": i + 1,
                "content": chapter["content"][:5000],
                "ts": time.time(),
            }
            
            chapter_file = f"book.chapter-{record.book_id[:8]}-ch{i+1:03d}.json"
            with open(date_dir / chapter_file, 'w', encoding='utf-8') as f:
                json.dump(chapter_record, f, indent=2, ensure_ascii=False)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get combined statistics."""
        return {
            **self.stats,
            "dedup": self.deduplicator.get_stats(),
            "registry": self.registry.get_stats(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced ScrapeFairy - Book Ingestion")
    parser.add_argument("path", help="File or folder to ingest")
    parser.add_argument("--recursive", "-r", action="store_true", help="Recurse into subfolders")
    parser.add_argument("--stats", action="store_true", help="Show stats only")
    
    args = parser.parse_args()
    
    fairy = EnhancedScrapeFairy()
    
    if args.stats:
        print("\n Statistics:")
        import pprint
        pprint.pprint(fairy.get_stats())
        return
    
    path = Path(args.path)
    
    if path.is_file():
        result = fairy.ingest_file(path)
    elif path.is_dir():
        result = fairy.ingest_folder(path, recursive=args.recursive)
    else:
        print(f"[X] Path not found: {path}")
        return
    
    print("\n Results:")
    import pprint
    pprint.pprint(result)
    
    print("\n Final Stats:")
    pprint.pprint(fairy.get_stats())


if __name__ == "__main__":
    main()
