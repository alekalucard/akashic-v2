"""
Boot Profiler - Sandbox boot analysis for performance debugging

This module provides tools to:
1. Launch the Akashic system in an isolated subprocess
2. Capture detailed timing for every fairy and plane
3. Identify bottlenecks and slow boots
4. Generate reports for optimization

The profiler works by:
- Starting server.py in a subprocess with enhanced logging
- Capturing stdout/stderr in real-time
- Parsing boot events to build a timing profile
- Producing structured JSON and human-readable reports

Usage:
    from fairies.P00_Autonomic.nervous_system.boot_profiler import BootProfiler
    
    profiler = BootProfiler()
    result = profiler.run_profiled_boot(timeout=120)
    print(profiler.generate_report())

Version: 0.1.0
Author: Ace + Claude
"""

from __future__ import annotations

import os
import sys
import time
import json
import re
import subprocess
import threading
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════════
# BOOT EVENT TYPES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FairyBootEvent:
    """Timing data for a single fairy boot."""
    name: str
    plane: str
    class_name: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    status: str = "pending"  # pending, booting, success, timeout, error
    error_message: str = ""
    init_blocked_sec: float = 0.0  # Time blocked during __init__
    on_boot_blocked_sec: float = 0.0  # Time blocked during on_boot


@dataclass
class PlaneBootEvent:
    """Timing data for a plane boot."""
    plane: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    fairy_count: int = 0
    success_count: int = 0
    timeout_count: int = 0
    error_count: int = 0
    fairies: List[FairyBootEvent] = field(default_factory=list)
    

@dataclass 
class BootProfile:
    """Complete boot profile."""
    start_time: float = 0.0
    end_time: float = 0.0
    total_duration_sec: float = 0.0
    planes: Dict[str, PlaneBootEvent] = field(default_factory=dict)
    fairies: Dict[str, FairyBootEvent] = field(default_factory=dict)
    blocked_tunnels: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    slowest_fairies: List[Tuple[str, float]] = field(default_factory=list)
    hardware_info: Dict[str, Any] = field(default_factory=dict)
    success: bool = False
    error: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# BOOT LOG PARSER
# ═══════════════════════════════════════════════════════════════════════════════

