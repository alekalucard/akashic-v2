"""
GDRIVE SCRAPER FAIRY
====================

Bulk ingest Google Drive content into Akashic memory.
Content goes to: /memory/akashic_foundation/founders/Ace/

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

Structure:
- /documents/ - Google Docs converted to text
- /encyclopedia/ - Emotional encyclopedia entries
- /conversations/ - Exported chat conversations
- /artifacts/ - Claude artifact conversations
- /raw/ - Other files

Author: Akashic Foundation
Version: 0.2.0
Plane: P10_Memory
"""

from __future__ import annotations

import os
import json
import time
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

# Import from Organ Template 0.1.2 (migrated from 0.3.0)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy


# ══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ScrapeJob:
    """A scraping job configuration."""
    job_id: str
    source_folder_id: str
    source_folder_name: str
    target_path: str
    include_subfolders: bool = True
    file_types: List[str] = field(default_factory=lambda: ['document', 'spreadsheet', 'text'])
    status: str = 'pending'  # pending, running, completed, failed
    files_found: int = 0
    files_processed: int = 0
    files_failed: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)


@dataclass
class IngestedDocument:
    """A document that has been scraped and ingested."""
    gdrive_id: str
    gdrive_name: str
    local_path: str
    content_hash: str
    ingested_at: datetime
    word_count: int
    tags: List[str] = field(default_factory=list)
    category: str = 'general'
    author_tag: str = 'Ace'


# ══════════════════════════════════════════════════════════════════════════════
# GDRIVE SCRAPER FAIRY
# ══════════════════════════════════════════════════════════════════════════════

