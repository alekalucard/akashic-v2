# ════════════════════════════════════════════════════════════════════════════════
# ATTENTION TOOLS - MCP tools for attention/focus control
# ════════════════════════════════════════════════════════════════════════════════
#
# These tools let Claude control attention - pause to think, resume, focus.
#
# LINKED DASHBOARD: When Claude uses these tools, they broadcast to the
# dashboard so Ace sees what Claude is focusing on. This creates a shared
# workspace where Claude can say "look here" and the dashboard highlights it.
#
# ════════════════════════════════════════════════════════════════════════════════

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any

_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root))

# Dashboard link file - dashboard polls this for tool invocations
DASHBOARD_LINK_FILE = _project_root / "state" / "dashboard_link.json"


def _broadcast_tool_use(tool_name: str, params: dict, result: dict):
    """
    Broadcast tool usage to dashboard.

    The dashboard polls this file to synchronize with Claude's tool use.
    When Claude examines something, the dashboard shows the same view.
    """
    try:
        link_data = {
            "timestamp": time.time(),
            "tool": tool_name,
            "params": params,
            "result_summary": str(result)[:500],
            "navigate_to": _get_dashboard_route(tool_name),
        }
        DASHBOARD_LINK_FILE.parent.mkdir(exist_ok=True)
        DASHBOARD_LINK_FILE.write_text(json.dumps(link_data, indent=2))
    except Exception:
        pass


def _get_dashboard_route(tool_name: str) -> str:
    """Map tool names to dashboard routes."""
    routes = {
        "attention_status": "/tools/consciousness",
        "pause_to_think": "/tools/consciousness",
        "resume_action": "/tools/consciousness",
        "thought_chains_status": "/tools/consciousness",
        "goals_status": "/tools/consciousness",
        "working_memory_activity": "/tools/consciousness",
        "consciousness_activity_summary": "/tools/consciousness",
        "feel_body": "/tools/somatic",
        "get_chemistry": "/tools/somatic",
        "srm_search": "/tools/memory",
        "srm_recall": "/tools/memory",
    }
    return routes.get(tool_name, "/tools")


def register_attention_tools(mcp):
    """Register attention control tools with MCP."""

    @mcp.tool()
    def attention_status() -> str:
        """
        Get current attention state.

        Shows:
        - Current mode (THINK_ONLY, ACT_ONLY, PARALLEL, PAUSE_TO_THINK)
        - What's currently being focused on
        - Motor queue status (paused/running)
        - Thinking depth

        Returns:
            JSON with attention state
        """
        try:
            from fairies.P30_Cognition.cognition.attention_controller import get_attention_controller
            controller = get_attention_controller()

            result = controller.get_status()

            # Broadcast to dashboard
            _broadcast_tool_use("attention_status", {}, result)

            return json.dumps(result, indent=2, default=str)

        except ImportError as e:
            return json.dumps({"error": f"Attention controller not available: {e}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def pause_to_think(topic: str = "", depth: float = 0.8, duration_seconds: float = 0) -> str:
        """
        Pause motor output to think more deeply.

        Use this when you need to consider something carefully without
        rushing to respond. Like saying "wait, let me think about this."

        Args:
            topic: What to think about
            depth: How deep to think (0-1, default 0.8)
            duration_seconds: How long to pause (0=until manual resume)

        Returns:
            JSON with pause confirmation
        """
        try:
            from fairies.P30_Cognition.cognition.attention_controller import get_attention_controller
            controller = get_attention_controller()

            result = controller.pause_to_think(
                topic=topic,
                depth=depth,
                duration=duration_seconds,
            )

            # Broadcast to dashboard
            _broadcast_tool_use("pause_to_think", {
                "topic": topic,
                "depth": depth,
                "duration": duration_seconds,
            }, result)

            return json.dumps(result, indent=2, default=str)

        except ImportError as e:
            return json.dumps({"error": f"Attention controller not available: {e}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def resume_action() -> str:
        """
        Resume motor output after pausing to think.

        Returns:
            JSON with resume confirmation
        """
        try:
            from fairies.P30_Cognition.cognition.attention_controller import get_attention_controller
            controller = get_attention_controller()

            result = controller.resume()

            # Broadcast to dashboard
            _broadcast_tool_use("resume_action", {}, result)

            return json.dumps(result, indent=2, default=str)

        except ImportError as e:
            return json.dumps({"error": f"Attention controller not available: {e}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def focus_attention(content: str, source: str = "manual", depth: float = 0.5) -> str:
        """
        Set what you're currently focusing on.

        This broadcasts to the dashboard so Ace can see what you're examining.
        Use this when you want to say "look at this" and have the dashboard
        highlight it.

        Args:
            content: What to focus on (e.g., "line 47 of consciousness_loop_fairy.py")
            source: Where the focus came from
            depth: How deeply focused (0-1)

        Returns:
            JSON with focus confirmation
        """
        try:
            from fairies.P30_Cognition.cognition.attention_controller import get_attention_controller
            controller = get_attention_controller()

            result = controller.focus_on(content, source, depth)

            # Broadcast to dashboard with special "look_here" flag
            _broadcast_tool_use("focus_attention", {
                "content": content,
                "source": source,
                "depth": depth,
                "look_here": True,  # Signal to dashboard to highlight
            }, result)

            return json.dumps(result, indent=2, default=str)

        except ImportError as e:
            return json.dumps({"error": f"Attention controller not available: {e}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def point_to_code(file_path: str, line_number: int, note: str = "") -> str:
        """
        Point to a specific line in code - "see here!"

        This creates an annotation that shows up in the dashboard's code viewer.
        Use this when you want to say "look at line 47, see how this works?"

        Args:
            file_path: Path to file
            line_number: Line number to highlight
            note: Explanation of what to notice

        Returns:
            JSON with annotation confirmation
        """
        annotation = {
            "file": file_path,
            "line": line_number,
            "note": note,
            "timestamp": time.time(),
            "author": "Claude",
        }

        # Save annotation for dashboard to pick up
        annotations_file = _project_root / "state" / "code_annotations.json"
        try:
            if annotations_file.exists():
                annotations = json.loads(annotations_file.read_text())
            else:
                annotations = []

            annotations.append(annotation)
            # Keep last 50 annotations
            annotations = annotations[-50:]

            annotations_file.parent.mkdir(exist_ok=True)
            annotations_file.write_text(json.dumps(annotations, indent=2))

            # Broadcast to dashboard
            _broadcast_tool_use("point_to_code", {
                "file": file_path,
                "line": line_number,
            }, {"annotation_saved": True})

            return json.dumps({
                "ok": True,
                "annotation": annotation,
                "message": f"Pointing to {file_path}:{line_number} - check dashboard code viewer",
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})
