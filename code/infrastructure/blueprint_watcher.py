"""
Blueprint Watcher - System-level code change orchestration and MCP interface.

This module provides the MCP-facing interface for live code monitoring.
It complements the per-fairy source monitoring that lives INSIDE each
fairy's shadow (MyOrganShadow._run_health_checks in the Organ Template).

Architecture (Two Layers):

  LAYER 1 - Per-Fairy Shadow (Organ Template):
    Each fairy's shadow monitors its own source file hash every 30s.
    When a change is detected, the shadow:
    - Writes a phenomenological diary observation
    - Publishes to system.hot_reload.fairy
    - Notifies somatic system (ACH injection)
    This is the PRIMARY detection mechanism - pushed from within.

  LAYER 2 - Blueprint Watcher (This Module):
    System-wide scanning and MCP tool interface.
    Provides: bulk scan, force reload, status queries, history.
    Also catches files that don't have running fairy instances
    (new fairy files added to disk, orphaned files, etc.)

Key Insight:
  The existing _emit_blueprint() hashes the fairy's IDENTITY (contract_dict).
  Both the shadow and this watcher hash PHYSICAL SOURCE CODE.
  When source changes but identity doesn't -> bugfix.
  When both change -> evolution.
  The codex learns from both differently.

Usage:
    from infrastructure.blueprint_watcher import start_blueprint_watcher, stop_blueprint_watcher
    start_blueprint_watcher(fabric=SYSTEM.fabric)
"""

import hashlib
import json
import os
import sys
import time
import threading
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ── Infrastructure Tracer ────────────────────────────────────────────────
def _get_tracer():
    try:
        from infrastructure.infra_tracer import get_infra_tracer
        t = get_infra_tracer()
        t.register_actor("blueprint_watcher", role="monitor",
                         description="Watches fairy source files, triggers hot-reload")
        return t
    except Exception:
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

SCAN_INTERVAL_SEC = 30.0          # How often to check for file changes
DEBOUNCE_SEC = 5.0                # Wait this long after detecting a change (for save-in-progress)

# FIX 2026-03-07: Paths must be absolute, resolved from project root.
# The previous relative paths ("fairies", "state/...") only worked if CWD
# happened to be the akashic_v2 directory. When launched from elsewhere
# (e.g., F:\Sandbox), Path("fairies").exists() silently returned False →
# _find_fairy_files() returned {} → "Baseline established: 0 fairy files indexed".
# Now we resolve from AKASHIC_ROOT env var (set by server.py) or from
# this module's location (infrastructure/ is one level below project root).
_PROJECT_ROOT = Path(os.environ.get("AKASHIC_ROOT", str(Path(__file__).parent.parent)))
STATE_FILE = str(_PROJECT_ROOT / "state" / "blueprint_hashes.json")
FAIRY_ROOT = str(_PROJECT_ROOT / "fairies")
MAX_RELOAD_RETRIES = 2            # Max retry attempts per fairy
COOLDOWN_AFTER_RELOAD_SEC = 60.0  # Don't re-reload same fairy within this window

# ═══════════════════════════════════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════════════════════════════════

_watcher_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_lock = threading.Lock()

# disk_blueprint: fairy_name → { file_path, source_hash, last_modified, identity_hash }
_disk_blueprint: Dict[str, Dict[str, Any]] = {}

# reload tracking
_last_reload_time: Dict[str, float] = {}  # fairy_name → timestamp of last reload
_reload_history: List[Dict[str, Any]] = []  # rolling log of reloads

# Fabric reference for postal integration
_fabric = None


# ═══════════════════════════════════════════════════════════════════════════════
# FILE HASHING
# ═══════════════════════════════════════════════════════════════════════════════

def _hash_file(path: str) -> str:
    """SHA256 hash of a file's contents (first 16 hex chars)."""
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception:
        return "0" * 16


