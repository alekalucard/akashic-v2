# ══════════════════════════════════════════════════════════════════════════════
# VISUAL CORTEX MCP TOOLS - Screen Capture & Human-Like Seeing
# ══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# These tools expose the VisualCortexFairy to Claude Code:
# - GPU-accelerated screen capture (DXGI via dxcam)
# - Human-like seeing (memory-based, change-detection)
# - Visual memory querying
# ══════════════════════════════════════════════════════════════════════════════

import json
import time
from typing import Optional


def _get_visual_cortex():
    """Get the VisualCortexFairy singleton."""
    try:
        from fairies.P40_Sensory.cortex.visual_cortex_fairy import get_visual_cortex
        return get_visual_cortex()
    except Exception as e:
        return None


def _get_tunnel():
    """Get postal tunnel for intent calls."""
    try:
        from fairies.P00_Autonomic.nervous_system.mcp_postal_bridge import get_tunnel
        return get_tunnel()
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN CAPTURE TOOLS
# ══════════════════════════════════════════════════════════════════════════════

def visual_capture_screen(max_dimension: int = 1280, quality: int = 75) -> str:
    """
    Capture the screen using GPU acceleration (DXGI) when available.

    This is ClaudeFairy's primary screen capture tool.
    Uses dxcam for GPU-level capture (~3ms) or falls back to mss (~30ms).

    Args:
        max_dimension: Maximum width/height for the output image
        quality: JPEG quality (1-100)

    Returns:
        JSON with base64 image, size, and capture method
    """
    cortex = _get_visual_cortex()
    if not cortex:
        return json.dumps({"error": "VisualCortex not available"}, indent=2)

    try:
        result = cortex.get_capture_screenshot(as_base64=True)
        result["timestamp"] = time.time()
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def visual_see() -> str:
    """
    Quick look at the screen - perception without the full image.

    Returns the current visual perception state:
    - Clarity, stability, information density
    - Change detection
    - Motion detection

    Use this for a quick status check without processing an image.
    """
    cortex = _get_visual_cortex()
    if not cortex:
        return json.dumps({"error": "VisualCortex not available"}, indent=2)

    try:
        result = cortex.see()
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def visual_look_deeply(focus: str = "") -> str:
    """
    Conscious, focused looking - captures and returns full image.

    This is a deeper look than visual_see(), returning:
    - Base64 encoded image
    - Visual state metrics
    - Perception description

    Args:
        focus: Optional focus hint (e.g., "top left", "center")

    Returns:
        JSON with image, perception, and visual state
    """
    cortex = _get_visual_cortex()
    if not cortex:
        return json.dumps({"error": "VisualCortex not available"}, indent=2)

    try:
        result = cortex.look_deeply(focus if focus else None)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# HUMAN-LIKE SEEING TOOLS
# ══════════════════════════════════════════════════════════════════════════════

