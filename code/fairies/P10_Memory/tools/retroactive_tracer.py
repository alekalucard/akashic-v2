# ═══════════════════════════════════════════════════════════════════════════════
# RETROACTIVE TRACER ASSIGNMENT
# ═══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# This tool scans existing memories and assigns tracers retroactively.
# Used by Memory Librarian and Forensic Scribe to bring legacy content
# into the universal tracking system.
#
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict


def scan_memory_directory(
    directory: str,
    file_pattern: str = "*.json",
    recursive: bool = True
) -> List[Dict[str, Any]]:
    """
    Scan a directory for memory files.

    Returns list of dicts with:
    - filepath: full path
    - filename: just the name
    - content_hash: from file or generated
    - tags: if present
    - timestamp: if present
    - needs_tracer: whether tracer_id is missing
    """
    results = []
    base = Path(directory)

    if not base.exists():
        return results

    pattern = f"**/{file_pattern}" if recursive else file_pattern
    for filepath in base.glob(pattern):
        if filepath.is_file():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                result = {
                    "filepath": str(filepath),
                    "filename": filepath.name,
                    "content_hash": data.get("content_hash", hashlib.md5(filepath.name.encode()).hexdigest()[:16]),
                    "tags": data.get("tags", []),
                    "timestamp": data.get("timestamp", data.get("unix_ts")),
                    "type": data.get("type", data.get("session_type", "unknown")),
                    "title": data.get("title", filepath.stem),
                    "needs_tracer": "tracer_id" not in data,
                    "has_cluster": "cluster_id" in data,
                    "existing_tracer_id": data.get("tracer_id"),
                }
                results.append(result)
            except (json.JSONDecodeError, Exception) as e:
                # Non-JSON or corrupt file
                results.append({
                    "filepath": str(filepath),
                    "filename": filepath.name,
                    "error": str(e),
                    "needs_tracer": True,
                })

    return results


def assign_tracers_to_files(
    files: List[Dict[str, Any]],
    post,  # SharedPostalHub instance
    cluster_id: str = "",
    parent_tracer_id: str = "",
    content_type: str = "session",
    update_files: bool = True
) -> Dict[str, Any]:
    """
    Assign tracers to a list of files.

    Args:
        files: List from scan_memory_directory
        post: SharedPostalHub instance (has register_content)
        cluster_id: Cluster for grouping (optional, will auto-generate if empty)
        parent_tracer_id: Parent tracer for lineage
        content_type: Type of content (session, file, media, etc.)
        update_files: Whether to write tracer_id back to files

    Returns:
        Summary with counts and tracer assignments
    """
    if not cluster_id:
        cluster_id = f"retroactive_{int(time.time())}"

    assigned = []
    skipped = []
    errors = []

    for file_info in files:
        if "error" in file_info:
            errors.append(file_info)
            continue

        if not file_info.get("needs_tracer", True):
            skipped.append(file_info)
            continue

        try:
            # Create tracer via postal hub
            tracer = post.register_content(
                content_type=content_type,
                content_id=file_info["content_hash"],
                name=file_info.get("title", file_info["filename"]),
                cluster_id=cluster_id,
                parent_tracer_id=parent_tracer_id,
                metadata={
                    "filepath": file_info["filepath"],
                    "tags": file_info.get("tags", []),
                    "original_type": file_info.get("type"),
                }
            )

            file_info["assigned_tracer_id"] = tracer["id"]

            # Optionally update the file
            if update_files:
                filepath = file_info["filepath"]
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                data["tracer_id"] = tracer["id"]
                data["cluster_id"] = cluster_id
                if parent_tracer_id:
                    data["parent_tracer_id"] = parent_tracer_id

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

            assigned.append(file_info)

        except Exception as e:
            file_info["error"] = str(e)
            errors.append(file_info)

    return {
        "cluster_id": cluster_id,
        "parent_tracer_id": parent_tracer_id,
        "assigned_count": len(assigned),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "assigned": assigned,
        "skipped": skipped,
        "errors": errors,
    }


def build_clusters_from_tags(
    files: List[Dict[str, Any]]
) -> Dict[str, List[str]]:
    """
    Build cluster groupings from file tags.

    Returns dict: tag -> [content_hashes]
    """
    clusters = defaultdict(list)

    for file_info in files:
        content_hash = file_info.get("content_hash")
        if not content_hash:
            continue

        for tag in file_info.get("tags", []):
            clusters[tag].append(content_hash)

    return dict(clusters)


