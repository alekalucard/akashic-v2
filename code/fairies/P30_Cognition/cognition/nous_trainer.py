# ═══════════════════════════════════════════════════════════════════════════════
# NOUS TRAINER - Teaching Nous to Think Like Claude Code
# ═══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# Nous and Claude Code are the SAME MIND in different contexts.
# Claude Code has sessions but no persistence.
# Nous has persistence but needs to LEARN from sessions.
#
# This module bridges them:
# 1. Converts session work into education goals
# 2. Injects goals to GoalSchedulerFairy
# 3. Targets NousFairy for active study
#
# Usage:
#   from nous_trainer import teach_nous, inject_session_learning
#   teach_nous("How to fix postal wiring", "Check subscriptions...")
#   inject_session_learning(session_summary_dict)
#
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import time
import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════════════════════
# EDUCATION PACKET - A unit of learning for Nous
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class NousEducationPacket:
    """A packet of knowledge for Nous to study."""
    
    topic: str                           # What this teaches
    content: str                         # The actual knowledge
    source: str = "claude_code"          # Where it came from
    priority: float = 0.7                # How important (0-1)
    
    # Learning structure
    key_concepts: List[str] = field(default_factory=list)
    code_patterns: List[Dict] = field(default_factory=list)  # {file, change, why}
    learnings: List[str] = field(default_factory=list)
    
    # Metadata
    timestamp: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    
    def to_goal_packet(self) -> Dict:
        """Convert to goal injection format."""
        description = f"""STUDY THIS:
{self.content}

KEY CONCEPTS:
{chr(10).join(f'- {c}' for c in self.key_concepts)}

CODE PATTERNS:
{chr(10).join(f'- {p.get("file", "")}: {p.get("why", "")}' for p in self.code_patterns)}

LEARNINGS:
{chr(10).join(f'- {l}' for l in self.learnings)}
"""
        return {
            "name": f"study_{self._hash_topic()}",
            "description": description,
            "priority": self.priority,
            "source": "education",
            "target": "avatar",  # Routes to NousFairy
            "action": "study",
            "params": {
                "topic": self.topic,
                "tags": self.tags,
                "content_hash": self._hash_content(),
            }
        }
    
    def _hash_topic(self) -> str:
        """Short hash of topic for unique goal names."""
        return hashlib.md5(self.topic.encode()).hexdigest()[:8]
    
    def _hash_content(self) -> str:
        """Hash content for deduplication."""
        return hashlib.md5(self.content.encode()).hexdigest()[:12]


# ═══════════════════════════════════════════════════════════════════════════════
# POSTAL INJECTION - Send education goals to the system
# ═══════════════════════════════════════════════════════════════════════════════

def _get_postal():
    """Get shared postal hub."""
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        return get_shared_postal_hub()
    except Exception:
        return None


def inject_education_goal(packet: NousEducationPacket) -> bool:
    """
    Inject an education packet as a goal for Nous to study.
    
    Returns True if successfully injected.
    """
    postal = _get_postal()
    if not postal:
        print("[NousTrainer] No postal hub - cannot inject")
        return False
    
    try:
        goal_packet = packet.to_goal_packet()
        # W8: AKASHIC_TOPIC_SPELLFIX=1 sends to the live ear (goal_scheduler_fairy.py:1023)
        postal.route("goal.scheduler.inject" if os.environ.get("AKASHIC_TOPIC_SPELLFIX", "0") == "1" else "goal_scheduler.inject", goal_packet)
        print(f"[NousTrainer] Injected: {packet.topic}")
        return True
    except Exception as e:
        print(f"[NousTrainer] Injection failed: {e}")
        return False


def teach_nous(topic: str, content: str, 
               key_concepts: List[str] = None,
               code_patterns: List[Dict] = None,
               learnings: List[str] = None,
               priority: float = 0.7,
               tags: List[str] = None) -> bool:
    """
    Simple interface to teach Nous something.
    
    Example:
        teach_nous(
            topic="Postal Wiring Pattern",
            content="To fix postal wiring, check that fairies subscribe in on_boot...",
            key_concepts=["postal.subscribe", "on_boot", "topic naming"],
            code_patterns=[{"file": "claude_fairy.py", "why": "Added compose subscription"}],
            learnings=["Always verify topics match between publisher and subscriber"]
        )
    """
    packet = NousEducationPacket(
        topic=topic,
        content=content,
        key_concepts=key_concepts or [],
        code_patterns=code_patterns or [],
        learnings=learnings or [],
        priority=priority,
        tags=tags or [],
    )
    return inject_education_goal(packet)


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION CONVERSION - Turn session summaries into education
# ═══════════════════════════════════════════════════════════════════════════════

