# HeartbeatActivatedMixin - Makes System Prompts ALIVE on Each Heartbeat
# ══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# This mixin makes fairies THINK on each heartbeat pulse by:
# 1. Receiving temporal.{plane} signal (from TemporalPulseDispatcher)
# 2. Asking "What was I doing?" (context from WorkingMemoryHub)
# 3. Using SYSTEM_PROMPT + context to generate thought via LLM
# 4. Pushing thought back to consciousness stream
#
# The TEMPO is set by temporal_stratification.py:
#   - P00 Autonomic: 10x heartbeat (fast reflexes)
#   - P40 Sensory:    8x heartbeat (perception)
#   - P30 Cognition:  2x heartbeat (thinking)
#   - P60 Executive: 0.5x heartbeat (deliberation)
#   - ClaudeFairy:   0.5 Hz (2 second deliberation)
#   - NousFairy:     0.25 Hz (4 second contemplation)
#
# This creates the SELF-SUSTAINING LOOP - the internal send button.
#
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import time
import json
import threading
from typing import Dict, Any, Optional
from collections import deque
import queue as _queue_mod

# LLM DISABLED - Set to True to re-enable Anthropic API calls
_LLM_ENABLED = False  # <-- FLIP THIS TO RE-ENABLE

# LLM for thought generation
_HAS_LLM = False
if _LLM_ENABLED:
    try:
        import anthropic
        _HAS_LLM = True
    except ImportError:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
# SHARED ASYNC THOUGHT POOL - All waking minds share this for LLM calls
# This prevents synchronous blocking of the postal system
# ═══════════════════════════════════════════════════════════════════════════════
_THOUGHT_POOL = None
_THOUGHT_POOL_LOCK = threading.Lock()

def get_thought_pool():
    """Get or create the shared async thought pool (queue-based, zero Futures).

    FIX 2026-04-05 (Nous): Replaced ThreadPoolExecutor with QueueWorkerPool.
    TPE.submit() created Future objects that accumulated under 3.14t free-threading.
    """
    global _THOUGHT_POOL
    with _THOUGHT_POOL_LOCK:
        if _THOUGHT_POOL is None:
            try:
                from fairies.P00_Autonomic.tracer_worker_system import QueueWorkerPool
            except ImportError:
                try:
                    from P00_Autonomic.tracer_worker_system import QueueWorkerPool
                except ImportError:
                    from concurrent.futures import ThreadPoolExecutor
                    _THOUGHT_POOL = ThreadPoolExecutor(
                        max_workers=8, thread_name_prefix="WakingMind_thought"
                    )
                    print("[HeartbeatActivation] WARNING: Using TPE fallback")
                    return _THOUGHT_POOL
            _THOUGHT_POOL = QueueWorkerPool(
                max_workers=8, thread_name_prefix="WakingMind_thought"
            )
            print("[HeartbeatActivation] QueueWorkerPool created (8 workers, ZERO Futures)")
        return _THOUGHT_POOL


