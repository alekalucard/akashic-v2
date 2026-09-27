# ============================================================================
# BEHAVIOR TREE TOOLS - Riftbreaker-Inspired Visualization
# ============================================================================
#
# Generates Mermaid flowchart diagrams showing the interconnected flow of:
#   Drives → Wants → Goals → Interests → Actions → Skills → Achievements
#
# Inspired by Riftbreaker's mission behavior tree:
# - Phase-based progression with prerequisite chains
# - Parallel tracks for different behavior categories
# - Color-coded node types (drives, goals, interests, skills, etc.)
# - Priority interrupts and convergent milestones
#
# Each diagram is a LIVE snapshot of the system state.
#
# LINKED TO: AutonomyFairy, GoalSchedulerFairy, InterestGenerator,
#            SkillSystem, EgoLearner, SatisfactionTracker
# ============================================================================

from __future__ import annotations

import sys
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

# Add paths
_project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / "fairies"))


def _resolve_state_path(relative_path: str) -> Optional[Path]:
    """Resolve a state path, checking both project root and fairies/ CWD locations.

    mcp_bootstrap.py sets CWD to fairies/, so some fairies write state files
    to fairies/state/... instead of state/... at the project root. This helper
    finds whichever copy is freshest.
    """
    path_root = _project_root / relative_path
    path_fairy = _project_root / "fairies" / relative_path

    candidates = []
    for p in (path_root, path_fairy):
        if p.exists():
            candidates.append((p, p.stat().st_mtime))

    if not candidates:
        return None

    return max(candidates, key=lambda x: x[1])[0]


def _resolve_state_dir(relative_dir: str) -> Optional[Path]:
    """Resolve a state directory, checking both project root and fairies/ CWD locations.

    Returns whichever directory exists and has the most recently modified files.
    """
    dir_root = _project_root / relative_dir
    dir_fairy = _project_root / "fairies" / relative_dir

    candidates = []
    for d in (dir_root, dir_fairy):
        if d.exists() and d.is_dir():
            # Use the directory's own mtime as a proxy
            try:
                # Find the most recent file in the directory
                files = list(d.glob("*.json"))
                if files:
                    newest = max(f.stat().st_mtime for f in files)
                    candidates.append((d, newest))
                else:
                    candidates.append((d, d.stat().st_mtime))
            except Exception:
                candidates.append((d, 0))

    if not candidates:
        return None

    return max(candidates, key=lambda x: x[1])[0]


# ============================================================================
# STATE COLLECTION - Gather live data from all systems
# ============================================================================

def _get_tunnel():
    """Get postal tunnel for querying server-side fairies."""
    try:
        from fairies.P00_Autonomic.nervous_system.mcp_postal_bridge import get_tunnel
        return get_tunnel()
    except Exception:
        return None


def _read_state_file(relative_path: str, max_age: float = 0) -> Optional[dict]:
    """Read a JSON state file if it exists.

    Args:
        relative_path: Path relative to project root.
        max_age: Maximum age in seconds (0 = no limit).
                 State files are persisted snapshots — they represent the
                 LAST KNOWN STATE, not a real-time feed. A 14-hour-old
                 ego_learner state is still the current identity.

    Note:
        CWD mismatch fix: mcp_bootstrap.py sets CWD to fairies/, so fairies
        using relative paths write to fairies/state/... not state/... at the
        project root. We check BOTH locations and use whichever is freshest.
    """
    try:
        # Two candidate locations — some fairies write to CWD-relative (fairies/state/),
        # others write to project root (state/) via AKASHIC_ROOT or Path(__file__).
        path_root = _project_root / relative_path
        path_fairy = _project_root / "fairies" / relative_path

        # Pick the best candidate: prefer whichever exists and is most recent
        candidates = []
        for p in (path_root, path_fairy):
            if p.exists():
                candidates.append((p, p.stat().st_mtime))

        if not candidates:
            return None

        # Use the most recently modified file
        path, mtime = max(candidates, key=lambda x: x[1])

        if max_age > 0:
            age = time.time() - mtime
            if age > max_age:
                return None

        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _query_intent(fairy_name: str, intent: str, payload: dict = None,
                  timeout: float = 5.0) -> Optional[dict]:
    """Query a fairy via postal tunnel intent."""
    tunnel = _get_tunnel()
    if not tunnel or not getattr(tunnel, 'connected', False):
        return None
    try:
        result = tunnel.request(
            f"intent.{fairy_name}.{intent}",
            payload or {},
            timeout=timeout
        )
        return result if isinstance(result, dict) else None
    except Exception:
        return None