class BootLogParser:
    """Parse boot-wave log output to extract timing data."""
    
    # Regex patterns for parsing boot-wave output
    PATTERNS = {
        "plane_enter": re.compile(r"\[boot-wave\] ENTER plane=(\w+)"),
        "plane_exit": re.compile(r"\[boot-wave\] .*plane=(\w+).*born=(\d+)"),
        "fairy_instantiating": re.compile(r"\[boot-wave\]\s+INSTANTIATING: (\w+)"),
        "fairy_instantiated": re.compile(r"\[boot-wave\]\s+INSTANTIATED: (\w+)"),
        "fairy_on_boot_start": re.compile(r"\[boot-wave\]\s+CALLING on_boot for (\w+)"),
        "fairy_on_boot_done": re.compile(r"\[boot-wave\]\s+>>> on_boot DONE: (\w+)"),
        "fairy_timeout": re.compile(r"\[boot-wave\]\s+⏰ TIMEOUT: (\w+)"),
        "fairy_error": re.compile(r"\[boot-wave\]\s+(?:INSTANTIATION ERROR|on_boot ERROR) for (\w+): (.+)"),
        "blocked_tunnel": re.compile(r" BLOCKED(?: TUNNEL)?: (.+)"),
        "cartographer_fairy": re.compile(r"\[(.+?)\] (?:✓|✗|⚠)?\s*(?:Subscribed|Loaded|Booted|Error|Failed)"),
        "collision": re.compile(r"Collision #(\d+) E:([\d.]+) R:([\d.]+)"),
        "worker_fail": re.compile(r"WORKER_START_FAIL"),
    }
    
    def __init__(self):
        self.profile = BootProfile()
        self._current_plane: Optional[str] = None
        self._current_fairy: Optional[str] = None
        self._fairy_start_times: Dict[str, float] = {}
        self._plane_start_times: Dict[str, float] = {}
        self._on_boot_start_times: Dict[str, float] = {}
        
    def parse_line(self, line: str, timestamp: float):
        """Parse a single log line and update the profile."""
        
        # Plane enter
        m = self.PATTERNS["plane_enter"].search(line)
        if m:
            plane = m.group(1)
            self._current_plane = plane
            self._plane_start_times[plane] = timestamp
            if plane not in self.profile.planes:
                self.profile.planes[plane] = PlaneBootEvent(plane=plane, start_time=timestamp)
            else:
                self.profile.planes[plane].start_time = timestamp
            return
            
        # Plane exit (with born count)
        m = self.PATTERNS["plane_exit"].search(line)
        if m:
            plane = m.group(1)
            born = int(m.group(2))
            if plane in self.profile.planes:
                self.profile.planes[plane].end_time = timestamp
                start = self._plane_start_times.get(plane, timestamp)
                self.profile.planes[plane].duration_ms = (timestamp - start) * 1000
                self.profile.planes[plane].fairy_count = born
            return
            
        # Fairy instantiating (start of __init__)
        m = self.PATTERNS["fairy_instantiating"].search(line)
        if m:
            fairy = m.group(1)
            self._current_fairy = fairy
            self._fairy_start_times[fairy] = timestamp
            if fairy not in self.profile.fairies:
                self.profile.fairies[fairy] = FairyBootEvent(
                    name=fairy,
                    plane=self._current_plane or "unknown",
                    class_name=fairy,
                    start_time=timestamp,
                    status="booting"
                )
            return
            
        # Fairy instantiated (end of __init__)
        m = self.PATTERNS["fairy_instantiated"].search(line)
        if m:
            fairy = m.group(1)
            if fairy in self.profile.fairies:
                start = self._fairy_start_times.get(fairy, timestamp)
                self.profile.fairies[fairy].init_blocked_sec = timestamp - start
            return
            
        # Fairy on_boot start
        m = self.PATTERNS["fairy_on_boot_start"].search(line)
        if m:
            fairy = m.group(1)
            self._on_boot_start_times[fairy] = timestamp
            return
            
        # Fairy on_boot done
        m = self.PATTERNS["fairy_on_boot_done"].search(line)
        if m:
            fairy = m.group(1)
            if fairy in self.profile.fairies:
                start = self._on_boot_start_times.get(fairy, timestamp)
                self.profile.fairies[fairy].on_boot_blocked_sec = timestamp - start
                self.profile.fairies[fairy].end_time = timestamp
                total_start = self._fairy_start_times.get(fairy, timestamp)
                self.profile.fairies[fairy].duration_ms = (timestamp - total_start) * 1000
                self.profile.fairies[fairy].status = "success"
                
                # Add to plane
                plane = self.profile.fairies[fairy].plane
                if plane in self.profile.planes:
                    self.profile.planes[plane].fairies.append(self.profile.fairies[fairy])
                    self.profile.planes[plane].success_count += 1
            return
            
        # Timeout
        m = self.PATTERNS["fairy_timeout"].search(line)
        if m:
            fairy = m.group(1)
            if fairy in self.profile.fairies:
                self.profile.fairies[fairy].status = "timeout"
                self.profile.fairies[fairy].end_time = timestamp
                plane = self.profile.fairies[fairy].plane
                if plane in self.profile.planes:
                    self.profile.planes[plane].timeout_count += 1
            return
            
        # Error
        m = self.PATTERNS["fairy_error"].search(line)
        if m:
            fairy = m.group(1)
            error = m.group(2) if len(m.groups()) > 1 else "unknown error"
            if fairy in self.profile.fairies:
                self.profile.fairies[fairy].status = "error"
                self.profile.fairies[fairy].error_message = error
                self.profile.fairies[fairy].end_time = timestamp
                plane = self.profile.fairies[fairy].plane
                if plane in self.profile.planes:
                    self.profile.planes[plane].error_count += 1
            return
            
        # Blocked tunnel
        m = self.PATTERNS["blocked_tunnel"].search(line)
        if m:
            self.profile.blocked_tunnels.append(m.group(1))
            return
            
        # Worker fail
        if self.PATTERNS["worker_fail"].search(line):
            self.profile.warnings.append(f"WORKER_START_FAIL detected: {line.strip()[:100]}")
            return
    
    def finalize(self):
        """Finalize the profile after parsing is complete."""
        # Calculate total duration
        if self.profile.planes:
            starts = [p.start_time for p in self.profile.planes.values() if p.start_time > 0]
            ends = [p.end_time for p in self.profile.planes.values() if p.end_time > 0]
            if starts and ends:
                self.profile.start_time = min(starts)
                self.profile.end_time = max(ends)
                self.profile.total_duration_sec = self.profile.end_time - self.profile.start_time
                
        # Find slowest fairies
        fairy_times = [(f.name, f.duration_ms) for f in self.profile.fairies.values() if f.duration_ms > 0]
        fairy_times.sort(key=lambda x: x[1], reverse=True)
        self.profile.slowest_fairies = fairy_times[:10]
        
        # Determine overall success
        total_fairies = len(self.profile.fairies)
        success_fairies = sum(1 for f in self.profile.fairies.values() if f.status == "success")
        self.profile.success = (success_fairies / total_fairies > 0.8) if total_fairies > 0 else False
        

