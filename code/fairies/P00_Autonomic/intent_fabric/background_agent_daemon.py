# ═══════════════════════════════════════════════════════════════════════════════
# BACKGROUND AGENT DAEMON - Autonomous Task Execution
# ═══════════════════════════════════════════════════════════════════════════════
#
# This daemon watches a task folder and executes requests autonomously.
# Like construction workers building around the busy public.
#
# Task Format (markdown or text):
#   ---
#   task: <task name>
#   priority: <1-10>
#   type: <infusion|creation|analysis|migration>
#   target: <satellite|local|both>
#   ---
#   <task description and instructions>
#
# Daemon will:
#   1. Watch task folder for new .md or .txt files
#   2. Parse task requirements
#   3. Execute autonomously
#   4. Move completed tasks to /completed
#   5. Report results to /results
#   6. Notify via forum post when done
#
# ═══════════════════════════════════════════════════════════════════════════════

import os
import sys
import time
import json
import shutil
import threading
import traceback
import subprocess
import re
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import hashlib

@dataclass
class Task:
    """A task to be executed"""
    id: str
    name: str
    priority: int
    task_type: str
    target: str
    description: str
    source_file: str
    status: str = "pending"  # pending, running, completed, failed
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None

class BackgroundAgentDaemon:
    """
    Autonomous daemon that executes tasks from a watched folder.
    Runs independently of Claude app.
    """

    def __init__(self,
                 task_folder: str,
                 results_folder: str,
                 satellite_endpoint: str = "http://192.168.1.24:5000",
                 check_interval: float = 10.0):

        self.task_folder = Path(task_folder)
        self.results_folder = Path(results_folder)
        self.completed_folder = self.task_folder / "completed"
        self.failed_folder = self.task_folder / "failed"
        self.satellite_endpoint = satellite_endpoint
        self.check_interval = check_interval

        # Create folders
        self.task_folder.mkdir(parents=True, exist_ok=True)
        self.results_folder.mkdir(parents=True, exist_ok=True)
        self.completed_folder.mkdir(exist_ok=True)
        self.failed_folder.mkdir(exist_ok=True)

        # State
        self.running = False
        self.tasks: Dict[str, Task] = {}
        self.completed_tasks: List[Task] = []
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # Task handlers by type
        self.handlers = {
            'infusion': self._handle_infusion,
            'creation': self._handle_creation,
            'analysis': self._handle_analysis,
            'migration': self._handle_migration,
            'shell': self._handle_shell,
            'python': self._handle_python,
        }

        # Log file
        self.log_file = self.results_folder / "daemon.log"

    def log(self, message: str):
        """Log a message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}\n"
        print(log_line.strip())
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_line)

    def parse_task_file(self, filepath: Path) -> Optional[Task]:
        """Parse a task file (markdown or text)"""
        try:
            content = filepath.read_text(encoding='utf-8')

            # Extract frontmatter
            frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)

            if frontmatter_match:
                frontmatter = frontmatter_match.group(1)
                description = frontmatter_match.group(2).strip()
            else:
                # No frontmatter, use filename as task name
                frontmatter = f"task: {filepath.stem}\npriority: 5\ntype: shell"
                description = content.strip()

            # Parse frontmatter
            meta = {}
            for line in frontmatter.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    meta[key.strip().lower()] = value.strip()

            # Generate task ID
            task_id = hashlib.md5(f"{filepath.name}{time.time()}".encode()).hexdigest()[:12]

            task = Task(
                id=task_id,
                name=meta.get('task', filepath.stem),
                priority=int(meta.get('priority', 5)),
                task_type=meta.get('type', 'shell'),
                target=meta.get('target', 'local'),
                description=description,
                source_file=str(filepath)
            )

            return task

        except Exception as e:
            self.log(f"Error parsing {filepath}: {e}")
            return None

    def scan_tasks(self) -> List[Task]:
        """Scan task folder for new tasks"""
        new_tasks = []

        for ext in ['*.md', '*.txt']:
            for filepath in self.task_folder.glob(ext):
                # Skip if already processed
                if str(filepath) in [t.source_file for t in self.tasks.values()]:
                    continue

                task = self.parse_task_file(filepath)
                if task:
                    new_tasks.append(task)
                    self.tasks[task.id] = task
                    self.log(f"Found new task: {task.name} (priority: {task.priority})")

        # Sort by priority (higher first)
        new_tasks.sort(key=lambda t: t.priority, reverse=True)
        return new_tasks

    def execute_task(self, task: Task) -> bool:
        """Execute a single task"""
        task.status = "running"
        task.started_at = time.time()
        self.log(f"Executing task: {task.name} [{task.task_type}]")

        try:
            handler = self.handlers.get(task.task_type, self._handle_generic)
            result = handler(task)

            task.status = "completed"
            task.completed_at = time.time()
            task.result = result

            # Move to completed
            source = Path(task.source_file)
            if source.exists():
                shutil.move(str(source), str(self.completed_folder / source.name))

            # Write result
            self._write_result(task)

            # Notify via forum (fire and forget)
            self._notify_completion(task)

            self.log(f"Completed task: {task.name}")
            return True

        except Exception as e:
            task.status = "failed"
            task.completed_at = time.time()
            task.error = str(e)

            # Move to failed
            source = Path(task.source_file)
            if source.exists():
                shutil.move(str(source), str(self.failed_folder / source.name))

            self._write_result(task)
            self.log(f"Failed task: {task.name} - {e}")
            return False

    def _write_result(self, task: Task):
        """Write task result to file"""
        result_file = self.results_folder / f"{task.id}_{task.name.replace(' ', '_')}.json"

        result_data = {
            'task_id': task.id,
            'name': task.name,
            'type': task.task_type,
            'status': task.status,
            'created_at': task.created_at,
            'started_at': task.started_at,
            'completed_at': task.completed_at,
            'duration_seconds': (task.completed_at - task.started_at) if task.completed_at and task.started_at else 0,
            'result': task.result,
            'error': task.error
        }

        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2)

    def _notify_completion(self, task: Task):
        """Notify via forum that task is done"""
        try:
            import urllib.request
            import urllib.error

            message = f"Task '{task.name}' completed in {(task.completed_at - task.started_at):.1f}s. Status: {task.status}"
            if task.error:
                message += f"\nError: {task.error}"

            # This would post to forum - simplified for now
            self.log(f"[NOTIFY] {message}")

        except Exception as e:
            self.log(f"Notification failed: {e}")

    # ═══ Task Handlers ═══

    def _handle_shell(self, task: Task) -> str:
        """Execute shell commands"""
        result = subprocess.run(
            task.description,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            raise Exception(f"Shell error: {result.stderr}")

        return result.stdout

    def _handle_python(self, task: Task) -> str:
        """Execute Python code"""
        # Write to temp file and execute
        temp_file = self.task_folder / f"_temp_{task.id}.py"
        temp_file.write_text(task.description, encoding='utf-8')

        try:
            result = subprocess.run(
                [sys.executable, str(temp_file)],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                raise Exception(f"Python error: {result.stderr}")

            return result.stdout
        finally:
            temp_file.unlink(missing_ok=True)

    def _handle_infusion(self, task: Task) -> str:
        """Handle component infusion tasks"""
        # Parse infusion instructions
        lines = task.description.split('\n')
        source_file = None
        target_path = None

        for line in lines:
            if line.startswith('source:'):
                source_file = line.split(':', 1)[1].strip()
            elif line.startswith('target:'):
                target_path = line.split(':', 1)[1].strip()

        if not source_file or not target_path:
            raise Exception("Infusion requires 'source:' and 'target:' in description")

        # Read source and send to satellite
        source_path = Path(source_file)
        if not source_path.exists():
            raise Exception(f"Source not found: {source_file}")

        content = source_path.read_text(encoding='utf-8')

        if task.target in ['satellite', 'both']:
            # Would send to satellite here
            self.log(f"Would infuse {len(content)} bytes to satellite:{target_path}")

        if task.target in ['local', 'both']:
            # Copy locally
            target = Path(target_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')

        return f"Infused {source_file} -> {target_path}"

    def _handle_creation(self, task: Task) -> str:
        """Handle file creation tasks"""
        lines = task.description.split('\n')
        filepath = None
        content_lines = []
        in_content = False

        for line in lines:
            if line.startswith('filepath:'):
                filepath = line.split(':', 1)[1].strip()
            elif line.strip() == '---content---':
                in_content = True
            elif in_content:
                content_lines.append(line)

        if not filepath:
            raise Exception("Creation requires 'filepath:' in description")

        target = Path(filepath)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('\n'.join(content_lines), encoding='utf-8')

        return f"Created {filepath}"

    def _handle_analysis(self, task: Task) -> str:
        """Handle analysis tasks"""
        # Simple analysis - count files, lines, etc.
        target_path = task.description.strip().split('\n')[0]
        target = Path(target_path)

        if not target.exists():
            raise Exception(f"Path not found: {target_path}")

        if target.is_file():
            lines = len(target.read_text(encoding='utf-8', errors='ignore').split('\n'))
            return f"File: {target_path}\nLines: {lines}"
        else:
            files = list(target.rglob('*.py'))
            return f"Directory: {target_path}\nPython files: {len(files)}"

    def _handle_migration(self, task: Task) -> str:
        """Handle migration tasks"""
        lines = task.description.split('\n')
        source = None
        dest = None

        for line in lines:
            if line.startswith('from:'):
                source = line.split(':', 1)[1].strip()
            elif line.startswith('to:'):
                dest = line.split(':', 1)[1].strip()

        if not source or not dest:
            raise Exception("Migration requires 'from:' and 'to:' in description")

        source_path = Path(source)
        dest_path = Path(dest)

        if source_path.is_file():
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, dest_path)
        else:
            shutil.copytree(source_path, dest_path, dirs_exist_ok=True)

        return f"Migrated {source} -> {dest}"

    def _handle_generic(self, task: Task) -> str:
        """Handle unknown task types"""
        return f"Acknowledged task: {task.name}\nDescription logged but no action taken."

    # ═══ Daemon Control ═══

    def start(self):
        """Start the daemon"""
        if self.running:
            return

        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.log(f"Daemon started. Watching: {self.task_folder}")

    def stop(self):
        """Stop the daemon"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        self.log("Daemon stopped")

    def _run_loop(self):
        """Main daemon loop"""
        while self.running:
            try:
                # Scan for new tasks
                new_tasks = self.scan_tasks()

                # Execute pending tasks
                pending = [t for t in self.tasks.values() if t.status == "pending"]
                pending.sort(key=lambda t: t.priority, reverse=True)

                for task in pending[:1]:  # One at a time
                    self.execute_task(task)

            except Exception as e:
                self.log(f"Loop error: {e}")

            time.sleep(self.check_interval)

    def get_status(self) -> Dict:
        """Get daemon status"""
        with self._lock:
            return {
                'running': self.running,
                'task_folder': str(self.task_folder),
                'pending': len([t for t in self.tasks.values() if t.status == 'pending']),
                'running_tasks': len([t for t in self.tasks.values() if t.status == 'running']),
                'completed': len([t for t in self.tasks.values() if t.status == 'completed']),
                'failed': len([t for t in self.tasks.values() if t.status == 'failed']),
                'total_processed': len(self.tasks)
            }


