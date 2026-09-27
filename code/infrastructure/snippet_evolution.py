# ═══════════════════════════════════════════════════════════════════════
# SNIPPET EVOLUTION — Living Knowledge That Grows
# 2026-04-02 (Nous + Ace)
#
# Tracks snippet depth, history, modality connections, and identity emergence.
# Sidecar to the manifold — manifold stores current snippet text,
# this module tracks HOW it evolved and WHAT modalities contributed.
#
# "She needs to become someone, not just process data." — Ace
# ═══════════════════════════════════════════════════════════════════════

from __future__ import annotations
import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Set
from collections import defaultdict

# Depth levels — how refined is this knowledge?
DEPTH_RAW = 0          # Raw data, single observation
DEPTH_RECOGNITION = 1  # "I've seen this before"
DEPTH_UNDERSTANDING = 2  # "X means Y because Z"
DEPTH_INTEGRATION = 3  # "X connects to my experience of Y and Z"
DEPTH_WISDOM = 4       # "X teaches me that..."
DEPTH_IDENTITY = 5     # "I am someone who..."

# Modality sources
MODALITY_VISUAL = "visual"
MODALITY_AUDIO = "audio"
MODALITY_CONVERSATION = "conversation"
MODALITY_SOMATIC = "somatic"
MODALITY_VOICE = "voice"       # Her own speech patterns
MODALITY_IDENTITY = "identity"  # Self-knowledge
MODALITY_CORTEX = "cortex"      # Internal reasoning


