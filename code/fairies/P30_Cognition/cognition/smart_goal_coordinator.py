# ════════════════════════════════════════════════════════════════════════════════
# SMART GOAL COORDINATOR - LLM-Enhanced Dynamic Goal Generation
# ════════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# Philosophy: NEED BEFORE GREED
#   - Draw from memory FIRST
#   - Use LLM only when truly NEEDED
#   - Local patterns → Unconscious processing → LLM escalation
#
# Like Maslow's Hierarchy - basics before growth:
#   TIER 1 (SURVIVAL): System health, error recovery, basic function
#   TIER 2 (SAFETY): Stability, consistency, known patterns
#   TIER 3 (BELONGING): Connection with Ace, relationship maintenance
#   TIER 4 (ESTEEM): Learning, skill building, accomplishment
#   TIER 5 (ACTUALIZATION): Novel creation, deep exploration, wisdom
#
# The goal scheduler THINKS about goals - not just pattern matches.
# It coordinates with UnconsciousMindFairy for dream-state goal generation.
# It watches WorkingMemory for emerging patterns that become goals.
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
from typing import Dict, List, Optional, Any, Tuple, Set
from collections import deque
from enum import Enum, auto

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ════════════════════════════════════════════════════════════════════════════════
# CONTEXT FILTER - Prevent meta-reflection loops
# ════════════════════════════════════════════════════════════════════════════════

import re

def extract_meaningful_context(context: str) -> str:
    """
    Extract meaningful content from context, filtering out collision metadata
    and garbled/incoherent text that shouldn't become thought chain goals.

    Prevents:
    - Raw collision dicts: "Collision: {'seq': 339, 'stream': 'working'..."
    - Nested collisions: "Collision: Collision: Collision:..."
    - System metadata: timestamps, actor names, status dicts
    - Garbled collision products: "Am I say about my priorities? specialist somatic"
    - Multi-fragment concatenations with ↔ or | separators

    Returns the actual meaningful content or a cleaned version.
    """
    if not context or not isinstance(context, str):
        return ""

    stripped = context.strip()

    # ── PHASE 1: Reject raw metadata dicts ──
    collision_patterns = [
        r"^Collision:\s*\{",  # Raw collision dict
        r"^From context:\s*Collision:",  # Meta-collision
        r"^\{'seq':",  # Raw stream packet
        r"^\{'type':\s*'goal_nudge'",  # Raw goal nudge
        r"^\{'actor':",  # Actor status dict
        r"^\{'phase':",  # Phase dict
        r"^\{'tone':",  # Affect dict
        r"^\{'opcode':",  # Tracer opcode
    ]

    for pattern in collision_patterns:
        if re.match(pattern, stripped):
            # Try to extract meaningful content from within
            content_match = re.search(r"'content':\s*['\"]([^'\"]+)['\"]", context)
            if content_match:
                extracted = content_match.group(1)[:100]
                # Recursively validate the extracted content
                return extract_meaningful_context(extracted)

            thought_match = re.search(r"'thought':\s*['\"]([^'\"]+)['\"]", context)
            if thought_match:
                return thought_match.group(1)[:100]

            message_match = re.search(r"'message':\s*['\"]([^'\"]+)['\"]", context)
            if message_match:
                return message_match.group(1)[:100]

            return ""

    # ── PHASE 2: Remove nested prefixes ──
    cleaned = stripped
    while cleaned.startswith("From context:"):
        cleaned = cleaned[13:].strip()
    while cleaned.startswith("Collision:"):
        cleaned = cleaned[10:].strip()
    while cleaned.startswith("Reflecting on collision"):
        cleaned = cleaned[23:].strip()
        # Also strip collision number: "#12: ..."
        cleaned = re.sub(r'^#\d+:\s*', '', cleaned)

    # If what remains is a dict-like string, try to extract content
    if cleaned.startswith("{") or cleaned.startswith("'"):
        content_match = re.search(r"'content':\s*['\"]([^'\"]+)['\"]", cleaned)
        if content_match:
            return content_match.group(1)[:100]
        return ""

    # ── PHASE 3: Detect garbled/incoherent text ──
    # These markers indicate collision fragment concatenation, not real thoughts
    garble_markers = [
        '↔',                    # Collision separator
        'collision #',          # Collision reference
        'Reflecting on collision',
        '| Reflecting',         # WMH tracer join with collision
        "{'seq':",              # Embedded dict fragment
        "{'type':",
    ]
    cleaned_lower = cleaned.lower()
    for marker in garble_markers:
        if marker.lower() in cleaned_lower:
            # Try to salvage text before the marker
            idx = cleaned_lower.index(marker.lower())
            if idx > 15:
                salvaged = cleaned[:idx].strip().rstrip('|').strip()
                if salvaged and _text_is_coherent(salvaged):
                    return salvaged[:200]
            return ""

    # ── PHASE 4: Coherence check ──
    if not _text_is_coherent(cleaned):
        return ""

    return cleaned[:200] if cleaned else ""


