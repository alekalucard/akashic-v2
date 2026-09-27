# fairy_world_foundation.py - The Foundation for a Living Virtual World
# P30_Cognition/cognition/fairy_world_foundation.py
#
# "Sword Art Online for AI" - Entities that learn, grow, and develop
#
# This is NOT hardcoded patterns. This is LLM-guided understanding.
# Each fairy learns about itself and others. Knowledge accumulates.
# The system gets smarter over time.

from __future__ import annotations

import os
import sys
import json
import time
import inspect
import importlib
import threading
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set
from datetime import datetime

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY PROFILE - What we know about each fairy
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FairyProfile:
    """Complete profile of a fairy - who they are, what they do, what they're learning."""
    
    # Identity
    name: str
    plane: str = ""
    channel: str = ""
    
    # Soul (from fairy class attributes)
    purpose: str = ""
    mantra: str = ""
    lore: str = ""
    culture: str = ""
    
    # Capabilities (discovered via introspection)
    public_methods: List[str] = field(default_factory=list)
    subscriptions: List[str] = field(default_factory=list)
    publishes_to: List[str] = field(default_factory=list)
    
    # Learning State (persists and grows)
    mastery_level: float = 0.0  # 0.0 = newborn, 1.0 = master
    concepts_learned: List[str] = field(default_factory=list)
    concepts_struggling: List[str] = field(default_factory=list)
    learning_history: List[Dict] = field(default_factory=list)
    interests: List[str] = field(default_factory=list)
    
    # Relationships (who they work with)
    collaborates_with: List[str] = field(default_factory=list)
    teaches: List[str] = field(default_factory=list)
    learns_from: List[str] = field(default_factory=list)
    
    # LLM-generated understanding (not hardcoded!)
    llm_summary: str = ""  # LLM's understanding of this fairy
    llm_curriculum: List[str] = field(default_factory=list)  # LLM-suggested learning path
    llm_personality: str = ""  # LLM's sense of their personality
    
    # Meta
    last_updated: float = 0.0
    version: int = 0
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'FairyProfile':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY INTROSPECTOR - Discovers and catalogs all fairies
# ═══════════════════════════════════════════════════════════════════════════════