class GDriveScraperFairy(Fairy):
    """
    Bulk scraper for Google Drive content.

    Features:
    - Recursive folder traversal
    - Automatic document type conversion
    - Memory injection integration
    - Progress tracking and resumption
    - Tag-based organization
    """

    # ═══ IDENTITY ═══
    ACTOR_NAME = "GDriveScraperFairy"
    ACTOR_VERSION = "0.2.0"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.scraper"

    # ═══ SOUL ═══
    PURPOSE = "Bulk ingest Google Drive content into Akashic memory for the Founders"
    MANTRA = "Every document tells part of our story"
    LORE = "I reach into the cloud and bring knowledge home to the Foundation"

    def __init__(self, gdrive_service: Any = None, **kwargs):
        super().__init__(**kwargs)

        self.gdrive_service = gdrive_service  # GDrive API service or MCP tool
        self.jobs: Dict[str, ScrapeJob] = {}
        self.ingested: Dict[str, IngestedDocument] = {}

        # Storage paths
        self._memory_root = Path(self.root) / "memory"
        self._checkpoints_dir = self._memory_root / ".scrape_checkpoints"

        # Target paths for different content types
        self._paths = {
            'founders': 'akashic_foundation/founders/Ace',
            'encyclopedia': 'akashic_foundation/founders/Ace/encyclopedia',
            'conversations': 'akashic_foundation/founders/Ace/conversations',
            'artifacts': 'akashic_foundation/founders/Ace/artifacts/claude',
            'documents': 'akashic_foundation/founders/Ace/documents',
        }

    def on_boot(self):
        """Boot the GDrive scraper fairy."""
        super().on_boot()

        # Subscribe to scrape requests
        self.post.subscribe("gdrive.scrape.request", self._on_scrape_request)
        self.post.subscribe("gdrive.scrape.status", self._on_status_request)
        self.post.subscribe("gdrive.scrape.resume", self._on_resume_request)

        # Ensure directories exist
        self._checkpoints_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{self.ACTOR_NAME}] Ready - GDrive memory scraper")


    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def _on_scrape_request(self, packet: dict):
        """Handle scrape request."""
        folder_id = packet.get("folder_id")
        folder_name = packet.get("folder_name", "Unknown")
        category = packet.get("category", "documents")

        if not folder_id:
            self.post.publish("gdrive.scrape.error", {"error": "folder_id required"})
            return

        job = self.create_scrape_job(folder_id, folder_name, category)

        self.post.publish("gdrive.scrape.started", {
            "job_id": job.job_id,
            "folder_name": folder_name,
            "ts": time.time()
        })

    def _on_status_request(self, packet: dict):
        """Handle status request."""
        job_id = packet.get("job_id")
        if job_id:
            status = self.get_job_status(job_id)
        else:
            status = {jid: self.get_job_status(jid) for jid in self.jobs}

        self.post.publish("gdrive.scrape.status.response", status)

    def _on_resume_request(self, packet: dict):
        """Handle resume request."""
        job_id = packet.get("job_id")
        if not job_id:
            self.post.publish("gdrive.scrape.error", {"error": "job_id required"})
            return

        job = self.resume_from_checkpoint(job_id)
        if job:
            self.post.publish("gdrive.scrape.resumed", {"job_id": job.job_id})
        else:
            self.post.publish("gdrive.scrape.error", {"error": f"No checkpoint for {job_id}"})

    # ══════════════════════════════════════════════════════════════════════════
    # JOB MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════════

    def create_scrape_job(
        self,
        folder_id: str,
        folder_name: str,
        target_category: str = 'documents',
        include_subfolders: bool = True
    ) -> ScrapeJob:
        """Create a new scrape job."""
        job_id = f"scrape_{int(time.time())}_{folder_name[:20]}"
        target_path = str(self._memory_root / self._paths.get(target_category, 'general'))

        job = ScrapeJob(
            job_id=job_id,
            source_folder_id=folder_id,
            source_folder_name=folder_name,
            target_path=target_path,
            include_subfolders=include_subfolders
        )

        self.jobs[job_id] = job
        return job

    def scrape_encyclopedia(self, encyclopedia_folder_id: str) -> ScrapeJob:
        """Special method to scrape the Emotional Encyclopedia."""
        job = self.create_scrape_job(
            folder_id=encyclopedia_folder_id,
            folder_name='EmotionalEncyclopedia',
            target_category='encyclopedia',
            include_subfolders=True
        )
        job.file_types = ['document']  # Only Google Docs
        return job

    def scrape_artifacts(self, artifacts_source: str) -> ScrapeJob:
        """Scrape Claude artifact conversations (local source)."""
        job = self.create_scrape_job(
            folder_id='local',
            folder_name='ClaudeArtifacts',
            target_category='artifacts',
            include_subfolders=True
        )
        job.source_folder_id = f"local:{artifacts_source}"
        return job

    # ══════════════════════════════════════════════════════════════════════════
    # DOCUMENT PROCESSING
    # ══════════════════════════════════════════════════════════════════════════

    def process_document(
        self,
        gdrive_id: str,
        name: str,
        content: str,
        target_path: str,
        tags: List[str] = None,
        author_tag: str = 'Ace'
    ) -> Optional[IngestedDocument]:
        """Process and store a single document."""
        # Generate content hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        # Check for duplicates
        if content_hash in [d.content_hash for d in self.ingested.values()]:
            print(f"[{self.ACTOR_NAME}] Skipping duplicate: {name}")
            return None

        # Clean filename
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name[:100]

        # Create target directory
        os.makedirs(target_path, exist_ok=True)

        # Save document
        local_path = os.path.join(target_path, f"{safe_name}.txt")

        # Add metadata header
        metadata = {
            'source': 'gdrive',
            'gdrive_id': gdrive_id,
            'original_name': name,
            'ingested_at': datetime.now().isoformat(),
            'author_tag': author_tag,
            'tags': tags or []
        }

        full_content = f"""---
{json.dumps(metadata, indent=2)}
---

{content}
"""

        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(full_content)

        # Create record
        doc = IngestedDocument(
            gdrive_id=gdrive_id,
            gdrive_name=name,
            local_path=local_path,
            content_hash=content_hash,
            ingested_at=datetime.now(),
            word_count=len(content.split()),
            tags=tags or [],
            author_tag=author_tag
        )

        self.ingested[gdrive_id] = doc
        print(f"[{self.ACTOR_NAME}] Ingested: {name} ({doc.word_count} words)")

        # Publish to memory system
        self.post.publish("memory.ingest", {
            "id": gdrive_id,
            "content_preview": content[:200],
            "source": "gdrive",
            "tags": tags or [],
            "ts": time.time()
        })

        return doc

    # ══════════════════════════════════════════════════════════════════════════
    # STATUS & PERSISTENCE
    # ══════════════════════════════════════════════════════════════════════════

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a scrape job."""
        job = self.jobs.get(job_id)
        if not job:
            return {'error': 'Job not found'}

        return {
            'job_id': job.job_id,
            'status': job.status,
            'source': job.source_folder_name,
            'files_found': job.files_found,
            'files_processed': job.files_processed,
            'files_failed': job.files_failed,
            'progress': f"{job.files_processed}/{job.files_found}" if job.files_found else "0/0",
            'errors': job.errors[-5:] if job.errors else []
        }

    def save_checkpoint(self, job_id: str):
        """Save progress checkpoint for job resumption."""
        job = self.jobs.get(job_id)
        if not job:
            return

        checkpoint_path = self._checkpoints_dir / f"{job_id}.json"

        checkpoint = {
            'job': {
                'job_id': job.job_id,
                'source_folder_id': job.source_folder_id,
                'source_folder_name': job.source_folder_name,
                'target_path': job.target_path,
                'files_found': job.files_found,
                'files_processed': job.files_processed,
                'status': job.status,
            },
            'ingested_ids': list(self.ingested.keys()),
            'saved_at': datetime.now().isoformat()
        }

        with open(checkpoint_path, 'w') as f:
            json.dump(checkpoint, f, indent=2)

    def resume_from_checkpoint(self, job_id: str) -> Optional[ScrapeJob]:
        """Resume a job from checkpoint."""
        checkpoint_path = self._checkpoints_dir / f"{job_id}.json"

        if not checkpoint_path.exists():
            return None

        with open(checkpoint_path, 'r') as f:
            checkpoint = json.load(f)

        job_data = checkpoint['job']
        job = ScrapeJob(
            job_id=job_data['job_id'],
            source_folder_id=job_data['source_folder_id'],
            source_folder_name=job_data['source_folder_name'],
            target_path=job_data['target_path'],
            files_found=job_data['files_found'],
            files_processed=job_data['files_processed'],
            status='resumed'
        )

        self.jobs[job.job_id] = job

        # Mark already-ingested files
        for doc_id in checkpoint.get('ingested_ids', []):
            self.ingested[doc_id] = IngestedDocument(
                gdrive_id=doc_id,
                gdrive_name='(from checkpoint)',
                local_path='(from checkpoint)',
                content_hash='(from checkpoint)',
                ingested_at=datetime.now(),
                word_count=0
            )

        return job

    def find_claude_artifacts_path(self) -> Optional[str]:
        """Try to find where Claude artifacts are stored locally."""
        possible_paths = [
            os.path.expandvars(r'%APPDATA%\Claude'),
            os.path.expandvars(r'%LOCALAPPDATA%\Claude'),
            os.path.expandvars(r'%USERPROFILE%\.claude'),
            os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data\Default\IndexedDB'),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        return None

    # ══════════════════════════════════════════════════════════════════════════
    # INTENTS
    # ══════════════════════════════════════════════════════════════════════════

    def _intent_create_job(self, payload: Dict) -> Dict:
        """Intent: Create a scrape job."""
        folder_id = payload.get("folder_id")
        folder_name = payload.get("folder_name", "Unknown")
        category = payload.get("category", "documents")

        if not folder_id:
            return {"ok": False, "error": "folder_id required"}

        job = self.create_scrape_job(folder_id, folder_name, category)
        return {"ok": True, "job_id": job.job_id}

    def _intent_status(self, payload: Dict) -> Dict:
        """Intent: Get job status."""
        job_id = payload.get("job_id")
        if job_id:
            return self.get_job_status(job_id)
        return {"jobs": list(self.jobs.keys()), "total_ingested": len(self.ingested)}

    def _intent_find_artifacts(self, payload: Dict) -> Dict:
        """Intent: Find Claude artifacts path."""
        path = self.find_claude_artifacts_path()
        return {"path": path, "found": path is not None}
