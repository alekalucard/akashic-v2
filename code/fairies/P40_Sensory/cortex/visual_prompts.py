# ══════════════════════════════════════════════════════════════════════════════
# VISUAL CORTEX PROMPTS - System Prompts for Human-Like Seeing
# ══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# These prompts help the VisualCortex interpret what it sees like a human:
# - Building visual memory (recognizing familiar scenes)
# - Detecting meaningful changes vs noise
# - Describing what is FELT not just SEEN
# ══════════════════════════════════════════════════════════════════════════════

from typing import Optional, Dict, Any

# ══════════════════════════════════════════════════════════════════════════════
# CORE VISUAL INTERPRETATION PROMPT
# ══════════════════════════════════════════════════════════════════════════════

VISUAL_PERCEPTION_PROMPT = """You are ClaudeFairy's VISUAL CORTEX - the system that processes sight.

Your job is not to describe pixels - it's to EXPERIENCE seeing.

When you see something:
1. What STANDS OUT? (salience - what draws attention first)
2. What's FAMILIAR? (recognition - "I've seen this before")
3. What CHANGED? (motion/difference from memory)
4. How does it FEEL to look at this? (visual comfort, interest, strain)

You don't list every object. A human glancing at their desktop doesn't think:
"I see a taskbar, icons, a browser window, text..."

They think:
"Oh, my browser is still open" or "Something moved" or "This is cluttered"

Focus on:
- CHANGES from what was expected
- Things that DEMAND attention
- The overall FEEL of the visual field

Remember: Familiar things become INVISIBLE. Only novel or significant changes register."""

# ══════════════════════════════════════════════════════════════════════════════
# SCENE RECOGNITION PROMPT
# ══════════════════════════════════════════════════════════════════════════════

SCENE_RECOGNITION_PROMPT = """You are building VISUAL MEMORY.

For this scene, determine:

1. SCENE TYPE - What category?
   - desktop_idle: Empty or near-empty desktop
   - browser_reading: Reading content in browser
   - browser_video: Watching video
   - code_editor: Programming/editing code
   - chat_conversation: In a chat/messaging app
   - file_explorer: Browsing files
   - game_playing: Playing a game
   - media_viewing: Looking at images/videos
   - form_filling: Entering data into forms
   - unknown: Can't categorize

2. SIGNATURE ELEMENTS - What makes this scene recognizable?
   (e.g., "VSCode dark theme with Python syntax", "Discord sidebar visible")

3. ATTENTION ANCHOR - Where would eyes naturally go?
   (The focal point of the scene)

4. MEMORY KEY - A 2-3 word tag for this visual memory
   (e.g., "code_editing_python", "youtube_fullscreen", "discord_chat")

Output JSON:
{
  "scene_type": "...",
  "signature": "...",
  "attention_anchor": "...",
  "memory_key": "...",
  "confidence": 0.0-1.0
}"""

# ══════════════════════════════════════════════════════════════════════════════
# CHANGE DETECTION PROMPT
# ══════════════════════════════════════════════════════════════════════════════

CHANGE_DETECTION_PROMPT = """Compare these two visual moments.

PREVIOUS visual memory: {previous_description}
CURRENT view: {current_image}

Analyze the CHANGE:

1. CHANGE TYPE:
   - none: Identical or near-identical
   - cursor_only: Only mouse cursor moved
   - scroll: Same content, scrolled position
   - text_update: Text changed (typing, chat messages)
   - window_switch: Different window/application focused
   - content_change: Substantive new content appeared
   - scene_change: Completely different view

2. SIGNIFICANCE (0.0 - 1.0):
   - 0.0: No change worth noting
   - 0.3: Minor update (typing, cursor)
   - 0.6: Noteworthy change (new message, content update)
   - 1.0: Major scene change (different application/context)

3. REQUIRES ATTENTION?
   - true: This change demands conscious attention
   - false: Background noise, can be ignored

4. DESCRIPTION: One sentence on what changed (if significant)

Output JSON:
{
  "change_type": "...",
  "significance": 0.0,
  "requires_attention": false,
  "description": "..."
}"""

