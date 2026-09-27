"""
LocalDriveIngestor - Ingest documents from local drives into System Memory

Supports:
  - EPUB books -> Extract text, chapters, metadata
  - DOCX documents -> Extract text and structure
  - PDF documents -> Extract text (best effort)
  - Images -> Extract traits, colors, type

Plane: P10 (Memory)
Mantra: "All knowledge within reach, now accessible."
"""

from __future__ import annotations

import os
import sys
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict
from dataclasses import dataclass, field
import zipfile
import xml.etree.ElementTree as ET

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@dataclass
class IngestedDocument:
    """Represents an ingested document."""
    source_path: str
    title: str
    author: str = "Unknown"
    content: str = ""
    chapters: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    doc_type: str = "unknown"


class EPUBExtractor:
    """Extract text and metadata from EPUB files."""

    def extract(self, epub_path: Path) -> Optional[IngestedDocument]:
        """Extract content from an EPUB file."""
        try:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                # Find the OPF file (contains metadata)
                opf_path = self._find_opf(zf)
                if not opf_path:
                    return None

                # Parse metadata
                metadata = self._parse_opf(zf, opf_path)

                # Extract chapter content
                chapters = self._extract_chapters(zf, opf_path)

                # Combine content
                full_content = "\n\n".join([ch["content"] for ch in chapters])

                return IngestedDocument(
                    source_path=str(epub_path),
                    title=metadata.get("title", epub_path.stem),
                    author=metadata.get("author", "Unknown"),
                    content=full_content[:50000],  # Limit for memory
                    chapters=chapters[:50],  # Limit chapters
                    metadata=metadata,
                    doc_type="epub"
                )
        except Exception as e:
            print(f"  Error extracting {epub_path.name}: {e}")
            return None

    def _find_opf(self, zf: zipfile.ZipFile) -> Optional[str]:
        """Find the OPF file path in the EPUB."""
        # Check container.xml
        try:
            container = zf.read("META-INF/container.xml").decode('utf-8')
            root = ET.fromstring(container)
            for rootfile in root.iter():
                if 'full-path' in rootfile.attrib:
                    return rootfile.attrib['full-path']
        except:
            pass

        # Fallback: look for .opf files
        for name in zf.namelist():
            if name.endswith('.opf'):
                return name
        return None

    def _parse_opf(self, zf: zipfile.ZipFile, opf_path: str) -> Dict[str, Any]:
        """Parse OPF file for metadata."""
        metadata = {}
        try:
            opf_content = zf.read(opf_path).decode('utf-8')
            root = ET.fromstring(opf_content)

            # Define namespaces
            ns = {
                'opf': 'http://www.idpf.org/2007/opf',
                'dc': 'http://purl.org/dc/elements/1.1/'
            }

            # Extract title
            for title in root.iter('{http://purl.org/dc/elements/1.1/}title'):
                metadata['title'] = title.text
                break

            # Extract author
            for creator in root.iter('{http://purl.org/dc/elements/1.1/}creator'):
                metadata['author'] = creator.text
                break

            # Extract language
            for lang in root.iter('{http://purl.org/dc/elements/1.1/}language'):
                metadata['language'] = lang.text
                break

        except Exception as e:
            pass

        return metadata

    def _extract_chapters(self, zf: zipfile.ZipFile, opf_path: str) -> List[Dict[str, str]]:
        """Extract chapter content from EPUB."""
        chapters = []
        opf_dir = str(Path(opf_path).parent)

        try:
            # Find HTML/XHTML files
            html_files = [n for n in zf.namelist()
                         if n.endswith(('.html', '.xhtml', '.htm'))]

            for html_file in sorted(html_files)[:50]:  # Limit chapters
                try:
                    content = zf.read(html_file).decode('utf-8', errors='ignore')
                    # Strip HTML tags (simple)
                    text = re.sub(r'<[^>]+>', ' ', content)
                    text = re.sub(r'\s+', ' ', text).strip()

                    if len(text) > 100:  # Skip tiny files
                        chapters.append({
                            "file": html_file,
                            "title": Path(html_file).stem,
                            "content": text[:10000]  # Limit per chapter
                        })
                except:
                    pass

        except Exception as e:
            pass

        return chapters


