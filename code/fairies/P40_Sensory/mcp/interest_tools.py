# ============================================================================
# INTEREST TOOLS - MCP tools for curiosity/interest query and influence
# ============================================================================
#
# Provides tools for Claude to:
# - Get currently active interests from InterestGenerator
# - Query the need vs want inference state
# - Observe interest generation patterns
# - Track concept frequency and collision activity
# - Trigger serendipitous interests
# - Mark interests as satisfied to influence urgency
#
# Philosophy: Curiosity is pain-avoidance for the mind. The interest generator
# ensures there's always something worth thinking about. These tools let Claude
# see what the unconscious mind is curious about and influence its curiosity.
#
# LINKED TO: unconscious_mind/interest_generator.py - Spontaneous Curiosity Engine
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

# Global reference (can be set directly for testing or wiring)
_interest_generator = None

# Need/Want category mapping for interest types
# Maps InterestType -> NeedCategory for classifying interests
INTEREST_NEED_MAP = {
    "wonder": "exploration",       # Wants - curiosity-driven
    "curiosity": "exploration",    # Wants - curiosity-driven
    "observation": "awareness",    # Operational - maintaining awareness
    "pattern": "synthesis",        # Wants - pattern seeking
    "anomaly": "pain_relief",      # Needs - anomaly = potential problem
    "connection": "synthesis",     # Wants - meaning making
    "exploration": "exploration",  # Wants - pure exploration
}

# Satisfaction tracking - reduces urgency of recently satisfied interest types
_satisfaction_timestamps: Dict[str, float] = {}
_SATISFACTION_DECAY_TIME = 300.0  # 5 minutes until satisfaction wears off


def set_interest_generator(generator):
    """
    Set the InterestGenerator instance for direct tool access.

    This allows wiring the tools directly to an InterestGenerator
    instance without going through UnconsciousMindFairy.
    """
    global _interest_generator
    _interest_generator = generator


def _get_interest_generator():
    """Get the InterestGenerator instance (lazy load from UnconsciousMindFairy)."""
    global _interest_generator

    # First check if directly wired
    if _interest_generator is not None:
        return _interest_generator

    try:
        # InterestGenerator is typically held by UnconsciousMindFairy
        from fairies.P20_Somatic.SomaticMindFairy import get_somatic_mind as get_unconscious_mind_fairy
        umf = get_unconscious_mind_fairy()
        if umf and hasattr(umf, '_interest_generator'):
            return umf._interest_generator
        return None
    except ImportError:
        pass

    # Fallback: Try to get from module directly
    try:
        from fairies.P20_Somatic.SomaticMindFairy.interest_generator import InterestGenerator
        # Can't create standalone - needs collision chamber
        return None
    except ImportError:
        return None


def _calculate_effective_urgency(interest) -> float:
    """
    Calculate effective urgency considering satisfaction decay.

    Recently satisfied interest types have reduced urgency.
    """
    base_urgency = getattr(interest, 'urgency', 0.5)
    interest_type = getattr(interest, 'interest_type', None)

    if interest_type is None:
        return base_urgency

    type_key = interest_type.value if hasattr(interest_type, 'value') else str(interest_type)

    # Check if this type was recently satisfied
    if type_key in _satisfaction_timestamps:
        elapsed = time.time() - _satisfaction_timestamps[type_key]
        if elapsed < _SATISFACTION_DECAY_TIME:
            # Reduce urgency based on how recently satisfied
            decay_factor = elapsed / _SATISFACTION_DECAY_TIME
            return base_urgency * (0.2 + 0.8 * decay_factor)

    return base_urgency


def _get_current_pain_level() -> float:
    """
    Get current pain level from somatic system.

    Pain level influences need vs want balance - high pain means needs dominate.
    """
    try:
        # Try to get from somatic tools
        from mcp_postal_helper import get_postal, is_bridged_to_server
        postal = get_postal()
        if is_bridged_to_server() and postal:
            if hasattr(postal, 'query_heart'):
                result = postal.query_heart("chemistry")
                if result and result.get('status') == 'ok':
                    blood = result.get('blood', {})
                    chemistry = blood.get('chemistry', {})
                    # Cortisol is a pain indicator
                    cortisol = chemistry.get('COR', 0.3)
                    # Higher cortisol = more pain
                    return min(1.0, cortisol * 1.5)
    except Exception:
        pass

    return 0.3  # Default moderate pain level


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


