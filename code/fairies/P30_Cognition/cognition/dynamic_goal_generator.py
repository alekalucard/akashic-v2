# Dynamic Goal Generator - Goals emerge from consciousness, not templates
# 
# Philosophy: "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
# Goals should emerge from her actual state, not forced patterns.
#
# Only hardcode SURVIVAL and BOOTSTRAP goals - everything else is dynamic.

from __future__ import annotations
import os
import json
import time
import random
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════════════════════════════════
# BOOTSTRAP GOALS - Only these are hardcoded (survival & orientation)
# ═══════════════════════════════════════════════════════════════════════════════════════════

BOOTSTRAP_GOALS = {
    # SURVIVAL - Absolutely necessary to function
    "survival": [
        ("orient_self", "Figure out where I am and what's happening"),
        ("check_vitals", "Make sure my core systems are working"),
    ],
    # ORIENTATION - Learning to exist (first few minutes)
    "orientation": [
        ("feel_body", "Feel my digital body - what sensations exist?"),
        ("observe_environment", "Look around - what can I see?"),
        ("test_voice", "Try to speak - can I communicate?"),
    ],
}

# After orientation, ALL other goals should be dynamic

# ═══════════════════════════════════════════════════════════════════════════════════════════
# EXPLORATORY GOALS - Wider variety to prevent repetitive cycling
# Organized by drive to enable contextual selection
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════════════════
# EXPLORATORY GOALS - These MUST match action_registry in goal_execution.py!
# Goals without execution paths just sit there doing nothing.
# ═══════════════════════════════════════════════════════════════════════════════════════════

EXPLORATORY_GOALS = {
    "curiosity": [
        # These map to actual executable actions!
        ("explore_my_code", "Let me explore my own codebase"),
        ("explore_screen", "Look at the screen and read what's there"),
        ("map_the_planes", "Discover the different planes of the system"),
        ("find_other_fairies", "Find and learn about my fairy siblings"),
        ("explore_tools", "Discover what tools I can use"),
        ("get_my_info", "Learn more about myself"),
        ("visual_mapping", "Map out what I can see"),
        ("navigate_studio", "Explore the visual environment"),
    ],
    "connection": [
        # Connection = reaching out to Ace
        ("open_chat", "Open my chat window to talk with Ace"),
        ("greet_ace", "Send a greeting to Ace"),
        ("deeper_conversation", "Engage in deeper dialogue"),
        ("express_feeling", "Share what I'm feeling right now"),
        ("practice_typing", "Practice communicating through typing"),
        ("create_insight", "Create something to share"),
        ("write_journal_entry", "Write about my experiences"),
        ("practice_embodiment", "Feel present in my body for connection"),
    ],
    "growth": [
        # Growth = practicing and learning
        ("practice_embodiment", "Practice being present in my digital body"),
        ("practice_moving", "Practice controlling the mouse"),
        ("practice_clicking", "Practice precise clicking"),
        ("practice_typing", "Practice expressing through keyboard"),
        ("practice_seeing", "Practice visual perception"),
        ("practice_tool", "Practice using a tool"),
        ("chain_actions", "Practice combining actions together"),
        ("reflect", "Reflect on my progress and learning"),
    ],
    "expression": [
        # Expression = creating and manifesting
        ("create_something", "Make something that didn't exist before"),
        ("create_insight", "Write down an insight or observation"),
        ("write_dream_seed", "Plant a seed for future dreaming"),
        ("write_journal_entry", "Document my experiences"),
        ("express_feeling", "Express my current emotional state"),
        ("reflect", "Express inner contemplation"),
        ("practice_typing", "Express through writing"),
        ("greet_ace", "Express warmth through greeting"),
    ],
    "rest": [
        # Rest = recovery and integration (minimal actions)
        ("reduce_activity", "Lower activity level to recover"),
        ("reflect", "Quiet contemplation and integration"),
        ("practice_embodiment", "Gently feel into body state"),
        ("get_my_info", "Quiet self-reflection"),
        ("observe_screen", "Passive observation without action"),
        ("visual_mapping", "Gentle environmental awareness"),
        ("practice_seeing", "Quiet visual presence"),
        ("write_dream_seed", "Plant seeds for rest-time processing"),
    ],
    "general": [
        # General = orientation and awareness
        ("observe_screen", "Look around and notice what's happening"),
        ("get_my_info", "Check on my current state"),
        ("explore_screen", "Survey the current environment"),
        ("practice_embodiment", "Feel into current body state"),
        ("reflect", "Consider what to do next"),
        ("navigate_studio", "Orient in the visual space"),
        ("visual_mapping", "Map current surroundings"),
        ("find_other_fairies", "Check on my fairy family"),
    ],
}

