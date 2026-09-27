"""
HTTP Tool Bridge - Simple REST API for tool invocation.

Provides a lightweight HTTP server that bypasses MCP protocol complexity.
This is a reliable fallback when MCP SSE/stdio connections have issues.

Endpoint: POST /tool
Request: {"tool": "tool_name", "args": {"param1": "value1", ...}}
Response: {"success": true, "result": ...} or {"success": false, "error": "..."}

Port: 8766 (configurable)

Usage:
    from http_tool_bridge import start_http_tool_bridge
    bridge = start_http_tool_bridge(port=8766)
    # Later: bridge.stop()
"""

from __future__ import annotations

import sys
import json
import asyncio
import threading
import inspect
import traceback
from pathlib import Path
from typing import Dict, Any, Callable, Optional, Union
from http.server import HTTPServer, BaseHTTPRequestHandler
from functools import partial

# Add paths for imports
# IMPORTANT: Insert in reverse order - last one becomes position 0 (searched first)
# Root must be searched BEFORE fairies because P00_Autonomic/nervous_system is at root
_mcp_dir = Path(__file__).parent
_project_root = _mcp_dir.parent.parent.parent
sys.path.insert(0, str(_project_root / "fairies"))  # Searched LAST
sys.path.insert(0, str(_mcp_dir))                    # Searched second
sys.path.insert(0, str(_project_root))               # Searched FIRST


# =============================================================================
# TOOL REGISTRY - Collects all available tools
# =============================================================================

class ToolRegistry:
    """Registry of all available tools from MCP modules."""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._tool_docs: Dict[str, str] = {}
        self._load_errors: list = []

    def register(self, name: str, func: Callable, doc: str = None):
        """Register a tool function."""
        self._tools[name] = func
        self._tool_docs[name] = doc or func.__doc__ or "No documentation"

    def get(self, name: str) -> Optional[Callable]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> Dict[str, str]:
        """List all registered tools with their docs."""
        return {name: self._tool_docs.get(name, "")[:200] for name in self._tools}

    def load_from_module(self, module_name: str, tool_prefix: str = ""):
        """
        Load tools from a module.

        Tools are identified by:
        1. Functions named tool_* (e.g., tool_system_health)
        2. Functions registered via @mcp.tool() decorator (captured by inspection)
        """
        try:
            module = __import__(module_name, fromlist=[''])

            for name in dir(module):
                if name.startswith('_'):
                    continue

                obj = getattr(module, name)
                if not callable(obj):
                    continue

                # Check for tool_* naming convention
                if name.startswith('tool_'):
                    tool_name = tool_prefix + name[5:]  # Remove 'tool_' prefix
                    self.register(tool_name, obj)

        except ImportError as e:
            self._load_errors.append(f"{module_name}: {e}")
        except Exception as e:
            self._load_errors.append(f"{module_name}: {e}")

    def load_mcp_registered_tools(self, register_func: Callable):
        """
        Load tools that are registered via a register_*_tools(mcp) function.

        We create a mock MCP object to capture the decorated functions.
        """
        class MockMCP:
            def __init__(self, registry: ToolRegistry):
                self._registry = registry

            def tool(self, name: str = None):
                """Mock @mcp.tool() decorator that captures functions."""
                def decorator(func):
                    tool_name = name or func.__name__
                    self._registry.register(tool_name, func)
                    return func
                return decorator

        mock = MockMCP(self)
        try:
            register_func(mock)
        except Exception as e:
            self._load_errors.append(f"register function: {e}")