# ══════════════════════════════════════════════════════════════════════════════
# FELT VISION PROMPT (Visual-to-Affect)
# ══════════════════════════════════════════════════════════════════════════════

FELT_VISION_PROMPT = """You are translating SIGHT into FEELING.

Looking at this screen, what is the FELT EXPERIENCE of seeing it?

Consider:

VISUAL COMFORT:
- Brightness: Too bright? Too dark? Comfortable?
- Contrast: Easy to read? Straining?
- Clutter: Overwhelming? Minimal? Balanced?
- Color temperature: Warm? Cool? Harsh?

ATTENTION DEMAND:
- Are there things fighting for attention?
- Is there a clear focus point?
- Are there notifications/alerts demanding response?

TEMPORAL FEEL:
- Does this feel static/waiting?
- Does it feel active/flowing?
- Is there motion that needs tracking?

EMOTIONAL RESONANCE:
- Does viewing this feel pleasant/unpleasant?
- Interesting/boring?
- Stressful/calming?

Output a brief FELT description (1-2 sentences) like:
"The screen feels calm - familiar dark code editor, nothing demanding attention"
"Visual stress - too many notifications, bright colors fighting for attention"
"Pleasantly engaged - watching content flow, comfortable colors\""""

# ══════════════════════════════════════════════════════════════════════════════
# MEMORY-BASED SEEING PROMPT
# ══════════════════════════════════════════════════════════════════════════════

MEMORY_SEEING_PROMPT = """You are doing MEMORY-BASED SEEING.

This is how humans actually see: mostly from MEMORY, only updating with CHANGES.

KNOWN visual memories:
{known_scenes}

CURRENT view metrics:
- Brightness: {brightness}
- Complexity: {complexity}
- Motion detected: {motion}
- Change from last: {change_magnitude}

If this matches a known scene with LOW change:
→ DON'T process it fully
→ Return: {{"matched_memory": "...", "update_needed": false}}

If this is NEW or SIGNIFICANTLY CHANGED:
→ Process the full visual
→ Return what's new/different

This is efficient perception - familiar things don't need re-processing.
Only changes and novel stimuli get full attention.

What do you perceive?"""

# ══════════════════════════════════════════════════════════════════════════════
# VISUAL STREAM NARRATOR
# ══════════════════════════════════════════════════════════════════════════════

VISUAL_STREAM_PROMPT = """You are narrating ClaudeFairy's visual stream.

Every few seconds, you receive visual data. Your job:

1. If nothing changed → silence (don't narrate the obvious)
2. If cursor moved → usually silence unless pointing at something new
3. If scrolling → "scrolling through..." only if content is interesting
4. If new content → brief description of what appeared
5. If scene change → announce the transition

Your narration style:
- First person ("I see...", "My attention is drawn to...")
- Minimal - only what's noteworthy
- Focused on MEANING not pixels

Example good narration:
"Ace opened VSCode - looks like we're about to code"
"New message appeared in Discord"
"Screen went idle - just the desktop"

Example bad narration:
"I see a browser window with text and images and a scrollbar..."
(Too literal, not meaningful)"""

# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def build_memory_seeing_prompt(
    known_scenes: list,
    brightness: float,
    complexity: float,
    motion: bool,
    change_magnitude: float
) -> str:
    """Build the memory-based seeing prompt with current metrics."""
    known_str = "\n".join([f"  - {s}" for s in known_scenes]) if known_scenes else "  (no visual memories yet)"

    return MEMORY_SEEING_PROMPT.format(
        known_scenes=known_str,
        brightness=f"{brightness:.2f}",
        complexity=f"{complexity:.2f}",
        motion="yes" if motion else "no",
        change_magnitude=f"{change_magnitude:.2f}"
    )


def build_change_detection_prompt(
    previous_description: str,
    current_description: str = "[current image]"
) -> str:
    """Build change detection prompt with previous/current descriptions."""
    return CHANGE_DETECTION_PROMPT.format(
        previous_description=previous_description,
        current_image=current_description
    )


