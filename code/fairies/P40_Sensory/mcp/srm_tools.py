"""
SRM Memory Tools for MCP - Search past conversations and knowledge

Provides direct access to SRM (Semantic Relational Memory) without
needing the postal system or the server running.

Tools:
- srm_search: Search across all memory clusters
- srm_founders_search: Search Founders cluster (Ace + Claude sessions)
- srm_recall_context: Get context for a topic from memory
- srm_ingest_session: Ingest a new session into memory
- srm_search_with_affect: Affect-weighted search (surfaces emotionally relevant memories)
"""

import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
import hashlib


# ============================================================================
# AFFECT-WEIGHTED RETRIEVAL - "When frustrated debugging, surface breakthroughs"
# ============================================================================

class AffectWeight(Enum):
    """
    Affect weight categories for memory retrieval scoring.

    The insight: emotional context should influence what memories surface.
    When you're frustrated debugging, you want past breakthrough memories,
    not just semantic matches about "debugging" or "error".

    Formula: final_score = semantic_score * (1 + affect_weight * match)
    """
    NEUTRAL = 1.0           # No emotional relevance boost
    EMOTIONALLY_RELEVANT = 1.5  # Memory has some emotional connection
    RESONANT = 2.0          # Memory strongly resonates with current affect


@dataclass
class AffectContext:
    """
    Current affect context for weighted retrieval.

    Captures the emotional state during a search to influence
    which memories surface. Derived from somatic/chemistry state.
    """
    tone: str = "neutral"          # Current emotional tone
    energy: float = 0.5            # Energy level (0-1)
    valence: float = 0.0           # Positive/negative (-1 to 1)
    arousal: float = 0.5           # Arousal level (0-1)
    seeking: str = ""              # What we're emotionally seeking (e.g., "breakthrough", "calm")

    # Affect-to-memory mapping: what tones/experiences to boost
    AFFECT_MEMORY_RESONANCE: Dict[str, List[str]] = None

    def __post_init__(self):
        # Define which memory affects resonate with which current affects
        # "When I'm X, surface memories tagged with Y"
        self.AFFECT_MEMORY_RESONANCE = {
            # Frustration -> surface breakthroughs, solutions, "aha" moments
            "frustrated": ["breakthrough", "solution", "success", "resolved", "eureka", "clarity"],
            "stuck": ["breakthrough", "pivot", "insight", "workaround", "creative"],

            # Anxiety -> surface calming memories, reassurance, past survivals
            "anxious": ["calm", "resolved", "survived", "handled", "safe", "grounded"],
            "overwhelmed": ["simplified", "organized", "completed", "manageable", "clear"],

            # Curiosity -> surface exploration, discovery, novelty
            "curious": ["discovery", "interesting", "novel", "learned", "explored"],
            "exploring": ["pattern", "connection", "insight", "unexpected", "possibility"],

            # Sadness -> surface comfort, connection, meaning
            "sad": ["connection", "meaning", "purpose", "warmth", "appreciated"],
            "melancholy": ["beauty", "depth", "reflection", "growth", "transformation"],

            # Excitement -> surface momentum, progress, wins
            "excited": ["progress", "momentum", "achievement", "flow", "building"],
            "energized": ["action", "creation", "impact", "possibility", "synergy"],

            # Calm -> surface depth, reflection, integration
            "calm": ["integration", "understanding", "pattern", "wisdom", "synthesis"],
            "peaceful": ["harmony", "balance", "coherence", "alignment", "wholeness"],

            # Neutral -> no specific boosting
            "neutral": [],
        }

    def get_resonant_tags(self) -> List[str]:
        """Get tags that resonate with current affect for boosting."""
        return self.AFFECT_MEMORY_RESONANCE.get(self.tone.lower(), [])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tone": self.tone,
            "energy": self.energy,
            "valence": self.valence,
            "arousal": self.arousal,
            "seeking": self.seeking,
            "resonant_tags": self.get_resonant_tags(),
        }