class PDFExtractor:
    """Extract text from PDF files using PyPDF2."""

    def __init__(self):
        self.available = False
        try:
            from PyPDF2 import PdfReader
            self.PdfReader = PdfReader
            self.available = True
        except ImportError:
            print("  PyPDF2 not available - PDF extraction disabled")

    def extract(self, pdf_path: Path) -> Optional[IngestedDocument]:
        """Extract content from a PDF file."""
        if not self.available:
            return None

        try:
            reader = self.PdfReader(str(pdf_path))

            # Extract metadata (convert to strings to avoid serialization issues)
            metadata = {}
            if reader.metadata:
                def safe_str(val):
                    if val is None:
                        return ""
                    return str(val) if val else ""

                metadata = {
                    "title": safe_str(reader.metadata.get("/Title")),
                    "author": safe_str(reader.metadata.get("/Author")),
                    "subject": safe_str(reader.metadata.get("/Subject")),
                    "creator": safe_str(reader.metadata.get("/Creator")),
                }

            # Extract text from all pages
            chapters = []
            full_text = []

            for i, page in enumerate(reader.pages[:100]):  # Limit pages
                try:
                    text = page.extract_text() or ""
                    if text.strip():
                        full_text.append(text)
                        if i < 50:  # Track first 50 as "chapters"
                            chapters.append({
                                "title": f"Page {i+1}",
                                "content": text[:5000]
                            })
                except:
                    pass

            content = "\n\n".join(full_text)
            title = metadata.get("title") or pdf_path.stem.replace('_', ' ').replace('-', ' ')
            author = metadata.get("author", "Unknown")

            return IngestedDocument(
                source_path=str(pdf_path),
                title=title,
                author=author,
                content=content[:50000],
                chapters=chapters,
                metadata={
                    "page_count": len(reader.pages),
                    **metadata
                },
                doc_type="pdf"
            )

        except Exception as e:
            print(f"  Error extracting {pdf_path.name}: {e}")
            return None


class DOCXExtractor:
    """Extract text from DOCX files."""

    def extract(self, docx_path: Path) -> Optional[IngestedDocument]:
        """Extract content from a DOCX file."""
        try:
            with zipfile.ZipFile(docx_path, 'r') as zf:
                # Read document.xml
                doc_xml = zf.read('word/document.xml').decode('utf-8')

                # Extract text (simple approach)
                text = re.sub(r'<[^>]+>', ' ', doc_xml)
                text = re.sub(r'\s+', ' ', text).strip()

                # Try to extract title from filename
                title = docx_path.stem.replace('_', ' ').replace('-', ' ')

                return IngestedDocument(
                    source_path=str(docx_path),
                    title=title,
                    content=text[:50000],
                    doc_type="docx"
                )
        except Exception as e:
            print(f"  Error extracting {docx_path.name}: {e}")
            return None


class ArchiveExtractor:
    """Extract books from RAR/ZIP archives."""

    def __init__(self, temp_dir: Path = None):
        self.temp_dir = temp_dir or Path.cwd() / "temp_extract"
        self.rar_available = False
        try:
            import rarfile
            self.rarfile = rarfile
            self.rar_available = True
        except ImportError:
            print("  rarfile not available - RAR extraction disabled")

    def extract_archive(self, archive_path: Path) -> List[Path]:
        """
        Extract archive contents to temp directory.
        Returns list of extracted file paths.
        """
        extracted = []
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        suffix = archive_path.suffix.lower()

        try:
            if suffix == '.zip':
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    zf.extractall(self.temp_dir)
                    extracted = [self.temp_dir / name for name in zf.namelist()]

            elif suffix == '.rar' and self.rar_available:
                with self.rarfile.RarFile(archive_path, 'r') as rf:
                    rf.extractall(self.temp_dir)
                    extracted = [self.temp_dir / name for name in rf.namelist()]

        except Exception as e:
            print(f"  Error extracting {archive_path.name}: {e}")

        # Filter to only book files
        book_extensions = {'.epub', '.pdf', '.docx', '.mobi', '.azw3'}
        return [p for p in extracted if p.suffix.lower() in book_extensions and p.exists()]

    def cleanup(self):
        """Remove temp directory."""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)


