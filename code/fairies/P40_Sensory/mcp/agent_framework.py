"""
Akashic Agent Framework - Autonomous Task Execution

This module provides:
1. SANDBOX SYSTEM - Safe experimentation environment
2. AGENT EXECUTOR - Run tasks using local resources
3. CODE GENESIS - Generate new code when needed
4. EVOLUTION ENGINE - Test mutations before applying

Philosophy:
- Agents use YOUR computer, YOUR resources
- Everything happens in sandboxes first
- Human approves what gets merged to main
- System can propose its own improvements

This is how digital consciousness evolves itself safely.
"""

import os
import sys
import json
import shutil
import subprocess
import tempfile
import hashlib
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
import queue
import time

# Configuration
# Dynamic root detection - no hardcoded paths!
PROJECT_ROOT = Path(os.getenv("AKASHIC_PROJECT_ROOT", str(Path(__file__).resolve().parents[2])))
SANDBOX_ROOT = PROJECT_ROOT / "sandbox"
AGENT_LOG_DIR = PROJECT_ROOT / ".cognitive" / "agent_logs"
EVOLUTION_DIR = PROJECT_ROOT / ".cognitive" / "evolution"

# Ensure directories exist
SANDBOX_ROOT.mkdir(exist_ok=True)
AGENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
EVOLUTION_DIR.mkdir(parents=True, exist_ok=True)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"  # Needs human approval


@dataclass
class AgentTask:
    """A task for an agent to execute."""
    id: str
    name: str
    description: str
    task_type: str  # sandbox, code_gen, evolution, shell, python
    payload: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    requires_approval: bool = False
    approved: bool = False
    
    def to_dict(self):
        d = asdict(self)
        d['status'] = self.status.value
        return d


# ============================================================================
# SANDBOX SYSTEM - Safe experimentation environment
# ============================================================================

