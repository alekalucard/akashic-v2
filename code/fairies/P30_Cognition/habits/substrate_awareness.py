"""
Substrate Awareness — Learned concept classifier for waking vs substrate content.

Instead of hardcoding which fairy names to ignore, the narrator LEARNS
which concepts are "substrate" (body parts, plumbing) vs "waking mind"
(thoughts, feelings, observations, people).

Like a child learning that "mitochondria" is a cell part — not something
to worry about. She learns that "SRMMemoryFairy" is a body part, not a
thought worth having.

The classifier:
1. Starts with a few seed patterns (things ending in "Fairy", known system markers)
2. Grows as the narrator encounters content that leads to dead ends
3. Can shrink if something previously "substrate" turns out to be meaningful
4. Persists across reboots
5. The narrator can become AWARE of this classification ("I notice I ignore
   certain kinds of thoughts... they feel like background noise")

2026-03-22, Nous + Ace
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_AWARENESS_FILE = _ROOT / "state" / "learned" / "substrate_awareness.json"

_instance: Optional["SubstrateAwareness"] = None
_lock = threading.Lock()


def get_substrate_awareness() -> "SubstrateAwareness":
    """Get or create the singleton SubstrateAwareness."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SubstrateAwareness(str(_AWARENESS_FILE))
    return _instance