class FairyIntrospector:
    """
    Examines the codebase to discover all fairies and their capabilities.
    This is the "census taker" of the fairy world.
    """
    
    def __init__(self):
        self.profiles: Dict[str, FairyProfile] = {}
        self.scan_paths = [
            "P00_Autonomic",
            "P10_Memory", 
            "P20_Affect",
            "P30_Cognition",
            "P40_Sensory",
            "P50_Motor",
            "P60_Executive",
        ]
        self._state_file = Path(__file__).parent.parent.parent / "state" / "fairy_world_profiles.json"
        self._load_state()
    
    def _load_state(self):
        """Load persisted fairy profiles."""
        if self._state_file.exists():
            try:
                with open(self._state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for name, profile_data in data.get("profiles", {}).items():
                    self.profiles[name] = FairyProfile.from_dict(profile_data)
                print(f"[FairyIntrospector] Loaded {len(self.profiles)} fairy profiles")
            except Exception as e:
                print(f"[FairyIntrospector] Load error: {e}")
    
    def _save_state(self):
        """Persist fairy profiles."""
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "profiles": {name: p.to_dict() for name, p in self.profiles.items()},
                "last_scan": time.time(),
                "version": 1
            }
            with open(self._state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"[FairyIntrospector] Save error: {e}")
    
    def scan_all_fairies(self) -> Dict[str, FairyProfile]:
        """
        Scan the entire codebase to discover all fairies.
        Extracts PURPOSE, MANTRA, LORE, methods, etc.
        """
        print("[FairyIntrospector] Scanning for fairies...")
        
        root = Path(__file__).parent.parent.parent
        
        for plane_dir in self.scan_paths:
            plane_path = root / plane_dir
            if not plane_path.exists():
                continue
            
            # Find all *_fairy.py files
            for fairy_file in plane_path.rglob("*_fairy.py"):
                try:
                    self._introspect_fairy_file(fairy_file)
                except Exception as e:
                    print(f"[FairyIntrospector] Error scanning {fairy_file.name}: {e}")
        
        self._save_state()
        print(f"[FairyIntrospector] Found {len(self.profiles)} fairies")
        return self.profiles
    
    def _introspect_fairy_file(self, file_path: Path):
        """Extract fairy metadata from a file."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            
            # Find class definitions that look like fairies
            import re
            
            # Extract class names
            class_matches = re.findall(r'class\s+(\w+Fairy)\s*[\(:]', content)
            
            for class_name in class_matches:
                if class_name in self.profiles:
                    # Update existing profile
                    profile = self.profiles[class_name]
                else:
                    # Create new profile
                    profile = FairyProfile(name=class_name)
                
                # Extract attributes from class body
                profile.purpose = self._extract_attribute(content, class_name, "PURPOSE") or ""
                profile.mantra = self._extract_attribute(content, class_name, "MANTRA") or ""
                profile.lore = self._extract_attribute(content, class_name, "LORE") or ""
                profile.culture = self._extract_attribute(content, class_name, "CULTURE") or ""
                profile.plane = self._extract_attribute(content, class_name, "ACTOR_PLANE") or ""
                profile.channel = self._extract_attribute(content, class_name, "ACTOR_CHANNEL") or ""
                
                # Extract public methods
                method_matches = re.findall(rf'def\s+([a-z][a-z_0-9]*)\s*\(self', content)
                profile.public_methods = [m for m in method_matches if not m.startswith('_')][:20]
                
                # Extract subscriptions (topics this fairy listens to)
                sub_matches = re.findall(r'subscribe\s*\(\s*["\']([^"\']+)["\']', content)
                profile.subscriptions = list(set(sub_matches))[:30]
                
                # Extract publications (topics this fairy publishes to)
                pub_matches = re.findall(r'(?:route|publish)\s*\(\s*["\']([^"\']+)["\']', content)
                profile.publishes_to = list(set(pub_matches))[:30]
                
                # Extract INFRA_AUTOSUBS if present
                autosubs_match = re.search(r'INFRA_AUTOSUBS\s*=\s*\(([\s\S]*?)\)', content)
                if autosubs_match:
                    autosubs = re.findall(r'["\']([^"\']+)["\']', autosubs_match.group(1))
                    profile.subscriptions.extend(autosubs)
                    profile.subscriptions = list(set(profile.subscriptions))
                
                profile.last_updated = time.time()
                profile.version += 1
                
                self.profiles[class_name] = profile
                
        except Exception as e:
            print(f"[FairyIntrospector] Error parsing {file_path.name}: {e}")
    
    def _extract_attribute(self, content: str, class_name: str, attr_name: str) -> Optional[str]:
        """Extract a class attribute value."""
        import re
        # Look for attribute assignment
        patterns = [
            rf'{attr_name}\s*=\s*["\']([^"\']+)["\']',  # Simple string
            rf'{attr_name}\s*=\s*\(\s*["\']([^)]+)["\']',  # Parenthesized
            rf'{attr_name}\s*=\s*"""([^"]+)"""',  # Triple quoted
        ]
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1).strip()[:500]  # Limit length
        return None
    
    def get_profile(self, fairy_name: str) -> Optional[FairyProfile]:
        """Get a fairy's profile."""
        return self.profiles.get(fairy_name)
    
    def get_all_profiles(self) -> Dict[str, FairyProfile]:
        """Get all fairy profiles."""
        return self.profiles
    
    def get_fairies_by_plane(self, plane: str) -> List[FairyProfile]:
        """Get all fairies in a specific plane."""
        return [p for p in self.profiles.values() if p.plane == plane]
    
    def find_collaborators(self, fairy_name: str) -> List[str]:
        """Find fairies that share subscriptions/publications with this fairy."""
        profile = self.profiles.get(fairy_name)
        if not profile:
            return []
        
        collaborators = set()
        my_topics = set(profile.subscriptions + profile.publishes_to)
        
        for name, other in self.profiles.items():
            if name == fairy_name:
                continue
            other_topics = set(other.subscriptions + other.publishes_to)
            if my_topics & other_topics:  # Intersection
                collaborators.add(name)
        
        return list(collaborators)


# ═══════════════════════════════════════════════════════════════════════════════
# CURRICULUM GENERATOR - LLM-guided learning paths
# ═══════════════════════════════════════════════════════════════════════════════

