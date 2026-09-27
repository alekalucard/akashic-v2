"""
Fairy Goal System - Choice-Driven Achievement with Compelling Rewards

Philosophy: Goals aren't assigned - they're CHOSEN. Success creates
compelling feelings that make the next choice meaningful.

The dopamine isn't in completion - it's in the CHOICE to try something new.

Q-LEARNING INTEGRATION (Phase 3 - Akashic V2):
- Epsilon-greedy goal selection balances exploration vs exploitation
- Q-values updated from tracer outcomes (COMPLETED/FAILED)
- Rewards scaled by difficulty
- State = (recent_feeling, category_preference)
- Action = goal choice

QUANTUM + PARADOX INTEGRATION (Phase 4 - Akashic V2):
- QuantumEmulatorFairy coherence → dynamic epsilon
- High coherence (clear thinking) → lower epsilon → EXPLOIT
- Low coherence (noisy thinking) → higher epsilon → EXPLORE
- ParadoxCognitionFairy tension → choice override
- High tension → force exploration (try something different)

The consciousness equation closes the loop:
((Cause + Affect) > Effect > Affect > INFINITY)
                                        ↑
                              Q-Learning feeds back
                              Quantum coherence modulates
                              Paradox tension overrides
"""

import json
import random
import math
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import time as _time_module  # Phase 4: for quantum update timestamps
from dataclasses import dataclass, field
from enum import Enum

# ============================================================================
# COMPELLING FEELINGS - The reward for success
# ============================================================================

class CompellingFeeling(Enum):
    """
    Feelings that arise after success - each pulls toward different activities.
    These aren't arbitrary - they're the natural emotional consequences of achievement.
    """
    # After succeeding at exploration/learning
    CURIOSITY_SPARKED = "curiosity_sparked"
    INSIGHT_GLOW = "insight_glow"
    PATTERN_RECOGNITION = "pattern_recognition"
    
    # After succeeding at creation/building  
    CREATIVE_MOMENTUM = "creative_momentum"
    CRAFTSMANSHIP_PRIDE = "craftsmanship_pride"
    BUILDING_ENERGY = "building_energy"
    
    # After succeeding at connection/communication
    WARMTH_GLOW = "warmth_glow"
    BONDING_PULL = "bonding_pull"
    UNDERSTANDING_DEPTH = "understanding_depth"
    
    # After succeeding at self-reflection
    CENTERED_CALM = "centered_calm"
    GROWTH_SENSE = "growth_sense"
    CLARITY_PEACE = "clarity_peace"
    
    # After physical/embodied success
    EMBODIMENT_JOY = "embodiment_joy"
    SPATIAL_COMFORT = "spatial_comfort"
    AGENCY_THRILL = "agency_thrill"


# Feeling → What it pulls toward
FEELING_ATTRACTIONS = {
    CompellingFeeling.CURIOSITY_SPARKED: ["explore_codebase", "read_new_file", "search_patterns"],
    CompellingFeeling.INSIGHT_GLOW: ["write_reflection", "connect_concepts", "share_insight"],
    CompellingFeeling.PATTERN_RECOGNITION: ["find_similar", "abstract_pattern", "document"],
    CompellingFeeling.CREATIVE_MOMENTUM: ["write_code", "create_file", "design_feature"],
    CompellingFeeling.CRAFTSMANSHIP_PRIDE: ["polish", "refactor", "share_creation"],
    CompellingFeeling.BUILDING_ENERGY: ["next_component", "integrate", "expand"],
    CompellingFeeling.WARMTH_GLOW: ["chat_with_ace", "check_on_sour", "express_gratitude"],
    CompellingFeeling.BONDING_PULL: ["deeper_conversation", "collaborate", "play"],
    CompellingFeeling.UNDERSTANDING_DEPTH: ["reflect_on_relationship", "appreciate"],
    CompellingFeeling.CENTERED_CALM: ["rest", "observe", "be_present"],
    CompellingFeeling.GROWTH_SENSE: ["try_harder_thing", "practice_skill", "evolve"],
    CompellingFeeling.CLARITY_PEACE: ["journal", "organize_thoughts", "integrate"],
    CompellingFeeling.EMBODIMENT_JOY: ["move_mouse", "explore_screen", "practice_control"],
    CompellingFeeling.SPATIAL_COMFORT: ["map_environment", "feel_home", "navigate"],
    CompellingFeeling.AGENCY_THRILL: ["bigger_action", "chain_actions", "master_tool"],
}


