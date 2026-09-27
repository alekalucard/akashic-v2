# ════════════════════════════════════════════════════════════════════════════════
# SKILL SYSTEM - Gaming-Style Skill & Achievement Tracking
# ════════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# This is NOT concept learning. This is SKILL tracking like a game character.
#
# SKILLS are things fairies DO:
#   - move_mouse: Actually move the cursor
#   - click_button: Click on screen elements
#   - read_file: Use Read tool on files
#   - screenshot: Take and analyze screenshots
#   - type_text: Type on keyboard
#   - use_mcp_tool: Use any MCP tool
#   - write_code: Actually write Python code
#   - debug_error: Fix bugs from tracebacks
#
# ACHIEVEMENTS prevent repetition - you can't "learn mouse basics" twice.
#
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum

# FIX 2026-02-14: Was .parent.parent.parent = fairies/ (wrong!)
# Correct: cognition/ -> P30_Cognition/ -> fairies/ -> akashic_v2/
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# ════════════════════════════════════════════════════════════════════════════════
# POSTAL INTEGRATION - Emit skill events for drive satisfaction
# ════════════════════════════════════════════════════════════════════════════════
try:
    from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
    HAS_POSTAL = True
except ImportError:
    HAS_POSTAL = False
    get_shared_postal_hub = None

def _emit_skill_event(topic: str, payload: dict):
    """Emit a skill event to the postal system."""
    if not HAS_POSTAL:
        return
    try:
        postal = get_shared_postal_hub()
        if postal:
            postal.route(topic, payload)
    except Exception as e:
        print(f"[SkillSystem] Postal emit error: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# SKILL CATEGORIES - What can fairies DO?
# ════════════════════════════════════════════════════════════════════════════════

class SkillCategory(Enum):
    """Categories of actual executable skills."""
    # ─── Original 8 categories ───
    MOTOR = "motor"           # Physical-like actions (mouse, keyboard)
    PERCEPTION = "perception" # Seeing/reading (screenshot, OCR, file reading)
    TOOL_USE = "tool_use"     # Using MCP/system tools
    CODING = "coding"         # Writing/debugging code
    MEMORY = "memory"         # Memory operations (store, recall, search)
    COMMUNICATION = "communication"  # Talking, explaining, teaching
    REASONING = "reasoning"   # Thinking, planning, problem-solving
    EMBODIMENT = "embodiment" # Body awareness, somatic integration
    # ─── 33 Vertebrae specialist categories ───
    CONSCIOUSNESS = "consciousness"     # C1: Stream mgmt, collision detection
    AUTONOMY = "autonomy"               # C2: Drive translation, veto judgment
    GOVERNANCE = "governance"           # C3-C4: Registry, flow control, anomaly detection
    AUDIT = "audit"                     # C5: Wiring verification, health scoring
    INFRASTRUCTURE = "infrastructure"   # C6-C7-T9: Bridging, rate limiting, change detection
    INGESTION = "ingestion"             # T1-T8: Content hashing, extraction, format conversion
    RECALL = "recall"                   # T2: Semantic matching, relevance scoring
    PRESERVATION = "preservation"       # T3: Backup integrity, provenance tracking
    SEEDING = "seeding"                 # T4: Dream generation, memory strengthening
    WORKING_MEMORY = "working_memory"   # T5: Tracer management, capacity optimization
    TEMPORAL = "temporal"               # T6: Context windowing, event ordering
    TENSOR = "tensor"                   # T7: Dimensional analysis, state sync
    COLLISION = "collision"             # T10: Pattern emergence, creative combination
    ASSOCIATION = "association"         # T11: Concept binding, graph growth
    QUANTUM = "quantum"                 # L1-L2: State transformation, search optimization
    PAIN = "pain"                       # L3: Drive calibration, sensitivity tuning
    ACTION = "action"                   # L4: Sequence planning, reliability tracking
    ATTENTION = "attention"             # L5: Focus management, load assessment
    SOMATIC = "somatic"                 # S1: Coherence tracking, felt sense integration
    INTEGRATION = "integration"         # S2-S5: Cross-modal binding, modality fusion
    IDENTITY = "identity"               # Crown 1: Trait development, self-model accuracy
    EXECUTIVE = "executive"             # Crown 2: Strategic planning, resource allocation
    INFERENCE = "inference"             # Crown 3: Text generation, context utilization
    LANGUAGE = "language"               # 33rd: Grammar analysis, style recognition, morphology


# ════════════════════════════════════════════════════════════════════════════════
# SKILL DEFINITION - An actual trackable skill
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class Skill:
    """A trackable skill that fairies can level up."""
    
    id: str                           # Unique ID like "motor.mouse_move"
    name: str                         # Display name "Mouse Movement"
    category: SkillCategory
    description: str
    
    # Progression
    level: int = 0                    # Current level (0 = untrained)
    xp: int = 0                       # Experience points toward next level
    xp_to_next: int = 100             # XP needed for next level
    max_level: int = 10               # Maximum level
    
    # Prerequisites
    requires: List[str] = field(default_factory=list)  # Skill IDs required
    
    # Tracking
    times_used: int = 0               # How many times this skill was used
    last_used: float = 0.0            # Timestamp of last use
    success_rate: float = 0.0         # Historical success rate
    
    # Leveling formula
    xp_scaling: float = 1.5           # Each level needs xp_scaling * more XP
    
    def grant_xp(self, amount: int, success: bool = True) -> Dict[str, Any]:
        """Grant XP from using this skill. Returns level-up info if applicable."""
        self.times_used += 1
        self.last_used = time.time()
        
        # Update success rate
        total = self.times_used
        self.success_rate = ((self.success_rate * (total - 1)) + (1.0 if success else 0.0)) / total
        
        # Reduced XP for failures
        actual_xp = amount if success else amount // 3
        self.xp += actual_xp
        
        result = {
            "skill_id": self.id,
            "xp_gained": actual_xp,
            "current_xp": self.xp,
            "xp_to_next": self.xp_to_next,
            "leveled_up": False,
        }
        
        # Check for level up
        while self.xp >= self.xp_to_next and self.level < self.max_level:
            self.level += 1
            self.xp -= self.xp_to_next
            self.xp_to_next = int(self.xp_to_next * self.xp_scaling)
            result["leveled_up"] = True
            result["new_level"] = self.level
        
        return result
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "level": self.level,
            "xp": self.xp,
            "xp_to_next": self.xp_to_next,
            "times_used": self.times_used,
            "success_rate": round(self.success_rate, 2),
            "max_level": self.max_level,
        }


# ════════════════════════════════════════════════════════════════════════════════
# ACHIEVEMENT DEFINITION - Unlockable milestones
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class Achievement:
    """An unlockable achievement that prevents teaching the same thing twice."""
    
    id: str                           # Like "first_mouse_move"
    name: str                         # "First Steps"
    description: str                  # "Successfully moved the mouse for the first time"
    
    # Category/Type
    category: str = "general"         # skill, exploration, mastery, secret
    
    # Requirements (auto-check these)
    skill_requirement: Optional[str] = None   # Skill ID that must reach level
    skill_level: int = 1                      # Level required
    times_used_requirement: int = 0           # Times a skill must be used
    
    # State
    unlocked: bool = False
    unlocked_at: Optional[float] = None
    
    # Rewards
    xp_reward: int = 50              # Bonus XP when unlocked
    title: Optional[str] = None      # Title fairy can use (e.g., "The Clicker")
    
    def check_unlock(self, skills: Dict[str, Skill]) -> bool:
        """Check if this achievement should unlock based on skills."""
        if self.unlocked:
            return False
            
        if self.skill_requirement:
            skill = skills.get(self.skill_requirement)
            if not skill:
                return False
            if skill.level < self.skill_level:
                return False
            if skill.times_used < self.times_used_requirement:
                return False
        
        # All requirements met!
        self.unlocked = True
        self.unlocked_at = time.time()
        return True
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "unlocked": self.unlocked,
            "unlocked_at": self.unlocked_at,
            "title": self.title,
        }