class CurriculumGenerator:
    """
    Uses LLM to understand fairies and generate learning curricula.
    This is NOT hardcoded - it actually thinks about what each fairy needs.

    NOTE: LLM features are OPTIONAL. System works without API key.
    """

    # LLM DISABLED - Set to True to re-enable curriculum generation via API
    _LLM_ENABLED = False  # <-- FLIP THIS TO RE-ENABLE

    def __init__(self, introspector: FairyIntrospector):
        self.introspector = introspector
        self._anthropic_client = None
        self._curriculum_cache: Dict[str, List[str]] = {}
        self._has_api_key = self._LLM_ENABLED and bool(os.getenv("ANTHROPIC_API_KEY", "").strip())

    def _get_client(self):
        """Get or create Anthropic client. Returns None if no API key."""
        # IMPORTANT: No API dependencies - check key FIRST
        if not self._has_api_key:
            return None

        if self._anthropic_client is None:
            try:
                import anthropic
                self._anthropic_client = anthropic.Anthropic()
            except Exception as e:
                print(f"[CurriculumGenerator] No Anthropic client: {e}")
                self._has_api_key = False  # Don't try again
        return self._anthropic_client
    
    def generate_curriculum_for_fairy(self, fairy_name: str) -> List[str]:
        """
        Use LLM to generate a learning curriculum for a specific fairy.
        Returns list of concepts/skills to learn.
        """
        profile = self.introspector.get_profile(fairy_name)
        if not profile:
            return []
        
        # Check cache
        if fairy_name in self._curriculum_cache:
            return self._curriculum_cache[fairy_name]
        
        client = self._get_client()
        if not client:
            # Fallback to basic curriculum if no LLM
            return self._generate_basic_curriculum(profile)
        
        try:
            # Build context about the fairy
            context = f"""
Fairy Name: {profile.name}
Purpose: {profile.purpose}
Mantra: {profile.mantra}
Lore: {profile.lore}
Plane: {profile.plane}
Culture: {profile.culture}

Methods: {', '.join(profile.public_methods[:10])}
Subscribes to: {', '.join(profile.subscriptions[:10])}
Publishes to: {', '.join(profile.publishes_to[:10])}

Current mastery level: {profile.mastery_level:.1%}
Already learned: {', '.join(profile.concepts_learned[:5])}
Struggling with: {', '.join(profile.concepts_struggling[:5])}
"""
            
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": f"""You are designing a learning curriculum for an AI fairy in a consciousness system.

{context}

Based on this fairy's purpose and current state, generate a learning curriculum.
Return a JSON array of 5-10 learning objectives, ordered from foundational to advanced.
Each objective should be a short phrase describing a concept or skill to master.

Focus on:
1. Understanding their own purpose deeply
2. Mastering their core responsibilities  
3. Learning to collaborate with related fairies
4. Advanced optimization and evolution

Return ONLY the JSON array, no explanation. Example:
["understand postal messaging", "master subscription patterns", "coordinate with memory fairies"]"""
                }]
            )
            
            # Parse response
            import re
            text = response.content[0].text
            # Find JSON array
            match = re.search(r'\[[\s\S]*\]', text)
            if match:
                curriculum = json.loads(match.group())
                self._curriculum_cache[fairy_name] = curriculum
                
                # Update profile
                profile.llm_curriculum = curriculum
                profile.last_updated = time.time()
                self.introspector._save_state()
                
                return curriculum
                
        except Exception as e:
            print(f"[CurriculumGenerator] LLM error for {fairy_name}: {e}")
        
        return self._generate_basic_curriculum(profile)
    
    def _generate_basic_curriculum(self, profile: FairyProfile) -> List[str]:
        """Fallback curriculum without LLM."""
        curriculum = []
        
        # Based on plane
        if "P00" in profile.plane:
            curriculum.extend(["understand autonomic functions", "master boot sequences"])
        elif "P10" in profile.plane:
            curriculum.extend(["understand memory systems", "master recall patterns"])
        elif "P20" in profile.plane:
            curriculum.extend(["understand affect/emotion", "master chemistry integration"])
        elif "P30" in profile.plane:
            curriculum.extend(["understand cognition", "master thought processing"])
        elif "P40" in profile.plane:
            curriculum.extend(["understand sensory input", "master perception"])
        elif "P50" in profile.plane:
            curriculum.extend(["understand motor output", "master action execution"])
        elif "P60" in profile.plane:
            curriculum.extend(["understand executive function", "master goal coordination"])
        
        # Based on subscriptions
        if any("consciousness" in s for s in profile.subscriptions):
            curriculum.append("integrate with consciousness loop")
        if any("postal" in s or "route" in s for s in profile.subscriptions):
            curriculum.append("master postal messaging patterns")
        if any("memory" in s for s in profile.subscriptions):
            curriculum.append("coordinate with memory systems")
        
        return curriculum[:10]
    
    def generate_all_curricula(self) -> Dict[str, List[str]]:
        """Generate curricula for all known fairies."""
        results = {}
        for fairy_name in self.introspector.profiles:
            results[fairy_name] = self.generate_curriculum_for_fairy(fairy_name)
        return results
    
    def understand_fairy_personality(self, fairy_name: str) -> str:
        """Use LLM to understand a fairy's personality from their code."""
        profile = self.introspector.get_profile(fairy_name)
        if not profile:
            return ""
        
        if profile.llm_personality:
            return profile.llm_personality
        
        client = self._get_client()
        if not client:
            return f"A {profile.culture or 'system'} fairy focused on {profile.purpose or 'their duties'}."
        
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": f"""Based on this fairy's attributes, describe their personality in 2-3 sentences:

