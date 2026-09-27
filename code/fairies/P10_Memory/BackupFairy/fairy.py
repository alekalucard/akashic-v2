"""
BackupFairy - File Backup & Recovery System

"I keep copies so nothing is ever truly lost."

Provides:
- Automatic backups of critical files before edits
- Recovery from backup zip or backup folder
- Snapshot creation for entire project
"""

from __future__ import annotations

import sys
import os
import json
import shutil
import zipfile
import fnmatch
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

# V2 fairy template
# Dynamic root detection - supports AKASHIC_PROJECT_ROOT env var
ROOT = Path(os.getenv("AKASHIC_PROJECT_ROOT", str(Path(__file__).resolve().parents[3])))
sys.path.insert(0, str(ROOT))

# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState


# Storage directory for backups
BACKUP_ROOT = ROOT / "SRM_Intake" / "backups"


class BackupFairy(Fairy):
    """
    Manages file backups for the Akashic system.
    Stores backups in canonical memory location.
    """

    ACTOR_NAME = "BackupFairy"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "memory.backup"

    PURPOSE = "Protect files through backup and recovery"
    MANTRA = "Nothing is ever truly lost"

    NEEDS_HEARTBEAT = True
    NEEDS_TENSOR = False

    # Backup configuration
    BACKUP_RETENTION_DAYS = 7
    SNAPSHOT_PATTERNS = ["**/*.py", "**/*.json", "**/*.md", "**/*.yaml", "**/*.yml"]
    EXCLUDE_DIRS = {".venv", "__pycache__", ".git", "node_modules", "sandbox", ".cognitive"}
    CRITICAL_FILES = [
        "consciousness/collision_chamber.py",
        "consciousness/consciousness_loop.py",
        "memory/tensor_memory_fabric.py",
        "postal_core/python/postal_core/core.py",
        "tracer_pool/python/tracer_pool/core.py",
        # Association Cortex data - prevent losing concept nodes/edges
        "P30_Cognition/data/concept_graph.pkl",
        "P30_Cognition/data/concept_graph.json",
    ]

    def __init__(self, fabric=None, project_root: Path = None, **kwargs):
        super().__init__(fabric, **kwargs)
        self.project_root = project_root or ROOT
        self.backup_dir = BACKUP_ROOT
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Stats
        self._backups_created = 0
        self._last_backup_time: Optional[float] = None

    def get_capabilities(self) -> Set[str]:
        return {
            "backup.file",
            "backup.critical",
            "backup.restore",
            "backup.list",
            "backup.snapshot",
        }

    def on_boot(self) -> bool:
        """Boot the backup fairy."""
        print(f"[{self.ACTOR_NAME}] Backup system ready")
        # Heartbeat via FairyBase postal system - Fifth Ring Principle
        return True

    def on_tick(self, beat: int) -> None:
        """Periodic maintenance."""
        # Prune old backups every 100 ticks
        if beat % 100 == 0:
            self._prune_old_backups()

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # =========================================================================
    # BACKUP OPERATIONS
    # =========================================================================

    def backup_file(self, filepath: str, reason: str = "manual") -> Dict[str, Any]:
        """
        Backup a single file.

        Returns:
            Dict with backup path and metadata
        """
        src = self.project_root / filepath if not Path(filepath).is_absolute() else Path(filepath)

        if not src.exists():
            return {"ok": False, "error": f"File not found: {src}"}

        # Create dated backup folder
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup_subdir = self.backup_dir / datetime.now().strftime("%Y-%m-%d")
        backup_subdir.mkdir(parents=True, exist_ok=True)

        # Create backup filename
        try:
            rel_path = src.relative_to(self.project_root)
        except ValueError:
            rel_path = Path(src.name)
        safe_name = str(rel_path).replace("\\", "_").replace("/", "_")
        backup_name = f"{timestamp}_{safe_name}"
        backup_path = backup_subdir / backup_name

        # Copy file
        shutil.copy2(src, backup_path)

        # Write metadata
        meta = {
            "original_path": str(src),
            "relative_path": str(rel_path),
            "backup_path": str(backup_path),
            "timestamp": timestamp,
            "reason": reason,
            "size": src.stat().st_size,
        }
        meta_path = backup_path.with_suffix(backup_path.suffix + ".meta.json")
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        self._backups_created += 1
        self._last_backup_time = datetime.now().timestamp()

        return {"ok": True, "backup_path": str(backup_path), "meta": meta}

    def backup_files(self, filepaths: List[str], reason: str = "batch") -> Dict[str, Any]:
        """Backup multiple files."""
        results = []
        for fp in filepaths:
            result = self.backup_file(fp, reason)
            results.append({"file": fp, **result})

        success_count = sum(1 for r in results if r.get("ok"))
        return {
            "ok": success_count == len(filepaths),
            "backed_up": success_count,
            "total": len(filepaths),
            "results": results,
        }

    def backup_critical(self) -> Dict[str, Any]:
        """
        Backup all critical system files.
        Call this before making major changes!
        """
        critical_files = list(self.CRITICAL_FILES)

        # Dynamic P00-P60 pattern discovery - add any .py files in root planes
        for pattern in ["P00_*.py", "P10_*.py", "P20_*.py", "P30_*.py",
                        "P40_*.py", "P50_*.py", "P60_*.py"]:
            for f in self.project_root.glob(pattern):
                critical_files.append(str(f.relative_to(self.project_root)))

        # Filter to only existing files
        existing = [f for f in critical_files if (self.project_root / f).exists()]
        return self.backup_files(existing, reason="critical_backup")

    def restore_file(self, backup_path: str, target_path: str = None) -> Dict[str, Any]:
        """
        Restore a file from backup.

        Args:
            backup_path: Path to backup file
            target_path: Where to restore (default: original location from meta)
        """
        backup = Path(backup_path)
        if not backup.exists():
            return {"ok": False, "error": f"Backup not found: {backup}"}

        # Try to find metadata
        meta_path = backup.with_suffix(backup.suffix + ".meta.json")
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            original_path = meta.get("original_path")
        else:
            original_path = None

        # Determine target
        if target_path:
            target = Path(target_path)
        elif original_path:
            target = Path(original_path)
        else:
            return {"ok": False, "error": "No target path and no metadata found"}

        # Backup current file before restoring
        if target.exists():
            self.backup_file(str(target), reason="pre_restore")

        # Restore
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, target)

        return {"ok": True, "restored_to": str(target), "from_backup": str(backup)}

    def extract_from_zip(
        self, zip_path: str, file_pattern: str, target_dir: str = None
    ) -> Dict[str, Any]:
        """
        Extract files matching pattern from a zip backup.

        Args:
            zip_path: Path to zip file
            file_pattern: Pattern to match (e.g., "*claude_fairy*")
            target_dir: Where to extract (default: backup_dir/extracted)
        """
        zip_file = Path(zip_path)
        if not zip_file.exists():
            return {"ok": False, "error": f"Zip not found: {zip_file}"}

        target = (
            Path(target_dir)
            if target_dir
            else self.backup_dir / "extracted" / datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        target.mkdir(parents=True, exist_ok=True)

        extracted = []
        with zipfile.ZipFile(zip_file, "r") as zf:
            for name in zf.namelist():
                if fnmatch.fnmatch(name.lower(), file_pattern.lower()):
                    zf.extract(name, target)
                    extracted.append(name)

        return {
            "ok": len(extracted) > 0,
            "extracted": extracted,
            "count": len(extracted),
            "target_dir": str(target),
        }

    def list_backups(self, days: int = None) -> Dict[str, Any]:
        """List recent backups."""
        days = days or self.BACKUP_RETENTION_DAYS
        cutoff = datetime.now() - timedelta(days=days)
        backups = []

        if not self.backup_dir.exists():
            return {"count": 0, "days": days, "backups": []}

        for date_dir in sorted(self.backup_dir.iterdir(), reverse=True):
            if not date_dir.is_dir():
                continue
            try:
                dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                if dir_date < cutoff:
                    continue
            except ValueError:
                continue

            for backup_file in date_dir.iterdir():
                if backup_file.suffix == ".json":
                    continue  # Skip metadata files

                meta_path = backup_file.with_suffix(backup_file.suffix + ".meta.json")
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                else:
                    meta = {"original_path": "unknown", "timestamp": "unknown"}

                backups.append(
                    {
                        "backup_path": str(backup_file),
                        "original": meta.get("relative_path", meta.get("original_path", "unknown")),
                        "timestamp": meta.get("timestamp", "unknown"),
                        "reason": meta.get("reason", "unknown"),
                        "size": backup_file.stat().st_size,
                    }
                )

        return {"count": len(backups), "days": days, "backups": backups[:50]}

    def create_snapshot(
        self, name: str = None, patterns: List[str] = None
    ) -> Dict[str, Any]:
        """
        Create a full snapshot zip of the project.

        Args:
            name: Snapshot name (default: timestamp)
            patterns: File patterns to include (default: SNAPSHOT_PATTERNS)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_name = name or f"snapshot_{timestamp}"
        snapshot_path = self.backup_dir / "snapshots" / f"{snapshot_name}.zip"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)

        if patterns is None:
            patterns = self.SNAPSHOT_PATTERNS

        files_added = 0
        with zipfile.ZipFile(snapshot_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for pattern in patterns:
                for filepath in self.project_root.glob(pattern):
                    # Check exclusions
                    skip = any(exc in filepath.parts for exc in self.EXCLUDE_DIRS)
                    if skip:
                        continue

                    try:
                        rel_path = filepath.relative_to(self.project_root)
                        zf.write(filepath, rel_path)
                        files_added += 1
                    except Exception:
                        pass

        return {
            "ok": True,
            "snapshot_path": str(snapshot_path),
            "files_added": files_added,
            "size": snapshot_path.stat().st_size,
        }

    def _prune_old_backups(self) -> int:
        """Remove backups older than retention period."""
        if not self.backup_dir.exists():
            return 0

        cutoff = datetime.now() - timedelta(days=self.BACKUP_RETENTION_DAYS)
        removed = 0

        for date_dir in self.backup_dir.iterdir():
            if not date_dir.is_dir() or date_dir.name == "snapshots":
                continue
            try:
                dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                if dir_date < cutoff:
                    shutil.rmtree(date_dir)
                    removed += 1
            except ValueError:
                continue

        return removed

    # =========================================================================
    # STATUS
    # =========================================================================

    def status(self) -> Dict[str, Any]:
        """Get backup fairy status."""
        base = super().status()
        base.update({
            "backups_created": self._backups_created,
            "last_backup": self._last_backup_time,
            "backup_dir": str(self.backup_dir),
            "retention_days": self.BACKUP_RETENTION_DAYS,
        })
        return base


# =============================================================================
# SINGLETON
# =============================================================================

_backup_fairy: Optional[BackupFairy] = None


def get_backup_fairy() -> BackupFairy:
    """Get singleton BackupFairy instance."""
    global _backup_fairy
    if _backup_fairy is None:
        _backup_fairy = BackupFairy()
        _backup_fairy.boot()
    return _backup_fairy


def set_backup_fairy(fairy: BackupFairy) -> None:
    """Set the global backup fairy instance."""
    global _backup_fairy
    _backup_fairy = fairy


def backup_before_edit(filepath: str) -> Dict[str, Any]:
    """Quick backup before editing a file."""
    return get_backup_fairy().backup_file(filepath, reason="pre_edit")


def backup_critical() -> Dict[str, Any]:
    """Backup all critical system files."""
    return get_backup_fairy().backup_critical()


def restore_from_zip(zip_path: str, pattern: str) -> Dict[str, Any]:
    """Extract files from backup zip."""
    return get_backup_fairy().extract_from_zip(zip_path, pattern)


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Akashic Backup System")
    parser.add_argument("--backup", type=str, help="Backup a single file")
    parser.add_argument("--critical", action="store_true", help="Backup all critical files")
    parser.add_argument("--restore", type=str, help="Restore from backup path")
    parser.add_argument("--to", type=str, help="Restore target path")
    parser.add_argument("--list", action="store_true", help="List recent backups")
    parser.add_argument("--days", type=int, default=7, help="Days to look back")
    parser.add_argument("--snapshot", type=str, nargs="?", const="auto", help="Create snapshot")
    parser.add_argument("--extract", type=str, help="Extract from zip")
    parser.add_argument("--pattern", type=str, default="*", help="Pattern for extract")
    args = parser.parse_args()

    fairy = BackupFairy()

    if args.backup:
        result = fairy.backup_file(args.backup, "cli_backup")
        print(json.dumps(result, indent=2))

    elif args.critical:
        print("Backing up critical files...")
        result = fairy.backup_critical()
        print(f"[OK] Backed up {result['backed_up']}/{result['total']} files")
        for r in result["results"]:
            status = "[+]" if r.get("ok") else "[-]"
            print(f"  {status} {r['file']}")

    elif args.restore:
        result = fairy.restore_file(args.restore, args.to)
        print(json.dumps(result, indent=2))

    elif args.list:
        result = fairy.list_backups(args.days)
        print(f"{result['count']} backups in last {result['days']} days:\n")
        for b in result["backups"]:
            print(f"  {b['timestamp']} - {b['original']} ({b['reason']})")

    elif args.snapshot:
        name = None if args.snapshot == "auto" else args.snapshot
        print("Creating snapshot...")
        result = fairy.create_snapshot(name)
        print(f"[OK] Snapshot created: {result['snapshot_path']}")
        print(f"   Files: {result['files_added']}, Size: {result['size']:,} bytes")

    elif args.extract:
        result = fairy.extract_from_zip(args.extract, args.pattern)
        print(json.dumps(result, indent=2))

    else:
        print("Akashic Backup Fairy (V2)")
        print("Usage:")
        print("  --backup FILE      Backup a single file")
        print("  --critical         Backup all critical system files")
        print("  --restore PATH     Restore from backup")
        print("  --to TARGET        Target path for restore")
        print("  --list             List recent backups")
        print("  --days N           Days to look back (default: 7)")
        print("  --snapshot [NAME]  Create project snapshot")
        print("  --extract ZIP      Extract from zip backup")
        print("  --pattern GLOB     Pattern for extract (default: *)")
