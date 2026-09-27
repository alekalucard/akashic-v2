"""
P40_Sensory.audio - Audio Cortex Module (LAZY LOADING)

The complete auditory processing pipeline, modeled after the human auditory system.

Layers:
    0. MediaPreservationLayer - Lossless archival (FLAC, H.265)
    1. CochleaFairy - Tonotopic frequency decomposition
    2. AuditoryNerveFairy - Spike pattern encoding (TODO)
    3. InferiorColliculusFairy - Binaural integration (TODO)
    4. PrimaryAuditoryCortexFairy - STRF feature extraction (TODO)
    5. BeltParabeltFairy - Complex sound processing (TODO)
    6. SpeechStreamsFairy - Dual pathway processing (TODO)
    7. VoiceSynthesisFairy - TTS and voice cloning (TODO)

NOTE: This module uses LAZY LOADING to avoid blocking boot.
      Heavy imports (librosa, scipy) only happen when classes are actually used.
"""

# Lazy loading - don't import anything at module level!
# This prevents pkgutil.walk_packages from triggering heavy imports.

__all__ = [
    # Preservation
    'MediaPreservationLayer',
    'get_preservation_layer',
    'PreservationResult',
    'MediaInfo',
    # Cochlea
    'CochleaFairy',
    'get_cochlea_fairy',
    'CochleaOutput',
    'SpectralSeeds',
    'TemporalSeeds',
    'HarmonicSeeds',
]

# Cache for lazy-loaded modules
_loaded = {}


def __getattr__(name):
    """Lazy import handler - only import when accessed."""
    global _loaded

    # Preservation layer items
    if name in ('MediaPreservationLayer', 'get_preservation_layer',
                'PreservationResult', 'MediaInfo'):
        if 'preservation' not in _loaded:
            from . import media_preservation_layer as preservation
            _loaded['preservation'] = preservation
        return getattr(_loaded['preservation'], name)

    # Cochlea items
    if name in ('CochleaFairy', 'get_cochlea_fairy', 'CochleaOutput',
                'SpectralSeeds', 'TemporalSeeds', 'HarmonicSeeds'):
        if 'cochlea' not in _loaded:
            from . import cochlea_fairy as cochlea
            _loaded['cochlea'] = cochlea
        return getattr(_loaded['cochlea'], name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
