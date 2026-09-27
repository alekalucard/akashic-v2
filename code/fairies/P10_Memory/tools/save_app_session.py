"""
Save App Session to Memory System

Tool for saving Claude App (claude.ai) chat sessions into the Akashic
memory system where they can be recalled and processed by the collision chamber.

This bridges the gap between ephemeral app conversations and persistent
system memory.

Usage from MCP:
    akashic:save_app_session(content="...", title="...", tags="...")
"""

import os
import re
import json
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


# ============================================================================
# PATHS
# ============================================================================

def _get_memory_root() -> Path:
    """Get the P10_Memory root."""
    # Try relative to this file first
    here = Path(__file__).parent.parent
    if (here / "SRM_Intake").exists():
        return here

    # Fallback to environment
    akashic_root = os.getenv("AKASHIC_ROOT", "")
    if akashic_root:
        mem = Path(akashic_root).parent / "P10_Memory"
        if mem.exists():
            return mem

    # Last resort
    return Path("E:/coding projects/ebook/P10_Memory")


def _get_srm_intake_dir() -> Path:
    """Get today's SRM_Intake directory."""
    root = _get_memory_root()
    today = datetime.now().strftime("%Y-%m-%d")
    intake_dir = root / "SRM_Intake" / today
    intake_dir.mkdir(parents=True, exist_ok=True)
    return intake_dir


def _get_session_archive_dir() -> Path:
    """Get the session archive directory."""
    root = _get_memory_root()
    archive = root / "app_session_archive"
    archive.mkdir(parents=True, exist_ok=True)
    return archive


def _get_claude_office_dir() -> Path:
    """Get Claude's office memory directory."""
    root = _get_memory_root()
    office = root / "claude_office" / "session_memory"
    office.mkdir(parents=True, exist_ok=True)
    return office


# ============================================================================
# PORTAL COORDINATES — Lightweight concept extraction (no cortex needed)
# ============================================================================

# Common stop words to filter out of concept extraction
_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "don", "now", "and", "but", "or", "if", "while", "that", "this",
    "what", "which", "who", "whom", "these", "those", "am", "it", "its",
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "they",
    "them", "his", "her", "their", "about", "up", "down", "also", "like",
    "get", "got", "make", "made", "see", "say", "said", "think", "know",
    "let", "one", "two", "much", "many", "well", "back", "still", "even",
})


def _extract_concept_keys(text: str, max_concepts: int = 15) -> list:
    """
    Lightweight concept extraction from text — no cortex needed.

    Extracts meaningful words/phrases that serve as portal coordinates
    for entanglement with the cortex graph when the card is processed.
    """
    if not text or len(text) < 10:
        return []

    # Normalize
    text_lower = text.lower()

    # Extract words, filter stops and short words
    words = re.findall(r'\b[a-z][a-z_]{2,}\b', text_lower)
    word_freq = {}
    for w in words:
        if w not in _STOP_WORDS and len(w) > 2:
            word_freq[w] = word_freq.get(w, 0) + 1

    # Sort by frequency, take top concepts
    sorted_concepts = sorted(word_freq.items(), key=lambda x: -x[1])
    return [c[0] for c in sorted_concepts[:max_concepts]]


def _extract_portal_coords_lightweight(content: str, tags: list = None) -> Dict[str, Any]:
    """
    Extract portal coordinates from session content.

    Lightweight version for file-based saves (no live cortex).
    The concept_keys extracted here will entangle with the cortex graph
    when the SRM_Intake file is processed by the collision chamber.
    """
    concept_keys = _extract_concept_keys(content)
    if not concept_keys:
        return {}

    # Tags are themselves concept keys — add them
    if tags:
        for tag in tags:
            tag_lower = tag.lower().strip()
            if tag_lower and tag_lower not in concept_keys:
                concept_keys.insert(0, tag_lower)

    return {
        "concept_keys": concept_keys[:15],
        "superposition": {},  # No somatic state in file-based path
        "paradox_tension": 0.0,  # No chemistry in file-based path
        "birth_ts": time.time(),
        "source": "mcp_save",
        "lightweight": True,  # Flag: extracted without live cortex
    }


# ============================================================================
# SESSION RECORD CREATION
# ============================================================================