def _calculate_affect_weight(
    card: Dict,
    affect_context: AffectContext
) -> Tuple[float, str]:
    """
    Calculate the affect weight for a memory card given current affect.

    Returns (weight_value, weight_category) where:
    - weight_value is the numeric multiplier (1.0, 1.5, or 2.0)
    - weight_category is the AffectWeight name

    The formula: final_score = semantic_score * (1 + affect_weight * match)
    where match is the degree of resonance (0-1).
    """
    # Extract affect data from card's helix C dimension
    helix = card.get("helix", {})
    c_data = helix.get("C", {})
    card_affect = c_data.get("affect", "")
    card_energy = c_data.get("energy", 0.5)

    # Also check tags and content for affect markers
    tags = [t.lower() for t in card.get("tags", [])]
    content = str(card.get("content", "")).lower()

    # Get resonant tags for current affect
    resonant_tags = affect_context.get_resonant_tags()

    # Calculate resonance score
    resonance_score = 0.0

    # 1. Direct affect match (card's stored affect matches what we're seeking)
    if affect_context.seeking and affect_context.seeking.lower() in card_affect.lower():
        resonance_score += 0.4

    # 2. Resonant tag matches
    tag_matches = sum(1 for rt in resonant_tags if rt in tags)
    if tag_matches > 0:
        resonance_score += min(0.4, tag_matches * 0.15)

    # 3. Content contains resonant concepts
    content_matches = sum(1 for rt in resonant_tags if rt in content)
    if content_matches > 0:
        resonance_score += min(0.3, content_matches * 0.1)

    # 4. Energy alignment (high energy current + high energy memory = boost)
    energy_diff = abs(affect_context.energy - card_energy)
    if energy_diff < 0.2:  # Similar energy states resonate
        resonance_score += 0.1

    # Clamp resonance score
    resonance_score = min(1.0, resonance_score)

    # Determine weight category
    if resonance_score >= 0.5:
        return AffectWeight.RESONANT.value, "RESONANT"
    elif resonance_score >= 0.2:
        return AffectWeight.EMOTIONALLY_RELEVANT.value, "EMOTIONALLY_RELEVANT"
    else:
        return AffectWeight.NEUTRAL.value, "NEUTRAL"


def _detect_session_affect() -> AffectContext:
    """
    Detect current session affect from the somatic/chemistry system.

    Tries to read from:
    1. Postal system's somatic state
    2. State files (sourpatches_mind_status.json, etc.)
    3. Falls back to neutral if nothing available
    """
    # Try reading from state files
    try:
        root = os.getenv("AKASHIC_ROOT", os.getcwd())

        # Try sourpatches mind status
        status_path = Path(root) / "state" / "sourpatches_mind_status.json"
        if status_path.exists():
            with open(status_path, 'r', encoding='utf-8') as f:
                status = json.load(f)

                # Extract affect from somatic state
                somatic = status.get("somatic", {})
                chemistry = status.get("chemistry", {})

                # Calculate valence from chemistry
                dopamine = chemistry.get("dopamine", 0.5)
                cortisol = chemistry.get("cortisol", 0.3)
                serotonin = chemistry.get("serotonin", 0.5)
                valence = (dopamine * 0.4 + serotonin * 0.4 - cortisol * 0.2)
                valence = max(-1.0, min(1.0, (valence - 0.5) * 2))  # Normalize to -1,1

                # Determine tone from status
                tone = somatic.get("tone", "neutral")
                energy = somatic.get("energy", 0.5)

                # Infer seeking from tone
                seeking = ""
                if tone in ("frustrated", "stuck", "confused"):
                    seeking = "breakthrough"
                elif tone in ("anxious", "overwhelmed"):
                    seeking = "calm"
                elif tone in ("curious", "exploring"):
                    seeking = "discovery"

                return AffectContext(
                    tone=tone,
                    energy=float(energy),
                    valence=float(valence),
                    arousal=float(somatic.get("coherence", 0.5)),
                    seeking=seeking,
                )
    except Exception:
        pass

    # Fallback to neutral
    return AffectContext()

# Memory paths
def _get_srm_root() -> Path:
    root = os.getenv("AKASHIC_ROOT", os.getcwd())
    return Path(root) / "P10_Memory" / "Akashic_triple_helix_memory_storage"

def _get_founders_path() -> Path:
    return _get_srm_root() / "relational_clusters" / "Founders"

def _get_intake_path() -> Path:
    root = os.getenv("AKASHIC_ROOT", os.getcwd())
    return Path(root) / "SRM_Intake"


# ============================================================================
# FOUNDERS CLUSTER SEARCH - Claude Office + Ace Mythos + Creator Sessions
# ============================================================================