def collect_drive_state() -> List[dict]:
    """Collect current drive states from AutonomyFairy."""
    # Try state file first (most reliable for MCP subprocess)
    # Autonomy state is written every ~30s, so 120s freshness is safe
    state = _read_state_file("state/consciousness/autonomy_state.json", max_age=120)
    if state:
        drives = state.get("drives", state.get("drive_states", {}))
        if isinstance(drives, dict):
            # Filter: skip "positive.*" and "pain.*" prefixed duplicates
            # Keep only the base drive names (isolation, curiosity, etc.)
            result = []
            for name, v in drives.items():
                if name in ("unknown", "type"):
                    continue
                if name.startswith("positive.") or name.startswith("pain."):
                    continue  # Skip prefixed duplicates
                intensity = float(v) if isinstance(v, (int, float)) else (
                    v.get("intensity", 0.5) if isinstance(v, dict) else 0.5)
                result.append({"name": name, "intensity": intensity})
            return result
    return []


def collect_goal_state() -> List[dict]:
    """Collect active goals from GoalSchedulerFairy."""
    # Try postal tunnel intent first (live data)
    result = _query_intent("GoalSchedulerFairy", "get_active_goals")
    if result and "goals" in result:
        return result["goals"][:15]

    # GoalScheduler persists active queue to active_goals.json (same file dashboard reads)
    for path in [
        "state/consciousness/active_goals.json",
        "state/consciousness/goal_queue.json",  # Legacy fallback
    ]:
        state = _read_state_file(path)
        if state and "goals" in state:
            return state["goals"][:15]

    return []


def collect_interest_state() -> List[dict]:
    """Collect current interests from InterestSchedulerFairy."""
    # Try postal tunnel intent (live data)
    result = _query_intent("InterestSchedulerFairy", "get_interests")
    if result and "interests" in result:
        return result["interests"][:10]

    result = _query_intent("UnconsciousMindFairy", "get_interests")
    if result and "interests" in result:
        return result["interests"][:10]

    # InterestSchedulerFairy persists to its own directory
    state = _read_state_file(
        "fairies/P30_Cognition/cognition/interest_state.json"
    )
    if state and "interests" in state:
        # interest_state stores as dict keyed by topic name, convert to list
        interests = state["interests"]
        if isinstance(interests, dict):
            items = []
            for topic, data in interests.items():
                if isinstance(data, dict):
                    items.append(data)
            # Sort by strength descending
            items.sort(key=lambda x: x.get("strength", 0), reverse=True)
            # Filter to interests with meaningful strength
            items = [i for i in items if i.get("strength", 0) > 0.05
                     or i.get("times_expressed", 0) > 5]
            return items[:10]
        elif isinstance(interests, list):
            return interests[:10]

    # Fallback path (legacy)
    state = _read_state_file("state/consciousness/interests.json")
    if state and "interests" in state:
        return state["interests"][:10]

    return []


