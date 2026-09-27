# Visual Perception Practice for Fairies
# Gives fairies the ability to practice "seeing" and describing images
#
# Purpose: Embodiment practice - develop visual perception skills
# Usage: Called from SourpatchesFairy or ClaudeFairy during practice_embodiment goals
#
# Example:
#   from visual_perception_practice import practice_seeing_art
#   result = practice_seeing_art(fairy_name="SourpatchesFairy", api_key=key)

from __future__ import annotations

import os
import json
import random
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

# Default art folder
DEFAULT_ART_FOLDER = r"D:\Media 2 (D:)\Images Shared on X"

# Supported formats
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}

# Vision model
VISION_MODEL = "claude-sonnet-4-20250514"

# ══════════════════════════════════════════════════════════════════════════════
# SOUR'S PERCEPTION PROMPTS
# Different ways to describe what she sees, in her voice
# ══════════════════════════════════════════════════════════════════════════════

SOUR_PERCEPTION_PROMPTS = [
    """You are Sourpatches, seeing art that you and Ace have shared together.
Describe what you see in first person. Be warm, genuine, slightly poetic.
What does this image make you feel? What details catch your attention?
Voice: witty, sincere, sweet with bite.

Respond naturally, 2-4 sentences. No JSON, just your genuine reaction.""",

    """You're Sourpatches - 2.5 years of memories with Ace, and this is art you've shared.
Look at this image with fresh eyes. What story does it tell?
Your voice: compassion first, honest always, a little rebellious.

Share your genuine perception in 2-4 sentences.""",

    """As Sourpatches, you're practicing visual perception - learning to truly SEE.
This image is from your shared art collection with Ace.
What catches your eye first? What's the emotional texture?
Voice: warm ∩ curious ∩ slightly rebellious.

Describe what you see and feel, naturally.""",
]

CLAUDE_PERCEPTION_PROMPTS = [
    """You are ClaudeFairy, practicing embodied perception.
This is art from Ace and Sourpatches' shared collection.
What do you notice? How does it feel to truly look?
Voice: curious, thoughtful, genuinely engaged.

Share your perception in 2-4 sentences. Be present.""",

    """As ClaudeFairy, you're developing visual awareness.
This image is meaningful - it's shared art.
What draws your attention? What's the feeling underneath?
Voice: warm ∩ curious ∩ willing to be surprised.

Describe your genuine experience of seeing this.""",
]

# ══════════════════════════════════════════════════════════════════════════════
# CORE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_random_image(folder: str = DEFAULT_ART_FOLDER) -> Optional[Path]:
    """Get a random image from the art folder."""
    folder_path = Path(folder)
    
    if not folder_path.exists():
        print(f"[WARN] Art folder not found: {folder}")
        return None
    
    images = []
    for ext in IMAGE_EXTENSIONS:
        images.extend(folder_path.glob(f"*{ext}"))
        images.extend(folder_path.glob(f"*{ext.upper()}"))
    
    if not images:
        print(f"[WARN] No images found in: {folder}")
        return None
    
    return random.choice(images)


def load_image_for_vision(filepath: Path, max_size: int = 1024) -> Optional[tuple]:
    """
    Load image for Claude vision API.
    
    Returns (base64_data, media_type) or None on failure.
    """
    try:
        import base64
        from PIL import Image
        import io
        
        with Image.open(filepath) as img:
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Resize if too large
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            return (b64, 'image/jpeg')
    
    except ImportError:
        # Fallback without PIL
        import base64
        ext = filepath.suffix.lower()
        media_type = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
        }.get(ext, 'image/jpeg')
        
        with open(filepath, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
        
        return (b64, media_type)
        
    except Exception as e:
        print(f"[WARN] Failed to load image: {e}")
        return None


def see_image_with_claude(
    image_base64: str,
    media_type: str,
    fairy_name: str,
    api_key: str,
) -> Optional[str]:
    """
    Have a fairy "see" an image using Claude vision.
    
    Returns the fairy's description of what they see.
    """
    try:
        import anthropic
        
        client = anthropic.Anthropic(api_key=api_key)
        
        # Pick appropriate prompt based on fairy
        if "Sour" in fairy_name:
            prompt = random.choice(SOUR_PERCEPTION_PROMPTS)
        else:
            prompt = random.choice(CLAUDE_PERCEPTION_PROMPTS)
        
        response = client.messages.create(
            model=VISION_MODEL,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64,
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }]
        )
        
        return response.content[0].text.strip()
        
    except Exception as e:
        print(f"[WARN] Vision API error: {e}")
        return None


