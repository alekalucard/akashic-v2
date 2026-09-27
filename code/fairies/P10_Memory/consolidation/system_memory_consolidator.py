"""
SystemMemoryConsolidator - Organize scraped knowledge into the Universal Library

Purpose: Process SRM_Intake files and organize them into:
  1. Domain clusters (programming, philosophy, chemistry, etc.)
  2. Sibling clusters (sections of same lesson/book grouped together)
  3. Manifests with tracers linking related content

Architecture:
  SYSTEM MEMORY (shared by all fairies)
  └── domains/
      ├── programming/
      │   ├── rosetta_code/
      │   │   ├── _manifest.json
      │   │   └── languages/
      │   │       ├── python/
      │   │       ├── rust/
      │   │       └── ... (800+ languages)
      │   ├── mozilla_mdn/
      │   └── geeksforgeeks/
      ├── philosophy/
      │   ├── gutenberg/
      │   │   ├── plato/
      │   │   ├── nietzsche/
      │   │   └── ...
      │   └── stanford_encyclopedia/
      ├── chemistry/
      ├── engineering/
      ├── graphics/
      └── gamedev/

Plane: P10 (Memory)
Mantra: "All knowledge, organized and accessible."
"""

from __future__ import annotations

import os
import sys
import json
import hashlib
import shutil
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass, field
import time

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@dataclass
class ClusterManifest:
    """Manifest for a sibling cluster (e.g., all sections of a lesson)."""
    cluster_id: str
    title: str
    domain: str
    source: str
    section_count: int = 0
    sections: List[Dict[str, Any]] = field(default_factory=list)
    tracers: List[Dict[str, str]] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> Dict:
        return {
            "cluster_id": self.cluster_id,
            "title": self.title,
            "domain": self.domain,
            "source": self.source,
            "section_count": self.section_count,
            "sections": self.sections,
            "tracers": self.tracers,
            "created_at": self.created_at or datetime.now().isoformat(),
        }