# ═══════════════════════════════════════════════════════════════════════════════
# BOOT PROFILER
# ═══════════════════════════════════════════════════════════════════════════════

class BootProfiler:
    """
    Runs the Akashic boot in an isolated subprocess and profiles it.
    
    This allows us to:
    - Test boot without affecting the current process
    - Capture precise timing data
    - Detect hangs and timeouts
    - Generate optimization recommendations
    """
    
    def __init__(self, project_root: Optional[str] = None):
        """
        Args:
            project_root: Path to the Akashic project root. Auto-detected if not provided.
        """
        if project_root:
            self.project_root = Path(project_root)
        else:
            # Auto-detect from current file location
            self.project_root = Path(__file__).parent.parent.parent
            
        self.python_exe = sys.executable
        self.profile: Optional[BootProfile] = None
        self._process: Optional[subprocess.Popen] = None
        self._output_lines: List[Tuple[float, str]] = []
        
    def run_profiled_boot(self, timeout: int = 120, capture_output: bool = True) -> BootProfile:
        """
        Run a profiled boot of the Akashic system.
        
        Args:
            timeout: Maximum time to wait for boot (seconds)
            capture_output: Whether to capture and parse output
            
        Returns:
            BootProfile with timing data
        """
        parser = BootLogParser()
        start_time = time.time()
        
        # Build the boot command
        boot_script = self.project_root / "server.py"
        if not boot_script.exists():
            boot_script = self.project_root / "P60_Executive" / "ebookmain" / "ebookmain.py"  # v1 fallback

        if not boot_script.exists():
            parser.profile.error = f"Boot script not found: {boot_script}"
            return parser.profile
            
        # Run in subprocess
        env = os.environ.copy()
        env["AKASHIC_ROOT"] = str(self.project_root)
        env["PYTHONPATH"] = str(self.project_root)
        env["AKASHIC_BOOT_PROFILE"] = "1"  # Signal to server.py for enhanced logging
        
        try:
            self._process = subprocess.Popen(
                [self.python_exe, str(boot_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(self.project_root),
                env=env,
                text=True,
                bufsize=1,  # Line buffered
            )
            
            # Read output in real-time
            output_thread = threading.Thread(
                target=self._read_output,
                args=(parser,),
                daemon=True
            )
            output_thread.start()
            
            # Wait for process or timeout
            try:
                self._process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                parser.profile.error = f"Boot timed out after {timeout}s"
                parser.profile.warnings.append("Process killed due to timeout")
                self._process.kill()
                self._process.wait()
                
            # Wait for output thread to finish
            output_thread.join(timeout=5)
            
        except Exception as e:
            parser.profile.error = f"Failed to start boot: {e}"
            
        # Finalize profile
        parser.finalize()
        parser.profile.end_time = time.time()
        if parser.profile.start_time == 0:
            parser.profile.start_time = start_time
        parser.profile.total_duration_sec = parser.profile.end_time - parser.profile.start_time
        
        # Get hardware info
        parser.profile.hardware_info = self._get_hardware_info()
        
        self.profile = parser.profile
        return self.profile
        
    def _read_output(self, parser: BootLogParser):
        """Read process output and parse it."""
        try:
            for line in self._process.stdout:
                timestamp = time.time()
                self._output_lines.append((timestamp, line))
                parser.parse_line(line, timestamp)
                # Also print to console for visibility
                print(line, end="", flush=True)
        except Exception as e:
            parser.profile.warnings.append(f"Output read error: {e}")
            
    def _get_hardware_info(self) -> Dict[str, Any]:
        """Get basic hardware info for the profile."""
        info = {
            "python_version": sys.version,
            "platform": sys.platform,
        }
        
        try:
            import psutil
            info["cpu_count"] = psutil.cpu_count()
            info["memory_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)
        except ImportError:
            pass
            
        try:
            # Check for CUDA
            import torch
            if torch.cuda.is_available():
                info["cuda_available"] = True
                info["cuda_device"] = torch.cuda.get_device_name(0)
                info["cuda_memory_gb"] = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1)
            else:
                info["cuda_available"] = False
        except ImportError:
            info["cuda_available"] = "unknown (torch not installed)"
            
        return info
        
    def generate_report(self, format: str = "text") -> str:
        """
        Generate a human-readable report from the profile.
        
        Args:
            format: "text" or "json"
            
        Returns:
            Formatted report string
        """
        if not self.profile:
            return "No profile data available. Run run_profiled_boot() first."
            
        if format == "json":
            return json.dumps(asdict(self.profile), indent=2, default=str)
            
        # Text format
        lines = []
        lines.append("=" * 70)
        lines.append("AKASHIC BOOT PROFILE REPORT")
        lines.append("=" * 70)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Total Duration: {self.profile.total_duration_sec:.1f}s")
        lines.append(f"Status: {'✅ SUCCESS' if self.profile.success else '❌ ISSUES DETECTED'}")
        lines.append("")
        
        # Hardware
        lines.append("─" * 40)
        lines.append("HARDWARE")
        lines.append("─" * 40)
        for k, v in self.profile.hardware_info.items():
            lines.append(f"  {k}: {v}")
        lines.append("")
        
        # Plane summary
        lines.append("─" * 40)
        lines.append("PLANE SUMMARY")
        lines.append("─" * 40)
        for plane_name in ["P00", "P10", "P20", "P30", "P40", "P50", "P60"]:
            if plane_name in self.profile.planes:
                p = self.profile.planes[plane_name]
                status = "✅" if p.error_count == 0 and p.timeout_count == 0 else "⚠"
                lines.append(f"  {status} {plane_name}: {p.duration_ms:.0f}ms "
                           f"({p.success_count}/{p.fairy_count} fairies)")
                if p.timeout_count > 0:
                    lines.append(f"      ⏰ {p.timeout_count} timeouts")
                if p.error_count > 0:
                    lines.append(f"      ❌ {p.error_count} errors")
        lines.append("")
        
        # Slowest fairies
        lines.append("─" * 40)
        lines.append("SLOWEST FAIRIES (top 10)")
        lines.append("─" * 40)
        for name, duration_ms in self.profile.slowest_fairies:
            duration_sec = duration_ms / 1000
            bar = "█" * min(int(duration_sec * 2), 40)
            lines.append(f"  {name:40} {duration_ms:8.0f}ms  {bar}")
        lines.append("")
        
        # Blocked tunnels
        if self.profile.blocked_tunnels:
            lines.append("─" * 40)
            lines.append("⚠ BLOCKED TUNNELS")
            lines.append("─" * 40)
            for tunnel in self.profile.blocked_tunnels:
                lines.append(f"   {tunnel}")
            lines.append("")
            
        # Warnings
        if self.profile.warnings:
            lines.append("─" * 40)
            lines.append("WARNINGS")
            lines.append("─" * 40)
            for warning in self.profile.warnings:
                lines.append(f"  ⚠ {warning}")
            lines.append("")
            
        # Recommendations
        lines.append("─" * 40)
        lines.append("RECOMMENDATIONS")
        lines.append("─" * 40)
        recommendations = self._generate_recommendations()
        for rec in recommendations:
            lines.append(f"  → {rec}")
            
        lines.append("")
        lines.append("=" * 70)
        
        return "\n".join(lines)
        
    def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations based on the profile."""
        recs = []
        
        if not self.profile:
            return ["No profile data available"]
            
        # Slow fairies
        for name, duration_ms in self.profile.slowest_fairies[:3]:
            if duration_ms > 5000:
                recs.append(f"Optimize {name} - taking {duration_ms/1000:.1f}s (defer heavy init to background)")
                
        # Blocked tunnels
        if self.profile.blocked_tunnels:
            recs.append("Investigate blocked tunnels - may indicate infinite loops or deadlocks")
            
        # Timeouts
        timeout_count = sum(1 for f in self.profile.fairies.values() if f.status == "timeout")
        if timeout_count > 0:
            recs.append(f"Fix {timeout_count} timeout(s) - fairies taking >5s in __init__")
            
        # Worker failures
        worker_fails = sum(1 for w in self.profile.warnings if "WORKER_START_FAIL" in w)
        if worker_fails > 0:
            recs.append(f"Fix {worker_fails} worker start failure(s) - check to_TRACER binding")
            
        # Hardware
        hw = self.profile.hardware_info
        if hw.get("cuda_available") is False:
            recs.append("Enable CUDA for acceleration (CudaFairy and HardwareFairy)")
            
        if not recs:
            recs.append("Boot looks healthy! Consider enabling hardware acceleration for performance.")
            
        return recs
        
    def stop(self):
        """Stop the profiled boot if running."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            time.sleep(0.5)
            if self._process.poll() is None:
                self._process.kill()


# ═══════════════════════════════════════════════════════════════════════════════
# QUICK BOOT TEST (for MCP tool)
# ═══════════════════════════════════════════════════════════════════════════════

def run_quick_boot_test(timeout: int = 60) -> Dict[str, Any]:
    """
    Run a quick boot test and return results as a dict.
    
    This is the function called by the MCP tool.
    """
    profiler = BootProfiler()
    profile = profiler.run_profiled_boot(timeout=timeout)
    
    return {
        "success": profile.success,
        "total_duration_sec": round(profile.total_duration_sec, 1),
        "planes": {
            name: {
                "duration_ms": round(p.duration_ms, 0),
                "fairy_count": p.fairy_count,
                "success_count": p.success_count,
                "timeout_count": p.timeout_count,
                "error_count": p.error_count,
            }
            for name, p in profile.planes.items()
        },
        "slowest_fairies": [
            {"name": n, "duration_ms": round(d, 0)} 
            for n, d in profile.slowest_fairies[:5]
        ],
        "blocked_tunnels": profile.blocked_tunnels,
        "warnings": profile.warnings[:5],
        "error": profile.error,
        "hardware": profile.hardware_info,
        "report": profiler.generate_report(),
    }


def get_boot_status_from_cartographer() -> Dict[str, Any]:
    """
    Get current boot status from CartographerFairy if available.
    
    This reads the in-memory state without running a new boot.
    """
    try:
        from fairies.P00_Autonomic.nervous_system.cartographer_fairy import get_cartographer
        carto = get_cartographer()
        if carto and hasattr(carto, 'topology'):
            topo = carto.topology
            return {
                "available": True,
                "planes": {
                    name: {
                        "entered": ps.entered,
                        "exited": ps.exited,
                        "expected": ps.expected_fairies,
                        "booted": ps.booted_fairies,
                        "blocked": ps.blocked,
                    }
                    for name, ps in topo.planes.items()
                },
                "fairies": {
                    name: {
                        "booted": fs.booted,
                        "duration_ms": fs.boot_duration_ms,
                        "error": fs.error,
                    }
                    for name, fs in topo.fairies.items()
                },
                "blocked_tunnels": topo.blocked_tunnels,
            }
    except Exception as e:
        return {"available": False, "error": str(e)}
        
    return {"available": False, "error": "CartographerFairy not found"}


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Profile Akashic boot sequence")
    parser.add_argument("--timeout", type=int, default=120, help="Boot timeout in seconds")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    args = parser.parse_args()
    
    profiler = BootProfiler()
    print(f"\n[GO] Starting profiled boot (timeout: {args.timeout}s)...\n")
    print("=" * 70)
    
    profile = profiler.run_profiled_boot(timeout=args.timeout)
    
    print("\n" + "=" * 70)
    print(profiler.generate_report(format=args.format))