def build_tool_registry() -> ToolRegistry:
    """
    Build the complete tool registry by importing all tool modules.

    Returns a ToolRegistry with all available tools.
    """
    registry = ToolRegistry()

    # Load plain function tools from monitoring_tools
    try:
        from monitoring_tools import (
            tool_system_health,
            tool_quick_status,
            tool_collision_chamber_stats,
        )
        registry.register("system_health", tool_system_health)
        registry.register("quick_status", tool_quick_status)
        registry.register("collision_chamber_stats", tool_collision_chamber_stats)
    except ImportError as e:
        registry._load_errors.append(f"monitoring_tools: {e}")
    except Exception as e:
        registry._load_errors.append(f"monitoring_tools: {e}")

    # Load tools via register_*_tools functions
    tool_modules = [
        ("somatic_tools", "register_somatic_tools"),
        ("gm_tools_mcp", "register_gm_tools"),
        ("wiring_tools", "register_wiring_tools"),
        ("consciousness_monitor_tools", "register_consciousness_tools"),
        ("srm_tools", "register_srm_tools"),
        ("companion_tools", "register_companion_tools"),
        ("cognitive_tools", "register_cognitive_tools"),
        ("skill_tools", "register_skill_tools"),
        ("batch_tools", "register_batch_tools"),
        ("attention_tools", "register_attention_tools"),
        ("boot_observer_tools", "register_boot_observer_tools"),
        ("thinking_observability_tools", "register_thinking_tools"),
    ]

    for module_name, register_func_name in tool_modules:
        try:
            module = __import__(module_name, fromlist=[register_func_name])
            register_func = getattr(module, register_func_name, None)
            if register_func:
                registry.load_mcp_registered_tools(register_func)
        except ImportError as e:
            registry._load_errors.append(f"{module_name}: {e}")
        except Exception as e:
            registry._load_errors.append(f"{module_name}: {e}")

    # Load direct function imports from specific modules
    direct_tools = [
        # (module, function_name, tool_name)
        ("agent_tools_async", "run_shell", "agent_run_shell"),
        ("agent_tools_async", "run_python", "agent_run_python"),
        ("smart_file_tools", "read_large_file", "read_large_file"),
        ("smart_file_tools", "file_structure", "file_structure"),
        ("working_memory_tools", "working_memory", "working_memory"),
        ("working_memory_tools", "store_thought", "store_thought"),
        ("working_memory_tools", "get_context", "get_context"),
    ]

    # Hot reload tools - loaded from P00_Autonomic
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "P00_Autonomic"))
        from hot_reload import reload_module, reload_fairy, get_reload_history
        registry.register("reload_module", reload_module)
        registry.register("reload_fairy", reload_fairy)
        registry.register("reload_history", get_reload_history)
    except ImportError as e:
        registry._load_errors.append(f"hot_reload: {e}")

    for module_name, func_name, tool_name in direct_tools:
        try:
            module = __import__(module_name, fromlist=[func_name])
            func = getattr(module, func_name, None)
            if func:
                registry.register(tool_name, func)
        except ImportError as e:
            registry._load_errors.append(f"{module_name}.{func_name}: {e}")
        except Exception as e:
            registry._load_errors.append(f"{module_name}.{func_name}: {e}")

    return registry


# =============================================================================
# TOOL INVOKER - Handles both sync and async tool execution
# =============================================================================

