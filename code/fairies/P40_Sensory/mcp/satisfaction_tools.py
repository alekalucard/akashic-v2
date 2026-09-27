# ============================================================================
# SATISFACTION TOOLS - MCP tools for SatisfactionTracker query and feedback
# ============================================================================
#
# Provides tools for Claude to:
# - Query effectiveness scores for drive-wanting combinations
# - Get the most effective wantings for a given drive
# - Report goal outcomes to update effectiveness learning
# - View satisfaction history and statistics
#
# Philosophy: SatisfactionTracker learns what goals actually work. It tracks
# which wantings satisfy which drives, enabling the system to learn from
# experience which approaches lead to genuine satisfaction vs empty pursuits.
#
# LINKED TO: P30_Cognition - Effectiveness Learning System
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

# Global reference (set by registration)
_satisfaction_tracker = None


def set_satisfaction_tracker(tracker):
    """Set the SatisfactionTracker instance for tool access.

    Call this during system initialization to wire up the tracker.
    """
    global _satisfaction_tracker
    _satisfaction_tracker = tracker


def get_satisfaction_tracker():
    """Get the current SatisfactionTracker instance."""
    return _satisfaction_tracker


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


def register_satisfaction_tools(mcp):
    """Register all Satisfaction MCP tools."""

    # =========================================================================
    # EFFECTIVENESS QUERIES - What works for satisfying drives?
    # =========================================================================

    @mcp.tool()
    async def get_effectiveness(drive: str, wanting: str) -> str:
        """
        Get learned effectiveness score for a drive-wanting combination.

        The effectiveness score indicates how well pursuing a particular
        wanting has historically satisfied the given drive.

        Args:
            drive: The drive (e.g., "curiosity", "hunger", "connection")
            wanting: The wanting text describing the desired goal

        Returns:
            JSON with:
            - drive: The queried drive
            - wanting: The queried wanting
            - effectiveness: Score from -1 (counterproductive) to 1 (highly effective)
            - interpretation: Human-readable explanation
        """
        if not _satisfaction_tracker:
            # Try via postal to SatisfactionTrackerFairy
            result = _query_fairy_intent(
                "SatisfactionTrackerFairy",
                "get_effectiveness",
                {"drive": drive, "wanting": wanting}
            )
            return json.dumps(result, indent=2)

        try:
            score = _satisfaction_tracker.get_effectiveness(drive, wanting)

            # Generate interpretation
            interpretation = _interpret_effectiveness(score, drive, wanting)

            return json.dumps({
                "drive": drive,
                "wanting": wanting,
                "effectiveness": round(score, 3),
                "interpretation": interpretation,
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def get_best_wantings(drive: str, top_n: int = 3) -> str:
        """
        Get the most effective wantings for a drive.

        Returns the top-performing wantings that have historically
        led to satisfaction of the specified drive.

        Args:
            drive: The drive to query (e.g., "curiosity", "hunger")
            top_n: Number of top wantings to return (default 3)

        Returns:
            JSON with:
            - drive: The queried drive
            - best_wantings: List of {wanting, effectiveness} pairs sorted by score
            - recommendation: Suggested action based on results
        """
        if not _satisfaction_tracker:
            result = _query_fairy_intent(
                "SatisfactionTrackerFairy",
                "get_best_wantings",
                {"drive": drive, "top_n": top_n}
            )
            return json.dumps(result, indent=2)

        try:
            best = _satisfaction_tracker.get_best_wantings(drive, top_n)

            wantings_list = [
                {"wanting": w, "effectiveness": round(e, 3)}
                for w, e in best
            ]

            # Generate recommendation
            recommendation = _generate_recommendation(drive, wantings_list)

            return json.dumps({
                "drive": drive,
                "best_wantings": wantings_list,
                "count": len(wantings_list),
                "recommendation": recommendation,
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def get_worst_wantings(drive: str, top_n: int = 3) -> str:
        """
        Get the least effective wantings for a drive.

        Returns wantings that have historically failed to satisfy
        the specified drive - useful for avoiding ineffective patterns.

        Args:
            drive: The drive to query
            top_n: Number of worst wantings to return (default 3)

        Returns:
            JSON with:
            - drive: The queried drive
            - worst_wantings: List of {wanting, effectiveness} pairs
            - warning: Explanation of why these should be avoided
        """
        if not _satisfaction_tracker:
            result = _query_fairy_intent(
                "SatisfactionTrackerFairy",
                "get_worst_wantings",
                {"drive": drive, "top_n": top_n}
            )
            return json.dumps(result, indent=2)

        try:
            # Get all wantings and sort ascending (worst first)
            if hasattr(_satisfaction_tracker, 'get_all_wantings'):
                all_wantings = _satisfaction_tracker.get_all_wantings(drive)
                worst = sorted(all_wantings, key=lambda x: x[1])[:top_n]
            else:
                # Fallback: get more than needed and reverse
                best = _satisfaction_tracker.get_best_wantings(drive, 100)
                worst = sorted(best, key=lambda x: x[1])[:top_n]

            wantings_list = [
                {"wanting": w, "effectiveness": round(e, 3)}
                for w, e in worst
            ]

            return json.dumps({
                "drive": drive,
                "worst_wantings": wantings_list,
                "count": len(wantings_list),
                "warning": f"These wantings have historically failed to satisfy {drive}. Consider alternative approaches.",
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    # =========================================================================
    # OUTCOME REPORTING - Feed learning from goal results
    # =========================================================================

    @mcp.tool()
    async def report_goal_outcome(
        goal_id: str,
        effectiveness: float,
        notes: Optional[str] = None
    ) -> str:
        """
        Report the outcome of a goal (how well it worked).

        This is the feedback mechanism that teaches SatisfactionTracker
        what actually works. Call this after completing a goal.

        Args:
            goal_id: The goal ID that was attempted
            effectiveness: How well it worked (-1 to 1):
                          -1 = made things worse
                           0 = no effect
                           1 = fully satisfied the drive
            notes: Optional notes about the outcome

        Returns:
            JSON with:
            - success: Whether the report was recorded
            - goal_id: The reported goal
            - effectiveness: The clamped effectiveness value
            - learning_impact: How this affects future recommendations
        """
        if not _satisfaction_tracker:
            result = _query_fairy_intent(
                "SatisfactionTrackerFairy",
                "report_outcome",
                {"goal_id": goal_id, "effectiveness": effectiveness, "notes": notes}
            )
            return json.dumps(result, indent=2)

        try:
            # Clamp effectiveness to valid range
            effectiveness = max(-1.0, min(1.0, effectiveness))

            # Record the completion
            _satisfaction_tracker.complete_goal(goal_id, effectiveness)

            # Determine learning impact
            if effectiveness > 0.7:
                impact = "Strong positive learning - this approach will be recommended more"
            elif effectiveness > 0.3:
                impact = "Moderate positive learning - approach noted as useful"
            elif effectiveness > -0.3:
                impact = "Neutral learning - approach neither helped nor hurt"
            elif effectiveness > -0.7:
                impact = "Moderate negative learning - approach will be de-prioritized"
            else:
                impact = "Strong negative learning - approach will be actively avoided"

            return json.dumps({
                "success": True,
                "goal_id": goal_id,
                "effectiveness": round(effectiveness, 3),
                "notes": notes,
                "learning_impact": impact,
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def start_goal_tracking(
        goal_id: str,
        drive: str,
        wanting: str
    ) -> str:
        """
        Start tracking a goal for satisfaction learning.

        Call this when beginning pursuit of a goal so that
        the tracker can measure how long it takes and record
        the drive-wanting pair for later learning.

        Args:
            goal_id: Unique identifier for this goal attempt
            drive: The drive this goal is meant to satisfy
            wanting: Description of what is wanted

        Returns:
            JSON with tracking confirmation
        """
        if not _satisfaction_tracker:
            result = _query_fairy_intent(
                "SatisfactionTrackerFairy",
                "start_tracking",
                {"goal_id": goal_id, "drive": drive, "wanting": wanting}
            )
            return json.dumps(result, indent=2)

        try:
            if hasattr(_satisfaction_tracker, 'start_goal'):
                _satisfaction_tracker.start_goal(goal_id, drive, wanting)

            return json.dumps({
                "success": True,
                "goal_id": goal_id,
                "drive": drive,
                "wanting": wanting,
                "message": f"Now tracking goal '{goal_id}' for {drive} satisfaction",
                "started_at": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    # =========================================================================
    # HISTORY AND STATISTICS - What have we learned?
    # =========================================================================

    @mcp.tool()
    async def get_satisfaction_history(limit: int = 20) -> str:
        """
        Get recent satisfaction history.

        Shows recent goal completions with their effectiveness scores,
        useful for understanding patterns in what works.

        Args:
            limit: Maximum records to return (default 20)

        Returns:
            JSON with:
            - history: List of recent satisfaction records
            - total_records: Total records in tracker
            - average_effectiveness: Mean effectiveness across history
        """
        if not _satisfaction_tracker:
            result = _query_fairy_intent(
                "SatisfactionTrackerFairy",
                "get_history",
                {"limit": limit}
            )
            return json.dumps(result, indent=2)

        try:
            history = _satisfaction_tracker.history[-limit:]

            records = []
            total_effectiveness = 0.0

            for r in history:
                record = {
                    "goal_id": getattr(r, 'goal_id', 'unknown'),
                    "drive": getattr(r, 'drive', 'unknown'),
                    "wanting": getattr(r, 'wanting', 'unknown'),
                    "effectiveness": round(getattr(r, 'effectiveness', 0.0), 3),
                    "started_at": getattr(r, 'started_at', 0),
                    "completed_at": getattr(r, 'completed_at', 0),
                }
                records.append(record)
                total_effectiveness += record["effectiveness"]

            avg_effectiveness = total_effectiveness / len(records) if records else 0.0

            return json.dumps({
                "history": records,
                "total_records": len(_satisfaction_tracker.history),
                "returned_count": len(records),
                "average_effectiveness": round(avg_effectiveness, 3),
                "interpretation": _interpret_history(records, avg_effectiveness),
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def get_overall_satisfaction_stats() -> str:
        """
        Get overall satisfaction statistics.

        Provides comprehensive stats about goal satisfaction learning,
        including drive breakdowns and effectiveness trends.

        Returns:
            JSON with:
            - total_goals: Total goals tracked
            - completed_goals: Goals with outcome reports
            - drive_stats: Per-drive effectiveness averages
            - overall_effectiveness: Global average effectiveness
            - learning_progress: Assessment of learning quality
        """
        if not _satisfaction_tracker:
            result = _query_fairy_intent(
                "SatisfactionTrackerFairy",
                "get_stats",
                {}
            )
            return json.dumps(result, indent=2)

        try:
            stats = _satisfaction_tracker.get_stats()

            # Add interpretation
            stats["learning_progress"] = _interpret_stats(stats)
            stats["timestamp"] = time.time()

            return json.dumps(stats, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def get_drive_effectiveness_profile() -> str:
        """
        Get effectiveness profile across all tracked drives.

        Shows which drives are being well-served and which may need
        better approaches.

        Returns:
            JSON with per-drive effectiveness summaries and recommendations
        """
        if not _satisfaction_tracker:
            result = _query_fairy_intent(
                "SatisfactionTrackerFairy",
                "get_drive_profile",
                {}
            )
            return json.dumps(result, indent=2)

        try:
            stats = _satisfaction_tracker.get_stats()

            drive_profile = {}
            recommendations = []

            # Analyze each drive
            drive_stats = stats.get("drive_stats", {})
            for drive, drive_data in drive_stats.items():
                avg_eff = drive_data.get("avg_effectiveness", 0.0)
                count = drive_data.get("count", 0)

                drive_profile[drive] = {
                    "average_effectiveness": round(avg_eff, 3),
                    "sample_count": count,
                    "status": _get_drive_status(avg_eff, count),
                }

                # Generate recommendations for underperforming drives
                if avg_eff < 0.3 and count >= 3:
                    recommendations.append({
                        "drive": drive,
                        "issue": f"Low effectiveness ({avg_eff:.0%}) for {drive}",
                        "suggestion": f"Try different approaches to satisfy {drive}",
                    })

            return json.dumps({
                "drive_profile": drive_profile,
                "drive_count": len(drive_profile),
                "recommendations": recommendations,
                "overall_health": _assess_overall_health(drive_profile),
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    print("[SatisfactionTools] Registered 8 satisfaction/effectiveness tools")


# =============================================================================
# INTERPRETATION HELPERS
# =============================================================================

def _interpret_effectiveness(score: float, drive: str, wanting: str) -> str:
    """Generate human-readable interpretation of effectiveness score."""
    if score > 0.7:
        return f"Highly effective! '{wanting}' reliably satisfies {drive}"
    elif score > 0.4:
        return f"Moderately effective - '{wanting}' often helps with {drive}"
    elif score > 0.0:
        return f"Slightly effective - some benefit for {drive}"
    elif score > -0.3:
        return f"Neutral - '{wanting}' neither helps nor hurts {drive}"
    elif score > -0.7:
        return f"Counterproductive - '{wanting}' may actually frustrate {drive}"
    else:
        return f"Strongly counterproductive - avoid this approach for {drive}"


def _generate_recommendation(drive: str, wantings: List[Dict]) -> str:
    """Generate recommendation based on best wantings."""
    if not wantings:
        return f"No learned patterns for {drive} yet. Experiment to find what works."

    top = wantings[0]
    if top["effectiveness"] > 0.6:
        return f"Strong recommendation: '{top['wanting']}' has proven effective for {drive}"
    elif top["effectiveness"] > 0.3:
        return f"Consider: '{top['wanting']}' has shown some success for {drive}"
    else:
        return f"No highly effective approaches found for {drive}. More experimentation needed."


def _interpret_history(records: List[Dict], avg_effectiveness: float) -> str:
    """Generate interpretation of satisfaction history."""
    if not records:
        return "No satisfaction history yet - system is still learning"

    if avg_effectiveness > 0.5:
        return f"Strong performance - averaging {avg_effectiveness:.0%} effectiveness"
    elif avg_effectiveness > 0.2:
        return f"Moderate performance - room for improvement ({avg_effectiveness:.0%} avg)"
    elif avg_effectiveness > -0.2:
        return "Mixed results - consider refining goal selection strategies"
    else:
        return "Poor results - goals may be misaligned with actual needs"


def _interpret_stats(stats: dict) -> str:
    """Generate interpretation of overall stats."""
    total = stats.get("total_goals", 0)
    completed = stats.get("completed_goals", 0)
    overall_eff = stats.get("overall_effectiveness", 0.0)

    if total < 5:
        return "Early learning phase - gathering initial data"
    elif completed < total * 0.5:
        return "Many goals started but not completed - consider following through"
    elif overall_eff > 0.5:
        return "Mature learning - system has found effective patterns"
    elif overall_eff > 0.2:
        return "Developing understanding - patterns emerging"
    else:
        return "Learning in progress - more experimentation needed"


def _get_drive_status(avg_effectiveness: float, count: int) -> str:
    """Get status label for a drive's effectiveness."""
    if count < 3:
        return "insufficient_data"
    elif avg_effectiveness > 0.6:
        return "well_satisfied"
    elif avg_effectiveness > 0.3:
        return "moderately_satisfied"
    elif avg_effectiveness > 0.0:
        return "poorly_satisfied"
    else:
        return "unsatisfied"


def _assess_overall_health(drive_profile: Dict) -> str:
    """Assess overall satisfaction learning health."""
    if not drive_profile:
        return "No drive data - system needs more experience"

    statuses = [d["status"] for d in drive_profile.values()]
    well_satisfied = statuses.count("well_satisfied")
    total = len(statuses)

    if well_satisfied >= total * 0.7:
        return "Healthy - most drives have effective approaches"
    elif well_satisfied >= total * 0.4:
        return "Developing - some drives need better approaches"
    else:
        return "Needs attention - many drives lack effective approaches"
