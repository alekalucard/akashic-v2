"""
Boot Observer - Comprehensive boot process logger for Claude analysis.

This module provides INLINE boot observation (not subprocess-based).
It hooks into the actual boot process and logs everything to structured JSON.

Features:
- Captures every fairy instantiation, start, and registration
- Tracks postal system registrations
- Monitors thread creation
- Logs import times
- Records errors with full tracebacks
- Generates both JSON-lines (for machine parsing) and summary (for humans)

Usage:
    # At the VERY TOP of server.py (before other imports):
    from fairies.P00_Autonomic.nervous_system.boot_observer import BootObserver
    boot_observer = BootObserver.get_instance()
    boot_observer.start_observation()
    
    # At the end of boot:
    boot_observer.finish_observation()
    boot_observer.write_summary()

The observer writes to:
    - boot_observation.jsonl  (JSON lines - one event per line)
    - boot_observation_summary.json  (complete summary for Claude)
    - boot_observation_report.txt  (human readable)

Version: 1.0.0
Author: Claude + Ace
Date: 2026-01-03
"""

from __future__ import annotations

import os
import sys
import time
import json
import threading
import traceback
import functools
import importlib
import atexit
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import logging

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Where to write logs (relative to project root)
LOG_DIR = Path(__file__).parent.parent.parent / "boot_logs"
JSONL_FILE = "boot_observation.jsonl"
SUMMARY_FILE = "boot_observation_summary.json"
REPORT_FILE = "boot_observation_report.txt"

# ═══════════════════════════════════════════════════════════════════════════════
# EVENT DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BootEvent:
    """A single boot event."""
    timestamp: float
    event_type: str  # fairy_init, fairy_start, fairy_error, postal_register, import, thread, etc
    source: str      # What generated this event
    plane: str = ""
    actor_name: str = ""
    duration_ms: float = 0.0
    success: bool = True
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    thread_id: int = 0
    thread_name: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.timestamp,
            "t": self.event_type,
            "src": self.source,
            "plane": self.plane,
            "actor": self.actor_name,
            "dur_ms": round(self.duration_ms, 2),
            "ok": self.success,
            "msg": self.message,
            "details": self.details,
            "tid": self.thread_id,
            "tname": self.thread_name,
        }


@dataclass
class FairyRecord:
    """Complete record for a single fairy's boot process."""
    class_name: str
    actor_name: str = ""
    plane: str = ""
    file_path: str = ""
    
    # Timing
    import_start: float = 0.0
    import_end: float = 0.0
    init_start: float = 0.0
    init_end: float = 0.0
    on_boot_start: float = 0.0
    on_boot_end: float = 0.0
    postal_register_time: float = 0.0
    
    # Computed
    import_ms: float = 0.0
    init_ms: float = 0.0
    on_boot_ms: float = 0.0
    total_ms: float = 0.0
    
    # Status
    status: str = "unknown"  # pending, importing, initializing, booting, registered, failed, timeout
    error: str = ""
    error_traceback: str = ""
    
    # Subscriptions and channels
    subscribed_channels: List[str] = field(default_factory=list)
    registered_intents: List[str] = field(default_factory=list)
    
    def compute_times(self):
        """Calculate durations from timestamps."""
        if self.import_end and self.import_start:
            self.import_ms = (self.import_end - self.import_start) * 1000
        if self.init_end and self.init_start:
            self.init_ms = (self.init_end - self.init_start) * 1000
        if self.on_boot_end and self.on_boot_start:
            self.on_boot_ms = (self.on_boot_end - self.on_boot_start) * 1000
        self.total_ms = self.import_ms + self.init_ms + self.on_boot_ms


@dataclass
class PlaneRecord:
    """Record for a plane's boot process."""
    plane: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    
    fairy_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    timeout_count: int = 0
    
    fairies: List[str] = field(default_factory=list)  # class names