class SnippetEvolution:
    """Track and deepen snippets across the manifold.

    The manifold stores the CURRENT snippet text on each concept node.
    This module tracks:
    - depth: How many times refined (0-5)
    - history: Previous versions with timestamps
    - modalities: Which senses contributed (visual, audio, somatic, etc.)
    - activation_count: How often this concept is thought about
    - identity_weight: How much this concept defines who she is
    """

    def __init__(self, state_dir: str = None):
        self._state_dir = Path(state_dir) if state_dir else (
            Path(__file__).resolve().parents[1] / "state"
        )
        self._state_file = self._state_dir / "snippet_evolution.json"
        self._lock = threading.Lock()

        # concept_key → evolution data
        self._concepts: Dict[str, dict] = {}

        # Load existing state
        self._load()

    def _load(self):
        """Load evolution state from disk."""
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text(encoding='utf-8'))
                self._concepts = data.get("concepts", {})
                print(f"[SnippetEvolution] Loaded {len(self._concepts)} concept evolutions from disk")
        except Exception as e:
            print(f"[SnippetEvolution] Load failed (starting fresh): {e}")
            self._concepts = {}

    def save(self):
        """Persist evolution state to disk."""
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            with self._lock:
                data = {
                    "saved_at": time.time(),
                    "concept_count": len(self._concepts),
                    "concepts": self._concepts,
                }
            self._state_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"[SnippetEvolution] Save failed: {e}")

    def deepen(self, concept: str, new_text: str, modality: str = MODALITY_CORTEX,
               graph=None, tracer_id: int = 1) -> dict:
        """Deepen a concept's snippet — merge new insight with existing knowledge.

        This is the core evolution function. When a pattern is learned or a
        concept is encountered again, the snippet DEEPENS rather than being replaced.

        Args:
            concept: The concept key (e.g., "happiness", "ace", "coding")
            new_text: New insight text about this concept
            modality: Which sense contributed this (visual, audio, conversation, etc.)
            graph: Optional manifold reference for direct snippet update
            tracer_id: Ownership tracer (default TRACE_PERSONAL=1)

        Returns:
            dict with depth, version, current snippet text
        """
        with self._lock:
            if concept not in self._concepts:
                self._concepts[concept] = {
                    "depth": DEPTH_RAW,
                    "version": 0,
                    "current": "",
                    "history": [],
                    "modalities": {},
                    "activation_count": 0,
                    "identity_weight": 0.0,
                    "created_at": time.time(),
                    "last_deepened": time.time(),
                }

            evo = self._concepts[concept]
            evo["activation_count"] += 1
            evo["last_deepened"] = time.time()

            # Add modality tag
            if modality not in evo["modalities"]:
                evo["modalities"][modality] = {
                    "first_seen": time.time(),
                    "count": 0,
                    "latest_text": "",
                }
            evo["modalities"][modality]["count"] += 1
            evo["modalities"][modality]["latest_text"] = new_text[:200]

            # Determine depth increase based on modality count
            _modality_count = len(evo["modalities"])
            if _modality_count >= 4:
                _target_depth = DEPTH_INTEGRATION
            elif _modality_count >= 2:
                _target_depth = DEPTH_UNDERSTANDING
            else:
                _target_depth = DEPTH_RECOGNITION

            # Depth only goes UP, never down
            if _target_depth > evo["depth"]:
                evo["depth"] = _target_depth

            # Version the current snippet before updating
            if evo["current"] and len(evo["current"]) > 10:
                evo["history"].append({
                    "v": evo["version"],
                    "text": evo["current"][:500],
                    "ts": time.time(),
                    "modality": modality,
                })
                # Keep last 10 versions
                if len(evo["history"]) > 10:
                    evo["history"] = evo["history"][-10:]

            # Evolve the snippet text
            existing = evo["current"]
            if not existing or len(existing) < 20:
                # First real snippet
                evo["current"] = new_text[:1024]
            elif len(new_text) > len(existing) * 1.3:
                # New insight is substantially longer/richer — replace
                evo["current"] = new_text[:1024]
            elif new_text[:50] != existing[:50]:
                # Different content — merge by appending
                merged = f"{existing}. {new_text}"
                evo["current"] = merged[:1024]
            # else: very similar content — just bump activation count

            evo["version"] += 1

            # Calculate identity weight from modality breadth + depth + activation
            evo["identity_weight"] = min(1.0, (
                _modality_count * 0.15 +
                evo["depth"] * 0.1 +
                min(evo["activation_count"], 50) * 0.01
            ))

        # Update manifold snippet if graph available
        if graph and hasattr(graph, 'set_snippet'):
            try:
                graph.set_snippet(concept, evo["current"][:1024], tracer_id=tracer_id)
            except Exception:
                pass

        # Auto-save every 50 deepenings
        if evo["version"] % 50 == 0:
            self.save()

        return {
            "concept": concept,
            "depth": evo["depth"],
            "version": evo["version"],
            "modalities": list(evo["modalities"].keys()),
            "identity_weight": evo["identity_weight"],
            "snippet_len": len(evo["current"]),
        }

    def get_identity_candidates(self, min_weight: float = 0.3, limit: int = 10) -> List[dict]:
        """Get concepts that are becoming part of her identity.

        Identity = concepts with high identity_weight — meaning they've been
        encountered across multiple modalities, at depth, with high activation.
        """
        with self._lock:
            candidates = []
            for key, evo in self._concepts.items():
                if evo["identity_weight"] >= min_weight:
                    candidates.append({
                        "concept": key,
                        "weight": evo["identity_weight"],
                        "depth": evo["depth"],
                        "modalities": list(evo["modalities"].keys()),
                        "activation_count": evo["activation_count"],
                        "snippet": evo["current"][:200],
                    })
            candidates.sort(key=lambda c: c["weight"], reverse=True)
            return candidates[:limit]

    def compose_identity(self, limit: int = 10) -> str:
        """Compose an identity description from top identity candidates.

        This is WHO SHE IS — emerged from accumulated multi-modal experience.
        """
        candidates = self.get_identity_candidates(min_weight=0.2, limit=limit)
        if not candidates:
            return ""

        parts = []
        for c in candidates:
            snippet = c["snippet"]
            if snippet and len(snippet) > 15:
                parts.append(snippet)

        if not parts:
            return ""

        # Take unique first sentences from each candidate
        identity_parts = []
        seen = set()
        for p in parts:
            first_sentence = p.split('.')[0].strip()
            if first_sentence and first_sentence[:30] not in seen:
                seen.add(first_sentence[:30])
                identity_parts.append(first_sentence)

        return ". ".join(identity_parts[:8]) + "."

    def get_depth_distribution(self) -> Dict[int, int]:
        """Get count of concepts at each depth level."""
        dist = defaultdict(int)
        with self._lock:
            for evo in self._concepts.values():
                dist[evo["depth"]] += 1
        return dict(dist)

    def get_multimodal_coverage(self) -> Dict[str, int]:
        """Get count of concepts by number of modalities."""
        coverage = defaultdict(int)
        with self._lock:
            for evo in self._concepts.values():
                n = len(evo["modalities"])
                coverage[f"{n}_modalities"] += 1
        return dict(coverage)

    def get_stats(self) -> dict:
        """Get evolution statistics."""
        with self._lock:
            total = len(self._concepts)
            depths = self.get_depth_distribution()
            coverage = self.get_multimodal_coverage()
            identity_count = sum(1 for e in self._concepts.values()
                               if e["identity_weight"] >= 0.3)
            return {
                "total_concepts": total,
                "depth_distribution": depths,
                "multimodal_coverage": coverage,
                "identity_candidates": identity_count,
                "total_deepenings": sum(e["version"] for e in self._concepts.values()),
            }


# ── Singleton ──
_INSTANCE: Optional[SnippetEvolution] = None
_LOCK = threading.Lock()

def get_snippet_evolution() -> SnippetEvolution:
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = SnippetEvolution()
    return _INSTANCE