def register_interest_tools(mcp):
    """Register all interest/curiosity tools with MCP."""

    # =========================================================================
    # INTEREST QUERIES - What is the mind curious about?
    # =========================================================================

    @mcp.tool()
    def get_current_interests(limit: int = 10) -> str:
        """
        Get currently active interests sorted by effective urgency.

        The InterestGenerator produces spontaneous questions and interests
        based on collision chamber activity, pattern detection, and serendipity.
        This is the "I wonder..." and "What if..." generator.

        Args:
            limit: Maximum number of interests to return (default 10)

        Returns:
            JSON with:
            - interests: List of interests with type, content, urgency, effective_urgency, need_category
            - active_interest: Currently pursued interest (if any)
            - interest_types: Breakdown by type (wonder, curiosity, observation, etc.)
            - generator_status: Overall generator health
        """
        gen = _get_interest_generator()

        if not gen:
            # Try via postal to UnconsciousMindFairy
            result = _query_fairy_intent(
                "UnconsciousMindFairy",
                "get_interests",
                {"limit": limit}
            )
            return json.dumps(result, indent=2)

        try:
            status = gen.status()
            recent = gen.get_recent_interests(limit=limit)
            active = gen.get_active_interest()

            # Enrich interests with effective urgency and need category
            enriched_interests = []
            for interest_dict in recent:
                itype = interest_dict.get("type", "unknown")
                base_urgency = interest_dict.get("urgency", 0.5)

                # Calculate effective urgency with satisfaction decay
                if itype in _satisfaction_timestamps:
                    elapsed = time.time() - _satisfaction_timestamps[itype]
                    if elapsed < _SATISFACTION_DECAY_TIME:
                        decay_factor = elapsed / _SATISFACTION_DECAY_TIME
                        effective_urgency = base_urgency * (0.2 + 0.8 * decay_factor)
                    else:
                        effective_urgency = base_urgency
                else:
                    effective_urgency = base_urgency

                enriched_interests.append({
                    "type": itype,
                    "content": interest_dict.get("content", ""),
                    "urgency": base_urgency,
                    "effective_urgency": round(effective_urgency, 3),
                    "need_category": INTEREST_NEED_MAP.get(itype, "idle"),
                    "source": interest_dict.get("source", "unknown"),
                    "created_at": interest_dict.get("created_at"),
                })

            # Sort by effective urgency
            enriched_interests.sort(key=lambda x: x["effective_urgency"], reverse=True)

            # Categorize by type
            type_counts = {}
            for interest in enriched_interests:
                itype = interest["type"]
                type_counts[itype] = type_counts.get(itype, 0) + 1

            return json.dumps({
                "interests": enriched_interests[:int(limit)],  # FIX 2026-06-10: coerce MCP str-limit
                "active_interest": active.to_dict() if active else None,
                "interest_types": type_counts,
                "generator_status": {
                    "total_interests": status.get("total_interests", 0),
                    "concepts_tracked": status.get("concepts_tracked", 0),
                    "recent_collisions": status.get("recent_collisions", 0),
                    "spontaneous_rate": status.get("spontaneous_rate", 0.3),
                    "worker_pool_wired": status.get("worker_pool_wired", False),
                    "atoms_submitted": status.get("atoms_submitted", 0),
                },
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def infer_need_want_state() -> str:
        """
        Get current need/want balance - what does the system need vs want?

        Classifies current interests into needs and wants using INTEREST_NEED_MAP:
        - NEEDS: Pain relief, operational concerns (anomalies, system health)
        - WANTS: Exploration, synthesis, curiosity-driven interests

        Also incorporates:
        - Pain level from somatic system (high pain = needs dominate)
        - EgoLearner trait deficiencies (low traits = identity needs)
        - GoalScheduler active goals (drive-based = needs, curiosity-based = wants)

        Returns:
            JSON with needs, wants, current_priority, and pain_level
        """
        gen = _get_interest_generator()

        if not gen:
            result = _query_fairy_intent(
                "UnconsciousMindFairy",
                "infer_need_want_state",
                {}
            )
            return json.dumps(result, indent=2)

        try:
            recent = gen.get_recent_interests(limit=20)
            pain_level = _get_current_pain_level()

            needs = []
            wants = []

            # Classify interests by need category
            for interest in recent:
                itype = interest.get("type", "unknown")
                category = INTEREST_NEED_MAP.get(itype, "idle")

                interest_data = {
                    "type": itype,
                    "content": interest.get("content", ""),
                    "urgency": interest.get("urgency", 0.5),
                }

                if category in ["pain_relief", "awareness"]:
                    # These are needs - things causing discomfort
                    needs.append(interest_data)
                elif category in ["exploration", "synthesis"]:
                    # These are wants - curiosity-driven desires
                    wants.append(interest_data)

            # Add needs from EgoLearner trait deficiencies
            try:
                from fairies.P00_Autonomic.nervous_system.fairy_directory import get_directory
                directory = get_directory()
                if directory:
                    ego = directory.lookup("EgoLearnerFairy")
                    if ego and hasattr(ego, 'get_identity_traits'):
                        traits = ego.get_identity_traits()
                        for trait, level in traits.items():
                            if level < 0.4:
                                needs.append({
                                    "type": "identity_deficiency",
                                    "content": f"Low {trait} ({level:.2f}) needs development",
                                    "urgency": 0.4 - level,  # Gap as urgency
                                })
            except Exception:
                pass

            # Add wants from GoalScheduler curiosity goals
            try:
                from fairies.P30_Cognition.goal_scheduler.goal_scheduler_fairy import get_goal_scheduler_fairy
                scheduler = get_goal_scheduler_fairy()
                if scheduler and hasattr(scheduler, 'goal_queue'):
                    for goal in list(scheduler.goal_queue.values())[:5]:
                        if getattr(goal, 'source', '') in ("curiosity", "exploration"):
                            wants.append({
                                "type": "goal",
                                "content": getattr(goal, 'name', str(goal)),
                                "urgency": getattr(goal, 'urgency', 0.5),
                            })
            except Exception:
                pass

            # Determine priority based on urgency sums and pain level
            needs_urgency = sum(n.get("urgency", 0.5) for n in needs)
            wants_urgency = sum(w.get("urgency", 0.5) for w in wants)

            # High pain boosts needs priority
            if pain_level > 0.6:
                needs_urgency *= (1 + pain_level)

            current_priority = "needs" if needs_urgency > wants_urgency else "wants"

            return json.dumps({
                "needs": needs,
                "wants": wants,
                "current_priority": current_priority,
                "pain_level": round(pain_level, 3),
                "needs_urgency_total": round(needs_urgency, 3),
                "wants_urgency_total": round(wants_urgency, 3),
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def get_concept_frequency() -> str:
        """
        Get concept frequency tracking from the interest generator.

        Shows which concepts are appearing most often in the thought stream.
        Frequent concepts may indicate:
        - Current preoccupations
        - Developing interests
        - Pattern formation
        - Memory consolidation activity

        Returns:
            JSON with top concepts and their frequency counts
        """
        gen = _get_interest_generator()

        if not gen:
            result = _query_fairy_intent(
                "UnconsciousMindFairy",
                "get_concept_frequency",
                {}
            )
            return json.dumps(result, indent=2)

        try:
            # Access internal frequency tracking
            if hasattr(gen, '_concept_frequency'):
                freq = dict(gen._concept_frequency)
                # Sort by frequency
                sorted_concepts = sorted(freq.items(), key=lambda x: x[1], reverse=True)

                return json.dumps({
                    "top_concepts": [
                        {"concept": c, "count": n}
                        for c, n in sorted_concepts[:20]
                    ],
                    "total_unique": len(freq),
                    "total_observations": sum(freq.values()),
                    "interpretation": _interpret_frequency(sorted_concepts[:5]),
                    "timestamp": time.time(),
                }, indent=2)
            else:
                return json.dumps({
                    "error": "Concept frequency tracking not available",
                    "suggestion": "Interest generator may not be fully initialized",
                })

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def get_collision_observations() -> str:
        """
        Get recent collision observations from the interest generator.

        Collisions occur when recall (memory retrieval) meets ingest (new input).
        The interest generator observes these to detect patterns and generate
        curiosity about recurring themes.

        Returns:
            JSON with recent collision patterns and detected themes
        """
        gen = _get_interest_generator()

        if not gen:
            result = _query_fairy_intent(
                "UnconsciousMindFairy",
                "get_collision_observations",
                {}
            )
            return json.dumps(result, indent=2)

        try:
            if hasattr(gen, '_recent_collisions'):
                collisions = list(gen._recent_collisions)

                # Analyze patterns
                recall_tags = []
                ingest_tags = []
                for c in collisions:
                    recall_tags.extend(c.get("recall", []))
                    ingest_tags.extend(c.get("ingest", []))

                # Count tag frequencies
                recall_freq = {}
                for tag in recall_tags:
                    recall_freq[tag] = recall_freq.get(tag, 0) + 1

                ingest_freq = {}
                for tag in ingest_tags:
                    ingest_freq[tag] = ingest_freq.get(tag, 0) + 1

                return json.dumps({
                    "collision_count": len(collisions),
                    "recall_themes": sorted(recall_freq.items(), key=lambda x: x[1], reverse=True)[:10],
                    "ingest_themes": sorted(ingest_freq.items(), key=lambda x: x[1], reverse=True)[:10],
                    "recent_collisions": collisions[-5:] if collisions else [],
                    "interpretation": _interpret_collisions(recall_freq, ingest_freq),
                    "timestamp": time.time(),
                }, indent=2)
            else:
                return json.dumps({
                    "error": "Collision observation not available",
                    "suggestion": "Interest generator may not be wired to collision chamber",
                })

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def trigger_serendipity(topic: Optional[str] = None) -> str:
        """
        Trigger serendipitous interest generation.

        Serendipity is the random exploration prompt - the "what if we looked at
        something completely different?" moment. Normally happens every ~2 minutes
        but can be triggered manually.

        Args:
            topic: Optional topic to seed the serendipity (influences what
                   the generated interest will be about)

        Returns:
            JSON with the generated serendipitous interest
        """
        gen = _get_interest_generator()

        if not gen:
            result = _query_fairy_intent(
                "UnconsciousMindFairy",
                "trigger_serendipity",
                {"topic": topic} if topic else {}
            )
            return json.dumps(result, indent=2)

        try:
            # If topic provided, observe it first to influence generation
            if topic:
                gen.observe_concept(topic, source="serendipity_seed")

            # Force serendipity by resetting the timer
            gen._last_serendipity = 0

            # Tick to potentially generate
            interest = gen.tick()

            if interest:
                return json.dumps({
                    "success": True,
                    "interest": {
                        "type": interest.interest_type.value if hasattr(interest.interest_type, 'value') else str(interest.interest_type),
                        "content": interest.content,
                        "urgency": interest.urgency,
                    },
                    "seeded_with": topic,
                    "timestamp": time.time(),
                }, indent=2)
            else:
                # Try direct generation
                if hasattr(gen, '_generate_serendipitous_interest'):
                    interest = gen._generate_serendipitous_interest()
                    if interest:
                        return json.dumps({
                            "success": True,
                            "interest": {
                                "type": interest.interest_type.value if hasattr(interest.interest_type, 'value') else str(interest.interest_type),
                                "content": interest.content,
                                "urgency": interest.urgency,
                            },
                            "seeded_with": topic,
                            "timestamp": time.time(),
                        }, indent=2)

                return json.dumps({
                    "success": False,
                    "reason": "No serendipitous interest generated",
                    "seeded_with": topic,
                    "suggestion": "System may need more context to generate interests",
                })

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def mark_interest_satisfied(interest_type: str) -> str:
        """
        Mark an interest type as recently satisfied (reduces its urgency).

        When an interest type is satisfied, future interests of that type
        will have reduced effective urgency for a decay period (~5 minutes).
        This prevents the system from repeatedly generating the same types
        of interests.

        Args:
            interest_type: The type of interest to mark satisfied
                          (e.g., "wonder", "curiosity", "observation", "anomaly")

        Returns:
            JSON with success status and timestamp
        """
        valid_types = list(INTEREST_NEED_MAP.keys())

        if interest_type not in valid_types:
            return json.dumps({
                "success": False,
                "error": f"Unknown interest type: {interest_type}",
                "valid_types": valid_types,
            })

        # Record satisfaction timestamp
        _satisfaction_timestamps[interest_type] = time.time()

        return json.dumps({
            "success": True,
            "interest_type": interest_type,
            "satisfaction_decay_seconds": _SATISFACTION_DECAY_TIME,
            "timestamp": time.time(),
            "message": f"Interests of type '{interest_type}' will have reduced urgency for {_SATISFACTION_DECAY_TIME / 60:.1f} minutes",
        }, indent=2)

    @mcp.tool()
    def get_satisfaction_state() -> str:
        """
        Get the current satisfaction state for all interest types.

        Shows which interest types have been recently satisfied and
        how much time remains until their urgency returns to normal.

        Returns:
            JSON with satisfaction timestamps and remaining decay times
        """
        now = time.time()
        satisfaction_state = {}

        for interest_type, satisfied_at in _satisfaction_timestamps.items():
            elapsed = now - satisfied_at
            remaining = max(0, _SATISFACTION_DECAY_TIME - elapsed)

            if remaining > 0:
                satisfaction_state[interest_type] = {
                    "satisfied_at": satisfied_at,
                    "elapsed_seconds": round(elapsed, 1),
                    "remaining_seconds": round(remaining, 1),
                    "urgency_multiplier": round(0.2 + 0.8 * (elapsed / _SATISFACTION_DECAY_TIME), 3),
                }

        return json.dumps({
            "active_satisfactions": satisfaction_state,
            "decay_time_seconds": _SATISFACTION_DECAY_TIME,
            "valid_interest_types": list(INTEREST_NEED_MAP.keys()),
            "timestamp": now,
        }, indent=2)

    print("[InterestTools] Registered 7 interest/curiosity tools")


def _interpret_frequency(top_concepts: List[tuple]) -> str:
    """Generate interpretation of concept frequency."""
    if not top_concepts:
        return "No concepts tracked yet - system is still warming up"

    top = top_concepts[0]
    if top[1] > 10:
        return f"Strong focus on '{top[0]}' ({top[1]} occurrences) - this may be a developing obsession or important theme"
    elif len(top_concepts) >= 3 and all(c[1] >= 3 for c in top_concepts[:3]):
        names = [c[0] for c in top_concepts[:3]]
        return f"Multiple active themes: {', '.join(names)} - mind is exploring several directions"
    else:
        return "Diverse concept exposure - healthy exploration pattern"


def _interpret_collisions(recall_freq: dict, ingest_freq: dict) -> str:
    """Generate interpretation of collision patterns."""
    if not recall_freq and not ingest_freq:
        return "No collision data - collision chamber may be quiet"

    recall_top = max(recall_freq.items(), key=lambda x: x[1]) if recall_freq else (None, 0)
    ingest_top = max(ingest_freq.items(), key=lambda x: x[1]) if ingest_freq else (None, 0)

    if recall_top[0] == ingest_top[0] and recall_top[0]:
        return f"Strong resonance on '{recall_top[0]}' - memory and input are aligned"
    elif recall_top[1] > ingest_top[1] * 2:
        return f"Memory-heavy collisions - past experiences dominating (top: {recall_top[0]})"
    elif ingest_top[1] > recall_top[1] * 2:
        return f"Input-heavy collisions - new information dominating (top: {ingest_top[0]})"
    else:
        return "Balanced collision pattern - healthy memory-input integration"