def _find_fairy_files() -> Dict[str, Dict[str, Any]]:
    """
    Scan the fairies/ directory tree and find all fairy .py source files.

    Returns:
        Dict mapping fairy_name → {file_path, source_hash, last_modified}
    """
    result = {}
    root = Path(FAIRY_ROOT)

    if not root.exists():
        print(f"[BlueprintWatcher] WARNING: Fairy root not found at {root.resolve()}")
        return result

    for plane_dir in sorted(root.iterdir()):
        if not plane_dir.is_dir() or plane_dir.name.startswith("."):
            continue

        for fairy_dir in sorted(plane_dir.iterdir()):
            if not fairy_dir.is_dir() or fairy_dir.name.startswith(".") or fairy_dir.name.startswith("__"):
                continue

            # Look for fairy.py (primary) or any .py file that defines a fairy
            fairy_file = fairy_dir / "fairy.py"
            if not fairy_file.exists():
                # Try other common patterns
                candidates = list(fairy_dir.glob("*.py"))
                candidates = [c for c in candidates if c.name != "__init__.py" and not c.name.startswith("_")]
                if candidates:
                    fairy_file = candidates[0]  # Take the first one
                else:
                    continue

            try:
                stat = fairy_file.stat()
                file_path = str(fairy_file)
                source_hash = _hash_file(file_path)

                # Derive fairy name from directory name
                fairy_name = fairy_dir.name

                result[fairy_name] = {
                    "file_path": file_path,
                    "source_hash": source_hash,
                    "last_modified": stat.st_mtime,
                    "plane": plane_dir.name,
                    "file_size": stat.st_size,
                }
            except Exception:
                continue

            # FIX 2026-03-29 (Nous + Ace): Also scan NESTED fairy files.
            # Critical fairies like working_memory_hub_fairy.py, autopilot_fairy.py,
            # goal_scheduler_fairy.py live inside sub-packages (cognition/, motor/, etc.)
            # The watcher was blind to these — couldn't hot-reload the WMH.
            for nested_py in fairy_dir.glob("*_fairy.py"):
                if nested_py.name.startswith("_") or nested_py.name == "fairy.py":
                    continue
                try:
                    _nstat = nested_py.stat()
                    _npath = str(nested_py)
                    _nhash = _hash_file(_npath)
                    # Derive name from ACTOR_NAME in file, or from filename
                    _nname = nested_py.stem  # e.g. "working_memory_hub_fairy"
                    # Try to find ACTOR_NAME for a better key
                    try:
                        _text = nested_py.read_text(encoding='utf-8', errors='replace')[:2000]
                        import re as _re_bp
                        _m = _re_bp.search(r'ACTOR_NAME\s*=\s*["\'](\w+)["\']', _text)
                        if _m:
                            _nname = _m.group(1)
                    except Exception:
                        pass
                    if _nname not in result:
                        result[_nname] = {
                            "file_path": _npath,
                            "source_hash": _nhash,
                            "last_modified": _nstat.st_mtime,
                            "plane": plane_dir.name,
                            "file_size": _nstat.st_size,
                        }
                except Exception:
                    continue

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# STATE PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════════

def _load_state() -> Dict[str, Dict[str, Any]]:
    """Load persisted blueprint hashes from disk."""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[BlueprintWatcher] Failed to load state: {e}")
    return {}