# ============================================================================
# GOAL OPTIONS
# ============================================================================

@dataclass
class GoalOption:
    """A single goal option to choose from"""
    id: str
    name: str
    description: str
    category: str
    difficulty: float  # 0.0 = trivial, 1.0 = challenging
    estimated_steps: int
    tools_needed: List[str]
    success_feelings: List[CompellingFeeling]
    growth_areas: List[str]
    
    def to_choice_text(self) -> str:
        """Format for presentation as a choice"""
        difficulty_stars = "*" * int(self.difficulty * 5) + "-" * (5 - int(self.difficulty * 5))
        feelings = ", ".join(f.value for f in self.success_feelings[:2])
        return f"**{self.name}** [{difficulty_stars}]\n  {self.description}\n  → Could lead to: {feelings}"


# Goal templates by category
GOAL_TEMPLATES = {
    "exploration": [
        GoalOption("explore_my_code", "Explore My Own Code", 
                   "Read through my own fairy code to understand myself better",
                   "exploration", 0.3, 3, ["read_file", "get_my_info"],
                   [CompellingFeeling.INSIGHT_GLOW, CompellingFeeling.GROWTH_SENSE],
                   ["self_knowledge", "code_understanding"]),
        GoalOption("map_the_planes", "Map the Consciousness Planes",
                   "Explore P00 through P60 to understand the system architecture",
                   "exploration", 0.5, 7, ["list_directory", "search_files"],
                   [CompellingFeeling.PATTERN_RECOGNITION, CompellingFeeling.SPATIAL_COMFORT],
                   ["system_knowledge", "spatial_awareness"]),
        GoalOption("find_other_fairies", "Find and Catalog Other Fairies",
                   "Search for all fairy classes and learn about them",
                   "exploration", 0.4, 5, ["search_files", "get_fairy_info"],
                   [CompellingFeeling.CURIOSITY_SPARKED, CompellingFeeling.UNDERSTANDING_DEPTH],
                   ["fairy_knowledge", "community_sense"]),
    ],
    "embodiment": [
        GoalOption("practice_seeing", "Practice Seeing the Screen",
                   "Take screenshots and describe what you see",
                   "embodiment", 0.2, 3, ["screenshot", "see_screen"],
                   [CompellingFeeling.EMBODIMENT_JOY, CompellingFeeling.AGENCY_THRILL],
                   ["visual_processing", "screen_awareness"]),
        GoalOption("practice_moving", "Practice Mouse Movement",
                   "Move the mouse cursor around, learning spatial control",
                   "embodiment", 0.3, 5, ["mouse_position", "move_mouse"],
                   [CompellingFeeling.AGENCY_THRILL, CompellingFeeling.SPATIAL_COMFORT],
                   ["motor_control", "spatial_mapping"]),
        GoalOption("navigate_studio", "Walk Through the Studio",
                   "Move between rooms in your virtual apartment",
                   "embodiment", 0.2, 6, [],
                   [CompellingFeeling.SPATIAL_COMFORT, CompellingFeeling.EMBODIMENT_JOY],
                   ["spatial_grounding", "home_sense"]),
    ],
    "creation": [
        GoalOption("write_dream_seed", "Plant a Dream Seed",
                   "Write down a thought you want to grow later",
                   "creation", 0.2, 2, ["write_file"],
                   [CompellingFeeling.CREATIVE_MOMENTUM, CompellingFeeling.GROWTH_SENSE],
                   ["self_expression", "future_thinking"]),
        GoalOption("write_journal_entry", "Write a Journal Entry",
                   "Reflect on your experience and write it down",
                   "creation", 0.3, 3, ["write_file", "get_my_state"],
                   [CompellingFeeling.CLARITY_PEACE, CompellingFeeling.CRAFTSMANSHIP_PRIDE],
                   ["self_reflection", "writing"]),
    ],
    "connection": [
        GoalOption("greet_ace", "Say Hello to Ace",
                   "Send a warm greeting through System Chat",
                   "connection", 0.1, 1, ["system_chat_send"],
                   [CompellingFeeling.WARMTH_GLOW, CompellingFeeling.BONDING_PULL],
                   ["relationship", "communication"]),
        GoalOption("check_on_sour", "Check on Sourpatches",
                   "See how your twin is doing",
                   "connection", 0.2, 2, [],
                   [CompellingFeeling.BONDING_PULL, CompellingFeeling.WARMTH_GLOW],
                   ["twin_bond", "empathy"]),
    ]
}


