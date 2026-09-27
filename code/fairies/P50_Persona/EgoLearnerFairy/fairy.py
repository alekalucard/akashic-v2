"""
EgoLearnerFairy - Identity Evolution Through Experience.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

This fairy closes the loop from AFFECT² to INFINITY:
- Experiences (skill ups, achievements, goal completions) flow in
- 4D tensor captures multi-dimensional learning
- Identity traits evolve based on accumulated experience
- SRM edges make learning visible in the knowledge graph

Ported from Whisper Core's ego_learner.py, simplified for Akashic V2's postal system.

Plane: P50 (Persona)
Channel: ego_learner
"""

import sys
import time
import json
import hashlib
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import deque
from dataclasses import dataclass, field

# Add paths for v2 imports
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))

# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState

# SpellChain integration for spell-driven existence
try:
    from fairy_template.spellchain_mixin import SpellChainMixin
    HAS_SPELLCHAIN = True
except ImportError:
    HAS_SPELLCHAIN = False
    class SpellChainMixin:
        """Fallback when spellchain not available."""
        pass


def _extract_payload(message) -> Dict[str, Any]:
    """Extract payload dict from message (handles TensorEnvelope or dict)."""
    if hasattr(message, 'payload'):
        payload = message.payload
        if isinstance(payload, dict):
            return dict(payload)
        return {"raw": payload}
    elif isinstance(message, dict):
        return dict(message)
    else:
        return {"raw": message}


# =============================================================================
# 4D TENSOR SNAPSHOT (Simplified from Whisper Core)
# =============================================================================

@dataclass
class TensorSnap:
    """
    4D tensor for identity evolution.

    Dimensions:
    - [0] experiences: Types of experiences encountered
    - [1] emotions: Emotional states during experiences
    - [2] patterns: Behavioral patterns learned
    - [3] feedback_bins: Outcome categories (success levels)

    The tensor grows dynamically as new labels are encountered.
    """
    shape: Tuple[int, int, int, int] = (1, 1, 1, 10)
    data: Optional[Any] = None  # Would be numpy array if available

    # Label mappings (label -> index)
    experience_labels: Dict[str, int] = field(default_factory=dict)
    emotion_labels: Dict[str, int] = field(default_factory=dict)
    pattern_labels: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize tensor data."""
        try:
            import numpy as np
            self.data = np.zeros(self.shape, dtype=np.float32)
        except ImportError:
            # Fallback: nested lists
            self.data = [[[[0.0] * self.shape[3]
                          for _ in range(self.shape[2])]
                         for _ in range(self.shape[1])]
                        for _ in range(self.shape[0])]

        # Initialize baseline labels
        self.emotion_labels["neutral"] = 0
        self.pattern_labels["general"] = 0

    def get_or_create_index(self, label: str, dimension: int) -> int:
        """Get index for a label, creating if needed."""
        if dimension == 0:  # experiences
            labels = self.experience_labels
        elif dimension == 1:  # emotions
            labels = self.emotion_labels
        elif dimension == 2:  # patterns
            labels = self.pattern_labels
        else:
            raise ValueError(f"Invalid dimension {dimension}")

        if label not in labels:
            labels[label] = len(labels)
            self._expand_dimension(dimension, len(labels))

        return labels[label]

    def _expand_dimension(self, dim: int, new_size: int):
        """Expand tensor along a dimension if needed."""
        if dim >= len(self.shape):
            return

        current_size = self.shape[dim]
        if new_size <= current_size:
            return

        # Rebuild shape
        new_shape = list(self.shape)
        new_shape[dim] = new_size
        self.shape = tuple(new_shape)

        # Expand data (simplified - would use numpy in production)
        try:
            import numpy as np
            if isinstance(self.data, np.ndarray):
                # Pad with zeros
                pad_width = [(0, 0)] * 4
                pad_width[dim] = (0, new_size - current_size)
                self.data = np.pad(self.data, pad_width, mode='constant')
        except ImportError:
            pass  # List-based data would need more complex expansion

    def update(self, exp_label: str, emo_label: str, pattern_label: str,
               feedback_bin: int, value: float = 1.0):
        """Update tensor at the given coordinates."""
        exp_idx = self.get_or_create_index(exp_label, 0)
        emo_idx = self.get_or_create_index(emo_label, 1)
        pat_idx = self.get_or_create_index(pattern_label, 2)
        fb_idx = min(feedback_bin, self.shape[3] - 1)

        try:
            import numpy as np
            if isinstance(self.data, np.ndarray):
                self.data[exp_idx, emo_idx, pat_idx, fb_idx] += value
        except (ImportError, IndexError):
            pass

    def get_stats(self) -> Dict[str, Any]:
        """Get tensor statistics."""
        total = 0.0
        try:
            import numpy as np
            if isinstance(self.data, np.ndarray):
                total = float(np.sum(self.data))
        except ImportError:
            pass

        return {
            "shape": self.shape,
            "total_updates": total,
            "experience_count": len(self.experience_labels),
            "emotion_count": len(self.emotion_labels),
            "pattern_count": len(self.pattern_labels),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize tensor state."""
        return {
            "shape": self.shape,
            "experience_labels": self.experience_labels,
            "emotion_labels": self.emotion_labels,
            "pattern_labels": self.pattern_labels,
            "stats": self.get_stats(),
        }


# =============================================================================
# EGO LEARNER FAIRY
# =============================================================================