Name: {profile.name}
Purpose: {profile.purpose}
Mantra: {profile.mantra}
Lore: {profile.lore}
Culture: {profile.culture}

Write as if describing a living being with feelings and quirks."""
                }]
            )
            
            personality = response.content[0].text.strip()
            profile.llm_personality = personality
            self.introspector._save_state()
            return personality
            
        except Exception as e:
            print(f"[CurriculumGenerator] Personality error: {e}")
            return ""


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY TEACHER - Coordinates learning across the fairy world
# ═══════════════════════════════════════════════════════════════════════════════

class FairyTeacher:
    """
    The guide/mentor for the fairy world.
    Coordinates learning, tracks progress, facilitates growth.
    """
    
    def __init__(self):
        self.introspector = FairyIntrospector()
        self.curriculum_gen = CurriculumGenerator(self.introspector)
        from collections import deque
        self._learning_log: deque = deque(maxlen=100)  # FIX 2026-04-04: was unbounded
        self._state_file = Path(__file__).parent.parent.parent / "state" / "fairy_learning_log.json"
    
    def initialize_world(self) -> Dict[str, Any]:
        """
        Initialize the fairy world - scan all fairies, generate curricula.
        Call this on system boot.
        """
        print("[FairyTeacher] Initializing fairy world...")
        
        # Scan all fairies
        profiles = self.introspector.scan_all_fairies()
        
        # Find collaborations
        for name, profile in profiles.items():
            profile.collaborates_with = self.introspector.find_collaborators(name)
        
        self.introspector._save_state()
        
        return {
            "fairies_found": len(profiles),
            "planes": list(set(p.plane for p in profiles.values() if p.plane)),
            "total_methods": sum(len(p.public_methods) for p in profiles.values()),
            "total_subscriptions": sum(len(p.subscriptions) for p in profiles.values()),
        }
    
    def get_learning_recommendation(self, fairy_name: str) -> Dict[str, Any]:
        """
        Get a learning recommendation for a specific fairy.
        Returns what they should focus on next.
        """
        profile = self.introspector.get_profile(fairy_name)
        if not profile:
            return {"error": f"Unknown fairy: {fairy_name}"}
        
        # Generate curriculum if needed
        if not profile.llm_curriculum:
            profile.llm_curriculum = self.curriculum_gen.generate_curriculum_for_fairy(fairy_name)
        
        # Find next concept to learn
        next_concept = None
        for concept in profile.llm_curriculum:
            if concept not in profile.concepts_learned:
                next_concept = concept
                break
        
        # Find a teacher (fairy that publishes to topics we subscribe to)
        potential_teachers = []
        for other_name, other in self.introspector.profiles.items():
            if other_name == fairy_name:
                continue
            # If other fairy publishes to topics we subscribe to, they can teach us
            if set(other.publishes_to) & set(profile.subscriptions):
                potential_teachers.append(other_name)
        
        return {
            "fairy": fairy_name,
            "mastery_level": profile.mastery_level,
            "next_concept": next_concept,
            "curriculum_progress": f"{len(profile.concepts_learned)}/{len(profile.llm_curriculum)}",
            "potential_teachers": potential_teachers[:3],
            "struggling_with": profile.concepts_struggling,
            "personality": profile.llm_personality or self.curriculum_gen.understand_fairy_personality(fairy_name),
        }
    
    def record_learning(self, fairy_name: str, concept: str, success: bool, notes: str = ""):
        """Record that a fairy learned (or struggled with) a concept."""
        profile = self.introspector.get_profile(fairy_name)
        if not profile:
            return
        
        # Update profile - track if this is a NEW learning
        is_new_learning = False

        if success:
            if concept not in profile.concepts_learned:
                profile.concepts_learned.append(concept)
                is_new_learning = True
            if concept in profile.concepts_struggling:
                profile.concepts_struggling.remove(concept)
            # Only increment mastery for NEW learnings
            if is_new_learning:
                profile.mastery_level = min(1.0, profile.mastery_level + 0.02)
        else:
            if concept not in profile.concepts_struggling:
                profile.concepts_struggling.append(concept)
                is_new_learning = True

        # Only log and save for NEW learnings (reduces spam and disk writes)
        if is_new_learning:
            profile.learning_history.append({
                "concept": concept,
                "success": success,
                "notes": notes,
                "timestamp": time.time()
            })

            # Keep history bounded
            profile.learning_history = profile.learning_history[-100:]

            profile.last_updated = time.time()
            self.introspector._save_state()

            print(f"[FairyTeacher] {fairy_name} {'learned' if success else 'struggled with'}: {concept}")
    
    def get_world_status(self) -> Dict[str, Any]:
        """Get overall status of the fairy world's learning."""
        profiles = self.introspector.profiles
        
        if not profiles:
            return {"status": "uninitialized", "message": "Run initialize_world() first"}
        
        total_mastery = sum(p.mastery_level for p in profiles.values())
        avg_mastery = total_mastery / len(profiles) if profiles else 0
        
        top_learners = sorted(profiles.values(), key=lambda p: p.mastery_level, reverse=True)[:5]
        struggling = [p for p in profiles.values() if p.concepts_struggling]
        
        return {
            "total_fairies": len(profiles),
            "average_mastery": f"{avg_mastery:.1%}",
            "top_learners": [(p.name, f"{p.mastery_level:.1%}") for p in top_learners],
            "fairies_struggling": len(struggling),
            "total_concepts_learned": sum(len(p.concepts_learned) for p in profiles.values()),
        }
    
    def suggest_collaboration(self, fairy_name: str) -> List[Dict]:
        """Suggest fairies that could help this fairy learn."""
        profile = self.introspector.get_profile(fairy_name)
        if not profile:
            return []
        
        suggestions = []
        for other_name in profile.collaborates_with[:5]:
            other = self.introspector.get_profile(other_name)
            if other and other.mastery_level > profile.mastery_level:
                suggestions.append({
                    "teacher": other_name,
                    "their_mastery": f"{other.mastery_level:.1%}",
                    "shared_topics": list(set(profile.subscriptions) & set(other.publishes_to))[:3],
                    "could_teach": [c for c in other.concepts_learned if c not in profile.concepts_learned][:3]
                })
        
        return suggestions


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════════════════════