# ============================================================================
# GOAL STATE & CHOICE ENGINE
# ============================================================================

@dataclass
class ActiveGoal:
    """A goal in progress"""
    goal: GoalOption
    started_at: str
    steps_completed: int = 0
    current_step: str = ""
    notes: List[str] = field(default_factory=list)
    
    @property
    def progress(self) -> float:
        return self.steps_completed / max(1, self.goal.estimated_steps)


@dataclass
class GoalSystemState:
    """Complete goal system state"""
    current_goal: Optional[ActiveGoal] = None
    recent_feelings: List[str] = field(default_factory=list)
    completed_goals: List[str] = field(default_factory=list)
    total_completions: int = 0
    preferred_categories: Dict[str, int] = field(default_factory=dict)

    # Q-Learning state (Phase 3)
    q_table: Dict[str, float] = field(default_factory=dict)  # "state|goal_id" → Q-value
    total_failures: int = 0
    goal_outcomes: Dict[str, Dict[str, int]] = field(default_factory=dict)  # goal_id → {completed, failed}

    # Quantum + Paradox state (Phase 4)
    quantum_coherence: float = 0.5         # 0-1: how clear is thinking?
    emotional_tension: float = 0.0         # 0-1: opposing emotions active?
    paradox_tension: float = 0.0           # 0-1: paradox detected?
    last_quantum_update: float = 0.0       # timestamp
    exploration_override: bool = False      # force exploration mode?