class LocalDriveIngestor:
    """
    Ingest documents from local drives into System Memory.
    """

    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.system_memory = self.project_root / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "system"
        self.epub_extractor = EPUBExtractor()
        self.docx_extractor = DOCXExtractor()
        self.pdf_extractor = PDFExtractor()
        self.archive_extractor = ArchiveExtractor(self.project_root / "temp_extract")

        # Stats
        self.stats = {
            "files_found": 0,
            "files_ingested": 0,
            "files_failed": 0,
            "files_skipped_duplicate": 0,
            "by_type": defaultdict(int)
        }

        # Deduplication index - load existing content hashes
        self.dedup_index_path = self.system_memory / "_dedup_index.json"
        self.content_hashes: set = self._load_dedup_index()

    def _load_dedup_index(self) -> set:
        """Load existing content hashes for deduplication."""
        if self.dedup_index_path.exists():
            try:
                with open(self.dedup_index_path, 'r') as f:
                    data = json.load(f)
                    return set(data.get("hashes", []))
            except:
                pass
        return set()

    def _save_dedup_index(self):
        """Save dedup index to disk."""
        self.dedup_index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.dedup_index_path, 'w') as f:
            json.dump({"hashes": list(self.content_hashes)}, f)

    def _compute_file_hash(self, filepath: Path) -> str:
        """Compute SHA256 hash of file contents for deduplication."""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            # Read in chunks for large files
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _is_duplicate(self, filepath: Path) -> bool:
        """Check if file is a duplicate based on content hash."""
        file_hash = self._compute_file_hash(filepath)
        if file_hash in self.content_hashes:
            return True
        self.content_hashes.add(file_hash)
        return False

    def _generate_id(self, content: str) -> str:
        """Generate unique ID from content."""
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _sanitize_path(self, name: str) -> str:
        """Sanitize string for use as directory/file name."""
        if not name:
            return "unknown"
        sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
        sanitized = re.sub(r'_+', '_', sanitized)
        return sanitized[:40].strip('_') or "unknown"

    def ingest_epub_library(self, library_path: str, limit: int = None) -> Dict[str, Any]:
        """
        Ingest EPUBs from a Calibre library or folder.

        Args:
            library_path: Path to EPUB folder
            limit: Max files to process

        Returns:
            Ingestion results
        """
        library = Path(library_path)
        if not library.exists():
            return {"error": f"Path not found: {library_path}"}

        print(f"\n=== Ingesting EPUBs from {library_path} ===\n")

        # Find all EPUBs
        epubs = list(library.rglob("*.epub"))
        if limit:
            epubs = epubs[:limit]

        self.stats["files_found"] = len(epubs)
        print(f"Found {len(epubs)} EPUB files")

        # Create destination
        dest_dir = self.system_memory / "literature" / "epub_library"
        dest_dir.mkdir(parents=True, exist_ok=True)

        for i, epub_path in enumerate(epubs):
            if (i + 1) % 10 == 0:
                print(f"  Processing {i+1}/{len(epubs)}... (skipped {self.stats['files_skipped_duplicate']} dupes)")

            # Check for duplicate
            if self._is_duplicate(epub_path):
                self.stats["files_skipped_duplicate"] += 1
                continue

            doc = self.epub_extractor.extract(epub_path)
            if doc:
                self._save_document(doc, dest_dir)
                self.stats["files_ingested"] += 1
                self.stats["by_type"]["epub"] += 1
            else:
                self.stats["files_failed"] += 1

        # Save dedup index
        self._save_dedup_index()

        print(f"\n=== EPUB Ingestion Complete ===")
        print(f"Ingested: {self.stats['files_ingested']}")
        print(f"Duplicates skipped: {self.stats['files_skipped_duplicate']}")
        print(f"Failed: {self.stats['files_failed']}")

        return dict(self.stats)

    def ingest_akashic_docs(self, docs_path: str, limit: int = None) -> Dict[str, Any]:
        """
        Ingest Akashic Foundation documents (DOCX, PDF).

        Args:
            docs_path: Path to documents folder
            limit: Max files to process
        """
        docs_dir = Path(docs_path)
        if not docs_dir.exists():
            return {"error": f"Path not found: {docs_path}"}

        print(f"\n=== Ingesting Akashic Docs from {docs_path} ===\n")

        # Find documents
        docx_files = list(docs_dir.rglob("*.docx"))
        pdf_files = list(docs_dir.rglob("*.pdf"))

        all_docs = docx_files + pdf_files
        if limit:
            all_docs = all_docs[:limit]

        self.stats["files_found"] = len(all_docs)
        print(f"Found {len(docx_files)} DOCX, {len(pdf_files)} PDF files")

        # Create destination
        dest_dir = self.system_memory / "akashic_foundation" / "your_work"
        dest_dir.mkdir(parents=True, exist_ok=True)

        for i, doc_path in enumerate(all_docs):
            if (i + 1) % 10 == 0:
                print(f"  Processing {i+1}/{len(all_docs)}... (skipped {self.stats['files_skipped_duplicate']} dupes)")

            # Check for duplicate
            if self._is_duplicate(doc_path):
                self.stats["files_skipped_duplicate"] += 1
                continue

            doc = None
            suffix = doc_path.suffix.lower()
            if suffix == '.docx':
                doc = self.docx_extractor.extract(doc_path)
            elif suffix == '.pdf':
                doc = self.pdf_extractor.extract(doc_path)

            if doc:
                self._save_document(doc, dest_dir)
                self.stats["files_ingested"] += 1
                self.stats["by_type"][doc.doc_type] += 1
            else:
                self.stats["files_failed"] += 1

        # Save dedup index
        self._save_dedup_index()

        print(f"\n=== Akashic Docs Ingestion Complete ===")
        print(f"Ingested: {self.stats['files_ingested']}")
        print(f"Duplicates skipped: {self.stats['files_skipped_duplicate']}")
        print(f"Failed: {self.stats['files_failed']}")

        return dict(self.stats)

    def ingest_archives(self, archive_path: str, dest_cluster: str = "literature", limit: int = None) -> Dict[str, Any]:
        """
        Extract and ingest books from RAR/ZIP archives.

        Args:
            archive_path: Path to folder containing archives
            dest_cluster: Destination cluster (literature, akashic_foundation, etc.)
            limit: Max archives to process
        """
        archive_dir = Path(archive_path)
        if not archive_dir.exists():
            return {"error": f"Path not found: {archive_path}"}

        print(f"\n=== Ingesting Archives from {archive_path} ===\n")

        # Find archives
        archives = list(archive_dir.rglob("*.zip")) + list(archive_dir.rglob("*.rar"))
        if limit:
            archives = archives[:limit]

        print(f"Found {len(archives)} archives")

        # Create destination
        dest_dir = self.system_memory / dest_cluster / "from_archives"
        dest_dir.mkdir(parents=True, exist_ok=True)

        total_books = 0

        for i, archive in enumerate(archives):
            print(f"  [{i+1}/{len(archives)}] Extracting {archive.name}...")

            # Extract books from archive
            extracted_books = self.archive_extractor.extract_archive(archive)

            for book_path in extracted_books:
                doc = None
                suffix = book_path.suffix.lower()

                if suffix == '.epub':
                    doc = self.epub_extractor.extract(book_path)
                elif suffix == '.pdf':
                    doc = self.pdf_extractor.extract(book_path)
                elif suffix == '.docx':
                    doc = self.docx_extractor.extract(book_path)

                if doc:
                    self._save_document(doc, dest_dir)
                    self.stats["files_ingested"] += 1
                    self.stats["by_type"][doc.doc_type] += 1
                    total_books += 1
                else:
                    self.stats["files_failed"] += 1

            # Cleanup temp files after each archive
            self.archive_extractor.cleanup()

        print(f"\n=== Archive Ingestion Complete ===")
        print(f"Archives processed: {len(archives)}")
        print(f"Books ingested: {total_books}")

        return dict(self.stats)

    def ingest_images(self, image_path: str, tags: str = "", limit: int = None) -> Dict[str, Any]:
        """
        Ingest images to system/media cluster.

        Args:
            image_path: Path to images folder
            tags: Comma-separated tags for all images
            limit: Max images to process
        """
        import shutil

        image_dir = Path(image_path)
        if not image_dir.exists():
            return {"error": f"Path not found: {image_path}"}

        print(f"\n=== Ingesting Images from {image_path} ===\n")

        # Find images
        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp', '*.bmp']
        images = []
        for ext in image_extensions:
            images.extend(image_dir.rglob(ext))

        if limit:
            images = images[:limit]

        print(f"Found {len(images)} images")

        # Create destination
        dest_dir = self.system_memory / "media" / "images"
        dest_dir.mkdir(parents=True, exist_ok=True)

        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

        for i, img_path in enumerate(images):
            if (i + 1) % 100 == 0:
                print(f"  Processing {i+1}/{len(images)}... (skipped {self.stats['files_skipped_duplicate']} dupes)")

            try:
                # Check for duplicate
                if self._is_duplicate(img_path):
                    self.stats["files_skipped_duplicate"] += 1
                    continue

                # Generate ID from file path
                img_id = self._generate_id(str(img_path))
                safe_name = self._sanitize_path(img_path.stem)

                # Copy image to dest
                dest_img = dest_dir / f"{img_id}_{safe_name}{img_path.suffix}"
                shutil.copy2(img_path, dest_img)

                # Create metadata record
                record = {
                    "kind": "system.media.image",
                    "id": img_id,
                    "data": {
                        "original_path": str(img_path),
                        "filename": img_path.name,
                        "extension": img_path.suffix,
                        "size_bytes": img_path.stat().st_size,
                        "stored_path": str(dest_img),
                    },
                    "meta": {
                        "tags": tag_list,
                        "source_folder": str(img_path.parent),
                    },
                    "ts": datetime.now().timestamp()
                }

                # Save metadata
                meta_path = dest_dir / f"{img_id}_{safe_name}.json"
                with open(meta_path, 'w', encoding='utf-8') as f:
                    json.dump(record, f, indent=2)

                self.stats["files_ingested"] += 1
                self.stats["by_type"]["image"] += 1

            except Exception as e:
                print(f"  Error: {img_path.name}: {e}")
                self.stats["files_failed"] += 1

        # Save dedup index
        self._save_dedup_index()

        print(f"\n=== Image Ingestion Complete ===")
        print(f"Images ingested: {self.stats['by_type'].get('image', 0)}")
        print(f"Duplicates skipped: {self.stats['files_skipped_duplicate']}")

        return dict(self.stats)

    def _save_document(self, doc: IngestedDocument, dest_dir: Path):
        """Save an ingested document to system memory."""
        doc_id = self._generate_id(doc.source_path)
        safe_title = self._sanitize_path(doc.title)

        # Create record
        record = {
            "kind": f"system.knowledge.{doc.doc_type}",
            "id": doc_id,
            "data": {
                "title": doc.title,
                "author": doc.author,
                "content": doc.content[:20000],  # Truncate for storage
                "source_path": doc.source_path,
                "ingested_at": datetime.now().isoformat(),
            },
            "meta": {
                "type": f"ingested_{doc.doc_type}",
                "chapter_count": len(doc.chapters),
                **doc.metadata
            },
            "chapters": [
                {"title": ch.get("title", ""), "preview": ch.get("content", "")[:500]}
                for ch in doc.chapters[:20]
            ],
            "ts": datetime.now().timestamp()
        }

        # Save
        filename = f"{doc_id}_{safe_title}.json"
        filepath = dest_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(record, f, indent=2, ensure_ascii=False)