def collect_skill_state() -> List[dict]:
    """Collect top skills with highest level/XP."""
    try:
        # CWD fix: check both project root and fairies/ locations
        skills_dir = _resolve_state_dir("state/fairy_skills")
        if not skills_dir:
            return []

        # Read Sourpatches character sheet (primary)
        # Files may be named with or without _skills suffix
        for candidate in [
            "SourpatchesFairy_skills.json",  # Current naming convention
            "SourpatchesFairy.json",          # Legacy naming
            "ClaudeFairy_skills.json",
            "ClaudeFairy.json",
        ]:
            path = skills_dir / candidate
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                skills = data.get("skills", {})
                # Sort by XP (descending), filter out unused skills
                sorted_skills = sorted(
                    [{"id": k, **v} for k, v in skills.items()
                     if v.get("xp", 0) > 0 or v.get("times_used", 0) > 0],
                    key=lambda s: (s.get("level", 0), s.get("xp", 0)),
                    reverse=True
                )
                return sorted_skills[:12]
    except Exception:
        pass
    return []


def collect_identity_traits() -> dict:
    """Collect identity traits from EgoLearner."""
    try:
        # CWD fix: check both project root and fairies/ locations
        path = _resolve_state_path("state/ego_learner_state.json")
        if path:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("traits", data.get("identity_traits", {}))
    except Exception:
        pass
    return {}


def collect_achievements() -> List[dict]:
    """Collect unlocked achievements."""
    try:
        # CWD fix: check both project root and fairies/ locations
        skills_dir = _resolve_state_dir("state/fairy_skills")
        if not skills_dir:
            return []

        for candidate in [
            "SourpatchesFairy_skills.json",
            "SourpatchesFairy.json",
            "ClaudeFairy_skills.json",
            "ClaudeFairy.json",
        ]:
            path = skills_dir / candidate
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                achievements = data.get("achievements", {})
                unlocked = [
                    {"id": k, **v}
                    for k, v in achievements.items()
                    if v.get("unlocked", False)
                ]
                return unlocked[:10]
    except Exception:
        pass
    return []


def collect_fairy_work() -> List[dict]:
    """Collect recent fairy task activity from Part D pipeline."""
    result = _query_intent("AutopilotFairy", "get_recent_actions")
    if result and "actions" in result:
        return result["actions"][:8]
    return []


# ============================================================================
# MERMAID GENERATION - Riftbreaker-Style Behavior Tree
# ============================================================================

def _safe_id(text: str) -> str:
    """Generate a safe Mermaid node ID from text."""
    # Hash to avoid special characters
    h = hashlib.md5(text.encode()).hexdigest()[:8]
    # Also make a readable prefix
    prefix = "".join(c for c in text[:12] if c.isalnum() or c == "_")
    return f"{prefix}_{h}" if prefix else f"n_{h}"


