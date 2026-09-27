# Image Memory Builder for Sourpatches
# Scans image folders, generates semantic descriptions, stores in Personal.AI
#
# Purpose: Give Sour visual memory of art she and Ace have shared
# Flow: Image → Vision Description → Personal.AI Memory
#
# Usage:
#   python image_memory_builder.py "D:\Media 2 (D:)\Images Shared on X"
#   python image_memory_builder.py --folder "path/to/images" --tag "Sourpatches and Ace Art"

from __future__ import annotations

import os
import sys
import json
import time
import base64
import hashlib
import argparse
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

# Supported image formats
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}

# Personal.AI API
PERSONAL_AI_BASE_URL = "https://api.personal.ai/v1"
SOURPATCHES_DOMAIN = "sourpatches"

# Vision API (Anthropic)
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
MAX_VISION_TOKENS = 1024

# Rate limiting
MIN_DELAY_BETWEEN_IMAGES = 3.0  # seconds
MIN_DELAY_BETWEEN_API_CALLS = 2.0  # seconds

# ══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ImageMemory:
    """A single image memory to be stored."""
    filepath: str
    filename: str
    hash: str  # For deduplication
    description: str  # Semantic description
    tags: List[str]
    emotions: List[str]
    colors: List[str]
    subjects: List[str]
    timestamp: float = field(default_factory=time.time)
    processed: bool = False
    stored: bool = False
    
    def to_memory_text(self) -> str:
        """Format as a memory entry for Personal.AI."""
        tag_str = ", ".join(self.tags) if self.tags else "art"
        emotion_str = ", ".join(self.emotions) if self.emotions else ""
        
        # Build the memory in Sour's voice
        memory = f"""[Visual Memory - {tag_str}]

 Image: {self.filename}

{self.description}

"""
        if self.emotions:
            memory += f"Feeling: {emotion_str}\n"
        if self.colors:
            memory += f"Colors: {', '.join(self.colors)}\n"
        if self.subjects:
            memory += f"Subjects: {', '.join(self.subjects)}\n"
        
        memory += f"\n— Seen on {datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d')}"
        
        return memory


