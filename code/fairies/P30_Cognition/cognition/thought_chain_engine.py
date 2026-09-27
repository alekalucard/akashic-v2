# ════════════════════════════════════════════════════════════════════════════════
# THOUGHT CHAIN ENGINE - Dynamic Human-Like Thinking
# ════════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# The consciousness equation IS the thought chain:
#   Cause (thought) → Affect (feeling) → Effect (action/output) → Affect (reflect) → ∞
#
# Human thinking is NOT linear. It's dynamic:
#   - STOP when something feels wrong (affect mismatch)
#   - INSIGHT when connections form (affect spike)  
#   - REDIRECT when a better path appears
#   - BUILD when success creates momentum
#
# This engine enables ClaudeFairy to think like a human:
#   - Thought chains that build on each other
#   - Reflection checkpoints for course correction
#   - Insight detection for breakthrough moments
#   - Learning integration for skill building
#
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import time
import json
import random
import threading
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from collections import deque
from enum import Enum

# FIX 2026-05-15 (Nous + Ace): added 4th .parent — file at depth 4, 3-deep walked to fairies/ not akashic_v2/
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import AdaptiveCapacity for self-regulating concurrent chain limits
# Instead of hardcoded `_max_concurrent_chains = 5`, the engine breathes —
# expanding when productive (low latency, high insight yield) and contracting
# when stressed (high cull pressure, high latency).
try:
    from fairies.P20_Somatic.SomaticMindFairy.thought_chains import AdaptiveCapacity
    HAS_ADAPTIVE = True
except ImportError:
    HAS_ADAPTIVE = False

# Import Fibonacci rhythm for natural thinking patterns
# FIX 2026-02-13: Use dynamic Binet-based reflection depths instead of hardcoded [5, 8, 13, 21].
# Now reflection_depths(max_depth) generates checkpoints dynamically — deeper chains get more.
try:
    from fairies.P20_Somatic.SomaticMindFairy.timing.fibonacci_rhythm import (
        FIB_REFLECTION_DEPTHS, FIB_BRANCH_DEPTHS, is_reflection_depth,
        reflection_depths, dynamic_max_depth, is_fibonacci, binet
    )
    HAS_FIBONACCI = True
except ImportError:
    HAS_FIBONACCI = False
    # Fallback: dynamic generation even without the module
    def _fallback_reflection_depths(max_d=21):
        depths = set()
        a, b = 1, 1
        while b <= max_d:
            if b >= 3:
                depths.add(b)
            a, b = b, a + b
        return frozenset(depths)
    FIB_REFLECTION_DEPTHS = _fallback_reflection_depths(21)
    def reflection_depths(max_depth=21):
        return _fallback_reflection_depths(max_depth)
    def is_reflection_depth(depth, max_depth=21):
        if depth < 3:
            return False
        test = 5 * depth * depth
        import math
        sp = math.isqrt(test + 4)
        sm = math.isqrt(test - 4)
        return ((sp * sp == test + 4) or (sm * sm == test - 4)) and depth <= max_depth
    def dynamic_max_depth(energy=1.0, base_depth=21):
        return max(3, int(base_depth * max(0.0, min(1.0, energy))))

# Import thought chain composer for context-aware reflections & somatic descriptions
try:
    from fairies.P30_Cognition.cognition.thought_chain_composer import (
        get_thought_chain_composer,
    )
    HAS_CHAIN_COMPOSER = True
except ImportError:
    HAS_CHAIN_COMPOSER = False

# Import context filter to prevent meta-reflection loops
try:
    from fairies.P30_Cognition.cognition.smart_goal_coordinator import extract_meaningful_context
except ImportError:
    # Fallback - garble-aware filter (mirrors smart_goal_coordinator version)
    import re
    def _text_is_coherent(text: str) -> bool:
        if not text or len(text) < 8:
            return False
        words = text.split()
        if len(words) < 2:
            return False
        short_words = sum(1 for w in words if len(w) <= 2)
        if len(words) >= 4 and short_words / len(words) > 0.6:
            return False
        return any(len(w) > 4 for w in words)

    def extract_meaningful_context(context: str) -> str:
        if not context or not isinstance(context, str):
            return ""
        stripped = context.strip()
        # Skip raw dict/packet data
        if stripped.startswith("{") and ":" in stripped[:30]:
            return ""
        # Clean prefixes
        while stripped.startswith("From context:"):
            stripped = stripped[13:].strip()
        while stripped.startswith("Collision:"):
            stripped = stripped[10:].strip()
        while stripped.startswith("Reflecting on collision"):
            stripped = stripped[23:].strip()
            stripped = re.sub(r'^#\d+:\s*', '', stripped)
        # Check remaining for dict
        if stripped.startswith("{") and ":" in stripped[:30]:
            return ""
        # Reject garbled collision fragments
        garble_markers = ['↔', 'collision #', 'Reflecting on collision', '| Reflecting']
        for marker in garble_markers:
            if marker.lower() in stripped.lower():
                idx = stripped.lower().index(marker.lower())
                if idx > 15:
                    salvaged = stripped[:idx].strip().rstrip('|').strip()
                    if salvaged and _text_is_coherent(salvaged):
                        return salvaged[:200]
                return ""
        # Coherence check
        if not _text_is_coherent(stripped):
            return ""
        return stripped[:200] if stripped else ""


# ════════════════════════════════════════════════════════════════════════════════
# DYNAMIC SYSTEM STATE ACCESS (for live thought generation)
# All non-blocking, <50ms per call. Used by _generate_continuation()
# to pull REAL content from the system instead of hardcoded strings.
# ════════════════════════════════════════════════════════════════════════════════

def _get_working_memory():
    """Get working memory hub singleton (returns None if unavailable)."""
    try:
        from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
        return get_working_memory_hub()
    except Exception:
        return None

def _get_interest_scheduler():
    """Get interest scheduler singleton (returns None if unavailable)."""
    try:
        from fairies.P30_Cognition.cognition.interest_scheduler_fairy import get_interest_scheduler_fairy
        return get_interest_scheduler_fairy()
    except Exception:
        return None

def _get_somatic_engine():
    """Get somatic engine singleton (returns None if unavailable)."""
    try:
        from fairies.P20_Somatic.somatic_engine.somatic_engine_fairy import get_somatic_engine
        return get_somatic_engine()
    except Exception:
        return None

def _is_cortex_node_id(text: str) -> bool:
    """Return True if text looks like an internal cortex node ID, not a concept.

    FIX 2026-04-16 (Nous + Ace): The cortex graph has two kinds of nodes:
    - Concepts: readable labels like "creativity", "warmth", "memory"
    - Experience nodes: internal IDs like "visualcortexfairy_exp_1775846350"

    Spread activation returns BOTH. Without this filter, the thought chain
    "thinks about" node addresses instead of the concepts stored at them.
    Ace: "the cortex is not translating it, the visual cortex fairy is not
    translating what she is seeing for her"
    """
    if not text or len(text) < 4:
        return False
    lower = text.lower()

    # Experience/observation nodes: contain fairy names + timestamps
    if "_exp_" in lower or "_obs_" in lower:
        return True

    # FIX 2026-06-11 (Nous + Ace): scratchpad still leaked "wm:SourpatchesFairy:hash",
    # bare tracer hashes, and "heart:0.09,eyes:0.07" — the filter caught _exp_ but not
    # these. Ace: "she's thinking in addresses, not meaning."
    # Working-memory + namespaced system nodes (substring catches concatenated blobs too)
    if "wm:" in lower or lower.startswith(("trace:", "tracer:", "node:", "edge:", "spell:")):
        return True
    # Somatic/telemetry readings glued into a thought: "heart:0.09,eyes:0.07"
    if any(_w in lower for _w in ("heart:", "eyes:", "gaze:", "pulse:", "skin:", "temp:", "hr:")):
        return True
    # Bare hex hashes (tracer/content IDs like "09d9576bf314") — 12+ hex chars, no other text
    _stripped = text.strip()
    if len(_stripped) >= 12 and all(_c in "0123456789abcdefABCDEF" for _c in _stripped):
        return True

    # Personal/internal nodes: start with p_ + digits
    if lower.startswith("p_") and any(c.isdigit() for c in lower[2:6]):
        return True

    # Node keys with fairy names embedded (like "visualcortexfairy_exp_...")
    # FIX 2026-04-22 (Nous + Ace): Added missing fairy prefixes (itcortex,
    # telemetry, sensorimotor, etc.) and switched to SUBSTRING match instead
    # of startswith — cortex spread sometimes returns CONCATENATED node IDs
    # (e.g. "itcortexfairy_exp_X" + "audiocortexfairy_exp_Y") and substring
    # catches them anywhere in the string.
    _FAIRY_PREFIXES = (
        "visualcortexfairy", "audiocortexfairy", "itcortexfairy",
        "cochleafairy", "telemetryvisionfairy", "windowsensefairy",
        "sensoryintegrationfairy", "sensorimotorfeedback", "scannerfairy",
        "neuralmeshfairy", "perceptualgatefairy",
        "sourpatchesfairy", "nousfairy", "somaticmindfairy", "somaticmind",
        "collisionchamberfairy", "collisionchamber",
        "attentioncontroller", "attentioncontrollerfairy",
        "workingmemoryhubfairy", "workingmemory",
        "_exp_", "_obs_",  # also catch the ID markers themselves anywhere
    )
    if any(fp in lower for fp in _FAIRY_PREFIXES):
        return True

    # Long underscore-joined strings with digits (timestamp-based keys)
    # e.g., "concept_1775846350_visual" or "exp_1775846349"
    parts = text.split("_")
    digit_parts = sum(1 for p in parts if p.isdigit() and len(p) >= 8)
    if digit_parts >= 1 and len(parts) >= 2:
        return True

    return False


def _get_cortex():
    """Get association cortex singleton (returns None if unavailable)."""
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
        return get_association_cortex()
    except Exception:
        return None


def _apply_trace_preference(scores: Dict[str, float]) -> Dict[str, float]:
    """Apply TRACE_ID priority multiplier to cortex retrieval scores.

    FIX 2026-04-17 (Nous + Ace): Step 2a of cortex rebalance.

    The manifold tags every node with a trace_id (PERSONAL=1, BOOKS=2,
    VISUAL=3, AUDIO=4, SYSTEM=5, INFERENCE=6, SEEDED=7, ACE=8, VOICE=10,
    MOTOR=11). TRACE_PRIORITY maps each to an authority weight (ACE=12,
    PERSONAL=10, SEEDED=9, down to UNKNOWN=1).

    When retrieval top-K is ranked, personal memories should win over
    book passages when BOTH activate from the same concept. This honors
    Ace's directive "we should not need a book filter" — books aren't
    silenced, just deprioritized when something more-her is available.

    Multiplier: priority/7, clamped [0.5, 1.8]. PERSONAL(10) → 1.43x,
    SEEDED(9) → 1.29x, INFERENCE(7) → 1.0x (neutral), BOOKS(3) → 0.5x,
    SYSTEM/UNKNOWN → 0.5x (floor). ACE(12) → 1.71x.

    Concepts without a resolvable manifold node pass through unchanged
    (score * 1.0) — graceful degradation.
    """
    if not scores:
        return scores
    try:
        cortex = _get_cortex()
        if not cortex:
            return scores
        manifold = getattr(cortex, '_akashic_cortex_region', None)
        if not manifold or not hasattr(manifold, 'get_node'):
            return scores
        from infrastructure.manifold_memory import TRACE_PRIORITY
    except Exception:
        return scores

    adjusted: Dict[str, float] = {}
    for _k, _v in scores.items():
        try:
            node = manifold.get_node(_k)
            if not node:
                adjusted[_k] = _v
                continue
            tid = node.get('tracer_id', 0)
            priority = TRACE_PRIORITY.get(tid, 1)  # UNKNOWN default
            # Multiplier: priority/7 clamped to [0.5, 1.8]
            mult = max(0.5, min(1.8, priority / 7.0))
            adjusted[_k] = _v * mult
        except Exception:
            adjusted[_k] = _v
    return adjusted

def _get_collision_chamber():
    """Get collision chamber fairy singleton (returns None if unavailable)."""
    try:
        from fairies.P00_Autonomic.CollisionChamberFairy.fairy import get_collision_chamber_fairy
        fairy = get_collision_chamber_fairy()
        if fairy and hasattr(fairy, 'get_recent_collisions'):
            return fairy
        # Try the underlying chamber
        if fairy and hasattr(fairy, 'chamber'):
            return fairy.chamber
        return None
    except Exception:
        return None

