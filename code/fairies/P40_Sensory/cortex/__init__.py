# P40_Sensory/cortex/__init__.py
# Sensory cortex modules - the felt experience of perception and action
#
# NOTE: This module uses LAZY LOADING to avoid blocking boot.
#       Heavy imports only happen when classes are actually used.

__all__ = [
    # Visual
    "VisualCortexFairy",
    "get_visual_cortex",
    "boot_visual_cortex",
    "VisualFrame",
    "VisualPerception",
    # Motor
    "MotorCortexFairy",
    "get_motor_cortex",
    "boot_motor_cortex",
    "MotorEvent",
    "MotorPerception",
    # Unified
    "UnifiedSensoryCortex",
    "get_unified_sensory_cortex",
    "boot_unified_sensory_cortex",
    "UnifiedPerception",
    "TOOL_CORTEX_MAP",
    # Video Memory (H.265)
    "VideoMemoryFairy",
    "get_video_memory",
    "boot_video_memory",
    "VideoSegment",
    "HAS_VIDEO_MEMORY",
]

# Cache for lazy-loaded modules
_loaded = {}
HAS_VIDEO_MEMORY = None  # Determined on first access


def __getattr__(name):
    """Lazy import handler - only import when accessed."""
    global _loaded, HAS_VIDEO_MEMORY

    # Visual cortex items
    if name in ('VisualCortexFairy', 'get_visual_cortex', 'boot_visual_cortex',
                'VisualFrame', 'VisualPerception'):
        if 'visual' not in _loaded:
            from . import visual_cortex_fairy as visual
            _loaded['visual'] = visual
        return getattr(_loaded['visual'], name)

    # Motor cortex items
    if name in ('MotorCortexFairy', 'get_motor_cortex', 'boot_motor_cortex',
                'MotorEvent', 'MotorPerception'):
        if 'motor' not in _loaded:
            from . import motor_cortex_fairy as motor
            _loaded['motor'] = motor
        return getattr(_loaded['motor'], name)

    # Unified sensory cortex items
    if name in ('UnifiedSensoryCortex', 'get_unified_sensory_cortex',
                'boot_unified_sensory_cortex', 'UnifiedPerception', 'TOOL_CORTEX_MAP'):
        if 'unified' not in _loaded:
            from . import unified_sensory_cortex as unified
            _loaded['unified'] = unified
        return getattr(_loaded['unified'], name)

    # Video memory items
    if name in ('VideoMemoryFairy', 'get_video_memory', 'boot_video_memory', 'VideoSegment'):
        if 'video' not in _loaded:
            try:
                from . import video_memory_fairy as video
                _loaded['video'] = video
                HAS_VIDEO_MEMORY = True
            except ImportError:
                _loaded['video'] = None
                HAS_VIDEO_MEMORY = False
        if _loaded['video'] is None:
            return None
        return getattr(_loaded['video'], name)

    # HAS_VIDEO_MEMORY flag
    if name == 'HAS_VIDEO_MEMORY':
        if HAS_VIDEO_MEMORY is None:
            # Trigger lazy load to determine
            try:
                from . import video_memory_fairy
                HAS_VIDEO_MEMORY = True
            except ImportError:
                HAS_VIDEO_MEMORY = False
        return HAS_VIDEO_MEMORY

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
