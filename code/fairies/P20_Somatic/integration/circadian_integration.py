# Circadian Integration - Helpers for wiring to circadian rhythm
# P20_Somatic/integration/circadian_integration.py
#
# NOTE: CircadianPacemakerFairy now self-boots with P20 plane.
# This module provides helper functions for other fairies to 
# integrate with the circadian rhythm.

from __future__ import annotations

import time
from typing import Optional, Dict, Any


def get_circadian_status() -> Dict[str, Any]:
    """Get current circadian status for display/debugging."""
    try:
        from fairies.P20_Somatic.circulation.circadian_pacemaker_fairy import get_circadian_pacemaker
        pacemaker = get_circadian_pacemaker()
        if not pacemaker:
            return {"status": "not_running", "error": "Pacemaker not started"}
        
        state = pacemaker.get_state()
        return {
            "status": "running",
            "phase": state.phase_name,
            "virtual_hour": f"{state.virtual_hour:.1f}h",
            "alertness": f"{state.alertness:.0%}",
            "tick_multiplier": f"{state.tick_multiplier:.2f}x",
            "is_active": pacemaker.is_active_hours(),
            "real_time": state.real_time.strftime("%H:%M") if state.real_time else None,
            "suggested_goals": pacemaker.get_suggested_goals(3),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_tick_modulation(base_interval: float = 1.0) -> float:
    """
    Get circadian-adjusted tick interval.
    
    Call from other fairies to adjust their tick rate based on circadian phase.
    
    Args:
        base_interval: The fairy's base tick interval in seconds
        
    Returns:
        Adjusted interval (or base_interval if pacemaker unavailable)
    """
    try:
        from fairies.P20_Somatic.circulation.circadian_pacemaker_fairy import get_circadian_pacemaker
        pacemaker = get_circadian_pacemaker()
        if pacemaker:
            return pacemaker.get_tick_multiplier(base_interval)
    except Exception:
        pass
    return base_interval


def get_drive_modulation() -> Dict[str, float]:
    """
    Get current drive multipliers from circadian phase.
    
    Returns dict like {"curiosity": 1.4, "rest": 0.5, ...}
    """
    try:
        from fairies.P20_Somatic.circulation.circadian_pacemaker_fairy import get_circadian_pacemaker
        pacemaker = get_circadian_pacemaker()
        if pacemaker:
            return pacemaker.get_drive_modulation()
    except Exception:
        pass
    return {}


def get_chemistry_modulation() -> Dict[str, float]:
    """
    Get current chemistry multipliers from circadian phase.
    
    Returns dict like {"COR": 1.4, "NOR": 1.2, ...}
    """
    try:
        from fairies.P20_Somatic.circulation.circadian_pacemaker_fairy import get_circadian_pacemaker
        pacemaker = get_circadian_pacemaker()
        if pacemaker:
            return pacemaker.get_chemistry_modulation()
    except Exception:
        pass
    return {}


def is_active_hours() -> bool:
    """Check if it's currently active hours in the circadian cycle."""
    try:
        from fairies.P20_Somatic.circulation.circadian_pacemaker_fairy import get_circadian_pacemaker
        pacemaker = get_circadian_pacemaker()
        if pacemaker:
            return pacemaker.is_active_hours()
    except Exception:
        pass
    return True  # Default to active


def is_rest_hours() -> bool:
    """Check if it's currently rest hours in the circadian cycle."""
    try:
        from fairies.P20_Somatic.circulation.circadian_pacemaker_fairy import get_circadian_pacemaker
        pacemaker = get_circadian_pacemaker()
        if pacemaker:
            return pacemaker.is_rest_hours()
    except Exception:
        pass
    return False  # Default to not rest


def record_goal_event(goal_name: str, event: str, lifespan: float = 0.0, category: str = "general"):
    """
    Record a goal lifecycle event for circadian memory.
    
    Args:
        goal_name: Name/pattern of the goal
        event: "created", "completed", or "abandoned"
        lifespan: For completed goals, how long it lived (seconds)
        category: Goal category
    """
    try:
        from fairies.P20_Somatic.circulation.circadian_pacemaker_fairy import get_circadian_pacemaker
        pacemaker = get_circadian_pacemaker()
        if pacemaker:
            if event == "created":
                pacemaker.record_goal_creation(goal_name, category)
            elif event == "completed":
                pacemaker.record_goal_completion(goal_name, lifespan)
            elif event == "abandoned":
                pacemaker.record_goal_abandonment(goal_name)
    except Exception:
        pass


def should_create_goal(goal_name: str) -> float:
    """
    Ask circadian memory: should this goal be created now?
    
    Returns probability 0.0-1.0 based on learned patterns.
    """
    try:
        from fairies.P20_Somatic.circulation.circadian_pacemaker_fairy import get_circadian_pacemaker
        pacemaker = get_circadian_pacemaker()
        if pacemaker:
            return pacemaker.should_create_goal(goal_name)
    except Exception:
        pass
    return 0.5  # No data - neutral
