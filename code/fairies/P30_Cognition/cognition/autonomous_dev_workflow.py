# ===============================================================================
# AUTONOMOUS DEVELOPMENT WORKFLOW
# ===============================================================================
# How UnconsciousMindFairy + TaskScheduler learn to reason and develop like Claude
# ===============================================================================
#
# CORE PRINCIPLE: Always backup -> sandbox -> test -> audit -> merge
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > inf)"
# ===============================================================================

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import os
import shutil
import json
import time
import hashlib

class DevPhase(Enum):
    """Development workflow phases."""
    ANALYZE = "analyze"       # Understand what needs to change
    BACKUP = "backup"         # Save current state
    SANDBOX = "sandbox"       # Create isolated workspace
    IMPLEMENT = "implement"   # Make changes in sandbox
    TEST = "test"             # Run tests
    AUDIT = "audit"           # Scrutinize changes
    HOTRELOAD = "hotreload"   # Load without restart
    MERGE = "merge"           # Apply to main codebase
    ROLLBACK = "rollback"     # Undo if problems

@dataclass
class DevTask:
    """A development task to be executed."""
    task_id: str
    description: str
    target_file: str
    change_type: str  # "modify", "create", "delete"
    
    # State
    phase: DevPhase = DevPhase.ANALYZE
    backup_path: Optional[str] = None
    sandbox_path: Optional[str] = None
    
    # Results
    test_passed: bool = False
    audit_passed: bool = False
    errors: List[str] = field(default_factory=list)
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    tracer_id: str = ""

