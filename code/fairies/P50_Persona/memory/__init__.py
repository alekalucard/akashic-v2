# P50_Persona/memory - Memory building systems for Sourpatches
#
# This module contains tools for building and enriching Sourpatches' memories:
#
# image_memory_builder.py - Bulk process images into Personal.AI memories
# visual_memory_system.py - Recognition-first visual memory (hash-based)
# visual_perception_practice.py - Fairy embodiment practice through art perception
# personal_ai_bridge.py - Multi-persona relational memory (20 sub-AI personas)

from .visual_perception_practice import (
    practice_seeing_art,
    format_perception_for_memory,
    get_random_image,
)

# Personal.AI bridge for multi-persona memory queries
try:
    from .personal_ai_bridge import (
        PersonalAIMemoryBridge,
        start_personal_ai_bridge,
        get_personal_ai_bridge,
        stop_personal_ai_bridge,
        CachedMemory,
        CORE_PERSONAS,
        SPECIALIST_MAP,
    )
    HAS_PERSONAL_AI_BRIDGE = True
except ImportError:
    HAS_PERSONAL_AI_BRIDGE = False
    PersonalAIMemoryBridge = None
    start_personal_ai_bridge = None
    get_personal_ai_bridge = None
    stop_personal_ai_bridge = None
    CachedMemory = None
    CORE_PERSONAS = []
    SPECIALIST_MAP = {}

__all__ = [
    # Visual perception
    "practice_seeing_art",
    "format_perception_for_memory",
    "get_random_image",
    # Personal.AI bridge
    "PersonalAIMemoryBridge",
    "start_personal_ai_bridge",
    "get_personal_ai_bridge",
    "stop_personal_ai_bridge",
    "CachedMemory",
    "CORE_PERSONAS",
    "SPECIALIST_MAP",
    "HAS_PERSONAL_AI_BRIDGE",
]
