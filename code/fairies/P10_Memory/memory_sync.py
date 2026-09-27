# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY SYNC - RAID-like Mirror Between Windows and Satellite
# ═══════════════════════════════════════════════════════════════════════════════
#
# Keeps memory in sync across nodes. What Ace puts into Windows memory
# gets mirrored to the satellite so fairies can access all knowledge.
#
# Like RAID-1: Same data, multiple locations, automatic sync.
#
# ═══════════════════════════════════════════════════════════════════════════════

import os
import time
import json
import hashlib
import threading
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
import requests

@dataclass
class SyncState:
    """Track sync state for a file/directory"""
    path: str
    local_hash: str = ""
    remote_hash: str = ""
    last_synced: float = 0
    last_modified: float = 0
    sync_status: str = "unknown"  # synced, pending, conflict, error

@dataclass
class SyncConfig:
    """Configuration for memory sync"""
    local_base: str = "E:/coding projects/ebook/P10_Memory"
    remote_base: str = "/root/akashic/memory"
    satellite_url: str = "http://192.168.1.24:5000"

    # What to sync
    sync_patterns: List[str] = field(default_factory=lambda: [
        "Akashic_triple_helix_memory_storage/**/*",
        "codex/**/*",
        "registry/**/*",
        "system_knowledge/**/*"
    ])

    # What to exclude
    exclude_patterns: List[str] = field(default_factory=lambda: [
        "__pycache__",
        "*.pyc",
        ".git",
        "*.tmp"
    ])

    # Sync interval
    interval_seconds: int = 60