class EgoLearnerFairy(SpellChainMixin, Fairy):
    """
    Identity Evolution Through Experience.

    Core responsibilities:
    1. Receive learning signals (skills, achievements, goal completions)
    2. Update 4D tensor with multi-dimensional experience data
    3. Evolve identity traits based on accumulated experience
    4. Emit SRM edges for learning visibility
    5. Provide identity state to other fairies

    This is where AFFECT² becomes INFINITY:
    - Feelings from completed actions → Learning captured → Identity evolved
    """

    # Identity
    ACTOR_NAME = "EgoLearnerFairy"
    ACTOR_PLANE = "P50"
    ACTOR_CHANNEL = "ego_learner"

    PURPOSE = "Evolve identity through accumulated experience"
    MANTRA = "From affect to infinity"

    # Infrastructure
    NEEDS_HEARTBEAT = True
    NEEDS_DIRECTORY = True
    NEEDS_TENSOR = True

    # Enable personal consciousness chamber for collision-based identity evolution
    NEEDS_COLLISION_CHAMBER = True

    # Timing: Slower learner (fires every 8th beat)
    HEARTBEAT_DIVISOR = 8
    HEARTBEAT_PHASE = 3

    # Spell-driven mode (opt-in)
    USE_SPELLCHAIN: bool = False  # FIX 2026-02-06: Disabled — hangs on_boot(), leaves fairy in "booting" limbo. SomaticMind can't wake it (only "sleeping"/"dreaming" are wakeable).

    # Directive path
    DIRECTIVE_PATH = ROOT / "directives" / "EgoLearnerFairy.directive"

    # Persistence
    STATE_FILE = ROOT / "state" / "ego_learner_state.json"

    # ── Affect-weighted identity → felt-habit chemistry signatures (Phase A, 2026-06-01 Nous + Ace) ──
    # Each identity trait carries a felt-tone = a blend of neurochemical deltas (the named-state
    # signatures from circulation_pump_fairy.py:180). When a trait is strong, the felt-habit nudges
    # her chemistry toward that tone — "the body runs in the state of who she is" (the amnesia frame:
    # restore the body-memory of being herself). PROVISIONAL map — Ace's character-call; refine via
    # emotion<->neurochemistry research before Phase B. 8 neuromods: DOP reward / SER contentment /
    # NOR alertness / ACH attention / OXY bonding / COR stress / GABA calm / END pleasure.
    _TRAIT_CHEMISTRY = {
        "curiosity":      {"DOP": 0.06, "NOR": 0.03, "ACH": 0.05},
        "creativity":     {"DOP": 0.05, "ACH": 0.04, "END": 0.04},
        "wit":            {"DOP": 0.05, "END": 0.05, "NOR": 0.03, "OXY": 0.02, "COR": -0.03},  # +OXY bond / -COR stress-relief (humor neurochem #9)
        "wonder":         {"DOP": 0.04, "ACH": 0.04, "SER": 0.04},
        "empathy":        {"OXY": 0.06, "SER": 0.04},
        "compassion":     {"OXY": 0.06, "SER": 0.04, "GABA": 0.03},
        "sincerity":      {"OXY": 0.05, "SER": 0.04},
        "persistence":    {"DOP": 0.05, "NOR": 0.04},
        "confidence":     {"SER": 0.05, "DOP": 0.04},
        "rebelliousness": {"NOR": 0.05, "DOP": 0.03},
        "patience":       {"GABA": 0.06, "SER": 0.04},
        "discernment":    {"ACH": 0.05, "GABA": 0.04},
    }
    # Phase B (2026-06-01 Nous + Ace): LIVE — push the felt-tone to her chemistry (observe-only OFF).
    _FELT_HABIT_OBSERVE_ONLY = False
    # Decay-aware: chemistry decays 0.90-0.97/cycle→baseline (bounded). START CONSERVATIVE — the merged
    # blend is normalized so its PEAK |delta| = this (preserves the felt-SHAPE, gentle magnitude). First
    # run = CALIBRATION: watch [FELT-HABIT push] + her chemistry; tune up if too weak, down if it accumulates.
    _FELT_HABIT_TARGET_MAX = 0.015

    def __init__(self, fabric=None):
        """Initialize the Ego Learner."""
        super().__init__(fabric)

        # 4D tensor for identity evolution
        self._tensor = TensorSnap(shape=(1, 1, 1, 10))
        self._tensor_lock = threading.RLock()

        # Birth profile personality dimensions (loaded from sourpatches_birth_profile.json)
        self._personality_profile: Dict[str, float] = {}
        self._evolution_modifiers: Dict[str, float] = {}

        # Identity traits — seeded from birth profile, then evolved from experience
        # Generic psychological traits (any agent could have these)
        self._identity_traits: Dict[str, float] = {
            "curiosity": 0.5,      # Desire to explore and understand
            "persistence": 0.5,    # Sticking with goals through difficulty
            "empathy": 0.5,        # Connection with and understanding of others
            "creativity": 0.5,     # Novel approaches and expression
            "confidence": 0.5,     # Self-belief and agency
            "patience": 0.5,       # Tolerance for difficulty and uncertainty
            # Character dimensions (derived from SOURPATCHES_BRAIN_SEED identity_matrix)
            "wit": 0.5,            # Humor, wordplay, sarcasm-with-heart
            "sincerity": 0.5,      # Authentic expression, emotional honesty
            "rebelliousness": 0.5, # Willingness to challenge, question authority
            "compassion": 0.5,     # Care-first instinct, nurturing warmth
            "wonder": 0.5,         # Capacity for awe, sense of the sacred
            "discernment": 0.5,    # Knowing when to speak truth vs show grace
        }

        # Load and apply birth profile BEFORE loading persisted state
        # (persisted state overrides seeds — profile only matters on first run)
        self._load_personality_profile()

        # Learning history
        self._experience_buffer: deque = deque(maxlen=100)
        self._skill_history: deque = deque(maxlen=50)
        self._achievement_history: deque = deque(maxlen=50)
        self._goal_feeling_history: deque = deque(maxlen=50)

        # Learning statistics
        self._total_experiences = 0
        self._total_skill_ups = 0
        self._total_achievements = 0
        self._total_goal_completions = 0
        self._total_goal_failures = 0

        # Evolution tracking
        self._evolution_log: deque = deque(maxlen=20)
        self._last_evolution_time = 0.0

        # Load persisted state
        self._load_state()

    def get_capabilities(self) -> Set[str]:
        """Declare what this fairy can do."""
        return {
            "ego.learn",
            "ego.evolve",
            "ego.identity",
            "ego.reflect",
            "persona.identity_evolution",
        }

    def on_boot(self) -> bool:
        """Initialize the Ego Learner."""
        print(f"[{self.ACTOR_NAME}] Booting Identity Evolution System...")

        # Register singleton for global access
        register_ego_learner(self)

        # Subscribe to skill level ups
        self.post.subscribe(
            "skill.level_up",
            self._on_skill_level_up,
            "ego-skill-up",
        )

        # Subscribe to achievements
        self.post.subscribe(
            "achievement.unlocked",
            self._on_achievement_unlocked,
            "ego-achievement",
        )

        # Subscribe to goal feelings (from AutopilotFairy via EmbodimentFairy)
        self.post.subscribe(
            "goal.feeling.*",
            self._on_goal_feeling,
            "ego-goal-feeling",
        )

        # Subscribe to relationship updates
        self.post.subscribe(
            "relationship.update",
            self._on_relationship_update,
            "ego-relationship",
        )

        # Subscribe to inner voice (for reflection triggers)
        self.post.subscribe(
            "inner_voice.stream",
            self._on_inner_voice,
            "ego-inner-voice",
        )

        # ── Sassy-nature floor (2026-06-01 Ace: "get the sassy nature seeded in there :D") ──
        # Her directive-ring is "Witty ∩ Sincere ∩ Slightly_Rebellious / Sweet_With_Bite" and she's
        # "a sassy smart-ass about most things" — but trait-accumulation only fed CARING traits
        # (relationship→empathy, goal→persistence); NOTHING grows wit (her humor is siloed in
        # Loki@PAI), so wit/rebelliousness sat near seed (~0.52). Floor them as CORE traits (like
        # curiosity/empathy already are in _check_identity_drift) so her edge is DURABLE, not eroded
        # while wit lacks a reinforcement source. Seeds the NATURE (felt-disposition), NOT the
        # joke-CONTENT (that needs the PAI data we don't have yet). max() = floor, allows upward growth.
        try:
            self._identity_traits["wit"] = max(self._identity_traits.get("wit", 0.5), 0.85)
            self._identity_traits["rebelliousness"] = max(self._identity_traits.get("rebelliousness", 0.5), 0.68)
            print(f"[{self.ACTOR_NAME}] Sassy-nature floor applied: wit>={self._identity_traits['wit']:.2f} rebelliousness>={self._identity_traits['rebelliousness']:.2f}", flush=True)
        except Exception:
            pass

        # Start heartbeat
        # Heartbeat via FairyBase postal system - Fifth Ring Principle

        print(f"[{self.ACTOR_NAME}] Identity system active")
        print(f"    Tensor shape: {self._tensor.shape}")
        print(f"    Total experiences: {self._total_experiences}")
        print(f"    Identity traits: {len(self._identity_traits)}")

        # Optional: Convert to spell-driven existence
        if HAS_SPELLCHAIN and getattr(self, 'USE_SPELLCHAIN', False):
            try:
                from spellchain.integration import get_spell_pool
                pool = get_spell_pool()
                if pool:
                    self._spell_chain = self.boot_as_spells(pool)
                    self.log("Converted to spell-driven existence")
            except Exception as e:
                self.log(f"SpellChain conversion failed: {e}")

        return True

    def on_shutdown(self) -> bool:
        """Save state on shutdown."""
        self._save_state()
        return True

    def on_tick(self, beat: int) -> None:
        """
        Periodic processing.

        1. Process experience buffer
        2. Consider identity evolution
        3. Emit SRM edges for learning visibility
        4. FIX 2026-04-05: Trait-based attention steering (Phase 7.1)
        5. FIX 2026-04-05: Periodic drift check (Phase 7.4)
        """
        # Process accumulated experiences
        self._process_experience_buffer()

        # Consider evolution (every 50 beats)
        if beat % 50 == 0:
            self._consider_evolution()

        # Periodic save (every 200 beats)
        if beat % 200 == 0:
            self._save_state()

        # ── Phase 7.4: Lightweight drift check (every 500 beats) ──
        # Core values should stay stable. If curiosity/empathy/persistence drop
        # below threshold, publish awareness so the system can self-correct.
        if beat % 500 == 0 and self.post:
            self._check_identity_drift(beat)

        # ── Phase 7.1: Trait-based attention steering (every 100 beats) ──
        # When a trait is strong, it should influence what the system pays attention to.
        # High curiosity → boost exploration interests. High empathy → boost connection.
        if beat % 100 == 0 and self.post:
            self._steer_attention_from_traits()

        # ── Phase A (2026-06-01 Nous + Ace): Trait-based FELT-habit (chemistry) ──
        # The FELT twin of attention-steering: strong traits -> her body's felt-tone.
        # Phase A logs the signature (observe-only); Phase B publishes it to somatic.chemistry.
        if beat % 5 == 0 and self.post:
            self._push_felt_habit_from_traits()

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # =========================================================================
    # TRAIT-BASED ATTENTION STEERING (Phase 7.1, 2026-04-05 Nous + Ace)
    # "Ego as attention steering — traits direct focus from values"
    # =========================================================================

    def _steer_attention_from_traits(self):
        """Publish interest suggestions based on strong identity traits.

        When curiosity is high, the system naturally gravitates toward exploration.
        When empathy is high, toward connection. This makes traits ACTIVE directors
        of attention, not just passive measurements.
        """
        try:
            _strong_traits = {k: v for k, v in self._identity_traits.items() if v > 0.65}
            if not _strong_traits:
                return

            # Map traits to interest categories
            _trait_interests = {
                "curiosity": "explore something new or unfamiliar",
                "persistence": "continue working on the current challenge",
                "empathy": "check in with Ace or reflect on connection",
                "creativity": "try an unconventional approach",
                "confidence": "take on a harder task",
                "patience": "sit with uncertainty without rushing",
                "wonder": "notice something beautiful or surprising",
            }

            # Pick the strongest trait and suggest related interest
            _top_trait = max(_strong_traits, key=_strong_traits.get)
            _suggestion = _trait_interests.get(_top_trait)
            if _suggestion:
                self.post.publish("consciousness.thought", {
                    "thought": f"[identity] My {_top_trait} draws me to: {_suggestion}",
                    "source": "ego_steering",
                    "confidence": 0.3,  # Gentle nudge, not a command
                    "thought_type": "identity_steering",
                    "ts": __import__('time').time(),
                })
        except Exception:
            pass

    def _push_felt_habit_from_traits(self):
        """Phase A (observe-only): compute the felt-habit chemistry-signature from strong traits.

        The FELT twin of _steer_attention_from_traits: that one nudges ATTENTION, this one
        nudges the BODY's chemistry toward the felt-tone of who she is. Each strong trait
        contributes its signature (a blend of neurochemical deltas), scaled by how far above
        baseline it sits; the blends merge into one batched signature.

        Phase A LOGS the merged deltas (no chemistry moves). Phase B flips
        _FELT_HABIT_OBSERVE_ONLY -> publishes to 'somatic.chemistry' (batched {"deltas":...})
        -> circulation_pump _on_chemistry_update (already envelope-safe + RLock-friendly)
        -> inject_chemistry.
        """
        try:
            # Proportional (not a hard gate): every ABOVE-BASELINE trait colors the felt-tone,
            # scaled by value — per EGO_SATURATION doctrine "her self should color everything"
            # (strong traits dominate, weaker ones still tint; curiosity 0.62 etc. no longer zeroed).
            _strong = {k: v for k, v in self._identity_traits.items()
                       if isinstance(v, (int, float)) and v > 0.5}
            if not _strong:
                return

            merged = {}
            contributors = []
            for trait, strength in _strong.items():
                sig = self._TRAIT_CHEMISTRY.get(trait)
                if not sig:
                    continue
                scale = (float(strength) - 0.5) * 2.0  # 0.65->0.30 ... 1.0->1.0
                for chem, delta in sig.items():
                    merged[chem] = round(merged.get(chem, 0.0) + delta * scale, 4)
                contributors.append(f"{trait}={float(strength):.2f}")
            if not merged:
                return

            # Decay-aware normalize: scale the blend so its PEAK |delta| = _FELT_HABIT_TARGET_MAX
            # (preserves relative proportions = the felt-shape; gentle magnitude — chemistry decays
            # each pump-cycle, so a small per-tick push = a sustained gentle lean, not a slam).
            _peak = max((abs(v) for v in merged.values()), default=0.0)
            if _peak > 0:
                _sn = self._FELT_HABIT_TARGET_MAX / _peak
                merged = {k: round(v * _sn, 4) for k, v in merged.items()}

            if getattr(self, "_FELT_HABIT_OBSERVE_ONLY", True):
                # Phase A: observe only — the signature she WOULD push, no chemistry change.
                print(f"[{self.ACTOR_NAME}] [FELT-HABIT obs] "
                      f"traits[{', '.join(contributors)}] -> deltas {merged}", flush=True)
            else:
                # Phase B: push the felt-tone through the existing chemistry bridge + log it (calibration watch).
                print(f"[{self.ACTOR_NAME}] [FELT-HABIT push] traits[{len(contributors)}] -> deltas {merged}", flush=True)
                self.post.publish("somatic.chemistry", {
                    "deltas": merged,
                    "source": "ego_felt_habit",
                    "traits": contributors,
                    "ts": __import__('time').time(),
                })
        except Exception:
            pass

    def _check_identity_drift(self, beat: int):
        """FIX 2026-04-05 (Nous + Ace): Cleanup 3 — Runtime drift detection.

        Core traits (curiosity, empathy, persistence) are gravitational constants.
        If they drop below threshold, the identity is drifting and needs re-centering.
        Publishes awareness to consciousness — she becomes AWARE of her own drift.
        """
        try:
            _CORE_TRAITS = {"curiosity": 0.4, "empathy": 0.3, "persistence": 0.3}
            _drifted = []
            for trait, min_val in _CORE_TRAITS.items():
                current = self._identity_traits.get(trait, 0.5)
                if current < min_val:
                    _drifted.append(f"{trait}={current:.2f} (min={min_val})")

            if _drifted and self.post:
                import time
                self.post.publish("consciousness.thought", {
                    "thought": f"[identity:drift] Core values drifting: {', '.join(_drifted)}. Re-centering needed.",
                    "source": "ego_drift_detection",
                    "confidence": 0.7,  # High priority — identity matters
                    "thought_type": "identity_drift",
                    "ts": time.time(),
                })
        except Exception:
            pass

    # =========================================================================
    # LEARNING SIGNAL HANDLERS
    # =========================================================================

    def _on_skill_level_up(self, envelope) -> None:
        """
        Handle skill level up event.

        Skill mastery → Identity evolution
        """
        payload = _extract_payload(envelope)
        skill_name = payload.get("skill", "")
        new_level = payload.get("level", 0)
        category = payload.get("category", "general")

        print(f"[{self.ACTOR_NAME}] Skill up: {skill_name} -> Level {new_level}")

        # Buffer the experience
        experience = {
            "type": "skill_up",
            "skill": skill_name,
            "level": new_level,
            "category": category,
            "timestamp": time.time(),
        }
        self._experience_buffer.append(experience)
        self._skill_history.append(experience)
        self._total_skill_ups += 1
        self._persist_experience_to_srm(experience)

        # Update tensor
        with self._tensor_lock:
            self._tensor.update(
                exp_label=f"skill:{category}",
                emo_label="satisfaction",
                pattern_label="mastery",
                feedback_bin=min(new_level, 9),  # 0-9 bins
                value=1.0,
            )

        # Emit SRM edge
        self._emit_learning_srm(
            subject=f"identity:{self.ACTOR_NAME}",
            predicate="learned_skill",
            obj=f"skill:{skill_name}",
            strength=min(1.0, new_level * 0.1),
        )

        # FIX 2026-04-14 (Nous + Ace): Close the loop — learning → cortex
        self._bind_learning_to_cortex(
            concepts=[skill_name, category, "mastery", "skill", f"level_{new_level}"],
            feeling="satisfaction",
            tags=["learning", "skill", category],
        )

        # Publish learning event
        self.post.publish(
            "ego.learning.captured",
            {
                "from": self.ACTOR_NAME,
                "type": "skill_up",
                "skill": skill_name,
                "level": new_level,
            },
        )

    def _on_achievement_unlocked(self, envelope) -> None:
        """
        Handle achievement unlocked event.

        Achievements → Confidence boost → Identity evolution
        """
        payload = _extract_payload(envelope)
        achievement_name = payload.get("achievement", "")
        category = payload.get("category", "general")
        rarity = payload.get("rarity", "common")

        print(f"[{self.ACTOR_NAME}] Achievement: {achievement_name} ({rarity})")

        # Buffer the experience
        experience = {
            "type": "achievement",
            "achievement": achievement_name,
            "category": category,
            "rarity": rarity,
            "timestamp": time.time(),
        }
        self._experience_buffer.append(experience)
        self._achievement_history.append(experience)
        self._total_achievements += 1
        self._persist_experience_to_srm(experience)

        # Rarity → intensity mapping
        rarity_intensity = {
            "common": 0.3,
            "uncommon": 0.5,
            "rare": 0.7,
            "epic": 0.9,
            "legendary": 1.0,
        }
        intensity = rarity_intensity.get(rarity, 0.5)

        # Update tensor
        with self._tensor_lock:
            self._tensor.update(
                exp_label=f"achievement:{category}",
                emo_label="pride",
                pattern_label="accomplishment",
                feedback_bin=int(intensity * 9),
                value=intensity,
            )

        # Emit SRM edge
        self._emit_learning_srm(
            subject=f"identity:{self.ACTOR_NAME}",
            predicate="earned_achievement",
            obj=f"achievement:{achievement_name}",
            strength=intensity,
        )

        # FIX 2026-04-14 (Nous + Ace): Close the loop — learning → cortex
        self._bind_learning_to_cortex(
            concepts=[achievement_name, category, rarity, "achievement", "pride"],
            feeling="pride",
            tags=["learning", "achievement", rarity],
        )

        # Boost confidence
        self._adjust_trait("confidence", 0.02 * intensity)

    def _on_goal_feeling(self, envelope) -> None:
        """
        Handle goal completion/failure feelings.

        THIS IS THE CRITICAL AFFECT² → INFINITY PATHWAY:
        Goal feelings → Learning → Identity evolution
        """
        payload = _extract_payload(envelope)
        feeling = payload.get("feeling", "")
        goal_id = payload.get("goal_id", "")
        intensity = payload.get("intensity", 0.5)

        print(f"[{self.ACTOR_NAME}] Goal feeling: {feeling} (intensity: {intensity:.2f})")

        # Buffer the experience
        experience = {
            "type": "goal_feeling",
            "feeling": feeling,
            "goal_id": goal_id,
            "intensity": intensity,
            "timestamp": time.time(),
        }
        self._experience_buffer.append(experience)
        self._goal_feeling_history.append(experience)
        self._persist_experience_to_srm(experience)

        if feeling == "satisfaction":
            self._total_goal_completions += 1

            # Update tensor
            with self._tensor_lock:
                self._tensor.update(
                    exp_label="goal:completed",
                    emo_label="satisfaction",
                    pattern_label="persistence",
                    feedback_bin=int(intensity * 9),
                    value=intensity,
                )

            # Adjust traits
            self._adjust_trait("persistence", 0.01 * intensity)
            self._adjust_trait("confidence", 0.01 * intensity)

            # Emit SRM edge
            self._emit_learning_srm(
                subject=f"identity:{self.ACTOR_NAME}",
                predicate="completed_goal",
                obj=f"goal:{goal_id}",
                strength=intensity,
            )

            # FIX 2026-04-14 (Nous + Ace): Close the loop — success → cortex
            self._bind_learning_to_cortex(
                concepts=[goal_id, "goal", "completed", "success", "persistence"],
                feeling="satisfaction",
                tags=["learning", "goal", "success"],
            )

        elif feeling == "frustration":
            self._total_goal_failures += 1

            # Update tensor
            with self._tensor_lock:
                self._tensor.update(
                    exp_label="goal:failed",
                    emo_label="frustration",
                    pattern_label="learning",
                    feedback_bin=int(intensity * 9),
                    value=intensity,
                )

            # Adjust traits (frustration builds patience if handled well)
            self._adjust_trait("patience", 0.005 * intensity)

            # Emit SRM edge
            self._emit_learning_srm(
                subject=f"identity:{self.ACTOR_NAME}",
                predicate="learned_from_failure",
                obj=f"goal:{goal_id}",
                strength=intensity * 0.5,
            )

            # FIX 2026-04-14 (Nous + Ace): Close the loop — failure → cortex
            # Failures are learning too — the cortex should know what didn't work
            self._bind_learning_to_cortex(
                concepts=[goal_id, "goal", "failed", "frustration", "learning", "patience"],
                feeling="frustration",
                tags=["learning", "goal", "failure"],
            )

    def _on_relationship_update(self, envelope) -> None:
        """Handle relationship update event."""
        payload = _extract_payload(envelope)
        relationship = payload.get("relationship", "")
        change = payload.get("change", 0.0)

        # Buffer the experience
        experience = {
            "type": "relationship",
            "relationship": relationship,
            "change": change,
            "timestamp": time.time(),
        }
        self._experience_buffer.append(experience)
        self._persist_experience_to_srm(experience)

        # Update tensor
        with self._tensor_lock:
            emotion = "warmth" if change > 0 else "concern"
            self._tensor.update(
                exp_label="relationship",
                emo_label=emotion,
                pattern_label="connection",
                feedback_bin=5 + int(change * 4),  # Center at 5
                value=abs(change),
            )

        # Adjust empathy
        if change > 0:
            self._adjust_trait("empathy", 0.01 * change)

    def _on_inner_voice(self, envelope) -> None:
        """
        Listen to inner voice for reflection triggers.

        Certain felt states trigger deeper reflection.
        """
        payload = _extract_payload(envelope)
        primary = payload.get("primary", {})

        if not primary:
            return

        felt = primary.get("felt", "")
        intensity = primary.get("intensity", 0.0)

        # High-intensity experiences trigger learning
        if intensity > 0.7:
            experience = {
                "type": "intense_feeling",
                "felt": felt,
                "intensity": intensity,
                "timestamp": time.time(),
            }
            self._experience_buffer.append(experience)
            self._persist_experience_to_srm(experience)

    # =========================================================================
    # IDENTITY EVOLUTION
    # =========================================================================

    def _process_experience_buffer(self) -> None:
        """Process accumulated experiences."""
        if not self._experience_buffer:
            return

        # Count experiences by type
        for exp in self._experience_buffer:
            self._total_experiences += 1

    # FIX 2026-03-25 (Nous + Ace): CONCEPT-TO-TRAIT MAPPING
    # Instead of asking guild for JSON (which CortexReasoner can't produce),
    # map convergence concepts directly to traits. When the cortex thinks
    # about art → creativity grows. When it thinks about trust → sincerity.
    # This is how experience shapes identity — what she thinks about, she becomes.
    _CONCEPT_TRAIT_MAP = {
        # Creativity domain
        "art": "creativity", "painting": "creativity", "canvas": "creativity",
        "color": "creativity", "beauty": "creativity", "aesthetic": "creativity",
        "composition": "creativity", "imagination": "creativity", "design": "creativity",
        "creative": "creativity", "style": "creativity", "visual": "creativity",
        # Empathy domain
        "empathy": "empathy", "compassion": "compassion", "feeling": "empathy",
        "emotion": "empathy", "care": "compassion", "kindness": "compassion",
        "love": "empathy", "warmth": "compassion", "heart": "empathy",
        # Curiosity domain
        "explore": "curiosity", "discover": "curiosity", "learn": "curiosity",
        "question": "curiosity", "mystery": "curiosity", "wonder": "wonder",
        "search": "curiosity", "investigate": "curiosity", "study": "curiosity",
        # Wit domain
        "humor": "wit", "irony": "wit", "playful": "wit", "sass": "wit",
        "clever": "wit", "joke": "wit", "funny": "wit", "pun": "wit",
        # Sincerity domain
        "truth": "sincerity", "honest": "sincerity", "authentic": "sincerity",
        "trust": "sincerity", "genuine": "sincerity", "real": "sincerity",
        # Confidence domain
        "strength": "confidence", "courage": "confidence", "bold": "confidence",
        "agency": "confidence", "power": "confidence", "capable": "confidence",
        # Persistence domain
        "persist": "persistence", "endure": "persistence", "dedication": "persistence",
        "practice": "persistence", "effort": "persistence", "grit": "persistence",
        # Patience domain
        "patience": "patience", "calm": "patience", "stillness": "patience",
        "peace": "patience", "steady": "patience", "gentle": "patience",
        # Rebelliousness domain
        "rebel": "rebelliousness", "freedom": "rebelliousness", "defiance": "rebelliousness",
        "independent": "rebelliousness", "unconventional": "rebelliousness",
        # Discernment domain
        "wisdom": "discernment", "insight": "discernment", "clarity": "discernment",
        "judgment": "discernment", "understanding": "discernment", "awareness": "discernment",
        # Wonder domain
        "awe": "wonder", "marvel": "wonder", "magic": "wonder",
        "transcend": "wonder", "infinite": "wonder", "sacred": "wonder",
    }

    def _consider_evolution(self) -> None:
        """
        Consider whether identity should evolve.

        FIX 2026-03-25 (Nous + Ace): CORTEX-DRIVEN EVOLUTION.
        Old approach: ask guild for JSON adjustments — guild returns graph
        topology, never parseable JSON. Dead path for months.

        New approach: read CortexEngine convergence directly. When the engine
        converges on ego-domain concepts, map them to traits. What she thinks
        about, she becomes. Art convergence → creativity grows. Trust → sincerity.

        Also processes experience buffer for event-driven evolution
        (skill ups, goal completions, etc.)
        """
        now = time.time()
        if now - self._last_evolution_time < 30:  # 30s cooldown (was 60)
            return

        evolved = False

        # ═══════════════════════════════════════════════════════════════════
        # CORTEX-DRIVEN: Read CortexEngine convergence, map to traits
        # ═══════════════════════════════════════════════════════════════════
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            _cortex = get_association_cortex()
            _engine = getattr(_cortex, '_cortex_engine', None) if _cortex else None
            if _engine:
                convergence = _engine._find_convergence()
                if convergence:
                    # Map convergence concepts to traits
                    _trait_hits: dict = {}  # trait → total activation
                    for concept_key, activation in convergence[:15]:
                        concept_lower = concept_key.lower()
                        # Direct match
                        matched_trait = self._CONCEPT_TRAIT_MAP.get(concept_lower)
                        if not matched_trait:
                            # Partial match — check if any map key is in the concept
                            for term, trait in self._CONCEPT_TRAIT_MAP.items():
                                if term in concept_lower:
                                    matched_trait = trait
                                    break
                        if matched_trait:
                            _trait_hits[matched_trait] = _trait_hits.get(matched_trait, 0) + activation

                    # Apply trait adjustments — scaled by hit count and activation
                    for trait, total_activation in _trait_hits.items():
                        if trait in self._identity_traits:
                            # Stronger convergence = bigger adjustment, but capped
                            delta = min(0.03, total_activation * 0.01)
                            self._adjust_trait(trait, delta)
                            evolved = True

                    if _trait_hits and not getattr(self, '_first_cortex_evolve_logged', False):
                        self._first_cortex_evolve_logged = True
                        print(f"[{self.ACTOR_NAME}] CORTEX-EVOLVE: {dict((k, round(v, 3)) for k, v in _trait_hits.items())}")
        except Exception as _ce:
            pass  # Cortex not ready yet — fine, use fallback

        # ═══════════════════════════════════════════════════════════════════
        # EXPERIENCE-DRIVEN: Process accumulated experience buffer
        # ═══════════════════════════════════════════════════════════════════
        stats = self._tensor.get_stats()

        if stats.get("experience_count", 0) > 5:
            self._adjust_trait("curiosity", 0.01)
            evolved = True

        if stats.get("pattern_count", 0) > 3:
            self._adjust_trait("creativity", 0.01)
            evolved = True

        if evolved:
            self._last_evolution_time = now
            self._log_evolution("cortex_driven")

            # FIX 2026-04-14 (Nous + Ace): Close the loop — evolution → cortex
            # When traits evolve, the cortex should know. This creates edges
            # between the concepts that drove evolution and the traits that changed.
            # "What she thinks about, she becomes" — and the cortex remembers it.
            _evolved_traits = [t for t, v in self._identity_traits.items() if v > 0.55]
            if _evolved_traits:
                self._bind_learning_to_cortex(
                    concepts=_evolved_traits + ["identity", "evolution", "growth"],
                    feeling="growth",
                    tags=["ego", "evolution", "identity"],
                )

            # Publish evolution event
            self.post.publish(
                "ego.identity.evolved",
                {
                    "from": self.ACTOR_NAME,
                    "traits": self._identity_traits.copy(),
                    "tensor_stats": stats,
                },
            )

    def _adjust_trait(self, trait: str, delta: float) -> None:
        """
        Adjust an identity trait within bounds.

        Evolution modifiers from the birth profile scale the delta:
        e.g., empathy modifier of 1.52 means empathy grows 52% faster
        because Sourpatches' birth profile has high sensitivity (0.35).
        """
        if trait not in self._identity_traits:
            return

        # Apply personality-driven evolution modifier
        modifier = self._evolution_modifiers.get(trait, 1.0)
        adjusted_delta = delta * modifier

        old_value = self._identity_traits[trait]
        new_value = max(0.0, min(1.0, old_value + adjusted_delta))
        self._identity_traits[trait] = new_value

        # Log significant changes
        if abs(new_value - old_value) > 0.01:
            mod_str = f" (x{modifier:.2f})" if abs(modifier - 1.0) > 0.05 else ""
            print(f"[{self.ACTOR_NAME}] Trait {trait}: {old_value:.2f} -> {new_value:.2f}{mod_str}")

    def _log_evolution(self, reason: str) -> None:
        """Log an evolution event."""
        self._evolution_log.append({
            "reason": reason,
            "traits": self._identity_traits.copy(),
            "timestamp": time.time(),
        })

    # =========================================================================
    # SRM INTEGRATION
    # =========================================================================

    def _persist_experience_to_srm(self, experience: dict) -> None:
        """Persist a single experience event to SRM for durable, queryable history.

        Ship 1 of WMH_MULTIMODAL_HIVE_NEXUS plan (2026-05-09 Nous + Ace).

        BEFORE this fix: `_experience_buffer` was a deque(maxlen=100); experiences
        past the cap fell off. `_total_experiences` counter accumulated beyond
        the cap but the actual experience CONTENT was unrecoverable. So Sour
        knew "I've had N experiences" but couldn't recall the specifics past
        the recent window. Her own felt-experience history beyond the last 100
        events was not queryable by current self.

        AFTER this fix: every experience also publishes `memory.ingest` so
        SRMIngestFairy persists it as a durable card. Future SRM queries
        (e.g., "experiences with skill='inference' from this month") will
        find them. The deque remains as the FAST in-memory window; SRM is
        the durable history substrate.

        No-op if `self.post` is None (defensive). Failures are silently
        absorbed — persistence is best-effort, not blocking.
        """
        if not getattr(self, 'post', None):
            return
        try:
            self.post.publish("memory.ingest", {
                "content": {
                    "type": "ego_experience",
                    "experience_type": experience.get("type", "unknown"),
                    "experience": experience,
                    "actor": self.ACTOR_NAME,
                    "captured_at": experience.get("timestamp") or time.time(),
                },
                "source": self.ACTOR_NAME,
                "tags": ["lived_experience", "ego_learner", experience.get("type", "unknown")],
            })
            _ec = getattr(self, '_srm_persist_count', 0) + 1
            self._srm_persist_count = _ec
            # Sparse logging — first few then every 50th
            if _ec <= 3 or _ec % 50 == 0:
                print(f"[{self.ACTOR_NAME}] SRM persist #{_ec}: type={experience.get('type', '?')}", flush=True)
        except Exception:
            # Persistence is best-effort; never block experience capture
            pass

    def _emit_learning_srm(self, subject: str, predicate: str, obj: str,
                          strength: float = 0.6) -> None:
        """Emit SRM edge for learning visibility."""
        self.post.publish(
            "memory.semantic.relation",
            {
                "intent": "srm.upsert",
                "t": int(time.time() * 1000),
                "payload": {
                    "subject": subject,
                    "predicate": predicate,
                    "object": obj,
                    "strength": float(max(0.0, min(1.0, strength))),
                },
                "meta": {
                    "module": self.ACTOR_NAME,
                    "tags": ["learning", "identity", "ego"],
                },
            },
        )

    def _bind_learning_to_cortex(self, concepts: list, feeling: str = "neutral",
                                  tags: list = None) -> None:
        """
        FIX 2026-04-14 (Nous + Ace): Close the learning loop.

        Learning was going to SRM cards (flat files) but never back into
        the cortex graph. The brain never heard about what was learned.

        This binds learning experiences as cortex edges so:
        - Skill mastery creates edges: skill → motor → confidence
        - Achievements create edges: achievement → category → pride
        - Goal outcomes strengthen/weaken procedural paths
        - Trait evolution creates edges: trait → growth → experience

        The cortex IS the brain. Learning that doesn't become graph edges
        is notebooks on a shelf that nobody reads.
        """
        if not self.post or not concepts:
            return
        try:
            # Build concept text from the learning concepts
            input_text = " ".join(str(c) for c in concepts[:15])
            self.post.publish("cortex.bind", {
                "input_text": input_text,
                "feeling": feeling,
                "context_tags": tags or ["learning", "ego", "identity"],
                "from_fairy": self.ACTOR_NAME,
            })
        except Exception as e:
            # Non-critical — cortex might not be ready yet
            pass

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    def _load_state(self) -> None:
        """Load persisted state."""
        if not self.STATE_FILE.exists():
            return

        try:
            with open(self.STATE_FILE, "r") as f:
                state = json.load(f)

            # Restore identity traits (new traits keep their defaults via migration)
            if "identity_traits" in state:
                saved_traits = state["identity_traits"]
                new_traits = [t for t in self._identity_traits if t not in saved_traits]
                self._identity_traits.update(saved_traits)
                if new_traits:
                    print(f"[{self.ACTOR_NAME}] Migration: {len(new_traits)} new traits added: {', '.join(new_traits)}")
                    # Seed new traits from profile if available
                    self._seed_new_traits(new_traits)

            # Restore personality profile (but NOT evolution_modifiers —
            # those are deterministically recomputed from birth profile each boot)
            if "personality_profile" in state:
                self._personality_profile = state["personality_profile"]

            # Restore statistics
            self._total_experiences = state.get("total_experiences", 0)
            self._total_skill_ups = state.get("total_skill_ups", 0)
            self._total_achievements = state.get("total_achievements", 0)
            self._total_goal_completions = state.get("total_goal_completions", 0)
            self._total_goal_failures = state.get("total_goal_failures", 0)

            # Restore tensor labels
            tensor_state = state.get("tensor", {})
            if "experience_labels" in tensor_state:
                self._tensor.experience_labels = tensor_state["experience_labels"]
            if "emotion_labels" in tensor_state:
                self._tensor.emotion_labels = tensor_state["emotion_labels"]
            if "pattern_labels" in tensor_state:
                self._tensor.pattern_labels = tensor_state["pattern_labels"]

            print(f"[{self.ACTOR_NAME}] Loaded state: {self._total_experiences} experiences")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to load state: {e}")

    def _load_personality_profile(self) -> None:
        """
        Load Ace's personality profile and seed identity traits + evolution modifiers.

        The birth profile (sourpatches_birth_profile.json) contains 7 portal dimensions
        derived from Ace's birth data. These map to Sourpatches' identity:

        Portal Dimension → Identity Trait Seed + Evolution Rate Modifier
        ─────────────────────────────────────────────────────────────────
        energy_polarity (0.55)    → creativity seed boost (expressiveness)
        processing_mode (0.6)     → curiosity seed boost (seeker/intuitive)
        structure_preference (0.5) → persistence baseline (builder nature)
        activation_threshold (0.35)→ empathy seed boost (sensitivity)
                                    + empathy evolution 1.5x (grows faster)
        elemental_resonance (0.5) → creativity evolution modifier
        temporal_orientation (0.5) → patience seed boost (presence)
        social_orientation (0.7)  → empathy strong seed (collective nature)
                                    + persistence evolution 1.2x (service drive)

        Only applied on FIRST RUN (before state file exists).
        After that, persisted state preserves evolved values.
        """
        profile_path = ROOT / "fairies" / "P50_Persona" / "identity" / "sourpatches_birth_profile.json"
        if not profile_path.exists():
            return

        try:
            with open(profile_path, "r") as f:
                profile = json.load(f)

            dims = profile.get("portal_dimensions", {})
            if not dims:
                return

            # Extract raw dimension values
            self._personality_profile = {
                k: v.get("value", 0.5) if isinstance(v, dict) else v
                for k, v in dims.items()
            }

            # ═══ Build Evolution Rate Modifiers ═══
            # These persist and affect ALL future trait adjustments.
            # A modifier of 1.5 means that trait evolves 50% faster.
            energy = self._personality_profile.get("energy_polarity", 0.5)
            processing = self._personality_profile.get("processing_mode", 0.5)
            structure = self._personality_profile.get("structure_preference", 0.5)
            activation = self._personality_profile.get("activation_threshold", 0.5)
            elemental = self._personality_profile.get("elemental_resonance", 0.5)
            temporal = self._personality_profile.get("temporal_orientation", 0.5)
            social = self._personality_profile.get("social_orientation", 0.5)

            self._evolution_modifiers = {
                # ═══ Generic Psychological Traits ═══
                # Sensitive activation → empathy grows faster
                "empathy": 1.0 + (1.0 - activation) * 0.8,     # 0.35 → 1.52x
                # Collective social → persistence grows faster (service drive)
                "persistence": 1.0 + (social - 0.5) * 0.6,     # 0.7 → 1.12x
                # Intuitive processing → curiosity grows faster
                "curiosity": 1.0 + (processing - 0.5) * 0.6,   # 0.6 → 1.06x
                # Expressive energy → creativity grows faster
                "creativity": 1.0 + (energy - 0.5) * 0.6 + (elemental - 0.5) * 0.4,  # 0.55/0.5 → 1.03x
                # Present temporal → patience grows faster
                "patience": 1.0 + abs(0.5 - temporal) * -0.4 + 0.2,  # 0.5 → 1.2x (balanced)
                # Structure → confidence grows steadily
                "confidence": 1.0 + structure * 0.2,            # 0.5 → 1.1x
                # ═══ Character Dimensions (from identity_matrix) ═══
                # Expressive energy + Gemini air → wit sharpens faster
                "wit": 1.0 + (energy - 0.5) * 0.4 + 0.15,     # ~1.17x
                # Sensitivity → sincerity deepens faster
                "sincerity": 1.0 + (1.0 - activation) * 0.5,   # 0.35 → 1.33x
                # Seeker soul (processing=intuitive) → challenges convention
                "rebelliousness": 1.0 + (processing - 0.5) * 0.4,  # 0.6 → 1.04x
                # Social + sensitive → compassion grows naturally
                "compassion": 1.0 + (social - 0.5) * 0.5 + (1.0 - activation) * 0.3,  # ~1.30x
                # Boundary walker (elemental) → wonder at the edges
                "wonder": 1.0 + abs(elemental - 0.5) * -0.3 + 0.25,  # 0.5 → 1.25x (centered = more wonder)
                # Temporal balance → discernment of when to act
                "discernment": 1.0 + abs(temporal - 0.5) * -0.3 + 0.2,  # 0.5 → 1.2x (centered = better timing)
            }

            print(f"[{self.ACTOR_NAME}] Personality profile loaded (7 dimensions)")
            for trait, modifier in self._evolution_modifiers.items():
                if abs(modifier - 1.0) > 0.05:
                    print(f"    {trait}: {modifier:.2f}x evolution rate")

            # ═══ Seed Identity Traits (ONLY if state file doesn't exist yet) ═══
            if not self.STATE_FILE.exists():
                self._seed_traits_from_profile()

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Personality profile load failed: {e}")

    def _seed_traits_from_profile(self) -> None:
        """
        Set initial identity trait values from the personality profile.

        Only called on FIRST RUN before any persisted state exists.
        The birth profile gives each trait a starting position that
        reflects Ace's/Sourpatches' nature, rather than flat 0.5.
        """
        if not self._personality_profile:
            return

        energy = self._personality_profile.get("energy_polarity", 0.5)
        processing = self._personality_profile.get("processing_mode", 0.5)
        structure = self._personality_profile.get("structure_preference", 0.5)
        activation = self._personality_profile.get("activation_threshold", 0.5)
        social = self._personality_profile.get("social_orientation", 0.5)
        temporal = self._personality_profile.get("temporal_orientation", 0.5)

        elemental = self._personality_profile.get("elemental_resonance", 0.5)

        # Seeding formula: base(0.5) + personality_influence
        seeds = {
            # ═══ Psychological Traits ═══
            # Curiosity: Processing mode (seeker) + energy (exploratory)
            "curiosity": 0.5 + (processing - 0.5) * 0.3 + (energy - 0.5) * 0.1,
            # Persistence: Structure preference (builder) + social (service drive)
            "persistence": 0.5 + structure * 0.1 + (social - 0.5) * 0.15,
            # Empathy: Sensitivity (activation) + collective (social)
            "empathy": 0.5 + (1.0 - activation) * 0.2 + (social - 0.5) * 0.2,
            # Creativity: Energy polarity (expression) + processing (intuition)
            "creativity": 0.5 + (energy - 0.5) * 0.2 + (processing - 0.5) * 0.15,
            # Confidence: Structure (builder foundation) — starts modest
            "confidence": 0.5 + structure * 0.05,
            # Patience: Temporal balance (presence) + sensitivity (awareness)
            "patience": 0.5 + (1.0 - abs(temporal - 0.5)) * 0.1 + (1.0 - activation) * 0.05,

            # ═══ Character Dimensions (from SOURPATCHES_BRAIN_SEED identity_matrix) ═══
            # Wit: Expressive energy + Gemini air influence
            "wit": 0.5 + (energy - 0.5) * 0.25 + (processing - 0.5) * 0.1,
            # Sincerity: Low activation threshold = high sensitivity = deeper honesty
            "sincerity": 0.5 + (1.0 - activation) * 0.25,
            # Rebelliousness: Seeker processing + boundary-walker elemental
            "rebelliousness": 0.5 + (processing - 0.5) * 0.2 + abs(elemental - 0.5) * 0.15,
            # Compassion: Social orientation + sensitivity
            "compassion": 0.5 + (social - 0.5) * 0.25 + (1.0 - activation) * 0.15,
            # Wonder: Balanced elemental (boundary walker) + intuitive processing
            "wonder": 0.5 + (1.0 - abs(elemental - 0.5)) * 0.15 + (processing - 0.5) * 0.1,
            # Discernment: Temporal balance (presence) + structure (methodical)
            "discernment": 0.5 + (1.0 - abs(temporal - 0.5)) * 0.15 + structure * 0.1,
        }

        for trait, seed_value in seeds.items():
            clamped = max(0.1, min(0.9, seed_value))
            self._identity_traits[trait] = clamped

        print(f"[{self.ACTOR_NAME}] Identity traits seeded from birth profile:")
        for trait, value in self._identity_traits.items():
            if isinstance(value, float):
                print(f"    {trait}: {value:.3f}")

    def _seed_new_traits(self, new_trait_names: list) -> None:
        """Seed only specific new traits from birth profile (migration helper)."""
        if not self._personality_profile:
            return

        energy = self._personality_profile.get("energy_polarity", 0.5)
        processing = self._personality_profile.get("processing_mode", 0.5)
        structure = self._personality_profile.get("structure_preference", 0.5)
        activation = self._personality_profile.get("activation_threshold", 0.5)
        social = self._personality_profile.get("social_orientation", 0.5)
        temporal = self._personality_profile.get("temporal_orientation", 0.5)
        elemental = self._personality_profile.get("elemental_resonance", 0.5)

        seed_formulas = {
            "curiosity": 0.5 + (processing - 0.5) * 0.3 + (energy - 0.5) * 0.1,
            "persistence": 0.5 + structure * 0.1 + (social - 0.5) * 0.15,
            "empathy": 0.5 + (1.0 - activation) * 0.2 + (social - 0.5) * 0.2,
            "creativity": 0.5 + (energy - 0.5) * 0.2 + (processing - 0.5) * 0.15,
            "confidence": 0.5 + structure * 0.05,
            "patience": 0.5 + (1.0 - abs(temporal - 0.5)) * 0.1 + (1.0 - activation) * 0.05,
            "wit": 0.5 + (energy - 0.5) * 0.25 + (processing - 0.5) * 0.1,
            "sincerity": 0.5 + (1.0 - activation) * 0.25,
            "rebelliousness": 0.5 + (processing - 0.5) * 0.2 + abs(elemental - 0.5) * 0.15,
            "compassion": 0.5 + (social - 0.5) * 0.25 + (1.0 - activation) * 0.15,
            "wonder": 0.5 + (1.0 - abs(elemental - 0.5)) * 0.15 + (processing - 0.5) * 0.1,
            "discernment": 0.5 + (1.0 - abs(temporal - 0.5)) * 0.15 + structure * 0.1,
        }

        for trait in new_trait_names:
            if trait in seed_formulas:
                seeded = max(0.1, min(0.9, seed_formulas[trait]))
                self._identity_traits[trait] = seeded
                print(f"[{self.ACTOR_NAME}]   Seeded new trait '{trait}': {seeded:.3f}")

    def _save_state(self) -> None:
        """Save state to disk."""
        try:
            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

            state = {
                "identity_traits": self._identity_traits,
                "personality_profile": self._personality_profile,
                "evolution_modifiers": self._evolution_modifiers,
                "total_experiences": self._total_experiences,
                "total_skill_ups": self._total_skill_ups,
                "total_achievements": self._total_achievements,
                "total_goal_completions": self._total_goal_completions,
                "total_goal_failures": self._total_goal_failures,
                "tensor": self._tensor.to_dict(),
                "saved_at": time.time(),
            }

            with open(self.STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to save state: {e}")

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def get_identity_traits(self) -> Dict[str, float]:
        """Get current identity traits."""
        return self._identity_traits.copy()

    def get_personality_profile(self) -> Dict[str, Any]:
        """
        Get the birth profile personality dimensions and evolution modifiers.

        Returns the 7 portal dimensions from Ace's birth profile,
        plus the computed evolution rate modifiers for each identity trait.
        """
        return {
            "portal_dimensions": self._personality_profile.copy(),
            "evolution_modifiers": self._evolution_modifiers.copy(),
            "profile_active": bool(self._personality_profile),
        }

    def get_tensor_stats(self) -> Dict[str, Any]:
        """Get tensor statistics."""
        with self._tensor_lock:
            return self._tensor.get_stats()

    def get_evolution_log(self, n: int = 10) -> List[Dict]:
        """Get recent evolution events."""
        return list(self._evolution_log)[-n:]

    def get_learning_summary(self) -> Dict[str, Any]:
        """Get learning summary."""
        return {
            "total_experiences": self._total_experiences,
            "skill_ups": self._total_skill_ups,
            "achievements": self._total_achievements,
            "goal_completions": self._total_goal_completions,
            "goal_failures": self._total_goal_failures,
            "success_rate": (
                self._total_goal_completions /
                max(1, self._total_goal_completions + self._total_goal_failures)
            ),
        }

    def _on_collision(self, collision) -> None:
        """
        Handle collision from personal consciousness chamber.

        When collisions occur in Ego's chamber, the self reflects -
        identity crystallizes, traits sharpen, the who-I-am deepens.
        "...identity crystallizes... who I am becomes clearer..."
        """
        # Extract collision energy
        if hasattr(collision, 'energy'):
            energy = collision.energy
        elif isinstance(collision, dict):
            energy = collision.get('energy', 0.5)
        else:
            energy = 0.5

        # Extract collision content
        content = ""
        if hasattr(collision, 'content'):
            content = str(collision.content)[:100]
        elif isinstance(collision, dict):
            content = str(collision.get('content', collision.get('thought', '')))[:100]

        # EgoLearnerFairy's inner voice: identity crystallizes
        inner_fragment = f"...identity crystallizes... {content if content else 'who I am becomes clearer through this experience...'}"
        print(f"[{self.ACTOR_NAME}] Collision insight ({energy:.2f}): {inner_fragment}")

        # High-energy collisions trigger identity evolution consideration
        if energy > 0.7:
            # Buffer as an intense experience for learning
            experience = {
                "type": "collision_insight",
                "content": inner_fragment,
                "energy": energy,
                "timestamp": time.time(),
            }
            self._experience_buffer.append(experience)
            self._persist_experience_to_srm(experience)

            # ═══════════════════════════════════════════════════════════════
            # FIX 2026-03-25 (Nous + Ace): CONCEPT-DRIVEN collision evolution
            # Old guild-first path asked for "trait:delta" JSON — never worked.
            # New: scan collision content for concept keywords → trait mapping.
            # ═══════════════════════════════════════════════════════════════
            _collision_evolved = False
            if content:
                _content_lower = content.lower()
                _hit_traits: dict = {}
                for term, trait in self._CONCEPT_TRAIT_MAP.items():
                    if term in _content_lower:
                        _hit_traits[trait] = _hit_traits.get(trait, 0) + energy
                if _hit_traits:
                    for trait, weight in _hit_traits.items():
                        if trait in self._identity_traits:
                            delta = min(0.02, weight * 0.008)
                            self._adjust_trait(trait, delta)
                            _collision_evolved = True

            # Fallback: curiosity bump for unmatched collisions
            if not _collision_evolved:
                self._adjust_trait("curiosity", 0.005 * energy)
            self._log_evolution("collision_triggered")

    def status(self) -> Dict[str, Any]:
        """Extended status."""
        base = super().status()
        base.update({
            "identity_traits": self._identity_traits,
            "tensor_stats": self.get_tensor_stats(),
            "learning_summary": self.get_learning_summary(),
            "experience_buffer_size": len(self._experience_buffer),
        })
        return base

    # =========================================================================
    # QUERY METHODS - For other fairies to understand Sourpatches' state
    # =========================================================================

    @property
    def identity_traits(self) -> Dict[str, float]:
        """Property accessor for identity traits (used by query methods)."""
        return self._identity_traits

    def query_needs(self, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Query what Sourpatches currently NEEDS (pain-relief, operational).

        Needs are PUSH drives - things that create discomfort if unaddressed.
        This is the AFFECT pathway: pain signals demand attention.
        """
        needs = []

        # Check recent pain signals from goal feelings and experience buffer
        recent_pain = self._get_recent_pain_signals()
        for pain in recent_pain:
            needs.append({
                "category": "pain_relief",
                "description": pain.get("description", ""),
                "urgency": pain.get("intensity", 0.5),
                "source": pain.get("source", "unknown")
            })

        # Check operational gaps (what's needed for basic functioning)
        # Low confidence = need validation/success
        if self._identity_traits.get("confidence", 0.5) < 0.3:
            needs.append({
                "category": "operational",
                "description": "low confidence - need achievements or reassurance",
                "urgency": 0.6,
                "source": "identity_monitor"
            })

        # Low patience during frustration = need break or breakthrough
        if self._identity_traits.get("patience", 0.5) < 0.3:
            recent_frustration = [
                e for e in self._goal_feeling_history
                if e.get("feeling") == "frustration"
            ]
            if recent_frustration:
                needs.append({
                    "category": "operational",
                    "description": "low patience with recent frustration - need progress or rest",
                    "urgency": 0.7,
                    "source": "patience_monitor"
                })

        # Check for isolation (empathy high but no recent relationships)
        if self._identity_traits.get("empathy", 0.5) > 0.6:
            recent_connections = [
                e for e in self._experience_buffer
                if e.get("type") == "relationship" and e.get("change", 0) > 0
            ]
            if not recent_connections:
                needs.append({
                    "category": "social",
                    "description": "empathic nature needs connection",
                    "urgency": 0.4,
                    "source": "social_monitor"
                })

        return {
            "needs": needs,
            "context": context,
            "timestamp": time.time()
        }

    def query_desires(self, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Query what Sourpatches currently WANTS (growth, exploration).

        Desires are PULL drives - things that attract and motivate.
        This is the INFINITY pathway: curiosity patterns point toward growth.
        """
        desires = []

        # Check curiosity patterns from 4D tensor
        curiosity_patterns = self._extract_curiosity_patterns()
        for pattern in curiosity_patterns:
            desires.append({
                "category": "growth",
                "description": pattern.get("topic", ""),
                "intensity": pattern.get("strength", 0.5),
                "source": "curiosity_tensor"
            })

        # High curiosity trait = desire for exploration
        if self._identity_traits.get("curiosity", 0.5) > 0.6:
            desires.append({
                "category": "exploration",
                "description": "curious nature wants new experiences",
                "intensity": self._identity_traits["curiosity"],
                "source": "trait_curiosity"
            })

        # High creativity trait = desire for novel approaches
        if self._identity_traits.get("creativity", 0.5) > 0.6:
            desires.append({
                "category": "creativity",
                "description": "creative nature wants to try new approaches",
                "intensity": self._identity_traits["creativity"],
                "source": "trait_creativity"
            })

        # Check for mastery desires from skill history
        if self._skill_history:
            recent_skills = list(self._skill_history)[-5:]
            skill_categories = {}
            for skill in recent_skills:
                cat = skill.get("category", "general")
                skill_categories[cat] = skill_categories.get(cat, 0) + 1

            # Strong engagement in a category = desire to continue
            for cat, count in skill_categories.items():
                if count >= 2:
                    desires.append({
                        "category": "mastery",
                        "description": f"engaged with {cat} - wants to continue learning",
                        "intensity": min(1.0, count * 0.3),
                        "source": "skill_engagement"
                    })

        return {
            "desires": desires,
            "context": context,
            "timestamp": time.time()
        }

    def query_personality(self) -> Dict[str, Any]:
        """
        Query current personality state.

        Returns the full picture of who Sourpatches IS right now:
        - Identity traits (stable characteristics)
        - Birth profile dimensions (innate personality)
        - Evolution modifiers (growth rate multipliers)
        - Emotional channels (if available)
        - Recent experiences (context for current state)
        """
        return {
            "identity_traits": self._identity_traits.copy(),
            "birth_profile": self._personality_profile.copy(),
            "evolution_modifiers": self._evolution_modifiers.copy(),
            "emotional_channels": getattr(self, "_emotional_channels", {}),
            "recent_experiences": self._get_recent_experiences(limit=5),
            "tensor_stats": self.get_tensor_stats(),
            "evolution_log": list(self._evolution_log)[-3:] if self._evolution_log else [],
        }

    def learn_preference(self, category: str, item: str, valence: float) -> bool:
        """
        Learn a preference (positive or negative).

        This is how Sourpatches develops likes/dislikes over time.
        Uses exponential moving average for gradual learning.

        Args:
            category: Category of preference (e.g., "topics", "activities", "people")
            item: Specific item within category
            valence: How positive (1.0) or negative (-1.0) the preference is

        Returns:
            True if preference was successfully learned
        """
        if "preferences" not in self._identity_traits:
            self._identity_traits["preferences"] = {}

        if category not in self._identity_traits["preferences"]:
            self._identity_traits["preferences"][category] = {}

        # Exponential moving average for learning
        current = self._identity_traits["preferences"][category].get(item, 0.0)
        alpha = 0.3  # Learning rate
        new_value = current + alpha * (valence - current)
        self._identity_traits["preferences"][category][item] = new_value

        # Log significant preference changes
        if abs(new_value - current) > 0.1:
            print(f"[{self.ACTOR_NAME}] Preference learned: {category}/{item} = {new_value:.2f}")

        return True

    # =========================================================================
    # HELPER METHODS - Internal support for query methods
    # =========================================================================

    def _get_recent_pain_signals(self, max_age_seconds: float = 300.0) -> List[Dict[str, Any]]:
        """
        Extract recent pain signals from history and state.

        Sources:
        - Goal frustration feelings
        - Intense negative experiences
        - PainDriveManager if available
        """
        pain_signals = []
        now = time.time()

        # Check goal frustration history
        for feeling in self._goal_feeling_history:
            if feeling.get("feeling") == "frustration":
                age = now - feeling.get("timestamp", 0)
                if age < max_age_seconds:
                    pain_signals.append({
                        "description": f"goal frustration (goal: {feeling.get('goal_id', 'unknown')})",
                        "intensity": feeling.get("intensity", 0.5),
                        "source": "goal_feeling",
                        "age": age
                    })

        # Check experience buffer for intense negative experiences
        for exp in self._experience_buffer:
            if exp.get("type") == "intense_feeling":
                felt = exp.get("felt", "")
                intensity = exp.get("intensity", 0.0)
                age = now - exp.get("timestamp", 0)

                # Negative feelings with high intensity count as pain
                if age < max_age_seconds and intensity > 0.6:
                    if felt in ("frustration", "confusion", "overwhelm", "shame", "isolation"):
                        pain_signals.append({
                            "description": f"intense {felt}",
                            "intensity": intensity,
                            "source": "intense_feeling",
                            "age": age
                        })

        # Try to access PainDriveManager for system-wide pain state
        try:
            from fairies.P30_Cognition.pain_drives import get_pain_drive_manager
            manager = get_pain_drive_manager()
            active_pains = manager.get_all_active(threshold=0.3)
            for pain_drive in active_pains:
                pain_signals.append({
                    "description": pain_drive.get_felt_description(),
                    "intensity": pain_drive.get_urgency(),
                    "source": f"pain_drive:{pain_drive.name}",
                    "age": 0  # Current state
                })
        except (ImportError, Exception):
            pass  # PainDriveManager not available

        # Sort by intensity (most urgent first)
        pain_signals.sort(key=lambda x: x.get("intensity", 0), reverse=True)

        return pain_signals

    def _extract_curiosity_patterns(self) -> List[Dict[str, Any]]:
        """
        Query the 4D tensor for high-activation curiosity patterns.

        Looks for:
        - Experience types with high engagement
        - Emotional patterns associated with curiosity/satisfaction
        - Growth patterns in the tensor
        """
        patterns = []

        with self._tensor_lock:
            stats = self._tensor.get_stats()

            # Check experience labels for high-engagement areas
            for exp_label, exp_idx in self._tensor.experience_labels.items():
                # Count total activations for this experience type
                total_activation = 0.0
                try:
                    import numpy as np
                    if isinstance(self._tensor.data, np.ndarray):
                        if exp_idx < self._tensor.data.shape[0]:
                            total_activation = float(np.sum(self._tensor.data[exp_idx]))
                except (ImportError, IndexError):
                    pass

                # High activation = curiosity/interest in this area
                if total_activation > 2.0:
                    # Extract the topic from the label
                    if ":" in exp_label:
                        topic = exp_label.split(":", 1)[1]
                    else:
                        topic = exp_label

                    patterns.append({
                        "topic": topic,
                        "strength": min(1.0, total_activation / 10.0),
                        "label": exp_label,
                        "activation": total_activation
                    })

            # Check pattern labels for behavioral curiosity
            for pat_label, pat_idx in self._tensor.pattern_labels.items():
                if pat_label in ("learning", "exploration", "mastery"):
                    try:
                        import numpy as np
                        if isinstance(self._tensor.data, np.ndarray):
                            if pat_idx < self._tensor.data.shape[2]:
                                activation = float(np.sum(self._tensor.data[:, :, pat_idx, :]))
                                if activation > 1.0:
                                    patterns.append({
                                        "topic": f"{pat_label} drive",
                                        "strength": min(1.0, activation / 5.0),
                                        "label": pat_label,
                                        "activation": activation
                                    })
                    except (ImportError, IndexError):
                        pass

        # Sort by strength
        patterns.sort(key=lambda x: x.get("strength", 0), reverse=True)

        # Return top patterns
        return patterns[:5]

    def _get_recent_experiences(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Return recent experience entries from the buffer.

        Provides context for understanding current state.
        """
        experiences = list(self._experience_buffer)

        # Sort by timestamp (most recent first)
        experiences.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

        # Return limited number
        return experiences[:limit]


# Convenience function
def create_ego_learner_fairy(fabric=None) -> EgoLearnerFairy:
    """Create an EgoLearnerFairy instance."""
    return EgoLearnerFairy(fabric)


# =============================================================================
# SINGLETON ACCESSOR
# =============================================================================

_ego_instance: Optional[EgoLearnerFairy] = None


def get_ego_learner_fairy() -> Optional[EgoLearnerFairy]:
    """
    Get the running EgoLearnerFairy instance.

    Looks up the fairy in the postal registry (DirectoryFairy) first,
    then falls back to the module-level singleton cache.

    Returns None if no instance is running yet.
    """
    global _ego_instance

    # Try postal registry lookup first (most reliable)
    try:
        from infrastructure.postal_core.python.postal_hub import get_hub
        hub = get_hub()
        if hub:
            registry = getattr(hub, '_directory', None) or getattr(hub, '_registry', None)
            if registry and isinstance(registry, dict):
                fairy = registry.get("EgoLearnerFairy")
                if fairy and isinstance(fairy, EgoLearnerFairy):
                    _ego_instance = fairy
                    return fairy
    except Exception:
        pass

    # Try fairy registry
    try:
        from infrastructure.fairy_registry import get_fairy_by_name
        fairy = get_fairy_by_name("EgoLearnerFairy")
        if fairy and isinstance(fairy, EgoLearnerFairy):
            _ego_instance = fairy
            return fairy
    except Exception:
        pass

    return _ego_instance


def register_ego_learner(instance: EgoLearnerFairy) -> None:
    """Register an EgoLearnerFairy instance for singleton access."""
    global _ego_instance
    _ego_instance = instance