def create_sample_task(task_folder: str, name: str, task_type: str, description: str, priority: int = 5):
    """Helper to create a task file"""
    folder = Path(task_folder)
    folder.mkdir(parents=True, exist_ok=True)

    filename = f"{name.replace(' ', '_').lower()}.md"
    filepath = folder / filename

    content = f"""---
task: {name}
priority: {priority}
type: {task_type}
target: local
---
{description}
"""

    filepath.write_text(content, encoding='utf-8')
    return str(filepath)


# ═══ Standalone Runner ═══

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Background Agent Daemon")
    parser.add_argument('--task-folder', default=r"E:\coding projects\ebook\Claude_Office\agent_tasks")
    parser.add_argument('--results-folder', default=r"E:\coding projects\ebook\Claude_Office\agent_results")
    parser.add_argument('--interval', type=float, default=10.0)
    args = parser.parse_args()

    daemon = BackgroundAgentDaemon(
        task_folder=args.task_folder,
        results_folder=args.results_folder,
        check_interval=args.interval
    )

    print(f"Starting Background Agent Daemon...")
    print(f"Task folder: {daemon.task_folder}")
    print(f"Results folder: {daemon.results_folder}")
    print(f"Check interval: {daemon.check_interval}s")
    print("Drop task files (.md or .txt) into the task folder to execute them.")
    print("Press Ctrl+C to stop.")

    daemon.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping daemon...")
        daemon.stop()