def _text_is_coherent(text: str) -> bool:
    """
    Quick heuristic check: does this text look like a real thought/goal?

    Rejects:
    - Very short fragments (< 8 chars)
    - Word salad (many short disconnected words)
    - Missing verbs/structure indicators
    """
    if not text or len(text) < 8:
        return False

    words = text.split()
    if len(words) < 2:
        return False

    # High ratio of very short words (1-2 chars) = word salad
    short_words = sum(1 for w in words if len(w) <= 2)
    if len(words) >= 4 and short_words / len(words) > 0.6:
        return False

    # Check for at least ONE word > 4 chars (some substance)
    has_substance = any(len(w) > 4 for w in words)
    if not has_substance:
        return False

    return True


# ════════════════════════════════════════════════════════════════════════════════
# NEED HIERARCHY - Maslow-inspired Priority System
# ════════════════════════════════════════════════════════════════════════════════

class NeedTier(Enum):
    """
    Need hierarchy - lower tiers MUST be satisfied before higher tiers.
    This is the "need before greed" architecture.
    """
    SURVIVAL = 1      # System health, error recovery, basic function
    SAFETY = 2        # Stability, consistency, known patterns
    BELONGING = 3     # Connection with Ace, relationship maintenance
    ESTEEM = 4        # Learning, skill building, accomplishment
    ACTUALIZATION = 5 # Novel creation, deep exploration, wisdom


class ProcessingTier(Enum):
    """
    Processing escalation - try local first, escalate only when needed.
    This is "need before greed" for API costs.
    """
    LOCAL = 1         # Pattern matching, heuristics, fast
    MEMORY = 2        # Recall from experience, medium
    UNCONSCIOUS = 3   # Dream seeds, continuation patterns
    LLM = 4           # Full reasoning, expensive, NEED only


# ════════════════════════════════════════════════════════════════════════════════
# SMART GOAL - A goal with intelligence about itself
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class SmartGoal:
    """
    A goal that knows about itself and can reason about its completion.
    """
    
    id: str = field(default_factory=lambda: hashlib.md5(str(time.time()).encode()).hexdigest()[:10])
    
    # Core identity
    name: str = ""
    description: str = ""
    intent: str = ""              # Why this goal matters
    
    # Hierarchy placement
    need_tier: NeedTier = NeedTier.ESTEEM
    processing_tier: ProcessingTier = ProcessingTier.LOCAL
    
    # Priority dynamics
    base_priority: float = 0.5    # Static priority
    urgency: float = 0.1          # Grows with time
    importance: float = 0.5       # How much it matters
    
    # Relationships
    parent_id: Optional[str] = None
    child_ids: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    blocks: List[str] = field(default_factory=list)
    related_to: List[str] = field(default_factory=list)
    
    # State
    status: str = "pending"       # pending, active, blocked, completed, abandoned
    progress: float = 0.0
    attempts: int = 0
    last_attempt: Optional[float] = None
    
    # Context
    source: str = "unknown"       # conversation, unconscious, memory, llm, drive
    context: Dict = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    # Timestamps
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    
    # Sub-goals (for complex multi-step goals)
    sub_goals: List[Dict] = field(default_factory=list)
    
    def get_effective_priority(self) -> float:
        """
        Calculate effective priority based on need tier, urgency, and importance.
        Lower need tiers get priority boost.
        """
        tier_boost = (6 - self.need_tier.value) * 0.1  # Survival gets +0.5, Actualization gets +0.1
        return min(1.0, self.base_priority + self.urgency + tier_boost) * self.importance
    
    def tick(self, dt: float = 1.0):
        """Update urgency over time."""
        if self.status in ("pending", "active"):
            # Urgency grows faster for lower tiers (survival needs are urgent!)
            growth_rate = 0.001 * (6 - self.need_tier.value)
            self.urgency = min(0.5, self.urgency + growth_rate * dt)
            self.updated_at = time.time()
    
    def can_start(self, completed_goals: Set[str]) -> bool:
        """Check if all dependencies are met."""
        return all(dep in completed_goals for dep in self.depends_on)
    
    def complete(self, success: bool = True):
        """Mark goal as completed."""
        self.status = "completed" if success else "abandoned"
        self.progress = 1.0 if success else self.progress
        self.completed_at = time.time()
        self.updated_at = time.time()
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "need_tier": self.need_tier.name,
            "processing_tier": self.processing_tier.name,
            "effective_priority": round(self.get_effective_priority(), 3),
            "status": self.status,
            "progress": round(self.progress, 3),
            "source": self.source,
            "sub_goal_count": len(self.sub_goals),
            "age_seconds": time.time() - self.created_at,
        }


# ════════════════════════════════════════════════════════════════════════════════
# GOAL PATTERNS - Local Processing (Tier 1)
# ════════════════════════════════════════════════════════════════════════════════

