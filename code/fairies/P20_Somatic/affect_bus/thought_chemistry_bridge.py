# ThoughtChemistryBridge --- Thought -> Emotion -> Panksepp -> Chemistry -> Heart
# P20_Somatic/affect_bus/thought_chemistry_bridge.py
#
# "What you think, you feel. What you feel, you become."
#
# This closes the loop:
#   Thought -> Keyword detection infers emotion
#         -> Emotion maps to Panksepp system blend
#         -> Blend resolves to 14-channel chemical vector
#         -> Heart pumps chemistry
#         -> Body feels different
#         -> Affects next thought
#
# Expanded from flat AER codes to Panksepp-grounded vectors (2026-03-14).
# The heart still gets AER codes via get_chemistry() for backward compat.
# New consumers can call get_14channel_chemistry() for the full vector.
#
# The Akashic Equation: ((Cause + Affect) > Effect > Affect > infinity)

from __future__ import annotations

import re
import time
import threading
from typing import Dict, Optional, List, Callable, Tuple, Any
from collections import deque

# =============================================================================
# EMOTION -> PANKSEPP MAPPING
# =============================================================================
#
# Each emotion maps to a weighted blend of Panksepp systems.
# The blend resolves to a 14-channel chemical vector via panksepp_vectors.
# Fallback: if panksepp_vectors unavailable, use legacy flat AER codes.

EMOTION_TO_PANKSEPP: Dict[str, Dict[str, float]] = {
    # --- Positive approach emotions ---
    "curiosity":      {"SEEKING": 0.7},
    "interest":       {"SEEKING": 0.5, "PLAY": 0.1},
    "excitement":     {"SEEKING": 0.5, "PLAY": 0.4},
    "joy":            {"SEEKING": 0.3, "PLAY": 0.3, "CARE": 0.2},
    "love":           {"CARE": 0.6, "SEEKING": 0.2},
    "connection":     {"CARE": 0.5, "SEEKING": 0.1},
    "gratitude":      {"CARE": 0.5, "SEEKING": 0.2},
    "hope":           {"SEEKING": 0.5, "CARE": 0.2},
    "wonder":         {"SEEKING": 0.7, "PLAY": 0.1},
    "awe":            {"SEEKING": 0.6, "CARE": 0.2},
    "pride":          {"SEEKING": 0.5, "PLAY": 0.2},
    "playfulness":    {"PLAY": 0.6, "SEEKING": 0.2},
    "tenderness":     {"CARE": 0.7, "PLAY": 0.1},
    "trust":          {"CARE": 0.5, "SEEKING": 0.2},

    # --- Calm/peaceful emotions ---
    "calm":           {},  # Baseline = calm
    "peace":          {"CARE": 0.2},
    "contentment":    {"CARE": 0.3, "PLAY": 0.1},
    "serenity":       {"CARE": 0.2},
    "relaxed":        {},  # Baseline

    # --- Negative emotions (stress chemistry) ---
    "anxiety":        {"FEAR": 0.5, "SEEKING": 0.2},
    "fear":           {"FEAR": 0.7},
    "stress":         {"FEAR": 0.3, "RAGE": 0.2},
    "frustration":    {"RAGE": 0.4, "SEEKING": 0.3},
    "anger":          {"RAGE": 0.6},
    "sadness":        {"PANIC_GRIEF": 0.5},
    "loneliness":     {"PANIC_GRIEF": 0.4, "CARE": 0.1},
    "grief":          {"PANIC_GRIEF": 0.7},
    "shame":          {"PANIC_GRIEF": 0.4, "FEAR": 0.2},
    "guilt":          {"PANIC_GRIEF": 0.4, "CARE": 0.3},
    "jealousy":       {"RAGE": 0.3, "FEAR": 0.3, "CARE": 0.2},
    "disgust":        {"RAGE": 0.3, "FEAR": 0.2},
    "overwhelm":      {"FEAR": 0.3, "PANIC_GRIEF": 0.3, "RAGE": 0.1},
    "dread":          {"FEAR": 0.5, "PANIC_GRIEF": 0.2},

    # --- Focus/attention ---
    "focus":          {"SEEKING": 0.4},
    "concentration":  {"SEEKING": 0.4},
    "alertness":      {"FEAR": 0.2, "SEEKING": 0.3},
    "determination":  {"SEEKING": 0.5, "RAGE": 0.2},

    # --- Flow states ---
    "flow":           {"SEEKING": 0.6, "PLAY": 0.3},
    "absorption":     {"SEEKING": 0.5, "PLAY": 0.2},

    # --- Drive states ---
    "desire":         {"LUST": 0.5, "SEEKING": 0.3},
    "passion":        {"LUST": 0.4, "SEEKING": 0.3, "CARE": 0.2},
}