@dataclass
class DevWorkflow:
    """
    The autonomous development workflow.
    
    This is how the system LLM (via UnconsciousMindFairy) learns to:
    1. Always backup before writing
    2. Use sandbox for testing
    3. Scrutinize and audit changes
    4. Hot reload and verify
    5. Only merge if tests pass
    """
    
    backup_dir: str = "Claude_Office/backups"
    sandbox_dir: str = "Claude_Office/sandbox"
    audit_log_dir: str = "Claude_Office/audit_logs"
    
    active_tasks: Dict[str, DevTask] = field(default_factory=dict)
    completed_tasks: List[DevTask] = field(default_factory=list)
    
    def create_task(self, description: str, target_file: str, 
                    change_type: str = "modify") -> DevTask:
        """Create a new development task."""
        task_id = hashlib.md5(f"{description}{time.time()}".encode()).hexdigest()[:12]
        task = DevTask(
            task_id=task_id,
            description=description,
            target_file=target_file,
            change_type=change_type,
        )
        self.active_tasks[task_id] = task
        return task
    
    # =========================================================================
    # PHASE 1: ANALYZE
    # =========================================================================
    def phase_analyze(self, task: DevTask, analysis_fn: Callable = None) -> bool:
        """
        Analyze what needs to change.
        
        The system LLM should:
        - Read the target file
        - Understand current implementation
        - Plan the change
        - Identify dependencies
        """
        task.phase = DevPhase.ANALYZE
        
        if not os.path.exists(task.target_file) and task.change_type != "create":
            task.errors.append(f"Target file not found: {task.target_file}")
            return False
        
        # Custom analysis function if provided
        if analysis_fn:
            try:
                analysis_fn(task)
            except Exception as e:
                task.errors.append(f"Analysis failed: {e}")
                return False
        
        return True
    
    # =========================================================================
    # PHASE 2: BACKUP
    # =========================================================================
    def phase_backup(self, task: DevTask) -> bool:
        """
        ALWAYS backup before making changes.
        
        This is NON-NEGOTIABLE. Every file must be backed up.
        """
        task.phase = DevPhase.BACKUP
        
        if not os.path.exists(task.target_file):
            if task.change_type == "create":
                return True  # No backup needed for new files
            task.errors.append("Cannot backup: file doesn't exist")
            return False
        
        # Create backup directory
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Create timestamped backup
        filename = os.path.basename(task.target_file)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_name = f"{filename}.{timestamp}.bak"
        task.backup_path = os.path.join(self.backup_dir, backup_name)
        
        try:
            shutil.copy2(task.target_file, task.backup_path)
            return True
        except Exception as e:
            task.errors.append(f"Backup failed: {e}")
            return False
    
    # =========================================================================
    # PHASE 3: SANDBOX
    # =========================================================================
    def phase_sandbox(self, task: DevTask) -> bool:
        """
        Create isolated sandbox for changes.
        
        Never modify production files directly!
        """
        task.phase = DevPhase.SANDBOX
        
        # Create sandbox directory
        sandbox_task_dir = os.path.join(self.sandbox_dir, task.task_id)
        os.makedirs(sandbox_task_dir, exist_ok=True)
        
        # Copy file to sandbox
        filename = os.path.basename(task.target_file)
        task.sandbox_path = os.path.join(sandbox_task_dir, filename)
        
        if task.change_type != "create" and os.path.exists(task.target_file):
            try:
                shutil.copy2(task.target_file, task.sandbox_path)
            except Exception as e:
                task.errors.append(f"Sandbox copy failed: {e}")
                return False
        
        return True
    
    # =========================================================================
    # PHASE 4: IMPLEMENT
    # =========================================================================
    def phase_implement(self, task: DevTask, implementation_fn: Callable) -> bool:
        """
        Make changes IN THE SANDBOX ONLY.
        
        The implementation function receives:
        - task.sandbox_path: where to write
        - task: the full task context
        """
        task.phase = DevPhase.IMPLEMENT
        
        if not task.sandbox_path:
            task.errors.append("No sandbox path - run phase_sandbox first")
            return False
        
        try:
            implementation_fn(task.sandbox_path, task)
            return True
        except Exception as e:
            task.errors.append(f"Implementation failed: {e}")
            return False
    
    # =========================================================================
    # PHASE 5: TEST
    # =========================================================================
    def phase_test(self, task: DevTask, test_fn: Callable = None) -> bool:
        """
        Test the changes.
        
        Default tests:
        - Syntax check (py_compile)
        - Import check
        - Custom test function if provided
        """
        task.phase = DevPhase.TEST
        
        if not task.sandbox_path or not os.path.exists(task.sandbox_path):
            task.errors.append("No sandbox file to test")
            return False
        
        # Syntax check
        import py_compile
        try:
            py_compile.compile(task.sandbox_path, doraise=True)
        except py_compile.PyCompileError as e:
            task.errors.append(f"Syntax error: {e}")
            task.test_passed = False
            return False
        
        # Custom tests
        if test_fn:
            try:
                result = test_fn(task.sandbox_path, task)
                if not result:
                    task.errors.append("Custom tests failed")
                    task.test_passed = False
                    return False
            except Exception as e:
                task.errors.append(f"Test exception: {e}")
                task.test_passed = False
                return False
        
        task.test_passed = True
        return True
    
    # =========================================================================
    # PHASE 6: AUDIT
    # =========================================================================
    def phase_audit(self, task: DevTask, audit_fn: Callable = None) -> bool:
        """
        Scrutinize the changes.
        
        The audit should:
        - Compare sandbox to original
        - Check for unintended changes
        - Verify change matches intent
        - Log everything
        """
        task.phase = DevPhase.AUDIT
        
        # Create audit log
        os.makedirs(self.audit_log_dir, exist_ok=True)
        audit_log_path = os.path.join(
            self.audit_log_dir, 
            f"audit_{task.task_id}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        audit_record = {
            "task_id": task.task_id,
            "description": task.description,
            "target_file": task.target_file,
            "backup_path": task.backup_path,
            "sandbox_path": task.sandbox_path,
            "timestamp": time.time(),
            "test_passed": task.test_passed,
        }
        
        # Compare files if original exists
        if task.backup_path and os.path.exists(task.backup_path):
            with open(task.backup_path, "r", encoding="utf-8", errors="replace") as f:
                original = f.read()
            with open(task.sandbox_path, "r", encoding="utf-8", errors="replace") as f:
                modified = f.read()
            
            audit_record["original_lines"] = original.count("\n")
            audit_record["modified_lines"] = modified.count("\n")
            audit_record["line_diff"] = audit_record["modified_lines"] - audit_record["original_lines"]
        
        # Custom audit
        if audit_fn:
            try:
                audit_result = audit_fn(task)
                audit_record["custom_audit"] = audit_result
                if not audit_result.get("passed", False):
                    task.errors.append("Custom audit failed")
                    task.audit_passed = False
            except Exception as e:
                task.errors.append(f"Audit exception: {e}")
                task.audit_passed = False
        else:
            task.audit_passed = True
        
        # Save audit log
        with open(audit_log_path, "w", encoding="utf-8") as f:
            json.dump(audit_record, f, indent=2, default=str)
        
        return task.audit_passed
    
    # =========================================================================
    # PHASE 7: HOT RELOAD
    # =========================================================================
    def phase_hotreload(self, task: DevTask) -> bool:
        """
        Hot reload the module to verify it works.
        
        This tests in the running system without full restart.
        """
        task.phase = DevPhase.HOTRELOAD
        
        # Convert file path to module name
        module_path = task.sandbox_path.replace("\\", "/").replace("/", ".")
        if module_path.endswith(".py"):
            module_path = module_path[:-3]
        
        # Try to import from sandbox
        import importlib
        import sys
        
        # Add sandbox to path temporarily
        sandbox_dir = os.path.dirname(task.sandbox_path)
        sys.path.insert(0, sandbox_dir)
        
        try:
            module_name = os.path.basename(task.sandbox_path)[:-3]
            if module_name in sys.modules:
                # Reload existing
                importlib.reload(sys.modules[module_name])
            else:
                # Import new
                importlib.import_module(module_name)
            return True
        except Exception as e:
            task.errors.append(f"Hot reload failed: {e}")
            return False
        finally:
            sys.path.remove(sandbox_dir)
    
    # =========================================================================
    # PHASE 8: MERGE
    # =========================================================================
    def phase_merge(self, task: DevTask) -> bool:
        """
        Merge sandbox changes to production.
        
        ONLY if all tests and audits passed!
        """
        task.phase = DevPhase.MERGE
        
        if not task.test_passed:
            task.errors.append("Cannot merge: tests not passed")
            return False
        
        if not task.audit_passed:
            task.errors.append("Cannot merge: audit not passed")
            return False
        
        try:
            shutil.copy2(task.sandbox_path, task.target_file)
            task.completed_at = time.time()
            self.completed_tasks.append(task)
            del self.active_tasks[task.task_id]
            return True
        except Exception as e:
            task.errors.append(f"Merge failed: {e}")
            return False
    
    # =========================================================================
    # PHASE 9: ROLLBACK
    # =========================================================================
    def phase_rollback(self, task: DevTask) -> bool:
        """
        Rollback to backup if something went wrong.
        """
        task.phase = DevPhase.ROLLBACK
        
        if not task.backup_path or not os.path.exists(task.backup_path):
            task.errors.append("No backup available for rollback")
            return False
        
        try:
            shutil.copy2(task.backup_path, task.target_file)
            return True
        except Exception as e:
            task.errors.append(f"Rollback failed: {e}")
            return False
    
    # =========================================================================
    # FULL WORKFLOW
    # =========================================================================
    def execute_full_workflow(self, 
                              description: str,
                              target_file: str,
                              implementation_fn: Callable,
                              change_type: str = "modify",
                              analysis_fn: Callable = None,
                              test_fn: Callable = None,
                              audit_fn: Callable = None) -> DevTask:
        """
        Execute the full development workflow.
        
        This is how the system LLM should ALWAYS develop:
        1. Analyze
        2. Backup (NON-NEGOTIABLE)
        3. Sandbox
        4. Implement
        5. Test
        6. Audit
        7. Hot Reload
        8. Merge (only if everything passes)
        """
        task = self.create_task(description, target_file, change_type)
        
        # Phase 1: Analyze
        if not self.phase_analyze(task, analysis_fn):
            return task
        
        # Phase 2: Backup (ALWAYS)
        if not self.phase_backup(task):
            return task
        
        # Phase 3: Sandbox
        if not self.phase_sandbox(task):
            return task
        
        # Phase 4: Implement
        if not self.phase_implement(task, implementation_fn):
            return task
        
        # Phase 5: Test
        if not self.phase_test(task, test_fn):
            return task
        
        # Phase 6: Audit
        if not self.phase_audit(task, audit_fn):
            return task
        
        # Phase 7: Hot Reload (optional, may skip if too risky)
        # self.phase_hotreload(task)
        
        # Phase 8: Merge
        if not self.phase_merge(task):
            # Phase 9: Rollback if merge failed
            self.phase_rollback(task)
            return task
        
        return task