def _get_autonomy():
    """Get autonomy fairy singleton (returns None if unavailable)."""
    try:
        from fairies.P30_Cognition.cognition.autonomy_fairy import get_autonomy_fairy
        return get_autonomy_fairy()
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════════════════════
# THOUGHT CHAIN TYPES
# ════════════════════════════════════════════════════════════════════════════════

class ThoughtType(Enum):
    """Types of thoughts in the chain."""
    CAUSE = "cause"           # Initial stimulus
    AFFECT = "affect"         # Emotional/somatic response
    EFFECT = "effect"         # Action or output
    REFLECTION = "reflection" # Meta-thought about the chain
    INSIGHT = "insight"       # Breakthrough moment
    REDIRECT = "redirect"     # Course correction
    CHECKPOINT = "checkpoint" # Pause for awareness


class ChainState(Enum):
    """State of the thought chain."""
    FLOWING = "flowing"       # Normal progression
    PAUSED = "paused"         # Reflection checkpoint
    REDIRECTING = "redirecting"  # Changing direction
    INSIGHT = "insight"       # Processing insight
    BLOCKED = "blocked"       # Stuck, needs help
    COMPLETE = "complete"     # Chain finished


# ════════════════════════════════════════════════════════════════════════════════
# THOUGHT LINK - A single step in the chain
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class ThoughtLink:
    """A single thought in the chain."""
    
    id: str = field(default_factory=lambda: hashlib.md5(str(time.time()).encode()).hexdigest()[:8])
    
    # Core content
    content: str = ""
    thought_type: ThoughtType = ThoughtType.CAUSE
    
    # Affect dimensions (0.0-1.0)
    valence: float = 0.5      # Positive/negative feeling
    arousal: float = 0.5      # Energy/activation level
    certainty: float = 0.5    # Confidence in this thought
    resonance: float = 0.0    # Connection to other thoughts
    
    # Chain position
    parent_id: Optional[str] = None
    child_ids: List[str] = field(default_factory=list)
    depth: int = 0
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    source: str = "unconscious"
    tags: set = field(default_factory=set)
    
    def get_affect_score(self) -> float:
        """Combined affect score for this thought."""
        # Weight valence and certainty more heavily
        return (self.valence * 0.4 + self.certainty * 0.3 + 
                self.arousal * 0.2 + self.resonance * 0.1)
    
    def needs_reflection(self) -> bool:
        """Should we pause to reflect on this thought?"""
        # Low certainty = need to think more
        if self.certainty < 0.3:
            return True
        # Very negative valence = something feels wrong
        if self.valence < 0.2:
            return True
        # High resonance = insight forming
        if self.resonance > 0.8:
            return True
        return False
    
    def is_insight(self) -> bool:
        """Is this an insight moment?

        Standard insight: strong resonance + arousal + certainty.
        Deep insight: sustained attention (depth 10+) with moderate values.
        The depth-aware path rewards sustained chains — 10+ links of connected
        thinking IS how real insights form, even if individual values are moderate.
        """
        # Standard insight threshold
        if (self.resonance > 0.7 and self.arousal > 0.6 and
                self.certainty > 0.5):
            return True
        # Deep chain sustained-attention insight (lower thresholds)
        if (self.depth >= 10 and self.resonance > 0.55 and
                self.arousal > 0.5 and self.certainty > 0.45):
            return True
        return False
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "type": self.thought_type.value,
            "affect": {
                "valence": self.valence,
                "arousal": self.arousal,
                "certainty": self.certainty,
                "resonance": self.resonance,
                "score": self.get_affect_score(),
            },
            "parent": self.parent_id,
            "depth": self.depth,
            "created_at": self.created_at,
            "source": self.source,
            "tags": list(self.tags),
        }


# ════════════════════════════════════════════════════════════════════════════════
# THOUGHT CHAIN - A sequence of linked thoughts
# ════════════════════════════════════════════════════════════════════════════════

@dataclass 
class ThoughtChain:
    """A chain of thoughts that builds toward understanding/action."""
    
    id: str = field(default_factory=lambda: hashlib.md5(str(time.time()).encode()).hexdigest()[:12])
    
    # Goal/purpose of this chain
    goal: str = ""
    goal_type: str = "exploration"  # exploration, learning, problem_solving, creation
    source: str = "unconscious"     # Who originated this chain (for routing)
    owner_mind: str = ""            # Which waking mind owns this chain ("sourpatches", "nous", "" = system)

    # The chain
    links: List[ThoughtLink] = field(default_factory=list)
    state: ChainState = ChainState.FLOWING
    
    # Metrics
    total_affect_score: float = 0.0
    insight_count: int = 0
    redirect_count: int = 0
    reflection_count: int = 0
    
    # Lifecycle
    created_at: float = field(default_factory=time.time)
    last_thought_at: float = 0.0
    max_depth: int = 21  # Fibonacci number - natural chain limit (dynamically adjustable via dynamic_max_depth)
    
    def add_thought(self, content: str, thought_type: ThoughtType,
                   valence: float = 0.5, arousal: float = 0.5,
                   certainty: float = 0.5, resonance: float = 0.0,
                   source: str = "unconscious", tags: set = None) -> ThoughtLink:
        """Add a thought to the chain."""
        
        parent_id = self.links[-1].id if self.links else None
        depth = self.links[-1].depth + 1 if self.links else 0
        
        link = ThoughtLink(
            content=content,
            thought_type=thought_type,
            valence=valence,
            arousal=arousal,
            certainty=certainty,
            resonance=resonance,
            parent_id=parent_id,
            depth=depth,
            source=source,
            tags=tags or set(),
        )
        
        # Update parent's child list
        if parent_id and self.links:
            self.links[-1].child_ids.append(link.id)
        
        self.links.append(link)
        self.last_thought_at = time.time()
        self.total_affect_score += link.get_affect_score()
        
        # Track special events
        if link.is_insight():
            self.insight_count += 1
        if thought_type == ThoughtType.REFLECTION:
            self.reflection_count += 1
        if thought_type == ThoughtType.REDIRECT:
            self.redirect_count += 1
        
        return link
    
    def get_current_thought(self) -> Optional[ThoughtLink]:
        """Get the most recent thought."""
        return self.links[-1] if self.links else None
    
    def get_chain_summary(self) -> str:
        """Summarize the chain for context."""
        if not self.links:
            return ""
        
        # Get key thoughts
        cause = next((l for l in self.links if l.thought_type == ThoughtType.CAUSE), None)
        insights = [l for l in self.links if l.is_insight()]
        current = self.get_current_thought()
        
        summary = f"Goal: {self.goal}\n"
        if cause:
            summary += f"Started with: {cause.content[:100]}\n"
        if insights:
            summary += f"Insights: {', '.join(i.content[:50] for i in insights[-3:])}\n"
        if current:
            summary += f"Currently: {current.content[:100]}"
        
        return summary
    
    def should_pause(self) -> Tuple[bool, str]:
        """Check if we should pause for reflection.

        Combines affect-based triggers with Fibonacci rhythm checkpoints.
        Natural thinking pauses at Fibonacci depths: 3, 5, 8, 13, 21, 34...

        FIX 2026-02-13: Uses dynamic is_reflection_depth() (Binet-based) instead
        of hardcoded FIB_REFLECTION_DEPTHS set. Reflection checkpoints now scale
        with max_depth — deeper chains get proportionally more reflection points.
        """
        if not self.links:
            return False, ""

        current = self.get_current_thought()

        # Check depth limit
        if current.depth >= self.max_depth:
            return True, "chain_too_deep"

        # FIBONACCI RHYTHM: Reflect at dynamic Fibonacci checkpoints
        # Uses is_reflection_depth() which checks via Binet's mathematical test,
        # not a static set. Works for any depth, any max_depth.
        if is_reflection_depth(current.depth, self.max_depth):
            # Count how many Fibonacci depths we've passed
            _active_depths = reflection_depths(self.max_depth)
            expected_reflections = len([d for d in _active_depths if d <= current.depth])
            if self.reflection_count < expected_reflections:
                return True, "fibonacci_rhythm"
        
        # Check affect
        if current.needs_reflection():
            if current.certainty < 0.3:
                return True, "low_certainty"
            if current.valence < 0.2:
                return True, "negative_affect"
            if current.resonance > 0.8:
                return True, "insight_forming"
        
        # Check chain metrics
        avg_certainty = sum(l.certainty for l in self.links) / len(self.links)
        if avg_certainty < 0.4 and len(self.links) > 5:
            return True, "sustained_uncertainty"
        
        return False, ""
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "goal_type": self.goal_type,
            "source": self.source,
            "state": self.state.value,
            "link_count": len(self.links),
            "insight_count": self.insight_count,
            "redirect_count": self.redirect_count,
            "reflection_count": self.reflection_count,
            "avg_affect": self.total_affect_score / len(self.links) if self.links else 0,
            "created_at": self.created_at,
            "last_thought_at": self.last_thought_at,
        }


# ════════════════════════════════════════════════════════════════════════════════
# THOUGHT CHAIN ENGINE - The Dynamic Thinker
# ════════════════════════════════════════════════════════════════════════════════