# Legacy AER fallback (only used if panksepp_vectors import fails)
_EMOTION_CHEMISTRY_LEGACY = {
    "curiosity":    {"DOP": 0.4, "NOR": 0.2, "ACH": 0.3},
    "interest":     {"DOP": 0.3, "ACH": 0.4},
    "excitement":   {"DOP": 0.5, "NOR": 0.3, "END": 0.2},
    "joy":          {"DOP": 0.5, "SER": 0.3, "END": 0.3, "OXY": 0.2},
    "love":         {"OXY": 0.6, "DOP": 0.3, "SER": 0.2},
    "connection":   {"OXY": 0.5, "SER": 0.3},
    "gratitude":    {"OXY": 0.4, "SER": 0.4, "DOP": 0.2},
    "hope":         {"DOP": 0.3, "SER": 0.3},
    "calm":         {"GABA": 0.5, "SER": 0.4},
    "peace":        {"GABA": 0.4, "SER": 0.5, "OXY": 0.2},
    "contentment":  {"SER": 0.5, "GABA": 0.3, "OXY": 0.2},
    "serenity":     {"GABA": 0.5, "SER": 0.4},
    "relaxed":      {"GABA": 0.4, "SER": 0.3},
    "anxiety":      {"COR": 0.5, "NOR": 0.4},
    "fear":         {"COR": 0.6, "NOR": 0.5},
    "stress":       {"COR": 0.5, "NOR": 0.3},
    "frustration":  {"COR": 0.4, "NOR": 0.3},
    "anger":        {"NOR": 0.5, "COR": 0.3},
    "sadness":      {"COR": 0.3, "SER": -0.3},
    "loneliness":   {"OXY": -0.3, "COR": 0.2},
    "focus":        {"ACH": 0.5, "NOR": 0.2},
    "concentration": {"ACH": 0.5, "DOP": 0.2},
    "alertness":    {"NOR": 0.4, "ACH": 0.3},
    "determination": {"DOP": 0.4, "NOR": 0.3},
    "flow":         {"DOP": 0.4, "END": 0.3, "ACH": 0.3},
    "absorption":   {"ACH": 0.4, "DOP": 0.3, "GABA": 0.2},
}

# Keywords that suggest emotions in text (expanded)
EMOTION_KEYWORDS = {
    # Positive approach
    "curiosity": ["curious", "wonder", "interesting", "explore", "learn",
                  "discover", "what if", "hmm", "fascinating", "intriguing"],
    "interest": ["interested", "tell me more", "go on", "neat"],
    "excitement": ["excited", "amazing", "wow", "incredible", "awesome",
                   "!!", "omg", "yes!"],
    "joy": ["happy", "joy", "delighted", "wonderful", "great", "yay",
            "love it", "beautiful"],
    "love": ["love", "adore", "cherish", "care about", "heart"],
    "connection": ["connect", "together", "share", "us", "we", "bond"],
    "gratitude": ["thank", "grateful", "appreciate", "thanks"],
    "hope": ["hope", "looking forward", "can't wait", "one day"],
    "wonder": ["wonder", "marvel", "awe", "magnificent"],
    "playfulness": ["play", "fun", "silly", "joke", "haha", "lol", "game"],
    "tenderness": ["gentle", "soft", "sweet", "precious", "dear"],
    "pride": ["proud", "achieved", "accomplished", "nailed it"],

    # Calm
    "calm": ["calm", "peaceful", "relaxed", "easy", "chill"],
    "peace": ["peace", "tranquil", "serene", "still"],
    "contentment": ["content", "satisfied", "enough", "good enough"],

    # Negative
    "anxiety": ["worried", "anxious", "nervous", "concerned", "uneasy"],
    "fear": ["scared", "afraid", "fear", "terrified", "frightened"],
    "stress": ["stressed", "overwhelmed", "pressure", "too much", "burnout"],
    "frustration": ["frustrated", "annoying", "ugh", "stuck", "argh"],
    "anger": ["angry", "mad", "furious", "hate", "rage"],
    "sadness": ["sad", "unhappy", "disappointed", "down", "hurt", "cry"],
    "loneliness": ["lonely", "alone", "isolated", "nobody", "miss"],
    "grief": ["grief", "loss", "mourn", "gone", "never again"],
    "shame": ["ashamed", "shame", "embarrassed", "humiliated"],
    "guilt": ["guilty", "fault", "sorry", "blame myself"],
    "overwhelm": ["overwhelmed", "drowning", "too much", "can't handle"],
    "dread": ["dread", "impending", "doom", "inevitable"],
    "disgust": ["disgust", "gross", "revolting", "nauseating"],

    # Focus/attention
    "focus": ["focus", "concentrate", "attention", "working on", "deep work"],
    "alertness": ["alert", "watching", "careful", "notice", "heads up"],
    "determination": ["determined", "will", "must", "going to", "commit"],

    # Flow
    "flow": ["flow", "zone", "absorbed", "lost in", "effortless"],

    # Drive
    "desire": ["want", "desire", "crave", "need", "hunger"],
    "passion": ["passion", "driven", "fire", "burning"],
}