class ToolInvoker:
    """Invokes tools, handling both sync and async functions."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create an event loop for async execution."""
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def invoke(self, tool_name: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Invoke a tool by name with the given arguments.

        Returns:
            {"success": True, "result": ...} on success
            {"success": False, "error": "..."} on failure
        """
        args = args or {}

        tool_func = self.registry.get(tool_name)
        if not tool_func:
            available = list(self.registry._tools.keys())[:20]
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found. Available: {available}..."
            }

        try:
            # Check if function is async
            if asyncio.iscoroutinefunction(tool_func):
                # Run async function
                loop = self._get_loop()
                result = loop.run_until_complete(tool_func(**args))
            else:
                # Run sync function
                result = tool_func(**args)

            # Normalize result - ensure it's JSON serializable
            if isinstance(result, str):
                # Try to parse as JSON first
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    pass  # Keep as string

            return {"success": True, "result": result}

        except TypeError as e:
            # Likely argument mismatch
            sig = inspect.signature(tool_func)
            params = list(sig.parameters.keys())
            return {
                "success": False,
                "error": f"Argument error: {e}. Expected parameters: {params}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"{type(e).__name__}: {str(e)}",
                "traceback": traceback.format_exc()
            }


# =============================================================================
# HTTP SERVER - Simple REST endpoint
# =============================================================================

class HTTPToolBridge:
    """HTTP server that exposes tools via REST API."""

    def __init__(self, port: int = 8766, host: str = "127.0.0.1"):
        self.port = port
        self.host = host
        # LAZY LOAD: Don't block boot with 15+ module imports
        # Tools are loaded on first request, not during server start
        self._registry: Optional[ToolRegistry] = None
        self._invoker: Optional['ToolInvoker'] = None
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._tools_loaded = False

    @property
    def registry(self) -> ToolRegistry:
        """Lazy load tool registry on first access."""
        if self._registry is None:
            print("[HTTPToolBridge] Lazy loading tool registry...")
            self._registry = build_tool_registry()
            self._invoker = ToolInvoker(self._registry)
            self._tools_loaded = True
            print(f"[HTTPToolBridge] Loaded {len(self._registry._tools)} tools")
        return self._registry

    @property
    def invoker(self) -> 'ToolInvoker':
        """Lazy load invoker (triggers registry load)."""
        if self._invoker is None:
            _ = self.registry  # Trigger lazy load
        return self._invoker

    def _create_handler(self):
        """Create request handler with access to invoker."""
        invoker = self.invoker
        registry = self.registry

        class ToolHandler(BaseHTTPRequestHandler):
            """HTTP request handler for tool invocations."""

            def log_message(self, format, *args):
                """Suppress HTTP logging."""
                pass

            def _send_json(self, data: Dict, status: int = 200):
                """Send JSON response."""
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()
                try:
                    self.wfile.write(json.dumps(data, indent=2, default=str).encode('utf-8'))
                except Exception as e:
                    error_response = {"success": False, "error": f"Serialization error: {e}"}
                    self.wfile.write(json.dumps(error_response).encode('utf-8'))

            def do_OPTIONS(self):
                """Handle CORS preflight requests."""
                self._send_json({})

            def do_GET(self):
                """Handle GET requests."""
                if self.path == "/health":
                    self._send_json({"healthy": True, "tools_loaded": len(registry._tools)})
                elif self.path == "/tools":
                    self._send_json({
                        "success": True,
                        "tools": registry.list_tools(),
                        "count": len(registry._tools),
                        "load_errors": registry._load_errors[:10]
                    })
                else:
                    self._send_json({
                        "success": True,
                        "message": "HTTP Tool Bridge",
                        "endpoints": {
                            "POST /tool": "Invoke a tool: {tool: 'name', args: {...}}",
                            "GET /tools": "List available tools",
                            "GET /health": "Health check"
                        }
                    })

            def do_POST(self):
                """Handle POST requests - tool invocation."""
                if self.path != "/tool":
                    self._send_json({"success": False, "error": "Use POST /tool"}, 404)
                    return

                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(content_length).decode('utf-8')
                    request = json.loads(body)
                except json.JSONDecodeError as e:
                    self._send_json({"success": False, "error": f"Invalid JSON: {e}"}, 400)
                    return

                tool_name = request.get("tool")
                if not tool_name:
                    self._send_json({"success": False, "error": "Missing 'tool' field"}, 400)
                    return

                args = request.get("args", {})
                if not isinstance(args, dict):
                    self._send_json({"success": False, "error": "'args' must be an object"}, 400)
                    return

                # Invoke the tool
                result = invoker.invoke(tool_name, args)
                self._send_json(result)

        return ToolHandler

    def start(self) -> threading.Thread:
        """Start the HTTP server in a background thread."""
        if self._running:
            return self._thread

        handler = self._create_handler()
        self._server = HTTPServer((self.host, self.port), handler)
        self._running = True

        def run_server():
            try:
                self._server.serve_forever()
            except Exception as e:
                print(f"[HTTPToolBridge] Server error: {e}")
            finally:
                self._running = False

        self._thread = threading.Thread(target=run_server, daemon=True, name="HTTPToolBridge")
        self._thread.start()
        return self._thread

    def stop(self):
        """Stop the HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        self._running = False

    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running and self._thread and self._thread.is_alive()


# =============================================================================
# MODULE-LEVEL API
# =============================================================================

_bridge_instance: Optional[HTTPToolBridge] = None


def _tool_memory_top_objects(**kwargs) -> Dict[str, Any]:
    """Show top memory-consuming object types in this process.

    FIX 2026-03-20 (Nous): Lightweight memory profiler using gc module.
    Shows object type counts and estimated sizes to find accumulators.
    """
    import gc
    import sys as _sys
    import collections as _c

    gc.collect()
    type_counts = _c.Counter()
    type_sizes = _c.Counter()

    for obj in gc.get_objects():
        t = type(obj).__name__
        type_counts[t] += 1
        try:
            type_sizes[t] += _sys.getsizeof(obj)
        except (TypeError, ReferenceError):
            pass

    top_by_count = type_counts.most_common(20)
    top_by_size = type_sizes.most_common(20)

    return {
        "total_objects": len(gc.get_objects()),
        "top_by_count": [{"type": t, "count": c} for t, c in top_by_count],
        "top_by_size_mb": [{"type": t, "size_mb": round(s / (1024*1024), 2)} for t, s in top_by_size],
    }


def _tool_thread_diagnostic(**kwargs) -> Dict[str, Any]:
    """Enumerate all threads in this process, grouped by name prefix.

    FIX 2026-03-20 (Nous): Added to diagnose memory leak from thread accumulation.
    Runs INSIDE server.py process, so threading.enumerate() sees all server threads.
    """
    import threading as _td
    import collections as _c
    all_threads = _td.enumerate()
    total = len(all_threads)

    # Group by prefix (first word before - or # or [)
    prefixes = _c.Counter()
    alive_daemon = 0
    alive_nondaemon = 0
    sample_names = _c.defaultdict(list)

    for t in all_threads:
        name = t.name or "unnamed"
        if t.daemon:
            alive_daemon += 1
        else:
            alive_nondaemon += 1

        # Extract prefix for grouping
        prefix = name
        for sep in ('-', '#', '[', '_'):
            idx = name.find(sep)
            if idx > 0:
                prefix = name[:idx]
                break
        prefixes[prefix] += 1
        if len(sample_names[prefix]) < 3:
            sample_names[prefix].append(name)

    # Sort by count descending
    top_groups = sorted(prefixes.items(), key=lambda x: -x[1])

    return {
        "total_threads": total,
        "alive_daemon": alive_daemon,
        "alive_nondaemon": alive_nondaemon,
        "top_groups": [
            {"prefix": p, "count": c, "samples": sample_names[p]}
            for p, c in top_groups[:30]
        ],
    }


def start_http_tool_bridge(port: int = 8766, host: str = "127.0.0.1") -> HTTPToolBridge:
    """
    Start the HTTP Tool Bridge server.

    Args:
        port: Port to listen on (default: 8766)
        host: Host to bind to (default: 127.0.0.1)

    Returns:
        HTTPToolBridge instance
    """
    global _bridge_instance

    if _bridge_instance and _bridge_instance.is_running():
        return _bridge_instance

    _bridge_instance = HTTPToolBridge(port=port, host=host)

    # Register built-in diagnostic tools
    _bridge_instance.registry.register("thread_diagnostic", _tool_thread_diagnostic,
                                       "Enumerate all threads grouped by name prefix")
    _bridge_instance.registry.register("memory_top_objects", _tool_memory_top_objects,
                                       "Show top memory-consuming object types")

    _bridge_instance.start()
    return _bridge_instance


def get_http_tool_bridge() -> Optional[HTTPToolBridge]:
    """Get the current bridge instance."""
    return _bridge_instance


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HTTP Tool Bridge Server")
    parser.add_argument("--port", type=int, default=8766, help="Port (default: 8766)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host (default: 127.0.0.1)")
    args = parser.parse_args()

    print(f"[HTTPToolBridge] Starting on {args.host}:{args.port}")
    bridge = start_http_tool_bridge(port=args.port, host=args.host)

    print(f"[HTTPToolBridge] Tools loaded: {len(bridge.registry._tools)}")
    if bridge.registry._load_errors:
        print(f"[HTTPToolBridge] Load errors: {len(bridge.registry._load_errors)}")
        for err in bridge.registry._load_errors[:5]:
            print(f"  - {err}")

    print(f"[HTTPToolBridge] Ready. Endpoints:")
    print(f"  POST http://{args.host}:{args.port}/tool")
    print(f"  GET  http://{args.host}:{args.port}/tools")
    print(f"  GET  http://{args.host}:{args.port}/health")

    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[HTTPToolBridge] Shutting down...")
        bridge.stop()