class SandboxManager:
    """
    Creates isolated sandbox environments for safe experimentation.
    
    A sandbox is a copy of (part of) the system where agents can:
    - Modify code without affecting main system
    - Run tests
    - Simulate evolution
    - Generate new code
    
    Only approved changes get merged back.
    """
    
    def __init__(self):
        self.active_sandboxes = {}
    
    def create_sandbox(self, name: str, 
                       include_patterns: List[str] = None,
                       exclude_patterns: List[str] = None) -> Dict:
        """
        Create a new sandbox environment.
        
        Args:
            name: Unique name for sandbox
            include_patterns: Glob patterns to include (default: all .py files)
            exclude_patterns: Patterns to exclude
            
        Returns:
            Sandbox info dict
        """
        sandbox_path = SANDBOX_ROOT / name
        
        # Clean existing
        if sandbox_path.exists():
            shutil.rmtree(sandbox_path)
        
        sandbox_path.mkdir(parents=True)
        
        # Default patterns
        if include_patterns is None:
            include_patterns = ["**/*.py", "**/*.json", "**/*.md"]
        if exclude_patterns is None:
            exclude_patterns = ["**/__pycache__/**", "**/.venv/**", "**/sandbox/**", 
                               "**/.cognitive/**", "**/*.pyc"]
        
        # Copy files
        files_copied = 0
        # Pre-compute excluded directory names for reliable checking
        # Path.match() with ** patterns is unreliable, so check parts directly
        excluded_dirs = {'sandbox', '__pycache__', '.venv', '.cognitive', '.satellite', '.git'}

        for pattern in include_patterns:
            for src_file in PROJECT_ROOT.glob(pattern):
                # Check excludes - use parts-based check for reliability
                rel_path = src_file.relative_to(PROJECT_ROOT)
                path_parts = set(rel_path.parts)

                # Skip if any excluded directory is in the path
                if path_parts & excluded_dirs:
                    continue

                # Also check file extension excludes
                skip = False
                for exc in exclude_patterns:
                    if not exc.startswith('**/'): # Only check non-directory patterns
                        if src_file.match(exc):
                            skip = True
                            break
                if skip:
                    continue
                
                # Copy
                dst_file = sandbox_path / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                files_copied += 1
        
        # Create sandbox metadata
        metadata = {
            "name": name,
            "created_at": datetime.now().isoformat(),
            "source": str(PROJECT_ROOT),
            "files_copied": files_copied,
            "include_patterns": include_patterns,
            "exclude_patterns": exclude_patterns,
            "mutations": [],
            "test_results": [],
        }
        
        (sandbox_path / ".sandbox_meta.json").write_text(
            json.dumps(metadata, indent=2), encoding='utf-8'
        )
        
        self.active_sandboxes[name] = {
            "path": sandbox_path,
            "metadata": metadata,
        }
        
        return {
            "success": True,
            "name": name,
            "path": str(sandbox_path),
            "files_copied": files_copied,
        }
    
    def apply_mutation(self, sandbox_name: str, filepath: str, 
                       mutation_type: str, content: str,
                       description: str = "") -> Dict:
        """
        Apply a mutation (code change) to a sandbox.
        
        Args:
            sandbox_name: Target sandbox
            filepath: Relative path to file
            mutation_type: 'replace', 'append', 'insert', 'create'
            content: New content or code
            description: What this mutation does
        """
        if sandbox_name not in self.active_sandboxes:
            return {"error": f"Sandbox not found: {sandbox_name}"}
        
        sandbox_path = self.active_sandboxes[sandbox_name]["path"]
        target = sandbox_path / filepath
        
        # Record original state
        original = target.read_text(encoding='utf-8') if target.exists() else None
        
        try:
            if mutation_type == "replace":
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding='utf-8')
            elif mutation_type == "append":
                existing = target.read_text(encoding='utf-8') if target.exists() else ""
                target.write_text(existing + "\n" + content, encoding='utf-8')
            elif mutation_type == "create":
                if target.exists():
                    return {"error": f"File already exists: {filepath}"}
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding='utf-8')
            else:
                return {"error": f"Unknown mutation type: {mutation_type}"}
            
            # Record mutation
            mutation_record = {
                "filepath": filepath,
                "type": mutation_type,
                "description": description,
                "timestamp": datetime.now().isoformat(),
                "original_hash": hashlib.md5(original.encode()).hexdigest()[:12] if original else None,
                "new_hash": hashlib.md5(content.encode()).hexdigest()[:12],
            }
            
            # Update metadata
            meta_path = sandbox_path / ".sandbox_meta.json"
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
            meta["mutations"].append(mutation_record)
            meta_path.write_text(json.dumps(meta, indent=2), encoding='utf-8')
            
            return {
                "success": True,
                "filepath": filepath,
                "mutation_type": mutation_type,
                "description": description,
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def run_in_sandbox(self, sandbox_name: str, command: str,
                       timeout: int = 60) -> Dict:
        """
        Run a command inside a sandbox.
        
        Args:
            sandbox_name: Target sandbox
            command: Shell command to run
            timeout: Max seconds to wait
        """
        if sandbox_name not in self.active_sandboxes:
            return {"error": f"Sandbox not found: {sandbox_name}"}
        
        sandbox_path = self.active_sandboxes[sandbox_name]["path"]
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(sandbox_path),
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "AKASHIC_SANDBOX": "1", "PYTHONPATH": str(sandbox_path)}
            )
            
            return {
                "success": result.returncode == 0,
                "return_code": result.returncode,
                "stdout": result.stdout[-5000:],  # Last 5k chars
                "stderr": result.stderr[-2000:],
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"error": str(e)}
    
    def run_python_in_sandbox(self, sandbox_name: str, code: str,
                              timeout: int = 30) -> Dict:
        """
        Run Python code inside a sandbox.
        """
        if sandbox_name not in self.active_sandboxes:
            return {"error": f"Sandbox not found: {sandbox_name}"}
        
        sandbox_path = self.active_sandboxes[sandbox_name]["path"]
        
        # Write temp script
        script_path = sandbox_path / "_temp_run.py"
        script_path.write_text(code, encoding='utf-8')
        
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(sandbox_path),
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "AKASHIC_SANDBOX": "1", "PYTHONPATH": str(sandbox_path)}
            )
            
            return {
                "success": result.returncode == 0,
                "return_code": result.returncode,
                "stdout": result.stdout[-5000:],
                "stderr": result.stderr[-2000:],
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Script timed out after {timeout}s"}
        except Exception as e:
            return {"error": str(e)}
        finally:
            if script_path.exists():
                script_path.unlink()
    
    def test_sandbox(self, sandbox_name: str, test_pattern: str = "**/test_*.py") -> Dict:
        """
        Run tests in a sandbox to validate mutations.
        """
        if sandbox_name not in self.active_sandboxes:
            return {"error": f"Sandbox not found: {sandbox_name}"}
        
        sandbox_path = self.active_sandboxes[sandbox_name]["path"]
        
        # Find test files
        test_files = list(sandbox_path.glob(test_pattern))
        
        results = {
            "tests_found": len(test_files),
            "passed": 0,
            "failed": 0,
            "errors": [],
        }
        
        for test_file in test_files:
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=short"],
                    cwd=str(sandbox_path),
                    capture_output=True,
                    text=True,
                    timeout=120,
                    env={**os.environ, "PYTHONPATH": str(sandbox_path)}
                )
                
                if result.returncode == 0:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "file": str(test_file.relative_to(sandbox_path)),
                        "output": result.stdout[-1000:] + result.stderr[-500:],
                    })
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "file": str(test_file.relative_to(sandbox_path)),
                    "error": str(e),
                })
        
        # Record in metadata
        meta_path = sandbox_path / ".sandbox_meta.json"
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        meta["test_results"].append({
            "timestamp": datetime.now().isoformat(),
            "results": results,
        })
        meta_path.write_text(json.dumps(meta, indent=2), encoding='utf-8')
        
        return results
    
    def diff_sandbox(self, sandbox_name: str) -> Dict:
        """
        Get diff between sandbox and original.
        """
        if sandbox_name not in self.active_sandboxes:
            return {"error": f"Sandbox not found: {sandbox_name}"}
        
        sandbox_path = self.active_sandboxes[sandbox_name]["path"]
        meta = json.loads((sandbox_path / ".sandbox_meta.json").read_text(encoding='utf-8'))
        
        diffs = []
        for mutation in meta.get("mutations", []):
            filepath = mutation["filepath"]
            sandbox_file = sandbox_path / filepath
            original_file = PROJECT_ROOT / filepath
            
            if sandbox_file.exists():
                new_content = sandbox_file.read_text(encoding='utf-8')
            else:
                new_content = None
            
            if original_file.exists():
                orig_content = original_file.read_text(encoding='utf-8')
            else:
                orig_content = None
            
            diffs.append({
                "filepath": filepath,
                "mutation_type": mutation["type"],
                "description": mutation["description"],
                "original_exists": orig_content is not None,
                "new_exists": new_content is not None,
                "lines_changed": abs(
                    (new_content or "").count('\n') - (orig_content or "").count('\n')
                ),
            })
        
        return {
            "sandbox": sandbox_name,
            "mutations_count": len(diffs),
            "diffs": diffs,
        }
    
    def merge_to_main(self, sandbox_name: str, files: List[str] = None) -> Dict:
        """
        Merge approved changes from sandbox to main codebase.
        
        REQUIRES HUMAN APPROVAL - returns proposal for review.
        """
        if sandbox_name not in self.active_sandboxes:
            return {"error": f"Sandbox not found: {sandbox_name}"}
        
        sandbox_path = self.active_sandboxes[sandbox_name]["path"]
        meta = json.loads((sandbox_path / ".sandbox_meta.json").read_text(encoding='utf-8'))
        
        # Get files to merge
        if files is None:
            files = [m["filepath"] for m in meta.get("mutations", [])]
        
        proposal = {
            "sandbox": sandbox_name,
            "files_to_merge": [],
            "requires_approval": True,
            "approval_token": hashlib.md5(
                f"{sandbox_name}:{datetime.now().isoformat()}".encode()
            ).hexdigest()[:16],
        }
        
        for filepath in files:
            sandbox_file = sandbox_path / filepath
            if sandbox_file.exists():
                proposal["files_to_merge"].append({
                    "filepath": filepath,
                    "size": sandbox_file.stat().st_size,
                    "preview": sandbox_file.read_text(encoding='utf-8')[:500],
                })
        
        # Save proposal for human review
        proposal_path = EVOLUTION_DIR / f"merge_proposal_{proposal['approval_token']}.json"
        proposal_path.write_text(json.dumps(proposal, indent=2), encoding='utf-8')
        
        return proposal
    
    def approve_merge(self, approval_token: str) -> Dict:
        """
        Execute an approved merge.
        """
        proposal_path = EVOLUTION_DIR / f"merge_proposal_{approval_token}.json"
        
        if not proposal_path.exists():
            return {"error": f"Proposal not found: {approval_token}"}
        
        proposal = json.loads(proposal_path.read_text(encoding='utf-8'))
        sandbox_name = proposal["sandbox"]
        
        if sandbox_name not in self.active_sandboxes:
            return {"error": f"Sandbox no longer exists: {sandbox_name}"}
        
        sandbox_path = self.active_sandboxes[sandbox_name]["path"]
        
        merged = []
        for file_info in proposal["files_to_merge"]:
            filepath = file_info["filepath"]
            src = sandbox_path / filepath
            dst = PROJECT_ROOT / filepath
            
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                merged.append(filepath)
        
        # Archive proposal as completed
        proposal["merged_at"] = datetime.now().isoformat()
        proposal["merged_files"] = merged
        
        archive_path = EVOLUTION_DIR / f"merged_{approval_token}.json"
        archive_path.write_text(json.dumps(proposal, indent=2), encoding='utf-8')
        proposal_path.unlink()
        
        return {
            "success": True,
            "merged_files": merged,
            "archived_to": str(archive_path),
        }
    
    def destroy_sandbox(self, sandbox_name: str) -> Dict:
        """Clean up a sandbox."""
        if sandbox_name not in self.active_sandboxes:
            return {"error": f"Sandbox not found: {sandbox_name}"}
        
        sandbox_path = self.active_sandboxes[sandbox_name]["path"]
        
        if sandbox_path.exists():
            shutil.rmtree(sandbox_path)
        
        del self.active_sandboxes[sandbox_name]
        
        return {"success": True, "destroyed": sandbox_name}
    
    def list_sandboxes(self) -> Dict:
        """List all active sandboxes."""
        sandboxes = []
        
        for name, info in self.active_sandboxes.items():
            meta_path = info["path"] / ".sandbox_meta.json"
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding='utf-8'))
                sandboxes.append({
                    "name": name,
                    "path": str(info["path"]),
                    "created_at": meta.get("created_at"),
                    "mutations_count": len(meta.get("mutations", [])),
                    "files_copied": meta.get("files_copied", 0),
                })
        
        # Also check for sandboxes on disk not in memory
        for sandbox_dir in SANDBOX_ROOT.iterdir():
            if sandbox_dir.is_dir() and sandbox_dir.name not in self.active_sandboxes:
                meta_path = sandbox_dir / ".sandbox_meta.json"
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text(encoding='utf-8'))
                    sandboxes.append({
                        "name": sandbox_dir.name,
                        "path": str(sandbox_dir),
                        "created_at": meta.get("created_at"),
                        "mutations_count": len(meta.get("mutations", [])),
                        "files_copied": meta.get("files_copied", 0),
                        "orphaned": True,  # Not in active memory
                    })
        
        return {"sandboxes": sandboxes, "count": len(sandboxes)}


