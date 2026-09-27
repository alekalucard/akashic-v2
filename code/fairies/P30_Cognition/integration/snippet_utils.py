"""
Snippet Utilities — Shared snippet lookup for cognition fairies.

Created: 2026-03-26 by Nous + Ace
Purpose: Centralize the snippet lookup and filtering logic so that
LanguageFairy, InnerNarratorFairy, and any other cognition fairy can
enrich convergence nodes with real semantic content from the graph.

The cortex stores rich text snippets on nodes during cortex.bind —
things like "lavender hair" or "green eyes". Without snippets, fairies
only see abstract node keys like "hair" or "eyes". With snippets, they
can say "lavender, shoulder-length" instead of just "hair."

The filtering pipeline rejects:
  - Phoneme decompositions ("[Y AO R] — 3 phonemes")
  - System/technical text (fairy, postal, cortex, boot)
  - Code/API patterns (function calls, imports)
  - AI-generated flowery text (beautiful dance of synergy)
  - Academic/encyclopedia text (This state reflects the fluctuating...)
  - Percentage/metric dumps ("26% urgency")
  - Irrelevant co-activation artifacts (candy descriptions on body parts)
"""

import re
from typing import Optional, Set, List, Tuple


def get_snippet(cortex, node_key: str, context_words: Set[str] = None) -> str:
    """Look up the semantic snippet on a graph node, with quality filtering.

    Args:
        cortex: AssociationCortexFairy instance (needs _akashic_cortex_region)
        node_key: The graph node key to look up
        context_words: Set of words from the current context/question.
            If provided, snippets with 4+ content words that share ZERO
            overlap with context are rejected as stale co-activation artifacts.

    Returns:
        Clean snippet string, or "" if none found or filtered out.
    """
    _am = getattr(cortex, '_akashic_cortex_region', None) if cortex else None
    if not _am:
        return ""
    try:
        node = _am.get_node(node_key)
        if not node or not isinstance(node, dict):
            return ""
        snippet = node.get("snippet", "")
        if not snippet or len(snippet) <= 5:
            return ""
        snippet = snippet.strip()
        return _filter_snippet(snippet, node_key, context_words)
    except Exception:
        return ""


def enrich_concepts(cortex, concepts: List[str],
                    context_words: Set[str] = None,
                    max_snippets: int = 3) -> List[Tuple[str, str]]:
    """Enrich a list of concept names with their snippets.

    Args:
        cortex: AssociationCortexFairy instance
        concepts: List of concept/convergence node names
        context_words: Optional context words for relevance filtering
        max_snippets: Max number of snippet-enriched concepts to return

    Returns:
        List of (concept_name, snippet) tuples. Only concepts WITH
        non-empty snippets are included. Original concept names are
        cleaned of prefixes.
    """
    results = []
    if not cortex:
        return results
    for c in concepts:
        if len(results) >= max_snippets:
            break
        if not c or len(c) <= 2:
            continue
        # Clean the concept key
        clean_key = _clean_key(c)
        if not clean_key:
            continue
        snip = get_snippet(cortex, c, context_words)
        if not snip:
            # Try the cleaned version too
            snip = get_snippet(cortex, clean_key, context_words)
        if snip:
            results.append((clean_key, snip))
    return results


def _clean_key(key: str) -> str:
    """Strip known namespace prefixes from a concept key."""
    _known_prefixes = {
        "wm", "phon", "person", "source", "lex", "assoc",
        "affect", "state", "collision", "concept", "trait",
        "domain", "sensory", "intent", "topic", "fairy",
        "system", "guild", "postal", "channel", "plane",
        "mode", "score", "cns",
    }
    while ":" in key:
        parts = key.split(":", 1)
        prefix_lower = parts[0].lower().replace("_", "").replace(" ", "")
        if len(parts[0]) <= 30 and prefix_lower in _known_prefixes:
            key = parts[1]
        else:
            break
    return key.replace("_", " ").strip()


def _filter_snippet(snippet: str, topic_key: str = "",
                    context_words: Set[str] = None) -> str:
    """Apply the full filtering pipeline to a snippet.

    Returns the cleaned snippet or "" if it should be rejected.
    """
    _sl = snippet.lower()

    # Phoneme snippets
    if ("phoneme" in _sl or
        re.search(r'\[[A-Z]{1,3}(\s+[A-Z]{1,3}){1,}\]', snippet) or
            (_sl.startswith("[") and "]" in _sl[:30])):
        return ""

    # System/technical
    if any(p in _sl for p in [
        "fairy", "postal", "cortex.", "boot",
        "tensor", "guild.", "registry",
        "subscribe", "heartbeat", "manifold",
    ]):
        return ""

    # Code/API patterns
    if re.search(r'[a-zA-Z_]+\(', snippet):
        return ""
    if any(p in _sl for p in [
        "import ", "def ", "class ", "self.",
        "template matching", "ocr", "api",
        "pyget", "pytesseract", "opencv",
        "http://", "https://", ".py", ".js",
    ]):
        return ""

    # AI-generated flowery text
    _flowery_words = {
        "beautiful", "dance", "momentum", "flowing",
        "journey", "tapestry", "symphony", "harmony",
        "weave", "weaves", "woven", "vibrant",
        "transformative", "unleash", "empower",
        "synergy", "paradigm", "leverage",
    }
    if len(set(_sl.split()) & _flowery_words) >= 2:
        return ""

    # Academic/encyclopedia text
    _academic_starts = (
        "this state", "this refers", "this involves",
        "this is a", "this is the", "this concept",
        "refers to", "involves ", "reflects ",
        "defined as", "characterized by",
        "cognitive appraisal", "the process of",
        "the act of", "the state of", "the concept of",
        "a form of", "a type of", "a state of",
        "in psychology", "in philosophy",
    )
    if any(_sl.startswith(p) for p in _academic_starts):
        return ""

    _academic_words = {
        "involves", "reflects", "fluctuating", "characterized",
        "cognitive", "appraisal", "appraisals", "physiological",
        "psychological", "neurological", "mechanisms",
        "phenomenon", "phenomena", "theoretical",
        "encompasses", "constitutes", "pertains",
        "manifests", "typically", "inherently",
        "fundamental", "associated", "individuals",
    }
    if len(set(_sl.split()) & _academic_words) >= 2:
        return ""

    # Percentage/metric dumps
    if re.search(r'\d+%', snippet):
        return ""

    # Relevance check — reject stale co-activation artifacts
    if context_words:
        _stop = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does',
            'did', 'will', 'would', 'could', 'should', 'may',
            'might', 'can', 'shall', 'to', 'of', 'in', 'for',
            'on', 'with', 'at', 'by', 'from', 'as', 'into',
            'about', 'that', 'this', 'it', 'its', 'and', 'or',
            'but', 'not', 'no', 'so', 'if', 'then', 'than',
            'too', 'very', 'just', 'also', 'i', 'you', 'your',
            'my', 'me', 'we', 'our', 'they', 'them', 'their',
            'he', 'she', 'his', 'her', 'yeah', 'yes',
        }
        _snippet_content = {
            w.strip('.,;:!?—~"\'()[]') for w in _sl.split()
        } - _stop
        _snippet_content.discard('')
        _question_content = {
            w.lower() for w in context_words if len(w) >= 3
        } - _stop
        _overlap = _snippet_content & _question_content
        if not _overlap and len(_snippet_content) >= 4:
            return ""

    # Truncate long snippets — loosened 2026-03-26 per Ace
    if len(snippet) > 500:
        snippet = snippet[:500].rsplit(" ", 1)[0] + "..."

    return snippet