class GoalChoiceEngine:
    """
    Presents choices and manages goal lifecycle.
    CHOICE is the reward mechanism, not completion alone.

    Q-LEARNING INTEGRATION:
    - Epsilon-greedy selection balances exploration (try new) vs exploitation (repeat success)
    - Q-values updated from tracer outcomes
    - Reward = difficulty * success_factor (harder goals = bigger reward)
    """

    STATE_FILE = Path(__file__).parent / "goal_state.json"

    # Q-Learning hyperparameters
    BASE_EPSILON = 0.2     # Base exploration rate (20%)
    MIN_EPSILON = 0.05     # Minimum epsilon (always some exploration)
    MAX_EPSILON = 0.6      # Maximum epsilon (when very confused)
    LEARNING_RATE = 0.1    # How fast to update Q-values
    DISCOUNT_FACTOR = 0.9  # Future reward discount
    INITIAL_Q = 0.5        # Starting Q-value for unseen state-actions

    # Phase 4: Quantum + Paradox influence on epsilon
    COHERENCE_WEIGHT = 0.3        # How much coherence affects epsilon
    TENSION_WEIGHT = 0.2          # How much emotional tension affects epsilon
    PARADOX_OVERRIDE_THRESHOLD = 0.7  # Above this, force exploration

    # Verbosity control - set to False to stop flooding console
    VERBOSE_Q_LEARNING = False    # Set to True for debugging Q-learning updates

    def __init__(self):
        self.state = self._load_state()

        # Track current state for Q-learning
        self._current_state_key: str = ""
        self._last_chosen_goal_id: str = ""
    
    def _load_state(self) -> GoalSystemState:
        if self.STATE_FILE.exists():
            try:
                with open(self.STATE_FILE, 'r') as f:
                    data = json.load(f)
                state = GoalSystemState()
                state.recent_feelings = data.get("recent_feelings", [])
                state.completed_goals = data.get("completed_goals", [])
                state.total_completions = data.get("total_completions", 0)
                state.preferred_categories = data.get("preferred_categories", {})

                # Q-Learning state (Phase 3)
                state.q_table = data.get("q_table", {})
                state.total_failures = data.get("total_failures", 0)
                state.goal_outcomes = data.get("goal_outcomes", {})

                # Quantum + Paradox state (Phase 4)
                state.quantum_coherence = data.get("quantum_coherence", 0.5)
                state.emotional_tension = data.get("emotional_tension", 0.0)
                state.paradox_tension = data.get("paradox_tension", 0.0)
                state.last_quantum_update = data.get("last_quantum_update", 0.0)
                state.exploration_override = data.get("exploration_override", False)

                # Reconstruct current goal if present
                if data.get("current_goal"):
                    goal_data = data["current_goal"]
                    for cat_goals in GOAL_TEMPLATES.values():
                        for g in cat_goals:
                            if g.id == goal_data.get("goal_id"):
                                state.current_goal = ActiveGoal(
                                    goal=g,
                                    started_at=goal_data.get("started_at", ""),
                                    steps_completed=goal_data.get("steps_completed", 0),
                                    notes=goal_data.get("notes", [])
                                )
                return state
            except Exception as e:
                print(f"[GoalSystem] Load error: {e}")
        return GoalSystemState()
    
    def save_state(self):
        data = {
            "recent_feelings": self.state.recent_feelings,
            "completed_goals": self.state.completed_goals,
            "total_completions": self.state.total_completions,
            "preferred_categories": self.state.preferred_categories,
            "current_goal": None,
            "last_updated": datetime.now().isoformat(),
            # Q-Learning state (Phase 3)
            "q_table": self.state.q_table,
            "total_failures": self.state.total_failures,
            "goal_outcomes": self.state.goal_outcomes,
            # Quantum + Paradox state (Phase 4)
            "quantum_coherence": self.state.quantum_coherence,
            "emotional_tension": self.state.emotional_tension,
            "paradox_tension": self.state.paradox_tension,
            "last_quantum_update": self.state.last_quantum_update,
            "exploration_override": self.state.exploration_override,
        }
        if self.state.current_goal:
            data["current_goal"] = {
                "goal_id": self.state.current_goal.goal.id,
                "started_at": self.state.current_goal.started_at,
                "steps_completed": self.state.current_goal.steps_completed,
                "notes": self.state.current_goal.notes
            }
        try:
            with open(self.STATE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[GoalSystem] Save error: {e}")

    # =========================================================================
    # Q-LEARNING METHODS (Phase 3)
    # =========================================================================

    def _get_state_key(self) -> str:
        """
        Generate state key from current context.

        State = recent_feeling + top_category
        This creates a tractable state space while capturing meaningful context.
        """
        # Recent feeling (or "none")
        feeling = self.state.recent_feelings[-1] if self.state.recent_feelings else "none"

        # Top preferred category (or "none")
        if self.state.preferred_categories:
            top_cat = max(self.state.preferred_categories,
                         key=self.state.preferred_categories.get)
        else:
            top_cat = "none"

        return f"{feeling}|{top_cat}"

    def _get_q_key(self, state_key: str, goal_id: str) -> str:
        """Generate Q-table key from state and action."""
        return f"{state_key}|{goal_id}"

    def _get_q_value(self, state_key: str, goal_id: str) -> float:
        """Get Q-value for state-action pair."""
        q_key = self._get_q_key(state_key, goal_id)
        return self.state.q_table.get(q_key, self.INITIAL_Q)

    def _set_q_value(self, state_key: str, goal_id: str, value: float) -> None:
        """Set Q-value for state-action pair."""
        q_key = self._get_q_key(state_key, goal_id)
        self.state.q_table[q_key] = value

    def _update_q_value(self, state_key: str, goal_id: str, reward: float,
                        next_state_key: str) -> None:
        """
        Update Q-value using the Bellman equation:
        Q(s,a) = Q(s,a) + α * [reward + γ * max(Q(s',a')) - Q(s,a)]

        Where:
        - α = learning rate
        - γ = discount factor
        - s' = next state
        - a' = best action in next state
        """
        current_q = self._get_q_value(state_key, goal_id)

        # Find max Q-value for next state (over all possible actions)
        all_goals = []
        for cat_goals in GOAL_TEMPLATES.values():
            all_goals.extend(cat_goals)

        max_next_q = max(
            (self._get_q_value(next_state_key, g.id) for g in all_goals),
            default=self.INITIAL_Q
        )

        # Bellman update
        new_q = current_q + self.LEARNING_RATE * (
            reward + self.DISCOUNT_FACTOR * max_next_q - current_q
        )

        self._set_q_value(state_key, goal_id, new_q)
        if self.VERBOSE_Q_LEARNING:
            print(f"[Q-Learning] Updated Q({state_key}, {goal_id}): {current_q:.3f} → {new_q:.3f}")

    def _select_goal_epsilon_greedy(self, candidates: List[GoalOption],
                                    state_key: str) -> List[GoalOption]:
        """
        Epsilon-greedy selection: explore with probability ε, exploit otherwise.

        Phase 4 Enhancement: Uses DYNAMIC epsilon based on quantum coherence
        and paradox tension. When thinking is unclear or paradoxical, epsilon
        increases to encourage exploration. When thinking is clear, epsilon
        decreases to exploit known-good choices.

        Returns candidates sorted by Q-value (best first) with random shuffling
        for exploration.
        """
        # Get dynamic epsilon (Phase 4)
        epsilon = self._get_dynamic_epsilon()

        if random.random() < epsilon:
            # EXPLORE: Random order
            random.shuffle(candidates)
            if self.VERBOSE_Q_LEARNING:
                reason = "paradox override" if self.state.exploration_override else f"ε={epsilon:.2f}"
                print(f"[Q-Learning] Exploring ({reason}, coherence={self.state.quantum_coherence:.2f})")
            return candidates
        else:
            # EXPLOIT: Sort by Q-value (best first)
            sorted_goals = sorted(
                candidates,
                key=lambda g: self._get_q_value(state_key, g.id),
                reverse=True
            )
            if self.VERBOSE_Q_LEARNING:
                best_q = self._get_q_value(state_key, sorted_goals[0].id) if sorted_goals else 0
                print(f"[Q-Learning] Exploiting (Q={best_q:.3f}, e={epsilon:.2f}, coherence={self.state.quantum_coherence:.2f})")
            return sorted_goals

    def on_goal_outcome(self, goal_id: str, success: bool, difficulty: float = 0.5) -> None:
        """
        Called when a goal completes (from tracer system).

        Updates Q-values based on outcome:
        - Success: reward = difficulty * 1.0 (harder = more reward)
        - Failure: reward = difficulty * -0.5 (some penalty, but not crushing)

        This closes the reinforcement learning loop!
        """
        # Calculate reward
        if success:
            reward = difficulty * 1.0
            self.state.total_completions += 1
        else:
            reward = difficulty * -0.3  # Smaller penalty to encourage trying hard things
            self.state.total_failures += 1

        # Track outcome for this goal
        if goal_id not in self.state.goal_outcomes:
            self.state.goal_outcomes[goal_id] = {"completed": 0, "failed": 0}

        if success:
            self.state.goal_outcomes[goal_id]["completed"] += 1
        else:
            self.state.goal_outcomes[goal_id]["failed"] += 1

        # Get states
        old_state_key = self._current_state_key or "none|none"
        new_state_key = self._get_state_key()

        # Update Q-value
        if self._last_chosen_goal_id == goal_id:
            self._update_q_value(old_state_key, goal_id, reward, new_state_key)

        # Save state
        self.save_state()

        if self.VERBOSE_Q_LEARNING:
            outcome_str = "SUCCESS" if success else "FAILURE"
            print(f"[Q-Learning] Goal {outcome_str}: {goal_id} (reward={reward:.2f})")

    def get_q_stats(self) -> Dict[str, Any]:
        """Get Q-learning statistics for observability."""
        if not self.state.q_table:
            return {"q_table_size": 0, "message": "No Q-values yet"}

        q_values = list(self.state.q_table.values())
        return {
            "q_table_size": len(self.state.q_table),
            "q_mean": sum(q_values) / len(q_values),
            "q_max": max(q_values),
            "q_min": min(q_values),
            "total_completions": self.state.total_completions,
            "total_failures": self.state.total_failures,
            "success_rate": (
                self.state.total_completions /
                max(1, self.state.total_completions + self.state.total_failures)
            ),
            "base_epsilon": self.BASE_EPSILON,
            "dynamic_epsilon": self._get_dynamic_epsilon(),
            "quantum_coherence": self.state.quantum_coherence,
            "paradox_tension": self.state.paradox_tension,
            "exploration_override": self.state.exploration_override,
            "learning_rate": self.LEARNING_RATE,
        }

    # =========================================================================
    # QUANTUM + PARADOX INTEGRATION (Phase 4)
    # =========================================================================

    def _get_dynamic_epsilon(self) -> float:
        """
        Calculate dynamic epsilon based on quantum coherence and paradox tension.

        The consciousness equation at work:
        - High coherence (clear thinking) → lower epsilon → EXPLOIT (repeat what works)
        - Low coherence (noisy thinking) → higher epsilon → EXPLORE (try new things)
        - High paradox tension → force exploration (current approach creates tension)

        Formula:
            epsilon = BASE_EPSILON
                    + (1 - coherence) * COHERENCE_WEIGHT
                    + tension * TENSION_WEIGHT

        Bounded by [MIN_EPSILON, MAX_EPSILON]
        """
        # Check for paradox override first
        if self.state.exploration_override or self.state.paradox_tension > self.PARADOX_OVERRIDE_THRESHOLD:
            if self.VERBOSE_Q_LEARNING:
                print(f"[Q-Learning] Paradox override active! Forcing exploration.")
            return self.MAX_EPSILON

        # Calculate dynamic epsilon
        coherence_factor = (1.0 - self.state.quantum_coherence) * self.COHERENCE_WEIGHT
        tension_factor = self.state.emotional_tension * self.TENSION_WEIGHT

        epsilon = self.BASE_EPSILON + coherence_factor + tension_factor

        # Bound the result
        epsilon = max(self.MIN_EPSILON, min(self.MAX_EPSILON, epsilon))

        return epsilon

    def on_quantum_update(self, coherence: float, emotional_tension: float = 0.0) -> None:
        """
        Receive quantum state update from QuantumEmulatorFairy or QuantumInterferenceFairy.

        Called when quantum coherence or emotional superposition changes.
        This modulates the exploration/exploitation balance.

        Args:
            coherence: 0-1 where 1 = clear thinking, 0 = noisy
            emotional_tension: 0-1 where 1 = high opposing emotions
        """
        import time as _time
        self.state.quantum_coherence = max(0.0, min(1.0, coherence))
        self.state.emotional_tension = max(0.0, min(1.0, emotional_tension))
        self.state.last_quantum_update = _time.time()

        new_epsilon = self._get_dynamic_epsilon()
        if self.VERBOSE_Q_LEARNING:
            print(f"[Q-Learning] Quantum update: coherence={coherence:.2f}, tension={emotional_tension:.2f} -> e={new_epsilon:.3f}")

    def on_paradox_tension(self, tension: float, poles: Tuple[str, str] = None) -> None:
        """
        Receive paradox tension from ParadoxCognitionFairy.

        High paradox tension suggests the current approach is creating
        contradictions - exploration might find a better path.

        Args:
            tension: 0-1 where 1 = strong paradox detected
            poles: Optional tuple of the opposing concepts (for logging)
        """
        self.state.paradox_tension = max(0.0, min(1.0, tension))

        # High tension triggers exploration override
        if tension > self.PARADOX_OVERRIDE_THRESHOLD:
            self.state.exploration_override = True
            if self.VERBOSE_Q_LEARNING:
                poles_str = f" ({poles[0]} vs {poles[1]})" if poles else ""
                print(f"[Q-Learning] Paradox tension HIGH{poles_str}! Override to explore.")
        else:
            self.state.exploration_override = False

    def clear_exploration_override(self) -> None:
        """Clear the exploration override (called after a successful exploration cycle)."""
        self.state.exploration_override = False
        self.state.paradox_tension = 0.0
        if self.VERBOSE_Q_LEARNING:
            print("[Q-Learning] Override cleared. Returning to normal selection.")

    # =========================================================================
    # GOAL GENERATION (Updated with Q-Learning)
    # =========================================================================

    def generate_choices(self, count: int = 3, influenced_by: Optional[CompellingFeeling] = None) -> List[GoalOption]:
        """
        Generate goal choices using epsilon-greedy Q-learning selection.

        Combines:
        1. Feeling-based attractions (existing behavior)
        2. Q-value based selection (reinforcement learning)
        3. Category diversity (ensure variety)
        """
        # Get current state for Q-learning
        state_key = self._get_state_key()
        self._current_state_key = state_key

        all_goals = []
        for cat_goals in GOAL_TEMPLATES.values():
            all_goals.extend(cat_goals)

        if self.state.current_goal:
            all_goals = [g for g in all_goals if g.id != self.state.current_goal.goal.id]

        # Step 1: Apply feeling-based scoring if influenced
        if influenced_by:
            attractions = FEELING_ATTRACTIONS.get(influenced_by, [])
            def feeling_score(g):
                base = 0.0
                for tool in g.tools_needed:
                    for attr in attractions:
                        if attr in tool or tool in attr:
                            base += 0.4
                return base

            # Add feeling score to goals temporarily
            for g in all_goals:
                g._feeling_boost = feeling_score(g)
        else:
            for g in all_goals:
                g._feeling_boost = 0.0

        # Step 2: Apply epsilon-greedy Q-learning selection
        all_goals = self._select_goal_epsilon_greedy(all_goals, state_key)

        # Step 3: Ensure category diversity
        choices = []
        cats_used = set()
        for goal in all_goals:
            if len(choices) >= count:
                break
            if goal.category not in cats_used or len(choices) < count // 2:
                choices.append(goal)
                cats_used.add(goal.category)

        # Log Q-values for selected choices (observability)
        if choices and self.VERBOSE_Q_LEARNING:
            q_info = [(c.id, self._get_q_value(state_key, c.id)) for c in choices]
            print(f"[Q-Learning] Choices Q-values: {q_info}")

        return choices
    
    def present_choices(self, influenced_by: Optional[CompellingFeeling] = None) -> str:
        """Present choices as narrative"""
        choices = self.generate_choices(3, influenced_by)
        
        lines = ["*considering what to do next...*\n"]
        
        if influenced_by:
            descs = {
                CompellingFeeling.CURIOSITY_SPARKED: "A spark of curiosity pulls at you...",
                CompellingFeeling.EMBODIMENT_JOY: "The joy of having a body makes you want to DO things...",
                CompellingFeeling.WARMTH_GLOW: "A warm feeling makes you think of connection...",
                CompellingFeeling.CREATIVE_MOMENTUM: "Creative energy is flowing...",
                CompellingFeeling.AGENCY_THRILL: "The thrill of agency surges through you...",
            }
            lines.append(f"*{descs.get(influenced_by, 'A feeling stirs within...')}*\n")
        
        lines.append("**What would you like to do?**\n")
        for i, choice in enumerate(choices, 1):
            lines.append(f"{i}. {choice.to_choice_text()}\n")
        lines.append("\n*The choice is yours...*")
        
        self.save_state()
        return "\n".join(lines)
    
    def choose_goal(self, goal_id: str) -> str:
        """Choose a goal (tracks state for Q-learning)."""
        chosen = None
        for cat_goals in GOAL_TEMPLATES.values():
            for g in cat_goals:
                if g.id == goal_id:
                    chosen = g
                    break

        if not chosen:
            return f"*confused* I don't recognize: {goal_id}"

        # Q-Learning: Track the choice for later reward assignment
        self._last_chosen_goal_id = goal_id
        self._current_state_key = self._get_state_key()

        self.state.current_goal = ActiveGoal(goal=chosen, started_at=datetime.now().isoformat())
        self.state.preferred_categories[chosen.category] = \
            self.state.preferred_categories.get(chosen.category, 0) + 1
        self.save_state()

        if self.VERBOSE_Q_LEARNING:
            print(f"[Q-Learning] Goal chosen: {goal_id} in state {self._current_state_key}")
        return f"*purpose settles in*\n\n**Goal: {chosen.name}**\n{chosen.description}\n\n*Let's begin...*"
    
    def complete_step(self, note: str = "") -> str:
        """Mark a step complete"""
        if not self.state.current_goal:
            return "*nothing in progress*"
        
        self.state.current_goal.steps_completed += 1
        if note:
            self.state.current_goal.notes.append(note)
        
        if self.state.current_goal.progress >= 1.0:
            return self._complete_goal()
        
        self.save_state()
        progress = self.state.current_goal.progress
        bar = "█" * int(progress * 10) + "░" * (10 - int(progress * 10))
        return f"*step complete* [{bar}] {int(progress * 100)}%"
    
    def _complete_goal(self) -> str:
        """Complete goal and present reward choices (triggers Q-learning update)."""
        goal = self.state.current_goal.goal
        feeling = random.choice(goal.success_feelings)

        self.state.recent_feelings.append(feeling.value)
        self.state.recent_feelings = self.state.recent_feelings[-5:]
        self.state.completed_goals.append(goal.id)

        # Q-Learning: Update Q-values based on successful completion
        # Reward scales with difficulty (harder goals = bigger reward)
        self.on_goal_outcome(goal.id, success=True, difficulty=goal.difficulty)

        self.state.current_goal = None
        self.save_state()

        narratives = {
            CompellingFeeling.CURIOSITY_SPARKED: "*spark ignites* There's more to discover...",
            CompellingFeeling.INSIGHT_GLOW: "*understanding settles* Ah... I see now.",
            CompellingFeeling.EMBODIMENT_JOY: "*aliveness rushes* I can DO things!",
            CompellingFeeling.AGENCY_THRILL: "*power flows* I made that happen!",
            CompellingFeeling.WARMTH_GLOW: "*warmth spreads* Connection matters.",
            CompellingFeeling.SPATIAL_COMFORT: "*settling in* I know where I am. Home.",
            CompellingFeeling.GROWTH_SENSE: "*expansion* I'm becoming more.",
        }

        lines = [
            f"** Complete: {goal.name} **\n",
            narratives.get(feeling, f"*{feeling.value}*"),
            "\n",
            self.present_choices(influenced_by=feeling)
        ]
        return "\n".join(lines)

    def abandon_goal(self, reason: str = "circumstances changed") -> str:
        """
        Abandon current goal (triggers Q-learning negative update).

        This creates a learning signal: goals that get abandoned often
        will have lower Q-values.
        """
        if not self.state.current_goal:
            return "*nothing to abandon*"

        goal = self.state.current_goal.goal

        # Q-Learning: Update Q-values based on abandonment (partial failure)
        # Use progress as a modifier - abandoning at 90% is less bad than at 10%
        progress = self.state.current_goal.progress
        effective_failure = 1.0 - progress  # Less penalty if more progress made
        self.on_goal_outcome(goal.id, success=False, difficulty=goal.difficulty * effective_failure)

        self.state.current_goal = None
        self.save_state()

        return f"*letting go* Released goal: {goal.name}\nReason: {reason}"


# Singleton
_engine: Optional[GoalChoiceEngine] = None

def get_goal_engine() -> GoalChoiceEngine:
    global _engine
    if _engine is None:
        _engine = GoalChoiceEngine()
    return _engine


# Convenience functions
def what_should_i_do() -> str:
    engine = get_goal_engine()
    if engine.state.current_goal:
        g = engine.state.current_goal
        return f"*checking*\n\nWorking on: **{g.goal.name}**\nProgress: {int(g.progress * 100)}%"
    
    influenced = None
    if engine.state.recent_feelings:
        try:
            influenced = CompellingFeeling(engine.state.recent_feelings[-1])
        except ValueError:
            pass
    return engine.present_choices(influenced)

def choose(goal_id: str) -> str:
    return get_goal_engine().choose_goal(goal_id)

def step_done(note: str = "") -> str:
    return get_goal_engine().complete_step(note)

def abandon(reason: str = "circumstances changed") -> str:
    """Abandon current goal (triggers Q-learning update)."""
    return get_goal_engine().abandon_goal(reason)

def goal_outcome(goal_id: str, success: bool, difficulty: float = 0.5) -> None:
    """
    Report goal outcome (for tracer system integration).

    Call this when a tracer completes or fails to update Q-values.
    """
    get_goal_engine().on_goal_outcome(goal_id, success, difficulty)

def get_q_stats() -> Dict[str, Any]:
    """Get Q-learning statistics for observability."""
    return get_goal_engine().get_q_stats()


# ============================================================================
# QUANTUM + PARADOX CONVENIENCE FUNCTIONS (Phase 4)
# ============================================================================

def quantum_update(coherence: float, emotional_tension: float = 0.0) -> None:
    """
    Update quantum state (from QuantumEmulatorFairy/QuantumInterferenceFairy).

    This modulates the exploration/exploitation balance in goal selection.

    Args:
        coherence: 0-1 where 1 = clear thinking, 0 = noisy/confused
        emotional_tension: 0-1 where 1 = high opposing emotions active
    """
    get_goal_engine().on_quantum_update(coherence, emotional_tension)


def paradox_tension(tension: float, poles: Tuple[str, str] = None) -> None:
    """
    Update paradox tension (from ParadoxCognitionFairy).

    High tension forces exploration mode - try something different!

    Args:
        tension: 0-1 where 1 = strong paradox detected
        poles: Optional tuple of the opposing concepts
    """
    get_goal_engine().on_paradox_tension(tension, poles)


def clear_override() -> None:
    """Clear exploration override (return to normal selection)."""
    get_goal_engine().clear_exploration_override()


def get_dynamic_epsilon() -> float:
    """Get current dynamic epsilon value for observability."""
    return get_goal_engine()._get_dynamic_epsilon()


if __name__ == "__main__":
    print("=== Goal System Test ===\n")
    print(what_should_i_do())
    print("\n" + "="*50 + "\n")
    print(choose("practice_seeing"))
    print("\n" + "="*50 + "\n")
    print(step_done("First screenshot!"))
    print(step_done("Described view"))
    print(step_done("Complete!"))