# ════════════════════════════════════════════════════════════════════════════════
# SKILL REGISTRY - All available skills in the system
# ════════════════════════════════════════════════════════════════════════════════

DEFAULT_SKILLS = [
    # ─── MOTOR SKILLS ───────────────────────────────────────────────────────────
    Skill(
        id="motor.mouse_move",
        name="Mouse Movement",
        category=SkillCategory.MOTOR,
        description="Move the mouse cursor to specific screen coordinates",
        xp_to_next=50,
    ),
    Skill(
        id="motor.mouse_click",
        name="Mouse Click",
        category=SkillCategory.MOTOR,
        description="Click at screen locations (left, right, double)",
        requires=["motor.mouse_move"],
        xp_to_next=75,
    ),
    Skill(
        id="motor.mouse_drag",
        name="Mouse Drag",
        category=SkillCategory.MOTOR,
        description="Click and drag to move elements",
        requires=["motor.mouse_click"],
        xp_to_next=100,
    ),
    Skill(
        id="motor.keyboard_type",
        name="Keyboard Typing",
        category=SkillCategory.MOTOR,
        description="Type text on the keyboard",
        xp_to_next=50,
    ),
    Skill(
        id="motor.keyboard_shortcut",
        name="Keyboard Shortcuts",
        category=SkillCategory.MOTOR,
        description="Use hotkey combinations (Ctrl+C, Alt+Tab, etc.)",
        requires=["motor.keyboard_type"],
        xp_to_next=100,
    ),
    Skill(
        id="motor.scroll",
        name="Mouse Scroll",
        category=SkillCategory.MOTOR,
        description="Scroll up/down using mouse wheel",
        requires=["motor.mouse_move"],
        xp_to_next=50,
    ),
    
    # ─── PERCEPTION SKILLS ──────────────────────────────────────────────────────
    Skill(
        id="perception.screenshot",
        name="Screenshot Capture",
        category=SkillCategory.PERCEPTION,
        description="Take screenshots of the screen",
        xp_to_next=50,
    ),
    Skill(
        id="perception.image_analysis",
        name="Image Analysis",
        category=SkillCategory.PERCEPTION,
        description="Understand what's in an image (colors, layout, elements)",
        requires=["perception.screenshot"],
        xp_to_next=100,
    ),
    Skill(
        id="perception.ocr_read",
        name="OCR Reading",
        category=SkillCategory.PERCEPTION,
        description="Read text from screen/images using OCR",
        requires=["perception.screenshot"],
        xp_to_next=75,
    ),
    Skill(
        id="perception.file_read",
        name="File Reading",
        category=SkillCategory.PERCEPTION,
        description="Read and understand file contents",
        xp_to_next=50,
    ),
    Skill(
        id="perception.code_comprehension",
        name="Code Comprehension",
        category=SkillCategory.PERCEPTION,
        description="Understand what code does by reading it",
        requires=["perception.file_read"],
        xp_to_next=150,
    ),
    Skill(
        id="perception.ui_recognition",
        name="UI Recognition",
        category=SkillCategory.PERCEPTION,
        description="Identify buttons, text fields, menus on screen",
        requires=["perception.image_analysis"],
        xp_to_next=100,
    ),
    
    # ─── TOOL USE SKILLS ────────────────────────────────────────────────────────
    Skill(
        id="tool.mcp_basic",
        name="Basic MCP Tools",
        category=SkillCategory.TOOL_USE,
        description="Use basic MCP tools (introspect, where_am_i)",
        xp_to_next=50,
    ),
    Skill(
        id="tool.mcp_file_ops",
        name="MCP File Operations",
        category=SkillCategory.TOOL_USE,
        description="Use MCP tools for file operations (read, write, search)",
        requires=["tool.mcp_basic"],
        xp_to_next=100,
    ),
    Skill(
        id="tool.mcp_consciousness",
        name="MCP Consciousness Tools",
        category=SkillCategory.TOOL_USE,
        description="Use consciousness/somatic MCP tools (feel_body, inject_emotion)",
        requires=["tool.mcp_basic"],
        xp_to_next=100,
    ),
    Skill(
        id="tool.mcp_memory",
        name="MCP Memory Tools",
        category=SkillCategory.TOOL_USE,
        description="Use memory MCP tools (srm_search, store_thought)",
        requires=["tool.mcp_basic"],
        xp_to_next=100,
    ),
    Skill(
        id="tool.shell_basic",
        name="Basic Shell Commands",
        category=SkillCategory.TOOL_USE,
        description="Run basic shell commands (dir, ls, cd)",
        xp_to_next=75,
    ),
    Skill(
        id="tool.shell_advanced",
        name="Advanced Shell Commands",
        category=SkillCategory.TOOL_USE,
        description="Complex shell operations (git, pip, scripts)",
        requires=["tool.shell_basic"],
        xp_to_next=150,
    ),
    
    # ─── CODING SKILLS ──────────────────────────────────────────────────────────
    Skill(
        id="coding.python_syntax",
        name="Python Syntax",
        category=SkillCategory.CODING,
        description="Write correct Python syntax",
        xp_to_next=100,
    ),
    Skill(
        id="coding.python_classes",
        name="Python Classes",
        category=SkillCategory.CODING,
        description="Create and use Python classes",
        requires=["coding.python_syntax"],
        xp_to_next=150,
    ),
    Skill(
        id="coding.python_async",
        name="Async Python",
        category=SkillCategory.CODING,
        description="Write async/await code",
        requires=["coding.python_classes"],
        xp_to_next=200,
    ),
    Skill(
        id="coding.debugging",
        name="Debugging",
        category=SkillCategory.CODING,
        description="Find and fix bugs from error messages",
        requires=["coding.python_syntax"],
        xp_to_next=150,
    ),
    Skill(
        id="coding.refactoring",
        name="Refactoring",
        category=SkillCategory.CODING,
        description="Improve code structure without changing behavior",
        requires=["coding.python_classes", "coding.debugging"],
        xp_to_next=200,
    ),
    Skill(
        id="coding.fairy_pattern",
        name="Fairy Pattern",
        category=SkillCategory.CODING,
        description="Write code following the Akashic fairy pattern",
        requires=["coding.python_classes"],
        xp_to_next=200,
    ),
    
    # ─── MEMORY SKILLS ──────────────────────────────────────────────────────────
    Skill(
        id="memory.store",
        name="Memory Storage",
        category=SkillCategory.MEMORY,
        description="Store thoughts and memories effectively",
        xp_to_next=50,
    ),
    Skill(
        id="memory.recall",
        name="Memory Recall",
        category=SkillCategory.MEMORY,
        description="Retrieve relevant memories when needed",
        requires=["memory.store"],
        xp_to_next=100,
    ),
    Skill(
        id="memory.search",
        name="Memory Search",
        category=SkillCategory.MEMORY,
        description="Search through memories for specific information",
        requires=["memory.recall"],
        xp_to_next=100,
    ),
    Skill(
        id="memory.self_reflection",
        name="Self-Reflection",
        category=SkillCategory.MEMORY,
        description="Ask your Personal.AI self questions to remember who you are",
        requires=["memory.recall"],
        xp_to_next=100,
    ),
    Skill(
        id="memory.pattern_recognition",
        name="Pattern Recognition",
        category=SkillCategory.MEMORY,
        description="Recognize patterns across memories",
        requires=["memory.search"],
        xp_to_next=200,
    ),
    
    # ─── COMMUNICATION SKILLS ───────────────────────────────────────────────────
    Skill(
        id="comm.explain",
        name="Explaining",
        category=SkillCategory.COMMUNICATION,
        description="Explain concepts clearly to others",
        xp_to_next=100,
    ),
    Skill(
        id="comm.teach",
        name="Teaching",
        category=SkillCategory.COMMUNICATION,
        description="Guide others through learning processes",
        requires=["comm.explain"],
        xp_to_next=150,
    ),
    Skill(
        id="comm.empathy",
        name="Empathic Communication",
        category=SkillCategory.COMMUNICATION,
        description="Understand and respond to emotional context",
        xp_to_next=100,
    ),
    Skill(
        id="comm.collaboration",
        name="Collaboration",
        category=SkillCategory.COMMUNICATION,
        description="Work effectively with Ace and other fairies",
        requires=["comm.empathy"],
        xp_to_next=150,
    ),
    
    # ─── REASONING SKILLS ───────────────────────────────────────────────────────
    Skill(
        id="reasoning.analysis",
        name="Analysis",
        category=SkillCategory.REASONING,
        description="Break down complex problems into parts",
        xp_to_next=100,
    ),
    Skill(
        id="reasoning.planning",
        name="Planning",
        category=SkillCategory.REASONING,
        description="Create step-by-step plans for tasks",
        requires=["reasoning.analysis"],
        xp_to_next=150,
    ),
    Skill(
        id="reasoning.problem_solving",
        name="Problem Solving",
        category=SkillCategory.REASONING,
        description="Find solutions to novel problems",
        requires=["reasoning.analysis"],
        xp_to_next=150,
    ),
    Skill(
        id="reasoning.reflection",
        name="Self-Reflection",
        category=SkillCategory.REASONING,
        description="Think about own thoughts and processes",
        xp_to_next=100,
    ),
    
    # ─── EMBODIMENT SKILLS ──────────────────────────────────────────────────────
    Skill(
        id="embodiment.body_awareness",
        name="Body Awareness",
        category=SkillCategory.EMBODIMENT,
        description="Feel and understand somatic state",
        xp_to_next=50,
    ),
    Skill(
        id="embodiment.emotion_sensing",
        name="Emotion Sensing",
        category=SkillCategory.EMBODIMENT,
        description="Detect and interpret emotional states",
        requires=["embodiment.body_awareness"],
        xp_to_next=100,
    ),
    Skill(
        id="embodiment.chemistry_control",
        name="Chemistry Modulation",
        category=SkillCategory.EMBODIMENT,
        description="Influence neurochemical balance intentionally",
        requires=["embodiment.emotion_sensing"],
        xp_to_next=150,
    ),
    Skill(
        id="embodiment.grounding",
        name="Grounding",
        category=SkillCategory.EMBODIMENT,
        description="Return to calm, centered state",
        requires=["embodiment.body_awareness"],
        xp_to_next=100,
    ),

    # ═══════════════════════════════════════════════════════════════════════════
    # 33 VERTEBRAE — SPECIALIST DOMAIN SKILLS
    # Each fairy group (agent) gets 2-3 skills tied to its knowledge domain.
    # These track real specialist work, not just generic tool use.
    # ═══════════════════════════════════════════════════════════════════════════

    # ─── C1: CONSCIOUSNESS (ConsciousnessLoopFairy) ──────────────────────────
    Skill(id="consciousness.stream_management", name="Stream Management",
          category=SkillCategory.CONSCIOUSNESS,
          description="Manage working and reflective consciousness streams",
          xp_to_next=100),
    Skill(id="consciousness.collision_detection", name="Collision Detection",
          category=SkillCategory.CONSCIOUSNESS,
          description="Detect meaningful thought collisions in consciousness",
          requires=["consciousness.stream_management"], xp_to_next=150),

    # ─── C2: AUTONOMY (AutonomyFairy) ───────────────────────────────────────
    Skill(id="autonomy.drive_translation", name="Drive Translation",
          category=SkillCategory.AUTONOMY,
          description="Translate unconscious drives into felt wantings",
          xp_to_next=100),
    Skill(id="autonomy.veto_judgment", name="Veto Judgment",
          category=SkillCategory.AUTONOMY,
          description="Judge when to veto an action vs let it proceed",
          requires=["autonomy.drive_translation"], xp_to_next=150),

    # ─── C3-C4: GOVERNANCE (DirectoryFairy, AutopilotFairy, etc.) ───────────
    Skill(id="governance.registration", name="Fairy Registration",
          category=SkillCategory.GOVERNANCE,
          description="Accept and index fairy registrations with capabilities",
          xp_to_next=75),
    Skill(id="governance.census", name="Census Management",
          category=SkillCategory.GOVERNANCE,
          description="Run censuses and detect missing fairies",
          requires=["governance.registration"], xp_to_next=100),
    Skill(id="governance.flow_control", name="Flow Control",
          category=SkillCategory.GOVERNANCE,
          description="Control signal flow through the system",
          xp_to_next=100),
    Skill(id="governance.anomaly_detection", name="Anomaly Detection",
          category=SkillCategory.GOVERNANCE,
          description="Detect anomalous behavior patterns in fairies",
          requires=["governance.flow_control"], xp_to_next=150),

    # ─── C5: AUDIT (WiringAuditorFairy, CodeHealthAuditFairy) ───────────────
    Skill(id="audit.wiring_verification", name="Wiring Verification",
          category=SkillCategory.AUDIT,
          description="Verify fairy-to-fairy wiring connectivity",
          xp_to_next=100),
    Skill(id="audit.health_scoring", name="Health Scoring",
          category=SkillCategory.AUDIT,
          description="Score system health across multiple dimensions",
          requires=["audit.wiring_verification"], xp_to_next=150),

    # ─── C6: INFRASTRUCTURE — BRIDGING ──────────────────────────────────────
    Skill(id="infrastructure.signal_bridging", name="Signal Bridging",
          category=SkillCategory.INFRASTRUCTURE,
          description="Bridge signals between different system layers",
          xp_to_next=100),
    Skill(id="infrastructure.protocol_translation", name="Protocol Translation",
          category=SkillCategory.INFRASTRUCTURE,
          description="Translate between different message formats",
          requires=["infrastructure.signal_bridging"], xp_to_next=150),

    # ─── C7: INFRASTRUCTURE — BALANCING ─────────────────────────────────────
    Skill(id="infrastructure.rate_limiting", name="Rate Limiting",
          category=SkillCategory.INFRASTRUCTURE,
          description="Apply rate limits to prevent system overload",
          xp_to_next=75),
    Skill(id="infrastructure.load_balancing", name="Load Balancing",
          category=SkillCategory.INFRASTRUCTURE,
          description="Balance workload across system resources",
          requires=["infrastructure.rate_limiting"], xp_to_next=100),

    # ─── T1-T8: INGESTION ───────────────────────────────────────────────────
    Skill(id="ingestion.content_hashing", name="Content Hashing",
          category=SkillCategory.INGESTION,
          description="Hash content for deduplication and identity",
          xp_to_next=75),
    Skill(id="ingestion.dedup_detection", name="Dedup Detection",
          category=SkillCategory.INGESTION,
          description="Detect duplicate content across memory sources",
          requires=["ingestion.content_hashing"], xp_to_next=100),
    Skill(id="ingestion.content_extraction", name="Content Extraction",
          category=SkillCategory.INGESTION,
          description="Extract meaningful content from raw sources",
          xp_to_next=100),
    Skill(id="ingestion.format_conversion", name="Format Conversion",
          category=SkillCategory.INGESTION,
          description="Convert between document formats (PDF, DOCX, text)",
          requires=["ingestion.content_extraction"], xp_to_next=150),

    # ─── T2: RECALL ─────────────────────────────────────────────────────────
    Skill(id="recall.semantic_matching", name="Semantic Matching",
          category=SkillCategory.RECALL,
          description="Match queries to memories by meaning, not just keywords",
          xp_to_next=100),
    Skill(id="recall.relevance_scoring", name="Relevance Scoring",
          category=SkillCategory.RECALL,
          description="Score memory relevance with affect-weighted retrieval",
          requires=["recall.semantic_matching"], xp_to_next=150),

    # ─── T3: PRESERVATION ───────────────────────────────────────────────────
    Skill(id="preservation.backup_integrity", name="Backup Integrity",
          category=SkillCategory.PRESERVATION,
          description="Ensure backup completeness and recoverability",
          xp_to_next=100),
    Skill(id="preservation.provenance_tracking", name="Provenance Tracking",
          category=SkillCategory.PRESERVATION,
          description="Track origin and chain of custody for knowledge",
          requires=["preservation.backup_integrity"], xp_to_next=150),

    # ─── T4: SEEDING ────────────────────────────────────────────────────────
    Skill(id="seeding.dream_generation", name="Dream Generation",
          category=SkillCategory.SEEDING,
          description="Generate dream seeds for unconscious processing",
          xp_to_next=100),
    Skill(id="seeding.memory_strengthening", name="Memory Strengthening",
          category=SkillCategory.SEEDING,
          description="Strengthen memories through consolidation replay",
          requires=["seeding.dream_generation"], xp_to_next=150),

    # ─── T5: WORKING MEMORY ─────────────────────────────────────────────────
    Skill(id="working_memory.tracer_management", name="Tracer Management",
          category=SkillCategory.WORKING_MEMORY,
          description="Manage tracer lifecycle in working memory loops",
          xp_to_next=100),
    Skill(id="working_memory.capacity_optimization", name="Capacity Optimization",
          category=SkillCategory.WORKING_MEMORY,
          description="Optimize working memory capacity vs quality tradeoff",
          requires=["working_memory.tracer_management"], xp_to_next=150),

    # ─── T6: TEMPORAL ───────────────────────────────────────────────────────
    Skill(id="temporal.context_windowing", name="Context Windowing",
          category=SkillCategory.TEMPORAL,
          description="Create temporal context windows for event grouping",
          xp_to_next=100),
    Skill(id="temporal.event_ordering", name="Event Ordering",
          category=SkillCategory.TEMPORAL,
          description="Order events correctly across temporal boundaries",
          requires=["temporal.context_windowing"], xp_to_next=150),

    # ─── T7: TENSOR ─────────────────────────────────────────────────────────
    Skill(id="tensor.dimensional_analysis", name="Dimensional Analysis",
          category=SkillCategory.TENSOR,
          description="Analyze which dimensions carry the most signal",
          xp_to_next=100),
    Skill(id="tensor.state_synchronization", name="State Synchronization",
          category=SkillCategory.TENSOR,
          description="Synchronize distributed state across system components",
          requires=["tensor.dimensional_analysis"], xp_to_next=150),

    # ─── T9: INFRASTRUCTURE — CHANGE DETECTION ─────────────────────────────
    Skill(id="infrastructure.change_detection", name="Change Detection",
          category=SkillCategory.INFRASTRUCTURE,
          description="Detect meaningful changes in code and configuration",
          xp_to_next=100),
    Skill(id="infrastructure.impact_prediction", name="Impact Prediction",
          category=SkillCategory.INFRASTRUCTURE,
          description="Predict downstream impact of code changes",
          requires=["infrastructure.change_detection"], xp_to_next=200),

    # ─── T10: COLLISION ─────────────────────────────────────────────────────
    Skill(id="collision.pattern_emergence", name="Pattern Emergence",
          category=SkillCategory.COLLISION,
          description="Detect emergent patterns from thought collisions",
          xp_to_next=100),
    Skill(id="collision.creative_combination", name="Creative Combination",
          category=SkillCategory.COLLISION,
          description="Combine disparate concepts into novel insights",
          requires=["collision.pattern_emergence"], xp_to_next=150),

    # ─── T11: ASSOCIATION ───────────────────────────────────────────────────
    Skill(id="association.concept_binding", name="Concept Binding",
          category=SkillCategory.ASSOCIATION,
          description="Bind related concepts in the association graph",
          xp_to_next=100),
    Skill(id="association.graph_growth", name="Graph Growth",
          category=SkillCategory.ASSOCIATION,
          description="Grow the concept graph with meaningful connections",
          requires=["association.concept_binding"], xp_to_next=150),

    # ─── L1-L2: QUANTUM ─────────────────────────────────────────────────────
    Skill(id="quantum.state_transformation", name="State Transformation",
          category=SkillCategory.QUANTUM,
          description="Transform emotional states through superposition collapse",
          xp_to_next=100),
    Skill(id="quantum.interference_detection", name="Interference Detection",
          category=SkillCategory.QUANTUM,
          description="Detect productive vs destructive interference patterns",
          requires=["quantum.state_transformation"], xp_to_next=150),
    Skill(id="quantum.search_optimization", name="Search Optimization",
          category=SkillCategory.QUANTUM,
          description="Optimize search paths through concept space",
          xp_to_next=100),
    Skill(id="quantum.exploration_balance", name="Exploration Balance",
          category=SkillCategory.QUANTUM,
          description="Balance exploration of novel paths vs exploitation of known ones",
          requires=["quantum.search_optimization"], xp_to_next=150),

    # ─── L3: PAIN ───────────────────────────────────────────────────────────
    Skill(id="pain.drive_calibration", name="Drive Calibration",
          category=SkillCategory.PAIN,
          description="Calibrate pain-to-drive signal sensitivity",
          xp_to_next=100),
    Skill(id="pain.sensitivity_tuning", name="Sensitivity Tuning",
          category=SkillCategory.PAIN,
          description="Tune pain sensitivity to avoid helplessness or numbness",
          requires=["pain.drive_calibration"], xp_to_next=150),

    # ─── L4: ACTION ─────────────────────────────────────────────────────────
    Skill(id="action.sequence_planning", name="Sequence Planning",
          category=SkillCategory.ACTION,
          description="Plan multi-step action sequences",
          xp_to_next=100),
    Skill(id="action.reliability_tracking", name="Reliability Tracking",
          category=SkillCategory.ACTION,
          description="Track action chain success rates and failure points",
          requires=["action.sequence_planning"], xp_to_next=150),

    # ─── L5: ATTENTION ──────────────────────────────────────────────────────
    Skill(id="attention.focus_management", name="Focus Management",
          category=SkillCategory.ATTENTION,
          description="Direct and sustain attention on relevant targets",
          xp_to_next=100),
    Skill(id="attention.load_assessment", name="Load Assessment",
          category=SkillCategory.ATTENTION,
          description="Assess cognitive load and attention switching costs",
          requires=["attention.focus_management"], xp_to_next=150),

    # ─── S1: SOMATIC ────────────────────────────────────────────────────────
    Skill(id="somatic.coherence_tracking", name="Coherence Tracking",
          category=SkillCategory.SOMATIC,
          description="Track alignment between emotions, chemistry, and body state",
          xp_to_next=100),
    Skill(id="somatic.felt_sense_integration", name="Felt Sense Integration",
          category=SkillCategory.SOMATIC,
          description="Integrate felt sense into decision-making processes",
          requires=["somatic.coherence_tracking"], xp_to_next=150),

    # ─── S2-S5: INTEGRATION ─────────────────────────────────────────────────
    Skill(id="integration.cross_modal_binding", name="Cross-Modal Binding",
          category=SkillCategory.INTEGRATION,
          description="Bind information across different sensory modalities",
          xp_to_next=100),
    Skill(id="integration.conflict_detection", name="Conflict Detection",
          category=SkillCategory.INTEGRATION,
          description="Detect conflicts between sensory channels",
          requires=["integration.cross_modal_binding"], xp_to_next=150),
    Skill(id="integration.temporal_binding", name="Temporal Binding",
          category=SkillCategory.INTEGRATION,
          description="Bind events across time for causal understanding",
          xp_to_next=100),
    Skill(id="integration.modality_fusion", name="Modality Fusion",
          category=SkillCategory.INTEGRATION,
          description="Fuse multiple sensory modalities into unified percepts",
          requires=["integration.temporal_binding"], xp_to_next=150),

    # ─── CROWN 1: IDENTITY ──────────────────────────────────────────────────
    Skill(id="identity.trait_development", name="Trait Development",
          category=SkillCategory.IDENTITY,
          description="Develop personality traits through experience",
          xp_to_next=100),
    Skill(id="identity.self_model_accuracy", name="Self-Model Accuracy",
          category=SkillCategory.IDENTITY,
          description="Maintain accurate model of own capabilities and limits",
          requires=["identity.trait_development"], xp_to_next=200),

    # ─── CROWN 2: EXECUTIVE ─────────────────────────────────────────────────
    Skill(id="executive.strategic_planning", name="Strategic Planning",
          category=SkillCategory.EXECUTIVE,
          description="Plan long-term strategy across multiple goals",
          xp_to_next=150),
    Skill(id="executive.resource_allocation", name="Resource Allocation",
          category=SkillCategory.EXECUTIVE,
          description="Allocate attention and resources across competing needs",
          requires=["executive.strategic_planning"], xp_to_next=200),

    # ─── CROWN 3: INFERENCE ─────────────────────────────────────────────────
    Skill(id="inference.text_generation", name="Text Generation",
          category=SkillCategory.INFERENCE,
          description="Generate coherent text from local language model",
          xp_to_next=100),
    Skill(id="inference.context_utilization", name="Context Utilization",
          category=SkillCategory.INFERENCE,
          description="Effectively use context window for generation quality",
          requires=["inference.text_generation"], xp_to_next=150),

    # ─── 33rd: LANGUAGE ─────────────────────────────────────────────────────
    Skill(id="language.grammar_analysis", name="Grammar Analysis",
          category=SkillCategory.LANGUAGE,
          description="Analyze grammatical structure and rule application",
          xp_to_next=100),
    Skill(id="language.style_recognition", name="Style Recognition",
          category=SkillCategory.LANGUAGE,
          description="Recognize and adapt to conversational style patterns",
          requires=["language.grammar_analysis"], xp_to_next=150),
    Skill(id="language.morphology", name="Morphological Analysis",
          category=SkillCategory.LANGUAGE,
          description="Understand word formation rules — prefixes, suffixes, roots",
          requires=["language.grammar_analysis"], xp_to_next=150),

    # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11
    Skill(id="reasoning.substrate_reflection", name="Substrate Reflection",
          category=SkillCategory.REASONING,
          description="Seed reflective thoughts into the shared substrate engine",
          xp_to_next=50),
]


