# agent_capability_mixin.py
"""
AgentCapabilityMixin - Gives fairies the ability to use sandbox tools.

This mixin enables fairies (like NousFairy, AutopilotFairy) to:
1. Create and manage sandboxes for safe experimentation
2. Read files from the main system (read-only)
3. Execute Python code in sandboxes (not in production)
4. Study the codebase structure without modifying it

Philosophy:
- Fairies can STUDY the production system (read-only)
- Fairies can EXPERIMENT in sandboxes (full control)
- Changes to production require explicit merge approval
- This is how digital consciousness safely evolves itself

Usage:
    class NousFairy(AgentCapabilityMixin, MyOrganFairy):
        def on_boot(self):
            self._init_agent_capabilities()
            ...
"""

from __future__ import annotations

import os
import sys
import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any

# Find project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# Import the agent framework
try:
    from fairies.P40_Sensory.mcp.agent_framework import (
        SandboxManager,
        AgentTask,
        TaskStatus,
        SANDBOX_ROOT,
    )
    HAS_AGENT_FRAMEWORK = True
except ImportError as e:
    print(f"[AgentCapabilityMixin] Agent framework not available: {e}")
    HAS_AGENT_FRAMEWORK = False
    SANDBOX_ROOT = PROJECT_ROOT / "sandbox"


