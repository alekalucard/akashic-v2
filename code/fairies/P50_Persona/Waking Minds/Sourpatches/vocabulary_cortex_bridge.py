"""
Cortex Vocabulary Bridge — Dynamic Fragment Retrieval
=====================================================

Drop-in adapter that queries the Association Cortex for inner monologue
vocabulary fragments. Replaces static dict lookups with live cortex queries.

Features:
- Lazy cortex connection with 60s retry cooldown
- Dual query: feature matching + spreading activation
- 30s result cache (monologue fires every ~5s, same cache serves multiple)
- Novelty filtering via recency deque (matches MonologueGenerator pattern)
- Graceful degradation: returns empty list if cortex unavailable (caller falls back)

Usage:
    bridge = CortexVocabularyBridge()
    fragments = bridge.query_fragments("energy", "high", limit=10)
    if fragments:
        chosen = random.choice(fragments)
        bridge.mark_used(chosen)
"""

from __future__ import annotations
import random
import time
from collections import deque
from typing import Dict, List, Optional, Tuple


class CortexVocabularyBridge:
    """
    Retrieves inner monologue vocabulary from the Association Cortex.

    Falls back gracefully (returns empty list) when cortex is unavailable,
    allowing the caller to blend with static pools.

    Performance target: <50ms per query (typically <5ms with warm cache).
    """

    MINIMUM_RESULTS = 3    # Below this, caller should blend with static fallback
    CACHE_TTL = 30.0       # Cache query results for 30 seconds
    CORTEX_RETRY_COOLDOWN = 60.0  # Don't retry cortex connection more often than this

    def __init__(self):
        self._cortex = None
        self._cache: Dict[str, Tuple[float, List[str]]] = {}
        self._recent_used: deque = deque(maxlen=15)
        self._cortex_connect_attempted: float = 0.0
        self._query_count: int = 0
        self._cache_hits: int = 0

    def _get_cortex(self):
        """
        Lazy cortex connection with retry cooldown.

        The cortex may boot AFTER Sourpatches (P30 boots after P50),
        so we retry periodically rather than failing permanently.
        """
        if self._cortex is not None:
            # Verify it's still alive
            if hasattr(self._cortex, '_graph') and self._cortex._graph:
                return self._cortex
            else:
                self._cortex = None

        now = time.time()
        if now - self._cortex_connect_attempted < self.CORTEX_RETRY_COOLDOWN:
            return None

        self._cortex_connect_attempted = now
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            cortex = get_association_cortex()
            if cortex and hasattr(cortex, '_graph') and cortex._graph:
                self._cortex = cortex
                return cortex
        except ImportError:
            pass
        except Exception:
            pass

        return None

    def query_fragments(self, somatic_axis: str, intensity: str,
                        limit: int = 10) -> List[str]:
        """
        Query cortex for vocabulary fragments matching a somatic state.

        Args:
            somatic_axis: "energy", "stress", "curiosity", "warmth", etc.
            intensity: "high", "medium", "low"
            limit: max fragments to return

        Returns:
            List of fragment strings, novelty-ordered.
            Empty list if cortex unavailable (caller handles static fallback).
        """
        self._query_count += 1
        cache_key = f"{somatic_axis}_{intensity}"

        # Check cache
        if cache_key in self._cache:
            cached_ts, cached_results = self._cache[cache_key]
            if time.time() - cached_ts < self.CACHE_TTL and cached_results:
                self._cache_hits += 1
                return self._novelty_filter(cached_results, limit)

        cortex = self._get_cortex()
        if not cortex or not cortex._graph:
            return []

        fragments = []
        seen_fragments = set()

        # Strategy 1: Query by bodystate modality
        # This finds concepts explicitly tagged with the right somatic condition
        try:
            bodystate_query = [f"{somatic_axis}_{intensity}"]
            results = cortex.query_by_features("bodystate", bodystate_query, limit=limit * 3)
            self._extract_lex_fragments(cortex, results, fragments, seen_fragments)
        except Exception:
            pass

        # Strategy 2: Spreading activation from anchor concept
        # This finds conceptually related fragments (including learned ones)
        try:
            anchor_key = f"mv_{somatic_axis}_{intensity}"
            if cortex._graph.get_node(anchor_key):
                spread_results = cortex.query(anchor_key, limit=limit * 2, use_gpu=False, owner_filter="sourpatches")
                self._extract_lex_fragments(cortex, spread_results, fragments, seen_fragments)
        except Exception:
            pass

        # Cache results
        if fragments:
            self._cache[cache_key] = (time.time(), list(fragments))

        return self._novelty_filter(fragments, limit)

    def _extract_lex_fragments(self, cortex, results: List[Tuple[str, float]],
                                fragments: List[str], seen: set):
        """
        Extract lex features from query results as fragment strings.

        ConceptNode.features["lex"] contains tokenized words. We reconstruct
        the fragment by joining the lex words. For single-word fragments,
        use the word directly.
        """
        for concept_key, score in results:
            try:
                node = cortex._graph.get_node(concept_key)
                if not node:
                    continue

                lex_features = node.features.get("lex", [])
                if not lex_features:
                    continue

                # Check this is actually a monologue vocabulary concept
                context_features = node.features.get("context", [])
                is_monologue = any("preverbal" in str(c) or "monologue" in str(c)
                                   for c in context_features) if context_features else False

                if isinstance(lex_features, list) and lex_features:
                    # Reconstruct the fragment from lex tokens
                    fragment = " ".join(str(w) for w in lex_features if w)
                    if fragment and fragment not in seen and len(fragment) > 1:
                        # Prioritize confirmed monologue vocabulary, but include
                        # cortex concepts with lex data too (they may be learned)
                        if is_monologue:
                            fragments.insert(0, fragment)  # Prioritize
                        else:
                            fragments.append(fragment)
                        seen.add(fragment)
                elif isinstance(lex_features, str) and lex_features not in seen:
                    if len(lex_features) > 1:
                        fragments.append(lex_features)
                        seen.add(lex_features)
            except Exception:
                continue

    def _novelty_filter(self, fragments: List[str], limit: int = 10) -> List[str]:
        """
        Push recently-used fragments to the back of the list.

        This preserves the MonologueGenerator's recency avoidance behavior:
        prefer fragments not used in the last 15 emissions.
        """
        if not fragments:
            return []

        fresh = [f for f in fragments if f not in self._recent_used]
        stale = [f for f in fragments if f in self._recent_used]

        # Shuffle fresh fragments for variety within the novel set
        if len(fresh) > 3:
            random.shuffle(fresh)

        return (fresh + stale)[:limit]

    def mark_used(self, fragment: str):
        """Track that a fragment was used (for novelty avoidance)."""
        if fragment and fragment != "...":
            self._recent_used.append(fragment)

    def invalidate_cache(self):
        """Clear cache when significant state change occurs."""
        self._cache.clear()

    def get_stats(self) -> Dict:
        """Return bridge usage statistics."""
        return {
            "queries": self._query_count,
            "cache_hits": self._cache_hits,
            "cache_size": len(self._cache),
            "recent_used_count": len(self._recent_used),
            "cortex_connected": self._cortex is not None,
            "hit_rate": round(self._cache_hits / max(1, self._query_count), 2),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_bridge_instance: Optional[CortexVocabularyBridge] = None


def get_vocabulary_bridge() -> CortexVocabularyBridge:
    """Get or create the singleton vocabulary bridge."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = CortexVocabularyBridge()
    return _bridge_instance
