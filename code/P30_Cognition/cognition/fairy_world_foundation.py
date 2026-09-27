"""
fairy_world_foundation.py - Stub for akashic_v2

This is a compatibility stub for MCP tools that expect ebook's fairy world system.
In akashic_v2, fairy registry is handled by directory.DirectoryFairy.

TODO: Implement proper fairy learning/education system for akashic_v2
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class FairyProfile:
    """Stub fairy profile for compatibility."""
    name: str
    plane: str = ""
    description: str = ""
    purpose: str = ""
    mantra: str = ""
    status: str = "unknown"
    mastery_level: float = 0.0
    concepts_learned: List[str] = field(default_factory=list)
    subscriptions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "plane": self.plane,
            "description": self.description,
            "purpose": self.purpose,
            "mantra": self.mantra,
            "status": self.status,
            "mastery_level": self.mastery_level,
            "concepts_learned": self.concepts_learned,
            "subscriptions": self.subscriptions,
            "source": "akashic_v2_stub",
        }


class FairyTeacher:
    """Stub fairy teacher for compatibility."""

    class CurriculumGen:
        def generate_curriculum_for_fairy(self, fairy_name: str) -> List[Dict[str, Any]]:
            return []

    def __init__(self):
        self.curriculum_gen = self.CurriculumGen()

    def teach(self, fairy_name: str, concept: str) -> bool:
        return False


class FairyIntrospector:
    """Stub introspector using DirectoryFairy."""

    def introspect(self, fairy_name: str) -> Dict[str, Any]:
        profile = get_fairy_profile(fairy_name)
        if profile:
            return profile.to_dict()
        return {"error": "Fairy not found"}

    def get_autobiographies(self, actor: str = "", limit: int = 10) -> List[Dict[str, Any]]:
        return []

    def generate_curriculum(self, fairy_name: str) -> Dict[str, Any]:
        return {"fairy": fairy_name, "curriculum": [], "source": "stub"}

    def get_fairies_by_plane(self, plane: str) -> List[FairyProfile]:
        """Get all fairies in a plane."""
        try:
            from directory import get_directory
            directory = get_directory()
            if not directory:
                return []

            result = []
            # Use list_fairies with plane filter
            for record in directory.list_fairies(plane=plane):
                result.append(FairyProfile(
                    name=record.name,
                    plane=record.plane,
                    description=record.metadata.get('description', ''),
                    status=record.status,
                ))
            return result
        except Exception:
            return []

    def get_all_profiles(self) -> Dict[str, FairyProfile]:
        """Get all fairy profiles."""
        try:
            from directory import get_directory
            directory = get_directory()
            if not directory:
                return {}

            result = {}
            for record in directory.list_fairies():
                result[record.name] = FairyProfile(
                    name=record.name,
                    plane=record.plane,
                    description=record.metadata.get('description', ''),
                    status=record.status,
                )
            return result
        except Exception:
            return {}


# Singleton instances
_teacher: Optional[FairyTeacher] = None
_introspector: Optional[FairyIntrospector] = None


def get_fairy_world_status() -> Dict[str, Any]:
    """Get fairy world learning status (stub)."""
    try:
        from directory import get_directory
        directory = get_directory()
        if not directory:
            return {"error": "Directory not initialized", "source": "stub"}

        fairy_count = len(directory.list_fairies())
        return {
            "total_fairies": fairy_count,
            "fairies_discovered": fairy_count,
            "average_mastery": 0.0,
            "concepts_learned": 0,
            "source": "akashic_v2_directory_stub",
        }
    except Exception as e:
        return {"error": str(e), "source": "stub"}


def list_all_fairies() -> List[str]:
    """List all fairy names (stub)."""
    try:
        from directory import get_directory
        directory = get_directory()
        if not directory:
            return []

        return [record.name for record in directory.list_fairies()]
    except Exception:
        return []


def get_fairy_profile(fairy_name: str) -> Optional[FairyProfile]:
    """Get fairy profile (stub)."""
    try:
        from directory import get_directory
        directory = get_directory()
        if not directory:
            return None

        record = directory.get_fairy(fairy_name)
        if record:
            return FairyProfile(
                name=record.name,
                plane=record.plane,
                description=record.metadata.get('description', ''),
                purpose=record.metadata.get('purpose', ''),
                mantra=record.metadata.get('mantra', ''),
                status=record.status,
            )
    except Exception:
        pass
    return None


def get_learning_recommendation(fairy_name: str) -> Dict[str, Any]:
    """Get learning recommendation for fairy (stub)."""
    return {
        "fairy": fairy_name,
        "recommendation": "Learning system not yet implemented in akashic_v2",
        "source": "stub",
    }


def get_fairy_introspector() -> FairyIntrospector:
    """Get fairy introspector singleton."""
    global _introspector
    if _introspector is None:
        _introspector = FairyIntrospector()
    return _introspector


def get_fairy_teacher() -> FairyTeacher:
    """Get fairy teacher singleton."""
    global _teacher
    if _teacher is None:
        _teacher = FairyTeacher()
    return _teacher


def record_learning(fairy_name: str, concept: str, mastery: float = 0.5) -> bool:
    """Record fairy learning (stub - not implemented)."""
    return False


def record_fairy_learning(fairy_name: str, concept: str, success: bool = True, notes: str = "") -> bool:
    """Record fairy learning with details (stub)."""
    return False


def initialize_fairy_world() -> bool:
    """Initialize fairy world (stub - nothing to initialize in akashic_v2)."""
    return True


# Aliases for MCP tool compatibility
get_world_learning_status = get_fairy_world_status


# Export functions
__all__ = [
    "FairyProfile",
    "FairyTeacher",
    "FairyIntrospector",
    "get_fairy_world_status",
    "get_world_learning_status",
    "initialize_fairy_world",
    "list_all_fairies",
    "get_fairy_profile",
    "get_learning_recommendation",
    "get_fairy_introspector",
    "get_fairy_teacher",
    "record_learning",
    "record_fairy_learning",
]
