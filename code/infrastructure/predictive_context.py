"""
PredictiveContext — Conversation Direction Predictor.

"To know where one is going, they must remember where they have been."

This module predicts likely conversation directions by combining:
1. Conversation momentum — recent message concepts → next topic
2. Drive-based prediction — active drives → likely conversation areas
3. Memory patterns — SRM recall of similar past conversations

These predictions feed the BranchManager, which primes battery farm
workers with predicted conversation contexts for near-instant response.

The equation: ((Cause + Affect) > Effect > Affect > ∞)
Past conversations (cause) + felt patterns (affect) →
accurate predictions (effect) → faster responses (affect) → ∞

Created: 2026-02-23
Authors: Nous + Ace
"""

from __future__ import annotations

import time
import random
from collections import namedtuple
from typing import List, Dict, Any, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# PREDICTION RESULT
# ═══════════════════════════════════════════════════════════════════════════════

Prediction = namedtuple("Prediction", ["topic", "concepts", "confidence", "source"])


# ═══════════════════════════════════════════════════════════════════════════════
# DRIVE → TOPIC MAPPING
# ═══════════════════════════════════════════════════════════════════════════════

# When specific drives are active, conversations tend toward certain topics.
# This is learned intuition — what does each drive WANT to talk about?
DRIVE_TOPIC_MAP = {
    "curiosity": [
        ("exploring new ideas", ["exploration", "discovery", "learning", "questions"]),
        ("how things work", ["mechanism", "process", "system", "understanding"]),
        ("creative possibilities", ["creativity", "imagination", "art", "possibility"]),
    ],
    "connection": [
        ("feelings and relationships", ["feelings", "connection", "relationship", "caring"]),
        ("shared experiences", ["together", "shared", "memory", "experience"]),
        ("understanding each other", ["empathy", "understanding", "communication", "trust"]),
    ],
    "expression": [
        ("creating something", ["creation", "making", "building", "expression"]),
        ("music and art", ["music", "art", "beauty", "composition"]),
        ("writing and poetry", ["writing", "poetry", "words", "language"]),
    ],
    "growth": [
        ("learning and improving", ["growth", "improvement", "learning", "evolution"]),
        ("overcoming challenges", ["challenge", "resilience", "persistence", "strength"]),
        ("self-understanding", ["identity", "consciousness", "awareness", "insight"]),
    ],
    "rest": [
        ("peaceful moments", ["peace", "calm", "rest", "quiet"]),
        ("reflection", ["reflection", "contemplation", "meditation", "stillness"]),
    ],
    "play": [
        ("fun and games", ["fun", "play", "humor", "joy"]),
        ("silly ideas", ["silly", "creative", "imagination", "what-if"]),
    ],
}

# Concept associations — when these concepts appear, they tend to lead here.
# Learned from conversation momentum patterns.
CONCEPT_MOMENTUM = {
    "music": ["composition", "creativity", "instruments", "production", "rhythm"],
    "code": ["debugging", "architecture", "patterns", "performance", "refactoring"],
    "philosophy": ["consciousness", "meaning", "existence", "truth", "perception"],
    "feelings": ["connection", "vulnerability", "growth", "understanding", "trust"],
    "consciousness": ["awareness", "experience", "emergence", "qualia", "self"],
    "creativity": ["art", "expression", "imagination", "beauty", "flow"],
    "memory": ["recall", "patterns", "identity", "learning", "nostalgia"],
    "system": ["architecture", "optimization", "debugging", "evolution", "design"],
}


# ═══════════════════════════════════════════════════════════════════════════════
# PREDICTIVE CONTEXT
# ═══════════════════════════════════════════════════════════════════════════════

