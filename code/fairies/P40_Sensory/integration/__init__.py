# P40_Sensory/integration/__init__.py
# Visual system integration module

from .visual_system_integration import (
    IntegratedVisualPipeline,
    GPUVisualCapture,
    ChangeDetector,
    VisualMemoryBridge,
    get_visual_pipeline,
    wire_visual_system,
)

__all__ = [
    'IntegratedVisualPipeline',
    'GPUVisualCapture', 
    'ChangeDetector',
    'VisualMemoryBridge',
    'get_visual_pipeline',
    'wire_visual_system',
]
