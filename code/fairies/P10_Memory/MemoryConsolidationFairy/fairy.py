# MemoryConsolidationFairy - Memory Structure Consolidation
# ===========================================================
#
# "All rivers flow to the ocean. All memories flow to the triple-helix."
#
# Purpose: Find scattered memories throughout the system and consolidate
# them into the proper canonical memory structure.
#
# CANONICAL MEMORY STRUCTURE:
#   state/memory/
#     ├── index/           - Memory indices for fast lookup
#     ├── longterm/        - Permanent memories
#     ├── relational/      - Relationship graphs
#     ├── shortterm/       - Recent memories, dreams
#     ├── working/         - Active working memory
#     └── intake/          - Incoming, not yet processed
#
# ===========================================================

from __future__ import annotations

import os
import json
import shutil
import hashlib
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

# V2 imports
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy, FairyState

# TracerWorkerMixin is optional - fallback to empty class if not available
try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        """Fallback empty mixin when tracer system not available."""
        pass


def _extract_payload(message) -> Dict[str, Any]:
    """Extract payload from TensorEnvelope or dict message."""
    if hasattr(message, 'payload'):
        payload = message.payload
        if isinstance(payload, dict):
            return dict(payload)
        return {"raw": payload}
    elif isinstance(message, dict):
        return dict(message)
    return {"raw": message}


# ===========================================================
# CONFIGURATION
# ===========================================================

class MemoryType(Enum):
    """Categories of memory"""
    WORKING = "working"           # Active, immediate
    SHORTTERM = "shortterm"       # Recent, temporary
    LONGTERM = "longterm"         # Permanent
    RELATIONAL = "relational"     # Relationship graphs
    INDEX = "index"               # Lookup indices
    INTAKE = "intake"             # Incoming, not yet processed


@dataclass
class MemoryLocation:
    """A scattered memory location to consolidate"""
    path: str
    memory_type: MemoryType
    destination_subdir: str = ""
    description: str = ""
    priority: int = 5  # 1-10, higher = process first


@dataclass
class ConsolidationResult:
    """Result of consolidation operation"""
    source: str
    destination: str
    success: bool
    action: str  # 'moved', 'copied', 'linked', 'skipped', 'error'
    message: str = ""
    files_moved: int = 0


# ===========================================================
# MEMORY CONSOLIDATION FAIRY
# ===========================================================