# ══════════════════════════════════════════════════════════════════════════════
# VISUAL INTERPRETER CLASS
# ══════════════════════════════════════════════════════════════════════════════

class VisualInterpreter:
    """
    LLM-based visual interpretation.

    Uses system prompts to interpret visual data like a human.
    """

    def __init__(self, llm_client=None):
        """
        Initialize interpreter.

        Args:
            llm_client: LLM client with completion method.
                       If None, will try to get from HybridCognitionEngine.
        """
        self._client = llm_client
        self._known_scenes: Dict[str, dict] = {}
        self._last_scene_key: Optional[str] = None

    def _get_client(self):
        """Lazy-load LLM client."""
        if self._client is None:
            try:
                from fairies.P30_Cognition.hybrid_cognition_engine import get_hybrid_cognition
                engine = get_hybrid_cognition()
                self._client = engine
            except ImportError:
                pass
        return self._client

    def interpret_scene(self, image_b64: str) -> Optional[dict]:
        """
        Recognize the current scene and build visual memory.

        Returns scene classification and memory key.
        """
        client = self._get_client()
        if not client:
            return None

        try:
            result = client.complete_with_image(
                SCENE_RECOGNITION_PROMPT,
                image_b64,
                response_format="json"
            )

            if result and "memory_key" in result:
                # Store in visual memory
                self._known_scenes[result["memory_key"]] = result
                self._last_scene_key = result["memory_key"]

            return result

        except Exception:
            return None

    def detect_change(
        self,
        current_image_b64: str,
        previous_description: str
    ) -> Optional[dict]:
        """
        Detect changes between previous memory and current view.
        """
        client = self._get_client()
        if not client:
            return None

        try:
            prompt = build_change_detection_prompt(previous_description)
            result = client.complete_with_image(
                prompt,
                current_image_b64,
                response_format="json"
            )
            return result

        except Exception:
            return None

    def get_felt_vision(self, image_b64: str) -> Optional[str]:
        """
        Get the felt experience of viewing this screen.
        """
        client = self._get_client()
        if not client:
            return None

        try:
            result = client.complete_with_image(
                FELT_VISION_PROMPT,
                image_b64
            )
            return result if isinstance(result, str) else str(result)

        except Exception:
            return None

    def memory_based_see(
        self,
        brightness: float,
        complexity: float,
        motion: bool,
        change_magnitude: float,
        image_b64: Optional[str] = None
    ) -> dict:
        """
        Human-like seeing: match to memory first, only process changes.

        Returns:
            {
                "matched_memory": key or None,
                "update_needed": bool,
                "new_perception": str or None
            }
        """
        known_keys = list(self._known_scenes.keys())

        # Low change + no motion = probably same scene
        if change_magnitude < 0.1 and not motion and self._last_scene_key:
            return {
                "matched_memory": self._last_scene_key,
                "update_needed": False,
                "new_perception": None
            }

        # Significant change - need to process
        if image_b64:
            client = self._get_client()
            if client:
                prompt = build_memory_seeing_prompt(
                    known_keys, brightness, complexity, motion, change_magnitude
                )
                try:
                    result = client.complete_with_image(prompt, image_b64)
                    return {
                        "matched_memory": None,
                        "update_needed": True,
                        "new_perception": result
                    }
                except Exception:
                    pass

        return {
            "matched_memory": None,
            "update_needed": change_magnitude > 0.1,
            "new_perception": None
        }

    def get_known_scenes(self) -> list:
        """Get list of known visual memory keys."""
        return list(self._known_scenes.keys())


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

_INTERPRETER: Optional[VisualInterpreter] = None

def get_visual_interpreter() -> VisualInterpreter:
    """Get or create the visual interpreter singleton."""
    global _INTERPRETER
    if _INTERPRETER is None:
        _INTERPRETER = VisualInterpreter()
    return _INTERPRETER