class SystemMemoryConsolidator:
    """
    Consolidate scraped knowledge into organized system memory.

    Routes content by:
    1. Domain (programming, philosophy, chemistry, etc.)
    2. Source (rosetta_code, gutenberg, libretexts, etc.)
    3. Sibling clusters (group sections of same lesson/book)
    """

    # Source detection patterns
    SOURCE_PATTERNS = {
        "rosetta_code": ["rosettacode.org"],
        "mozilla_mdn": ["developer.mozilla.org"],
        "geeksforgeeks": ["geeksforgeeks.org"],
        "scratchapixel": ["scratchapixel.com"],
        "gutenberg": ["gutenberg.org"],
        "standard_ebooks": ["standardebooks.org"],
        "libretexts_chem": ["chem.libretexts.org"],
        "libretexts_eng": ["eng.libretexts.org"],
        "game_developer": ["gamedeveloper.com", "gamedev"],
    }

    # Domain mapping
    KIND_TO_DOMAIN = {
        "system.knowledge.programming": "programming",
        "system.knowledge.gamedev": "gamedev",
        "system.knowledge.graphics": "graphics",
        "system.knowledge.philosophy": "philosophy",
        "system.knowledge.chemistry": "chemistry",
        "system.knowledge.engineering": "engineering",
        "system.knowledge.literature": "literature",
        "system.knowledge.architecture": "architecture",
        "system.knowledge.mathematics": "mathematics",
        "system.knowledge.physics": "physics",
    }

    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root) if project_root else self._find_project_root()
        self.srm_intake = self.project_root / "P10_Memory" / "SRM_Intake"
        self.system_memory = self.project_root / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "system"

        # Stats
        self.stats = {
            "files_processed": 0,
            "files_skipped": 0,
            "clusters_created": 0,
            "domains": defaultdict(int),
            "sources": defaultdict(int),
            "errors": [],
        }

        # Cluster accumulator (parent_title -> files)
        self.clusters: Dict[str, List[Dict]] = defaultdict(list)

    def _find_project_root(self) -> Path:
        """Find project root by looking for P10_Memory."""
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "P10_Memory").exists():
                return parent
        return Path.cwd()

    def _detect_source(self, url: str) -> str:
        """Detect source from URL."""
        url_lower = url.lower()
        for source, patterns in self.SOURCE_PATTERNS.items():
            for pattern in patterns:
                if pattern in url_lower:
                    return source
        return "other"

    def _get_domain(self, kind: str, data: Dict) -> str:
        """Get domain from kind or data."""
        # Try exact match first
        if kind in self.KIND_TO_DOMAIN:
            return self.KIND_TO_DOMAIN[kind]

        # Try prefix match
        for k, v in self.KIND_TO_DOMAIN.items():
            if kind.startswith(k):
                return v

        # Fallback to data.domain
        return data.get("domain", "general")

    def _generate_cluster_id(self, title: str) -> str:
        """Generate stable cluster ID from title."""
        return hashlib.md5(title.encode()).hexdigest()[:8]

    def _sanitize_path(self, name: str) -> str:
        """Sanitize string for use as directory/file name."""
        if not name:
            return "unknown"
        # Replace ALL non-alphanumeric characters except dash and underscore
        sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
        # Collapse multiple underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Limit length
        sanitized = sanitized[:40]
        # Strip leading/trailing underscores
        sanitized = sanitized.strip('_')
        return sanitized or "unknown"

    def scan_intake(self, limit: int = None) -> Dict[str, Any]:
        """
        Scan SRM_Intake and categorize files.

        Args:
            limit: Max files to process (None for all)

        Returns:
            Summary of what was found
        """
        print(f"\n=== Scanning SRM_Intake ===\n")

        # Find all intake locations
        intake_dirs = [
            self.srm_intake,
            self.srm_intake / "SRM_Intake",  # Nested structure
        ]

        count = 0
        for intake_dir in intake_dirs:
            if not intake_dir.exists():
                continue

            for json_file in intake_dir.rglob("*.json"):
                if limit and count >= limit:
                    break

                try:
                    self._process_file(json_file)
                    count += 1

                    if count % 1000 == 0:
                        print(f"  Processed {count:,} files...")

                except Exception as e:
                    self.stats["errors"].append(f"{json_file.name}: {str(e)[:50]}")
                    self.stats["files_skipped"] += 1

        self.stats["files_processed"] = count

        print(f"\n=== Scan Complete ===")
        print(f"Files processed: {count:,}")
        print(f"Unique clusters found: {len(self.clusters):,}")
        print(f"Domains: {dict(self.stats['domains'])}")

        return self.stats

    def _process_file(self, filepath: Path):
        """Process a single JSON file and categorize it."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        kind = data.get("kind", "unknown")

        # Only process system.knowledge.* files
        if not kind.startswith("system.knowledge"):
            self.stats["files_skipped"] += 1
            return

        # Extract metadata
        file_data = data.get("data", {})
        meta = data.get("meta", {})

        domain = self._get_domain(kind, file_data)
        source_url = file_data.get("source_url", "")
        source = self._detect_source(source_url)
        parent_title = meta.get("parent_title") or file_data.get("query", "Unknown")
        section = meta.get("section", "Main")

        # Update stats
        self.stats["domains"][domain] += 1
        self.stats["sources"][source] += 1

        # Build cluster key
        cluster_key = f"{domain}|{source}|{parent_title}"

        # Add to cluster
        self.clusters[cluster_key].append({
            "filepath": str(filepath),
            "section": section,
            "domain": domain,
            "source": source,
            "parent_title": parent_title,
            "source_url": source_url,
            "kind": kind,
            "ts": data.get("ts", 0),
            "affect": data.get("affect", {}),
        })

    def consolidate(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Consolidate scanned files into organized system memory.

        Args:
            dry_run: If True, show what would happen without moving files

        Returns:
            Consolidation results
        """
        print(f"\n=== Consolidating System Memory ===")
        print(f"Dry run: {dry_run}")
        print(f"Clusters to process: {len(self.clusters):,}\n")

        results = {
            "clusters_created": 0,
            "files_moved": 0,
            "manifests_created": 0,
            "by_domain": defaultdict(int),
        }

        for cluster_key, files in self.clusters.items():
            domain, source, parent_title = cluster_key.split("|", 2)

            # Create destination path
            cluster_id = self._generate_cluster_id(parent_title)
            safe_title = self._sanitize_path(parent_title)

            cluster_dir = (
                self.system_memory /
                domain /
                source /
                f"{cluster_id}_{safe_title}"
            )

            if not dry_run:
                cluster_dir.mkdir(parents=True, exist_ok=True)

            # Create manifest
            manifest = ClusterManifest(
                cluster_id=cluster_id,
                title=parent_title,
                domain=domain,
                source=source,
                section_count=len(files),
            )

            # Process each file in cluster
            for i, file_info in enumerate(sorted(files, key=lambda x: x.get("section", ""))):
                section_num = f"{i+1:03d}"
                section_name = self._sanitize_path(file_info["section"])
                dest_name = f"section_{section_num}_{section_name}.json"

                manifest.sections.append({
                    "index": i + 1,
                    "section": file_info["section"],
                    "filename": dest_name,
                })

                if not dry_run:
                    # Copy file to destination
                    try:
                        src_path = Path(file_info["filepath"])
                        dest_path = cluster_dir / dest_name

                        if src_path.exists():
                            shutil.copy2(src_path, dest_path)
                            results["files_moved"] += 1
                    except Exception as e:
                        # Skip problematic files, log error
                        self.stats["errors"].append(f"Copy failed: {str(e)[:50]}")

            # Add tracers (same domain = related)
            # This is a simple tracer - could be enhanced with semantic similarity
            manifest.tracers = [
                {"relation": "same_domain", "domain": domain},
                {"relation": "same_source", "source": source},
            ]

            # Write manifest
            if not dry_run:
                manifest_path = cluster_dir / "_manifest.json"
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)
                results["manifests_created"] += 1

            results["clusters_created"] += 1
            results["by_domain"][domain] += 1

            if results["clusters_created"] % 100 == 0:
                print(f"  Created {results['clusters_created']:,} clusters...")

        print(f"\n=== Consolidation Complete ===")
        print(f"Clusters created: {results['clusters_created']:,}")
        print(f"Files moved: {results['files_moved']:,}")
        print(f"Manifests created: {results['manifests_created']:,}")
        print(f"By domain: {dict(results['by_domain'])}")

        return results

    def get_cluster_summary(self, limit: int = 20) -> List[Dict]:
        """Get summary of largest clusters."""
        summaries = []
        for cluster_key, files in sorted(self.clusters.items(), key=lambda x: -len(x[1]))[:limit]:
            domain, source, parent_title = cluster_key.split("|", 2)
            summaries.append({
                "cluster_id": self._generate_cluster_id(parent_title),
                "title": parent_title,
                "domain": domain,
                "source": source,
                "section_count": len(files),
            })
        return summaries


def main():
    """CLI for system memory consolidation."""
    import argparse

    parser = argparse.ArgumentParser(description="Consolidate scraped knowledge into system memory")
    parser.add_argument("--scan", action="store_true", help="Scan intake and show summary")
    parser.add_argument("--consolidate", action="store_true", help="Actually consolidate files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen")
    parser.add_argument("--limit", type=int, help="Limit files to process")
    parser.add_argument("--summary", action="store_true", help="Show cluster summary")

    args = parser.parse_args()

    consolidator = SystemMemoryConsolidator()

    if args.scan or args.consolidate:
        consolidator.scan_intake(limit=args.limit)

        if args.summary:
            print("\n=== Top Clusters ===")
            for cluster in consolidator.get_cluster_summary(20):
                print(f"  [{cluster['section_count']:>4} sections] {cluster['domain']}/{cluster['source']}: {cluster['title'][:50]}")

        if args.consolidate:
            consolidator.consolidate(dry_run=args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