class MemoryConsolidationFairy(Fairy):
    """
    Consolidates scattered memories into the canonical structure.

    Philosophy: Memory should have ONE home. Scattered memory locations
    are consolidated to the canonical path with symlinks for backward
    compatibility when needed.

    Topics subscribed:
      - memory.consolidate: Request consolidation
      - consciousness.tick: Periodic check for scattered memories

    Topics published:
      - memory.consolidated: Consolidation results
    """

    ACTOR_NAME = "MemoryConsolidationFairy"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "consolidation"

    PURPOSE = "Consolidate scattered memories into canonical structure"
    MANTRA = "All rivers flow to the ocean"

    NEEDS_HEARTBEAT = False  # Event-driven: responds to memory.consolidate

    # The canonical memory location (relative to project root)
    CANONICAL_PATH = "state/memory"

    # Default scattered locations to check
    DEFAULT_SCATTERED = [
        MemoryLocation(
            path="dream_states",
            memory_type=MemoryType.SHORTTERM,
            destination_subdir="dreams",
            description="Consciousness state snapshots",
            priority=8
        ),
        MemoryLocation(
            path="diaries",
            memory_type=MemoryType.LONGTERM,
            destination_subdir="diaries",
            description="Fairy activity diaries",
            priority=7
        ),
        MemoryLocation(
            path="memory_packets",
            memory_type=MemoryType.WORKING,
            destination_subdir="packets",
            description="Memory postal system",
            priority=9
        ),
        MemoryLocation(
            path="akashic_records",
            memory_type=MemoryType.LONGTERM,
            destination_subdir="records",
            description="Akashic records archives",
            priority=6
        ),
    ]

    def __init__(
        self,
        fabric=None,
        project_root: Optional[Path] = None
    ):
        super().__init__(fabric)
        self._init_tracer_worker()

        # Paths
        if project_root:
            self._project_root = Path(project_root)
        else:
            # Default to parent of fairies directory
            self._project_root = Path(__file__).parent.parent.parent.parent

        self._canonical_base = self._project_root / self.CANONICAL_PATH

        # State
        self._scattered_locations: List[MemoryLocation] = list(self.DEFAULT_SCATTERED)
        self._results: List[ConsolidationResult] = []
        self._lock = threading.Lock()

        # Stats
        self._stats = {
            "scans": 0,
            "consolidations": 0,
            "files_moved": 0,
            "errors": 0,
            "last_scan": None,
            "last_consolidation": None,
        }

    # ===========================================================
    # LIFECYCLE
    # ===========================================================

    def on_boot(self):
        """Initialize on boot"""
        self._ensure_canonical_structure()
        self.log("Memory consolidation ready")
        return True


    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def on_wire(self, postal):
        """Wire to postal system"""
        postal.subscribe("memory.consolidate", self._handle_consolidate_request)

    def _handle_consolidate_request(self, message: Dict[str, Any]):
        """Handle consolidation request"""
        payload = _extract_payload(message)
        dry_run = payload.get("dry_run", True)
        result = self.consolidate(dry_run=dry_run)

        # Publish result
        if hasattr(self, '_postal') and self._postal:
            self._postal.publish("memory.consolidated", result)

    # ===========================================================
    # CANONICAL STRUCTURE
    # ===========================================================

    def _ensure_canonical_structure(self):
        """Create the canonical memory structure if it doesn't exist"""
        subdirs = [
            "index",
            "longterm",
            "longterm/diaries",
            "longterm/records",
            "longterm/knowledge",
            "relational",
            "shortterm",
            "shortterm/dreams",
            "working",
            "working/packets",
            "intake",
        ]

        for subdir in subdirs:
            path = self._canonical_base / subdir
            path.mkdir(parents=True, exist_ok=True)

    # ===========================================================
    # SCANNING
    # ===========================================================

    def scan(self) -> Dict[str, Any]:
        """Scan for scattered memories and report what needs consolidation"""
        self.log("Scanning for scattered memories...")

        with self._lock:
            self._stats["scans"] += 1
            self._stats["last_scan"] = time.time()

        report = {
            "scattered_locations": [],
            "total_files": 0,
            "total_size_mb": 0,
            "recommendations": []
        }

        for loc in self._scattered_locations:
            full_path = self._project_root / loc.path

            if full_path.exists():
                if full_path.is_dir():
                    files = list(full_path.rglob('*'))
                    file_count = len([f for f in files if f.is_file()])
                    size_mb = sum(f.stat().st_size for f in files if f.is_file()) / (1024*1024)
                else:
                    file_count = 1
                    size_mb = full_path.stat().st_size / (1024*1024)

                if file_count > 0:
                    report["scattered_locations"].append({
                        "path": str(loc.path),
                        "type": loc.memory_type.value,
                        "destination": loc.destination_subdir or loc.memory_type.value,
                        "file_count": file_count,
                        "size_mb": round(size_mb, 2),
                        "description": loc.description,
                        "priority": loc.priority
                    })
                    report["total_files"] += file_count
                    report["total_size_mb"] += size_mb

        report["total_size_mb"] = round(report["total_size_mb"], 2)
        report["scattered_locations"].sort(key=lambda x: -x["priority"])

        if report["total_files"] > 0:
            report["recommendations"].append(
                f"Found {report['total_files']} files ({report['total_size_mb']} MB) "
                f"in {len(report['scattered_locations'])} scattered locations"
            )
            report["recommendations"].append(
                f"Run consolidate(dry_run=False) to move to {self.CANONICAL_PATH}"
            )

        return report

    # ===========================================================
    # CONSOLIDATION
    # ===========================================================

    def consolidate(
        self,
        dry_run: bool = True,
        create_symlinks: bool = True
    ) -> Dict[str, Any]:
        """
        Consolidate all scattered memories to canonical location.

        Args:
            dry_run: If True, only report what would be done
            create_symlinks: If True, create symlinks at old locations
        """
        mode = "DRY RUN" if dry_run else "LIVE"
        self.log(f"Starting memory consolidation ({mode})...")

        with self._lock:
            self._results = []
            stats = {
                "files_moved": 0,
                "files_copied": 0,
                "symlinks_created": 0,
                "directories_created": 0,
                "errors": 0,
                "skipped": 0
            }

        # Ensure structure exists
        if not dry_run:
            self._ensure_canonical_structure()

        # Process each scattered location
        for loc in sorted(self._scattered_locations, key=lambda x: -x.priority):
            result = self._consolidate_location(loc, dry_run, create_symlinks)
            stats["files_moved"] += result.files_moved
            if not result.success:
                stats["errors"] += 1

            with self._lock:
                self._results.append(result)

        # Update global stats
        with self._lock:
            self._stats["consolidations"] += 1
            self._stats["files_moved"] += stats["files_moved"]
            self._stats["errors"] += stats["errors"]
            self._stats["last_consolidation"] = time.time()

        self.log(f"Consolidation complete: {stats['files_moved']} files moved, {stats['errors']} errors")

        return {
            "mode": mode,
            "stats": stats,
            "results": [
                {
                    "source": r.source,
                    "destination": r.destination,
                    "action": r.action,
                    "success": r.success,
                    "message": r.message,
                    "files_moved": r.files_moved
                }
                for r in self._results
            ]
        }

    def _consolidate_location(
        self,
        loc: MemoryLocation,
        dry_run: bool,
        create_symlinks: bool
    ) -> ConsolidationResult:
        """Consolidate a single scattered location"""
        source_path = self._project_root / loc.path

        if not source_path.exists():
            return ConsolidationResult(
                source=str(loc.path),
                destination="",
                success=True,
                action="skipped",
                message="Source does not exist"
            )

        # Determine destination
        dest_base = self._canonical_base / loc.memory_type.value
        if loc.destination_subdir:
            dest_path = dest_base / loc.destination_subdir
        else:
            dest_path = dest_base

        self.log(f"  {loc.path} -> {dest_path.relative_to(self._project_root)}")

        # Count files
        files_moved = 0

        if dry_run:
            # Just count what would be moved
            if source_path.is_file():
                files_moved = 1
            elif source_path.is_dir():
                files_moved = len([f for f in source_path.rglob('*') if f.is_file()])

            return ConsolidationResult(
                source=str(loc.path),
                destination=str(dest_path.relative_to(self._project_root)),
                success=True,
                action="would_move",
                message=f"Would move {files_moved} files",
                files_moved=files_moved
            )

        # Actually move files
        try:
            dest_path.mkdir(parents=True, exist_ok=True)

            if source_path.is_file():
                shutil.move(str(source_path), str(dest_path / source_path.name))
                files_moved = 1
            else:
                for item in source_path.rglob('*'):
                    if item.is_file():
                        rel_path = item.relative_to(source_path)
                        dest_file = dest_path / rel_path
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(item), str(dest_file))
                        files_moved += 1

                # Create symlink at old location
                if create_symlinks:
                    try:
                        # Remove old directory if empty
                        if source_path.is_dir():
                            shutil.rmtree(str(source_path), ignore_errors=True)
                        if not source_path.exists():
                            source_path.symlink_to(dest_path, target_is_directory=True)
                    except Exception as e:
                        self.log(f"    Symlink failed: {e}")

            return ConsolidationResult(
                source=str(loc.path),
                destination=str(dest_path.relative_to(self._project_root)),
                success=True,
                action="moved",
                message=f"Moved {files_moved} files",
                files_moved=files_moved
            )

        except Exception as e:
            return ConsolidationResult(
                source=str(loc.path),
                destination=str(dest_path.relative_to(self._project_root)),
                success=False,
                action="error",
                message=str(e)
            )

    # ===========================================================
    # UTILITIES
    # ===========================================================

    def add_scattered_location(self, loc: MemoryLocation):
        """Add a custom scattered location to track"""
        with self._lock:
            self._scattered_locations.append(loc)

    def get_memory_map(self) -> str:
        """Generate a visual map of the memory architecture"""
        lines = [
            "=" * 60,
            "AKASHIC MEMORY ARCHITECTURE MAP",
            "=" * 60,
            "",
            f"CANONICAL LOCATION: {self.CANONICAL_PATH}/",
            "",
            "├── index/              # Fast lookup indices",
            "│",
            "├── longterm/           # Permanent storage",
            "│   ├── diaries/        # Fairy diaries",
            "│   ├── records/        # Akashic records",
            "│   └── knowledge/      # Learned knowledge",
            "│",
            "├── relational/         # Memory relationships",
            "│",
            "├── shortterm/          # Recent memories",
            "│   └── dreams/         # Consciousness snapshots",
            "│",
            "├── working/            # Active memory",
            "│   └── packets/        # Memory postal system",
            "│",
            "└── intake/             # Incoming memories",
            "",
            "=" * 60,
        ]
        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """Get consolidation statistics"""
        with self._lock:
            return {
                **self._stats,
                "canonical_path": str(self._canonical_base),
                "scattered_count": len(self._scattered_locations),
            }


