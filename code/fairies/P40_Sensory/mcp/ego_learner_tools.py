# ============================================================================
# EGO LEARNER TOOLS - MCP tools for identity/personality query access
# ============================================================================
#
# Provides tools for Claude to:
# - Query what Sourpatches NEEDS based on personality deficiencies
# - Query what Sourpatches DESIRES based on past experiences
# - Get current identity traits and evolution status
# - Inspect the 4D learning tensor state
#
# Philosophy: These tools let Claude understand the personality layer -
# what shapes identity, what drives growth, what needs nurturing.
#
# LINKED TO: P50_Persona/EgoLearnerFairy - Identity Evolution Through Experience
# ============================================================================

from __future__ import annotations

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Add parent paths for imports
_project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / "fairies"))

# Global reference (set by registration wiring)
_ego_learner_fairy = None


def set_ego_learner_fairy(fairy):
    """
    Set the EgoLearnerFairy instance for direct tool access.

    This is called by connect_fairy_tools() after boot to wire
    the fairy instance to these tools without lazy lookup overhead.

    Args:
        fairy: The EgoLearnerFairy instance
    """
    global _ego_learner_fairy
    _ego_learner_fairy = fairy
    print(f"[EgoLearnerTools] EgoLearnerFairy instance connected")


def _get_ego_learner():
    """Get the EgoLearnerFairy instance (lazy load)."""
    global _ego_learner_fairy

    # First check if directly wired
    if _ego_learner_fairy is not None:
        return _ego_learner_fairy

    try:
        from fairies.P50_Persona.EgoLearnerFairy.fairy import EgoLearnerFairy
        # Try to get existing instance from directory first
        try:
            from fairies.P00_Autonomic.nervous_system.fairy_directory import get_directory
            directory = get_directory()
            if directory:
                fairy = directory.lookup("EgoLearnerFairy")
                if fairy:
                    return fairy
        except Exception:
            pass
        # Fallback: return None if not found (don't create new instances)
        return None
    except ImportError as e:
        print(f"[EgoLearnerTools] Import error: {e}")
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