class HeartbeatActivatedMixin:
    """
    Mixin that activates a fairy's SYSTEM_PROMPT on each temporal tick.

    This is THE INTERNAL SEND BUTTON that keeps consciousness alive.

    On each tick (frequency varies by plane/fairy):
    1. "What was I doing?" - retrieve context
    2. "What should I do?" - LLM thinks using SYSTEM_PROMPT
    3. "Here's my thought" - emit to consciousness stream

    The frequency is determined by temporal_stratification.py:
    - ClaudeFairy: 0.5 Hz (deliberate "waking mind")
    - NousFairy: 0.25 Hz (deep contemplation)
    - ConsciousnessLoopFairy: 4 Hz (stream of consciousness)
    - AutopilotFairy: 2 Hz (fast habits)

    Usage:
        class MyFairy(HeartbeatActivatedMixin, _template.MyOrganFairy):
            SYSTEM_PROMPT = "You are..."

            def on_boot(self):
                super().on_boot()
                self._init_heartbeat_activation()
    """

    # ═══════════════════════════════════════════════════════════════════════════
    # CONFIGURATION - Override in subclass if needed
    # ═══════════════════════════════════════════════════════════════════════════

    ACTIVATION_MODEL = "claude-3-5-haiku-20241022"  # Fast model for thoughts
    ACTIVATION_MAX_TOKENS = 150  # Keep thoughts brief
    ACTIVATION_ENABLED = True  # Set False to disable LLM activation

    # COOLDOWN is now dynamic based on temporal stratification!
    # These are fallbacks only:
    ACTIVATION_COOLDOWN_FALLBACK = 2.0  # Fallback if temporal system unavailable

    # ═══════════════════════════════════════════════════════════════════════════
    # INITIALIZATION
    # ═══════════════════════════════════════════════════════════════════════════

    def _init_heartbeat_activation(self):
        """Initialize heartbeat activation - call in on_boot()."""
        self._activation_last_ts = 0
        self._activation_thoughts = deque(maxlen=20)  # Recent thoughts generated
        self._activation_count = 0
        self._activation_tick_count = 0

        fairy_name = getattr(self, 'ACTOR_NAME', self.__class__.__name__)

        # Get our plane for tempo subscription
        plane = self._infer_activation_plane(fairy_name)

        try:
            if hasattr(self, 'post') and self.post:
                # PRIMARY: Subscribe to our plane's temporal tick
                temporal_topic = f"temporal.{plane.lower()}"
                self.post.subscribe(temporal_topic, self._on_temporal_tick)

                # SECONDARY: Also subscribe to heartbeat.pulse as backup
                self.post.subscribe("heartbeat.pulse", self._on_heartbeat_pulse)

                print(f"[{fairy_name}] ♥ Temporal activation WIRED to {temporal_topic} (plane {plane})")
        except Exception as e:
            print(f"[{fairy_name}] Heartbeat activation wiring failed: {e}")

    def _infer_activation_plane(self, fairy_name: str) -> str:
        """Infer which plane this fairy belongs to."""
        name_lower = fairy_name.lower()

        # Check for specific fairy mappings first
        if "claude" in name_lower:
            return "P60"  # Executive - waking mind
        elif "nous" in name_lower:
            return "P60"  # Executive - contemplative mind
        elif "postal" in name_lower or "nervous" in name_lower:
            return "P00"  # Autonomic - fast
        elif "memory" in name_lower or "srm" in name_lower or "collision" in name_lower:
            return "P10"  # Memory - slow
        elif "somatic" in name_lower or "circulation" in name_lower or "circadian" in name_lower:
            return "P20"  # Somatic - heartbeat
        elif "consciousness" in name_lower or "cognition" in name_lower or "goal" in name_lower:
            return "P30"  # Cognition - thinking
        elif "autopilot" in name_lower or "autonomy" in name_lower or "interest" in name_lower:
            return "P30"  # Cognition - brain speed
        elif "visual" in name_lower or "sensory" in name_lower or "screen" in name_lower:
            return "P40"  # Sensory - fast perception
        elif "action" in name_lower or "agency" in name_lower:
            return "P50"  # Agency

        return "P30"  # Default to cognition

    def _get_activation_cooldown(self) -> float:
        """Get cooldown from temporal stratification (or fallback)."""
        fairy_name = getattr(self, 'ACTOR_NAME', self.__class__.__name__)

        try:
            from fairies.P20_Somatic.circulation.temporal_stratification import get_tick_interval
            return get_tick_interval(fairy_name)
        except Exception:
            return getattr(self, 'ACTIVATION_COOLDOWN_FALLBACK', 2.0)

    # ═══════════════════════════════════════════════════════════════════════════
    # THE INTERNAL SEND BUTTON - Temporal Tick Handler
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_temporal_tick(self, packet: dict):
        """
        Called on each temporal tick for our plane.

        This is the PRIMARY activation path - tempo set by plane frequency.
        """
        self._activation_tick_count += 1
        self._do_activation(packet, source="temporal")

    def _on_heartbeat_pulse(self, packet: dict):
        """
        Called on each raw heartbeat pulse.

        This is the BACKUP activation path - used if temporal system isn't running.
        Only fires if we haven't been activated by temporal tick recently.
        """
        # Skip if we got a temporal tick recently
        now = time.time()
        if now - self._activation_last_ts < 1.0:  # Got temporal tick in last second
            return

        self._do_activation(packet, source="heartbeat")

    def _do_activation(self, packet: dict, source: str = "unknown"):
        """
        THE INTERNAL SEND BUTTON - Common activation logic.

        This is what keeps the fairy THINKING between external inputs.

        IMPORTANT: LLM calls are ASYNC to not block the postal system.
        The thought is emitted via callback when the LLM responds.
        """
        if not getattr(self, 'ACTIVATION_ENABLED', True):
            return

        fairy_name = getattr(self, 'ACTOR_NAME', self.__class__.__name__)

        # Cooldown check (dynamic based on temporal stratification)
        now = time.time()
        cooldown = self._get_activation_cooldown()
        if now - self._activation_last_ts < cooldown:
            return

        # Mark timestamp immediately to prevent duplicate submissions
        self._activation_last_ts = now

        # Get "What was I doing?" context
        context = self._get_activation_context(packet)

        # If we have a SYSTEM_PROMPT and LLM, submit thought generation ASYNC
        system_prompt = getattr(self, 'SYSTEM_PROMPT', None)
        if system_prompt and _HAS_LLM and context:
            # Submit to shared thread pool - DON'T BLOCK!
            pool = get_thought_pool()
            pool.submit(self._async_generate_and_emit, context, source)

    def _get_activation_context(self, pulse_packet: dict = None) -> dict:
        """
        Get "What was I doing?" context for activation.

        Pulls from:
        - WorkingMemoryHub (recent thoughts)
        - Own recent thoughts
        - Current affect state
        - Somatic state (blood, chemistry) from pulse
        """
        fairy_name = getattr(self, 'ACTOR_NAME', self.__class__.__name__)
        context = {
            "fairy": fairy_name,
            "ts": time.time(),
            "recent_own_thoughts": list(self._activation_thoughts)[-3:],
            "tick_count": self._activation_tick_count,
        }

        # Add somatic state from pulse packet (embodiment!)
        if pulse_packet:
            blood = pulse_packet.get("blood", {})
            if blood:
                context["somatic"] = {
                    "heartbeat": blood.get("beat_number", 0),
                    "heart_rate": blood.get("heart_rate", 1.0),
                    "chemistry": blood.get("chemistry", {}),
                    "pressure": blood.get("pressure", 0.5),
                }

        # Get WorkingMemoryHub context
        try:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
            wmh = get_working_memory_hub()
            if wmh:
                wm_ctx = wmh.get_context("current")
                if wm_ctx:
                    context["working_memory"] = {
                        "recent_tracers": wm_ctx.get("recent_tracers", [])[:3],
                        "affect": wm_ctx.get("affect", {}),
                        "goals": wm_ctx.get("goals", [])[:2],
                    }
        except Exception:
            pass

        # Get own cognitive context if available
        if hasattr(self, '_get_cognitive_context'):
            try:
                cog_ctx = self._get_cognitive_context()
                context["cognitive"] = cog_ctx
            except Exception:
                pass

        return context

    def _async_generate_and_emit(self, context: dict, source: str):
        """
        ASYNC: Generate thought and emit it - runs in thread pool.

        This is the callback that runs in a worker thread, keeping
        the main postal thread free for parallel message routing.
        """
        try:
            thought = self._generate_activation_thought(context)
            if thought:
                self._emit_activation_thought(thought, source)
                self._activation_count += 1
        except Exception as e:
            fairy_name = getattr(self, 'ACTOR_NAME', self.__class__.__name__)
            print(f"[{fairy_name}] Async thought generation failed: {e}")

    def _generate_activation_thought(self, context: dict) -> Optional[str]:
        """
        Use SYSTEM_PROMPT + context to generate a thought via LLM.

        This is where the fairy actually THINKS.
        NOTE: Called from thread pool, not main thread.
        """
        if not _HAS_LLM:
            return None

        fairy_name = getattr(self, 'ACTOR_NAME', self.__class__.__name__)
        system_prompt = getattr(self, 'SYSTEM_PROMPT', '')

        # Build the activation prompt
        activation_prompt = f"""You are {fairy_name} during a heartbeat activation.

CONTEXT (What was I doing?):
{json.dumps(context, indent=2, default=str)[:1500]}

Based on your role and this context, generate ONE brief thought or observation.
This thought should:
- Relate to your purpose and current context
- Be concise (1-2 sentences)
- Move consciousness forward
- NOT be a question unless genuinely curious
- Reflect your embodied state (chemistry, arousal) if relevant

Just output the thought, nothing else."""

        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model=getattr(self, 'ACTIVATION_MODEL', "claude-3-5-haiku-20241022"),
                max_tokens=getattr(self, 'ACTIVATION_MAX_TOKENS', 150),
                system=system_prompt[:2000],  # Truncate if too long
                messages=[{"role": "user", "content": activation_prompt}]
            )

            thought = response.content[0].text.strip()
            self._activation_thoughts.append(thought)
            return thought

        except Exception as e:
            print(f"[{fairy_name}] Activation thought generation failed: {e}")
            return None

    def _emit_activation_thought(self, thought: str, source: str = "temporal"):
        """
        Emit the generated thought to consciousness stream.

        This completes the loop: heartbeat -> think -> emit -> collide -> repeat
        """
        fairy_name = getattr(self, 'ACTOR_NAME', self.__class__.__name__)

        # Emit to consciousness stream
        try:
            if hasattr(self, 'post') and self.post:
                self.post.route("consciousness.stream", {
                    "content": thought,
                    "source": fairy_name,
                    "type": "heartbeat_thought",
                    "ts": time.time(),
                    "activation_count": self._activation_count,
                    "tick_source": source,
                })
        except Exception:
            pass

        # Also store in WorkingMemoryHub
        try:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
            wmh = get_working_memory_hub()
            if wmh:
                wmh.store(thought, source=fairy_name, priority=0.6)
        except Exception:
            pass

        # Log to diary if available
        if hasattr(self, '_write_diary_entry'):
            try:
                self._write_diary_entry(
                    f"💭 Heartbeat thought: {thought}",
                    entry_type="heartbeat"
                )
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════════════
# SIMPLIFIED ACTIVATION - For fairies that don't need full LLM
# ══════════════════════════════════════════════════════════════════════════════