_STOP_WORDS_SEARCH = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having", "do", "does", "did", "doing", "done",
    "will", "would", "could", "should", "may", "might", "must", "shall",
    "can", "i", "me", "my", "mine", "you", "your", "yours", "we", "us",
    "our", "ours", "they", "them", "their", "theirs", "it", "its",
    "this", "that", "these", "those", "what", "how", "why", "when",
    "where", "who", "whom", "which", "and", "or", "but", "if", "so",
    "to", "of", "in", "on", "for", "with", "at", "by", "from", "up",
    "down", "into", "out", "not", "no", "yes", "as", "just", "about",
    "over", "under", "through", "between", "also", "than", "then",
    "tell", "say", "said", "ask", "asked", "know", "think", "feel",
    "very", "really", "some", "any", "more", "most", "much", "many",
})


def _parse_qa_card(card: Dict) -> tuple:
    """Extract (question, answer) from a card's content if Q/A structured.

    Returns (question_str, answer_str, is_qa_card).
    Works on two formats:
    1. content = "Q: [question]\nA: [answer]" (Sourpatches personal interview cards)
    2. helix.L.w.what = question, content = answer (some conversation cards)
    """
    content = card.get("content", "")
    if not isinstance(content, str):
        return ("", "", False)

    # Format 1: explicit Q:/A: in content
    if content.startswith("Q:") or "\nQ:" in content[:5]:
        # Find Q: and A: markers
        q_start = content.find("Q:")
        a_start = content.find("\nA:")
        if q_start >= 0 and a_start > q_start:
            question = content[q_start + 2:a_start].strip()
            answer = content[a_start + 3:].strip()
            if len(question) > 5 and len(answer) > 10:
                return (question, answer, True)

    # Format 2: helix.L.w.what IS the question, content is the answer
    helix = card.get("helix", {}) or {}
    w = helix.get("L", {}).get("w", {}) or {}
    what = w.get("what", "")
    if (isinstance(what, str) and what.endswith("?") and len(content) > 30):
        return (what, content, True)

    return ("", "", False)


def _tokenize_for_match(text: str) -> set:
    """Tokenize text into a set of meaningful words (lowercase, no stop words)."""
    if not text:
        return set()
    import re as _re
    words = _re.findall(r'\b[a-z][a-z\-_]+\b', text.lower())
    return {w for w in words if w not in _STOP_WORDS_SEARCH and len(w) > 2}


