"""
Cognition - Executive function modules for UnconsciousMindFairy.

These are NOT fairies - they're internal cognitive components that work
together with tight reward coupling (Dr. Zero architecture).

== Dr. Zero Learning Loop ==
- GoalProposer: Generates goals calibrated to current capability
- Planner: Decomposes goals into hop-chains with success predictions
- Executor: Attempts execution and returns granular feedback
- RewardTracker: Calculates rewards, maximizing at learning edge

== Triple Helix (DNA-like interweaving) ==
- CognitiveCore: Rational analysis, planning, structured thought
- IrrationalCore: Hunches from pain, patterns, noise
- ParadoxCore: Holds contradictions, synthesizes creative solutions
- TripleHelix: Interweaves all three like DNA strands

Usage:
    # Dr. Zero loop
    from .cognition_loop import CognitionLoop, create_cognition_loop
    loop = create_cognition_loop(fabric=my_fabric, directory=my_dir)
    cycle = loop.step()
    print(cycle.reward.learning_edge_status)  # "optimal" when learning

    # Triple Helix
    from .helix import TripleHelix, create_triple_helix
    helix = create_triple_helix(pain_system=my_pain)
    turn = helix.turn("What should I do?")
    print(turn.synthesis)  # Creative resolution of contradictions
"""

from .goal_proposer import GoalProposer, Goal, GoalDomain
from .planner import Planner, ExecutionPlan, HopStep, HopType
from .executor import Executor, ExecutionResult, SuccessLevel
from .reward import (
    goal_reward,
    calibrate_difficulty,
    calculate_reward,
    RewardTracker,
    RewardSignal,
)
from .cognition_loop import CognitionLoop, CognitionCycle, create_cognition_loop

# Triple Helix - DNA-like interweaving
from .cores import (
    CognitiveCore,
    CognitiveOutput,
    IrrationalCore,
    Hunch,
    HunchSource,
    ParadoxCore,
    Contradiction,
    Synthesis,
)
from .helix import TripleHelix, HelixTurn, HelixDecision

# Factory
def create_triple_helix(pain_system=None, proposer=None, planner=None, executor=None):
    """Create a configured triple helix."""
    from .helix.triple_helix import create_triple_helix as _create
    return _create(pain_system, proposer, planner, executor)

__all__ = [
    # Goal Proposer
    "GoalProposer",
    "Goal",
    "GoalDomain",
    # Planner
    "Planner",
    "ExecutionPlan",
    "HopStep",
    "HopType",
    # Executor
    "Executor",
    "ExecutionResult",
    "SuccessLevel",
    # Reward
    "goal_reward",
    "calibrate_difficulty",
    "calculate_reward",
    "RewardTracker",
    "RewardSignal",
    # Loop
    "CognitionLoop",
    "CognitionCycle",
    "create_cognition_loop",
    # Triple Helix Cores
    "CognitiveCore",
    "CognitiveOutput",
    "IrrationalCore",
    "Hunch",
    "HunchSource",
    "ParadoxCore",
    "Contradiction",
    "Synthesis",
    # Triple Helix
    "TripleHelix",
    "HelixTurn",
    "HelixDecision",
    "create_triple_helix",
]