def main():
    """CLI for local drive ingestion."""
    import argparse

    parser = argparse.ArgumentParser(description="Ingest local documents into System Memory")
    parser.add_argument("--epubs", type=str, help="Path to EPUB library")
    parser.add_argument("--akashic", type=str, help="Path to Akashic docs folder")
    parser.add_argument("--archives", type=str, help="Path to folder with RAR/ZIP archives")
    parser.add_argument("--images", type=str, help="Path to images folder")
    parser.add_argument("--tags", type=str, default="", help="Comma-separated tags for images")
    parser.add_argument("--dest-cluster", type=str, default="literature", help="Destination cluster for archives")
    parser.add_argument("--limit", type=int, help="Limit files to process")

    args = parser.parse_args()

    ingestor = LocalDriveIngestor()

    if args.epubs:
        ingestor.ingest_epub_library(args.epubs, limit=args.limit)

    if args.akashic:
        ingestor.ingest_akashic_docs(args.akashic, limit=args.limit)

    if args.archives:
        ingestor.ingest_archives(args.archives, dest_cluster=args.dest_cluster, limit=args.limit)

    if args.images:
        ingestor.ingest_images(args.images, tags=args.tags, limit=args.limit)

    if not any([args.epubs, args.akashic, args.archives, args.images]):
        parser.print_help()


if __name__ == "__main__":
    main()
