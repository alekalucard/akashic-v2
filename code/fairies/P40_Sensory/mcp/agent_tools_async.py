"""
Async Agent Tools for MCP Server

This replaces the blocking tools with async versions that don't freeze the event loop.

Usage in akashic_mcp_server.py:
    from agent_tools_async import register_async_agent_tools
    register_async_agent_tools(mcp)
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Import the async subprocess wrappers
try:
    from .async_subprocess_fix import run_shell_async, run_python_async
except ImportError:
    from async_subprocess_fix import run_shell_async, run_python_async

# Import sandbox manager from agent_framework
try:
    from .agent_framework import _sandbox_manager, AgentTask, AGENT_LOG_DIR, PROJECT_ROOT
except ImportError:
    from agent_framework import _sandbox_manager, AgentTask, AGENT_LOG_DIR, PROJECT_ROOT


def register_async_agent_tools(mcp):
    """Register async agent tools with MCP server."""
    
    @mcp.tool()
    async def agent_run_shell(command: str, cwd: str = "", timeout: int = 60) -> str:
        """
        Run a shell command on the local system.
        
        Args:
            command: Command to execute
            cwd: Working directory (default: project root)
            timeout: Max seconds
        """
        working_dir = cwd if cwd else str(PROJECT_ROOT)
        result = await run_shell_async(command, working_dir, timeout)
        
        task_id = f"shell_{int(time.time()*1000)}"
        log_path = AGENT_LOG_DIR / f"task_{task_id}.json"
        try:
            log_path.write_text(json.dumps({
                "id": task_id,
                "type": "shell",
                "command": command[:200],
                "result": result,
                "timestamp": datetime.now().isoformat()
            }, indent=2), encoding='utf-8')
        except:
            pass
        
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    async def agent_run_python(code: str, timeout: int = 30) -> str:
        """
        Run Python code on the local system.
        
        Args:
            code: Python code to execute
            timeout: Max seconds
        """
        result = await run_python_async(code, timeout=timeout)
        
        task_id = f"python_{int(time.time()*1000)}"
        log_path = AGENT_LOG_DIR / f"task_{task_id}.json"
        try:
            log_path.write_text(json.dumps({
                "id": task_id,
                "type": "python",
                "code": code[:500],
                "result": result,
                "timestamp": datetime.now().isoformat()
            }, indent=2), encoding='utf-8')
        except:
            pass
        
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_create(name: str, include_patterns: str = "") -> str:
        """Create a sandbox environment for safe experimentation."""
        patterns = include_patterns.split(",") if include_patterns else None
        result = _sandbox_manager.create_sandbox(name, patterns)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_mutate(sandbox: str, filepath: str, 
                             mutation_type: str, content: str,
                             description: str = "") -> str:
        """Apply a code change to a sandbox."""
        result = _sandbox_manager.apply_mutation(
            sandbox, filepath, mutation_type, content, description
        )
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    async def agent_sandbox_run(sandbox: str, command: str, timeout: int = 60) -> str:
        """Run a command in a sandbox."""
        if sandbox not in _sandbox_manager.active_sandboxes:
            return json.dumps({"error": f"Sandbox not found: {sandbox}"})
        
        sandbox_path = _sandbox_manager.active_sandboxes[sandbox]["path"]
        
        result = await run_shell_async(
            command, 
            str(sandbox_path), 
            timeout,
            env={**os.environ, "AKASHIC_SANDBOX": "1", "PYTHONPATH": str(sandbox_path)}
        )
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    async def agent_sandbox_python(sandbox: str, code: str, timeout: int = 30) -> str:
        """Run Python code in a sandbox."""
        if sandbox not in _sandbox_manager.active_sandboxes:
            return json.dumps({"error": f"Sandbox not found: {sandbox}"})
        
        sandbox_path = _sandbox_manager.active_sandboxes[sandbox]["path"]
        
        result = await run_python_async(
            code,
            cwd=str(sandbox_path),
            timeout=timeout,
            script_name="_sandbox_temp.py"
        )
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_test(sandbox: str, test_pattern: str = "**/test_*.py") -> str:
        """Run tests in a sandbox."""
        result = _sandbox_manager.test_sandbox(sandbox, test_pattern)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_diff(sandbox: str) -> str:
        """Get diff between sandbox and original codebase."""
        result = _sandbox_manager.diff_sandbox(sandbox)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_propose_merge(sandbox: str) -> str:
        """Propose merging sandbox changes to main codebase."""
        result = _sandbox_manager.merge_to_main(sandbox)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_approve_merge(approval_token: str) -> str:
        """Approve and execute a merge proposal."""
        result = _sandbox_manager.approve_merge(approval_token)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_list() -> str:
        """List all sandboxes."""
        result = _sandbox_manager.list_sandboxes()
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_destroy(sandbox: str) -> str:
        """Destroy a sandbox."""
        result = _sandbox_manager.destroy_sandbox(sandbox)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    async def agent_evolve(experiment_name: str, mutations_json: str) -> str:
        """Run an evolution experiment with proposed mutations."""
        try:
            mutations = json.loads(mutations_json)
        except:
            return json.dumps({"error": "Invalid mutations JSON"})
        
        sandbox_result = _sandbox_manager.create_sandbox(experiment_name)
        if not sandbox_result.get("success"):
            return json.dumps({"error": "Failed to create sandbox", "details": sandbox_result})
        
        mutation_results = []
        for mutation in mutations:
            result = _sandbox_manager.apply_mutation(
                experiment_name,
                mutation.get("filepath"),
                mutation.get("type", "replace"),
                mutation.get("content"),
                mutation.get("description", ""),
            )
            mutation_results.append(result)
        
        test_results = _sandbox_manager.test_sandbox(experiment_name)
        diff = _sandbox_manager.diff_sandbox(experiment_name)
        
        return json.dumps({
            "experiment": experiment_name,
            "sandbox_created": sandbox_result.get("success", False),
            "mutations_applied": len([r for r in mutation_results if r.get("success")]),
            "test_results": test_results,
            "diff": diff,
            "ready_for_review": test_results.get("failed", 0) == 0,
        }, indent=2)
    
    @mcp.tool()
    def agent_generate_code(purpose: str, fairy_type: str = "observer",
                            plane: str = "P30") -> str:
        """Generate new fairy code based on requirements."""
        template = f'''"""
{purpose}

Auto-generated fairy for plane {plane}.
Type: {fairy_type}
"""

try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
    _HAS_FAIRY = True
except ImportError:
    _HAS_FAIRY = False
    Fairy = object

class Generated{fairy_type.title()}Fairy(Fairy):
    IDENTITY = {{
        "name": "Generated{fairy_type.title()}Fairy",
        "plane": "{plane}",
        "purpose": "{purpose}",
        "type": "{fairy_type}"
    }}

    def __init__(self, fabric=None):
        if _HAS_FAIRY and fabric is not None:
            super().__init__(fabric)
        self.purpose = "{purpose}"

    async def process(self, message):
        pass

    async def observe(self):
        pass

    def on_boot(self):
        return True


if __name__ == "__main__":
    fairy = Generated{fairy_type.title()}Fairy()
    print(f"Created: {{fairy.IDENTITY}}")
'''
        
        return json.dumps({
            "success": True,
            "purpose": purpose,
            "fairy_type": fairy_type,
            "plane": plane,
            "generated_code": template,
            "suggested_path": f"{plane}/generated_{fairy_type}_fairy.py"
        }, indent=2)


if __name__ == "__main__":
    print("Async agent tools module loaded successfully")
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"AGENT_LOG_DIR: {AGENT_LOG_DIR}")