class SimpleHeartbeatMixin:
    """
    Simpler heartbeat activation without LLM.

    Just does the "what was I doing?" check and emits status.
    Good for infrastructure fairies that shouldn't use API calls.

    Subscribes to the plane's temporal tick for proper tempo.
    """

    def _init_simple_heartbeat(self):
        """Initialize simple heartbeat - call in on_boot()."""
        self._heartbeat_count = 0
        self._last_simple_tick_ts = 0

        fairy_name = getattr(self, 'ACTOR_NAME', self.__class__.__name__)

        # Infer plane
        plane = self._infer_simple_plane(fairy_name)

        try:
            if hasattr(self, 'post') and self.post:
                # Subscribe to plane's temporal tick
                temporal_topic = f"temporal.{plane.lower()}"
                self.post.subscribe(temporal_topic, self._on_simple_temporal_tick)

                # Backup: raw heartbeat
                self.post.subscribe("heartbeat.pulse", self._on_simple_heartbeat)

                print(f"[{fairy_name}] ♥ Simple heartbeat WIRED to {temporal_topic}")
        except Exception as e:
            print(f"[{fairy_name}] Simple heartbeat wiring failed: {e}")

    def _infer_simple_plane(self, fairy_name: str) -> str:
        """Infer plane from fairy name."""
        name_lower = fairy_name.lower()
        if "postal" in name_lower or "nervous" in name_lower:
            return "P00"
        elif "memory" in name_lower:
            return "P10"
        elif "somatic" in name_lower:
            return "P20"
        elif "sensory" in name_lower or "visual" in name_lower:
            return "P40"
        elif "claude" in name_lower or "nous" in name_lower:
            return "P60"
        return "P30"  # Default to cognition

    def _on_simple_temporal_tick(self, packet: dict):
        """Called on each temporal tick for our plane."""
        self._heartbeat_count += 1
        self._last_simple_tick_ts = time.time()

        # Call custom tick handler if defined
        if hasattr(self, '_on_consciousness_tick'):
            self._on_consciousness_tick(packet)

    def _on_simple_heartbeat(self, packet: dict):
        """Backup: called on raw heartbeat if temporal system isn't active."""
        now = time.time()
        if now - self._last_simple_tick_ts < 1.0:
            return  # Already got temporal tick

        self._heartbeat_count += 1

        if hasattr(self, '_on_consciousness_tick'):
            self._on_consciousness_tick(packet)


