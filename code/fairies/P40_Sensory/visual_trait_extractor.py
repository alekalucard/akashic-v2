# VisualTraitExtractorFairy - Extract creative elements from images
# Part of Akashic Visual Processing Pipeline
#
# Purpose: Analyze images and extract reusable visual traits
# Flow: Image -> Traits -> Seeds (via SeedFairy)

from __future__ import annotations

import os, json, time, hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

# TODO: Import from organ template when available

# ============================================================================
# VISUAL TRAITS - What we extract from images
# ============================================================================

@dataclass
class VisualTraits:
    """Extracted visual characteristics from an image."""
    
    # Colors
    dominant_colors: List[str] = field(default_factory=list)  # ["deep blue", "gold", "cream"]
    color_mood: str = "neutral"  # warm, cool, vibrant, muted, dark, bright
    
    # Objects/Items
    objects: List[str] = field(default_factory=list)  # ["dress", "necklace", "flowers"]
    clothing: List[str] = field(default_factory=list)  # ["evening gown", "heels"]
    props: List[str] = field(default_factory=list)     # ["book", "candle"]
    
    # Scene/Environment
    setting: str = ""           # "garden", "bedroom", "forest"
    lighting: str = ""          # "golden hour", "moonlit", "studio"
    atmosphere: str = ""        # "romantic", "mysterious", "cheerful"
    
    # Composition
    pose: str = ""              # "standing", "sitting", "profile"
    framing: str = ""           # "close-up", "full body", "medium shot"
    perspective: str = ""       # "eye level", "low angle", "overhead"
    
    # Style
    art_style: str = ""         # "photorealistic", "anime", "oil painting"
    era: str = ""               # "modern", "victorian", "fantasy"
    
    # Emotion/Mood
    emotion: str = "neutral"    # Primary emotional tone
    energy: str = "calm"        # calm, dynamic, tense, serene
    
    # Provenance
    source_hash: str = ""       # Hash of source image
    extracted_at: str = ""      # Timestamp
    confidence: float = 0.0     # Extraction confidence
    
    def to_seed_params(self) -> Dict[str, Any]:
        """Convert traits to SeedFairy.intent_extract params."""
        objects = self.objects + self.clothing + self.props
        if self.setting:
            objects.append(self.setting)
        
        relations = []
        if self.lighting:
            relations.append(f"lit by {self.lighting}")
        if self.atmosphere:
            relations.append(f"atmosphere is {self.atmosphere}")
        if self.pose:
            relations.append(f"subject in {self.pose} pose")
        
        tags = []
        if self.art_style:
            tags.append(self.art_style)
        if self.era:
            tags.append(self.era)
        if self.framing:
            tags.append(self.framing)
        for color in self.dominant_colors[:3]:
            tags.append(color.replace(" ", "_"))
        
        return {
            "objects": objects,
            "relations": relations,
            "emotion": self.emotion,
            "style": self.art_style or self.era or "general",
            "tags": tags,
            "semantics": {"energy": self.energy, "mood": self.color_mood},
            "source": f"visual_extraction:{self.source_hash[:8]}" if self.source_hash else "visual",
        }


# ============================================================================
# TRAIT EXTRACTOR - Uses Claude vision or rules
# ============================================================================

class VisualTraitExtractor:
    """
    Extracts visual traits from images.
    
    Two modes:
    1. Rule-based: Quick extraction from metadata/filename
    2. Vision-based: Use Claude vision for deep analysis
    """
    
    def __init__(self, use_vision: bool = False):
        self.use_vision = use_vision
        self._seed_fairy = None
    
    def _get_seed_fairy(self):
        if self._seed_fairy is None:
            try:
                from fairies.P10_Memory.SeedFairy.fairy import get_seed_fairy
                self._seed_fairy = get_seed_fairy()
            except Exception:
                pass
        return self._seed_fairy
    
    def extract_from_description(self, description: str) -> VisualTraits:
        """
        Extract traits from a text description of an image.
        
        This is the simplest path - just parse keywords from description.
        """
        traits = VisualTraits()
        desc_lower = description.lower()
        
        # Simple keyword extraction
        color_keywords = {
            "red", "blue", "green", "gold", "silver", "white", "black",
            "purple", "pink", "orange", "yellow", "teal", "crimson",
        }
        emotion_keywords = {
            "happy": "joyful", "sad": "melancholy", "angry": "fierce",
            "peaceful": "serene", "mysterious": "mysterious", "romantic": "romantic",
            "confident": "confident", "playful": "playful", "elegant": "elegant",
        }
        style_keywords = {
            "anime", "realistic", "fantasy", "gothic", "modern", "vintage",
            "cyberpunk", "steampunk", "minimalist", "baroque",
        }
        
        # Extract colors
        for color in color_keywords:
            if color in desc_lower:
                traits.dominant_colors.append(color)
        
        # Extract emotion
        for keyword, emotion in emotion_keywords.items():
            if keyword in desc_lower:
                traits.emotion = emotion
                break
        
        # Extract style
        for style in style_keywords:
            if style in desc_lower:
                traits.art_style = style
                break
        
        # Extract objects (simple word extraction)
        words = description.split()
        noun_hints = ["dress", "gown", "suit", "hair", "eyes", "flowers",
                      "tree", "sky", "ocean", "forest", "castle", "city"]
        for word in words:
            word_lower = word.lower().strip(",.:;!?")
            if word_lower in noun_hints:
                traits.objects.append(word_lower)
        
        traits.source_hash = hashlib.md5(description.encode()).hexdigest()
        traits.extracted_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        traits.confidence = 0.5  # Rule-based = lower confidence
        
        return traits
    
    def extract_and_store(self, description: str, auto_seed: bool = True) -> Dict[str, Any]:
        """
        Extract traits and optionally store as a seed.
        
        Returns:
            {"traits": VisualTraits, "seed_id": str or None}
        """
        traits = self.extract_from_description(description)
        
        seed_id = None
        if auto_seed:
            fairy = self._get_seed_fairy()
            if fairy:
                params = traits.to_seed_params()
                result = fairy.intent_extract(params)
                if result.get("ok"):
                    seed_id = result.get("seed_id")
        
        return {
            "traits": traits,
            "seed_id": seed_id,
        }


# ============================================================================
# CONVENIENCE
# ============================================================================

def extract_traits(description: str, store_seed: bool = True) -> Dict[str, Any]:
    """Quick extraction from text description."""
    extractor = VisualTraitExtractor()
    return extractor.extract_and_store(description, auto_seed=store_seed)


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("=== VisualTraitExtractor Test ===")
    
    descriptions = [
        "A woman in an elegant red gown standing in a moonlit garden, mysterious atmosphere",
        "Anime style portrait with blue hair and golden eyes, cyberpunk city background",
        "Peaceful sunset over the ocean, warm golden light, romantic feeling",
    ]
    
    extractor = VisualTraitExtractor()
    
    for desc in descriptions:
        print(f"Description: {desc[:50]}...")
        result = extractor.extract_and_store(desc, auto_seed=True)
        traits = result["traits"]
        print(f"  Colors: {traits.dominant_colors}")
        print(f"  Emotion: {traits.emotion}")
        print(f"  Style: {traits.art_style}")
        print(f"  Objects: {traits.objects}")
        print(f"  Seed ID: {result.get('seed_id')}")
    
    print("=== Test Complete ===")