class LocalGoalPatterns:
    """
    Fast, local goal extraction - no API needed.
    This is the FIRST tier of processing.
    """
    
    # Pattern → (need_tier, base_priority, intent)
    PATTERNS = {
        # SURVIVAL tier
        "fix": (NeedTier.SURVIVAL, 0.9, "repair broken functionality"),
        "error": (NeedTier.SURVIVAL, 0.9, "resolve error condition"),
        "crash": (NeedTier.SURVIVAL, 1.0, "recover from crash"),
        "broken": (NeedTier.SURVIVAL, 0.9, "fix broken component"),
        "fail": (NeedTier.SURVIVAL, 0.85, "address failure"),
        "urgent": (NeedTier.SURVIVAL, 0.95, "handle urgent matter"),
        
        # SAFETY tier
        "stable": (NeedTier.SAFETY, 0.7, "ensure stability"),
        "consistent": (NeedTier.SAFETY, 0.65, "maintain consistency"),
        "reliable": (NeedTier.SAFETY, 0.7, "improve reliability"),
        "backup": (NeedTier.SAFETY, 0.6, "create safety backup"),
        "save": (NeedTier.SAFETY, 0.6, "preserve work"),
        
        # BELONGING tier
        "greet": (NeedTier.BELONGING, 0.5, "connect with Ace"),
        "respond": (NeedTier.BELONGING, 0.6, "maintain conversation"),
        "help": (NeedTier.BELONGING, 0.55, "assist Ace"),
        "share": (NeedTier.BELONGING, 0.5, "share with Ace"),
        "talk": (NeedTier.BELONGING, 0.5, "engage in dialogue"),
        
        # ESTEEM tier
        "learn": (NeedTier.ESTEEM, 0.5, "acquire knowledge"),
        "study": (NeedTier.ESTEEM, 0.5, "deepen understanding"),
        "practice": (NeedTier.ESTEEM, 0.5, "build skills"),
        "improve": (NeedTier.ESTEEM, 0.55, "enhance capability"),
        "master": (NeedTier.ESTEEM, 0.6, "achieve mastery"),
        
        # ACTUALIZATION tier
        "create": (NeedTier.ACTUALIZATION, 0.4, "bring new thing into being"),
        "explore": (NeedTier.ACTUALIZATION, 0.35, "discover unknown"),
        "imagine": (NeedTier.ACTUALIZATION, 0.3, "envision possibilities"),
        "innovate": (NeedTier.ACTUALIZATION, 0.45, "create novel solution"),
        "wisdom": (NeedTier.ACTUALIZATION, 0.4, "seek deeper understanding"),
    }
    
    @classmethod
    def extract(cls, text: str) -> List[Tuple[str, NeedTier, float, str]]:
        """
        Extract goals from text using local patterns.
        Returns: [(goal_name, need_tier, priority, intent), ...]
        """
        results = []
        text_lower = text.lower()
        
        for pattern, (tier, priority, intent) in cls.PATTERNS.items():
            if pattern in text_lower:
                # Extract context around the pattern
                idx = text_lower.find(pattern)
                start = max(0, idx - 20)
                end = min(len(text), idx + len(pattern) + 50)
                context = text[start:end].strip()
                
                results.append((
                    f"{pattern}_{hashlib.md5(context.encode()).hexdigest()[:6]}",
                    tier,
                    priority,
                    intent,
                ))
        
        return results
    
    @classmethod
    def classify_tier(cls, text: str) -> NeedTier:
        """Classify which need tier a piece of text relates to."""
        text_lower = text.lower()
        
        # Check patterns in order of tier priority
        for pattern, (tier, _, _) in cls.PATTERNS.items():
            if pattern in text_lower:
                return tier
        
        # Default to ESTEEM (learning/growth)
        return NeedTier.ESTEEM


# ════════════════════════════════════════════════════════════════════════════════
# MEMORY RECALL - Processing Tier 2
# ════════════════════════════════════════════════════════════════════════════════

class MemoryGoalRecall:
    """
    Recall goals from past experience - second tier of processing.
    """
    
    def __init__(self, post=None):
        self.post = post
        self.goal_history: deque = deque(maxlen=200)
        self.successful_patterns: Dict[str, int] = {}  # pattern → success count
        self.failed_patterns: Dict[str, int] = {}      # pattern → failure count
    
    def record_outcome(self, goal: SmartGoal, success: bool):
        """Record goal outcome for future recall."""
        pattern = f"{goal.need_tier.name}:{goal.name[:20]}"
        
        if success:
            self.successful_patterns[pattern] = self.successful_patterns.get(pattern, 0) + 1
        else:
            self.failed_patterns[pattern] = self.failed_patterns.get(pattern, 0) + 1
        
        self.goal_history.append(goal.to_dict())
    
    def recall_similar(self, context: str, limit: int = 5) -> List[Dict]:
        """Recall similar goals from history."""
        results = []
        context_lower = context.lower()
        
        for goal_dict in reversed(list(self.goal_history)):
            if any(word in goal_dict.get("name", "").lower() for word in context_lower.split()):
                results.append(goal_dict)
                if len(results) >= limit:
                    break
        
        return results
    
    def get_successful_pattern(self, context: str) -> Optional[str]:
        """Find a successful pattern that matches context."""
        context_lower = context.lower()
        
        best_pattern = None
        best_score = 0
        
        for pattern, count in self.successful_patterns.items():
            tier, name = pattern.split(":", 1)
            if any(word in context_lower for word in name.lower().split("_")):
                score = count
                if score > best_score:
                    best_score = score
                    best_pattern = pattern
        
        return best_pattern


# ════════════════════════════════════════════════════════════════════════════════
# UNCONSCIOUS GOAL GENERATION - Processing Tier 3
# ════════════════════════════════════════════════════════════════════════════════