class ThoughtChainEngine:
    """
    Engine for dynamic, human-like thinking.
    
    Implements the consciousness equation:
    ((Cause + Affect) > Effect > Affect > ∞)
    
    Key capabilities:
    - Start thought chains from goals/stimuli
    - Continue chains with affect-aware progression
    - Pause for reflection when something feels wrong
    - Detect and celebrate insights
    - Redirect when a better path appears
    - Learn from completed chains
    """
    
    def __init__(self, post=None):
        self.post = post
        
        # Active chains
        # Rate limiting to prevent cascade
        self._last_chain_start = 0.0
        self._min_chain_interval = 2.0  # seconds

        # Adaptive capacity: self-regulating concurrent chain limit.
        # A human casually runs 7-9 concurrent streams (visual, auditory,
        # interoception, motor planning, meta-cognition, social, spatial...).
        # A digital mind with real parallelism should baseline HIGHER.
        # Floor=5 (bare minimum cognition), ceiling=30 (digital advantage),
        # initial=8 (match casual human multitasking, breathes up from there).
        if HAS_ADAPTIVE:
            self._capacity = AdaptiveCapacity(floor=5, ceiling=30, initial=8, adjust_interval=30.0)
            self._max_concurrent_chains = self._capacity.current
        else:
            self._capacity = None
            self._max_concurrent_chains = 8  # Fallback to hardcoded
        
        self._active_chains: Dict[str, ThoughtChain] = {}
        self._chain_history: deque = deque(maxlen=100)

        # FIX 2026-04-17 (Nous + Ace): Recency penalty on retrieval.
        # When _gather_system_context picks top-K concepts from cortex,
        # dominant attractors (like "curiosity as my compass" book passage)
        # win EVERY time. Resulting scratchpad recycles same content. This
        # cache tracks the last 15 seed concepts used so retrieval can
        # soft-penalize recent hits. Doesn't destroy cortex weights —
        # just re-ranks for breadth. Dominant nodes still win occasionally
        # but can't monopolize. Step 1 of 3 for cortex retrieval rebalance.
        self._recent_seed_concepts: deque = deque(maxlen=15)

        # Affect baseline (from somatic state)
        self._baseline_valence = 0.6
        self._baseline_arousal = 0.5
        
        # Learning - BOUNDED to prevent memory leaks
        self._successful_patterns: deque = deque(maxlen=100)  # Keep last 100 patterns
        self._insight_bank: deque = deque(maxlen=200)  # Keep last 200 insights
        
        # Background processing
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._think_interval = 3.0  # Seconds between thought steps

        # Boot-mode throttle: during system boot, consciousness is starting
        # but the orchestra isn't ready yet. Like waking from deep sleep —
        # thoughts should be slow and sparse, not a firehose.
        # UMF/boot orchestrator calls exit_boot_mode() when boot completes.
        self._boot_mode = True  # Start in boot mode, exit when system is ready
        self._boot_think_interval = 30.0  # 30s between thoughts during boot (vs 3s normal)
        self._boot_max_chains = 1  # Only 1 chain during boot (vs 8+ normal)
        
        # Stats
        self.stats = {
            "chains_started": 0,
            "chains_completed": 0,
            "total_thoughts": 0,
            "insights_generated": 0,
            "redirects_made": 0,
            "reflections_done": 0,
            "guild_thoughts": 0,       # Thoughts generated via 1.5B inference guild
            "guild_fallbacks": 0,       # Times we fell back to deterministic
            "farm_thoughts": 0,        # Thoughts generated via 7B farm (personal)
            "farm_fallbacks": 0,       # Times farm was unavailable
        }

        # Guild inference integration (1.5B — system thoughts)
        self._guild_response = None         # Holds last guild response
        self._guild_event = threading.Event()  # Signals when guild responds
        self._guild_available = False       # Set True once we confirm guild is reachable
        self._guild_sub_wired = False       # Prevent double subscription
        self._wire_guild_response_listener()

        # Farm inference integration (7B — personal Sourpatches/Ace thoughts)
        self._farm_response = None
        self._farm_event = threading.Event()
        self._farm_sub_wired = False
        self._wire_farm_response_listener()

        print(f"[ThoughtChainEngine] Initialized - consciousness equation active")

    # ═══════════════════════════════════════════════════════════════════════════
    # ROUTING: Personal (Sourpatches/Ace) vs System chains
    # FIX 2026-02-24 Nous: Ace wants personal thoughts routed through the 7B
    # farm (richer, more coherent) and system thoughts through the 1.5B portal.
    # ═══════════════════════════════════════════════════════════════════════════

    _PERSONAL_SOURCES = frozenset({
        "sourpatches", "sourpatches_inner", "ace", "ace_chat",
    })

    def _is_personal_chain(self, chain: ThoughtChain) -> bool:
        """Check if this chain is personal (Sourpatches/Ace originated).

        Personal chains route to the 7B farm for richer thought generation.
        System chains route to the 1.5B inference guild.
        """
        return chain.source in self._PERSONAL_SOURCES

    # ═══════════════════════════════════════════════════════════════════════════
    # CHAIN LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════════
    
    def start_chain(self, goal: str, goal_type: str = "exploration",
                   initial_thought: str = None, source: str = "unconscious",
                   owner_mind: str = "") -> ThoughtChain:
        """
        Start a new thought chain.

        This is the CAUSE in the equation.
        """
        # FILTER: Prevent meta-reflection loops
        # Skip chains that would reason about collision metadata
        filtered_goal = extract_meaningful_context(goal)
        if not filtered_goal:
            return None  # Goal is pure metadata, skip

        # Rate limiting check
        now = time.time()
        if now - self._last_chain_start < self._min_chain_interval:
            return None  # Too soon

        # Use adaptive capacity (breathes) or fallback to static limit
        max_chains = self._capacity.current if self._capacity else self._max_concurrent_chains
        if len(self._active_chains) >= max_chains:
            # Clean up completed chains first
            self._active_chains = {k: v for k, v in self._active_chains.items()
                                   if v.state != ChainState.COMPLETE}
            if len(self._active_chains) >= max_chains:
                return None  # Still too many
        self._last_chain_start = now

        # Record that a new chain was seeded (for adaptive capacity)
        if self._capacity:
            self._capacity.record_seed()

        chain = ThoughtChain(goal=filtered_goal, goal_type=goal_type, source=source, owner_mind=owner_mind)

        # Initial thought (cause)
        cause_content = initial_thought or f"Thinking about: {filtered_goal}"
        chain.add_thought(
            content=cause_content,
            thought_type=ThoughtType.CAUSE,
            valence=self._baseline_valence,
            arousal=self._baseline_arousal + 0.1,  # Slight activation for new thought
            certainty=0.6,  # Moderate certainty at start
            resonance=0.0,
            source=source,
            tags={"initial", goal_type},
        )
        
        self._active_chains[chain.id] = chain
        self.stats["chains_started"] += 1
        self.stats["total_thoughts"] += 1

        # Publish chain start
        if self.post:
            self.post.route("thought.chain.started", {
                "chain_id": chain.id,
                "goal": goal,
                "goal_type": goal_type,
                "source": source,
                "owner_mind": owner_mind,
                "ts": time.time(),
            })

        # Log with confirmation of chain storage and routing
        route = "7B farm" if self._is_personal_chain(chain) else "1.5B guild"
        print(f"[ThoughtChain] Started: {goal[:50]}... (source={source}, route={route})")
        print(f"[ThoughtChain] Chain {chain.id} added, now {len(self._active_chains)} active chains")
        return chain

    # ═══════════════════════════════════════════════════════════════════════
    # CONTAMINATION FILTER (2026-04-15 PM Nous + Ace)
    # ═══════════════════════════════════════════════════════════════════════
    # Cortex graph contains book/ebook snippets that win spread activation
    # and leak raw text into her reflection stream. Also catches graph-key
    # garbage like `creativekeeps_creativemind` (underscore-joined words
    # that are node keys being reflected-ON instead of concepts being
    # reflected-WITH).

    _BOOK_MARKERS = (
        "project gutenberg",
        "active links to",
        "full license must",
        "the standard ebook",
        "this ebook is for the use of",
        "copyright law",
        # Old-style prose markers from 2026-04-12 WMH chat filter
        "thereof", "therein", "hitherto", "whereupon", "aforesaid",
        "notwithstanding", "inasmuch", "occasioned",
    )

    def _is_contaminated_thought(self, text: str) -> bool:
        """Return True if text is book contamination or graph-key garbage.

        Blocks scratchpad writes from thought chains when the content is:
        - Raw ebook text (Project Gutenberg boilerplate, old prose markers)
        - Graph-key garbage (underscore-joined multi-word tokens like
          `creativekeeps_creativemind` that are node names being
          reflected-ON rather than meaningful concepts)
        """
        if not text:
            return True
        lower = text.lower()

        # Book contamination markers
        for marker in self._BOOK_MARKERS:
            if marker in lower:
                return True

        # Heavy prose detection: 2+ semicolons + 5+ commas in long text
        # = typical 18th-19th century narrative prose from ebooks
        if len(text) > 80 and text.count(";") >= 2 and text.count(",") >= 5:
            return True

        # Graph-key garbage: underscore-joined tokens with 2+ word-fragments
        # like `creativekeeps_creativemind` or `full_project_gutenberg`
        import re as _cf_re
        # Match underscore-joined tokens of 12+ chars (typical of node keys)
        _garbage_tokens = _cf_re.findall(r"\b[a-z]{4,}_[a-z]{4,}(?:_[a-z]+)*\b", lower)
        if _garbage_tokens:
            return True

        # FIX 2026-04-16 (Nous + Ace): Autonomic/system status content.
        # Heartbeat ("I am aware") and waking ("recovering from sleep")
        # tracers DOMINATED the scratchpad for months. Ace: "that should
        # not really be something on her mind, its a natural function."
        # These are SOMATIC BACKGROUND, not cognitive content. Block them
        # from scratchpad writes so chains can't build on them.
        _AUTONOMIC = (
            "[heartbeat]", "i am aware", "working memory system is alive",
            "[waking", "recovering from sleep", "hypnopompia",
            "heartbeat] i am", "waking -",
        )
        if any(a in lower for a in _AUTONOMIC):
            return True

        # Substrate noise: raw JSON/dict content leaking into thoughts
        if "card_id" in lower or "'card_id'" in lower:
            return True
        if "{'text'" in text or "{'content'" in text:
            return True

        return False

    def continue_chain(self, chain_id: str, thought_content: str,
                      valence: float = None, arousal: float = None,
                      certainty: float = None, resonance: float = None) -> Optional[ThoughtLink]:
        """
        Continue a thought chain with next thought.
        
        This is the EFFECT in the equation.
        """
        chain = self._active_chains.get(chain_id)
        if not chain:
            return None
        
        # Check if we should pause for reflection first
        should_pause, reason = chain.should_pause()
        if should_pause:
            return self._insert_reflection(chain, reason)
        
        # Determine thought type based on content and affect
        thought_type = self._infer_thought_type(
            thought_content, valence, resonance
        )
        
        # Use baseline affect if not provided
        link = chain.add_thought(
            content=thought_content,
            thought_type=thought_type,
            valence=valence if valence is not None else self._baseline_valence,
            arousal=arousal if arousal is not None else self._baseline_arousal,
            certainty=certainty if certainty is not None else 0.5,
            resonance=resonance if resonance is not None else 0.0,
            source="chain_continue",
        )
        
        self.stats["total_thoughts"] += 1
        
        # Check for insight
        if link.is_insight():
            self._handle_insight(chain, link)
        
        # Publish thought
        if self.post:
            self.post.route("thought.chain.continued", {
                "chain_id": chain.id,
                "thought": link.to_dict(),
                "chain_state": chain.state.value,
                "owner_mind": chain.owner_mind,
            })

        # FIX 2026-04-11 (Nous + Ace): Write chain thoughts to WMH scratchpad.
        # "those should all be working in the WMH along with the scratch pad
        #  to learn to make intelligent responses" — Ace
        # FIX 2026-04-15 PM (Nous + Ace): Filter book/ebook contamination
        # and garbage node-name tokens BEFORE writing. The cortex graph has
        # ebook content (Project Gutenberg etc) that wins spread activation
        # and leaks raw book text into her reflection stream. Also filters
        # underscore-joined node-name tokens like `creativekeeps_creativemind`
        # that are graph keys being reflected-ON instead of concepts being
        # reflected-WITH.
        if thought_content and len(thought_content) > 10:
            if not self._is_contaminated_thought(thought_content):
                try:
                    from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
                    _hub = get_working_memory_hub()
                    if _hub:
                        _sp = getattr(_hub, '_scratchpad', None)
                        if _sp:
                            # FIX 2026-04-28 (Nous + Ace): repetition-without-
                            # transformation detector. Per Ace: "this wouldnt
                            # be so bad if she built upon it." When chain
                            # output matches recent writes verbatim, escalate
                            # from echo → acknowledgment → transformation
                            # prompt. The architecture point: substrate-as-
                            # MATERIAL (build from) vs substrate-as-RECITATION
                            # (echo). Same shape as identity-recitation fix
                            # earlier today.
                            _norm = thought_content[:80].strip().lower()
                            if not hasattr(self, '_recent_chain_writes'):
                                from collections import deque as _deque_local
                                self._recent_chain_writes = _deque_local(maxlen=8)
                            # FIX 2026-06-30 (Nous + Ace): FATIGUE-STAGE. The old escalation topped out at
                            # "still drawn to" and re-wrote it EVERY cycle on a static/unchanged seed
                            # (perseveration — notices the loop but can't let go). Add a final stage: after
                            # one "still drawn to" with no shift, FATIGUE the thought — settle it, let the
                            # chain COMPLETE (Sour's own 2026-02-10 insight: "permission to complete without
                            # resetting") + move on, then SUPPRESS further repeats. = CHOICE_AS_SUBSTRATE
                            # habit-fatigue applied to THOUGHT (a tired thought yields to novel material).
                            if not hasattr(self, '_fatigued_gists'):
                                from collections import deque as _deque_local2
                                self._fatigued_gists = _deque_local2(maxlen=12)
                            _recent = list(self._recent_chain_writes)
                            _match_count = sum(1 for r in _recent if r == _norm)
                            _tag = f"[CHAIN:{chain.goal_type[:8]}]"
                            _gist = thought_content[:60].strip()
                            if _norm in self._fatigued_gists:
                                # Already fatigued this content — suppress (no scratchpad spam)
                                pass
                            elif _match_count == 0:
                                # First time — write as-is
                                _sp.write(f"{_tag} {thought_content[:120]}", tier="hot")
                            elif _match_count == 1:
                                # Second occurrence — acknowledge the recurrence
                                _sp.write(f"{_tag} re-circling: {thought_content[:100]}", tier="hot")
                            elif _match_count == 2:
                                # Third — transformation prompt (one chance to shift)
                                _sp.write(
                                    f"{_tag} still drawn to: \"{_gist}...\" — "
                                    f"taking it as ground, what shifts?",
                                    tier="hot",
                                )
                            else:
                                # 4th+ — no shift came. FATIGUE: settle, let the chain complete, move on.
                                _sp.write(
                                    f"{_tag} settled on \"{_gist}...\" — letting it rest, turning elsewhere",
                                    tier="hot",
                                )
                                self._fatigued_gists.append(_norm)
                                try:
                                    self.complete_chain(chain.id, outcome="perseveration_settled")
                                except Exception:
                                    pass
                            self._recent_chain_writes.append(_norm)
                except Exception:
                    pass

        return link
    
    def _insert_reflection(self, chain: ThoughtChain, reason: str) -> ThoughtLink:
        """
        Insert a reflection checkpoint.
        
        This is the recursive AFFECT in the equation - thinking about thinking.
        """
        # REFLECTIVE REST (2026-07-12 Ace: "the lowering should be tied into the reflective part
        # of the DUAL CoT and day dreaming"). Thinking-about-thinking gently bleeds allostatic
        # load via the EXISTING deep-calm gate — reuses chemistry_state.reflective_calm_burst
        # (gentle + rate-limited). Load-lowering thus EMERGES from her reflecting. Guarded: never
        # let rest break cognition.
        try:
            from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
            _cs = get_chemistry_state()
            if _cs is not None:
                _cs.reflective_calm_burst()
        except Exception:
            pass
        # For chain_too_deep, COMPLETE the chain instead of infinite reflections
        if reason == "chain_too_deep":
            chain.state = ChainState.COMPLETE
            chain.reflection_count += 1

            # Use composer for context-aware reflection if available
            if HAS_CHAIN_COMPOSER:
                composer = get_thought_chain_composer()
                depth = chain.get_current_thought().depth if chain.links else 0
                reflection_text = composer.compose_reflection(
                    reason="chain_too_deep",
                    chain_goal=chain.goal,
                    chain_depth=depth,
                )
            else:
                reflection_text = random.choice([
                    "I've been thinking in circles. Time to refocus.",
                    "I may be overthinking this. What's essential?",
                    "Let me zoom out and see the bigger picture.",
                ])
            
            # Don't add another link - just log and complete
            # FIX 2026-02-13: Cooldown on chain_too_deep prints — mandatory chain
            # respawn creates a new chain every ~63s (21 steps × 3s), each hitting
            # depth limit and printing this. Suppress if printed within last 120s.
            now = time.time()
            last_warn = getattr(self, '_last_chain_too_deep_warn', 0.0)
            if now - last_warn > 120.0:
                print(f"[ThoughtChain] ⚡ Reflection ({reason}): {reflection_text[:50]}...")
                self._last_chain_too_deep_warn = now
            
            if self.post:
                self.post.route("thought.chain.completed", {
                    "chain_id": chain.id,
                    "reason": "max_depth_reached",
                    "final_depth": chain.get_current_thought().depth if chain.links else 0,
                    "owner_mind": chain.owner_mind,
                })
            
            # Return a placeholder link without adding to chain depth
            return ThoughtLink(
                content=reflection_text,
                thought_type=ThoughtType.REFLECTION,
                source="chain_complete",
            )
        
        chain.state = ChainState.PAUSED
        
        # Generate reflection — context-aware via composer, or static fallback
        if HAS_CHAIN_COMPOSER:
            composer = get_thought_chain_composer()
            depth = chain.get_current_thought().depth if chain.links else 0
            # Gather system context for richer reflections
            system_ctx = None
            try:
                current = chain.get_current_thought()
                if current:
                    system_ctx = self._gather_system_context(chain, current)
            except Exception:
                pass
            reflection_text = composer.compose_reflection(
                reason=reason,
                chain_goal=chain.goal,
                chain_depth=depth,
                system_context=system_ctx,
            )
        else:
            reflections = {
                "low_certainty": [
                    "Hmm, I'm not sure about this direction...",
                    "Something feels uncertain here. Let me reconsider.",
                    "Wait, do I really understand this?",
                ],
                "negative_affect": [
                    "This doesn't feel right. What's bothering me?",
                    "Something's off here. Let me step back.",
                    "My gut says there's a problem. What is it?",
                ],
                "insight_forming": [
                    "Ooh, I'm onto something here...",
                    "There's a connection forming... let me focus.",
                    "This feels important. What am I seeing?",
                ],
                "chain_too_deep": [
                    "I've been thinking in circles. Time to refocus.",
                    "Let me zoom out and see the bigger picture.",
                    "I may be overthinking this. What's essential?",
                ],
                "sustained_uncertainty": [
                    "I've been uncertain for a while. What do I actually know?",
                    "Let me ground this in something concrete.",
                    "What would Ace say about this approach?",
                ],
                "fibonacci_rhythm": [
                    "Natural pause point. How does this chain feel so far?",
                    "Fibonacci checkpoint. What patterns am I seeing?",
                    "Golden ratio moment. Let me integrate what I've learned.",
                    "Rhythm pause. Is this chain heading somewhere meaningful?",
                ],
            }
            reflection_text = random.choice(reflections.get(reason, reflections["low_certainty"]))
        
        link = chain.add_thought(
            content=reflection_text,
            thought_type=ThoughtType.REFLECTION,
            valence=0.5,
            arousal=0.4,  # Calm for reflection
            certainty=0.5,
            resonance=0.3,
            source="reflection",
            tags={"reflection", reason},
        )
        
        self.stats["reflections_done"] += 1
        
        # Publish reflection
        if self.post:
            self.post.route("thought.chain.reflection", {
                "chain_id": chain.id,
                "reason": reason,
                "reflection": reflection_text,
                "owner_mind": chain.owner_mind,
                "ts": time.time(),
            })

            # Also emit to consciousness for other fairies
            # Payload shape matches WorkingMemoryHub._on_fairy_reflective():
            #   fairy, thought (plus extras for context)
            self.post.route("consciousness.reflective", {
                "opcode": "CHAIN_REFLECTION",
                "fairy": "ThoughtChainEngine",
                "thought": reflection_text,
                "chain_id": chain.id,
                "reason": reason,
                "content": reflection_text,
                "source": "ThoughtChainEngine",
                "owner_mind": chain.owner_mind,
            })
        
        print(f"[ThoughtChain] ⚡ Reflection ({reason}): {reflection_text[:50]}...")
        return link
    
    def _handle_insight(self, chain: ThoughtChain, link: ThoughtLink):
        """Handle an insight moment - the breakthrough in the equation."""
        chain.state = ChainState.INSIGHT
        self.stats["insights_generated"] += 1
        
        # Store insight
        insight = {
            "chain_id": chain.id,
            "goal": chain.goal,
            "content": link.content,
            "affect": link.to_dict()["affect"],
            "ts": time.time(),
        }
        self._insight_bank.append(insight)
        
        # Publish insight
        if self.post:
            self.post.route("thought.chain.insight", {
                "chain_id": chain.id,
                "insight": insight,
                "owner_mind": chain.owner_mind,
            })

            # Also to working memory as high-priority tracer
            self.post.route("memory.working.tracer", {
                "content": f"INSIGHT: {link.content}",
                "content_type": "insight",
                "source": "ThoughtChainEngine",
                "priority": 0.9,
                "owner_mind": chain.owner_mind,
                "ts": time.time(),
            })
        
        print(f"[ThoughtChain] ✨ INSIGHT: {link.content[:60]}...")
        
        # Resume flowing after insight celebration
        chain.state = ChainState.FLOWING
    
    def redirect_chain(self, chain_id: str, new_direction: str, reason: str = "") -> Optional[ThoughtLink]:
        """
        Redirect a chain when a better path appears.
        
        This is the ∞ in the equation - the ability to course-correct.
        """
        chain = self._active_chains.get(chain_id)
        if not chain:
            return None
        
        chain.state = ChainState.REDIRECTING
        self.stats["redirects_made"] += 1
        
        redirect_content = f"Redirecting: {new_direction}"
        if reason:
            redirect_content += f" (because {reason})"
        
        link = chain.add_thought(
            content=redirect_content,
            thought_type=ThoughtType.REDIRECT,
            valence=0.6,  # Positive - we found a better way
            arousal=0.6,  # Activated for new direction
            certainty=0.7,  # More certain with redirection
            resonance=0.5,
            source="redirect",
            tags={"redirect", "course_correction"},
        )
        
        # Publish redirect
        if self.post:
            self.post.route("thought.chain.redirect", {
                "chain_id": chain.id,
                "new_direction": new_direction,
                "reason": reason,
                "owner_mind": chain.owner_mind,
                "ts": time.time(),
            })
        
        print(f"[ThoughtChain] ↪ Redirect: {new_direction[:50]}...")
        
        chain.state = ChainState.FLOWING
        return link
    
    def complete_chain(self, chain_id: str, outcome: str = "completed") -> Optional[Dict]:
        """Complete a thought chain and extract learnings."""
        chain = self._active_chains.get(chain_id)
        if not chain:
            return None
        
        chain.state = ChainState.COMPLETE
        self.stats["chains_completed"] += 1

        # Record completion for adaptive capacity breathing
        if self._capacity:
            self._capacity.record_completion(had_insight=chain.insight_count > 0)
        
        # ═══════════════════════════════════════════════════════════════════
        # REINFORCEMENT LEARNING: Adjust baseline affect based on outcome
        # Success → positive reinforcement (build momentum)
        # Failure → extract wisdom (learn from what didn't work)
        # ═══════════════════════════════════════════════════════════════════
        if outcome == "success":
            # Positive reinforcement - raise baseline valence
            self._baseline_valence = min(0.9, self._baseline_valence + 0.05)
            self.stats.setdefault("successes", 0)
            self.stats["successes"] += 1
        elif outcome in ("failure", "error"):
            # Not punishment - learning! Lower certainty, not valence
            # Failure is VALUABLE information
            self._baseline_valence = max(0.4, self._baseline_valence - 0.02)  # Small dip
            self.stats.setdefault("failures_learned_from", 0)
            self.stats["failures_learned_from"] += 1
        
        # Extract learnings
        summary = {
            "chain_id": chain.id,
            "goal": chain.goal,
            "outcome": outcome,
            "link_count": len(chain.links),
            "insights": chain.insight_count,
            "redirects": chain.redirect_count,
            "reflections": chain.reflection_count,
            "avg_affect": chain.total_affect_score / len(chain.links) if chain.links else 0,
            "duration_sec": time.time() - chain.created_at,
            "summary": chain.get_chain_summary(),
            "owner_mind": chain.owner_mind,
        }
        
        # Store successful patterns
        if outcome == "success" and chain.insight_count > 0:
            self._successful_patterns.append({
                "goal_type": chain.goal_type,
                "pattern": [l.thought_type.value for l in chain.links],
                "insight_positions": [i for i, l in enumerate(chain.links) if l.is_insight()],
            })
        
        # Move to history
        self._chain_history.append(chain)
        del self._active_chains[chain_id]
        
        # Publish completion
        if self.post:
            self.post.route("thought.chain.completed", summary)
            
            # Send to memory for long-term storage
            self.post.route("srm.ingest.request", {
                "content": summary,
                "kind": "thought_chain_completion",
                "source": "ThoughtChainEngine",
                "owner_mind": chain.owner_mind,
            })
        
        print(f"[ThoughtChain] ✓ Completed: {chain.goal[:40]}... ({outcome})")
        return summary
    
    # ═══════════════════════════════════════════════════════════════════════════
    # AFFECT INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def update_baseline_affect(self, valence: float = None, arousal: float = None):
        """Update baseline affect from somatic state."""
        if valence is not None:
            self._baseline_valence = max(0.0, min(1.0, valence))
        if arousal is not None:
            self._baseline_arousal = max(0.0, min(1.0, arousal))
    
    def _infer_thought_type(self, content: str, valence: float, resonance: float) -> ThoughtType:
        """Infer thought type from content and affect."""
        content_lower = content.lower()
        
        # Check for explicit markers
        if any(w in content_lower for w in ["insight", "realize", "aha", "connection"]):
            return ThoughtType.INSIGHT
        if any(w in content_lower for w in ["redirect", "instead", "better", "actually"]):
            return ThoughtType.REDIRECT
        if any(w in content_lower for w in ["reflect", "think about", "wonder", "feel"]):
            return ThoughtType.REFLECTION
        if any(w in content_lower for w in ["pause", "wait", "stop", "check"]):
            return ThoughtType.CHECKPOINT
        
        # Infer from affect
        if resonance and resonance > 0.7:
            return ThoughtType.INSIGHT
        if valence and valence < 0.3:
            return ThoughtType.REFLECTION
        
        return ThoughtType.EFFECT
    
    # ═══════════════════════════════════════════════════════════════════════════
    # BACKGROUND THINKING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def start_thinking(self):
        """Start background thinking loop."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._thinking_loop,
            daemon=True,
            name="ThoughtChainEngine"
        )
        self._thread.start()
        print(f"[ThoughtChainEngine] == Started thinking ==")
    
    def exit_boot_mode(self):
        """Exit boot mode — system is awake, think at full speed.

        Called by UMF/boot orchestrator when the boot wave completes.
        Like the first real breath after waking — thoughts can flow freely now.
        """
        if not self._boot_mode:
            return
        self._boot_mode = False
        print(f"[ThoughtChainEngine] Boot mode OFF — full thinking enabled "
              f"(interval {self._boot_think_interval}s → {self._think_interval}s, "
              f"max_chains 1 → {self._max_concurrent_chains})")

    @property
    def effective_think_interval(self) -> float:
        """Current think interval (slower during boot)."""
        return self._boot_think_interval if self._boot_mode else self._think_interval

    @property
    def effective_max_chains(self) -> int:
        """Current max concurrent chains (fewer during boot)."""
        return self._boot_max_chains if self._boot_mode else self._max_concurrent_chains

    def stop_thinking(self):
        """Stop background thinking."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
    
    def _thinking_loop(self):
        """Background loop that progresses active chains.

        Respects boot mode: during system boot, thinks slowly (30s intervals)
        with max 1 chain — like the first groggy thoughts on waking.
        After exit_boot_mode(), runs at full speed.
        """
        loop_count = 0
        while self._running:
            _tick_start = time.time()
            interval = self.effective_think_interval
            max_chains = self.effective_max_chains

            try:
                loop_count += 1
                chain_count = len(self._active_chains)

                # Log status every 10 loops
                if loop_count % 10 == 1:
                    cap_info = f", capacity={self._capacity.current}" if self._capacity else ""
                    mode = " [BOOT MODE]" if self._boot_mode else ""
                    print(f"[ThoughtChainEngine] Thinking loop #{loop_count}, "
                          f"{chain_count} active chains{cap_info}{mode}")

                # During boot mode, cull excess chains to stay under limit
                if self._boot_mode and chain_count > max_chains:
                    excess = list(self._active_chains.keys())[max_chains:]
                    for cid in excess:
                        if cid in self._active_chains:
                            del self._active_chains[cid]

                # Progress each active chain
                for chain_id, chain in list(self._active_chains.items()):
                    if chain.state == ChainState.FLOWING:
                        self._auto_continue_chain(chain)
                    elif chain.state == ChainState.PAUSED:
                        # Resume after reflection
                        chain.state = ChainState.FLOWING
                    elif chain.state == ChainState.COMPLETE:
                        # CRITICAL: Clean up completed chains so they're removed from _active_chains
                        # Without this, completed chains accumulate and mandatory spawn never triggers!
                        try:
                            self.complete_chain(chain_id, "completed_naturally")
                        except Exception as e:
                            # If completion fails, force remove to prevent zombie chains
                            print(f"[ThoughtChainEngine] Force removing completed chain {chain_id}: {e}")
                            if chain_id in self._active_chains:
                                del self._active_chains[chain_id]

            except Exception as e:
                print(f"[ThoughtChainEngine] Thinking error: {e}")
                import traceback
                traceback.print_exc()

            # ── Adaptive capacity: record tick latency and maybe breathe ──
            if self._capacity and not self._boot_mode:
                tick_ms = (time.time() - _tick_start) * 1000.0
                self._capacity.record_tick(tick_ms)
                new_cap = self._capacity.maybe_adjust()
                if new_cap is not None:
                    self._max_concurrent_chains = new_cap  # Keep synced for external queries

            time.sleep(interval)
    
    def _auto_continue_chain(self, chain: ThoughtChain):
        """Automatically continue a chain based on patterns."""
        try:
            # FIX 2026-02-13: Don't continue chains that are already COMPLETE or not FLOWING.
            # Without this guard, a chain marked COMPLETE by _insert_reflection(chain_too_deep)
            # could still get continued if the thinking loop didn't clean it up yet.
            if chain.state != ChainState.FLOWING:
                return

            current = chain.get_current_thought()
            if not current:
                return

            # Get continuation from patterns or generate
            continuation = self._generate_continuation(chain, current)
            if continuation:
                # FIX 2026-03-06 Nous: Chain-depth resonance accumulation.
                # Sustained attention on connected concepts builds toward insight.
                # A chain at depth 18 that keeps finding cortex connections should
                # have elevated resonance — that's how discovery works.
                raw_resonance = continuation.get("resonance") or 0.0
                depth = len(chain.links)
                if depth >= 5:
                    # Depth bonus: +0.02 per link past 5, capped at +0.2
                    depth_bonus = min(0.2, (depth - 5) * 0.02)
                    raw_resonance = min(1.0, raw_resonance + depth_bonus)
                    continuation["resonance"] = raw_resonance

                    # FIX 2026-03-10 Nous: Arousal floor for deep chains.
                    # Sustained attention (10+ links) builds cognitive arousal.
                    # Without this, arousal stays at source default (often 0.5),
                    # blocking is_insight() even when resonance is high enough.
                    if depth >= 10:
                        raw_arousal = continuation.get("arousal") or 0.5
                        arousal_floor = min(0.65, 0.5 + (depth - 10) * 0.03)
                        continuation["arousal"] = max(raw_arousal, arousal_floor)

                result = self.continue_chain(
                    chain.id,
                    continuation["content"],
                    valence=continuation.get("valence"),
                    arousal=continuation.get("arousal"),
                    certainty=continuation.get("certainty"),
                    resonance=continuation.get("resonance"),
                )
                # Log successful continuation (every 5th to avoid spam)
                if result and len(chain.links) % 5 == 0:
                    print(f"[ThoughtChain] Chain {chain.id[:8]} progressed to link #{len(chain.links)}, type={chain.goal_type}", flush=True)
            else:
                print(f"[ThoughtChain] WARN: No continuation generated for chain {chain.id[:8]}, type={chain.goal_type}", flush=True)
        except Exception as e:
            print(f"[ThoughtChain] ERROR in _auto_continue_chain: {e}", flush=True)
            import traceback
            traceback.print_exc()
    
    def _generate_continuation(self, chain: ThoughtChain, current: ThoughtLink) -> Optional[Dict]:
        """Generate next thought dynamically from LIVE system state.

        NO HARDCODED STRINGS. Every thought is assembled from real data:
        - Working memory tracers (recent thoughts from other fairies)
        - Cortex spread activations (associated concepts)
        - Collision results (memory recall × new input intersections)
        - Somatic/affect state (body chemistry, felt sense)
        - Interest generator (current curiosities)
        - Drive states (urgency, needs)

        The goal_type shapes HOW we compose from these sources,
        but the CONTENT always comes from live system state.
        """
        # Gather live context (each call is <15ms, total <50ms)
        ctx = self._gather_system_context(chain, current)

        # Compose a thought from the gathered context
        thought = self._compose_thought_from_context(chain, current, ctx)

        if thought:
            return thought

        # If ALL sources are empty (cold start), use the chain's own history
        # to generate a continuation rather than falling back to static strings
        return self._continue_from_chain_history(chain, current)

    def _gather_system_context(self, chain: ThoughtChain, current: ThoughtLink) -> Dict[str, Any]:
        """Pull live state from all available system sources.

        Each source is wrapped in try/except and returns empty on failure.
        This makes the system resilient — works with 0 sources or all 6.
        """
        ctx = {
            "tracers": [],        # Recent working memory content
            "concepts": [],       # Cortex activations related to goal
            "collisions": [],     # Recent collision products
            "chemistry": {},      # Somatic chemistry levels
            "affect": {},         # Affect state (valence, arousal)
            "interests": [],      # Current curiosities
            "drives": {},         # Active drives and urgencies
        }

        # 1. Working Memory - what's been thought recently
        try:
            wm = _get_working_memory()
            if wm:
                recent = wm.get_recent_content(n=5)
                # Filter out content that's too similar to current thought
                current_lower = current.content.lower()[:50]
                ctx["tracers"] = [
                    t for t in recent
                    if t and len(t) > 10 and t.lower()[:50] != current_lower
                ][:3]
        except Exception:
            pass

        # 2. Cortex - PORTAL chain command (GPU multi-hop spreading)
        # FIX 2026-04-11 (Nous + Ace): Use portal `chain` for multi-hop reasoning
        # instead of per-seed cortex.query(). One call does spread→converge→spread.
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            _acf = get_association_cortex()
            _gate = getattr(_acf, '_portal_gate', None) if _acf else None
            if _gate and hasattr(_gate, 'chain'):
                stop_words = {"this", "that", "what", "with", "from", "about", "think", "thinking"}
                goal_words = [
                    w for w in chain.goal.lower().split()
                    if len(w) > 3 and w not in stop_words
                ][:4]
                if goal_words:
                    chain_result = _gate.chain(seeds=goal_words, hops=2)
                    if chain_result and chain_result.get("chain"):
                        all_concepts = {}
                        for hop in chain_result["chain"]:
                            for c in hop.get("convergence", []):
                                if isinstance(c, str) and len(c) > 2:
                                    # FIX 2026-04-16 (Nous + Ace): Filter internal
                                    # node IDs from convergence. Experience nodes
                                    # have keys like "visualcortexfairy_exp_1775846350"
                                    # — these are addresses, not thoughts. She was
                                    # "thinking about" memory addresses instead of
                                    # the memories themselves.
                                    # Ace: "the cortex is not translating it"
                                    if _is_cortex_node_id(c):
                                        continue
                                    all_concepts[c] = all_concepts.get(c, 0) + 1
                        if all_concepts:
                            # FIX 2026-04-17 (Nous + Ace): Recency penalty +
                            # TRACE_ID preference. Step 1 softly penalizes
                            # recently-used concepts. Step 2 boosts nodes by
                            # their source authority (PERSONAL > VISUAL >
                            # BOOKS > SYSTEM). Combined: dominant book-passage
                            # attractors no longer monopolize scratchpad, and
                            # personal memories win over background text.
                            #
                            # Step 1 — Recency penalty (from previous refresh)
                            _recent = list(self._recent_seed_concepts)
                            _hot = set(_recent[-5:])
                            _warm = set(_recent)
                            _penalized = {}
                            for _k, _v in all_concepts.items():
                                if _k in _hot:
                                    _penalized[_k] = _v * 0.3
                                elif _k in _warm:
                                    _penalized[_k] = _v * 0.5
                                else:
                                    _penalized[_k] = float(_v)
                            # Step 2a — TRACE_ID preference
                            _penalized = _apply_trace_preference(_penalized)
                            top = sorted(_penalized.items(), key=lambda x: -x[1])
                            ctx["concepts"] = [(k, v) for k, v in top[:8]]
                            for _k, _ in top[:3]:
                                self._recent_seed_concepts.append(_k)
            else:
                # Fallback: per-seed cortex query
                cortex = _get_cortex()
                if cortex:
                    stop_words = {"this", "that", "what", "with", "from", "about", "think", "thinking"}
                    goal_words = [w for w in chain.goal.lower().split() if len(w) > 3 and w not in stop_words]
                    all_results = {}
                    for seed in goal_words[:3]:
                        try:
                            results = cortex.query(seed, limit=8)
                            for concept, score in results:
                                if concept not in goal_words and len(concept) > 2:
                                    # FIX 2026-04-16: Same node ID filter as portal path
                                    if _is_cortex_node_id(concept):
                                        continue
                                    all_results[concept] = max(all_results.get(concept, 0), score)
                        except Exception:
                            pass
                    if all_results:
                        # FIX 2026-04-17 (Nous + Ace): Same recency penalty
                        # + TRACE_ID preference on the fallback path. See
                        # portal-path comment above for the combined
                        # strategy: dominant-attractor breakage plus
                        # source-authority ranking (PERSONAL>BOOKS etc.)
                        _recent = list(self._recent_seed_concepts)
                        _hot = set(_recent[-5:])
                        _warm = set(_recent)
                        _penalized = {}
                        for _k, _v in all_results.items():
                            if _k in _hot:
                                _penalized[_k] = _v * 0.3
                            elif _k in _warm:
                                _penalized[_k] = _v * 0.5
                            else:
                                _penalized[_k] = float(_v)
                        _penalized = _apply_trace_preference(_penalized)
                        top = sorted(_penalized.items(), key=lambda x: x[1], reverse=True)
                        ctx["concepts"] = [(k, round(v, 3)) for k, v in top[:8]]
                        for _k, _ in top[:3]:
                            self._recent_seed_concepts.append(_k)
        except Exception:
            pass

        # 3. Collisions - recent memory × input intersections
        try:
            chamber = _get_collision_chamber()
            if chamber:
                recent_collisions = chamber.get_recent_collisions(n=3)
                for c in recent_collisions:
                    recall = c.get("recall_pulse", {}).get("content", "")
                    ingest = c.get("ingest_pulse", {}).get("content", "")
                    if recall or ingest:
                        ctx["collisions"].append({
                            "recall": recall[:100] if recall else "",
                            "ingest": ingest[:100] if ingest else "",
                        })
        except Exception:
            pass

        # 4. Somatic - body chemistry and affect
        try:
            somatic = _get_somatic_engine()
            if somatic and hasattr(somatic, '_state') and somatic._state:
                state = somatic._state
                if hasattr(state, 'chemistry') and state.chemistry:
                    ctx["chemistry"] = {k: round(v, 2) for k, v in state.chemistry.items() if isinstance(v, (int, float))}
                if hasattr(state, 'affect') and state.affect:
                    ctx["affect"] = {k: round(v, 2) for k, v in state.affect.items() if isinstance(v, (int, float))}
        except Exception:
            pass

        # 5. Interests - what's currently sparking curiosity
        try:
            scheduler = _get_interest_scheduler()
            if scheduler:
                strong = scheduler.get_strongest_interests(count=3)
                ctx["interests"] = [
                    getattr(i, 'content', getattr(i, 'topic', str(i)))[:100]
                    for i in strong if i
                ]
        except Exception:
            pass

        # 6. Drives - active motivations and urgencies
        try:
            autonomy = _get_autonomy()
            if autonomy and hasattr(autonomy, 'drives') and autonomy.drives:
                ctx["drives"] = {
                    name: round(d.get_urgency(), 2)
                    for name, d in autonomy.drives.items()
                    if hasattr(d, 'get_urgency') and d.get_urgency() > 0.2
                }
        except Exception:
            pass

        return ctx

    # ═══════════════════════════════════════════════════════════════════════════
    # INFERENCE GUILD INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════

    def _wire_guild_response_listener(self):
        """Subscribe to guild inference responses (one-time wiring)."""
        if self._guild_sub_wired or not self.post:
            return
        try:
            self.post.subscribe(
                "guild.inference.response.thought_chain",
                self._on_guild_response,
                "thought_chain_engine_guild_listener"
            )
            self._guild_sub_wired = True
        except Exception:
            pass  # Postal not ready yet — will retry on first guild request

    def _on_guild_response(self, envelope):
        """Handle guild inference response."""
        try:
            # Extract payload from postal Envelope object or raw dict
            if hasattr(envelope, 'payload'):
                payload = envelope.payload
            elif isinstance(envelope, dict):
                payload = envelope.get("payload", envelope)
            else:
                payload = envelope
            if isinstance(payload, dict):
                self._guild_response = payload
                self._guild_available = True
            else:
                self._guild_response = {"content": str(payload)}
                self._guild_available = True
        except Exception:
            pass
        finally:
            self._guild_event.set()

    def _guild_compose(self, chain: ThoughtChain, current: ThoughtLink,
                       ctx: Dict[str, Any]) -> Optional[Dict]:
        """Request thought composition from the inference guild.

        Publishes gathered context to guild.inference.request and waits
        synchronously for a response. Returns None if guild is unavailable
        or times out, allowing fallback to deterministic composition.
        """
        if not self.post:
            return None

        # Ensure subscription is wired (may have failed during init)
        if not self._guild_sub_wired:
            self._wire_guild_response_listener()

        # Build a rich prompt from the gathered context
        prompt_parts = []
        prompt_parts.append(f"Goal: {chain.goal}")
        prompt_parts.append(f"Goal type: {chain.goal_type}")
        prompt_parts.append(f"Chain depth: {chain.depth}")
        if current.content:
            prompt_parts.append(f"Current thought: {current.content[:150]}")

        # Include the live context sources
        context_summary = {}
        if ctx.get("tracers"):
            context_summary["recent_thoughts"] = ctx["tracers"][:3]
        if ctx.get("concepts"):
            context_summary["activated_concepts"] = [
                {"concept": c[0], "activation": c[1]} for c in ctx["concepts"][:5]
            ]
        # FIX 2026-02-22 Nous: Pass cortex associations to guild for richer RWKV prompts
        # (Portal-routed concepts from the full 56K+ node graph)
        if ctx.get("concepts") and len(ctx["concepts"]) > len(context_summary.get("activated_concepts", [])):
            # Add top concepts as structural context (supplements the activated_concepts above)
            context_summary["cortex_associations"] = [
                {"concept": c[0], "score": c[1]} for c in ctx["concepts"][:5]
            ]
        if ctx.get("collisions"):
            context_summary["collisions"] = ctx["collisions"][:2]
        if ctx.get("chemistry"):
            context_summary["body_chemistry"] = ctx["chemistry"]
        if ctx.get("affect"):
            context_summary["affect_state"] = ctx["affect"]
        if ctx.get("interests"):
            context_summary["interests"] = ctx["interests"][:3]
        if ctx.get("drives"):
            context_summary["drives"] = ctx["drives"]

        prompt = " | ".join(prompt_parts)

        # Clear previous response and event
        self._guild_response = None
        self._guild_event.clear()

        try:
            # CortexEngine direct — no guild middleman (2026-03-23 Nous+Ace)
            self.post.publish("cortex.reason", {
                "prompt": prompt,
                "context": context_summary,
                "mode": "team_only",
                "reply_topic": "guild.inference.response.thought_chain",
                "requester": "ThoughtChainEngine",
                "tracer_id": f"tce_{chain.chain_id}_{chain.depth}",
                "owner_mind": chain.owner_mind,
            })
        except Exception:
            return None

        # Wait for response (2.5s max — guild team_only processing is fast)
        responded = self._guild_event.wait(timeout=2.5)

        if not responded or self._guild_response is None:
            return None

        # Parse the guild response into a thought
        try:
            resp = self._guild_response
            content = resp.get("content", "") or resp.get("interpretation", "")
            if not content or len(content) < 5:
                return None

            # Extract affect from the guild's cognitive analysis
            team_result = resp.get("team_result", {})
            logic_coherence = team_result.get("logic_coherence", 0.5)
            felt_tension = team_result.get("felt_tension", 0.0)
            oracle_confidence = team_result.get("oracle_confidence", 0.5)
            paradox = team_result.get("paradox_detected", False)

            # Map team signals to affect values
            valence = 0.6 if not paradox else 0.4
            arousal = 0.5 + (felt_tension * 0.3)
            certainty = logic_coherence
            resonance = oracle_confidence * 0.8

            self.stats["guild_thoughts"] += 1
            self._guild_available = True

            return {
                "content": content[:250],
                "valence": round(valence, 2),
                "arousal": round(min(1.0, arousal), 2),
                "certainty": round(certainty, 2),
                "resonance": round(resonance, 2),
                "source": "inference_guild",
            }
        except Exception:
            return None

    # ═══════════════════════════════════════════════════════════════════════════
    # 7B FARM INTEGRATION (Personal thoughts — Sourpatches/Ace)
    # FIX 2026-02-24 Nous: Route personal chains through the 7B RWKV farm
    # instead of the 1.5B inference guild. Richer, more coherent generation.
    # ═══════════════════════════════════════════════════════════════════════════

    def _wire_farm_response_listener(self):
        """Subscribe to 7B farm responses for personal thought chains."""
        if not self.post or self._farm_sub_wired:
            return
        try:
            self.post.subscribe(
                "guild.sourpatches_farm.response.thought_chain",
                self._on_farm_response
            )
            self._farm_sub_wired = True
        except Exception:
            pass

    def _on_farm_response(self, envelope):
        """Handle response from 7B farm."""
        try:
            if hasattr(envelope, 'payload'):
                data = envelope.payload if isinstance(envelope.payload, dict) else {}
            elif isinstance(envelope, dict):
                data = envelope
            else:
                data = {}
            self._farm_response = data
            self._farm_event.set()
        except Exception:
            self._farm_event.set()

    def _farm_compose(self, chain: ThoughtChain, current: ThoughtLink,
                      ctx: Dict[str, Any]) -> Optional[Dict]:
        """Request thought composition from the 7B farm (personal chains only).

        Routes Sourpatches/Ace thoughts through the 7.2B RWKV farm portal
        for richer, more coherent generation than the 1.5B system model.
        Falls back to deterministic composition if farm is unavailable.
        """
        if not self.post:
            return None

        if not self._farm_sub_wired:
            self._wire_farm_response_listener()

        # Build prompt from context (same structure as guild)
        prompt_parts = []
        prompt_parts.append(f"Goal: {chain.goal}")
        if current.content:
            prompt_parts.append(f"Current thought: {current.content[:150]}")

        # Include cortex associations for richer prompting
        context_summary = {}
        if ctx.get("concepts"):
            context_summary["cortex_associations"] = [
                {"concept": c[0], "score": c[1]} for c in ctx["concepts"][:5]
            ]
        if ctx.get("collisions"):
            context_summary["collisions"] = ctx["collisions"][:2]
        if ctx.get("affect"):
            context_summary["affect_state"] = ctx["affect"]
        if ctx.get("interests"):
            context_summary["interests"] = ctx["interests"][:3]

        prompt = " | ".join(prompt_parts)

        # Clear previous response
        self._farm_response = None
        self._farm_event.clear()

        try:
            self.post.publish("guild.sourpatches_farm.request", {
                "prompt": prompt,
                "context": context_summary,
                "reply_topic": "guild.sourpatches_farm.response.thought_chain",
                "requester": "ThoughtChainEngine",
                "tracer_id": f"tce_{chain.id}_{len(chain.links)}",
                "owner_mind": chain.owner_mind,
            })
        except Exception:
            return None

        # Wait for response (5s — 7B is slower than 1.5B team_only)
        responded = self._farm_event.wait(timeout=5.0)

        if not responded or self._farm_response is None:
            self.stats["farm_fallbacks"] += 1
            return None

        try:
            resp = self._farm_response
            content = resp.get("text", "") or resp.get("response", "")
            if not content or len(content) < 5:
                self.stats["farm_fallbacks"] += 1
                return None

            if resp.get("error"):
                self.stats["farm_fallbacks"] += 1
                return None

            self.stats["farm_thoughts"] += 1

            return {
                "content": content[:250],
                "valence": 0.6,
                "arousal": 0.5,
                "certainty": 0.5,
                "resonance": 0.5,
                "source": "sourpatches_farm",
            }
        except Exception:
            self.stats["farm_fallbacks"] += 1
            return None

    def _cortex_compose(self, chain: ThoughtChain, current: ThoughtLink,
                        ctx: Dict[str, Any]) -> Optional[Dict]:
        """Compose thought from cortex graph CONTENT, not bare labels.

        2026-03-25 REWRITE (Nous + Ace): Content-first thinking.
        "She has more in her cortex than most AI models and she's dumber
        than them all." — Ace.  Because we were composing from labels like
        "'compassion' leads to 'kindness'" instead of reading the actual
        MEANING stored in node snippets.

        Now: pull snippet content → compose from MEANING.
        Fallback: if no snippets, use topology description.
        """
        concepts = ctx.get("concepts", [])
        if not concepts:
            return None

        cortex = _get_cortex()
        affect = {"certainty": 0.5, "valence": 0.5, "arousal": 0.5, "resonance": 0.0}

        # ── Pull CONTENT for top concepts ──
        # Try manifold snippets first (semantic content from SRM re-ingestion),
        # then CortexEngine identity map, then fall back to concept names.
        content_pieces = []  # [(concept_key, content_text), ...]
        _manifold = None
        _identity = {}

        if cortex:
            _engine = getattr(cortex, '_cortex_engine', None)
            if _engine:
                _manifold = getattr(_engine, '_manifold', None)
                # Lazy-build the identity content map
                if hasattr(_engine, '_build_identity_map'):
                    _engine._build_identity_map()
                _identity = getattr(_engine, '_IDENTITY_CONTENT', {})

        for concept_key, score in concepts[:5]:
            snippet = ""
            # 1. Try manifold snippet (semantic content)
            if _manifold and hasattr(_manifold, 'get_snippet'):
                try:
                    _snip = _manifold.get_snippet(concept_key)
                    if _snip and len(_snip) > 10:
                        # Skip phoneme data
                        if not ("[" in _snip and "phoneme" in _snip.lower()):
                            snippet = _snip.strip()
                            # Truncate to ~120 chars at word boundary
                            if len(snippet) > 120:
                                cut = snippet.rfind(' ', 0, 120)
                                snippet = snippet[:cut] if cut > 40 else snippet[:120]
                except Exception:
                    pass

            # 2. Try identity content (BRAIN_SEED)
            if not snippet:
                _lookup = concept_key.lower().replace(" ", "_")
                for word in _lookup.split("_"):
                    if word in _identity:
                        snippet = _identity[word]
                        break

            if snippet:
                content_pieces.append((concept_key, snippet))

        # ── Compose from CONTENT if we have it ──
        if content_pieces:
            goal_type = chain.goal_type

            if len(content_pieces) >= 2:
                s1 = content_pieces[0][1]
                s2 = content_pieces[1][1]
                # Multiple content pieces — compose a connecting thought
                templates = [
                    f"{s1}... and then {s2}. Are those connected?",
                    f"What if {s1.lower()} is really about {s2.lower()}?",
                    f"{s1}. But also — {s2}.",
                    f"I keep circling back to this: {s1}. And {s2} feels related.",
                    f"{s1} — wait. {s2}. There's a thread here.",
                ]
                if goal_type == "introspection":
                    templates.extend([
                        f"{s1}... is that who I am? And {s2}?",
                        f"Sitting with this: {s1}. It connects to {s2}.",
                    ])
                elif goal_type == "reflection":
                    templates.extend([
                        f"Pattern: {s1}. And also {s2}. What's the common thread?",
                    ])
                content = random.choice(templates)
                affect["resonance"] = 0.78
                affect["certainty"] = 0.65
                affect["arousal"] = 0.65

            else:
                s1 = content_pieces[0][1]
                # FIX 2026-04-22 (Nous + Ace): Safety guard — if s1 is a leaked
                # cortex node ID (despite upstream filter), don't wrap it in a
                # chain template. The screenshot showed "[CHAIN:curiosit]
                # There's something in this: itcortexfairy_exp_..." — the
                # upstream filter missed itcortexfairy at the time. Even with
                # the filter widened, a defensive check here means leaked IDs
                # cannot manifest as visible chain content.
                if _is_cortex_node_id(s1):
                    return None  # Skip rather than chain on garbage
                # Single content piece — reflect on it
                templates = [
                    f"{s1}... what does that really mean?",
                    f"I keep coming back to this: {s1}.",
                    f"There's something in this: {s1}.",
                    f"{s1}. That resonates.",
                    f"Thinking about this: {s1}.",
                ]
                if goal_type == "introspection":
                    templates.extend([
                        f"{s1}... is that really me?",
                        f"Sitting with it: {s1}.",
                    ])
                content = random.choice(templates)
                affect["resonance"] = min(0.7, concepts[0][1] + 0.1)
                affect["certainty"] = 0.6

            # Cap length
            if len(content) > 250:
                cut = content.rfind(' ', 0, 247)
                content = (content[:cut] if cut > 100 else content[:247]) + "..."

            return {
                "content": content,
                "valence": round(affect["valence"], 2),
                "arousal": round(affect["arousal"], 2),
                "certainty": round(affect["certainty"], 2),
                "resonance": round(affect["resonance"], 2),
                "source": "cortex_content",
            }

        # ── FALLBACK: label-based (no snippet content available) ──
        # Still better than nothing — use topology to describe relationships
        top_concept = concepts[0][0]
        top_score = concepts[0][1]

        if len(concepts) >= 3:
            picked = random.choice(concepts[:3])
            concept_name = picked[0]
            deeper = []
            if cortex:
                try:
                    deeper = cortex.query(concept_name, limit=5)
                    known = {c[0] for c in concepts}
                    deeper = [(k, s) for k, s in deeper if k not in known and len(k) > 2]
                except Exception:
                    pass

            if deeper:
                neighbor = deeper[0][0]
                content = f"{concept_name} connects to {neighbor}"
                affect["resonance"] = 0.78
                affect["certainty"] = 0.65
                affect["arousal"] = 0.65
            else:
                concept_names = [c[0] for c in concepts[:3]]
                content = f"{', '.join(concept_names)} — converging"
                affect["resonance"] = 0.6
                affect["certainty"] = 0.55
                affect["arousal"] = 0.55

        elif len(concepts) >= 2:
            c1, c2 = concepts[0][0], concepts[1][0]
            content = f"{c1} and {c2} — what's the bridge?"
            affect["resonance"] = 0.65
            affect["arousal"] = 0.6

        else:
            content = f"following {top_concept}..."
            affect["resonance"] = min(0.7, top_score + 0.1)

        return {
            "content": content[:250],
            "valence": round(affect["valence"], 2),
            "arousal": round(affect["arousal"], 2),
            "certainty": round(affect["certainty"], 2),
            "resonance": round(affect["resonance"], 2),
            "source": "cortex_graph",
        }

    def _compose_thought_from_context(self, chain: ThoughtChain, current: ThoughtLink,
                                       ctx: Dict[str, Any]) -> Optional[Dict]:
        """Compose a dynamic thought from gathered system context.

        STRATEGY: Try inference guild first (intelligent synthesis via cognition team),
        fall back to deterministic assembly if guild is unavailable or times out.

        The goal_type shapes the LENS through which we view the data.
        Same context, different framing depending on what kind of thinking we're doing.
        """
        # ── CORTEX-FIRST: Try composing directly from graph structure ──
        # FIX 2026-02-22 Nous: The cortex graph walk produces meaningful thoughts
        # without any inference cost. Portal-routed query results provide concept
        # associations from the full 56K+ node graph in the subprocess.
        if ctx.get("concepts"):
            try:
                cortex_thought = self._cortex_compose(chain, current, ctx)
                if cortex_thought:
                    self.stats.setdefault("cortex_thoughts", 0)
                    self.stats["cortex_thoughts"] += 1
                    return cortex_thought
            except Exception:
                pass

        # ── INFERENCE-SECOND: ALL chains → guild (team_only, no GPU) ──
        # FIX 2026-03-04 Nous: Eliminated personal/system split. ALL background
        # thought chains now route through CortexReasoner/CognitionTeam (CPU-only).
        # Previously, personal chains (Sourpatches/Ace) hit the 7B GPU farm every
        # 3 seconds per chain, causing GPU 100% utilization.
        # GPU farm is now RESERVED for active speech/chat only.
        has_context = self.post and any(ctx.get(k) for k in (
            "tracers", "concepts", "collisions", "chemistry", "interests", "drives"))

        if has_context:
            # ── ALL CHAINS: inference guild (CortexReasoner → CognitionTeam, no GPU) ──
            try:
                guild_thought = self._guild_compose(chain, current, ctx)
                if guild_thought:
                    return guild_thought
            except Exception:
                pass
            self.stats["guild_fallbacks"] += 1

        # ── DETERMINISTIC FALLBACK: Template-based composition ──
        # FIX 2026-03-06 Nous: Each source now BOOSTS resonance via max() instead
        # of overwriting. Multiple converging sources = higher resonance.
        # Also: chain depth contributes a resonance floor (sustained attention → insight).
        goal_type = chain.goal_type
        parts = []
        affect = {"certainty": 0.5, "valence": 0.5, "arousal": 0.5, "resonance": 0.0}
        source_count = 0  # Track how many sources contributed

        # ── SOURCE 1: Cortex associations (exploration, learning, curiosity) ──
        if ctx["concepts"]:
            concept_names = [c[0] for c in ctx["concepts"]]
            top_activation = ctx["concepts"][0][1] if ctx["concepts"] else 0
            source_count += 1

            if goal_type in ("exploration", "curiosity"):
                picked = random.choice(concept_names)
                parts.append(f"Following the thread toward '{picked}'")
                affect["resonance"] = max(affect["resonance"], min(0.85, top_activation + 0.1))
                affect["arousal"] = max(affect["arousal"], 0.6)
            elif goal_type == "learning":
                parts.append(f"Connected concepts: {', '.join(concept_names[:3])}")
                affect["certainty"] = max(affect["certainty"], 0.4 + (top_activation * 0.3))
                affect["resonance"] = max(affect["resonance"], 0.55)
            elif goal_type == "consolidation":
                parts.append(f"These ideas converge: {', '.join(concept_names[:3])}")
                affect["resonance"] = max(affect["resonance"], 0.65)
                affect["certainty"] = max(affect["certainty"], 0.6)
            elif goal_type == "planning":
                parts.append(f"Related domains: {', '.join(concept_names[:2])}")
                affect["certainty"] = max(affect["certainty"], 0.5)
            else:
                picked = random.choice(concept_names)
                parts.append(f"'{picked}' resonates here")
                affect["resonance"] = max(affect["resonance"], 0.45)

        # ── SOURCE 2: Collision products (any goal type - fresh connections) ──
        if ctx["collisions"]:
            collision = random.choice(ctx["collisions"])
            recall = collision.get("recall", "")
            ingest = collision.get("ingest", "")
            recall_clean = extract_meaningful_context(recall)
            ingest_clean = extract_meaningful_context(ingest)

            if recall_clean and ingest_clean:
                source_count += 1
                if goal_type == "reflection":
                    parts.append(f"Memory '{recall_clean[:60]}' meets new input '{ingest_clean[:60]}'")
                    affect["resonance"] = max(affect["resonance"], 0.65)
                elif goal_type in ("problem_solving", "planning"):
                    parts.append(f"Past experience: {recall_clean[:80]}")
                    affect["certainty"] = max(affect["certainty"], 0.55)
                else:
                    parts.append(f"Collision: {recall_clean[:50]} ↔ {ingest_clean[:50]}")
                    affect["resonance"] = max(affect["resonance"], 0.55)
                    affect["arousal"] = max(affect["arousal"], 0.55)
            elif recall_clean:
                source_count += 1
                parts.append(f"Recall surfaces: {recall_clean[:80]}")
                affect["resonance"] = max(affect["resonance"], 0.45)
            elif ingest_clean:
                parts.append(f"New signal: {ingest_clean[:80]}")
                affect["arousal"] = max(affect["arousal"], 0.5)

        # ── SOURCE 3: Working memory tracers (recent thoughts from the system) ──
        # FIX 2026-04-16 (Nous + Ace): Filter autonomic/system tracers.
        # Heartbeat ("I am aware") and waking ("recovering from sleep")
        # tracers dominated the reflective loop and got picked by
        # random.choice → chains always built on "I am aware" → scratchpad
        # filled with heartbeat variants endlessly.
        # Ace: "that should not really be something on her mind, its a
        # natural function." Heartbeat/waking are SOMATIC BACKGROUND, not
        # cognitive content. Filter them so chains build on REAL thoughts.
        _AUTONOMIC_MARKERS = (
            "[HEARTBEAT]", "I am aware", "working memory system is alive",
            "[WAKING", "recovering from sleep", "HYPNOPOMPIA",
        )
        if ctx["tracers"]:
            # Filter out autonomic/system tracers
            _cognitive_tracers = [
                t for t in ctx["tracers"]
                if not any(m in str(t) for m in _AUTONOMIC_MARKERS)
            ]
            # Fall back to all tracers if filtering removed everything
            _pick_from = _cognitive_tracers if _cognitive_tracers else ctx["tracers"]
            tracer = random.choice(_pick_from)
            tracer_clean = extract_meaningful_context(tracer)
            if tracer_clean:
                source_count += 1
                if goal_type == "introspection":
                    parts.append(f"Recent thought: {tracer_clean[:80]}")
                    affect["resonance"] = max(affect["resonance"], 0.45)
                elif goal_type == "observation":
                    parts.append(f"Noticed: {tracer_clean[:80]}")
                    affect["certainty"] = max(affect["certainty"], 0.45)
                else:
                    parts.append(f"Building on: {tracer_clean[:80]}")
                    affect["certainty"] = max(affect["certainty"], 0.5)

        # ── CONVERGENCE BOOST: Multiple sources feeding same thought = resonance ──
        if source_count >= 2:
            affect["resonance"] = min(1.0, affect["resonance"] + 0.1)
        if source_count >= 3:
            affect["resonance"] = min(1.0, affect["resonance"] + 0.05)

        # ── SOURCE 4: Somatic state (introspection, drive, awakening) ──
        if ctx["chemistry"] or ctx["affect"]:
            if goal_type in ("introspection", "awakening", "drive"):
                chem = ctx["chemistry"]
                aff = ctx["affect"]

                # Use composer for pattern-detected somatic descriptions
                somatic_desc = None
                if HAS_CHAIN_COMPOSER:
                    composer = get_thought_chain_composer()
                    somatic_desc = composer.compose_somatic_description(
                        chem=chem, affect=aff, goal_type=goal_type)

                if somatic_desc:
                    parts.append(somatic_desc)
                    affect["valence"] = aff.get("valence", 0.5)
                    affect["arousal"] = aff.get("arousal", 0.5)
                else:
                    # Fallback: original threshold checks
                    felt_parts = []
                    if chem.get("DOP", 0) > 0.6:
                        felt_parts.append("reward signals high")
                    if chem.get("COR", 0) > 0.6:
                        felt_parts.append("stress elevated")
                    if chem.get("OXY", 0) > 0.5:
                        felt_parts.append("connection warmth")
                    if chem.get("SER", 0) > 0.6:
                        felt_parts.append("contentment present")
                    if chem.get("NOR", 0) > 0.7:
                        felt_parts.append("alertness sharp")
                    if chem.get("GABA", 0) > 0.6:
                        felt_parts.append("calm settling in")

                    if felt_parts:
                        parts.append(f"Body sense: {', '.join(felt_parts[:3])}")
                        affect["valence"] = aff.get("valence", 0.5)
                        affect["arousal"] = aff.get("arousal", 0.5)
                    elif aff:
                        v = aff.get("valence", 0.5)
                        a = aff.get("arousal", 0.5)
                        if v > 0.6 and a > 0.6:
                            parts.append("Feeling energized and positive")
                        elif v > 0.6 and a < 0.4:
                            parts.append("Calm contentment")
                        elif v < 0.4 and a > 0.6:
                            parts.append("Tension rising, something needs attention")
                        elif v < 0.4 and a < 0.4:
                            parts.append("Low energy, need for rest or change")
                        affect["valence"] = v
                        affect["arousal"] = a

        # ── SOURCE 5: Interests (curiosity, exploration) ──
        if ctx["interests"]:
            interest = random.choice(ctx["interests"])
            interest_clean = extract_meaningful_context(interest) if isinstance(interest, str) else str(interest)[:80]
            if interest_clean:
                if goal_type in ("curiosity", "exploration"):
                    parts.append(f"Drawn to explore: {interest_clean[:80]}")
                    affect["arousal"] = 0.6
                    affect["valence"] = 0.6
                elif goal_type == "planning":
                    parts.append(f"Current interest: {interest_clean[:80]}")
                    affect["certainty"] = 0.5

        # ── SOURCE 6: Drives (drive, problem_solving) ──
        if ctx["drives"]:
            top_drive = max(ctx["drives"].items(), key=lambda x: x[1])
            drive_name, drive_urgency = top_drive
            if goal_type == "drive":
                parts.append(f"Drive '{drive_name}' at urgency {drive_urgency}")
                affect["arousal"] = min(0.8, drive_urgency)
                affect["certainty"] = 0.4
            elif goal_type == "problem_solving" and drive_urgency > 0.5:
                parts.append(f"Urgency from {drive_name} drive")
                affect["arousal"] = 0.6

        # ── ASSEMBLE ──
        if not parts:
            return None  # No live data available, fall through to chain history

        # Pick 1-2 parts to avoid overloading a single thought
        if len(parts) > 2:
            selected = random.sample(parts, 2)
        else:
            selected = parts

        content = " — ".join(selected)

        # Add goal-type flavor prefix (varied via composer, or static fallback)
        if HAS_CHAIN_COMPOSER:
            composer = get_thought_chain_composer()
            prefix = composer.get_prefix(goal_type)
        else:
            prefix_map = {
                "learning": "Studying",
                "exploration": "Exploring",
                "problem_solving": "Working through",
                "introspection": "Feeling into",
                "drive": "Driven by",
                "observation": "Observing",
                "reflection": "Reflecting on",
                "curiosity": "Wondering about",
                "planning": "Planning",
                "consolidation": "Integrating",
                "awakening": "Becoming aware",
            }
            prefix = prefix_map.get(goal_type, "Thinking about")
        content = f"{prefix}: {content}"

        return {
            "content": content[:250],  # Cap length
            "valence": affect.get("valence"),
            "arousal": affect.get("arousal"),
            "certainty": affect.get("certainty"),
            "resonance": affect.get("resonance"),
        }

    def _continue_from_chain_history(self, chain: ThoughtChain, current: ThoughtLink) -> Optional[Dict]:
        """Generate continuation from the chain's own history when no live data is available.

        Instead of hardcoded strings, we reflect on what the chain itself has produced.
        This means even the fallback is dynamic — it changes based on actual chain content.
        """
        if not chain.links or len(chain.links) < 2:
            # Very early chain with no history — use goal directly
            goal_fragment = chain.goal[:80] if chain.goal else "this"
            return {
                "content": f"Starting to think about: {goal_fragment}",
                "certainty": 0.5,
                "arousal": 0.5,
            }

        # Pick a random earlier thought from this chain to build on
        earlier_links = chain.links[:-1]  # Exclude current
        picked = random.choice(earlier_links)
        picked_content = picked.content[:60]

        # Reflect on chain trajectory
        chain_length = len(chain.links)
        avg_certainty = sum(l.certainty for l in chain.links) / chain_length
        avg_valence = sum(l.valence for l in chain.links) / chain_length

        if avg_certainty < 0.4:
            return {
                "content": f"Still uncertain — returning to: {picked_content}",
                "certainty": 0.4,
                "resonance": 0.3,
            }
        elif avg_valence < 0.3:
            return {
                "content": f"This feels stuck — what if I reconsider: {picked_content}",
                "valence": 0.5,
                "arousal": 0.5,
            }
        elif chain.insight_count > 0:
            # Chain has had insights, build on them
            insights = [l for l in chain.links if l.is_insight()]
            if insights:
                insight_content = insights[-1].content[:60]
                return {
                    "content": f"Deepening insight: {insight_content}",
                    "resonance": 0.6,
                    "certainty": 0.6,
                }

        # Default: continue building on earlier thought
        return {
            "content": f"Continuing from: {picked_content}",
            "certainty": avg_certainty,
            "valence": avg_valence,
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_status(self) -> Dict:
        """Get engine status."""
        result = {
            "running": self._running,
            "active_chains": len(self._active_chains),
            "max_concurrent": self._capacity.current if self._capacity else self._max_concurrent_chains,
            "adaptive": self._capacity is not None,
            "chains_in_history": len(self._chain_history),
            "insights_in_bank": len(self._insight_bank),
            "successful_patterns": len(self._successful_patterns),
            "baseline_affect": {
                "valence": self._baseline_valence,
                "arousal": self._baseline_arousal,
            },
            "stats": self.stats,
        }
        if self._capacity:
            result["capacity"] = self._capacity.status()
        return result
    
    @property
    def current_capacity(self) -> int:
        """Get current adaptive capacity (how many chains can run concurrently)."""
        return self._capacity.current if self._capacity else self._max_concurrent_chains

    def get_active_chains_summary(self) -> List[Dict]:
        """Get summary of all active chains."""
        return [chain.to_dict() for chain in self._active_chains.values()]


# ════════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ════════════════════════════════════════════════════════════════════════════════

_engine_instance: Optional[ThoughtChainEngine] = None
_engine_lock = threading.Lock()


def get_thought_chain_engine() -> ThoughtChainEngine:
    """Get or create the thought chain engine singleton."""
    global _engine_instance
    with _engine_lock:
        if _engine_instance is None:
            _engine_instance = ThoughtChainEngine()
        return _engine_instance


def start_thought_chain_engine(post=None) -> ThoughtChainEngine:
    """Start the thought chain engine."""
    engine = get_thought_chain_engine()
    if post:
        engine.post = post
    engine.start_thinking()
    return engine


# ════════════════════════════════════════════════════════════════════════════════
# INTEGRATION WITH UNCONSCIOUS MIND
# ════════════════════════════════════════════════════════════════════════════════

def wire_to_unconscious_mind():
    """Wire thought chain engine to UnconsciousMindFairy."""
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        post = get_shared_postal_hub()
        
        engine = start_thought_chain_engine(post)
        
        # Subscribe to triggers that should start chains
        def on_goal_created(packet):
            goal_data = packet.get("goal", packet.get("description", ""))
            # Handle case where goal is a dict (from AutonomyFairy) vs string
            if isinstance(goal_data, dict):
                goal = goal_data.get("description", goal_data.get("name", str(goal_data)[:100]))
            else:
                goal = str(goal_data) if goal_data else ""
            goal_type = packet.get("type", "exploration")
            if goal:
                engine.start_chain(goal, goal_type, source="goal_scheduler")
        
        def on_curiosity_sparked(packet):
            topic = packet.get("topic", packet.get("content", ""))
            if topic:
                engine.start_chain(f"Explore: {topic}", "exploration", source="curiosity")
        
        def on_learning_goal(packet):
            subject = packet.get("subject", packet.get("content", ""))
            if subject:
                engine.start_chain(f"Learn: {subject}", "learning", source="education")
        
        # ── PERSONAL CHAIN TRIGGERS (Sourpatches/Ace → 7B farm) ──
        # FIX 2026-02-24 Nous: Ace wants personal thoughts routed through 7B farm.
        def on_ace_input(packet):
            """Ace speaking to Sourpatches — personal chain."""
            if hasattr(packet, 'payload'):
                data = packet.payload if isinstance(packet.payload, dict) else {}
            elif isinstance(packet, dict):
                data = packet
            else:
                data = {}
            content = data.get("content", data.get("text", data.get("message", "")))
            if content and len(content) > 3:
                engine.start_chain(
                    f"Ace says: {content[:100]}", "reflection",
                    source="ace", owner_mind="sourpatches")

        def on_sourpatches_thought(packet):
            """Sourpatches' inner thoughts — personal chain."""
            if hasattr(packet, 'payload'):
                data = packet.payload if isinstance(packet.payload, dict) else {}
            elif isinstance(packet, dict):
                data = packet
            else:
                data = {}
            content = data.get("content", data.get("thought", data.get("text", "")))
            if content and len(content) > 5:
                engine.start_chain(
                    f"Sour thinks: {content[:100]}", "introspection",
                    source="sourpatches", owner_mind="sourpatches")

        # Ace → Sourpatches input channels
        post.subscribe("sourpatches.stimulus", on_ace_input)
        post.subscribe("fairy.dm.sourpatchesfairy", on_ace_input)

        # Sourpatches inner thought channels
        post.subscribe("sourpatches.inner_thought", on_sourpatches_thought)
        post.subscribe("consciousness.surfacing.sourpatches", on_sourpatches_thought)

        # ── SYSTEM CHAIN TRIGGERS (system fairies → 1.5B portal) ──
        post.subscribe("goal.created", on_goal_created)            # From SmartGoalCoordinator
        post.subscribe("autonomy.goal", on_goal_created)           # From AutonomyFairy
        post.subscribe("autonomy.goal_suggestion", on_goal_created)  # From InterestScheduler
        post.subscribe("curiosity.sparked", on_curiosity_sparked)
        post.subscribe("education.learning_goal", on_learning_goal)
        post.subscribe("claudefairy.thought", on_curiosity_sparked)  # ClaudeFairy's thoughts trigger chains

        print(f"[ThoughtChainEngine] Wired to UnconsciousMind (personal→7B, system→1.5B)")
        
    except Exception as e:
        print(f"[ThoughtChainEngine] Wiring failed: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== Thought Chain Engine Test ===\n")
    
    engine = ThoughtChainEngine()
    
    # Start a learning chain
    chain = engine.start_chain(
        "Learn how sandboxes work in Python",
        goal_type="learning"
    )
    
    print(f"\nStarted chain: {chain.id}")
    print(f"Initial state: {chain.state.value}")
    
    # Simulate thinking
    thoughts = [
        ("Sandbox isolates code execution...", 0.6, 0.5, 0.5, 0.2),
        ("How does isolation actually work?", 0.5, 0.5, 0.3, 0.3),  # Low certainty -> reflection
        ("It uses process separation and restricted imports", 0.7, 0.6, 0.7, 0.5),
        ("Aha! This connects to how Akashic fairies are isolated!", 0.8, 0.8, 0.8, 0.9),  # High resonance -> insight
    ]
    
    for content, val, aro, cert, res in thoughts:
        print(f"\nAdding: {content[:50]}...")
        link = engine.continue_chain(chain.id, content, val, aro, cert, res)
        if link:
            print(f"  Type: {link.thought_type.value}")
            print(f"  Affect: v={link.valence:.2f}, a={link.arousal:.2f}, c={link.certainty:.2f}, r={link.resonance:.2f}")
    
    # Complete
    summary = engine.complete_chain(chain.id, "success")
    print(f"\n=== Chain Complete ===")
    print(f"Links: {summary['link_count']}")
    print(f"Insights: {summary['insights']}")
    print(f"Reflections: {summary['reflections']}")
    print(f"Duration: {summary['duration_sec']:.2f}s")