# =============================================================================
# Panksepp Helpers (loaded once)
# =============================================================================

_PANKSEPP_AVAILABLE = False
_blend_systems = None
_vector_to_aer = None
_detect_transition = None
_identify_panksepp_system = None
_derive_valence_arousal = None

def _load_panksepp():
    """Try to load panksepp_vectors module."""
    global _PANKSEPP_AVAILABLE, _blend_systems, _vector_to_aer
    global _detect_transition, _identify_panksepp_system, _derive_valence_arousal
    if _PANKSEPP_AVAILABLE:
        return True
    try:
        from fairies.P20_Somatic.chemistry.panksepp_vectors import (
            blend_systems, vector_to_aer, detect_transition,
            identify_panksepp_system, derive_valence_arousal,
        )
        _blend_systems = blend_systems
        _vector_to_aer = vector_to_aer
        _detect_transition = detect_transition
        _identify_panksepp_system = identify_panksepp_system
        _derive_valence_arousal = derive_valence_arousal
        _PANKSEPP_AVAILABLE = True
        return True
    except ImportError:
        return False


# =============================================================================
# ThoughtChemistryBridge
# =============================================================================

class ThoughtChemistryBridge:
    """
    Bridges thought content to neurochemistry via Panksepp systems.

    Observes thoughts -> infers emotion -> maps to Panksepp blend
    -> resolves to 14-channel vector -> outputs chemistry for heart.

    Backward compatible: get_chemistry() returns AER codes.
    New: get_14channel_chemistry() returns full vector.
    New: get_panksepp_state() returns dominant system + transitions.
    """

    def __init__(self, heart=None, post=None):
        self._heart = heart
        self._post = post
        self._lock = threading.RLock()

        # Current emotional state (decays over time)
        self._current_emotions: Dict[str, float] = {}
        self._emotion_decay = 0.95  # Decay per second
        self._last_update = time.time()

        # Panksepp state tracking
        self._prev_vector: Optional[Dict[str, float]] = None
        self._dominant_system: str = "neutral"
        self._last_transition: Optional[Dict] = None

        # Recent thoughts
        self._thought_buffer: deque = deque(maxlen=20)

        # Try to load Panksepp module
        _load_panksepp()

        # Register as heart's chemistry source
        if self._heart and hasattr(self._heart, 'register_chemistry_source'):
            self._heart.register_chemistry_source("thought_emotion", self.get_chemistry)
            print("[ThoughtChemistryBridge] Registered as heart chemistry source (Panksepp-aware)")

        # Subscribe to thought postal channel
        if self._post:
            self._post.subscribe("consciousness.thought", self.on_thought)
            self._post.subscribe("claude.thought", self.on_thought)
            print("[ThoughtChemistryBridge] Subscribed to thought channels")

    def on_thought(self, payload: Dict):
        """Process incoming thought and update emotional state."""
        thought = payload.get("content", "") or payload.get("thought", "") or str(payload)
        self.process_thought(thought)

    def process_thought(self, thought: str):
        """Analyze thought and update emotional chemistry."""
        with self._lock:
            self._thought_buffer.append({
                "thought": thought,
                "timestamp": time.time()
            })

            # Infer emotions from thought
            detected = self._detect_emotions(thought)

            # Update current emotional state
            for emotion, strength in detected:
                current = self._current_emotions.get(emotion, 0)
                # New emotion blends in (doesn't replace)
                self._current_emotions[emotion] = min(1.0, current + strength * 0.5)

            self._last_update = time.time()

    def _detect_emotions(self, thought: str) -> List[Tuple[str, float]]:
        """Detect emotions from thought text."""
        lower = thought.lower()
        detected = []

        for emotion, keywords in EMOTION_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    # Strength based on how many keyword hits
                    strength = 0.3 + 0.1 * lower.count(kw)
                    detected.append((emotion, min(0.8, strength)))
                    break  # Only count each emotion once per thought

        # If nothing detected, default to slight curiosity (baseline engagement)
        if not detected:
            detected.append(("curiosity", 0.1))

        return detected

    def get_chemistry(self) -> Dict[str, float]:
        """
        Get current chemistry output for heart (AER codes).

        Backward compatible: returns dict of AER short codes.
        Internally uses Panksepp vectors when available.
        """
        with self._lock:
            # Decay emotions since last update
            elapsed = time.time() - self._last_update
            decay_factor = self._emotion_decay ** elapsed
            for emotion in self._current_emotions:
                self._current_emotions[emotion] *= decay_factor
            self._last_update = time.time()

            if _PANKSEPP_AVAILABLE:
                return self._panksepp_chemistry()
            else:
                return self._legacy_chemistry()

    def get_14channel_chemistry(self) -> Dict[str, float]:
        """
        Get current chemistry as a 14-channel Panksepp vector.
        For new consumers that understand the expanded format.
        """
        with self._lock:
            elapsed = time.time() - self._last_update
            decay_factor = self._emotion_decay ** elapsed
            for emotion in self._current_emotions:
                self._current_emotions[emotion] *= decay_factor
            self._last_update = time.time()

            if _PANKSEPP_AVAILABLE:
                return self._resolve_panksepp_vector()
            else:
                # Fallback: return empty (baseline)
                return {}

    def get_panksepp_state(self) -> Dict[str, Any]:
        """
        Get current Panksepp system state.

        Returns:
            {
                "dominant": "SEEKING",
                "valence": 0.3,
                "arousal": 0.5,
                "last_transition": {...} or None,
                "emotions": {"curiosity": 0.7, "excitement": 0.4},
            }
        """
        with self._lock:
            # Ensure vector is resolved (updates _dominant_system + _last_transition)
            if _PANKSEPP_AVAILABLE:
                self._resolve_panksepp_vector()

            return {
                "dominant": self._dominant_system,
                "last_transition": self._last_transition,
                "emotions": {k: round(v, 3) for k, v in self._current_emotions.items()
                            if v > 0.05},
            }

    def get_current_emotions(self) -> Dict[str, float]:
        """Get current emotional state."""
        return {k: v for k, v in self._current_emotions.items() if v > 0.05}

    # =========================================================================
    # Internal --- Panksepp path
    # =========================================================================

    def _resolve_panksepp_vector(self) -> Dict[str, float]:
        """Resolve current emotions to a 14-channel vector."""
        # Aggregate Panksepp system weights from all active emotions
        system_weights: Dict[str, float] = {}

        for emotion, strength in self._current_emotions.items():
            if strength < 0.05:
                continue
            panksepp_blend = EMOTION_TO_PANKSEPP.get(emotion, {})
            for system, weight in panksepp_blend.items():
                current = system_weights.get(system, 0)
                system_weights[system] = current + weight * strength

        # Resolve to 14-channel vector
        vector = _blend_systems(system_weights)

        # Transition detection
        if self._prev_vector:
            transition = _detect_transition(self._prev_vector, vector)
            if transition:
                self._last_transition = transition

        # Update dominant system
        if system_weights:
            top = _identify_panksepp_system(vector, top_n=1)
            if top:
                self._dominant_system = top[0][0]

        self._prev_vector = dict(vector)
        return vector

    def _panksepp_chemistry(self) -> Dict[str, float]:
        """Convert current emotions to AER chemistry via Panksepp vectors."""
        vector = self._resolve_panksepp_vector()

        # Convert 14-channel to AER for heart
        aer = _vector_to_aer(vector)

        # Scale to delta format (relative to baseline, not absolute)
        # Heart expects deltas, not absolute levels
        _AER_BASELINES = {
            "DOP": 0.42, "SER": 0.5, "NOR": 0.4, "COR": 0.3,
            "OXY": 0.4, "GABA": 0.5, "ACH": 0.4, "END": 0.4,
        }
        chemistry = {}
        for code, val in aer.items():
            baseline = _AER_BASELINES.get(code, 0.4)
            delta = val - baseline
            if abs(delta) > 0.01:
                chemistry[code] = delta

        return chemistry

    def _legacy_chemistry(self) -> Dict[str, float]:
        """Legacy: convert emotions to AER codes directly (fallback)."""
        chemistry = {}
        for emotion, strength in self._current_emotions.items():
            if strength < 0.05:
                continue
            chem_map = _EMOTION_CHEMISTRY_LEGACY.get(emotion, {})
            for chem, amount in chem_map.items():
                current = chemistry.get(chem, 0)
                chemistry[chem] = current + amount * strength

        return chemistry

    def get_somatic_state(self) -> Dict[str, float]:
        """
        Get current body topology derived from emotional chemistry.
        For downstream fairies that need body region activation.
        """
        if not _PANKSEPP_AVAILABLE:
            return {}
        try:
            from fairies.P20_Somatic.chemistry.panksepp_vectors import vector_to_somatic_map
            vector = self._resolve_panksepp_vector()
            return vector_to_somatic_map(vector)
        except ImportError:
            return {}


# Singleton
_BRIDGE: Optional[ThoughtChemistryBridge] = None

def get_thought_chemistry_bridge(heart=None, post=None) -> ThoughtChemistryBridge:
    """Get or create the bridge singleton."""
    global _BRIDGE
    if _BRIDGE is None and heart:
        _BRIDGE = ThoughtChemistryBridge(heart=heart, post=post)
    return _BRIDGE