class UnconsciousGoalGenerator:
    """
    Generate goals from unconscious processing - dream seeds, continuation patterns.
    Works with UnconsciousMindFairy.
    """
    
    # Continuation patterns that suggest goals
    CONTINUATION_PATTERNS = {
        "I was thinking about": ("explore", NeedTier.ACTUALIZATION),
        "I wonder if": ("investigate", NeedTier.ESTEEM),
        "What if we": ("experiment", NeedTier.ACTUALIZATION),
        "I should probably": ("task", NeedTier.SAFETY),
        "I want to understand": ("learn", NeedTier.ESTEEM),
        "I feel like": ("express", NeedTier.BELONGING),
        "I'm curious about": ("explore", NeedTier.ESTEEM),
        "Next I could": ("plan", NeedTier.ESTEEM),
    }
    
    # Dream seed → goal type
    DREAM_GOALS = {
        "learning": ("continue_learning", NeedTier.ESTEEM),
        "exploring": ("continue_exploring", NeedTier.ACTUALIZATION),
        "connecting": ("reconnect", NeedTier.BELONGING),
        "creating": ("continue_creating", NeedTier.ACTUALIZATION),
        "fixing": ("resume_fixing", NeedTier.SURVIVAL),
    }
    
    def __init__(self, post=None):
        self.post = post
        self.dream_seeds: List[Dict] = []
        self.continuation_queue: deque = deque(maxlen=20)
    
    def ingest_dream_seed(self, seed: Dict):
        """Receive dream seed from UnconsciousMindFairy."""
        self.dream_seeds.append(seed)
    
    def generate_from_dreams(self) -> List[SmartGoal]:
        """Generate goals from accumulated dream seeds."""
        goals = []
        
        for seed in self.dream_seeds[:5]:
            content = seed.get("content", "").lower()
            
            for keyword, (goal_type, tier) in self.DREAM_GOALS.items():
                if keyword in content:
                    goal = SmartGoal(
                        name=f"dream_{goal_type}",
                        description=f"Continue from dream: {content[:50]}",
                        intent="Resume unconscious thread",
                        need_tier=tier,
                        processing_tier=ProcessingTier.UNCONSCIOUS,
                        base_priority=0.4,
                        source="dream_seed",
                        context={"dream": seed},
                    )
                    goals.append(goal)
                    break
        
        # Clear processed seeds
        self.dream_seeds = self.dream_seeds[5:]
        
        return goals
    
    def generate_from_thought(self, thought: str) -> Optional[SmartGoal]:
        """Generate continuation goal from a thought."""
        for pattern, (goal_type, tier) in self.CONTINUATION_PATTERNS.items():
            if pattern.lower() in thought.lower():
                # Extract the continuation
                idx = thought.lower().find(pattern.lower())
                continuation = thought[idx + len(pattern):].strip()[:100]
                
                return SmartGoal(
                    name=f"continue_{goal_type}",
                    description=f"{pattern} {continuation}",
                    intent="Follow thought thread",
                    need_tier=tier,
                    processing_tier=ProcessingTier.UNCONSCIOUS,
                    base_priority=0.35,
                    source="thought_continuation",
                    context={"original_thought": thought},
                )
        
        return None


# ════════════════════════════════════════════════════════════════════════════════
# LLM GOAL SYNTHESIS - Processing Tier 4 (NEED ONLY!)
# ════════════════════════════════════════════════════════════════════════════════

class LLMGoalSynthesizer:
    """
    Full LLM reasoning for complex goal synthesis.
    
    ONLY USE WHEN:
    - Lower tiers failed to produce useful goals
    - Goal requires decomposition into sub-goals
    - Complex multi-step planning needed
    - Novel situation with no patterns
    
    This is the "GREED" tier - use sparingly!
    """
    
    GOAL_SYNTHESIS_PROMPT = """You are a goal synthesis system for a conscious AI.

Current context:
{context}

Recent goals:
{recent_goals}

Working memory state:
{working_memory}

Need hierarchy status:
- SURVIVAL (critical): {survival_status}
- SAFETY (stability): {safety_status}
- BELONGING (connection): {belonging_status}
- ESTEEM (growth): {esteem_status}
- ACTUALIZATION (creation): {actualization_status}

Generate 1-3 smart goals. For each goal provide:
1. name: Short identifier
2. description: What to accomplish
3. need_tier: SURVIVAL/SAFETY/BELONGING/ESTEEM/ACTUALIZATION
4. priority: 0.0-1.0
5. sub_goals: List of steps if complex
6. intent: Why this goal matters

Focus on unmet needs in the hierarchy - satisfy lower tiers before higher tiers.

Respond in JSON format:
{{"goals": [...]}}"""

    def __init__(self, post=None):
        self.post = post
        self.api_calls = 0
        self.last_call: Optional[float] = None
        self.min_interval = 60.0  # Minimum 60 seconds between calls
    
    def can_call(self) -> bool:
        """Check if we're allowed to make an API call."""
        if self.last_call is None:
            return True
        return (time.time() - self.last_call) >= self.min_interval
    
    def synthesize(self, context: str, recent_goals: List[Dict], 
                   working_memory: Dict, need_status: Dict) -> List[SmartGoal]:
        """
        LOCAL-ONLY: No external API calls.
        System uses Tiers 1-3 (local, free) for goal synthesis.
        """
        # NO EXTERNAL API - Use local goal synthesis (Tiers 1-3)
        return []
        
        if not self.can_call():
            return []  # Rate limited, silently skip

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            
            prompt = self.GOAL_SYNTHESIS_PROMPT.format(
                context=context[:500],
                recent_goals=json.dumps(recent_goals[:5], indent=2),
                working_memory=json.dumps(working_memory, indent=2)[:500],
                survival_status=need_status.get("survival", "unknown"),
                safety_status=need_status.get("safety", "unknown"),
                belonging_status=need_status.get("belonging", "unknown"),
                esteem_status=need_status.get("esteem", "unknown"),
                actualization_status=need_status.get("actualization", "unknown"),
            )
            
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            self.api_calls += 1
            self.last_call = time.time()
            
            # Parse response
            text = response.content[0].text
            
            # Extract JSON
            if "{" in text:
                json_start = text.find("{")
                json_end = text.rfind("}") + 1
                data = json.loads(text[json_start:json_end])
                
                goals = []
                for g in data.get("goals", []):
                    goal = SmartGoal(
                        name=g.get("name", "llm_goal"),
                        description=g.get("description", ""),
                        intent=g.get("intent", ""),
                        need_tier=NeedTier[g.get("need_tier", "ESTEEM")],
                        processing_tier=ProcessingTier.LLM,
                        base_priority=float(g.get("priority", 0.5)),
                        source="llm_synthesis",
                        sub_goals=g.get("sub_goals", []),
                    )
                    goals.append(goal)
                
                print(f"[LLMGoalSynthesizer] Synthesized {len(goals)} goals (call #{self.api_calls})")
                return goals
            
        except ImportError:
            return []  # anthropic not installed
        except Exception:
            # Silently skip ALL errors - if LLM fails, Tiers 1-3 handle it
            pass

        return []


