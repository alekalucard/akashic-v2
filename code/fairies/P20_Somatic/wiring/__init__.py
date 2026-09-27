# P20_Somatic/wiring/__init__.py
# Somatic Wiring System

from .somatic_wiring import (
    SomaticWiring,
    get_somatic_wiring,
    wire_somatic_to_gates,
    start_somatic_systems,
    get_somatic_status,
)

__all__ = [
    "SomaticWiring",
    "get_somatic_wiring",
    "wire_somatic_to_gates",
    "start_somatic_systems",
    "get_somatic_status",
]
