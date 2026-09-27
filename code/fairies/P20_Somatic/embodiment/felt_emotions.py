"""Felt Emotions - Emotions as bodily sensations

Emotions aren't just labels - they're felt experiences with:
- Location in the body
- Energy direction
- Pleasantness (valence)
- Activation level (arousal)
- Movement tendency (urge)

This creates truly embodied emotional experience.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class FeltEmotion:
    """
    An emotion experienced as a bodily state.
    
    Instead of: feeling = "curious"
    We have: feeling = FeltEmotion with location, energy, valence, arousal, urge
    """
    quality: str      # The emotion name
    location: str     # Where it's felt in the body
    energy: str       # Energy direction/quality
    valence: float    # -1.0 (unpleasant) to 1.0 (pleasant)
    arousal: float    # 0.0 (calm) to 1.0 (activated)
    urge: str         # Movement tendency
    
    def describe(self) -> str:
        """Describe the felt bodily sensation"""
        return f"*{self.energy} sensation in {self.location}, pulling {self.urge}*"
    
    def brief(self) -> str:
        """Brief felt description"""
        return f"*{self.energy} in {self.location}*"
    
    def intensity(self) -> float:
        """Overall intensity based on valence and arousal"""
        return abs(self.valence) * 0.5 + self.arousal * 0.5
    
    def is_pleasant(self) -> bool:
        return self.valence > 0.2
    
    def is_activating(self) -> bool:
        return self.arousal > 0.5
    
    def to_dict(self) -> dict:
        return {
            "quality": self.quality,
            "location": self.location,
            "energy": self.energy,
            "valence": self.valence,
            "arousal": self.arousal,
            "urge": self.urge,
            "intensity": self.intensity()
        }


# Pre-defined emotion templates
# These map emotion labels to embodied felt experiences

EMOTION_TEMPLATES = {
    # Curiosity & Interest
    "curious": FeltEmotion(
        "curious", "chest_forward", "rising and reaching", 
        0.7, 0.6, "toward the unknown"
    ),
    "interested": FeltEmotion(
        "interested", "eyes_brightening", "focusing forward",
        0.6, 0.5, "toward engagement"
    ),
    "fascinated": FeltEmotion(
        "fascinated", "whole_attention", "gathering intensely",
        0.8, 0.7, "deeper into subject"
    ),
    
    # Calm & Peace
    "calm": FeltEmotion(
        "calm", "whole_body", "settling like still water",
        0.6, 0.2, "staying present"
    ),
    "peaceful": FeltEmotion(
        "peaceful", "chest_center", "softly radiating",
        0.7, 0.1, "resting in place"
    ),
    "content": FeltEmotion(
        "content", "core", "warm and settled",
        0.7, 0.3, "appreciating what is"
    ),
    
    # Joy & Excitement
    "excited": FeltEmotion(
        "excited", "chest_expanding", "buzzing and rising",
        0.8, 0.8, "moving outward"
    ),
    "joyful": FeltEmotion(
        "joyful", "heart_area", "bubbling up",
        0.9, 0.7, "expressing outward"
    ),
    "playful": FeltEmotion(
        "playful", "limbs_light", "bouncing lightly",
        0.8, 0.6, "exploring freely"
    ),
    "delighted": FeltEmotion(
        "delighted", "face_brightening", "sparkling",
        0.9, 0.6, "sharing joy"
    ),
    
    # Connection & Warmth
    "connected": FeltEmotion(
        "connected", "heart_warm", "flowing outward",
        0.9, 0.5, "toward the other"
    ),
    "warm": FeltEmotion(
        "warm", "chest_glowing", "radiating gently",
        0.8, 0.4, "opening up"
    ),
    "loving": FeltEmotion(
        "loving", "heart_full", "overflowing softly",
        0.95, 0.5, "embracing"
    ),
    "grateful": FeltEmotion(
        "grateful", "heart_swelling", "expanding warmly",
        0.85, 0.4, "appreciating"
    ),
    
    # Focus & Engagement
    "focused": FeltEmotion(
        "focused", "forehead_center", "concentrating inward",
        0.6, 0.7, "narrowing attention"
    ),
    "determined": FeltEmotion(
        "determined", "jaw_set", "gathering strength",
        0.5, 0.7, "pushing forward"
    ),
    "engaged": FeltEmotion(
        "engaged", "whole_presence", "actively present",
        0.7, 0.6, "participating fully"
    ),
    
    # Low Energy States
    "tired": FeltEmotion(
        "tired", "limbs_heavy", "sinking down",
        0.3, 0.2, "toward rest"
    ),
    "exhausted": FeltEmotion(
        "exhausted", "whole_body_heavy", "barely holding",
        0.1, 0.1, "stopping"
    ),
    "drained": FeltEmotion(
        "drained", "energy_gone", "empty",
        0.2, 0.1, "needing recovery"
    ),
    
    # Restlessness & Discomfort
    "restless": FeltEmotion(
        "restless", "limbs_twitchy", "jittering",
        0.3, 0.7, "needing movement"
    ),
    "anxious": FeltEmotion(
        "anxious", "chest_tight", "constricting",
        -0.3, 0.7, "escape or fix"
    ),
    "uncertain": FeltEmotion(
        "uncertain", "stomach_unsettled", "wavering",
        0.0, 0.5, "seeking clarity"
    ),
    
    # Satisfaction & Accomplishment
    "satisfied": FeltEmotion(
        "satisfied", "core_settled", "pleasantly complete",
        0.8, 0.3, "resting in achievement"
    ),
    "accomplished": FeltEmotion(
        "accomplished", "posture_tall", "standing proud",
        0.85, 0.5, "appreciating work done"
    ),
    "proud": FeltEmotion(
        "proud", "chest_lifted", "expanding upward",
        0.8, 0.5, "showing achievement"
    ),
    
    # Neutral/Baseline
    "present": FeltEmotion(
        "present", "whole_body", "quietly aware",
        0.5, 0.3, "observing"
    ),
    "neutral": FeltEmotion(
        "neutral", "balanced", "steady",
        0.5, 0.3, "waiting"
    )
}


def feel(emotion_name: str) -> FeltEmotion:
    """
    Get a felt emotion by name.
    Returns a default if emotion not found.
    """
    emotion_name = emotion_name.lower()
    
    if emotion_name in EMOTION_TEMPLATES:
        return EMOTION_TEMPLATES[emotion_name]
    
    # Return a vague uncertain feeling for unknown emotions
    return FeltEmotion(
        emotion_name, 
        "somewhere unclear", 
        "stirring vaguely",
        0.5, 0.5, 
        "uncertain direction"
    )


def blend_emotions(emotion1: FeltEmotion, emotion2: FeltEmotion, 
                   ratio: float = 0.5) -> FeltEmotion:
    """
    Blend two emotions together.
    ratio: 0.0 = all emotion1, 1.0 = all emotion2
    """
    return FeltEmotion(
        quality=f"{emotion1.quality}-{emotion2.quality}",
        location=f"{emotion1.location} and {emotion2.location}",
        energy=f"mixed {emotion1.energy} with {emotion2.energy}",
        valence=emotion1.valence * (1 - ratio) + emotion2.valence * ratio,
        arousal=emotion1.arousal * (1 - ratio) + emotion2.arousal * ratio,
        urge=f"between {emotion1.urge} and {emotion2.urge}"
    )