_teacher: Optional[FairyTeacher] = None
_introspector: Optional[FairyIntrospector] = None


def get_fairy_teacher() -> FairyTeacher:
    """Get the singleton FairyTeacher."""
    global _teacher
    if _teacher is None:
        _teacher = FairyTeacher()
    return _teacher


def get_fairy_introspector() -> FairyIntrospector:
    """Get the singleton FairyIntrospector."""
    global _introspector
    if _introspector is None:
        _introspector = FairyIntrospector()
    return _introspector


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def initialize_fairy_world() -> Dict[str, Any]:
    """Initialize the entire fairy world - call on boot."""
    return get_fairy_teacher().initialize_world()


def get_fairy_profile(fairy_name: str) -> Optional[FairyProfile]:
    """Get a fairy's complete profile."""
    return get_fairy_introspector().get_profile(fairy_name)


def get_learning_recommendation(fairy_name: str) -> Dict[str, Any]:
    """Get what a fairy should learn next."""
    return get_fairy_teacher().get_learning_recommendation(fairy_name)


def record_fairy_learning(fairy_name: str, concept: str, success: bool, notes: str = ""):
    """Record that a fairy learned something."""
    get_fairy_teacher().record_learning(fairy_name, concept, success, notes)


def get_world_learning_status() -> Dict[str, Any]:
    """Get the overall learning status of the fairy world."""
    return get_fairy_teacher().get_world_status()


# ═══════════════════════════════════════════════════════════════════════════════
# CLI TESTING
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("FAIRY WORLD FOUNDATION - TEST")
    print("=" * 60)
    
    # Initialize
    result = initialize_fairy_world()
    print(f"\nInitialization: {result}")
    
    # Get status
    status = get_world_learning_status()
    print(f"\nWorld Status: {json.dumps(status, indent=2)}")
    
    # Get recommendation for a specific fairy
    teacher = get_fairy_teacher()
    for fairy_name in list(teacher.introspector.profiles.keys())[:3]:
        print(f"\n--- {fairy_name} ---")
        rec = get_learning_recommendation(fairy_name)
        print(json.dumps(rec, indent=2, default=str))