class MemorySyncAgent:
    """
    Keeps Windows memory mirrored to satellite.

    Works in background, syncs changes automatically.
    Like a RAID controller for consciousness.
    """

    def __init__(self, config: SyncConfig = None):
        self.config = config or SyncConfig()
        self._lock = threading.RLock()

        # Track sync state
        self.sync_states: Dict[str, SyncState] = {}

        # Stats
        self.files_synced = 0
        self.bytes_synced = 0
        self.last_sync_time = 0
        self.sync_errors: List[Dict] = []

        # Background thread
        self.running = False
        self._thread: Optional[threading.Thread] = None

        # State file
        self.state_file = Path(self.config.local_base) / ".sync_state.json"
        self._load_state()

    def _load_state(self):
        """Load sync state from disk"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    for path, state in data.items():
                        self.sync_states[path] = SyncState(**state)
            except:
                pass

    def _save_state(self):
        """Save sync state to disk"""
        try:
            with open(self.state_file, 'w') as f:
                data = {path: {
                    'path': s.path,
                    'local_hash': s.local_hash,
                    'remote_hash': s.remote_hash,
                    'last_synced': s.last_synced,
                    'last_modified': s.last_modified,
                    'sync_status': s.sync_status
                } for path, s in self.sync_states.items()}
                json.dump(data, f, indent=2)
        except:
            pass

    def _hash_file(self, filepath: Path) -> str:
        """Calculate hash of a file"""
        if not filepath.exists():
            return ""
        try:
            with open(filepath, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return ""

    def _should_exclude(self, path: str) -> bool:
        """Check if path should be excluded"""
        for pattern in self.config.exclude_patterns:
            if pattern in path:
                return True
        return False

    def _get_files_to_sync(self) -> List[Path]:
        """Get list of files that need syncing"""
        files = []
        base = Path(self.config.local_base)

        for pattern in self.config.sync_patterns:
            # Handle glob patterns
            for filepath in base.glob(pattern):
                if filepath.is_file() and not self._should_exclude(str(filepath)):
                    files.append(filepath)

        return files

    def _check_satellite_health(self) -> bool:
        """Check if satellite is reachable"""
        try:
            r = requests.get(f"{self.config.satellite_url}/health", timeout=5)
            return r.status_code == 200
        except:
            return False

    def _upload_file(self, filepath: Path) -> bool:
        """Upload a file to satellite"""
        try:
            # Calculate relative path
            rel_path = filepath.relative_to(Path(self.config.local_base))
            remote_path = f"{self.config.remote_base}/{rel_path}"

            # Read file content
            with open(filepath, 'rb') as f:
                content = f.read()

            # Upload via /python endpoint (write file)
            import base64
            b64_content = base64.b64encode(content).decode('ascii')

            code = f'''
import base64
import os

content = base64.b64decode("{b64_content}")
os.makedirs(os.path.dirname("{remote_path}") or ".", exist_ok=True)
with open("{remote_path}", "wb") as f:
    f.write(content)
result = {{"path": "{remote_path}", "size": len(content)}}
'''

            r = requests.post(
                f"{self.config.satellite_url}/python",
                json={"code": code},
                timeout=30
            )

            if r.status_code == 200:
                return True
            return False

        except Exception as e:
            self.sync_errors.append({
                'time': time.time(),
                'file': str(filepath),
                'error': str(e)
            })
            return False

    def sync_file(self, filepath: Path) -> bool:
        """Sync a single file to satellite"""
        str_path = str(filepath)
        current_hash = self._hash_file(filepath)
        current_mtime = filepath.stat().st_mtime if filepath.exists() else 0

        with self._lock:
            state = self.sync_states.get(str_path)

            # Check if needs sync
            if state and state.local_hash == current_hash:
                return True  # Already synced

            # Upload file
            success = self._upload_file(filepath)

            if success:
                # Update state
                self.sync_states[str_path] = SyncState(
                    path=str_path,
                    local_hash=current_hash,
                    remote_hash=current_hash,
                    last_synced=time.time(),
                    last_modified=current_mtime,
                    sync_status="synced"
                )
                self.files_synced += 1
                self.bytes_synced += filepath.stat().st_size
                return True
            else:
                self.sync_states[str_path] = SyncState(
                    path=str_path,
                    local_hash=current_hash,
                    last_modified=current_mtime,
                    sync_status="error"
                )
                return False

    def sync_all(self) -> Dict:
        """Sync all files"""
        if not self._check_satellite_health():
            return {"success": False, "error": "Satellite unreachable"}

        files = self._get_files_to_sync()
        synced = 0
        failed = 0
        skipped = 0

        for filepath in files:
            str_path = str(filepath)
            current_hash = self._hash_file(filepath)

            # Check if already synced
            state = self.sync_states.get(str_path)
            if state and state.local_hash == current_hash and state.sync_status == "synced":
                skipped += 1
                continue

            if self.sync_file(filepath):
                synced += 1
            else:
                failed += 1

        self.last_sync_time = time.time()
        self._save_state()

        return {
            "success": True,
            "synced": synced,
            "failed": failed,
            "skipped": skipped,
            "total_files": len(files)
        }

    def start(self, interval: int = None):
        """Start background sync"""
        if self.running:
            return

        self.running = True
        if interval:
            self.config.interval_seconds = interval

        self._thread = threading.Thread(
            target=self._sync_loop,
            daemon=True,
            name="MemorySyncAgent"
        )
        self._thread.start()
        print(f"[MemorySync] Started with {self.config.interval_seconds}s interval")

    def stop(self):
        """Stop background sync"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _sync_loop(self):
        """Background sync loop"""
        while self.running:
            try:
                result = self.sync_all()
                if result.get('synced', 0) > 0:
                    print(f"[MemorySync] Synced {result['synced']} files")
            except Exception as e:
                print(f"[MemorySync] Error: {e}")

            time.sleep(self.config.interval_seconds)

    def get_status(self) -> Dict:
        """Get sync status"""
        with self._lock:
            pending = sum(1 for s in self.sync_states.values() if s.sync_status == "pending")
            synced = sum(1 for s in self.sync_states.values() if s.sync_status == "synced")
            errors = sum(1 for s in self.sync_states.values() if s.sync_status == "error")

            return {
                "running": self.running,
                "total_files_tracked": len(self.sync_states),
                "synced": synced,
                "pending": pending,
                "errors": errors,
                "files_synced_total": self.files_synced,
                "bytes_synced_total": self.bytes_synced,
                "last_sync": self.last_sync_time,
                "recent_errors": self.sync_errors[-5:]
            }


# ═══ Convenience Functions ═══

def create_memory_sync(
    local_base: str = None,
    satellite_url: str = None,
    auto_start: bool = True
) -> MemorySyncAgent:
    """Create and optionally start a memory sync agent"""
    config = SyncConfig()
    if local_base:
        config.local_base = local_base
    if satellite_url:
        config.satellite_url = satellite_url

    agent = MemorySyncAgent(config)

    if auto_start:
        agent.start()

    return agent


# ═══ Flask Routes ═══

def add_sync_routes(app, sync_agent: MemorySyncAgent = None):
    """Add sync routes to Flask app"""
    from flask import jsonify

    @app.route('/sync/status')
    def sync_status():
        if sync_agent:
            return jsonify(sync_agent.get_status())
        return jsonify({"error": "Sync not configured"})

    @app.route('/sync/now', methods=['POST'])
    def sync_now():
        if sync_agent:
            result = sync_agent.sync_all()
            return jsonify(result)
        return jsonify({"error": "Sync not configured"})


# Export
__all__ = [
    'MemorySyncAgent',
    'SyncConfig',
    'SyncState',
    'create_memory_sync',
    'add_sync_routes'
]