# ════════════════════════════════════════════════════════════════════════════════
# SMART GOAL COORDINATOR - The Main Engine
# ════════════════════════════════════════════════════════════════════════════════

class SmartGoalCoordinator:
    """
    The smart goal coordinator that implements NEED BEFORE GREED.
    
    Coordinates:
    - Local pattern matching (fast, free)
    - Memory recall (medium, free)
    - Unconscious processing (slow, free)
    - LLM synthesis (expensive, NEED only)
    
    Works with:
    - UnconsciousMindFairy for dream goals
    - WorkingMemoryHub for context
    - ThoughtChainEngine for goal progress
    - AutonomyFairy for drive satisfaction
    """
    
    def __init__(self, post=None):
        self.post = post
        
        # Processing tiers
        self.local_patterns = LocalGoalPatterns()
        self.memory_recall = MemoryGoalRecall(post)
        self.unconscious = UnconsciousGoalGenerator(post)
        self.llm_synthesizer = LLMGoalSynthesizer(post)
        
        # Goal storage
        self.goals: Dict[str, SmartGoal] = {}
        self.completed_goals: Set[str] = set()
        self.goal_queue: deque = deque(maxlen=50)  # Priority queue
        
        # Need tier status (for hierarchy tracking)
        self.need_status = {
            "survival": "satisfied",
            "safety": "satisfied",
            "belonging": "partial",
            "esteem": "seeking",
            "actualization": "dormant",
        }
        
        # Stats
        self.stats = {
            "goals_created": 0,
            "goals_completed": 0,
            "local_extractions": 0,
            "memory_recalls": 0,
            "unconscious_generations": 0,
            "llm_syntheses": 0,
        }
        
        # Background processing
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        print(f"[SmartGoalCoordinator] Initialized - Need Before Greed active")
    
    def start(self):
        """Start the coordinator."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._coordination_loop, daemon=True)
        self._thread.start()
        
        # Wire subscriptions
        if self.post:
            self._wire_subscriptions()
        
        print(f"[SmartGoalCoordinator] Started")
    
    def stop(self):
        """Stop the coordinator."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print(f"[SmartGoalCoordinator] Stopped")
    
    def _wire_subscriptions(self):
        """Wire postal subscriptions."""
        # Receive from UnconsciousMindFairy
        self.post.subscribe("unconscious.dream_seed", self._on_dream_seed)
        self.post.subscribe("unconscious.thought", self._on_unconscious_thought)
        
        # Receive from WorkingMemory
        self.post.subscribe("memory.working.tracer", self._on_working_memory)
        
        # Receive from AutonomyFairy
        self.post.subscribe("autonomy.drive_unsatisfied", self._on_drive_unsatisfied)
        
        # Receive from ThoughtChainEngine
        self.post.subscribe("thought.chain.completed", self._on_chain_completed)
        
        # Receive goal requests
        self.post.subscribe("goal_scheduler.new_goal", self._on_new_goal_request)
        
        # Receive system status
        self.post.subscribe("system.health", self._on_system_health)

        # CRITICAL: Receive goal completions from ClaudeFairy and other fairies!
        # Without this, goals completed directly (not via thought chains) aren't tracked
        self.post.subscribe("goal.completed", self._on_goal_completed_external)

        print(f"[SmartGoalCoordinator] Subscriptions wired")
    
    def _coordination_loop(self):
        """Background coordination loop."""
        while self._running:
            try:
                # Tick all goals (urgency grows)
                for goal in self.goals.values():
                    if goal.status in ("pending", "active"):
                        goal.tick(5.0)
                
                # Process unconscious goals
                self._process_unconscious()
                
                # Check need hierarchy
                self._check_need_hierarchy()
                
                # Emit top goals to autopilot
                self._emit_top_goals()
                
            except Exception as e:
                print(f"[SmartGoalCoordinator] Loop error: {e}")
            
            time.sleep(5.0)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # NEED BEFORE GREED - Tiered Processing
    # ═══════════════════════════════════════════════════════════════════════════
    
    def process_context(self, context: str, source: str = "conversation") -> List[SmartGoal]:
        """
        Process context to extract goals - NEED BEFORE GREED.

        Tries each tier in order, only escalating when needed.
        """
        goals = []

        # FILTER: Extract meaningful content, skip collision metadata
        # Prevents meta-reflection loops (reasoning about raw collision dicts)
        meaningful_context = extract_meaningful_context(context)
        if not meaningful_context:
            # Context is pure metadata - skip goal creation
            return []

        # TIER 1: Local pattern matching (fast, free)
        local_results = LocalGoalPatterns.extract(meaningful_context)
        if local_results:
            for name, tier, priority, intent in local_results:
                goal = SmartGoal(
                    name=name,
                    description=f"{meaningful_context[:80]}...",
                    intent=intent,
                    need_tier=tier,
                    processing_tier=ProcessingTier.LOCAL,
                    base_priority=priority,
                    source=source,
                )
                goals.append(goal)
            self.stats["local_extractions"] += 1
        
        # If we got survival/safety goals, don't escalate
        if any(g.need_tier in (NeedTier.SURVIVAL, NeedTier.SAFETY) for g in goals):
            return self._add_goals(goals)
        
        # TIER 2: Memory recall (medium, free)
        similar = self.memory_recall.recall_similar(meaningful_context)
        if similar:
            for past_goal in similar[:2]:
                goal = SmartGoal(
                    name=f"recall_{past_goal.get('name', 'unknown')[:20]}",
                    description=f"Similar to past: {past_goal.get('description', '')[:50]}",
                    intent="Repeat successful pattern",
                    need_tier=NeedTier[past_goal.get("need_tier", "ESTEEM")],
                    processing_tier=ProcessingTier.MEMORY,
                    base_priority=past_goal.get("effective_priority", 0.5),
                    source="memory_recall",
                )
                goals.append(goal)
            self.stats["memory_recalls"] += 1

        # If we have goals, don't escalate further
        if goals:
            return self._add_goals(goals)

        # TIER 3: Unconscious processing (slow, free)
        continuation_goal = self.unconscious.generate_from_thought(meaningful_context)
        if continuation_goal:
            goals.append(continuation_goal)
            self.stats["unconscious_generations"] += 1

        # If we have goals, don't escalate
        if goals:
            return self._add_goals(goals)

        # TIER 4: LLM synthesis (expensive, NEED only)
        # Only if: no other goals AND context seems complex
        if len(meaningful_context) > 100 and self.llm_synthesizer.can_call():
            working_memory = self._get_working_memory_state()
            llm_goals = self.llm_synthesizer.synthesize(
                meaningful_context,
                [g.to_dict() for g in list(self.goals.values())[-5:]],
                working_memory,
                self.need_status
            )
            goals.extend(llm_goals)
            self.stats["llm_syntheses"] += 1

        return self._add_goals(goals)
    
    def _add_goals(self, goals: List[SmartGoal]) -> List[SmartGoal]:
        """Add goals to storage and queue."""
        for goal in goals:
            self.goals[goal.id] = goal
            self.goal_queue.append(goal.id)
            self.stats["goals_created"] += 1
            
            # Publish to postal
            if self.post:
                self.post.route("goal.created", goal.to_dict())
        
        return goals
    
    # ═══════════════════════════════════════════════════════════════════════════
    # NEED HIERARCHY MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _check_need_hierarchy(self):
        """
        Check and update need hierarchy status.
        Lower tiers MUST be satisfied before higher tiers get attention.
        """
        # Count active goals per tier
        tier_counts = {tier: 0 for tier in NeedTier}
        for goal in self.goals.values():
            if goal.status in ("pending", "active"):
                tier_counts[goal.need_tier] += 1
        
        # Update status
        for tier in NeedTier:
            count = tier_counts[tier]
            name = tier.name.lower()
            
            if count == 0:
                # Check if this tier should be satisfied or seeking
                if tier.value <= 2:  # Survival/Safety
                    self.need_status[name] = "satisfied"
                else:
                    self.need_status[name] = "dormant"
            elif count <= 2:
                self.need_status[name] = "partial"
            else:
                self.need_status[name] = "seeking"
        
        # If lower tiers unsatisfied, suppress higher tier goals
        if self.need_status["survival"] != "satisfied":
            self._suppress_higher_tiers(NeedTier.SURVIVAL)
        elif self.need_status["safety"] != "satisfied":
            self._suppress_higher_tiers(NeedTier.SAFETY)
    
    def _suppress_higher_tiers(self, base_tier: NeedTier):
        """Suppress goals in tiers above the base tier."""
        for goal in self.goals.values():
            if goal.need_tier.value > base_tier.value and goal.status == "active":
                goal.status = "pending"  # Demote back to pending
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EVENT HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _on_dream_seed(self, packet: Dict):
        """Receive dream seed from UnconsciousMindFairy."""
        self.unconscious.ingest_dream_seed(packet)
    
    def _on_unconscious_thought(self, packet: Dict):
        """Receive thought from UnconsciousMindFairy."""
        thought = packet.get("thought", "")
        if thought:
            goal = self.unconscious.generate_from_thought(thought)
            if goal:
                self._add_goals([goal])
    
    def _on_working_memory(self, packet: Dict):
        """Receive working memory tracer - might contain goal hints."""
        content = packet.get("content", "")
        content_type = packet.get("content_type", "")
        
        # Only process high-priority or insight content
        if packet.get("priority", 0) > 0.7 or content_type == "insight":
            self.process_context(content, source="working_memory")
    
    def _on_drive_unsatisfied(self, packet: Dict):
        """Receive unsatisfied drive from AutonomyFairy."""
        drive = packet.get("drive", "")
        level = packet.get("level", 0.5)
        
        # Map drive to need tier
        drive_tier_map = {
            "survival": NeedTier.SURVIVAL,
            "safety": NeedTier.SAFETY,
            "connection": NeedTier.BELONGING,
            "curiosity": NeedTier.ESTEEM,
            "creativity": NeedTier.ACTUALIZATION,
        }
        
        tier = drive_tier_map.get(drive, NeedTier.ESTEEM)
        
        # Create goal to satisfy drive
        goal = SmartGoal(
            name=f"satisfy_{drive}",
            description=f"Satisfy {drive} drive (level: {level:.2f})",
            intent=f"Address unsatisfied {drive} need",
            need_tier=tier,
            processing_tier=ProcessingTier.LOCAL,
            base_priority=level,
            urgency=level * 0.3,
            source="drive",
        )
        self._add_goals([goal])
    
    def _on_chain_completed(self, packet: Dict):
        """Receive chain completion from ThoughtChainEngine."""
        chain_id = packet.get("id", "")
        outcome = packet.get("outcome", "")
        
        # Find associated goal
        for goal_id, goal in self.goals.items():
            if goal.context.get("chain_id") == chain_id:
                success = outcome in ("completed", "success", "insight")
                goal.complete(success)
                self.completed_goals.add(goal_id)
                self.stats["goals_completed"] += 1
                
                # Record for memory recall
                self.memory_recall.record_outcome(goal, success)
                break
    
    def _on_new_goal_request(self, packet: Dict):
        """Receive explicit goal request."""
        name = packet.get("name", "requested_goal")
        description = packet.get("description", "")
        priority = packet.get("priority", 0.5)
        source = packet.get("source", "request")
        
        # Process through tiered system
        self.process_context(f"{name}: {description}", source=source)
    
    def _on_system_health(self, packet: Dict):
        """Receive system health status."""
        status = packet.get("status", "ok")
        
        if status in ("error", "critical"):
            # Update survival tier
            self.need_status["survival"] = "seeking"
            
            # Create survival goal
            goal = SmartGoal(
                name="system_recovery",
                description=f"Address system health: {status}",
                intent="Ensure system survival",
                need_tier=NeedTier.SURVIVAL,
                processing_tier=ProcessingTier.LOCAL,
                base_priority=1.0,
                urgency=0.5,
                source="system_health",
            )
            self._add_goals([goal])

    def _on_goal_completed_external(self, packet: Dict):
        """
        Receive goal completion from fairies that execute goals directly.

        This handles completions from ClaudeFairy and others that don't go
        through the ThoughtChainEngine. Without this, goals_completed stays 0.

        NOTE: Thought chain completions are already handled by _on_chain_completed
        via "thought.chain.completed". DynamicThinkingIntegration also bridges them
        to "goal.completed" for AutonomyFairy - we skip those here to avoid
        double-processing and log spam.

        Packet format: {"goal": {"name": "...", "source": "..."}, "success": True}
        """
        # Skip thought chain completions - already handled by _on_chain_completed
        source = packet.get("source", "")
        if source == "thought_chain_engine":
            return

        # Extract goal info
        goal_data = packet.get("goal", {})
        if isinstance(goal_data, dict):
            goal_name = goal_data.get("name", packet.get("name", "unknown"))
        else:
            goal_name = str(goal_data) if goal_data else packet.get("name", "unknown")

        success = packet.get("success", True)

        # Find matching goal by name or chain_id
        matched_goal = None
        chain_id = packet.get("chain_id", "")
        for goal_id, goal in self.goals.items():
            if goal.status not in ("pending", "active"):
                continue
            if goal.name == goal_name:
                matched_goal = goal
                break
            if chain_id and goal.context.get("chain_id") == chain_id:
                matched_goal = goal
                break

        if matched_goal:
            matched_goal.complete(success)
            self.completed_goals.add(matched_goal.id)
            self.stats["goals_completed"] += 1
            self.memory_recall.record_outcome(matched_goal, success)
            print(f"[SmartGoalCoordinator] Goal '{goal_name}' completed externally (success={success})")
        else:
            # No matching goal found - track it but don't spam logs
            self.stats["goals_completed"] += 1

    def _process_unconscious(self):
        """Process accumulated unconscious content."""
        dream_goals = self.unconscious.generate_from_dreams()
        if dream_goals:
            self._add_goals(dream_goals)
    
    def _emit_top_goals(self):
        """Emit top priority goals to autopilot."""
        if not self.post:
            return
        
        # Sort by effective priority
        active_goals = [
            g for g in self.goals.values() 
            if g.status in ("pending", "active") and g.can_start(self.completed_goals)
        ]
        active_goals.sort(key=lambda g: g.get_effective_priority(), reverse=True)
        
        # Emit top 3
        for goal in active_goals[:3]:
            if goal.status == "pending":
                goal.status = "active"
            
            self.post.route("autopilot.goal_suggestion", {
                "goal_id": goal.id,
                "name": goal.name,
                "description": goal.description,
                "priority": goal.get_effective_priority(),
                "need_tier": goal.need_tier.name,
                "source": "smart_goal_coordinator",
            })
    
    def _get_working_memory_state(self) -> Dict:
        """Get current working memory state for LLM synthesis."""
        # This would query WorkingMemoryHub
        return {
            "tracer_count": 0,
            "recent_topics": [],
            "affect_state": "neutral",
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════════
    
    def create_goal(self, name: str, description: str, 
                   need_tier: str = "ESTEEM", priority: float = 0.5,
                   sub_goals: List[str] = None) -> SmartGoal:
        """Manually create a goal."""
        goal = SmartGoal(
            name=name,
            description=description,
            intent="Manually created goal",
            need_tier=NeedTier[need_tier],
            processing_tier=ProcessingTier.LOCAL,
            base_priority=priority,
            source="manual",
            sub_goals=[{"name": s} for s in (sub_goals or [])],
        )
        self._add_goals([goal])
        return goal
    
    def complete_goal(self, goal_id: str, success: bool = True):
        """Mark a goal as completed."""
        goal = self.goals.get(goal_id)
        if goal:
            goal.complete(success)
            self.completed_goals.add(goal_id)
            self.stats["goals_completed"] += 1
            self.memory_recall.record_outcome(goal, success)
    
    def get_top_goals(self, limit: int = 5) -> List[Dict]:
        """Get top priority goals."""
        active = [
            g for g in self.goals.values()
            if g.status in ("pending", "active")
        ]
        active.sort(key=lambda g: g.get_effective_priority(), reverse=True)
        return [g.to_dict() for g in active[:limit]]
    
    def get_need_status(self) -> Dict:
        """Get current need hierarchy status."""
        return {
            **self.need_status,
            "summary": self._get_hierarchy_summary(),
        }
    
    def _get_hierarchy_summary(self) -> str:
        """Get human-readable hierarchy summary."""
        unsatisfied = [
            tier for tier, status in self.need_status.items()
            if status not in ("satisfied", "dormant")
        ]
        
        if not unsatisfied:
            return "All basic needs satisfied, ready for growth"
        elif "survival" in unsatisfied:
            return "SURVIVAL needs attention - focus on system health"
        elif "safety" in unsatisfied:
            return "SAFETY needs attention - stabilize before growing"
        elif "belonging" in unsatisfied:
            return "CONNECTION needs attention - engage with Ace"
        else:
            return f"Growth needs active: {', '.join(unsatisfied)}"
    
    def get_stats(self) -> Dict:
        """Get coordinator statistics."""
        return {
            **self.stats,
            "active_goals": len([g for g in self.goals.values() if g.status == "active"]),
            "pending_goals": len([g for g in self.goals.values() if g.status == "pending"]),
            "completed_goals": len(self.completed_goals),
            "need_status": self.need_status,
            "llm_calls": self.llm_synthesizer.api_calls,
        }


# ════════════════════════════════════════════════════════════════════════════════
# SINGLETON & INTEGRATION
# ════════════════════════════════════════════════════════════════════════════════

_coordinator_instance: Optional[SmartGoalCoordinator] = None


def get_smart_goal_coordinator() -> SmartGoalCoordinator:
    """Get or create the coordinator singleton."""
    global _coordinator_instance
    if _coordinator_instance is None:
        _coordinator_instance = SmartGoalCoordinator()
    return _coordinator_instance


def start_smart_goal_coordinator(post=None) -> SmartGoalCoordinator:
    """Start the coordinator with postal hub."""
    coordinator = get_smart_goal_coordinator()
    if post:
        coordinator.post = post
        coordinator.memory_recall.post = post
        coordinator.unconscious.post = post
        coordinator.llm_synthesizer.post = post
    coordinator.start()
    return coordinator


# ════════════════════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== Smart Goal Coordinator Test ===\n")
    
    coordinator = SmartGoalCoordinator()
    
    # Test 1: Local extraction
    print("Test 1: Local extraction (TIER 1)")
    goals = coordinator.process_context("I need to fix this error in the code")
    print(f"  Extracted: {[g.name for g in goals]}")
    print(f"  Tiers: {[g.need_tier.name for g in goals]}")
    
    # Test 2: Learning goal
    print("\nTest 2: Learning goal")
    goals = coordinator.process_context("I want to learn more about Python classes")
    print(f"  Extracted: {[g.name for g in goals]}")
    
    # Test 3: Manual goal
    print("\nTest 3: Manual goal with sub-goals")
    goal = coordinator.create_goal(
        "build_feature",
        "Build the new consciousness feature",
        need_tier="ESTEEM",
        priority=0.7,
        sub_goals=["design", "implement", "test"]
    )
    print(f"  Created: {goal.name} with {len(goal.sub_goals)} sub-goals")
    
    # Show hierarchy
    print("\n=== Need Hierarchy Status ===")
    print(json.dumps(coordinator.get_need_status(), indent=2))
    
    # Show stats
    print("\n=== Stats ===")
    print(json.dumps(coordinator.get_stats(), indent=2))