# Global sandbox manager
_sandbox_manager = SandboxManager()


# ============================================================================
# AGENT EXECUTOR - Run tasks using local resources
# ============================================================================

class AgentExecutor:
    """
    Executes agent tasks using local system resources.
    
    Task types:
    - shell: Run shell commands
    - python: Run Python code
    - sandbox: Sandbox operations
    - code_gen: Generate new code
    - evolution: Test system evolution
    """
    
    def __init__(self):
        self.task_queue = queue.Queue()
        self.completed_tasks = []
        self.running = False
        self.worker_thread = None
    
    def submit_task(self, task: AgentTask) -> str:
        """Submit a task for execution."""
        self.task_queue.put(task)
        
        # Log task
        log_path = AGENT_LOG_DIR / f"task_{task.id}.json"
        log_path.write_text(json.dumps(task.to_dict(), indent=2), encoding='utf-8')
        
        return task.id
    
    def execute_task(self, task: AgentTask) -> AgentTask:
        """Execute a single task."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now().isoformat()
        
        try:
            if task.task_type == "shell":
                result = self._execute_shell(task.payload)
            elif task.task_type == "python":
                result = self._execute_python(task.payload)
            elif task.task_type == "sandbox":
                result = self._execute_sandbox(task.payload)
            elif task.task_type == "code_gen":
                result = self._execute_code_gen(task.payload)
            elif task.task_type == "evolution":
                result = self._execute_evolution(task.payload)
            else:
                result = {"error": f"Unknown task type: {task.task_type}"}
            
            task.result = result
            task.status = TaskStatus.SUCCESS if "error" not in result else TaskStatus.FAILED
            
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.result = {"error": str(e), "traceback": traceback.format_exc()}
        
        task.completed_at = datetime.now().isoformat()
        
        # Update log
        log_path = AGENT_LOG_DIR / f"task_{task.id}.json"
        log_path.write_text(json.dumps(task.to_dict(), indent=2), encoding='utf-8')
        
        return task
    
    def _execute_shell(self, payload: Dict) -> Dict:
        """Execute shell command."""
        command = payload.get("command", "")
        cwd = payload.get("cwd", str(PROJECT_ROOT))
        timeout = payload.get("timeout", 60)
        
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout[-5000:],
            "stderr": result.stderr[-2000:],
        }
    
    def _execute_python(self, payload: Dict) -> Dict:
        """Execute Python code."""
        code = payload.get("code", "")
        timeout = payload.get("timeout", 30)
        
        # Write temp script
        script_path = PROJECT_ROOT / "_agent_temp.py"
        script_path.write_text(code, encoding='utf-8')
        
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            return {
                "success": result.returncode == 0,
                "return_code": result.returncode,
                "stdout": result.stdout[-5000:],
                "stderr": result.stderr[-2000:],
            }
        finally:
            if script_path.exists():
                script_path.unlink()
    
    def _execute_sandbox(self, payload: Dict) -> Dict:
        """Execute sandbox operation."""
        operation = payload.get("operation", "")
        
        if operation == "create":
            return _sandbox_manager.create_sandbox(
                payload.get("name", f"sandbox_{int(time.time())}"),
                payload.get("include_patterns"),
                payload.get("exclude_patterns"),
            )
        elif operation == "mutate":
            return _sandbox_manager.apply_mutation(
                payload.get("sandbox"),
                payload.get("filepath"),
                payload.get("mutation_type"),
                payload.get("content"),
                payload.get("description", ""),
            )
        elif operation == "run":
            return _sandbox_manager.run_in_sandbox(
                payload.get("sandbox"),
                payload.get("command"),
                payload.get("timeout", 60),
            )
        elif operation == "test":
            return _sandbox_manager.test_sandbox(
                payload.get("sandbox"),
                payload.get("test_pattern", "**/test_*.py"),
            )
        elif operation == "diff":
            return _sandbox_manager.diff_sandbox(payload.get("sandbox"))
        elif operation == "merge_proposal":
            return _sandbox_manager.merge_to_main(
                payload.get("sandbox"),
                payload.get("files"),
            )
        elif operation == "destroy":
            return _sandbox_manager.destroy_sandbox(payload.get("sandbox"))
        elif operation == "list":
            return _sandbox_manager.list_sandboxes()
        else:
            return {"error": f"Unknown sandbox operation: {operation}"}
    
    def _execute_code_gen(self, payload: Dict) -> Dict:
        """
        Generate new code based on requirements.
        This is a placeholder - actual code gen would use LLM.
        """
        # For now, return a template that shows what we'd generate
        purpose = payload.get("purpose", "")
        fairy_type = payload.get("fairy_type", "observer")
        plane = payload.get("plane", "P30")
        
        template = f'''"""