def build_clusters_from_dates(
    files: List[Dict[str, Any]],
    granularity: str = "day"  # day, week, month
) -> Dict[str, List[str]]:
    """
    Build cluster groupings from timestamps.

    Returns dict: date_key -> [content_hashes]
    """
    clusters = defaultdict(list)

    for file_info in files:
        content_hash = file_info.get("content_hash")
        timestamp = file_info.get("timestamp")

        if not content_hash or not timestamp:
            continue

        # Handle string or numeric timestamp
        if isinstance(timestamp, str):
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                ts = dt.timestamp()
            except:
                continue
        else:
            ts = timestamp

        from datetime import datetime
        dt = datetime.fromtimestamp(ts)

        if granularity == "day":
            key = dt.strftime("%Y-%m-%d")
        elif granularity == "week":
            key = dt.strftime("%Y-W%W")
        elif granularity == "month":
            key = dt.strftime("%Y-%m")
        else:
            key = dt.strftime("%Y-%m-%d")

        clusters[key].append(content_hash)

    return dict(clusters)


def generate_tracer_report(
    directory: str,
    recursive: bool = True
) -> Dict[str, Any]:
    """
    Generate a report of tracer status in a directory.

    Returns summary of what needs tracers vs what has them.
    """
    files = scan_memory_directory(directory, recursive=recursive)

    needs_tracer = [f for f in files if f.get("needs_tracer", True) and "error" not in f]
    has_tracer = [f for f in files if not f.get("needs_tracer", True)]
    has_errors = [f for f in files if "error" in f]

    tag_clusters = build_clusters_from_tags(files)
    date_clusters = build_clusters_from_dates(files)

    return {
        "directory": directory,
        "total_files": len(files),
        "needs_tracer": len(needs_tracer),
        "has_tracer": len(has_tracer),
        "has_errors": len(has_errors),
        "unique_tags": list(tag_clusters.keys()),
        "date_range": list(date_clusters.keys()),
        "files_by_type": _count_by_type(files),
        "sample_needs_tracer": needs_tracer[:5] if needs_tracer else [],
    }


def _count_by_type(files: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count files by type."""
    counts = defaultdict(int)
    for f in files:
        counts[f.get("type", "unknown")] += 1
    return dict(counts)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT - For use by Memory Librarian / Forensic Scribe
# ═══════════════════════════════════════════════════════════════════════════════

def retroactively_trace_memory(
    base_dir: str = None,
    post = None
) -> Dict[str, Any]:
    """
    Main entry point: Scan all memory locations and assign tracers.

    This is called by Memory Librarian to bring legacy content into
    the universal tracking system.

    Args:
        base_dir: Root of P10_Memory (auto-detected if None)
        post: SharedPostalHub instance (auto-fetched if None)

    Returns:
        Complete report of what was traced
    """
    if base_dir is None:
        # Try to find P10_Memory
        candidates = [
            os.path.join(os.getcwd(), "P10_Memory"),
            os.path.join(os.getenv("AKASHIC_ROOT", ""), "P10_Memory"),
            r"F:\Sandbox\ebook\P10_Memory",
        ]
        for c in candidates:
            if os.path.isdir(c):
                base_dir = c
                break

    if post is None:
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            post = get_shared_postal_hub()
        except ImportError:
            return {"error": "Could not get SharedPostalHub"}

    # Memory locations to scan
    locations = [
        ("session_memory", os.path.join(base_dir, "claude_office", "session_memory")),
        ("srm_intake", os.path.join(base_dir, "SRM_Intake")),
        ("app_archive", os.path.join(base_dir, "app_session_archive")),
        ("genesis", os.path.join(base_dir, "genesis_memories")),
        ("reasoning", os.path.join(base_dir, "reasoning_traces")),
    ]

    results = {}
    total_assigned = 0

    for name, path in locations:
        if not os.path.isdir(path):
            results[name] = {"skipped": True, "reason": "directory not found"}
            continue

        report = generate_tracer_report(path)

        if report["needs_tracer"] > 0:
            # Scan and assign
            files = scan_memory_directory(path)
            assignment = assign_tracers_to_files(
                files,
                post,
                cluster_id=f"memory_{name}",
                content_type="session" if "session" in name else "memory",
                update_files=True
            )
            results[name] = {
                "report": report,
                "assignment": assignment,
            }
            total_assigned += assignment["assigned_count"]
        else:
            results[name] = {
                "report": report,
                "assignment": None,
            }

    return {
        "base_dir": base_dir,
        "total_assigned": total_assigned,
        "locations": results,
        "timestamp": time.time(),
    }


__all__ = [
    "scan_memory_directory",
    "assign_tracers_to_files",
    "build_clusters_from_tags",
    "build_clusters_from_dates",
    "generate_tracer_report",
    "retroactively_trace_memory",
]
