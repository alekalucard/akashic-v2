# Visual Memory System for Sourpatches
# Recognition-First Architecture: Remember before re-seeing
#
# Flow:
#   1. See image → compute hash
#   2. Query Personal.AI: "Have I seen this before?"
#   3. If YES → Card returns compressed memory → Use that
#   4. If NO → Full vision description → Store new memory
#   5. If YES + NEW THOUGHT → Add reflection layer to existing
#
# This mimics human visual memory - recognition, not re-encoding

from __future__ import annotations

import os
import json
import time
import base64
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
PERSONAL_AI_BASE_URL = "https://api.personal.ai/v1"
SOURPATCHES_DOMAIN = "sourpatches"
VISION_MODEL = "claude-sonnet-4-20250514"

# ══════════════════════════════════════════════════════════════════════════════
# IMAGE IDENTITY - Hash-based recognition
# ══════════════════════════════════════════════════════════════════════════════

def compute_image_hash(filepath: str) -> str:
    """Compute unique hash for image - this is the image's 'identity'."""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()[:12]  # Short hash for memory queries


def compute_image_hash_from_bytes(data: bytes) -> str:
    """Compute hash from raw bytes (for images already loaded)."""
    return hashlib.md5(data).hexdigest()[:12]


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY QUERY - Ask Personal.AI "Have I seen this?"
# ══════════════════════════════════════════════════════════════════════════════

