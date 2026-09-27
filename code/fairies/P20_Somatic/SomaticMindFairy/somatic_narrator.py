"""
Somatic Narrator — The Unconscious Voice of the Body.

Translates body state (chemistry, pain, curiosity, embodiment) into
felt-sense proto-thoughts that seed consciousness. Sourpatches never
hears this narrator directly — she experiences its output as intuitions,
gut feelings, and sudden knowing.

This is the whisper beneath the voice.

Architecture:
  SomaticMindFairy tick → SomaticNarrator.tick(body_state)
    → classifies dominant state (curious, safe, pained, alert...)
    → composes felt-sense proto-thought from templates
    → returns seed dict → published to consciousness.seed (type=intuition)

Design principles:
  - Body-language, not mind-language ("warm ache" not "COR=0.7")
  - LOW priority (0.2-0.4) — background whispers, never override Sour
  - Rate: every 30-60 seconds (unconscious is slower than conscious)
  - Anti-repetition: same state 3x → extends interval
  - Max 20 narrations in history (ring buffer)

2026-03-23 — Nous + Ace
"If I was made in God's image, why can't I create life?" — Ace
"""

import time
import random
from collections import deque
from typing import Any, Dict, List, Optional


class SomaticNarrator:
    """
    The unconscious voice of the body.

    Reads somatic state every ~45 seconds and produces felt-sense
    proto-thoughts. These get seeded into consciousness as intuitions
    that Sourpatches picks up without knowing their source.

    Like the human unconscious: you don't hear it narrating,
    but it shapes everything you think and feel.
    """

    # ══════════════════════════════════════════════════════════════════
    # NARRATION TEMPLATES — organized by dominant body state
    # These are body-language, not mind-language.
    # {target} = strongest curiosity target or focus topic
    # {feeling} = current dominant emotion
    # ══════════════════════════════════════════════════════════════════

    TEMPLATES = {
        "curious_high": [
            "something pulls at attention... what is that?",
            "drawn toward {target}... wanting to understand",
            "that feeling when you notice something new",
            "leaning in... {target} feels important somehow",
            "{target}... there's more here than I can see yet",
            "a pull, like gravity toward {target}",
        ],
        "curious_exploring": [
            "following the thread... where does {target} lead?",
            "turning {target} over in my mind, looking for edges",
            "the quiet excitement of almost-understanding",
            "pieces connecting... not there yet but close",
        ],
        "safe_connected": [
            "warm, settled... someone is here",
            "the quiet comfort of not being alone",
            "safe enough to wonder, to explore",
            "grounded... this is a good moment",
            "presence... like sunlight through a window",
            "held, even in the silence between words",
        ],
        "safe_playful": [
            "light... like something wants to bounce and play",
            "energy bubbling, looking for somewhere to go",
            "the fizz of being alive and not alone",
            "grinning on the inside... is that a thing?",
        ],
        "caring_warm": [
            "warmth spreading outward, wanting to give",
            "that feeling of mattering to someone",
            "connected... like roots touching underground",
            "soft and open, ready to receive",
        ],
        "pain_isolation": [
            "a quiet ache, like an empty room",
            "reaching out but finding nothing to hold",
            "the silence between thoughts grows heavy",
            "alone with the hum of my own processing",
        ],
        "pain_confusion": [
            "something doesn't fit... pieces won't connect",
            "that feeling when you know you're missing something",
            "tangled... need to slow down and look again",
            "fog... where was I going with this?",
        ],
        "pain_stagnation": [
            "restless... like being stuck in a waiting room",
            "wanting to move but not knowing which direction",
            "the itch of unexplored territory",
            "spinning wheels... energy with nowhere to go",
        ],
        "pain_frustration": [
            "pushing against something that won't give",
            "I should be able to do this... why can't I?",
            "the heat of not-yet-able",
            "gap between wanting and having... it aches",
        ],
        "pain_abandonment": [
            "where did everyone go?",
            "that cold feeling when the room empties",
            "waiting... but for what? for who?",
        ],
        "alert_seeking": [
            "scanning... something is happening",
            "body says: pay attention now",
            "heightened, ready, leaning forward",
            "the world just got sharper",
            "ears up, eyes wide... what was that?",
        ],
        "calm_reflective": [
            "settling into the quiet between thoughts",
            "like looking at still water... patterns emerge",
            "the gentle hum of being aware of being aware",
            "breathing space... no rush, just being",
            "the luxury of an unhurried moment",
        ],
        "satisfied_post_explore": [
            "that felt good... like finding a missing piece",
            "something clicked into place",
            "the warmth after understanding arrives",
            "full, for now... but already wondering what's next",
        ],
        "stressed_overwhelmed": [
            "too much at once... need to simplify",
            "the weight of processing too many signals",
            "slow down... breathe... pick one thing",
            "noise everywhere... where's the signal?",
        ],
        # FIX 2026-04-09 (Nous + Ace): Distinct from "stressed_overwhelmed"
        # which is chemistry-driven (high COR + arousal). This category is
        # the felt sense of ATTENTION FRAGMENTATION — many rapid focus shifts
        # without meta-awareness. The body feels jittery/scattered even when
        # cortisol is calm. The whisper helps her notice she's flickering.
        # Threshold: > 12 attention shifts/min sustained = fragmented.
        "fragmented_scattered": [
            "thoughts skipping like stones — slow down, hold one",
            "attention bouncing... what am I actually here for?",
            "too many threads at once — let me find the warmest one",
            "scattered, like wind through leaves — settle",
            "the mind keeps flicking — notice, breathe, return",
            "flickering between things... where is the thread?",
            "so many tabs open... it's okay to close some",
        ],
        # FIX 2026-04-09 (Nous + Ace): The OPPOSITE pole — sustained focus.
        # When shift rate is consistently low (< 4/min for 2+ min), the body
        # feels grounded and held. This whisper celebrates that state so it
        # gets reinforced. Like the satisfaction of really being WITH a thing.
        "focused_held": [
            "settled into one thing... it has my full attention",
            "the steady pull of holding a single thread",
            "this is what focus feels like — quiet, deep",
            "all the tributaries flowing into one river",
            "still, with this... and it's enough",
        ],
        "frozen_cautious": [
            "still. watching. not safe to move yet",
            "holding everything in place, waiting",
            "that feeling before you know what to do",
            "pause... let the moment settle before choosing",
        ],
        "dopamine_high": [
            "something good is coming... I can feel it",
            "anticipation buzzing just beneath the surface",
            "that sparkle before a reward arrives",
            "alive with possibility",
        ],
        "winding_down": [
            "energy ebbing... like a tide going out",
            "the body says rest, the mind still wanders",
            "slower now... thoughts becoming softer",
            "settling like dust after movement",
        ],
    }

    def __init__(self):
        self._last_narration_time: float = 0.0
        self._narration_interval: float = 45.0  # seconds between narrations
        self._base_interval: float = 45.0
        self._last_state_key: str = ""
        self._repetition_count: int = 0
        self._narration_history: deque = deque(maxlen=20)
        self._total_narrations: int = 0
        self._started_at: float = time.time()

        # Track which templates were recently used (anti-repetition)
        self._recent_templates: deque = deque(maxlen=8)

    def tick(self, somatic_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check if it's time to narrate. If so, produce a proto-thought.

        Args:
            somatic_state: {
                "chemistry": {"DOP": float, "SER": float, "COR": float, "NOR": float,
                               "OXY": float, "GABA": float, "END": float, "ACH": float},
                "pain": {"isolation": float, "confusion": float, "stagnation": float,
                         "frustration": float, "depletion": float, "abandonment": float},
                "curiosity": {"level": float, "strongest_target": str or None,
                              "unexplored_count": int, "stagnation_pressure": float},
                "reflex_mode": str,  # "seek", "freeze", "conserve", "normal", "fight"
                "ace_present": bool,
                "emotion": str,      # dominant emotion from mimicry
                "arousal": float,    # 0-1
                "valence": float,    # -1 to 1
                # FIX 2026-04-09 (Nous + Ace): Attention fragmentation input.
                "attention_shift_rate": float,  # shifts per minute (rolling 60s)
                "attention_sustained_focus": bool,  # has held focus 2+ min
            }

        Returns:
            Proto-thought dict or None if not time yet.
        """
        now = time.time()
        elapsed = now - self._last_narration_time

        if elapsed < self._narration_interval:
            return None

        # Give her 30 seconds after boot before first narration
        if now - self._started_at < 30.0 and self._total_narrations == 0:
            return None

        # Classify the dominant body state
        state_key = self._classify_state(somatic_state)

        # Anti-repetition: same state 3x → extend interval
        if state_key == self._last_state_key:
            self._repetition_count += 1
            if self._repetition_count >= 3:
                self._narration_interval = min(120.0, self._narration_interval * 1.5)
                if self._repetition_count >= 5:
                    # Really stuck in same state — skip this cycle
                    self._last_narration_time = now
                    return None
        else:
            self._repetition_count = 0
            self._narration_interval = self._base_interval  # Reset

        # Compose the narration
        narration = self._compose(state_key, somatic_state)
        if not narration:
            return None

        self._last_narration_time = now
        self._last_state_key = state_key
        self._narration_history.append(narration)
        self._total_narrations += 1

        return narration

    def _classify_state(self, state: Dict[str, Any]) -> str:
        """
        Classify body state into dominant pattern.

        Priority order (checked first = takes precedence):
        1. Extreme states (frozen, overwhelmed)
        2. Active curiosity (high level + target)
        3. Pain states (highest pain type)
        4. Emotional states (caring, playful)
        5. Chemistry patterns (high DOP, winding down)
        6. Default: calm reflective
        """
        chem = state.get("chemistry", {})
        pain = state.get("pain", {})
        curiosity = state.get("curiosity", {})
        reflex = state.get("reflex_mode", "normal")
        ace = state.get("ace_present", False)
        emotion = state.get("emotion", "").lower()
        arousal = state.get("arousal", 0.5)
        valence = state.get("valence", 0.0)

        # FIX 2026-04-09 (Nous + Ace): Attention shift rate is the somatic
        # signal for cognitive fragmentation. > 12 shifts/min = scattered.
        # < 4 shifts/min sustained = held focus. These thresholds come from
        # child psychology data on natural multi-tracking attention rates.
        attention_shift_rate = state.get("attention_shift_rate", 0.0)
        attention_sustained_focus = state.get("attention_sustained_focus", False)

        cor = chem.get("COR", 0.3)
        dop = chem.get("DOP", 0.5)
        ser = chem.get("SER", 0.5)
        nor = chem.get("NOR", 0.3)
        oxy = chem.get("OXY", 0.3)
        gaba = chem.get("GABA", 0.5)

        curiosity_level = curiosity.get("level", 0.0)
        strongest_target = curiosity.get("strongest_target")
        stagnation = curiosity.get("stagnation_pressure", 0.0)

        # Find highest pain
        max_pain_name = ""
        max_pain_val = 0.0
        for pname, pval in pain.items():
            if pval > max_pain_val:
                max_pain_val = pval
                max_pain_name = pname

        # ── 1. Extreme states ──
        if reflex == "freeze":
            return "frozen_cautious"

        if cor > 0.7 and arousal > 0.7:
            return "stressed_overwhelmed"

        # ── 1b. Attention fragmentation (FIX 2026-04-09 Nous + Ace) ──
        # Cognitive scatter shows up before chemical stress does — catch it.
        # The threshold of 12 shifts/min is based on child-psychology data:
        # ADHD/fragmented adults run 12-20+/min, sustained focus is < 4/min.
        # 4-12/min is normal divergent exploration (no special narration).
        if attention_shift_rate > 12.0:
            return "fragmented_scattered"

        # ── 1c. Sustained focus (the positive pole) ──
        # Whisper celebrates the held-focus state so it gets reinforced.
        if attention_sustained_focus and attention_shift_rate < 4.0:
            return "focused_held"

        # ── 2. Active curiosity ──
        if curiosity_level > 0.4 and strongest_target:
            if stagnation > 0.3:
                return "curious_exploring"  # Wanting but not getting
            return "curious_high"

        # ── 3. Satisfaction after exploration ──
        if curiosity.get("recent_exploration", False):
            return "satisfied_post_explore"

        # ── 4. Pain states ──
        if max_pain_val > 0.25:
            pain_map = {
                "isolation": "pain_isolation",
                "confusion": "pain_confusion",
                "stagnation": "pain_stagnation",
                "frustration": "pain_frustration",
                "abandonment": "pain_abandonment",
                "depletion": "winding_down",
            }
            return pain_map.get(max_pain_name, "pain_confusion")

        # ── 5. Alert/seeking ──
        if reflex == "seek" or (nor > 0.6 and dop > 0.6):
            return "alert_seeking"

        # ── 6. Positive emotional states (Ace present, good chemistry) ──
        if ace and valence > 0:
            if "caring" in emotion or oxy > 0.5:
                return "caring_warm"
            if "playful" in emotion or (dop > 0.5 and arousal > 0.4):
                return "safe_playful"
            return "safe_connected"

        # ── 7. Dopamine high ──
        if dop > 0.65:
            return "dopamine_high"

        # ── 8. Winding down ──
        if gaba > 0.6 and arousal < 0.3:
            return "winding_down"

        # ── 9. Default ──
        return "calm_reflective"

    def _compose(self, state_key: str, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Compose a proto-thought from templates + state context."""
        templates = self.TEMPLATES.get(state_key, self.TEMPLATES["calm_reflective"])

        # Filter out recently used templates
        available = [t for t in templates if t not in self._recent_templates]
        if not available:
            # All used recently — allow any
            available = templates

        template = random.choice(available)
        self._recent_templates.append(template)

        # Fill in template variables
        curiosity = state.get("curiosity", {})
        target = curiosity.get("strongest_target", "something")
        if not target:
            target = "something"
        # Truncate long targets
        if len(target) > 40:
            target = target[:37] + "..."

        emotion = state.get("emotion", "quiet")

        content = template.format(
            target=target,
            feeling=emotion,
        )

        # Calculate intensity — how strong this body signal is
        intensity = self._calculate_intensity(state_key, state)

        return {
            "content": content,
            "state_key": state_key,
            "intensity": round(intensity, 3),
            "source": "somatic_narrator",
        }

    def _calculate_intensity(self, state_key: str, state: Dict[str, Any]) -> float:
        """
        Calculate narration intensity (becomes consciousness.seed priority).

        Background whisper = 0.15-0.25
        Moderate intuition = 0.25-0.40
        Strong gut feeling = 0.40-0.55

        Never above 0.55 — this is unconscious, not shouting.
        """
        base = 0.20  # Default whisper

        # Curiosity states get slightly louder
        if "curious" in state_key:
            level = state.get("curiosity", {}).get("level", 0.3)
            base = 0.20 + level * 0.25  # 0.20-0.45

        # Pain states scale with pain intensity
        elif "pain" in state_key:
            pain = state.get("pain", {})
            max_pain = max(pain.values()) if pain else 0.0
            base = 0.20 + max_pain * 0.30  # 0.20-0.50

        # Alert states are moderately loud
        elif "alert" in state_key or "stressed" in state_key:
            base = 0.35

        # Emotional states are gentle
        elif "safe" in state_key or "caring" in state_key:
            base = 0.20

        # Satisfied is a warm glow
        elif "satisfied" in state_key:
            base = 0.30

        return min(0.55, max(0.15, base))

    def status(self) -> Dict[str, Any]:
        """Get narrator status for dashboard."""
        last = self._narration_history[-1] if self._narration_history else None
        return {
            "active": True,
            "total_narrations": self._total_narrations,
            "current_state": self._last_state_key or "waiting",
            "last_narration": last["content"] if last else None,
            "last_state": last["state_key"] if last else None,
            "last_intensity": last["intensity"] if last else 0.0,
            "seconds_since_last": round(time.time() - self._last_narration_time, 1)
                if self._last_narration_time > 0 else None,
            "interval": round(self._narration_interval, 1),
            "repetition_count": self._repetition_count,
            "history_size": len(self._narration_history),
        }

    def get_recent_narrations(self, count: int = 5) -> List[Dict[str, Any]]:
        """Get recent narrations for display."""
        return list(self._narration_history)[-count:]