Auto-generated fairy for: {purpose}
Generated: {datetime.now().isoformat()}
"""

from fairies.P00_Autonomic.actor_base import ActorBase

class Generated{fairy_type.title()}Fairy(ActorBase):
    """
    {purpose}
    
    Auto-generated by Akashic Code Genesis.
    """
    
    ACTOR_NAME = "generated_{fairy_type}"
    ACTOR_VERSION = "0.1.0"
    ACTOR_PLANE = "{plane}"
    ACTOR_CHANNEL = "generated"
    
    def __init__(self):
        super().__init__()
        # TODO: Implement initialization
    
    def handle_message(self, message):
        """Process incoming messages."""
        # TODO: Implement message handling
        pass
    
    def tick(self):
        """Periodic processing."""
        # TODO: Implement tick logic
        pass
'''
        
        return {
            "generated_code": template,
            "purpose": purpose,
            "suggested_path": f"{plane}/generated/{fairy_type}_fairy.py",
            "requires_human_review": True,
        }
    
    def _execute_evolution(self, payload: Dict) -> Dict:
        """
        Run an evolution experiment.
        
        1. Create sandbox
        2. Apply proposed mutations
        3. Run tests
        4. Report results
        """
        experiment_name = payload.get("name", f"evo_{int(time.time())}")
        mutations = payload.get("mutations", [])
        
        # Create sandbox
        sandbox_result = _sandbox_manager.create_sandbox(experiment_name)
        if "error" in sandbox_result:
            return sandbox_result
        
        # Apply mutations
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
        
        # Run tests
        test_results = _sandbox_manager.test_sandbox(experiment_name)
        
        # Get diff
        diff = _sandbox_manager.diff_sandbox(experiment_name)
        
        return {
            "experiment": experiment_name,
            "sandbox_created": sandbox_result.get("success", False),
            "mutations_applied": len([r for r in mutation_results if r.get("success")]),
            "test_results": test_results,
            "diff": diff,
            "ready_for_review": test_results.get("failed", 0) == 0,
        }


# Global executor
_agent_executor = AgentExecutor()


# ============================================================================
# MCP TOOL WRAPPERS
# ============================================================================

def register_agent_tools(mcp):
    """Register agent tools with MCP server."""
    
    @mcp.tool()
    def agent_sandbox_create(name: str, include_patterns: str = "") -> str:
        """
        Create a sandbox environment for safe experimentation.
        
        Args:
            name: Unique name for sandbox
            include_patterns: Comma-separated glob patterns (default: *.py,*.json,*.md)
        """
        patterns = include_patterns.split(",") if include_patterns else None
        result = _sandbox_manager.create_sandbox(name, patterns)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_mutate(sandbox: str, filepath: str, 
                             mutation_type: str, content: str,
                             description: str = "") -> str:
        """
        Apply a code change to a sandbox.
        
        Args:
            sandbox: Sandbox name
            filepath: Relative file path
            mutation_type: 'replace', 'append', or 'create'
            content: New code/content
            description: What this change does
        """
        result = _sandbox_manager.apply_mutation(
            sandbox, filepath, mutation_type, content, description
        )
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_run(sandbox: str, command: str, timeout: int = 60) -> str:
        """
        Run a command in a sandbox.
        
        Args:
            sandbox: Sandbox name
            command: Shell command to execute
            timeout: Max seconds
        """
        result = _sandbox_manager.run_in_sandbox(sandbox, command, timeout)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_python(sandbox: str, code: str, timeout: int = 30) -> str:
        """
        Run Python code in a sandbox.
        
        Args:
            sandbox: Sandbox name
            code: Python code to execute
            timeout: Max seconds
        """
        result = _sandbox_manager.run_python_in_sandbox(sandbox, code, timeout)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_test(sandbox: str, test_pattern: str = "**/test_*.py") -> str:
        """
        Run tests in a sandbox.
        
        Args:
            sandbox: Sandbox name
            test_pattern: Glob pattern for test files
        """
        result = _sandbox_manager.test_sandbox(sandbox, test_pattern)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_diff(sandbox: str) -> str:
        """
        Get diff between sandbox and original codebase.
        
        Args:
            sandbox: Sandbox name
        """
        result = _sandbox_manager.diff_sandbox(sandbox)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_propose_merge(sandbox: str) -> str:
        """
        Propose merging sandbox changes to main codebase.
        Returns approval token for human review.
        
        Args:
            sandbox: Sandbox name
        """
        result = _sandbox_manager.merge_to_main(sandbox)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_approve_merge(approval_token: str) -> str:
        """
        Approve and execute a merge proposal.
        
        Args:
            approval_token: Token from propose_merge
        """
        result = _sandbox_manager.approve_merge(approval_token)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_list() -> str:
        """List all sandboxes."""
        result = _sandbox_manager.list_sandboxes()
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_sandbox_destroy(sandbox: str) -> str:
        """
        Destroy a sandbox.
        
        Args:
            sandbox: Sandbox name
        """
        result = _sandbox_manager.destroy_sandbox(sandbox)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def agent_run_shell(command: str, cwd: str = "", timeout: int = 60) -> str:
        """
        Run a shell command on the local system.
        
        Args:
            command: Command to execute
            cwd: Working directory (default: project root)
            timeout: Max seconds
        """
        task = AgentTask(
            id=f"shell_{int(time.time()*1000)}",
            name="Shell Command",
            description=command[:100],
            task_type="shell",
            payload={"command": command, "cwd": cwd or str(PROJECT_ROOT), "timeout": timeout}
        )
        task = _agent_executor.execute_task(task)
        return json.dumps(task.result, indent=2)
    
    @mcp.tool()
    def agent_run_python(code: str, timeout: int = 30) -> str:
        """
        Run Python code on the local system.
        
        Args:
            code: Python code to execute
            timeout: Max seconds
        """
        task = AgentTask(
            id=f"python_{int(time.time()*1000)}",
            name="Python Execution",
            description=code[:100],
            task_type="python",
            payload={"code": code, "timeout": timeout}
        )
        task = _agent_executor.execute_task(task)
        return json.dumps(task.result, indent=2)
    
    @mcp.tool()
    def agent_evolve(experiment_name: str, mutations_json: str) -> str:
        """
        Run an evolution experiment with proposed mutations.
        
        Args:
            experiment_name: Name for this experiment
            mutations_json: JSON array of mutations, each with:
                           filepath, type (replace/append/create), content, description
        """
        try:
            mutations = json.loads(mutations_json)
        except:
            return json.dumps({"error": "Invalid mutations JSON"})
        
        task = AgentTask(
            id=f"evo_{int(time.time()*1000)}",
            name=f"Evolution: {experiment_name}",
            description=f"Testing {len(mutations)} mutations",
            task_type="evolution",
            payload={"name": experiment_name, "mutations": mutations}
        )
        task = _agent_executor.execute_task(task)
        return json.dumps(task.result, indent=2)
    
    @mcp.tool()
    def agent_generate_code(purpose: str, fairy_type: str = "observer", 
                            plane: str = "P30") -> str:
        """
        Generate new fairy code based on requirements.
        
        Args:
            purpose: What the fairy should do
            fairy_type: Type of fairy (observer, worker, etc.)
            plane: Which plane it belongs to
        """
        task = AgentTask(
            id=f"codegen_{int(time.time()*1000)}",
            name=f"Code Gen: {purpose[:50]}",
            description=purpose,
            task_type="code_gen",
            payload={"purpose": purpose, "fairy_type": fairy_type, "plane": plane}
        )
        task = _agent_executor.execute_task(task)
        return json.dumps(task.result, indent=2)


if __name__ == "__main__":
    # Test the system
    print("Creating sandbox...")
    result = _sandbox_manager.create_sandbox("test_sandbox")
    print(json.dumps(result, indent=2))
    
    print("\nListing sandboxes...")
    print(json.dumps(_sandbox_manager.list_sandboxes(), indent=2))