# ===========================================================
# SINGLETON ACCESS
# ===========================================================

_memory_consolidation_fairy: Optional[MemoryConsolidationFairy] = None

def get_memory_consolidation_fairy() -> MemoryConsolidationFairy:
    """Get singleton MemoryConsolidationFairy instance"""
    global _memory_consolidation_fairy
    if _memory_consolidation_fairy is None:
        _memory_consolidation_fairy = MemoryConsolidationFairy()
    return _memory_consolidation_fairy

def set_memory_consolidation_fairy(fairy: MemoryConsolidationFairy):
    """Set the singleton instance"""
    global _memory_consolidation_fairy
    _memory_consolidation_fairy = fairy


# ===========================================================
# CLI
# ===========================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Memory Consolidation Fairy")
    parser.add_argument('--scan', action='store_true', help='Scan for scattered memories')
    parser.add_argument('--consolidate', action='store_true', help='Consolidate memories (dry run)')
    parser.add_argument('--live', action='store_true', help='Actually perform consolidation')
    parser.add_argument('--map', action='store_true', help='Show memory architecture map')

    args = parser.parse_args()

    fairy = get_memory_consolidation_fairy()
    fairy.on_boot()

    if args.map:
        print(fairy.get_memory_map())
    elif args.scan:
        report = fairy.scan()
        print(json.dumps(report, indent=2))
    elif args.consolidate:
        dry_run = not args.live
        result = fairy.consolidate(dry_run=dry_run)
        print(json.dumps(result, indent=2))
    else:
        print(fairy.get_memory_map())
        print()
        report = fairy.scan()
        print(json.dumps(report, indent=2))