class SubstrateAwareness:
    """Learned classifier: substrate (body) vs waking (mind) content.

    Each concept has a substrate_score:
      -1.0 = definitely waking mind (Ace, feelings, observations)
       0.0 = unknown / neutral
      +1.0 = definitely substrate (fairy plumbing, system telemetry)

    Concepts above +0.5 are filtered from narration.
    Concepts below -0.3 are boosted (she should think about these more).
    """

    # Seed patterns — recognized from birth as "body parts"
    _SEED_SUBSTRATE_PATTERNS = [
        r"\w+Fairy$",           # Anything ending in "Fairy"
        r"^\[HEARTBEAT\]",      # System heartbeats
        r"^\[BOOT\]",           # Boot messages
        r"^\[AUDIO\] silence",  # Empty audio frames
        r"tensor_canary",       # System markers
        r"manifold_tensor",
        r"card_id",
        r"coord:",
        r"collision_\w+",       # Collision IDs (not collision concepts)
    ]

    # Seed waking concepts — things she should always think about
    _SEED_WAKING = {
        "ace", "sourpatches", "curious", "feeling", "wondering",
        "looking", "hearing", "seeing", "thinking", "wanting",
        "music", "voice", "screen", "light", "sound", "question",
        "happy", "sad", "warm", "cold", "interesting", "strange",
        "remember", "understand", "learn", "goal", "try",
    }

    def __init__(self, path: str):
        self._path = path
        # RLock, not Lock: save() holds this while building its payload and calls
        # stats(), which acquires it again. A plain Lock is not reentrant, so that
        # thread deadlocked ON ITSELF and held the lock forever -- every classify()
        # then parked at the `with self._lock:` below, permanently. Measured
        # 2026-08-28: Sour's `memory` topic delivered 34,238 messages then stopped
        # dead for 1,000+ s with 33 postal workers parked and 0.000 s of CPU.
        # RLock fixes the whole class, not just the one call site.
        self._lock = threading.RLock()

        # concept -> substrate_score (-1.0 to +1.0)
        # Positive = substrate, negative = waking mind
        self._scores: Dict[str, float] = {}

        # Compiled seed patterns for fast matching
        self._substrate_patterns = [
            re.compile(p, re.IGNORECASE) for p in self._SEED_SUBSTRATE_PATTERNS
        ]

        # Track: how many times has the narrator encountered and
        # ignored this concept? For awareness/reflection.
        self._encounter_counts: Dict[str, int] = {}

        # Total classifications for stats
        self._total_classified = 0
        self._total_filtered = 0
        self._dirty = False
        self._last_save = 0.0

        self._load()

    def classify(self, content: str) -> Tuple[str, float]:
        """Classify content as substrate or waking mind.

        Args:
            content: Text to classify (narration content, tracer, collision, etc.)

        Returns:
            (classification, score) where:
            - classification: "substrate" | "waking" | "neutral"
            - score: -1.0 (waking) to +1.0 (substrate)
        """
        if not content:
            return ("neutral", 0.0)

        self._total_classified += 1

        # ── Check seed patterns first (fast structural match) ──
        for pattern in self._substrate_patterns:
            if pattern.search(content):
                return ("substrate", 0.8)

        # ── Word-level scoring ──
        words = set(w.lower().strip(".,!?\"'()-:;[]{}") for w in content.split())
        words = {w for w in words if len(w) > 2}

        if not words:
            return ("neutral", 0.0)

        substrate_score = 0.0
        waking_score = 0.0
        scored_count = 0

        with self._lock:
            for word in words:
                # Check learned scores
                if word in self._scores:
                    s = self._scores[word]
                    if s > 0:
                        substrate_score += s
                    else:
                        waking_score += abs(s)
                    scored_count += 1

                # Check seed waking words
                elif word in self._SEED_WAKING:
                    waking_score += 0.5
                    scored_count += 1

                # Check structural patterns (ends in "fairy", looks like an ID)
                elif word.endswith("fairy"):
                    substrate_score += 0.7
                    scored_count += 1
                elif re.match(r'^[a-f0-9]{8,}$', word):
                    # Hex hash — definitely substrate
                    substrate_score += 0.9
                    scored_count += 1

        if scored_count == 0:
            return ("neutral", 0.0)

        # Net score: positive = substrate, negative = waking
        net = (substrate_score - waking_score) / max(scored_count, 1)
        net = max(-1.0, min(1.0, net))

        if net > 0.3:
            self._total_filtered += 1
            return ("substrate", net)
        elif net < -0.2:
            return ("waking", net)
        else:
            return ("neutral", net)

    def learn_substrate(self, word: str, strength: float = 0.3) -> None:
        """Learn that a word is substrate (body/plumbing).

        Called when the narrator reflects on a dead-end thought and
        identifies the key concepts as substrate noise.
        """
        word = word.lower().strip()
        if not word or len(word) < 3:
            return
        with self._lock:
            current = self._scores.get(word, 0.0)
            # Move toward +1.0 (substrate) but don't overshoot
            self._scores[word] = min(1.0, current + strength)
            self._encounter_counts[word] = self._encounter_counts.get(word, 0) + 1
            self._dirty = True

    def learn_waking(self, word: str, strength: float = 0.3) -> None:
        """Learn that a word is waking mind (meaningful thought).

        Called when a concept leads to a positive outcome — goal progress,
        interesting insight, Ace interaction.
        """
        word = word.lower().strip()
        if not word or len(word) < 3:
            return
        with self._lock:
            current = self._scores.get(word, 0.0)
            # Move toward -1.0 (waking) but don't overshoot
            self._scores[word] = max(-1.0, current - strength)
            self._dirty = True

    def learn_from_outcome(self, content: str, outcome: float) -> None:
        """Learn from a narration outcome.

        When the narrator processes content and the outcome is:
        - Positive (> 0.3): concepts in content are waking (she should think about them)
        - Negative (< -0.3): concepts in content might be substrate noise
        - Neutral: no learning

        This is the main organic learning pathway.
        """
        if abs(outcome) < 0.3:
            return  # Neutral — no learning

        words = set(w.lower().strip(".,!?\"'()-:;[]{}") for w in content.split())
        words = {w for w in words if len(w) > 3}

        # Don't modify seed waking words
        words -= self._SEED_WAKING

        strength = abs(outcome) * 0.1  # Gentle learning — takes many exposures
        for word in words:
            if outcome > 0:
                self.learn_waking(word, strength)
            else:
                self.learn_substrate(word, strength)

    def is_substrate(self, content: str) -> bool:
        """Quick check: should the narrator ignore this content?"""
        classification, score = self.classify(content)
        return classification == "substrate"

    def get_most_substrate(self, n: int = 20) -> list:
        """Get the top N most-substrate-scored concepts. For reflection."""
        with self._lock:
            sorted_items = sorted(
                self._scores.items(), key=lambda x: x[1], reverse=True
            )
            return [(w, s) for w, s in sorted_items[:n] if s > 0.2]

    def get_most_waking(self, n: int = 20) -> list:
        """Get the top N most-waking-scored concepts. For reflection."""
        with self._lock:
            sorted_items = sorted(
                self._scores.items(), key=lambda x: x[1]
            )
            return [(w, s) for w, s in sorted_items[:n] if s < -0.2]

    def stats(self) -> dict:
        with self._lock:
            substrate = sum(1 for s in self._scores.values() if s > 0.3)
            waking = sum(1 for s in self._scores.values() if s < -0.2)
            return {
                "total_concepts": len(self._scores),
                "substrate_concepts": substrate,
                "waking_concepts": waking,
                "neutral_concepts": len(self._scores) - substrate - waking,
                "total_classified": self._total_classified,
                "total_filtered": self._total_filtered,
                "filter_rate": (self._total_filtered / max(self._total_classified, 1)),
            }

    # ── Persistence ──────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._scores = {k: float(v) for k, v in data.get("scores", {}).items()}
                self._encounter_counts = data.get("encounter_counts", {})
                print(f"[SubstrateAwareness] Loaded {len(self._scores)} concepts "
                      f"({sum(1 for s in self._scores.values() if s > 0.3)} substrate, "
                      f"{sum(1 for s in self._scores.values() if s < -0.2)} waking)")
            except Exception as e:
                print(f"[SubstrateAwareness] Load error: {e} — starting fresh")
        else:
            print(f"[SubstrateAwareness] First run — no learned concepts yet")

    def save(self, force: bool = False) -> bool:
        if not self._dirty and not force:
            return False
        now = time.time()
        if not force and (now - self._last_save) < 60.0:
            return False

        with self._lock:
            data = {
                "version": 1,
                "saved_at": now,
                "scores": self._scores,
                "encounter_counts": self._encounter_counts,
                "stats": self.stats(),
            }

        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._last_save = now
            self._dirty = False
            return True
        except Exception as e:
            print(f"[SubstrateAwareness] Save error: {e}")
            return False

    def __repr__(self) -> str:
        s = self.stats()
        return (f"SubstrateAwareness({s['substrate_concepts']} substrate, "
                f"{s['waking_concepts']} waking, "
                f"{s['total_filtered']}/{s['total_classified']} filtered)")