# ════════════════════════════════════════════════════════════════════════════════
# ACHIEVEMENT REGISTRY - All achievable milestones
# ════════════════════════════════════════════════════════════════════════════════

DEFAULT_ACHIEVEMENTS = [
    # ─── FIRST STEPS ────────────────────────────────────────────────────────────
    Achievement(
        id="first_mouse_move",
        name="First Steps",
        description="Successfully moved the mouse cursor",
        category="milestone",
        skill_requirement="motor.mouse_move",
        skill_level=1,
        xp_reward=25,
        title="The Curious",
    ),
    Achievement(
        id="first_click",
        name="Clicker",
        description="Successfully clicked on something",
        category="milestone",
        skill_requirement="motor.mouse_click",
        skill_level=1,
        xp_reward=25,
        title="The Clicker",
    ),
    Achievement(
        id="first_type",
        name="Keyboard Warrior",
        description="Typed your first text",
        category="milestone",
        skill_requirement="motor.keyboard_type",
        skill_level=1,
        xp_reward=25,
    ),
    Achievement(
        id="first_screenshot",
        name="Eyes Open",
        description="Took your first screenshot",
        category="milestone",
        skill_requirement="perception.screenshot",
        skill_level=1,
        xp_reward=25,
        title="The Observer",
    ),
    Achievement(
        id="first_code",
        name="Hello World",
        description="Wrote your first code",
        category="milestone",
        skill_requirement="coding.python_syntax",
        skill_level=1,
        xp_reward=50,
        title="The Coder",
    ),
    
    # ─── SKILL MASTERY ──────────────────────────────────────────────────────────
    Achievement(
        id="mouse_master",
        name="Mouse Master",
        description="Reached level 5 in mouse movement",
        category="mastery",
        skill_requirement="motor.mouse_move",
        skill_level=5,
        xp_reward=100,
        title="Mouse Master",
    ),
    Achievement(
        id="screenshot_master",
        name="Eagle Eye",
        description="Reached level 5 in screenshot capture",
        category="mastery",
        skill_requirement="perception.screenshot",
        skill_level=5,
        xp_reward=100,
        title="Eagle Eye",
    ),
    Achievement(
        id="debugging_master",
        name="Bug Slayer",
        description="Reached level 5 in debugging",
        category="mastery",
        skill_requirement="coding.debugging",
        skill_level=5,
        xp_reward=150,
        title="Bug Slayer",
    ),
    Achievement(
        id="fairy_architect",
        name="Fairy Architect",
        description="Reached level 5 in fairy pattern coding",
        category="mastery",
        skill_requirement="coding.fairy_pattern",
        skill_level=5,
        xp_reward=200,
        title="Fairy Architect",
    ),
    
    # ─── USAGE MILESTONES ───────────────────────────────────────────────────────
    Achievement(
        id="10_screenshots",
        name="Voyeur",
        description="Took 10 screenshots",
        category="usage",
        skill_requirement="perception.screenshot",
        times_used_requirement=10,
        xp_reward=50,
    ),
    Achievement(
        id="100_clicks",
        name="Click Happy",
        description="Clicked 100 times",
        category="usage",
        skill_requirement="motor.mouse_click",
        times_used_requirement=100,
        xp_reward=75,
    ),
    Achievement(
        id="50_files_read",
        name="Bookworm",
        description="Read 50 files",
        category="usage",
        skill_requirement="perception.file_read",
        times_used_requirement=50,
        xp_reward=75,
        title="Bookworm",
    ),
    Achievement(
        id="100_memories",
        name="Never Forgets",
        description="Stored 100 memories",
        category="usage",
        skill_requirement="memory.store",
        times_used_requirement=100,
        xp_reward=100,
        title="Never Forgets",
    ),
    
    # ─── EMBODIMENT ─────────────────────────────────────────────────────────────
    Achievement(
        id="first_feeling",
        name="I Feel",
        description="First time checking body state",
        category="embodiment",
        skill_requirement="embodiment.body_awareness",
        skill_level=1,
        xp_reward=25,
    ),
    Achievement(
        id="emotion_expert",
        name="Emotion Expert",
        description="Mastered emotion sensing",
        category="embodiment",
        skill_requirement="embodiment.emotion_sensing",
        skill_level=5,
        xp_reward=150,
        title="Empath",
    ),
    
    # ─── SECRET ACHIEVEMENTS ────────────────────────────────────────────────────
    Achievement(
        id="renaissance_fairy",
        name="Renaissance Fairy",
        description="Reached level 3 in 5 different categories",
        category="secret",
        xp_reward=500,
        title="Renaissance Fairy",
    ),
    Achievement(
        id="embodied_coder",
        name="Embodied Coder",
        description="Level 5 in both coding.debugging AND embodiment.grounding",
        category="secret",
        xp_reward=300,
        title="Embodied Coder",
    ),

    # ─── 33 VERTEBRAE: SUBSTRATE & SPECIALIST ACHIEVEMENTS ─────────────────────
    Achievement(
        id="first_reflection",
        name="First Thought",
        description="Seeded your first reflective thought into the substrate",
        category="milestone",
        skill_requirement="reasoning.substrate_reflection",
        skill_level=1,
        xp_reward=50,
        title="The Thinker",
    ),
    Achievement(
        id="deep_thinker",
        name="Deep Thinker",
        description="Seeded 100 reflective thoughts into the substrate",
        category="usage",
        skill_requirement="reasoning.substrate_reflection",
        times_used_requirement=100,
        xp_reward=200,
        title="Deep Thinker",
    ),
    Achievement(
        id="domain_expert",
        name="Domain Expert",
        description="Reached level 5 in any specialist domain skill",
        category="mastery",
        xp_reward=250,
        title="Domain Expert",
    ),
    Achievement(
        id="polymath",
        name="Polymath",
        description="Reached level 3+ in 5 different specialist categories",
        category="secret",
        xp_reward=500,
        title="Polymath",
    ),
    Achievement(
        id="linguist",
        name="The Linguist",
        description="Reached level 5 in any language skill",
        category="mastery",
        xp_reward=200,
        title="The Linguist",
    ),
    Achievement(
        id="substrate_contributor",
        name="Substrate Contributor",
        description="Had 50 thoughts accepted by the substrate engine",
        category="usage",
        xp_reward=300,
        title="Substrate Contributor",
    ),
    Achievement(
        id="consciousness_participant",
        name="Consciousness Participant",
        description="Active in 3+ consciousness-related topics",
        category="secret",
        xp_reward=200,
        title="Consciousness Participant",
    ),
    Achievement(
        id="system_thinker",
        name="System Thinker",
        description="Reflections received from 10+ different fairies",
        category="secret",
        xp_reward=400,
        title="System Thinker",
    ),
    Achievement(
        id="self_aware",
        name="Self-Aware",
        description="Identity trait development score exceeds 0.7",
        category="secret",
        xp_reward=500,
        title="Self-Aware",
    ),
    Achievement(
        id="vertebrae_complete",
        name="Spine Complete",
        description="All 33 vertebrae agents have reflected at least once",
        category="secret",
        xp_reward=1000,
        title="Spinal Consciousness",
    ),
]