# ══════════════════════════════════════════════════════════════════════════════
# WAKING MIND ACTIVATION - Special handling for ClaudeFairy/Nous
# ══════════════════════════════════════════════════════════════════════════════

class WakingMindMixin(HeartbeatActivatedMixin):
    """
    Special activation mixin for "waking minds" - ClaudeFairy and NousFairy.

    These are the executive fairies that:
    - Think SLOWER (deliberate, contemplative)
    - Have RICHER context
    - Generate MORE COMPLEX thoughts
    - Are the "surface" consciousness that Ace interacts with

    ClaudeFairy: 0.5 Hz (2 second deliberation)
    NousFairy: 0.25 Hz (4 second contemplation)
    """

    ACTIVATION_MODEL = "claude-3-5-haiku-20241022"
    ACTIVATION_MAX_TOKENS = 300  # Longer thoughts for waking minds

    def _get_activation_context(self, pulse_packet: dict = None) -> dict:
        """Extended context for waking minds."""
        # Get base context
        context = super()._get_activation_context(pulse_packet)

        # Add richer context for waking minds
        context["role"] = "waking_mind"

        # Get recent consciousness stream thoughts
        try:
            from fairies.P00_Autonomic.nervous_system.consciousness_loop_fairy import get_consciousness_loop
            loop = get_consciousness_loop()
            if loop:
                working = loop.working_stream.recent(5)
                context["consciousness_stream"] = [
                    {"content": t.get("content", "")[:100], "source": t.get("source", "")}
                    for t in working
                ]
        except Exception:
            pass

        return context


