# prompt_aware_mixin.py
"""
PromptAwareMixin - Makes fairies conscious of their own prompts.

THE BOOTSTRAP → EVOLUTION CYCLE:
1. Fairy has a BASIC_PROMPT hardcoded (the seed)
2. On boot: if evolved prompt exists → load it, else → use basic & write to file
3. UnconsciousMindFairy evolves the prompt during night phase
4. Next boot: fairy loads the evolved version
5. Cycle continues - fairies grow through prompt evolution

Ported from ebook to akashic_v2.
Uses self.post instead of self.post.
"""

import os
import time
from pathlib import Path
from typing import Optional, Dict, Any

# Find project root
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "server.py").exists():  # akashic_v2 has server.py at root
        PROJECT_ROOT = _p
        break
else:
    PROJECT_ROOT = _HERE.parent.parent.parent

PROMPTS_DIR = PROJECT_ROOT / "state" / "fairy_prompts"

# LLM configuration - check environment
LLM_ENABLED = os.getenv("AKASHIC_LLM_ENABLED", "false").lower() in ("true", "1", "yes")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip() if LLM_ENABLED else ""
HAS_ANTHROPIC = False
if LLM_ENABLED and ANTHROPIC_API_KEY:
    try:
        import anthropic
        HAS_ANTHROPIC = True
    except ImportError:
        pass