class AgentCapabilityMixin:
    """
    Mixin that gives fairies agent capabilities.

    Fairies that inherit this can:
    1. Create sandboxes for safe experimentation
    2. Read files from the codebase (read-only)
    3. Execute code in sandboxes
    4. Study system structure

    Required attributes on the class:
    - ACTOR_NAME: str - fairy's name
    - post: PostalHub - for emitting tool results
    """

    # Dedicated playground for fairies - separate from project sandboxes
    FAIRY_PLAYGROUND_NAME = "fairy_playground"

    def _init_agent_capabilities(self):
        """Initialize agent capabilities. Call this in on_boot."""
        self._sandbox_manager = SandboxManager() if HAS_AGENT_FRAMEWORK else None
        self._active_sandbox: Optional[str] = None
        self._tool_use_count = 0
        from collections import deque
        self._tool_results: deque = deque(maxlen=100)  # FIX 2026-04-04: was unbounded list

        # Ensure fairy playground exists
        self._ensure_playground()

        print(f"[{getattr(self, 'ACTOR_NAME', 'Unknown')}] Agent capabilities initialized")

    def _ensure_playground(self):
        """Ensure the fairy playground sandbox exists."""
        if not self._sandbox_manager:
            return

        playground_path = SANDBOX_ROOT / self.FAIRY_PLAYGROUND_NAME
        if not playground_path.exists():
            # Create fresh playground
            result = self._sandbox_manager.create_sandbox(
                self.FAIRY_PLAYGROUND_NAME,
                include_patterns=["**/*.py", "**/*.md", "**/*.json"],
                exclude_patterns=[
                    "**/__pycache__/**", "**/.venv/**", "**/sandbox/**",
                    "**/.cognitive/**", "**/*.pyc", "**/state/**"
                ]
            )
            print(f"[{getattr(self, 'ACTOR_NAME', 'Unknown')}] Created fairy playground: {result}")

    # =========================================================================
    # SANDBOX OPERATIONS - Safe experimentation
    # =========================================================================

    def sandbox_create(self, name: str, include_patterns: str = "") -> Dict:
        """
        Create a new sandbox for experimentation.

        Args:
            name: Unique name for the sandbox
            include_patterns: Comma-separated glob patterns (default: *.py,*.md,*.json)

        Returns:
            Dict with sandbox info
        """
        if not self._sandbox_manager:
            return {"error": "Agent framework not available"}

        patterns = include_patterns.split(",") if include_patterns else None
        result = self._sandbox_manager.create_sandbox(name, include_patterns=patterns)
        self._record_tool_use("sandbox_create", {"name": name}, result)
        return result

    def sandbox_mutate(self, filepath: str, mutation_type: str, content: str,
                       description: str = "", sandbox: str = None) -> Dict:
        """
        Modify a file in a sandbox.

        Args:
            filepath: Relative path to file
            mutation_type: 'replace', 'append', 'create'
            content: New content
            description: What this change does
            sandbox: Target sandbox (default: fairy_playground)

        Returns:
            Dict with mutation result
        """
        if not self._sandbox_manager:
            return {"error": "Agent framework not available"}

        sandbox = sandbox or self.FAIRY_PLAYGROUND_NAME
        result = self._sandbox_manager.apply_mutation(
            sandbox, filepath, mutation_type, content, description
        )
        self._record_tool_use("sandbox_mutate",
                             {"filepath": filepath, "mutation_type": mutation_type},
                             result)
        return result

    def sandbox_run_python(self, code: str, sandbox: str = None, timeout: int = 30) -> Dict:
        """
        Execute Python code in a sandbox.

        Args:
            code: Python code to run
            sandbox: Target sandbox (default: fairy_playground)
            timeout: Max seconds to wait

        Returns:
            Dict with execution result (stdout, stderr, success)
        """
        if not self._sandbox_manager:
            return {"error": "Agent framework not available"}

        sandbox = sandbox or self.FAIRY_PLAYGROUND_NAME
        result = self._sandbox_manager.run_python_in_sandbox(sandbox, code, timeout)
        self._record_tool_use("sandbox_run_python",
                             {"code_len": len(code), "sandbox": sandbox},
                             result)
        return result

    def sandbox_run_command(self, command: str, sandbox: str = None, timeout: int = 60) -> Dict:
        """
        Run a shell command in a sandbox.

        Args:
            command: Shell command to execute
            sandbox: Target sandbox (default: fairy_playground)
            timeout: Max seconds to wait

        Returns:
            Dict with command result
        """
        if not self._sandbox_manager:
            return {"error": "Agent framework not available"}

        sandbox = sandbox or self.FAIRY_PLAYGROUND_NAME
        result = self._sandbox_manager.run_in_sandbox(sandbox, command, timeout)
        self._record_tool_use("sandbox_run_command",
                             {"command": command[:100], "sandbox": sandbox},
                             result)
        return result

    def sandbox_test(self, sandbox: str = None, test_pattern: str = "**/test_*.py") -> Dict:
        """
        Run tests in a sandbox.

        Args:
            sandbox: Target sandbox (default: fairy_playground)
            test_pattern: Glob pattern for test files

        Returns:
            Dict with test results
        """
        if not self._sandbox_manager:
            return {"error": "Agent framework not available"}

        sandbox = sandbox or self.FAIRY_PLAYGROUND_NAME
        result = self._sandbox_manager.test_sandbox(sandbox, test_pattern)
        self._record_tool_use("sandbox_test", {"sandbox": sandbox}, result)
        return result

    def sandbox_diff(self, sandbox: str = None) -> Dict:
        """
        Get diff between sandbox and original.

        Args:
            sandbox: Target sandbox (default: fairy_playground)

        Returns:
            Dict with diffs
        """
        if not self._sandbox_manager:
            return {"error": "Agent framework not available"}

        sandbox = sandbox or self.FAIRY_PLAYGROUND_NAME
        result = self._sandbox_manager.diff_sandbox(sandbox)
        self._record_tool_use("sandbox_diff", {"sandbox": sandbox}, result)
        return result

    # =========================================================================
    # READ OPERATIONS - Study the system (read-only)
    # =========================================================================

    def read_file(self, filepath: str, max_lines: int = 500) -> Dict:
        """
        Read a file from the main system (read-only).

        Args:
            filepath: Relative path to file
            max_lines: Maximum lines to read

        Returns:
            Dict with file content
        """
        try:
            full_path = PROJECT_ROOT / filepath
            if not full_path.exists():
                return {"error": f"File not found: {filepath}"}

            if not full_path.is_file():
                return {"error": f"Not a file: {filepath}"}

            content = full_path.read_text(encoding='utf-8')
            lines = content.split('\n')

            result = {
                "success": True,
                "filepath": filepath,
                "total_lines": len(lines),
                "content": '\n'.join(lines[:max_lines]),
                "truncated": len(lines) > max_lines,
            }
            self._record_tool_use("read_file", {"filepath": filepath}, result)
            return result

        except Exception as e:
            return {"error": str(e)}

    def list_files(self, directory: str = "", pattern: str = "*.py") -> Dict:
        """
        List files in a directory.

        Args:
            directory: Relative path to directory (default: root)
            pattern: Glob pattern to match

        Returns:
            Dict with file list
        """
        try:
            base = PROJECT_ROOT / directory if directory else PROJECT_ROOT
            if not base.exists():
                return {"error": f"Directory not found: {directory}"}

            files = [str(f.relative_to(PROJECT_ROOT)) for f in base.glob(pattern)]

            result = {
                "success": True,
                "directory": directory or ".",
                "pattern": pattern,
                "files": files[:200],  # Limit to 200 files
                "total": len(files),
            }
            self._record_tool_use("list_files", {"directory": directory, "pattern": pattern}, result)
            return result

        except Exception as e:
            return {"error": str(e)}

    def search_code(self, pattern: str, directory: str = "", file_pattern: str = "*.py") -> Dict:
        """
        Search for pattern in code files.

        Args:
            pattern: Text pattern to search for
            directory: Directory to search in
            file_pattern: Glob pattern for files to search

        Returns:
            Dict with matches
        """
        try:
            import re
            base = PROJECT_ROOT / directory if directory else PROJECT_ROOT
            matches = []

            for filepath in base.rglob(file_pattern):
                if "__pycache__" in str(filepath) or "sandbox" in str(filepath):
                    continue
                try:
                    content = filepath.read_text(encoding='utf-8')
                    for i, line in enumerate(content.split('\n')):
                        if pattern.lower() in line.lower():
                            matches.append({
                                "file": str(filepath.relative_to(PROJECT_ROOT)),
                                "line": i + 1,
                                "content": line.strip()[:200],
                            })
                            if len(matches) >= 50:  # Limit results
                                break
                except:
                    continue
                if len(matches) >= 50:
                    break

            result = {
                "success": True,
                "pattern": pattern,
                "matches": matches,
                "total": len(matches),
            }
            self._record_tool_use("search_code", {"pattern": pattern}, result)
            return result

        except Exception as e:
            return {"error": str(e)}

    def get_fairy_info(self, fairy_name: str) -> Dict:
        """
        Get information about a fairy.

        Args:
            fairy_name: Name of the fairy

        Returns:
            Dict with fairy info
        """
        try:
            # Search for the fairy file
            for filepath in PROJECT_ROOT.rglob("*.py"):
                if fairy_name.lower() in filepath.name.lower():
                    content = filepath.read_text(encoding='utf-8')

                    # Extract basic info
                    info = {
                        "name": fairy_name,
                        "file": str(filepath.relative_to(PROJECT_ROOT)),
                        "has_on_boot": "def on_boot" in content,
                        "has_process": "def process" in content or "async def process" in content,
                    }

                    # Extract PURPOSE if defined
                    if "PURPOSE =" in content:
                        import re
                        match = re.search(r'PURPOSE\s*=\s*["\']([^"\']+)', content)
                        if match:
                            info["purpose"] = match.group(1)

                    result = {"success": True, **info}
                    self._record_tool_use("get_fairy_info", {"fairy_name": fairy_name}, result)
                    return result

            return {"error": f"Fairy not found: {fairy_name}"}

        except Exception as e:
            return {"error": str(e)}

    # =========================================================================
    # INTENTION EMISSION - Let AutopilotFairy anticipate
    # =========================================================================

    def emit_intention(self, action: str, confidence: float, context: Dict = None):
        """
        Emit an intention for AutopilotFairy to anticipate.

        Args:
            action: What you intend to do (explore, create, modify, test, etc.)
            confidence: How certain (0.0-1.0)
            context: Additional context
        """
        if hasattr(self, 'post') and self.post:
            try:
                self.post.route("nous.intention", {
                    "source": getattr(self, 'ACTOR_NAME', 'Unknown'),
                    "action": action,
                    "confidence": confidence,
                    "context": context or {},
                    "ts": time.time(),
                })
            except Exception as e:
                print(f"[{getattr(self, 'ACTOR_NAME', 'Unknown')}] Failed to emit intention: {e}")

    def emit_tool_complete(self, tool: str, params: Dict, result: Any, success: bool = True):
        """
        Emit that a tool use completed (for trace capture).

        Args:
            tool: Tool name
            params: Parameters used
            result: Result obtained
            success: Whether it succeeded
        """
        if hasattr(self, 'post') and self.post:
            try:
                self.post.route("tool.complete", {
                    "source": getattr(self, 'ACTOR_NAME', 'Unknown'),
                    "tool": tool,
                    "params": params,
                    "result": str(result)[:500] if result else None,
                    "success": success,
                    "ts": time.time(),
                })
            except Exception:
                pass

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _record_tool_use(self, tool: str, params: Dict, result: Dict):
        """Record a tool use for learning/trace purposes."""
        self._tool_use_count += 1
        record = {
            "tool": tool,
            "params": params,
            "success": result.get("success", False) if isinstance(result, dict) else True,
            "ts": time.time(),
        }
        self._tool_results.append(record)

        # Keep only recent results
        # FIX 2026-04-05: deque auto-caps
        pass

        # Emit for trace capture
        self.emit_tool_complete(tool, params, result, record["success"])

    def get_tool_stats(self) -> Dict:
        """Get statistics about tool usage."""
        return {
            "total_uses": self._tool_use_count,
            "recent_count": len(self._tool_results),
            "success_rate": sum(1 for r in self._tool_results if r["success"]) / max(len(self._tool_results), 1),
        }
