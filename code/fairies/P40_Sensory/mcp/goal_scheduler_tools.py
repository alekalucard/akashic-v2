# ============================================================================
# GOAL SCHEDULER TOOLS - MCP tools for goal queue management
# ============================================================================
#
# Provides tools for Claude to:
# - Get current goal queue with priorities
# - Inject new goals into the scheduler
# - Complete or abandon goals
# - Query mastered goals (what we've already learned)
# - Observe goal-to-action loop status
#
# Philosophy: Goals beget goals beget action. The maintained goal queue IS
# the urge to act. These tools let Claude understand and influence what
# Sourpatches is driven to do.
#
# LINKED TO: P30_Cognition/goal_scheduler/goal_scheduler_fairy.py
# ============================================================================

from __future__ import annotations

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add parent paths for imports
_project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / "fairies"))

# Global reference (set by registration wiring)
_goal_scheduler_fairy = None


def set_goal_scheduler(fairy):
    """
    Set the GoalSchedulerFairy instance for direct tool access.

    This is called by connect_fairy_tools() after boot to wire
    the fairy instance to these tools without lazy lookup overhead.

    Args:
        fairy: The GoalSchedulerFairy instance
    """
    global _goal_scheduler_fairy
    _goal_scheduler_fairy = fairy
    print(f"[GoalSchedulerTools] GoalSchedulerFairy instance connected")


def _get_goal_scheduler():
    """Get the GoalSchedulerFairy instance (lazy load)."""
    global _goal_scheduler_fairy

    # First check if directly wired
    if _goal_scheduler_fairy is not None:
        return _goal_scheduler_fairy

    try:
        from fairies.P30_Cognition.goal_scheduler.goal_scheduler_fairy import get_goal_scheduler_fairy
        return get_goal_scheduler_fairy()
    except ImportError as e:
        print(f"[GoalSchedulerTools] Import error: {e}")
        return None


def _get_tunnel():
    """Get postal tunnel for intent calls to the server."""
    try:
        from fairies.P00_Autonomic.nervous_system.mcp_postal_bridge import get_tunnel
        return get_tunnel()
    except Exception:
        return None


def _query_fairy_intent(fairy_name: str, intent: str, payload: dict, timeout: float = 5.0) -> dict:
    """Query a fairy via postal intent."""
    tunnel = _get_tunnel()
    if not tunnel or not getattr(tunnel, 'connected', False):
        return {"error": "Not connected to server. Start the system first."}

    try:
        if hasattr(tunnel, 'intent_call'):
            result = tunnel.intent_call(fairy_name, intent, payload, timeout=timeout)
            return result if result else {"status": "sent", "no_response": True}
        else:
            return {"error": "Tunnel does not support intent_call"}
    except Exception as e:
        return {"error": str(e)}


