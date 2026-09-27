"""
Boot Observer MCP Tools - Let Claude analyze boot processes.

These tools provide access to boot observation data:
- Read the latest boot summary
- Get boot events
- Compare boot runs
- Identify issues

Register with: register_boot_observer_tools(mcp)
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# Add parent path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Boot observation log directory
BOOT_LOG_DIR = Path(__file__).parent.parent.parent / "boot_logs"


def register_boot_observer_tools(mcp):
    """Register all boot observer tools with the MCP server."""
    
    @mcp.tool()
    def boot_get_latest_summary() -> str:
        """
        Get the most recent boot observation summary.
        
        Returns comprehensive boot analysis:
        - Total fairies found/booted/failed
        - Slowest fairies (bottlenecks)
        - Plane-by-plane breakdown
        - Errors and warnings
        - Postal system stats
        
        Returns:
            JSON with boot summary or error message
        """
        try:
            if not BOOT_LOG_DIR.exists():
                return json.dumps({
                    "error": "No boot logs found",
                    "hint": "Run a boot with BootObserver enabled first. Add to server.py:\n  from fairies.P00_Autonomic.nervous_system.boot_observer import start_boot_observation\n  start_boot_observation()"
                })
                
            # Find most recent summary file
            summaries = sorted(BOOT_LOG_DIR.glob("*_boot_observation_summary.json"), reverse=True)
            if not summaries:
                return json.dumps({
                    "error": "No boot summaries found",
                    "log_dir": str(BOOT_LOG_DIR),
                    "files": [f.name for f in BOOT_LOG_DIR.iterdir()][:20]
                })
                
            with open(summaries[0], 'r', encoding='utf-8') as f:
                summary = json.load(f)
                
            return json.dumps({
                "file": summaries[0].name,
                "summary": summary
            }, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def boot_get_events(limit: int = 100, event_type: str = "") -> str:
        """
        Get boot events from the most recent observation.
        
        Args:
            limit: Maximum events to return (default 100)
            event_type: Filter by type (fairy_init_start, fairy_boot_end, error, etc.)
        
        Returns:
            JSON list of boot events
        """
        try:
            if not BOOT_LOG_DIR.exists():
                return json.dumps({"error": "No boot logs found"})
                
            # Find most recent JSONL file
            jsonl_files = sorted(BOOT_LOG_DIR.glob("*_boot_observation.jsonl"), reverse=True)
            if not jsonl_files:
                return json.dumps({"error": "No boot event logs found"})
                
            events = []
            with open(jsonl_files[0], 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        event = json.loads(line)
                        # Filter by type if specified
                        if event_type and event.get("t") != event_type:
                            continue
                        events.append(event)
                        
            # Return last N events
            return json.dumps({
                "file": jsonl_files[0].name,
                "total_events": len(events),
                "events": events[-limit:] if limit else events
            }, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def boot_get_failures() -> str:
        """
        Get all boot failures from the most recent observation.
        
        Returns:
            JSON with failed fairies, timeouts, errors, and blocked tunnels
        """
        try:
            if not BOOT_LOG_DIR.exists():
                return json.dumps({"error": "No boot logs found"})
                
            # Get summary
            summaries = sorted(BOOT_LOG_DIR.glob("*_boot_observation_summary.json"), reverse=True)
            if not summaries:
                return json.dumps({"error": "No boot summaries found"})
                
            with open(summaries[0], 'r', encoding='utf-8') as f:
                summary = json.load(f)
                
            failures = {
                "observation_id": summary.get("observation_id"),
                "failed_fairies": summary.get("fairies_by_status", {}).get("failed", []),
                "timeout_fairies": summary.get("fairies_by_status", {}).get("timeout", []),
                "errors": summary.get("errors", []),
                "warnings": summary.get("warnings", []),
                "blocked_tunnels": summary.get("blocked_tunnels", []),
                "counts": {
                    "failed": summary.get("total_fairies_failed", 0),
                    "timeout": summary.get("total_fairies_timeout", 0),
                    "errors": len(summary.get("errors", [])),
                }
            }
            
            return json.dumps(failures, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def boot_get_slowest(n: int = 15) -> str:
        """
        Get the N slowest fairies from boot (bottleneck analysis).
        
        Args:
            n: Number of slow fairies to return (default 15)
        
        Returns:
            JSON with slowest fairies and their timings
        """
        try:
            if not BOOT_LOG_DIR.exists():
                return json.dumps({"error": "No boot logs found"})
                
            summaries = sorted(BOOT_LOG_DIR.glob("*_boot_observation_summary.json"), reverse=True)
            if not summaries:
                return json.dumps({"error": "No boot summaries found"})
                
            with open(summaries[0], 'r', encoding='utf-8') as f:
                summary = json.load(f)
                
            slowest = summary.get("slowest_fairies", [])[:int(n)]  # FIX 2026-06-10: coerce MCP str-arg
            total_slow_time = sum(f.get("total_ms", 0) for f in slowest)
            boot_duration = summary.get("duration_sec", 0) * 1000
            
            return json.dumps({
                "observation_id": summary.get("observation_id"),
                "boot_duration_ms": boot_duration,
                "slowest_combined_ms": total_slow_time,
                "percentage_of_boot": f"{(total_slow_time / boot_duration * 100):.1f}%" if boot_duration > 0 else "N/A",
                "slowest_fairies": slowest
            }, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def boot_get_plane_breakdown() -> str:
        """
        Get boot times broken down by plane.
        
        Returns:
            JSON with plane-by-plane boot analysis
        """
        try:
            if not BOOT_LOG_DIR.exists():
                return json.dumps({"error": "No boot logs found"})
                
            summaries = sorted(BOOT_LOG_DIR.glob("*_boot_observation_summary.json"), reverse=True)
            if not summaries:
                return json.dumps({"error": "No boot summaries found"})
                
            with open(summaries[0], 'r', encoding='utf-8') as f:
                summary = json.load(f)
                
            planes = summary.get("planes", {})
            plane_list = []
            for name, data in sorted(planes.items()):
                plane_list.append({
                    "plane": name,
                    "duration_ms": data.get("duration_ms", 0),
                    "fairy_count": data.get("fairy_count", 0),
                    "success": data.get("success_count", 0),
                    "failed": data.get("failed_count", 0),
                })
                
            return json.dumps({
                "observation_id": summary.get("observation_id"),
                "total_duration_sec": summary.get("duration_sec", 0),
                "planes": plane_list
            }, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def boot_list_observations(limit: int = 10) -> str:
        """
        List available boot observations.
        
        Args:
            limit: Maximum observations to list (default 10)
        
        Returns:
            JSON list of observation files with basic stats
        """
        try:
            if not BOOT_LOG_DIR.exists():
                return json.dumps({
                    "error": "No boot logs directory",
                    "expected_path": str(BOOT_LOG_DIR)
                })
                
            summaries = sorted(BOOT_LOG_DIR.glob("*_boot_observation_summary.json"), reverse=True)[:int(limit)]  # FIX 2026-06-10: coerce MCP str-limit
            
            observations = []
            for summary_file in summaries:
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    observations.append({
                        "id": data.get("observation_id"),
                        "host": data.get("host"),
                        "duration_sec": data.get("duration_sec", 0),
                        "fairies_found": data.get("total_fairies_found", 0),
                        "fairies_booted": data.get("total_fairies_booted", 0),
                        "fairies_failed": data.get("total_fairies_failed", 0),
                        "errors": len(data.get("errors", [])),
                    })
                except Exception:
                    continue
                    
            return json.dumps({
                "count": len(observations),
                "observations": observations
            }, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def boot_get_registration_status() -> str:
        """
        Get postal system registration status from boot.
        
        Shows which fairies registered vs which were expected.
        
        Returns:
            JSON with registration analysis
        """
        try:
            if not BOOT_LOG_DIR.exists():
                return json.dumps({"error": "No boot logs found"})
                
            summaries = sorted(BOOT_LOG_DIR.glob("*_boot_observation_summary.json"), reverse=True)
            if not summaries:
                return json.dumps({"error": "No boot summaries found"})
                
            with open(summaries[0], 'r', encoding='utf-8') as f:
                summary = json.load(f)
                
            by_status = summary.get("fairies_by_status", {})
            
            return json.dumps({
                "observation_id": summary.get("observation_id"),
                "postal_registrations": summary.get("postal_registrations", 0),
                "active_channels": summary.get("postal_channels_active", []),
                "registered_fairies": by_status.get("registered", []),
                "booted_not_registered": by_status.get("booted", []),
                "initialized_only": by_status.get("initialized", []),
                "importing": by_status.get("importing", []),
                "unknown": by_status.get("unknown", []),
            }, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def boot_read_report() -> str:
        """
        Read the human-readable boot report.
        
        Returns the full text report for easy reading.
        
        Returns:
            Plain text boot report
        """
        try:
            if not BOOT_LOG_DIR.exists():
                return "No boot logs directory found"
                
            reports = sorted(BOOT_LOG_DIR.glob("*_boot_observation_report.txt"), reverse=True)
            if not reports:
                return "No boot reports found"
                
            with open(reports[0], 'r', encoding='utf-8') as f:
                return f.read()
                
        except Exception as e:
            return f"Error reading report: {e}"
    
    @mcp.tool()
    def boot_compare_runs(observation_id_1: str = "", observation_id_2: str = "") -> str:
        """
        Compare two boot runs.
        
        Args:
            observation_id_1: First observation ID (default: most recent)
            observation_id_2: Second observation ID (default: second most recent)
        
        Returns:
            JSON comparison of two boot runs
        """
        try:
            if not BOOT_LOG_DIR.exists():
                return json.dumps({"error": "No boot logs found"})
                
            summaries = sorted(BOOT_LOG_DIR.glob("*_boot_observation_summary.json"), reverse=True)
            if len(summaries) < 2:
                return json.dumps({"error": "Need at least 2 boot observations to compare"})
            
            # Find the two files
            def find_summary(obs_id: str):
                if not obs_id:
                    return None
                for s in summaries:
                    if obs_id in s.name:
                        return s
                return None
            
            file1 = find_summary(observation_id_1) or summaries[0]
            file2 = find_summary(observation_id_2) or summaries[1]
            
            with open(file1, 'r') as f:
                run1 = json.load(f)
            with open(file2, 'r') as f:
                run2 = json.load(f)
                
            # Compare
            comparison = {
                "run1": {
                    "id": run1.get("observation_id"),
                    "duration_sec": run1.get("duration_sec", 0),
                    "fairies_found": run1.get("total_fairies_found", 0),
                    "fairies_booted": run1.get("total_fairies_booted", 0),
                    "fairies_failed": run1.get("total_fairies_failed", 0),
                    "registrations": run1.get("postal_registrations", 0),
                },
                "run2": {
                    "id": run2.get("observation_id"),
                    "duration_sec": run2.get("duration_sec", 0),
                    "fairies_found": run2.get("total_fairies_found", 0),
                    "fairies_booted": run2.get("total_fairies_booted", 0),
                    "fairies_failed": run2.get("total_fairies_failed", 0),
                    "registrations": run2.get("postal_registrations", 0),
                },
                "changes": {
                    "duration_change_sec": run1.get("duration_sec", 0) - run2.get("duration_sec", 0),
                    "fairies_change": run1.get("total_fairies_found", 0) - run2.get("total_fairies_found", 0),
                    "failures_change": run1.get("total_fairies_failed", 0) - run2.get("total_fairies_failed", 0),
                }
            }
            
            # Find new failures
            failures1 = set(run1.get("fairies_by_status", {}).get("failed", []))
            failures2 = set(run2.get("fairies_by_status", {}).get("failed", []))
            comparison["new_failures"] = list(failures1 - failures2)
            comparison["fixed_failures"] = list(failures2 - failures1)
            
            return json.dumps(comparison, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e)})

    # =========================================================================
    # LIVE LOG ANALYSIS - Read and analyze state/boot_live.log in real-time
    # FIX 2026-02-13: Nous kept getting stuck in old logs. This tool reads
    # the ACTUAL live log and auto-flags errors/warnings/deaths/restarts.
    # =========================================================================

    LIVE_LOG = Path(__file__).parent.parent.parent.parent / "state" / "boot_live.log"
    PREV_LOG = Path(__file__).parent.parent.parent.parent / "state" / "boot_live_prev.log"

    # Patterns that indicate problems (scored by severity)
    _ERROR_PATTERNS = {
        # CRITICAL (score 3) - things that break functionality
        "FAIRY DEATH": 3,
        "Traceback": 3,
        "CRITICAL": 3,
        "FATAL": 3,
        "crashed": 3,
        "segfault": 3,
        "MemoryError": 3,

        # HIGH (score 2) - things that need attention
        "Error": 2,
        "ERROR": 2,
        "Exception": 2,
        "failed": 2,
        "Attempting to restart": 2,
        "DEATH DETECTED": 2,
        "AttributeError": 2,
        "TypeError": 2,
        "ImportError": 2,
        "KeyError": 2,
        "ModuleNotFoundError": 2,
        "NoneType": 2,
        "No fairy_instance": 2,

        # MEDIUM (score 1) - things worth knowing about
        "WARNING": 1,
        "Warning": 1,
        "timeout": 1,
        "timed out": 1,
        "Silent for": 1,
        "not found": 1,
        "not available": 1,
        "skipping": 1,
        "DISABLED": 1,
        "Access is denied": 1,
    }

    # Patterns to IGNORE (known noise, not real problems)
    _IGNORE_PATTERNS = [
        "SetProcessDpiAwarenessContext",  # Qt DPI warning, cosmetic
        "qt.qpa.window",                 # Qt window warning, cosmetic
        "Qt's default DPI",              # Qt follow-up message
        "QApplication was not created in the main",  # Qt thread warning
        "ThoughtChainEngine not available",  # Expected when no RWKV
        "DISABLED per Ace",              # Intentionally disabled features
        "sifting DISABLED",              # Intentionally disabled
        "PyCUDA",                        # Optional GPU stuff
        "UserWarning",                   # Python user warnings (usually benign)
    ]

    @mcp.tool()
    def analyze_boot_log(tail_lines: int = 0, show_all: bool = False) -> str:
        """
        Analyze the live boot log for errors, warnings, and problems.

        This reads state/boot_live.log (written in real-time by server.py)
        and returns a smart summary of everything that needs attention.

        Use this instead of manually reading log files!

        Args:
            tail_lines: If > 0, only analyze the last N lines (default: all)
            show_all: If True, include all flagged lines. If False, deduplicate.

        Returns:
            JSON with:
            - boot_age: How long ago the boot started
            - total_lines: Lines in the log
            - critical: Lines with critical issues (score 3)
            - errors: Lines with errors (score 2)
            - warnings: Lines with warnings (score 1)
            - fairy_deaths: Any fairy death events
            - restart_attempts: Any UMF restart attempts
            - stderr_lines: Lines that came from stderr
            - summary: Human-readable summary
        """
        try:
            if not LIVE_LOG.exists():
                return json.dumps({"error": "No boot_live.log found. Is server.py running?",
                                   "hint": "The log is at state/boot_live.log"})

            # Read log
            try:
                with open(LIVE_LOG, 'r', encoding='utf-8', errors='replace') as f:
                    all_lines = f.readlines()
            except Exception as e:
                return json.dumps({"error": f"Cannot read log: {e}"})

            if tail_lines > 0:
                lines = all_lines[-tail_lines:]
            else:
                lines = all_lines

            # Parse boot timestamp
            boot_age_str = "unknown"
            import time as _time
            for line in all_lines[:3]:
                if "BOOT STARTED:" in line:
                    try:
                        ts = float(line.split("BOOT STARTED:")[1].strip().rstrip("=").strip())
                        age = _time.time() - ts
                        if age < 120:
                            boot_age_str = f"{age:.0f}s ago"
                        elif age < 7200:
                            boot_age_str = f"{age/60:.1f}min ago"
                        else:
                            boot_age_str = f"{age/3600:.1f}hrs ago"
                    except Exception:
                        pass

            # Classify lines
            critical = []
            errors = []
            warnings = []
            fairy_deaths = []
            restart_attempts = []
            stderr_lines = []
            seen_msgs = set()  # Dedup

            for i, raw_line in enumerate(lines):
                line = raw_line.strip()
                if not line:
                    continue

                # Check ignore patterns first
                if any(ign in line for ign in _IGNORE_PATTERNS):
                    continue

                # Track stderr lines
                if line.startswith("[STDERR]"):
                    stderr_lines.append({"line": len(all_lines) - len(lines) + i + 1, "text": line[:200]})

                # Special: fairy deaths
                if "FAIRY DEATH" in line or "DEATH DETECTED" in line:
                    fairy_deaths.append({"line": len(all_lines) - len(lines) + i + 1, "text": line[:200]})

                # Special: restart attempts
                if "Attempting to restart" in line or "restart attempt" in line.lower():
                    restart_attempts.append({"line": len(all_lines) - len(lines) + i + 1, "text": line[:200]})

                # Score the line
                max_score = 0
                matched_pattern = None
                for pattern, score in _ERROR_PATTERNS.items():
                    if pattern in line:
                        if score > max_score:
                            max_score = score
                            matched_pattern = pattern

                if max_score > 0:
                    # Dedup: skip if we've seen a very similar message
                    dedup_key = line[:80] if not show_all else f"{i}:{line[:80]}"
                    if dedup_key in seen_msgs and not show_all:
                        continue
                    seen_msgs.add(dedup_key)

                    entry = {
                        "line": len(all_lines) - len(lines) + i + 1,
                        "pattern": matched_pattern,
                        "text": line[:200]
                    }

                    if max_score >= 3:
                        critical.append(entry)
                    elif max_score >= 2:
                        errors.append(entry)
                    else:
                        warnings.append(entry)

            # Build summary
            summary_parts = []
            if not critical and not errors and not fairy_deaths:
                summary_parts.append("✅ Boot looks clean — no critical issues or errors found.")
            else:
                if fairy_deaths:
                    summary_parts.append(f"💀 {len(fairy_deaths)} FAIRY DEATH(s)")
                if restart_attempts:
                    summary_parts.append(f"🔄 {len(restart_attempts)} restart attempt(s)")
                if critical:
                    summary_parts.append(f"🔴 {len(critical)} CRITICAL issue(s)")
                if errors:
                    summary_parts.append(f"🟠 {len(errors)} error(s)")
            if warnings:
                summary_parts.append(f"🟡 {len(warnings)} warning(s)")
            if stderr_lines:
                summary_parts.append(f"📝 {len(stderr_lines)} stderr line(s)")
            summary_parts.append(f"📋 {len(all_lines)} total lines, boot started {boot_age_str}")

            result = {
                "boot_age": boot_age_str,
                "total_lines": len(all_lines),
                "summary": " | ".join(summary_parts),
                "fairy_deaths": fairy_deaths,
                "restart_attempts": restart_attempts,
                "critical": critical[:20],  # Cap at 20 to avoid huge responses
                "errors": errors[:30],
                "warnings": warnings[:20],
                "stderr_lines": stderr_lines[:15],
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def read_boot_log_tail(lines: int = 50) -> str:
        """
        Read the last N lines of the live boot log.

        Simple tail of state/boot_live.log. Use analyze_boot_log for
        smart analysis, use this for raw recent output.

        Args:
            lines: Number of lines from the end (default 50, max 500)

        Returns:
            Raw text of the last N lines
        """
        try:
            if not LIVE_LOG.exists():
                return "No boot_live.log found. Is server.py running?"

            lines = min(lines, 500)
            with open(LIVE_LOG, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()

            tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return f"[boot_live.log — {len(all_lines)} total lines, showing last {len(tail)}]\n" + "".join(tail)

        except Exception as e:
            return f"Error reading log: {e}"

    @mcp.tool()
    def search_boot_log(pattern: str, context: int = 2) -> str:
        """
        Search the live boot log for a pattern.

        Searches state/boot_live.log for lines matching the pattern
        and returns them with surrounding context.

        Args:
            pattern: Text to search for (case-insensitive)
            context: Lines of context before and after each match (default 2)

        Returns:
            Matching lines with context
        """
        try:
            if not LIVE_LOG.exists():
                return "No boot_live.log found."

            import re
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error:
                # If pattern isn't valid regex, use literal search
                regex = re.compile(re.escape(pattern), re.IGNORECASE)

            with open(LIVE_LOG, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()

            matches = []
            for i, line in enumerate(all_lines):
                if regex.search(line):
                    matches.append(i)

            if not matches:
                return f"No matches for '{pattern}' in {len(all_lines)} lines."

            # Build output with context
            output_parts = [f"Found {len(matches)} match(es) for '{pattern}':\n"]
            shown = set()
            for match_idx in matches[:30]:  # Cap at 30 matches
                start = max(0, match_idx - context)
                end = min(len(all_lines), match_idx + context + 1)
                for j in range(start, end):
                    if j not in shown:
                        marker = ">>>" if j == match_idx else "   "
                        output_parts.append(f"{marker} {j+1:5d}: {all_lines[j].rstrip()}")
                        shown.add(j)
                output_parts.append("   ---")

            return "\n".join(output_parts)

        except Exception as e:
            return f"Error: {e}"

    # ═══ Boot Digest (from boot_watcher.py) ═══

    DIGEST_FILE = Path(__file__).parent.parent.parent.parent / "state" / "boot_digest.json"

    @mcp.tool()
    def boot_watch_digest() -> str:
        """
        Get the most recent boot digest from boot_watcher.py.

        The boot watcher monitors boot_full.log in real-time and produces
        a structured digest with GPU status, fairy counts, errors, slow
        operations, guild wiring status, and a health score.

        Launch the watcher:  python tools/boot_watcher.py
        Or analyze existing:  python tools/boot_watcher.py --analyze

        Returns:
            JSON with boot digest or hint if no digest exists
        """
        try:
            if DIGEST_FILE.exists():
                return DIGEST_FILE.read_text(encoding="utf-8")
            return json.dumps({
                "status": "no_digest",
                "hint": "Run: python tools/boot_watcher.py --analyze  (or launch before boot)"
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    sys.stderr.write("[MCP]  Boot observer tools loaded (with live log analysis)\n")