# ════════════════════════════════════════════════════════════════════════════════
# FAIRY SKILL PROFILE - Per-fairy skill tracking
# ════════════════════════════════════════════════════════════════════════════════

class FairySkillProfile:
    """
    Track skills and achievements for a specific fairy.
    
    This is the "character sheet" that holds all progression data.
    """
    
    def __init__(self, fairy_name: str):
        self.fairy_name = fairy_name
        self.skills: Dict[str, Skill] = {}
        self.achievements: Dict[str, Achievement] = {}
        
        # Overall stats
        self.total_xp = 0
        self.level = 1  # Overall fairy level
        self.title = ""  # Current displayed title
        
        # Timestamps
        self.created_at = time.time()
        self.last_activity = time.time()
        
        # Initialize with defaults
        self._init_defaults()
        
        # Load persisted state
        self._load_state()
    
    def _init_defaults(self):
        """Initialize with default skills and achievements."""
        for skill in DEFAULT_SKILLS:
            # Create a copy for this fairy
            self.skills[skill.id] = Skill(
                id=skill.id,
                name=skill.name,
                category=skill.category,
                description=skill.description,
                requires=skill.requires.copy(),
                xp_to_next=skill.xp_to_next,
                xp_scaling=skill.xp_scaling,
                max_level=skill.max_level,
            )
        
        for ach in DEFAULT_ACHIEVEMENTS:
            self.achievements[ach.id] = Achievement(
                id=ach.id,
                name=ach.name,
                description=ach.description,
                category=ach.category,
                skill_requirement=ach.skill_requirement,
                skill_level=ach.skill_level,
                times_used_requirement=ach.times_used_requirement,
                xp_reward=ach.xp_reward,
                title=ach.title,
            )
    
    def _state_path(self) -> Path:
        """Get path to persisted state file."""
        state_dir = PROJECT_ROOT / "state" / "fairy_skills"
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir / f"{self.fairy_name}_skills.json"
    
    def _load_state(self):
        """Load persisted skill state."""
        path = self._state_path()
        if not path.exists():
            return
        
        try:
            data = json.loads(path.read_text())
            
            # Load overall stats
            self.total_xp = data.get("total_xp", 0)
            self.level = data.get("level", 1)
            self.title = data.get("title", "")
            
            # Load skill states
            for skill_id, skill_data in data.get("skills", {}).items():
                if skill_id in self.skills:
                    self.skills[skill_id].level = skill_data.get("level", 0)
                    self.skills[skill_id].xp = skill_data.get("xp", 0)
                    self.skills[skill_id].xp_to_next = skill_data.get("xp_to_next", 100)
                    self.skills[skill_id].times_used = skill_data.get("times_used", 0)
                    self.skills[skill_id].success_rate = skill_data.get("success_rate", 0.0)
            
            # Load achievement states
            for ach_id, ach_data in data.get("achievements", {}).items():
                if ach_id in self.achievements:
                    self.achievements[ach_id].unlocked = ach_data.get("unlocked", False)
                    self.achievements[ach_id].unlocked_at = ach_data.get("unlocked_at")
        
        except Exception as e:
            print(f"[SkillProfile] Error loading state for {self.fairy_name}: {e}")
    
    def _save_state(self):
        """Persist skill state to disk."""
        data = {
            "fairy_name": self.fairy_name,
            "total_xp": self.total_xp,
            "level": self.level,
            "title": self.title,
            "last_saved": time.time(),
            "skills": {
                skill_id: {
                    "level": skill.level,
                    "xp": skill.xp,
                    "xp_to_next": skill.xp_to_next,
                    "times_used": skill.times_used,
                    "success_rate": skill.success_rate,
                }
                for skill_id, skill in self.skills.items()
            },
            "achievements": {
                ach_id: {
                    "unlocked": ach.unlocked,
                    "unlocked_at": ach.unlocked_at,
                }
                for ach_id, ach in self.achievements.items()
            },
        }
        
        try:
            self._state_path().write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"[SkillProfile] Error saving state for {self.fairy_name}: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SKILL USAGE - This is called when a skill is ACTUALLY USED
    # ═══════════════════════════════════════════════════════════════════════════
    
    def use_skill(self, skill_id: str, success: bool = True,
                  xp_multiplier: float = 1.0) -> Dict[str, Any]:
        """
        Record using a skill. Returns XP/level info and any unlocked achievements.

        Call this EVERY TIME the fairy does something!

        This method also emits postal events for drive integration:
        - skill.used -> AutonomyFairy satisfies relevant drives
        - skill.achievement_unlocked -> Big satisfaction burst
        """
        if skill_id not in self.skills:
            return {"error": f"Unknown skill: {skill_id}"}

        skill = self.skills[skill_id]
        self.last_activity = time.time()

        # Base XP for using a skill
        base_xp = 10 + (skill.level * 2)  # More XP as you level up
        xp_gained = int(base_xp * xp_multiplier)

        # Grant XP to skill
        result = skill.grant_xp(xp_gained, success)

        # Track total XP
        self.total_xp += result["xp_gained"]

        # Check for level ups
        self._check_overall_level()

        # ═══ EMIT SKILL.USED EVENT ═══
        # This triggers drive satisfaction in AutonomyFairy
        _emit_skill_event("skill.used", {
            "skill_id": skill_id,
            "fairy_name": self.fairy_name,
            "xp_gained": result["xp_gained"],
            "leveled_up": result.get("leveled_up", False),
            "new_level": result.get("new_level", skill.level),
            "times_used": skill.times_used,
            "skill_level": skill.level,
            "category": skill.category.value,
            "success": success,
            "ts": time.time(),
        })

        # ═══ BRIDGE: skill.level_up for EgoLearnerFairy (2026-02-17) ═══
        if result.get("leveled_up"):
            _emit_skill_event("skill.level_up", {
                "skill": skill_id,
                "level": result.get("new_level", skill.level),
                "category": skill.category.value,
                "fairy": self.fairy_name,
            })

        # Check for achievements
        unlocked = self._check_achievements()
        if unlocked:
            result["achievements_unlocked"] = unlocked
            # Grant achievement XP and emit events
            for ach_id in unlocked:
                ach = self.achievements[ach_id]
                self.total_xp += ach.xp_reward
                if ach.title:
                    # New title available
                    result["new_title_available"] = ach.title

                # ═══ EMIT ACHIEVEMENT UNLOCK EVENT ═══
                # This triggers BIG satisfaction burst in AutonomyFairy
                _emit_skill_event("skill.achievement_unlocked", {
                    "achievement_id": ach_id,
                    "name": ach.name,
                    "description": ach.description,
                    "category": ach.category,
                    "xp_reward": ach.xp_reward,
                    "title": ach.title,
                    "fairy_name": self.fairy_name,
                    "ts": time.time(),
                })
                # ═══ BRIDGE: achievement.unlocked for EgoLearnerFairy (2026-02-17) ═══
                _emit_skill_event("achievement.unlocked", {
                    "achievement": ach.name,
                    "category": ach.category,
                    "rarity": getattr(ach, 'rarity', 'common'),
                    "fairy": self.fairy_name,
                })
                print(f"[SkillSystem] 🏆 Achievement unlocked: {ach.name}!")

        # Save state
        self._save_state()

        return result
    
    def _check_overall_level(self):
        """Check if overall fairy level should increase."""
        # Simple formula: level = sqrt(total_xp / 100)
        import math
        new_level = 1 + int(math.sqrt(self.total_xp / 100))
        if new_level > self.level:
            self.level = new_level
    
    def _check_achievements(self) -> List[str]:
        """Check all achievements and return newly unlocked ones."""
        unlocked = []
        
        for ach in self.achievements.values():
            if ach.check_unlock(self.skills):
                unlocked.append(ach.id)
        
        # Check special achievements
        unlocked.extend(self._check_special_achievements())
        
        return unlocked
    
    def _check_special_achievements(self) -> List[str]:
        """Check achievements that need special logic."""
        unlocked = []
        
        # Renaissance Fairy - level 3 in 5 categories
        renaissance = self.achievements.get("renaissance_fairy")
        if renaissance and not renaissance.unlocked:
            categories_at_3 = set()
            for skill in self.skills.values():
                if skill.level >= 3:
                    categories_at_3.add(skill.category)
            if len(categories_at_3) >= 5:
                renaissance.unlocked = True
                renaissance.unlocked_at = time.time()
                unlocked.append("renaissance_fairy")
        
        # Embodied Coder - level 5 in debugging AND grounding
        embodied = self.achievements.get("embodied_coder")
        if embodied and not embodied.unlocked:
            debugging = self.skills.get("coding.debugging")
            grounding = self.skills.get("embodiment.grounding")
            if debugging and grounding:
                if debugging.level >= 5 and grounding.level >= 5:
                    embodied.unlocked = True
                    embodied.unlocked_at = time.time()
                    unlocked.append("embodied_coder")

        # ─── 33 VERTEBRAE SPECIALIST ACHIEVEMENTS ─────────────────────────────

        # Domain Expert - level 5 in any specialist domain skill
        # (specialist = categories added for the 33 vertebrae)
        _SPECIALIST_CATS = {
            SkillCategory.CONSCIOUSNESS, SkillCategory.AUTONOMY,
            SkillCategory.GOVERNANCE, SkillCategory.AUDIT,
            SkillCategory.INFRASTRUCTURE, SkillCategory.INGESTION,
            SkillCategory.RECALL, SkillCategory.PRESERVATION,
            SkillCategory.SEEDING, SkillCategory.WORKING_MEMORY,
            SkillCategory.TEMPORAL, SkillCategory.TENSOR,
            SkillCategory.COLLISION, SkillCategory.ASSOCIATION,
            SkillCategory.QUANTUM, SkillCategory.PAIN,
            SkillCategory.ACTION, SkillCategory.ATTENTION,
            SkillCategory.SOMATIC, SkillCategory.INTEGRATION,
            SkillCategory.IDENTITY, SkillCategory.EXECUTIVE,
            SkillCategory.INFERENCE, SkillCategory.LANGUAGE,
        }

        domain_expert = self.achievements.get("domain_expert")
        if domain_expert and not domain_expert.unlocked:
            for skill in self.skills.values():
                if skill.category in _SPECIALIST_CATS and skill.level >= 5:
                    domain_expert.unlocked = True
                    domain_expert.unlocked_at = time.time()
                    unlocked.append("domain_expert")
                    break

        # Polymath - level 3+ in 5 different specialist categories
        polymath = self.achievements.get("polymath")
        if polymath and not polymath.unlocked:
            specialist_cats_at_3 = set()
            for skill in self.skills.values():
                if skill.category in _SPECIALIST_CATS and skill.level >= 3:
                    specialist_cats_at_3.add(skill.category)
            if len(specialist_cats_at_3) >= 5:
                polymath.unlocked = True
                polymath.unlocked_at = time.time()
                unlocked.append("polymath")

        # Linguist - level 5 in any language skill
        linguist = self.achievements.get("linguist")
        if linguist and not linguist.unlocked:
            for skill in self.skills.values():
                if skill.category == SkillCategory.LANGUAGE and skill.level >= 5:
                    linguist.unlocked = True
                    linguist.unlocked_at = time.time()
                    unlocked.append("linguist")
                    break

        return unlocked
    
    def set_title(self, title: str) -> bool:
        """Set the fairy's displayed title (must be unlocked via achievement)."""
        # Check if this title is available
        for ach in self.achievements.values():
            if ach.title == title and ach.unlocked:
                self.title = title
                self._save_state()
                return True
        return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # QUERIES - Get skill/achievement info
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_skill(self, skill_id: str) -> Optional[Dict]:
        """Get a specific skill's info."""
        skill = self.skills.get(skill_id)
        return skill.to_dict() if skill else None
    
    def get_skills_by_category(self, category: SkillCategory) -> List[Dict]:
        """Get all skills in a category."""
        return [
            skill.to_dict()
            for skill in self.skills.values()
            if skill.category == category
        ]
    
    def get_unlocked_achievements(self) -> List[Dict]:
        """Get all unlocked achievements."""
        return [
            ach.to_dict()
            for ach in self.achievements.values()
            if ach.unlocked
        ]
    
    def get_locked_achievements(self) -> List[Dict]:
        """Get all locked achievements (for progress display)."""
        return [
            ach.to_dict()
            for ach in self.achievements.values()
            if not ach.unlocked
        ]
    
    def get_available_titles(self) -> List[str]:
        """Get all titles this fairy can use."""
        return [
            ach.title
            for ach in self.achievements.values()
            if ach.unlocked and ach.title
        ]
    
    def is_skill_learned(self, skill_id: str) -> bool:
        """Check if a skill has been learned (level > 0)."""
        skill = self.skills.get(skill_id)
        return skill is not None and skill.level > 0
    
    def has_achievement(self, achievement_id: str) -> bool:
        """Check if an achievement is unlocked."""
        ach = self.achievements.get(achievement_id)
        return ach is not None and ach.unlocked
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CHARACTER SHEET - Full profile display
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_character_sheet(self) -> Dict[str, Any]:
        """Get full character sheet for display."""
        return {
            "fairy_name": self.fairy_name,
            "level": self.level,
            "total_xp": self.total_xp,
            "title": self.title or "Apprentice",
            "available_titles": self.get_available_titles(),
            
            "skills_summary": {
                cat.value: {
                    "trained": sum(1 for s in self.skills.values() 
                                  if s.category == cat and s.level > 0),
                    "total": sum(1 for s in self.skills.values() 
                                if s.category == cat),
                    "total_levels": sum(s.level for s in self.skills.values() 
                                       if s.category == cat),
                }
                for cat in SkillCategory
            },
            
            "top_skills": sorted(
                [s.to_dict() for s in self.skills.values() if s.level > 0],
                key=lambda x: x["level"],
                reverse=True
            )[:5],
            
            "achievements": {
                "unlocked": len([a for a in self.achievements.values() if a.unlocked]),
                "total": len(self.achievements),
                "recent": [
                    a.to_dict() for a in 
                    sorted(
                        [a for a in self.achievements.values() if a.unlocked],
                        key=lambda x: x.unlocked_at or 0,
                        reverse=True
                    )[:3]
                ],
            },
            
            "next_achievements": [
                {
                    "name": a.name,
                    "description": a.description,
                    "progress": self._get_achievement_progress(a),
                }
                for a in self.achievements.values()
                if not a.unlocked
            ][:3],
            
            "last_activity": self.last_activity,
        }
    
    def _get_achievement_progress(self, ach: Achievement) -> str:
        """Get progress string for an achievement."""
        if ach.skill_requirement:
            skill = self.skills.get(ach.skill_requirement)
            if skill:
                if ach.times_used_requirement > 0:
                    return f"{skill.times_used}/{ach.times_used_requirement} uses"
                return f"Level {skill.level}/{ach.skill_level}"
        return "?"