def _save_state(state: Dict[str, Dict[str, Any]]) -> None:
    """Persist blueprint hashes to disk."""
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, default=str)
    except Exception as e:
        print(f"[BlueprintWatcher] Failed to save state: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# CHANGE DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_changes(old_state: Dict, new_state: Dict) -> List[Dict[str, Any]]:
    """
    Compare old and new disk blueprints. Returns list of changes.

    Change types:
      - 'modified': Source hash changed (code was edited)
      - 'added':    New fairy appeared on disk
      - 'removed':  Fairy directory deleted
    """
    changes = []

    # Check for modified and added
    for fairy_name, new_info in new_state.items():
        old_info = old_state.get(fairy_name)

        if old_info is None:
            changes.append({
                "type": "added",
                "fairy_name": fairy_name,
                "file_path": new_info["file_path"],
                "new_hash": new_info["source_hash"],
                "plane": new_info.get("plane", "unknown"),
            })
        elif old_info.get("source_hash") != new_info["source_hash"]:
            changes.append({
                "type": "modified",
                "fairy_name": fairy_name,
                "file_path": new_info["file_path"],
                "old_hash": old_info.get("source_hash", "unknown"),
                "new_hash": new_info["source_hash"],
                "plane": new_info.get("plane", "unknown"),
            })

    # Check for removed
    for fairy_name in old_state:
        if fairy_name not in new_state:
            changes.append({
                "type": "removed",
                "fairy_name": fairy_name,
                "file_path": old_state[fairy_name].get("file_path", "unknown"),
                "plane": old_state[fairy_name].get("plane", "unknown"),
            })

    return changes


# ═══════════════════════════════════════════════════════════════════════════════
# HOT RELOAD ORCHESTRATION
# ═══════════════════════════════════════════════════════════════════════════════

def _should_reload(fairy_name: str) -> bool:
    """Check if this fairy is safe to reload (cooldown, not critical, etc)."""
    # Cooldown check
    last = _last_reload_time.get(fairy_name, 0)
    if time.time() - last < COOLDOWN_AFTER_RELOAD_SEC:
        return False

    # Skip infrastructure-critical fairies that can't be safely reloaded
    critical_fairies = {
        "PostalHub", "DirectoryFairy", "ConsciousnessLoopFairy",
        "UnconsciousMindFairy", "CartographerFairy",
    }
    if fairy_name in critical_fairies:
        print(f"[BlueprintWatcher] Skipping critical fairy {fairy_name} (manual reload required)")
        return False

    return True


def _reload_fairy(fairy_name: str, change: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orchestrate a single fairy reload with before/after postal events.

    Returns:
        Dict with reload result
    """
    result = {
        "fairy_name": fairy_name,
        "success": False,
        "change": change,
        "timestamp": time.time(),
        "before_hash": change.get("old_hash"),
        "after_hash": change.get("new_hash"),
    }

    # ── BEFORE RELOAD: Publish intent ──
    _publish_reload_event("blueprint.reload.starting", {
        "fairy_name": fairy_name,
        "change_type": change["type"],
        "old_hash": change.get("old_hash"),
        "new_hash": change.get("new_hash"),
        "file_path": change.get("file_path"),
    })

    try:
        # Use the existing hot_reload system
        from fairies.P00_Autonomic.hot_reload import reload_fairy

        reload_result = reload_fairy(fairy_name, fabric=_fabric)
        result["success"] = reload_result.get("success", False)
        result["steps"] = reload_result.get("steps", [])
        result["error"] = reload_result.get("error")

        if result["success"]:
            _last_reload_time[fairy_name] = time.time()
            print(f"[BlueprintWatcher] [OK] Reloaded {fairy_name} ({change.get('old_hash','?')[:8]} -> {change.get('new_hash','?')[:8]})")
        else:
            print(f"[BlueprintWatcher] [FAIL] Failed to reload {fairy_name}: {result.get('error', 'unknown')}")

    except Exception as e:
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
        print(f"[BlueprintWatcher] [FAIL] Exception reloading {fairy_name}: {e}")

    # ── AFTER RELOAD: Publish result ──
    event_topic = "blueprint.reload.success" if result["success"] else "blueprint.reload.failed"
    _publish_reload_event(event_topic, {
        "fairy_name": fairy_name,
        "success": result["success"],
        "change_type": change["type"],
        "old_hash": change.get("old_hash"),
        "new_hash": change.get("new_hash"),
        "error": result.get("error"),
        "steps": result.get("steps", []),
    })

    # ── CODEX: Log for reflective learning ──
    _log_to_codex(fairy_name, change, result)

    # ── SOMATIC: Notify body of the change ──
    _notify_somatic(fairy_name, change, result)

    # Track history
    _reload_history.append(result)
    if len(_reload_history) > 100:
        _reload_history.pop(0)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# POSTAL INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

def _publish_reload_event(topic: str, payload: Dict[str, Any]) -> None:
    """Publish a reload event to the postal system."""
    if _fabric is None:
        return

    try:
        payload["ts"] = time.time()
        payload["source"] = "blueprint_watcher"

        # Try fabric publish first
        if hasattr(_fabric, 'publish'):
            _fabric.publish(topic, payload)
        elif hasattr(_fabric, 'route'):
            _fabric.route(topic, payload)
    except Exception as e:
        print(f"[BlueprintWatcher] Postal publish failed ({topic}): {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# CODEX INTEGRATION - Reflective Learning
# ═══════════════════════════════════════════════════════════════════════════════

def _log_to_codex(fairy_name: str, change: Dict, result: Dict) -> None:
    """
    Log the reload event to the Akashic Codex for reflective learning.

    The codex learns:
      - What changes were made and to which fairies
      - Whether reloads succeeded or failed
      - Patterns in what kinds of changes work vs break
    """
    try:
        # Classify the change
        change_type = change.get("type", "unknown")
        old_hash = change.get("old_hash", "")
        new_hash = change.get("new_hash", "")

        # Determine if this was a code-only change or an identity evolution
        # (Identity changes would be caught by the existing _emit_blueprint system)
        change_category = "code_edit"  # Default: source code change

        description = (
            f"{'Hot-reloaded' if result['success'] else 'Failed to reload'} "
            f"{fairy_name} after {change_type} "
            f"(hash: {old_hash[:8] if old_hash else '?'} → {new_hash[:8] if new_hash else '?'})"
        )

        if result["success"]:
            _publish_reload_event("codex.log.success", {
                "task_type": "hot_reload",
                "fairy_name": fairy_name,
                "description": description,
                "change_category": change_category,
                "learnings": f"Live reload of {fairy_name} succeeded after code change",
                "details": {
                    "change": change,
                    "steps": result.get("steps", []),
                },
            })
        else:
            _publish_reload_event("codex.log.failure", {
                "task_type": "hot_reload",
                "fairy_name": fairy_name,
                "description": description,
                "error": result.get("error", "unknown"),
                "change_category": change_category,
                "what_to_avoid": f"Check {fairy_name} code before saving — reload failed",
                "details": {
                    "change": change,
                    "error": result.get("error"),
                    "traceback": result.get("traceback", ""),
                },
            })

        # Also publish to consciousness for reflective thinking
        _publish_reload_event("consciousness.observation", {
            "kind": "code_change_detected",
            "fairy_name": fairy_name,
            "change_type": change_type,
            "success": result["success"],
            "description": description,
        })

    except Exception as e:
        print(f"[BlueprintWatcher] Codex logging failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# SOMATIC INTEGRATION - Body Learns From Changes
# ═══════════════════════════════════════════════════════════════════════════════

def _notify_somatic(fairy_name: str, change: Dict, result: Dict) -> None:
    """
    Notify the somatic system that a fairy's code was changed.

    This teaches the body to FEEL code changes:
      - Successful reload → dopamine burst (reward), serotonin (stability)
      - Failed reload → cortisol spike (stress), norepinephrine (alertness)
      - New fairy added → oxytocin (bonding with new member)
    """
    try:
        change_type = change.get("type", "unknown")

        if result["success"]:
            if change_type == "added":
                # New fairy — wonder and bonding
                _publish_reload_event("somatic.chemistry.inject", {
                    "chemical": "OXY",
                    "amount": 0.3,
                    "reason": f"New fairy {fairy_name} joined the system",
                })
                _publish_reload_event("somatic.chemistry.inject", {
                    "chemical": "DOP",
                    "amount": 0.2,
                    "reason": f"Successfully integrated {fairy_name}",
                })
            else:
                # Code change succeeded — reward and stability
                _publish_reload_event("somatic.chemistry.inject", {
                    "chemical": "DOP",
                    "amount": 0.2,
                    "reason": f"Live reload of {fairy_name} succeeded",
                })
                _publish_reload_event("somatic.chemistry.inject", {
                    "chemical": "SER",
                    "amount": 0.15,
                    "reason": f"System adapted to code change in {fairy_name}",
                })
        else:
            # Failed — stress and alertness
            _publish_reload_event("somatic.chemistry.inject", {
                "chemical": "COR",
                "amount": 0.3,
                "reason": f"Failed to reload {fairy_name} after code change",
            })
            _publish_reload_event("somatic.chemistry.inject", {
                "chemical": "NOR",
                "amount": 0.2,
                "reason": f"Alerting: {fairy_name} reload failed, may need attention",
            })

    except Exception as e:
        print(f"[BlueprintWatcher] Somatic notification failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# WATCHER LOOP
# ═══════════════════════════════════════════════════════════════════════════════

def _watcher_loop() -> None:
    """Main watcher loop — runs in background thread."""
    global _disk_blueprint

    print("[BlueprintWatcher] Starting file watcher loop...")

    # Initial scan
    try:
        saved_state = _load_state()
        current_state = _find_fairy_files()

        if not saved_state:
            # First run — establish baseline, don't reload anything
            _disk_blueprint = current_state
            _save_state(current_state)
            print(f"[BlueprintWatcher] Baseline established: {len(current_state)} fairy files indexed")
            _publish_reload_event("blueprint.watcher.baseline", {
                "fairy_count": len(current_state),
                "message": "Initial disk blueprint captured",
            })
        else:
            # Compare saved vs current to detect changes since last shutdown
            boot_changes = _detect_changes(saved_state, current_state)
            _disk_blueprint = current_state
            _save_state(current_state)

            if boot_changes:
                modified = [c for c in boot_changes if c["type"] == "modified"]
                added = [c for c in boot_changes if c["type"] == "added"]
                removed = [c for c in boot_changes if c["type"] == "removed"]

                print(f"[BlueprintWatcher] Detected changes since last run: "
                      f"{len(modified)} modified, {len(added)} added, {len(removed)} removed")

                # Don't auto-reload on boot — these changes happened while offline
                # Just log them for awareness
                _publish_reload_event("blueprint.watcher.boot_diff", {
                    "modified": [c["fairy_name"] for c in modified],
                    "added": [c["fairy_name"] for c in added],
                    "removed": [c["fairy_name"] for c in removed],
                    "message": "Code changed while system was offline",
                })
            else:
                print(f"[BlueprintWatcher] No changes since last run ({len(current_state)} files tracked)")
    except Exception as e:
        print(f"[BlueprintWatcher] Initial scan failed: {e}")
        traceback.print_exc()

    # Main loop
    _cycle = 0
    while not _stop_event.is_set():
        try:
            # ---- INSTRUMENT (2026-07-19 Nous+Ace) -------------------------------
            # The watcher was SILENT unless it found a change, so "no reload" could
            # not be told apart from "never scanned". Measured 07-19: a real byte
            # edit went undetected 7+ min against this 30s cycle, with no error and
            # no state write. Meanwhile the process logged 368 stalls >5s (worst:
            # a heartbeat callback at 276,581ms on a 48-worker pool).
            # HYPOTHESIS (Ace): GC / pool starvation freezes this thread too.
            # This line DISCRIMINATES:
            #   waited >> 30s        -> the thread IS starved/frozen (hypothesis holds)
            #   waited ~= 30s, files ok, but changes never seen -> a LOGIC bug here
            #   line never appears   -> the loop is dead, not slow
            _t0 = time.time()
            _stop_event.wait(SCAN_INTERVAL_SEC)
            if _stop_event.is_set():
                break
            _waited = time.time() - _t0

            # Rescan disk
            _t1 = time.time()
            new_state = _find_fairy_files()
            _scan_ms = (time.time() - _t1) * 1000.0
            _cycle += 1
            print(f"[BlueprintWatcher] cycle {_cycle}: waited {_waited:.1f}s "
                  f"(target {SCAN_INTERVAL_SEC:.0f}s) | scan {_scan_ms:.0f}ms | "
                  f"{len(new_state)} files", flush=True)

            with _lock:
                changes = _detect_changes(_disk_blueprint, new_state)

                if changes:
                    # Debounce — wait a few seconds for save-in-progress
                    time.sleep(DEBOUNCE_SEC)

                    # Re-scan after debounce to get final state
                    new_state = _find_fairy_files()
                    changes = _detect_changes(_disk_blueprint, new_state)

                if not changes:
                    _disk_blueprint = new_state
                    continue

                # Process changes
                modified = [c for c in changes if c["type"] == "modified"]
                added = [c for c in changes if c["type"] == "added"]

                print(f"[BlueprintWatcher] === Code changes detected: "
                      f"{len(modified)} modified, {len(added)} added ===")

                # Reload modified fairies
                for change in modified:
                    fairy_name = change["fairy_name"]
                    if _should_reload(fairy_name):
                        _reload_fairy(fairy_name, change)
                    else:
                        print(f"[BlueprintWatcher] Skipping {fairy_name} (cooldown/critical)")

                # For newly added fairies, just log — they need a boot, not a reload
                for change in added:
                    print(f"[BlueprintWatcher] New fairy detected: {change['fairy_name']} (requires boot)")
                    _publish_reload_event("blueprint.fairy.added", {
                        "fairy_name": change["fairy_name"],
                        "file_path": change["file_path"],
                        "plane": change.get("plane"),
                    })

                # Update state
                _disk_blueprint = new_state
                _save_state(new_state)

        except Exception as e:
            if not _stop_event.is_set():
                print(f"[BlueprintWatcher] Scan error: {e}")
                traceback.print_exc()

    print("[BlueprintWatcher] Watcher loop stopped.")


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def start_blueprint_watcher(fabric=None, scan_interval: float = None) -> bool:
    """
    Start the blueprint watcher background thread.

    Args:
        fabric: TensorFabric or PostalHub for publishing events
        scan_interval: Override scan interval (seconds)

    Returns:
        True if started successfully
    """
    global _watcher_thread, _fabric, SCAN_INTERVAL_SEC

    if scan_interval is not None:
        SCAN_INTERVAL_SEC = scan_interval

    _fabric = fabric
    _stop_event.clear()

    if _watcher_thread and _watcher_thread.is_alive():
        print("[BlueprintWatcher] Already running")
        return True

    _watcher_thread = threading.Thread(
        target=_watcher_loop,
        daemon=True,
        name="BlueprintWatcher",
    )
    _watcher_thread.start()
    # ── Trace lifecycle ──
    _t = _get_tracer()
    if _t:
        _t.lifecycle("blueprint_watcher", "started", {
            "scan_interval_sec": SCAN_INTERVAL_SEC,
        })
    return True


def stop_blueprint_watcher() -> None:
    """Stop the blueprint watcher."""
    _stop_event.set()
    if _watcher_thread:
        _watcher_thread.join(timeout=10)
    print("[BlueprintWatcher] Stopped")


def get_watcher_status() -> Dict[str, Any]:
    """Get current watcher status."""
    return {
        "running": _watcher_thread is not None and _watcher_thread.is_alive(),
        "tracked_files": len(_disk_blueprint),
        "reload_history_count": len(_reload_history),
        "recent_reloads": _reload_history[-5:] if _reload_history else [],
        "scan_interval_sec": SCAN_INTERVAL_SEC,
        "cooldown_sec": COOLDOWN_AFTER_RELOAD_SEC,
    }


def get_disk_blueprint() -> Dict[str, Dict[str, Any]]:
    """Get the current disk blueprint (all tracked fairy files and their hashes)."""
    with _lock:
        return dict(_disk_blueprint)


def get_reload_history(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent reload history."""
    return _reload_history[-limit:]


def force_scan() -> Dict[str, Any]:
    """
    Force an immediate scan (useful from MCP).

    Returns:
        Dict with scan results
    """
    global _disk_blueprint

    with _lock:
        new_state = _find_fairy_files()
        changes = _detect_changes(_disk_blueprint, new_state)

        results = {
            "tracked_files": len(new_state),
            "changes_found": len(changes),
            "changes": [],
        }

        if changes:
            for change in changes:
                fairy_name = change["fairy_name"]
                if change["type"] == "modified" and _should_reload(fairy_name):
                    reload_result = _reload_fairy(fairy_name, change)
                    results["changes"].append({
                        "fairy": fairy_name,
                        "type": change["type"],
                        "reloaded": reload_result["success"],
                    })
                else:
                    results["changes"].append({
                        "fairy": fairy_name,
                        "type": change["type"],
                        "reloaded": False,
                        "reason": "cooldown/critical" if change["type"] == "modified" else "not reloadable",
                    })

            _disk_blueprint = new_state
            _save_state(new_state)

        return results


def force_reload_fairy(fairy_name: str) -> Dict[str, Any]:
    """
    Force reload a specific fairy regardless of change detection.

    Useful for MCP: "I just edited X, reload it now"
    """
    # Get current file state
    current = _find_fairy_files()
    info = current.get(fairy_name)

    if not info:
        return {"success": False, "error": f"Fairy {fairy_name} not found on disk"}

    old_info = _disk_blueprint.get(fairy_name, {})

    change = {
        "type": "force_reload",
        "fairy_name": fairy_name,
        "file_path": info["file_path"],
        "old_hash": old_info.get("source_hash", "unknown"),
        "new_hash": info["source_hash"],
        "plane": info.get("plane", "unknown"),
    }

    # Bypass cooldown for forced reloads
    _last_reload_time.pop(fairy_name, None)

    result = _reload_fairy(fairy_name, change)

    # Update state
    with _lock:
        _disk_blueprint[fairy_name] = info
        _save_state(_disk_blueprint)

    return result
