# ════════════════════════════════════════════════════════════════════════════════
# SKILL TOOLS - MCP tools for skill/achievement tracking
# ════════════════════════════════════════════════════════════════════════════════
#
# Like Dungeon Crawler Carl's stat screen but for fairies.
# Track skills, achievements, XP, levels.
#
# ════════════════════════════════════════════════════════════════════════════════

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any

_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root))


def register_skill_tools(mcp):
    """Register skill tracking tools with MCP."""

    @mcp.tool()
    def skill_use(skill_id: str, fairy_name: str = "ClaudeFairy", 
                  success: bool = True) -> str:
        """
        Record using a skill. Awards XP and checks achievements.
        
        Call this EVERY TIME a fairy does something!
        
        Common skill_ids:
        - motor.mouse_move, motor.mouse_click, motor.keyboard_type
        - perception.screenshot, perception.file_read, perception.image_analysis
        - tool.mcp_basic, tool.mcp_file_ops, tool.shell_basic
        - coding.python_syntax, coding.debugging, coding.fairy_pattern
        - memory.store, memory.recall, memory.search
        - embodiment.body_awareness, embodiment.emotion_sensing
        
        Args:
            skill_id: The skill being used
            fairy_name: Which fairy is using it (default ClaudeFairy)
            success: Whether the skill use succeeded
            
        Returns:
            JSON with XP gained, level ups, and achievements unlocked
        """
        try:
            from fairies.P30_Cognition.cognition.skill_system import get_skill_profile
            
            profile = get_skill_profile(fairy_name)
            result = profile.use_skill(skill_id, success)
            
            # Add notification if leveled up
            if result.get("leveled_up"):
                result["notification"] = f"LEVEL UP! {skill_id} is now level {result['new_level']}"
            
            # Add notification for achievements
            if result.get("achievements_unlocked"):
                result["notification"] = f"ACHIEVEMENT UNLOCKED: {', '.join(result['achievements_unlocked'])}"
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def skill_check(skill_id: str, fairy_name: str = "ClaudeFairy") -> str:
        """
        Check if a fairy has a skill and at what level.
        
        Use this BEFORE teaching something - if already learned, skip!
        
        Args:
            skill_id: The skill to check
            fairy_name: Which fairy
            
        Returns:
            JSON with skill level and info, or null if not learned
        """
        try:
            from fairies.P30_Cognition.cognition.skill_system import get_skill_profile
            
            profile = get_skill_profile(fairy_name)
            skill = profile.get_skill(skill_id)
            
            if skill:
                return json.dumps({
                    "skill": skill,
                    "is_learned": skill["level"] > 0,
                    "recommendation": (
                        "SKIP - already learned" if skill["level"] > 0 
                        else "OK to teach"
                    ),
                }, indent=2)
            else:
                return json.dumps({"error": f"Unknown skill: {skill_id}"})
                
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def character_sheet(fairy_name: str = "ClaudeFairy") -> str:
        """
        Get full character sheet for a fairy - like opening the stat screen.
        
        Shows:
        - Overall level and XP
        - Title
        - Skills by category with levels
        - Top 5 skills
        - Achievements (unlocked count, recent)
        - Next achievable achievements with progress
        
        Args:
            fairy_name: Which fairy's sheet to get
            
        Returns:
            JSON character sheet
        """
        try:
            from fairies.P30_Cognition.cognition.skill_system import get_skill_profile
            
            profile = get_skill_profile(fairy_name)
            sheet = profile.get_character_sheet()
            
            return json.dumps(sheet, indent=2, default=str)
            
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def achievements_list(fairy_name: str = "ClaudeFairy", 
                         show_locked: bool = True) -> str:
        """
        List all achievements for a fairy.
        
        Args:
            fairy_name: Which fairy
            show_locked: Include locked achievements too
            
        Returns:
            JSON list of achievements
        """
        try:
            from fairies.P30_Cognition.cognition.skill_system import get_skill_profile
            
            profile = get_skill_profile(fairy_name)
            
            result = {
                "unlocked": profile.get_unlocked_achievements(),
                "count_unlocked": len(profile.get_unlocked_achievements()),
                "count_total": len(profile.achievements),
            }
            
            if show_locked:
                result["locked"] = profile.get_locked_achievements()
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def skills_by_category(category: str, fairy_name: str = "ClaudeFairy") -> str:
        """
        List all skills in a category.
        
        Categories: motor, perception, tool_use, coding, memory, 
                   communication, reasoning, embodiment
        
        Args:
            category: The category to list
            fairy_name: Which fairy
            
        Returns:
            JSON list of skills in category
        """
        try:
            from fairies.P30_Cognition.cognition.skill_system import (
                get_skill_profile, SkillCategory
            )
            
            profile = get_skill_profile(fairy_name)
            
            try:
                cat = SkillCategory(category)
            except ValueError:
                return json.dumps({
                    "error": f"Unknown category: {category}",
                    "valid_categories": [c.value for c in SkillCategory],
                })
            
            skills = profile.get_skills_by_category(cat)
            
            return json.dumps({
                "category": category,
                "skills": skills,
                "trained_count": sum(1 for s in skills if s["level"] > 0),
                "total_count": len(skills),
            }, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def set_fairy_title(title: str, fairy_name: str = "ClaudeFairy") -> str:
        """
        Set a fairy's displayed title (must be unlocked via achievement).
        
        Available titles come from achievements like "Mouse Master", "Bug Slayer", etc.
        
        Args:
            title: The title to use
            fairy_name: Which fairy
            
        Returns:
            JSON with success/failure
        """
        try:
            from fairies.P30_Cognition.cognition.skill_system import get_skill_profile
            
            profile = get_skill_profile(fairy_name)
            
            available = profile.get_available_titles()
            if title not in available:
                return json.dumps({
                    "error": f"Title '{title}' not unlocked",
                    "available_titles": available,
                })
            
            profile.set_title(title)
            
            return json.dumps({
                "success": True,
                "title": title,
                "message": f"{fairy_name} is now known as '{title}'",
            }, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def what_skill_is_this(action: str) -> str:
        """
        Map an action/tool name to its skill.
        
        Useful to know which skill to record when doing something.
        
        Args:
            action: The action or tool name (e.g., "screenshot", "click")
            
        Returns:
            JSON with the skill_id to use
        """
        try:
            from fairies.P30_Cognition.cognition.skill_system import (
                skill_for_action, ACTION_TO_SKILL
            )
            
            skill_id = skill_for_action(action)
            
            if skill_id:
                return json.dumps({
                    "action": action,
                    "skill_id": skill_id,
                    "usage": f"Call skill_use('{skill_id}') after using {action}",
                }, indent=2)
            else:
                return json.dumps({
                    "action": action,
                    "skill_id": None,
                    "hint": "Unknown action. Known actions:",
                    "known_actions": list(ACTION_TO_SKILL.keys()),
                })
                
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def skill_leaderboard() -> str:
        """
        Get leaderboard of all fairies by level/XP.
        
        Returns:
            JSON leaderboard
        """
        try:
            from fairies.P30_Cognition.cognition.skill_system import _skill_profiles, get_skill_profile
            
            # Also check for saved profiles on disk
            state_dir = _project_root / "state" / "fairy_skills"
            if state_dir.exists():
                for f in state_dir.glob("*_skills.json"):
                    fairy_name = f.stem.replace("_skills", "")
                    get_skill_profile(fairy_name)  # Load it
            
            leaderboard = []
            for name, profile in _skill_profiles.items():
                leaderboard.append({
                    "fairy_name": name,
                    "level": profile.level,
                    "total_xp": profile.total_xp,
                    "title": profile.title or "Apprentice",
                    "achievements_unlocked": len([a for a in profile.achievements.values() if a.unlocked]),
                    "skills_trained": sum(1 for s in profile.skills.values() if s.level > 0),
                })
            
            leaderboard.sort(key=lambda x: x["total_xp"], reverse=True)
            
            return json.dumps({
                "leaderboard": leaderboard,
                "count": len(leaderboard),
            }, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def should_i_learn(topic: str, fairy_name: str = "ClaudeFairy") -> str:
        """
        Check if a fairy should learn about something.
        
        Prevents repetitive teaching by checking existing skills/achievements.
        
        Args:
            topic: What we're thinking of teaching (e.g., "mouse basics", "screenshot")
            fairy_name: Which fairy
            
        Returns:
            JSON with recommendation
        """
        try:
            from fairies.P30_Cognition.cognition.skill_system import get_skill_profile
            
            profile = get_skill_profile(fairy_name)
            
            # Map common topics to skills
            topic_to_skills = {
                "mouse basics": ["motor.mouse_move", "motor.mouse_click"],
                "mouse": ["motor.mouse_move", "motor.mouse_click", "motor.scroll"],
                "keyboard": ["motor.keyboard_type", "motor.keyboard_shortcut"],
                "screenshot": ["perception.screenshot", "perception.image_analysis"],
                "file reading": ["perception.file_read", "perception.code_comprehension"],
                "coding": ["coding.python_syntax", "coding.python_classes"],
                "debugging": ["coding.debugging"],
                "memory": ["memory.store", "memory.recall", "memory.search"],
                "embodiment": ["embodiment.body_awareness", "embodiment.emotion_sensing"],
                "tools": ["tool.mcp_basic", "tool.mcp_file_ops"],
            }
            
            topic_lower = topic.lower()
            relevant_skills = []
            
            # Find matching skills
            for key, skills in topic_to_skills.items():
                if key in topic_lower:
                    relevant_skills.extend(skills)
            
            # If no mapping, try direct skill lookup
            if not relevant_skills:
                for skill_id in profile.skills.keys():
                    if topic_lower in skill_id.lower():
                        relevant_skills.append(skill_id)
            
            if not relevant_skills:
                return json.dumps({
                    "topic": topic,
                    "recommendation": "TEACH",
                    "reason": "No matching skills found - this appears to be new content",
                    "confidence": 0.5,
                })
            
            # Check skill levels
            skill_info = []
            for skill_id in relevant_skills:
                skill = profile.get_skill(skill_id)
                if skill:
                    skill_info.append({
                        "skill_id": skill_id,
                        "level": skill["level"],
                        "times_used": skill["times_used"],
                    })
            
            # Make recommendation
            avg_level = sum(s["level"] for s in skill_info) / len(skill_info) if skill_info else 0
            
            if avg_level >= 3:
                recommendation = "SKIP"
                reason = f"Already proficient (avg level {avg_level:.1f})"
            elif avg_level >= 1:
                recommendation = "REVIEW"
                reason = f"Basic understanding (avg level {avg_level:.1f}) - maybe advanced topics?"
            else:
                recommendation = "TEACH"
                reason = "Not yet learned"
            
            return json.dumps({
                "topic": topic,
                "relevant_skills": skill_info,
                "recommendation": recommendation,
                "reason": reason,
                "avg_level": round(avg_level, 1),
            }, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})

    print("[SkillTools] Registered skill tracking tools")