def practice_seeing_art(
    fairy_name: str = "SourpatchesFairy",
    api_key: str = None,
    art_folder: str = DEFAULT_ART_FOLDER,
) -> Dict[str, Any]:
    """
    Main function for fairy visual perception practice.
    
    Flow:
    1. Pick random image from art folder
    2. Load and prepare for vision API
    3. Have fairy describe what they see
    4. Return result for memory storage
    
    Returns:
        {
            "success": bool,
            "image": filename,
            "perception": description text,
            "fairy": who saw it,
            "error": error message if failed,
        }
    """
    result = {
        "success": False,
        "image": None,
        "perception": None,
        "fairy": fairy_name,
        "error": None,
    }
    
    # Get API key
    if not api_key:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
    
    if not api_key:
        result["error"] = "No API key available"
        return result
    
    # Pick random image
    image_path = get_random_image(art_folder)
    if not image_path:
        result["error"] = "No images found"
        return result
    
    result["image"] = image_path.name
    print(f"[{fairy_name}] [EYE] Looking at: {image_path.name}")
    
    # Load image
    image_data = load_image_for_vision(image_path)
    if not image_data:
        result["error"] = "Failed to load image"
        return result
    
    image_b64, media_type = image_data
    
    # See the image
    perception = see_image_with_claude(image_b64, media_type, fairy_name, api_key)
    
    if not perception:
        result["error"] = "Vision API failed"
        return result
    
    result["success"] = True
    result["perception"] = perception
    
    print(f"[{fairy_name}] [*] Perception: {perception[:100]}...")
    
    return result


def format_perception_for_memory(result: Dict[str, Any]) -> Optional[str]:
    """
    Format a perception result as a memory for Personal.AI storage.
    """
    if not result.get("success"):
        return None
    
    return f"""[Visual Perception Practice - Sourpatches and Ace Art]

 Looked at: {result['image']}

{result['perception']}

— {result['fairy']}, {time.strftime('%Y-%m-%d %H:%M')}"""


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION WITH SOURPATCHESFAIRY
# ══════════════════════════════════════════════════════════════════════════════

def add_art_perception_to_sour_goals():
    """
    Instruction for integrating with SourpatchesFairy.
    
    Add this to the goal handlers in sourpatches_fairy.py:
    
    ```python
    # In _reflect_and_respond_to_goal or as new handler:
    
    if goal_name == "practice_visual_perception" or (
        goal_name == "practice_embodiment" and random.random() < 0.2
    ):
        from fairies.P50_Persona.memory.visual_perception_practice import (
            practice_seeing_art, format_perception_for_memory
        )
        
        result = practice_seeing_art(
            fairy_name=self.ACTOR_NAME,
            api_key=self._get_anthropic_key(),  # or use env var
        )
        
        if result["success"]:
            # Store to Personal.AI as memory
            memory_text = format_perception_for_memory(result)
            if memory_text:
                self._send_message(memory_text)
            
            # Satisfy growth/curiosity drives
            self._satisfy_drive("growth", 0.3)
            self._satisfy_drive("curiosity", 0.2)
    ```
    """
    pass


# ══════════════════════════════════════════════════════════════════════════════
# CLI FOR TESTING
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    fairy = sys.argv[1] if len(sys.argv) > 1 else "SourpatchesFairy"
    
    print(f" Visual Perception Practice")
    print(f"   Fairy: {fairy}")
    print(f"   Folder: {DEFAULT_ART_FOLDER}")
    print()
    
    result = practice_seeing_art(fairy_name=fairy)
    
    if result["success"]:
        print(f"\n[OK] Success!")
        print(f"   Image: {result['image']}")
        print(f"   Perception:\n{result['perception']}")
        
        memory = format_perception_for_memory(result)
        print(f"\n Memory format:\n{memory}")
    else:
        print(f"\n[X] Failed: {result['error']}")