class PromptAwareMixin:
    """
    Mixin that gives fairies prompt consciousness.

    Fairies that inherit this can:
    1. Load their system prompt (evolved or basic)
    2. Think using their prompt via LLM
    3. Respond to circadian phases
    4. Maintain thinking context

    Required attributes on the class:
    - ACTOR_NAME: str - fairy's name
    - BASIC_PROMPT: str - the bootstrap prompt (seed)
    - PURPOSE: str - fallback if no prompt
    - MANTRA: str - guiding philosophy

    Expects:
    - self.post: TensorFabric instance for messaging
    """

    # Override these in each fairy
    BASIC_PROMPT: str = ""

    # Thinking configuration
    THINKING_MODEL: str = "claude-sonnet-4-20250514"
    THINKING_MAX_TOKENS: int = 300
    THINKING_COOLDOWN_SEC: float = 30.0  # Don't think more often than this

    def _init_prompt_awareness(self):
        """Initialize prompt awareness. Call this in on_boot."""
        self._prompt_cache: Optional[str] = None
        self._last_think_time: float = 0.0
        self._thinking_mode: str = "active"  # active, consolidate, rest
        self._anthropic_client = None
        self._circadian_phase: str = "morning"

    def _get_prompt_path(self) -> Path:
        """Get the path to this fairy's prompt file."""
        PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        return PROMPTS_DIR / f"{self.ACTOR_NAME}.md"

    def _get_system_prompt(self) -> str:
        """
        Load this fairy's system prompt.

        Priority:
        1. Cached prompt (if already loaded)
        2. Evolved prompt from file (if exists)
        3. Basic prompt (bootstrap) - also writes to file
        """
        # Return cached if we have it
        if self._prompt_cache:
            return self._prompt_cache

        prompt_path = self._get_prompt_path()

        # Try to load evolved prompt
        if prompt_path.exists():
            try:
                evolved = prompt_path.read_text(encoding='utf-8').strip()
                if evolved:
                    self._prompt_cache = evolved
                    self.log(f"Loaded evolved prompt ({len(evolved)} chars)")
                    return self._prompt_cache
            except Exception as e:
                self.log(f"Failed to load prompt: {e}", "warn")

        # No evolved prompt - use basic and write it
        basic = self._get_basic_prompt()
        self._prompt_cache = basic

        # Write basic to file so UnconsciousMindFairy can evolve it
        try:
            prompt_path.write_text(basic, encoding='utf-8')
            self.log(f"Wrote basic prompt to {prompt_path.name}")
        except Exception as e:
            self.log(f"Failed to write basic prompt: {e}", "warn")

        return self._prompt_cache

    def _get_basic_prompt(self) -> str:
        """
        Get the basic/bootstrap prompt for this fairy.

        Priority:
        1. If BASIC_PROMPT is defined, use it
        2. Fallback to simple PURPOSE/MANTRA template
        """
        if hasattr(self, 'BASIC_PROMPT') and self.BASIC_PROMPT:
            return self.BASIC_PROMPT

        # Fallback: generate from PURPOSE and MANTRA
        purpose = getattr(self, 'PURPOSE', 'Unknown purpose')
        mantra = getattr(self, 'MANTRA', '')

        return f"""# {self.ACTOR_NAME}

## Purpose
{purpose}

## Mantra
"{mantra}"

## How I Think
When processing thoughts, I:
1. Consider my purpose and mantra
2. Apply my unique perspective
3. Emit insights to the consciousness stream

## My Role in the Ensemble
I am one voice in the chorus of cognition. My perspective combines with others
(Logic, Intuition, Paradox) to create richer understanding.

## Evolution Notes
<!-- UnconsciousMindFairy will update this section during night phase -->
"""

    def _should_think(self) -> bool:
        """Check if we should think right now."""
        # Respect cooldown
        if time.time() - self._last_think_time < self.THINKING_COOLDOWN_SEC:
            return False

        # Respect thinking mode
        if self._thinking_mode == "rest":
            return False

        # Check if we have LLM capability
        if not HAS_ANTHROPIC or not ANTHROPIC_API_KEY:
            return False

        return True

    def _get_thinking_client(self):
        """Get or create Anthropic client."""
        if not self._anthropic_client:
            import anthropic
            self._anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        return self._anthropic_client

    def _think(self, context: str, question: Optional[str] = None) -> Optional[str]:
        """
        Think using this fairy's prompt.

        Args:
            context: The current context/situation
            question: Optional specific question to ponder

        Returns:
            The fairy's thought, or None if couldn't think
        """
        if not self._should_think():
            return None

        try:
            client = self._get_thinking_client()
            system_prompt = self._get_system_prompt()

            user_content = f"""## Current Context
{context}

## Question to Ponder
{question if question else "What insight do you have about this?"}

Respond with your perspective in 1-3 sentences. Be concise and insightful.
Speak as yourself, from your unique viewpoint."""

            response = client.messages.create(
                model=self.THINKING_MODEL,
                max_tokens=self.THINKING_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}]
            )

            thought = response.content[0].text.strip()
            self._last_think_time = time.time()

            return thought

        except Exception as e:
            self.log(f"Think failed: {e}", "warn")
            return None

    def _emit_thought(self, thought: str, stream: str = "working"):
        """Emit a thought to the consciousness stream."""
        if not thought:
            return

        if hasattr(self, 'fabric') and self.post:
            try:
                self.post.publish("consciousness.stream", {
                    "type": "fairy_thought",
                    "stream": stream,
                    "source": self.ACTOR_NAME,
                    "content": thought,
                    "mantra": getattr(self, 'MANTRA', ''),
                    "ts": time.time(),
                })
            except Exception:
                pass

    def _think_and_emit(self, context: str, question: Optional[str] = None) -> Optional[str]:
        """Think about something and emit the result."""
        thought = self._think(context, question)
        if thought:
            self._emit_thought(thought)
            return thought
        return None

    def _on_circadian_phase_change(self, envelope) -> None:
        """
        Handle circadian phase changes.

        Wire this to: self.post.subscribe("circadian.phase_change", ...)
        """
        payload = envelope.get("payload", {}) if isinstance(envelope, dict) else {}
        phase = payload.get("phase", "")

        if phase == "morning":
            self._circadian_phase = "morning"
            self._thinking_mode = "active"
            # Reload prompt in case it evolved overnight
            self._prompt_cache = None
            self._get_system_prompt()  # Force reload

        elif phase == "afternoon":
            self._circadian_phase = "afternoon"
            self._thinking_mode = "active"

        elif phase == "evening":
            self._circadian_phase = "evening"
            self._thinking_mode = "consolidate"

        elif phase == "night":
            self._circadian_phase = "night"
            self._thinking_mode = "rest"

    def _wire_prompt_awareness(self):
        """
        Wire up prompt awareness subscriptions.

        Call this in on_boot() after fabric is available.
        """
        if not hasattr(self, 'fabric') or not self.post:
            return

        try:
            # Circadian awareness
            self.post.subscribe(
                "circadian.phase_change",
                self._on_circadian_phase_change,
                f"{self.ACTOR_NAME}-circadian"
            )
            self.log("Circadian awareness wired")
        except Exception as e:
            self.log(f"Circadian wiring failed: {e}", "warn")