def register_goal_scheduler_tools(mcp):
    """Register all goal scheduler tools with MCP."""

    # =========================================================================
    # GOAL QUEUE QUERIES - What are we driven to do?
    # =========================================================================

    @mcp.tool()
    def get_active_goals() -> str:
        """
        Get current goal queue with priorities.

        The goal queue is the urge to act - it contains:
        - Extracted goals from conversation
        - Expanded sub-goals
        - Drive-sourced goals (from pain/desire)
        - Injected goals (from education/external)

        Each goal has:
        - priority: Base importance (0-1)
        - urgency: Grows over time (0-1)
        - nudge_strength: Combined priority * urgency * (1-progress)
        - status: pending, active, done, abandoned

        Returns:
            JSON with goal queue sorted by nudge strength
        """
        scheduler = _get_goal_scheduler()

        if not scheduler:
            result = _query_fairy_intent(
                "GoalSchedulerFairy",
                "get_queue",
                {}
            )
            return json.dumps(result, indent=2)

        try:
            # Get goals sorted by nudge strength
            goals = sorted(
                scheduler.goal_queue.values(),
                key=lambda g: g.get_nudge_strength(),
                reverse=True
            )

            goal_list = [g.to_dict() for g in goals]

            # Calculate queue statistics
            pending = sum(1 for g in goals if g.status == "pending")
            active = sum(1 for g in goals if g.status == "active")
            blocked = sum(1 for g in goals if g.status == "blocked")

            # Get source breakdown
            sources = {}
            for g in goals:
                sources[g.source] = sources.get(g.source, 0) + 1

            return json.dumps({
                "goals": goal_list,
                "queue_size": len(goals),
                "status_breakdown": {
                    "pending": pending,
                    "active": active,
                    "blocked": blocked,
                },
                "source_breakdown": sources,
                "top_nudge_goal": goal_list[0] if goal_list else None,
                "scheduler_intensity": scheduler.scheduler_intensity,
                "nudge_threshold": scheduler.nudge_threshold,
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def get_goal_statistics() -> str:
        """
        Get goal scheduler statistics.

        Shows historical performance:
        - Goals extracted from conversation
        - Goals expanded (sub-goal generation)
        - Nudges sent to autopilot
        - Completed vs failed goals
        - Mastery progress

        Returns:
            JSON with comprehensive statistics
        """
        scheduler = _get_goal_scheduler()

        if not scheduler:
            result = _query_fairy_intent(
                "GoalSchedulerFairy",
                "status",
                {}
            )
            return json.dumps(result, indent=2)

        try:
            completed = list(scheduler.completed_goals)

            return json.dumps({
                "extraction_stats": {
                    "goals_extracted": scheduler.goals_extracted,
                    "goals_expanded": scheduler.goals_expanded,
                    "queue_size": len(scheduler.goal_queue),
                    "max_queue_size": scheduler.max_queue_size,
                },
                "action_stats": {
                    "nudges_sent": scheduler.nudges_sent,
                    "nudge_threshold": scheduler.nudge_threshold,
                    "scheduler_intensity": scheduler.scheduler_intensity,
                },
                "completion_stats": {
                    "completed_count": len(completed),
                    "recent_completions": completed[-5:] if completed else [],
                },
                "mastery_stats": {
                    "mastered_count": len(scheduler.mastered_goals),
                    "mastery_threshold": scheduler._mastery_threshold,
                },
                "expansion_config": {
                    "depth_limit": scheduler.expansion_depth_limit,
                    "enabled": scheduler.expansion_depth_limit > 0,
                },
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    # =========================================================================
    # GOAL MANAGEMENT - Add, complete, abandon
    # =========================================================================

    @mcp.tool()
    def inject_goal(name: str, description: str, priority: float = 0.5, source: str = "mcp") -> str:
        """
        Inject a new goal into the scheduler.

        Use this to add goals that should drive action:
        - Learning tasks
        - Exploration objectives
        - Behavior modifications
        - External assignments

        Args:
            name: Short goal name (will be normalized)
            description: Detailed description of what to achieve
            priority: Importance level 0-1 (default 0.5)
            source: Origin of goal (mcp, education, manual, external)

        Returns:
            JSON with success status and goal details
        """
        scheduler = _get_goal_scheduler()

        if not scheduler:
            # Route via postal
            result = _query_fairy_intent(
                "GoalSchedulerFairy",
                "add_goal",
                {
                    "name": name,
                    "description": description,
                    "priority": priority,
                    "source": source,
                }
            )
            return json.dumps(result, indent=2)

        try:
            from fairies.P30_Cognition.goal_scheduler.goal_scheduler_fairy import ScheduledGoal

            # Normalize priority
            priority = max(0.0, min(1.0, priority))

            goal = ScheduledGoal(
                name=name,
                description=description,
                source=source,
                priority=priority,
            )

            success = scheduler.add_goal(goal)

            if success:
                return json.dumps({
                    "success": True,
                    "goal": goal.to_dict(),
                    "queue_size": len(scheduler.goal_queue),
                    "message": f"Goal '{goal.name}' added with priority {priority:.0%}",
                    "timestamp": time.time(),
                }, indent=2)
            else:
                # Check if mastered or duplicate
                if scheduler._is_mastered(name):
                    return json.dumps({
                        "success": False,
                        "reason": "mastered",
                        "message": f"Goal '{name}' is already mastered - we've learned this",
                        "suggestion": "Try a variation or more advanced version",
                    }, indent=2)
                else:
                    return json.dumps({
                        "success": False,
                        "reason": "duplicate_or_full",
                        "message": f"Could not add goal '{name}'",
                        "suggestion": "Goal may already exist or queue is full",
                    }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def complete_goal(goal_id: str) -> str:
        """
        Mark a goal as completed.

        Completing a goal:
        - Removes it from the active queue
        - Records it in completion history
        - Counts toward mastery threshold
        - May trigger pain relief if goal addressed a drive

        Args:
            goal_id: The goal ID or name to complete

        Returns:
            JSON with completion status and mastery progress
        """
        scheduler = _get_goal_scheduler()

        if not scheduler:
            result = _query_fairy_intent(
                "GoalSchedulerFairy",
                "complete_goal",
                {"goal_id": goal_id}
            )
            return json.dumps(result, indent=2)

        try:
            # Find goal by ID or name
            goal = scheduler.goal_queue.get(goal_id)
            if not goal:
                # Try by name
                for gid, g in scheduler.goal_queue.items():
                    if g.name == goal_id:
                        goal = g
                        goal_id = gid
                        break

            if not goal:
                return json.dumps({
                    "success": False,
                    "error": f"Goal not found: {goal_id}",
                    "available_goals": [g.name for g in scheduler.goal_queue.values()][:10],
                }, indent=2)

            # Get mastery status before completing
            old_count = scheduler._completion_counts.get(scheduler._normalize_goal_name(goal.name), 0)

            # Complete it
            scheduler.complete_goal(goal_id)

            # Check new mastery status
            new_count = scheduler._completion_counts.get(scheduler._normalize_goal_name(goal.name), 0)
            newly_mastered = scheduler._is_mastered(goal.name)

            return json.dumps({
                "success": True,
                "goal_name": goal.name,
                "completion_count": new_count,
                "mastery_threshold": scheduler._mastery_threshold,
                "newly_mastered": newly_mastered and old_count < scheduler._mastery_threshold,
                "message": f"Goal '{goal.name}' completed! ({new_count}/{scheduler._mastery_threshold} toward mastery)",
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def abandon_goal(goal_id: str, reason: str = "") -> str:
        """
        Abandon a goal (give up on it).

        Use this when a goal is:
        - No longer relevant
        - Impossible to achieve
        - Superseded by something else

        Args:
            goal_id: The goal ID or name to abandon
            reason: Why abandoning (for logging)

        Returns:
            JSON with abandonment confirmation
        """
        scheduler = _get_goal_scheduler()

        if not scheduler:
            result = _query_fairy_intent(
                "GoalSchedulerFairy",
                "abandon_goal",
                {"goal_id": goal_id, "reason": reason}
            )
            return json.dumps(result, indent=2)

        try:
            # Find goal
            goal = scheduler.goal_queue.get(goal_id)
            if not goal:
                for gid, g in scheduler.goal_queue.items():
                    if g.name == goal_id:
                        goal = g
                        goal_id = gid
                        break

            if not goal:
                return json.dumps({
                    "success": False,
                    "error": f"Goal not found: {goal_id}",
                }, indent=2)

            # Abandon it
            goal.abandon(reason)
            del scheduler.goal_queue[goal_id]

            return json.dumps({
                "success": True,
                "goal_name": goal.name,
                "reason": reason or "No reason given",
                "queue_size": len(scheduler.goal_queue),
                "message": f"Goal '{goal.name}' abandoned",
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    # =========================================================================
    # MASTERY QUERIES - What have we already learned?
    # =========================================================================

    @mcp.tool()
    def get_mastered_goals() -> str:
        """
        Get all mastered goals (things we've already learned).

        Mastery happens when a goal is completed multiple times
        (default threshold: 3). Mastered goals are not re-added
        to the queue - we've internalized that learning.

        Returns:
            JSON with mastered goal list and categories
        """
        scheduler = _get_goal_scheduler()

        if not scheduler:
            result = _query_fairy_intent(
                "GoalSchedulerFairy",
                "get_mastered",
                {}
            )
            return json.dumps(result, indent=2)

        try:
            mastered = list(scheduler.mastered_goals)
            variations = dict(scheduler.mastered_variations)
            counts = dict(scheduler._completion_counts)

            return json.dumps({
                "mastered_goals": mastered,
                "mastered_count": len(mastered),
                "mastery_threshold": scheduler._mastery_threshold,
                "by_category": variations,
                "completion_counts": {
                    k: v for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:20]
                },
                "message": f"{len(mastered)} skills/behaviors mastered through repetition",
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def check_goal_mastery(goal_name: str) -> str:
        """
        Check if a specific goal is already mastered.

        Uses fuzzy matching to catch variations of the same goal.

        Args:
            goal_name: The goal name to check

        Returns:
            JSON with mastery status and completion count
        """
        scheduler = _get_goal_scheduler()

        if not scheduler:
            result = _query_fairy_intent(
                "GoalSchedulerFairy",
                "check_mastery",
                {"goal_name": goal_name}
            )
            return json.dumps(result, indent=2)

        try:
            is_mastered = scheduler._is_mastered(goal_name)
            normalized = scheduler._normalize_goal_name(goal_name)
            count = scheduler._completion_counts.get(normalized, 0)

            return json.dumps({
                "goal_name": goal_name,
                "normalized": normalized,
                "is_mastered": is_mastered,
                "completion_count": count,
                "mastery_threshold": scheduler._mastery_threshold,
                "progress": f"{count}/{scheduler._mastery_threshold}",
                "message": "Already mastered - no need to repeat" if is_mastered else f"Not yet mastered ({count}/{scheduler._mastery_threshold} completions)",
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    # =========================================================================
    # EXTRACTION - Find goals in text
    # =========================================================================

    @mcp.tool()
    def extract_goals_from_text(text: str, source: str = "manual") -> str:
        """
        Extract goals from provided text.

        Uses pattern matching to find implicit goals in conversation:
        - "we should..." -> goal
        - "need to..." -> high priority goal
        - "what about..." -> exploration goal
        - "...is missing" -> gap-filling goal

        Args:
            text: Text to extract goals from
            source: Label for goal origin (manual, conversation, thinking)

        Returns:
            JSON with extracted goals
        """
        scheduler = _get_goal_scheduler()

        if not scheduler:
            result = _query_fairy_intent(
                "GoalSchedulerFairy",
                "extract",
                {"text": text, "source": source}
            )
            return json.dumps(result, indent=2)

        try:
            goals = scheduler.extract_goals(text, source=source)

            extracted = []
            added = []
            skipped = []

            for goal in goals:
                goal_dict = goal.to_dict()
                extracted.append(goal_dict)

                if scheduler.add_goal(goal):
                    added.append(goal.name)
                else:
                    skipped.append({
                        "name": goal.name,
                        "reason": "mastered" if scheduler._is_mastered(goal.name) else "duplicate/full"
                    })

            return json.dumps({
                "extracted_count": len(extracted),
                "added_count": len(added),
                "skipped_count": len(skipped),
                "extracted": extracted,
                "added": added,
                "skipped": skipped,
                "queue_size": len(scheduler.goal_queue),
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def boost_goal_priority(goal_id: str, boost: float = 0.1, reason: str = "") -> str:
        """
        Boost a goal's priority.

        Use when external factors make a goal more urgent:
        - User explicitly requests focus on something
        - Oracle guidance suggests a path
        - Pain drive intensifies

        Args:
            goal_id: Goal ID or name to boost
            boost: Amount to add to priority (0.0-0.2, capped at 1.0)
            reason: Why boosting (for logging)

        Returns:
            JSON with updated priority
        """
        scheduler = _get_goal_scheduler()

        if not scheduler:
            result = _query_fairy_intent(
                "GoalSchedulerFairy",
                "boost_goal",
                {"goal_id": goal_id, "boost": boost, "reason": reason}
            )
            return json.dumps(result, indent=2)

        try:
            # Find goal
            goal = scheduler.goal_queue.get(goal_id)
            if not goal:
                for gid, g in scheduler.goal_queue.items():
                    if g.name == goal_id:
                        goal = g
                        break

            if not goal:
                return json.dumps({
                    "success": False,
                    "error": f"Goal not found: {goal_id}",
                }, indent=2)

            # Apply boost
            boost = min(0.2, max(0.0, boost))
            old_priority = goal.priority
            goal.priority = min(1.0, goal.priority + boost)
            goal.urgency = min(1.0, goal.urgency + boost * 0.5)

            return json.dumps({
                "success": True,
                "goal_name": goal.name,
                "old_priority": round(old_priority, 3),
                "new_priority": round(goal.priority, 3),
                "boost_applied": round(boost, 3),
                "reason": reason or "Manual boost",
                "new_nudge_strength": round(goal.get_nudge_strength(), 3),
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    # =========================================================================
    # INTEREST BRIDGE - Connect interests to goals
    # =========================================================================

    @mcp.tool()
    def get_interest_bridge_status() -> str:
        """
        Get the connection status between InterestSchedulerFairy and GoalScheduler.

        Shows:
        - Active interests that could become goals
        - Interests that have generated goals
        - Interest-to-goal conversion rate
        - Bridge health

        Returns:
            JSON with interest bridge status
        """
        scheduler = _get_goal_scheduler()

        if not scheduler:
            result = _query_fairy_intent(
                "GoalSchedulerFairy",
                "get_interest_bridge",
                {}
            )
            return json.dumps(result, indent=2)

        try:
            # Try to get InterestSchedulerFairy
            interest_scheduler = None
            try:
                from fairies.P30_Cognition.cognition.interest_scheduler_fairy import get_interest_scheduler_fairy
                interest_scheduler = get_interest_scheduler_fairy()
            except ImportError:
                pass

            if not interest_scheduler:
                return json.dumps({
                    "bridge_status": "disconnected",
                    "reason": "InterestSchedulerFairy not available",
                    "suggestion": "Interest tracking requires the InterestSchedulerFairy to be running",
                    "timestamp": time.time(),
                }, indent=2)

            # Get active interests
            active_interests = []
            if hasattr(interest_scheduler, 'get_active_interests'):
                active_interests = interest_scheduler.get_active_interests()
            elif hasattr(interest_scheduler, '_interests'):
                active_interests = [
                    i for i in interest_scheduler._interests.values()
                    if hasattr(i, 'is_active') and i.is_active
                ]

            # Count interests that have goals
            interests_with_goals = 0
            goal_names = {g.name.lower() for g in scheduler.goal_queue.values()}
            for interest in active_interests:
                topic = interest.topic if hasattr(interest, 'topic') else str(interest)
                if any(topic.lower() in gn for gn in goal_names):
                    interests_with_goals += 1

            return json.dumps({
                "bridge_status": "connected",
                "active_interests": len(active_interests),
                "interests_with_goals": interests_with_goals,
                "conversion_rate": round(interests_with_goals / max(1, len(active_interests)), 3),
                "top_interests": [
                    {
                        "topic": i.topic if hasattr(i, 'topic') else str(i),
                        "strength": getattr(i, 'strength', 0.5),
                        "wants_continuation": getattr(i, 'wants_continuation', False),
                    }
                    for i in active_interests[:5]
                ],
                "goal_queue_size": len(scheduler.goal_queue),
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def convert_interest_to_goal(topic: str, priority: float = 0.6) -> str:
        """
        Convert an expressed interest into a goal.

        Use when you detect interest in something and want to create
        a goal to pursue it. This bridges the interest -> goal -> action loop.

        Args:
            topic: The interest topic to convert
            priority: Goal priority (0-1, default 0.6)

        Returns:
            JSON with created goal or error
        """
        scheduler = _get_goal_scheduler()

        if not scheduler:
            result = _query_fairy_intent(
                "GoalSchedulerFairy",
                "add_goal",
                {
                    "name": f"explore_{topic}",
                    "description": f"Explore interest: {topic}",
                    "priority": priority,
                    "source": "interest_bridge",
                }
            )
            return json.dumps(result, indent=2)

        try:
            from fairies.P30_Cognition.goal_scheduler.goal_scheduler_fairy import ScheduledGoal

            # Check if already mastered
            if scheduler._is_mastered(topic):
                return json.dumps({
                    "success": False,
                    "reason": "mastered",
                    "message": f"Interest '{topic}' is already mastered - try a new variation",
                }, indent=2)

            # Create goal from interest
            goal = ScheduledGoal(
                name=scheduler._normalize_goal_name(f"explore_{topic}"),
                description=f"Explore interest: {topic}",
                source="interest_bridge",
                priority=min(1.0, max(0.0, priority)),
            )

            if scheduler.add_goal(goal):
                return json.dumps({
                    "success": True,
                    "goal": goal.to_dict(),
                    "message": f"Interest '{topic}' converted to goal",
                    "queue_size": len(scheduler.goal_queue),
                    "timestamp": time.time(),
                }, indent=2)
            else:
                return json.dumps({
                    "success": False,
                    "reason": "duplicate_or_full",
                    "message": f"Could not convert interest '{topic}' - may already exist",
                }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    # =========================================================================
    # SATISFACTION TRACKING - How effective are our goals?
    # =========================================================================

    @mcp.tool()
    def get_goal_effectiveness_stats() -> str:
        """
        Get satisfaction/effectiveness statistics for completed goals.

        Shows how well goals are satisfying underlying drives:
        - Completion rate by source
        - Average effectiveness by category
        - Pain relief statistics
        - Mastery progress

        Returns:
            JSON with effectiveness statistics
        """
        scheduler = _get_goal_scheduler()

        if not scheduler:
            result = _query_fairy_intent(
                "GoalSchedulerFairy",
                "get_effectiveness",
                {}
            )
            return json.dumps(result, indent=2)

        try:
            completed = list(scheduler.completed_goals)

            # Calculate stats by source
            source_stats = {}
            for goal_dict in completed:
                source = goal_dict.get("source", "unknown")
                if source not in source_stats:
                    source_stats[source] = {"count": 0, "total_priority": 0}
                source_stats[source]["count"] += 1
                source_stats[source]["total_priority"] += goal_dict.get("priority", 0.5)

            # Calculate averages
            for source, stats in source_stats.items():
                stats["avg_priority"] = round(stats["total_priority"] / max(1, stats["count"]), 3)
                del stats["total_priority"]

            # Mastery stats
            mastery_stats = {
                "mastered_count": len(scheduler.mastered_goals),
                "threshold": scheduler._mastery_threshold,
                "top_completion_counts": sorted(
                    [(k, v) for k, v in scheduler._completion_counts.items()],
                    key=lambda x: x[1],
                    reverse=True
                )[:10],
            }

            # Pain relief correlation (if tracking)
            pain_relief_stats = {}
            if hasattr(scheduler, '_pain_relief_history'):
                for relief in scheduler._pain_relief_history:
                    drive = relief.get("drive", "unknown")
                    if drive not in pain_relief_stats:
                        pain_relief_stats[drive] = {"count": 0, "total_relief": 0}
                    pain_relief_stats[drive]["count"] += 1
                    pain_relief_stats[drive]["total_relief"] += relief.get("amount", 0.2)

            return json.dumps({
                "total_completed": len(completed),
                "by_source": source_stats,
                "mastery_stats": mastery_stats,
                "pain_relief_stats": pain_relief_stats if pain_relief_stats else "Not tracked",
                "completion_rate": round(
                    len(completed) / max(1, scheduler.goals_extracted), 3
                ),
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def report_goal_satisfaction(goal_id: str, satisfaction: float, feedback: str = "") -> str:
        """
        Report how satisfying a goal completion was.

        Use this after completing a goal to record how effective it was.
        This helps tune future goal priorities and mastery tracking.

        Args:
            goal_id: The goal ID (can be from completed_goals)
            satisfaction: How satisfying (-1.0 to 1.0, where 1.0 is very satisfying)
            feedback: Optional text feedback about the experience

        Returns:
            JSON with recording confirmation
        """
        scheduler = _get_goal_scheduler()

        if not scheduler:
            result = _query_fairy_intent(
                "GoalSchedulerFairy",
                "record_satisfaction",
                {"goal_id": goal_id, "satisfaction": satisfaction, "feedback": feedback}
            )
            return json.dumps(result, indent=2)

        try:
            # Clamp satisfaction
            satisfaction = max(-1.0, min(1.0, satisfaction))

            # Initialize tracking if needed
            if not hasattr(scheduler, '_satisfaction_history'):
                scheduler._satisfaction_history = []

            # Find the goal in completed_goals
            goal_dict = None
            for g in scheduler.completed_goals:
                if g.get("id") == goal_id or g.get("name") == goal_id:
                    goal_dict = g
                    break

            if not goal_dict:
                return json.dumps({
                    "success": False,
                    "error": f"Goal not found in completed goals: {goal_id}",
                    "recent_completed": [g.get("name") for g in list(scheduler.completed_goals)[-5:]],
                }, indent=2)

            # Record satisfaction
            record = {
                "goal_id": goal_dict.get("id"),
                "goal_name": goal_dict.get("name"),
                "source": goal_dict.get("source"),
                "satisfaction": satisfaction,
                "feedback": feedback,
                "timestamp": time.time(),
            }
            scheduler._satisfaction_history.append(record)

            # High satisfaction might boost mastery progress
            if satisfaction > 0.8 and hasattr(scheduler, '_record_completion'):
                scheduler._record_completion(goal_dict.get("name"), goal_dict.get("source", "general"))

            # Negative satisfaction might warrant re-adding
            suggestion = None
            if satisfaction < -0.5:
                suggestion = "Consider re-adding this goal with different approach"
            elif satisfaction > 0.8:
                suggestion = "Great result! This goal type is effective"

            return json.dumps({
                "success": True,
                "recorded": record,
                "suggestion": suggestion,
                "total_satisfaction_records": len(scheduler._satisfaction_history),
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def get_oracle_guidance_status() -> str:
        """
        Get current Oracle guidance affecting goal priorities.

        The ProbabilityOracleFairy provides probability guidance that
        influences goal priorities. This shows the current guidance state.

        Returns:
            JSON with oracle guidance affecting goals
        """
        scheduler = _get_goal_scheduler()

        if not scheduler:
            result = _query_fairy_intent(
                "GoalSchedulerFairy",
                "get_oracle_guidance",
                {}
            )
            return json.dumps(result, indent=2)

        try:
            guidance = scheduler.get_oracle_guidance() if hasattr(scheduler, 'get_oracle_guidance') else None

            if not guidance:
                return json.dumps({
                    "oracle_connected": False,
                    "message": "No oracle guidance received yet",
                    "suggestion": "Oracle guidance arrives via oracle.reading channel from ProbabilityOracleFairy",
                    "timestamp": time.time(),
                }, indent=2)

            # Check freshness
            age = time.time() - guidance.get("ts", 0)
            is_fresh = age < 300  # Fresh if less than 5 minutes old

            return json.dumps({
                "oracle_connected": True,
                "guidance": {
                    "recommended_path": guidance.get("recommended", ""),
                    "confidence": guidance.get("confidence", 0),
                    "paths": guidance.get("paths", {}),
                    "reasoning": guidance.get("reasoning", []),
                    "question": guidance.get("question", ""),
                },
                "freshness": {
                    "is_fresh": is_fresh,
                    "age_seconds": round(age, 1),
                    "received_at": guidance.get("ts"),
                },
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    print("[GoalSchedulerTools] Registered 14 goal scheduler tools")