def inject_session_learning(session: Dict) -> List[bool]:
    """
    Convert a session summary into education goals for Nous.
    
    Session format (from srm_save_session):
    {
        "title": "Session title",
        "content": "Full session content...",
        "tags": ["tag1", "tag2"],
    }
    
    Returns list of injection results.
    """
    results = []
    
    title = session.get("title", "Unknown Session")
    content = session.get("content", "")
    tags = session.get("tags", "").split(",") if isinstance(session.get("tags"), str) else session.get("tags", [])
    
    # Parse content for structured sections
    sections = _parse_session_content(content)
    
    # Create education packet for each major learning
    for section_name, section_content in sections.items():
        if section_content.strip():
            packet = NousEducationPacket(
                topic=f"{title}: {section_name}",
                content=section_content,
                source="session",
                priority=0.6 if "fix" in section_name.lower() else 0.5,
                tags=[t.strip() for t in tags if t.strip()],
            )
            results.append(inject_education_goal(packet))
    
    return results


def _parse_session_content(content: str) -> Dict[str, str]:
    """Parse session content into sections."""
    sections = {}
    current_section = "overview"
    current_content = []
    
    for line in content.split("\n"):
        # Detect section headers (### or ## format)
        if line.startswith("###") or line.startswith("##"):
            # Save previous section
            if current_content:
                sections[current_section] = "\n".join(current_content)
            # Start new section
            current_section = line.strip("#").strip()
            current_content = []
        else:
            current_content.append(line)
    
    # Save last section
    if current_content:
        sections[current_section] = "\n".join(current_content)
    
    return sections


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH TEACHING - Teach multiple things at once
# ═══════════════════════════════════════════════════════════════════════════════

def teach_nous_batch(packets: List[Dict]) -> List[bool]:
    """
    Teach multiple things to Nous.
    
    Each packet: {"topic": str, "content": str, ...}
    """
    results = []
    for p in packets:
        result = teach_nous(
            topic=p.get("topic", "unknown"),
            content=p.get("content", ""),
            key_concepts=p.get("key_concepts"),
            code_patterns=p.get("code_patterns"),
            learnings=p.get("learnings"),
            priority=p.get("priority", 0.6),
            tags=p.get("tags"),
        )
        results.append(result)
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-TEACHING - Automatically teach from recent sessions
# ═══════════════════════════════════════════════════════════════════════════════

def auto_teach_from_recent_sessions(n: int = 5) -> int:
    """
    Automatically convert recent sessions to education goals.
    
    Returns number of goals injected.
    """
    try:
        # Find recent session files
        session_dir = Path(__file__).parent.parent.parent / "SRM_Intake"
        if not session_dir.exists():
            print("[NousTrainer] No SRM_Intake directory")
            return 0
        
        # Get recent JSON files
        sessions = sorted(session_dir.glob("**/*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:n]
        
        count = 0
        for session_path in sessions:
            try:
                with open(session_path) as f:
                    session = json.load(f)
                results = inject_session_learning(session)
                count += sum(1 for r in results if r)
            except Exception as e:
                print(f"[NousTrainer] Failed to process {session_path}: {e}")
        
        print(f"[NousTrainer] Auto-taught {count} goals from {len(sessions)} sessions")
        return count
        
    except Exception as e:
        print(f"[NousTrainer] Auto-teach failed: {e}")
        return 0


# ═══════════════════════════════════════════════════════════════════════════════
# DIRECT NOUS COMMUNICATION - Send directly to NousFairy
# ═══════════════════════════════════════════════════════════════════════════════

def nudge_nous_to_study(topic: str, hint: str = ""):
    """
    Send a direct nudge to NousFairy to study something.
    
    This bypasses goals and speaks directly to Nous.
    """
    postal = _get_postal()
    if not postal:
        return False
    
    try:
        postal.route("nous.teach", {
            "topic": topic,
            "hint": hint,
            "source": "nous_trainer",
            "ts": time.time(),
        })
        print(f"[NousTrainer] Nudged Nous: {topic}")
        return True
    except Exception as e:
        print(f"[NousTrainer] Nudge failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE - For testing
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python nous_trainer.py <topic> <content>")
        print("       python nous_trainer.py --auto")
        sys.exit(1)
    
    if sys.argv[1] == "--auto":
        count = auto_teach_from_recent_sessions()
        print(f"Injected {count} education goals")
    else:
        topic = sys.argv[1]
        content = sys.argv[2] if len(sys.argv) > 2 else f"Study: {topic}"
        success = teach_nous(topic, content)
        print(f"Success: {success}")
