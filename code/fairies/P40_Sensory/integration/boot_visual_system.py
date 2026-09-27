# P40_Sensory/integration/boot_visual_system.py
# Boot integration for the visual system
#
# Call wire_visual_on_boot() from server.py after EmbodimentFairy

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fairies.P40_Sensory.integration.visual_system_integration import IntegratedVisualPipeline

_VISUAL_PIPELINE: Optional['IntegratedVisualPipeline'] = None


def wire_visual_on_boot(continuous: bool = False) -> Optional['IntegratedVisualPipeline']:
    """
    Wire the visual system during boot.
    
    Call this after EmbodimentFairy is booted.
    
    Args:
        continuous: Use continuous GPU capture (for watching videos)
        
    Returns:
        The visual pipeline instance, or None if failed
    """
    global _VISUAL_PIPELINE
    
    try:
        from fairies.P40_Sensory.integration.visual_system_integration import get_visual_pipeline
        
        pipeline = get_visual_pipeline()
        
        print(f"[boot] VisualSystem: backend={pipeline.capture.backend}, GPU={pipeline.capture.is_gpu}")
        
        # Start the pipeline
        pipeline.start(continuous=continuous)
        
        _VISUAL_PIPELINE = pipeline
        print(f"[boot] VisualSystem started ({pipeline.capture_fps} FPS target)")
        
        return pipeline
        
    except ImportError as e:
        print(f"[boot] VisualSystem not available: {e}")
        return None
    except Exception as e:
        print(f"[boot] VisualSystem error: {e}")
        return None


def get_visual_pipeline_instance() -> Optional['IntegratedVisualPipeline']:
    """Get the booted visual pipeline instance."""
    return _VISUAL_PIPELINE


def stop_visual_system():
    """Stop the visual system (call on shutdown)."""
    global _VISUAL_PIPELINE
    if _VISUAL_PIPELINE:
        _VISUAL_PIPELINE.stop()
        _VISUAL_PIPELINE = None
        print("[shutdown] VisualSystem stopped")