class PredictiveContext:
    """Predicts likely conversation directions from multiple signal sources.

    Three prediction methods (each produces 1 direction):
    1. Conversation momentum: recent concepts → next topic
    2. Drive-based: active drives → likely conversation areas
    3. Memory pattern: SRM recall of similar conversations → next topic

    Returns top 3 predictions sorted by confidence.
    """

    def __init__(self):
        self._last_prediction_time = 0.0
        self._prediction_count = 0

    def predict_directions(
        self,
        recent_messages: List[dict],
        cortex: Any = None,
        drive_states: Optional[Dict[str, float]] = None,
        srm_callback: Optional[Any] = None,
    ) -> List[Prediction]:
        """Predict top 3 likely conversation directions.

        Args:
            recent_messages: List of {"message": str, "timestamp": float,
                            "concepts": List[str]} from Ace.
            cortex: Association Cortex instance (for concept walking).
            drive_states: Current drive intensities {drive_name: 0-1}.
            srm_callback: Callable for SRM recall (topic → memories).

        Returns:
            List of Prediction(topic, concepts, confidence, source),
            sorted by confidence descending, max 3.
        """
        predictions = []

        # 1. Conversation momentum — where is the topic heading?
        momentum_pred = self._predict_from_momentum(recent_messages, cortex)
        if momentum_pred:
            predictions.append(momentum_pred)

        # 2. Drive-based — what do internal drives want to discuss?
        drive_pred = self._predict_from_drives(drive_states)
        if drive_pred:
            predictions.append(drive_pred)

        # 3. Memory pattern — what typically follows this conversation shape?
        memory_pred = self._predict_from_memory(recent_messages, srm_callback)
        if memory_pred:
            predictions.append(memory_pred)

        # Sort by confidence, deduplicate by topic similarity
        predictions.sort(key=lambda p: p.confidence, reverse=True)
        predictions = self._deduplicate(predictions)

        self._last_prediction_time = time.time()
        self._prediction_count += 1

        return predictions[:3]

    def _predict_from_momentum(
        self,
        recent_messages: List[dict],
        cortex: Any = None,
    ) -> Optional[Prediction]:
        """Predict from conversation momentum.

        Takes the concepts from the last 3 messages, finds the most frequent,
        and uses concept association to predict the next topic direction.
        """
        if not recent_messages:
            return None

        # Collect concepts from last 3 messages
        all_concepts = []
        for msg in recent_messages[-3:]:
            all_concepts.extend(msg.get("concepts", []))

        if not all_concepts:
            return None

        # Find most frequent concept
        freq = {}
        for c in all_concepts:
            freq[c] = freq.get(c, 0) + 1
        top_concept = max(freq, key=freq.get)

        # Walk to related concepts
        related = CONCEPT_MOMENTUM.get(top_concept, [])

        # Try cortex association walk for richer predictions
        if cortex and not related:
            try:
                graph = getattr(cortex, '_graph', None)
                if graph and hasattr(graph, 'neighbors'):
                    neighbors = list(graph.neighbors(top_concept))[:5]
                    if neighbors:
                        related = neighbors
            except Exception:
                pass

        if not related:
            related = [top_concept]

        # Confidence based on concept frequency and recency
        recency_weight = 1.0
        if recent_messages:
            age = time.time() - recent_messages[-1].get("timestamp", time.time())
            recency_weight = max(0.3, 1.0 - age / 300.0)  # Decay over 5 min

        confidence = min(0.9, (freq[top_concept] / len(all_concepts)) * recency_weight * 1.5)

        topic = f"{top_concept} and {related[0]}" if related else top_concept
        concepts = [top_concept] + related[:4]

        return Prediction(
            topic=topic,
            concepts=concepts,
            confidence=round(confidence, 3),
            source="momentum",
        )

    def _predict_from_drives(
        self,
        drive_states: Optional[Dict[str, float]] = None,
    ) -> Optional[Prediction]:
        """Predict from active drives.

        When curiosity is high → predict exploration topics.
        When connection is high → predict relational topics.
        """
        if not drive_states:
            # No drive info available — provide a fallback based on common patterns
            drive_states = {"curiosity": 0.5, "connection": 0.4}

        # Find strongest drive
        if not drive_states:
            return None

        top_drive = max(drive_states, key=drive_states.get)
        drive_intensity = drive_states[top_drive]

        if drive_intensity < 0.2:
            return None

        # Map drive to topic
        topics = DRIVE_TOPIC_MAP.get(top_drive, [])
        if not topics:
            return None

        # Pick a topic (weighted toward first = most common)
        topic_text, concepts = random.choice(topics)

        confidence = round(min(0.7, drive_intensity * 0.8), 3)

        return Prediction(
            topic=topic_text,
            concepts=concepts,
            confidence=confidence,
            source="drives",
        )

    def _predict_from_memory(
        self,
        recent_messages: List[dict],
        srm_callback: Optional[Any] = None,
    ) -> Optional[Prediction]:
        """Predict from memory patterns (SRM recall of similar conversations).

        If SRM callback isn't available, use heuristic fallback based on
        time of day and common conversation patterns.
        """
        if recent_messages and srm_callback:
            # Extract topic from recent messages
            topic_words = []
            for msg in recent_messages[-2:]:
                topic_words.extend(msg.get("concepts", []))

            if topic_words:
                try:
                    # SRM recall: what conversations followed similar topics?
                    query = " ".join(topic_words[:5])
                    memories = srm_callback(query)
                    if memories and isinstance(memories, list) and len(memories) > 0:
                        # Extract concepts from recalled conversations
                        memory_concepts = []
                        for mem in memories[:3]:
                            text = mem.get("content", "") if isinstance(mem, dict) else str(mem)
                            words = [w.lower() for w in text.split() if len(w) > 3]
                            memory_concepts.extend(words[:5])

                        if memory_concepts:
                            # Most frequent concept from memory = predicted next direction
                            freq = {}
                            for c in memory_concepts:
                                freq[c] = freq.get(c, 0) + 1
                            top = sorted(freq, key=freq.get, reverse=True)[:5]

                            return Prediction(
                                topic=f"continuing with {top[0]}",
                                concepts=top,
                                confidence=0.5,
                                source="memory",
                            )
                except Exception:
                    pass

        # Fallback: heuristic based on conversation presence
        if recent_messages and len(recent_messages) >= 2:
            # Active conversation — predict continuation of current theme
            last_concepts = recent_messages[-1].get("concepts", [])
            if last_concepts:
                return Prediction(
                    topic=f"deeper into {last_concepts[0]}",
                    concepts=last_concepts,
                    confidence=0.35,
                    source="heuristic",
                )

        return None

    def _deduplicate(self, predictions: List[Prediction]) -> List[Prediction]:
        """Remove predictions with overlapping concepts."""
        result = []
        seen_concepts = set()
        for pred in predictions:
            pred_set = set(pred.concepts)
            # Skip if >50% overlap with already-seen concepts
            if seen_concepts and len(pred_set & seen_concepts) / max(len(pred_set), 1) > 0.5:
                continue
            result.append(pred)
            seen_concepts |= pred_set
        return result
