# P40_Sensory/wiring/__init__.py
# Sensory Wiring System

from .sensory_wiring import (
    SensoryWiring,
    get_sensory_wiring,
    wire_sensory_to_gates,
    start_sensory_systems,
    get_sensory_status,
)

__all__ = [
    "SensoryWiring",
    "get_sensory_wiring",
    "wire_sensory_to_gates",
    "start_sensory_systems",
    "get_sensory_status",
]
