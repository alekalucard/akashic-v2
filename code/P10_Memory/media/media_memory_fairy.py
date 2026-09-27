# MediaMemoryFairy - Media Memory Tools
# =========================================================
#
# This module provides MCP tools for media memory operations.
# Bridges with MediaIngestFairy for full dimensional media storage.
#
# Philosophy: "Store the soul, not the shell. Context IS Emotional Context."
#
# =========================================================

from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import hashlib
import time

# Storage paths
MEDIA_ROOT = Path(__file__).parent.parent.parent / "SRM_Intake" / "media"
MEDIA_INDEX_PATH = MEDIA_ROOT / "media_index.json"


class MediaIndex:
    """Simple index for stored media files."""

    def __init__(self):
        self.index_path = MEDIA_INDEX_PATH
        self._index: Dict[str, Dict] = {}
        self._load_index()

    def _load_index(self):
        """Load index from disk."""
        if self.index_path.exists():
            try:
                with open(self.index_path, 'r') as f:
                    self._index = json.load(f)
            except Exception:
                self._index = {}

    def _save_index(self):
        """Save index to disk."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, 'w') as f:
            json.dump(self._index, f, indent=2)

    def add(self, image_id: str, metadata: Dict) -> None:
        """Add entry to index."""
        self._index[image_id] = {
            **metadata,
            "indexed_at": time.time()
        }
        self._save_index()

    def get(self, image_id: str) -> Optional[Dict]:
        """Get entry from index."""
        return self._index.get(image_id)

    def search(self, query: str = "", tags: List[str] = None, limit: int = 20) -> List[Dict]:
        """Search media index."""
        results = []
        for img_id, meta in self._index.items():
            # Simple text search
            if query and query.lower() not in json.dumps(meta).lower():
                continue
            # Tag filter
            if tags:
                item_tags = meta.get("tags", [])
                if not any(t in item_tags for t in tags):
                    continue
            results.append({"id": img_id, **meta})
            if len(results) >= limit:
                break
        return results

    def count(self) -> int:
        """Count entries."""
        return len(self._index)


def ingest_image_fast(image_path: str, tags: List[str] = None) -> Dict[str, Any]:
    """
    Fast image ingestion - stores basic metadata.
    Full dimensional extraction happens via MediaIngestFairy.
    """
    path = Path(image_path)
    if not path.exists():
        return {"error": f"File not found: {image_path}"}

    # Generate ID from content hash
    with open(path, 'rb') as f:
        content_hash = hashlib.sha256(f.read()).hexdigest()[:16]

    image_id = f"img_{content_hash}"

    # Store in index
    index = MediaIndex()
    index.add(image_id, {
        "path": str(path.absolute()),
        "name": path.name,
        "size": path.stat().st_size,
        "tags": tags or [],
        "ingested_at": time.time(),
    })

    return {
        "ok": True,
        "image_id": image_id,
        "path": str(path),
    }


def register_media_memory_tools(mcp):
    """
    Register media memory tools with MCP server.

    Tools:
    - preserve_media: Store media file with tags
    - batch_preserve_media: Bulk ingest
    - get_media_preservation_stats: Index statistics
    """

    @mcp.tool()
    async def preserve_media(
        path: str,
        tags: str = "",
        description: str = ""
    ) -> str:
        """
        Preserve a media file (image/video/audio) in the memory system.

        Args:
            path: Path to media file
            tags: Comma-separated tags
            description: Optional description

        Returns:
            JSON with preservation result
        """
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        result = ingest_image_fast(path, tag_list)
        if description:
            index = MediaIndex()
            entry = index.get(result.get("image_id", ""))
            if entry:
                entry["description"] = description
                index.add(result["image_id"], entry)
        return json.dumps(result)

    @mcp.tool()
    async def batch_preserve_media(
        paths: str,
        tags: str = ""
    ) -> str:
        """
        Batch preserve multiple media files.

        Args:
            paths: JSON array of paths, or comma-separated paths
            tags: Comma-separated tags to apply to all

        Returns:
            JSON with results for each file
        """
        # Parse paths
        try:
            path_list = json.loads(paths)
        except json.JSONDecodeError:
            path_list = [p.strip() for p in paths.split(",") if p.strip()]

        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

        results = []
        for p in path_list:
            result = ingest_image_fast(p, tag_list)
            results.append(result)

        return json.dumps({
            "total": len(path_list),
            "successful": sum(1 for r in results if r.get("ok")),
            "results": results
        })

    @mcp.tool()
    async def get_media_preservation_stats() -> str:
        """
        Get statistics about preserved media.

        Returns:
            JSON with index statistics
        """
        index = MediaIndex()
        return json.dumps({
            "total_files": index.count(),
            "index_path": str(MEDIA_INDEX_PATH),
        })

    print("[MCP] Media memory tools registered")


# Init file for module
__all__ = [
    "MediaIndex",
    "ingest_image_fast",
    "register_media_memory_tools",
]