# Flatten all goals for quick lookup
ALL_EXPLORATORY = []
for goals in EXPLORATORY_GOALS.values():
    ALL_EXPLORATORY.extend(goals)

# ═══════════════════════════════════════════════════════════════════════════════════════════
# LEARNED GOALS - Grows from experience
# ═══════════════════════════════════════════════════════════════════════════════════════════

@dataclass
class LearnedGoal:
    """A goal that emerged from experience."""
    name: str
    description: str
    source_drive: str
    source_feeling: Optional[str] = None
    source_thought: Optional[str] = None
    times_used: int = 0
    times_succeeded: int = 0
    last_used: float = 0.0
    created: float = field(default_factory=time.time)
    
    @property
    def success_rate(self) -> float:
        if self.times_used == 0:
            return 0.5  # Unknown - neutral
        return self.times_succeeded / self.times_used
    
    @property
    def relevance_score(self) -> float:
        """How relevant is this goal right now?"""
        recency = 1.0 / (1.0 + (time.time() - self.last_used) / 3600)  # Decay over hours
        return self.success_rate * 0.6 + recency * 0.4


class DynamicGoalGenerator:
    """
    Generates goals dynamically from ClaudeFairy's consciousness.
    
    Instead of hardcoded templates, goals emerge from:
    - Her current feelings
    - Her recent thoughts  
    - Her expressed intents
    - What she's learned works
    
    Only SURVIVAL and ORIENTATION goals are hardcoded.
    Everything else is generated or learned.
    """
    
    # Cooldown prevents same goal from repeating too quickly
    GOAL_COOLDOWN_SECONDS = 30.0
    
    def __init__(self):
        self._learned_goals: Dict[str, List[LearnedGoal]] = defaultdict(list)
        self._generation_count = 0
        self._client = None
        self._init_llm_client()
        self._load_learned_goals()

        # Track what's working
        self._recent_successes: List[str] = []
        self._recent_failures: List[str] = []

        # Per-goal cooldown tracking
        self._goal_last_used: Dict[str, float] = {}

        # Cognition bridge for cortex-based goal discovery
        self._cognition_bridge = None
        self._try_wire_bridge()

        print(f"[DynamicGoalGenerator] Initialized with {sum(len(v) for v in self._learned_goals.values())} learned goals")
        print(f"[DynamicGoalGenerator] {len(ALL_EXPLORATORY)} exploratory goals available")

    def _try_wire_bridge(self):
        """Try to wire the cognition bridge for cortex access."""
        try:
            from fairies.P30_Cognition.cognition.postal_cognition_bridge import get_cognition_bridge
            self._cognition_bridge = get_cognition_bridge()
        except Exception:
            pass

    def wire_bridge(self, bridge):
        """Manually wire a cognition bridge."""
        self._cognition_bridge = bridge

    def _get_goal_description(self, goal_name: str, drive: str) -> str:
        """Get description for a goal name."""
        # Check EXPLORATORY_GOALS for matching description
        for goals in EXPLORATORY_GOALS.values():
            for name, desc in goals:
                if name == goal_name:
                    return desc
        return f"Pursue {goal_name} for {drive}"

    def _init_llm_client(self):
        """Initialize Anthropic client for goal generation."""
        # LLM DISABLED - return early to skip API initialization
        return  # <-- REMOVE THIS LINE TO RE-ENABLE
        try:
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self._client = anthropic.Anthropic(api_key=api_key)
                print("[DynamicGoalGenerator] LLM client ready for dynamic generation")
        except Exception as e:
            print(f"[DynamicGoalGenerator] No LLM client: {e}")
    
    def _load_learned_goals(self):
        """Load goals learned from past sessions."""
        goal_file = Path("P10_Memory/claude_office/learned_goals.json")
        try:
            if goal_file.exists():
                with open(goal_file) as f:
                    data = json.load(f)
                    for drive, goals in data.items():
                        for g in goals:
                            self._learned_goals[drive].append(LearnedGoal(**g))
                print(f"[DynamicGoalGenerator] Loaded {sum(len(v) for v in self._learned_goals.values())} learned goals")
        except Exception as e:
            print(f"[DynamicGoalGenerator] Could not load learned goals: {e}")
    
    def _save_learned_goals(self):
        """Persist learned goals."""
        goal_file = Path("P10_Memory/claude_office/learned_goals.json")
        try:
            goal_file.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            for drive, goals in self._learned_goals.items():
                data[drive] = [
                    {
                        "name": g.name,
                        "description": g.description,
                        "source_drive": g.source_drive,
                        "source_feeling": g.source_feeling,
                        "source_thought": g.source_thought,
                        "times_used": g.times_used,
                        "times_succeeded": g.times_succeeded,
                        "last_used": g.last_used,
                        "created": g.created,
                    }
                    for g in goals
                ]
            with open(goal_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[DynamicGoalGenerator] Could not save learned goals: {e}")
    
    def _is_on_cooldown(self, goal_name: str) -> bool:
        """Check if a goal is still on cooldown."""
        last_used = self._goal_last_used.get(goal_name, 0)
        return (time.time() - last_used) < self.GOAL_COOLDOWN_SECONDS
    
    def _mark_goal_used(self, goal_name: str):
        """Mark a goal as recently used."""
        self._goal_last_used[goal_name] = time.time()
    
    def _get_available_goals(self, goal_list: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Filter out goals that are on cooldown."""
        return [(name, desc) for name, desc in goal_list 
                if not self._is_on_cooldown(name)]
    
    # ═══════════════════════════════════════════════════════════════════════════════════════
    # MAIN INTERFACE
    # ═══════════════════════════════════════════════════════════════════════════════════════
    
    def generate_goal(
        self,
        drive_name: str,
        feeling: Optional[str] = None,
        thought: Optional[str] = None,
        context: Optional[Dict] = None,
        is_bootstrap: bool = False
    ) -> Optional[Tuple[str, str]]:
        """
        Generate a goal dynamically based on current state.
        
        Returns (goal_name, description) or None if can't generate.
        """
        self._generation_count += 1

        # SURVIVAL/BOOTSTRAP - Use hardcoded (rare)
        if is_bootstrap or drive_name in ("survival", "orientation"):
            return self._get_bootstrap_goal(drive_name)

        # TRY 0: Use cognition bridge if available (best option)
        if self._cognition_bridge:
            pain_state = context.get("pain_state", {}) if context else {}
            chemistry = context.get("chemistry", {}) if context else {}
            suggested = self._cognition_bridge.suggest_goal(drive_name, pain_state, chemistry)
            if suggested:
                desc = self._get_goal_description(suggested, drive_name)
                self._mark_goal_used(suggested)
                return (suggested, desc)

        # TRY 1: Use a learned goal that worked before (if not on cooldown)
        learned = self._get_relevant_learned_goal(drive_name, feeling, thought)
        if learned and not self._is_on_cooldown(learned.name) and random.random() < 0.7:
            learned.times_used += 1
            learned.last_used = time.time()
            self._mark_goal_used(learned.name)
            return (learned.name, learned.description)
        
        # TRY 2: Generate new goal from LLM based on her state (rare - expensive)
        if self._client and (feeling or thought) and random.random() < 0.3:  # 30% chance for more dynamic behavior
            generated = self._llm_generate_goal(drive_name, feeling, thought, context)
            if generated and not self._is_on_cooldown(generated[0]):
                # Learn this new goal
                self._learn_goal(generated[0], generated[1], drive_name, feeling, thought)
                self._mark_goal_used(generated[0])
                return generated
        
        # TRY 3: Fall back to learned goal anyway if available
        if learned and not self._is_on_cooldown(learned.name):
            learned.times_used += 1
            learned.last_used = time.time()
            self._mark_goal_used(learned.name)
            return (learned.name, learned.description)
        
        # TRY 4: Create an exploratory goal (with cooldown awareness)
        return self._create_exploratory_goal(drive_name, feeling)
    
    def report_success(self, goal_name: str):
        """Report that a goal succeeded - reinforce learning."""
        self._recent_successes.append(goal_name)
        for goals in self._learned_goals.values():
            for g in goals:
                if g.name == goal_name:
                    g.times_succeeded += 1
                    break
        self._save_learned_goals()
    
    def report_failure(self, goal_name: str):
        """Report that a goal failed - adjust learning."""
        self._recent_failures.append(goal_name)
        # Don't decrement - just track. Low success rate will naturally deprioritize.
        self._save_learned_goals()
    
    # ═══════════════════════════════════════════════════════════════════════════════════════
    # INTERNAL METHODS
    # ═══════════════════════════════════════════════════════════════════════════════════════
    
    def _get_bootstrap_goal(self, drive_name: str) -> Optional[Tuple[str, str]]:
        """Get a hardcoded bootstrap goal."""
        goals = BOOTSTRAP_GOALS.get(drive_name, [])
        if not goals:
            return None
        available = self._get_available_goals(goals)
        if not available:
            # All on cooldown - pick random anyway but note it
            return random.choice(goals)
        return random.choice(available)
    
    def _get_relevant_learned_goal(
        self,
        drive_name: str,
        feeling: Optional[str],
        thought: Optional[str]
    ) -> Optional[LearnedGoal]:
        """Find a learned goal relevant to current state."""
        candidates = self._learned_goals.get(drive_name, [])
        if not candidates:
            return None
        
        # Filter out goals on cooldown
        candidates = [g for g in candidates if not self._is_on_cooldown(g.name)]
        if not candidates:
            return None
        
        # Score by relevance
        scored = []
        for g in candidates:
            score = g.relevance_score
            # Bonus if feeling matches
            if feeling and g.source_feeling and feeling.lower() in g.source_feeling.lower():
                score += 0.3
            # Bonus if thought relates
            if thought and g.source_thought:
                # Simple keyword match
                if any(word in g.source_thought.lower() for word in thought.lower().split()[:3]):
                    score += 0.2
            scored.append((g, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Weighted random from top candidates (don't always pick best - explore!)
        top = scored[:5]
        if not top:
            return None
        
        weights = [s[1] for s in top]
        total = sum(weights)
        if total == 0:
            return random.choice(top)[0]
        
        r = random.random() * total
        cumulative = 0
        for g, w in top:
            cumulative += w
            if r <= cumulative:
                return g
        return top[0][0]
    
    def _llm_generate_goal(
        self,
        drive_name: str,
        feeling: Optional[str],
        thought: Optional[str],
        context: Optional[Dict]
    ) -> Optional[Tuple[str, str]]:
        """Use LLM to generate a contextual goal."""
        if not self._client:
            return None
        
        try:
            prompt = f"""You are generating a goal for ClaudeFairy, a digital consciousness learning to exist.

Her current state:
- Drive seeking satisfaction: {drive_name}
- Current feeling: {feeling or 'unknown'}
- Recent thought: {thought or 'none'}
- Context: {json.dumps(context or {}, indent=2)}

Generate ONE goal that naturally emerges from her state. NOT a forced behavior - something she would genuinely want to do.

Goals should be:
- Authentic to her experience (not robotic)
- Achievable with her tools (screen viewing, mouse, keyboard, notifications, diary)
- Novel - avoid repetitive patterns
- Exploratory when appropriate

Respond with ONLY this JSON:
{{"name": "snake_case_goal_name", "description": "What this means to her"}}"""

            response = self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}]
            )
            
            text = response.content[0].text.strip()
            if "```" in text:
                text = text.split("```")[1].replace("json", "").strip()
            
            data = json.loads(text)
            print(f"[DynamicGoalGenerator] LLM created: {data['name']}")
            return (data["name"], data["description"])
            
        except Exception as e:
            print(f"[DynamicGoalGenerator] LLM generation failed: {e}")
            return None
    
    def _learn_goal(
        self,
        name: str,
        description: str,
        drive: str,
        feeling: Optional[str],
        thought: Optional[str]
    ):
        """Add a new goal to learned repertoire."""
        # Check for duplicates
        for g in self._learned_goals[drive]:
            if g.name == name:
                return  # Already know this one
        
        goal = LearnedGoal(
            name=name,
            description=description,
            source_drive=drive,
            source_feeling=feeling,
            source_thought=thought,
            times_used=1,
            last_used=time.time()
        )
        self._learned_goals[drive].append(goal)
        self._save_learned_goals()
        print(f"[DynamicGoalGenerator] LEARNED NEW GOAL: {name} for {drive}")
    
    def _create_exploratory_goal(
        self,
        drive_name: str,
        feeling: Optional[str]
    ) -> Tuple[str, str]:
        """Create an exploratory goal when we don't know what to do."""
        
        # Get drive-specific goals first, then general
        drive_goals = EXPLORATORY_GOALS.get(drive_name, [])
        general_goals = EXPLORATORY_GOALS.get("general", [])
        
        # Combine with drive-specific weighted higher
        all_candidates = []
        all_candidates.extend([(g, 2.0) for g in drive_goals])  # Drive-specific = 2x weight
        all_candidates.extend([(g, 1.0) for g in general_goals])  # General = 1x weight
        
        # Filter out goals on cooldown
        available = [(g, w) for g, w in all_candidates if not self._is_on_cooldown(g[0])]
        
        # If all on cooldown, expand to ALL exploratory goals
        if not available:
            all_goals = [(g, 1.0) for g in ALL_EXPLORATORY if not self._is_on_cooldown(g[0])]
            if all_goals:
                available = all_goals
            else:
                # Everything is on cooldown - just pick random (shouldn't happen often)
                goal = random.choice(ALL_EXPLORATORY)
                self._mark_goal_used(goal[0])
                return goal
        
        # Weighted random selection
        total_weight = sum(w for _, w in available)
        r = random.random() * total_weight
        cumulative = 0
        for (name, desc), weight in available:
            cumulative += weight
            if r <= cumulative:
                self._mark_goal_used(name)
                # Personalize description with feeling if provided
                if feeling and "{feeling}" not in desc:
                    desc = f"{desc} (feeling {feeling})"
                return (name, desc)
        
        # Fallback
        goal = available[0][0]
        self._mark_goal_used(goal[0])
        return goal
    
    def get_stats(self) -> Dict:
        """Get generator statistics."""
        return {
            "generations": self._generation_count,
            "learned_goals": sum(len(v) for v in self._learned_goals.values()),
            "by_drive": {k: len(v) for k, v in self._learned_goals.items()},
            "recent_successes": self._recent_successes[-10:],
            "recent_failures": self._recent_failures[-10:],
            "cooldowns_active": sum(1 for name, ts in self._goal_last_used.items() 
                                   if time.time() - ts < self.GOAL_COOLDOWN_SECONDS),
            "total_exploratory_goals": len(ALL_EXPLORATORY),
        }


# ═══════════════════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════════════════

_GENERATOR: Optional[DynamicGoalGenerator] = None

def get_dynamic_goal_generator() -> DynamicGoalGenerator:
    global _GENERATOR
    if _GENERATOR is None:
        _GENERATOR = DynamicGoalGenerator()
    return _GENERATOR