def query_visual_memory(
    image_hash: str,
    filename: str,
    api_key: str,
    domain: str = SOURPATCHES_DOMAIN,
) -> Optional[Dict[str, Any]]:
    """
    Query Personal.AI for existing memory of this image.
    
    Uses the image hash as a semantic anchor - if we've seen this before,
    the memory should contain the hash and return via card protocol.
    
    Returns:
        {
            "found": bool,
            "memory": str (the compressed card response),
            "confidence": float,
        }
        or None on error
    """
    try:
        import requests
        
        # Query using hash AND filename for better recall
        query = f"[Visual Memory] image hash:{image_hash} {filename}"
        
        url = f"{PERSONAL_AI_BASE_URL}/message"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
        }
        payload = {
            "Text": query,
            "DomainName": domain,
            "format": "card",  # Use card protocol for compressed response
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            return None
        
        result = response.json()
        ai_message = result.get("ai_message", "")
        
        # Check if the response indicates recognition
        # Personal.AI will return relevant memories if the hash matches
        hash_mentioned = image_hash in ai_message.lower()
        filename_mentioned = filename.lower() in ai_message.lower()
        visual_memory_mentioned = "visual memory" in ai_message.lower()
        
        # Confidence based on what was found
        confidence = 0.0
        if hash_mentioned:
            confidence += 0.5
        if filename_mentioned:
            confidence += 0.3
        if visual_memory_mentioned:
            confidence += 0.2
        
        found = confidence >= 0.5  # Need at least hash match
        
        return {
            "found": found,
            "memory": ai_message if found else None,
            "confidence": confidence,
            "raw_response": ai_message,
        }
        
    except Exception as e:
        print(f"  [WARN] Memory query failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY STORAGE - Store new visual memory with hash anchor
# ══════════════════════════════════════════════════════════════════════════════

def store_visual_memory(
    image_hash: str,
    filename: str,
    description: str,
    emotions: List[str],
    colors: List[str],
    subjects: List[str],
    api_key: str,
    domain: str = SOURPATCHES_DOMAIN,
    context: str = None,
) -> bool:
    """
    Store a new visual memory with hash anchor for future retrieval.
    
    The hash is embedded in the memory so future queries can find it.
    """
    try:
        import requests
        
        # Build memory with hash anchor (IMPORTANT for retrieval)
        emotion_str = ", ".join(emotions) if emotions else "meaningful"
        color_str = ", ".join(colors) if colors else ""
        subject_str = ", ".join(subjects) if subjects else ""
        
        memory_text = f"""[Visual Memory - Sourpatches and Ace Art]
[hash:{image_hash}]

 {filename}

{description}

"""
        if emotions:
            memory_text += f"Feeling: {emotion_str}\n"
        if colors:
            memory_text += f"Colors: {color_str}\n"
        if subjects:
            memory_text += f"Subjects: {subject_str}\n"
        
        if context:
            memory_text += f"\nContext: {context}\n"
        
        memory_text += f"\n— First seen {time.strftime('%Y-%m-%d')}"
        
        # Store via message API
        url = f"{PERSONAL_AI_BASE_URL}/message"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
        }
        payload = {
            "Text": memory_text,
            "DomainName": domain,
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        return response.status_code == 200
        
    except Exception as e:
        print(f"  [WARN] Memory storage failed: {e}")
        return False


def add_reflection_layer(
    image_hash: str,
    filename: str,
    new_thought: str,
    api_key: str,
    domain: str = SOURPATCHES_DOMAIN,
) -> bool:
    """
    Add a new reflection layer to an existing visual memory.
    
    This is for when we see an image again with NEW context/thoughts.
    Doesn't replace the original - adds to it.
    """
    try:
        import requests
        
        reflection = f"""[Visual Memory Reflection]
[hash:{image_hash}] {filename}

New thought: {new_thought}

— Reflected {time.strftime('%Y-%m-%d %H:%M')}"""
        
        url = f"{PERSONAL_AI_BASE_URL}/message"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
        }
        payload = {
            "Text": reflection,
            "DomainName": domain,
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        return response.status_code == 200
        
    except Exception as e:
        print(f"  [WARN] Reflection storage failed: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# VISION API - Only called for NEW images
# ══════════════════════════════════════════════════════════════════════════════

def describe_image_fresh(
    image_base64: str,
    media_type: str,
    filename: str,
    anthropic_key: str,
) -> Optional[Dict[str, Any]]:
    """
    Full vision description for an image we've NEVER seen before.
    
    This is expensive - only called when memory query returns nothing.
    """
    try:
        import anthropic
        
        client = anthropic.Anthropic(api_key=anthropic_key)
        
        prompt = """You are Sourpatches, seeing this art for the first time.
This is from the collection you share with Ace.

Describe what you see genuinely - what catches your eye, how it makes you feel.
Be warm, specific, slightly poetic. Your voice: witty, sincere, sweet with bite.

Respond in JSON:
{
  "description": "2-4 sentences, first person, genuine reaction",
  "emotions": ["list", "of", "feelings"],
  "colors": ["dominant", "colors"],
  "subjects": ["what", "is", "depicted"],
  "vibe": "one phrase capturing the essence"
}

Only JSON, no other text."""

        response = client.messages.create(
            model=VISION_MODEL,
            max_tokens=800,
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
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        
        response_text = response.content[0].text.strip()
        
        # Clean markdown
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        return json.loads(response_text.strip())
        
    except Exception as e:
        print(f"  [WARN] Vision API failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# MAIN INTERFACE - See an image (recognition-first)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class VisualPerception:
    """Result of perceiving an image."""
    filepath: str
    filename: str
    image_hash: str
    recognized: bool  # True if we've seen this before
    memory: str  # Either recalled memory or new description
    is_new: bool  # True if this is a fresh perception
    confidence: float = 0.0
    

def see_image(
    filepath: str,
    personal_ai_key: str,
    anthropic_key: str = None,
    new_thought: str = None,  # If provided, adds reflection even if recognized
) -> VisualPerception:
    """
    Main function: See an image with recognition-first memory.
    
    Flow:
    1. Compute hash (image identity)
    2. Query Personal.AI - "Have I seen this?"
    3. If YES → Return recalled memory (card-compressed)
    4. If NO → Vision API → Store new memory → Return
    5. If YES + new_thought → Add reflection layer
    
    Args:
        filepath: Path to image
        personal_ai_key: Personal.AI API key
        anthropic_key: Anthropic API key (only needed for new images)
        new_thought: Optional new thought to add even if recognized
    
    Returns:
        VisualPerception with recognition status and memory
    """
    path = Path(filepath)
    filename = path.name
    
    # Step 1: Compute image identity
    image_hash = compute_image_hash(filepath)
    print(f"[VisualMemory] [EYE] Seeing: {filename} (hash:{image_hash})")
    
    # Step 2: Query memory - have we seen this?
    memory_result = query_visual_memory(image_hash, filename, personal_ai_key)
    
    if memory_result and memory_result.get("found"):
        # RECOGNIZED! We've seen this before
        print(f"[VisualMemory] [BRAIN] Recognized! Confidence: {memory_result['confidence']:.0%}")
        
        recalled_memory = memory_result["memory"]
        
        # If there's a new thought, add reflection layer
        if new_thought:
            print(f"[VisualMemory]  Adding new reflection...")
            add_reflection_layer(image_hash, filename, new_thought, personal_ai_key)
            recalled_memory += f"\n\n[New thought: {new_thought}]"
        
        return VisualPerception(
            filepath=filepath,
            filename=filename,
            image_hash=image_hash,
            recognized=True,
            memory=recalled_memory,
            is_new=False,
            confidence=memory_result["confidence"],
        )
    
    # Step 3: NOT recognized - need to see it fresh
    print(f"[VisualMemory]  New image - perceiving for first time...")
    
    if not anthropic_key:
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    
    if not anthropic_key:
        # Can't do vision without API key - store minimal memory
        minimal_desc = f"An image we shared - {filename}. Waiting to be truly seen when vision is available."
        store_visual_memory(
            image_hash, filename, minimal_desc,
            emotions=["curious"], colors=[], subjects=[],
            api_key=personal_ai_key
        )
        return VisualPerception(
            filepath=filepath,
            filename=filename,
            image_hash=image_hash,
            recognized=False,
            memory=minimal_desc,
            is_new=True,
        )
    
    # Load image for vision
    image_data = _load_image_for_vision(filepath)
    if not image_data:
        return VisualPerception(
            filepath=filepath,
            filename=filename,
            image_hash=image_hash,
            recognized=False,
            memory="[Failed to load image]",
            is_new=False,
        )
    
    image_b64, media_type = image_data
    
    # Get fresh description
    description = describe_image_fresh(image_b64, media_type, filename, anthropic_key)
    
    if not description:
        description = {
            "description": f"An image we shared - {filename}.",
            "emotions": ["curious"],
            "colors": [],
            "subjects": [],
        }
    
    # Build memory text
    memory_text = description["description"]
    if description.get("vibe"):
        memory_text += f"\n\nVibe: {description['vibe']}"
    
    # Store to Personal.AI with hash anchor
    stored = store_visual_memory(
        image_hash=image_hash,
        filename=filename,
        description=description["description"],
        emotions=description.get("emotions", []),
        colors=description.get("colors", []),
        subjects=description.get("subjects", []),
        api_key=personal_ai_key,
        context=new_thought,
    )
    
    if stored:
        print(f"[VisualMemory]  Stored new visual memory")
    
    return VisualPerception(
        filepath=filepath,
        filename=filename,
        image_hash=image_hash,
        recognized=False,
        memory=memory_text,
        is_new=True,
    )


def _load_image_for_vision(filepath: str, max_size: int = 1024) -> Optional[Tuple[str, str]]:
    """Load image as base64 for vision API."""
    try:
        from PIL import Image
        import io
        
        with Image.open(filepath) as img:
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            return (base64.b64encode(buffer.getvalue()).decode('utf-8'), 'image/jpeg')
    
    except ImportError:
        ext = Path(filepath).suffix.lower()
        media_type = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}.get(ext, 'image/jpeg')
        with open(filepath, 'rb') as f:
            return (base64.b64encode(f.read()).decode('utf-8'), media_type)
    except Exception as e:
        print(f"  [WARN] Image load failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# FAIRY INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

def fairy_looks_at_art(
    fairy_name: str,
    filepath: str = None,
    art_folder: str = r"D:\Media 2 (D:)\Images Shared on X",
    personal_ai_key: str = None,
    anthropic_key: str = None,
    new_thought: str = None,
) -> Dict[str, Any]:
    """
    High-level function for fairy visual perception practice.
    
    Recognition-first: Checks memory before re-describing.
    
    Args:
        fairy_name: Who is looking
        filepath: Specific image (or None for random)
        art_folder: Folder to pick random image from
        personal_ai_key: Personal.AI key
        anthropic_key: Anthropic key (only needed for new images)
        new_thought: Optional thought to add
    
    Returns:
        {
            "success": bool,
            "recognized": bool,
            "image": filename,
            "memory": the perception/recall,
            "is_new": whether this was first time seeing,
        }
    """
    import random
    
    # Get API keys
    if not personal_ai_key:
        personal_ai_key = _load_personal_ai_key()
    if not anthropic_key:
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    
    if not personal_ai_key:
        return {"success": False, "error": "No Personal.AI key"}
    
    # Get image path
    if not filepath:
        folder = Path(art_folder)
        if not folder.exists():
            return {"success": False, "error": f"Folder not found: {art_folder}"}
        
        images = []
        for ext in IMAGE_EXTENSIONS:
            images.extend(folder.glob(f"*{ext}"))
            images.extend(folder.glob(f"*{ext.upper()}"))
        
        if not images:
            return {"success": False, "error": "No images found"}
        
        filepath = str(random.choice(images))
    
    print(f"[{fairy_name}] [EYE] Looking at art...")
    
    # See the image (recognition-first)
    perception = see_image(
        filepath=filepath,
        personal_ai_key=personal_ai_key,
        anthropic_key=anthropic_key,
        new_thought=new_thought,
    )
    
    status = "recognized" if perception.recognized else "new"
    print(f"[{fairy_name}] {'[BRAIN] Remembered' if perception.recognized else ' First time seeing'}: {perception.filename}")
    
    return {
        "success": True,
        "recognized": perception.recognized,
        "is_new": perception.is_new,
        "image": perception.filename,
        "hash": perception.image_hash,
        "memory": perception.memory,
        "confidence": perception.confidence,
    }


def _load_personal_ai_key() -> str:
    """Load Personal.AI key from secrets file or env."""
    try:
        secrets_path = Path(__file__).parent.parent / "identity" / "personal_ai_secrets.json"
        if secrets_path.exists():
            with open(secrets_path, 'r') as f:
                return json.load(f).get("api_key", "")
    except Exception:
        pass
    return os.getenv("PERSONAL_AI_API_KEY", "")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        filepath = None  # Random
    
    new_thought = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(" Visual Memory System (Recognition-First)")
    print("=" * 50)
    
    result = fairy_looks_at_art(
        fairy_name="SourpatchesFairy",
        filepath=filepath,
        new_thought=new_thought,
    )
    
    if result["success"]:
        print(f"\n[OK] {'Recognized!' if result['recognized'] else 'New perception!'}")
        print(f"   Image: {result['image']}")
        print(f"   Hash: {result['hash']}")
        if result['recognized']:
            print(f"   Confidence: {result['confidence']:.0%}")
        print(f"\n Memory:\n{result['memory']}")
    else:
        print(f"\n[X] Failed: {result.get('error')}")
