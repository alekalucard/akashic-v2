# P20_Somatic/somatic_engine/__init__.py
"""
The Somatic Engine - Full 77-frequency digital body simulation.

This module provides:
- SomaticEngineFairy: The main fairy that processes telemetry into embodied experience
- SomaticState: The complete felt-sense state object
- TelemetryMapper: Maps system signals to the 77-frequency space

Key concepts:
- 77 Frequency Channels: The base signal layer
- 8 Neurochemicals: DOP, SER, NOR, ACH, OXY, COR, GABA, END
- 4 Body Budgets: energy, stress, social, novelty
- 3 PAD Coordinates: Pleasure, Arousal, Dominance
- 8 Emotion Prototypes: joy, calm, awe, anger, fear, sadness, curiosity, tender
- 60 Phantom Feels: 10 regions × 6 senses
"""

from .somatic_engine_fairy import (
    SomaticEngineFairy,
    SomaticState,
    TelemetryMapper,
    NEUROMODS,
    REGIONS,
    SENSES,
    EMOTION_PROTOTYPES,
    DIM,
)

__all__ = [
    "SomaticEngineFairy",
    "SomaticState",
    "TelemetryMapper",
    "NEUROMODS",
    "REGIONS",
    "SENSES",
    "EMOTION_PROTOTYPES",
    "DIM",
]