@dataclass
class BootSummary:
    """Complete boot observation summary."""
    observation_id: str = ""
    host: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    duration_sec: float = 0.0
    
    # Counts
    total_fairies_expected: int = 0
    total_fairies_found: int = 0
    total_fairies_booted: int = 0
    total_fairies_registered: int = 0
    total_fairies_failed: int = 0
    total_fairies_timeout: int = 0
    
    # Planes
    planes: Dict[str, PlaneRecord] = field(default_factory=dict)
    
    # Fairies by status
    fairies_by_status: Dict[str, List[str]] = field(default_factory=dict)
    
    # Performance
    slowest_fairies: List[Dict[str, Any]] = field(default_factory=list)  # top 10
    fastest_fairies: List[Dict[str, Any]] = field(default_factory=list)  # top 10
    
    # Issues
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    blocked_tunnels: List[str] = field(default_factory=list)
    
    # Postal system
    postal_registrations: int = 0
    postal_channels_active: List[str] = field(default_factory=list)
    
    # Threads
    threads_created: int = 0
    threads_at_end: int = 0
    
    # System
    python_version: str = ""
    platform: str = ""
    memory_mb_start: float = 0.0
    memory_mb_end: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# BOOT OBSERVER SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

class BootObserver:
    """
    Singleton observer that hooks into the boot process.
    
    Call get_instance() to get the singleton.
    Call start_observation() at boot start.
    Call finish_observation() when boot completes.
    """
    
    _instance: Optional['BootObserver'] = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls) -> 'BootObserver':
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        if BootObserver._instance is not None:
            raise RuntimeError("Use BootObserver.get_instance() instead")
        
        self.observation_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.start_time = 0.0
        self.end_time = 0.0
        self.observing = False
        
        # Event log
        self.events: List[BootEvent] = []
        self._events_lock = threading.Lock()
        
        # Fairy tracking
        self.fairies: Dict[str, FairyRecord] = {}
        self._fairies_lock = threading.Lock()
        
        # Plane tracking
        self.planes: Dict[str, PlaneRecord] = {}
        
        # Postal tracking
        self.postal_registrations: Dict[str, float] = {}  # actor_name -> timestamp
        self.active_channels: Set[str] = set()
        
        # Thread tracking
        self.threads_at_start: Set[int] = set()
        self.threads_created: List[Dict[str, Any]] = []
        
        # File handles
        self._jsonl_file: Optional[Any] = None
        self._log_dir: Optional[Path] = None
        
        # Original functions (for unhooking)
        self._original_funcs: Dict[str, Callable] = {}
        
        # Import tracking
        self._import_times: Dict[str, float] = {}
        
    def start_observation(self):
        """Begin observing the boot process."""
        if self.observing:
            return
            
        self.observing = True
        self.start_time = time.time()
        self.threads_at_start = {t.ident for t in threading.enumerate()}
        
        # Ensure log directory exists
        self._log_dir = LOG_DIR
        self._log_dir.mkdir(parents=True, exist_ok=True)
        
        # Open JSONL file for streaming writes
        jsonl_path = self._log_dir / f"{self.observation_id}_{JSONL_FILE}"
        self._jsonl_file = open(jsonl_path, 'w', encoding='utf-8')
        
        # Log start event
        self._log_event(BootEvent(
            timestamp=self.start_time,
            event_type="boot_start",
            source="BootObserver",
            message=f"Boot observation started: {self.observation_id}",
            details={
                "python_version": sys.version,
                "platform": sys.platform,
                "cwd": os.getcwd(),
            }
        ))
        
        # Install hooks
        self._install_hooks()
        
        # Register cleanup on exit
        atexit.register(self._emergency_flush)
        
        print(f"[BootObserver] [START] Observation started: {self.observation_id}")
        
    def _install_hooks(self):
        """Install hooks into the system to capture boot events."""
        # Hook into postal system if available
        try:
            self._hook_postal_system()
        except Exception as e:
            self._log_event(BootEvent(
                timestamp=time.time(),
                event_type="hook_error",
                source="BootObserver",
                success=False,
                message=f"Failed to hook postal system: {e}"
            ))
        
        # Hook into thread creation
        try:
            self._hook_threading()
        except Exception as e:
            self._log_event(BootEvent(
                timestamp=time.time(),
                event_type="hook_error", 
                source="BootObserver",
                success=False,
                message=f"Failed to hook threading: {e}"
            ))
    
    def _hook_postal_system(self):
        """Hook into the postal system to capture registrations."""
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import SharedPostalHub
            
            # Wrap the register method
            original_register = SharedPostalHub.register
            observer = self
            
            @functools.wraps(original_register)
            def wrapped_register(self_hub, actor_name: str, *args, **kwargs):
                result = original_register(self_hub, actor_name, *args, **kwargs)
                observer.on_postal_register(actor_name)
                return result
            
            SharedPostalHub.register = wrapped_register
            self._original_funcs['postal_register'] = original_register
            
        except ImportError:
            pass  # Postal system not yet available
            
    def _hook_threading(self):
        """Hook thread creation to track new threads."""
        original_start = threading.Thread.start
        observer = self
        
        @functools.wraps(original_start)
        def wrapped_start(self_thread):
            result = original_start(self_thread)
            observer.on_thread_start(self_thread)
            return result
        
        threading.Thread.start = wrapped_start
        self._original_funcs['thread_start'] = original_start
        
    def _log_event(self, event: BootEvent):
        """Log an event to both memory and file."""
        # Fill in thread info
        event.thread_id = threading.current_thread().ident or 0
        event.thread_name = threading.current_thread().name
        
        with self._events_lock:
            self.events.append(event)
            
            # Write to JSONL file immediately
            if self._jsonl_file:
                try:
                    self._jsonl_file.write(json.dumps(event.to_dict()) + "\n")
                    self._jsonl_file.flush()
                except Exception:
                    pass  # Don't let logging errors break boot
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC API - Call these from boot code
    # ═══════════════════════════════════════════════════════════════════════════
    
    def on_plane_enter(self, plane: str):
        """Called when entering a plane for boot."""
        now = time.time()
        self.planes[plane] = PlaneRecord(plane=plane, start_time=now)
        self._log_event(BootEvent(
            timestamp=now,
            event_type="plane_enter",
            source="boot_wave",
            plane=plane,
            message=f"Entering plane {plane}"
        ))
        
    def on_plane_exit(self, plane: str, fairy_count: int = 0):
        """Called when exiting a plane after boot."""
        now = time.time()
        if plane in self.planes:
            self.planes[plane].end_time = now
            self.planes[plane].duration_ms = (now - self.planes[plane].start_time) * 1000
            self.planes[plane].fairy_count = fairy_count
        self._log_event(BootEvent(
            timestamp=now,
            event_type="plane_exit",
            source="boot_wave",
            plane=plane,
            message=f"Exiting plane {plane} with {fairy_count} fairies",
            details={"fairy_count": fairy_count}
        ))
        
    def on_fairy_import_start(self, class_name: str, file_path: str = ""):
        """Called when starting to import a fairy module."""
        now = time.time()
        with self._fairies_lock:
            if class_name not in self.fairies:
                self.fairies[class_name] = FairyRecord(class_name=class_name)
            self.fairies[class_name].import_start = now
            self.fairies[class_name].file_path = file_path
            self.fairies[class_name].status = "importing"
        self._log_event(BootEvent(
            timestamp=now,
            event_type="fairy_import_start",
            source=class_name,
            message=f"Importing {class_name}",
            details={"file_path": file_path}
        ))
        
    def on_fairy_import_end(self, class_name: str, success: bool = True, error: str = ""):
        """Called when fairy module import completes."""
        now = time.time()
        with self._fairies_lock:
            if class_name in self.fairies:
                self.fairies[class_name].import_end = now
                if not success:
                    self.fairies[class_name].status = "failed"
                    self.fairies[class_name].error = error
        self._log_event(BootEvent(
            timestamp=now,
            event_type="fairy_import_end",
            source=class_name,
            success=success,
            message=f"Imported {class_name}" if success else f"Import failed: {error}"
        ))
        
    def on_fairy_init_start(self, class_name: str, actor_name: str = "", plane: str = ""):
        """Called when fairy __init__ starts."""
        now = time.time()
        with self._fairies_lock:
            if class_name not in self.fairies:
                self.fairies[class_name] = FairyRecord(class_name=class_name)
            self.fairies[class_name].init_start = now
            self.fairies[class_name].actor_name = actor_name
            self.fairies[class_name].plane = plane
            self.fairies[class_name].status = "initializing"
        self._log_event(BootEvent(
            timestamp=now,
            event_type="fairy_init_start",
            source=class_name,
            actor_name=actor_name,
            plane=plane,
            message=f"Initializing {class_name} as {actor_name}"
        ))
        
    def on_fairy_init_end(self, class_name: str, success: bool = True, error: str = "", tb: str = ""):
        """Called when fairy __init__ completes."""
        now = time.time()
        with self._fairies_lock:
            if class_name in self.fairies:
                self.fairies[class_name].init_end = now
                if success:
                    self.fairies[class_name].status = "initialized"
                else:
                    self.fairies[class_name].status = "failed"
                    self.fairies[class_name].error = error
                    self.fairies[class_name].error_traceback = tb
        self._log_event(BootEvent(
            timestamp=now,
            event_type="fairy_init_end",
            source=class_name,
            success=success,
            message=f"Initialized {class_name}" if success else f"Init failed: {error}",
            details={"traceback": tb} if tb else {}
        ))
        
    def on_fairy_boot_start(self, class_name: str):
        """Called when fairy on_boot starts."""
        now = time.time()
        with self._fairies_lock:
            if class_name in self.fairies:
                self.fairies[class_name].on_boot_start = now
                self.fairies[class_name].status = "booting"
        self._log_event(BootEvent(
            timestamp=now,
            event_type="fairy_boot_start",
            source=class_name,
            message=f"on_boot starting for {class_name}"
        ))
        
    def on_fairy_boot_end(self, class_name: str, success: bool = True, error: str = "", tb: str = ""):
        """Called when fairy on_boot completes."""
        now = time.time()
        with self._fairies_lock:
            if class_name in self.fairies:
                self.fairies[class_name].on_boot_end = now
                if success:
                    self.fairies[class_name].status = "booted"
                else:
                    self.fairies[class_name].status = "failed"
                    self.fairies[class_name].error = error
                    self.fairies[class_name].error_traceback = tb
                self.fairies[class_name].compute_times()
        self._log_event(BootEvent(
            timestamp=now,
            event_type="fairy_boot_end",
            source=class_name,
            success=success,
            message=f"on_boot complete for {class_name}" if success else f"on_boot failed: {error}"
        ))
        
    def on_fairy_timeout(self, class_name: str, timeout_sec: float):
        """Called when a fairy times out during boot."""
        now = time.time()
        with self._fairies_lock:
            if class_name in self.fairies:
                self.fairies[class_name].status = "timeout"
                self.fairies[class_name].error = f"Timeout after {timeout_sec}s"
        self._log_event(BootEvent(
            timestamp=now,
            event_type="fairy_timeout",
            source=class_name,
            success=False,
            message=f"TIMEOUT: {class_name} after {timeout_sec}s",
            details={"timeout_sec": timeout_sec}
        ))
        
    def on_postal_register(self, actor_name: str):
        """Called when a fairy registers with the postal system."""
        now = time.time()
        self.postal_registrations[actor_name] = now
        
        # Update fairy record if we can find it
        with self._fairies_lock:
            for fairy in self.fairies.values():
                if fairy.actor_name == actor_name:
                    fairy.postal_register_time = now
                    fairy.status = "registered"
                    break
                    
        self._log_event(BootEvent(
            timestamp=now,
            event_type="postal_register",
            source="postal_system",
            actor_name=actor_name,
            message=f"Registered: {actor_name}"
        ))
        
    def on_channel_subscribe(self, actor_name: str, channel: str):
        """Called when a fairy subscribes to a postal channel."""
        now = time.time()
        self.active_channels.add(channel)
        
        with self._fairies_lock:
            for fairy in self.fairies.values():
                if fairy.actor_name == actor_name:
                    fairy.subscribed_channels.append(channel)
                    break
                    
        self._log_event(BootEvent(
            timestamp=now,
            event_type="channel_subscribe",
            source=actor_name,
            message=f"{actor_name} subscribed to {channel}",
            details={"channel": channel}
        ))
        
    def on_thread_start(self, thread: threading.Thread):
        """Called when a new thread starts."""
        if not self.observing:
            return
            
        now = time.time()
        thread_info = {
            "name": thread.name,
            "ident": thread.ident,
            "daemon": thread.daemon,
            "started_at": now,
        }
        self.threads_created.append(thread_info)
        
        self._log_event(BootEvent(
            timestamp=now,
            event_type="thread_start",
            source="threading",
            message=f"Thread started: {thread.name}",
            details=thread_info
        ))
        
    def on_error(self, source: str, error: str, tb: str = ""):
        """Log a general error during boot."""
        self._log_event(BootEvent(
            timestamp=time.time(),
            event_type="error",
            source=source,
            success=False,
            message=error,
            details={"traceback": tb} if tb else {}
        ))
        
    def on_warning(self, source: str, message: str):
        """Log a warning during boot."""
        self._log_event(BootEvent(
            timestamp=time.time(),
            event_type="warning",
            source=source,
            message=message
        ))
        
    def on_blocked_tunnel(self, description: str):
        """Log a blocked tunnel / dependency issue."""
        self._log_event(BootEvent(
            timestamp=time.time(),
            event_type="blocked_tunnel",
            source="boot_wave",
            success=False,
            message=f"BLOCKED: {description}"
        ))
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FINISH AND REPORTING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def finish_observation(self):
        """Complete the observation and finalize data."""
        if not self.observing:
            return
            
        self.end_time = time.time()
        self.observing = False
        
        # Log finish event
        self._log_event(BootEvent(
            timestamp=self.end_time,
            event_type="boot_finish",
            source="BootObserver",
            message=f"Boot observation complete: {self.end_time - self.start_time:.2f}s"
        ))
        
        # Close JSONL file
        if self._jsonl_file:
            self._jsonl_file.close()
            self._jsonl_file = None
            
        # Compute all fairy times
        with self._fairies_lock:
            for fairy in self.fairies.values():
                fairy.compute_times()
                
        # Restore original functions
        self._restore_hooks()
        
        print(f"[BootObserver] [OK] Observation complete: {self.end_time - self.start_time:.2f}s")
        
    def _restore_hooks(self):
        """Restore original functions."""
        if 'thread_start' in self._original_funcs:
            threading.Thread.start = self._original_funcs['thread_start']
            
        # Note: We don't restore postal hook to keep tracking registrations
        
    def _emergency_flush(self):
        """Emergency flush on exit."""
        if self._jsonl_file:
            try:
                self._jsonl_file.flush()
                self._jsonl_file.close()
            except Exception:
                pass
                
    def generate_summary(self) -> BootSummary:
        """Generate a complete boot summary."""
        import platform
        
        summary = BootSummary(
            observation_id=self.observation_id,
            host=platform.node(),
            start_time=self.start_time,
            end_time=self.end_time,
            duration_sec=self.end_time - self.start_time if self.end_time else 0,
            python_version=sys.version.split()[0],
            platform=sys.platform,
        )
        
        # Fairy stats
        with self._fairies_lock:
            summary.total_fairies_found = len(self.fairies)
            
            status_counts = defaultdict(list)
            fairy_times = []
            
            for name, fairy in self.fairies.items():
                status_counts[fairy.status].append(name)
                if fairy.total_ms > 0:
                    fairy_times.append({
                        "name": name,
                        "actor": fairy.actor_name,
                        "plane": fairy.plane,
                        "total_ms": fairy.total_ms,
                        "init_ms": fairy.init_ms,
                        "on_boot_ms": fairy.on_boot_ms,
                        "status": fairy.status,
                    })
                    
            summary.fairies_by_status = dict(status_counts)
            summary.total_fairies_booted = len(status_counts.get("booted", []))
            summary.total_fairies_registered = len(status_counts.get("registered", []))
            summary.total_fairies_failed = len(status_counts.get("failed", []))
            summary.total_fairies_timeout = len(status_counts.get("timeout", []))
            
            # Sort by time
            fairy_times.sort(key=lambda x: x["total_ms"], reverse=True)
            summary.slowest_fairies = fairy_times[:10]
            summary.fastest_fairies = fairy_times[-10:][::-1] if len(fairy_times) > 10 else []
            
        # Plane stats
        for plane_name, plane in self.planes.items():
            summary.planes[plane_name] = plane
            
        # Postal stats
        summary.postal_registrations = len(self.postal_registrations)
        summary.postal_channels_active = list(self.active_channels)
        
        # Thread stats
        summary.threads_created = len(self.threads_created)
        summary.threads_at_end = len(threading.enumerate())
        
        # Collect errors
        with self._events_lock:
            for event in self.events:
                if event.event_type in ("error", "fairy_timeout", "blocked_tunnel"):
                    summary.errors.append({
                        "type": event.event_type,
                        "source": event.source,
                        "message": event.message,
                        "timestamp": event.timestamp,
                    })
                elif event.event_type == "warning":
                    summary.warnings.append(event.message)
                    
        return summary
        
    def write_summary(self):
        """Write summary files."""
        if not self._log_dir:
            self._log_dir = LOG_DIR
            self._log_dir.mkdir(parents=True, exist_ok=True)
            
        summary = self.generate_summary()
        
        # Write JSON summary
        summary_path = self._log_dir / f"{self.observation_id}_{SUMMARY_FILE}"
        with open(summary_path, 'w', encoding='utf-8') as f:
            # Convert dataclasses to dicts
            summary_dict = asdict(summary)
            # Convert plane records
            summary_dict['planes'] = {k: asdict(v) for k, v in summary.planes.items()}
            json.dump(summary_dict, f, indent=2, default=str)
            
        # Write human-readable report
        report_path = self._log_dir / f"{self.observation_id}_{REPORT_FILE}"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(self._generate_text_report(summary))
            
        print(f"[BootObserver]  Summary written to: {summary_path}")
        print(f"[BootObserver]  Report written to: {report_path}")
        
        return summary_path, report_path
        
    def _generate_text_report(self, summary: BootSummary) -> str:
        """Generate a human-readable text report."""
        lines = []
        lines.append("=" * 80)
        lines.append(f"BOOT OBSERVATION REPORT: {summary.observation_id}")
        lines.append("=" * 80)
        lines.append("")
        
        # Overview
        lines.append("OVERVIEW")
        lines.append("-" * 40)
        lines.append(f"  Host:          {summary.host}")
        lines.append(f"  Duration:      {summary.duration_sec:.2f} seconds")
        lines.append(f"  Python:        {summary.python_version}")
        lines.append(f"  Platform:      {summary.platform}")
        lines.append("")
        
        # Fairy counts
        lines.append("FAIRY STATISTICS")
        lines.append("-" * 40)
        lines.append(f"  Found:         {summary.total_fairies_found}")
        lines.append(f"  Booted:        {summary.total_fairies_booted}")
        lines.append(f"  Registered:    {summary.total_fairies_registered}")
        lines.append(f"  Failed:        {summary.total_fairies_failed}")
        lines.append(f"  Timeout:       {summary.total_fairies_timeout}")
        lines.append("")
        
        # By status
        if summary.fairies_by_status:
            lines.append("FAIRIES BY STATUS")
            lines.append("-" * 40)
            for status, fairies in sorted(summary.fairies_by_status.items()):
                lines.append(f"  {status.upper()} ({len(fairies)}):")
                for name in fairies[:10]:  # Limit to 10 per status
                    lines.append(f"    - {name}")
                if len(fairies) > 10:
                    lines.append(f"    ... and {len(fairies) - 10} more")
            lines.append("")
            
        # Slowest fairies
        if summary.slowest_fairies:
            lines.append("SLOWEST FAIRIES (potential bottlenecks)")
            lines.append("-" * 40)
            for fairy in summary.slowest_fairies[:10]:
                lines.append(f"  {fairy['name']:40} {fairy['total_ms']:8.1f}ms [{fairy['status']}]")
            lines.append("")
            
        # Planes
        if summary.planes:
            lines.append("PLANE BOOT TIMES")
            lines.append("-" * 40)
            for plane_name in sorted(summary.planes.keys()):
                plane = summary.planes[plane_name]
                lines.append(f"  {plane_name:10} {plane.duration_ms:8.1f}ms  ({plane.fairy_count} fairies)")
            lines.append("")
            
        # Postal system
        lines.append("POSTAL SYSTEM")
        lines.append("-" * 40)
        lines.append(f"  Registrations: {summary.postal_registrations}")
        lines.append(f"  Channels:      {len(summary.postal_channels_active)}")
        if summary.postal_channels_active:
            for ch in sorted(summary.postal_channels_active)[:20]:
                lines.append(f"    - {ch}")
            if len(summary.postal_channels_active) > 20:
                lines.append(f"    ... and {len(summary.postal_channels_active) - 20} more")
        lines.append("")
        
        # Threads
        lines.append("THREADS")
        lines.append("-" * 40)
        lines.append(f"  Created during boot: {summary.threads_created}")
        lines.append(f"  Active at end:       {summary.threads_at_end}")
        lines.append("")
        
        # Errors
        if summary.errors:
            lines.append("⚠  ERRORS")
            lines.append("-" * 40)
            for err in summary.errors:
                lines.append(f"  [{err['type']}] {err['source']}: {err['message']}")
            lines.append("")
            
        # Warnings
        if summary.warnings:
            lines.append("WARNINGS")
            lines.append("-" * 40)
            for warn in summary.warnings[:20]:
                lines.append(f"  - {warn}")
            lines.append("")
            
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MCP TOOL HELPER - For Claude to read results
    # ═══════════════════════════════════════════════════════════════════════════
    
    @classmethod
    def get_latest_observation(cls) -> Optional[Dict[str, Any]]:
        """Get the most recent boot observation summary."""
        log_dir = LOG_DIR
        if not log_dir.exists():
            return None
            
        # Find most recent summary file
        summaries = sorted(log_dir.glob(f"*_{SUMMARY_FILE}"), reverse=True)
        if not summaries:
            return None
            
        with open(summaries[0], 'r', encoding='utf-8') as f:
            return json.load(f)
            
    @classmethod
    def get_latest_events(cls, limit: int = 100) -> List[Dict[str, Any]]:
        """Get the most recent boot events from JSONL."""
        log_dir = LOG_DIR
        if not log_dir.exists():
            return []
            
        jsonl_files = sorted(log_dir.glob(f"*_{JSONL_FILE}"), reverse=True)
        if not jsonl_files:
            return []
            
        events = []
        with open(jsonl_files[0], 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
                    
        return events[-limit:] if limit else events


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE DECORATOR
# ═══════════════════════════════════════════════════════════════════════════════

def observed_fairy(cls):
    """
    Decorator to automatically observe a fairy class.
    
    Usage:
        @observed_fairy
        class MyFairy:
            ...
    """
    original_init = cls.__init__
    original_on_boot = getattr(cls, 'on_boot', None)
    
    @functools.wraps(original_init)
    def wrapped_init(self, *args, **kwargs):
        observer = BootObserver.get_instance()
        class_name = cls.__name__
        
        # Get actor_name if available
        actor_name = getattr(cls, 'ACTOR_NAME', '') or kwargs.get('actor_name', '')
        plane = getattr(cls, 'ACTOR_PLANE', '') or kwargs.get('plane', '')
        
        observer.on_fairy_init_start(class_name, actor_name, plane)
        try:
            result = original_init(self, *args, **kwargs)
            # Update actor_name from instance if not set
            if hasattr(self, 'ACTOR_NAME'):
                actor_name = self.ACTOR_NAME
            observer.on_fairy_init_end(class_name, success=True)
            return result
        except Exception as e:
            observer.on_fairy_init_end(class_name, success=False, error=str(e), tb=traceback.format_exc())
            raise
            
    if original_on_boot:
        @functools.wraps(original_on_boot)
        def wrapped_on_boot(self, *args, **kwargs):
            observer = BootObserver.get_instance()
            class_name = cls.__name__
            
            observer.on_fairy_boot_start(class_name)
            try:
                result = original_on_boot(self, *args, **kwargs)
                observer.on_fairy_boot_end(class_name, success=True)
                return result
            except Exception as e:
                observer.on_fairy_boot_end(class_name, success=False, error=str(e), tb=traceback.format_exc())
                raise
                
        cls.on_boot = wrapped_on_boot
        
    cls.__init__ = wrapped_init
    return cls


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def start_boot_observation():
    """Start boot observation (call at very beginning of boot)."""
    observer = BootObserver.get_instance()
    observer.start_observation()
    return observer
    
def finish_boot_observation():
    """Finish boot observation and write reports."""
    observer = BootObserver.get_instance()
    observer.finish_observation()
    return observer.write_summary()
    
def get_boot_observer() -> BootObserver:
    """Get the boot observer instance."""
    return BootObserver.get_instance()


if __name__ == "__main__":
    # Test the observer
    print("Testing BootObserver...")
    
    observer = start_boot_observation()
    
    # Simulate some boot events
    observer.on_plane_enter("P00")
    observer.on_fairy_init_start("TestFairy", "test.fairy", "P00")
    time.sleep(0.1)
    observer.on_fairy_init_end("TestFairy")
    observer.on_fairy_boot_start("TestFairy")
    time.sleep(0.05)
    observer.on_fairy_boot_end("TestFairy")
    observer.on_postal_register("test.fairy")
    observer.on_plane_exit("P00", 1)
    
    summary_path, report_path = finish_boot_observation()
    
    print(f"\nSummary: {summary_path}")
    print(f"Report: {report_path}")