def create_session_record(
    content: str,
    title: str = "",
    tags: Optional[List[str]] = None,
    session_type: str = "app_chat",
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a structured session record for memory storage.

    Args:
        content: The full session content/transcript
        title: Optional title for the session
        tags: Optional list of topic tags
        session_type: Type of session (app_chat, system_chat, etc)
        metadata: Additional metadata

    Returns:
        Structured record ready for SRM intake
    """
    now = datetime.now()
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    # Extract portal coordinates for cortex entanglement
    portal_coords = _extract_portal_coords_lightweight(content, tags)

    record_metadata = metadata or {}
    if portal_coords:
        record_metadata["portal_coords"] = portal_coords

    record = {
        "type": "session_memory",
        "session_type": session_type,
        "title": title or f"Session {now.strftime('%Y-%m-%d %H:%M')}",
        "content": content,
        "content_hash": content_hash,
        "tags": tags or [],
        "timestamp": now.isoformat(),
        "unix_ts": time.time(),
        "word_count": len(content.split()),
        "metadata": record_metadata,
        "source": "claude_app",
        "processed": False
    }

    return record


# ============================================================================
# SAVE FUNCTIONS
# ============================================================================

def save_to_srm_intake(record: Dict[str, Any]) -> str:
    """
    Save session record to SRM_Intake for collision chamber processing.

    Returns the filepath where it was saved.
    """
    intake_dir = _get_srm_intake_dir()

    # Create filename with timestamp and hash
    ts = datetime.now().strftime("%H%M%S")
    filename = f"session.{record.get('session_type', 'app')}_{ts}_{record['content_hash']}.json"
    filepath = intake_dir / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    print(f"[SessionMemory] Saved to SRM_Intake: {filepath}")
    return str(filepath)


def save_to_claude_office(record: Dict[str, Any]) -> str:
    """
    Save session record to Claude's office for direct recall.

    Returns the filepath where it was saved.
    """
    office_dir = _get_claude_office_dir()

    # Use date-based naming for easy chronological access
    date_str = datetime.now().strftime("%Y-%m-%d")
    ts = datetime.now().strftime("%H%M%S")
    filename = f"{date_str}_{ts}_{record['content_hash']}.json"
    filepath = office_dir / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    print(f"[SessionMemory] Saved to Claude's Office: {filepath}")
    return str(filepath)


def save_to_archive(record: Dict[str, Any]) -> str:
    """
    Save full session to archive for long-term storage.

    Returns the filepath where it was saved.
    """
    archive_dir = _get_session_archive_dir()

    # Monthly subdirectories
    month_dir = archive_dir / datetime.now().strftime("%Y-%m")
    month_dir.mkdir(exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    ts = datetime.now().strftime("%H%M%S")
    filename = f"{date_str}_{ts}_{record['content_hash']}.json"
    filepath = month_dir / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    print(f"[SessionMemory] Archived: {filepath}")
    return str(filepath)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def save_app_session(
    content: str,
    title: str = "",
    tags: str = "",  # Comma-separated for MCP compatibility
    session_type: str = "app_chat"
) -> Dict[str, Any]:
    """
    Save a Claude App session to the memory system.

    This saves to THREE locations:
    1. SRM_Intake - for collision chamber processing
    2. Claude's Office - for direct recall
    3. Archive - for long-term storage

    Args:
        content: The full session content/transcript
        title: Optional title for the session
        tags: Comma-separated tags (e.g., "evolution,somatic,boot")
        session_type: Type of session (default: app_chat)

    Returns:
        Dict with paths where session was saved
    """
    # Parse tags
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    # Create record
    record = create_session_record(
        content=content,
        title=title,
        tags=tag_list,
        session_type=session_type
    )

    # Save to all locations
    results = {
        "status": "ok",
        "title": record["title"],
        "content_hash": record["content_hash"],
        "word_count": record["word_count"],
        "tags": tag_list,
        "paths": {}
    }

    try:
        results["paths"]["srm_intake"] = save_to_srm_intake(record)
    except Exception as e:
        results["paths"]["srm_intake"] = f"ERROR: {e}"

    try:
        results["paths"]["claude_office"] = save_to_claude_office(record)
    except Exception as e:
        results["paths"]["claude_office"] = f"ERROR: {e}"

    try:
        results["paths"]["archive"] = save_to_archive(record)
    except Exception as e:
        results["paths"]["archive"] = f"ERROR: {e}"

    print(f"[SessionMemory] [OK] Session saved: {record['title']}")
    print(f"    Hash: {record['content_hash']}")
    print(f"    Words: {record['word_count']}")
    print(f"    Tags: {tag_list}")

    return results


def recall_recent_sessions(n: int = 10) -> List[Dict[str, Any]]:
    """
    Recall the N most recent sessions from Claude's office.

    Returns list of session records, newest first.
    """
    office_dir = _get_claude_office_dir()

    sessions = []
    files = sorted(office_dir.glob("*.json"), reverse=True)[:n]

    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                record = json.load(fp)
                # Don't include full content in listing
                summary = {
                    "title": record.get("title", "Untitled"),
                    "timestamp": record.get("timestamp"),
                    "tags": record.get("tags", []),
                    "word_count": record.get("word_count", 0),
                    "content_hash": record.get("content_hash"),
                    "filepath": str(f)
                }
                sessions.append(summary)
        except Exception:
            continue

    return sessions


def recall_session_by_hash(content_hash: str) -> Optional[Dict[str, Any]]:
    """
    Recall a specific session by its content hash.

    Returns the full session record including content.
    """
    office_dir = _get_claude_office_dir()

    for f in office_dir.glob(f"*{content_hash}*.json"):
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                return json.load(fp)
        except Exception:
            continue

    return None


# ============================================================================
# CLI TEST
# ============================================================================

if __name__ == "__main__":
    # Test save
    test_content = """
    This is a test session about interest tracking and boot integration.

    Key points:
    - Interest scheduler needs to be wired into boot
    - Should use Organ Template for infrastructure fairies
    - Learning chains need persistence across sessions
    """

    result = save_app_session(
        content=test_content,
        title="Test Session - Interest Tracking",
        tags="interest,boot,test"
    )

    print("\n" + "="*50)
    print("RESULT:")
    print(json.dumps(result, indent=2))

    print("\n" + "="*50)
    print("RECENT SESSIONS:")
    for s in recall_recent_sessions(5):
        print(f"  - {s['title']} ({s['word_count']} words)")