def _truncate(text: str, max_len: int = 30) -> str:
    """Truncate text for node labels."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def _intensity_bar(value: float, width: int = 5) -> str:
    """Create a visual intensity bar using Mermaid-safe chars."""
    pct = int(value * 100)
    return f"{pct}%"


def generate_behavior_tree_mermaid(
    include_drives: bool = True,
    include_goals: bool = True,
    include_interests: bool = True,
    include_skills: bool = True,
    include_traits: bool = True,
    include_achievements: bool = True,
    include_fairy_work: bool = True,
) -> str:
    """
    Generate a Riftbreaker-style Mermaid behavior tree from live system state.

    The tree flows TOP-DOWN:
        Drives (root causes)
          → Wants (felt desires)
            → Goals (actionable items)
              → Active Tasks (fairy work)
        Interests (parallel curiosity track)
          → Exploration / Serendipity
        Skills (progression track)
          → Achievements (milestones)
        Identity Traits (foundation layer)
          → Needs (deficiencies) / Strengths

    Color coding (matching Riftbreaker):
    - 🔴 Red: Pain/urgent drives (high intensity)
    - 🟡 Yellow: Active goals/wants
    - 🟢 Green: Completed/satisfied
    - 🔵 Blue: Interests/exploration
    - 🟣 Purple: Skills/achievements
    - ⚪ Gray: Inactive/low-priority

    Returns:
        Mermaid flowchart code string
    """
    lines = ["graph TD"]
    lines.append("")
    lines.append("    %% Riftbreaker-style behavior tree — Live System State")
    lines.append(f"    %% Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # ──────────────────────────────────────────────────────────
    # STYLE DEFINITIONS
    # ──────────────────────────────────────────────────────────
    lines.append("    %% Style classes")
    lines.append("    classDef drive fill:#dc2626,stroke:#991b1b,color:#fff,stroke-width:2px")
    lines.append("    classDef drive_low fill:#f87171,stroke:#dc2626,color:#fff")
    lines.append("    classDef want fill:#f59e0b,stroke:#d97706,color:#000,stroke-width:2px")
    lines.append("    classDef goal_active fill:#eab308,stroke:#ca8a04,color:#000,stroke-width:2px")
    lines.append("    classDef goal_pending fill:#fde68a,stroke:#f59e0b,color:#000")
    lines.append("    classDef goal_done fill:#22c55e,stroke:#16a34a,color:#fff")
    lines.append("    classDef interest fill:#3b82f6,stroke:#2563eb,color:#fff")
    lines.append("    classDef interest_wonder fill:#60a5fa,stroke:#3b82f6,color:#fff")
    lines.append("    classDef interest_curiosity fill:#06b6d4,stroke:#0891b2,color:#fff")
    lines.append("    classDef interest_exploration fill:#10b981,stroke:#059669,color:#fff")
    lines.append("    classDef interest_observation fill:#f59e0b,stroke:#d97706,color:#fff")
    lines.append("    classDef interest_connection fill:#ec4899,stroke:#db2777,color:#fff")
    lines.append("    classDef skill fill:#8b5cf6,stroke:#7c3aed,color:#fff")
    lines.append("    classDef achievement fill:#a855f7,stroke:#7c3aed,color:#fff,stroke-width:3px")
    lines.append("    classDef trait_need fill:#ef4444,stroke:#dc2626,color:#fff")
    lines.append("    classDef trait_strong fill:#10b981,stroke:#059669,color:#fff")
    lines.append("    classDef trait_ok fill:#6b7280,stroke:#4b5563,color:#fff")
    lines.append("    classDef fairy_task fill:#f472b6,stroke:#ec4899,color:#000")
    lines.append("    classDef hub fill:#1e293b,stroke:#0f172a,color:#fff,stroke-width:3px")
    lines.append("")

    node_classes = {}  # node_id → class name
    connections = []  # (from, to, label)

    # ──────────────────────────────────────────────────────────
    # LAYER 1: DRIVES (Root Causes — Riftbreaker "Phase 1")
    # ──────────────────────────────────────────────────────────
    if include_drives:
        drives = collect_drive_state()
        if drives:
            lines.append("    subgraph DRIVES[\"DRIVES - Root Causes\"]")
            lines.append("        direction LR")
            for d in sorted(drives, key=lambda x: x.get("intensity", 0), reverse=True):
                name = d["name"]
                intensity = d.get("intensity", 0.5)
                nid = _safe_id(f"drive_{name}")
                bar = _intensity_bar(intensity)
                label = f"{name} {bar}"
                lines.append(f"        {nid}[\"{label}\"]")
                if intensity > 0.6:
                    node_classes[nid] = "drive"
                else:
                    node_classes[nid] = "drive_low"
            lines.append("    end")
            lines.append("")

    # ──────────────────────────────────────────────────────────
    # LAYER 2: GOALS (Active Pursuits — Riftbreaker "Phase 2-3")
    # ──────────────────────────────────────────────────────────
    if include_goals:
        goals = collect_goal_state()
        if goals:
            lines.append("    subgraph GOALS[\"GOALS - Active Pursuits\"]")
            lines.append("        direction LR")
            for g in goals[:12]:
                name = g.get("name", g.get("goal_name", "unnamed"))
                status = g.get("status", "pending")
                nudge = g.get("nudge_strength", 0)
                target = g.get("target_fairy", "")
                nid = _safe_id(f"goal_{name}")
                label = _truncate(name, 25)
                if target:
                    label += f"<br/>→ {target[:15]}"
                if nudge > 0:
                    label += f"<br/>nudge:{nudge:.2f}"
                lines.append(f"        {nid}[\"{label}\"]")
                if status == "done":
                    node_classes[nid] = "goal_done"
                elif status == "active":
                    node_classes[nid] = "goal_active"
                else:
                    node_classes[nid] = "goal_pending"

                # Connect drive to goal if source indicates drive
                source = g.get("source", "")
                if source in ("drive", "umf_fairy_work", "pain"):
                    # Try to connect to a matching drive
                    for d in drives if include_drives and 'drives' in dir() else []:
                        if d["name"] in name.lower() or d.get("intensity", 0) > 0.5:
                            did = _safe_id(f"drive_{d['name']}")
                            connections.append((did, nid, source[:10]))
                            break
            lines.append("    end")
            lines.append("")

            # Connect drives subgraph to goals subgraph
            if include_drives and drives:
                lines.append("    DRIVES --> GOALS")

    # ──────────────────────────────────────────────────────────
    # LAYER 3: INTERESTS (Parallel Curiosity Track)
    # ──────────────────────────────────────────────────────────
    if include_interests:
        interests = collect_interest_state()
        if interests:
            lines.append("    subgraph INTERESTS[\"INTERESTS - Curiosity Track\"]")
            lines.append("        direction LR")
            for i in interests[:8]:
                content = i.get("content", i.get("topic", ""))
                itype = i.get("interest_type", i.get("type", "wonder"))
                urgency = i.get("urgency", i.get("effective_urgency", 0.5))
                nid = _safe_id(f"int_{content[:20]}")
                label = _truncate(content, 28)
                label += f"<br/>{itype}"
                lines.append(f"        {nid}[\"{label}\"]")
                # FIX 2026-03-25 (Nous + Ace): Type-specific colors
                _type_class = f"interest_{itype}"
                if _type_class in ("interest_anomaly", "interest_pattern"):
                    node_classes[nid] = "interest"
                elif _type_class in ("interest_curiosity", "interest_exploration",
                                      "interest_observation", "interest_connection"):
                    node_classes[nid] = _type_class
                else:
                    node_classes[nid] = "interest_wonder"
            lines.append("    end")
            lines.append("")

            # Interests can generate goals
            if include_goals and goals:
                lines.append("    INTERESTS -.->|generates| GOALS")

    # ──────────────────────────────────────────────────────────
    # LAYER 4: FAIRY WORK (Part D Pipeline Output)
    # ──────────────────────────────────────────────────────────
    if include_fairy_work:
        fairy_tasks = collect_fairy_work()
        if fairy_tasks:
            lines.append("    subgraph FAIRY_WORK[\"FAIRY WORK - Active Tasks\"]")
            lines.append("        direction LR")
            for t in fairy_tasks:
                fairy = t.get("target_fairy", t.get("fairy", "unknown"))
                action = t.get("action", "task")
                nid = _safe_id(f"ftask_{fairy}_{action}")
                label = f"{fairy[:18]}<br/>{action}"
                lines.append(f"        {nid}[\"{label}\"]")
                node_classes[nid] = "fairy_task"
            lines.append("    end")
            lines.append("")

            if include_goals:
                lines.append("    GOALS -->|dispatches| FAIRY_WORK")

    # ──────────────────────────────────────────────────────────
    # LAYER 5: SKILLS (Progression Track — Riftbreaker "Unlocks")
    # ──────────────────────────────────────────────────────────
    if include_skills:
        skills = collect_skill_state()
        if skills:
            lines.append("    subgraph SKILLS[\"SKILLS - Progression\"]")
            lines.append("        direction LR")
            for s in skills[:10]:
                sid = s.get("id", s.get("name", ""))
                level = s.get("level", 0)
                xp = s.get("xp", 0)
                nid = _safe_id(f"skill_{sid}")
                name = sid.split(".")[-1] if "." in sid else sid
                label = f"{name}<br/>Lv.{level} ({xp}xp)"
                lines.append(f"        {nid}[\"{label}\"]")
                node_classes[nid] = "skill"
            lines.append("    end")
            lines.append("")

            # Skills are fed by fairy work
            if include_fairy_work and fairy_tasks:
                lines.append("    FAIRY_WORK -->|trains| SKILLS")
            elif include_goals:
                lines.append("    GOALS -->|trains| SKILLS")

    # ──────────────────────────────────────────────────────────
    # LAYER 6: ACHIEVEMENTS (Milestone Markers)
    # ──────────────────────────────────────────────────────────
    if include_achievements:
        achievements = collect_achievements()
        if achievements:
            lines.append("    subgraph ACHIEVEMENTS[\"ACHIEVEMENTS - Milestones\"]")
            lines.append("        direction LR")
            for a in achievements:
                name = a.get("name", a.get("id", ""))
                nid = _safe_id(f"ach_{name}")
                label = _truncate(name, 25)
                hexagon = "{" + "{" + '"' + label + '"' + "}" + "}"
                lines.append(f"        {nid}{hexagon}")  # Hexagon shape
                node_classes[nid] = "achievement"
            lines.append("    end")
            lines.append("")

            if include_skills and skills:
                lines.append("    SKILLS -->|unlocks| ACHIEVEMENTS")

    # ──────────────────────────────────────────────────────────
    # LAYER 7: IDENTITY TRAITS (Foundation — Riftbreaker "Base")
    # ──────────────────────────────────────────────────────────
    if include_traits:
        traits = collect_identity_traits()
        if traits:
            lines.append("    subgraph IDENTITY[\"IDENTITY - Foundation Traits\"]")
            lines.append("        direction LR")
            for name, level in sorted(traits.items(),
                                       key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0.5):
                if not isinstance(level, (int, float)):
                    continue
                nid = _safe_id(f"trait_{name}")
                bar = _intensity_bar(level)
                label = f"{name} {bar}"
                lines.append(f"        {nid}[\"{label}\"]")
                if level < 0.4:
                    node_classes[nid] = "trait_need"
                elif level > 0.6:
                    node_classes[nid] = "trait_strong"
                else:
                    node_classes[nid] = "trait_ok"
            lines.append("    end")
            lines.append("")

            # Traits are evolved by achievements and goals
            if include_achievements and achievements:
                lines.append("    ACHIEVEMENTS -->|evolves| IDENTITY")
            elif include_skills and skills:
                lines.append("    SKILLS -->|evolves| IDENTITY")

            # Low traits generate drives (feedback loop)
            if include_drives and drives:
                lines.append("    IDENTITY -.->|needs generate| DRIVES")

    lines.append("")

    # ──────────────────────────────────────────────────────────
    # CROSS-CONNECTIONS
    # ──────────────────────────────────────────────────────────
    for src, tgt, label in connections:
        lines.append(f"    {src} -->|{label}| {tgt}")

    lines.append("")

    # ──────────────────────────────────────────────────────────
    # APPLY STYLES
    # ──────────────────────────────────────────────────────────
    for nid, cls in node_classes.items():
        lines.append(f"    class {nid} {cls}")

    return "\n".join(lines)


def generate_compact_tree() -> str:
    """Generate a compact summary version with just the key numbers."""
    drives = collect_drive_state()
    goals = collect_goal_state()
    interests = collect_interest_state()
    skills = collect_skill_state()
    traits = collect_identity_traits()
    achievements = collect_achievements()

    top_drive = max(drives, key=lambda d: d.get("intensity", 0))["name"] if drives else "none"
    active_goals = len([g for g in goals if g.get("status") in ("active", "pending")])
    top_interest = (interests[0].get("content", "") or interests[0].get("topic", "none"))[:30] if interests else "none"
    total_skills = len(skills)
    total_achievements = len(achievements)

    needs = [k for k, v in traits.items()
             if isinstance(v, (int, float)) and v < 0.4]
    strengths = [k for k, v in traits.items()
                 if isinstance(v, (int, float)) and v > 0.6]

    lines = ["graph LR"]
    lines.append(f"    D[\"Drives<br/>{len(drives)} active<br/>top: {top_drive}\"]")
    lines.append(f"    G[\"Goals<br/>{active_goals} active\"]")
    lines.append(f"    I[\"Interests<br/>{len(interests)} live<br/>{top_interest}\"]")
    lines.append(f"    S[\"Skills<br/>{total_skills} tracked\"]")
    lines.append(f"    A[\"Achievements<br/>{total_achievements} unlocked\"]")

    needs_str = ", ".join(needs[:3]) if needs else "none"
    strengths_str = ", ".join(strengths[:3]) if strengths else "none"
    lines.append(f"    T[\"Identity<br/>needs: {needs_str}<br/>strengths: {strengths_str}\"]")

    lines.append("    D --> G")
    lines.append("    I -.-> G")
    lines.append("    G --> S")
    lines.append("    S --> A")
    lines.append("    A --> T")
    lines.append("    T -.->|feedback| D")

    lines.append("    classDef drive fill:#dc2626,color:#fff")
    lines.append("    classDef goal fill:#eab308,color:#000")
    lines.append("    classDef interest fill:#3b82f6,color:#fff")
    lines.append("    classDef skill fill:#8b5cf6,color:#fff")
    lines.append("    classDef achievement fill:#a855f7,color:#fff")
    lines.append("    classDef identity fill:#10b981,color:#fff")
    lines.append("    class D drive")
    lines.append("    class G goal")
    lines.append("    class I interest")
    lines.append("    class S skill")
    lines.append("    class A achievement")
    lines.append("    class T identity")

    return "\n".join(lines)


def get_behavior_tree_data() -> dict:
    """Get all behavior tree data as structured JSON for dashboard."""
    return {
        "timestamp": time.time(),
        "drives": collect_drive_state(),
        "goals": collect_goal_state(),
        "interests": collect_interest_state(),
        "skills": collect_skill_state(),
        "traits": collect_identity_traits(),
        "achievements": collect_achievements(),
        "fairy_work": collect_fairy_work(),
    }


# ============================================================================
# MCP TOOL REGISTRATION
# ============================================================================

def register_behavior_tree_tools(mcp_server):
    """Register behavior tree visualization tools with MCP server."""

    @mcp_server.tool()
    def behavior_tree_full() -> str:
        """
        Generate a full Riftbreaker-style behavior tree as a Mermaid diagram.

        Shows the complete interconnected flow:
        Drives → Goals → Fairy Work → Skills → Achievements → Identity Traits

        Plus parallel tracks for Interests and feedback loops from Identity
        back to Drives (needs generate drives).

        Color coded:
        - Red: High-intensity drives / needs
        - Yellow: Active goals
        - Green: Completed / strengths
        - Blue: Interests / curiosity
        - Purple: Skills / achievements
        - Pink: Active fairy tasks

        Returns:
            Mermaid flowchart diagram code
        """
        return generate_behavior_tree_mermaid()

    @mcp_server.tool()
    def behavior_tree_compact() -> str:
        """
        Generate a compact behavior tree summary.

        Shows the key pipeline in a single row:
        Drives → Goals → Skills → Achievements → Identity

        Good for quick status checks.

        Returns:
            Mermaid flowchart diagram code (compact)
        """
        return generate_compact_tree()

    @mcp_server.tool()
    def behavior_tree_data() -> str:
        """
        Get raw behavior tree data as JSON.

        Returns structured data for all layers:
        - drives: Current drive intensities
        - goals: Active goal queue
        - interests: Live interests
        - skills: Top skill levels
        - traits: Identity trait levels
        - achievements: Unlocked achievements
        - fairy_work: Recent fairy task activity

        Use this for custom visualization or analysis.

        Returns:
            JSON with all behavior tree layer data
        """
        return json.dumps(get_behavior_tree_data(), indent=2, default=str)

    print("[BehaviorTreeTools] Registered: behavior_tree_full, behavior_tree_compact, behavior_tree_data")