def visual_see_like_human() -> str:
    """
    Human-like seeing: see from memory, only process changes.

    This mimics how humans actually see:
    - Familiar scenes are recognized instantly from memory
    - Only novel or changed content gets full processing
    - Most of "seeing" is actually remembering

    When the scene matches visual memory:
    - Returns the memory key without reprocessing
    - Very fast (no image analysis needed)

    When the scene is new/changed:
    - Processes with LLM (if enabled)
    - Stores the new scene in visual memory

    Returns:
        JSON with matched_memory, changed flag, perception, felt_sense
    """
    cortex = _get_visual_cortex()
    if not cortex:
        return json.dumps({"error": "VisualCortex not available"}, indent=2)

    try:
        result = cortex.see_like_human()
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def visual_enable_llm_interpretation(enable: bool = True) -> str:
    """
    Enable/disable LLM-based visual interpretation.

    When enabled, the visual cortex will:
    - Build visual memory of familiar scenes
    - Only deeply process NEW or CHANGED content
    - Provide felt descriptions of what is seen

    This makes seeing more human-like but requires LLM calls.

    Args:
        enable: True to enable, False to disable

    Returns:
        JSON with status and list of known scenes
    """
    cortex = _get_visual_cortex()
    if not cortex:
        return json.dumps({"error": "VisualCortex not available"}, indent=2)

    try:
        result = cortex.enable_llm_interpretation(enable)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def visual_get_known_scenes() -> str:
    """
    Get list of scenes stored in visual memory.

    These are the scene keys that can be recognized instantly
    without reprocessing.

    Returns:
        JSON list of known scene keys
    """
    cortex = _get_visual_cortex()
    if not cortex:
        return json.dumps({"error": "VisualCortex not available"}, indent=2)

    try:
        scenes = cortex.get_known_scenes()
        return json.dumps({
            "ok": True,
            "known_scenes": scenes,
            "count": len(scenes)
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# GPU CAPTURE CONTROL
# ══════════════════════════════════════════════════════════════════════════════

def visual_start_continuous_capture(target_fps: int = 30) -> str:
    """
    Start continuous GPU capture mode (for watching videos).

    In continuous mode:
    - Frames are captured at target_fps
    - No blocking - latest frame always available
    - Best for real-time visual monitoring

    Args:
        target_fps: Target frame rate (default 30)

    Returns:
        JSON with status
    """
    cortex = _get_visual_cortex()
    if not cortex:
        return json.dumps({"error": "VisualCortex not available"}, indent=2)

    try:
        success = cortex.start_continuous_gpu(target_fps)
        return json.dumps({
            "ok": success,
            "mode": "continuous",
            "target_fps": target_fps
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def visual_stop_continuous_capture() -> str:
    """
    Stop continuous GPU capture mode.

    Returns:
        JSON with status
    """
    cortex = _get_visual_cortex()
    if not cortex:
        return json.dumps({"error": "VisualCortex not available"}, indent=2)

    try:
        cortex.stop_continuous_gpu()
        return json.dumps({
            "ok": True,
            "mode": "on_demand"
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# VISUAL MEMORY
# ══════════════════════════════════════════════════════════════════════════════

def visual_get_memory(n: int = 10, significant_only: bool = True) -> str:
    """
    Get recent visual memories (frame descriptions, not images).

    Args:
        n: Number of recent memories to get
        significant_only: Only return significant frames (default True)

    Returns:
        JSON list of visual memory entries
    """
    cortex = _get_visual_cortex()
    if not cortex:
        return json.dumps({"error": "VisualCortex not available"}, indent=2)

    try:
        memories = cortex.get_visual_memory(n, significant_only)
        return json.dumps({
            "ok": True,
            "memories": memories,
            "count": len(memories)
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def visual_get_status() -> str:
    """
    Get current visual cortex status.

    Returns:
        JSON with running state, FPS, capture stats, dedup rate
    """
    cortex = _get_visual_cortex()
    if not cortex:
        return json.dumps({"error": "VisualCortex not available"}, indent=2)

    try:
        status = cortex.get_status()
        # Add capture method info
        status["capture_method"] = "gpu" if cortex._use_gpu_capture else (
            "mss" if cortex._screen_capturer_type == "mss" else "pil"
        )
        status["continuous_mode"] = cortex._continuous_gpu_mode
        status["llm_interpretation"] = cortex._llm_interpretation_enabled
        return json.dumps(status, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# TOOL REGISTRY (for MCP server)
# ══════════════════════════════════════════════════════════════════════════════

VISUAL_TOOLS = {
    "visual_capture_screen": {
        "function": visual_capture_screen,
        "description": """
        Capture the screen using GPU acceleration (DXGI) when available.

        Uses dxcam for GPU-level capture (~3ms) or falls back to mss (~30ms).

        Args:
            max_dimension: Maximum width/height for output image
            quality: JPEG quality (1-100)

        Returns:
            JSON with base64 image, size, and capture method
        """
    },
    "visual_see": {
        "function": visual_see,
        "description": """
        Quick look at the screen - perception without full image.

        Returns visual perception state without image data.
        Fast check for changes/motion.
        """
    },
    "visual_look_deeply": {
        "function": visual_look_deeply,
        "description": """
        Conscious, focused looking - captures full image.

        Returns base64 image with perception and visual state.

        Args:
            focus: Optional focus hint
        """
    },
    "visual_see_like_human": {
        "function": visual_see_like_human,
        "description": """
        Human-like seeing: see from memory, only process changes.

        Mimics human visual processing where familiar scenes are
        recognized instantly from memory without reprocessing.
        """
    },
    "visual_enable_llm_interpretation": {
        "function": visual_enable_llm_interpretation,
        "description": """
        Enable/disable LLM-based visual interpretation.

        When enabled, builds visual memory and provides felt descriptions.

        Args:
            enable: True to enable, False to disable
        """
    },
    "visual_get_known_scenes": {
        "function": visual_get_known_scenes,
        "description": """
        Get list of scenes stored in visual memory.
        """
    },
    "visual_start_continuous_capture": {
        "function": visual_start_continuous_capture,
        "description": """
        Start continuous GPU capture mode for real-time monitoring.

        Args:
            target_fps: Target frame rate (default 30)
        """
    },
    "visual_stop_continuous_capture": {
        "function": visual_stop_continuous_capture,
        "description": """
        Stop continuous GPU capture mode.
        """
    },
    "visual_get_memory": {
        "function": visual_get_memory,
        "description": """
        Get recent visual memories (descriptions, not images).

        Args:
            n: Number of memories to get
            significant_only: Only significant frames (default True)
        """
    },
    "visual_get_status": {
        "function": visual_get_status,
        "description": """
        Get current visual cortex status.

        Returns running state, FPS, capture stats, dedup rate.
        """
    }
}