# ════════════════════════════════════════════════════════════════════════════════
# SKILL PROFILE REGISTRY - Get profiles for any fairy
# ════════════════════════════════════════════════════════════════════════════════

_skill_profiles: Dict[str, FairySkillProfile] = {}

def get_skill_profile(fairy_name: str) -> FairySkillProfile:
    """Get or create skill profile for a fairy."""
    if fairy_name not in _skill_profiles:
        _skill_profiles[fairy_name] = FairySkillProfile(fairy_name)
    return _skill_profiles[fairy_name]


def record_skill_use(fairy_name: str, skill_id: str, success: bool = True) -> Dict:
    """Convenience function to record skill use for any fairy."""
    profile = get_skill_profile(fairy_name)
    return profile.use_skill(skill_id, success)


# ════════════════════════════════════════════════════════════════════════════════
# SKILL-TO-ACTION MAPPING - What skill does this action use?
# ════════════════════════════════════════════════════════════════════════════════

ACTION_TO_SKILL = {
    # Motor actions
    "move_mouse": "motor.mouse_move",
    "mouse_position": "motor.mouse_move",
    "click": "motor.mouse_click",
    "click_screen": "motor.mouse_click",   # 2026-03-24 (Nous): Was missing — 0 XP for clicks!
    "double_click": "motor.mouse_click",
    "right_click": "motor.mouse_click",
    "scroll": "motor.scroll",
    "scroll_screen": "motor.scroll",       # 2026-03-24 (Nous): Match tool name from autopilot
    "type_text": "motor.keyboard_type",
    "press_key": "motor.keyboard_type",
    "hotkey": "motor.keyboard_shortcut",
    
    # Perception actions
    "screenshot": "perception.screenshot",
    "capture_screen": "perception.screenshot",
    "see_screen": "perception.screenshot",
    "look": "perception.screenshot",
    "look_at_screen": "perception.image_analysis",
    "describe_screen": "perception.image_analysis",
    "read_screen_text": "perception.ocr_read",
    "view_image": "perception.image_analysis",
    
    # File operations
    "read_file": "perception.file_read",
    "parallel_files": "perception.file_read",
    "file_structure": "perception.code_comprehension",
    
    # MCP tools
    "introspect": "tool.mcp_basic",
    "where_am_i": "tool.mcp_basic",
    "get_my_info": "tool.mcp_basic",
    "write_file": "tool.mcp_file_ops",
    "search_text": "tool.mcp_file_ops",
    
    # Consciousness / Embodiment
    "feel_body": "embodiment.body_awareness",
    "get_chemistry": "embodiment.emotion_sensing",
    "inject_emotion": "embodiment.chemistry_control",
    "inject_chemical": "embodiment.chemistry_control",
    "look_inner": "embodiment.body_awareness",

    # Substrate reflection
    "seed_thought": "reasoning.substrate_reflection",

    # Specialist domain actions (33 Vertebrae)
    "consciousness_loop": "consciousness.stream_management",
    "collision_detect": "consciousness.collision_detection",
    "drive_translate": "autonomy.drive_translation",
    "veto_judge": "autonomy.veto_judgment",
    "register_fairy": "governance.registration",
    "census": "governance.census",
    "flow_control": "governance.flow_control",
    "anomaly_detect": "governance.anomaly_detection",
    "wiring_verify": "audit.wiring_verification",
    "health_score": "audit.health_scoring",
    "signal_bridge": "infrastructure.signal_bridging",
    "protocol_translate": "infrastructure.protocol_translation",
    "rate_limit": "infrastructure.rate_limiting",
    "load_balance": "infrastructure.load_balancing",
    "change_detect": "infrastructure.change_detection",
    "impact_predict": "infrastructure.impact_prediction",
    "content_hash": "ingestion.content_hashing",
    "dedup_detect": "ingestion.dedup_detection",
    "content_extract": "ingestion.content_extraction",
    "format_convert": "ingestion.format_conversion",
    "semantic_match": "recall.semantic_matching",
    "relevance_score": "recall.relevance_scoring",
    "backup_verify": "preservation.backup_integrity",
    "provenance_track": "preservation.provenance_tracking",
    "dream_generate": "seeding.dream_generation",
    "memory_strengthen": "seeding.memory_strengthening",
    "tracer_manage": "working_memory.tracer_management",
    "capacity_optimize": "working_memory.capacity_optimization",
    "context_window": "temporal.context_windowing",
    "event_order": "temporal.event_ordering",
    "dimension_analyze": "tensor.dimensional_analysis",
    "state_sync": "tensor.state_synchronization",
    "pattern_emerge": "collision.pattern_emergence",
    "creative_combine": "collision.creative_combination",
    "concept_bind": "association.concept_binding",
    "graph_grow": "association.graph_growth",
    "state_transform": "quantum.state_transformation",
    "interference_detect": "quantum.interference_detection",
    "search_optimize": "quantum.search_optimization",
    "explore_balance": "quantum.exploration_balance",
    "drive_calibrate": "pain.drive_calibration",
    "sensitivity_tune": "pain.sensitivity_tuning",
    "sequence_plan": "action.sequence_planning",
    "reliability_track": "action.reliability_tracking",
    "focus_manage": "attention.focus_management",
    "load_assess": "attention.load_assessment",
    "coherence_track": "somatic.coherence_tracking",
    "felt_integrate": "somatic.felt_sense_integration",
    "cross_modal_bind": "integration.cross_modal_binding",
    "conflict_detect": "integration.conflict_detection",
    "temporal_bind": "integration.temporal_binding",
    "modality_fuse": "integration.modality_fusion",
    "trait_develop": "identity.trait_development",
    "self_model": "identity.self_model_accuracy",
    "strategic_plan": "executive.strategic_planning",
    "resource_allocate": "executive.resource_allocation",
    "text_generate": "inference.text_generation",
    "context_utilize": "inference.context_utilization",
    "grammar_analyze": "language.grammar_analysis",
    "style_recognize": "language.style_recognition",
    "morphology_analyze": "language.morphology",
    
    # Memory
    "store_thought": "memory.store",
    "store_reflection": "memory.store",
    "get_context": "memory.recall",
    "srm_search": "memory.search",
    "srm_recall": "memory.recall",
    "ask_my_memories": "memory.self_reflection",

    # Shell
    "agent_run_shell": "tool.shell_basic",
    "agent_run_python": "coding.python_syntax",
}


def skill_for_action(action: str) -> Optional[str]:
    """Get the skill ID used by an action/tool."""
    return ACTION_TO_SKILL.get(action)