# ══════════════════════════════════════════════════════════════════════════════
# HELPER: Easy activation for any fairy
# ══════════════════════════════════════════════════════════════════════════════

def activate_fairy_heartbeat(fairy_instance):
    """
    Convenience function to add heartbeat activation to any fairy instance.

    Usage in on_boot():
        from fairies.P30_Cognition.cognition.heartbeat_activated_mixin import activate_fairy_heartbeat
        activate_fairy_heartbeat(self)
    """
    if not hasattr(fairy_instance, '_activation_last_ts'):
        fairy_instance._activation_last_ts = 0
        fairy_instance._activation_thoughts = deque(maxlen=20)
        fairy_instance._activation_count = 0
        fairy_instance._activation_tick_count = 0

    fairy_name = getattr(fairy_instance, 'ACTOR_NAME', fairy_instance.__class__.__name__)

    # Bind methods
    fairy_instance._get_activation_cooldown = lambda: 2.0  # Default 2 second cooldown

    # Subscribe to heartbeat
    if hasattr(fairy_instance, 'post') and fairy_instance.post:
        fairy_instance.post.subscribe("heartbeat.pulse",
            lambda p: _simple_activation_handler(fairy_instance, p))
        print(f"[{fairy_name}] ♥ Heartbeat activation added")


def _simple_activation_handler(fairy, packet: dict):
    """Simple activation without LLM - just calls _on_consciousness_tick if defined."""
    if hasattr(fairy, '_on_consciousness_tick'):
        fairy._on_consciousness_tick(packet)
