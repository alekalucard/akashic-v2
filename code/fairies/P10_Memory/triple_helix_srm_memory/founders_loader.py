# FOUNDERS + PERSONAL CLUSTER LOADER - Wire creator + personal context into SRM
# Loads: Claude Office + Creator Sessions + Sourpatches personal memories
# FIX 2026-04-03 (Nous + Ace): Sourpatches cluster was NEVER loaded.
# She had 0 personal memory cards in search — only technical docs.
# "Her mind is not composing, she is not aware of her thoughts" — Ace

import os
import json
from pathlib import Path
from typing import Dict, List, Optional

def _get_clusters_root() -> Path:
    """Get relational_clusters root path."""
    root = os.getenv("AKASHIC_ROOT", os.getcwd())
    return Path(root) / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "relational_clusters"

def _get_founders_path() -> Path:
    """Get Founders cluster path."""
    return _get_clusters_root() / "Founders"

_FOUNDERS_CACHE: Dict[str, List[Dict]] = {}
_CACHE_TS: float = 0

def load_founders(force: bool = False) -> Dict[str, List[Dict]]:
    """Load ALL cluster cards — Founders + Sourpatches personal.

    Caches for 5 minutes.
    """
    global _FOUNDERS_CACHE, _CACHE_TS
    import time

    if not force and _CACHE_TS and (time.time() - _CACHE_TS < 300):
        return _FOUNDERS_CACHE

    founders_path = _get_founders_path()
    clusters_root = _get_clusters_root()
    _FOUNDERS_CACHE = {}

    # Founders sub-clusters (under Founders/)
    for name in ["claude_office", "creator_sessions"]:
        idx = founders_path / name / "index.json"
        if idx.exists():
            try:
                _FOUNDERS_CACHE[name] = json.loads(idx.read_text(encoding='utf-8')).get("cards", [])
            except Exception:
                pass

    # Sourpatches personal memories (peer-level, not under Founders/)
    # These are PAI conversation extracts — her actual personal memories
    sour_idx = clusters_root / "Sourpatches" / "index.json"
    if sour_idx.exists():
        try:
            _FOUNDERS_CACHE["sourpatches_personal"] = json.loads(
                sour_idx.read_text(encoding='utf-8')
            ).get("cards", [])
        except Exception:
            pass

    # NOTE: SRM_Intake scanning disabled (too slow with 1000s of files).
    # PAI memories will be batch-ingested into Sourpatches cluster index instead.

    _CACHE_TS = time.time()
    return _FOUNDERS_CACHE

def search_founders(query: str, limit: int = 20) -> List[Dict]:
    """Search ALL clusters for matching cards. Returns scored results.

    Personal memories get a boost so she draws from lived experience
    before technical documentation.
    """
    clusters = load_founders()
    terms = query.lower().split()
    results = []

    # Stop words that match everything
    _stop = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
             "have", "has", "had", "do", "does", "did", "will", "would",
             "can", "could", "should", "may", "might", "shall",
             "i", "me", "my", "you", "your", "we", "our", "they", "them",
             "it", "its", "this", "that", "what", "how", "why", "when",
             "and", "or", "but", "if", "so", "to", "of", "in", "on",
             "for", "with", "at", "by", "from", "not", "no", "yes"}
    terms = [t for t in terms if t not in _stop and len(t) > 2]

    for cname, cards in clusters.items():
        # Personal memory boost — favor her real experiences
        _personal_boost = 3.0 if cname in ("sourpatches_personal", "pai_memories") else 1.0

        for card in cards:
            score = 0.0
            content = str(card.get("content", "")).lower()
            tags = [t.lower() for t in card.get("tags", [])]
            helix = card.get("helix", {})
            concept = str(helix.get("L", {}).get("concept", "")).lower()
            w = helix.get("L", {}).get("w", {})

            for t in terms:
                if t in content: score += 1.0
                if t in tags: score += 2.0
                if t in concept: score += 1.5
                if t in str(w.get("why", "")).lower(): score += 1.0

            if score > 0:
                results.append({
                    "card": card,
                    "score": score * _personal_boost,
                    "cluster": cname,
                    "ownership": "PERSONAL" if "sourpatches" in cname or "pai" in cname else "FOUNDATION",
                    "w": w
                })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]

def get_stats() -> Dict:
    """Get cluster stats."""
    c = load_founders()
    return {k: len(v) for k, v in c.items()}