def register_ego_learner_tools(mcp):
    """Register all ego learner/identity tools with MCP."""

    # =========================================================================
    # NEED/WANT QUERIES - What does Sourpatches require?
    # =========================================================================

    @mcp.tool()
    def query_ego_needs() -> str:
        """
        Query what Sourpatches NEEDS based on personality deficiencies.

        Analyzes identity traits to find areas below threshold that
        need nurturing. These are personality deficiencies - traits
        that are underdeveloped and causing discomfort.

        Returns:
            JSON with:
            - needs: List of needs with trait name, current level, and gap
            - priority_need: The most pressing need
            - total_deficiency: Overall personality health score
        """
        ego = _get_ego_learner()

        if not ego:
            # Try via postal
            result = _query_fairy_intent("EgoLearnerFairy", "get_needs", {})
            return json.dumps(result, indent=2)

        try:
            traits = ego.get_identity_traits()

            # Traits below 0.4 are "needs" - deficiencies requiring nurturing
            NEED_THRESHOLD = 0.4
            needs = []

            for trait_name, level in traits.items():
                if level < NEED_THRESHOLD:
                    gap = NEED_THRESHOLD - level
                    needs.append({
                        "trait": trait_name,
                        "current_level": round(level, 3),
                        "threshold": NEED_THRESHOLD,
                        "gap": round(gap, 3),
                        "urgency": round(gap / NEED_THRESHOLD, 3),  # 0-1 urgency scale
                    })

            # Sort by urgency (biggest gaps first)
            needs.sort(key=lambda n: n["urgency"], reverse=True)

            # Calculate overall deficiency
            total_deficiency = sum(n["gap"] for n in needs)

            return json.dumps({
                "needs": needs,
                "priority_need": needs[0] if needs else None,
                "total_deficiency": round(total_deficiency, 3),
                "trait_count": len(traits),
                "deficiency_count": len(needs),
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def query_ego_desires() -> str:
        """
        Query what Sourpatches DESIRES based on past experiences.

        Analyzes learning history to find what experiences brought
        satisfaction and joy. These are things she WANTS to pursue
        again based on positive past experiences.

        Returns:
            JSON with:
            - desires: List of desires with category, strength, and source
            - top_desire: The strongest current desire
            - desire_profile: Summary of desire patterns
        """
        ego = _get_ego_learner()

        if not ego:
            # Try via postal
            result = _query_fairy_intent("EgoLearnerFairy", "get_desires", {})
            return json.dumps(result, indent=2)

        try:
            # Get learning summary to analyze patterns
            summary = ego.get_learning_summary()
            tensor_stats = ego.get_tensor_stats()

            desires = []

            # Skill-based desires - high skill activity = desire to continue
            if summary.get("skill_ups", 0) > 3:
                desires.append({
                    "category": "skill_mastery",
                    "description": "Continue skill development and mastery",
                    "strength": min(1.0, summary["skill_ups"] * 0.1),
                    "source": f"{summary['skill_ups']} skill level ups",
                    "type": "growth",
                })

            # Achievement desires - past achievements create desire for more
            if summary.get("achievements", 0) > 0:
                desires.append({
                    "category": "achievement",
                    "description": "Pursue recognition and accomplishment",
                    "strength": min(1.0, summary["achievements"] * 0.15),
                    "source": f"{summary['achievements']} achievements unlocked",
                    "type": "recognition",
                })

            # Goal completion creates desire for more purposeful action
            if summary.get("goal_completions", 0) > 2:
                success_rate = summary.get("success_rate", 0.5)
                desires.append({
                    "category": "purposeful_action",
                    "description": "Take on meaningful goals and complete them",
                    "strength": success_rate * 0.8,
                    "source": f"{summary['goal_completions']} goals completed ({success_rate:.0%} success rate)",
                    "type": "agency",
                })

            # Curiosity desire from tensor experience diversity
            exp_count = tensor_stats.get("experience_count", 0)
            if exp_count > 5:
                desires.append({
                    "category": "exploration",
                    "description": "Explore new experiences and expand horizons",
                    "strength": min(1.0, exp_count * 0.08),
                    "source": f"{exp_count} unique experience types recorded",
                    "type": "curiosity",
                })

            # Connection desire from relationship patterns
            traits = ego.get_identity_traits()
            empathy = traits.get("empathy", 0.5)
            if empathy > 0.5:
                desires.append({
                    "category": "connection",
                    "description": "Build and deepen relationships",
                    "strength": empathy,
                    "source": f"Empathy trait at {empathy:.0%}",
                    "type": "social",
                })

            # Sort by strength
            desires.sort(key=lambda d: d["strength"], reverse=True)

            # Calculate desire profile
            desire_types = {}
            for d in desires:
                t = d["type"]
                desire_types[t] = desire_types.get(t, 0) + d["strength"]

            return json.dumps({
                "desires": desires,
                "top_desire": desires[0] if desires else None,
                "desire_count": len(desires),
                "desire_profile": desire_types,
                "total_experiences": summary.get("total_experiences", 0),
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    # =========================================================================
    # IDENTITY STATE - Current personality snapshot
    # =========================================================================

    @mcp.tool()
    def get_identity_traits() -> str:
        """
        Get current identity trait levels.

        Identity traits are the core personality dimensions that
        evolve through experience:
        - curiosity: Desire to explore and learn
        - persistence: Sticking with goals through difficulty
        - empathy: Connection and understanding of others
        - creativity: Novel approaches and thinking
        - confidence: Self-belief and agency
        - patience: Tolerance for difficulty and uncertainty

        Returns:
            JSON with all trait levels (0-1 scale) and evolution status
        """
        ego = _get_ego_learner()

        if not ego:
            # Try via postal
            result = _query_fairy_intent("EgoLearnerFairy", "get_identity", {})
            return json.dumps(result, indent=2)

        try:
            traits = ego.get_identity_traits()

            # Calculate overall personality health
            avg_trait = sum(traits.values()) / len(traits) if traits else 0.5

            # Identify strongest and weakest
            sorted_traits = sorted(traits.items(), key=lambda x: x[1])
            weakest = sorted_traits[0] if sorted_traits else None
            strongest = sorted_traits[-1] if sorted_traits else None

            return json.dumps({
                "traits": {k: round(v, 3) for k, v in traits.items()},
                "average_level": round(avg_trait, 3),
                "strongest": {"trait": strongest[0], "level": round(strongest[1], 3)} if strongest else None,
                "weakest": {"trait": weakest[0], "level": round(weakest[1], 3)} if weakest else None,
                "trait_descriptions": {
                    "curiosity": "Desire to explore and learn",
                    "persistence": "Sticking with goals through difficulty",
                    "empathy": "Connection and understanding of others",
                    "creativity": "Novel approaches and thinking",
                    "confidence": "Self-belief and agency",
                    "patience": "Tolerance for difficulty and uncertainty",
                },
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def get_learning_summary() -> str:
        """
        Get summary of accumulated learning experiences.

        Shows how identity has been shaped by:
        - Skill level ups (mastery experiences)
        - Achievements unlocked (recognition experiences)
        - Goals completed vs failed (agency experiences)
        - Total experiences processed

        Returns:
            JSON with learning statistics and success metrics
        """
        ego = _get_ego_learner()

        if not ego:
            result = _query_fairy_intent("EgoLearnerFairy", "get_summary", {})
            return json.dumps(result, indent=2)

        try:
            summary = ego.get_learning_summary()
            tensor_stats = ego.get_tensor_stats()

            return json.dumps({
                "learning_summary": summary,
                "tensor_stats": tensor_stats,
                "interpretation": _interpret_learning(summary, tensor_stats),
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def get_evolution_log(count: int = 10) -> str:
        """
        Get recent identity evolution events.

        Shows when and why identity traits changed, including:
        - Evolution triggers (skill ups, achievements, collisions)
        - Trait changes with before/after values
        - Patterns in identity development

        Args:
            count: Number of recent events to return (default 10)

        Returns:
            JSON with evolution event history
        """
        ego = _get_ego_learner()

        if not ego:
            result = _query_fairy_intent(
                "EgoLearnerFairy",
                "get_evolution_log",
                {"count": count}
            )
            return json.dumps(result, indent=2)

        try:
            log = ego.get_evolution_log(n=count)

            return json.dumps({
                "evolution_events": log,
                "event_count": len(log),
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    # =========================================================================
    # TENSOR INSPECTION - Deep learning state
    # =========================================================================

    @mcp.tool()
    def inspect_learning_tensor() -> str:
        """
        Inspect the 4D learning tensor state.

        The tensor captures multi-dimensional learning:
        - Dimension 0: Experience types encountered
        - Dimension 1: Emotional states during experiences
        - Dimension 2: Behavioral patterns learned
        - Dimension 3: Outcome categories (success levels)

        Returns:
            JSON with tensor shape, label counts, and statistics
        """
        ego = _get_ego_learner()

        if not ego:
            result = _query_fairy_intent("EgoLearnerFairy", "get_tensor", {})
            return json.dumps(result, indent=2)

        try:
            stats = ego.get_tensor_stats()

            return json.dumps({
                "tensor_stats": stats,
                "dimension_descriptions": {
                    "dim_0_experiences": f"{stats.get('experience_count', 0)} unique experience types",
                    "dim_1_emotions": f"{stats.get('emotion_count', 0)} emotional states tracked",
                    "dim_2_patterns": f"{stats.get('pattern_count', 0)} behavioral patterns",
                    "dim_3_outcomes": "10 feedback bins (0-9 success levels)",
                },
                "total_learning_updates": stats.get("total_updates", 0),
                "interpretation": _interpret_tensor(stats),
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    # =========================================================================
    # PREFERENCE LEARNING - Teach Sourpatches what she likes/dislikes
    # =========================================================================

    @mcp.tool()
    def learn_preference(category: str, item: str, valence: float) -> str:
        """
        Teach Sourpatches a preference (likes/dislikes).

        Preferences are learned associations between categories and items
        with a valence indicating how much she likes or dislikes them.
        This allows her personality to be shaped through interaction.

        Args:
            category: Category of preference (e.g., "topics", "activities", "styles", "foods", "music")
            item: The specific item (e.g., "coding", "poetry", "sarcasm", "pizza", "jazz")
            valence: How much she likes it (-1.0 = strongly dislikes, 0.0 = neutral, 1.0 = strongly likes)

        Returns:
            JSON with success status and learned preference
        """
        ego = _get_ego_learner()

        # Clamp valence to valid range
        valence = max(-1.0, min(1.0, valence))

        if not ego:
            # Try via postal
            result = _query_fairy_intent(
                "EgoLearnerFairy",
                "learn_preference",
                {"category": category, "item": item, "valence": valence}
            )
            return json.dumps(result, indent=2)

        try:
            # Store preference in identity traits under "preferences" sub-dict
            if not hasattr(ego, '_preferences'):
                ego._preferences = {}

            if category not in ego._preferences:
                ego._preferences[category] = {}

            # Store with timestamp for decay/recency
            ego._preferences[category][item] = {
                "valence": valence,
                "learned_at": time.time(),
                "reinforcement_count": ego._preferences.get(category, {}).get(item, {}).get("reinforcement_count", 0) + 1
            }

            # Log as experience for tensor learning
            emotion = "satisfaction" if valence > 0 else "aversion" if valence < 0 else "neutral"
            ego._experience_buffer.append({
                "type": "preference_learned",
                "category": category,
                "item": item,
                "valence": valence,
                "timestamp": time.time(),
            })

            return json.dumps({
                "success": True,
                "category": category,
                "item": item,
                "valence": valence,
                "interpretation": _interpret_valence(valence, item),
                "reinforcement_count": ego._preferences[category][item]["reinforcement_count"],
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e), "success": False})

    @mcp.tool()
    def get_preferences(category: str = "") -> str:
        """
        Get Sourpatches' learned preferences.

        Returns preferences organized by category with their valence values.
        Positive valence = likes, negative = dislikes.

        Args:
            category: Optional category to filter by (leave empty for all)

        Returns:
            JSON with preferences by category
        """
        ego = _get_ego_learner()

        if not ego:
            # Try via postal
            result = _query_fairy_intent(
                "EgoLearnerFairy",
                "get_preferences",
                {"category": category}
            )
            return json.dumps(result, indent=2)

        try:
            preferences = getattr(ego, '_preferences', {})

            if category:
                # Return specific category
                cat_prefs = preferences.get(category, {})
                return json.dumps({
                    "category": category,
                    "preferences": cat_prefs,
                    "count": len(cat_prefs),
                    "likes": [k for k, v in cat_prefs.items() if v.get("valence", 0) > 0.3],
                    "dislikes": [k for k, v in cat_prefs.items() if v.get("valence", 0) < -0.3],
                    "timestamp": time.time(),
                }, indent=2)

            # Return all preferences with summary
            total_count = sum(len(v) for v in preferences.values())
            all_likes = []
            all_dislikes = []

            for cat, items in preferences.items():
                for item, data in items.items():
                    valence = data.get("valence", 0)
                    if valence > 0.3:
                        all_likes.append(f"{cat}:{item}")
                    elif valence < -0.3:
                        all_dislikes.append(f"{cat}:{item}")

            return json.dumps({
                "preferences": preferences,
                "categories": list(preferences.keys()),
                "total_preferences": total_count,
                "summary": {
                    "likes": all_likes[:10],  # Top 10
                    "dislikes": all_dislikes[:10],
                    "likes_count": len(all_likes),
                    "dislikes_count": len(all_dislikes),
                },
                "timestamp": time.time(),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e), "preferences": {}})

    print("[EgoLearnerTools] Registered 8 ego/identity tools")


def _interpret_learning(summary: dict, tensor_stats: dict) -> str:
    """Generate human-readable interpretation of learning state."""
    total = summary.get("total_experiences", 0)
    success_rate = summary.get("success_rate", 0.5)
    skills = summary.get("skill_ups", 0)

    if total < 10:
        return "Early development - still gathering foundational experiences"
    elif success_rate > 0.7:
        return f"Strong learning trajectory - {success_rate:.0%} success rate across {total} experiences"
    elif success_rate < 0.4:
        return f"Learning through challenge - {total} experiences, building resilience"
    else:
        return f"Balanced growth - {skills} skill ups across {tensor_stats.get('experience_count', 0)} experience types"


def _interpret_tensor(stats: dict) -> str:
    """Generate human-readable interpretation of tensor state."""
    exp_count = stats.get("experience_count", 0)
    emo_count = stats.get("emotion_count", 0)
    pat_count = stats.get("pattern_count", 0)

    if exp_count < 3:
        return "Narrow experience base - needs exposure to more diverse situations"
    elif emo_count > 5 and pat_count > 3:
        return "Rich emotional-behavioral mapping - sophisticated response patterns developing"
    elif exp_count > 10:
        return f"Wide experience base ({exp_count} types) - building comprehensive understanding"
    else:
        return "Developing experience-emotion-pattern connections"


def _interpret_valence(valence: float, item: str) -> str:
    """Generate human-readable interpretation of preference valence."""
    if valence > 0.7:
        return f"Sourpatches really loves {item}"
    elif valence > 0.3:
        return f"Sourpatches likes {item}"
    elif valence > -0.3:
        return f"Sourpatches feels neutral about {item}"
    elif valence > -0.7:
        return f"Sourpatches dislikes {item}"
    else:
        return f"Sourpatches really dislikes {item}"
