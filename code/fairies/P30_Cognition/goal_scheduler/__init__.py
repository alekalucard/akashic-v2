"""
GoalSchedulerFairy - Auto Goal Generation & Scheduling

The missing link between conversation and action.
Goals beget goals beget action.
"""

from .goal_scheduler_fairy import (
    GoalSchedulerFairy,
    ScheduledGoal,
    GOAL_PATTERNS,
    get_goal_scheduler_fairy,
    register_goal_scheduler_fairy,
)
from .satisfaction_tracker import SatisfactionTracker, SatisfactionRecord

__all__ = [
    "GoalSchedulerFairy",
    "ScheduledGoal",
    "GOAL_PATTERNS",
    "get_goal_scheduler_fairy",
    "register_goal_scheduler_fairy",
    "SatisfactionTracker",
    "SatisfactionRecord",
]