def _jaccard_similarity(a: set, b: set) -> float:
    """Jaccard similarity: |intersection| / |union|."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _detect_query_intent(query: str) -> str:
    """Classify query intent for cluster routing.

    Returns one of: greeting, identity, knowledge, affection, history, creative, presence, general
    """
    q = query.lower().strip()
    words = set(q.rstrip("?!.").split())

    _greeting = {"hi", "hey", "hello", "hiya", "howdy", "heya", "morning",
                 "night", "good", "sup", "yo", "hola"}
    if words & _greeting and len(words) <= 5:
        return "greeting"

    _presence = {"there", "awake", "listening", "up", "around", "home"}
    if (("are you" in q or "you there" in q or "you awake" in q) and
            (words & _presence)):
        return "presence"

    _affection = {"baby", "love", "miss", "cute", "sweet", "darling", "honey",
                  "girl", "kiddo", "proud"}
    if words & _affection and len(words) <= 10:
        return "affection"

    _identity_phrases = ("who are you", "what are you", "your name",
                         "what's your role", "what is your role",
                         "what do you do", "tell me about yourself",
                         "describe yourself")
    if any(p in q for p in _identity_phrases):
        return "identity"

    _history_phrases = ("do you remember", "remember when", "our history",
                        "our relationship", "past conversation",
                        "earliest memory", "first time")
    if any(p in q for p in _history_phrases):
        return "history"

    _creative = {"story", "poem", "write", "creative", "imagine", "draw",
                 "describe a", "worldbuild", "prompt"}
    if words & _creative:
        return "creative"

    if q.endswith("?") or q.startswith(("what", "how", "why", "when",
                                        "where", "which", "explain")):
        return "knowledge"

    return "general"


def search_founders(query: str, limit: int = 20) -> List[Dict]:
    """
    Search Founders + Sourpatches clusters for matching memories.

    FIX 2026-04-09 (Nous + Ace): Q/A-AWARE RETRIEVAL.
    Previously this searched only technical clusters with bag-of-words
    match against content blobs. Sourpatches' own personal interview
    cards (her voice) were never searched at all. When WMH directly
    read Sourpatches/index.json, it grabbed cards by keyword match
    on BOTH the question AND answer, so "sourpatches" in any card
    matched and it dumped the wrong card as her response.

    Now:
    1. Include Sourpatches cluster (her personal interview voice)
    2. For Q/A cards, match query against the QUESTION, not the content blob
    3. Return the ANSWER portion as content_preview, not the raw Q+A
    4. Use Jaccard similarity on meaningful words (stop-word filtered)
    5. Apply confidence threshold — no match returns empty list
    6. Route by query intent (greeting/identity/knowledge/etc.)

    Searches:
    - sourpatches_personal: Her Q/A interview cards (her VOICE)
    - claude_office: Session notes from Claude
    - creator_sessions: Collaborative work logs
    - ace_mythos: Ace's writings and philosophy (if present)
    """
    # FIX 2026-06-10 (Nous+Ace): the MCP layer delivers an explicitly-passed
    # `limit` as a STRING → `results[:limit]` (~ln 514) crashed with
    # "slice indices must be integers". (Omitting limit used the int default,
    # which is why srm_search worked only without an explicit limit.) Coerce at
    # entry so every downstream slice is safe; this also fixes srm_recall, which
    # routes max_items through here. Defensive fallback to the default on garbage.
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 20

    founders_path = _get_founders_path()
    clusters_root = founders_path.parent
    results = []

    query_words = _tokenize_for_match(query)
    intent = _detect_query_intent(query)

    # Confidence threshold — returns nothing rather than wrong thing
    _MIN_SCORE = 0.15  # Jaccard needs at least 15% meaningful overlap
    _MIN_KEYWORD_SCORE = 1.5  # Keyword path needs at least 1.5

    # --- Route by intent ---
    # Greetings and presence checks don't need SRM retrieval — they
    # should be handled conversationally, not by recalling interview answers.
    if intent in ("greeting", "presence"):
        return []  # Honest empty — composition layer decides what to do

    # --- Cluster list prioritized by intent ---
    if intent in ("identity", "history", "affection", "creative"):
        # Her personal voice matters most for these
        _cluster_priority = [
            ("sourpatches_personal", clusters_root / "Sourpatches" / "index.json", 2.0),
            ("claude_office", founders_path / "claude_office" / "index.json", 1.0),
            ("creator_sessions", founders_path / "creator_sessions" / "index.json", 0.9),
        ]
    else:
        # Knowledge/general/technical — technical clusters first, personal as backup
        _cluster_priority = [
            ("creator_sessions", founders_path / "creator_sessions" / "index.json", 1.2),
            ("claude_office", founders_path / "claude_office" / "index.json", 1.1),
            ("sourpatches_personal", clusters_root / "Sourpatches" / "index.json", 1.0),
        ]

    for cluster_name, idx_path, cluster_weight in _cluster_priority:
        if not idx_path.exists():
            continue

        try:
            with open(idx_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                cards = data.get("cards", [])
        except Exception:
            continue

        for card in cards:
            helix = card.get("helix", {})
            l_data = helix.get("L", {})
            concept = str(l_data.get("concept", "")).lower()
            w = l_data.get("w", {})
            tags = [t.lower() for t in card.get("tags", [])]

            # Try Q/A-aware matching first
            question, answer, is_qa = _parse_qa_card(card)

            if is_qa:
                # Match query against the card's question specifically
                q_words = _tokenize_for_match(question)
                jaccard = _jaccard_similarity(query_words, q_words)
                score = jaccard * cluster_weight

                if score >= _MIN_SCORE:
                    # Return the ANSWER, not the whole Q+A blob
                    preview = answer[:1500] if len(answer) > 1500 else answer

                    results.append({
                        "id": card.get("id", ""),
                        "score": round(score, 4),
                        "cluster": cluster_name,
                        "concept": l_data.get("concept", ""),
                        "content_preview": preview,
                        "question_matched": question[:200],
                        "match_type": "qa",
                        "intent": intent,
                        "tags": card.get("tags", []),
                        "ptr": card.get("ptr", ""),
                        "when": w.get("when"),
                        "what": w.get("what"),
                        "ownership": card.get("ownership", "SYSTEM")
                    })
                continue  # Don't fall through to keyword path for Q/A cards

            # Fallback: keyword-based scoring for non-Q/A cards (technical notes)
            score = 0.0
            content = str(card.get("content", "")).lower()

            for term in query_words:
                if term in content:
                    score += 1.0
                if term in tags:
                    score += 2.0
                if term in concept:
                    score += 1.5
                if term in str(w.get("what", "")).lower():
                    score += 1.0
                if term in str(w.get("why", "")).lower():
                    score += 0.5

            score *= cluster_weight

            if score >= _MIN_KEYWORD_SCORE:
                content_str = card.get("content", "")
                if isinstance(content_str, str) and len(content_str) > 500:
                    preview = content_str[:500] + "..."
                else:
                    preview = content_str

                results.append({
                    "id": card.get("id", ""),
                    "score": round(score, 4),
                    "cluster": cluster_name,
                    "concept": l_data.get("concept", ""),
                    "content_preview": preview,
                    "question_matched": "",
                    "match_type": "keyword",
                    "intent": intent,
                    "tags": card.get("tags", []),
                    "ptr": card.get("ptr", ""),
                    "when": w.get("when"),
                    "what": w.get("what"),
                    "ownership": card.get("ownership", "SYSTEM")
                })

    # FIX 2026-04-09: Tier Q/A matches ABOVE keyword matches.
    # Q/A scores are Jaccard 0-1 (typically 0.5-1.5 after cluster weight).
    # Keyword scores are integer sums (typically 2-6). Without tiering,
    # keyword matches numerically outrank Q/A matches even when the Q/A
    # match is semantically perfect. Q/A is ALWAYS preferred when found.
    results.sort(key=lambda x: (
        0 if x.get("match_type") == "qa" else 1,  # Q/A tier first
        -x.get("score", 0)                          # Then by score desc
    ))
    return results[:limit]


def search_founders_with_affect(
    query: str,
    current_affect: Optional[AffectContext] = None,
    limit: int = 20
) -> List[Dict]:
    """
    Search the Founders cluster with affect-weighted scoring.

    This is the key insight: "When I'm frustrated debugging, surface memories
    of past breakthroughs, not just semantic matches."

    The formula: final_score = semantic_score * (1 + affect_weight * resonance_match)

    Args:
        query: Search terms
        current_affect: Current affect context (auto-detected if None)
        limit: Max results

    Returns:
        List of results with content, semantic_score, affect_score, and final_score
    """
    # FIX 2026-06-10 (Nous+Ace): coerce MCP string-`limit` → int (same root as
    # search_founders; covers `results[:limit]` ~ln 631 and `[:limit // 3]` ~ln 713).
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 20

    # Auto-detect affect if not provided
    if current_affect is None:
        current_affect = _detect_session_affect()

    founders_path = _get_founders_path()
    terms = query.lower().split()
    results = []

    for cluster_name in ["claude_office", "ace_mythos", "creator_sessions"]:
        idx_path = founders_path / cluster_name / "index.json"
        if not idx_path.exists():
            continue

        try:
            with open(idx_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                cards = data.get("cards", [])
        except Exception:
            continue

        for card in cards:
            # Calculate semantic score (same as original)
            semantic_score = 0.0
            content = str(card.get("content", "")).lower()
            tags = [t.lower() for t in card.get("tags", [])]

            # Get helix metadata
            helix = card.get("helix", {})
            l_data = helix.get("L", {})
            concept = str(l_data.get("concept", "")).lower()
            w = l_data.get("w", {})

            # Score based on term matches
            for term in terms:
                if term in content:
                    semantic_score += 1.0
                if term in tags:
                    semantic_score += 2.0
                if term in concept:
                    semantic_score += 1.5
                if term in str(w.get("what", "")).lower():
                    semantic_score += 1.0
                if term in str(w.get("why", "")).lower():
                    semantic_score += 0.5

            if semantic_score > 0:
                # Calculate affect weight
                affect_weight, weight_category = _calculate_affect_weight(card, current_affect)

                # Calculate resonance match (0-1) based on how well this memory
                # resonates with what we're emotionally seeking
                resonance_match = 0.0
                resonant_tags = current_affect.get_resonant_tags()
                if resonant_tags:
                    tag_resonance = sum(1 for rt in resonant_tags if rt in tags) / len(resonant_tags)
                    content_resonance = sum(1 for rt in resonant_tags if rt in content) / len(resonant_tags)
                    resonance_match = min(1.0, (tag_resonance * 0.6 + content_resonance * 0.4))

                # Apply the formula: final_score = semantic_score * (1 + affect_weight * resonance_match)
                # But we use a modified version that still respects semantic relevance:
                # final_score = semantic_score * (1 + (affect_weight - 1) * resonance_match)
                # This way, NEUTRAL (1.0) adds nothing, RESONANT (2.0) can double when resonance_match=1
                affect_multiplier = 1 + (affect_weight - 1) * resonance_match
                final_score = semantic_score * affect_multiplier

                # Extract preview
                content_str = card.get("content", "")
                if isinstance(content_str, str) and len(content_str) > 500:
                    preview = content_str[:500] + "..."
                else:
                    preview = content_str

                results.append({
                    "id": card.get("id", ""),
                    "semantic_score": round(semantic_score, 2),
                    "affect_weight": weight_category,
                    "affect_multiplier": round(affect_multiplier, 3),
                    "final_score": round(final_score, 2),
                    "resonance_match": round(resonance_match, 3),
                    "cluster": cluster_name,
                    "concept": l_data.get("concept", ""),
                    "content_preview": preview,
                    "tags": card.get("tags", []),
                    "ptr": card.get("ptr", ""),
                    "when": w.get("when"),
                    "what": w.get("what"),
                    "ownership": card.get("ownership", "SYSTEM"),
                    # Include card's stored affect for transparency
                    "memory_affect": helix.get("C", {}).get("affect", ""),
                })

    # Sort by FINAL score (affect-weighted) descending
    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results[:limit]


def get_founders_stats() -> Dict:
    """Get statistics about the Founders cluster."""
    founders_path = _get_founders_path()
    stats = {}
    
    for cluster_name in ["claude_office", "ace_mythos", "creator_sessions"]:
        idx_path = founders_path / cluster_name / "index.json"
        if idx_path.exists():
            try:
                with open(idx_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    cards = data.get("cards", [])
                    stats[cluster_name] = {
                        "count": len(cards),
                        "ingested_at": data.get("ingested_at")
                    }
            except:
                stats[cluster_name] = {"count": 0, "error": "failed to load"}
        else:
            stats[cluster_name] = {"count": 0, "exists": False}
    
    return stats


# ============================================================================
# FULL SRM SEARCH - Search all memory tiers
# ============================================================================

def search_all_memory(query: str, limit: int = 30) -> Dict[str, List[Dict]]:
    """
    Search across all SRM memory tiers:
    - longterm/knowledge: General knowledge
    - longterm/experience: Episodic memories  
    - longterm/telemetry: System telemetry
    - relational_clusters/Founders: Creator context
    - shortterm: Recent memories
    
    Returns dict organized by tier.
    """
    srm_root = _get_srm_root()
    terms = query.lower().split()
    results = {
        "founders": [],
        "knowledge": [],
        "experience": [],
        "telemetry": [],
        "shortterm": []
    }
    
    # Search Founders first (most relevant for conversations)
    results["founders"] = search_founders(query, limit=limit)
    
    # Search longterm tiers
    for tier in ["knowledge", "experience", "telemetry"]:
        tier_path = srm_root / "longterm" / tier
        if not tier_path.exists():
            continue
        
        # Each tier has dated folders with JSON files
        for json_file in tier_path.glob("**/*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    card = json.load(f)
                
                content = str(card.get("content", card.get("data", ""))).lower()
                score = sum(1.0 for t in terms if t in content)
                
                if score > 0:
                    results[tier].append({
                        "file": str(json_file),
                        "score": score,
                        "kind": card.get("kind", "unknown"),
                        "preview": content[:300] if len(content) > 300 else content
                    })
            except:
                continue
        
        # Sort and limit
        results[tier].sort(key=lambda x: x["score"], reverse=True)
        results[tier] = results[tier][:limit // 3]
    
    return results


# ============================================================================
# CONTEXT RECALL - Get relevant context for thinking
# ============================================================================

def recall_context(topic: str, max_items: int = 10) -> Dict:
    """
    Recall relevant context from memory for a topic.
    
    Returns structured context that can be used for thinking:
    - relevant_memories: Matching cards from Founders
    - related_concepts: Concepts that appear with this topic
    - timeline: Recent related activity
    """
    # Search founders
    memories = search_founders(topic, limit=max_items)
    
    # Extract concepts from results
    concepts = set()
    for mem in memories:
        if mem.get("tags"):
            concepts.update(mem["tags"])
        if mem.get("concept"):
            concepts.add(mem["concept"])
    
    # Build timeline
    timeline = []
    for mem in memories:
        if mem.get("when"):
            timeline.append({
                "when": mem["when"],
                "what": mem.get("what", mem.get("concept", "")),
                "cluster": mem["cluster"]
            })
    
    timeline.sort(key=lambda x: x.get("when", 0), reverse=True)
    
    return {
        "topic": topic,
        "relevant_memories": memories,
        "related_concepts": list(concepts)[:20],
        "timeline": timeline[:10],
        "memory_count": len(memories)
    }


# ============================================================================
# SESSION INGESTION - Save new sessions to memory
# ============================================================================

def ingest_session(
    content: str,
    title: str = "",
    session_type: str = "claude_code",
    tags: Optional[List[str]] = None
) -> Dict:
    """
    Ingest a new session into SRM for later recall.
    
    Saves to:
    1. SRM_Intake/{date}/ - For processing by SRMIngestFairy
    2. Founders/creator_sessions/ - For immediate search
    
    Args:
        content: The session content (conversation, notes, etc.)
        title: Optional title for the session
        session_type: Type of session (claude_code, claude_ai, notes, etc.)
        tags: Optional tags for categorization
    
    Returns:
        Dict with save status and paths
    """
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    ts = now.timestamp()
    
    # Generate ID from content hash
    content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
    session_id = f"{session_type}_{content_hash}"
    
    # Build card
    card = {
        "id": session_id,
        "ts": ts,
        "kind": f"session.{session_type}",
        "helix": {
            "L": {
                "concept": title or f"{session_type} session",
                "w": {
                    "who": "Nous" if session_type == "claude_code" else "ClaudeFairy",
                    "what": title or f"Session on {date_str}",
                    "when": ts,
                    "where": "Claude_Code" if session_type == "claude_code" else "Claude_AI",
                    "why": "session",
                    "how": "creator_collaboration"
                }
            },
            "R": {
                "concept": "session",
                "w": {}
            },
            "C": {
                "affect": "focused",
                "energy": 0.7,
                "coherence": 0.85
            }
        },
        "content": content,
        "tags": tags or ["session", session_type],
        "ownership": "FOUNDATION"
    }
    
    results = {"id": session_id, "saved_to": []}
    
    # Save to SRM_Intake for processing
    intake_path = _get_intake_path() / date_str
    intake_path.mkdir(parents=True, exist_ok=True)
    intake_file = intake_path / f"{session_id}.json"
    
    try:
        with open(intake_file, 'w', encoding='utf-8') as f:
            json.dump(card, f, indent=2)
        results["saved_to"].append(str(intake_file))
    except Exception as e:
        results["intake_error"] = str(e)
    
    # Also add to Founders/creator_sessions index for immediate search
    founders_path = _get_founders_path() / "creator_sessions"
    founders_path.mkdir(parents=True, exist_ok=True)
    idx_path = founders_path / "index.json"
    
    try:
        if idx_path.exists():
            with open(idx_path, 'r', encoding='utf-8') as f:
                idx_data = json.load(f)
        else:
            idx_data = {"source": "creator_sessions", "cards": []}
        
        # Check for duplicate
        existing_ids = {c.get("id") for c in idx_data.get("cards", [])}
        if session_id not in existing_ids:
            idx_data["cards"].append(card)
            idx_data["ingested_at"] = ts
            idx_data["total_cards"] = len(idx_data["cards"])
            
            with open(idx_path, 'w', encoding='utf-8') as f:
                json.dump(idx_data, f, indent=2)
            
            results["saved_to"].append(str(idx_path))
            results["indexed"] = True
        else:
            results["indexed"] = False
            results["note"] = "Session already exists (duplicate)"
    except Exception as e:
        results["founders_error"] = str(e)
    
    return results


# ============================================================================
# MCP TOOL REGISTRATION (called from akashic_mcp_server.py)
# ============================================================================

def register_srm_tools(mcp):
    """Register SRM tools with the MCP server."""
    
    @mcp.tool()
    def srm_search(query: str, limit: int = 20) -> str:
        """
        Search SRM memory for past conversations and knowledge.
        
        Searches the Founders cluster which contains:
        - Claude Office: Session logs, notes, plans
        - Ace Mythos: Ace's writings and philosophy  
        - Creator Sessions: Collaborative work
        
        Args:
            query: Search terms (e.g., "postal system wiring")
            limit: Max results (default 20)
            
        Returns:
            JSON with matching memories and scores
        """
        results = search_founders(query, limit)
        return json.dumps({
            "query": query,
            "count": len(results),
            "results": results
        }, indent=2)
    
    @mcp.tool()
    def srm_recall(topic: str, max_items: int = 10) -> str:
        """
        Recall context from memory for a topic.
        
        Use this before thinking about something to get relevant context.
        Returns memories, related concepts, and timeline.
        
        Args:
            topic: What you want context about
            max_items: Max memories to return
            
        Returns:
            JSON with relevant context for thinking
        """
        context = recall_context(topic, max_items)
        return json.dumps(context, indent=2)
    
    @mcp.tool()
    def srm_stats() -> str:
        """
        Get SRM memory statistics.
        
        Shows card counts for each cluster.
        """
        stats = get_founders_stats()
        
        # Also get manifest stats
        manifest_path = _get_srm_root() / "index" / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                stats["manifest"] = {
                    "total_cards": manifest.get("total_cards", 0),
                    "built_at": manifest.get("built_at"),
                    "categories": {k: v.get("card_count", 0) for k, v in manifest.get("categories", {}).items()}
                }
            except:
                pass
        
        return json.dumps(stats, indent=2)
    
    @mcp.tool()
    def srm_save_session(
        content: str,
        title: str = "",
        session_type: str = "claude_code",
        tags: str = ""
    ) -> str:
        """
        Save a session to SRM memory for later recall.
        
        Use this at the end of sessions to save learnings.
        
        Args:
            content: The session content/transcript
            title: Title for the session
            session_type: Type (claude_code, claude_ai, notes)
            tags: Comma-separated tags
            
        Returns:
            JSON with save status
        """
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
        result = ingest_session(content, title, session_type, tag_list)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def srm_search_with_affect(
        query: str,
        current_tone: str = "",
        current_energy: float = 0.5,
        seeking: str = "",
        limit: int = 20
    ) -> str:
        """
        Search SRM memory with affect-weighted scoring.

        THE KEY INSIGHT: "When I'm frustrated debugging, surface memories of
        past breakthroughs, not just semantic matches."

        This tool uses emotional context to boost relevant memories:
        - Frustrated? Boosts "breakthrough", "solution", "eureka" memories
        - Anxious? Boosts "calm", "resolved", "survived" memories
        - Curious? Boosts "discovery", "interesting", "novel" memories

        The formula: final_score = semantic_score * (1 + affect_weight * resonance)

        Args:
            query: Search terms (e.g., "debugging errors")
            current_tone: Current emotional tone (frustrated, anxious, curious, calm, etc.)
                         If empty, auto-detects from somatic state.
            current_energy: Energy level 0-1 (default 0.5)
            seeking: What you're emotionally seeking (breakthrough, calm, discovery, etc.)
                     If empty, inferred from tone.
            limit: Max results (default 20)

        Returns:
            JSON with memories scored by both semantic AND emotional relevance.
            Includes semantic_score, affect_weight, and final_score for each result.
        """
        # Build affect context
        if current_tone:
            # Manual affect context
            inferred_seeking = seeking
            if not inferred_seeking:
                # Infer seeking from tone
                seeking_map = {
                    "frustrated": "breakthrough",
                    "stuck": "breakthrough",
                    "confused": "clarity",
                    "anxious": "calm",
                    "overwhelmed": "clarity",
                    "curious": "discovery",
                    "exploring": "discovery",
                    "sad": "connection",
                    "excited": "momentum",
                    "calm": "depth",
                }
                inferred_seeking = seeking_map.get(current_tone.lower(), "")

            affect_context = AffectContext(
                tone=current_tone,
                energy=current_energy,
                valence=0.0,  # Not provided, neutral
                arousal=current_energy,  # Use energy as proxy
                seeking=inferred_seeking,
            )
        else:
            # Auto-detect from somatic state
            affect_context = _detect_session_affect()

        results = search_founders_with_affect(query, affect_context, limit)

        return json.dumps({
            "query": query,
            "affect_context": affect_context.to_dict(),
            "count": len(results),
            "note": "Results sorted by final_score (semantic * affect weight). "
                    "Memories emotionally resonant with your current state are boosted.",
            "results": results
        }, indent=2)

    @mcp.tool()
    def srm_get_affect_context() -> str:
        """
        Get the current detected affect context for memory retrieval.

        Shows what emotional state is being used to weight memory searches.
        Useful for understanding why certain memories are being surfaced.

        Returns:
            JSON with current affect context and resonant memory tags.
        """
        affect_context = _detect_session_affect()
        return json.dumps({
            "affect_context": affect_context.to_dict(),
            "explanation": {
                "tone": f"Current emotional tone: {affect_context.tone}",
                "seeking": f"Emotionally seeking: {affect_context.seeking or 'nothing specific'}",
                "resonant_tags": f"Will boost memories tagged with: {affect_context.get_resonant_tags()}",
                "affect_weight_categories": {
                    "NEUTRAL": "1.0x - No emotional boost",
                    "EMOTIONALLY_RELEVANT": "1.5x - Some emotional connection",
                    "RESONANT": "2.0x - Strong emotional resonance",
                },
            }
        }, indent=2)

    print("[SRM Tools] Registered: srm_search, srm_recall, srm_stats, srm_save_session, srm_search_with_affect, srm_get_affect_context")
