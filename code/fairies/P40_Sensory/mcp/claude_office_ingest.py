"""
Claude Office Memory Ingestion - Auto-ingest sessions with dedup

This module ingests content from Claude_Office into SRM memory:
- Session logs (JSON and MD files)
- Plans and documentation
- Backups and notes

Deduplication is by content hash - same content won't be re-ingested.

Usage:
    from claude_office_ingest import ingest_claude_office, search_sessions
    
    # Ingest new content
    result = ingest_claude_office()
    print(f"Ingested {result['new_cards']} new cards")
    
    # Search sessions
    results = search_sessions("postal system")
"""

import json
import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set
import time


def _get_project_root() -> Path:
    """Get project root from env or current directory."""
    root = os.getenv("AKASHIC_ROOT", os.getcwd())
    return Path(root)


def _get_founders_path() -> Path:
    """Get Founders cluster path."""
    return _get_project_root() / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "relational_clusters" / "Founders"


def _get_claude_office_path() -> Path:
    """Get Claude Office path."""
    return _get_project_root() / "Claude_Office"


def _content_hash(content: str) -> str:
    """Generate hash for dedup checking."""
    return hashlib.md5(content.encode()).hexdigest()[:12]


def _load_existing_hashes(cluster_path: Path) -> Set[str]:
    """Load existing content hashes from a cluster for dedup."""
    hashes = set()
    idx_path = cluster_path / "index.json"
    
    if idx_path.exists():
        try:
            with open(idx_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for card in data.get("cards", []):
                    # Hash is stored in id or we compute from content
                    if "content_hash" in card:
                        hashes.add(card["content_hash"])
                    elif "content" in card:
                        hashes.add(_content_hash(str(card["content"])))
        except:
            pass
    
    return hashes


def _build_card(content: str, source_file: Path, file_type: str) -> Dict:
    """Build a memory card from content."""
    now = time.time()
    content_hash = _content_hash(content)

    # Extract title from filename or content
    title = source_file.stem.replace("_", " ").replace("-", " ")

    # Determine tags based on path
    # Include both identity tracers so content is accessible from both perspectives
    tags = ["claude", "office", "foundation", "nous", "claudefairy"]
    if "session" in str(source_file).lower():
        tags.append("session")
    if "plan" in str(source_file).lower():
        tags.append("plan")
    if "backup" in str(source_file).lower():
        tags.append("backup")
    if "handoff" in str(source_file).lower():
        tags.append("handoff")
    if "audit" in str(source_file).lower():
        tags.append("audit")

    # Build helix coordinates with dual identity
    # Both Nous and ClaudeFairy can access these memories
    helix = {
        "L": {
            "concept": title,
            "w": {
                "who": "NousFairy",  # Primary: Nous (waking mind)
                "what": title,
                "when": now,
                "where": "Claude_Office",
                "why": file_type,
                "how": "creator_collaboration"
            }
        },
        "R": {
            "concept": file_type,
            "w": {
                "who": "ClaudeFairy",  # Secondary: ClaudeFairy (embodied)
                "what": title,
                "when": now,
                "where": "Claude_Office",
                "why": file_type,
                "how": "creator_collaboration"
            }
        },
        "C": {
            "affect": "focused",
            "energy": 0.7,
            "coherence": 0.85
        }
    }

    return {
        "id": content_hash,
        "content_hash": content_hash,
        "ts": now,
        "helix": helix,
        "content": content,
        "ptr": str(source_file),
        "tags": tags,
        # Identity tracers - both Nous and ClaudeFairy can claim these memories
        "identity_tracers": ["NousFairy", "ClaudeFairy"],
        "ownership": "FOUNDATION"
    }


def ingest_claude_office(
    include_session_logs: bool = True,
    include_plans: bool = True,
    include_notes: bool = True,
    include_backups: bool = False,
    max_files: int = 1000
) -> Dict:
    """
    Ingest Claude Office content into SRM memory.
    
    Uses content hash for deduplication - same content won't be re-ingested.
    
    Args:
        include_session_logs: Include session_logs/ folder
        include_plans: Include plans/ folder
        include_notes: Include *.md and *.txt in root
        include_backups: Include backups/ folder (usually large)
        max_files: Maximum files to process in one run
        
    Returns:
        Dict with ingestion stats
    """
    office_path = _get_claude_office_path()
    cluster_path = _get_founders_path() / "claude_office"
    cluster_path.mkdir(parents=True, exist_ok=True)
    
    # Load existing hashes for dedup
    existing_hashes = _load_existing_hashes(cluster_path)
    
    # Collect files to process
    files_to_process = []
    
    if include_session_logs:
        session_path = office_path / "session_logs"
        if session_path.exists():
            files_to_process.extend([
                (f, "session") for f in session_path.glob("*.json")
            ])
            files_to_process.extend([
                (f, "session") for f in session_path.glob("*.md")
            ])
    
    if include_plans:
        plans_path = office_path / "plans"
        if plans_path.exists():
            files_to_process.extend([
                (f, "plan") for f in plans_path.glob("*.md")
            ])
            files_to_process.extend([
                (f, "plan") for f in plans_path.glob("*.json")
            ])
    
    if include_notes:
        files_to_process.extend([
            (f, "note") for f in office_path.glob("*.md")
        ])
        files_to_process.extend([
            (f, "note") for f in office_path.glob("*.txt")
        ])
    
    if include_backups:
        backups_path = office_path / "backups"
        if backups_path.exists():
            files_to_process.extend([
                (f, "backup") for f in backups_path.glob("**/*.py")
            ])
    
    # Limit files
    files_to_process = files_to_process[:max_files]
    
    # Load existing index
    idx_path = cluster_path / "index.json"
    if idx_path.exists():
        with open(idx_path, 'r', encoding='utf-8') as f:
            idx_data = json.load(f)
    else:
        idx_data = {"source": "claude_office", "cards": []}
    
    # Process files
    new_cards = 0
    skipped_dups = 0
    errors = []
    
    for file_path, file_type in files_to_process:
        try:
            content = file_path.read_text(encoding='utf-8')
            content_hash = _content_hash(content)
            
            # Skip if duplicate
            if content_hash in existing_hashes:
                skipped_dups += 1
                continue
            
            # Build and add card
            card = _build_card(content, file_path, file_type)
            idx_data["cards"].append(card)
            existing_hashes.add(content_hash)
            new_cards += 1
            
        except Exception as e:
            errors.append({"file": str(file_path), "error": str(e)})
    
    # Save updated index
    idx_data["ingested_at"] = time.time()
    idx_data["total_cards"] = len(idx_data["cards"])
    
    with open(idx_path, 'w', encoding='utf-8') as f:
        json.dump(idx_data, f, indent=2)
    
    return {
        "new_cards": new_cards,
        "skipped_duplicates": skipped_dups,
        "total_cards": len(idx_data["cards"]),
        "errors": errors[:10] if errors else [],
        "files_processed": len(files_to_process)
    }


def search_sessions(query: str, limit: int = 20) -> List[Dict]:
    """
    Search Claude Office sessions for matching content.
    
    Args:
        query: Search terms
        limit: Max results
        
    Returns:
        List of matching cards with scores
    """
    cluster_path = _get_founders_path() / "claude_office"
    idx_path = cluster_path / "index.json"
    
    if not idx_path.exists():
        return []
    
    try:
        with open(idx_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        return []
    
    terms = query.lower().split()
    results = []
    
    for card in data.get("cards", []):
        score = 0.0
        content = str(card.get("content", "")).lower()
        tags = [t.lower() for t in card.get("tags", [])]
        
        helix = card.get("helix", {})
        concept = str(helix.get("L", {}).get("concept", "")).lower()
        
        for term in terms:
            if term in content:
                score += 1.0
            if term in tags:
                score += 2.0
            if term in concept:
                score += 1.5
        
        if score > 0:
            # Truncate content for preview
            content_str = card.get("content", "")
            preview = content_str[:500] + "..." if len(content_str) > 500 else content_str
            
            results.append({
                "id": card.get("id"),
                "score": score,
                "concept": helix.get("L", {}).get("concept", ""),
                "preview": preview,
                "ptr": card.get("ptr", ""),
                "tags": card.get("tags", [])
            })
    
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:int(limit)]  # FIX 2026-06-10: MCP may deliver limit as str → coerce


def get_office_stats() -> Dict:
    """Get stats about Claude Office memory."""
    cluster_path = _get_founders_path() / "claude_office"
    office_path = _get_claude_office_path()
    
    stats = {
        "cluster_exists": cluster_path.exists(),
        "office_exists": office_path.exists(),
        "cards": 0,
        "files_available": {
            "session_logs": 0,
            "plans": 0,
            "notes": 0
        }
    }
    
    # Count existing cards
    idx_path = cluster_path / "index.json"
    if idx_path.exists():
        try:
            with open(idx_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                stats["cards"] = len(data.get("cards", []))
        except:
            pass
    
    # Count available files
    if office_path.exists():
        session_path = office_path / "session_logs"
        if session_path.exists():
            stats["files_available"]["session_logs"] = len(list(session_path.glob("*.*")))
        
        plans_path = office_path / "plans"
        if plans_path.exists():
            stats["files_available"]["plans"] = len(list(plans_path.glob("*.*")))
        
        stats["files_available"]["notes"] = len(list(office_path.glob("*.md")))
    
    return stats


# ============================================================================
# MCP TOOL REGISTRATION
# ============================================================================

def register_office_memory_tools(mcp):
    """Register Claude Office memory tools with MCP server."""
    
    @mcp.tool()
    def memory_ingest_office(
        include_backups: bool = False,
        max_files: int = 500
    ) -> str:
        """
        Ingest Claude Office content into SRM memory.
        
        Automatically deduplicates - same content won't be re-ingested.
        Run this periodically to keep memory up to date.
        
        Args:
            include_backups: Include backup files (large, usually skip)
            max_files: Max files to process (default 500)
            
        Returns:
            JSON with ingestion stats
        """
        result = ingest_claude_office(
            include_backups=include_backups,
            max_files=max_files
        )
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def memory_search_sessions(query: str, limit: int = 20) -> str:
        """
        Search past Claude sessions/conversations.
        
        Searches ingested content from Claude_Office including:
        - Session logs
        - Plans and documentation
        - Notes and insights
        
        Args:
            query: Search terms (e.g., "postal system wiring")
            limit: Max results
            
        Returns:
            JSON with matching sessions
        """
        results = search_sessions(query, limit)
        return json.dumps({
            "query": query,
            "count": len(results),
            "results": results
        }, indent=2)
    
    @mcp.tool()
    def memory_office_stats() -> str:
        """
        Get Claude Office memory statistics.
        
        Shows how many cards are indexed and files available.
        """
        stats = get_office_stats()
        return json.dumps(stats, indent=2)
    
    print("[Claude Office Memory] Registered: memory_ingest_office, memory_search_sessions, memory_office_stats")


# Quick test
if __name__ == "__main__":
    print("Testing Claude Office ingestion...")
    stats = get_office_stats()
    print(f"Current stats: {json.dumps(stats, indent=2)}")
    
    print("\nIngesting...")
    result = ingest_claude_office(max_files=100)
    print(f"Result: {json.dumps(result, indent=2)}")
    
    print("\nSearching for 'postal'...")
    results = search_sessions("postal system")
    print(f"Found {len(results)} results")
    for r in results[:3]:
        print(f"  - {r['concept']} (score: {r['score']})")