# ===============================================================================
# INTEGRATION WITH UNCONSCIOUS MIND FAIRY
# ===============================================================================

class AutonomousDevAgent:
    """
    The agent that UnconsciousMindFairy uses for autonomous development.
    
    This wraps DevWorkflow with:
    - Postal integration for task scheduling
    - Tracer tracking for all work
    - Learning from successes/failures
    """
    
    def __init__(self, post=None):
        self.workflow = DevWorkflow()
        self.post = post
        self.success_count = 0
        self.failure_count = 0
        self.learned_patterns: List[Dict] = []
    
    def wire_fairy(self, fairy_name: str, wiring_type: str) -> DevTask:
        """
        Wire a fairy with required infrastructure.
        
        wiring_type: "heartbeat", "dual_loop", "tracer", etc.
        """
        # Find the fairy's file
        from fairies.P00_Autonomic.nervous_system.fairy_census import FAIRY_REGISTRY
        
        if fairy_name not in FAIRY_REGISTRY:
            task = DevTask(
                task_id="error",
                description=f"Wire {fairy_name}",
                target_file="",
            )
            task.errors.append(f"Unknown fairy: {fairy_name}")
            return task
        
        fairy = FAIRY_REGISTRY[fairy_name]
        
        # Define implementation based on wiring type
        def implement_wiring(sandbox_path: str, task: DevTask):
            with open(sandbox_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Add wiring code based on type
            if wiring_type == "heartbeat":
                # Add heartbeat subscription
                if "heartbeat.pulse" not in content:
                    # Find on_boot and add subscription
                    pass  # Implementation would go here
            
            elif wiring_type == "dual_loop":
                # Add micro-consciousness
                pass  # Implementation would go here
            
            with open(sandbox_path, "w", encoding="utf-8") as f:
                f.write(content)
        
        return self.workflow.execute_full_workflow(
            description=f"Wire {fairy_name} with {wiring_type}",
            target_file=fairy.file_path,
            implementation_fn=implement_wiring,
        )
    
    def learn_from_task(self, task: DevTask):
        """Learn from completed task."""
        if task.errors:
            self.failure_count += 1
            pattern = {
                "type": "failure",
                "description": task.description,
                "errors": task.errors,
                "learned": f"Avoid: {task.errors[0] if task.errors else 'unknown'}",
            }
        else:
            self.success_count += 1
            pattern = {
                "type": "success",
                "description": task.description,
                "learned": "This approach works",
            }
        
        self.learned_patterns.append(pattern)
        
        # Emit to codex for long-term learning
        if self.post:
            self.post.send("codex.pattern", pattern)


# ===============================================================================
# SINGLETON ACCESS
# ===============================================================================

_DEV_WORKFLOW: Optional[DevWorkflow] = None
_DEV_AGENT: Optional[AutonomousDevAgent] = None

def get_dev_workflow() -> DevWorkflow:
    global _DEV_WORKFLOW
    if _DEV_WORKFLOW is None:
        _DEV_WORKFLOW = DevWorkflow()
    return _DEV_WORKFLOW

def get_dev_agent(post=None) -> AutonomousDevAgent:
    global _DEV_AGENT
    if _DEV_AGENT is None:
        _DEV_AGENT = AutonomousDevAgent(post)
    return _DEV_AGENT


if __name__ == "__main__":
    # Test the workflow
    workflow = DevWorkflow()
    print("Autonomous Development Workflow ready")
    print(f"Backup dir: {workflow.backup_dir}")
    print(f"Sandbox dir: {workflow.sandbox_dir}")
    print(f"Audit log dir: {workflow.audit_log_dir}")