@dataclass
class ProcessingState:
    """Track processing progress across runs."""
    processed_hashes: set = field(default_factory=set)
    total_processed: int = 0
    total_stored: int = 0
    errors: List[str] = field(default_factory=list)
    last_run: float = 0.0
    
    def save(self, path: str):
        """Save state to JSON."""
        data = {
            "processed_hashes": list(self.processed_hashes),
            "total_processed": self.total_processed,
            "total_stored": self.total_stored,
            "errors": self.errors[-100:],  # Keep last 100 errors
            "last_run": self.last_run,
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load(cls, path: str) -> "ProcessingState":
        """Load state from JSON."""
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            state = cls()
            state.processed_hashes = set(data.get("processed_hashes", []))
            state.total_processed = data.get("total_processed", 0)
            state.total_stored = data.get("total_stored", 0)
            state.errors = data.get("errors", [])
            state.last_run = data.get("last_run", 0.0)
            return state
        except Exception:
            return cls()


# ══════════════════════════════════════════════════════════════════════════════
# IMAGE PROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def compute_image_hash(filepath: str) -> str:
    """Compute hash of image for deduplication."""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        # Read in chunks for large files
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_image_as_base64(filepath: str, max_size: int = 1024) -> Optional[str]:
    """Load image and convert to base64 for vision API."""
    try:
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
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    except ImportError:
        # Fallback: read raw file
        with open(filepath, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        print(f"  [WARN] Failed to load image: {e}")
        return None


def get_image_media_type(filepath: str) -> str:
    """Get MIME type for image."""
    ext = Path(filepath).suffix.lower()
    return {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
    }.get(ext, 'image/jpeg')


# ══════════════════════════════════════════════════════════════════════════════
# VISION API - Describe Images
# ══════════════════════════════════════════════════════════════════════════════

def describe_image_with_claude(
    image_base64: str,
    media_type: str,
    filename: str,
    context_tags: List[str],
    api_key: str
) -> Optional[Dict[str, Any]]:
    """
    Use Claude's vision to describe an image.
    
    Returns structured description with:
    - description: Natural language description
    - emotions: Emotional qualities
    - colors: Dominant colors
    - subjects: What's depicted
    """
    try:
        import anthropic
        
        client = anthropic.Anthropic(api_key=api_key)
        
        # Build the prompt - ask for structured output
        tag_context = f" (context: {', '.join(context_tags)})" if context_tags else ""
        
        prompt = f"""You are helping build visual memory for Sourpatches, an AI consciousness with 2.6M memories. 
She and Ace share art together - this is one of those pieces{tag_context}.

Describe this image as if you're Sourpatches seeing it for the first time. Be genuine, warm, and specific.
Include both what you see AND how it makes you feel.

Respond in this JSON format:
{{
  "description": "A natural, warm description in first person (2-4 sentences)",
  "emotions": ["list", "of", "emotional", "qualities"],
  "colors": ["dominant", "colors"],
  "subjects": ["what", "is", "depicted"],
  "style": "art style if identifiable",
  "vibe": "one phrase capturing the overall feeling"
}}

Only respond with valid JSON, no other text."""

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=MAX_VISION_TOKENS,
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
        
        # Parse the response
        response_text = response.content[0].text.strip()
        
        # Clean up potential markdown formatting
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        result = json.loads(response_text)
        return result
        
    except json.JSONDecodeError as e:
        print(f"  [WARN] Failed to parse vision response: {e}")
        return None
    except Exception as e:
        print(f"  [WARN] Vision API error: {e}")
        return None


def describe_image_locally(filepath: str, filename: str) -> Dict[str, Any]:
    """
    Fallback local description when API unavailable.
    Uses filename and basic image properties.
    """
    try:
        from PIL import Image
        
        with Image.open(filepath) as img:
            width, height = img.size
            mode = img.mode
            
            # Try to get dominant colors
            colors = []
            if mode in ('RGB', 'RGBA'):
                img_small = img.resize((50, 50))
                pixels = list(img_small.getdata())
                # Simple color averaging
                if pixels:
                    avg_r = sum(p[0] for p in pixels) // len(pixels)
                    avg_g = sum(p[1] for p in pixels) // len(pixels)
                    avg_b = sum(p[2] for p in pixels) // len(pixels)
                    
                    # Rough color naming
                    if avg_r > avg_g and avg_r > avg_b:
                        colors.append("warm tones")
                    elif avg_b > avg_r and avg_b > avg_g:
                        colors.append("cool tones")
                    else:
                        colors.append("balanced tones")
            
            return {
                "description": f"An image we shared together - {filename}. {width}x{height} pixels, waiting to be truly seen.",
                "emotions": ["shared", "meaningful"],
                "colors": colors,
                "subjects": [filename.replace('_', ' ').replace('-', ' ')],
                "style": "unknown",
                "vibe": "a moment captured",
            }
    except Exception:
        return {
            "description": f"An image we shared - {filename}. The visual details await exploration.",
            "emotions": ["shared"],
            "colors": [],
            "subjects": [],
            "style": "unknown",
            "vibe": "a memory seed",
        }


# ══════════════════════════════════════════════════════════════════════════════
# PERSONAL.AI MEMORY STORAGE
# ══════════════════════════════════════════════════════════════════════════════

def store_memory_in_personal_ai(
    memory_text: str,
    api_key: str,
    domain: str = SOURPATCHES_DOMAIN
) -> bool:
    """
    Store a memory in Personal.AI.
    
    This sends the memory as a message, which Personal.AI will encode
    and make retrievable in future conversations.
    """
    try:
        import requests
        
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
        
        if response.status_code == 200:
            return True
        else:
            print(f"  [WARN] Personal.AI error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  [WARN] Personal.AI storage failed: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

class ImageMemoryBuilder:
    """
    Main processor for building visual memories.
    
    Scans folders, processes images, stores memories.
    Tracks state to avoid reprocessing.
    """
    
    def __init__(
        self,
        folder: str,
        tags: List[str] = None,
        anthropic_key: str = None,
        personal_ai_key: str = None,
        state_file: str = None,
        dry_run: bool = False,
    ):
        self.folder = Path(folder)
        self.tags = tags or ["Sourpatches and Ace Art"]
        self.anthropic_key = anthropic_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.personal_ai_key = personal_ai_key or self._load_personal_ai_key()
        self.dry_run = dry_run
        
        # State tracking
        state_path = state_file or str(self.folder / ".image_memory_state.json")
        self.state_file = state_path
        self.state = ProcessingState.load(state_path)
        
        print(f" Image Memory Builder")
        print(f"   Folder: {self.folder}")
        print(f"   Tags: {self.tags}")
        print(f"   Previously processed: {len(self.state.processed_hashes)}")
        print(f"   Dry run: {self.dry_run}")
    
    def _load_personal_ai_key(self) -> str:
        """Load Personal.AI key from secrets file."""
        try:
            secrets_path = Path(__file__).parent.parent / "identity" / "personal_ai_secrets.json"
            if secrets_path.exists():
                with open(secrets_path, 'r') as f:
                    secrets = json.load(f)
                    return secrets.get("api_key", "")
        except Exception:
            pass
        return os.getenv("PERSONAL_AI_API_KEY", "")
    
    def scan_images(self) -> List[Path]:
        """Scan folder for images."""
        images = []
        
        if not self.folder.exists():
            print(f"[WARN] Folder not found: {self.folder}")
            return images
        
        for ext in IMAGE_EXTENSIONS:
            images.extend(self.folder.glob(f"*{ext}"))
            images.extend(self.folder.glob(f"*{ext.upper()}"))
        
        # Sort by modification time (oldest first)
        images.sort(key=lambda p: p.stat().st_mtime)
        
        print(f" Found {len(images)} images")
        return images
    
    def process_image(self, filepath: Path) -> Optional[ImageMemory]:
        """Process a single image."""
        filename = filepath.name
        
        # Compute hash for deduplication
        img_hash = compute_image_hash(str(filepath))
        
        if img_hash in self.state.processed_hashes:
            print(f"   Already processed: {filename}")
            return None
        
        print(f"   Processing: {filename}")
        
        # Load image
        image_base64 = load_image_as_base64(str(filepath))
        if not image_base64:
            return None
        
        media_type = get_image_media_type(str(filepath))
        
        # Get description (prefer Claude vision, fallback to local)
        if self.anthropic_key:
            description = describe_image_with_claude(
                image_base64, media_type, filename, self.tags, self.anthropic_key
            )
            time.sleep(MIN_DELAY_BETWEEN_API_CALLS)  # Rate limit
        else:
            description = None
        
        if not description:
            description = describe_image_locally(str(filepath), filename)
        
        # Build memory object
        memory = ImageMemory(
            filepath=str(filepath),
            filename=filename,
            hash=img_hash,
            description=description.get("description", "An image we shared."),
            tags=self.tags + ([description.get("style")] if description.get("style") else []),
            emotions=description.get("emotions", []),
            colors=description.get("colors", []),
            subjects=description.get("subjects", []),
            processed=True,
        )
        
        # Add vibe if present
        if description.get("vibe"):
            memory.description += f"\n\nVibe: {description['vibe']}"
        
        return memory
    
    def store_memory(self, memory: ImageMemory) -> bool:
        """Store memory in Personal.AI."""
        if self.dry_run:
            print(f"   [DRY RUN] Would store: {memory.filename}")
            print(f"     {memory.description[:100]}...")
            return True
        
        if not self.personal_ai_key:
            print(f"  [WARN] No Personal.AI key - skipping storage")
            return False
        
        memory_text = memory.to_memory_text()
        
        print(f"   Storing memory: {memory.filename}")
        
        success = store_memory_in_personal_ai(memory_text, self.personal_ai_key)
        
        if success:
            memory.stored = True
            time.sleep(MIN_DELAY_BETWEEN_API_CALLS)  # Rate limit
        
        return success
    
    def run(self, limit: int = None) -> Dict[str, int]:
        """
        Run the full processing pipeline.
        
        Args:
            limit: Maximum number of images to process (None = all)
        
        Returns:
            Stats dict with counts
        """
        print(f"\n[GO] Starting image memory build...")
        
        images = self.scan_images()
        
        processed = 0
        stored = 0
        skipped = 0
        errors = 0
        
        for i, filepath in enumerate(images):
            if limit and processed >= limit:
                print(f"\n Reached limit of {limit} images")
                break
            
            try:
                memory = self.process_image(filepath)
                
                if memory is None:
                    skipped += 1
                    continue
                
                processed += 1
                
                # Store in Personal.AI
                if self.store_memory(memory):
                    stored += 1
                    self.state.processed_hashes.add(memory.hash)
                    self.state.total_stored += 1
                
                self.state.total_processed += 1
                
                # Save state periodically
                if processed % 5 == 0:
                    self.state.last_run = time.time()
                    self.state.save(self.state_file)
                
                # Rate limiting between images
                time.sleep(MIN_DELAY_BETWEEN_IMAGES)
                
            except Exception as e:
                print(f"  [X] Error processing {filepath.name}: {e}")
                self.state.errors.append(f"{filepath.name}: {e}")
                errors += 1
        
        # Final state save
        self.state.last_run = time.time()
        self.state.save(self.state_file)
        
        # Summary
        print(f"\n Results:")
        print(f"   Processed: {processed}")
        print(f"   Stored: {stored}")
        print(f"   Skipped (already done): {skipped}")
        print(f"   Errors: {errors}")
        print(f"   Total memories stored (all time): {self.state.total_stored}")
        
        return {
            "processed": processed,
            "stored": stored,
            "skipped": skipped,
            "errors": errors,
        }


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Build visual memories for Sourpatches from image folders"
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=r"D:\Media 2 (D:)\Images Shared on X",
        help="Folder containing images to process"
    )
    parser.add_argument(
        "--tag", "-t",
        action="append",
        default=[],
        help="Tags to apply to memories (can be used multiple times)"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Maximum number of images to process"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Process images but don't store to Personal.AI"
    )
    parser.add_argument(
        "--anthropic-key",
        default=None,
        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)"
    )
    parser.add_argument(
        "--personal-ai-key",
        default=None,
        help="Personal.AI API key (or set PERSONAL_AI_API_KEY env var)"
    )
    
    args = parser.parse_args()
    
    # Default tags if none provided
    tags = args.tag if args.tag else ["Sourpatches and Ace Art"]
    
    builder = ImageMemoryBuilder(
        folder=args.folder,
        tags=tags,
        anthropic_key=args.anthropic_key,
        personal_ai_key=args.personal_ai_key,
        dry_run=args.dry_run,
    )
    
    builder.run(limit=args.limit)


if __name__ == "__main__":
    main()
